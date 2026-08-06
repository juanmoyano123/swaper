"""Mecánica pdfplumber pura: encontrar la tabla, sus headers y clasificar cada fila de la grilla.

Este módulo no sabe nada de bonos, de ley ni de moneda de pago — entrega filas como listas de
celdas alineadas por posición a los headers de la página. Esa separación es a propósito: si el
día de mañana IAMC cambia qué campos publica pero no cómo arma la grilla, sólo se toca
`secciones.py`.

**Por qué el mapeo por índice es tolerante y no exacto.** El plan original suponía índices de
columna estables dentro de una página (la fila de headers y las de datos comparten los mismos
índices). Eso es cierto la mayoría de las veces, pero se verificó contra la muestra real que **no
siempre**: filas con una celda de emisor muy larga a dos líneas, o la última fila de una página
—que pdfplumber mezcla con el bloque de notas metodológicas de más abajo— corren todos sus campos
un índice de columna hacia la izquierda respecto de los headers de esa misma página (`PQCOO` en
la sección de cupón cero es el caso medido: emisor en el índice 3, no en el 4 donde está el
header). Mapear por igualdad exacta de índice descartaría esas filas como "no reconocidas" y
abortaría el informe entero por un artefacto de renderizado, no por un cambio de layout real —
exactamente el falso positivo que la regla de aborto (`InformeInvalido`) no debería disparar.
La solución es un mapeo por índice más cercano dentro de una tolerancia chica (`TOLERANCIA`): así
absorbe el corrimiento de un renglón sin dejar de detectar un campo genuinamente ausente (si no
hay ninguna celda cerca del índice esperado, el campo es `None`, no se le asigna cualquier cosa).
Se verificó fila por fila contra las 242 filas de datos reales de la muestra: sólo las que de
verdad faltan un valor en origen (un bono en default sin paridad, un cupón cero sin frecuencia de
cupón) quedan con huecos; el resto mapea completo.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

RE_TICKER = re.compile(r"^[A-Z0-9]{4,6}$")

TOLERANCIA = 2
"""Corrimiento máximo de índice de columna que se tolera al mapear una celda a un header, y al
detectar el ancla de ticker. Calibrado contra la muestra real: el corrimiento medido es de un
único índice; 2 da margen sin arriesgar cruzar al header vecino (los headers están, como mínimo,
2 índices de columna aparte entre sí)."""

_CELDA_VACIA = (None, "")


class _Tabla(Protocol):
    bbox: tuple[float, float, float, float]

    def extract(self) -> list[list[str | None]]: ...


class _Pagina(Protocol):
    def find_tables(self) -> list[_Tabla]: ...


@dataclass(slots=True)
class FilaCruda:
    """Una fila de datos ya mapeada por posición a los headers de la página, con las
    continuaciones (emisores o valores a dos líneas) ya concatenadas adentro."""

    valores: list[str | None]
    pagina: int


@dataclass(slots=True)
class TablaPagina:
    header_names: list[str] = field(default_factory=list)
    """Tal como aparecen en el PDF — pueden venir truncados; la validación contra el catálogo
    tolera eso (`parser._headers_compatibles`)."""

    filas: list[FilaCruda] = field(default_factory=list)


class FilaNoReconocida(Exception):
    """Una fila de la grilla no clasifica como dato, continuación ni basura conocida.

    Es la señal de que algo en el layout cambió de una forma que esta mecánica no anticipa —
    `parser.py` la convierte en `InformeInvalido` y aborta el informe entero.
    """

    def __init__(self, pagina: int, indice_fila: int, celdas: list[tuple[int, str]]):
        self.pagina = pagina
        self.indice_fila = indice_fila
        self.celdas = celdas[:4]
        super().__init__(f"página {pagina}, fila de grilla {indice_fila}: {self.celdas}")


def _area(tabla: _Tabla) -> float:
    x0, top, x1, bottom = tabla.bbox
    return (x1 - x0) * (bottom - top)


def _tabla_mayor(pagina: _Pagina) -> _Tabla | None:
    """Cuando pdfplumber ve dos tablas en la página, la segunda es un artefacto chico del
    encabezado "Power BI Desktop": se elige siempre la de mayor área."""
    tablas = pagina.find_tables()
    if not tablas:
        return None
    return max(tablas, key=_area)


def _celdas_no_vacias(fila: list[Any]) -> list[tuple[int, str]]:
    return [(indice, celda) for indice, celda in enumerate(fila) if celda not in _CELDA_VACIA]


def _es_glifo_privado(texto: str) -> bool:
    """Íconos de Power BI (rango Unicode de Uso Privado) que aparecen como celda suelta, ej. el
    `` observado junto a la columna de ADTV. Basura conocida, se descarta sin más."""
    texto = texto.strip()
    if not texto:
        return False
    return all(
        0xE000 <= ord(caracter) <= 0xF8FF or 0xF0000 <= ord(caracter) <= 0x10FFFD
        for caracter in texto
    )


def _buscar_ancla_ticker(celdas: list[tuple[int, str]], indice_ticker: int) -> int | None:
    """Posición dentro de `celdas` (no índice de columna) de la celda que arranca una fila de
    datos: cerca de donde el header ubica a `Ticker`, y con forma de ticker.

    Se busca por contenido y no simplemente `celdas[0]`: la última fila de cada página a veces
    llega con una celda extra al principio, en el índice de columna 0, que pdfplumber rellena con
    el bloque de notas metodológicas de más abajo pegado al resto de la fila — el ticker real
    sigue estando un poco más a la derecha, en su índice habitual.
    """
    for posicion, (indice, contenido) in enumerate(celdas):
        if abs(indice - indice_ticker) <= TOLERANCIA and RE_TICKER.match(contenido.strip()):
            return posicion
    return None


def _mapear_fila(
    celdas: list[tuple[int, str]], desde: int, indices_headers: list[int]
) -> list[str | None]:
    """Empareja, en orden, cada header con la celda no vacía más cercana a su índice.

    Avance de dos punteros: como tanto los headers como las celdas están ordenados de izquierda a
    derecha, no hace falta comparar todos contra todos. Un header sin celda cercana queda `None`
    — eso es lo que representa un campo genuinamente ausente en el PDF (GWT-3), no un error de
    mapeo.
    """
    valores: list[str | None] = []
    posicion = desde
    for indice_header in indices_headers:
        while posicion < len(celdas) and celdas[posicion][0] < indice_header - TOLERANCIA:
            posicion += 1
        if posicion < len(celdas) and abs(celdas[posicion][0] - indice_header) <= TOLERANCIA:
            valores.append(celdas[posicion][1])
            posicion += 1
        else:
            valores.append(None)
    return valores


def _es_continuacion(celdas: list[tuple[int, str]], indice_ticker: int) -> bool:
    """Una fila de continuación (segunda línea de un emisor o de un valor a dos líneas) nunca
    trae nada cerca de la columna del ticker: si lo trajera, sería una fila de datos nueva."""
    return not any(abs(indice - indice_ticker) <= TOLERANCIA for indice, _ in celdas)


def _mapear_continuacion(
    celdas: list[tuple[int, str]], indices_headers: list[int]
) -> list[tuple[int, str]] | None:
    """Para cada celda de una fila de continuación, la posición (no el índice de columna) del
    header más cercano. `None` si alguna celda no cae cerca de ningún header — esa fila no es una
    continuación reconocible."""
    aportes: list[tuple[int, str]] = []
    for indice, contenido in celdas:
        mejor_posicion: int | None = None
        mejor_distancia: int | None = None
        for posicion, indice_header in enumerate(indices_headers):
            distancia = abs(indice - indice_header)
            if distancia <= TOLERANCIA and (mejor_distancia is None or distancia < mejor_distancia):
                mejor_posicion = posicion
                mejor_distancia = distancia
        if mejor_posicion is None:
            return None
        aportes.append((mejor_posicion, contenido))
    return aportes


def extraer_tabla_pagina(pagina_pdf: _Pagina, numero_pagina: int) -> TablaPagina | None:
    """Extrae la tabla de una página ya clasificada en filas de datos, con continuaciones
    concatenadas. `None` si la página no tiene ninguna tabla con una fila de headers reconocible
    (celda `Ticker`) — `parser.py` decide si eso es un problema según lo que el catálogo esperaba
    de esa página.
    """
    tabla = _tabla_mayor(pagina_pdf)
    if tabla is None:
        return None
    grilla = tabla.extract()

    indice_header: int | None = None
    celdas_header: list[tuple[int, str]] | None = None
    for indice, fila in enumerate(grilla):
        celdas = _celdas_no_vacias(fila)
        tiene_ticker = any(contenido.strip() == "Ticker" for _, contenido in celdas)
        if tiene_ticker and (celdas_header is None or len(celdas) > len(celdas_header)):
            indice_header = indice
            celdas_header = celdas

    if indice_header is None or celdas_header is None:
        return None

    indices_headers = [indice for indice, _ in celdas_header]
    header_names = [contenido for _, contenido in celdas_header]
    n_headers = len(celdas_header)
    indice_ticker = indices_headers[0]

    filas: list[FilaCruda] = []
    fila_actual: FilaCruda | None = None

    for indice_fila in range(indice_header + 1, len(grilla)):
        celdas = _celdas_no_vacias(grilla[indice_fila])
        if not celdas:
            continue
        if len(celdas) == 1 and _es_glifo_privado(celdas[0][1]):
            continue

        ancla = _buscar_ancla_ticker(celdas, indice_ticker)
        if ancla is not None:
            valores = _mapear_fila(celdas, ancla, indices_headers)
            presentes = sum(1 for valor in valores if valor is not None)
            if presentes * 2 >= n_headers:
                fila_actual = FilaCruda(valores=valores, pagina=numero_pagina)
                filas.append(fila_actual)
                continue

        if fila_actual is not None and _es_continuacion(celdas, indice_ticker):
            aportes = _mapear_continuacion(celdas, indices_headers)
            if aportes is not None:
                for posicion, contenido in aportes:
                    anterior = fila_actual.valores[posicion]
                    nuevo_valor = f"{anterior} {contenido}" if anterior else contenido
                    fila_actual.valores[posicion] = nuevo_valor
                continue

        raise FilaNoReconocida(numero_pagina, indice_fila, celdas)

    return TablaPagina(header_names=header_names, filas=filas)
