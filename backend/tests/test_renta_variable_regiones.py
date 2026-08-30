"""La subregión M49 de la ONU — F-078.

Lo que se fija acá no es que un dict tenga entradas: es **que el módulo diga lo que el estándar dice
y no lo que nos resultaría cómodo**. Los dos casos que más importan son México (que la ONU pone en
América Latina y el Caribe, no en América del Norte) y la Antártida (que la ONU no ubica en ninguna
subregión, y acá queda sin región en vez de empujarse a la más cercana).
"""

from app.renta_variable.regiones import REGION_M49, region_de

# --- Los países que van a aparecer en CEDEARs ----------------------------------------------------


def test_los_paises_de_los_cedears_tienen_region() -> None:
    """Los treinta que la ficha de F-078 enumera como esperables en el universo de CEDEARs. Sin
    región, un papel curado entraría a la base sin poder agruparse por ningún eje geográfico."""
    esperados = [
        "US", "CA", "BR", "MX", "CL", "AR", "CN", "TW", "JP", "KR",
        "IN", "IL", "GB", "IE", "NL", "DE", "FR", "CH", "ES", "IT",
        "SE", "DK", "AU", "ZA", "SG", "HK", "BM", "KY", "LU", "UY",
    ]
    sin_region = [pais for pais in esperados if region_de(pais) is None]
    assert sin_region == []


def test_la_subregion_separa_lo_que_el_continente_junta() -> None:
    """Es la razón por la que se eligió subregión y no continente: con continente, Israel y Japón
    serían los dos "Asia", y Estados Unidos y Brasil los dos "América"."""
    assert region_de("IL") == "Asia occidental"
    assert region_de("JP") == "Asia oriental"
    assert region_de("US") == "América del Norte"
    assert region_de("BR") == "América Latina y el Caribe"


def test_mexico_va_donde_la_onu_lo_pone_y_no_donde_intuiriamos() -> None:
    """M49 ubica a México en América Latina y el Caribe (419), no en América del Norte (021).
    "Corregirlo" sería inventar una agrupación propia, que es justo lo que el estándar evita."""
    assert region_de("MX") == "América Latina y el Caribe"
    assert region_de("CA") == "América del Norte"


def test_hong_kong_no_se_pliega_a_china() -> None:
    """M49 los lista como áreas separadas; van a la misma subregión pero como dos códigos."""
    assert region_de("HK") == region_de("CN") == "Asia oriental"
    assert REGION_M49["HK"] == REGION_M49["MO"]


# --- Lo que no se sabe, no se aproxima -----------------------------------------------------------


def test_la_antartida_no_se_empuja_a_la_subregion_mas_cercana() -> None:
    """M49 no le asigna región. Mismo criterio que `division_de` con un código SIC que cae en un
    hueco del manual: sin dato, `None`."""
    assert region_de("AQ") is None


def test_sin_pais_no_hay_region_inventada() -> None:
    assert region_de(None) is None
    assert region_de("") is None
    assert region_de("   ") is None


def test_un_codigo_que_no_es_alfa_2_no_resuelve() -> None:
    """No se adivina un alfa-3 ni un nombre de país escrito en castellano: el vocabulario del CSV
    curado es ISO 3166-1 alfa-2 y sólo eso."""
    assert region_de("USA") is None
    assert region_de("Estados Unidos") is None


def test_se_acepta_la_caja_y_los_espacios_del_csv_editado_a_mano() -> None:
    """El curado se edita en planillas. Normalizar la caja no es interpretar el código: `us` y `US`
    son literalmente la misma entrada del estándar."""
    assert region_de(" us ") == region_de("US")
    assert region_de("br") == region_de("BR")


# --- La forma del mapa ---------------------------------------------------------------------------


def test_toda_clave_es_un_alfa_2_en_mayusculas() -> None:
    """El dict es además el vocabulario cerrado contra el que `paises.py` valida el CSV: una clave
    mal escrita haría pasar o rebotar filas por el motivo equivocado."""
    malas = [k for k in REGION_M49 if len(k) != 2 or not k.isupper() or not k.isalpha()]
    assert malas == []


def test_las_agrupaciones_son_las_veinte_que_el_modulo_declara() -> None:
    """Cinco de África (septentrional más las cuatro regiones intermedias subsaharianas), dos de
    América, cinco de Asia, cuatro de Europa y cuatro de Oceanía. Si aparece una vigésimo primera es
    un typo en un nombre repetido, y el error se ve acá y no en una pantalla con dos facetas casi
    iguales."""
    assert len(set(REGION_M49.values())) == 20


def test_africa_se_lee_a_la_altura_de_los_demas_continentes() -> None:
    """La subregión M49 de África son sólo dos y la subsahariana junta medio continente. Se usa la
    región intermedia —también publicada por la ONU— para que la escala sea comparable con
    "Europa occidental" o "Asia oriental". Es el único corte del módulo que hubo que elegir, y por
    eso se fija con un test."""
    assert region_de("ZA") == "África meridional"
    assert region_de("NG") == "África occidental"
    assert region_de("KE") == "África oriental"
    assert "África subsahariana" not in set(REGION_M49.values())
