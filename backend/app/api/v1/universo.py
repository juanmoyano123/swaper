"""Endpoints del universo saneado — F-010, F-011 y F-012.

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

from collections import Counter
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db
from app.calendario.cupones import indexar_cronograma
from app.calendario.lectura import leer_cashflow
from app.core.pagination import CursorParams, Page, build_page
from app.ingesta.raiz import raiz_emision
from app.rotaciones.frecuencia import frecuencia_por_raiz
from app.universo import EspecieUniverso, MotivoDescarte, UniversoDeduplicado
from app.universo.segmentacion import DESC_SEGMENTO, NATURALEZA_TASA, NOMBRE_NATURALEZA
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
    saneado = await sanear_universo(conn, con_contraste=True)
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
    "/tipo-de-cambio",
    summary="El tipo de cambio implícito del día, derivado del propio universo",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def tipo_de_cambio(conn: Annotated[object, Depends(get_db)]) -> dict[str, object]:
    """El cociente entre el precio en pesos y el precio en dólares de las mismas emisiones.

    **No hay fuente externa acá y no la va a haber.** El tipo de cambio al que opera el mercado ya
    está adentro del universo: la misma emisión cotiza en las dos monedas y ese cociente es el
    número. Lo que se devuelve es la mediana, con cuántos pares la formaron y cuánto se dispersan —
    sin esos dos no se puede saber si creerle.

    El contraste contra los índices que publica BYMA viene en `contraste` y es exactamente eso: un
    control. Si difiere, sale alerta y **se sigue usando el implícito**.
    """
    saneado = await sanear_universo(conn, con_contraste=True)
    return {
        "tipo_de_cambio": saneado.cambio.como_dict(),
        "alertas": [a.como_dict() for a in saneado.cambio.alertas],
    }


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
    "/segmentos",
    summary="De dónde saca el monitor sus pestañas: los segmentos con especies hoy, y su conteo",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def segmentos(conn: Annotated[object, Depends(get_db)]) -> dict[str, object]:
    """F-038: el monitor muestra un solo segmento por vez, y acá saca la lista de pestañas.

    Reusa el mismo camino que `/emisiones/especies` — `sanear_universo` + `.emisiones().vivo()` —
    para que el conteo de cada pestaña coincida exactamente con lo que esa vista devuelve al
    filtrarla por `?segmento=`. Sólo viajan los segmentos con al menos una especie hoy: una pestaña
    vacía no es una pestaña, es ruido.

    `renta_variable` y `sin_segmento` viajan aparte y no como una pestaña más: son lo que no entra
    en ninguna, y el monitor los declara para que no desaparezcan en silencio.
    """
    saneado = await sanear_universo(conn)
    listado = saneado.emisiones().vivo()

    conteos = Counter(e.segmento for e in listado)
    presentes = [
        {
            "clave": clave,
            "nombre": DESC_SEGMENTO[clave],
            "naturaleza": NATURALEZA_TASA[clave],
            "naturaleza_nombre": NOMBRE_NATURALEZA[NATURALEZA_TASA[clave]],
            "especies": conteos[clave],
        }
        for clave in DESC_SEGMENTO
        if conteos[clave] > 0
    ]
    return {
        "segmentos": presentes,
        "renta_variable": saneado.renta_variable,
        "sin_segmento": len(saneado.sin_segmento),
    }


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
    segmento: Annotated[
        str | None,
        Query(
            description="Filtra por segmento comparable. F-038: un segmento inexistente hoy es "
            "una consulta válida, y devuelve página vacía en vez de 404."
        ),
    ] = None,
) -> Page[dict[str, object]]:
    """Todas las especies individuales, cada una con su clave de emisión y su sanidad.

    Es la vista del optimizador y no se filtra por defecto: los swaps de perfil rotan justamente
    entre especies de la misma emisión —de MEP a Cable—, y una vista colapsada no las dejaría ver.
    El filtro `segmento` es opcional y lo usa el monitor de F-038, que muestra un solo segmento a
    la vez: rendimientos de distinta naturaleza no comparten columna, y filtrar del lado del
    cliente obligaría a traer todo el universo para mirar uno solo.

    Cada especie viaja con su precio, su moneda de cotización declarada, su volumen crudo y su
    **volumen en dólares**, que es el único de los dos que se puede comparar entre hermanas: el
    crudo está en la moneda de cada especie y la que cotiza en pesos muestra ~1.500 veces más por
    el tipo de cambio, no por operarse más. Los dos viajan porque el crudo es lo que la fuente
    publicó y el normalizado lo que se deriva de él: esconder el primero haría imposible auditar
    el segundo.

    **La punta compradora y vendedora sigue sin viajar**: no existe en la vista `resumen`, así que
    hoy no hay de dónde sacarla.

    **`periodicidad` sale del cronograma contractual, no de la ventana de doce meses.** Se mide
    sobre los pagos futuros de renta de cada emisión con `frecuencia_por_raiz` (la misma función
    que usa el motor de rotaciones), así que un bono con un solo pago por delante se declara
    `al vencimiento` en vez de "anual": la ventana no alcanza para afirmar una frecuencia y
    suponerla sería inventar (regla 1). Una emisión sin cronograma no trae el campo — es faltante
    declarado, no `irregular`.
    """
    saneado = await sanear_universo(conn)
    dedup = saneado.emisiones()
    descartados = saneado.sanidad.descartados
    listado = dedup.vivo()
    if segmento is not None:
        listado = [e for e in listado if e.segmento == segmento]

    desde = params.decoded_cursor()
    if desde is not None:
        ultimo = str(desde.get("ticker", ""))
        listado = [e for e in listado if e.ticker > ultimo]

    # El cronograma entero por página: es la misma lectura completa que ya hace `sanear_universo`
    # de su lado, así que no cambia el orden de magnitud del request. Si alguna vez pesa, lo que
    # corresponde es cachear las dos, no dejar el campo afuera.
    frecuencias = frecuencia_por_raiz(
        indexar_cronograma(await leer_cashflow(conn)), datetime.now(UTC).date()
    )

    filas = []
    for especie in listado[: params.limit + 1]:
        frecuencia = frecuencias.get(raiz_emision(especie.ticker))
        filas.append(
            {
                **especie.como_dict(),
                "dato_sano": especie.ticker not in descartados,
                "hermanas": [h.ticker for h in dedup.hermanas(especie.ticker)],
                "periodicidad": frecuencia[0] if frecuencia else None,
            }
        )
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
