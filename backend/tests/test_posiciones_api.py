"""El contrato de `POST /api/v1/posiciones/resolver` — F-029.

El veredicto de la resolución ya está probado sin levantar nada en `test_posiciones_resolucion.py`.
Lo que se prueba acá es lo que sólo se ve por HTTP: que las posiciones no reconocidas **viajen** en
la respuesta en vez de desaparecer, que el diagnóstico declare la base del porcentaje, y que la
cartera del cliente entre por el cuerpo y no por la query string.
"""

from typing import Any

from app.posiciones.lectura import TABLA_INSTRUMENTOS
from tests.conftest import cliente

RESOLVER = "/api/v1/posiciones/resolver"


def fila_universo(ticker: str, *, tipo_tasa: str | None = "hard-dollar") -> dict[str, Any]:
    return {
        "ticker": ticker,
        "clase_activo": "on_corporativo",
        "tipo_tasa": tipo_tasa,
        "tir": 0.0727,
        "tna": None,
        "duration": 2.4,
        "maturity": None,
        "law": None,
        "couponCurrency": None,
        "underlying": None,
        "lastPrice": 98.4,
        "effectiveVolume": 1000.0,
        "moneda_cotizacion": "USD",
    }


def fila_instrumento(ticker: str, clase: str, plazo: str | None) -> dict[str, Any]:
    return {"ticker": ticker, "clase_activo": clase, "plazo_liquidacion": plazo}


# `RUCEX` está en `instrumentos` pero sin tipo de tasa, así que no llega al universo comparable: es
# el caso real que hace que "existe pero no resuelve" sea distinto de "no existe".
UNIVERSO = [fila_universo("MR46D"), fila_universo("AL30"), fila_universo("RUCEO")]
INSTRUMENTOS = [
    fila_instrumento("MR46D", "on_corporativo", "2"),
    fila_instrumento("AL30", "bono_soberano", "2"),
    fila_instrumento("RUCEO", "on_corporativo", "2"),
    fila_instrumento("RUCEX", "on_corporativo", "1"),
    fila_instrumento("GGAL", "accion", "2"),
]


class FakeConexionCartera:
    """Conexión falsa que contesta distinto según qué tabla le pidan.

    Hace falta porque el servicio hace **dos** lecturas sobre la misma conexión —el universo
    saneado y el índice de instrumentos— y una conexión que devolviera siempre lo mismo taparía
    justamente el enganche que se quiere probar.
    """

    def __init__(
        self,
        universo: list[dict[str, Any]] | None = None,
        instrumentos: list[dict[str, Any]] | None = None,
    ) -> None:
        self.universo = UNIVERSO if universo is None else universo
        self.instrumentos = INSTRUMENTOS if instrumentos is None else instrumentos
        self.consultas: list[str] = []

    async def fetch(self, query: str, *_: Any) -> list[dict[str, Any]]:
        self.consultas.append(query)
        if TABLA_INSTRUMENTOS in query and "public.resumen" not in query:
            return self.instrumentos
        return self.universo


def cuerpo(*posiciones: dict[str, Any]) -> dict[str, Any]:
    return {"posiciones": list(posiciones)}


def pos(ticker: str, *, fila: int = 1, monto: float | None = 1000.0, nominal: float | None = None):
    return {
        "id": f"p{fila}",
        "fila": fila,
        "ticker_declarado": ticker,
        "nominal": nominal,
        "monto": monto,
    }


def app_con(crear_app, conexion: FakeConexionCartera | None = None):
    return crear_app(conexion or FakeConexionCartera())


# --- Lo resuelto ---------------------------------------------------------------------------------


async def test_una_posicion_conocida_vuelve_con_su_emision_su_especie_y_su_plazo(crear_app) -> None:
    async with cliente(app_con(crear_app)) as http:
        respuesta = await http.post(RESOLVER, json=cuerpo(pos("MR46D")))

    assert respuesta.status_code == 200
    (item,) = respuesta.json()["posiciones"]
    assert item["resuelta"] is True
    assert item["ticker"] == "MR46D"
    assert item["emision"] == "MR46"
    assert item["plazo_liquidacion"] == "2"
    assert item["segmento"] == "usd_hard"


async def test_el_plazo_no_se_traduce_en_la_respuesta(crear_app) -> None:
    """Viaja `"2"`, el código de BYMA. Ninguna fuente del proyecto dice qué plazo es cada código."""
    async with cliente(app_con(crear_app)) as http:
        cuerpo_respuesta = (await http.post(RESOLVER, json=cuerpo(pos("AL30")))).json()

    (item,) = cuerpo_respuesta["posiciones"]
    assert item["plazo_liquidacion"] == "2"


# --- Lo no resuelto sigue en la cartera ----------------------------------------------------------


async def test_el_ticker_desconocido_vuelve_en_la_respuesta_con_su_monto(crear_app) -> None:
    async with cliente(app_con(crear_app)) as http:
        datos = (await http.post(RESOLVER, json=cuerpo(pos("NOEXISTE", monto=5000.0)))).json()

    (item,) = datos["posiciones"]
    assert item["resuelta"] is False
    assert item["ticker"] is None
    assert item["ticker_declarado"] == "NOEXISTE"
    assert item["monto"] == 5000.0
    assert item["motivo"] == "no_esta_en_el_universo"


async def test_ninguna_posicion_se_pierde_por_el_camino(crear_app) -> None:
    posiciones = [pos("AL30", fila=1), pos("NOEXISTE", fila=2), pos("GGAL", fila=3)]
    async with cliente(app_con(crear_app)) as http:
        datos = (await http.post(RESOLVER, json=cuerpo(*posiciones))).json()

    assert [p["fila"] for p in datos["posiciones"]] == [1, 2, 3]
    assert datos["cobertura"]["posiciones"] == 3
    assert datos["cobertura"]["no_resueltas"] == 2


async def test_rucex_no_se_deriva_de_ruceo(crear_app) -> None:
    async with cliente(app_con(crear_app)) as http:
        datos = (await http.post(RESOLVER, json=cuerpo(pos("RUCEX")))).json()

    (item,) = datos["posiciones"]
    assert item["resuelta"] is False
    assert item["ticker"] is None
    assert item["motivo"] == "sin_tipo_de_tasa"
    # La especie hermana no aparece en ningún lado de la respuesta: no se la propone como reemplazo.
    assert "RUCEO" not in str(datos)


# --- El diagnóstico de cobertura -----------------------------------------------------------------


async def test_la_cobertura_declara_cantidad_y_porcentaje_del_monto(crear_app) -> None:
    posiciones = [pos("AL30", fila=1, monto=9000.0), pos("NOEXISTE", fila=2, monto=1000.0)]
    async with cliente(app_con(crear_app)) as http:
        datos = (await http.post(RESOLVER, json=cuerpo(*posiciones))).json()

    cobertura = datos["cobertura"]
    assert cobertura["no_resueltas"] == 1
    assert cobertura["monto_declarado"] == 10_000.0
    assert cobertura["porcentaje_no_resuelto"] == 10.0
    assert cobertura["posiciones_con_monto"] == 2
    assert cobertura["posiciones_sin_monto"] == 0


async def test_la_cobertura_declara_la_base_cuando_hay_posiciones_sin_monto(crear_app) -> None:
    posiciones = [
        pos("AL30", fila=1, monto=1000.0),
        pos("NOEXISTE", fila=2, monto=None, nominal=50_000.0),
    ]
    async with cliente(app_con(crear_app)) as http:
        datos = (await http.post(RESOLVER, json=cuerpo(*posiciones))).json()

    cobertura = datos["cobertura"]
    assert cobertura["posiciones_con_monto"] == 1
    assert cobertura["posiciones_sin_monto"] == 1
    assert cobertura["posiciones_sin_monto_no_resueltas"] == 1
    assert cobertura["porcentaje_no_resuelto"] == 0.0
    assert "posiciones_sin_monto" in {a["codigo"] for a in datos["alertas"]}


async def test_sin_ningun_monto_declarado_el_porcentaje_viaja_nulo(crear_app) -> None:
    posiciones = [pos("AL30", fila=1, monto=None, nominal=1.0)]
    async with cliente(app_con(crear_app)) as http:
        datos = (await http.post(RESOLVER, json=cuerpo(*posiciones))).json()

    assert datos["cobertura"]["porcentaje_no_resuelto"] is None
    assert "sin_base_para_el_porcentaje" in {a["codigo"] for a in datos["alertas"]}


async def test_una_cartera_vacia_devuelve_un_diagnostico_vacio_y_no_falla(crear_app) -> None:
    async with cliente(app_con(crear_app)) as http:
        respuesta = await http.post(RESOLVER, json=cuerpo())

    assert respuesta.status_code == 200
    assert respuesta.json()["cobertura"]["posiciones"] == 0
    assert respuesta.json()["alertas"] == []


# --- El contrato del pedido ----------------------------------------------------------------------


async def test_una_posicion_sin_ticker_declarado_es_un_pedido_invalido(crear_app) -> None:
    async with cliente(app_con(crear_app)) as http:
        respuesta = await http.post(RESOLVER, json={"posiciones": [{"id": "p1", "fila": 1}]})

    assert respuesta.status_code == 422


async def test_el_nominal_y_el_monto_pueden_venir_los_dos_nulos(crear_app) -> None:
    """Es una fila que F-028 marcó inválida y que igual llega: no se la descarta en silencio."""
    async with cliente(app_con(crear_app)) as http:
        respuesta = await http.post(
            RESOLVER, json={"posiciones": [{"id": "p1", "fila": 1, "ticker_declarado": "AL30"}]}
        )

    assert respuesta.status_code == 200
    assert respuesta.json()["posiciones"][0]["resuelta"] is True


async def test_se_rechaza_una_cartera_absurdamente_larga(crear_app) -> None:
    posiciones = [pos("AL30", fila=i) for i in range(1001)]
    async with cliente(app_con(crear_app)) as http:
        respuesta = await http.post(RESOLVER, json=cuerpo(*posiciones))

    assert respuesta.status_code == 422


# --- La base caída -------------------------------------------------------------------------------


async def test_sin_base_de_datos_responde_503(crear_app) -> None:
    async with cliente(crear_app(None)) as http:
        respuesta = await http.post(RESOLVER, json=cuerpo(pos("AL30")))

    assert respuesta.status_code == 503


# --- Lo que el servicio le pide a la base --------------------------------------------------------


async def test_no_se_pide_el_contraste_de_byma(crear_app) -> None:
    """Resolver un ticker no usa el tipo de cambio, así que esto no sale a la red.

    Se verifica por lo que se consultó: dos lecturas SQL y ninguna llamada al índice de BYMA. Si
    alguien enchufara `con_contraste=True`, la suite offline empezaría a salir a Internet.
    """
    conexion = FakeConexionCartera()
    async with cliente(app_con(crear_app, conexion)) as http:
        await http.post(RESOLVER, json=cuerpo(pos("AL30")))

    assert len(conexion.consultas) == 2
    assert any("public.resumen" in q for q in conexion.consultas)
    assert any(TABLA_INSTRUMENTOS in q for q in conexion.consultas)
