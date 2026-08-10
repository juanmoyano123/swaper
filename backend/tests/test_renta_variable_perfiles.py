"""SQL puro de `app/renta_variable/perfiles.py` — Etapa 4 del rediseño del armador.

Reusa `FakeConexionEscritura` de `conftest.py`: no prueba que PostgreSQL entienda `make_interval` o
`ON CONFLICT`, prueba el contrato — qué SQL se emite y qué parámetros viajan y en qué orden.
"""

from datetime import UTC, datetime

from app.renta_variable.perfiles import guardar_perfil, tickers_pendientes
from tests.conftest import FakeConexionEscritura


async def test_tickers_pendientes_lee_el_ticker_de_cada_fila() -> None:
    conn = FakeConexionEscritura(metricas_previas=[{"ticker": "GGAL"}, {"ticker": "PAMP"}])

    resultado = await tickers_pendientes(conn)

    assert resultado == ["GGAL", "PAMP"]
    assert conn.consultas
    assert "perfil_renta_variable" in conn.consultas[0]


async def test_tickers_pendientes_filtra_por_clase_de_renta_variable() -> None:
    conn = FakeConexionEscritura(metricas_previas=[])

    await tickers_pendientes(conn)

    assert "'accion'" in conn.consultas[0]
    assert "'cedear'" in conn.consultas[0]


async def test_tickers_pendientes_pasa_los_dias_de_vencimiento_como_parametro_posicional() -> None:
    conn = FakeConexionEscritura(metricas_previas=[])

    await tickers_pendientes(conn, dias_vencimiento=7)

    assert "$1" in conn.consultas[0]


async def test_guardar_perfil_hace_upsert_con_los_ocho_campos_en_orden() -> None:
    conn = FakeConexionEscritura()
    capturado = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)

    await guardar_perfil(
        conn,
        "GGAL",
        nombre_corto="GRUPO FINANCIERO GALICIA",
        nombre_largo="Grupo Financiero Galicia S.A.",
        sector="Financial Services",
        industria="Banks - Regional",
        pais="Argentina",
        fuente="Yahoo Finance",
        capturado_en=capturado,
    )

    filas = conn.filas_de("perfil_renta_variable")
    assert filas == [
        (
            "GGAL",
            "GRUPO FINANCIERO GALICIA",
            "Grupo Financiero Galicia S.A.",
            "Financial Services",
            "Banks - Regional",
            "Argentina",
            "Yahoo Finance",
            capturado,
        )
    ]
    assert "ON CONFLICT (ticker) DO UPDATE" in conn.sql_de("perfil_renta_variable")


async def test_guardar_perfil_acepta_campos_faltantes_como_none() -> None:
    """Un perfil parcial (sólo el nombre, sin país/sector/industria) no inventa el resto."""
    conn = FakeConexionEscritura()

    await guardar_perfil(
        conn,
        "GGAL",
        nombre_corto="GRUPO FINANCIERO GALICIA",
        nombre_largo=None,
        sector=None,
        industria=None,
        pais=None,
        fuente="Yahoo Finance",
        capturado_en=datetime(2026, 8, 9, tzinfo=UTC),
    )

    fila = conn.filas_de("perfil_renta_variable")[0]
    assert fila[2:6] == (None, None, None, None)
