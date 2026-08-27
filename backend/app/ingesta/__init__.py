"""Andamiaje común de las fuentes de datos de mercado.

Las fuentes del producto —BYMA, data912, CAFCI— hacen estructuralmente lo mismo: traen datos de
afuera, los normalizan, miden qué campos vinieron completos y avisan qué salió mal. Lo que cambia es
el protocolo y el formato, no la forma del resultado.

Este paquete define esa forma una sola vez. El consolidador (F-007) las lee a través del mismo
contrato en vez de aprender un dialecto por fuente, y la barra de estado del dato (F-013) puede
mostrar alertas de cualquiera sin saber de cuál vino.
"""

from app.ingesta.alertas import Alerta, Severidad
from app.ingesta.cobertura import Cobertura, medir_cobertura
from app.ingesta.snapshot import Snapshot

__all__ = ["Alerta", "Cobertura", "Severidad", "Snapshot", "medir_cobertura"]
