"""La cartera del cliente resuelta contra el universo — F-029.

Es la primera feature del Flujo B que toca el backend: F-028 lee el resumen de cuenta en el
navegador y produce posiciones crudas —un ticker escrito y un monto, nada más—, y acá cada ticker
se busca contra el universo del día para saber qué instrumento es.

**Lo que define a la feature es lo que no hace.** Un ticker que no está en el universo no se
aproxima al más parecido y no se deriva por manipulación de sufijos: queda no reconocido, con su
monto, adentro de la cartera y marcado. El antecedente está en `CLAUDE.md`, regla 1 — 121 tickers
inexistentes derivados cortando strings, que hubo que revertir.

## La forma del paquete

    lectura.py     `instrumentos` → filas crudas. Sólo SQL.
    resolucion.py  la búsqueda, los motivos de no resolución y la cobertura. Funciones puras.
    servicio.py    la corrida: universo saneado + instrumentos → `CarteraResuelta`.

Es la misma partición de tres capas de `app/universo/`, y por la misma razón: toda la lógica que
decide algo se prueba sin Postgres y sin red.

## Dónde engancha lo que sigue

**F-030 — Valuación y diagnóstico de la cartera cargada** consume `CarteraResuelta.posiciones`:
cada `PosicionResuelta` ya trae la `EspecieUniverso` con su precio, su segmento y su naturaleza de
tasa, que es lo que hace falta para valorizar y para abrir los rendimientos por unidad. Lo que
F-030 agrega y acá no está: el precio del snapshot vigente con su hora, la renta mes a mes contra
el calendario de F-015, la concentración por emisor y por sector, y el tratamiento de las
posiciones sin monto que acá quedan declaradas pero sin valorizar (`posiciones_sin_monto`).
"""

from app.posiciones.lectura import leer_instrumentos
from app.posiciones.resolucion import (
    CarteraResuelta,
    Cobertura,
    FilaInstrumento,
    MotivoNoResuelta,
    PosicionDeclarada,
    PosicionResuelta,
    clave_de_busqueda,
    indexar_instrumentos,
    resolver,
)
from app.posiciones.servicio import resolver_cartera

__all__ = [
    "CarteraResuelta",
    "Cobertura",
    "FilaInstrumento",
    "MotivoNoResuelta",
    "PosicionDeclarada",
    "PosicionResuelta",
    "clave_de_busqueda",
    "indexar_instrumentos",
    "leer_instrumentos",
    "resolver",
    "resolver_cartera",
]
