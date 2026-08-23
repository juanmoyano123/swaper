"""Conversión de celda cruda de openpyxl a valor tipado, para la planilla de CAFCI.

openpyxl ya entrega tipos nativos para una celda numérica (`float`/`int`) — a diferencia del PDF de
IAMC, acá no hay texto que parsear a número. Lo que sí llega como texto son las fechas: la fuente las
publica como cadena `dd/mm/aa`, no como celda de fecha de Excel (verificado el 23/08/2026: `type(ws
["E12"].value) is str`).
"""

from datetime import date, datetime


def texto(valor: object) -> str | None:
    """Recorta espacios; la cadena vacía es faltante. No se normaliza el contenido (regla 11): lo
    que la fuente escribe se guarda tal cual, incluidos los códigos que no se entienden (`USB`)."""
    if valor is None:
        return None
    if isinstance(valor, str):
        limpio = valor.strip()
        return limpio or None
    return str(valor)


def entero(valor: object) -> int | None:
    """`Plazo Liq.` y los códigos: enteros, incluidos los centinelas (999, 9999, 99999, -1) — se
    guardan tal cual, nunca se traducen a "no aplica" (regla 11)."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        return int(valor)
    if isinstance(valor, str):
        limpio = valor.strip()
        try:
            return int(float(limpio)) if limpio else None
        except ValueError:
            return None
    return None


def numero(valor: object) -> float | None:
    """Cualquier columna numérica de la planilla (VCP, variaciones, patrimonio, comisiones…)."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, int | float):
        return float(valor)
    if isinstance(valor, str):
        limpio = valor.strip()
        if not limpio:
            return None
        try:
            return float(limpio)
        except ValueError:
            return None
    return None


def fecha(valor: object) -> date | None:
    """`dd/mm/aa` de la fuente, con el año de dos dígitos resuelto por la convención estándar de
    `strptime('%y')`: 00-68 → 20xx, 69-99 → 19xx. No es una interpretación propia del proyecto —
    es la regla documentada de la librería estándar—, y es la que explica fondos con fecha
    `03/06/04` (2004: fondos que dejaron de reportar, no un error de tipeo).

    También acepta un `datetime`/`date` nativo, por si una corrida futura de la fuente cambia el
    formato de celda de texto a fecha real.
    """
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        limpio = valor.strip()
        if not limpio:
            return None
        try:
            return datetime.strptime(limpio, "%d/%m/%y").date()
        except ValueError:
            return None
    return None
