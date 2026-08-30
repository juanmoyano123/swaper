"""De qué subregión del mundo es un país, según el estándar M49 de la ONU — F-078.

## La fuente, citada

**Estándar**: *Standard Country or Area Codes for Statistical Use (Series M, No. 49)*, División de
Estadística de las Naciones Unidas. Composición geográfica y nombres en español publicados en
<https://unstats.un.org/unsd/methodology/m49/>. Leído el 28/08/2026.

## Por qué leer esto no viola la regla 11

La regla 11 prohíbe traducir un **código propietario de la fuente**: `EXT` de BYMA se muestra `EXT`
porque BYMA no publica en ningún lado qué significa. Un estándar publicado es lo contrario — su
significado *está* publicado, por el organismo que lo define, y leerlo es leer, no interpretar. Es
exactamente el criterio con el que el proyecto ya lee `ARS` y `USD` de ISO 4217, y con el que
`pais_cedear.pais` guarda ISO 3166-1 alfa-2.

Lo que sí sería inventar es una agrupación propia. Por eso el mapa no dice "Europa desarrollada" ni
"mercados emergentes": dice lo que la ONU dice, con el corte que la ONU hace.

## Por qué subregión y no continente

El continente pierde justo lo que el asesor necesita distinguir. Israel y Japón son los dos "Asia";
con la subregión, uno es **Asia occidental** (que es lo que en el mercado se llama Medio Oriente) y
el otro **Asia oriental**. Y del lado americano, la subregión es lo que separa **América del Norte**
de **América Latina y el Caribe** sin que tengamos que decidir nosotros dónde va México — la ONU ya
lo decidió, y lo pone en América Latina y el Caribe.

Ojo con eso último, porque es contraintuitivo y está bien: en M49 México **no** está en América del
Norte. La subregión 021 (Northern America) son Bermudas, Canadá, Estados Unidos, Groenlandia y San
Pedro y Miquelón; México cae en 419 junto con el resto de América Latina. Se respeta el estándar tal
como está en vez de "corregirlo", que sería justamente inventar una agrupación propia.

## El único corte que hay que declarar: África

M49 tiene dos niveles debajo de cada continente —*subregión* y *región intermedia*— y no siempre los
usa igual. En Asia, Europa y Oceanía la subregión ya es fina (Asia occidental, Europa septentrional,
Polinesia); en las Américas también (América del Norte / América Latina y el Caribe, que es
exactamente el corte que este producto necesita). En África, en cambio, la subregión son sólo dos
—África septentrional y **África subsahariana**—, y esa segunda mete a Sudáfrica, Nigeria y Kenia en
una sola bolsa: mucho más gruesa que cualquier otro continente del mismo mapa.

Para África se usa entonces la **región intermedia** de la ONU (África oriental, central, meridional
y occidental). Sigue siendo composición publicada por el mismo estándar, no una agrupación nuestra:
lo único que se elige es a qué nivel del árbol leer, y se elige el que hace comparables las escalas.
Queda declarado acá porque es lo único de este módulo que no sale de aplicar una sola regla.

## Qué no hace este módulo

No se persiste: la región se deriva del país al leer, igual que `division_cadena` se deriva del
código SIC. Es dato derivado y re-derivable, y guardarlo obligaría a mantener sincronizadas dos
copias de la misma verdad.

No convive unificado con `perfil_renta_variable.region_etf`, que es la geografía que declara el
nombre de un ETF (`Brazil`, `EAFE`). Son dos vocabularios distintos y se muestran como valores
distintos a propósito: mapear `Brazil` a "América Latina y el Caribe" sería traducir el nombre del
fondo, y ese nombre no es un código ISO. Ver `app/renta_variable/etfs.py::region_declarada`.
"""

# Cada bloque es una subregión M49, con su código numérico al lado para poder cotejarlo contra la
# publicación de la ONU sin tener que adivinar cuál es cuál. Los nombres de subregión son los que la
# ONU publica en español; los de los países van en el comentario sólo para que el bloque se lea.

# África septentrional (015)
_AFRICA_SEPTENTRIONAL = "África septentrional"
# África subsahariana (202), abierta en sus cuatro regiones intermedias
_AFRICA_ORIENTAL = "África oriental"
_AFRICA_CENTRAL = "África central"
_AFRICA_MERIDIONAL = "África meridional"
_AFRICA_OCCIDENTAL = "África occidental"
# América (019)
_AMERICA_DEL_NORTE = "América del Norte"
_AMERICA_LATINA = "América Latina y el Caribe"
# Asia (142)
_ASIA_CENTRAL = "Asia central"
_ASIA_ORIENTAL = "Asia oriental"
_ASIA_SUDORIENTAL = "Asia sudoriental"
_ASIA_MERIDIONAL = "Asia meridional"
_ASIA_OCCIDENTAL = "Asia occidental"
# Europa (150)
_EUROPA_ORIENTAL = "Europa oriental"
_EUROPA_SEPTENTRIONAL = "Europa septentrional"
_EUROPA_MERIDIONAL = "Europa meridional"
_EUROPA_OCCIDENTAL = "Europa occidental"
# Oceanía (009)
_AUSTRALIA_Y_NUEVA_ZELANDIA = "Australia y Nueva Zelandia"
_MELANESIA = "Melanesia"
_MICRONESIA = "Micronesia"
_POLINESIA = "Polinesia"

_POR_SUBREGION: dict[str, tuple[str, ...]] = {
    # Argelia, Egipto, Libia, Marruecos, Sáhara Occidental, Sudán, Túnez
    _AFRICA_SEPTENTRIONAL: ("DZ", "EG", "EH", "LY", "MA", "SD", "TN"),
    _AFRICA_ORIENTAL: (
        # Burundi, Comoras, Yibuti, Eritrea, Etiopía, Kenia, Madagascar, Malawi, Mauricio, Mayotte,
        # Mozambique, Reunión, Ruanda, Seychelles, Somalia, Sudán del Sur, Uganda, Tanzanía,
        # Zambia, Zimbabwe, y los dos territorios oceánicos que M49 pone acá (IO, TF).
        "BI", "IO", "KM", "DJ", "ER", "ET", "TF", "KE", "MG", "MW", "MU", "YT",
        "MZ", "RE", "RW", "SC", "SO", "SS", "UG", "TZ", "ZM", "ZW",
    ),
    # Angola, Camerún, Rep. Centroafricana, Chad, Congo, Rep. Dem. del Congo, Guinea Ecuatorial,
    # Gabón, Santo Tomé y Príncipe
    _AFRICA_CENTRAL: ("AO", "CM", "CF", "TD", "CG", "CD", "GQ", "GA", "ST"),
    # Botswana, Eswatini, Lesotho, Namibia, Sudáfrica
    _AFRICA_MERIDIONAL: ("BW", "SZ", "LS", "NA", "ZA"),
    _AFRICA_OCCIDENTAL: (
        # Benin, Burkina Faso, Cabo Verde, Côte d'Ivoire, Gambia, Ghana, Guinea, Guinea-Bissau,
        # Liberia, Malí, Mauritania, Níger, Nigeria, Santa Elena, Senegal, Sierra Leona, Togo
        "BJ", "BF", "CV", "CI", "GM", "GH", "GN", "GW", "LR", "ML", "MR", "NE",
        "NG", "SH", "SN", "SL", "TG",
    ),
    # Bermudas, Canadá, Groenlandia, San Pedro y Miquelón, Estados Unidos. **Sin México**: M49 lo
    # ubica en América Latina y el Caribe.
    _AMERICA_DEL_NORTE: ("BM", "CA", "GL", "PM", "US"),
    _AMERICA_LATINA: (
        # Caribe: Anguila, Antigua y Barbuda, Aruba, Bahamas, Barbados, Bonaire, Islas Vírgenes
        # Británicas, Islas Caimán, Cuba, Curaçao, Dominica, República Dominicana, Granada,
        # Guadalupe, Haití, Jamaica, Martinica, Montserrat, Puerto Rico, San Bartolomé, San
        # Cristóbal y Nieves, Santa Lucía, San Martín (fr.), San Vicente y las Granadinas,
        # Sint Maarten, Trinidad y Tabago, Islas Turcas y Caicos, Islas Vírgenes de los EE.UU.
        "AI", "AG", "AW", "BS", "BB", "BQ", "VG", "KY", "CU", "CW", "DM", "DO",
        "GD", "GP", "HT", "JM", "MQ", "MS", "PR", "BL", "KN", "LC", "MF", "VC",
        "SX", "TT", "TC", "VI",
        # América Central: Belice, Costa Rica, El Salvador, Guatemala, Honduras, México, Nicaragua,
        # Panamá
        "BZ", "CR", "SV", "GT", "HN", "MX", "NI", "PA",
        # América del Sur: Argentina, Bolivia, Isla Bouvet, Brasil, Chile, Colombia, Ecuador, Islas
        # Malvinas, Guayana Francesa, Guyana, Paraguay, Perú, Georgias del Sur, Suriname, Uruguay,
        # Venezuela
        "AR", "BO", "BV", "BR", "CL", "CO", "EC", "FK", "GF", "GY", "PY", "PE",
        "GS", "SR", "UY", "VE",
    ),
    # Kazajstán, Kirguistán, Tayikistán, Turkmenistán, Uzbekistán
    _ASIA_CENTRAL: ("KZ", "KG", "TJ", "TM", "UZ"),
    # China, Hong Kong, Macao, Rep. Pop. Dem. de Corea, Japón, Mongolia, Rep. de Corea, Taiwán.
    # Hong Kong y Macao van separados de China porque M49 los lista separados: son áreas propias del
    # estándar, no una subdivisión que estemos inventando.
    _ASIA_ORIENTAL: ("CN", "HK", "MO", "KP", "JP", "MN", "KR", "TW"),
    # Brunei, Camboya, Indonesia, Laos, Malasia, Myanmar, Filipinas, Singapur, Tailandia,
    # Timor-Leste, Viet Nam
    _ASIA_SUDORIENTAL: ("BN", "KH", "ID", "LA", "MY", "MM", "PH", "SG", "TH", "TL", "VN"),
    # Afganistán, Bangladesh, Bhután, India, Irán, Maldivas, Nepal, Pakistán, Sri Lanka
    _ASIA_MERIDIONAL: ("AF", "BD", "BT", "IN", "IR", "MV", "NP", "PK", "LK"),
    _ASIA_OCCIDENTAL: (
        # Armenia, Azerbaiyán, Bahrein, Chipre, Georgia, Iraq, Israel, Jordania, Kuwait, Líbano,
        # Omán, Qatar, Arabia Saudita, Estado de Palestina, Siria, Türkiye, Emiratos Árabes Unidos,
        # Yemen. Es la subregión que el mercado llama "Medio Oriente".
        "AM", "AZ", "BH", "CY", "GE", "IQ", "IL", "JO", "KW", "LB", "OM", "QA",
        "SA", "PS", "SY", "TR", "AE", "YE",
    ),
    # Belarús, Bulgaria, Chequia, Hungría, Polonia, Rep. de Moldova, Rumania, Federación de Rusia,
    # Eslovaquia, Ucrania
    _EUROPA_ORIENTAL: ("BY", "BG", "CZ", "HU", "PL", "MD", "RO", "RU", "SK", "UA"),
    _EUROPA_SEPTENTRIONAL: (
        # Islas Åland, Dinamarca, Estonia, Islas Feroe, Guernsey, Islandia, Irlanda, Isla de Man,
        # Jersey, Letonia, Lituania, Noruega, Svalbard, Suecia, Reino Unido
        "AX", "DK", "EE", "FO", "GG", "IS", "IE", "IM", "JE", "LV", "LT", "NO",
        "SJ", "SE", "GB",
    ),
    _EUROPA_MERIDIONAL: (
        # Albania, Andorra, Bosnia y Herzegovina, Croacia, Gibraltar, Grecia, Santa Sede, Italia,
        # Malta, Montenegro, Macedonia del Norte, Portugal, San Marino, Serbia, Eslovenia, España
        "AL", "AD", "BA", "HR", "GI", "GR", "VA", "IT", "MT", "ME", "MK", "PT",
        "SM", "RS", "SI", "ES",
    ),
    # Austria, Bélgica, Francia, Alemania, Liechtenstein, Luxemburgo, Mónaco, Países Bajos, Suiza
    _EUROPA_OCCIDENTAL: ("AT", "BE", "FR", "DE", "LI", "LU", "MC", "NL", "CH"),
    # Australia, Isla de Navidad, Islas Cocos, Islas Heard y McDonald, Nueva Zelandia, Isla Norfolk
    _AUSTRALIA_Y_NUEVA_ZELANDIA: ("AU", "CX", "CC", "HM", "NZ", "NF"),
    # Fiji, Nueva Caledonia, Papua Nueva Guinea, Islas Salomón, Vanuatu
    _MELANESIA: ("FJ", "NC", "PG", "SB", "VU"),
    # Guam, Kiribati, Islas Marshall, Micronesia, Nauru, Islas Marianas del Norte, Palau, Islas
    # menores alejadas de los EE.UU.
    _MICRONESIA: ("GU", "KI", "MH", "FM", "NR", "MP", "PW", "UM"),
    # Samoa Americana, Islas Cook, Polinesia Francesa, Niue, Pitcairn, Samoa, Tokelau, Tonga,
    # Tuvalu, Wallis y Futuna
    _POLINESIA: ("AS", "CK", "PF", "NU", "PN", "WS", "TK", "TO", "TV", "WF"),
}

REGION_M49: dict[str, str] = {
    pais: subregion for subregion, paises in _POR_SUBREGION.items() for pais in paises
}
"""ISO 3166-1 alfa-2 → subregión geográfica M49, en español y tal como la ONU la publica.

**La Antártida (`AQ`) no está**, y no es un olvido: M49 no le asigna región ni subregión. Un país
ausente de este dict no tiene región, y ese es el resultado — no se lo empuja a la subregión más
cercana, por el mismo motivo por el que `division_de` deja sin eslabón a un código SIC que cae en
un hueco del manual.

Además de ser la tabla de traducción, este dict es el **vocabulario cerrado** con el que
`app/renta_variable/paises.py` valida el CSV curado: un `pais` que no sea una de estas claves se
descarta y se reporta, en vez de cargarse sin poder decir de qué región es.
"""


def region_de(pais: str | None) -> str | None:
    """La subregión M49 de un país ISO 3166-1 alfa-2, o `None`.

    `None` para un país no declarado, para uno que el estándar no ubica (la Antártida) y para
    cualquier código que no sea alfa-2 — nunca una región aproximada. Acepta minúsculas y espacios
    porque el CSV curado se edita a mano en planillas; lo que no hace es adivinar un alfa-3 ni un
    nombre de país escrito en castellano.
    """
    if not pais:
        return None
    return REGION_M49.get(pais.strip().upper())
