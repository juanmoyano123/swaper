"""La clasificación de renta variable: eslabón de la cadena (SIC) y estrategia de un ETF.

Los casos salen de los 413 CEDEARs que BYMA lista y de los códigos SIC reales de la SEC, medidos
el 13/08/2026. Lo que se fija acá no es que el código funcione: es **hasta dónde se puede afirmar
algo y dónde hay que declarar que no se sabe**.
"""

from app.externos.sic import division_de
from app.renta_variable.etfs import SIN_CLASIFICAR, es_fondo, estrategia_de

# --- El eslabón de la cadena productiva -----------------------------------------------------------


def test_el_sic_ubica_a_la_empresa_en_la_cadena() -> None:
    """Los cuatro eslabones que el asesor necesita distinguir para armar un portafolio, con
    códigos SIC reales de la SEC."""
    assert division_de("1040").eslabon == "Extracción", "Gold and Silver Ores"
    assert division_de("1311").eslabon == "Extracción", "Crude Petroleum & Natural Gas"
    assert division_de("3571").eslabon == "Manufactura", "Electronic Computers (Apple)"
    assert division_de("5912").eslabon == "Comercio minorista"
    assert division_de("6021").eslabon == "Finanzas y seguros", "National Commercial Banks"
    assert division_de("7372").eslabon == "Servicios", "Prepackaged Software (Microsoft)"


def test_el_codigo_llega_con_y_sin_ceros_a_la_izquierda() -> None:
    """`100` y `0100` son el mismo código de agricultura: la SEC lo sirve de las dos formas."""
    assert division_de("100") == division_de("0100")
    assert division_de(100).eslabon == "Producción primaria"


def test_un_codigo_de_un_hueco_del_manual_no_se_empuja_a_la_division_vecina() -> None:
    """El SIC Manual deja huecos (18-19, 68-69, 90). Un código ahí es un dato que no tenemos, no
    uno que se pueda aproximar al eslabón más parecido."""
    assert division_de("1850") is None
    assert division_de("6850") is None


def test_sin_sic_no_se_inventa_un_eslabon() -> None:
    assert division_de(None) is None
    assert division_de("") is None
    assert division_de("no es un numero") is None


# --- La estrategia de un ETF ----------------------------------------------------------------------


def test_netflix_no_es_un_fondo() -> None:
    """`NETFLIX` contiene `ETF` como substring. La primera versión de esto lo clasificó como fondo;
    por eso el detector compara por palabra entera."""
    assert es_fondo("Netflix, Inc.") is False
    assert es_fondo("iShares MSCI ACWI ETF") is True
    assert es_fondo("SPDR GOLD TRUST") is True


def test_una_empresa_no_tiene_estrategia_de_fondo() -> None:
    """`None` y `SIN_CLASIFICAR` dicen cosas distintas: uno es "no es un fondo", el otro "es un
    fondo y su nombre no declara la estrategia"."""
    assert estrategia_de("Apple Inc.") is None


def test_cada_idea_de_armado_se_reconoce_por_lo_que_el_nombre_dice() -> None:
    """Los nombres son los que publica BYMA, tal cual."""
    casos = {
        "Invesco S&P 500 eql wght ETF": "equiponderado",
        "iShares S&P 500 Value ETF": "factor",
        "iShares S&P 500 Growth ETF": "factor",
        "IShares ESG Aware MSCI USA ETF": "esg",
        "ISHARES ETHEREUM TR ETF": "cripto",
        "ETF SPDR GOLD TRUST": "activo_fisico",
        "Global X Uranium ETF": "sectorial",
        "VAN ECK SEMICONDUCTOR ETF": "sectorial",
        "Utilities Select Sector SPDR Fund": "sectorial",
        "iShares MSCI JAPAN ETF": "geografico",
        "IShares Latin America 40 ETF": "geografico",
        "IShares Core S&P 500 ETF": "indice_amplio",
    }
    for nombre, clave in casos.items():
        assert estrategia_de(nombre).clave == clave, nombre


def test_el_factor_gana_sobre_el_indice_que_lo_contiene() -> None:
    """`iShares S&P 500 Value ETF` nombra un índice amplio **y** un factor. Lo que lo distingue de
    `IVV` es el factor, así que ese es el que manda."""
    assert estrategia_de("iShares S&P 500 Value ETF").clave == "factor"
    assert estrategia_de("IShares Core S&P 500 ETF").clave == "indice_amplio"


def test_un_fondo_cuyo_nombre_no_declara_nada_no_se_fuerza() -> None:
    """`INVESCO QQQ TRUST` no dice qué replica. Meterlo en la categoría más parecida sería
    inventar; se declara sin clasificar y se muestra el nombre oficial."""
    estrategia = estrategia_de("INVESCO QQQ TRUST")
    assert estrategia.clave == SIN_CLASIFICAR
    assert "no declara" in estrategia.porque


def test_la_estrategia_dice_por_que_se_clasifico_asi() -> None:
    """Un fondo clasificado sin decir por qué es una caja negra."""
    assert "equal weight" in estrategia_de("Invesco S&P 500 eql wght ETF").porque
