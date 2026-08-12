"""F-012 contra la base real y contra BYMA. Marcado `integration`, fuera de la corrida por defecto.

Lo que sólo se puede verificar acá son tres cosas que ningún test puro alcanza:

1. Que la lectura traiga `lastPrice`, `effectiveVolume` y la `moneda_cotizacion` que **no está en
   la vista** y llega por el `LEFT JOIN` contra `instrumentos`. Si ese JOIN estuviera mal escrito,
   esto falla con un error de SQL antes de la primera aserción, que es lo que tiene que pasar.
2. Que el universo de verdad tenga pares suficientes: si diera menos de 20, el volumen quedaría sin
   normalizar todos los días y la feature no estaría haciendo nada.
3. Que el implícito y el índice que publica BYMA hablen del mismo número. Es el contraste corriendo
   de punta a punta, con la fuente viva.

**Las aserciones son sobre invariantes, no sobre el valor del día.** El tipo de cambio cambia cada
rueda; lo que tiene que valer siempre es que exista, que salga de una muestra grande y que el
volumen en dólares esté en el mismo orden de magnitud para las dos especies del mismo bono.
"""

from pathlib import Path

import asyncpg
import pytest
from dotenv import dotenv_values

from app.universo.cambio import FX_MAXIMO, FX_MINIMO, MIN_PARES_FX, derivar_tipo_de_cambio
from app.universo.indice import leer_indices
from app.universo.servicio import sanear_universo

RAIZ_REPO = Path(__file__).resolve().parents[2]


def _dsn() -> str:
    dsn = dotenv_values(RAIZ_REPO / ".env").get("DATABASE_URL")
    if not dsn:
        pytest.skip("sin DATABASE_URL en el .env de la raíz")
    return dsn


@pytest.fixture
async def conexion():
    conn = await asyncpg.connect(_dsn(), timeout=10.0)
    try:
        yield conn
    finally:
        await conn.close()


@pytest.fixture
async def saneado(conexion):
    return await sanear_universo(conexion)


@pytest.mark.integration
async def test_la_lectura_trae_el_precio_el_volumen_y_la_moneda_declarada(saneado) -> None:
    """Los tres campos de F-012, y el tercero es el que prueba el JOIN: `moneda_cotizacion` vive en
    `instrumentos` y no en la vista, así que si el JOIN se cayera esto daría todo `None`."""
    especies = saneado.especies
    assert especies, "el universo vino vacío"
    assert any(e.precio is not None for e in especies)
    assert any(e.volumen is not None for e in especies)
    assert {e.moneda_cotizacion for e in especies if e.moneda_cotizacion} <= {"ARS", "USD", "EXT"}
    assert any(e.moneda_cotizacion == "ARS" for e in especies)
    assert any(e.moneda_cotizacion in ("USD", "EXT") for e in especies)


@pytest.mark.integration
async def test_el_join_a_instrumentos_no_duplica_ni_pierde_filas(conexion, saneado) -> None:
    """El invariante que hace seguro el JOIN: `instrumentos` tiene una fila por ticker.

    Si tuviera dos, el universo entero se duplicaría en silencio y todos los conteos de sanidad y
    de concentración quedarían al doble sin que nada lo delate. Se compara contra la vista sola,
    que es lo que se leía antes de F-012.
    """
    filas_de_la_vista = await conexion.fetchval("SELECT count(*) FROM public.resumen")
    assert saneado.leidos == filas_de_la_vista


@pytest.mark.integration
async def test_el_universo_real_alcanza_para_derivar_el_tipo_de_cambio(saneado) -> None:
    """Si esto diera menos de 20 pares, el volumen quedaría sin normalizar todos los días y la
    feature no estaría haciendo nada sobre el universo de hoy."""
    cambio = saneado.cambio
    assert cambio.disponible
    assert cambio.pares >= MIN_PARES_FX
    assert FX_MINIMO < cambio.valor < FX_MAXIMO


@pytest.mark.integration
async def test_las_dos_especies_del_mismo_bono_tienen_liquidez_del_mismo_orden(saneado) -> None:
    """El punto de la feature, sobre el universo de verdad.

    Sin normalizar, la especie en pesos de cualquier bono muestra ~1.500 veces más volumen que su
    hermana en dólares. Normalizadas, la diferencia entre las dos tiene que caber en un factor
    razonable: no se pide que operen lo mismo —no operan lo mismo— sino que estén en la misma
    unidad, y tres órdenes de magnitud de diferencia sistemática serían la unidad equivocada.
    """
    por_raiz: dict[str, list] = {}
    for especie in saneado.especies:
        if especie.volumen_usd:
            por_raiz.setdefault(especie.raiz, []).append(especie.volumen_usd)

    parejas = [v for v in por_raiz.values() if len(v) > 1]
    assert parejas, "ninguna emisión tiene dos especies con volumen: no hay nada que comparar"
    cocientes = sorted(max(v) / min(v) for v in parejas)
    mediana = cocientes[len(cocientes) // 2]
    assert mediana < 1_000, f"la mediana del cociente de volúmenes es {mediana:,.0f}"


@pytest.mark.integration
async def test_el_volumen_en_pesos_se_dividio_y_el_de_dolares_no(saneado) -> None:
    """La normalización aplicada, especie por especie. Es la aserción más directa que hay: lo que
    cotiza en dólares queda igual y lo que cotiza en pesos queda dividido por el implícito."""
    fx = saneado.cambio.valor
    for especie in saneado.especies:
        if especie.volumen is None or especie.moneda_cotizacion is None:
            continue
        if especie.moneda_cotizacion == "ARS":
            assert especie.volumen_usd == pytest.approx(especie.volumen / fx)
        else:
            assert especie.volumen_usd == especie.volumen


@pytest.mark.integration
async def test_el_implicito_coincide_con_lo_que_publica_byma(saneado) -> None:
    """El contraste de punta a punta, con la fuente viva.

    Se salta si BYMA no está: el contraste es un control y su indisponibilidad no es un fallo de
    esta feature — que el implícito salga igual sin él ya está probado sin red.
    """
    indices = await leer_indices()
    contraste = derivar_tipo_de_cambio(saneado.especies, indices).contraste
    if contraste is None:
        pytest.skip("BYMA no publicó los dos índices del contraste en esta corrida")
    assert contraste.coincide, (
        f"implícito {contraste.implicito:,.2f} contra publicado {contraste.publicado:,.2f}"
    )


@pytest.mark.integration
async def test_el_representante_de_cada_emision_es_el_mas_liquido_de_los_igual_de_completos(
    saneado,
) -> None:
    """El desempate de F-011 que F-012 cerró, verificado sobre el universo real.

    Se compara sólo contra las hermanas que empatan en sanidad y completitud, porque ésos son los
    criterios que van antes: una especie más líquida pero con menos datos **tiene** que perder.
    """
    from app.universo.emisiones import CAMPOS_COMPLETITUD

    descartados = saneado.sanidad.descartados
    dedup = saneado.emisiones()

    def completitud(especie) -> int:
        return sum(getattr(especie, campo) is not None for campo in CAMPOS_COMPLETITUD)

    for emision in dedup.emisiones:
        elegido = emision.representante
        if elegido is None:
            continue
        pares = [
            e
            for e in emision.especies
            if (e.ticker in descartados) == (elegido.ticker in descartados)
            and completitud(e) == completitud(elegido)
        ]
        assert (elegido.volumen_usd or 0.0) == max((e.volumen_usd or 0.0) for e in pares), (
            emision.raiz
        )
