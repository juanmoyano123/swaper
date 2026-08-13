"""La corrida completa y su endpoint, con las fuentes simuladas.

Lo que se prueba acá es la orquestación, que es donde vive la asimetría entre fuentes: BYMA y
data912 son asíncronas y declaran sus fallos, IAMC es síncrona, llega por subida manual y lanza.
Que ninguna pueda tumbar la corrida es la propiedad que hace que un universo incompleto se
publique declarado en vez de no publicarse.

El cronograma no se le pide a ninguna fuente desde la baja de Docta: sale de `public.cashflow`, y
por eso los tests que necesitan renta fija clasificada se lo pasan a la conexión falsa por
`cronograma=` en vez de montar un mock HTTP.

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
DATA912_URL = "https://data912-test.local"

ENDPOINTS_BYMA = (
    "negociable-obligations",
    "public-bonds",
    "cedears",
    "general-equity",
    "leading-equity",
    "index-price",
)

# Experimento data912: los cinco tramos `live/`. Ver `app/ingesta/data912/cliente.py:TRAMOS_LIVE`.
TRAMOS_DATA912 = ("arg_bonds", "arg_corp", "arg_notes", "arg_cedears", "arg_stocks")


async def _no_dormir(_: float) -> None:
    return None


@pytest.fixture
def settings_de_prueba(tmp_path, monkeypatch):
    # `iamc_habilitado=True` y no el default: en producción IAMC está pausado desde el 13/08/2026,
    # pero estos tests existen para probar la orquestación *con* la fuente, que es el
    # comportamiento que hay que poder recuperar prendiendo la variable. La pausa tiene sus
    # propios tests, abajo, con la fixture `settings_iamc_pausado`.
    settings = get_settings().model_copy(
        update={
            "byma_base_url": BYMA_URL,
            "iamc_directorio": str(tmp_path),
            "iamc_habilitado": True,
            "data912_base_url": DATA912_URL,
        }
    )
    # El almacén lee del caché de settings, no del objeto que se le pasa a `consolidar`.
    monkeypatch.setattr(get_settings(), "iamc_directorio", str(tmp_path))
    return settings


@pytest.fixture
def settings_iamc_pausado(settings_de_prueba):
    return settings_de_prueba.model_copy(update={"iamc_habilitado": False})


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
    settings_de_prueba, informe_guardado
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
    assert set(resultado.snapshots) == {"byma", "iamc", "data912"}

    instrumentos = {f["ticker"]: f for f in resultado.consolidacion.filas_instrumentos}
    assert instrumentos["PLC7O"]["law"] == "Ley Argentina", "heredó de IAMC"
    assert instrumentos["PLC7O"]["tipo_tasa"] == "hard-dollar", "clasificado por el cronograma"
    assert instrumentos["PLC7O"]["archivo_origen"] == "iamc-deuda-corporativa-2026-08-05.pdf"

    precios = {f["ticker"]: f for f in resultado.consolidacion.filas_precios}
    assert precios["PLC7O"]["tir"] == pytest.approx(0.0792)
    assert precios["PLC7O"]["last_price"] == 156460.0
    assert precios["PLC7O"]["fuente"] == "byma+iamc"


# --- Experimento data912: la corrida completa con el overlay puesto -----------------------------


async def test_data912_pisa_el_precio_de_byma_y_queda_rotulado(
    settings_de_prueba, informe_guardado
) -> None:
    """Corrida de punta a punta: PLC7O llega de BYMA a 156460 y de data912 (operado) a 200 — gana
    data912, la TIR se recalcula sobre ese precio, y la fila queda rotulada `data912+iamc`."""
    conn = FakeConexionEscritura(cronograma=CASHFLOW_MINIMO)
    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_data912({"arg_corp": [{"symbol": "PLC7O", "c": 200.0, "q_op": 5, "v": 500.0}]})

        resultado = await consolidar(conn, settings_de_prueba, dormir=_no_dormir)

    assert "data912" in resultado.snapshots
    precios = {f["ticker"]: f for f in resultado.consolidacion.filas_precios}
    assert precios["PLC7O"]["last_price"] == 200.0
    assert precios["PLC7O"]["fuente"] == "data912+iamc"
    assert precios["PLC7O"]["effective_volume"] == 500.0


async def test_data912_caido_deja_el_precio_de_respaldo_byma(
    settings_de_prueba, informe_guardado
) -> None:
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
    assert precios["PLC7O"]["fuente"] == "byma+iamc"


async def test_sin_informe_la_corrida_sigue_y_pide_que_lo_suban(settings_de_prueba) -> None:
    conn = FakeConexionEscritura(cronograma=CASHFLOW_MINIMO)
    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_data912()

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
    conn = FakeConexionEscritura(cronograma=CASHFLOW_MINIMO)

    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_data912()

        resultado = await consolidar(conn, settings_de_prueba, dormir=_no_dormir)

    assert resultado.escritura.filas_por_tabla["instrumentos"] >= 1
    assert resultado.snapshots["iamc"].hubo_errores


# --- IAMC pausado (13/08/2026) ------------------------------------------------------------------
#
# La pausa tiene que cumplir dos cosas a la vez, y la segunda es la que la hace útil: no leer el
# informe, y **no arrastrar lo que el último informe dejó guardado**. Sin lo segundo el universo
# seguiría publicando la TIR del 05/08 para siempre, que es exactamente lo que se quiso evitar.


async def test_con_iamc_pausado_no_se_lee_el_informe_aunque_haya_uno_guardado(
    settings_iamc_pausado, informe_guardado
) -> None:
    conn = FakeConexionEscritura(cronograma=CASHFLOW_MINIMO)
    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_data912()

        resultado = await consolidar(conn, settings_iamc_pausado, dormir=_no_dormir)

    instrumentos = {f["ticker"]: f for f in resultado.consolidacion.filas_instrumentos}
    assert instrumentos["PLC7O"]["law"] is None, "no heredó del informe: no se leyó"
    assert instrumentos["PLC7O"]["tipo_tasa"] == "hard-dollar", "el cronograma sí clasificó"


async def test_con_iamc_pausado_las_metricas_guardadas_no_se_arrastran(
    settings_iamc_pausado, informe_guardado
) -> None:
    """El corazón de la pausa: una métrica de un informe viejo no puede volver a publicarse."""
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

        resultado = await consolidar(conn, settings_iamc_pausado, dormir=_no_dormir)

    precios = {f["ticker"]: f for f in resultado.consolidacion.filas_precios}
    for columna in ("tir", "duration", "paridad", "convexidad", "residual_value"):
        assert precios["PLC7O"][columna] is None, f"{columna} se arrastró del informe del 05/08"
    assert precios["PLC7O"]["fecha_metricas"] is None


async def test_con_iamc_pausado_la_alerta_es_informativa_y_no_pide_nada(
    settings_iamc_pausado, informe_guardado
) -> None:
    """Un rojo permanente por una decisión enseña a ignorar el rojo. No es una falla."""
    conn = FakeConexionEscritura(cronograma=CASHFLOW_MINIMO)
    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_data912()

        resultado = await consolidar(conn, settings_iamc_pausado, dormir=_no_dormir)

    (alerta,) = resultado.snapshots["iamc"].alertas
    assert alerta.codigo == "iamc_pausado"
    assert alerta.severidad == "info"
    assert alerta.accion_requerida is None
    assert not resultado.snapshots["iamc"].hubo_errores


async def test_con_iamc_pausado_la_especie_calculable_conserva_su_tir_propia(
    settings_iamc_pausado, informe_guardado
) -> None:
    """La pausa corta el arrastre de IAMC, no el cálculo de F-051."""
    conn = FakeConexionEscritura(cronograma=CASHFLOW_CALCULABLE)
    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON_EN_USD]})
        _montar_data912()

        resultado = await consolidar(conn, settings_iamc_pausado, dormir=_no_dormir)

    precios = {f["ticker"]: f for f in resultado.consolidacion.filas_precios}
    assert precios["PLC7O"]["tir"] is not None, "la calculada no depende de IAMC"
    assert precios["PLC7O"]["fuente"] == "byma+calculo"


async def test_una_emision_sin_cronograma_persistido_queda_sin_clasificar(
    settings_de_prueba, informe_guardado
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
    assert instrumentos["PLC7O"]["law"] == "Ley Argentina", "IAMC sí aportó"


async def test_byma_caido_no_deja_universo_pero_la_corrida_reporta(
    settings_de_prueba, informe_guardado
) -> None:
    conn = FakeConexionEscritura(cronograma=CASHFLOW_MINIMO)
    with respx.mock:
        for endpoint in ENDPOINTS_BYMA:
            respx.post(f"{BYMA_URL}/{endpoint}").mock(return_value=httpx.Response(500))
        _montar_data912()

        resultado = await consolidar(conn, settings_de_prueba, dormir=_no_dormir)

    assert resultado.escritura.filas_por_tabla["instrumentos"] == 0
    assert not conn.escribio_en("cashflow"), "el cronograma persistido queda intacto"
    assert resultado.snapshots["byma"].hubo_errores


async def test_toda_la_corrida_comparte_el_instante_de_captura(
    settings_de_prueba, informe_guardado
) -> None:
    conn = FakeConexionEscritura(cronograma=CASHFLOW_MINIMO)
    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_data912()

        resultado = await consolidar(conn, settings_de_prueba, dormir=_no_dormir)

    instantes = {tupla[1] for tupla in conn.filas_de("precios")}
    assert instantes == {resultado.capturado_en}


# --- El endpoint --------------------------------------------------------------------------------


async def test_el_endpoint_devuelve_conteos_cobertura_y_alertas(
    crear_app, settings_de_prueba, informe_guardado, en_rueda
) -> None:
    app = crear_app(FakeConexionEscritura(cronograma=CASHFLOW_MINIMO))
    app.dependency_overrides[get_settings] = lambda: settings_de_prueba

    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_data912()

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
    app = crear_app(FakeConexionEscritura(cronograma=CASHFLOW_MINIMO))
    app.dependency_overrides[get_settings] = lambda: settings

    async with cliente(app) as http:
        respuesta = await http.post("/api/v1/consolidar")

    mensaje = respuesta.json()["error"]["message"]
    assert "11:00" in mensaje and "17:00" in mensaje


async def test_con_forzar_corre_igual_fuera_de_la_rueda(
    crear_app, settings_de_prueba, informe_guardado, fuera_de_rueda
) -> None:
    """Probar la ingesta un domingo es legítimo mientras sea una decisión y no un accidente."""
    app = crear_app(FakeConexionEscritura(cronograma=CASHFLOW_MINIMO))
    app.dependency_overrides[get_settings] = lambda: settings_de_prueba

    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_data912()

        async with cliente(app) as http:
            respuesta = await http.post("/api/v1/consolidar?forzar=true")

    assert respuesta.status_code == 200
    assert respuesta.json()["escrito"]["instrumentos"] >= 1


async def test_en_rueda_no_hace_falta_forzar(
    crear_app, settings_de_prueba, informe_guardado, en_rueda
) -> None:
    """El guardia no estorba en el caso normal: con el mercado abierto, el default corre."""
    app = crear_app(FakeConexionEscritura(cronograma=CASHFLOW_MINIMO))
    app.dependency_overrides[get_settings] = lambda: settings_de_prueba

    with respx.mock:
        _montar_byma_con_filas({"negociable-obligations": [ESPECIE_ON]})
        _montar_data912()

        async with cliente(app) as http:
            respuesta = await http.post("/api/v1/consolidar")

    assert respuesta.status_code == 200
