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
    """Conexión falsa que despacha por consulta: el universo de renta fija o el de renta
    variable -- mismo patrón que `FakeConexionRentaVariable` de `test_renta_variable_api.py`. Con
    `pct_rv: 0` la segunda nunca se ejecuta (ver el docstring del módulo)."""

    def __init__(
        self,
        universo: list[dict[str, Any]] | None = None,
        renta_variable: list[dict[str, Any]] | None = None,
    ) -> None:
        self.universo = FILAS_UNIVERSO if universo is None else universo
        self.renta_variable = [] if renta_variable is None else renta_variable
        self.consultas: list[str] = []

    async def fetch(self, query: str, *_: Any) -> list[dict[str, Any]]:
        self.consultas.append(query)
        if "clase_activo IN" in query:
            return self.renta_variable
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


async def test_con_renta_variable_activa_el_endpoint_consulta_las_dos_fuentes(crear_app) -> None:
    conexion = FakeConexionArmado()
    async with cliente(crear_app(conexion)) as http:
        await http.post(RUTA, json={"monto": 100_000, "pct_rv": 25})

    assert len(conexion.consultas) == 2


# --- Composición con renta variable ---------------------------------------------------------

# Todas en USD para no depender del tipo de cambio implícito: con sólo 3 bonos en FILAS_UNIVERSO
# no hay los 20 pares que pide `derivar_tipo_de_cambio`, así que el implícito no sale y una
# especie en pesos quedaría sin `volumen_usd` -- lo que se quiere probar acá es la composición, no
# el tipo de cambio (eso ya lo prueba `test_armado_renta_variable.py`).
FILAS_RENTA_VARIABLE: list[dict[str, Any]] = [
    {
        "ticker": "GGAL",
        "clase_activo": "accion",
        "lastPrice": 5000.0,
        "effectiveVolume": 1_500_000.0,
        "moneda_cotizacion": "USD",
        "sector": "Bancos",
    },
    {
        "ticker": "YPFD",
        "clase_activo": "accion",
        "lastPrice": 30_000.0,
        "effectiveVolume": 800_000.0,
        "moneda_cotizacion": "USD",
        "sector": "O&G",
    },
    {
        "ticker": "PAMP",
        "clase_activo": "accion",
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
        "ticker": "GGAL",
        "clase_activo": "accion",
        "lastPrice": 5000.0,
        "effectiveVolume": 1_500_000.0,
        "moneda_cotizacion": "USD",
    },
    {
        "ticker": "YPFD",
        "clase_activo": "accion",
        "lastPrice": 30_000.0,
        "effectiveVolume": 800_000.0,
        "moneda_cotizacion": "USD",
    },
    {
        "ticker": "PAMP",
        "clase_activo": "accion",
        "lastPrice": 2000.0,
        "effectiveVolume": 600_000.0,
        "moneda_cotizacion": "USD",
    },
]


async def test_sin_perfiles_de_renta_variable_la_cartera_sigue_siendo_usable(
    app_con_universo,
) -> None:
    """El caso de las acciones argentinas, que son el 91 % sin clasificar: sin un sólo rubro
    informado, `pct_rv > 0` igual devuelve un bloque de renta variable elegido por liquidez pura,
    la cartera sigue sumando 100% y la alerta declara por qué no se pudo diversificar por rubro --
    no se rompe nada, no se inventa un rubro para poder diversificar."""
    async with cliente(app_con_universo(renta_variable=FILAS_RENTA_VARIABLE_SIN_PERFIL)) as http:
        cuerpo = (await http.post(RUTA, json={"monto": 100_000, "perfil": "moderado"})).json()

    assert cuerpo["pct_rv_aplicado"] == pytest.approx(25.0)
    posiciones_rv = [p for p in cuerpo["posiciones"] if p["clase"] == "renta_variable"]
    assert posiciones_rv
    assert all(p["ticker"] in {"GGAL", "YPFD", "PAMP"} for p in posiciones_rv)
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
