"""El CSV curado de países de CEDEARs se vuelve filas con fuente y fecha — F-078, fase 3.

Calcado de `app/condiciones/semilla.py`, que es el patrón de siembra desde artefacto curado del
proyecto, y por las mismas razones. Lo que cambia es qué se cura y con qué grado de trazabilidad.

## Qué se cura acá, y por qué a mano

El país de la empresa detrás de un CEDEAR **no tiene fuente viva**. El domicilio legal que publica
la SEC no sirve: el dueño del producto lo rechazó explícitamente (28/08/2026) porque lo que hace
falta es la economía a la que queda expuesta la plata, no dónde está constituida la sociedad —una
minera que opera en Perú y cotiza en NYSE con holding en las Islas Caimán no es exposición a las
Islas Caimán—. Y la columna `pais` que dejó Yahoo se eliminó con la migración
`20260828182500_f078_drop_perfil_yahoo.sql`: llegaba sin fuente por fila y sin fecha.

Así que se investiga papel por papel, se declara **qué lo dice y dónde**, y el dueño del producto lo
valida antes de que se cargue. `data/paises_cedears_pendientes.csv` es la cola de ese trabajo;
`data/paises_cedears.csv` es lo ya validado, y es la única fuente de esta siembra.

## Trazabilidad por fila, no por artefacto

Es la diferencia con `condiciones_emision.csv`, donde el origen es el nombre del archivo y la fecha
es la del artefacto porque el CSV no trae ninguna de las dos por valor. Acá sí: cada fila se
investigó una por una y en un momento distinto, así que cada fila trae su `fuente` y su
`verificado`. Poner una fecha común a las 559 sería perder información que tenemos, que es el error
espejo del que la semilla de condiciones evita cometer.

Por eso la tabla las declara `NOT NULL`: una fila sin fuente no se puede mostrar (regla 11) y no se
carga. Se descarta y se cuenta, igual que un país fuera del vocabulario.

## El vocabulario cerrado es `REGION_M49`

Un `pais` que no sea una clave de `app/renta_variable/regiones.py::REGION_M49` se descarta y se
reporta. No es una validación de forma: es que un país del que no podemos decir la región entraría a
la base para aparecer en pantalla sin poder agruparse por ningún eje, y un valor así no se
distingue a simple vista de un error de tipeo en la planilla. El antecedente es el mismo que cita la
semilla de condiciones: una vez se tradujo un código de la fuente como "Ley Inglesa", categoría que
no existe, y hubo que revertir.

**`pais` vacío sí es un valor válido** y no un descarte: significa "se investigó y no se resolvió",
o "es un ETF, su eje geográfico es `region_etf`". Se carga con su fuente —que es donde queda escrita
la duda— y se cuenta aparte, en `sin_pais`, para poder medir cuánto del curado quedó abierto.

## Se lee con el `csv` de la stdlib y no con pandas

Mismo criterio que la semilla de condiciones: para ~559 filas de texto plano, pandas agrega la
ambigüedad del NaN —que obliga a distinguir hueco de vacío en cada columna— sin aportar nada.
"""

import csv
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import structlog
from starlette.concurrency import run_in_threadpool

from app.core.config import ENV_FILE, Settings
from app.ingesta.alertas import Alerta, Severidad, formato_inesperado
from app.renta_variable.regiones import REGION_M49, region_de

logger = structlog.get_logger()

TABLA = "pais_cedear"

COLUMNAS: tuple[str, ...] = ("ticker_papel", "pais", "fuente", "verificado")
"""Las cuatro que el CSV tiene que traer. `cargado_en` lo pone la base, no el artefacto."""

CODIGO_CURADO_AUSENTE = "paises_cedears_no_encontrado"
CODIGO_PAIS_FUERA_DE_VOCABULARIO = "pais_fuera_de_vocabulario"
CODIGO_PAPEL_REPETIDO = "papel_repetido_en_curado"
CODIGO_FILA_SIN_TRAZA = "fila_curada_sin_trazabilidad"

ACCION_REVISAR_CSV = (
    "Revisar data/paises_cedears.csv: cada fila lleva el país que la empresa declara, con la "
    "fuente que lo dice y la fecha en que se verificó."
)

# La ruta relativa se resuelve contra la raíz del repo y no contra el cwd, que cambia según se
# arranque con uvicorn, pytest o Docker. Mismo criterio que `condiciones/corrida.py::ruta_semilla`.
_RAIZ_REPO = ENV_FILE.parent


@dataclass(frozen=True, slots=True)
class FilaPais:
    """El país de un papel, con lo que lo declara y cuándo se verificó.

    `pais` en `None` es un valor y no un hueco: dice que se investigó y no se resolvió. `fuente` y
    `verificado` están siempre —son `NOT NULL` en la tabla—, y cuando `pais` es `None` la fuente es
    justamente donde quedó escrita la duda.
    """

    ticker_papel: str
    pais: str | None
    fuente: str
    verificado: date

    @property
    def region(self) -> str | None:
        """La subregión M49 del país, derivada al leer. No se persiste: ver `regiones.py`."""
        return region_de(self.pais)


@dataclass(frozen=True, slots=True)
class CuradoPaises:
    """Lo que se pudo leer del artefacto, con lo descartado declarado al lado."""

    filas: list[FilaPais] = field(default_factory=list)
    alertas: list[Alerta] = field(default_factory=list)
    archivo: str | None = None
    descartados: dict[str, dict[str, str]] = field(default_factory=dict)
    """Qué se dejó afuera, por motivo y con nombre y apellido: `{codigo: {ticker: valor}}`. Va a la
    respuesta del job entero y no sólo al log — un descarte silencioso es un papel que va a
    aparecer sin país y nadie va a saber por qué."""


@dataclass(frozen=True, slots=True)
class ResumenSiembraPaises:
    """Lo que la siembra dejó cargado y lo que no, con los motivos separados."""

    cargados: int
    descartados: int
    sin_pais: int
    """Filas cargadas con `pais` vacío. **No son un fallo**: son el curado declarando que investigó
    y no resolvió, más los ETFs, cuyo eje geográfico es `region_etf` y no un país."""
    archivo: str | None = None
    detalle_descartes: dict[str, dict[str, str]] = field(default_factory=dict)
    alertas: list[Alerta] = field(default_factory=list)

    def como_dict(self) -> dict[str, object]:
        return {
            "archivo": self.archivo,
            "cargados": self.cargados,
            "descartados": self.descartados,
            "sin_pais": self.sin_pais,
            "detalle_descartes": self.detalle_descartes,
            "alertas": [a.como_dict() for a in self.alertas],
        }


def ruta_paises(settings: Settings) -> Path:
    ruta = Path(settings.paises_cedears_csv)
    return ruta if ruta.is_absolute() else _RAIZ_REPO / ruta


def curado_ausente(ruta: Path) -> Alerta:
    """El archivo no está donde `settings.paises_cedears_csv` dice.

    Es un ERROR y no una advertencia por el mismo motivo que en la semilla de condiciones: sin
    artefacto no hay nada que sembrar, y una corrida que cantara éxito sobre cero filas sería
    indistinguible de un curado que todavía no empezó. **Y hoy es el caso normal**: el CSV
    definitivo no existe hasta que el dueño del producto valide la primera tanda, así que este
    endpoint devuelve esta alerta y cero filas hasta entonces, que es el estado correcto.
    """
    return Alerta(
        codigo=CODIGO_CURADO_AUSENTE,
        mensaje=f"No se encontró el CSV curado de países de CEDEARs en {ruta}.",
        severidad=Severidad.ERROR,
        accion_requerida=(
            "Verificar PAISES_CEDEARS_CSV. Si el curado todavía no se validó, el archivo no existe "
            "y no hay nada que sembrar: el país de cada CEDEAR queda declarado como faltante."
        ),
        detalle={"ruta": str(ruta)},
    )


def _descarte(codigo: str, motivo: str, valores: dict[str, str]) -> Alerta:
    """Filas que no se cargan, dichas con nombre y apellido.

    Los tres motivos comparten forma porque comparten consecuencia —el papel queda sin país y
    alguien tiene que mirar el CSV—; lo que cambia es qué hay que mirar, y eso va en `motivo`.
    """
    muestra = ", ".join(f"{papel}={valor!r}" for papel, valor in sorted(valores.items())[:8])
    return Alerta(
        codigo=codigo,
        mensaje=f"{len(valores)} papeles {motivo} ({muestra}): no se cargan.",
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=ACCION_REVISAR_CSV,
        detalle={"papeles": valores},
    )


def _leer_fecha(texto: str) -> date | None:
    """`verificado` en ISO (`2026-08-28`), o `None`. No se aceptan otros formatos a propósito: un
    `08/09/2026` es 8 de septiembre o 9 de agosto según quién lo escriba, y adivinar cuál sería
    inventar la fecha del dato."""
    try:
        return date.fromisoformat(texto)
    except ValueError:
        return None


def leer_curado(ruta: Path) -> CuradoPaises:
    """Lee el CSV curado y devuelve una fila por papel, ya validada contra el vocabulario.

    Función pura: sin base, sin red y sin reloj. Nunca lanza — un archivo ausente o mal formado
    vuelve como alerta y con cero filas, que es lo que la siembra necesita para no escribir nada en
    vez de vaciar la tabla.
    """
    if not ruta.is_file():
        return CuradoPaises(alertas=[curado_ausente(ruta)])

    # utf-8-sig y no utf-8: el CSV se edita en planillas que dejan BOM al principio, y con utf-8 la
    # primera columna pasa a llamarse "﻿ticker_papel" y no matchea con nada.
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        faltantes = sorted(set(COLUMNAS) - set(lector.fieldnames or ()))
        if faltantes:
            return CuradoPaises(
                alertas=[
                    formato_inesperado(
                        "El curado de países de CEDEARs",
                        f"le faltan columnas ({', '.join(faltantes)})",
                        archivo=ruta.name,
                        faltantes=faltantes,
                    )
                ],
                archivo=ruta.name,
            )
        crudas = list(lector)

    filas: list[FilaPais] = []
    vistos: set[str] = set()
    descartados: dict[str, dict[str, str]] = {}

    def _descartar(codigo: str, papel: str, valor: str) -> None:
        descartados.setdefault(codigo, {})[papel] = valor

    for cruda in crudas:
        papel = (cruda.get("ticker_papel") or "").strip().upper()
        if not papel:
            continue
        if papel in vistos:
            # Se conserva la primera aparición y no se fusionan las dos filas: fusionar sería
            # decidir cuál de los dos países vale, y eso es exactamente lo que el sistema no hace
            # por cuenta propia. Mismo criterio que `condiciones/semilla.py`.
            _descartar(CODIGO_PAPEL_REPETIDO, papel, (cruda.get("pais") or "").strip())
            continue
        vistos.add(papel)

        pais = (cruda.get("pais") or "").strip().upper()
        fuente = (cruda.get("fuente") or "").strip()
        verificado = _leer_fecha((cruda.get("verificado") or "").strip())

        if pais and pais not in REGION_M49:
            _descartar(CODIGO_PAIS_FUERA_DE_VOCABULARIO, papel, pais)
            continue
        if not fuente or verificado is None:
            # La fila entera se cae, incluso con un país impecable: la tabla exige las dos y un país
            # sin fuente no se muestra. Lo que falta va en el detalle para que se vea cuál de las
            # dos fue.
            _descartar(
                CODIGO_FILA_SIN_TRAZA,
                papel,
                f"fuente={fuente!r} verificado={(cruda.get('verificado') or '').strip()!r}",
            )
            continue

        filas.append(
            FilaPais(ticker_papel=papel, pais=pais or None, fuente=fuente, verificado=verificado)
        )

    motivos = {
        CODIGO_PAPEL_REPETIDO: "aparecen más de una vez en el curado",
        CODIGO_PAIS_FUERA_DE_VOCABULARIO: (
            "declaran un país que no es un código ISO 3166-1 alfa-2 con región M49 conocida"
        ),
        CODIGO_FILA_SIN_TRAZA: "no declaran fuente o fecha de verificación",
    }
    alertas = [
        _descarte(codigo, motivos[codigo], valores)
        for codigo, valores in descartados.items()
        if valores
    ]

    return CuradoPaises(
        filas=filas, alertas=alertas, archivo=ruta.name, descartados=descartados
    )


SQL_UPSERT = (
    f"INSERT INTO public.{TABLA} (ticker_papel, pais, fuente, verificado) "
    "VALUES ($1, $2, $3, $4) "
    "ON CONFLICT (ticker_papel) DO UPDATE SET "
    # Sin COALESCE y a propósito: vaciar un país **es una decisión** del curado —"se investigó y no
    # se resolvió"—, no una ausencia. Protegerlo resucitaría desde la carga anterior un valor que el
    # curado acaba de retirar. Mismo criterio que `condiciones/persistencia.py`.
    "pais = EXCLUDED.pais, "
    "fuente = EXCLUDED.fuente, "
    "verificado = EXCLUDED.verificado, "
    "cargado_en = now()"
)

SQL_LEER = f"SELECT ticker_papel, pais, fuente, verificado FROM public.{TABLA}"


async def persistir_paises(conn: Any, filas: Sequence[FilaPais]) -> None:
    """Escribe el curado en una sola transacción.

    **No borra las filas que el CSV dejó de traer.** Una fila que desaparece del artefacto es casi
    siempre una edición a medio hacer, y borrarla dejaría al papel sin país sin que nadie lo haya
    decidido; retirar un país curado se hace vaciando su `pais` y dejando la duda en `fuente`, que
    es explícito y queda registrado. Mismo criterio que la semilla de condiciones.
    """
    if not filas:
        return
    async with conn.transaction():
        await conn.executemany(
            SQL_UPSERT,
            [(f.ticker_papel, f.pais, f.fuente, f.verificado) for f in filas],
        )


async def sembrar_paises(conn: Any, settings: Settings) -> ResumenSiembraPaises:
    """Siembra `public.pais_cedear` desde el CSV curado y devuelve qué quedó cargado.

    Idempotente: no hay reloj ni fuente externa en el medio, así que sembrar dos veces seguidas deja
    la misma tabla. Lo único que se mueve es `cargado_en`, que dice cuándo entró a la base — la
    fecha del dato es `verificado` y esa sale del artefacto.
    """
    ruta = ruta_paises(settings)
    # Lectura de archivo síncrona: en el event loop bloquearía al resto del servicio.
    curado = await run_in_threadpool(leer_curado, ruta)

    await persistir_paises(conn, curado.filas)

    descartados = sum(len(v) for v in curado.descartados.values())
    sin_pais = sum(1 for fila in curado.filas if fila.pais is None)

    logger.info(
        "siembra_paises_cedears_termino",
        archivo=curado.archivo,
        cargados=len(curado.filas),
        descartados=descartados,
        sin_pais=sin_pais,
    )
    return ResumenSiembraPaises(
        cargados=len(curado.filas),
        descartados=descartados,
        sin_pais=sin_pais,
        archivo=curado.archivo,
        detalle_descartes=curado.descartados,
        alertas=curado.alertas,
    )


async def leer_paises(conn: Any) -> dict[str, FilaPais]:
    """El curado cargado, indexado por papel, para que la lectura de especies haga el join en
    memoria.

    Es una tabla chica —una fila por papel CEDEAR, ~559 al 28/08/2026— y se trae entera en una
    consulta en vez de sumarse como un LEFT JOIN más a `leer_renta_variable`. El motivo es que el
    join no es por especie sino **por papel**, y esa correspondencia la resuelve el agrupamiento en
    Python (`agrupamiento.py`), que contrasta cada grupo contra el tipo de cambio del universo antes
    de afirmarlo. Reproducir eso en SQL sería reescribir el agrupamiento en otro lenguaje.
    """
    filas = await conn.fetch(SQL_LEER)
    return {
        fila["ticker_papel"]: FilaPais(
            ticker_papel=fila["ticker_papel"],
            pais=fila["pais"],
            fuente=fila["fuente"],
            verificado=fila["verificado"],
        )
        for fila in filas
    }
