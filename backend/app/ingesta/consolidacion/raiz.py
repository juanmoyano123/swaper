"""La raíz de emisión: qué especies son el mismo bono.

AL30, AL30D y AL30C son la misma emisión cotizando en pesos, en dólar MEP y en cable. Ley, moneda
de pago y estructura de cupón son atributos de la emisión, así que se cruzan por acá; el precio, la
punta y la moneda de cotización son de cada especie y nunca se cruzan.

Es una copia deliberada de `raiz_emision` en `tools/segmentos.py` —el backend no importa de
`tools/`— y las dos tienen que seguir coincidiendo: si divergen, el universo que escribe el backend
deja de agruparse como lo agrupa el motor que lo lee. La única diferencia es la firma: allá opera
sobre una Series de pandas, acá sobre un `str`.

Sobre lo que NO se corta. BYMA publica también AL30X, AL30Y y AL30Z: un segundo trío del mismo bono,
mismo vencimiento y mismas monedas. Cortar la X para llegar a AL30 sería derivar un ticker de otro
por manipulación de strings, que es exactamente el error que ya costó revertir 121 tickers
inventados. Esas especies quedan sin cronograma, sin clase y por lo tanto fuera del universo —que
es donde estuvieron siempre: el consolidado histórico nunca las tuvo.
"""


def raiz_emision(ticker: str) -> str:
    """MR46O / MR46D / MR46C → MR46. Las tres especies del mismo bono.

    El guardia de longitud existe para no comerse la última letra de un ticker corto que termina
    en O, D o C por casualidad y no por ser una especie de liquidación.
    """
    if len(ticker) >= 4 and ticker[-1] in ("O", "D", "C"):
        return ticker[:-1]
    return ticker
