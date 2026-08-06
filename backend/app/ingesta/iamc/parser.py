"""Orquestación página → sección → filas del informe diario de IAMC.

Recorre las páginas del PDF, clasifica el título de cada una contra el catálogo de
`secciones.py`, arma las filas por sección aplicando ley y moneda de pago según lo que la sección
declara, mide cobertura y **aborta con `InformeInvalido` ante cualquier sección o fila no
reconocida, sin devolver filas parciales** — es preferible no tener el informe del día a tener uno
a medias que nadie sabe que está incompleto (CLAUDE.md, regla 1).

La iteración de páginas de pdfplumber está separada de la lógica de secciones (`_procesar_paginas`
trabaja sobre tuplas planas, no sobre objetos de pdfplumber) justamente para poder testear el
aborto con páginas sintéticas, sin fabricar un PDF.
"""

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from typing import TypedDict

import pdfplumber
import structlog

from app.ingesta.alertas import Alerta, Severidad, formato_inesperado
from app.ingesta.cobertura import medir_cobertura
from app.ingesta.snapshot import Snapshot

from .normalizacion import _fecha, _ley, _numero, _texto
from .secciones import GRAFICO_PREFIJOS, SECCIONES, OrigenDato, Seccion
from .tablas import FilaCruda, FilaNoReconocida, TablaPagina, extraer_tabla_pagina

logger = structlog.get_logger()

FUENTE = "IAMC"

CODIGO_DISCREPANCIA_MONEDA_PAGO = "discrepancia_moneda_pago"
"""No es ninguno de los códigos comunes de `app.ingesta.alertas`: es específico de la sección de
cupón cero, la única donde el título y una columna declaran moneda de pago por separado."""

CAMPOS_COBERTURA = (
    "emisor",
    "ley",
    "moneda_pago",
    "estructura_cupon",
    "tasa_cupon_vigente",
    "proximo_cupon",
    "proximo_pago_capital",
    "valor_residual",
    "paridad_pct",
    "valor_tecnico",
    "tir",
    "duracion_modificada",
    "convexidad",
    "vida_promedio",
    "volumen_promedio_20r_ars",
    "cierre_ars",
)
"""Los campos que la spec pide poder ver incompletos (F-005, criterio GWT-3). `ticker` no está
acá: es el ancla con la que se reconoce una fila de datos, así que siempre está presente."""


class FilaInforme(TypedDict):
    ticker: str
    emisor: str | None
    seccion: str
    ley: str | None
    moneda_pago: str | None
    fecha_informe: date
    monto_emitido: float | None
    moneda_monto_emitido: str | None
    fecha_emision: date | None
    fecha_vencimiento: date | None
    estructura_cupon: str | None
    indice_cupon: str | None
    frecuencia_cupon: str | None
    proximo_cupon: date | None
    tasa_cupon_vigente: float | None
    current_yield: float | None
    interes_corrido: float | None
    valor_residual: float | None
    cuotas_capital: float | None
    frecuencia_pago_capital: str | None
    proximo_pago_capital: date | None
    cierre_ars: float | None
    paridad_pct: float | None
    valor_tecnico: float | None
    tir: float | None
    duracion_modificada: float | None
    convexidad: float | None
    vida_promedio: float | None
    volumen_promedio_20r_ars: float | None
    moneda_emision: str | None


class InformeInvalido(Exception):
    """El layout del informe no matchea el catálogo conocido: no se persiste nada a medias."""

    def __init__(self, mensaje: str, **detalle: object):
        super().__init__(mensaje)
        self.detalle = detalle


@dataclass(frozen=True, slots=True)
class ResultadoInforme:
    filas: list[FilaInforme]
    fecha_informe: date
    snapshot: Snapshot


_RE_FECHA_AL_FINAL_DEL_TITULO = re.compile(r"\s+(\d{2}-[A-Za-z]{3}-\d{2})$")


def _titulo_y_fecha(texto_pagina: str) -> tuple[str, date | None]:
    """La segunda línea de cada página trae el título de la sección con la fecha del informe
    pegada al final, ej. `"DEUDA CORPORATIVA EN USD - LEY NY 05-Aug-26"`."""
    lineas = texto_pagina.split("\n")
    cruda = lineas[1] if len(lineas) > 1 else ""
    coincidencia = _RE_FECHA_AL_FINAL_DEL_TITULO.search(cruda)
    fecha = _fecha(coincidencia.group(1)) if coincidencia else None
    titulo = _RE_FECHA_AL_FINAL_DEL_TITULO.sub("", cruda).strip()
    return titulo, fecha


def _es_grafico(titulo: str) -> bool:
    return any(titulo.startswith(prefijo) for prefijo in GRAFICO_PREFIJOS)


def _normalizar_header(texto: str) -> str:
    return re.sub(r"[^a-z0-9]", "", texto.lower())


def _headers_compatibles(observado: str, esperado: str) -> bool:
    """Tolera truncamiento por ancho de celda (`"Fecha\\nVencimient\\no"` vs
    `"Fecha\\nVencimiento"`): uno es prefijo del otro con un mínimo de 4 caracteres. Exige
    igualdad de cantidad y de orden en el llamador — acá sólo compara un par ya emparejado por
    posición."""
    observado_norm = _normalizar_header(observado)
    esperado_norm = _normalizar_header(esperado)
    if observado_norm == esperado_norm:
        return True
    corto, largo = (
        (observado_norm, esperado_norm)
        if len(observado_norm) <= len(esperado_norm)
        else (esperado_norm, observado_norm)
    )
    return len(corto) >= 4 and largo.startswith(corto)


def _validar_headers(seccion: Seccion, observados: list[str], pagina: int) -> None:
    esperados = [campo.header for campo in seccion.campos]
    if len(observados) != len(esperados):
        raise InformeInvalido(
            f"la sección '{seccion.titulo}' trajo {len(observados)} columnas, "
            f"se esperaban {len(esperados)}",
            pagina=pagina,
            seccion=seccion.titulo,
            observados=observados,
            esperados=esperados,
        )
    for observado, esperado in zip(observados, esperados, strict=True):
        if not _headers_compatibles(observado, esperado):
            raise InformeInvalido(
                f"la sección '{seccion.titulo}' trajo una columna inesperada",
                pagina=pagina,
                seccion=seccion.titulo,
                observado=observado,
                esperado=esperado,
            )


def _resolver_ley_moneda_pago(
    seccion: Seccion, crudos: dict[str, str | None], ticker: str, snapshot: Snapshot
) -> tuple[str | None, str | None]:
    if seccion.origen_ley is OrigenDato.TITULO:
        ley = seccion.ley_fija
    elif seccion.origen_ley is OrigenDato.NINGUNO:
        ley = None
    else:
        crudo_ley = crudos.get("ley")
        ley = _ley(crudo_ley)
        if crudo_ley is not None and ley is None:
            snapshot.alertar(
                formato_inesperado(
                    FUENTE,
                    "código de ley no reconocido",
                    seccion=seccion.titulo,
                    ticker=ticker,
                    valor_crudo=crudo_ley,
                )
            )

    if seccion.origen_moneda_pago is OrigenDato.COLUMNA:
        moneda_pago = _texto(crudos.get("moneda_pago"))
        if (
            moneda_pago is not None
            and seccion.moneda_pago_fija is not None
            and moneda_pago != seccion.moneda_pago_fija
        ):
            # El dato por fila es más específico que el rótulo de la sección: se conserva la
            # columna y se deja la discrepancia declarada, no resuelta en silencio.
            snapshot.alertar(
                Alerta(
                    codigo=CODIGO_DISCREPANCIA_MONEDA_PAGO,
                    mensaje=(
                        f"{ticker}: la columna Moneda Pago dice {moneda_pago!r}, "
                        f"la sección declara {seccion.moneda_pago_fija!r}"
                    ),
                    severidad=Severidad.ADVERTENCIA,
                    detalle={
                        "seccion": seccion.titulo,
                        "ticker": ticker,
                        "moneda_columna": moneda_pago,
                        "moneda_seccion": seccion.moneda_pago_fija,
                    },
                )
            )
    else:
        moneda_pago = seccion.moneda_pago_fija

    return ley, moneda_pago


def _construir_fila(
    seccion: Seccion, cruda: FilaCruda, fecha_informe: date, snapshot: Snapshot
) -> FilaInforme:
    crudos: dict[str, str | None] = {
        campo.campo: valor for campo, valor in zip(seccion.campos, cruda.valores, strict=True)
    }

    def numero(campo: str) -> float | None:
        crudo = crudos.get(campo)
        valor = _numero(crudo)
        if crudo is not None and valor is None:
            snapshot.alertar(
                formato_inesperado(
                    FUENTE,
                    f"el campo {campo} no se pudo interpretar como número",
                    seccion=seccion.titulo,
                    ticker=crudos.get("ticker"),
                    pagina=cruda.pagina,
                    campo=campo,
                    valor_crudo=crudo,
                )
            )
        return valor

    def fecha(campo: str) -> date | None:
        crudo = crudos.get(campo)
        valor = _fecha(crudo)
        if crudo is not None and valor is None:
            snapshot.alertar(
                formato_inesperado(
                    FUENTE,
                    f"el campo {campo} no se pudo interpretar como fecha",
                    seccion=seccion.titulo,
                    ticker=crudos.get("ticker"),
                    pagina=cruda.pagina,
                    campo=campo,
                    valor_crudo=crudo,
                )
            )
        return valor

    def texto(campo: str) -> str | None:
        return _texto(crudos.get(campo))

    ticker = texto("ticker") or ""
    ley, moneda_pago = _resolver_ley_moneda_pago(seccion, crudos, ticker, snapshot)
    moneda_monto_emitido = seccion.moneda_monto_emitido or texto("moneda_emision")

    return FilaInforme(
        ticker=ticker,
        emisor=texto("emisor"),
        seccion=seccion.titulo,
        ley=ley,
        moneda_pago=moneda_pago,
        fecha_informe=fecha_informe,
        monto_emitido=numero("monto_emitido"),
        moneda_monto_emitido=moneda_monto_emitido,
        fecha_emision=fecha("fecha_emision"),
        fecha_vencimiento=fecha("fecha_vencimiento"),
        estructura_cupon=seccion.estructura_cupon_fija or texto("estructura_cupon"),
        indice_cupon=texto("indice_cupon"),
        frecuencia_cupon=texto("frecuencia_cupon"),
        proximo_cupon=fecha("proximo_cupon"),
        tasa_cupon_vigente=numero("tasa_cupon_vigente"),
        current_yield=numero("current_yield"),
        interes_corrido=numero("interes_corrido"),
        valor_residual=numero("valor_residual"),
        cuotas_capital=numero("cuotas_capital"),
        frecuencia_pago_capital=texto("frecuencia_pago_capital"),
        proximo_pago_capital=fecha("proximo_pago_capital"),
        cierre_ars=numero("cierre_ars"),
        paridad_pct=numero("paridad_pct"),
        valor_tecnico=numero("valor_tecnico"),
        tir=numero("tir"),
        duracion_modificada=numero("duracion_modificada"),
        convexidad=numero("convexidad"),
        vida_promedio=numero("vida_promedio"),
        volumen_promedio_20r_ars=numero("volumen_promedio_20r_ars"),
        moneda_emision=texto("moneda_emision"),
    )


PaginaProcesada = tuple[int, str, "date | None", "TablaPagina | None"]
"""(número de página, título sin fecha, fecha declarada, tabla — `None` si la página es un
gráfico o si no se encontró una fila de headers)."""


def _procesar_paginas(
    paginas: Iterable[PaginaProcesada], snapshot: Snapshot
) -> tuple[list[FilaInforme], date]:
    """La lógica de secciones, separada de pdfplumber: opera sobre tuplas planas para que se
    pueda testear el aborto (GWT-2) con páginas sintéticas."""
    filas: list[FilaInforme] = []
    fechas_vistas: set[date] = set()
    fecha_informe: date | None = None

    for pagina, titulo, fecha_pagina, tabla in paginas:
        if _es_grafico(titulo):
            continue

        seccion = SECCIONES.get(titulo)
        if seccion is None:
            raise InformeInvalido(
                f"sección no reconocida: {titulo!r}", pagina=pagina, titulo=titulo
            )
        if tabla is None:
            raise InformeInvalido(
                f"la sección {titulo!r} no trajo una tabla de datos reconocible",
                pagina=pagina,
                titulo=titulo,
            )

        _validar_headers(seccion, tabla.header_names, pagina)

        if fecha_pagina is not None:
            fechas_vistas.add(fecha_pagina)
            if fecha_informe is None:
                fecha_informe = fecha_pagina

        for cruda in tabla.filas:
            filas.append(_construir_fila(seccion, cruda, fecha_informe or fecha_pagina, snapshot))

    if fecha_informe is None:
        raise InformeInvalido("no se pudo determinar la fecha del informe en ninguna página")

    if len(fechas_vistas) > 1:
        snapshot.alertar(
            Alerta(
                codigo="fechas_de_informe_distintas",
                mensaje=(
                    "las páginas del informe declaran fechas distintas: "
                    f"{sorted(f.isoformat() for f in fechas_vistas)}"
                ),
                severidad=Severidad.ADVERTENCIA,
                detalle={"fechas": sorted(f.isoformat() for f in fechas_vistas)},
            )
        )

    return filas, fecha_informe


def _paginas_desde_pdf(pdf: pdfplumber.PDF) -> Iterator[PaginaProcesada]:
    for indice, pagina_pdf in enumerate(pdf.pages):
        numero_pagina = indice + 1
        titulo, fecha_pagina = _titulo_y_fecha(pagina_pdf.extract_text() or "")
        if _es_grafico(titulo):
            yield numero_pagina, titulo, fecha_pagina, None
            continue
        tabla = extraer_tabla_pagina(pagina_pdf, numero_pagina)
        yield numero_pagina, titulo, fecha_pagina, tabla


def parsear_informe(contenido: bytes) -> ResultadoInforme:
    """Punto de entrada. Recibe los bytes del PDF —no un path—: el endpoint le pasa el cuerpo
    subido, los tests le pasan el archivo leído, y quien consuma esto (F-007) puede dispararlo
    desde donde quiera.
    """
    snapshot = Snapshot(fuente=FUENTE, demora_declarada_minutos=0)

    try:
        with pdfplumber.open(BytesIO(contenido)) as pdf:
            paginas = list(_paginas_desde_pdf(pdf))
    except InformeInvalido:
        raise
    except FilaNoReconocida as exc:
        raise InformeInvalido(
            "una fila del informe no se pudo clasificar",
            pagina=exc.pagina,
            indice_fila=exc.indice_fila,
            celdas=exc.celdas,
        ) from exc
    except Exception as exc:
        raise InformeInvalido(f"no se pudo abrir el PDF: {exc}") from exc

    filas, fecha_informe = _procesar_paginas(paginas, snapshot)

    conteo_por_seccion: dict[str, int] = {}
    for fila in filas:
        conteo_por_seccion[fila["seccion"]] = conteo_por_seccion.get(fila["seccion"], 0) + 1
    for titulo, cantidad in conteo_por_seccion.items():
        snapshot.registrar_tramo(titulo, cantidad)

    snapshot.cobertura = medir_cobertura(filas, CAMPOS_COBERTURA)

    logger.info(
        "informe_iamc_parseado",
        filas=len(filas),
        secciones=conteo_por_seccion,
        fecha_informe=fecha_informe.isoformat(),
    )

    return ResultadoInforme(filas=filas, fecha_informe=fecha_informe, snapshot=snapshot)
