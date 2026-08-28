"""La corrida completa y su endpoint, con las fuentes simuladas.

Lo que se prueba acá es la orquestación: BYMA y data912 son asíncronas y declaran sus fallos en el
snapshot en vez de lanzar. Que ninguna pueda tumbar la corrida es la propiedad que hace que un
universo incompleto se publique declarado en vez de no publicarse.

El cronograma no se le pide a ninguna fuente desde la baja de Docta: sale de `public.cashflow`, y
por eso los tests que necesitan renta fija clasificada se lo pasan a la conexión falsa por
`cronograma=` en vez de montar un mock HTTP.

Los tests de la tercera fuente —IAMC, síncrona y por subida manual— se fueron con la ingesta el
26/08/2026. Lo que queda de ellos es la invariante que sobrevive: los atributos de emisión y las
métricas que sólo esa fuente llenaba salen `None` y la corrida no los arrastra de ningún lado.

Los tests del endpoint mandan credencial de cron: desde la Tanda 3 el router está detrás de
`cron_o_asesor`. Los de la corrida no pasan por HTTP y no la necesitan.
"""

import json
from datetime import date

import httpx
import pytest
import respx

from app.api.v1 import consolidar as modulo_endpoint
from app.core.config import get_settings
from app.ingesta.consolidacion.corrida import consolidar
from tests.conftest import AUTORIZACION_DE_CRON, FakeConexionEscritura, cliente

BYMA_URL = "https://byma-test.local/free"
DATA912_URL = "https://data912-test.local"

ENDPOINTS_BYMA = (
    "negociable-obligations",
    "public-bonds",
    "cedears",
    "general-equity",
    "leading-equity",
    "lebacs",
    "index-price",
)

# Experimento data912: los cinco tramos `live/`. Ver `app/ingesta/data912/cliente.py:TRAMOS_LIVE`.
TRAMOS_DATA912 = ("arg_bonds", "arg_corp", "arg_notes", "arg_cedears", "arg_stocks")


async def _no_dormir(_: float) -> None:
    return None


@pytest.fixture
def settings_de_prueba():
    return get_settings().model_copy(
        update={"byma_base_url": BYMA_URL, "data912_base_url": DATA912_URL}
    )


@pytest.fixture
def en_rueda(monkeypatch):
    """El endpoint mira el reloj real para decidir si el mercado está abierto. Sin fijarlo, estos
    tests pasarían un martes al mediodía y darían 409 un sábado — que es exactamente el guardia que
    se agregó el 08/08/2026. Los tests del guardia en sí lo fijan al revés, abajo."""
    monkeypatch.setattr(modulo_endpoint, "en_ventana_de_rueda", lambda *_: True)


@pytest.fixture
def fuera_de_rueda(monkeypatch):
    monkeypatch.setattr(modulo_endpoint, "en_ventana_de_rueda", lambda *_: False)


def _montar_byma_con_filas(mapa: dict[str, list[dict]]) -> None:
    for endpoint in ENDPOINTS_BYMA:
        filas = mapa.get(endpoint, [])
        # Lista plana con al menos una fila; los endpoints vacíos devuelven una fila de relleno
        # porque cero filas es fallo reintentable en el cliente de F-004.
        respx.post(f"{BYMA_URL}/{endpoint}").mock(
            return_value=httpx.Response(200, json=filas or [{"symbol": f"RELLENO-{endpoint}"}])
        )


def _montar_data912(mapa: dict[str, list[dict]] | None = None) -> None:
    """Sin `mapa`, cada tramo responde una fila de relleno con precio 0 — nunca un precio válido
    para el overlay (`c=0` no pasa `tiene_precio_valido`), así que data912 "está" (aparece en los
    snapshots de la corrida) pero no pisa ni agrega nada: el comportamiento de estos tests es el
    mismo que antes de que data912 existiera. Relleno y no lista vacía por la misma razón que
    `_montar_byma_con_filas`: una lista vacía es fallo reintentable, y los tests que pegan al
    endpoint HTTP real no pueden inyectar `dormir` — reintentar de verdad los cinco tramos tardaría
    minutos. Pasar `mapa` para que un tramo sí traiga filas con precio."""
    mapa = mapa or {}
    for tramo in TRAMOS_DATA912:
        filas = mapa.get(tramo, [])
        respx.get(f"{DATA912_URL}/live/{tramo}").mock(
            return_value=httpx.Response(200, json=filas or [{"symbol": f"RELLENO-{tramo}", "c": 0}])
        )


def _montar_data912_caido() -> None:
    for tramo in TRAMOS_DATA912:
        respx.get(f"{DATA912_URL}/live/{tramo}").mock(return_value=httpx.Response(500))


CASHFLOW_MINIMO = [
    {
        "ticker": "PLC7O",
        "type": "ON",
        "issue_date": "2020-09-04",
        "payment_date": "2027-01-09",
        "capital": 0.0,
        "interest_rate": 5.0,
        "interest_amount": 2.5,
        "residual_value": 100.0,
        "cash_flow": 2.5,
        "days_convention": "30/360",
        "theoretical_payment_date": "2027-01-09",
        "theoretical_days_before": 180,
    }
]

ESPECIE_ON = {
    "symbol": "PLC7O",
    "denominationCcy": "ARS",
    "settlementType": "2",
    "trade": 156460.0,
    "volumeAmount": 1000.0,
    "bidPrice": 156000.0,
    "offerPrice": 157000.0,
    "maturityDate": "2030-07-09",
}

# La misma especie cotizando en dólares, que es la condición para que F-051 le calcule la TIR:
# precio y flujo en la misma moneda. El precio es del orden del residual del cronograma para que
# la TIR salga en un rango creíble y no la descarte la sanidad.
ESPECIE_ON_EN_USD = {**ESPECIE_ON, "denominationCcy": "USD", "trade": 98.0}

# `CASHFLOW_MINIMO` alcanza para clasificar por submarket —eso sólo mira `type`— pero no para
# calcular: sus fechas son strings y `indexar_cronograma` descarta la fila por `sin_fecha`, que es
# lo que pasa acá y no en producción, donde asyncpg ya devuelve `date`. Este cronograma trae fechas
# nativas y la amortización final, sin la cual no hay flujo que descontar.
_PAGO_BASE = {"ticker": "PLC7O", "type": "ON", "issue_date": date(2020, 9, 4), "interest_rate": 5.0}
CASHFLOW_CALCULABLE = [
    {
        **_PAGO_BASE,
        "payment_date": date(2027, 1, 9),
        "capital": 0.0,
        "interest_amount": 2.5,
        "residual_value": 100.0,
        "cash_flow": 2.5,
    },
    {
        **_PAGO_BASE,
        "payment_date": date(2027, 7, 9),
        "capital": 100.0,
        "interest_amount": 2.5,
        "residual_value": 0.0,
        "cash_flow": 102.5,
    },
]


# --- La corrida completa ------------------------------------------------------------------------


async def test_una_corrida_completa_escribe_el_universo_y_no_toca_el_cronograma(
    settings_de_prueba,
) -> None:
    conn = FakeConexionEscritura(cronograma=CASHFLOW_MINIMO)
    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_data912()

        resultado = await consolidar(conn, settings_de_prueba, dormir=_no_dormir)

    escrito = resultado.escritura.filas_por_tabla
    assert escrito["instrumentos"] >= 1
    assert escrito["precios"] == escrito["instrumentos"]
    assert escrito["cashflow"] == 0, "el cronograma se lee, ya no se escribe"
    assert set(resultado.snapshots) == {"byma", "data912"}

    instrumentos = {f["ticker"]: f for f in resultado.consolidacion.filas_instrumentos}
    assert instrumentos["PLC7O"]["tipo_tasa"] == "hard-dollar", "clasificado por el cronograma"
    assert instrumentos["PLC7O"]["law"] is None, "la ley la traía IAMC; el COALESCE la conserva"
    assert instrumentos["PLC7O"]["archivo_origen"] == "BYMA"

    precios = {f["ticker"]: f for f in resultado.consolidacion.filas_precios}
    assert precios["PLC7O"]["last_price"] == 156460.0
    # PLC7O cotiza en pesos y su flujo está en dólares: no se calcula, y no hay otra fuente.
    assert precios["PLC7O"]["tir"] is None
    assert precios["PLC7O"]["fuente"] == "byma"


# --- Experimento data912: la corrida completa con el overlay puesto -----------------------------


async def test_data912_pisa_el_precio_de_byma_y_queda_rotulado(settings_de_prueba) -> None:
    """Corrida de punta a punta: PLC7O llega de BYMA a 156460 y de data912 (operado) a 200 — gana
    data912, y la fila queda rotulada con la fuente del precio que efectivamente muestra."""
    conn = FakeConexionEscritura(cronograma=CASHFLOW_MINIMO)
    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_data912({"arg_corp": [{"symbol": "PLC7O", "c": 200.0, "q_op": 5, "v": 500.0}]})

        resultado = await consolidar(conn, settings_de_prueba, dormir=_no_dormir)

    assert "data912" in resultado.snapshots
    precios = {f["ticker"]: f for f in resultado.consolidacion.filas_precios}
    assert precios["PLC7O"]["last_price"] == 200.0
    assert precios["PLC7O"]["fuente"] == "data912"
    assert precios["PLC7O"]["effective_volume"] == 500.0


async def test_data912_caido_deja_el_precio_de_respaldo_byma(settings_de_prueba) -> None:
    """Con los cinco tramos de data912 caídos, la corrida sigue exactamente como si data912 no
    existiera: el precio y la fuente son los de BYMA."""
    conn = FakeConexionEscritura(cronograma=CASHFLOW_MINIMO)
    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_data912_caido()

        resultado = await consolidar(conn, settings_de_prueba, dormir=_no_dormir)

    assert resultado.snapshots["data912"].hubo_errores
    precios = {f["ticker"]: f for f in resultado.consolidacion.filas_precios}
    assert precios["PLC7O"]["last_price"] == 156460.0
    assert precios["PLC7O"]["fuente"] == "byma"


async def test_las_metricas_guardadas_no_se_arrastran_a_una_corrida_nueva(
    settings_de_prueba,
) -> None:
    """Lo que quedó guardado de un informe viejo no vuelve a publicarse (26/08/2026).

    La corrida ya no lee las métricas previas de `precios` — la lectura se borró junto con IAMC —
    y este test lo fija: aunque la base tenga una TIR del 05/08 para PLC7O, la fila nueva sale
    vacía. Sin esto, reintroducir un arrastre "para no publicar un universo sin TIR" volvería a
    poner la métrica de un día al lado del precio de otro.
    """
    previas = [
        {
            "ticker": "PLC7O",
            "tir": 0.0792,
            "duration": 3.1,
            "paridad": 0.88,
            "convexidad": 12.0,
            "residual_value": 100.0,
            "fecha_metricas": date(2026, 8, 5),
        }
    ]
    conn = FakeConexionEscritura(cronograma=CASHFLOW_MINIMO, metricas_previas=previas)
    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_data912()

        resultado = await consolidar(conn, settings_de_prueba, dormir=_no_dormir)

    precios = {f["ticker"]: f for f in resultado.consolidacion.filas_precios}
    for columna in ("tir", "duration", "paridad", "convexidad", "residual_value"):
        assert precios["PLC7O"][columna] is None, f"{columna} se arrastró del informe del 05/08"
    assert precios["PLC7O"]["fecha_metricas"] is None


async def test_una_especie_calculable_publica_su_tir_propia(settings_de_prueba) -> None:
    """El cálculo de F-051 no dependía de IAMC y por eso quedó en pie cuando se la eliminó."""
    conn = FakeConexionEscritura(cronograma=CASHFLOW_CALCULABLE)
    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON_EN_USD]})
        _montar_data912()

        resultado = await consolidar(conn, settings_de_prueba, dormir=_no_dormir)

    precios = {f["ticker"]: f for f in resultado.consolidacion.filas_precios}
    assert precios["PLC7O"]["tir"] is not None
    assert precios["PLC7O"]["fuente"] == "byma+calculo"


async def test_una_emision_sin_cronograma_persistido_queda_sin_clasificar(
    settings_de_prueba,
) -> None:
    """El caso de una emisión nueva después de la baja de Docta: cotiza pero nadie publica su
    cronograma, así que entra al universo sin tipo de tasa y sin métricas propias — declarada
    faltante, nunca clasificada por analogía con una hermana (regla 1)."""
    conn = FakeConexionEscritura()
    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_data912()

        resultado = await consolidar(conn, settings_de_prueba, dormir=_no_dormir)

    assert not conn.escribio_en("cashflow"), "la tabla del cronograma no se toca"
    instrumentos = {f["ticker"]: f for f in resultado.consolidacion.filas_instrumentos}
    assert instrumentos["PLC7O"]["tipo_tasa"] is None


async def test_byma_caido_no_deja_universo_pero_la_corrida_reporta(settings_de_prueba) -> None:
    conn = FakeConexionEscritura(cronograma=CASHFLOW_MINIMO)
    with respx.mock:
        for endpoint in ENDPOINTS_BYMA:
            respx.post(f"{BYMA_URL}/{endpoint}").mock(return_value=httpx.Response(500))
        _montar_data912()

        resultado = await consolidar(conn, settings_de_prueba, dormir=_no_dormir)

    assert resultado.escritura.filas_por_tabla["instrumentos"] == 0
    assert not conn.escribio_en("cashflow"), "el cronograma persistido queda intacto"
    assert resultado.snapshots["byma"].hubo_errores


async def test_toda_la_corrida_comparte_el_instante_de_captura(settings_de_prueba) -> None:
    conn = FakeConexionEscritura(cronograma=CASHFLOW_MINIMO)
    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_data912()

        resultado = await consolidar(conn, settings_de_prueba, dormir=_no_dormir)

    instantes = {tupla[1] for tupla in conn.filas_de("precios")}
    assert instantes == {resultado.capturado_en}


# --- El endpoint --------------------------------------------------------------------------------


async def test_el_endpoint_devuelve_conteos_cobertura_y_alertas(
    crear_app, settings_de_prueba, en_rueda
) -> None:
    app = crear_app(FakeConexionEscritura(cronograma=CASHFLOW_MINIMO))
    app.dependency_overrides[get_settings] = lambda: settings_de_prueba

    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_data912()

        async with cliente(app) as http:
            respuesta = await http.post("/api/v1/consolidar", headers=AUTORIZACION_DE_CRON)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"capturado_en", "snapshots", "escrito", "cobertura", "alertas"}
    assert cuerpo["escrito"]["instrumentos"] >= 1
    assert {c["campo"] for c in cuerpo["cobertura"]} >= {"law", "tir", "last_price", "px_bid"}
    # Las filas no viajan: son miles y ya están en la base.
    assert "filas" not in json.dumps(cuerpo)[:200]


async def test_sin_base_el_endpoint_responde_503(crear_app, en_rueda) -> None:
    app = crear_app(None)

    async with cliente(app) as http:
        respuesta = await http.post("/api/v1/consolidar", headers=AUTORIZACION_DE_CRON)

    assert respuesta.status_code == 503


# --- El guardia de rueda cerrada (08/08/2026) ---------------------------------------------------
#
# Correr esto con el mercado cerrado no falla, y ese es el problema: BYMA responde un universo
# parcial, se escribe igual, y el indicador de frescura pasa a declarar hoy sobre datos de la última
# rueda de verdad. Pasó un sábado —466 filas, cero precios, cero TIR— y hubo que borrarlas a mano.


async def test_fuera_de_la_rueda_responde_409_y_no_toca_las_fuentes(
    crear_app, settings_de_prueba, fuera_de_rueda
) -> None:
    """Sin `respx.mock` montado: si el endpoint saliera a la red, el test reventaría. Que pase es
    la prueba de que ni siquiera se molesta a BYMA."""
    conn = FakeConexionEscritura(cronograma=CASHFLOW_MINIMO)
    app = crear_app(conn)
    app.dependency_overrides[get_settings] = lambda: settings_de_prueba

    async with cliente(app) as http:
        respuesta = await http.post("/api/v1/consolidar", headers=AUTORIZACION_DE_CRON)

    assert respuesta.status_code == 409
    error = respuesta.json()["error"]
    assert error["code"] == "fuera_de_la_rueda", "código propio, no el `conflict` genérico"
    assert "lunes a viernes" in error["message"]
    assert "forzar" in error["message"]
    assert not conn.escribio_en("precios"), "no se escribió nada"


async def test_el_mensaje_del_409_nombra_la_ventana_configurada(
    crear_app, settings_de_prueba, fuera_de_rueda
) -> None:
    """La ventana no está hardcodeada en el mensaje: sale de Settings, así que si cambia el horario
    el texto lo acompaña."""
    settings = settings_de_prueba.model_copy(
        update={"ingesta_rueda_desde": "11:00", "ingesta_rueda_hasta": "17:00"}
    )
    app = crear_app(FakeConexionEscritura(cronograma=CASHFLOW_MINIMO))
    app.dependency_overrides[get_settings] = lambda: settings

    async with cliente(app) as http:
        respuesta = await http.post("/api/v1/consolidar", headers=AUTORIZACION_DE_CRON)

    mensaje = respuesta.json()["error"]["message"]
    assert "11:00" in mensaje and "17:00" in mensaje


async def test_con_forzar_corre_igual_fuera_de_la_rueda(
    crear_app, settings_de_prueba, fuera_de_rueda
) -> None:
    """Probar la ingesta un domingo es legítimo mientras sea una decisión y no un accidente."""
    app = crear_app(FakeConexionEscritura(cronograma=CASHFLOW_MINIMO))
    app.dependency_overrides[get_settings] = lambda: settings_de_prueba

    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_data912()

        async with cliente(app) as http:
            respuesta = await http.post(
                "/api/v1/consolidar?forzar=true", headers=AUTORIZACION_DE_CRON
            )

    assert respuesta.status_code == 200
    assert respuesta.json()["escrito"]["instrumentos"] >= 1


async def test_en_rueda_no_hace_falta_forzar(crear_app, settings_de_prueba, en_rueda) -> None:
    """El guardia no estorba en el caso normal: con el mercado abierto, el default corre."""
    app = crear_app(FakeConexionEscritura(cronograma=CASHFLOW_MINIMO))
    app.dependency_overrides[get_settings] = lambda: settings_de_prueba

    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_data912()

        async with cliente(app) as http:
            respuesta = await http.post("/api/v1/consolidar", headers=AUTORIZACION_DE_CRON)

    assert respuesta.status_code == 200
