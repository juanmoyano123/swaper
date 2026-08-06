"""La segmentación: con quién es comparable cada especie y en qué unidad se la mide.

No es un detalle previo a la sanidad: es lo que decide contra qué tope se compara cada instrumento.
Si acá un CER cayera en `usd_hard`, la capa 2 lo mediría contra 300 % en vez de contra 100 % y el
descarte que la spec pide no ocurriría — el test de sanidad seguiría en verde por la razón
equivocada.
"""

import pytest

from app.universo.sanidad import TOPE_SANIDAD_SEGMENTO
from app.universo.segmentacion import (
    DESC_SEGMENTO,
    MONEDA_SEGMENTO,
    NATURALEZA_TASA,
    NOMBRE_NATURALEZA,
    SEGMENTO_POR_TIPO_TASA,
    asignar_segmento,
    rendimiento_declarado,
    segmentar,
)


def fila(ticker: str, tipo_tasa: str | None, *, clase: str = "on_corporativo", **campos: object):
    base: dict[str, object] = {
        "ticker": ticker,
        "clase_activo": clase,
        "tipo_tasa": tipo_tasa,
        "tir": None,
        "tna": None,
    }
    return base | campos


# --- Los segmentos y sus unidades ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("tipo_tasa", "esperado"),
    [
        ("hard-dollar", "usd_hard"),
        ("bopreal", "usd_hard"),
        ("cer", "cer"),
        ("tasa-fija", "tasa_fija"),
        ("dollar-linked", "dollar_linked"),
        ("badlar", "badlar"),
        ("tamar", "tamar"),
    ],
)
def test_cada_tipo_de_tasa_cae_en_su_segmento(tipo_tasa: str, esperado: str) -> None:
    assert asignar_segmento(tipo_tasa) == esperado


def test_un_tipo_de_tasa_desconocido_no_recibe_segmento_por_defecto() -> None:
    """Rule 1: si no se sabe, se deja vacío. Elegirle un segmento lo haría comparable contra una
    vara que no es la suya, que es peor que dejarlo afuera y avisar."""
    assert asignar_segmento("tasa-que-nadie-vio") is None
    assert asignar_segmento(None) is None


def test_los_cuatro_diccionarios_cubren_exactamente_los_mismos_segmentos() -> None:
    """La unidad, la moneda, la descripción y el tope tienen que existir para todo segmento: un
    segmento sin tope pasaría la capa 2 sin que nadie lo note."""
    segmentos = set(SEGMENTO_POR_TIPO_TASA.values())
    assert set(MONEDA_SEGMENTO) == segmentos
    assert set(NATURALEZA_TASA) == segmentos
    assert set(DESC_SEGMENTO) == segmentos
    assert set(TOPE_SANIDAD_SEGMENTO) == segmentos
    assert set(NATURALEZA_TASA.values()) <= set(NOMBRE_NATURALEZA)


def test_hard_dollar_y_pesos_no_comparten_naturaleza_de_tasa() -> None:
    """Regla 2 del dominio, hecha dato: es lo que impide que un tope único cruce unidades."""
    assert NATURALEZA_TASA["usd_hard"] != NATURALEZA_TASA["tasa_fija"]
    assert NATURALEZA_TASA["cer"] != NATURALEZA_TASA["tasa_fija"]
    assert NATURALEZA_TASA["badlar"] == NATURALEZA_TASA["tamar"] == "tna_nominal_ars"


# --- Qué número mide a cada especie -------------------------------------------------------------


def test_la_tasa_fija_se_mide_por_tna_y_el_resto_por_tir() -> None:
    assert rendimiento_declarado("tasa_fija", tir=0.90, tna=4.80) == 4.80
    assert rendimiento_declarado("usd_hard", tir=0.13, tna=4.80) == 0.13


def test_una_tasa_fija_sin_tna_queda_sin_rendimiento_aunque_tenga_tir() -> None:
    """No se rellena una unidad con la otra: una TNA nominal y una TIR no son el mismo número, y
    elegir la que esté cargada sería inventar el dato."""
    assert rendimiento_declarado("tasa_fija", tir=0.35, tna=None) is None


# --- Qué entra al universo comparable y qué no --------------------------------------------------


def test_la_renta_variable_sale_antes_de_segmentar_y_no_cuenta_como_sin_segmento() -> None:
    """Si las acciones cayeran por "sin segmento", la alerta diría 750+ todas las corridas y taparía
    el caso que existe para mostrar: un bono cuyo tipo de tasa no se reconoció."""
    resultado = segmentar(
        [
            fila("GGAL", None, clase="accion"),
            fila("AAPL", None, clase="cedear"),
            fila("MR46O", "hard-dollar", clase="bono_soberano"),
        ]
    )
    assert resultado.renta_variable == 2
    assert resultado.sin_segmento == []
    assert [e.ticker for e in resultado.especies] == ["MR46O"]


def test_la_renta_fija_sin_tipo_de_tasa_se_lista_con_nombre_y_apellido() -> None:
    resultado = segmentar([fila("XXXX", None, clase="bono_subsoberano")])
    assert resultado.sin_segmento == ["XXXX"]
    assert resultado.especies == []


def test_las_especies_de_una_emision_comparten_raiz() -> None:
    resultado = segmentar(
        [
            fila("MR46O", "hard-dollar", tir=0.1310),
            fila("MR46D", "hard-dollar", tir=0.1308),
            fila("MR46C", "hard-dollar", tir=0.1309),
        ]
    )
    assert {e.raiz for e in resultado.especies} == {"MR46"}


def test_un_decimal_de_la_base_llega_como_float_y_lo_que_no_es_numero_queda_vacio() -> None:
    """asyncpg devuelve `Decimal` en las columnas numéricas; lo que no es número no se lee."""
    from decimal import Decimal

    resultado = segmentar(
        [
            fila("AAAAO", "hard-dollar", tir=Decimal("0.1308")),
            fila("BBBBO", "hard-dollar", tir="no es un numero"),
        ]
    )
    por_ticker = {e.ticker: e.rendimiento for e in resultado.especies}
    assert por_ticker["AAAAO"] == pytest.approx(0.1308)
    assert por_ticker["BBBBO"] is None


def test_un_nan_es_un_faltante_y_no_un_numero() -> None:
    """`NaN` es como pandas dice "esta celda estaba vacía". Si llegara como número, la capa 2 lo
    trataría como violación del techo —`nan <= tope` es `False`— y descartaría por roto lo que
    simplemente no se sabe. Sobre el consolidado histórico eran 366 falsos descartes."""
    resultado = segmentar([fila("CCCCO", "hard-dollar", tir=float("nan"))])
    assert resultado.especies[0].rendimiento is None
