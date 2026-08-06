"""GWT-3 de F-005 en su forma más chica: una celda que no parsea queda `None`, sin inferencia.

También cubre el episodio "Ley Inglesa" (CLAUDE.md, regla 1) como test de regresión: un código de
ley fuera del mapa cerrado no se traduce ni se inventa, queda `None`.
"""

from datetime import date

from app.ingesta.iamc.normalizacion import _fecha, _ley, _numero, _texto

# --- _numero: formato anglosajón, no argentino ---------------------------------------------


def test_un_numero_con_comas_de_miles_y_sufijo_de_millones_se_interpreta() -> None:
    assert _numero("1,100M") == 1_100_000_000.0
    assert _numero("2,064.08M") == 2_064_080_000.0


def test_un_porcentaje_se_devuelve_en_puntos_porcentuales_sin_reescalar() -> None:
    assert _numero("7.92%") == 7.92
    assert _numero("-0.93%") == -0.93


def test_un_numero_sin_sufijo_se_interpreta_tal_cual() -> None:
    assert _numero("156250.0") == 156250.0
    assert _numero("3") == 3.0


def test_un_cero_declarado_es_un_numero_valido_no_un_faltante() -> None:
    """Un volumen de 0.00M es una ON que no operó ese día: es dato, no hueco."""
    assert _numero("0.00M") == 0.0


def test_una_celda_vacia_o_ausente_no_se_completa() -> None:
    assert _numero("") is None
    assert _numero("   ") is None
    assert _numero(None) is None


def test_un_valor_ilegible_no_se_adivina() -> None:
    assert _numero("N/D") is None
    assert _numero("--") is None


# --- _fecha: dd-MMM-yy en inglés, sin depender del locale del proceso -----------------------


def test_una_fecha_con_mes_en_ingles_se_interpreta() -> None:
    assert _fecha("30-Jun-26") == date(2026, 6, 30)
    assert _fecha("05-Aug-26") == date(2026, 8, 5)


def test_un_anio_de_dos_digitos_se_lee_como_veinte_veinte() -> None:
    assert _fecha("01-Jan-99") == date(2099, 1, 1)


def test_una_fecha_ilegible_queda_vacia() -> None:
    assert _fecha("no aplica") is None
    assert _fecha("") is None
    assert _fecha(None) is None


# --- _ley: el episodio "Ley Inglesa" convertido en test de regresión ------------------------


def test_los_codigos_conocidos_de_ley_se_traducen() -> None:
    assert _ley("ARG") == "Ley Argentina"
    assert _ley("NY") == "Ley N.Y."


def test_un_codigo_de_ley_fuera_del_mapa_no_se_traduce_ni_se_inventa() -> None:
    """Antecedente real: un código se tradujo una vez como "Ley Inglesa", categoría que no
    existe. Un código nuevo tiene que quedar vacío, nunca una traducción adivinada."""
    assert _ley("UK") is None


def test_la_ley_es_case_insensitive_pero_no_mas_permisiva_que_eso() -> None:
    assert _ley("arg") == "Ley Argentina"
    assert _ley(None) is None


# --- _texto: celdas envueltas a dos líneas dentro de la misma celda -------------------------


def test_los_saltos_de_linea_internos_se_colapsan_a_un_espacio() -> None:
    assert _texto("PECOM SERVICIOS\nENERGIA S.A.U") == "PECOM SERVICIOS ENERGIA S.A.U"


def test_una_celda_de_texto_vacia_o_ausente_queda_vacia() -> None:
    assert _texto("") is None
    assert _texto("   ") is None
    assert _texto(None) is None
