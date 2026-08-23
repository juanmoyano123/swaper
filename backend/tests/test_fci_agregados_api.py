"""El contrato HTTP de `/api/v1/fci/agregados/*` — F-067.

Mismo fake que `test_fci_api.py`: `leer_fondos` despacha por `conn.fetch` sin filtros de
`tipo_renta`/`moneda` (los endpoints piden el universo entero para agregarlo acá).
"""

from typing import Any

import pytest

from tests.conftest import cliente

FONDO_ARS = {
    "codigo_cafci": "1031",
    "fondo": "Gainvest Renta Variable - Clase A",
    "codigo_cnv": "500",
    "seccion": "Renta Variable Peso Argentina",
    "tipo_renta": "renta_variable",
    "moneda": "ARS",
    "region": "Arg",
    "horizonte": "Lar",
    "fecha_vcp": "2026-08-21",
    "vcp": 1500.0,
    "vcp_anterior": 1490.0,
    "var_diaria_pct": 0.67,
    "var_mes_pct": 5.2,
    "var_anio_pct": 40.1,
    "var_12m_pct": 55.3,
    "cuotapartes": 100.0,
    "cuotapartes_anterior": 99.0,
    "patrimonio": 1_000_000.0,
    "patrimonio_anterior": 990_000.0,
    "market_share": 1.2,
    "gerente": "Gainvest S.A.",
    "depositaria": "Banco X",
    "calificacion": "EF-3",
    "calificado": "Si",
    "tipo_dinero": "Ahorro",
    "comision_ingreso": 0.0,
    "honorarios_adm_sg": 2.0,
    "honorarios_adm_sd": 0.3,
    "gastos_ord_gestion": 0.1,
    "comision_rescate": 0.0,
    "comision_transferencia": 0.0,
    "honorarios_exito": 0.0,
    "moneda_fondo": "ARS",
    "plazo_liq": 1,
    "minimo_inversion": 1000.0,
}

FONDO_USD = {
    **FONDO_ARS,
    "codigo_cafci": "3223",
    "fondo": "Delta Renta Fija Dólares",
    "tipo_renta": "renta_fija",
    "moneda": "USD",
    "moneda_fondo": "USD",
    "patrimonio": 2_000_000.0,
    "gerente": "Delta S.A.",
}


class FakeConexionFciAgregados:
    def __init__(self, fondos: list[dict[str, Any]] | None = None) -> None:
        self.fondos = fondos if fondos is not None else []

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        return self.fondos


@pytest.fixture
def app_con_fci_agregados(crear_app):
    def _crear(fondos: list[dict[str, Any]] | None = None):
        return crear_app(FakeConexionFciAgregados(fondos=fondos))

    return _crear


async def test_categorias_agrupa_por_tipo_de_renta_y_no_cruza_monedas(app_con_fci_agregados) -> None:
    async with cliente(app_con_fci_agregados(fondos=[FONDO_ARS, FONDO_USD])) as http:
        respuesta = await http.get("/api/v1/fci/agregados/categorias")

    assert respuesta.status_code == 200
    categorias = respuesta.json()["categorias"]
    assert {c["tipo_renta"] for c in categorias} == {"renta_variable", "renta_fija"}

    renta_variable = next(c for c in categorias if c["tipo_renta"] == "renta_variable")
    (bloque_ars,) = renta_variable["por_moneda"]
    assert bloque_ars["moneda"] == "ARS"
    assert bloque_ars["aum"] == 1_000_000.0


async def test_categorias_sin_fondos_devuelve_lista_vacia(app_con_fci_agregados) -> None:
    async with cliente(app_con_fci_agregados(fondos=[])) as http:
        respuesta = await http.get("/api/v1/fci/agregados/categorias")

    assert respuesta.json()["categorias"] == []


async def test_gestoras_agrupa_por_gerente_verbatim(app_con_fci_agregados) -> None:
    async with cliente(app_con_fci_agregados(fondos=[FONDO_ARS, FONDO_USD])) as http:
        respuesta = await http.get("/api/v1/fci/agregados/gestoras")

    assert respuesta.status_code == 200
    gestoras = respuesta.json()["gestoras"]
    assert {g["gerente"] for g in gestoras} == {"Gainvest S.A.", "Delta S.A."}


async def test_gestoras_declara_flujo_neto_no_disponible(app_con_fci_agregados) -> None:
    async with cliente(app_con_fci_agregados(fondos=[FONDO_ARS])) as http:
        respuesta = await http.get("/api/v1/fci/agregados/gestoras")

    (gestora,) = respuesta.json()["gestoras"]
    assert gestora["flujo_neto"] == {
        "disponible": False,
        "motivo": (
            "requiere acumular planillas diarias; el producto no acumula series históricas "
            "(decisión del 23/08/2026)"
        ),
    }


async def test_gestoras_no_suma_aum_de_monedas_distintas_de_la_misma_gestora(app_con_fci_agregados) -> None:
    fondo_ars_gainvest = {**FONDO_ARS, "codigo_cafci": "9001", "gerente": "Gainvest S.A."}
    fondo_usb_gainvest = {
        **FONDO_ARS,
        "codigo_cafci": "9002",
        "gerente": "Gainvest S.A.",
        "moneda": "USB",
        "moneda_fondo": "USB",
        "patrimonio": 500_000.0,
    }
    async with cliente(app_con_fci_agregados(fondos=[fondo_ars_gainvest, fondo_usb_gainvest])) as http:
        respuesta = await http.get("/api/v1/fci/agregados/gestoras")

    (gestora,) = respuesta.json()["gestoras"]
    por_moneda = {b["moneda"]: b["aum"] for b in gestora["por_moneda"]}
    assert por_moneda == {"ARS": 1_000_000.0, "USB": 500_000.0}
