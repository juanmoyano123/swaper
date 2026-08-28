"""Raíz de emisión y clasificación: las dos reglas que deciden qué entra al universo y como qué.

Lo que se prueba acá no es aritmética: es que ninguna de las dos derive un dato que la fuente no
declaró. La raíz agrupa especies de la misma emisión y la clasificación traduce declaraciones de
BYMA y de Docta; cuando ninguna de las dos alcanza, el resultado tiene que ser `None` y no una
suposición razonable.
"""

from app.ingesta.consolidacion.clasificacion import (
    CLASE_POR_ENDPOINT,
    ENDPOINTS_SIN_CLASE_PROPIA,
    SUBMARKET_MAP,
    clasificar,
    hay_discrepancia,
    subtipo_de,
    subtipo_en_corrida,
)
from app.ingesta.raiz import raiz_emision

# --- Raíz de emisión ---------------------------------------------------------------------------


def test_las_tres_especies_de_liquidacion_comparten_raiz() -> None:
    assert raiz_emision("AL30") == "AL30"
    assert raiz_emision("AL30D") == "AL30"
    assert raiz_emision("AL30C") == "AL30"
    assert raiz_emision("MR46O") == "MR46"


def test_un_ticker_corto_que_termina_en_o_d_o_c_no_se_corta() -> None:
    """Sin el guardia de longitud, un ticker de tres letras perdería una y pasaría a ser otro."""
    assert raiz_emision("GGD") == "GGD"
    assert raiz_emision("ALO") == "ALO"


def test_las_especies_x_y_z_no_se_reducen_a_la_raiz() -> None:
    """BYMA publica AL30X/Y/Z como un segundo trío del mismo bono, pero eso no lo declara nadie.

    Cortar la X para llegar a AL30 sería derivar un ticker de otro manipulando strings, que es
    justamente el error que ya obligó a revertir 121 tickers inventados. Quedan como están, sin
    cronograma y por lo tanto fuera del universo.
    """
    assert raiz_emision("AL30X") == "AL30X"
    assert raiz_emision("AL30Y") == "AL30Y"
    assert raiz_emision("AL30Z") == "AL30Z"


def test_la_raiz_del_backend_coincide_con_la_del_motor() -> None:
    """Las dos copias tienen que dar lo mismo o el universo se agrupa distinto de como se lee."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    import segmentos  # type: ignore[import-not-found]

    tickers = ["AL30", "AL30D", "AL30C", "AL30X", "MR46O", "GGD", "ALO", "TX26", "PLC7O", "CEDI"]
    del_motor = list(segmentos.raiz_emision(__import__("pandas").Series(tickers)))

    assert [raiz_emision(t) for t in tickers] == del_motor


# --- Clasificación: el endpoint declara la clase ------------------------------------------------


def test_el_endpoint_declara_la_clase_de_tres_grupos() -> None:
    assert clasificar("negociable-obligations", None) == ("on_corporativo", None)
    assert clasificar("cedears", None) == ("cedear", None)
    assert clasificar("general-equity", None) == ("accion", None)
    assert clasificar("leading-equity", None) == ("accion", None)


def test_acciones_y_cedears_entran_sin_tipo_de_tasa() -> None:
    """No tienen tasa, y ese None es lo que los deja fuera del armador y del swaper."""
    for endpoint in ("cedears", "general-equity", "leading-equity"):
        _, tipo_tasa = clasificar(endpoint, None)
        assert tipo_tasa is None, f"{endpoint} no debería tener tipo de tasa"


def test_el_cronograma_aporta_el_tipo_de_tasa_de_una_on() -> None:
    assert clasificar("negociable-obligations", "ON_TAMAR") == ("on_corporativo", "tamar")
    assert clasificar("negociable-obligations", "ON_CER") == ("on_corporativo", "cer")


def test_uva_y_cer_son_el_mismo_casillero() -> None:
    """El nombre cambia según el endpoint que lo publique; el segmento es el mismo."""
    assert SUBMARKET_MAP["ON_UVA"] == SUBMARKET_MAP["ON_CER"]


# --- Clasificación: public-bonds necesita el cronograma -----------------------------------------


def test_el_cronograma_separa_soberanos_de_subsoberanos() -> None:
    """BYMA no los distingue: securitySubType vale 'B' en las 1106 filas de public-bonds."""
    assert clasificar("public-bonds", "HARD_DOLLAR") == ("bono_soberano", "hard-dollar")
    assert clasificar("public-bonds", "SUB_SOBERANO") == ("bono_subsoberano", "hard-dollar")
    assert clasificar("public-bonds", "SUB_SOBERANO_CER") == ("bono_subsoberano", "cer")


def test_un_bono_publico_sin_cronograma_no_se_clasifica() -> None:
    """Es el caso de AL30X. Elegirle una clase sería inventar el dato que las separa."""
    assert clasificar("public-bonds", None) is None


def test_un_tipo_de_cronograma_desconocido_no_se_mapea_por_parecido() -> None:
    """'SUB_SOBERANO_UVA' se parece a uno conocido, y eso no lo hace conocido."""
    assert clasificar("public-bonds", "SUB_SOBERANO_UVA") is None


def test_un_endpoint_que_no_existe_no_clasifica() -> None:
    assert clasificar("corporate-bonds", "ON") is None


# --- Discrepancias: el endpoint gana y la contradicción se declara ------------------------------


def test_una_on_cuya_raiz_declara_submarket_soberano_conserva_la_clase_del_endpoint() -> None:
    clase, tipo_tasa = clasificar("negociable-obligations", "HARD_DOLLAR")

    assert clase == "on_corporativo", "el endpoint es la fuente declarada de especies"
    assert tipo_tasa is None, "el tipo de tasa no se toma de un cronograma que contradice la clase"
    assert hay_discrepancia("negociable-obligations", "HARD_DOLLAR")


def test_no_hay_discrepancia_cuando_las_dos_fuentes_acuerdan() -> None:
    assert not hay_discrepancia("negociable-obligations", "ON_TAMAR")
    assert not hay_discrepancia("cedears", None)
    assert not hay_discrepancia("public-bonds", "HARD_DOLLAR"), (
        "no tiene clase propia que contradecir"
    )


# --- Subtipo -----------------------------------------------------------------------------------


def test_el_subtipo_sale_de_la_ley_y_solo_para_hard_dollar() -> None:
    assert subtipo_de("hard-dollar", "Ley N.Y.") == "global"
    assert subtipo_de("hard-dollar", "Ley Argentina") == "bonar"
    assert subtipo_de("cer", "Ley Argentina") is None


def test_sin_ley_no_hay_subtipo() -> None:
    """En F-007 es el caso normal: la ley llega por IAMC, que cubre 242 emisiones de 822."""
    assert subtipo_de("hard-dollar", None) is None


def test_el_panel_de_letras_se_clasifica_por_cronograma_igual_que_public_bonds() -> None:
    """`lebacs` no declara clase propia: la da el `type` del cronograma, como en public-bonds."""
    assert clasificar("lebacs", "FIXED_RATE") == ("bono_soberano", "tasa-fija")
    assert clasificar("lebacs", "SUB_SOBERANO_TAMAR") == ("bono_subsoberano", "tamar")
    assert "lebacs" in ENDPOINTS_SIN_CLASE_PROPIA


def test_una_especie_del_panel_de_letras_sin_cronograma_no_se_clasifica() -> None:
    """Las 108 `.SB` y las 147 variantes C/D/X/Y/Z caen acá: sin cronograma no hay clase.

    Marcarlas "letra" porque vinieron del panel de letras sería leer el panel como si declarara el
    emisor, que es lo que la regla 11 prohíbe.
    """
    assert clasificar("lebacs", None) is None
    assert clasificar("lebacs", "SUB_SOBERANO_UVA") is None


def test_el_panel_de_letras_no_tiene_clase_propia_que_pueda_discrepar() -> None:
    assert not hay_discrepancia("lebacs", "SUB_SOBERANO_TAMAR")


def test_una_letra_del_tesoro_lleva_subtipo_letra() -> None:
    assert subtipo_en_corrida("lebacs", "bono_soberano", "tasa-fija") == "letra"


def test_una_letra_subsoberana_del_mismo_panel_no_lleva_subtipo() -> None:
    """El panel mezcla Tesoro y provincias: una letra provincial no es una letra del Tesoro."""
    assert subtipo_en_corrida("lebacs", "bono_subsoberano", "tamar") is None


def test_un_bopreal_lleva_subtipo_bopreal_venga_del_panel_que_venga() -> None:
    """Lo declara `tipo_tasa`, que sale del `type` del cronograma, no el ticker ni el panel."""
    assert subtipo_en_corrida("public-bonds", "bono_soberano", "bopreal") == "bopreal"
    assert subtipo_en_corrida("lebacs", "bono_soberano", "bopreal") == "letra", (
        "combinación que no se observó el 28/08/2026; el orden queda fijado para que el resultado "
        "no dependa del azar si alguna vez aparece"
    )


def test_la_corrida_no_deriva_bonar_ni_global() -> None:
    """Dependen de `law`, que no viaja en la fila de BYMA. Los escribe el backfill, no la corrida.

    Devolver `None` es lo que deja que el COALESCE del upsert conserve el subtipo ya persistido.
    """
    assert subtipo_en_corrida("public-bonds", "bono_soberano", "hard-dollar") is None


def test_los_subtipos_que_derivan_las_dos_funciones_estan_en_el_dominio_de_la_tabla() -> None:
    """Si alguna devolviera un valor fuera del CHECK, el INSERT fallaría en la corrida real."""
    del_check = {"global", "bonar", "letra", "bopreal"}
    derivados = {
        subtipo_en_corrida("lebacs", "bono_soberano", "tasa-fija"),
        subtipo_en_corrida("public-bonds", "bono_soberano", "bopreal"),
        subtipo_de("hard-dollar", "Ley N.Y."),
        subtipo_de("hard-dollar", "Ley Argentina"),
    }

    assert derivados <= del_check


def test_las_clases_del_endpoint_estan_todas_en_el_dominio_de_la_tabla() -> None:
    """Si alguien agrega un endpoint con una clase que el CHECK no admite, el INSERT falla."""
    del_check = {"bono_soberano", "bono_subsoberano", "on_corporativo", "accion", "cedear"}

    assert set(CLASE_POR_ENDPOINT.values()) <= del_check
    assert {clase for clase, _ in SUBMARKET_MAP.values()} <= del_check


def test_los_tipos_de_tasa_estan_todos_en_el_dominio_de_la_tabla() -> None:
    del_check = {"hard-dollar", "tasa-fija", "cer", "dollar-linked", "badlar", "tamar", "bopreal"}
    tipos = {tipo for _, tipo in SUBMARKET_MAP.values() if tipo is not None}

    assert tipos <= del_check
