"""De dónde sale el calendario: la tabla `cashflow` y la paridad de la vista `resumen`.

Misma partición que `app/universo/lectura.py` — acá no se decide nada, sólo SQL. Toda la matemática
vive en `cupones.py` y `grilla.py`, que se prueban sin levantar Postgres.

## Por qué se lee el cronograma entero

`valor_tecnico` necesita el **último pago ya ocurrido** de cada bono para saber cuánto residual le
queda vivo y desde cuándo devenga intereses corridos. Un `WHERE payment_date > now()` traería sólo
el futuro y dejaría a todos los bonos arrancando de 100 de residual: los amortizing quedarían
sobrevaluados y su cupón, expresado como fracción del monto invertido, saldría más chico de lo que
es. Son ~6.100 filas: traerlas enteras cuesta menos que equivocarse.

## Por qué de `resumen` se pide sólo la paridad

`tir` y `maturity` también están en la vista, pero **ya llegan con el universo saneado** dentro de
cada `EspecieUniverso` (`rendimiento` y `vencimiento`), y ahí llegan con algo que la columna cruda
no tiene: la naturaleza de su tasa. Una LECAP cotiza por TNA y no por TIR, así que leer `tir` en
crudo y mostrarla como "la TIR del instrumento" sería rotular una TNA nominal en pesos como si fuera
una TIR en dólares — la regla 2 del proyecto en su forma más silenciosa. La paridad es lo único de
la vista que el universo saneado no arrastra, y es lo único que se pide acá.

La paridad se trae **de todas las especies, también de las que no la tienen**. Quién no la tiene es
justamente lo que hay que poder alertar con nombre y apellido, y un `WHERE paridad IS NOT NULL`
borraría del resultado exactamente a los instrumentos sobre los que hay que avisar.
"""

from typing import Any

TABLA_CASHFLOW = "public.cashflow"
VISTA_UNIVERSO = "public.resumen"

# Las columnas del cronograma que la matemática usa. `type` e `interest_rate` no se piden: el
# submarket no interviene en ningún cálculo y la tasa contractual tampoco — lo que se reparte es
# `interest_amount`, que es el monto ya calculado por 100 nominales.
COLUMNAS_CASHFLOW: tuple[str, ...] = (
    "ticker",
    "issue_date",
    "payment_date",
    "capital",
    "interest_amount",
    "residual_value",
    "cash_flow",
)

SQL_CASHFLOW = (
    f"SELECT {', '.join(COLUMNAS_CASHFLOW)} FROM {TABLA_CASHFLOW} ORDER BY ticker, payment_date"
)

SQL_PARIDADES = f"SELECT ticker, paridad FROM {VISTA_UNIVERSO} ORDER BY ticker"


async def leer_cashflow(conn: Any) -> list[dict[str, Any]]:
    """El cronograma completo de pagos, tal como está en la base.

    Los montos vienen **por 100 de valor nominal y en la moneda de emisión del bono**: así los
    publica la fuente y así se guardan. Convertirlos a plata es trabajo de `cupones.py`, que lo hace
    contra la paridad —que es adimensional— y nunca contra un tipo de cambio traído de afuera.
    """
    filas = await conn.fetch(SQL_CASHFLOW)
    return [dict(fila) for fila in filas]


async def leer_paridades(conn: Any) -> list[dict[str, Any]]:
    """La paridad declarada de cada especie del universo, sin filtrar los faltantes."""
    filas = await conn.fetch(SQL_PARIDADES)
    return [dict(fila) for fila in filas]
