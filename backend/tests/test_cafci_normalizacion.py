from datetime import date

from app.ingesta.cafci.normalizacion import entero, fecha, numero, texto


class TestTexto:
    def test_recorta_espacios(self) -> None:
        assert texto("  ARS  ") == "ARS"

    def test_cadena_vacia_es_faltante(self) -> None:
        assert texto("   ") is None
        assert texto("") is None

    def test_none_es_faltante(self) -> None:
        assert texto(None) is None

    def test_no_normaliza_el_contenido(self) -> None:
        """USB no se traduce a nada: se guarda tal cual llega (regla 11)."""
        assert texto("USB") == "USB"


class TestEntero:
    def test_centinelas_se_guardan_tal_cual(self) -> None:
        assert entero(999) == 999
        assert entero(9999) == 9999
        assert entero(99999) == 99999
        assert entero(-1) == -1

    def test_desde_float(self) -> None:
        assert entero(1.0) == 1

    def test_none_es_faltante(self) -> None:
        assert entero(None) is None

    def test_bool_no_es_entero(self) -> None:
        assert entero(True) is None


class TestNumero:
    def test_desde_int_y_float(self) -> None:
        assert numero(5) == 5.0
        assert numero(5.5) == 5.5

    def test_desde_texto(self) -> None:
        assert numero("3.14") == 3.14

    def test_texto_vacio_es_faltante(self) -> None:
        assert numero("") is None
        assert numero("   ") is None

    def test_texto_no_numerico_es_faltante(self) -> None:
        assert numero("abc") is None

    def test_none_es_faltante(self) -> None:
        assert numero(None) is None


class TestFecha:
    def test_dd_mm_aa_resuelve_siglo_via_convencion_estandar(self) -> None:
        """00-68 -> 20xx, 69-99 -> 19xx (`datetime.strptime('%y')`): un fondo con `03/06/04` es de
        2004, no de 1904 — la convención de la librería estándar, no una interpretación propia."""
        assert fecha("21/08/26") == date(2026, 8, 21)
        assert fecha("03/06/04") == date(2004, 6, 3)
        assert fecha("31/03/21") == date(2021, 3, 31)

    def test_none_es_faltante(self) -> None:
        assert fecha(None) is None

    def test_texto_vacio_es_faltante(self) -> None:
        assert fecha("") is None

    def test_formato_no_reconocido_es_faltante(self) -> None:
        assert fecha("2026-08-21") is None

    def test_acepta_date_nativo(self) -> None:
        assert fecha(date(2026, 8, 21)) == date(2026, 8, 21)
