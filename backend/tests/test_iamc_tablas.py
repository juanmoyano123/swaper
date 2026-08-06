"""Mecánica de `app.ingesta.iamc.tablas` contra grillas sintéticas que imitan lo que pdfplumber
devuelve de verdad: índices de columna dispersos, `None` intercalados, y los artefactos
verificados contra la muestra real (glifos de ícono, la fila-artefacto de Ticker+ADTV antes del
header, filas de continuación de un emisor a dos líneas).

No se fabrica ningún PDF acá: `extraer_tabla_pagina` recibe un objeto con `.find_tables()`, y eso
se puede simular con clases chicas.
"""

import pytest

from app.ingesta.iamc.tablas import FilaNoReconocida, extraer_tabla_pagina

ANCHO_FILA = 20
"""Cantidad de columnas de la grilla sintética — alcanza para separar los headers de sobra."""

_INDICES_HEADERS = [1, 4, 7, 10, 13]
_NOMBRES_HEADERS = ["Ticker", "Emisor", "Monto", "Fecha", "VR"]


def _fila_vacia() -> list[str | None]:
    return [None] * ANCHO_FILA


def _fila_header() -> list[str | None]:
    fila = _fila_vacia()
    for indice, nombre in zip(_INDICES_HEADERS, _NOMBRES_HEADERS, strict=True):
        fila[indice] = nombre
    return fila


def _fila_datos(ticker: str, emisor: str, monto: str, fecha: str, vr: str) -> list[str | None]:
    fila = _fila_vacia()
    for indice, valor in zip(_INDICES_HEADERS, [ticker, emisor, monto, fecha, vr], strict=True):
        fila[indice] = valor
    return fila


class _TablaFalsa:
    def __init__(self, grilla: list[list[str | None]], area: float = 1000.0):
        self._grilla = grilla
        ancho = area**0.5
        self.bbox = (0.0, 0.0, ancho, ancho)

    def extract(self) -> list[list[str | None]]:
        return self._grilla


class _PaginaFalsa:
    def __init__(self, tablas: list[_TablaFalsa]):
        self._tablas = tablas

    def find_tables(self) -> list[_TablaFalsa]:
        return self._tablas


# --- selección de tabla y de la fila de headers ---------------------------------------------


def test_entre_dos_tablas_de_la_pagina_se_elige_la_de_mayor_area() -> None:
    """El artefacto chico del encabezado "Power BI Desktop" nunca gana."""
    fila_datos = _fila_datos("AL30O", "EMISOR UNO", "100M", "01-Jan-26", "100.0")
    grilla_grande = [_fila_header(), fila_datos]
    tabla_grande = _TablaFalsa(grilla_grande, area=500_000)
    tabla_chica = _TablaFalsa([["Power BI Desktop"] + [None] * (ANCHO_FILA - 1)], area=7_800)

    pagina = _PaginaFalsa([tabla_chica, tabla_grande])
    resultado = extraer_tabla_pagina(pagina, numero_pagina=1)

    assert resultado is not None
    assert resultado.header_names == _NOMBRES_HEADERS
    assert len(resultado.filas) == 1


def test_la_fila_artefacto_de_dos_celdas_no_se_toma_como_header() -> None:
    """Antes del header real, IAMC deja una fila con sólo `Ticker` + la última columna: tiene
    menos celdas que el header de verdad, así que pierde."""
    fila_artefacto = _fila_vacia()
    fila_artefacto[0] = "Ticker"
    fila_artefacto[19] = "ADTV"

    grilla = [
        fila_artefacto,
        _fila_header(),
        _fila_datos("AL30O", "EMISOR UNO", "100M", "01-Jan-26", "100.0"),
    ]
    pagina = _PaginaFalsa([_TablaFalsa(grilla)])
    resultado = extraer_tabla_pagina(pagina, numero_pagina=1)

    assert resultado is not None
    assert resultado.header_names == _NOMBRES_HEADERS
    assert len(resultado.filas) == 1


def test_una_pagina_sin_ninguna_fila_con_ticker_no_tiene_tabla_reconocible() -> None:
    grilla = [_fila_vacia(), _fila_vacia()]
    pagina = _PaginaFalsa([_TablaFalsa(grilla)])

    assert extraer_tabla_pagina(pagina, numero_pagina=1) is None


def test_una_pagina_sin_ninguna_tabla_no_tiene_tabla_reconocible() -> None:
    pagina = _PaginaFalsa([])

    assert extraer_tabla_pagina(pagina, numero_pagina=1) is None


# --- filas de continuación: el emisor a dos líneas se concatena ------------------------------


def test_la_continuacion_del_emisor_se_concatena_a_la_fila_de_datos_anterior() -> None:
    """Caso real verificado: `MCC3O | PECOM SERVICIOS` seguido de una fila con una sola celda,
    `ENERGIA S.A.U`, en el índice de columna del emisor."""
    fila_continuacion = _fila_vacia()
    fila_continuacion[4] = "ENERGIA S.A.U"

    grilla = [
        _fila_header(),
        _fila_datos("MCC3O", "PECOM SERVICIOS", "197M", "11-May-26", "100.0"),
        fila_continuacion,
    ]
    pagina = _PaginaFalsa([_TablaFalsa(grilla)])
    resultado = extraer_tabla_pagina(pagina, numero_pagina=5)

    assert resultado is not None
    (fila,) = resultado.filas
    assert fila.valores[0] == "MCC3O"
    assert fila.valores[1] == "PECOM SERVICIOS ENERGIA S.A.U"


def test_una_fila_con_dos_continuaciones_a_la_vez_aporta_a_dos_campos_distintos() -> None:
    """Verificado en la sección de pesos: una misma fila de continuación puede traer, a la vez,
    el resto del emisor y el resto de otro campo a dos líneas."""
    fila_continuacion = _fila_vacia()
    fila_continuacion[4] = "S.A.U."
    fila_continuacion[10] = "26"

    grilla = [
        _fila_header(),
        _fila_datos("T661O", "TARJETA NARANJA", "81764M", "30-Nov-", "100.0"),
        fila_continuacion,
    ]
    pagina = _PaginaFalsa([_TablaFalsa(grilla)])
    resultado = extraer_tabla_pagina(pagina, numero_pagina=20)

    assert resultado is not None
    (fila,) = resultado.filas
    assert fila.valores[1] == "TARJETA NARANJA S.A.U."
    assert fila.valores[3] == "30-Nov- 26"


def test_una_continuacion_sin_fila_de_datos_previa_no_se_pierde_en_silencio() -> None:
    fila_continuacion = _fila_vacia()
    fila_continuacion[4] = "S.A.U."

    grilla = [_fila_header(), fila_continuacion]
    pagina = _PaginaFalsa([_TablaFalsa(grilla)])

    with pytest.raises(FilaNoReconocida):
        extraer_tabla_pagina(pagina, numero_pagina=1)


# --- basura conocida: el glifo de ícono de Power BI se ignora --------------------------------


def test_el_glifo_de_icono_se_ignora() -> None:
    fila_glifo = _fila_vacia()
    fila_glifo[13] = ""

    grilla = [
        _fila_header(),
        fila_glifo,
        _fila_datos("AL30O", "EMISOR UNO", "100M", "01-Jan-26", "100.0"),
    ]
    pagina = _PaginaFalsa([_TablaFalsa(grilla)])
    resultado = extraer_tabla_pagina(pagina, numero_pagina=1)

    assert resultado is not None
    assert len(resultado.filas) == 1


def test_las_filas_totalmente_vacias_se_ignoran() -> None:
    grilla = [
        _fila_header(),
        _fila_vacia(),
        _fila_datos("AL30O", "EMISOR UNO", "100M", "01-Jan-26", "100.0"),
        _fila_vacia(),
    ]
    pagina = _PaginaFalsa([_TablaFalsa(grilla)])
    resultado = extraer_tabla_pagina(pagina, numero_pagina=1)

    assert resultado is not None
    assert len(resultado.filas) == 1


# --- mapeo tolerante a corrimiento de índice: el caso PQCOO verificado en la muestra real ----


def test_una_fila_con_todos_los_indices_corridos_uno_hacia_la_izquierda_se_mapea_igual() -> None:
    """Verificado contra la muestra real (PQCOO, sección cupón cero): un emisor largo a dos
    líneas puede correr todos los campos de la fila un índice de columna hacia la izquierda
    respecto de los headers de esa misma página. El mapeo tolera ese corrimiento."""
    fila_corrida = _fila_vacia()
    for indice, valor in zip(
        [0, 3, 6, 9, 12], ["PQCOO", "EMISOR LARGO", "60M", "22-Sep-23", "100.0"], strict=True
    ):
        fila_corrida[indice] = valor

    grilla = [_fila_header(), fila_corrida]
    pagina = _PaginaFalsa([_TablaFalsa(grilla)])
    resultado = extraer_tabla_pagina(pagina, numero_pagina=18)

    assert resultado is not None
    (fila,) = resultado.filas
    assert fila.valores == ["PQCOO", "EMISOR LARGO", "60M", "22-Sep-23", "100.0"]


def test_un_campo_realmente_ausente_no_se_confunde_con_un_corrimiento() -> None:
    """Si falta un valor de verdad (no está ni cerca de su índice esperado), el mapeo tolerante
    no le asigna el valor de un campo vecino: lo deja `None` (GWT-3)."""
    fila_incompleta = _fila_vacia()
    fila_incompleta[1] = "RZ9BO"
    fila_incompleta[4] = "RIZOBACTER"
    # el monto (índice 7) falta de verdad: el siguiente valor real está en fecha (índice 10)
    fila_incompleta[10] = "28-Jun-24"

    grilla = [_fila_header(), fila_incompleta]
    pagina = _PaginaFalsa([_TablaFalsa(grilla)])
    resultado = extraer_tabla_pagina(pagina, numero_pagina=12)

    assert resultado is not None
    (fila,) = resultado.filas
    assert fila.valores[2] is None  # Monto
    assert fila.valores[3] == "28-Jun-24"  # Fecha


# --- lo que no clasifica como nada conocido aborta --------------------------------------------


def test_una_fila_que_no_es_dato_ni_continuacion_ni_basura_no_se_absorbe_en_silencio() -> None:
    fila_rara = _fila_vacia()
    fila_rara[0] = "algo"
    fila_rara[9] = "que no encaja"
    fila_rara[18] = "en nada conocido"

    grilla = [
        _fila_header(),
        _fila_datos("AL30O", "EMISOR UNO", "100M", "01-Jan-26", "100.0"),
        fila_rara,
    ]
    pagina = _PaginaFalsa([_TablaFalsa(grilla)])

    with pytest.raises(FilaNoReconocida) as exc:
        extraer_tabla_pagina(pagina, numero_pagina=7)

    assert exc.value.pagina == 7
