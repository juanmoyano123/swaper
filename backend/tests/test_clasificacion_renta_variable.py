"""La clasificación de renta variable: eslabón de la cadena (SIC) y estrategia de un ETF.

Los casos salen de los 413 CEDEARs que BYMA lista y de los códigos SIC reales de la SEC, medidos
el 13/08/2026. Lo que se fija acá no es que el código funcione: es **hasta dónde se puede afirmar
algo y dónde hay que declarar que no se sabe**.
"""

from app.externos.sic import division_de, major_group_de, titulo_major_group_de
from app.renta_variable.etfs import (
    SIN_CLASIFICAR,
    es_fondo,
    estrategia_de,
    region_declarada,
)

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


# --- El major group, extraído para F-079 ----------------------------------------------------------


def test_major_group_de_devuelve_dos_digitos_con_cero_a_la_izquierda() -> None:
    """`28` (Chemicals) queda `"28"`, y `1` (Agricultural Production Crops) queda `"01"`: el eje de
    "sector" de F-079 agrupa por este string, no por el int."""
    assert major_group_de("2834") == "28"
    assert major_group_de("1040") == "10"
    assert major_group_de(100) == "01"
    assert major_group_de("0100") == "01"


def test_major_group_de_con_menos_de_dos_digitos_no_afirma_nada() -> None:
    """Un código de un solo dígito no alcanza para decir el major group — no se rellena a
    ciegas."""
    assert major_group_de("1") is None
    assert major_group_de("") is None


def test_major_group_de_con_none_o_no_numerico_es_none() -> None:
    assert major_group_de(None) is None
    assert major_group_de("no es un numero") is None


def test_division_de_sigue_igual_reusando_major_group_de() -> None:
    """El refactor de extracción no cambia el comportamiento observable de `division_de`: sigue
    resolviendo la división a partir del mismo major group que ahora expone `major_group_de`."""
    assert division_de("2834").eslabon == "Manufactura"
    assert major_group_de("2834") == "28"
    assert division_de("6850") is None  # hueco del manual, mismo caso que antes del refactor
    assert major_group_de("6850") == "68"


# --- El nombre oficial del major group, del SIC Manual de OSHA (30/08/2026) -----------------------


def test_titulo_major_group_de_trae_el_nombre_oficial() -> None:
    """Los mismos códigos SIC reales que ya usa `test_el_sic_ubica_a_la_empresa_en_la_cadena`."""
    assert titulo_major_group_de("1040") == "Metal Mining"  # Gold and Silver Ores
    assert titulo_major_group_de("3571") == (
        "Industrial And Commercial Machinery And Computer Equipment"
    )  # Electronic Computers (Apple)
    assert titulo_major_group_de("7372") == "Business Services"  # Prepackaged Software (Microsoft)
    assert titulo_major_group_de("6021") == "Depository Institutions"  # National Commercial Banks


def test_titulo_major_group_de_con_ceros_a_la_izquierda_recortados() -> None:
    assert titulo_major_group_de("100") == titulo_major_group_de("0100")
    assert titulo_major_group_de(100) == "Agricultural Production Crops"


def test_titulo_major_group_de_en_un_hueco_del_manual_es_none() -> None:
    """Mismo hueco que ya prueba `division_de`: el Manual no define 18-19, 68-69 ni 90 — no hay
    nombre que afirmar ahí."""
    assert titulo_major_group_de("1850") is None
    assert titulo_major_group_de("6850") is None
    assert titulo_major_group_de("9050") is None


def test_titulo_major_group_de_sin_sic_no_inventa_nada() -> None:
    assert titulo_major_group_de(None) is None
    assert titulo_major_group_de("") is None
    assert titulo_major_group_de("no es un numero") is None
    assert titulo_major_group_de("1") is None


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


# --- La geografía que el nombre declara ----------------------------------------------------------


def test_la_geografia_sale_del_nombre_tal_como_aparece() -> None:
    """Los nueve fondos con geografía en el nombre, medidos contra la base el 28/08/2026. Los
    nombres llegan en mayúsculas y en mixta, y lo único que se normaliza es la caja: `EAFE` sigue
    siendo `EAFE` y no "Europa, Australasia y Lejano Oriente", que es correcto pero no está escrito
    en ninguna parte de la fuente (regla 11)."""
    casos = {
        "iShares MSCI ACWI ETF": "ACWI",
        "iShares MSCI EAFE ETF": "EAFE",
        "iShares MSCI JAPAN ETF": "Japan",
        "iShares MSCI South Korea ETF": "South Korea",
        "ISHARES CHINA LARGE-CAP ETF": "China",
        "iShares Core MSCI Emerging Markets ETF": "Emerging Markets",
        "iShares Core MSCI Europe ETF": "Europe",
        "IShares Latin America 40 ETF": "Latin America",
        "Vanguard FTSE Developed Markets ETF": "Developed Markets",
    }
    for nombre, region in casos.items():
        assert region_declarada(nombre) == region, nombre


def test_un_fondo_que_no_nombra_geografia_queda_sin_region() -> None:
    """`None` acá no es "invierte en todos lados": es que no se sabe. Completar `XLK` con "Estados
    Unidos" porque el SPDR sectorial sigue al S&P 500 sería inferir, no leer."""
    assert region_declarada("IShares Core S&P 500 ETF") is None
    assert region_declarada("The Technology Select Sector SPDR Fund") is None
    assert region_declarada("ETF SPDR GOLD TRUST") is None


def test_una_empresa_no_tiene_geografia_de_fondo() -> None:
    """Mismo guardia que `estrategia_de`: si no es un fondo, no hay nada que leer. Y el detector es
    por palabra entera — `PetroChina` contiene `China` como substring, que es la misma familia de
    bug que clasificó a Netflix como fondo."""
    assert region_declarada("Apple Inc.") is None
    assert region_declarada("PetroChina Company Limited") is None
    assert region_declarada(None) is None


def test_un_pais_en_la_razon_social_no_es_geografia_de_exposicion() -> None:
    """Los dos falsos positivos medidos el 28/08/2026. `United States Oil Fund` compra futuros de
    WTI y `Global X` es la marca del emisor: en los dos el topónimo nombra a quién emite, no dónde
    invierte. Por eso el vocabulario es cerrado y no "cualquier topónimo"."""
    assert region_declarada("United States Oil Fund") is None
    assert region_declarada("Global X Copper Miners ETF") is None
    assert region_declarada("Global X Uranium ETF") is None
    # `Global` sin la X sí es alcance del fondo, y ese sí se lee.
    assert region_declarada("iShares Global Clean Energy ETF") == "Global"


def test_una_geografia_negada_no_se_declara_como_exposicion() -> None:
    """`ex China` nombra China para excluirla. Devolver `China` sería decir exactamente lo contrario
    de lo que el nombre dice."""
    assert region_declarada("iShares MSCI Emerging Markets ex China ETF") == "Emerging Markets"


def test_lo_especifico_gana_sobre_lo_general() -> None:
    """Mismo criterio de orden que `_REGLAS`: un nombre que dice `South Korea` no se recorta a
    `Korea`, porque lo que la fuente escribió es lo primero."""
    assert region_declarada("iShares MSCI South Korea ETF") == "South Korea"
    assert region_declarada("Some Korea Fund ETF") == "Korea"
