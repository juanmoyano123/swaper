"""El port de la deduplicación contra su original en `tools/segmentos.py` — F-011.

El backend no importa de `tools/`, así que `deduplicar_emisiones` está copiada. Una copia sin un
test que la compare no es un port: es una segunda implementación que va a divergir sin que nadie se
entere, y el día que diverja el motor y el producto van a estar armando carteras sobre universos
distintos. Es la misma razón por la que existe `test_universo_paridad_motor.py` para la sanidad.

**Los dos no tienen que coincidir en todo, y eso también se prueba acá.** Se exige coincidencia
exacta en lo que decide qué es una emisión —qué grupos se colapsan, cuántas filas quedan, y que el
representante elegido sea igual de sano y de completo— y se mide, sin exigirla, la coincidencia del
representante.

## Por qué ese último número no llega al 100 % con F-012, y por qué está bien

F-011 dejó escrito que cuando el desempate por volumen normalizado existiera los dos iban a elegir
siempre lo mismo. Con F-012 enchufado son **272 de 279**, y las 7 que faltan no son un port mal
hecho: son un bug numérico del motor.

El motor no ordena por una tupla, ordena por un único número:
`sano * 1e24 + completitud * 1e12 + volumen_usd`, y se queda con el `idxmax`. En float64 el espacio
entre dos números representables alrededor de 1e24 es 134.217.728, y los volúmenes del consolidado
llegan hasta 1,9e8: **casi todos caen por debajo de un ulp y la suma los descarta enteros**. Cuando
eso pasa, las hermanas quedan con la misma clave bit a bit y `idxmax` devuelve la primera fila, que
en un universo ordenado por ticker es la alfabética.

Las 7 diferencias son exactamente los grupos donde el volumen sí debería haber decidido, y en los 7
el backend elige la especie más operada: BA7DD (333.383 USD) contra BA7DC (3.455), BB7DD (115.402)
contra BB7DC (80), y así. Reproducir el redondeo para que el número diera 279 sería portar el error,
no el criterio.

Se compara sobre el consolidado histórico y no sobre la base porque el Excel es lo que el motor lee,
y porque ahí hay especies con `duration` cargada — sin duraciones, el chequeo del 5 % no puede
disparar y el test estaría probando que los dos coinciden en no hacer nada.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

from app.universo.cambio import derivar_tipo_de_cambio, normalizar_volumen
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
    """El universo del backend con el camino entero: segmentar, normalizar el volumen, deduplicar.

    El tipo de cambio se deriva acá y no se pasa a mano porque es lo que hace `sanear`: si el
    desempate por volumen se probara con una columna cargada a dedo, este test no verificaría que el
    volumen que llega al desempate es el que F-012 produce.
    """
    crudas = segmentar(universo).especies
    especies = normalizar_volumen(crudas, derivar_tipo_de_cambio(crudas))
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


def test_donde_los_dos_difieren_es_donde_el_motor_pierde_el_volumen(
    elegido_por_el_motor, dedup_del_backend, capsys
):
    """Cuánto se parecen las dos elecciones, y que cada diferencia esté explicada por el volumen.

    No se exige coincidencia total —el porqué está en el docstring del módulo: el motor suma el
    volumen a un 1e24 que lo redondea a cero— pero sí se exige que **cada** diferencia sea un caso
    donde el backend eligió la especie más operada. Una diferencia en la que el backend eligiera la
    menos líquida no sería el bug del motor: sería el port mal hecho.
    """
    multiespecie = [e for e in dedup_del_backend.emisiones if len(e.especies) > 1 and e.colapsada]
    assert multiespecie, "el consolidado dejó de tener emisiones con varias especies"

    difieren = [
        e for e in multiespecie if elegido_por_el_motor.get(e.raiz) != e.representante.ticker
    ]
    menos_liquidas = [
        e.raiz
        for e in difieren
        if any((h.volumen_usd or 0) > (e.representante.volumen_usd or 0) for h in e.especies)
    ]
    assert menos_liquidas == []

    with capsys.disabled():
        print(
            f"\nrepresentante coincidente con el motor: "
            f"{len(multiespecie) - len(difieren)}/{len(multiespecie)} emisiones multiespecie; "
            f"las {len(difieren)} que difieren son las que el motor decide con un volumen que su "
            f"propia suma en float64 redondeó a cero ({', '.join(e.raiz for e in difieren)})"
        )
