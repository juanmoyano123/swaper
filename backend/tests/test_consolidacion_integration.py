"""F-007 contra la base real. Marcado `integration`, fuera de la corrida por defecto.

Dos cosas que sólo se pueden verificar acá. Una es que PostgreSQL acepte las sentencias que
`persistencia.py` arma —los tests offline prueban el contrato del SQL, no que el motor de base lo
ejecute—. La otra es el GWT-4, que es la razón de ser de toda la feature: el motor Python
(`segmentos.py`, `cupones.py`, `mercado.py`) tiene que poder leer el universo consolidado sin que
haya que tocarle una línea. Si eso no se cumple, F-007 escribió una base que nadie puede usar.
"""

import sys
from pathlib import Path

import asyncpg
import pandas as pd
import pytest
from dotenv import dotenv_values

RAIZ_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ_REPO / "tools"))


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


# --- El esquema que la migración de F-007 dejó --------------------------------------------------


@pytest.mark.integration
async def test_el_dominio_de_moneda_de_pago_admite_lo_que_declara_iamc(conexion) -> None:
    """IAMC declara USD/ARS y el CSV curado MEP/CCL: las dos granularidades tienen que entrar."""
    transaccion = conexion.transaction()
    await transaccion.start()
    try:
        for moneda in ("MEP", "CCL", "USD", "ARS"):
            await conexion.execute(
                "INSERT INTO public.instrumentos (ticker, clase_activo, coupon_currency) "
                "VALUES ($1, 'on_corporativo', $2)",
                f"PRUEBA{moneda}",
                moneda,
            )
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await conexion.execute(
                "INSERT INTO public.instrumentos (ticker, clase_activo, coupon_currency) "
                "VALUES ('PRUEBAEUR', 'on_corporativo', 'EUR')"
            )
    finally:
        await transaccion.rollback()


@pytest.mark.integration
async def test_las_columnas_nuevas_existen_con_el_tipo_declarado(conexion) -> None:
    filas = await conexion.fetch(
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'public' AND ("
        "  (table_name = 'instrumentos' AND column_name IN "
        "     ('estructura_cupon','moneda_cotizacion','plazo_liquidacion'))"
        "  OR (table_name = 'precios' AND column_name = 'convexidad'))"
    )
    tipos = {(f["table_name"], f["column_name"]): f["data_type"] for f in filas}

    assert tipos[("instrumentos", "estructura_cupon")] == "text"
    assert tipos[("instrumentos", "moneda_cotizacion")] == "text"
    assert tipos[("instrumentos", "plazo_liquidacion")] == "text"
    assert tipos[("precios", "convexidad")] == "numeric"


# --- Lo que la corrida dejó en la base ----------------------------------------------------------


@pytest.mark.integration
async def test_toda_la_corrida_quedo_en_un_solo_instante(conexion) -> None:
    """`max(capturado_en)` tiene que nombrar una corrida, no la última fila que se escribió."""
    ultimo = await conexion.fetchval("SELECT max(capturado_en) FROM public.precios")
    if ultimo is None:
        pytest.skip("todavía no corrió ninguna consolidación contra esta base")

    de_esa_corrida = await conexion.fetchval(
        "SELECT count(*) FROM public.precios WHERE capturado_en = $1", ultimo
    )
    total_tickers = await conexion.fetchval("SELECT count(DISTINCT ticker) FROM public.precios")

    assert de_esa_corrida == total_tickers


@pytest.mark.integration
async def test_la_vista_devuelve_una_fila_por_instrumento_con_las_dos_fuentes(conexion) -> None:
    """La vista toma UNA fila de precios por ticker: si BYMA e IAMC no estuvieran consolidadas en
    la misma fila, el Resumen tendría el precio o la TIR, nunca los dos."""
    fila = await conexion.fetchrow(
        'SELECT ticker, "lastPrice", tir, law FROM public.resumen '
        'WHERE tir IS NOT NULL AND "lastPrice" IS NOT NULL LIMIT 1'
    )
    if fila is None:
        pytest.skip("la base no tiene un instrumento con precio de BYMA y TIR de IAMC")

    assert fila["lastPrice"] is not None
    assert fila["tir"] is not None
    assert fila["law"] is not None, "si tiene TIR de IAMC también debería tener su ley"


@pytest.mark.integration
async def test_las_especies_sin_clasificar_conservan_su_punta(conexion) -> None:
    """`puntas` no tiene FK justamente para esto: el dato de una especie excluida no se pierde."""
    huerfanas = await conexion.fetchval(
        "SELECT count(*) FROM public.puntas p "
        "WHERE NOT EXISTS (SELECT 1 FROM public.instrumentos i WHERE i.ticker = p.ticker)"
    )
    total = await conexion.fetchval("SELECT count(*) FROM public.puntas")
    if not total:
        pytest.skip("todavía no corrió ninguna consolidación contra esta base")

    assert huerfanas > 0, "sin especies excluidas no se está probando nada"


# --- GWT-4: el motor lee el universo nuevo sin modificarse ---------------------------------------


@pytest.mark.integration
async def test_el_motor_carga_el_universo_de_la_base_sin_tocarle_una_linea(
    conexion, tmp_path, monkeypatch
) -> None:
    """La prueba de fuego de F-007: el contrato de salida se conservó.

    Se consulta la vista, se materializa en el mismo Excel que el motor espera y se lo hace cargar.
    Redirigir `CONSOLIDADO_PATH` es un `setattr` en runtime: no toca el archivo del motor ni el
    consolidado versionado.
    """
    import segmentos  # type: ignore[import-not-found]

    filas = await conexion.fetch("SELECT * FROM public.resumen")
    if not filas:
        pytest.skip("todavía no corrió ninguna consolidación contra esta base")

    columnas_del_contrato = [
        "ticker",
        "clase_activo",
        "tipo_tasa",
        "subtipo",
        "underlying",
        "sector",
        "tir",
        "tna",
        "duration",
        "maturity",
        "law",
        "couponCurrency",
        "lamina",
        "calificacion",
        "paridad",
        "residualValue",
        "lastPrice",
        "effectiveVolume",
        "revisar",
        "duplicado",
        "archivo_origen",
    ]
    assert list(filas[0].keys()) == columnas_del_contrato, "la vista cambió de forma"

    universo = pd.DataFrame([dict(f) for f in filas], columns=columnas_del_contrato)
    for numerica in (
        "tir",
        "tna",
        "duration",
        "paridad",
        "residualValue",
        "lastPrice",
        "effectiveVolume",
        "lamina",
    ):
        universo[numerica] = pd.to_numeric(universo[numerica], errors="coerce")

    destino = tmp_path / "universo_consolidado.xlsx"
    universo.to_excel(destino, sheet_name="Resumen", index=False)
    monkeypatch.setattr(segmentos, "CONSOLIDADO_PATH", str(destino))

    alertas: list[str] = []
    renta_fija = segmentos.cargar_universo(alertas, dedup=False)
    renta_variable = segmentos.cargar_renta_variable([])

    assert len(renta_fija) > 0, "el motor no encontró un solo instrumento segmentable"
    assert len(renta_variable) > 0, "el motor no encontró renta variable"
    assert renta_fija["segmento"].notna().all()
    # Las columnas que el motor deriva al cargar y que F-007 no persiste a propósito.
    for derivada in ("segmento", "rendimiento", "clave_riesgo", "raiz_emision", "es_soberano"):
        assert derivada in renta_fija.columns, f"el motor no pudo derivar {derivada}"

    # La regla 4 del dominio: el Tesoro es una sola clave de riesgo bajo todos sus prefijos.
    soberanos = renta_fija[renta_fija["es_soberano"]]
    if len(soberanos):
        assert set(soberanos["clave_riesgo"]) == {"SOBERANO_AR"}


@pytest.mark.integration
async def test_las_metricas_del_universo_dicen_de_que_informe_salieron(conexion) -> None:
    """Una fila de precios tiene dos fechas porque junta dos fuentes de frecuencias distintas.

    `capturado_en` fecha el precio de la rueda y `fecha_metricas` el informe de IAMC. Sin la
    segunda, la primera corrida sin informe a mano dejaba la TIR nula para todo el universo —la
    vista lee una sola fila de precios por ticker— aunque siguiera persistida en las anteriores.
    """
    fila = await conexion.fetchrow(
        "SELECT tir, fecha_metricas, capturado_en, fuente FROM public.precios "
        "WHERE tir IS NOT NULL ORDER BY capturado_en DESC LIMIT 1"
    )
    if fila is None:
        pytest.skip("la base no tiene métricas de IAMC todavía")

    assert fila["fecha_metricas"] is not None, "una TIR sin fecha de informe no se interpreta"
    assert fila["fecha_metricas"] <= fila["capturado_en"].date()
    assert fila["fuente"] == "byma+iamc"

    huerfanas = await conexion.fetchval(
        "SELECT count(*) FROM public.precios WHERE tir IS NOT NULL AND fecha_metricas IS NULL"
    )
    assert huerfanas == 0, "toda métrica persistida tiene que decir de qué informe salió"
