"""Endpoints de la ficha de instrumento — F-039, sensibilidad — F-040, prospecto de ONs — F-072.

Vive separado de `universo.py` porque responde una pregunta distinta — "todo lo que se sabe de ESTE
ticker" contra "el universo entero paginado" — y de `condiciones.py` porque ese es el dato curado
como colección y acá se pide por especie. Seis recursos de sólo lectura, cada uno independiente:
- `/{ticker}`: la especie más sus hermanas de liquidación (F-011), vía `ficha_de`.
- `/{ticker}/condiciones`: el mismo triplete `campo/campo_origen/campo_fecha` que ya devuelve
  `GET /condiciones`, filtrado a un ticker.
- `/{ticker}/cronograma`: los pagos futuros del cronograma, por 100 de VN y en la moneda de emisión
  — sin pasar por paridad, que es lo que hace F-016/F-021 para expresarlos como plata.
- `/{ticker}/sensibilidad`: cuánto se movería el precio si la TIR vigente comprimiera o se abriera,
  por repricing completo del cashflow contractual (F-040) — nunca la aproximación por duración.
- `/{ticker}/prospecto`: los documentos que el emisor de una ON presentó ante la CNV —prospectos,
  suplementos, avisos—, agrupados tal como la fuente los declara (F-072).
- `/{ticker}/prospecto/{uuid}/archivo`: el PDF real de uno de esos documentos.

Los seis pueden fallar por separado en el frontend (F-039, Parte 2: queries independientes) y por
eso acá también son seis endpoints y no uno que junte todo: una ficha de precios que se puede
mostrar aunque el cronograma no cargue no puede depender de un solo request que falle entero.
"""

from collections.abc import Sequence
from datetime import date
from typing import Annotated, Any

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import get_db
from app.calendario.cupones import Pago, componentes_valor_tecnico, indexar_cronograma
from app.calendario.lectura import leer_cashflow
from app.calendario.metricas import paridad_de, retorno_por_tir
from app.condiciones.persistencia import COLUMNAS, TABLA, fila_para_api
from app.core.config import Settings, get_settings
from app.externos.cnv import DocumentoCnv, RespuestaInesperadaDeCnv, cliente_cnv, url_emisor
from app.externos.emisores_cuit import leer_emisores_cuit, ruta_emisores_cuit
from app.ingesta.consolidacion.metricas import FUENTE_CALCULO, fuente_de_metricas
from app.ingesta.raiz import raiz_emision
from app.instrumentos import ficha_de
from app.universo.segmentacion import NOMBRE_NATURALEZA, EspecieUniverso
from app.universo.servicio import sanear_universo

logger = structlog.get_logger()

router = APIRouter(prefix="/instrumentos", tags=["instrumentos"])

CLASE_ON = "on_corporativo"

MOTIVO_PAUSA_CNV = (
    "La consulta a la CNV está pausada. Se activa con CNV_HABILITADO=true (ver app/core/config.py)."
)

# Escenarios de movimiento de la TIR, en bps. Los mismos del motor (tools/detectar_swaps.py:71):
# cinco compresiones, el escenario nulo y dos aperturas. El 0 no es decorativo — es la
# autoconsistencia del repricing a la vista (retorno exactamente 0).
ESCENARIOS_BPS: tuple[int, ...] = (-500, -400, -300, -200, -100, 0, 100, 200)

# Naturaleza cuyo rendimiento es TNA nominal en pesos: no es una tasa efectiva descontable (regla 2
# del proyecto). Cubre tasa_fija, badlar y tamar (ver NATURALEZA_TASA en universo/segmentacion.py).
NATURALEZA_TNA_NOMINAL = "tna_nominal_ars"

# Mismas columnas que `GET /condiciones`, filtradas a un solo ticker: la forma de la fila no cambia,
# sólo el WHERE. No se redefine la lista de columnas — divergiría de la semilla en cuanto alguien
# agregue un campo curado.
SQL_CONDICIONES_POR_TICKER = f"SELECT {', '.join(COLUMNAS)} FROM public.{TABLA} WHERE ticker = $1"


@router.get(
    "/{ticker}",
    summary="La especie pedida más sus hermanas de liquidación",
    responses={
        404: {"description": "El ticker no está en el universo de hoy"},
        503: {"description": "La base de datos no está disponible"},
    },
)
async def instrumento(ticker: str, conn: Annotated[object, Depends(get_db)]) -> dict[str, object]:
    """El mismo bono en sus especies de liquidación (GWT-1): precio, moneda y volumen de cada una,
    nunca sumados ni promediados entre sí — son tickers distintos del mismo instrumento.

    404 y no una ficha vacía: no se inventa una ficha para un ticker que no cotiza hoy.
    """
    resultado = await ficha_de(conn, ticker)
    if resultado is None:
        raise HTTPException(404, detail=f"{ticker} no está en el universo de hoy")
    return resultado


@router.get(
    "/{ticker}/condiciones",
    summary="Las condiciones de emisión curadas de un ticker, con origen y fecha",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def condiciones(ticker: str, conn: Annotated[object, Depends(get_db)]) -> dict[str, object]:
    """Ley, moneda de pago, lámina, calificación, sector y emisor, cada uno con de dónde salió y
    cuándo (GWT-4). `condiciones: null` cuando el ticker no tiene fila curada: no es un 404, es un
    estado normal y declarado — que no haya condiciones curadas no es que el ticker no exista.
    """
    fila = await conn.fetchrow(SQL_CONDICIONES_POR_TICKER, ticker)
    return {"ticker": ticker, "condiciones": fila_para_api(fila) if fila is not None else None}


@router.get(
    "/{ticker}/cronograma",
    summary="Los pagos futuros del cronograma, por 100 de VN y en la moneda de emisión",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def cronograma(ticker: str, conn: Annotated[object, Depends(get_db)]) -> dict[str, object]:
    """El flujo de fondos hasta el vencimiento, distinguiendo interés de amortización (GWT-3).

    Los montos vienen tal como los publica la fuente — por 100 nominales, en la moneda de emisión,
    sin pasar por paridad ni convertir a fracción del invertido: eso es lo que hacen los cálculos de
    cartera (F-016/F-021), y esta ficha muestra el dato crudo, no una proyección.

    Sin cronograma para la raíz de este ticker: `pagos: []`, declarado y no 404 — puede ser
    legítimamente un instrumento sin cashflow cargado en la fuente.

    **`resumen`** suma el residual vigente, el valor técnico y —cuando la moneda del flujo y la
    de cotización coinciden— la paridad, calculados en vivo sobre estos mismos pagos (17/08/2026).
    Si el residual que declara la fuente contradice la suma de amortizaciones ya pagadas, los tres
    números y el residual de cada pago van vacíos: se prefiere declarar el motivo antes que
    publicar un valor técnico sobreestimado (ver `cupones.componentes_valor_tecnico`).
    """
    filas = await leer_cashflow(conn)
    pagos = indexar_cronograma(filas).pagos_de(raiz_emision(ticker))
    especie = await _especie_de(conn, ticker)
    moneda = especie.moneda_cupon if especie is not None else None
    hoy = date.today()
    resumen = _resumen_del_cronograma(pagos, especie, hoy)
    return {
        "ticker": ticker,
        "pagos": [
            {
                "fecha": pago.fecha.isoformat(),
                "interes": pago.interes,
                "amortizacion": pago.capital,
                "moneda": moneda,
                "residual": pago.residual if resumen["coherente"] else None,
            }
            for pago in pagos
        ],
        "resumen": resumen,
    }


def _resumen_del_cronograma(
    pagos: Sequence[Pago], especie: EspecieUniverso | None, hoy: date
) -> dict[str, object]:
    """Residual vigente, valor técnico, cupón corrido y paridad, todos derivados de estos mismos
    pagos — nunca de lo que ya quedó persistido en la última corrida, para que la ficha muestre
    exactamente lo que puede probar con el cronograma que tiene adelante.

    `paridad` respeta el mismo gate de moneda que F-051 (`fuente_de_metricas`): sin eso, comparar
    el precio contra el valor técnico mezclaría monedas (regla 3).
    """
    if not pagos:
        return {
            "residual_vigente": None,
            "valor_tecnico": None,
            "cupon_corrido": None,
            "paridad": None,
            "coherente": True,
            "motivo_ausente": "sin cronograma de pagos en la fuente",
        }

    componentes = componentes_valor_tecnico(pagos, hoy)
    paridad: float | None = None
    motivo_ausente: str | None = None

    if not componentes.coherente:
        motivo_ausente = (
            "el residual que declara la fuente contradice la suma de amortizaciones ya pagadas: "
            "no se calcula un valor técnico sobreestimado"
        )
    elif componentes.valor_tecnico is None:
        motivo_ausente = (
            "sin pagos futuros: la emisión ya venció"
            if not any(p.fecha > hoy for p in pagos)
            else "sin residual vivo"
        )
    elif especie is None:
        motivo_ausente = "el ticker no está en el universo de hoy: no hay precio con qué comparar"
    elif especie.precio is None:
        motivo_ausente = "sin precio de mercado hoy"
    elif fuente_de_metricas(especie.tipo_tasa, especie.moneda_cotizacion) != FUENTE_CALCULO:
        motivo_ausente = (
            "cotiza en una moneda distinta de la que paga el flujo: comparar sin convertir "
            "mezclaría monedas, y convertir inventaría un tipo de cambio (regla 3)"
        )
    else:
        paridad = paridad_de(especie.precio, componentes.valor_tecnico)

    return {
        "residual_vigente": componentes.residual_vigente,
        "valor_tecnico": componentes.valor_tecnico,
        "cupon_corrido": componentes.cupon_corrido,
        "paridad": paridad,
        "coherente": componentes.coherente,
        "motivo_ausente": motivo_ausente,
    }


async def _especie_de(conn: Any, ticker: str) -> EspecieUniverso | None:
    """La especie del universo saneado de hoy, o `None` si el ticker no está."""
    saneado = await sanear_universo(conn)
    return next((e for e in saneado.especies if e.ticker == ticker), None)


@router.get(
    "/{ticker}/sensibilidad",
    summary="Cuánto se movería el precio si la TIR vigente comprimiera o se abriera",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def sensibilidad(ticker: str, conn: Annotated[object, Depends(get_db)]) -> dict[str, object]:
    """Repricing completo del cashflow contractual a la TIR de cada escenario (GWT-1): se descuentan
    todos los flujos futuros a la TIR nueva y se compara contra descontarlos a la TIR vigente. Nunca
    la aproximación lineal por duración — en bonos largos subestima fuerte la suba ante compresiones
    grandes, y esos son justamente los escenarios que interesan.

    Siempre 200 con una declaración (GWT-3): sin TIR vigente en una unidad descontable, sin
    cronograma o sin pagos futuros, `calculable` sale `false` con su `motivo` y nunca se cae a
    duración x delta. Un ticker fuera del universo de hoy también da 200 y no 404: éste es un
    endpoint derivado, y el 404 de "el ticker no existe" ya lo da la ficha del instrumento.
    """

    def _sin_calcular(motivo: str, especie: EspecieUniverso | None = None) -> dict[str, object]:
        nombre = NOMBRE_NATURALEZA[especie.naturaleza] if especie is not None else None
        return {
            "ticker": ticker,
            "tir_actual": especie.rendimiento if especie is not None else None,
            "naturaleza": especie.naturaleza if especie is not None else None,
            "naturaleza_nombre": nombre,
            "calculable": False,
            "motivo": motivo,
            "escenarios": [],
            "omitidos_bps": [],
        }

    especie = await _especie_de(conn, ticker)
    if especie is None:
        return _sin_calcular("no está en el universo de hoy: no hay TIR vigente para descontar")

    if especie.naturaleza == NATURALEZA_TNA_NOMINAL:
        return _sin_calcular(
            "el rendimiento de este segmento es TNA nominal en pesos, no una tasa efectiva "
            "descontable: no se calcula",
            especie,
        )

    if especie.rendimiento is None:
        return _sin_calcular("sin TIR vigente publicada ni calculada hoy", especie)

    filas = await leer_cashflow(conn)
    pagos = indexar_cronograma(filas).pagos_de(raiz_emision(ticker))
    if not pagos:
        return _sin_calcular("sin cronograma de pagos en la fuente", especie)

    hoy = date.today()
    if not any(p.fecha > hoy for p in pagos):
        return _sin_calcular("sin pagos futuros: la emisión ya venció", especie)

    deltas = [d / 10_000 for d in ESCENARIOS_BPS]
    r = retorno_por_tir(pagos, especie.rendimiento, deltas, hoy)
    if r is None:
        return _sin_calcular(
            "valor presente no positivo a la TIR vigente: no hay base de repricing", especie
        )

    escenarios = [
        {
            "delta_bps": d,
            "tir_escenario": especie.rendimiento + (d / 10_000),
            "retorno": r[d / 10_000],
        }
        for d in ESCENARIOS_BPS
        if (d / 10_000) in r
    ]
    omitidos_bps = [d for d in ESCENARIOS_BPS if (d / 10_000) not in r]

    return {
        "ticker": ticker,
        "tir_actual": especie.rendimiento,
        "naturaleza": especie.naturaleza,
        "naturaleza_nombre": NOMBRE_NATURALEZA[especie.naturaleza],
        "calculable": True,
        "motivo": None,
        "escenarios": escenarios,
        "omitidos_bps": omitidos_bps,
    }


def _sin_prospecto(
    ticker: str, motivo: str, *, emisor: str | None = None, cuit: str | None = None
) -> dict[str, object]:
    return {
        "ticker": ticker,
        "aplica": False,
        "emisor": emisor,
        "cuit": cuit,
        "url_emisor_cnv": url_emisor(cuit) if cuit else None,
        "grupos": [],
        "motivo_ausente": motivo,
        "fuente": "CNV",
    }


def _agrupar_documentos(documentos: list[DocumentoCnv]) -> list[dict[str, object]]:
    """Los documentos agrupados tal como la CNV los declara, con "Prospectos" primero cuando
    aparece — el resto queda en el orden en que la fuente los sirvió. Nunca se reordena por fecha
    ni se elige uno como "el" prospecto: el asesor ve todo lo que hay y elige."""
    orden: list[str] = []
    por_grupo: dict[str, list[DocumentoCnv]] = {}
    for doc in documentos:
        if doc.grupo not in por_grupo:
            orden.append(doc.grupo)
            por_grupo[doc.grupo] = []
        por_grupo[doc.grupo].append(doc)

    if "Prospectos" in orden:
        orden.remove("Prospectos")
        orden.insert(0, "Prospectos")

    return [
        {
            "grupo": grupo,
            "documentos": [
                {
                    "fecha": doc.fecha.isoformat() if doc.fecha is not None else None,
                    "hora": doc.hora,
                    "descripcion": doc.descripcion,
                    "documento_id": doc.documento_id,
                    "uuid": doc.uuid,
                    "url_publicview": doc.url_publicview(),
                }
                for doc in por_grupo[grupo]
            ],
        }
        for grupo in orden
    ]


@router.get(
    "/{ticker}/prospecto",
    summary="Los documentos que el emisor de una ON presentó ante la CNV",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def prospecto(
    ticker: str,
    conn: Annotated[object, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    """Prospectos, suplementos y avisos de una ON, agrupados tal como la CNV los declara (F-072).

    Siempre 200 con el estado declarado, mismo criterio que `/sensibilidad`: un ticker que no es ON
    o que no está en el universo de hoy no es un 404 — es `aplica: false`, y el 404 de "el ticker no
    existe" ya lo da la ficha del instrumento.

    **No se intenta emparejar el documento con la clase/serie exacta del ticker**: la investigación
    original ya midió que no hay una regla general para derivarla del número de ticker (funciona
    para Cresud, no para IRSA), y un mismo Suplemento puede cubrir varias clases a la vez. Los
    documentos van todos, agrupados por tipo, y el asesor elige a ojo cuál corresponde.

    `url_emisor_cnv` viaja siempre que hay CUIT resuelto, incluso si la CNV no responde o el parseo
    falla: es la salida de emergencia que no depende de nada más que el CUIT.
    """
    especie = await _especie_de(conn, ticker)
    if especie is None:
        return _sin_prospecto(ticker, "no está en el universo de hoy")
    if especie.clase_activo != CLASE_ON:
        return _sin_prospecto(ticker, "no es una obligación negociable")
    if especie.emisor is None:
        return _sin_prospecto(ticker, "sin emisor declarado en el universo de hoy")

    cuit = leer_emisores_cuit(ruta_emisores_cuit(settings)).get(especie.emisor)
    if cuit is None:
        return _sin_prospecto(
            ticker,
            f"el emisor {especie.emisor!r} todavía no tiene CUIT curado "
            "(ver tools/curar_emisores_cuit.py y data/emisores_cuit_pendientes.csv)",
            emisor=especie.emisor,
        )

    if not settings.cnv_habilitado:
        return _sin_prospecto(ticker, MOTIVO_PAUSA_CNV, emisor=especie.emisor, cuit=cuit)

    try:
        documentos = await cliente_cnv().documentos_de(cuit)
    except httpx.HTTPError as exc:
        logger.warning("cnv_prospecto_fallo_de_red", ticker=ticker, cuit=cuit, error=str(exc))
        return _sin_prospecto(
            ticker,
            "la CNV no respondió — probá de nuevo en un momento, o abrí el link a la CNV",
            emisor=especie.emisor,
            cuit=cuit,
        )

    if documentos is None:
        return _sin_prospecto(
            ticker,
            "la CNV no confirmó los resultados de este emisor — probá el link directo a la CNV",
            emisor=especie.emisor,
            cuit=cuit,
        )

    return {
        "ticker": ticker,
        "aplica": True,
        "emisor": especie.emisor,
        "cuit": cuit,
        "url_emisor_cnv": url_emisor(cuit),
        "grupos": _agrupar_documentos(documentos),
        "motivo_ausente": None if documentos else "el emisor no tiene documentos filed",
        "fuente": "CNV",
    }


@router.get(
    "/{ticker}/prospecto/{uuid}/archivo",
    summary="El PDF real de un documento del prospecto",
    responses={
        404: {"description": "El documento no tiene archivo adjunto en la CNV"},
        502: {"description": "La CNV no devolvió el archivo esperado"},
        503: {"description": "La consulta a la CNV está pausada"},
    },
)
async def prospecto_archivo(ticker: str, uuid: str) -> StreamingResponse:
    """El PDF real, bajado en vivo por el intercambio de dos pasos verificado el 17/08/2026
    (`ClienteCnv.archivo_de` + `ClienteCnv.descargar`) — nunca cacheado ni persistido: es contenido
    binario potencialmente grande, pedido a demanda por un clic del asesor.

    `ticker` no participa del pedido en sí —el `uuid` ya identifica la presentación en la CNV, sin
    ambigüedad— y viaja en la ruta sólo para que la URL sea legible y quede en el log de qué ficha
    la pidió.
    """
    settings = get_settings()
    if not settings.cnv_habilitado:
        raise HTTPException(503, detail=MOTIVO_PAUSA_CNV)

    try:
        cliente = cliente_cnv()
        archivo = await cliente.archivo_de(uuid)
        if archivo is None:
            raise HTTPException(
                404, detail="este documento de la CNV no tiene un archivo adjunto para descargar"
            )
        contenido = await cliente.descargar(archivo.guid)
    except ValueError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except RespuestaInesperadaDeCnv as exc:
        logger.warning("cnv_descarga_inesperada", ticker=ticker, uuid=uuid, error=str(exc))
        raise HTTPException(502, detail="la CNV no devolvió el archivo esperado") from exc
    except httpx.HTTPError as exc:
        logger.warning("cnv_descarga_fallo_de_red", ticker=ticker, uuid=uuid, error=str(exc))
        raise HTTPException(
            502, detail="la CNV no respondió — probá de nuevo en un momento"
        ) from exc

    return StreamingResponse(
        iter([contenido]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{archivo.nombre_archivo}"'},
    )
