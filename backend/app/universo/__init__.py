"""El universo como servicio: la lógica verificada de `tools/segmentos.py` portada al backend.

Tres features construyen este paquete, en este orden y nunca en paralelo, porque las tres exponen
el mismo módulo y hacerlas a la vez produciría tres envolturas incompatibles:

- **F-010** — sanidad en dos capas (coherencia entre especies y techo por segmento). Hecha.
- **F-011** — deduplicación de especies de liquidación, en doble vista. Hecha.
- **F-012** — tipo de cambio implícito y normalización de volumen. Hecha: cierra el Ciclo 1.

El backend **no importa de `tools/`**: la lógica se porta con su docstring citando el origen. El
motor Python sigue leyendo la vista `resumen` sin modificarse, y eso es un criterio de aceptación
verificado (GWT-4 de F-007), no una casualidad que se pueda romper de paso.

## La forma del paquete

    lectura.py       la vista `resumen` (más la moneda de `instrumentos`) → filas crudas. Sólo SQL.
    segmentacion.py  con quién es comparable cada especie y en qué unidad está su rendimiento.
    sanidad.py       las dos capas. Funciones puras sobre `EspecieUniverso`, sin base ni reloj.
    cambio.py        el tipo de cambio implícito, el volumen en dólares y el contraste. Puro.
    indice.py        de dónde sale el `index-price` del contraste. Lo único que toca la red.
    emisiones.py     la doble vista: qué especies son el mismo bono y cuál lo representa.
    servicio.py      la corrida: leer, segmentar, derivar el cambio, sanear. → `UniversoSaneado`.

`EspecieUniverso` es el tipo que atraviesa todo el paquete y es donde creció cada feature. **F-011**
le sumó lo que decide el representante de una emisión: la duración —el chequeo que dice si un grupo
de especies es de verdad un solo bono— y los cuatro campos cuya presencia mide la completitud del
dato. **F-012** le sumó las dos puntas de la comparación de liquidez: el precio del que sale el tipo
de cambio, el volumen, la moneda declarada en la que están los dos, y el volumen ya en dólares.

**El desempate por volumen del representante, que F-011 dejó abierto, está cerrado**: `_prioridad`
ordena por sanidad, completitud, `volumen_usd` y ticker, en ese orden. Lo que sigue abierto es otra
cosa y está declarado en `emisiones.py`: 146 de 431 emisiones tienen rendimiento publicado en una
especie que no es la que las representa, y resolverlo requiere un criterio de dominio que nadie
decidió todavía.

Las features que envuelven este universo parten del universo **ya saneado** y no de la lectura
cruda: elegir como representante de una emisión a la especie con el precio mal escalado, o derivar
el tipo de cambio de ese mismo precio, sería propagar el error en vez de contenerlo. Por eso el
enganche de las dos es el `UniversoSaneado` que devuelve `sanear_universo`.
"""

from app.universo.cambio import (
    DISPERSION_ACEPTABLE,
    MIN_PARES_FX,
    TOLERANCIA_CONTRASTE,
    Contraste,
    TipoDeCambio,
    cotiza_en_dolares,
    derivar_tipo_de_cambio,
    normalizar_volumen,
)
from app.universo.emisiones import (
    CAMPOS_COMPLETITUD,
    TOLERANCIA_DURACION,
    Emision,
    UniversoDeduplicado,
    deduplicar,
)
from app.universo.indice import leer_indices
from app.universo.sanidad import (
    DISCORDANCIA_ESPECIES,
    TOPE_SANIDAD_SEGMENTO,
    Descarte,
    MotivoDescarte,
    Sanidad,
    evaluar_sanidad,
)
from app.universo.segmentacion import (
    NATURALEZA_TASA,
    EspecieUniverso,
    asignar_segmento,
    segmentar,
)
from app.universo.servicio import UniversoSaneado, sanear, sanear_universo

__all__ = [
    "CAMPOS_COMPLETITUD",
    "DISCORDANCIA_ESPECIES",
    "DISPERSION_ACEPTABLE",
    "MIN_PARES_FX",
    "NATURALEZA_TASA",
    "TOLERANCIA_CONTRASTE",
    "TOLERANCIA_DURACION",
    "TOPE_SANIDAD_SEGMENTO",
    "Contraste",
    "Descarte",
    "Emision",
    "EspecieUniverso",
    "MotivoDescarte",
    "Sanidad",
    "TipoDeCambio",
    "UniversoDeduplicado",
    "UniversoSaneado",
    "asignar_segmento",
    "cotiza_en_dolares",
    "deduplicar",
    "derivar_tipo_de_cambio",
    "evaluar_sanidad",
    "leer_indices",
    "normalizar_volumen",
    "sanear",
    "sanear_universo",
    "segmentar",
]
