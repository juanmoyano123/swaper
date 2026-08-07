"""El universo como servicio: la lógica verificada de `tools/segmentos.py` portada al backend.

Tres features construyen este paquete, en este orden y nunca en paralelo, porque las tres exponen
el mismo módulo y hacerlas a la vez produciría tres envolturas incompatibles:

- **F-010** — sanidad en dos capas (coherencia entre especies y techo por segmento). Hecha.
- **F-011** — deduplicación de especies de liquidación, en doble vista. Hecha.
- **F-012** — tipo de cambio implícito y normalización de volumen.

El backend **no importa de `tools/`**: la lógica se porta con su docstring citando el origen. El
motor Python sigue leyendo la vista `resumen` sin modificarse, y eso es un criterio de aceptación
verificado (GWT-4 de F-007), no una casualidad que se pueda romper de paso.

## La forma que dejó F-010, y dónde se engancha lo que falta

    lectura.py       la vista `resumen` → filas crudas. Sólo SQL, no decide nada.
    segmentacion.py  con quién es comparable cada especie y en qué unidad está su rendimiento.
    sanidad.py       las dos capas. Funciones puras sobre `EspecieUniverso`, sin base ni reloj.
    emisiones.py     la doble vista: qué especies son el mismo bono y cuál lo representa.
    servicio.py      la corrida: leer, segmentar, sanear. Devuelve `UniversoSaneado`.

`EspecieUniverso` es el tipo que atraviesa todo el paquete y es donde crece lo que falta. **F-011**
ya le sumó lo que decide el representante de una emisión: la duración —el chequeo que dice si un
grupo de especies es de verdad un solo bono— y los cuatro campos cuya presencia mide la completitud
del dato. **F-012** le va a sumar las dos puntas del cociente del que sale el tipo de cambio (precio
y moneda de cotización) y el volumen. Las columnas se agregan en `lectura.COLUMNAS` y en el
dataclass; el resto del paquete no se entera.

**El desempate por volumen del representante quedó abierto a propósito**, y es lo primero que F-012
tiene que cerrar: el punto de enganche es `emisiones._prioridad`, y el porqué está en el docstring
de `emisiones.py`. En una frase: el volumen crudo hace ganar siempre a la especie en pesos por el
tipo de cambio y no por liquidez, así que hasta que exista el volumen normalizado no se desempata
por volumen — se desempata por ticker, que es arbitrario pero no miente.

Las features que envuelven este universo parten del universo **ya saneado** y no de la lectura
cruda: elegir como representante de una emisión a la especie con el precio mal escalado, o derivar
el tipo de cambio de ese mismo precio, sería propagar el error en vez de contenerlo. Por eso el
enganche de las dos es el `UniversoSaneado` que devuelve `sanear_universo`.
"""

from app.universo.emisiones import (
    CAMPOS_COMPLETITUD,
    TOLERANCIA_DURACION,
    Emision,
    UniversoDeduplicado,
    deduplicar,
)
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
    "NATURALEZA_TASA",
    "TOLERANCIA_DURACION",
    "TOPE_SANIDAD_SEGMENTO",
    "Descarte",
    "Emision",
    "EspecieUniverso",
    "MotivoDescarte",
    "Sanidad",
    "UniversoDeduplicado",
    "UniversoSaneado",
    "asignar_segmento",
    "deduplicar",
    "evaluar_sanidad",
    "sanear",
    "sanear_universo",
    "segmentar",
]
