"""Valida y tipa las filas del Excel de cashflow contra el contrato de 9 columnas.

El contrato son las columnas que `guardar_cashflow_completo()` del motor viejo exigía para poder
separar renta de amortización: identidad (`ticker`, `type`), fechas (`issue_date`,
`payment_date`) y los cinco montos (`capital`, `interest_rate`, `interest_amount`,
`residual_value`, `cash_flow`). Si falta cualquiera de las nueve, el cashflow no sirve para
proyectar cupones y se declara `formato_inesperado` en vez de entregarlo a medias.

El feed real (verificado 06/08/2026) trae además tres columnas no documentadas en ningún lado:
`days_convention`, `theoretical_payment_date`, `theoretical_days_before`. Viajan como passthrough,
tal como llegan, sin tipado propio ni cobertura medida: descartarlas tiraría dato que la fuente
declaró (`days_convention` es potencialmente valioso para F-015), pero prometerlas a contrato
exigiría entender una semántica que Docta no documenta — eso sería un juicio inventado. Se deja la
decisión de promoverlas a quien consolida (F-007), con el dato a la vista.
"""

from datetime import date, datetime

import pandas as pd

COLUMNAS_CONTRACTUALES = (
    "ticker",
    "type",
    "issue_date",
    "payment_date",
    "capital",
    "interest_rate",
    "interest_amount",
    "residual_value",
    "cash_flow",
)

_COLUMNAS_TEXTO = ("ticker", "type")
_COLUMNAS_FECHA = ("issue_date", "payment_date")
_COLUMNAS_MONTO = ("capital", "interest_rate", "interest_amount", "residual_value", "cash_flow")


def columnas_faltantes(df: pd.DataFrame) -> list[str]:
    """Cuáles de las nueve columnas contractuales no vinieron en el Excel."""
    return [columna for columna in COLUMNAS_CONTRACTUALES if columna not in df.columns]


def normalizar_filas(df: pd.DataFrame) -> list[dict[str, object]]:
    """Tipa las nueve columnas contractuales; el resto de columnas viaja intacto (passthrough).

    Se asume que `df` ya pasó `columnas_faltantes()` sin faltantes: esta función no vuelve a
    validar el contrato, sólo tipa lo que sabe que está.
    """
    filas = []
    for registro in df.to_dict(orient="records"):
        fila = dict(registro)
        for columna in _COLUMNAS_TEXTO:
            fila[columna] = _a_texto(fila.get(columna))
        for columna in _COLUMNAS_FECHA:
            fila[columna] = _a_fecha(fila.get(columna))
        for columna in _COLUMNAS_MONTO:
            fila[columna] = _a_monto(fila.get(columna))
        filas.append(fila)
    return filas


def _es_nulo(valor: object) -> bool:
    """`pd.isna` sobre un escalar cualquiera: cubre `None`, `NaN` y `NaT` en una sola llamada."""
    resultado = pd.isna(valor)
    return bool(resultado)


def _a_texto(valor: object) -> str | None:
    if _es_nulo(valor):
        return None
    texto = str(valor).strip()
    return texto or None


def _a_fecha(valor: object) -> date | None:
    if _es_nulo(valor):
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    # Verificado contra el feed real (06/08/2026): `issue_date` y `payment_date` no llegan como
    # datetime de pandas sino como texto ISO ("2020-09-04") — pandas no siempre infiere el tipo
    # de una columna de fechas en un Excel ajeno. Se parsea en vez de descartar el dato.
    return pd.to_datetime(valor).date()


def _a_monto(valor: object) -> float | None:
    """`NaN` → `None`, pero un `0.0` real se conserva: un pago de capital 0 en una fecha de cupón
    puro es dato, no un hueco."""
    if _es_nulo(valor):
        return None
    if isinstance(valor, str):
        # Verificado contra el feed real (06/08/2026): `capital` llega como texto en las 6.150
        # filas, y al menos un valor trae un artefacto de escape de Excel para un retorno de
        # carro incrustado en la celda ("3.125_x000d_\n"). Se lo saca antes de convertir: es
        # ruido de formato alrededor de un número, no una ambigüedad sobre qué número es — no
        # aplica la regla de "nunca inventar un dato", que es sobre no completar lo que falta.
        valor = valor.replace("_x000D_", "").replace("_x000d_", "").strip()
    return float(valor)
