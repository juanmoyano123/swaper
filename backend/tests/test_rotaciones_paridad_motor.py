"""El port contra su original: `app/rotaciones/` y `tools/detectar_swaps.py` tienen que coincidir
(GWT-2 de la ficha, riesgo R9 del plan de la tanda: "el desacople del motor resulta ser reescritura
encubierta").

Mismo patrón que `test_concentracion_paridad_motor.py`/`test_armado_paridad_motor.py`: se corren
las dos implementaciones sobre el consolidado versionado (`data/output/universo_consolidado.xlsx`
+ `cashflow_completo.csv`) y se compara el resultado.

## Por qué el universo del backend se arma traduciendo el DataFrame del motor, y no por el camino
## real (`segmentar` + `sanear_universo`)

Mismo motivo que documenta `test_armado_paridad_motor.py`: `universo_consolidado.xlsx` es un
snapshot anterior a F-012 y no tiene `moneda_cotizacion`/`denominationCcy`. Sin esa columna,
`derivar_tipo_de_cambio` no encuentra un solo par y `volumen_usd` queda `None` para todo el
universo del lado del backend — mientras que el motor, que deriva la moneda del sufijo del ticker,
sí arma el suyo. El filtro de liquidez y `mejora_volumen` (que sí importan acá, a diferencia de
concentración) quedarían neutralizados sólo de un lado. Se arma entonces **una sola vez** el
universo con `tools/segmentos.py::cargar_universo(dedup=False)` — la carga real del motor, con su
propio tipo de cambio— y se traduce a `EspecieUniverso` fila por fila sin volver a derivar nada.
Lo que se compara a partir de acá es el algoritmo de `evaluar_par`/`detectar`, no las capas de
abajo (que ya tienen su propio test de paridad).

## Divergencias deliberadas, declaradas

- **Costo/spread/payback no se comparan.** F-035 (tanda 13) no existe todavía; se corre el motor
  con `--sin-spread` (`spread_pct` en `NaN`) para que el costo no entre en la comparación, y el
  backend directamente no tiene esos campos (D8 del plan de la tanda).
- **El flag `revisar` de `filtrar_operables` del CLI no existe en `saneado.operables()`.** Acá no
  se pasa por `saneado.operables()` (ver arriba), así que el corte de "operable" para los destinos
  se aplica **explícito** con el mismo criterio del motor (`rendimiento`, `lastPrice`, `dato_sano`,
  `revisar`) en los dos lados — es la forma concreta de neutralizar esta divergencia.
- **La propagación de sector no aplica**: el motor de swaps no usa sector en ningún criterio.
"""

import sys
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from app.calendario.cupones import flujos_por_peso, indexar_cronograma, indexar_paridades
from app.concentracion.riesgo import derivar_riesgo
from app.ingesta.raiz import raiz_emision
from app.rotaciones.constantes import ParametrosRotacion
from app.rotaciones.emisores import clave_emisor_swap, nombre_emisor
from app.rotaciones.frecuencia import frecuencia_por_raiz
from app.rotaciones.legislacion import premio_por_legislacion
from app.rotaciones.motor import detectar
from app.universo.segmentacion import EspecieUniverso

RAIZ_REPO = Path(__file__).resolve().parents[2]
CONSOLIDADO = RAIZ_REPO / "data" / "output" / "universo_consolidado.xlsx"
CASHFLOW = RAIZ_REPO / "data" / "output" / "cashflow_completo.csv"

# Fija a propósito, mismo criterio que `test_calendario_paridad_motor.py`: con el input
# versionado, una fecha fija hace el test reproducible para siempre.
HOY = date(2026, 8, 7)
HOY_MOTOR = pd.Timestamp(HOY)

TOLERANCIA_PP = 0.01


def _o(valor: object) -> Any:
    """Un valor de una fila del motor, o `None` si es `NaN`. Mismo criterio que
    `segmentacion.a_numero`/`_texto`, sin reimportar el módulo para una fila a mano."""
    if valor is None:
        return None
    if isinstance(valor, float) and pd.isna(valor):
        return None
    return valor


def _motor() -> Any:
    """`tools/detectar_swaps.py`, corrido tal cual está y sin tocarle una línea."""
    sys.path.insert(0, str(RAIZ_REPO / "tools"))
    import detectar_swaps

    return detectar_swaps


class _ParamsMotor:
    """Un `argparse.Namespace` a mano, con los defaults del CLI —equivalentes al perfil moderado,
    ver el docstring de `app/rotaciones/constantes.py`— y `--sin-spread`."""

    def __init__(self) -> None:
        self.min_dtir = 0.005
        self.max_mas_duration = 1.5
        self.umbral_neutro = -0.003
        self.arancel = 0.0075
        self.factor_volumen = 3.0
        self.max_rend_destino = None
        self.percentil_liquidez = 25.0
        self.percentil_distress = 95.0
        self.frecuencia_cupon = None
        self.min_rend = 0.0
        self.dias_cupon = 45
        self.top_n = 3


def _tipo_normalizado(tipo_motor: str) -> str:
    return "mejora_rendimiento" if tipo_motor.startswith("A") else "mejora_perfil"


@pytest.fixture(scope="module")
def datos_del_motor() -> tuple[pd.DataFrame, list[dict[str, Any]], list[str]]:
    if not CONSOLIDADO.exists() or not CASHFLOW.exists():
        pytest.skip("faltan data/output/universo_consolidado.xlsx o cashflow_completo.csv")
    motor = _motor()
    alertas: list[str] = []
    universo = motor.preparar_universo(alertas)
    cashflow = motor.cupones.cargar_cashflow(alertas)
    universo = motor.anotar_frecuencia_cupon(universo, cashflow, HOY_MOTOR, alertas)
    universo["spread_pct"] = pd.NA  # --sin-spread

    _spread_ley, mediana_ley = motor.tabla_spread_legislacion(universo, alertas)
    flujos = motor.cupones.flujos_por_peso(universo, cashflow, HOY_MOTOR, alertas)

    params = _ParamsMotor()
    params._topes = dict(motor.TOPE_DISTRESS_DEFAULT)
    params._mediana_ley = mediana_ley
    params._flujos = flujos
    params._hoy = HOY_MOTOR

    # `--origen todos`: el mismo modo con el que la mesa corre el CLI cuando quiere ver todo el
    # universo, no sólo lo que rinde negativo.
    oportunidades = motor.detectar(universo, universo, params, alertas)
    return universo, oportunidades, alertas


@pytest.fixture(scope="module")
def especies_del_backend(datos_del_motor) -> list[EspecieUniverso]:
    universo, _oportunidades, _alertas = datos_del_motor
    especies = []
    for fila in universo.to_dict("records"):
        ticker = str(fila["ticker"])
        especies.append(
            EspecieUniverso(
                ticker=ticker,
                raiz=raiz_emision(ticker),
                clase_activo=str(fila["clase_activo"]),
                segmento=str(fila["segmento"]),
                rendimiento=_o(fila.get("rendimiento")),
                duracion=_o(fila.get("duration_aprox")),
                ley=_o(fila.get("law")),
                moneda_cupon=_o(fila.get("couponCurrency")),
                emisor=_o(fila.get("underlying")),
                volumen_usd=_o(fila.get("volumen_usd")),
                lamina=_o(fila.get("lamina")),
                calificacion=_o(fila.get("calificacion")),
                tipo_tasa=_o(fila.get("tipo_tasa")),
            )
        )
    return especies


@pytest.fixture(scope="module")
def operables_tickers(datos_del_motor) -> set[str]:
    """El mismo corte que `segmentos.filtrar_operables`, calculado explícito para neutralizar que
    `saneado.operables()` no lee `lastPrice` ni `revisar` (ver el docstring del módulo)."""
    universo, _oportunidades, _alertas = datos_del_motor
    ok = (
        universo["rendimiento"].notna()
        & universo["lastPrice"].notna()
        & (universo["revisar"] != True)  # noqa: E712 (la columna puede venir como object)
    )
    if "dato_sano" in universo.columns:
        ok &= universo["dato_sano"]
    return set(universo.loc[ok, "ticker"].astype(str))


@pytest.fixture(scope="module")
def resultado_del_backend(especies_del_backend, operables_tickers):
    origenes = [e for e in especies_del_backend if e.rendimiento is not None]
    universo_operable = [e for e in especies_del_backend if e.ticker in operables_tickers]

    riesgos = derivar_riesgo(especies_del_backend)
    claves_emisor = {e.ticker: clave_emisor_swap(e, riesgos) for e in especies_del_backend}
    nombres_emisor = {
        e.ticker: nombre_emisor(e, claves_emisor[e.ticker]) for e in especies_del_backend
    }

    filas_cashflow = pd.read_csv(CASHFLOW, parse_dates=["issue_date", "payment_date"]).to_dict(
        "records"
    )
    cronograma = indexar_cronograma(filas_cashflow)
    frecuencias = frecuencia_por_raiz(cronograma, HOY)

    resumen = pd.read_excel(CONSOLIDADO, sheet_name="Resumen")
    paridades = indexar_paridades(resumen[["ticker", "paridad"]].to_dict("records"))
    flujos = flujos_por_peso(especies_del_backend, cronograma, paridades, HOY)

    _pares, medianas_ley = premio_por_legislacion(universo_operable, claves_emisor)

    params = ParametrosRotacion.de_perfil("moderado")
    candidatas, alertas = detectar(
        origenes,
        universo_operable,
        claves_emisor=claves_emisor,
        nombres_emisor=nombres_emisor,
        frecuencias=frecuencias,
        flujos=flujos,
        hoy=HOY,
        medianas_ley=medianas_ley,
        params=params,
    )
    return candidatas, alertas


def _por_clave_motor(oportunidades: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict]:
    return {(o["origen"], o["destino"], _tipo_normalizado(o["tipo"])): o for o in oportunidades}


def _por_clave_backend(candidatas) -> dict[tuple[str, str, str], Any]:
    return {(c.origen.ticker, c.destino.ticker, c.tipo): c for c in candidatas}


# --- GWT-2 / criterio de aceptación: TLCWO → TLCMO ----------------------------------------------


def test_tlcwo_a_tlcmo_aparece_en_las_dos_implementaciones(
    datos_del_motor, resultado_del_backend
) -> None:
    """Si el consolidado versionado alguna vez dejara de traer este par, la fixture sintética de
    `test_rotaciones_motor.py::test_tlcwo_a_tlcmo_reproduce_el_swap_que_la_mesa_ejecuto` es la
    aceptación de respaldo (declarado en la ficha): esto no se lee como regresión cuando cambie el
    dato de mercado."""
    _universo, oportunidades, _alertas = datos_del_motor
    candidatas, _alertas_backend = resultado_del_backend

    destinos_motor = {o["destino"] for o in oportunidades if o["origen"] == "TLCWO"}
    destinos_backend = {c.destino.ticker for c in candidatas if c.origen.ticker == "TLCWO"}

    assert "TLCMO" in destinos_motor, (
        "el dato versionado dejó de traer TLCWO→TLCMO: revisar la aceptación de respaldo"
    )
    assert "TLCMO" in destinos_backend


# --- El subconjunto común: mismo tipo, mismos deltas, mismas flags -------------------------------


def test_el_subconjunto_comun_coincide_en_tipo_flags_y_deltas(
    datos_del_motor, resultado_del_backend
) -> None:
    _universo, oportunidades, _alertas = datos_del_motor
    candidatas, _alertas_backend = resultado_del_backend

    del_motor = _por_clave_motor(oportunidades)
    del_backend = _por_clave_backend(candidatas)
    comunes = set(del_motor) & set(del_backend)

    print(
        f"\n{len(oportunidades)} candidatas del motor, {len(candidatas)} del backend, "
        f"{len(comunes)} en común"
    )
    assert comunes, "no hay ningún par (origen, destino, tipo) en común entre las dos corridas"

    diferencias = []
    for clave in comunes:
        o, c = del_motor[clave], del_backend[clave]
        if abs(c.d_rend_pp - o["d_rend_pp"]) > TOLERANCIA_PP:
            diferencias.append((clave, "d_rend_pp", c.d_rend_pp, o["d_rend_pp"]))
        if (o["d_duration"] is None) != (c.d_duracion is None):
            diferencias.append((clave, "d_duration (presencia)", c.d_duracion, o["d_duration"]))
        elif o["d_duration"] is not None and abs(c.d_duracion - o["d_duration"]) > TOLERANCIA_PP:
            diferencias.append((clave, "d_duration", c.d_duracion, o["d_duration"]))
        if c.mismo_emisor != o["mismo_emisor"]:
            diferencias.append((clave, "mismo_emisor", c.mismo_emisor, o["mismo_emisor"]))
        if c.pasa_a_cable != o["pasa_a_cable"]:
            diferencias.append((clave, "pasa_a_cable", c.pasa_a_cable, o["pasa_a_cable"]))
        if c.mejora_ley != o["mejora_ley"]:
            diferencias.append((clave, "mejora_ley", c.mejora_ley, o["mejora_ley"]))
        if c.empeora_ley != o["empeora_ley"]:
            diferencias.append((clave, "empeora_ley", c.empeora_ley, o["empeora_ley"]))

    assert diferencias == []
