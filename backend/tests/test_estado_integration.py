"""F-013 contra la base real. Marcado `integration`, fuera de la corrida por defecto.

Lo que sólo se puede verificar acá es que las cinco consultas del camino de la barra entren por la
puerta contra el esquema de verdad, y que el resultado sea coherente entre sus partes: que la
cobertura se mida sobre el mismo universo que se saneó, que el calendario no diga cubrir más
emisiones de las que hay, y que la hora del dato salga de `precios` y no del reloj.

**Las aserciones son sobre invariantes, no sobre números del día.** Cuántos instrumentos descarta la
sanidad o qué proporción del universo llega al calendario depende de la corrida de ingesta que haya
pasado último, y un test que fijara esos números fallaría todos los días por la razón equivocada.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest

from app.core.config import get_settings
from app.estado.analisis import CONTRASTE_EVALUADO, CacheDelAnalisis
from app.estado.campos import CAMPOS_CRITICOS
from app.estado.servicio import estado_del_dato

RAIZ_REPO = Path(__file__).resolve().parents[2]


def _dsn() -> str:
    from dotenv import dotenv_values

    dsn = dotenv_values(RAIZ_REPO / ".env").get("DATABASE_URL")
    if not dsn:
        pytest.skip("sin DATABASE_URL en el .env de la raíz")
    return dsn


@pytest.fixture
async def conexion():
    conn = await asyncpg.connect(_dsn(), timeout=10.0)
    try:
        yield conn
    finally:
        await conn.close()


@pytest.fixture
async def estado(conexion):
    return await estado_del_dato(conexion, get_settings(), cache=CacheDelAnalisis())


@pytest.mark.integration
class TestContraLaBaseReal:
    async def test_las_cinco_consultas_entran_por_la_puerta(self, estado) -> None:
        """Un cambio de columna en `resumen` o en `cashflow` sólo se descubre acá."""
        cuerpo = estado.como_dict()

        assert cuerpo["universo"]["leidos"] > 0
        assert cuerpo["cobertura"]
        assert cuerpo["calendario"]["emisiones"] > 0

    async def test_la_hora_del_dato_sale_de_precios_y_no_del_reloj(self, estado) -> None:
        """GWT-2 contra el dato real: la barra declara cuándo se capturó, no cuándo se preguntó."""
        capturado = estado.dato["capturado_en"]
        assert capturado is not None
        assert capturado < estado.consultado_en.isoformat()

        demora = estado.dato["demora"]["minutos"]
        esperado = datetime.fromisoformat(capturado) - timedelta(minutes=demora)
        assert estado.dato["dato_valido_hasta"] == esperado.isoformat()
        assert estado.dato["antiguedad_minutos"] >= 0

    async def test_la_cobertura_se_mide_sobre_el_universo_entero(self, estado) -> None:
        """El denominador de todos los campos críticos es la misma lectura que se saneó.

        Si alguno midiera sobre un subconjunto, su porcentaje diría que el dato está más completo de
        lo que está, que es exactamente el error que la barra existe para no cometer.
        """
        leidos = estado.analisis.universo["leidos"]
        medidos = {c["campo"] for c in estado.analisis.cobertura}

        assert medidos == {c.campo for c in CAMPOS_CRITICOS}
        assert all(c["total"] == leidos for c in estado.analisis.cobertura)

    async def test_el_universo_cierra_consigo_mismo(self, estado) -> None:
        universo = estado.analisis.universo

        assert (
            universo["evaluados"] + universo["renta_variable"] + universo["sin_segmento"]
            == (universo["leidos"])
        )
        assert universo["descartados"] <= universo["evaluados"]
        assert universo["operables"] <= universo["con_rendimiento"]
        assert universo["emisiones"] <= universo["evaluados"]

    async def test_el_calendario_nunca_dice_cubrir_mas_de_lo_que_hay(self, estado) -> None:
        calendario = estado.analisis.calendario

        assert calendario["con_calendario"] <= calendario["emisiones"]
        assert calendario["emisiones"] == estado.analisis.universo["emisiones"]

    async def test_la_cobertura_del_calendario_se_declara_siempre(self, estado) -> None:
        """Aunque no haya un solo caso que revisar. Es el hallazgo que hoy no expone ninguna
        pantalla: la grilla muestra un subconjunto del universo y hay que decir que lo es."""
        codigos = {a["codigo"] for a in estado.alertas}

        assert "cobertura_del_calendario" in codigos

    async def test_no_se_contrasta_contra_byma_y_se_declara(self, estado) -> None:
        """El único control que saldría a Internet queda afuera del camino de la barra."""
        assert estado.analisis.tipo_de_cambio["contraste_evaluado"] == CONTRASTE_EVALUADO
        assert estado.analisis.tipo_de_cambio["contraste"] is None

    async def test_ninguna_alerta_expone_una_url(self, estado) -> None:
        """Las URLs de Docta llevan el token embebido y esta respuesta se serializa al log."""
        texto = str(estado.como_dict())

        assert "http://" not in texto
        assert "https://" not in texto

    async def test_la_segunda_consulta_no_vuelve_a_leer_el_universo(self, conexion) -> None:
        """La propiedad por la que este endpoint puede estar en las seis pantallas."""
        cache = CacheDelAnalisis()

        primera = await estado_del_dato(conexion, get_settings(), cache=cache)
        empezado = datetime.now(UTC)
        segunda = await estado_del_dato(conexion, get_settings(), cache=cache)
        tardo = (datetime.now(UTC) - empezado).total_seconds()

        assert primera.desde_cache is False
        assert segunda.desde_cache is True
        # El análisis cacheado es el mismo objeto, así que declara la misma hora de cálculo.
        assert segunda.analisis.calculado_en == primera.analisis.calculado_en
        # Y la segunda vuelta cuesta menos que lo que costó calcular el análisis.
        assert tardo * 1000 < primera.analisis.duracion_ms
