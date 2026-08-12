"""Qué especie entra al cálculo propio y cuál no — F-051, la parte que decide el dominio.

`test_calendario_metricas.py` prueba que el número esté bien calculado. Acá se prueba lo otro: que
se calcule **sólo donde corresponde**. La tabla por naturaleza de tasa, la regla de que el precio y
el flujo compartan moneda, y que todo lo que queda afuera salga nombrado en una alerta en vez de
desaparecer.

El caso que más importa vuelve a ser el que no calcula nada: un bono CER tiene precio, cronograma y
todo lo que hace falta para que el solver devuelva un número — y ese número sería una tasa nominal
presentada donde va una real.
"""

from datetime import date

import pytest

from app.calendario.metricas import MetricasEspecie
from app.ingesta.byma.normalizacion import normalizar_fila_rueda
from app.ingesta.consolidacion.armado import armar_consolidacion
from app.ingesta.consolidacion.metricas import (
    CODIGO_METRICAS_CONTRASTE_IAMC,
    CODIGO_METRICAS_FUERA_DE_NATURALEZA,
    CODIGO_METRICAS_SIN_INSUMO,
    FUENTE_CALCULO,
    FUENTE_FUERA,
    FUENTE_IAMC,
    ContrasteMetricas,
    ResultadoMetricas,
    fuente_de_metricas,
)
from app.ingesta.iamc.parser import FilaInforme

HOY = date(2026, 8, 7)
FECHA_INFORME = date(2026, 8, 5)


def especie(ticker: str, *, moneda="USD", ultimo=56.7, **extra):
    crudo = {
        "symbol": ticker,
        "denominationCcy": moneda,
        "settlementType": "2",
        "trade": ultimo,
        "volumeAmount": 1000.0,
        "bidPrice": 99.0,
        "offerPrice": 101.0,
        "numberOfOrders": 5,
        "maturityDate": "2030-07-09",
        **extra,
    }
    return normalizar_fila_rueda(crudo)


def informe(ticker: str, **overrides) -> FilaInforme:
    base = dict.fromkeys(FilaInforme.__annotations__)
    base.update(
        {
            "ticker": ticker,
            "seccion": "DEUDA CORPORATIVA EN USD - LEY ARG",
            "fecha_informe": FECHA_INFORME,
            "emisor": "YPF S.A.",
            "ley": "Ley Argentina",
            "moneda_pago": "USD",
            "tir": 7.92,
            "paridad_pct": 98.5,
            "duracion_modificada": 6.7,
        }
    )
    base.update(overrides)
    return base  # type: ignore[return-value]


def cronograma(ticker: str, tipo: str) -> list[dict[str, object]]:
    """Tres pagos futuros con amortización al final: alcanza para que el solver resuelva."""
    return [
        {
            "ticker": ticker,
            "type": tipo,
            "payment_date": fecha,
            "issue_date": date(2020, 1, 1),
            "capital": capital,
            "interest_rate": 5.0,
            "interest_amount": 2.5,
            "residual_value": 100.0 - capital,
            "cash_flow": 2.5 + capital,
        }
        for fecha, capital in (
            (date(2027, 1, 9), 0.0),
            (date(2028, 1, 9), 0.0),
            (date(2029, 1, 9), 100.0),
        )
    ]


def armar(**kwargs):
    kwargs.setdefault("hoy", HOY)
    return armar_consolidacion(**kwargs)


def alerta_con(resultado, codigo):
    return next((a for a in resultado.alertas if a.codigo == codigo), None)


class TestQuienSeCalcula:
    """La tabla de decisión, una fila por naturaleza de tasa."""

    @pytest.mark.parametrize(
        ("tipo_tasa", "moneda", "esperado"),
        [
            ("hard-dollar", "USD", FUENTE_CALCULO),
            # `EXT` pasó de `calculo` a `fuera` el 08/08/2026 con la regla 11: para dividir el
            # precio por el flujo hay que saber que están en la misma moneda, y BYMA no documenta
            # qué denota ese código. Cuesta 63 de las 276 hard-dollar calculables del universo real.
            ("hard-dollar", "EXT", FUENTE_FUERA),
            ("hard-dollar", "ARS", FUENTE_FUERA),
            ("bopreal", "USD", FUENTE_CALCULO),
            ("bopreal", "EXT", FUENTE_FUERA),
            ("tasa-fija", "ARS", FUENTE_CALCULO),
            ("tasa-fija", "USD", FUENTE_FUERA),
            ("cer", "ARS", FUENTE_FUERA),
            ("dollar-linked", "ARS", FUENTE_FUERA),
            ("badlar", "ARS", FUENTE_FUERA),
            ("tamar", "ARS", FUENTE_FUERA),
            (None, "ARS", FUENTE_IAMC),
        ],
    )
    def test_la_tabla_por_naturaleza(self, tipo_tasa, moneda, esperado) -> None:
        assert fuente_de_metricas(tipo_tasa, moneda) == esperado

    def test_una_naturaleza_desconocida_conserva_lo_publicado_en_vez_de_improvisar(self) -> None:
        assert fuente_de_metricas("uva-plus-plus", "ARS") == FUENTE_IAMC

    def test_sin_moneda_declarada_no_se_calcula(self) -> None:
        """La moneda se lee, no se deduce del sufijo: hay especies con D declaradas en pesos."""
        assert fuente_de_metricas("hard-dollar", None) == FUENTE_FUERA


class TestUnBonoCerNoSeCalcula:
    """GWT-5, el caso que la regla 2 protege."""

    def test_queda_fuera_y_la_alerta_dice_por_que(self) -> None:
        resultado = armar(
            especies_por_endpoint={"public-bonds": [especie("TX26", moneda="ARS", ultimo=1500.0)]},
            filas_cashflow=cronograma("TX26", "CER"),
        )

        (precio,) = resultado.filas_precios
        assert precio["tir"] is None, "descontar el flujo sin ajuste daría una tasa nominal"
        assert precio["paridad"] is None

        alerta = alerta_con(resultado, CODIGO_METRICAS_FUERA_DE_NATURALEZA)
        assert alerta is not None
        detalle = alerta.detalle["por_motivo"]["cer"]
        assert detalle["tickers"] == ["TX26"]
        assert "coeficiente CER" in detalle["porque"]

    def test_no_se_le_reporta_la_tasa_de_otra_naturaleza(self) -> None:
        """Ni siquiera cuando el solver tendría todo para devolver un número."""
        resultado = armar(
            especies_por_endpoint={"public-bonds": [especie("TX26", moneda="ARS", ultimo=1500.0)]},
            filas_cashflow=cronograma("TX26", "CER"),
            filas_iamc=[informe("TX26", tir=None, paridad_pct=None, duracion_modificada=None)],
            fecha_informe=FECHA_INFORME,
        )
        (precio,) = resultado.filas_precios
        assert precio["tir"] is None


class TestFaltaDeInsumo:
    """GWT-3: el campo queda vacío y la especie sale nombrada."""

    def test_sin_cronograma_la_especie_queda_nombrada(self) -> None:
        resultado = armar(
            especies_por_endpoint={"public-bonds": [especie("AL30D")]},
            filas_cashflow=cronograma("GD30", "HARD_DOLLAR"),
        )
        # Sin cronograma propio no se clasifica y no llega a precios: lo declara la alerta de clase.
        assert resultado.filas_precios == []

    def test_sin_precio_del_dia_queda_vacia_y_nombrada(self) -> None:
        resultado = armar(
            especies_por_endpoint={"public-bonds": [especie("AL30D", ultimo=0.0)]},
            filas_cashflow=cronograma("AL30", "HARD_DOLLAR"),
        )

        (precio,) = resultado.filas_precios
        assert precio["last_price"] is None, "un precio de cero es que no operó"
        assert precio["tir"] is None
        alerta = alerta_con(resultado, CODIGO_METRICAS_SIN_INSUMO)
        assert alerta is not None
        assert alerta.detalle["por_motivo"]["sin_precio"] == ["AL30D"]

    def test_un_bono_vencido_se_declara_vencido(self) -> None:
        pagos = [
            {
                "ticker": "AL30",
                "type": "HARD_DOLLAR",
                "payment_date": date(2025, 1, 9),
                "issue_date": date(2020, 1, 1),
                "capital": 100.0,
                "interest_rate": 5.0,
                "interest_amount": 2.5,
                "residual_value": 0.0,
                "cash_flow": 102.5,
            }
        ]
        resultado = armar(
            especies_por_endpoint={"public-bonds": [especie("AL30D")]},
            filas_cashflow=pagos,
        )
        alerta = alerta_con(resultado, CODIGO_METRICAS_SIN_INSUMO)
        assert alerta is not None
        assert alerta.detalle["por_motivo"]["vencida"] == ["AL30D"]


class TestPrecedencia:
    def test_el_calculo_propio_no_lo_pisa_iamc(self) -> None:
        """Aunque IAMC publique esa misma especie, la que manda es la calculada."""
        resultado = armar(
            especies_por_endpoint={"public-bonds": [especie("AL30D")]},
            filas_cashflow=cronograma("AL30", "HARD_DOLLAR"),
            filas_iamc=[informe("AL30D", tir=7.92)],
            fecha_informe=FECHA_INFORME,
        )
        (precio,) = resultado.filas_precios
        assert precio["tir"] is not None
        assert precio["tir"] != pytest.approx(0.0792)
        assert "calculo" in precio["fuente"]

    def test_el_calculo_propio_no_lo_pisa_el_arrastre_de_ayer(self) -> None:
        resultado = armar(
            especies_por_endpoint={"public-bonds": [especie("AL30D")]},
            filas_cashflow=cronograma("AL30", "HARD_DOLLAR"),
            metricas_previas={
                "AL30D": {
                    "tir": 0.0757,
                    "duration": 6.7,
                    "paridad": 0.88,
                    "convexidad": 0.55,
                    "residual_value": 100.0,
                    "fecha_metricas": date(2026, 8, 4),
                }
            },
        )
        (precio,) = resultado.filas_precios
        assert precio["tir"] != pytest.approx(0.0757), "una TIR de ayer con el precio de hoy no es"
        assert precio["convexidad"] == 0.55, "lo que IAMC sí es fuente de, se conserva"

    def test_lo_que_no_se_calcula_sigue_viniendo_de_iamc(self) -> None:
        resultado = armar(
            especies_por_endpoint={
                "public-bonds": [especie("AL30", moneda="ARS", ultimo=86_320.0)]
            },
            filas_cashflow=cronograma("AL30", "HARD_DOLLAR"),
            filas_iamc=[informe("AL30", tir=7.92)],
            fecha_informe=FECHA_INFORME,
        )
        (precio,) = resultado.filas_precios
        assert precio["tir"] == pytest.approx(0.0792)
        assert precio["fuente"] == "byma+iamc"

    def test_la_tna_sigue_sin_fuente(self) -> None:
        """El solver devuelve efectiva anual; pasarla a nominal exige una convención inventada."""
        resultado = armar(
            especies_por_endpoint={"public-bonds": [especie("AL30D")]},
            filas_cashflow=cronograma("AL30", "HARD_DOLLAR"),
        )
        (precio,) = resultado.filas_precios
        assert precio["tir"] is not None
        assert precio["tna"] is None


class TestCronogramaPersistido:
    def test_una_corrida_sin_docta_calcula_igual_con_el_cronograma_guardado(self) -> None:
        """El cronograma es contractual y no envejece; el precio sigue siendo el del día."""
        resultado = armar(
            especies_por_endpoint={"public-bonds": [especie("AL30D")]},
            filas_cashflow=None,
            cronograma_persistido=cronograma("AL30", "HARD_DOLLAR"),
        )
        (precio,) = resultado.filas_precios
        assert precio["tir"] is not None
        assert resultado.filas_cashflow is None, "no se re-persiste lo que no vino de la fuente"


class TestContrasteContraIamc:
    """GWT-4: IAMC pasa de fuente a control."""

    def test_una_divergencia_grande_alerta_y_conserva_el_calculo(self) -> None:
        resultado = armar(
            especies_por_endpoint={"public-bonds": [especie("AL30D", ultimo=56.7)]},
            filas_cashflow=cronograma("AL30", "HARD_DOLLAR"),
            filas_iamc=[informe("AL30", tir=1.0, paridad_pct=98.5, duracion_modificada=6.7)],
            fecha_informe=FECHA_INFORME,
        )

        alerta = alerta_con(resultado, CODIGO_METRICAS_CONTRASTE_IAMC)
        assert alerta is not None
        (precio,) = resultado.filas_precios
        assert precio["tir"] is not None, "el cálculo propio se conserva como dato"

    def test_las_unidades_se_convierten_antes_de_comparar(self) -> None:
        """IAMC publica en puntos y nosotros en fracción: comparar 7,92 contra 0,0792 alertaría
        todos los días en todas las emisiones y taparía las divergencias de verdad."""
        contraste = ContrasteMetricas(
            raiz="AL30",
            ticker_propio="AL30D",
            ticker_iamc="AL30",
            tir_propia=0.0792,
            tir_iamc=0.0792,
            paridad_propia=0.985,
            paridad_iamc=0.985,
            duration_propia=6.7,
            duration_iamc=6.7,
        )
        assert contraste.coincide

    def test_no_se_contrasta_contra_un_faltante(self) -> None:
        contraste = ContrasteMetricas(
            raiz="AL30", ticker_propio="AL30D", ticker_iamc="AL30", tir_propia=0.12, tir_iamc=None
        )
        assert contraste.coincide, "un faltante no es una divergencia"
        assert contraste.divergencias() == {}

    def test_una_diferencia_dentro_de_la_tolerancia_no_alerta(self) -> None:
        """El canje MEP/cable separa las dos puntas todos los días: no es un hallazgo."""
        contraste = ContrasteMetricas(
            raiz="AL30",
            ticker_propio="AL30D",
            ticker_iamc="AL30",
            tir_propia=0.0850,
            tir_iamc=0.0792,
        )
        assert contraste.coincide


class TestResumen:
    def test_cuenta_lo_calculado_y_lo_que_falto_por_motivo(self) -> None:
        resultado = ResultadoMetricas()
        resultado.registrar("AL30D", MetricasEspecie(0.12, 2.1, 2.3, 0.88, None))
        resultado.anotar("cer", "TX26")
        resultado.anotar("cer", "TZX28")
        resultado.anotar("sin_precio", "GD35D")

        assert resultado.resumen() == {
            "calculadas": 1,
            "sin_metrica": {"cer": 2, "sin_precio": 1},
            "contrastadas": 0,
            "divergentes": 0,
        }
