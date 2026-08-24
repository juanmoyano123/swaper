"""El contrato HTTP de `/api/v1/fci/*` — F-057.

Fake que despacha por SQL: `leer_fondos`/`leer_segmentos` usan `fetch`, `leer_planilla`/`leer_fondo`
usan `fetchrow`, y hay que distinguir `fci` de `fci_planilla` en las dos — mismo criterio que
`test_renta_variable_api.py`.
"""

from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.api.v1 import fci as modulo_fci
from tests.conftest import cliente

FONDO_A = {
    "codigo_cafci": "1031",
    "fondo": "Gainvest Renta Variable - Clase A",
    "codigo_cnv": "500",
    "seccion": "Renta Variable Peso Argentina",
    "tipo_renta": "renta_variable",
    "moneda": "ARS",
    "region": "Arg",
    "horizonte": "Lar",
    "fecha_vcp": date(2026, 8, 21),
    "vcp": 1500.0,
    "vcp_anterior": 1490.0,
    "var_diaria_pct": 0.67,
    "var_mes_pct": 5.2,
    "var_anio_pct": 40.1,
    "var_12m_pct": 55.3,
    "cuotapartes": 100.0,
    "cuotapartes_anterior": 99.0,
    "patrimonio": 10_000_000.0,
    "patrimonio_anterior": 9_900_000.0,
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

FONDO_USB = {**FONDO_A, "codigo_cafci": "3223", "fondo": "Delta Acciones - Clase I", "moneda": "USB"}

PLANILLA = {
    "fecha_planilla": date(2026, 8, 21),
    "fecha_cierre_anterior": date(2026, 8, 20),
    "fecha_base_mes": date(2026, 7, 31),
    "fecha_base_anio": date(2025, 12, 30),
    "fecha_base_12m": date(2025, 7, 31),
    "total_filas": 2,
    "capturado_en": datetime(2026, 8, 21, 12, 0, tzinfo=UTC),
}


class FakeConexionFci:
    def __init__(
        self,
        fondos: list[dict[str, Any]] | None = None,
        planilla: dict[str, Any] | None = None,
    ) -> None:
        self.fondos = fondos if fondos is not None else []
        self.planilla = planilla

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        if "GROUP BY tipo_renta" in query:
            por_tipo: dict[str, list[str]] = {}
            for f in self.fondos:
                por_tipo.setdefault(f["tipo_renta"], []).append(f["moneda"])
            return [
                {"tipo_renta": t, "cantidad": len(m), "monedas": sorted(set(m))}
                for t, m in sorted(por_tipo.items())
            ]

        filas = self.fondos
        if args:
            for arg in args:
                filas = [f for f in filas if f.get("tipo_renta") == arg or f.get("moneda") == arg]
        return filas

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        if "fci_planilla" in query:
            return self.planilla
        if args:
            codigo = args[0]
            return next((f for f in self.fondos if f["codigo_cafci"] == codigo), None)
        return None


@pytest.fixture
def app_con_fci(crear_app):
    def _crear(**kwargs: Any):
        return crear_app(FakeConexionFci(**kwargs))

    return _crear


async def test_segmentos_agrupa_por_tipo_de_renta(app_con_fci) -> None:
    async with cliente(app_con_fci(fondos=[FONDO_A, FONDO_USB], planilla=PLANILLA)) as http:
        respuesta = await http.get("/api/v1/fci/segmentos")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["segmentos"] == [
        {"tipo_renta": "renta_variable", "cantidad": 2, "monedas": ["ARS", "USB"]}
    ]
    assert cuerpo["planilla"]["fecha_planilla"] == "2026-08-21"
    assert cuerpo["planilla"]["fecha_base_mes"] == "2026-07-31"


async def test_segmentos_sin_ingesta_previa_planilla_es_null(app_con_fci) -> None:
    async with cliente(app_con_fci(fondos=[], planilla=None)) as http:
        respuesta = await http.get("/api/v1/fci/segmentos")

    assert respuesta.json()["planilla"] is None
    assert respuesta.json()["segmentos"] == []


async def test_fondos_devuelve_naturaleza_fija_variacion_cuotaparte(app_con_fci) -> None:
    async with cliente(app_con_fci(fondos=[FONDO_A])) as http:
        respuesta = await http.get("/api/v1/fci/fondos")

    (fondo,) = respuesta.json()["items"]
    assert fondo["naturaleza"] == "variacion_cuotaparte"
    assert "tir" not in fondo["naturaleza"]


async def test_fondos_usb_no_se_traduce(app_con_fci) -> None:
    async with cliente(app_con_fci(fondos=[FONDO_USB])) as http:
        respuesta = await http.get("/api/v1/fci/fondos")

    (fondo,) = respuesta.json()["items"]
    assert fondo["moneda"] == "USB"


async def test_fondos_plazo_centinela_da_dias_para_rescatar_null(app_con_fci) -> None:
    con_centinela = {**FONDO_A, "plazo_liq": 9999}
    async with cliente(app_con_fci(fondos=[con_centinela])) as http:
        respuesta = await http.get("/api/v1/fci/fondos")

    (fondo,) = respuesta.json()["items"]
    assert fondo["plazo_liq"] == 9999
    assert fondo["dias_para_rescatar"] is None


async def test_fondos_calificacion_ausente_es_null_no_texto(app_con_fci) -> None:
    sin_calificacion = {**FONDO_A, "calificacion": None}
    async with cliente(app_con_fci(fondos=[sin_calificacion])) as http:
        respuesta = await http.get("/api/v1/fci/fondos")

    (fondo,) = respuesta.json()["items"]
    assert fondo["calificacion"] is None


async def test_fondos_discrepancia_de_moneda_se_declara(app_con_fci) -> None:
    con_discrepancia = {**FONDO_A, "moneda": "ARS", "moneda_fondo": "USD"}
    async with cliente(app_con_fci(fondos=[con_discrepancia])) as http:
        respuesta = await http.get("/api/v1/fci/fondos")

    (fondo,) = respuesta.json()["items"]
    assert fondo["discrepancia_moneda"] is True


async def test_ficha_404_si_no_esta_en_la_planilla_de_hoy(app_con_fci) -> None:
    async with cliente(app_con_fci(fondos=[])) as http:
        respuesta = await http.get("/api/v1/fci/9999/ficha")

    assert respuesta.status_code == 404


async def test_ficha_devuelve_el_fondo(app_con_fci) -> None:
    async with cliente(app_con_fci(fondos=[FONDO_A])) as http:
        respuesta = await http.get("/api/v1/fci/1031/ficha")

    assert respuesta.status_code == 200
    assert respuesta.json()["gerente"] == "Gainvest S.A."
    assert respuesta.json()["codigo_cnv"] == "500"


async def test_ficha_con_codigo_cnv_mapeado_trae_el_enlace(app_con_fci, monkeypatch) -> None:
    monkeypatch.setattr(
        modulo_fci,
        "enlace_composicion_cnv",
        lambda codigo_cnv: f"https://www.cnv.gov.ar/SitioWeb/FondosComunesInversion/DetallesFCI/{codigo_cnv}",
    )
    async with cliente(app_con_fci(fondos=[FONDO_A])) as http:
        respuesta = await http.get("/api/v1/fci/1031/ficha")

    assert respuesta.json()["enlace_composicion_cnv"] == (
        "https://www.cnv.gov.ar/SitioWeb/FondosComunesInversion/DetallesFCI/500"
    )


async def test_ficha_sin_codigo_cnv_mapeado_no_trae_enlace(app_con_fci, monkeypatch) -> None:
    monkeypatch.setattr(modulo_fci, "enlace_composicion_cnv", lambda codigo_cnv: None)
    async with cliente(app_con_fci(fondos=[FONDO_A])) as http:
        respuesta = await http.get("/api/v1/fci/1031/ficha")

    assert respuesta.json()["enlace_composicion_cnv"] is None


async def test_listado_de_fondos_no_lleva_enlace_composicion_cnv(app_con_fci) -> None:
    async with cliente(app_con_fci(fondos=[FONDO_A])) as http:
        respuesta = await http.get("/api/v1/fci/fondos")

    (fondo,) = respuesta.json()["items"]
    assert "enlace_composicion_cnv" not in fondo
