"""El universo como servicio: la lógica verificada de `tools/segmentos.py` portada al backend.

Tres features construyen este paquete, en este orden y nunca en paralelo, porque las tres exponen
el mismo módulo y hacerlas a la vez produciría tres envolturas incompatibles:

- **F-010** — sanidad en dos capas (coherencia entre especies y techo por segmento). Hecha.
- **F-011** — deduplicación de especies de liquidación, en doble vista.
- **F-012** — tipo de cambio implícito y normalización de volumen.

El backend **no importa de `tools/`**: la lógica se porta con su docstring citando el origen. El
motor Python sigue leyendo la vista `resumen` sin modificarse, y eso es un criterio de aceptación
verificado (GWT-4 de F-007), no una casualidad que se pueda romper de paso.

## La forma que dejó F-010, y dónde se engancha lo que falta

    lectura.py       la vista `resumen` → filas crudas. Sólo SQL, no decide nada.
    segmentacion.py  con quién es comparable cada especie y en qué unidad está su rendimiento.
    sanidad.py       las dos capas. Funciones puras sobre `EspecieUniverso`, sin base ni reloj.
    servicio.py      la corrida: leer, segmentar, sanear. Devuelve `UniversoSaneado`.

`EspecieUniverso` es el tipo que atraviesa todo el paquete y es donde crece lo que falta: **F-011**
le suma lo que decide el representante de una emisión (duración, completitud de datos, volumen) y
**F-012** las dos puntas del cociente del que sale el tipo de cambio (precio y moneda de
cotización). Las columnas se agregan en `lectura.COLUMNAS` y en el dataclass; el resto del paquete
no se entera.

Las dos features siguientes parten del universo **ya saneado** y no de la lectura cruda: elegir como
representante de una emisión a la especie con el precio mal escalado, o derivar el tipo de cambio de
ese mismo precio, sería propagar el error en vez de contenerlo. Por eso el enganche natural de las
dos es el `UniversoSaneado` que devuelve `sanear_universo`.
"""

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
    "DISCORDANCIA_ESPECIES",
    "NATURALEZA_TASA",
    "TOPE_SANIDAD_SEGMENTO",
    "Descarte",
    "EspecieUniverso",
    "MotivoDescarte",
    "Sanidad",
    "UniversoSaneado",
    "asignar_segmento",
    "evaluar_sanidad",
    "sanear",
    "sanear_universo",
    "segmentar",
]
