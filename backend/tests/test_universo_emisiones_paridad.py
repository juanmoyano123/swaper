"""El port de la deduplicación contra su original en `tools/segmentos.py` — F-011.

El backend no importa de `tools/`, así que `deduplicar_emisiones` está copiada. Una copia sin un
test que la compare no es un port: es una segunda implementación que va a divergir sin que nadie se
entere, y el día que diverja el motor y el producto van a estar armando carteras sobre universos
distintos. Es la misma razón por la que existe `test_universo_paridad_motor.py` para la sanidad.

**Los dos no tienen que coincidir en todo, y eso también se prueba acá.** El motor desempata por
volumen normalizado a dólares, que es F-012 y todavía no existe; el backend desempata por ticker.
Entonces se exige coincidencia exacta en lo que sí está portado —qué grupos son una emisión, cuántas
filas quedan, y que el representante elegido sea igual de sano y de completo— y se mide, sin
exigirla, la coincidencia del representante. Cuando F-012 cierre el hueco, ese último número tiene
que llegar al 100 %: el test lo deja escrito.

Se compara sobre el consolidado histórico y no sobre la base porque el Excel es lo que el motor lee,
y porque ahí hay especies con `duration` cargada — sin duraciones, el chequeo del 5 % no puede
disparar y el test estaría probando que los dos coinciden en no hacer nada.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

from app.universo.emisiones import deduplicar
from app.universo.sanidad import evaluar_sanidad
from app.universo.segmentacion import segmentar

RAIZ_REPO = Path(__file__).resolve().parents[2]
CONSOLIDADO = RAIZ_REPO / "data" / "output" / "universo_consolidado.xlsx"


@pytest.fixture(scope="module")
def universo() -> list[dict]:
    if not CONSOLIDADO.exists():
        pytest.skip("no está data/output/universo_consolidado.xlsx")
    return pd.read_excel(CONSOLIDADO, sheet_name="Resumen").to_dict("records")


@pytest.fixture(scope="module")
def motor():
    sys.path.insert(0, str(RAIZ_REPO / "tools"))
    import segmentos

    return segmentos


@pytest.fixture(scope="module")
def dedup_del_motor(motor, universo: list[dict]) -> pd.DataFrame:
    """El universo tal como lo recibe el armador del motor: colapsado por emisión.

    Se llama a `cargar_universo` entero y no sólo a `deduplicar_emisiones` porque el desempate del
    motor necesita `volumen_usd`, y ése sale del tipo de cambio implícito que esa función calcula.
    Reproducir el camino a mano sería probar mi reproducción, no el motor.
    """
    return motor.cargar_universo([], dedup=True)


@pytest.fixture(scope="module")
def dedup_del_backend(universo: list[dict]):
    especies = segmentar(universo).especies
    return deduplicar(especies, evaluar_sanidad(especies).descartados)


@pytest.fixture(scope="module")
def elegido_por_el_motor(dedup_del_motor) -> dict[str, str]:
    """Qué especie representa a cada emisión según el motor."""
    return dict(zip(dedup_del_motor["raiz_emision"], dedup_del_motor["ticker"], strict=True))


def test_los_dos_agrupan_el_universo_en_las_mismas_emisiones(dedup_del_motor, dedup_del_backend):
    """Si las claves de emisión no coincidieran, todo lo demás sobra: estarían hablando de bonos
    distintos antes de elegir nada."""
    assert set(dedup_del_backend.por_raiz) == set(dedup_del_motor["raiz_emision"])


def test_los_mismos_grupos_quedan_sin_colapsar_por_el_chequeo_de_duracion(
    dedup_del_motor, dedup_del_backend
):
    """El chequeo del 5 % es el criterio que evita fusionar dos bonos que comparten raíz. Es lo
    primero que tiene que coincidir, porque decide qué es una emisión."""
    sin_colapsar_motor = {
        raiz for raiz, grupo in dedup_del_motor.groupby("raiz_emision") if len(grupo) > 1
    }
    sin_colapsar_backend = {e.raiz for e in dedup_del_backend.emisiones if not e.colapsada}
    assert sin_colapsar_backend == sin_colapsar_motor
    assert sin_colapsar_motor, "el consolidado dejó de tener grupos con duraciones dispares"


def test_la_vista_colapsada_tiene_la_misma_cantidad_de_filas(dedup_del_motor, dedup_del_backend):
    """Una fila de más es una posición duplicada en la cartera; una de menos, un bono desaparecido.
    El número tiene que ser el mismo aunque el representante elegido no lo sea."""
    assert len(dedup_del_backend.colapsado()) == len(dedup_del_motor)


def test_el_representante_del_backend_es_igual_de_sano_y_de_completo_que_el_del_motor(
    elegido_por_el_motor, dedup_del_backend, universo: list[dict]
):
    """Los tres criterios que sí están portados, verificados uno por uno sobre el universo real.

    El desempate puede elegir otra especie, pero nunca una peor: si el backend eligiera una especie
    con menos datos o con el dato roto, alguno de los tres criterios estaría mal portado y esto lo
    muestra con nombre y apellido.
    """
    completitud = {
        str(f["ticker"]): sum(
            pd.notna(f.get(campo)) for campo in ("maturity", "law", "couponCurrency", "underlying")
        )
        for f in universo
    }
    descartados = evaluar_sanidad(segmentar(universo).especies).descartados

    peores = []
    for raiz, ticker_motor in elegido_por_el_motor.items():
        emision = dedup_del_backend.por_raiz[raiz]
        if emision.representante is None:
            continue  # grupo no colapsado: el motor tampoco eligió uno
        mio = emision.representante.ticker
        if (mio in descartados) > (ticker_motor in descartados) or completitud.get(
            mio, 0
        ) < completitud.get(ticker_motor, 0):
            peores.append((raiz, mio, ticker_motor))

    assert peores == []


def test_el_desempate_pendiente_es_la_unica_diferencia_medible(
    elegido_por_el_motor, dedup_del_backend, capsys
):
    """Cuánto se parecen las dos elecciones hoy. **Este test tiene que llegar al 100 % con F-012**:
    si el desempate por volumen normalizado estuviera, los dos elegirían siempre lo mismo.

    No falla por debajo del 100 % a propósito —el hueco está declarado y es la decisión de la
    feature— pero sí falla si el universo dejara de tener emisiones multiespecie, porque ahí este
    archivo entero dejaría de probar algo.
    """
    multiespecie = [e for e in dedup_del_backend.emisiones if len(e.especies) > 1 and e.colapsada]
    assert multiespecie, "el consolidado dejó de tener emisiones con varias especies"

    coinciden = sum(
        1 for e in multiespecie if elegido_por_el_motor.get(e.raiz) == e.representante.ticker
    )
    with capsys.disabled():
        print(
            f"\nrepresentante coincidente con el motor: {coinciden}/{len(multiespecie)} emisiones "
            "multiespecie (el resto es el desempate por volumen que espera a F-012)"
        )
