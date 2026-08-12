"""Sensibilidad del precio por repricing completo — F-040.

`retorno_por_tir` no tiene una forma cerrada conocida como la de `resolver_tir` con un cupón cero,
así que lo que se prueba acá es autoconsistencia, signo, monotonía y la duración modificada como
cota — nunca como umbral con tolerancia inventada (ver el docstring del plan sobre por qué GWT-2 no
se puede verificar contra la tabla externa de 0,12 pp: no está versionada en el repo).

La segunda mitad de este archivo es el sustituto declarado de esa verificación: una regresión
contra `tools/cupones.py::retorno_por_tir`, que sí fue el que se verificó en su momento contra la
tabla de la mesa. El mecanismo es el mismo que usa `test_calendario_paridad_motor.py`.
"""

import itertools
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from app.calendario.cupones import Pago, indexar_cronograma
from app.calendario.metricas import anios_entre, duracion_modificada, retorno_por_tir

HOY = date(2026, 8, 7)

DELTAS_ESTANDAR = [d / 10_000 for d in (-500, -400, -300, -200, -100, 0, 100, 200)]


def pago(
    fecha: str, *, capital: float = 0.0, interes: float = 0.0, residual: float = 100.0
) -> Pago:
    return Pago(
        fecha=date.fromisoformat(fecha),
        capital=capital,
        interes=interes,
        total=capital + interes,
        residual=residual,
        emision=date(2020, 1, 1),
    )


class TestAutoconsistenciaYSigno:
    def test_delta_cero_da_retorno_exactamente_cero(self) -> None:
        """`VP(y)/VP(y) - 1` es idénticamente cero, no "casi cero"."""
        pagos = [pago("2028-01-09", interes=5.0), pago("2030-01-09", capital=100.0, interes=5.0)]
        r = retorno_por_tir(pagos, 0.10, [0.0], HOY)
        assert r is not None
        assert r[0.0] == 0.0

    def test_suba_de_tir_da_retorno_negativo_y_compresion_positivo(self) -> None:
        pagos = [pago("2028-01-09", interes=5.0), pago("2030-01-09", capital=100.0, interes=5.0)]
        r = retorno_por_tir(pagos, 0.10, [0.01, -0.01], HOY)
        assert r is not None
        assert r[0.01] < 0
        assert r[-0.01] > 0

    def test_el_retorno_decrece_estrictamente_al_crecer_el_delta(self) -> None:
        pagos = [pago("2029-01-09", interes=6.0), pago("2033-01-09", capital=100.0, interes=6.0)]
        r = retorno_por_tir(pagos, 0.10, DELTAS_ESTANDAR, HOY)
        assert r is not None
        ordenados = [r[d] for d in DELTAS_ESTANDAR]
        assert all(a > b for a, b in itertools.pairwise(ordenados))


class TestConvexidadContraLaDuracion:
    """La duración modificada como cota, no como umbral (Test Strategy del plan de F-040).

    Las dos desigualdades son consecuencia exacta de la convexidad de un flujo positivo: un bono
    largo sube más de lo que la recta tangente dice ante una compresión grande, y cae menos de lo
    que dice ante una suba grande. No llevan tolerancia y no se les inventa una.
    """

    @staticmethod
    def _pagos_largo() -> list[Pago]:
        return [
            pago(f"{anio}-01-09", interes=7.0, capital=0.0 if anio < 2036 else 100.0)
            for anio in range(2027, 2037)
        ]

    def test_compresion_grande_da_mas_suba_que_la_aproximacion_lineal(self) -> None:
        pagos = self._pagos_largo()
        tir = 0.10
        t = [anios_entre(HOY, p.fecha) for p in pagos]
        cf = [p.total for p in pagos]
        dur_mod = duracion_modificada(t, cf, tir)
        assert dur_mod is not None

        r = retorno_por_tir(pagos, tir, [-0.03], HOY)
        assert r is not None
        assert r[-0.03] > dur_mod * 0.03

    def test_suba_grande_cae_menos_que_la_aproximacion_lineal(self) -> None:
        pagos = self._pagos_largo()
        tir = 0.10
        t = [anios_entre(HOY, p.fecha) for p in pagos]
        cf = [p.total for p in pagos]
        dur_mod = duracion_modificada(t, cf, tir)
        assert dur_mod is not None

        r = retorno_por_tir(pagos, tir, [0.02], HOY)
        assert r is not None
        assert abs(r[0.02]) < dur_mod * 0.02


class TestGuardiaDelPiso:
    def test_un_delta_degenerado_se_omite_y_el_resto_se_calcula(self) -> None:
        pagos = [pago("2028-01-09", interes=5.0), pago("2030-01-09", capital=100.0, interes=5.0)]
        r = retorno_por_tir(pagos, 0.02, [-1.02, 0.0], HOY)
        assert r is not None
        assert set(r) == {0.0}

    def test_con_todos_los_deltas_degenerados_no_hay_resultado(self) -> None:
        pagos = [pago("2028-01-09", interes=5.0), pago("2030-01-09", capital=100.0, interes=5.0)]
        assert retorno_por_tir(pagos, 0.02, [-1.02, -2.0], HOY) is None


class TestFaltantes:
    def test_sin_tir_actual_no_hay_resultado(self) -> None:
        pagos = [pago("2028-01-09", interes=5.0)]
        assert retorno_por_tir(pagos, None, [0.0], HOY) is None

    def test_sin_pagos_futuros_no_hay_resultado(self) -> None:
        assert retorno_por_tir([], 0.10, [0.0], HOY) is None

    def test_con_todos_los_pagos_pasados_no_hay_resultado(self) -> None:
        pagos = [pago("2020-01-09", interes=5.0), pago("2021-01-09", capital=100.0, interes=5.0)]
        assert retorno_por_tir(pagos, 0.10, [0.0], HOY) is None


# --- Regresión contra el motor: el sustituto declarado de GWT-2 --------------------------------

RAIZ_REPO = Path(__file__).resolve().parents[2]
CASHFLOW = RAIZ_REPO / "data" / "output" / "cashflow_completo.csv"

# Los cuatro propuestos por el plan de F-040. Los cuatro tienen cronograma versionado bajo su
# propio ticker (ninguno necesita el cruce por raíz para aparecer acá).
TICKERS_REGRESION = ["AL30", "GD30", "AE38", "GD46"]

# Insumo del test, no un dato de mercado: el motor y el backend tienen que dar el mismo número
# partiendo de la misma TIR, sea cual sea.
TIR_FIJA = 0.12


@pytest.fixture(scope="module")
def motor():
    """`tools/cupones.py` corrido tal cual está, sin tocarle una línea."""
    if not CASHFLOW.exists():
        pytest.skip("falta data/output/cashflow_completo.csv")
    sys.path.insert(0, str(RAIZ_REPO / "tools"))
    import cupones

    return cupones


@pytest.fixture(scope="module")
def cashflow_motor(motor):
    alertas: list[str] = []
    cashflow = motor.cargar_cashflow(alertas, str(CASHFLOW))
    assert cashflow is not None, alertas
    return cashflow


@pytest.fixture(scope="module")
def cronograma_backend():
    filas = pd.read_csv(CASHFLOW, parse_dates=["issue_date", "payment_date"]).to_dict("records")
    return indexar_cronograma(filas)


class TestRegresionContraElMotor:
    """El motor es quien se verificó contra la tabla de la mesa (0,12 pp, ESTADO.md, ver también
    el docstring de este módulo); esto dice que el backend no se despegó del motor. Ni más, ni
    menos: la tabla externa no está versionada y no se re-verifica acá."""

    def test_el_backend_reproduce_al_motor_en_los_cuatro_tickers(
        self, motor, cashflow_motor, cronograma_backend
    ) -> None:
        hoy_motor = pd.Timestamp(HOY)
        vistos = []
        for ticker in TICKERS_REGRESION:
            pagos = cronograma_backend.pagos_de(ticker)
            if not pagos:
                continue
            vistos.append(ticker)

            del_backend = retorno_por_tir(pagos, TIR_FIJA, DELTAS_ESTANDAR, HOY)
            del_motor = motor.retorno_por_tir(
                cashflow_motor, ticker, TIR_FIJA, DELTAS_ESTANDAR, hoy_motor
            )

            assert del_backend is not None, f"{ticker}: el backend no produjo resultado"
            assert del_motor is not None, f"{ticker}: el motor no produjo resultado"
            assert set(del_backend) == set(del_motor)
            for delta, valor in del_backend.items():
                assert valor == pytest.approx(del_motor[delta])

        assert vistos, "ninguno de los cuatro tickers propuestos tiene cronograma versionado"
