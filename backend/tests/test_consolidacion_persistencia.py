"""El contrato de las sentencias que escriben el universo.

Que PostgreSQL acepte el SQL lo verifica el test de integración. Lo que se prueba acá es lo que la
base no puede protegerte de: que el upsert de `instrumentos` no vacíe un atributo cuando la fuente
que lo aportaba no estuvo, que `precios` sea un INSERT plano y no un upsert, que el cronograma no
se toque cuando la corrida no trajo uno usable, y que el fallo de un bloque no arrastre a los otros.
"""

from datetime import UTC, datetime

from app.ingesta.consolidacion.armado import Consolidacion
from app.ingesta.consolidacion.persistencia import (
    CODIGO_ESCRITURA_FALLIDA,
    COLUMNAS_INSTRUMENTOS,
    COLUMNAS_PRECIOS,
    persistir,
)
from tests.conftest import FakeConexionEscritura

CAPTURADO_EN = datetime(2026, 8, 6, 15, 49, tzinfo=UTC)


def consolidacion_minima(**overrides) -> Consolidacion:
    base = {
        "filas_instrumentos": [{"ticker": "AL30", "clase_activo": "bono_soberano"}],
        "filas_precios": [{"ticker": "AL30", "last_price": 86320.0}],
        "filas_puntas": [{"ticker": "AL30", "px_bid": 86310.0}],
        "filas_cashflow": [{"ticker": "AL30", "payment_date": "2027-01-09", "type": "HARD_DOLLAR"}],
    }
    base.update(overrides)
    return Consolidacion(**base)


# --- Instrumentos: el upsert que no pisa con nulos ----------------------------------------------


async def test_el_upsert_de_instrumentos_conserva_lo_que_la_corrida_no_trajo() -> None:
    """Es la puerta que F-008 necesita abierta: un refresco sin IAMC no puede vaciar la ley."""
    conn = FakeConexionEscritura()

    await persistir(conn, consolidacion_minima(), CAPTURADO_EN)

    sql = conn.sql_de("instrumentos")
    assert "ON CONFLICT (ticker) DO UPDATE" in sql
    for columna in ("law", "coupon_currency", "underlying", "estructura_cupon", "tipo_tasa"):
        assert f"{columna} = COALESCE(EXCLUDED.{columna}, public.instrumentos.{columna})" in sql


async def test_las_banderas_de_calidad_se_reescriben_enteras() -> None:
    """Con COALESCE, una emisión que dejó de estar en conflicto quedaría marcada para siempre."""
    conn = FakeConexionEscritura()

    await persistir(conn, consolidacion_minima(), CAPTURADO_EN)
    sql = conn.sql_de("instrumentos")

    assert "revisar = EXCLUDED.revisar" in sql
    assert "duplicado = EXCLUDED.duplicado" in sql
    assert "COALESCE(EXCLUDED.revisar" not in sql


async def test_las_columnas_van_en_el_orden_declarado() -> None:
    """Si el orden del INSERT y el de las tuplas se separan, los valores entran en otra columna."""
    conn = FakeConexionEscritura()
    fila = {col: f"valor-{col}" for col in COLUMNAS_INSTRUMENTOS}

    await persistir(conn, consolidacion_minima(filas_instrumentos=[fila]), CAPTURADO_EN)

    (tupla,) = conn.filas_de("instrumentos")
    assert list(tupla) == [f"valor-{col}" for col in COLUMNAS_INSTRUMENTOS]


# --- Precios y puntas: series temporales --------------------------------------------------------


async def test_precios_es_un_insert_plano_y_no_un_upsert() -> None:
    """La PK es (ticker, capturado_en): cada corrida agrega una fila, no reescribe la anterior."""
    conn = FakeConexionEscritura()

    await persistir(conn, consolidacion_minima(), CAPTURADO_EN)

    assert "ON CONFLICT" not in conn.sql_de("precios")
    assert "ON CONFLICT" not in conn.sql_de("puntas")


async def test_toda_la_corrida_comparte_un_solo_capturado_en() -> None:
    """Si cada fila llevara su propio now(), max(capturado_en) dejaría de nombrar una corrida."""
    conn = FakeConexionEscritura()
    consolidacion = consolidacion_minima(
        filas_precios=[{"ticker": "AL30"}, {"ticker": "GD30"}],
        filas_puntas=[{"ticker": "AL30"}, {"ticker": "GD30"}],
    )

    await persistir(conn, consolidacion, CAPTURADO_EN)

    indice = COLUMNAS_PRECIOS.index("capturado_en")
    assert {t[indice] for t in conn.filas_de("precios")} == {CAPTURADO_EN}
    assert {t[1] for t in conn.filas_de("puntas")} == {CAPTURADO_EN}


async def test_las_puntas_se_escriben_aunque_la_especie_no_este_en_instrumentos() -> None:
    """`puntas` no tiene FK a propósito: es lo que salva el dato de una especie sin clasificar."""
    conn = FakeConexionEscritura()
    consolidacion = consolidacion_minima(
        filas_instrumentos=[],
        filas_precios=[],
        filas_puntas=[{"ticker": "AL30X", "px_bid": 12345.0}],
    )

    escritura = await persistir(conn, consolidacion, CAPTURADO_EN)

    assert escritura.filas_por_tabla["puntas"] == 1
    assert conn.filas_de("puntas")[0][0] == "AL30X"


# --- Cronograma ---------------------------------------------------------------------------------


async def test_el_cronograma_es_un_upsert_por_ticker_y_fecha() -> None:
    conn = FakeConexionEscritura()

    await persistir(conn, consolidacion_minima(), CAPTURADO_EN)

    sql = conn.sql_de("cashflow")
    assert "ON CONFLICT (ticker, payment_date) DO UPDATE" in sql
    assert "cash_flow = EXCLUDED.cash_flow" in sql, "el cronograma vigente sí sobreescribe"


async def test_sin_cronograma_usable_no_se_toca_la_tabla() -> None:
    """El contrato de F-006: `None` significa conservar lo persistido, no borrarlo."""
    conn = FakeConexionEscritura()

    escritura = await persistir(conn, consolidacion_minima(filas_cashflow=None), CAPTURADO_EN)

    assert not conn.escribio_en("cashflow")
    assert escritura.filas_por_tabla["cashflow"] == 0
    assert escritura.alertas == [], "no escribir por contrato no es un fallo"


# --- Aislamiento entre bloques ------------------------------------------------------------------


async def test_un_fallo_escribiendo_el_cronograma_no_arrastra_a_precios_ni_puntas() -> None:
    conn = FakeConexionEscritura(fallar_en="public.cashflow")

    escritura = await persistir(conn, consolidacion_minima(), CAPTURADO_EN)

    assert escritura.filas_por_tabla["instrumentos"] == 1
    assert escritura.filas_por_tabla["precios"] == 1
    assert escritura.filas_por_tabla["puntas"] == 1
    assert escritura.filas_por_tabla["cashflow"] == 0

    (alerta,) = escritura.alertas
    assert alerta.codigo == CODIGO_ESCRITURA_FALLIDA
    assert alerta.detalle["tabla"] == "cashflow"
    assert alerta.accion_requerida, "hay que decir que la tabla quedó como estaba"


async def test_un_fallo_en_instrumentos_deshace_su_transaccion_y_deja_correr_las_otras() -> None:
    conn = FakeConexionEscritura(fallar_en="public.instrumentos")

    escritura = await persistir(conn, consolidacion_minima(), CAPTURADO_EN)

    assert escritura.filas_por_tabla["instrumentos"] == 0
    assert escritura.filas_por_tabla["precios"] == 0, "precios tiene FK: cae con instrumentos"
    assert escritura.filas_por_tabla["puntas"] == 1
    assert escritura.filas_por_tabla["cashflow"] == 1
    assert conn.transacciones[0] == "begin"
    assert conn.transacciones[1] == "rollback"


async def test_persistir_nunca_lanza() -> None:
    """Quien llama tiene que poder reportar la corrida entera, no perderla en una excepción."""
    conn = FakeConexionEscritura(fallar_en="INTO public.")

    escritura = await persistir(conn, consolidacion_minima(), CAPTURADO_EN)

    assert len(escritura.alertas) == 3
    assert all(v == 0 for v in escritura.filas_por_tabla.values())


async def test_cada_bloque_abre_y_cierra_su_propia_transaccion() -> None:
    conn = FakeConexionEscritura()

    await persistir(conn, consolidacion_minima(), CAPTURADO_EN)

    assert conn.transacciones == ["begin", "commit"] * 3


# --- Lotes --------------------------------------------------------------------------------------


async def test_las_escrituras_grandes_se_trocean() -> None:
    conn = FakeConexionEscritura()
    muchas = [{"ticker": f"T{i}"} for i in range(2500)]

    escritura = await persistir(conn, consolidacion_minima(filas_instrumentos=muchas), CAPTURADO_EN)

    lotes = [args for query, args in conn.escrituras if "INTO public.instrumentos" in query]
    assert [len(lote) for lote in lotes] == [1000, 1000, 500]
    assert escritura.filas_por_tabla["instrumentos"] == 2500
