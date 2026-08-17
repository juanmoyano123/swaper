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


# --- El cruce con la tabla curada: qué se rellena, qué se vacía y qué se deja como está ----------
#
# Agregado el 08/08/2026. La vista `resumen` lee la ley y el emisor de `instrumentos`, donde IAMC
# sólo los cargó para las especies que publica; `condiciones_emision` los tiene para 823 tickers
# curados. Cruzarlos sube la ley de 592 a 772 y el emisor de 720 a 859 sobre 1.477 de renta fija.


def test_la_ley_curada_rellena_el_hueco_que_la_vista_deja() -> None:
    """El caso de AE38C, que motivó todo esto: la vista no la tiene y la tabla curada sí."""
    resultado = segmentar([fila("AE38C", "hard-dollar", law=None, ley_curada="Ley Argentina")])

    assert resultado.especies[0].ley == "Ley Argentina"
    assert resultado.ley_en_conflicto == []


def test_dos_leyes_distintas_dejan_la_ley_vacia_en_vez_de_elegir_una() -> None:
    """Regla 11 sobre el eje de riesgo más caro de equivocar: la ley decide dónde se cobra.

    Sobre la base real son cuatro emisiones —PLC4, PN38, RC1C e YM39— con sus tres especies cada
    una. Elegir la fuente que quede más cómoda daría un universo filtrable por legislación con doce
    papeles mal clasificados, y nada lo delataría.
    """
    resultado = segmentar(
        [fila("PN38O", "hard-dollar", law="Ley N.Y.", ley_curada="Ley Argentina")]
    )

    assert resultado.especies[0].ley is None
    assert resultado.ley_en_conflicto == ["PN38O"]


def test_cuando_las_dos_fuentes_coinciden_no_hay_conflicto_que_declarar() -> None:
    """La contracara: el detector no puede estar marcando todo lo que tiene las dos fuentes."""
    resultado = segmentar(
        [fila("AL30O", "hard-dollar", law="Ley Argentina", ley_curada="Ley Argentina")]
    )

    assert resultado.especies[0].ley == "Ley Argentina"
    assert resultado.ley_en_conflicto == []


def test_el_emisor_curado_rellena_pero_no_pisa_al_de_la_vista() -> None:
    """Al revés que la ley, y a propósito: acá las fuentes no se contradicen, escriben distinto.

    `BANCO BBVA ARGENTINA S.A.` contra `Banco Bbva Argentina S.A` es el mismo emisor con otra
    tipografía. Vaciarlo borraría 261 emisores que hoy se muestran bien, y emparejarlos por regla de
    strings sería decidir si `S.A.` y `S.A.U.` son la misma sociedad.
    """
    resultado = segmentar(
        [
            fila("BF37O", "hard-dollar", underlying="BANCO BBVA ARGENTINA S.A.",
                 emisor_curado="Banco Bbva Argentina S.A"),
            fila("AEC2O", "hard-dollar", underlying=None,
                 emisor_curado="Aes Argentina Generación S.A."),
        ]
    )
    por_ticker = {e.ticker: e.emisor for e in resultado.especies}

    assert por_ticker["BF37O"] == "BANCO BBVA ARGENTINA S.A.", "gana la vista, no se vacía"
    assert por_ticker["AEC2O"] == "Aes Argentina Generación S.A.", "el curado rellena el hueco"
    assert resultado.emisor_escrito_distinto == ["BF37O"]


def test_la_misma_grafia_en_otro_case_no_cuenta_como_divergencia() -> None:
    """Sólo se reporta lo que de verdad se escribe distinto, no lo que difiere en mayúsculas."""
    resultado = segmentar(
        [fila("XXXXO", "hard-dollar", underlying="ACME S.A.", emisor_curado="Acme S.A.")]
    )

    assert resultado.especies[0].emisor == "ACME S.A."
    assert resultado.emisor_escrito_distinto == []


def test_sin_columnas_curadas_la_segmentacion_sigue_funcionando() -> None:
    """Las filas de un test viejo no traen `ley_curada` ni `emisor_curado`, y no tienen por qué."""
    resultado = segmentar([fila("VIEJOO", "hard-dollar", law="Ley N.Y.", underlying="ACME")])

    assert resultado.especies[0].ley == "Ley N.Y."
    assert resultado.especies[0].emisor == "ACME"
    assert resultado.ley_en_conflicto == []
    assert resultado.emisor_escrito_distinto == []


# --- Especies huérfanas (relevamiento de confiabilidad de datos, 16/08/2026) ---------------------


def test_una_especie_con_la_captura_mas_vieja_que_el_resto_es_huerfana() -> None:
    """El caso central: dejó de cotizar, la poda por-ticker conserva su última fila y esa fila es
    de una corrida anterior a la que trajo a sus vecinas."""
    resultado = segmentar(
        [
            fila("AL30O", "hard-dollar", capturado_en="2026-08-16T11:30:00+00:00"),
            fila("VIEJOO", "hard-dollar", capturado_en="2026-08-14T11:30:00+00:00"),
        ]
    )

    assert resultado.huerfanas == ["VIEJOO"]
    por_ticker = {e.ticker: e.capturado_en for e in resultado.especies}
    assert por_ticker["AL30O"].isoformat() == "2026-08-16T11:30:00+00:00"


def test_todas_las_especies_de_la_misma_corrida_no_tienen_huerfanas() -> None:
    """El contraste: mismo `capturado_en` en todas, ninguna se marca."""
    resultado = segmentar(
        [
            fila("AL30O", "hard-dollar", capturado_en="2026-08-16T11:30:00+00:00"),
            fila("GD30O", "hard-dollar", capturado_en="2026-08-16T11:30:00+00:00"),
        ]
    )

    assert resultado.huerfanas == []


def test_sin_capturado_en_en_ninguna_fila_no_hay_con_que_comparar_y_no_se_marca_nada() -> None:
    """Una corrida anterior a la migración que expone la columna: `capturado_en` es `None` en toda
    la vista, y sin un máximo contra el que comparar no se inventa ninguna huérfana."""
    resultado = segmentar(
        [
            fila("AL30O", "hard-dollar"),
            fila("GD30O", "hard-dollar"),
        ]
    )

    assert resultado.huerfanas == []


def test_una_especie_sin_capturado_en_no_se_marca_huerfana_por_default() -> None:
    """Sin su propio dato no hay con qué comparar esa especie puntual, aunque el resto del universo
    sí tenga `capturado_en`: no se le adivina que está vieja, se declara sin dato en su lugar."""
    resultado = segmentar(
        [
            fila("AL30O", "hard-dollar", capturado_en="2026-08-16T11:30:00+00:00"),
            fila("SINFECHAO", "hard-dollar", capturado_en=None),
        ]
    )

    assert resultado.huerfanas == []
    por_ticker = {e.ticker: e.capturado_en for e in resultado.especies}
    assert por_ticker["SINFECHAO"] is None
