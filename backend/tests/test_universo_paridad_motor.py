"""El port contra su original: el backend y `tools/segmentos.py` tienen que dar el mismo veredicto.

El backend no importa de `tools/`, así que la sanidad está copiada. Una copia sin un test que la
compare no es un port: es una segunda implementación que va a divergir sin que nadie se entere, y el
día que diverja el motor y el producto van a estar descartando instrumentos distintos del mismo
universo.

Se comparan sobre el consolidado histórico y no sobre la base porque ahí están los casos rotos de
verdad —MR43D al 9.298.976 % contra su hermana MR43O al 25 %, CRCJO al 218.605 % en dólares— que la
base de hoy todavía no tiene. Un test de paridad sobre un universo sin nada roto sólo probaría que
los dos coinciden en no hacer nada.

Este test es también el que encontró la única diferencia real que tuvo el port: pandas escribe `NaN`
donde no hay dato, `NaN <= tope` es `False`, y la condición escrita como negación convertía 366
faltantes en descartes. El motor no tenía el problema porque pandas filtra los `NaN` antes de
comparar. Ver `numero` en `segmentacion.py`.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

from app.universo.sanidad import MotivoDescarte, evaluar_sanidad
from app.universo.segmentacion import segmentar

RAIZ_REPO = Path(__file__).resolve().parents[2]
CONSOLIDADO = RAIZ_REPO / "data" / "output" / "universo_consolidado.xlsx"


@pytest.fixture(scope="module")
def universo() -> list[dict]:
    if not CONSOLIDADO.exists():
        pytest.skip("no está data/output/universo_consolidado.xlsx")
    return pd.read_excel(CONSOLIDADO, sheet_name="Resumen").to_dict("records")


def _segmentado_por_el_motor():
    """El universo tal como lo deja `cargar_universo` justo antes de llamar a `marcar_datos_sanos`.

    Se reproducen acá esos tres pasos —sacar la renta variable, asignar segmento, elegir TIR o TNA—
    en vez de llamar a `cargar_universo` porque esa función arrastra además el tipo de cambio
    implícito, que es F-012 y no tiene nada que ver con la sanidad.
    """
    sys.path.insert(0, str(RAIZ_REPO / "tools"))
    import segmentos as motor

    df = pd.read_excel(CONSOLIDADO, sheet_name="Resumen")
    df = df[~df["clase_activo"].isin(motor.CLASES_RENTA_VARIABLE)].copy()
    df["segmento"] = df.apply(motor.asignar_segmento, axis=1)
    return motor, df


@pytest.fixture(scope="module")
def veredicto_del_motor(universo: list[dict]) -> set[str]:
    """Lo que descarta `tools/segmentos.py`, corrido tal cual está y sin tocarle una línea."""
    motor, df = _segmentado_por_el_motor()
    df = df[df["segmento"].notna()].copy()
    df["rendimiento"] = df["tir"]
    tasa_fija = df["segmento"] == "tasa_fija"
    df.loc[tasa_fija, "rendimiento"] = df.loc[tasa_fija, "tna"]

    df = motor.marcar_datos_sanos(df, [])
    return set(df.loc[~df["dato_sano"], "ticker"])


@pytest.fixture(scope="module")
def veredicto_del_backend(universo: list[dict]):
    return evaluar_sanidad(segmentar(universo).especies)


def test_el_backend_descarta_exactamente_lo_mismo_que_el_motor(
    veredicto_del_motor: set[str], veredicto_del_backend
) -> None:
    assert set(veredicto_del_backend.descartados) == veredicto_del_motor


def test_el_backend_evalua_exactamente_el_mismo_universo_que_el_motor(
    universo: list[dict], veredicto_del_backend
) -> None:
    """Que coincidan los descartes no alcanza si uno de los dos mira menos instrumentos: podrían
    coincidir en cero por no haber evaluado a nadie."""
    _, df = _segmentado_por_el_motor()
    assert veredicto_del_backend.evaluados == int(df["segmento"].notna().sum())


def test_las_dos_capas_encuentran_los_casos_reales_que_las_justifican(
    veredicto_del_backend,
) -> None:
    """Los cuatro descartes del consolidado histórico, con nombre y apellido. Si alguno dejara de
    aparecer, la capa correspondiente dejó de andar aunque el total siga dando lo mismo."""
    incoherentes = {
        d.ticker for d in veredicto_del_backend.por_motivo(MotivoDescarte.ESPECIE_INCOHERENTE)
    }
    fuera_de_rango = {
        d.ticker for d in veredicto_del_backend.por_motivo(MotivoDescarte.FUERA_DE_RANGO)
    }
    assert incoherentes == {"MGCED", "MR43D"}
    assert fuera_de_rango == {"CRCJO", "SNSBO"}


def test_un_faltante_del_excel_no_se_lee_como_un_valor_imposible(
    veredicto_del_backend, universo: list[dict]
) -> None:
    """La regresión del `NaN`. El consolidado tiene cientos de especies sin TIR: ninguna puede
    aparecer como descarte, porque no saber un número no es lo mismo que saberlo imposible."""
    assert all(d.rendimiento == d.rendimiento for d in veredicto_del_backend.descartes)
    sin_tir = sum(1 for f in universo if pd.isna(f["tir"]))
    assert sin_tir > 100, "el consolidado dejó de tener faltantes: el test ya no prueba nada"
