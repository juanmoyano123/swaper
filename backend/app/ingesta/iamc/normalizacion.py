"""Celda cruda del PDF de IAMC → valor tipado.

Funciones puras: nunca deciden qué hacer con un faltante, sólo devuelven el valor tipado o
`None` cuando la celda no se puede interpretar. Quien orquesta (`parser.py`) es quien sabe si ese
`None` corresponde a una celda vacía (un faltante común, que la cobertura ya cuenta) o a una
celda con contenido que no se pudo leer (la regla 1 del proyecto: se alerta con el valor crudo,
nunca se adivina).

Todo lo que sigue está calibrado contra el informe real del 05/08/2026
(`fuentes/iamc-deuda-corporativa-2026-08-05.pdf`), no contra un formato "esperable": los números
vienen en formato anglosajón (`2,064.08M`, `7.92%`) y las fechas en `dd-MMM-yy` con meses en
inglés (`30-Jun-26`), porque así es como IAMC exporta el reporte desde Power BI.
"""

import re
from datetime import date

MAPA_LEY = {"ARG": "Ley Argentina", "NY": "Ley N.Y."}
"""Mismo criterio que `tools/merge_condiciones.py`: un código fuera de este mapa se reporta y no
se traduce. El episodio que motiva la regla —un código que terminó traducido como "Ley Inglesa",
una categoría que no existe— es exactamente el que esta tabla cerrada evita repetir.
"""

_MESES_INGLES = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
"""Explícito y no delegado a `locale`: el proceso puede correr con cualquier locale del sistema,
y `strptime("%b")` con meses en inglés no es fiable si el locale no es `en_US`."""

_RE_FECHA = re.compile(r"^(\d{2})-([A-Za-z]{3})-(\d{2})$")


def _numero(crudo: str | None) -> float | None:
    """`"2,064.08M"` → `2064080.0`; `"7.92%"` → `7.92`; `"156250.0"` → `156250.0`; vacío → `None`.

    Los porcentajes se entregan en puntos porcentuales (7.92, no 0.0792): así los reporta IAMC y
    así se comparan campo a campo, sin reescalar. `M` es millones. La coma es separador de miles
    y se descarta; el punto es el separador decimal, como corresponde al formato anglosajón real
    del export, no al que sería esperable en un informe local (CLAUDE.md, regla 1: se normaliza
    lo que la fuente trae, no lo que se supondría que trae).
    """
    if crudo is None:
        return None
    texto = crudo.strip()
    if not texto:
        return None

    multiplicador = 1.0
    if texto.endswith("%"):
        texto = texto[:-1]
    elif texto.endswith("M"):
        texto = texto[:-1]
        multiplicador = 1_000_000.0

    texto = texto.replace(",", "")
    try:
        return float(texto) * multiplicador
    except ValueError:
        return None


def _fecha(crudo: str | None) -> date | None:
    """`"30-Jun-26"` → `date(2026, 6, 30)`. Año de dos dígitos se lee como 20xx."""
    if crudo is None:
        return None
    coincidencia = _RE_FECHA.match(crudo.strip())
    if coincidencia is None:
        return None

    dia, mes_texto, anio_corto = coincidencia.groups()
    mes = _MESES_INGLES.get(mes_texto.lower())
    if mes is None:
        return None

    try:
        return date(2000 + int(anio_corto), mes, int(dia))
    except ValueError:
        return None


def _texto(crudo: str | None) -> str | None:
    """Colapsa saltos de línea internos (celdas envueltas a dos líneas) en un espacio simple."""
    if crudo is None:
        return None
    limpio = re.sub(r"\s+", " ", crudo).strip()
    return limpio or None


def _ley(codigo: str | None) -> str | None:
    """Traduce el código de ley de una columna (`"ARG"`, `"NY"`) a su forma canónica.

    Un código fuera de `MAPA_LEY` devuelve `None`: la persona que llama es quien decide si eso
    amerita una alerta (`formato_inesperado`, con el valor crudo adentro).
    """
    if codigo is None:
        return None
    return MAPA_LEY.get(codigo.strip().upper())
