"""Fuentes de terceros que alimentan la ficha, siempre como bloque rotulado y siempre degradables.

Vive aparte de `app/ingesta/` a propósito: lo de ingesta entra a nuestra base y se consolida en el
universo; lo de acá se consulta en vivo, se muestra con la fuente y la hora de captura a la vista, y
**nunca se persiste ni se mezcla con nuestro dato**. Si mañana Yahoo desaparece, lo que se pierde es
un bloque declarado vacío, no una columna del universo.
"""

from app.externos.yahoo import (
    MOTIVO_PAUSA,
    BloqueExterno,
    ClienteYahoo,
    CotizacionExterna,
    MontoExterno,
    PerfilExterno,
    PuntoHistorico,
    ResultadoPerfilEmpresa,
    ValuacionExterna,
    bloque_pausado,
    cliente_yahoo,
)

__all__ = [
    "MOTIVO_PAUSA",
    "BloqueExterno",
    "ClienteYahoo",
    "CotizacionExterna",
    "MontoExterno",
    "PerfilExterno",
    "PuntoHistorico",
    "ResultadoPerfilEmpresa",
    "ValuacionExterna",
    "bloque_pausado",
    "cliente_yahoo",
]
