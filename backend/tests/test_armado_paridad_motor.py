"""El port contra su original: `app/armado/` y `tools/armar_cartera.py::armar()` deben coincidir.

El backend no importa de `tools/`, así que el algoritmo de selección está copiado. Es el mismo
arreglo que `test_concentracion_paridad_motor.py` y `test_calendario_paridad_motor.py`: una copia
sin un test que la compare no es un port, es una segunda implementación que va a divergir sin que
nadie se entere.

## Qué compara exactamente, y qué no

Compara el **algoritmo de selección** (`candidatos_del_segmento`, `elegir_siguiente`, `armar`),
no las capas de arriba (segmentación, saneamiento, deduplicación por emisión, tipo de cambio): esas
ya tienen su propio test de paridad (`test_universo_paridad_motor.py`,
`test_universo_emisiones_paridad.py`) y volver a probarlas acá sólo escondería, detrás de una
divergencia ya conocida y ya cubierta, la pregunta que este archivo existe para contestar.

Por eso el universo que reciben los dos lados **es el mismo objeto de datos**: se arma una sola vez
con `tools/segmentos.py::cargar_universo(dedup=True)` — la carga real del motor, con su propio tipo
de cambio y su propio desempate de representante — y se lo traduce a `EspecieUniverso`/
`RiesgoDeEspecie` fila por fila, sin volver a derivar nada. Cualquier diferencia que aparezca a
partir de acá es del algoritmo de selección, que es lo que se está portando.

**Por qué no se arma el universo por el camino real del backend** (`segmentar` + `sanear` +
`saneado.emisiones().colapsado()`, que es lo que hace `app/api/v1/armado.py`): se probó primero así
y aparecían divergencias de candidatos que no eran de `armar()` sino de dos capas de abajo:

1. `data/output/universo_consolidado.xlsx` es un snapshot **anterior a F-012**: no tiene la columna
   `moneda_cotizacion`/`denominationCcy`. Sin ella `derivar_tipo_de_cambio` no encuentra un solo par
   y `volumen_usd` queda `None` para todo el universo del lado del backend, mientras que el motor
   —que deriva la moneda del sufijo del ticker y no de esa columna— sí arma la suya. El filtro de
   liquidez de `candidatos_del_segmento` quedaba neutralizado sólo de un lado, no por un bug del
   port sino porque el fixture no tiene el dato que ese cálculo necesita.
2. El representante que elige `deduplicar_emisiones` (el motor, por volumen nominal) y el que elige
   `app/universo/emisiones.py` (el backend, por completitud de datos y sanidad) no siempre
   coinciden — es la divergencia que prueba `test_universo_emisiones_paridad.py`. Sobre este
   consolidado en particular alcanza a mover 5-8 tickers de frontera en algunos segmentos, lo
   bastante para desplazar cuál cae justo en la posición n_objetivo de la cartera.

Las dos son reales y las dos están ya declaradas y cubiertas en otro archivo. Construir el universo
una sola vez a partir de la carga del motor las neutraliza de raíz en vez de perseguirlas acá.

## El desempate por calendario se neutraliza de los dos lados

El backend no lo implementa (ver el docstring de `app/armado/motor.py`), así que al motor se le
pasa `pago_mensual=False` para que tampoco lo aplique: sin esto, cualquier diferencia de desempate
dentro de la banda de rendimiento se leería como un bug de paridad cuando en realidad es la
simplificación ya declarada.

## El desempate por sector SÍ puede mover un ticket puntual, y es a propósito

El alcance ampliado de F-019 (08/2026) le agrega a `elegir_siguiente` una preferencia por sector no
representado que el motor no tiene. Sobre 15 escenarios con muchos candidatos dentro de la banda de
rendimiento, es posible que puntualmente el backend y el motor difieran en **una o dos posiciones**
de un segmento grande — no porque el port esté mal, sino porque el criterio de selección cambió
deliberadamente (GWT-4/GWT-5 de la ficha). El test lo tolera hasta `MAX_DIFERENCIAS_POR_DESEMPATE`
tickers de diferencia por escenario, y lo declara cuando pasa: una diferencia de 1-2 tickers en un
segmento de 15-40 candidatos con el mismo peso total es la firma del desempate sectorial, no de un
bug — un bug se ve como una cartera completamente distinta, no como un ticket cambiado dentro de la
misma banda de rendimiento.
"""

import math
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from app.armado.constantes import MIX_COBERTURA
from app.armado.motor import armar as armar_backend
from app.armado.motor import filtrar_por_moneda, percentil_lineal
from app.armado.parametros import ParametrosArmado
from app.concentracion.perfiles import PERFILES
from app.concentracion.riesgo import RiesgoDeEspecie
from app.universo.segmentacion import EspecieUniverso

RAIZ_REPO = Path(__file__).resolve().parents[2]
CONSOLIDADO = RAIZ_REPO / "data" / "output" / "universo_consolidado.xlsx"

TOLERANCIA_PESO = 0.05  # puntos porcentuales
MAX_DIFERENCIAS_POR_DESEMPATE = 2  # ver el docstring del módulo


def _motor() -> Any:
    sys.path.insert(0, str(RAIZ_REPO / "tools"))
    import armar_cartera

    return armar_cartera


class _ParamsMotor:
    """Un `argparse.Namespace` a mano: sólo los atributos que `armar()` del motor lee."""

    def __init__(self, *, monto: float, n_total: int = 15, horizonte: str = "medio") -> None:
        self.monto = monto
        self.n_total = n_total
        self.horizonte = horizonte
        self.min_rend = 0.0
        # Neutraliza el desempate por calendario de los dos lados: ver el docstring del módulo.
        self.pago_mensual = False
        self._flujos = None
        self._hoy = None


def _o(valor: object) -> Any:
    """Un valor de la fila del motor, o `None` si es `NaN`/`NaT`. Mismo criterio que
    `segmentacion.a_numero`/`_texto`, sin reimportar el módulo entero para una fila a mano."""
    if valor is None:
        return None
    if isinstance(valor, float) and math.isnan(valor):
        return None
    return valor


@pytest.fixture(scope="module")
def universo() -> tuple[list[EspecieUniverso], dict[str, RiesgoDeEspecie]]:
    """El universo real que carga el motor (`dedup=True`), traducido a los tipos del backend sin
    volver a derivar nada — ver el docstring del módulo para el porqué."""
    motor = _motor()
    if not CONSOLIDADO.exists():
        pytest.skip("no está data/output/universo_consolidado.xlsx")
    df = motor.segmentos.cargar_universo([], dedup=True, alerta_sin_segmento=False)

    especies: list[EspecieUniverso] = []
    riesgos: dict[str, RiesgoDeEspecie] = {}
    for fila in df.to_dict("records"):
        ticker = str(fila["ticker"])
        vencimiento = _o(fila.get("maturity"))
        especies.append(
            EspecieUniverso(
                ticker=ticker,
                raiz=ticker,
                clase_activo=str(fila["clase_activo"]),
                segmento=str(fila["segmento"]),
                rendimiento=_o(fila.get("rendimiento")),
                duracion=_o(fila.get("duration")),
                vencimiento=(
                    vencimiento.date() if isinstance(vencimiento, pd.Timestamp) else vencimiento
                ),
                ley=_o(fila.get("law")),
                moneda_cupon=_o(fila.get("couponCurrency")),
                emisor=_o(fila.get("emisor")),
                precio=_o(fila.get("lastPrice")),
                volumen=_o(fila.get("effectiveVolume")),
                moneda_cotizacion=_o(fila.get("moneda_cotizacion")),
                volumen_usd=_o(fila.get("volumen_usd")),
                lamina=_o(fila.get("lamina")),
                sector=_o(fila.get("sector")),
            )
        )
        nombre = fila["emisor"] if _o(fila.get("emisor")) is not None else fila["grupo_emisor"]
        riesgos[ticker] = RiesgoDeEspecie(
            ticker=ticker,
            grupo_emisor=str(fila["grupo_emisor"]),
            es_soberano=bool(fila["es_soberano"]),
            clave_riesgo=str(fila["clave_riesgo"]),
            nombre=str(nombre),
        )
    return especies, riesgos


@pytest.fixture(scope="module")
def universo_del_motor() -> pd.DataFrame:
    motor = _motor()
    if not CONSOLIDADO.exists():
        pytest.skip("no está data/output/universo_consolidado.xlsx")
    return motor.segmentos.cargar_universo([], dedup=True, alerta_sin_segmento=False)


# --- Los 15 escenarios ------------------------------------------------------------------------

ESCENARIOS: list[dict[str, Any]] = [
    dict(
        nombre="conservador/medio/mixta/todas",
        perfil="conservador",
        horizonte="medio",
        cobertura="mixta",
        moneda="todas",
    ),
    dict(
        nombre="moderado/medio/mixta/todas (default)",
        perfil="moderado",
        horizonte="medio",
        cobertura="mixta",
        moneda="todas",
    ),
    dict(
        nombre="agresivo/medio/mixta/todas",
        perfil="agresivo",
        horizonte="medio",
        cobertura="mixta",
        moneda="todas",
    ),
    dict(
        nombre="moderado/corto/mixta/todas",
        perfil="moderado",
        horizonte="corto",
        cobertura="mixta",
        moneda="todas",
    ),
    dict(
        nombre="moderado/largo/mixta/todas",
        perfil="moderado",
        horizonte="largo",
        cobertura="mixta",
        moneda="todas",
    ),
    dict(
        nombre="moderado/medio/devaluacion/todas",
        perfil="moderado",
        horizonte="medio",
        cobertura="devaluacion",
        moneda="todas",
    ),
    dict(
        nombre="moderado/medio/inflacion/todas",
        perfil="moderado",
        horizonte="medio",
        cobertura="inflacion",
        moneda="todas",
    ),
    dict(
        nombre="moderado/medio/tasa-pesos/todas",
        perfil="moderado",
        horizonte="medio",
        cobertura="tasa-pesos",
        moneda="todas",
    ),
    dict(
        nombre="moderado/medio/mix-manual-usd-cer/todas",
        perfil="moderado",
        horizonte="medio",
        mix={"usd_hard": 60, "cer": 40},
        moneda="todas",
    ),
    dict(
        nombre="moderado/medio/mixta/usd",
        perfil="moderado",
        horizonte="medio",
        cobertura="mixta",
        moneda="usd",
    ),
    dict(
        nombre="moderado/medio/mixta/ars",
        perfil="moderado",
        horizonte="medio",
        cobertura="mixta",
        moneda="ars",
    ),
    dict(
        nombre="conservador/largo/devaluacion/usd",
        perfil="conservador",
        horizonte="largo",
        cobertura="devaluacion",
        moneda="usd",
    ),
    dict(
        nombre="agresivo/corto/tasa-pesos/ars",
        perfil="agresivo",
        horizonte="corto",
        cobertura="tasa-pesos",
        moneda="ars",
    ),
    dict(
        nombre="moderado/medio/mixta/todas/n_total=40",
        perfil="moderado",
        horizonte="medio",
        cobertura="mixta",
        moneda="todas",
        n_total=40,
    ),
    dict(
        nombre="conservador/medio/mix-manual-cer-tasafija-badlar/ars",
        perfil="conservador",
        horizonte="medio",
        mix={"cer": 30, "tasa_fija": 40, "badlar": 30},
        moneda="ars",
    ),
]

assert len(ESCENARIOS) == 15


# --- El percentil, aislado del resto -------------------------------------------------------


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 10, 25, 50, 99, 100])
@pytest.mark.parametrize("q", [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0])
def test_percentil_lineal_coincide_con_pandas(n: int, q: float) -> None:
    """`pandas.Series.quantile(q)` con interpolación lineal es el método por defecto, el mismo que
    usa `tools/armar_cartera.py` para el piso de liquidez. Sin esto, un piso distinto filtraría un
    conjunto de candidatos distinto y ningún test de paridad más arriba probaría lo mismo dos veces
    con la misma semilla."""
    import random

    rng = random.Random(1000 + n)
    valores = [rng.uniform(0, 1_000_000) for _ in range(n)]
    esperado = pd.Series(valores).quantile(q)
    assert math.isclose(percentil_lineal(valores, q), esperado, abs_tol=1e-9)


def _mix_resuelto(escenario: dict[str, Any]) -> dict[str, float]:
    """El mix ya resuelto (cobertura o manual), sin el filtro de moneda: se le aplica igual a los
    dos lados con la misma función (`filtrar_por_moneda` del backend), para no comparar dos
    implementaciones de un parseo que no es lo que este test mide."""
    if "mix" in escenario:
        return dict(escenario["mix"])
    return dict(MIX_COBERTURA[escenario["cobertura"]])


@pytest.mark.parametrize("escenario", ESCENARIOS, ids=[e["nombre"] for e in ESCENARIOS])
def test_el_backend_arma_la_misma_cartera_que_el_motor(
    universo: tuple[list[EspecieUniverso], dict[str, RiesgoDeEspecie]],
    universo_del_motor: pd.DataFrame,
    escenario: dict[str, Any],
) -> None:
    especies, riesgos = universo
    motor = _motor()

    monto = 100_000.0
    n_total = escenario.get("n_total", 15)
    mix, _ = filtrar_por_moneda(_mix_resuelto(escenario), escenario["moneda"])

    params_backend = ParametrosArmado(
        monto=monto,
        moneda=escenario["moneda"],
        horizonte=escenario["horizonte"],
        perfil=escenario["perfil"],
        n_total=n_total,
    )
    resultado = armar_backend(
        especies, mix, PERFILES[escenario["perfil"]], escenario["perfil"], params_backend, riesgos
    )
    del_backend = {p.ticker: p.pct_cartera for p in resultado.posiciones}

    params_motor = _ParamsMotor(monto=monto, n_total=n_total, horizonte=escenario["horizonte"])
    cartera_motor = motor.armar(
        universo_del_motor, dict(mix), motor.PERFILES[escenario["perfil"]], params_motor, []
    )
    del_motor = dict(zip(cartera_motor["ticker"], cartera_motor["pct_cartera"], strict=True))

    diferencias = set(del_backend) ^ set(del_motor)
    assert len(diferencias) <= MAX_DIFERENCIAS_POR_DESEMPATE, (
        f"{escenario['nombre']}: {len(diferencias)} tickers de diferencia (tolerancia "
        f"{MAX_DIFERENCIAS_POR_DESEMPATE} por el desempate sectorial de GWT-4/GWT-5).\n"
        f"sólo backend: {sorted(set(del_backend) - set(del_motor))}\n"
        f"sólo motor: {sorted(set(del_motor) - set(del_backend))}"
    )
    if diferencias:
        print(
            f"\n{escenario['nombre']}: {len(diferencias)} tickers distintos por desempate "
            f"sectorial: {sorted(diferencias)}"
        )

    comunes = set(del_backend) & set(del_motor)
    for ticker in comunes:
        assert abs(del_backend[ticker] - del_motor[ticker]) <= TOLERANCIA_PESO, (
            f"{escenario['nombre']}: {ticker} pesa {del_backend[ticker]:.4f}% en el backend y "
            f"{del_motor[ticker]:.4f}% en el motor"
        )
    # Aun con tickers distintos, el peso total tiene que coincidir: la reponderación final no
    # depende de qué ticket puntual haya entrado, sólo de cuántos entraron por segmento.
    assert abs(sum(del_backend.values()) - sum(del_motor.values())) <= TOLERANCIA_PESO, (
        f"{escenario['nombre']}: la cartera del backend suma {sum(del_backend.values()):.2f}% y "
        f"la del motor {sum(del_motor.values()):.2f}%"
    )
