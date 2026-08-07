"""El port contra su original: el backend y `tools/cupones.py` tienen que dar los mismos números.

El backend no importa de `tools/`, así que la matemática de los cupones está copiada. Una copia sin
un test que la compare no es un port: es una segunda implementación que va a divergir sin que nadie
se entere, y el día que diverja el motor y el producto van a estar proyectando rentas distintas del
mismo bono. Es el mismo arreglo que `test_universo_paridad_motor.py` para la sanidad.

## Qué es exactamente lo que verifica este archivo, y qué no

El GWT-4 de F-015 pide que los nominales de RUCED, SBC2D, CS47D y LOC5D reproduzcan **exacto los del
Excel real de la mesa** ("Propuesta Base 7-26", hoja "Renta Fija pago mensual"). **Ese Excel no
está en el repositorio** y no se pudo acceder a él, así que ese GWT no está verificado acá y no se
lo debe dar por verificado.

Lo que sí se verifica es otra cosa, y hay que leerla como lo que es: **la implementación del backend
reproduce al motor sobre el mismo input**, pago por pago y mes por mes, sobre el cronograma
versionado (`data/output/cashflow_completo.csv`) y el universo versionado
(`data/output/universo_consolidado.xlsx`). El motor es el que fue validado contra el Excel en su
momento; este test dice que el backend no se despegó de él. Es una cadena de dos eslabones y el
primero no se re-verifica acá.

Los cuatro tickers del GWT tienen su propia comparación además de la general, porque son los que
alguien va a querer mirar si algún día esto falla.
"""

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from app.calendario.cupones import flujos_por_peso, indexar_cronograma, indexar_paridades
from app.calendario.grilla import armar_calendario
from app.universo.segmentacion import segmentar

RAIZ_REPO = Path(__file__).resolve().parents[2]
CONSOLIDADO = RAIZ_REPO / "data" / "output" / "universo_consolidado.xlsx"
CASHFLOW = RAIZ_REPO / "data" / "output" / "cashflow_completo.csv"

# Fija a propósito: el input está versionado, así que con una fecha fija el test es reproducible
# para siempre. Una fecha móvil haría que el conjunto de pagos futuros cambiara todos los días y que
# un fallo no se pudiera distinguir de un cambio del calendario.
HOY = date(2026, 8, 7)
HOY_MOTOR = pd.Timestamp(HOY)

# Los cuatro del GWT-4. El cronograma de los cuatro está indexado bajo la especie O (RUCEO, SBC2O,
# CS47O, LOC5O), así que sólo se los encuentra cruzando por raíz de emisión: son justamente el caso
# que el lookup existe para resolver.
DEL_GWT = ["CS47D", "LOC5D", "RUCED", "SBC2D"]

TOLERANCIA = 1e-12


@pytest.fixture(scope="module")
def datos():
    """El universo y el cronograma versionados, más lo que el motor necesita para leerlos igual."""
    if not CONSOLIDADO.exists() or not CASHFLOW.exists():
        pytest.skip("faltan data/output/universo_consolidado.xlsx o cashflow_completo.csv")

    resumen = pd.read_excel(CONSOLIDADO, sheet_name="Resumen")
    especies = segmentar(resumen.to_dict("records")).especies
    tickers = [e.ticker for e in especies]

    # El motor recibe exactamente el mismo conjunto y en el mismo orden, para que las listas de
    # faltantes se puedan comparar posición por posición y no sólo como conjuntos.
    universo_motor = resumen.set_index("ticker").loc[tickers].reset_index()
    return especies, universo_motor, resumen


@pytest.fixture(scope="module")
def motor():
    """`tools/cupones.py` corrido tal cual está, sin tocarle una línea."""
    sys.path.insert(0, str(RAIZ_REPO / "tools"))
    import cupones

    return cupones


@pytest.fixture(scope="module")
def flujos_del_motor(motor, datos):
    _, universo_motor, _ = datos
    alertas: list[str] = []
    cashflow = motor.cargar_cashflow(alertas, str(CASHFLOW))
    assert cashflow is not None, alertas
    return motor.flujos_por_peso(universo_motor, cashflow, HOY_MOTOR, alertas), alertas


@pytest.fixture(scope="module")
def flujos_del_backend(datos):
    especies, _, resumen = datos
    filas = pd.read_csv(CASHFLOW, parse_dates=["issue_date", "payment_date"]).to_dict("records")
    cronograma = indexar_cronograma(filas)
    paridades = indexar_paridades(resumen[["ticker", "paridad"]].to_dict("records"))
    return flujos_por_peso(especies, cronograma, paridades, HOY), cronograma


def _indexado(flujos) -> dict[tuple[str, pd.Timestamp], tuple[float, float, float]]:
    return {
        (f.ticker, pd.Timestamp(f.fecha)): (f.pct_renta, f.pct_amortizacion, f.pct_total)
        for f in flujos.flujos
    }


def _indexado_motor(df: pd.DataFrame) -> dict[tuple[str, pd.Timestamp], tuple[float, float, float]]:
    return {
        (fila.ticker, fila.payment_date): (fila.pct_interes, fila.pct_capital, fila.pct_total)
        for fila in df.itertuples()
    }


# --- Los flujos, pago por pago --------------------------------------------------------------------


def test_el_backend_produce_exactamente_los_mismos_pagos_que_el_motor(
    flujos_del_backend, flujos_del_motor
) -> None:
    """Mismo conjunto de (ticker, fecha): ni un pago de más ni uno de menos."""
    mios, _ = flujos_del_backend
    del_motor, _ = flujos_del_motor
    assert set(_indexado(mios)) == set(_indexado_motor(del_motor))


def test_cada_pago_vale_lo_mismo_en_los_dos(flujos_del_backend, flujos_del_motor) -> None:
    """Renta, amortización y total, cada uno contra su equivalente del motor.

    `pct_renta` es `pct_interes` y `pct_amortizacion` es `pct_capital`: el backend los renombró para
    hablar el idioma de la spec, pero son el mismo número y esto es lo que lo demuestra.
    """
    mios, _ = flujos_del_backend
    del_motor, _ = flujos_del_motor
    referencia = _indexado_motor(del_motor)

    diferencias = [
        (clave, valores, referencia[clave])
        for clave, valores in _indexado(mios).items()
        if max(abs(a - b) for a, b in zip(valores, referencia[clave], strict=True)) > TOLERANCIA
    ]
    assert diferencias == []


def test_los_dos_dejan_afuera_a_los_mismos_instrumentos_sin_cronograma(
    flujos_del_backend, flujos_del_motor
) -> None:
    """El cruce por raíz encuentra lo mismo en los dos, que es lo que dice que el lookup es el
    mismo lookup."""
    mios, _ = flujos_del_backend
    _, alertas = flujos_del_motor
    del_motor = next(a for a in alertas if "sin cashflow en la fuente" in a)
    assert f"{len(mios.sin_cronograma)} instrumentos" in del_motor


def test_los_cuatro_tickers_del_gwt_reproducen_al_motor_pago_por_pago(
    flujos_del_backend, flujos_del_motor
) -> None:
    """GWT-4, con la salvedad del docstring del módulo: esto reproduce **al motor**, no al Excel.

    Los cuatro entran por el cruce de raíz —su cronograma está bajo la especie O— así que este test
    es además la verificación de que el lookup encuentra el bono correcto para la especie correcta.
    """
    mios, _ = flujos_del_backend
    del_motor, _ = flujos_del_motor
    referencia = _indexado_motor(del_motor)
    calculados = _indexado(mios)

    for ticker in DEL_GWT:
        pagos = {clave: v for clave, v in calculados.items() if clave[0] == ticker}
        assert pagos, f"{ticker} no produjo ningún flujo: revisar el cruce por raíz"
        for clave, valores in pagos.items():
            assert valores == pytest.approx(referencia[clave], abs=TOLERANCIA)


# --- La grilla de doce meses ----------------------------------------------------------------------


def test_la_grilla_mensual_coincide_con_la_del_motor_para_los_cuatro_del_gwt(
    datos, motor, flujos_del_backend, flujos_del_motor
) -> None:
    """Una cartera de los cuatro, mes a mes, contra `cupones.calendario`.

    Los cuatro son hard dollar, así que cobran en una sola moneda y el total único del motor es
    comparable contra el total en dólares del backend. Con monedas mezcladas no lo sería, y ésa es
    justamente la diferencia declarada en `grilla.py`.
    """
    especies, _, _ = datos
    mios, _ = flujos_del_backend
    del_motor, _ = flujos_del_motor
    montos = dict.fromkeys(DEL_GWT, 100_000.0)

    calendario = armar_calendario(
        mios, [e for e in especies if e.ticker in montos], HOY, montos=montos
    )
    cartera = pd.DataFrame({"ticker": DEL_GWT, "monto": [100_000.0] * len(DEL_GWT)})
    detalle, _totales = motor.calendario(cartera, del_motor, HOY_MOTOR)

    esperado = {fila.Mes: (fila.renta, fila.amortizacion) for fila in detalle.itertuples()}
    obtenido = {
        mes.etiqueta: ((mes.renta or {}).get("usd", 0.0), (mes.amortizacion or {}).get("usd", 0.0))
        for mes in calendario.meses
    }

    assert set(obtenido) == set(esperado)
    for etiqueta, (renta, amortizacion) in obtenido.items():
        assert renta == pytest.approx(esperado[etiqueta][0], abs=1e-9)
        assert amortizacion == pytest.approx(esperado[etiqueta][1], abs=1e-9)


def test_los_meses_sin_renta_son_los_mismos_que_cuenta_el_motor(
    datos, motor, flujos_del_backend, flujos_del_motor
) -> None:
    """El número que decide un armado: cuántos meses del año quedan sin cobrar renta."""
    especies, _, _ = datos
    mios, _ = flujos_del_backend
    del_motor, _ = flujos_del_motor
    montos = dict.fromkeys(DEL_GWT, 100_000.0)

    calendario = armar_calendario(
        mios, [e for e in especies if e.ticker in montos], HOY, montos=montos
    )
    cartera = pd.DataFrame({"ticker": DEL_GWT, "monto": [100_000.0] * len(DEL_GWT)})
    _detalle, totales = motor.calendario(cartera, del_motor, HOY_MOTOR)

    assert len(calendario.meses_sin_renta) == totales["meses_sin_renta"]
