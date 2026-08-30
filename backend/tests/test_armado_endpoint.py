"""El endpoint del armado asistido — F-019, `POST /api/v1/armado`.

Lo que se prueba acá es el **contrato HTTP**: qué viaja, qué se rechaza y qué pasa sin base. El
algoritmo de selección ya está probado sin levantar nada en `test_armado_paridad_motor.py` y
`test_armado_min_sectores.py`, así que este archivo no lo vuelve a recorrer — mismo criterio que
`test_concentracion_api.py` frente a `test_concentracion_servicio.py`. La composición de renta
variable (selección por liquidez, desempate, diversificación sectorial) tiene su propio test puro
en `test_armado_renta_variable.py`; acá se prueba que el endpoint reparte cupos y reescala bien.

## Por qué la mayoría de los tests de acá mandan `pct_rv: 0`

El default de `pct_rv` es el del perfil (`PCT_RV_PERFIL`), y moderado y agresivo no son `0`: un
pedido sin `pct_rv` explícito dispara una segunda consulta (la de renta variable) y, sin datos de
renta variable en el fixture, la alerta `rv_sin_candidatos`. Los tests que no están probando la
renta variable mandan `pct_rv: 0` a propósito, para reproducir bit a bit el comportamiento previo a
esta feature (ver el test de que `pct_rv=0` mantiene el comportamiento previo, más abajo).
"""

from datetime import date
from typing import Any

import pytest

from tests.conftest import cliente

RUTA = "/api/v1/armado"

# Sólo instrumentos `usd_hard`: con la cobertura por defecto ("mixta", que reparte también en cer,
# tasa_fija y dollar_linked) los otros tres segmentos quedan sin candidatos a propósito, para poder
# probar la cartera parcial del GWT-3 sin tener que armar cuatro segmentos completos.
FILAS_UNIVERSO: list[dict[str, Any]] = [
    {
        "ticker": "YMCHO",
        "clase_activo": "on_corporativo",
        "tipo_tasa": "hard-dollar",
        "tir": 0.07,
        "duration": 3.0,
        "sector": "O&G",
        "underlying": "YPF S.A.",
        "lastPrice": 99.0,
    },
    {
        "ticker": "PECNO",
        "clase_activo": "on_corporativo",
        "tipo_tasa": "hard-dollar",
        "tir": 0.075,
        "duration": 3.5,
        "sector": "Servicios",
        "underlying": "Pecom S.A.",
        "lastPrice": 100.0,
    },
    {
        "ticker": "AL30",
        "clase_activo": "bono_soberano",
        "tipo_tasa": "hard-dollar",
        "tir": 0.08,
        "duration": 2.0,
        "sector": "Soberano",
        "lastPrice": 86.0,
    },
]


class FakeConexionArmado:
    """Conexión falsa que despacha por consulta: el universo de renta fija, el de renta variable o
    el curado de países -- mismo patrón que `FakeConexionRentaVariable` de
    `test_renta_variable_api.py`. Con `pct_rv: 0` las dos últimas nunca se ejecutan (ver el
    docstring del módulo)."""

    def __init__(
        self,
        universo: list[dict[str, Any]] | None = None,
        renta_variable: list[dict[str, Any]] | None = None,
        paises: list[dict[str, Any]] | None = None,
        geografia_etfs: list[dict[str, Any]] | None = None,
    ) -> None:
        self.universo = FILAS_UNIVERSO if universo is None else universo
        self.renta_variable = [] if renta_variable is None else renta_variable
        # Vacío por default, que es el estado real hasta que se siembre `data/paises_cedears.csv`
        # (F-078 Fase 3): sin curado, `pais` y `region` salen `None` en todo el bloque.
        self.paises = [] if paises is None else paises
        # Vacío por default, mismo motivo que `paises` (F-079, D3): sin el curado de
        # `data/etfs_geografia.csv`, los seis campos `etf_*` salen `None` en todo el bloque.
        self.geografia_etfs = [] if geografia_etfs is None else geografia_etfs
        self.consultas: list[str] = []

    async def fetch(self, query: str, *_: Any) -> list[dict[str, Any]]:
        self.consultas.append(query)
        if "clase_activo IN" in query:
            return self.renta_variable
        if "etf_geografia" in query:
            return self.geografia_etfs
        if "pais_cedear" in query:
            return self.paises
        return self.universo


@pytest.fixture
def app_con_universo(crear_app):
    def _crear(**kwargs):
        return crear_app(FakeConexionArmado(**kwargs))

    return _crear


async def test_arma_una_cartera_parcial_cuando_el_universo_no_alcanza(app_con_universo) -> None:
    """GWT-3: sin candidatos en cer/tasa_fija/dollar_linked, la cartera sale igual con lo que hay
    en usd_hard y declara qué segmentos quedaron sin candidatos -- nunca se rellena con otra
    naturaleza."""
    async with cliente(app_con_universo()) as http:
        respuesta = await http.post(RUTA, json={"monto": 100_000, "pct_rv": 0})

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert len(cuerpo["posiciones"]) > 0
    tickers = {p["ticker"] for p in cuerpo["posiciones"]}
    assert tickers <= {"YMCHO", "PECNO", "AL30"}
    # La cartera se reescala a 100% con lo único que se pudo cubrir (usd_hard).
    assert sum(p["pct_cartera"] for p in cuerpo["posiciones"]) == pytest.approx(100.0, abs=0.5)
    codigos = {a["codigo"] for a in cuerpo["alertas"]}
    assert "segmento_sin_candidatos" in codigos
    assert cuerpo["origen_mix"] == "mix balanceado (por defecto)"


async def test_la_respuesta_trae_el_contrato_completo(app_con_universo) -> None:
    pedido = {"monto": 50_000, "cobertura": "devaluacion", "moneda": "usd", "pct_rv": 0}
    async with cliente(app_con_universo()) as http:
        cuerpo = (await http.post(RUTA, json=pedido)).json()

    assert set(cuerpo) == {
        "posiciones",
        "mix_aplicado",
        "origen_mix",
        "perfil",
        "sectores",
        "pct_rv_aplicado",
        "alertas",
    }
    assert set(cuerpo["sectores"]) == {"presentes", "minimo", "suficiente"}
    if cuerpo["posiciones"]:
        assert set(cuerpo["posiciones"][0]) == {"ticker", "pct_cartera", "monto", "clase"}


async def test_un_mix_con_segmento_desconocido_se_rechaza(app_con_universo) -> None:
    async with cliente(app_con_universo()) as http:
        respuesta = await http.post(RUTA, json={"monto": 100_000, "mix": {"no_existe": 100}})

    assert respuesta.status_code == 422


async def test_un_monto_no_positivo_se_rechaza(app_con_universo) -> None:
    async with cliente(app_con_universo()) as http:
        assert (await http.post(RUTA, json={"monto": 0})).status_code == 422
        assert (await http.post(RUTA, json={"monto": -1000})).status_code == 422


async def test_una_moneda_sin_segmentos_del_mix_se_rechaza(app_con_universo) -> None:
    """`--moneda usd` sobre una cobertura 100% en pesos no tiene nada que armar: es un pedido mal
    formado (422), no un hecho de la cartera (200 con alerta)."""
    async with cliente(app_con_universo()) as http:
        respuesta = await http.post(
            RUTA, json={"monto": 100_000, "cobertura": "tasa-pesos", "moneda": "usd"}
        )

    assert respuesta.status_code == 422


async def test_sin_base_de_datos_responde_503(crear_app) -> None:
    async with cliente(crear_app(None)) as http:
        respuesta = await http.post(RUTA, json={"monto": 100_000})

    assert respuesta.status_code == 503


async def test_con_pct_rv_cero_el_endpoint_hace_una_sola_consulta(crear_app) -> None:
    """`pct_rv: 0` no necesita renta variable: ni se la consulta ni se la arma."""
    conexion = FakeConexionArmado()
    async with cliente(crear_app(conexion)) as http:
        await http.post(RUTA, json={"monto": 100_000, "pct_rv": 0})

    assert len(conexion.consultas) == 1


async def test_con_renta_variable_activa_el_endpoint_consulta_las_cuatro_fuentes(crear_app) -> None:
    """Universo de renta fija, universo de renta variable, curado de países y curado de geografía
    de ETFs. La tercera se sumó en F-078 (sin ella `pais` sale `None` en todo el bloque y los topes
    de país y región no tendrían nunca qué medir) y la cuarta en F-079 (mismo motivo, para
    `etf_pais`/`etf_region`). Las cuatro cuelgan de `pct_rv > 0`, así que el caso `pct_rv: 0` del
    test de arriba sigue haciendo una sola."""
    conexion = FakeConexionArmado()
    async with cliente(crear_app(conexion)) as http:
        await http.post(RUTA, json={"monto": 100_000, "pct_rv": 25})

    assert len(conexion.consultas) == 4


# --- Composición con renta variable ---------------------------------------------------------

# Todas en USD para no depender del tipo de cambio implícito: con sólo 3 bonos en FILAS_UNIVERSO
# no hay los 20 pares que pide `derivar_tipo_de_cambio`, así que el implícito no sale y una
# especie en pesos quedaría sin `volumen_usd` -- lo que se quiere probar acá es la composición, no
# el tipo de cambio (eso ya lo prueba `test_armado_renta_variable.py`).
#
# `clase_activo: "cedear"` en las tres (14/08/2026): el armado automático dejó de poder sugerir
# acciones argentinas -- ver `test_el_armado_automatico_nunca_sugiere_una_accion` más abajo, que
# prueba el filtro con un universo mixto.
FILAS_RENTA_VARIABLE: list[dict[str, Any]] = [
    {
        "ticker": "AAPL",
        "clase_activo": "cedear",
        "lastPrice": 5000.0,
        "effectiveVolume": 1_500_000.0,
        "moneda_cotizacion": "USD",
        "sector": "Bancos",
    },
    {
        "ticker": "XOM",
        "clase_activo": "cedear",
        "lastPrice": 30_000.0,
        "effectiveVolume": 800_000.0,
        "moneda_cotizacion": "USD",
        "sector": "O&G",
    },
    {
        "ticker": "KO",
        "clase_activo": "cedear",
        "lastPrice": 2000.0,
        "effectiveVolume": 600_000.0,
        "moneda_cotizacion": "USD",
        "sector": "Energía",
    },
]


async def test_pct_rv_explicito_pisa_el_default_del_perfil(app_con_universo) -> None:
    async with cliente(app_con_universo(renta_variable=FILAS_RENTA_VARIABLE)) as http:
        cuerpo = (
            await http.post(RUTA, json={"monto": 100_000, "perfil": "conservador", "pct_rv": 30})
        ).json()

    assert cuerpo["pct_rv_aplicado"] == pytest.approx(30.0)
    clases_rv = {p["ticker"] for p in cuerpo["posiciones"] if p["clase"] == "renta_variable"}
    assert clases_rv


@pytest.mark.parametrize(
    ("perfil", "pct_rv_esperado"),
    [("conservador", 0.0), ("moderado", 25.0), ("agresivo", 60.0)],
)
async def test_el_default_de_pct_rv_depende_del_perfil(
    app_con_universo, perfil: str, pct_rv_esperado: float
) -> None:
    async with cliente(app_con_universo(renta_variable=FILAS_RENTA_VARIABLE)) as http:
        cuerpo = (await http.post(RUTA, json={"monto": 100_000, "perfil": perfil})).json()

    assert cuerpo["pct_rv_aplicado"] == pytest.approx(pct_rv_esperado)
    hay_renta_variable = any(p["clase"] == "renta_variable" for p in cuerpo["posiciones"])
    assert hay_renta_variable == (pct_rv_esperado > 0)


async def test_todas_las_posiciones_declaran_su_clase(app_con_universo) -> None:
    async with cliente(app_con_universo(renta_variable=FILAS_RENTA_VARIABLE)) as http:
        cuerpo = (
            await http.post(RUTA, json={"monto": 100_000, "perfil": "moderado"})
        ).json()

    assert cuerpo["posiciones"]
    assert all(p["clase"] in {"renta_fija", "renta_variable"} for p in cuerpo["posiciones"])


async def test_la_cartera_con_renta_variable_sigue_sumando_100(app_con_universo) -> None:
    async with cliente(app_con_universo(renta_variable=FILAS_RENTA_VARIABLE)) as http:
        cuerpo = (
            await http.post(RUTA, json={"monto": 100_000, "perfil": "moderado"})
        ).json()

    assert sum(p["pct_cartera"] for p in cuerpo["posiciones"]) == pytest.approx(100.0, abs=0.5)


async def test_pct_rv_cero_reproduce_el_comportamiento_previo(app_con_universo) -> None:
    """Mismas posiciones, mismo `pct_cartera`, mismo `monto` que antes de esta feature -- el único
    campo nuevo en cada posición es `clase`, siempre `renta_fija` acá."""
    async with cliente(app_con_universo(renta_variable=FILAS_RENTA_VARIABLE)) as http:
        cuerpo = (await http.post(RUTA, json={"monto": 100_000, "pct_rv": 0})).json()

    assert cuerpo["pct_rv_aplicado"] == 0.0
    assert all(p["clase"] == "renta_fija" for p in cuerpo["posiciones"])
    tickers = {p["ticker"] for p in cuerpo["posiciones"]}
    assert tickers <= {"YMCHO", "PECNO", "AL30"}


async def test_sin_candidatos_de_renta_variable_la_renta_fija_no_se_reescala(
    app_con_universo,
) -> None:
    """Sin filas de renta variable (el default del fixture), `pct_rv_aplicado` sale en 0 y la
    cartera de renta fija queda sumando 100% igual -- no se rearma con más candidatos de los que
    `armar()` buscó para cubrir el hueco que dejó la renta variable vacía."""
    async with cliente(app_con_universo()) as http:
        cuerpo = (await http.post(RUTA, json={"monto": 100_000, "perfil": "moderado"})).json()

    assert cuerpo["pct_rv_aplicado"] == 0.0
    codigos = {a["codigo"] for a in cuerpo["alertas"]}
    assert "rv_sin_candidatos" in codigos
    assert sum(p["pct_cartera"] for p in cuerpo["posiciones"]) == pytest.approx(100.0, abs=0.5)


# --- Sólo CEDEARs (14/08/2026) --------------------------------------------------------------

# Una acción con el volumen más alto de todo el universo: si el filtro de clase no anduviera,
# sería la primera candidata elegida por el ranking de liquidez (`app/armado/renta_variable.py`
# ordena por `volumen_usd` descendente). Que quede afuera es justo lo que este test prueba.
FILAS_RENTA_VARIABLE_MIXTA: list[dict[str, Any]] = [
    {
        "ticker": "GGAL",
        "clase_activo": "accion",
        "lastPrice": 5000.0,
        "effectiveVolume": 50_000_000.0,
        "moneda_cotizacion": "USD",
    },
    {
        "ticker": "AAPL",
        "clase_activo": "cedear",
        "lastPrice": 24_000.0,
        "effectiveVolume": 1_000_000.0,
        "moneda_cotizacion": "USD",
    },
    {
        "ticker": "KO",
        "clase_activo": "cedear",
        "lastPrice": 6_000.0,
        "effectiveVolume": 500_000.0,
        "moneda_cotizacion": "USD",
    },
]


async def test_el_armado_automatico_nunca_sugiere_una_accion(app_con_universo) -> None:
    """El picker manual dejó de ofrecer acciones argentinas (13/08/2026): el armado automático no
    puede sugerir algo que el asesor no puede ni buscar, aunque esa acción tenga más liquidez que
    cualquier CEDEAR del universo."""
    async with cliente(app_con_universo(renta_variable=FILAS_RENTA_VARIABLE_MIXTA)) as http:
        cuerpo = (
            await http.post(RUTA, json={"monto": 100_000, "perfil": "moderado", "pct_rv": 25})
        ).json()

    posiciones_rv = [p for p in cuerpo["posiciones"] if p["clase"] == "renta_variable"]
    assert posiciones_rv, "el universo tiene CEDEARs candidatos, el bloque no puede quedar vacío"
    assert "GGAL" not in {p["ticker"] for p in posiciones_rv}
    assert all(p["ticker"] in {"AAPL", "KO"} for p in posiciones_rv)


async def test_un_pct_rv_fuera_de_rango_se_rechaza(app_con_universo) -> None:
    async with cliente(app_con_universo()) as http:
        assert (
            await http.post(RUTA, json={"monto": 100_000, "pct_rv": -1})
        ).status_code == 422
        assert (
            await http.post(RUTA, json={"monto": 100_000, "pct_rv": 101})
        ).status_code == 422


# --- El estado real de hoy: `public.perfil_renta_variable` vacía --------------------------------
#
# Verificado contra producción (08/2026): la tabla tiene 0 filas mientras `instrumentos` tiene 434
# acciones y 1205 CEDEARs. Desde el 13/08/2026 la clasificación contra la SEC llena la tabla,
# pero cubre el 74 % de los CEDEARs y el 9 % de las acciones argentinas: un papel sin rubro sigue
# siendo el caso normal, no un borde. Sin la clave "sic_oficina" en la fila cruda,
# `EspecieRentaVariable.sic_oficina` sale `None` -- mismo camino que toma la lectura real, no un
# atajo del fixture.
FILAS_RENTA_VARIABLE_SIN_PERFIL: list[dict[str, Any]] = [
    {
        "ticker": "AAPL",
        "clase_activo": "cedear",
        "lastPrice": 5000.0,
        "effectiveVolume": 1_500_000.0,
        "moneda_cotizacion": "USD",
    },
    {
        "ticker": "XOM",
        "clase_activo": "cedear",
        "lastPrice": 30_000.0,
        "effectiveVolume": 800_000.0,
        "moneda_cotizacion": "USD",
    },
    {
        "ticker": "KO",
        "clase_activo": "cedear",
        "lastPrice": 2000.0,
        "effectiveVolume": 600_000.0,
        "moneda_cotizacion": "USD",
    },
]


async def test_sin_perfiles_de_renta_variable_la_cartera_sigue_siendo_usable(
    app_con_universo,
) -> None:
    """El caso de un CEDEAR sin clasificación SEC todavía (26 % de los CEDEARs, medido el
    13/08/2026): sin un sólo rubro informado, `pct_rv > 0` igual devuelve un bloque de renta
    variable elegido por liquidez pura, la cartera sigue sumando 100% y la alerta declara por qué
    no se pudo diversificar por rubro -- no se rompe nada, no se inventa un rubro para poder
    diversificar."""
    async with cliente(app_con_universo(renta_variable=FILAS_RENTA_VARIABLE_SIN_PERFIL)) as http:
        cuerpo = (await http.post(RUTA, json={"monto": 100_000, "perfil": "moderado"})).json()

    assert cuerpo["pct_rv_aplicado"] == pytest.approx(25.0)
    posiciones_rv = [p for p in cuerpo["posiciones"] if p["clase"] == "renta_variable"]
    assert posiciones_rv
    assert all(p["ticker"] in {"AAPL", "XOM", "KO"} for p in posiciones_rv)
    codigos = {a["codigo"] for a in cuerpo["alertas"]}
    assert "rv_sin_perfil_sectorial" in codigos
    assert sum(p["pct_cartera"] for p in cuerpo["posiciones"]) == pytest.approx(100.0, abs=0.5)


async def test_sin_perfiles_y_con_tematica_activa_no_hay_ningun_match(app_con_universo) -> None:
    """Mismo estado real, pero pidiendo una temática explícita: sin un sólo rubro
    informado, ninguna especie puede afirmarse que pertenece a esa temática (regla 1 del dominio,
    no se completa el dato que falta), así que el bloque de renta variable queda vacío,
    `rv_sin_candidatos` lo declara, y la renta fija no se reescala -- queda sumando 100% con lo
    que armó `armar()`."""
    async with cliente(app_con_universo(renta_variable=FILAS_RENTA_VARIABLE_SIN_PERFIL)) as http:
        cuerpo = (
            await http.post(
                RUTA, json={"monto": 100_000, "perfil": "moderado", "rubro_rv": "Office of Finance"}
            )
        ).json()

    assert cuerpo["pct_rv_aplicado"] == 0.0
    assert all(p["clase"] == "renta_fija" for p in cuerpo["posiciones"])
    codigos = {a["codigo"] for a in cuerpo["alertas"]}
    assert "rv_sin_candidatos" in codigos
    assert sum(p["pct_cartera"] for p in cuerpo["posiciones"]) == pytest.approx(100.0, abs=0.5)


# --- Topes de renta variable (F-078) -----------------------------------------------------------
#
# Un universo con la clasificación puesta, que es lo que el resto de los fixtures de acá no tiene:
# sin `sic_codigo` ni `mercado_origen` ningún tope puede acotar nada (categoría faltante no
# computa), y entonces el default del perfil sería indistinguible de no tener defaults.
#
# `sic_codigo` (F-079): el eje "rubro" del armador topea por `sector_codigo` -- el major group SIC
# de dos dígitos derivado de `sic_codigo`, no por `sic_oficina` -- así que AAPL y MSFT necesitan el
# mismo major group ("73", Computer And Data Processing Services) para seguir cayendo en el mismo
# cupo, y XOM uno distinto ("29", Petroleum Refining And Related Industries). `sic_oficina` se
# conserva igual: sigue viajando en la especie y sigue siendo lo que filtra `FiltroRv.rubros`
# (sin cambios, compatibilidad F-079).
FILAS_RENTA_VARIABLE_CLASIFICADAS: list[dict[str, Any]] = [
    {
        "ticker": "AAPL",
        "clase_activo": "cedear",
        "lastPrice": 5000.0,
        "effectiveVolume": 1_500_000.0,
        "moneda_cotizacion": "USD",
        "sic_codigo": "7372",
        "sic_oficina": "Office of Technology",
        "mercado_origen": "NASDAQ",
    },
    {
        "ticker": "MSFT",
        "clase_activo": "cedear",
        "lastPrice": 30_000.0,
        "effectiveVolume": 1_400_000.0,
        "moneda_cotizacion": "USD",
        "sic_codigo": "7372",
        "sic_oficina": "Office of Technology",
        "mercado_origen": "NASDAQ",
    },
    {
        "ticker": "XOM",
        "clase_activo": "cedear",
        "lastPrice": 2000.0,
        "effectiveVolume": 600_000.0,
        "moneda_cotizacion": "USD",
        "sic_codigo": "2911",
        "sic_oficina": "Office of Energy & Transportation",
        "mercado_origen": "NYSE",
    },
]


async def test_los_topes_del_perfil_aplican_solos(app_con_universo) -> None:
    """La promesa de F-078: un pedido que no nombra topes igual arma con los del perfil. Es un
    **cambio de comportamiento** -- antes de la feature el bloque se armaba sin ninguna restricción
    y las dos tecnológicas podían convivir. Con `n_rv=4` (moderado sobre `n_total=15`) y el tope de
    rubro en 40 %, el cupo por rubro es 1: entra AAPL y MSFT queda afuera."""
    async with cliente(
        app_con_universo(renta_variable=FILAS_RENTA_VARIABLE_CLASIFICADAS)
    ) as http:
        cuerpo = (await http.post(RUTA, json={"monto": 100_000, "perfil": "moderado"})).json()

    tickers_rv = [p["ticker"] for p in cuerpo["posiciones"] if p["clase"] == "renta_variable"]
    assert tickers_rv == ["AAPL", "XOM"]
    assert "MSFT" not in tickers_rv


async def test_topes_rv_explicito_pisa_el_default_del_perfil(app_con_universo) -> None:
    """Mismo pedido, con el tope de rubro apagado a mano: vuelve el comportamiento previo a F-078
    y las dos tecnológicas entran. Un `topes_rv` presente significa exactamente lo que declara --
    no se completa con el perfil, porque si se completara apagar un eje sería inexpresable."""
    async with cliente(
        app_con_universo(renta_variable=FILAS_RENTA_VARIABLE_CLASIFICADAS)
    ) as http:
        cuerpo = (
            await http.post(
                RUTA, json={"monto": 100_000, "perfil": "moderado", "topes_rv": {}}
            )
        ).json()

    # El orden es el de las dos pasadas de siempre: primero un papel por rubro nuevo (AAPL, XOM) y
    # después el relleno por liquidez (MSFT), que es justo el que el tope del perfil dejaba afuera.
    tickers_rv = [p["ticker"] for p in cuerpo["posiciones"] if p["clase"] == "renta_variable"]
    assert tickers_rv == ["AAPL", "XOM", "MSFT"]


async def test_el_tope_incumplible_no_es_un_error_del_pedido(app_con_universo) -> None:
    """Siempre 200, igual que la cartera parcial: un tope que el universo no puede cumplir es un
    hecho del mercado, no un pedido mal formado. Se declara con alerta y la cartera sale."""
    async with cliente(
        app_con_universo(renta_variable=FILAS_RENTA_VARIABLE_CLASIFICADAS)
    ) as http:
        respuesta = await http.post(
            RUTA,
            json={
                "monto": 100_000,
                "perfil": "moderado",
                "topes_rv": {"max_pct_mercado": 20},
            },
        )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    codigos = {a["codigo"] for a in cuerpo["alertas"]}
    assert "rv_tope_excedido" in codigos
    assert sum(p["pct_cartera"] for p in cuerpo["posiciones"]) == pytest.approx(100.0, abs=0.5)


async def test_el_filtro_rv_recorta_el_universo_de_renta_variable(app_con_universo) -> None:
    async with cliente(
        app_con_universo(renta_variable=FILAS_RENTA_VARIABLE_CLASIFICADAS)
    ) as http:
        cuerpo = (
            await http.post(
                RUTA,
                json={
                    "monto": 100_000,
                    "perfil": "moderado",
                    "filtro_rv": {"mercados": ["nyse"]},
                    "topes_rv": {},
                },
            )
        ).json()

    tickers_rv = [p["ticker"] for p in cuerpo["posiciones"] if p["clase"] == "renta_variable"]
    assert tickers_rv == ["XOM"]


async def test_un_tope_fuera_de_rango_se_rechaza(app_con_universo) -> None:
    """`0 < x <= 100`: un tope de 0 no acota, prohíbe, y uno de 120 no dice nada."""
    async with cliente(app_con_universo()) as http:
        for tope in (0, 120, -5):
            assert (
                await http.post(
                    RUTA, json={"monto": 100_000, "topes_rv": {"max_pct_rubro": tope}}
                )
            ).status_code == 422


async def test_rubro_rv_y_filtro_rv_contradictorios_dan_422(app_con_universo) -> None:
    """`rubro_rv` es la forma vieja de decir `filtro_rv.rubros` con un solo valor: si los dos
    vienen y dicen cosas distintas no se elige ninguno (mismo criterio que
    `condiciones_en_conflicto` en la ingesta). Eso sí es un pedido mal formado."""
    async with cliente(app_con_universo()) as http:
        respuesta = await http.post(
            RUTA,
            json={
                "monto": 100_000,
                "rubro_rv": "Office of Technology",
                "filtro_rv": {"rubros": ["Office of Finance"]},
            },
        )
    assert respuesta.status_code == 422

    async with cliente(app_con_universo()) as http:
        # Diciendo lo mismo no hay conflicto: es el pedido que manda el frontend viejo.
        respuesta = await http.post(
            RUTA,
            json={
                "monto": 100_000,
                "pct_rv": 0,
                "rubro_rv": "Office of Technology",
                "filtro_rv": {"rubros": ["Office of Technology"]},
            },
        )
    assert respuesta.status_code == 200


async def test_con_el_curado_sembrado_el_tope_de_pais_deja_de_estar_a_ciegas(
    app_con_universo,
) -> None:
    """El armador lee `public.pais_cedear` y propaga el país a la especie, así que el tope de país
    pasa de "no se pudo medir" a medirse de verdad. Sin esta lectura el eje quedaría declarado como
    faltante para siempre, aun con el CSV ya sembrado."""
    curado = [
        {"ticker_papel": t, "pais": "US", "fuente": "10-K 2025", "verificado": date(2026, 8, 28)}
        for t in ("AAPL", "MSFT", "XOM")
    ]
    async with cliente(
        app_con_universo(renta_variable=FILAS_RENTA_VARIABLE_CLASIFICADAS, paises=curado)
    ) as http:
        cuerpo = (await http.post(RUTA, json={"monto": 100_000, "perfil": "moderado"})).json()

    ejes_sin_dato = {
        a["detalle"]["eje"] for a in cuerpo["alertas"] if a["codigo"] == "rv_tope_sin_dato_en_eje"
    }
    assert "pais" not in ejes_sin_dato
    # Y con todo el bloque en un solo país, el tope del perfil (50 %) queda excedido y se declara.
    excedidos = [
        a
        for a in cuerpo["alertas"]
        if a["codigo"] == "rv_tope_excedido" and a["detalle"]["eje"] == "pais"
    ]
    assert excedidos and excedidos[0]["detalle"]["categoria"] == "US"
