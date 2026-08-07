"""Las dos vistas del universo por HTTP: qué viaja en cada una y cómo se paginan — F-011.

El veredicto de la deduplicación ya está probado sin levantar nada en `test_universo_emisiones.py`.
Lo que se prueba acá es el contrato: que la clave de emisión viaje en **las dos** vistas, que la
colapsada tenga una fila donde la viva tiene tres, y que la pregunta del armador —"¿esto que quiero
agregar ya lo tengo?"— se pueda contestar sin que el cliente corte un ticker por su cuenta.
"""

from datetime import date
from typing import Any

from tests.conftest import cliente
from tests.test_universo_servicio import FakeConexionLectura

EMISIONES = "/api/v1/universo/emisiones"
COLAPSADA = "/api/v1/universo/emisiones/colapsada"
ESPECIES = "/api/v1/universo/emisiones/especies"
DUPLICADO = "/api/v1/universo/emisiones/duplicado"


def fila(ticker: str, *, duration: float | None = 6.4, completa: bool = True) -> dict[str, Any]:
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


def app_con(crear_app, filas: list[dict[str, Any]] | None = None):
    return crear_app(FakeConexionLectura(UNIVERSO if filas is None else filas))


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
