"""Endpoints del universo saneado — F-010 y F-011, y después F-012.

Las tres features que envuelven `tools/segmentos.py` —sanidad, deduplicación y tipo de cambio
implícito— exponen el mismo universo bajo este prefijo, y por eso el plan las serializa: son tres
vistas del mismo servicio, no tres servicios.

**El resumen y las colecciones son recursos distintos.** El resumen contesta "¿sirve el universo de
hoy?" y es lo que mira una corrida; el listado de descartes contesta "¿por qué no está VSCQD?" y es
lo que mira alguien auditando un caso. Meterlos juntos obligaría a devolver la colección entera en
cada chequeo de salud, que es exactamente lo que la paginación por cursor existe para evitar. La
deduplicación de F-011 repite la forma: `/universo/emisiones` es el resumen y las dos vistas son dos
colecciones paginadas.

**Las dos vistas son dos recursos y no un parámetro.** Podrían haber sido un `?colapsado=true`, pero
quien pide la vista colapsada y quien pide la viva no son el mismo cliente ni preguntan lo mismo: el
armador necesita que una emisión cuente una vez y el optimizador necesita ver las tres especies para
poder rotar entre ellas. Un flag las haría parecer la misma pregunta con un ajuste, y el default de
ese flag sería una decisión silenciosa sobre cuál de los dos se rompe.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db
from app.core.pagination import CursorParams, Page, build_page
from app.universo import EspecieUniverso, MotivoDescarte, UniversoDeduplicado
from app.universo.servicio import sanear_universo

router = APIRouter(prefix="/universo", tags=["universo"])


@router.get(
    "/sanidad",
    summary="Cuánto del universo de hoy es dato confiable",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def sanidad(conn: Annotated[object, Depends(get_db)]) -> dict[str, object]:
    """Corre las dos capas sobre el universo del día y devuelve los conteos y las alertas.

    El desglose viene abierto por segmento a propósito: un descarte sólo se lee contra su unidad de
    tasa, y un total único mezclaría una TIR en dólares con una TNA nominal en pesos.

    Los instrumentos descartados **siguen en el universo**. Lo que dice este endpoint es cuáles no
    se proponen y por qué; ninguno se corrige ni se estima.
    """
    saneado = await sanear_universo(conn)
    return saneado.como_dict()


@router.get(
    "/sanidad/descartes",
    summary="Qué instrumentos no se proponen, con su motivo y el valor que lo disparó",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def descartes(
    conn: Annotated[object, Depends(get_db)],
    params: Annotated[CursorParams, Depends()],
    motivo: Annotated[
        MotivoDescarte | None,
        Query(description="Filtra por capa: coherencia entre especies o techo por segmento."),
    ] = None,
) -> Page[dict[str, object]]:
    """El listado auditable: ticker, motivo, valor declarado y contra qué se comparó.

    Ordenado por ticker, que además es la clave del cursor: la sanidad es determinística sobre el
    universo del día, así que dos páginas consecutivas ven el mismo listado salvo que haya entrado
    una corrida nueva en el medio — y en ese caso lo correcto es ver el universo nuevo, no una foto
    del anterior.
    """
    saneado = await sanear_universo(conn)
    listado = saneado.descartes if motivo is None else saneado.sanidad.por_motivo(motivo)

    desde = params.decoded_cursor()
    if desde is not None:
        ultimo = str(desde.get("ticker", ""))
        listado = [d for d in listado if d.ticker > ultimo]

    filas = [d.como_dict() for d in listado[: params.limit + 1]]
    return build_page(filas, params.limit, lambda f: {"ticker": f["ticker"]})


@router.get(
    "/emisiones",
    summary="Cuántas especies del universo son en realidad el mismo bono",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def emisiones(conn: Annotated[object, Depends(get_db)]) -> dict[str, object]:
    """Los conteos de la deduplicación: cuántas emisiones hay, cuántas especies se colapsaron y
    cuántos grupos no se colapsaron porque sus duraciones no coinciden.

    Ese último número es el que dice si el chequeo de sanidad está haciendo algo: un grupo que
    comparte raíz pero no duración **no es la misma emisión**, y colapsarlo fusionaría dos bonos
    distintos en una sola fila, que es peor que duplicar uno.
    """
    saneado = await sanear_universo(conn)
    return saneado.emisiones().como_dict()


@router.get(
    "/emisiones/colapsada",
    summary="La vista del armador: una fila por emisión",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def vista_colapsada(
    conn: Annotated[object, Depends(get_db)],
    params: Annotated[CursorParams, Depends()],
) -> Page[dict[str, object]]:
    """Una fila por emisión, con la clave de emisión explícita y las especies que representa.

    Es la vista con la que se arma y con la que se cuenta concentración: acá MR46O, MR46D y MR46C
    son una sola línea, porque comprar dos de ellas es comprar el mismo bono dos veces.

    Un grupo que no pasó el chequeo de duración aporta todas sus especies y viene marcado
    `colapsada: false`, con la dispersión que lo dejó afuera.
    """
    saneado = await sanear_universo(conn)
    dedup = saneado.emisiones()
    listado = dedup.colapsado()

    desde = params.decoded_cursor()
    if desde is not None:
        ultimo = str(desde.get("ticker", ""))
        listado = [e for e in listado if e.ticker > ultimo]

    filas = [_fila_colapsada(dedup, especie) for especie in listado[: params.limit + 1]]
    return build_page(filas, params.limit, lambda f: {"ticker": f["ticker"]})


def _fila_colapsada(dedup: UniversoDeduplicado, especie: EspecieUniverso) -> dict[str, object]:
    """La especie que ocupa la fila, más de qué emisión está hablando y a cuántas especies tapa."""
    emision = dedup.emision_de(especie.ticker)
    return {
        **especie.como_dict(),
        "colapsada": emision is not None and emision.colapsada,
        "especies": emision.tickers if emision is not None else [especie.ticker],
        "dispersion_duracion": emision.dispersion_duracion if emision is not None else None,
    }


@router.get(
    "/emisiones/especies",
    summary="La vista del optimizador: todas las especies, vivas",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def vista_viva(
    conn: Annotated[object, Depends(get_db)],
    params: Annotated[CursorParams, Depends()],
) -> Page[dict[str, object]]:
    """Todas las especies individuales, cada una con su clave de emisión y su sanidad.

    Es la vista del optimizador y no se filtra: los swaps de perfil rotan justamente entre especies
    de la misma emisión —de MEP a Cable—, y una vista colapsada no los dejaría ni ver.

    **El precio, la punta y la moneda de cotización todavía no viajan acá.** El precio y el volumen
    son las columnas que F-012 necesita para derivar el tipo de cambio implícito y le pertenecen; la
    punta compradora y vendedora no existe en la vista `resumen`, así que hoy no hay de dónde
    sacarla. Lo que sí es de cada especie y ya viaja es su rendimiento declarado y su sufijo de
    liquidación.
    """
    saneado = await sanear_universo(conn)
    dedup = saneado.emisiones()
    descartados = saneado.sanidad.descartados
    listado = dedup.vivo()

    desde = params.decoded_cursor()
    if desde is not None:
        ultimo = str(desde.get("ticker", ""))
        listado = [e for e in listado if e.ticker > ultimo]

    filas = [
        {
            **especie.como_dict(),
            "dato_sano": especie.ticker not in descartados,
            "hermanas": [h.ticker for h in dedup.hermanas(especie.ticker)],
        }
        for especie in listado[: params.limit + 1]
    ]
    return build_page(filas, params.limit, lambda f: {"ticker": f["ticker"]})


@router.get(
    "/emisiones/duplicado",
    summary="Si agregar una especie a una cartera suma diversificación o repite un bono",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def duplicado(
    conn: Annotated[object, Depends(get_db)],
    ticker: Annotated[str, Query(description="La especie que se quiere agregar.")],
    cartera: Annotated[
        list[str] | None,
        Query(description="Los tickers que la cartera ya tiene. Se repite el parámetro."),
    ] = None,
) -> dict[str, object]:
    """Contesta lo que el armador necesita preguntar antes de agregar una posición.

    Es un servicio y no una pantalla: la decisión de qué es la misma emisión se toma con el mismo
    criterio que colapsa las filas, y si viviera en la interfaz la interfaz tendría que volver a
    cortar tickers por su cuenta.

    Sobre un grupo que **no** se colapsó no advierte nada: el chequeo de duración ya dijo que esas
    especies son emisiones distintas, y llamarlas duplicado sería tan falso como el error que la
    feature ataca.
    """
    saneado = await sanear_universo(conn)
    dedup = saneado.emisiones()
    emision = dedup.emision_de(ticker)
    advertencia = dedup.advertencia_de_duplicado(ticker, cartera or [])
    return {
        "ticker": ticker,
        "emision": emision.raiz if emision else None,
        "en_el_universo": emision is not None and ticker in emision.tickers,
        "duplicado": advertencia is not None,
        "advertencia": advertencia.como_dict() if advertencia else None,
    }
