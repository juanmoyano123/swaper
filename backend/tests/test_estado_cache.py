"""El caché del análisis — F-013.

Es la pieza que hace que la barra pueda estar en las seis pantallas sin que cada carga pague el
universo entero. Se prueba sola, sin base y sin el resto del servicio, porque lo que tiene que valer
es una propiedad del caché y no del contenido: **misma clave, mismo resultado sin recalcular; clave
distinta, recálculo; y con el caché frío, un solo cálculo aunque entren seis pedidos a la vez**.
"""

import asyncio
from datetime import UTC, datetime

from app.estado.analisis import Analisis, CacheDelAnalisis


def _analisis(marca: int) -> Analisis:
    """Un análisis identificable por su marca, para poder ver cuál se devolvió."""
    return Analisis(
        universo={"marca": marca},
        descartes=[],
        descartes_totales=0,
        cobertura=[],
        tipo_de_cambio={},
        calendario={},
        alertas=[],
        calculado_en=datetime.now(UTC),
        duracion_ms=marca,
    )


class Contador:
    """Calculador que cuenta cuántas veces lo llamaron y devuelve una marca distinta cada vez."""

    def __init__(self, *, demora: float = 0.0) -> None:
        self.llamadas = 0
        self.demora = demora

    async def __call__(self) -> Analisis:
        self.llamadas += 1
        if self.demora:
            await asyncio.sleep(self.demora)
        return _analisis(self.llamadas)


class TestIdentidadDeLaCorrida:
    async def test_la_primera_vez_calcula(self) -> None:
        cache, calcular = CacheDelAnalisis(), Contador()

        analisis, desde_cache = await cache.resolver((7, "11:00"), calcular)

        assert desde_cache is False
        assert calcular.llamadas == 1
        assert analisis.universo["marca"] == 1

    async def test_la_misma_clave_no_vuelve_a_calcular(self) -> None:
        cache, calcular = CacheDelAnalisis(), Contador()

        await cache.resolver((7, "11:00"), calcular)
        analisis, desde_cache = await cache.resolver((7, "11:00"), calcular)

        assert desde_cache is True
        assert calcular.llamadas == 1
        assert analisis.universo["marca"] == 1

    async def test_una_clave_distinta_recalcula(self) -> None:
        """Es lo que hace que una corrida nueva se vea enseguida, y no dentro de cinco minutos."""
        cache, calcular = CacheDelAnalisis(), Contador()

        await cache.resolver((7, "11:00"), calcular)
        analisis, desde_cache = await cache.resolver((8, "11:15"), calcular)

        assert desde_cache is False
        assert calcular.llamadas == 2
        assert analisis.universo["marca"] == 2

    async def test_volver_a_la_clave_anterior_tambien_recalcula(self) -> None:
        """Guarda uno solo: el de la corrida vigente. No hay dos respuestas correctas a la vez."""
        cache, calcular = CacheDelAnalisis(), Contador()

        await cache.resolver((7, "11:00"), calcular)
        await cache.resolver((8, "11:15"), calcular)
        _, desde_cache = await cache.resolver((7, "11:00"), calcular)

        assert desde_cache is False
        assert calcular.llamadas == 3

    async def test_la_clave_sin_corrida_sigue_funcionando(self) -> None:
        """Con `corridas_ingesta` vacía, la hora del snapshot es lo único que identifica al dato."""
        cache, calcular = CacheDelAnalisis(), Contador()

        await cache.resolver((None, "11:00"), calcular)
        _, desde_cache = await cache.resolver((None, "11:00"), calcular)

        assert desde_cache is True
        assert calcular.llamadas == 1


class TestTTL:
    async def test_vencido_recalcula_aunque_la_clave_no_haya_cambiado(self) -> None:
        """La red de seguridad: hay escrituras que mueven el resultado sin mover la clave.

        La semilla curada de F-009 escribe `instrumentos` sin tocar `precios`, así que el análisis
        cambiaría con la clave intacta. El TTL acota cuánto puede durar esa discrepancia.
        """
        cache, calcular = CacheDelAnalisis(ttl_segundos=0.0), Contador()

        await cache.resolver((7, "11:00"), calcular)
        _, desde_cache = await cache.resolver((7, "11:00"), calcular)

        assert desde_cache is False
        assert calcular.llamadas == 2

    async def test_limpiar_descarta_lo_guardado(self) -> None:
        cache, calcular = CacheDelAnalisis(), Contador()

        await cache.resolver((7, "11:00"), calcular)
        cache.limpiar()
        _, desde_cache = await cache.resolver((7, "11:00"), calcular)

        assert desde_cache is False


class TestEstampida:
    async def test_seis_pantallas_a_la_vez_disparan_un_solo_calculo(self) -> None:
        """El caso real: seis pantallas cargando con el caché frío.

        Sin el lock serían seis lecturas del universo entero para escribir seis veces el mismo
        resultado, que es justo el costo que este módulo existe para no pagar.
        """
        cache, calcular = CacheDelAnalisis(), Contador(demora=0.02)

        resultados = await asyncio.gather(
            *(cache.resolver((7, "11:00"), calcular) for _ in range(6))
        )

        assert calcular.llamadas == 1
        assert sum(1 for _, desde_cache in resultados if desde_cache) == 5
        assert {analisis.universo["marca"] for analisis, _ in resultados} == {1}
