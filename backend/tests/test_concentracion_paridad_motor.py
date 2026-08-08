"""El port contra su original: `app/concentracion/` y `tools/armar_cartera.py` tienen que coincidir.

El backend no importa de `tools/`, así que los topes están copiados. Una copia sin un test que la
compare no es un port: es una segunda implementación que va a divergir sin que nadie se entere, y el
día que diverja el motor y el producto van a estar advirtiendo cosas distintas sobre la misma
cartera. Es el mismo arreglo de `test_universo_paridad_motor` y `test_calendario_paridad_motor`.

Se compara sobre el consolidado versionado —el mismo universo, con los mismos emisores y los mismos
prefijos— y sobre carteras generadas con una semilla fija: una sola cartera de ejemplo probaría que
los dos coinciden en un caso, no que aplican el mismo criterio.

## La divergencia deliberada: el sector no se propaga

`tools/segmentos.py:370-381` rellena el sector faltante con la **moda del sector dentro del grupo de
emisor**: si un ticker del grupo tiene sector, le pone ése a los demás. El backend no lo hace, y no
es un olvido del port:

- F-017 ya lo decidió al revés. El docstring de `EspecieUniverso.sector` dice que a un sector no
  informado "no se le asigna uno por parecido con otro emisor".
- La ficha de F-020 lo repite para la distribución: *"Las posiciones sin sector figuran como 'sector
  no informado', nunca repartidas entre los conocidos"*.
- Es la regla 11 del dominio. El grupo de emisor es un prefijo de tres letras, no una prueba de que
  dos emisiones sean del mismo emisor; propagar un sector por ahí es completar el hueco entre lo que
  la fuente dice y lo que necesitamos que diga.

**Cómo se neutraliza acá**: al motor se le pasa una cartera cuya columna `sector` ya es la del
backend —sin propagar—, así los dos miran exactamente el mismo dato y lo único que se compara es el
criterio de los topes. La propagación en sí queda cubierta por el test que la mide de frente
(`test_el_motor_propaga_sector_y_el_backend_no`), que existe para que la divergencia se vea en un
número y no sólo en un comentario.

Se neutraliza además la **grafía del nombre del emisor**: el motor elige la moda del `underlying`
dentro del grupo y el backend la primera en orden de ticker. Es presentación pura —el nombre no
entra en ningún cálculo— y `test_los_dos_identifican_a_los_mismos_grupos` cubre lo único que sí
importa de eso: que los dos sepan el nombre de los mismos grupos.

Es el mismo criterio con el que `test_universo_paridad_motor` declara su desvío de `NaN`.
"""

import random
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from app.concentracion.perfiles import PERFILES
from app.concentracion.riesgo import derivar_riesgo
from app.concentracion.servicio import Posicion, TipoDeTope, evaluar_concentracion
from app.universo.segmentacion import segmentar

RAIZ_REPO = Path(__file__).resolve().parents[2]
CONSOLIDADO = RAIZ_REPO / "data" / "output" / "universo_consolidado.xlsx"

# Semilla fija: las carteras tienen que ser las mismas en cada corrida. Un test de paridad que
# fallara una vez de cada diez sería peor que no tenerlo.
SEMILLA = 20260808
CARTERAS = 60
MAX_POSICIONES = 12


def _motor() -> Any:
    """`tools/armar_cartera.py`, corrido tal cual está y sin tocarle una línea."""
    sys.path.insert(0, str(RAIZ_REPO / "tools"))
    import armar_cartera

    return armar_cartera


@pytest.fixture(scope="module")
def consolidado() -> pd.DataFrame:
    if not CONSOLIDADO.exists():
        pytest.skip("no está data/output/universo_consolidado.xlsx")
    return pd.read_excel(CONSOLIDADO, sheet_name="Resumen")


@pytest.fixture(scope="module")
def universo_del_motor(consolidado: pd.DataFrame) -> pd.DataFrame:
    """El universo con las columnas de riesgo que deriva el motor, sin deduplicar.

    `dedup=False` porque la concentración se mide sobre la vista **viva**: el asesor tiene RUCED o
    RUCEO, no "la emisión RUCE", y las dos concentran el mismo crédito.
    """
    motor = _motor()
    return motor.segmentos.cargar_universo([], dedup=False, alerta_sin_segmento=False)


@pytest.fixture(scope="module")
def especies_del_backend(consolidado: pd.DataFrame):
    return segmentar(consolidado.to_dict("records")).especies


@pytest.fixture(scope="module")
def riesgos_del_backend(especies_del_backend):
    return derivar_riesgo(especies_del_backend)


@pytest.fixture(scope="module")
def comunes(universo_del_motor: pd.DataFrame, riesgos_del_backend) -> list[str]:
    """Los tickers que los dos evalúan. La segmentación ya tiene su propio test de paridad."""
    del_motor = set(universo_del_motor["ticker"].astype(str))
    return sorted(del_motor & set(riesgos_del_backend))


# --- La derivación: de qué crédito es cada especie -----------------------------------------------


def test_los_dos_agrupan_cada_especie_bajo_la_misma_clave_de_riesgo(
    universo_del_motor: pd.DataFrame, riesgos_del_backend, comunes: list[str]
) -> None:
    del_motor = universo_del_motor.set_index("ticker")
    distintos = [
        t
        for t in comunes
        if del_motor.loc[t, "clave_riesgo"] != riesgos_del_backend[t].clave_riesgo
    ]

    print(
        f"\nclave de riesgo coincidente en "
        f"{len(comunes) - len(distintos)}/{len(comunes)} especies"
    )
    assert distintos == []


def test_los_dos_reconocen_al_mismo_riesgo_soberano(
    universo_del_motor: pd.DataFrame, riesgos_del_backend, comunes: list[str]
) -> None:
    """Regla 4 del dominio: la separación del soberano es la que hacía que una cartera 100 %
    soberana pasara como diversificada, así que es la que menos puede divergir."""
    del_motor = universo_del_motor.set_index("ticker")
    soberanos_motor = {t for t in comunes if bool(del_motor.loc[t, "es_soberano"])}
    soberanos_backend = {t for t in comunes if riesgos_del_backend[t].es_soberano}

    assert soberanos_motor == soberanos_backend
    assert len(soberanos_motor) > 0


def test_los_dos_identifican_a_los_mismos_grupos(
    universo_del_motor: pd.DataFrame, riesgos_del_backend, comunes: list[str]
) -> None:
    """Qué grupos tienen nombre y cuáles quedan como `(sin identificar: XXX)`.

    La **grafía** puede diferir —el motor toma la moda del grupo, el backend la primera en orden de
    ticker— y eso no se compara: el nombre no entra en ningún cálculo. Lo que sí tiene que coincidir
    es el conjunto, porque un grupo que uno identifica y el otro no significaría que uno de los dos
    perdió el `underlying`.
    """
    del_motor = universo_del_motor.set_index("ticker")
    sin_nombre_motor = {t for t in comunes if not bool(del_motor.loc[t, "emisor_identificado"])}
    sin_nombre_backend = {
        t for t in comunes if riesgos_del_backend[t].nombre.startswith("(sin identificar:")
    }

    # Los soberanos quedan afuera de la comparación: el backend les pone el texto largo del riesgo
    # país y el motor conserva el `underlying` de cada bono, que es otra pregunta.
    soberanos = {t for t in comunes if riesgos_del_backend[t].es_soberano}
    assert sin_nombre_motor - soberanos == sin_nombre_backend - soberanos


def test_el_motor_propaga_sector_y_el_backend_no(
    universo_del_motor: pd.DataFrame, especies_del_backend, comunes: list[str]
) -> None:
    """La única divergencia deliberada, medida de frente. Ver el docstring del módulo.

    El motor le asigna sector a especies que la fuente no informó, tomando el de otra emisión con el
    mismo prefijo de ticker. El backend las deja vacías y las muestra como "sector no informado".
    """
    del_motor = universo_del_motor.set_index("ticker")
    del_backend = {e.ticker: e.sector for e in especies_del_backend}

    propagados = [
        t
        for t in comunes
        if del_backend[t] is None and isinstance(del_motor.loc[t, "sector"], str)
    ]
    contradichos = [
        t
        for t in comunes
        if del_backend[t] is not None and del_motor.loc[t, "sector"] != del_backend[t]
    ]

    print(f"\nsector propagado por el motor y no por el backend: {len(propagados)} especies")
    # La divergencia es sólo por relleno: donde los dos tienen dato, el dato es el mismo.
    assert contradichos == []
    assert len(propagados) > 0, (
        "el motor dejó de propagar sector: si eso pasó a propósito, esta divergencia ya no existe "
        "y hay que sacar la neutralización de este archivo"
    )


# --- Los topes: el mismo veredicto sobre la misma cartera ----------------------------------------


def _carteras(comunes: list[str]) -> list[dict[str, float]]:
    """Carteras pseudoaleatorias sobre el universo real, con semilla fija.

    Los pesos no se normalizan a 100 en ninguno de los dos lados: el motor mide `pct_cartera` tal
    como salió de la reponderación y el backend mide lo que declara el armador. Que este generador
    tampoco normalice es lo que mantiene la comparación honesta.
    """
    rng = random.Random(SEMILLA)
    carteras = []
    for _ in range(CARTERAS):
        tickers = rng.sample(comunes, rng.randint(2, MAX_POSICIONES))
        carteras.append({t: round(rng.uniform(1, 45), 2) for t in tickers})
    return carteras


def _alertas_del_motor(
    motor: Any,
    universo: pd.DataFrame,
    pesos: dict[str, float],
    riesgos,
    sectores: dict[str, str | None],
    perfil: dict[str, Any],
) -> list[str]:
    """`verificar_concentracion` sobre la misma cartera, con las dos neutralizaciones aplicadas.

    El `sector` y el `emisor` que se le pasan son los del backend: el primero para que la
    propagación no ensucie la comparación de los topes, el segundo porque la grafía del nombre es
    presentación y no criterio. Todo lo demás —cómo agrupa, contra qué tope compara, con qué
    tolerancia— es del motor, sin tocar.
    """
    filas = universo[universo["ticker"].isin(pesos)].copy()
    filas["pct_cartera"] = filas["ticker"].map(pesos)
    filas["sector"] = filas["ticker"].map(sectores)
    filas["emisor"] = filas["ticker"].map(lambda t: riesgos[t].nombre)

    alertas: list[str] = []
    motor.verificar_concentracion(filas, perfil, alertas)
    return alertas


@pytest.mark.parametrize("nombre_perfil", sorted(PERFILES))
def test_los_dos_advierten_los_mismos_topes_sobre_las_mismas_carteras(
    universo_del_motor: pd.DataFrame,
    especies_del_backend,
    riesgos_del_backend,
    comunes: list[str],
    nombre_perfil: str,
) -> None:
    motor = _motor()
    sectores = {e.ticker: e.sector for e in especies_del_backend}
    perfil_motor = motor.PERFILES[nombre_perfil]

    revisadas = 0
    con_exceso = 0
    for pesos in _carteras(comunes):
        del_motor = _alertas_del_motor(
            motor, universo_del_motor, pesos, riesgos_del_backend, sectores, perfil_motor
        )
        del_backend = evaluar_concentracion(
            [Posicion(t, p) for t, p in pesos.items()], especies_del_backend, nombre_perfil
        )

        assert len(del_motor) == len(del_backend.excedidos), (
            f"{nombre_perfil}: el motor advirtió {len(del_motor)} topes y el backend "
            f"{len(del_backend.excedidos)} sobre la cartera {sorted(pesos)}"
        )
        # Y no sólo la misma cantidad: el mismo excedido, con el mismo peso al décimo de punto.
        for tope in del_backend.excedidos:
            que = tope.nombre if tope.tipo is not TipoDeTope.SECTOR else tope.clave
            assert any(que in a and f"{tope.peso:.1f}%" in a for a in del_motor), (
                f"{nombre_perfil}: el backend advirtió {que} en {tope.peso:.1f}% y el motor no. "
                f"Alertas del motor: {del_motor}"
            )
        revisadas += 1
        con_exceso += len(del_backend.excedidos)

    print(f"\n{nombre_perfil}: {revisadas} carteras comparadas, {con_exceso} topes excedidos")
    assert con_exceso > 0, "ninguna cartera rompió un tope: la comparación no probó nada"
