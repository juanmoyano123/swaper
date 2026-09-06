"""La estructura del SIC: en qué eslabón de la cadena productiva está una empresa, y el nombre
oficial de cada major group.

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

## Los nombres de major group, y por qué no son la traducción curada de F-079

`titulo_major_group_de` trae el nombre oficial del major group (`"73"` → `"Business Services"`),
tal como lo publica el mismo SIC Manual de OSHA que ya arma `DIVISIONES` — no de memoria, se copió
del listado publicado en `osha.gov/data/sic-manual`. Es un catálogo público y fijo (83 valores, en
inglés), así que traerlo no es interpretar un código propietario (regla 11): es leer un estándar,
igual que ya hace `sic_titulo` con el título de 4 dígitos que publica la SEC.

**No reemplaza** el curado en español de `app/renta_variable/sic_es.py` — ese sigue siendo el que
necesita validación del dueño del producto antes de cargarse, porque traducir "Business Services" a
un rótulo en español es una decisión de producto (¿"Servicios empresariales"? ¿"Servicios B2B"?),
no una lectura mecánica. Esto es sólo el escalón anterior: mostrar el nombre real en inglés en vez
del código pelado mientras esa traducción no existe, el mismo criterio que ya usa `sic_titulo`."""

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


def major_group_de(sic: str | int | None) -> str | None:
    """El major group SIC de dos dígitos (`"01"`, `"73"`) de un código, o `None`.

    Es el eslabón intermedio de la escalera SIC — más fino que la división (10 valores) y más
    grueso que el rubro (el código de 4 dígitos entero, ~120 valores presentes). F-079 lo usa como
    eje de "sector" con traducción curada al español (`app/renta_variable/sic_es.py::sector_de`).

    `None` para un código ausente, ilegible (no numérico) o con menos de dos dígitos — no hay major
    group que afirmar en esos casos, igual que `division_de` no afirma división.
    """
    if sic is None:
        return None
    texto = str(sic).strip()
    if not texto.isdigit() or len(texto) < 2:
        # Un solo dígito no alcanza: `"1"` podría ser `"01"` con el cero recortado o un código
        # roto, y las dos lecturas son igual de una adivinanza. El SIC real siempre tiene el major
        # group entero (2 dígitos) aunque el código completo pierda ceros a la izquierda.
        return None
    # El SIC llega con y sin ceros a la izquierda según el endpoint: `100` y `0100` son el mismo
    # código de agricultura. Los dos primeros dígitos del código de cuatro son el major group.
    return texto.zfill(4)[:2]


# Los 83 major groups del SIC Manual de OSHA, con su nombre oficial en inglés tal como lo publica
# `osha.gov/data/sic-manual`. Los huecos (18-19, 68-69, 90) no están definidos por el Manual y no
# entran acá, igual que no entran en el rango de ninguna `Division`.
MAJOR_GROUPS: dict[str, str] = {
    "01": "Agricultural Production Crops",
    "02": "Agriculture Production Livestock And Animal Specialties",
    "07": "Agricultural Services",
    "08": "Forestry",
    "09": "Fishing, Hunting, And Trapping",
    "10": "Metal Mining",
    "12": "Coal Mining",
    "13": "Oil And Gas Extraction",
    "14": "Mining And Quarrying Of Nonmetallic Minerals, Except Fuels",
    "15": "Building Construction General Contractors And Operative Builders",
    "16": "Heavy Construction Other Than Building Construction Contractors",
    "17": "Construction Special Trade Contractors",
    "20": "Food And Kindred Products",
    "21": "Tobacco Products",
    "22": "Textile Mill Products",
    "23": "Apparel And Other Finished Products Made From Fabrics And Similar Materials",
    "24": "Lumber And Wood Products, Except Furniture",
    "25": "Furniture And Fixtures",
    "26": "Paper And Allied Products",
    "27": "Printing, Publishing, And Allied Industries",
    "28": "Chemicals And Allied Products",
    "29": "Petroleum Refining And Related Industries",
    "30": "Rubber And Miscellaneous Plastics Products",
    "31": "Leather And Leather Products",
    "32": "Stone, Clay, Glass, And Concrete Products",
    "33": "Primary Metal Industries",
    "34": "Fabricated Metal Products, Except Machinery And Transportation Equipment",
    "35": "Industrial And Commercial Machinery And Computer Equipment",
    "36": "Electronic And Other Electrical Equipment And Components, Except Computer Equipment",
    "37": "Transportation Equipment",
    "38": (
        "Measuring, Analyzing, And Controlling Instruments; Photographic, Medical And Optical "
        "Goods; Watches And Clocks"
    ),
    "39": "Miscellaneous Manufacturing Industries",
    "40": "Railroad Transportation",
    "41": "Local And Suburban Transit And Interurban Highway Passenger Transportation",
    "42": "Motor Freight Transportation And Warehousing",
    "43": "United States Postal Service",
    "44": "Water Transportation",
    "45": "Transportation By Air",
    "46": "Pipelines, Except Natural Gas",
    "47": "Transportation Services",
    "48": "Communications",
    "49": "Electric, Gas, And Sanitary Services",
    "50": "Wholesale Trade-durable Goods",
    "51": "Wholesale Trade-non-durable Goods",
    "52": "Building Materials, Hardware, Garden Supply, And Mobile Home Dealers",
    "53": "General Merchandise Stores",
    "54": "Food Stores",
    "55": "Automotive Dealers And Gasoline Service Stations",
    "56": "Apparel And Accessory Stores",
    "57": "Home Furniture, Furnishings, And Equipment Stores",
    "58": "Eating And Drinking Places",
    "59": "Miscellaneous Retail",
    "60": "Depository Institutions",
    "61": "Non-depository Credit Institutions",
    "62": "Security And Commodity Brokers, Dealers, Exchanges, And Services",
    "63": "Insurance Carriers",
    "64": "Insurance Agents, Brokers, And Service",
    "65": "Real Estate",
    "67": "Holding And Other Investment Offices",
    "70": "Hotels, Rooming Houses, Camps, And Other Lodging Places",
    "72": "Personal Services",
    "73": "Business Services",
    "75": "Automotive Repair, Services, And Parking",
    "76": "Miscellaneous Repair Services",
    "78": "Motion Pictures",
    "79": "Amusement And Recreation Services",
    "80": "Health Services",
    "81": "Legal Services",
    "82": "Educational Services",
    "83": "Social Services",
    "84": "Museums, Art Galleries, And Botanical And Zoological Gardens",
    "86": "Membership Organizations",
    "87": "Engineering, Accounting, Research, Management, And Related Services",
    "88": "Private Households",
    "89": "Miscellaneous Services",
    "91": "Executive, Legislative, And General Government, Except Finance",
    "92": "Justice, Public Order, And Safety",
    "93": "Public Finance, Taxation, And Monetary Policy",
    "94": "Administration Of Human Resource Programs",
    "95": "Administration Of Environmental Quality And Housing Programs",
    "96": "Administration Of Economic Programs",
    "97": "National Security And International Affairs",
    "99": "Nonclassifiable Establishments",
}


def titulo_major_group_de(sic: str | int | None) -> str | None:
    """El nombre oficial del major group SIC (`"Business Services"` para `"73"`), del SIC Manual de
    OSHA. `None` si no hay major group afirmable (`major_group_de`) o si cae en uno de los huecos
    que el Manual no define (18-19, 68-69, 90) — mismo criterio que `division_de`."""
    grupo = major_group_de(sic)
    return MAJOR_GROUPS.get(grupo) if grupo is not None else None


def division_de(sic: str | int | None) -> Division | None:
    """En qué eslabón de la cadena está un código SIC. `None` si no se puede afirmar.

    `3571` (Electronic Computers) → Manufactura. `1040` (Gold and Silver Ores) → Extracción.

    Devuelve `None` para un código ausente, ilegible o fuera de todos los rangos del manual. Los
    tres casos son el mismo desde el punto de vista del asesor: **no sabemos**, y así se muestra.
    """
    grupo = major_group_de(sic)
    if grupo is None:
        return None
    major = int(grupo)
    for desde, hasta, division in DIVISIONES:
        if desde <= major <= hasta:
            return division
    return None
