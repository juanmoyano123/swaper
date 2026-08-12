"""Los dos endpoints del calendario: el del universo y el de una cartera dada — F-015.

Lo que se prueba acá es el contrato HTTP —qué viaja, qué pasa sin base y qué se rechaza—; la
matemática y el armado de la grilla ya están probados sin levantar nada en `test_calendario_cupones`
y `test_calendario_grilla`.

La conexión falsa despacha por SQL: el universo, el cronograma y las paridades salen de tres
consultas distintas, y un fake que devolviera lo mismo a las tres no probaría que cada capa lee lo
que dice leer.
"""

from datetime import date
from typing import Any

import pytest

from app.calendario.grilla import ventana
from tests.conftest import cliente

UNIVERSO = "/api/v1/calendario/universo"
CARTERA = "/api/v1/calendario/cartera"

# Dos emisiones que no comparten raíz, para que la deduplicación no cambie de tema: una ON hard
# dollar con dos especies de liquidación y una LECAP en pesos.
FILAS_UNIVERSO: list[dict[str, Any]] = [
    {
        "ticker": "RUCED",
        "clase_activo": "on_corporativo",
        "tipo_tasa": "hard-dollar",
        "tir": 0.0717,
        "tna": None,
        "duration": 1.09,
        "maturity": date(2028, 3, 1),
        "lastPrice": 43.77,
        "effectiveVolume": 1_000.0,
        "moneda_cotizacion": "USD",
    },
    {
        "ticker": "RUCEO",
        "clase_activo": "on_corporativo",
        "tipo_tasa": "hard-dollar",
        "tir": 0.0717,
        "tna": None,
        "duration": 1.09,
        "maturity": date(2028, 3, 1),
        "lastPrice": 62_000.0,
        "effectiveVolume": 500.0,
        "moneda_cotizacion": "ARS",
    },
    {
        "ticker": "S30J6",
        "clase_activo": "bono_soberano",
        "tipo_tasa": "tasa-fija",
        "tir": None,
        "tna": 0.35,
        "duration": 0.5,
        "maturity": date(2027, 6, 30),
        "lastPrice": 130.0,
        "effectiveVolume": 9_000.0,
        "moneda_cotizacion": "ARS",
    },
]

# Las fechas del cronograma se arman **relativas al día de la corrida** y no fijas. Los endpoints no
# exponen un parámetro `hoy` —sería un botón para viajar en el tiempo que nadie pidió— así que la
# grilla siempre habla de los doce meses que vienen de hoy: un cronograma con fechas literales haría
# pasar estos tests hasta que el calendario los alcanzara y fallaría después por el día, no por el
# código.
VENTANA = ventana(date.today())
PRIMER_MES, MES_DEL_CAPITAL, MES_DE_LA_LECAP = VENTANA[0], VENTANA[6], VENTANA[10]


def _dia(mes: tuple[int, int]) -> date:
    return date(mes[0], mes[1], 1)


def _etiqueta(mes: tuple[int, int]) -> str:
    return f"{mes[1]:02d}/{mes[0]}"


FILAS_CASHFLOW: list[dict[str, Any]] = [
    {
        "ticker": "RUCEO",
        "issue_date": date(2024, 3, 1),
        # Un pago ya ocurrido: es el que fija el residual vivo y desde cuándo devengan los corridos.
        "payment_date": date.today().replace(day=1),
        "capital": 0.0,
        "interest_amount": 3.5,
        "residual_value": 100.0,
        "cash_flow": 3.5,
    },
    {
        "ticker": "RUCEO",
        "issue_date": date(2024, 3, 1),
        "payment_date": _dia(PRIMER_MES),
        "capital": 0.0,
        "interest_amount": 3.5,
        "residual_value": 100.0,
        "cash_flow": 3.5,
    },
    {
        "ticker": "RUCEO",
        "issue_date": date(2024, 3, 1),
        "payment_date": _dia(MES_DEL_CAPITAL),
        "capital": 100.0,
        "interest_amount": 3.5,
        "residual_value": 0.0,
        "cash_flow": 103.5,
    },
    {
        "ticker": "S30J6",
        "issue_date": date(2025, 6, 30),
        "payment_date": _dia(MES_DE_LA_LECAP),
        "capital": 100.0,
        "interest_amount": 20.0,
        "residual_value": 0.0,
        "cash_flow": 120.0,
    },
]

FILAS_PARIDAD: list[dict[str, Any]] = [
    {"ticker": "RUCED", "paridad": 1.0055},
    {"ticker": "RUCEO", "paridad": 1.0055},
    {"ticker": "S30J6", "paridad": 0.98},
]


class FakeConexionCalendario:
    """Conexión falsa que despacha por consulta: universo, cronograma o paridades."""

    def __init__(
        self,
        universo: list[dict[str, Any]] | None = None,
        cashflow: list[dict[str, Any]] | None = None,
        paridades: list[dict[str, Any]] | None = None,
    ) -> None:
        self.universo = FILAS_UNIVERSO if universo is None else universo
        self.cashflow = FILAS_CASHFLOW if cashflow is None else cashflow
        self.paridades = FILAS_PARIDAD if paridades is None else paridades
        self.consultas: list[str] = []

    async def fetch(self, query: str, *_: Any) -> list[dict[str, Any]]:
        self.consultas.append(query)
        if "public.cashflow" in query:
            return self.cashflow
        if query.startswith("SELECT ticker, paridad"):
            return self.paridades
        return self.universo


@pytest.fixture
def app_con_calendario(crear_app):
    def _crear(**kwargs):
        return crear_app(FakeConexionCalendario(**kwargs))

    return _crear


# --- El calendario del universo -------------------------------------------------------------------


async def test_el_universo_devuelve_siempre_doce_meses(app_con_calendario) -> None:
    async with cliente(app_con_calendario()) as http:
        respuesta = await http.get(UNIVERSO)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert len(cuerpo["meses"]) == 12
    assert cuerpo["resumen"]["con_montos"] is False


async def test_el_universo_no_trae_totales_en_plata(app_con_calendario) -> None:
    """Sin montos no hay plata: los números son fracciones del monto que se invierta."""
    async with cliente(app_con_calendario()) as http:
        cuerpo = (await http.get(UNIVERSO)).json()

    assert cuerpo["resumen"]["renta_anual"] is None
    assert all(mes["renta"] is None for mes in cuerpo["meses"])


async def test_el_universo_trabaja_sobre_la_vista_colapsada(app_con_calendario) -> None:
    """RUCED y RUCEO son el mismo bono: en la grilla del selector la emisión cuenta una sola vez.

    Mostrar las dos como candidatas para tapar el mismo mes haría creer que se diversifica comprando
    dos veces el mismo crédito.
    """
    async with cliente(app_con_calendario()) as http:
        cuerpo = (await http.get(UNIVERSO)).json()

    tickers = {i["ticker"] for mes in cuerpo["meses"] for i in mes["instrumentos"]}
    assert tickers & {"RUCED", "RUCEO"} != set()
    assert len(tickers & {"RUCED", "RUCEO"}) == 1


async def test_el_detalle_se_puede_apagar(app_con_calendario) -> None:
    async with cliente(app_con_calendario()) as http:
        cuerpo = (await http.get(UNIVERSO, params={"detalle": "false"})).json()

    assert len(cuerpo["meses"]) == 12
    assert all("instrumentos" not in mes for mes in cuerpo["meses"])


async def test_el_instrumento_sin_cronograma_sale_nombrado_en_las_alertas(
    app_con_calendario,
) -> None:
    """No se le inventa un cronograma parecido: se lo nombra y queda fuera de la grilla."""
    async with cliente(app_con_calendario(cashflow=[])) as http:
        cuerpo = (await http.get(UNIVERSO)).json()

    alerta = next(a for a in cuerpo["alertas"] if a["codigo"] == "instrumento_sin_cronograma")
    assert set(alerta["detalle"]["tickers"]) == {"RUCED", "S30J6"} or set(
        alerta["detalle"]["tickers"]
    ) == {"RUCEO", "S30J6"}


async def test_el_universo_declara_siempre_cuanto_del_universo_cubre(app_con_calendario) -> None:
    """Va también cuando entran todas: si la alerta apareciera sólo ante un faltante, una lista
    vacía no distinguiría "no falta nada" de "nadie lo midió"."""
    async with cliente(app_con_calendario()) as http:
        cuerpo = (await http.get(UNIVERSO)).json()

    alerta = next(a for a in cuerpo["alertas"] if a["codigo"] == "cobertura_del_calendario")
    assert alerta["severidad"] == "info"
    assert alerta["detalle"]["cobertura"] == 1.0
    assert alerta["detalle"]["con_calendario"] == alerta["detalle"]["emisiones"]


async def test_la_cobertura_se_alerta_aunque_ningun_faltante_tenga_nombre(
    app_con_calendario,
) -> None:
    """El caso que motivó la alerta: 360 de 431 emisiones afuera y `sin_paridad` sin nombrar a
    ninguna, porque ninguna declara rendimiento ni duración. Con el criterio del motor solo, la
    respuesta salía con la lista de alertas **vacía**.

    Acá se reproduce en chico: se le saca la paridad a todo el universo y se le sacan las métricas,
    así ningún instrumento entra al listado de `sin_paridad` — y la cobertura igual lo dice.
    """
    sin_metricas = [fila | {"tir": None, "tna": None, "duration": None} for fila in FILAS_UNIVERSO]
    sin_paridad = [{"ticker": fila["ticker"], "paridad": None} for fila in FILAS_PARIDAD]
    async with cliente(app_con_calendario(universo=sin_metricas, paridades=sin_paridad)) as http:
        cuerpo = (await http.get(UNIVERSO)).json()

    codigos = [a["codigo"] for a in cuerpo["alertas"]]
    assert "instrumento_sin_paridad" not in codigos
    alerta = next(a for a in cuerpo["alertas"] if a["codigo"] == "cobertura_del_calendario")
    assert alerta["severidad"] == "advertencia"
    assert alerta["detalle"]["con_calendario"] == 0
    assert alerta["detalle"]["cobertura"] == 0.0
    assert alerta["detalle"]["sin_paridad"] == alerta["detalle"]["emisiones"]


async def test_la_alerta_de_cobertura_no_lista_tickers(app_con_calendario) -> None:
    """Es un agregado a propósito: nombrar a los cientos que no cotizan haría un padrón del universo
    entero donde nadie miraría ninguno. Los que sí hay que revisar los nombra `sin_paridad`."""
    async with cliente(app_con_calendario()) as http:
        cuerpo = (await http.get(UNIVERSO)).json()

    alerta = next(a for a in cuerpo["alertas"] if a["codigo"] == "cobertura_del_calendario")
    assert "tickers" not in alerta["detalle"]
    assert "motivos" not in alerta["detalle"]


async def test_la_cartera_no_declara_cobertura_del_universo(app_con_calendario) -> None:
    """La pregunta es otra: en una cartera lo que importa es qué posición no se pudo calcular, con
    nombre, y una proporción sobre tres posiciones sería ruido."""
    async with cliente(app_con_calendario()) as http:
        cuerpo = (
            await http.post(CARTERA, json={"posiciones": [{"ticker": "RUCED", "monto": 100_000}]})
        ).json()

    assert all(a["codigo"] != "cobertura_del_calendario" for a in cuerpo["alertas"])


async def test_sin_base_de_datos_el_calendario_contesta_503(crear_app) -> None:
    async with cliente(crear_app(None)) as http:
        respuesta = await http.get(UNIVERSO)

    assert respuesta.status_code == 503


# --- El calendario de una cartera -----------------------------------------------------------------


async def test_la_cartera_devuelve_la_renta_abierta_por_moneda(app_con_calendario) -> None:
    """Una cartera con un hard dollar y una LECAP tiene dos monedas de cobro, y no se suman."""
    async with cliente(app_con_calendario()) as http:
        respuesta = await http.post(
            CARTERA,
            json={
                "posiciones": [
                    {"ticker": "RUCED", "monto": 100_000},
                    {"ticker": "S30J6", "monto": 1_000_000},
                ]
            },
        )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["resumen"]["con_montos"] is True
    assert set(cuerpo["resumen"]["monedas"]) == {"usd", "ars"}
    assert set(cuerpo["resumen"]["renta_anual"]) == {"usd", "ars"}
    assert all(set(mes["renta"]) == {"ars", "usd"} for mes in cuerpo["meses"])


async def test_la_cartera_ve_la_especie_que_tiene_y_no_la_que_representa_a_la_emision(
    app_con_calendario,
) -> None:
    """El asesor tiene RUCED, no "la emisión RUCE". En la vista colapsada RUCED podría no estar, y
    la posición desaparecería del calendario."""
    async with cliente(app_con_calendario()) as http:
        cuerpo = (
            await http.post(CARTERA, json={"posiciones": [{"ticker": "RUCED", "monto": 100_000}]})
        ).json()

    tickers = {i["ticker"] for mes in cuerpo["meses"] for i in mes["instrumentos"]}
    assert tickers == {"RUCED"}


async def test_renta_y_amortizacion_llegan_separadas_al_cliente(app_con_calendario) -> None:
    """El último pago de RUCED devuelve el capital y paga cupón: los dos números viajan aparte."""
    async with cliente(app_con_calendario()) as http:
        cuerpo = (
            await http.post(CARTERA, json={"posiciones": [{"ticker": "RUCED", "monto": 100_000}]})
        ).json()

    vencimiento = next(
        mes for mes in cuerpo["meses"] if mes["etiqueta"] == _etiqueta(MES_DEL_CAPITAL)
    )
    instrumento = vencimiento["instrumentos"][0]
    assert instrumento["renta"] > 0
    assert instrumento["amortizacion"] > instrumento["renta"]
    assert vencimiento["renta"]["usd"] == pytest.approx(instrumento["renta"])
    assert vencimiento["amortizacion"]["usd"] == pytest.approx(instrumento["amortizacion"])


async def test_una_posicion_que_no_esta_en_el_universo_se_nombra(app_con_calendario) -> None:
    """La renta proyectada sale más chica de lo que es, y eso hay que decirlo en vez de que se
    descubra."""
    async with cliente(app_con_calendario()) as http:
        cuerpo = (
            await http.post(
                CARTERA,
                json={
                    "posiciones": [
                        {"ticker": "RUCED", "monto": 100_000},
                        {"ticker": "NOEXISTE", "monto": 50_000},
                    ]
                },
            )
        ).json()

    alerta = next(a for a in cuerpo["alertas"] if a["codigo"] == "posicion_fuera_del_universo")
    assert alerta["detalle"]["tickers"] == ["NOEXISTE"]


async def test_una_posicion_que_no_se_pudo_calcular_se_nombra_con_su_motivo(
    app_con_calendario,
) -> None:
    """El caso real que el motor dejaba pasar en silencio: la posición está en el universo pero no
    tiene paridad, así que su renta desaparece del total del mes.

    Sin esta alerta la respuesta son doce meses de renta cero sin una sola advertencia, que se lee
    como "este bono no paga nada" cuando lo que pasa es que no se lo pudo valuar. Pasa hoy con
    RUCED, SBC2D, CS47D y LOC5D: IAMC publicó las métricas del día en la especie O de cada emisión.
    """
    sin_paridad = [{"ticker": fila["ticker"], "paridad": None} for fila in FILAS_PARIDAD]
    async with cliente(app_con_calendario(paridades=sin_paridad)) as http:
        cuerpo = (
            await http.post(CARTERA, json={"posiciones": [{"ticker": "RUCED", "monto": 100_000}]})
        ).json()

    assert cuerpo["resumen"]["renta_anual"] == {"usd": 0.0}
    alerta = next(a for a in cuerpo["alertas"] if a["codigo"] == "posicion_sin_calendario")
    assert alerta["detalle"]["motivos"] == {
        "RUCED": "sin paridad: no se puede pasar el cupón a plata"
    }


async def test_una_posicion_vencida_se_nombra_con_su_motivo(app_con_calendario) -> None:
    """Que venció y que no se pudo valuar se arreglan distinto, y presentarlas como lo mismo manda
    a alguien a buscar donde no es."""
    vencido = [fila | {"payment_date": date(2020, 1, 1)} for fila in FILAS_CASHFLOW]
    async with cliente(app_con_calendario(cashflow=vencido)) as http:
        cuerpo = (
            await http.post(CARTERA, json={"posiciones": [{"ticker": "RUCED", "monto": 100_000}]})
        ).json()

    alerta = next(a for a in cuerpo["alertas"] if a["codigo"] == "posicion_sin_calendario")
    assert alerta["detalle"]["motivos"] == {"RUCED": "sin pagos futuros: la emisión ya venció"}


async def test_un_ticker_repetido_suma_sus_montos(app_con_calendario) -> None:
    """Son dos compras de la misma especie: en el calendario cobra como una sola posición."""
    async with cliente(app_con_calendario()) as http:
        una = (
            await http.post(CARTERA, json={"posiciones": [{"ticker": "RUCED", "monto": 100_000}]})
        ).json()
        dos = (
            await http.post(
                CARTERA,
                json={
                    "posiciones": [
                        {"ticker": "RUCED", "monto": 60_000},
                        {"ticker": "RUCED", "monto": 40_000},
                    ]
                },
            )
        ).json()

    assert dos["resumen"]["renta_anual"]["usd"] == pytest.approx(
        una["resumen"]["renta_anual"]["usd"]
    )


async def test_un_monto_no_positivo_se_rechaza_con_422(app_con_calendario) -> None:
    async with cliente(app_con_calendario()) as http:
        respuesta = await http.post(CARTERA, json={"posiciones": [{"ticker": "RUCED", "monto": 0}]})

    assert respuesta.status_code == 422


async def test_una_cartera_vacia_se_rechaza_con_422(app_con_calendario) -> None:
    async with cliente(app_con_calendario()) as http:
        respuesta = await http.post(CARTERA, json={"posiciones": []})

    assert respuesta.status_code == 422
