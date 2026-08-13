"""La estructura del SIC: en qué eslabón de la cadena productiva está una empresa.

## Qué es esto y por qué no es una interpretación nuestra

El SIC (Standard Industrial Classification) no es una lista plana de códigos: está **organizado en
diez divisiones**, y los dos primeros dígitos de cada código dicen a cuál pertenece. La división es
justamente el eslabón: extraer materia prima, transformarla, distribuirla al por mayor, venderla al
público, o prestar un servicio.

Las diez divisiones y sus rangos salen del **SIC Manual**, que publica OSHA
(`osha.gov/data/sic-manual`) con cada división de la A a la J y los major groups que abarca. Son
taxonomía oficial del gobierno de Estados Unidos, no una agrupación que hayamos armado acá — que es
la diferencia entre decir "Barrick extrae" y opinar sobre Barrick.

## Lo que este módulo NO dice, a propósito

**No dice para qué sirve la materia prima.** Que el cobre alimente la construcción y la
electrificación es cierto y es útil, pero no está en ninguna fuente: es análisis de cadena de
valor. Escribirlo acá sería exactamente lo que la regla 1 prohíbe — presentar una interpretación
con la misma cara que un dato. El módulo llega hasta donde llega la taxonomía y ahí se detiene.

**Un código fuera de todo rango conocido devuelve `None`**, y quien lo muestre declara el faltante.
Nunca se lo empuja a la división más parecida: un SIC que no reconocemos es un dato que no tenemos,
no uno que podamos aproximar.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Division:
    """Un eslabón de la cadena productiva, tal como lo define el SIC Manual."""

    letra: str
    """La letra con que el SIC Manual la identifica (A a J)."""
    nombre: str
    """El nombre oficial, en inglés, tal como lo publica la fuente."""
    eslabon: str
    """Cómo se lee en castellano en la pantalla del asesor. Es traducción del nombre oficial, no
    una categoría nueva: `Mining` es minería y `Manufacturing` es manufactura, y ninguna de las dos
    admite otra lectura."""


# Las diez divisiones con el rango de major groups (los dos primeros dígitos del SIC) que abarca
# cada una. Del SIC Manual de OSHA. Los rangos no son contiguos entre sí a propósito: el manual
# deja huecos (18-19, 68-69, 90) que no pertenecen a ninguna división, y esos códigos caen en
# `None` en vez de asignarse a la vecina.
DIVISIONES: tuple[tuple[int, int, Division], ...] = (
    (1, 9, Division("A", "Agriculture, Forestry, And Fishing", "Producción primaria")),
    (10, 14, Division("B", "Mining", "Extracción")),
    (15, 17, Division("C", "Construction", "Construcción")),
    (20, 39, Division("D", "Manufacturing", "Manufactura")),
    (
        40,
        49,
        Division(
            "E",
            "Transportation, Communications, Electric, Gas, And Sanitary Services",
            "Transporte y servicios públicos",
        ),
    ),
    (50, 51, Division("F", "Wholesale Trade", "Comercio mayorista")),
    (52, 59, Division("G", "Retail Trade", "Comercio minorista")),
    (60, 67, Division("H", "Finance, Insurance, And Real Estate", "Finanzas y seguros")),
    (70, 89, Division("I", "Services", "Servicios")),
    (91, 99, Division("J", "Public Administration", "Administración pública")),
)


def division_de(sic: str | int | None) -> Division | None:
    """En qué eslabón de la cadena está un código SIC. `None` si no se puede afirmar.

    `3571` (Electronic Computers) → Manufactura. `1040` (Gold and Silver Ores) → Extracción.

    Devuelve `None` para un código ausente, ilegible o fuera de todos los rangos del manual. Los
    tres casos son el mismo desde el punto de vista del asesor: **no sabemos**, y así se muestra.
    """
    if sic is None:
        return None
    texto = str(sic).strip()
    if not texto.isdigit():
        return None
    # El SIC llega con y sin ceros a la izquierda según el endpoint: `100` y `0100` son el mismo
    # código de agricultura. Los dos primeros dígitos del código de cuatro son el major group.
    major = int(texto.zfill(4)[:2])
    for desde, hasta, division in DIVISIONES:
        if desde <= major <= hasta:
            return division
    return None
