"""Andamiaje común de las fuentes de datos de mercado.

Las tres fuentes del producto —BYMA, IAMC y el feed de cashflow— hacen estructuralmente lo mismo:
traen datos de afuera, los normalizan, miden qué campos vinieron completos y avisan qué salió mal.
Lo que cambia es el protocolo y el formato, no la forma del resultado.

Este paquete define esa forma una sola vez. El consolidador (F-007) lee las tres a través del mismo
contrato en vez de aprender tres dialectos, y la barra de estado del dato (F-013) puede mostrar
alertas de cualquier fuente sin saber de cuál vino.
"""

from app.ingesta.alertas import Alerta, Severidad
from app.ingesta.cobertura import Cobertura, medir_cobertura
from app.ingesta.snapshot import Snapshot

__all__ = ["Alerta", "Cobertura", "Severidad", "Snapshot", "medir_cobertura"]
