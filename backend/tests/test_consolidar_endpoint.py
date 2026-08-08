"""La corrida completa y su endpoint, con las tres fuentes simuladas.

Lo que se prueba acá es la orquestación, que es donde vive la asimetría entre fuentes: BYMA y
Docta son asíncronas y declaran sus fallos, IAMC es síncrona, llega por subida manual y lanza. Que
ninguna de las tres pueda tumbar la corrida es la propiedad que hace que un universo incompleto se
publique declarado en vez de no publicarse.

El PDF real se parsea en `test_iamc_parser.py`; acá `parsear_informe` se reemplaza para no pagar
siete megas de pdfplumber en cada test de orquestación.
"""

import json
from dataclasses import dataclass, field
from datetime import date

import httpx
import pytest
import respx

from app.api.v1 import consolidar as modulo_endpoint
from app.core.config import get_settings
from app.ingesta.consolidacion import corrida as modulo_corrida
from app.ingesta.consolidacion.corrida import consolidar
from app.ingesta.iamc import InformeInvalido
from app.ingesta.iamc.almacen import guardar_informe
from tests.conftest import FakeConexionEscritura, cliente
from tests.test_consolidacion_armado import informe

BYMA_URL = "https://byma-test.local/free"
DOCTA_URL = "https://docta-test.local/cashflow?token=${DOCTA_API_TOKEN}&fromDate=2026-01-01"

ENDPOINTS_BYMA = (
    "negociable-obligations",
    "public-bonds",
    "cedears",
    "general-equity",
    "leading-equity",
    "index-price",
)


async def _no_dormir(_: float) -> None:
    return None


@pytest.fixture
def settings_de_prueba(tmp_path, monkeypatch):
    settings = get_settings().model_copy(
        update={
            "byma_base_url": BYMA_URL,
            "docta_cashflow_url": DOCTA_URL,
            "docta_api_token": "token-de-prueba",
            "iamc_directorio": str(tmp_path),
        }
    )
    # El almacén lee del caché de settings, no del objeto que se le pasa a `consolidar`.
    monkeypatch.setattr(get_settings(), "iamc_directorio", str(tmp_path))
    return settings


@pytest.fixture
def informe_guardado(settings_de_prueba, monkeypatch):
    """Un PDF en el almacén y un parser que devuelve filas conocidas sin abrirlo."""
    guardar_informe(b"%PDF-fake", fecha_informe=date(2026, 8, 5))

    @dataclass(frozen=True)
    class _Resultado:
        filas: list = field(default_factory=lambda: [informe("PLC7O", tir=7.92)])
        fecha_informe: date = date(2026, 8, 5)

    monkeypatch.setattr(modulo_corrida, "parsear_informe", lambda _: _Resultado())
    return _Resultado


@pytest.fixture
def en_rueda(monkeypatch):
    """El endpoint mira el reloj real para decidir si el mercado está abierto. Sin fijarlo, estos
    tests pasarían un martes al mediodía y darían 409 un sábado — que es exactamente el guardia que
    se agregó el 08/08/2026. Los tests del guardia en sí lo fijan al revés, abajo."""
    monkeypatch.setattr(modulo_endpoint, "en_ventana_de_rueda", lambda *_: True)


@pytest.fixture
def fuera_de_rueda(monkeypatch):
    monkeypatch.setattr(modulo_endpoint, "en_ventana_de_rueda", lambda *_: False)


def _excel_de_cashflow(filas: list[dict]) -> bytes:
    import io

    import pandas as pd

    buffer = io.BytesIO()
    pd.DataFrame(filas).to_excel(buffer, index=False)
    return buffer.getvalue()


def _montar_byma_con_filas(mapa: dict[str, list[dict]]) -> None:
    for endpoint in ENDPOINTS_BYMA:
        filas = mapa.get(endpoint, [])
        # Lista plana con al menos una fila; los endpoints vacíos devuelven una fila de relleno
        # porque cero filas es fallo reintentable en el cliente de F-004.
        respx.post(f"{BYMA_URL}/{endpoint}").mock(
            return_value=httpx.Response(200, json=filas or [{"symbol": f"RELLENO-{endpoint}"}])
        )


def _montar_docta(filas: list[dict]) -> None:
    respx.get(url__startswith="https://docta-test.local/cashflow").mock(
        return_value=httpx.Response(200, content=_excel_de_cashflow(filas))
    )


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


# --- La corrida completa ------------------------------------------------------------------------


async def test_una_corrida_con_las_tres_fuentes_escribe_las_cuatro_tablas(
    settings_de_prueba, informe_guardado
) -> None:
    conn = FakeConexionEscritura()
    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_docta(CASHFLOW_MINIMO)

        resultado = await consolidar(conn, settings_de_prueba, dormir=_no_dormir)

    escrito = resultado.escritura.filas_por_tabla
    assert escrito["instrumentos"] >= 1
    assert escrito["precios"] == escrito["instrumentos"]
    assert escrito["cashflow"] == 1
    assert set(resultado.snapshots) == {"byma", "iamc", "docta"}

    instrumentos = {f["ticker"]: f for f in resultado.consolidacion.filas_instrumentos}
    assert instrumentos["PLC7O"]["law"] == "Ley Argentina", "heredó de IAMC"
    assert instrumentos["PLC7O"]["tipo_tasa"] == "hard-dollar", "clasificado por el cronograma"
    assert instrumentos["PLC7O"]["archivo_origen"] == "iamc-deuda-corporativa-2026-08-05.pdf"

    precios = {f["ticker"]: f for f in resultado.consolidacion.filas_precios}
    assert precios["PLC7O"]["tir"] == pytest.approx(0.0792)
    assert precios["PLC7O"]["last_price"] == 156460.0
    assert precios["PLC7O"]["fuente"] == "byma+iamc"


async def test_sin_informe_la_corrida_sigue_y_pide_que_lo_suban(settings_de_prueba) -> None:
    conn = FakeConexionEscritura()
    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_docta(CASHFLOW_MINIMO)

        resultado = await consolidar(conn, settings_de_prueba, dormir=_no_dormir)

    assert resultado.escritura.filas_por_tabla["instrumentos"] >= 1
    instrumentos = {f["ticker"]: f for f in resultado.consolidacion.filas_instrumentos}
    assert instrumentos["PLC7O"]["law"] is None
    assert instrumentos["PLC7O"]["tipo_tasa"] == "hard-dollar", "el cronograma sí llegó"

    (alerta,) = resultado.snapshots["iamc"].alertas
    assert "POST /api/v1/iamc/informe" in alerta.accion_requerida


async def test_un_informe_que_dejo_de_parsearse_no_tumba_la_corrida(
    settings_de_prueba, monkeypatch
) -> None:
    guardar_informe(b"%PDF-fake", fecha_informe=date(2026, 8, 5))

    def _explotar(_):
        raise InformeInvalido("sección desconocida", seccion="NUEVA")

    monkeypatch.setattr(modulo_corrida, "parsear_informe", _explotar)
    conn = FakeConexionEscritura()

    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_docta(CASHFLOW_MINIMO)

        resultado = await consolidar(conn, settings_de_prueba, dormir=_no_dormir)

    assert resultado.escritura.filas_por_tabla["instrumentos"] >= 1
    assert resultado.snapshots["iamc"].hubo_errores


async def test_docta_caido_deja_la_renta_fija_sin_clasificar_y_no_toca_el_cronograma(
    settings_de_prueba, informe_guardado
) -> None:
    conn = FakeConexionEscritura()
    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        respx.get(url__startswith="https://docta-test.local/cashflow").mock(
            return_value=httpx.Response(500)
        )

        resultado = await consolidar(conn, settings_de_prueba, dormir=_no_dormir)

    assert not conn.escribio_en("cashflow"), "sin cronograma usable se conserva el persistido"
    instrumentos = {f["ticker"]: f for f in resultado.consolidacion.filas_instrumentos}
    assert instrumentos["PLC7O"]["tipo_tasa"] is None
    assert instrumentos["PLC7O"]["law"] == "Ley Argentina", "IAMC sí aportó"


async def test_byma_caido_no_deja_universo_pero_la_corrida_reporta(
    settings_de_prueba, informe_guardado
) -> None:
    conn = FakeConexionEscritura()
    with respx.mock:
        for endpoint in ENDPOINTS_BYMA:
            respx.post(f"{BYMA_URL}/{endpoint}").mock(return_value=httpx.Response(500))
        _montar_docta(CASHFLOW_MINIMO)

        resultado = await consolidar(conn, settings_de_prueba, dormir=_no_dormir)

    assert resultado.escritura.filas_por_tabla["instrumentos"] == 0
    assert resultado.escritura.filas_por_tabla["cashflow"] == 1, "el cronograma sí se escribió"
    assert resultado.snapshots["byma"].hubo_errores


async def test_toda_la_corrida_comparte_el_instante_de_captura(
    settings_de_prueba, informe_guardado
) -> None:
    conn = FakeConexionEscritura()
    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_docta(CASHFLOW_MINIMO)

        resultado = await consolidar(conn, settings_de_prueba, dormir=_no_dormir)

    instantes = {tupla[1] for tupla in conn.filas_de("precios")}
    assert instantes == {resultado.capturado_en}


# --- El endpoint --------------------------------------------------------------------------------


async def test_el_endpoint_devuelve_conteos_cobertura_y_alertas(
    crear_app, settings_de_prueba, informe_guardado, en_rueda
) -> None:
    app = crear_app(FakeConexionEscritura())
    app.dependency_overrides[get_settings] = lambda: settings_de_prueba

    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_docta(CASHFLOW_MINIMO)

        async with cliente(app) as http:
            respuesta = await http.post("/api/v1/consolidar")

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
        respuesta = await http.post("/api/v1/consolidar")

    assert respuesta.status_code == 503


async def test_el_endpoint_no_publica_la_url_de_docta(
    crear_app, settings_de_prueba, informe_guardado, en_rueda
) -> None:
    """La URL del feed lleva el token adentro: no puede salir en una respuesta ni en una alerta."""
    app = crear_app(FakeConexionEscritura())
    app.dependency_overrides[get_settings] = lambda: settings_de_prueba

    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        # 404 y no 500: el endpoint no puede inyectar `dormir`, así que un fallo reintentable
        # haría esperar de verdad los 3+6+9+12 segundos de la política.
        respx.get(url__startswith="https://docta-test.local/cashflow").mock(
            return_value=httpx.Response(404)
        )

        async with cliente(app) as http:
            respuesta = await http.post("/api/v1/consolidar")

    assert "token-de-prueba" not in respuesta.text


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
    conn = FakeConexionEscritura()
    app = crear_app(conn)
    app.dependency_overrides[get_settings] = lambda: settings_de_prueba

    async with cliente(app) as http:
        respuesta = await http.post("/api/v1/consolidar")

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
    app = crear_app(FakeConexionEscritura())
    app.dependency_overrides[get_settings] = lambda: settings

    async with cliente(app) as http:
        respuesta = await http.post("/api/v1/consolidar")

    mensaje = respuesta.json()["error"]["message"]
    assert "11:00" in mensaje and "17:00" in mensaje


async def test_con_forzar_corre_igual_fuera_de_la_rueda(
    crear_app, settings_de_prueba, informe_guardado, fuera_de_rueda
) -> None:
    """Probar la ingesta un domingo es legítimo mientras sea una decisión y no un accidente."""
    app = crear_app(FakeConexionEscritura())
    app.dependency_overrides[get_settings] = lambda: settings_de_prueba

    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_docta(CASHFLOW_MINIMO)

        async with cliente(app) as http:
            respuesta = await http.post("/api/v1/consolidar?forzar=true")

    assert respuesta.status_code == 200
    assert respuesta.json()["escrito"]["instrumentos"] >= 1


async def test_en_rueda_no_hace_falta_forzar(
    crear_app, settings_de_prueba, informe_guardado, en_rueda
) -> None:
    """El guardia no estorba en el caso normal: con el mercado abierto, el default corre."""
    app = crear_app(FakeConexionEscritura())
    app.dependency_overrides[get_settings] = lambda: settings_de_prueba

    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_docta(CASHFLOW_MINIMO)

        async with cliente(app) as http:
            respuesta = await http.post("/api/v1/consolidar")

    assert respuesta.status_code == 200
