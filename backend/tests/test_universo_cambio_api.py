"""El tipo de cambio por HTTP y el volumen normalizado que viaja con cada especie — F-012.

El cálculo ya está probado sin levantar nada en `test_universo_cambio.py`. Lo que se prueba acá es
el contrato: que el endpoint devuelva el número **con su muestra** —sin los pares y la dispersión no
se puede saber si creerle—, que la vista viva lleve el volumen crudo y el normalizado, y que el
contraste sea un campo aparte y no algo que reemplace al implícito.

El índice de BYMA se anula con un `monkeypatch` sobre `leer_indices`: un test que dependiera de que
la API abierta esté arriba fallaría los días que BYMA falla, y lo que hay que probar acá no es BYMA.
"""

from typing import Any

import pytest

from app.universo import servicio
from tests.conftest import cliente
from tests.test_universo_servicio import FakeConexionLectura

TIPO_DE_CAMBIO = "/api/v1/universo/tipo-de-cambio"
ESPECIES = "/api/v1/universo/emisiones/especies"
SANIDAD = "/api/v1/universo/sanidad"

FX = 1500.0


def par(raiz: str, *, volumen_ars: float = 0.0, volumen_usd: float = 0.0) -> list[dict[str, Any]]:
    return [
        {
            "ticker": f"{raiz}O",
            "clase_activo": "on_corporativo",
            "tipo_tasa": "hard-dollar",
            "tir": 0.10,
            "duration": 3.2,
            "lastPrice": FX,
            "effectiveVolume": volumen_ars,
            "moneda_cotizacion": "ARS",
        },
        {
            "ticker": f"{raiz}D",
            "clase_activo": "on_corporativo",
            "tipo_tasa": "hard-dollar",
            "tir": 0.10,
            "duration": 3.2,
            "lastPrice": 1.0,
            "effectiveVolume": volumen_usd,
            "moneda_cotizacion": "USD",
        },
    ]


UNIVERSO = [f for i in range(20) for f in par(f"E{i:03d}", volumen_ars=15_000.0, volumen_usd=10.0)]


@pytest.fixture(autouse=True)
def sin_byma(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin índices: el implícito tiene que salir igual, que es lo que se quiere probar acá."""

    async def _vacio() -> list:
        return []

    monkeypatch.setattr(servicio, "leer_indices", _vacio)


@pytest.fixture
def app_con_universo(crear_app):
    return crear_app(FakeConexionLectura(UNIVERSO))


async def test_el_endpoint_devuelve_el_implicito_con_su_muestra(app_con_universo) -> None:
    async with cliente(app_con_universo) as http:
        respuesta = await http.get(TIPO_DE_CAMBIO)

    assert respuesta.status_code == 200
    cambio = respuesta.json()["tipo_de_cambio"]
    assert cambio["valor"] == pytest.approx(FX)
    assert cambio["disponible"] is True
    assert cambio["pares"] == 20
    assert cambio["minimo_de_pares"] == 20
    assert cambio["dispersion"] == pytest.approx(0.0)


async def test_sin_indice_de_byma_el_implicito_sale_igual_y_se_declara(app_con_universo) -> None:
    """El contraste es un control. Si no está, se dice; lo que no se hace es dejar de calcular."""
    async with cliente(app_con_universo) as http:
        cuerpo = (await http.get(TIPO_DE_CAMBIO)).json()

    assert cuerpo["tipo_de_cambio"]["valor"] == pytest.approx(FX)
    assert cuerpo["tipo_de_cambio"]["contraste"] is None
    assert "tipo_de_cambio_sin_contraste" in {a["codigo"] for a in cuerpo["alertas"]}


async def test_la_vista_viva_lleva_el_volumen_crudo_y_el_normalizado(app_con_universo) -> None:
    """Los dos, porque el crudo es lo que la fuente publicó y el otro es lo que se deriva de él.

    Las dos especies de este bono operaron lo mismo: 15.000 pesos y 10 dólares al mismo tipo de
    cambio. En crudo la de pesos parece 1.500 veces más líquida.
    """
    async with cliente(app_con_universo) as http:
        items = (await http.get(f"{ESPECIES}?limit=100")).json()["items"]

    por_ticker = {i["ticker"]: i for i in items}
    assert por_ticker["E000O"]["moneda_cotizacion"] == "ARS"
    assert por_ticker["E000O"]["volumen"] == 15_000.0
    assert por_ticker["E000O"]["volumen_usd"] == pytest.approx(10.0)
    assert por_ticker["E000D"]["volumen"] == 10.0
    assert por_ticker["E000D"]["volumen_usd"] == pytest.approx(10.0)


async def test_el_resumen_de_sanidad_lleva_el_tipo_de_cambio_de_la_corrida(
    app_con_universo,
) -> None:
    """Van juntos porque son el mismo universo: el volumen en dólares de estas especies salió de
    ese número, y publicarlos por separado dejaría el derivado sin su origen."""
    async with cliente(app_con_universo) as http:
        cuerpo = (await http.get(SANIDAD)).json()

    assert cuerpo["resumen"]["tipo_de_cambio"]["valor"] == pytest.approx(FX)
