"""Caché en memoria con vencimiento, compartida por los clientes de `app/externos/`.

Nació en `yahoo.py` (F-053) y se extrajo acá cuando `data912.py` la necesitó igual: los dos clientes
consultan por especie, al ritmo de los clics del asesor, y los dos necesitan recordar un acierto por
un rato y un fallo por menos tiempo — mismo problema, misma solución.
"""

import time
from collections.abc import Callable


class CacheConTTL[T]:
    """Caché en memoria con vencimiento. Sin tope de tamaño a propósito.

    Las claves son tickers del universo del día: unos pocos miles como mucho, y las entradas
    vencidas se pisan solas. Un LRU acá sería complejidad sin problema que resolver.
    """

    def __init__(self, ttl: float, reloj: Callable[[], float] = time.monotonic) -> None:
        self._ttl = ttl
        self._reloj = reloj
        self._entradas: dict[str, tuple[float, T]] = {}

    def obtener(self, clave: str) -> T | None:
        entrada = self._entradas.get(clave)
        if entrada is None:
            return None
        vence_en, valor = entrada
        if self._reloj() >= vence_en:
            del self._entradas[clave]
            return None
        return valor

    def guardar(self, clave: str, valor: T) -> None:
        self._entradas[clave] = (self._reloj() + self._ttl, valor)
