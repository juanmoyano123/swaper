"""Dato curado por especie: semilla, herencia entre especies y conflictos (F-009).

Reemplaza a `tools/merge_condiciones.py` y `tools/aplicar_sectores.py` conservando su lógica. Vive
en su propio paquete y no dentro de `ingesta/` porque no es ingesta: no hay fuente que consultar.
El CSV curado de 823 tickers no tiene origen vivo —se rescató del universo consolidado después de
que se borraran los archivos originales— y el proyecto lo trata como irrecuperable.

Superficie pública mínima, igual que la consolidación: `sembrar` es la corrida completa (leer,
resolver, escribir, medir); `resolver` es la parte pura, expuesta porque es donde vive la decisión
de qué hereda quién y qué se vacía por conflicto, y es lo que hay que poder probar sin base.
`medir_cobertura_curada` la necesita cualquier feature que quiera reportar cuánto del universo
tiene lámina, calificación o sector sin volver a sembrar.
"""

from app.condiciones.corrida import ResultadoSemilla, sembrar
from app.condiciones.persistencia import CoberturaCurada, medir_cobertura_curada
from app.condiciones.resolucion import Conflicto, Resolucion, resolver
from app.condiciones.semilla import CAMPOS, Condiciones, Semilla, Valor, leer_semilla

__all__ = [
    "CAMPOS",
    "CoberturaCurada",
    "Condiciones",
    "Conflicto",
    "Resolucion",
    "ResultadoSemilla",
    "Semilla",
    "Valor",
    "leer_semilla",
    "medir_cobertura_curada",
    "resolver",
    "sembrar",
]
