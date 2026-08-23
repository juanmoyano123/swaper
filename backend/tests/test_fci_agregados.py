"""`agregados_por_categoria` y `agregados_por_gestora` — F-067. Dominio puro, sin Postgres.

El caso testigo en toda esta suite: un grupo con fondos en `ARS` y en `USD` (o `USB`) nunca
suma esos patrimonios en el mismo AUM (regla 3).
"""

from app.fci.agregados import agregados_por_categoria, agregados_por_gestora
from app.fci.fondos import FondoFci


def fondo(**overrides: object) -> FondoFci:
    base: dict[str, object] = {
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
    base.update(overrides)
    return FondoFci(**base)  # type: ignore[arg-type]


class TestAgregadosPorCategoria:
    def test_aum_nunca_cruza_monedas(self) -> None:
        fondos = [
            fondo(codigo_cafci="1", moneda="ARS", patrimonio=1_000_000.0),
            fondo(codigo_cafci="2", moneda="USD", patrimonio=2_000_000.0),
        ]
        (categoria,) = agregados_por_categoria(fondos)

        por_moneda = {b["moneda"]: b for b in categoria["por_moneda"]}
        assert por_moneda["ARS"]["aum"] == 1_000_000.0
        assert por_moneda["USD"]["aum"] == 2_000_000.0
        assert not any(b["aum"] == 3_000_000.0 for b in por_moneda.values())

    def test_agrupa_por_tipo_de_renta(self) -> None:
        fondos = [
            fondo(codigo_cafci="1", tipo_renta="renta_variable"),
            fondo(codigo_cafci="2", tipo_renta="renta_fija"),
        ]
        categorias = agregados_por_categoria(fondos)
        assert {c["tipo_renta"] for c in categorias} == {"renta_variable", "renta_fija"}

    def test_participacion_pct_se_calcula_contra_el_aum_de_su_propia_moneda(self) -> None:
        fondos = [
            fondo(codigo_cafci="1", moneda="ARS", patrimonio=750_000.0),
            fondo(codigo_cafci="2", moneda="ARS", patrimonio=250_000.0),
        ]
        (categoria,) = agregados_por_categoria(fondos)
        (bloque_ars,) = categoria["por_moneda"]
        participaciones = {f["codigo_cafci"]: f["participacion_pct"] for f in bloque_ars["fondos"]}
        assert participaciones["1"] == 75.0
        assert participaciones["2"] == 25.0

    def test_patrimonio_ausente_no_se_inventa_como_cero_en_el_aum(self) -> None:
        fondos = [
            fondo(codigo_cafci="1", moneda="ARS", patrimonio=None),
        ]
        (categoria,) = agregados_por_categoria(fondos)
        (bloque_ars,) = categoria["por_moneda"]
        assert bloque_ars["aum"] is None
        (fondo_dict,) = bloque_ars["fondos"]
        assert fondo_dict["participacion_pct"] is None

    def test_cantidad_fondos_por_moneda_y_por_categoria(self) -> None:
        fondos = [
            fondo(codigo_cafci="1", moneda="ARS"),
            fondo(codigo_cafci="2", moneda="ARS"),
            fondo(codigo_cafci="3", moneda="USD"),
        ]
        (categoria,) = agregados_por_categoria(fondos)
        assert categoria["cantidad_fondos"] == 3
        por_moneda = {b["moneda"]: b["cantidad_fondos"] for b in categoria["por_moneda"]}
        assert por_moneda == {"ARS": 2, "USD": 1}


class TestAgregadosPorGestora:
    def test_agrupa_por_gerente_tal_cual_sin_normalizar_grafia(self) -> None:
        fondos = [
            fondo(codigo_cafci="1", gerente="Gainvest S.A."),
            fondo(codigo_cafci="2", gerente="GAINVEST SA"),
        ]
        gestoras = agregados_por_gestora(fondos)
        nombres = {g["gerente"] for g in gestoras}
        assert nombres == {"Gainvest S.A.", "GAINVEST SA"}

    def test_aum_por_gestora_nunca_cruza_monedas(self) -> None:
        fondos = [
            fondo(codigo_cafci="1", gerente="Gainvest S.A.", moneda="ARS", patrimonio=1_000_000.0),
            fondo(codigo_cafci="2", gerente="Gainvest S.A.", moneda="USB", patrimonio=500_000.0),
        ]
        (gestora,) = agregados_por_gestora(fondos)
        por_moneda = {b["moneda"]: b["aum"] for b in gestora["por_moneda"]}
        assert por_moneda == {"ARS": 1_000_000.0, "USB": 500_000.0}

    def test_gerente_no_informado_queda_en_su_propio_grupo_y_al_final(self) -> None:
        fondos = [
            fondo(codigo_cafci="1", gerente="Gainvest S.A."),
            fondo(codigo_cafci="2", gerente=None),
        ]
        gestoras = agregados_por_gestora(fondos)
        assert gestoras[-1]["gerente"] is None
        assert gestoras[-1]["cantidad_fondos"] == 1

    def test_flujo_neto_siempre_declarado_como_no_disponible(self) -> None:
        (gestora,) = agregados_por_gestora([fondo()])
        assert gestora["flujo_neto"]["disponible"] is False
        assert "planillas" in gestora["flujo_neto"]["motivo"]

    def test_market_share_se_suma_cuando_esta_informado(self) -> None:
        fondos = [
            fondo(codigo_cafci="1", gerente="Gainvest S.A.", market_share=1.2),
            fondo(codigo_cafci="2", gerente="Gainvest S.A.", market_share=0.8),
        ]
        (gestora,) = agregados_por_gestora(fondos)
        assert gestora["market_share"] == 2.0

    def test_market_share_ausente_en_todos_los_fondos_es_null(self) -> None:
        (gestora,) = agregados_por_gestora([fondo(market_share=None)])
        assert gestora["market_share"] is None
