"""La tabla oficial de CEDEARs de BYMA: nombre de la empresa, mercado de origen y ratio.

Trae lo que la SEC no da y el asesor necesita para reconocer un papel: el **nombre**, el **ratio de
conversión** (cuántos CEDEARs equivalen a una acción del subyacente) y en qué mercado cotiza ese
subyacente. Son 413 papeles.

## Cómo se llega al archivo

BYMA lo publica como PDF, y **la URL cambia en cada actualización** —lleva un hash del CDN—, así
que no se puede clavar: hay que leer `byma.com.ar/en/products/financial-products/cedears` y sacar
el link de ahí. El parseo del PDF reusa `pdfplumber`, que ya es dependencia por el informe de IAMC.

## Dos cosas que la fuente hace mal, y cómo se las trata

**Está incompleta.** `XPEV` (XPeng) cotiza desde mayo de 2025 —lo anunció la propia BYMA en su
newsroom— y no figura en el PDF del 12/06/2026. No es atraso: es un hueco. Por eso esta lista
**aporta** nombre y ratio donde los tiene y **nunca decide que un papel no existe**: quien la use
completa lo que puede y declara el resto.

**Tiene errores.** El PDF publica "First Trust NASDAQ Cybersecurity" con el código `XLU`, que es el
del ETF de Utilities — y también publica `XLU` correctamente para "Utilities Select Sector SPDR
Fund". Un código con dos nombres distintos **no se resuelve eligiendo uno**: no hay forma de saber
cuál es el bueno, así que el código entero se descarta y se declara el conflicto. Es el mismo
criterio que `condiciones/corrida.py` aplica a los conflictos del artefacto curado.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from app.ingesta.alertas import Alerta, Severidad

NOMBRE_FUENTE = "BYMA (tabla de CEDEARs)"

URL_PAGINA = "https://www.byma.com.ar/en/products/financial-products/cedears"

CODIGO_CEDEAR_EN_CONFLICTO = "cedear_en_conflicto"

# Nombre · código · mercado de origen · ratio, que es como el PDF arma cada renglón. El mercado se
# enumera en vez de aceptar cualquier palabra: es lo que separa un renglón de la tabla de una línea
# de texto suelta del documento, y sin esa ancla el parseo levanta títulos y notas al pie.
MERCADOS = (
    "NASDAQ",
    "NYSE",
    "B3",
    "XETRA",
    "BATS",
    "LSE",
    "TSX",
    "AMEX",
    "CBOE",
    "OTC",
)
_RENGLON = re.compile(
    rf"^(?P<nombre>.+?)\s+(?P<codigo>[A-Z0-9.]{{1,8}})\s+"
    rf"(?P<mercado>(?:{'|'.join(MERCADOS)})[A-Za-z ]*?)\s+"
    rf"(?P<ratio>\d+\s*:\s*\d+)\s*$"
)


@dataclass(frozen=True, slots=True)
class CedearDeByma:
    """Un renglón de la tabla, tal como BYMA lo publica. Nada se normaliza ni se traduce."""

    codigo: str
    nombre: str
    mercado: str
    ratio: str


@dataclass(frozen=True, slots=True)
class ResultadoLista:
    """Lo que se pudo leer y lo que quedó en conflicto."""

    cedears: dict[str, CedearDeByma] = field(default_factory=dict)
    alertas: list[Alerta] = field(default_factory=list)


def link_del_pdf(html: str) -> str | None:
    """La URL del PDF dentro de la página de BYMA, o `None` si la página cambió de forma.

    Se busca un `.pdf` cuyo nombre mencione CEDEARs: la página tiene otros PDF (reglamentos,
    comunicados) y agarrar el primero que aparezca sería traer cualquier cosa.
    """
    for url in re.findall(r'href="([^"]+\.pdf[^"]*)"', html, re.I):
        if "cedear" in url.lower():
            return url
    return None


def parsear_lista(texto_por_pagina: list[str]) -> ResultadoLista:
    """Los renglones de la tabla, con los códigos en conflicto declarados y fuera.

    Recibe el texto ya extraído de cada página —no el PDF— para que esto se pueda probar sin
    archivo, igual que `iamc/parser.py` separa la extracción del análisis.
    """
    por_codigo: dict[str, list[CedearDeByma]] = defaultdict(list)
    for pagina in texto_por_pagina:
        for linea in pagina.split("\n"):
            encontrado = _RENGLON.match(linea.strip())
            if encontrado is None:
                continue
            fila = CedearDeByma(
                codigo=encontrado["codigo"].upper(),
                nombre=encontrado["nombre"].strip(),
                mercado=encontrado["mercado"].strip(),
                ratio=encontrado["ratio"].replace(" ", ""),
            )
            por_codigo[fila.codigo].append(fila)

    cedears: dict[str, CedearDeByma] = {}
    conflictos: list[tuple[str, list[str]]] = []
    for codigo, filas in por_codigo.items():
        nombres = {f.nombre for f in filas}
        if len(nombres) > 1:
            conflictos.append((codigo, sorted(nombres)))
            continue
        cedears[codigo] = filas[0]

    alertas = [_alerta_de_conflicto(conflictos)] if conflictos else []
    return ResultadoLista(cedears=cedears, alertas=alertas)


def _alerta_de_conflicto(conflictos: list[tuple[str, list[str]]]) -> Alerta:
    """Un código que la fuente publica con dos nombres distintos. Se descartan los dos."""
    muestra = "; ".join(f"{codigo} ({' / '.join(nombres)})" for codigo, nombres in conflictos[:3])
    return Alerta(
        codigo=CODIGO_CEDEAR_EN_CONFLICTO,
        mensaje=(
            f"{len(conflictos)} código(s) aparecen en la tabla de BYMA con más de un nombre y "
            f"quedan sin clasificar: {muestra}. No se elige uno: no hay forma de saber cuál es el "
            f"correcto."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=None,
        detalle={"codigos": [c for c, _ in conflictos]},
    )


def texto_de_pdf(contenido: bytes) -> list[str]:
    """El texto de cada página del PDF. Import diferido: `pdfplumber` tarda en cargar y sólo hace
    falta cuando de verdad hay un PDF que abrir."""
    import io

    import pdfplumber

    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        return [(pagina.extract_text() or "") for pagina in pdf.pages]


def como_dict(resultado: ResultadoLista) -> dict[str, Any]:
    """Para el resumen de una corrida: cuántos se leyeron y qué quedó declarado."""
    return {
        "cedears": len(resultado.cedears),
        "alertas": [a.como_dict() for a in resultado.alertas],
    }
