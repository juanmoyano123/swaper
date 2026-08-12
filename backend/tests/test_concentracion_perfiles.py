"""Los perfiles, y sobre todo si `min_sectores` es alcanzable — F-020.

`min_sectores` es el único campo del perfil que **no** viene del motor: lo agrega F-020 porque su
ficha pide advertir cuando la cartera queda por debajo del mínimo del perfil. Un tope máximo se
puede fijar por criterio y listo —nadie deja de poder armar una cartera por un techo—, pero un
**mínimo** puede volverse imposible sin que nadie se entere: alcanza con que el dato curado de
sector se achique. El día que pase, el perfil conservador va a advertir sobre todas las carteras
por una razón que no es la cartera, y el asesor va a aprender a ignorar la advertencia.

Por eso este test mira el universo real y no una muestra: cuenta cuántos sectores tienen con qué
armarse, y falla declarando el número si no alcanzan.

## Qué cuenta como "sector alcanzable"

Un sector **computable** —informado y no exento, que es lo que puede llegar a tocar el tope
sectorial— con al menos **dos emisores operables**. Los dos requisitos son deliberados:

- **Dos emisores y no uno**, porque un sector con un solo emisor no permite diversificar adentro:
  llenarlo obliga a concentrar ese crédito, y entonces cumplir el mínimo sectorial rompería el tope
  por emisor. Un mínimo que sólo se puede cumplir violando otro tope no es alcanzable.
- **Operable = con precio publicado.** No se puede comprar lo que no cotiza. Es el único filtro que
  se aplica: exigir además liquidez mínima metería `percentil_liquidez` acá y haría que este test
  midiera dos cosas a la vez.

La cuenta es **conservadora a propósito**: Soberano y Subsoberano sí cuentan como sectores presentes
para el mínimo (la exención es del tope sectorial, no de la existencia), así que el universo real
tiene dos sectores más de los que este test cuenta. Si pasa con la cuenta estricta, pasa.
"""

from pathlib import Path

import pandas as pd
import pytest

from app.concentracion.perfiles import (
    NOMBRES_DE_PERFIL,
    PERFILES,
    SECTORES_EXENTOS,
    sector_computable,
)
from app.concentracion.riesgo import grupo_emisor

RAIZ_REPO = Path(__file__).resolve().parents[2]
CONSOLIDADO = RAIZ_REPO / "data" / "output" / "universo_consolidado.xlsx"

MIN_EMISORES_POR_SECTOR = 2


@pytest.fixture(scope="module")
def sectores_alcanzables() -> dict[str, int]:
    """Sectores computables del universo real, con cuántos emisores operables tiene cada uno."""
    if not CONSOLIDADO.exists():
        pytest.skip("no está data/output/universo_consolidado.xlsx")

    universo = pd.read_excel(CONSOLIDADO, sheet_name="Resumen")
    operables = universo[universo["lastPrice"].notna() & (universo["lastPrice"] > 0)]

    emisores: dict[str, set[str]] = {}
    for fila in operables.itertuples():
        sector = sector_computable(fila.sector if isinstance(fila.sector, str) else None)
        if sector is not None:
            emisores.setdefault(sector, set()).add(grupo_emisor(str(fila.ticker)))

    return {
        sector: len(grupos)
        for sector, grupos in emisores.items()
        if len(grupos) >= MIN_EMISORES_POR_SECTOR
    }


def test_cada_perfil_pide_un_minimo_que_el_universo_puede_cumplir(
    sectores_alcanzables: dict[str, int],
) -> None:
    disponibles = len(sectores_alcanzables)
    print(
        f"\nsectores computables con >= {MIN_EMISORES_POR_SECTOR} emisores operables: "
        f"{disponibles} ({', '.join(sorted(sectores_alcanzables))})"
    )

    for nombre, perfil in PERFILES.items():
        assert perfil["min_sectores"] <= disponibles, (
            f"el perfil {nombre} pide {perfil['min_sectores']} sectores y el universo sólo tiene "
            f"{disponibles} con al menos {MIN_EMISORES_POR_SECTOR} emisores operables "
            f"({', '.join(sorted(sectores_alcanzables))}): el mínimo dejó de ser alcanzable y "
            "advertiría sobre toda cartera por una razón que no es la cartera."
        )


def test_los_minimos_salen_de_los_gwt_del_plan_y_no_de_una_preferencia() -> None:
    """Moderado ≥ 3 lo fija el GWT-5 de F-020 ('sólo 2 sectores en perfil moderado → advierte') y
    conservador = 4 lo fija el GWT de F-019 que nombra un perfil con `min_sectores` = 4."""
    assert PERFILES["conservador"]["min_sectores"] == 4
    assert PERFILES["moderado"]["min_sectores"] == 3
    assert PERFILES["agresivo"]["min_sectores"] == 2


def test_el_perfil_se_endurece_de_agresivo_a_conservador_en_los_cinco_ejes() -> None:
    """Un perfil no es una lista de números sueltos: si un eje se aflojara al revés que los demás,
    'conservador' dejaría de significar lo mismo en cada pantalla que lo mire."""
    conservador, moderado, agresivo = (PERFILES[n] for n in ("conservador", "moderado", "agresivo"))

    for tope in ("tope_rend_usd", "max_emisor", "max_soberano", "max_sector"):
        assert conservador[tope] < moderado[tope] < agresivo[tope], tope
    # Estos dos van al revés: más exigentes cuanto más conservador.
    liquidez = [p["percentil_liquidez"] for p in (conservador, moderado, agresivo)]
    assert liquidez[0] > liquidez[1] > liquidez[2]
    assert conservador["min_sectores"] > moderado["min_sectores"] > agresivo["min_sectores"]


def test_estan_los_cinco_campos_del_motor_mas_el_que_agrega_esta_feature() -> None:
    """`tope_rend_usd` y `percentil_liquidez` no los usa F-020 y están igual: F-019 los lee de acá,
    y partir el perfil en dos archivos permitiría que 'moderado' signifique dos cosas distintas."""
    esperados = {
        "tope_rend_usd",
        "percentil_liquidez",
        "max_emisor",
        "max_soberano",
        "max_sector",
        "min_sectores",
    }
    for nombre in NOMBRES_DE_PERFIL:
        assert set(PERFILES[nombre]) == esperados, nombre


def test_los_perfiles_coinciden_con_los_del_motor_en_los_cinco_campos_portados() -> None:
    """El port contra `tools/armar_cartera.py`: los números tienen que ser los mismos.

    El motor no se importa —el backend nunca importa de `tools/`—: se leen sus constantes con el
    mismo mecanismo que usa `test_concentracion_paridad_motor`, y la comparación es campo por campo
    sobre los cinco que existen en los dos lados.
    """
    import sys

    sys.path.insert(0, str(RAIZ_REPO / "tools"))
    import armar_cartera as motor

    assert set(motor.PERFILES) == set(PERFILES)
    for nombre, del_motor in motor.PERFILES.items():
        for campo, valor in del_motor.items():
            assert PERFILES[nombre][campo] == valor, f"{nombre}.{campo}"
    assert set(motor.SECTORES_EXENTOS) == SECTORES_EXENTOS


def test_el_sector_computable_excluye_lo_exento_y_lo_que_falta() -> None:
    assert sector_computable("O&G") == "O&G"
    assert sector_computable("Soberano") is None
    assert sector_computable("Subsoberano") is None
    assert sector_computable(None) is None
