"""Las dos vistas del universo por HTTP: qué viaja en cada una y cómo se paginan — F-011.

El veredicto de la deduplicación ya está probado sin levantar nada en `test_universo_emisiones.py`.
Lo que se prueba acá es el contrato: que la clave de emisión viaje en **las dos** vistas, que la
colapsada tenga una fila donde la viva tiene tres, y que la pregunta del armador —"¿esto que quiero
agregar ya lo tengo?"— se pueda contestar sin que el cliente corte un ticker por su cuenta.
"""

from datetime import date, timedelta
from typing import Any

from tests.conftest import cliente
from tests.test_universo_servicio import FakeConexionLectura

EMISIONES = "/api/v1/universo/emisiones"
COLAPSADA = "/api/v1/universo/emisiones/colapsada"
ESPECIES = "/api/v1/universo/emisiones/especies"
DUPLICADO = "/api/v1/universo/emisiones/duplicado"


def fila(
    ticker: str,
    *,
    duration: float | None = 6.4,
    completa: bool = True,
    lamina: float | None = None,
) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "clase_activo": "bono_soberano",
        "tipo_tasa": "hard-dollar",
        "tir": 0.13,
        "tna": None,
        "duration": duration,
        "maturity": date(2046, 1, 9) if completa else None,
        "law": "Ley N.Y." if completa else None,
        "couponCurrency": "MEP" if completa else None,
        "underlying": "Tesoro Nacional" if completa else None,
        "lamina": lamina,
    }


# Las tres especies de MR46, un bono de una sola especie, y dos que comparten raíz con duraciones
# incompatibles: el caso que el chequeo del 5 % existe para no fusionar.
UNIVERSO: list[dict[str, Any]] = [
    fila("MR46O", completa=False),
    fila("MR46D"),
    fila("MR46C", completa=False),
    fila("AL30"),
    fila("XXXXO", duration=2.0),
    fila("XXXXD", duration=9.0),
]


def app_con(
    crear_app,
    filas: list[dict[str, Any]] | None = None,
    cashflow: list[dict[str, Any]] | None = None,
):
    return crear_app(FakeConexionLectura(UNIVERSO if filas is None else filas, cashflow))


def pago(ticker: str, payment_date: date, *, interest_amount: float = 2.5) -> dict[str, Any]:
    """Una fila de cronograma con lo que `indexar_cronograma` necesita para agrupar y medir."""
    return {
        "ticker": ticker,
        "issue_date": date(2020, 1, 9),
        "payment_date": payment_date,
        "capital": 0.0,
        "interest_amount": interest_amount,
        "residual_value": 100.0,
        "cash_flow": interest_amount,
    }


# Un semestral (dos pagos separados seis meses) y un bono al que le queda un solo pago por delante.
# Las fechas son futuras contra el reloj real: `frecuencia_por_raiz` mide sólo pagos futuros, así
# que fechas fijas del pasado dejarían el caso sin medir con el correr de los meses.
def cronograma_de_prueba() -> list[dict[str, Any]]:
    hoy = date.today()
    return [
        pago("MR46O", hoy.replace(year=hoy.year + 1)),
        pago("MR46O", hoy.replace(year=hoy.year + 1, day=1) + timedelta(days=182)),
        pago("AL30", hoy.replace(year=hoy.year + 2)),
    ]


# --- El resumen ----------------------------------------------------------------------------------


async def test_el_resumen_dice_cuanto_colapso_y_cuanto_no(crear_app) -> None:
    async with cliente(app_con(crear_app)) as http:
        respuesta = await http.get(EMISIONES)

    assert respuesta.status_code == 200
    resumen = respuesta.json()["resumen"]
    assert resumen["especies"] == 6
    assert resumen["emisiones"] == 3
    assert resumen["especies_colapsadas"] == 2
    assert resumen["no_colapsadas_por_duracion"]["cantidad"] == 1


async def test_el_resumen_declara_las_alertas_de_la_deduplicacion(crear_app) -> None:
    async with cliente(app_con(crear_app)) as http:
        cuerpo = (await http.get(EMISIONES)).json()

    codigos = {a["codigo"] for a in cuerpo["alertas"]}
    assert codigos == {"especies_colapsadas", "emision_no_colapsada"}


# --- GWT-1: la vista colapsada -------------------------------------------------------------------


async def test_las_tres_especies_de_mr46_son_una_fila_con_la_clave_de_emision(crear_app) -> None:
    async with cliente(app_con(crear_app)) as http:
        items = (await http.get(COLAPSADA)).json()["items"]

    de_mr46 = [i for i in items if i["emision"] == "MR46"]
    assert len(de_mr46) == 1
    assert de_mr46[0]["ticker"] == "MR46D"  # la única de las tres con los datos completos
    assert de_mr46[0]["especies"] == ["MR46C", "MR46D", "MR46O"]
    assert de_mr46[0]["colapsada"] is True


async def test_un_grupo_con_duraciones_dispares_no_se_fusiona_y_lo_dice(crear_app) -> None:
    async with cliente(app_con(crear_app)) as http:
        items = (await http.get(COLAPSADA)).json()["items"]

    de_xxxx = [i for i in items if i["emision"] == "XXXX"]
    assert [i["ticker"] for i in de_xxxx] == ["XXXXD", "XXXXO"]
    assert all(i["colapsada"] is False for i in de_xxxx)
    assert de_xxxx[0]["dispersion_duracion"] > 0.05


# --- GWT-2: la vista viva ------------------------------------------------------------------------


async def test_la_vista_viva_devuelve_las_tres_especies_con_lo_suyo(crear_app) -> None:
    async with cliente(app_con(crear_app)) as http:
        items = (await http.get(ESPECIES)).json()["items"]

    por_ticker = {i["ticker"]: i for i in items}
    assert {"MR46O", "MR46D", "MR46C"} <= set(por_ticker)
    assert por_ticker["MR46C"]["sufijo_liquidacion"] == "C"
    assert por_ticker["MR46D"]["rendimiento"] == 0.13
    assert por_ticker["MR46D"]["dato_sano"] is True


async def test_cada_especie_viva_declara_la_periodicidad_de_su_cronograma(crear_app) -> None:
    """Sale del cronograma contractual, no de la ventana de doce meses: es la diferencia entre
    medir la frecuencia y contar cuántas veces cayó un pago en un año arbitrario."""
    app = app_con(crear_app, cashflow=cronograma_de_prueba())
    async with cliente(app) as http:
        items = (await http.get(ESPECIES)).json()["items"]

    por_ticker = {i["ticker"]: i for i in items}
    assert por_ticker["MR46O"]["periodicidad"] == "semestral"
    # La periodicidad es de la emisión: las hermanas de liquidación la comparten, no se recalcula
    # por especie.
    assert por_ticker["MR46D"]["periodicidad"] == "semestral"


async def test_un_solo_pago_por_delante_se_declara_al_vencimiento_y_no_anual(crear_app) -> None:
    """Con un pago no se puede medir una frecuencia. Llamarlo 'anual' sería inventarla."""
    app = app_con(crear_app, cashflow=cronograma_de_prueba())
    async with cliente(app) as http:
        items = (await http.get(ESPECIES)).json()["items"]

    assert {i["ticker"]: i for i in items}["AL30"]["periodicidad"] == "al vencimiento"


async def test_una_emision_sin_cronograma_no_inventa_periodicidad(crear_app) -> None:
    """Faltante declarado, nunca 'irregular': no tener cronograma no es tener uno irregular."""
    async with cliente(app_con(crear_app)) as http:
        items = (await http.get(ESPECIES)).json()["items"]

    assert all(i["periodicidad"] is None for i in items)


async def test_cada_especie_viva_lleva_su_clave_de_emision_y_sus_hermanas(crear_app) -> None:
    """La clave va en las dos vistas: quien mira la viva tiene que poder ver que MR46O y MR46D son
    el mismo bono sin volver a cortar el ticker."""
    async with cliente(app_con(crear_app)) as http:
        items = (await http.get(ESPECIES)).json()["items"]

    por_ticker = {i["ticker"]: i for i in items}
    assert por_ticker["MR46D"]["emision"] == "MR46"
    assert por_ticker["MR46D"]["hermanas"] == ["MR46C", "MR46O"]
    assert por_ticker["AL30"]["hermanas"] == []


async def test_las_dos_vistas_son_del_mismo_universo(crear_app) -> None:
    """La colapsada no puede tener nada que la viva no tenga: no es un universo distinto, es el
    mismo mirado por emisión."""
    async with cliente(app_con(crear_app)) as http:
        colapsada = {i["ticker"] for i in (await http.get(COLAPSADA)).json()["items"]}
        viva = {i["ticker"] for i in (await http.get(ESPECIES)).json()["items"]}

    assert colapsada <= viva
    assert len(colapsada) < len(viva)


# --- GWT-3: la advertencia que va a usar el armador ---------------------------------------------


async def test_agregar_mr46c_teniendo_mr46d_avisa_que_no_suma_diversificacion(crear_app) -> None:
    async with cliente(app_con(crear_app)) as http:
        cuerpo = (
            await http.get(DUPLICADO, params={"ticker": "MR46C", "cartera": ["MR46D", "AL30"]})
        ).json()

    assert cuerpo["duplicado"] is True
    assert cuerpo["emision"] == "MR46"
    assert cuerpo["advertencia"]["codigo"] == "misma_emision"
    assert "MR46D" in cuerpo["advertencia"]["mensaje"]


async def test_agregar_una_emision_nueva_no_advierte_nada(crear_app) -> None:
    async with cliente(app_con(crear_app)) as http:
        cuerpo = (await http.get(DUPLICADO, params={"ticker": "AL30", "cartera": ["MR46D"]})).json()

    assert cuerpo["duplicado"] is False
    assert cuerpo["advertencia"] is None


async def test_una_cartera_vacia_no_advierte_nada(crear_app) -> None:
    async with cliente(app_con(crear_app)) as http:
        cuerpo = (await http.get(DUPLICADO, params={"ticker": "MR46C"})).json()

    assert cuerpo["duplicado"] is False
    assert cuerpo["emision"] == "MR46"
    assert cuerpo["en_el_universo"] is True


# --- Paginación y base caída ---------------------------------------------------------------------


async def test_el_cursor_de_la_vista_viva_avanza_sin_repetir_ni_saltear(crear_app) -> None:
    async with cliente(app_con(crear_app)) as http:
        primera = (await http.get(ESPECIES, params={"limit": 2})).json()
        assert [i["ticker"] for i in primera["items"]] == ["AL30", "MR46C"]

        segunda = (
            await http.get(ESPECIES, params={"limit": 2, "cursor": primera["next_cursor"]})
        ).json()

    assert [i["ticker"] for i in segunda["items"]] == ["MR46D", "MR46O"]


async def test_el_cursor_de_la_vista_colapsada_termina_sin_cursor(crear_app) -> None:
    async with cliente(app_con(crear_app)) as http:
        pagina = (await http.get(COLAPSADA, params={"limit": 100})).json()

    assert pagina["next_cursor"] is None
    assert len(pagina["items"]) == 4  # AL30 + MR46 + las dos XXXX que no se fusionan


async def test_sin_base_de_datos_las_dos_vistas_responden_503(crear_app) -> None:
    async with cliente(crear_app(None)) as http:
        assert (await http.get(EMISIONES)).status_code == 503
        assert (await http.get(COLAPSADA)).status_code == 503
        assert (await http.get(ESPECIES)).status_code == 503


# --- F-038: paridad, filtro por segmento y `/segmentos` -------------------------------------------

SEGMENTOS = "/api/v1/universo/segmentos"


def fila_segmento(
    ticker: str, tipo_tasa: str, *, tir: float | None = 0.13, paridad: float | None = None
) -> dict[str, Any]:
    """Una fila de un segmento a elección, con su paridad. `fila()` fija `hard-dollar`; acá se
    necesita más de un segmento para probar el filtro y el endpoint de pestañas."""
    return {**fila(ticker), "tipo_tasa": tipo_tasa, "tir": tir, "tna": None, "paridad": paridad}


# Dos especies hard-dollar (una con paridad, otra sin) y una CER: alcanza para separar pestañas.
# La paridad es adimensional y ronda 1.0 (`cupones.py`: "precio sucio = paridad x valor técnico"),
# así que 0.875 es un bono que cotiza bajo la par y no un 87,5% escrito distinto.
UNIVERSO_MULTISEGMENTO: list[dict[str, Any]] = [
    fila_segmento("AL30", "hard-dollar", paridad=0.875),
    fila_segmento("GD30", "hard-dollar", paridad=None),
    fila_segmento("TX26", "cer", tir=0.05, paridad=0.95),
]


async def test_la_paridad_viaja_por_la_vista_viva_y_es_none_cuando_es_null(crear_app) -> None:
    async with cliente(app_con(crear_app, UNIVERSO_MULTISEGMENTO)) as http:
        por_ticker = {i["ticker"]: i for i in (await http.get(ESPECIES)).json()["items"]}

    assert por_ticker["AL30"]["paridad"] == 0.875
    assert por_ticker["GD30"]["paridad"] is None


# --- F-024: la lámina real, de condiciones_emision vía la base común de la tanda 8b ---------------


async def test_la_lamina_viaja_por_la_vista_viva_como_numero(crear_app) -> None:
    """Con lámina informada llega como número, no como string: acá se caería el `Decimal` de
    Postgres sin convertir (el cast a `float8` vive en `lectura.py`, ver su docstring)."""
    universo = [fila("AL30", lamina=100.0), fila("GD30", lamina=None)]

    async with cliente(app_con(crear_app, universo)) as http:
        por_ticker = {i["ticker"]: i for i in (await http.get(ESPECIES)).json()["items"]}

    assert por_ticker["AL30"]["lamina"] == 100.0
    assert not isinstance(por_ticker["AL30"]["lamina"], str)


async def test_una_especie_sin_lamina_informada_no_asume_ninguna(crear_app) -> None:
    """Regla 1 del proyecto: sin dato curado, `lamina` es `None`, no 1 ni 1.000 ni un estándar de
    mercado (F-024)."""
    universo = [fila("AL30", lamina=None)]

    async with cliente(app_con(crear_app, universo)) as http:
        por_ticker = {i["ticker"]: i for i in (await http.get(ESPECIES)).json()["items"]}

    assert por_ticker["AL30"]["lamina"] is None


async def test_el_filtro_por_segmento_deja_afuera_las_demas(crear_app) -> None:
    async with cliente(app_con(crear_app, UNIVERSO_MULTISEGMENTO)) as http:
        items = (await http.get(ESPECIES, params={"segmento": "usd_hard"})).json()["items"]

    assert {i["ticker"] for i in items} == {"AL30", "GD30"}
    assert all(i["segmento"] == "usd_hard" for i in items)


async def test_un_segmento_inexistente_es_una_pagina_vacia_no_un_404(crear_app) -> None:
    async with cliente(app_con(crear_app, UNIVERSO_MULTISEGMENTO)) as http:
        respuesta = await http.get(ESPECIES, params={"segmento": "no-existe"})

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["items"] == []
    assert cuerpo["next_cursor"] is None


async def test_segmentos_devuelve_forma_y_conteos_reales(crear_app) -> None:
    async with cliente(app_con(crear_app, UNIVERSO_MULTISEGMENTO)) as http:
        cuerpo = (await http.get(SEGMENTOS)).json()

    por_clave = {s["clave"]: s for s in cuerpo["segmentos"]}
    assert set(por_clave) == {"usd_hard", "cer"}
    assert por_clave["usd_hard"] == {
        "clave": "usd_hard",
        "nombre": "Hard dollar (globales, bonares, ONs y bopreales en USD)",
        "naturaleza": "tir_usd",
        "naturaleza_nombre": "TIR en dólares (hard dollar)",
        "especies": 2,
    }
    assert por_clave["cer"]["especies"] == 1
    assert cuerpo["renta_variable"] == 0
    assert cuerpo["sin_segmento"] == 0


async def test_un_segmento_sin_especies_no_aparece_en_las_pestanas(crear_app) -> None:
    """`tasa_fija`, `dollar_linked`, `badlar` y `tamar` no tienen ninguna especie en este universo
    de prueba: una pestaña vacía no es una pestaña, es ruido."""
    async with cliente(app_con(crear_app, UNIVERSO_MULTISEGMENTO)) as http:
        claves = {s["clave"] for s in (await http.get(SEGMENTOS)).json()["segmentos"]}

    assert claves == {"usd_hard", "cer"}
    assert "tasa_fija" not in claves


async def test_sin_base_de_datos_segmentos_responde_503(crear_app) -> None:
    async with cliente(crear_app(None)) as http:
        assert (await http.get(SEGMENTOS)).status_code == 503
