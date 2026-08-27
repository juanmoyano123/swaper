"""El ensamblado de la barra de estado del dato — F-013.

El grueso de lo que se prueba acá es el GWT-2: **la hora que se muestra es la del snapshot, no la
del reloj**. Es la regla 1 del proyecto aplicada al tiempo, y el error que evita —presentar el
momento de la consulta como si fuera el momento del dato— es de los que no se ven mirando la
pantalla, porque el número siempre parece razonable.
"""

import json
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from app.core.config import get_settings
from app.estado.alertas import CODIGO_SIN_CORRIDA, CODIGO_SIN_DATO_DE_MERCADO
from app.estado.analisis import CacheDelAnalisis
from app.estado.servicio import ORIGEN_ESTADO, ORIGEN_INGESTA, estado_del_dato, ordenar
from app.ingesta.alertas import (
    CODIGO_CREDENCIAL_VENCIDA,
    Alerta,
    Severidad,
    credencial_vencida,
    fuente_caida,
)

# 11:00 de la mañana del 7 de agosto de 2026, en UTC. Es el snapshot del GWT-2.
SNAPSHOT = datetime(2026, 8, 7, 14, 0, tzinfo=UTC)
# Y las 11:15, quince minutos después: el momento en que alguien lo mira.
AHORA = SNAPSHOT + timedelta(minutes=15)

HOY = date(2026, 8, 7)


def fila_universo(**campos: object) -> dict[str, object]:
    """Una fila de la vista `resumen` con lo mínimo para que `segmentar` no explote."""
    base: dict[str, object] = {
        "ticker": "AL30",
        "clase_activo": "soberano",
        "tipo_tasa": "hard-dollar",
        "tir": 0.0725,
        "tna": None,
        "duration": 3.1,
        "maturity": date(2030, 7, 9),
        "law": "NY",
        "couponCurrency": "USD",
        "underlying": "Tesoro Nacional",
        "lastPrice": 68.5,
        "effectiveVolume": 120_000.0,
        "moneda_cotizacion": "USD",
    }
    base.update(campos)
    return base


def fila_corrida(
    *,
    id_: int = 7,
    alertas: list[Alerta] | None = None,
    estado: str = "completa",
) -> dict[str, Any]:
    """Una fila de `corridas_ingesta` como la devuelve asyncpg: los `jsonb` sin deserializar."""
    return {
        "id": id_,
        "tipo": "matinal",
        "iniciado_en": SNAPSHOT - timedelta(minutes=3),
        "finalizado_en": SNAPSHOT,
        "duracion_ms": 180_000,
        "filas_por_fuente": json.dumps({"byma": 2894, "iamc": 241}),
        "alertas": json.dumps([a.como_dict() for a in (alertas or [])]),
        "estado": estado,
    }


class FakeConexionEstado:
    """Conexión falsa que sirve las cinco consultas del camino de la barra.

    Cuenta cuántas veces se pidió cada cosa: es lo que permite verificar que el caché de verdad
    evita las lecturas caras, que es la propiedad por la que este endpoint existe tal como existe.
    """

    def __init__(
        self,
        *,
        corrida: dict[str, Any] | None = None,
        snapshot: datetime | None = SNAPSHOT,
        universo: list[dict[str, object]] | None = None,
        cashflow: list[dict[str, object]] | None = None,
        paridades: list[dict[str, object]] | None = None,
        tabla_precios: bool = True,
        columna_snapshot: bool = True,
    ) -> None:
        self.corrida = corrida
        self.snapshot = snapshot
        self.universo = universo if universo is not None else [fila_universo()]
        self.cashflow = cashflow or []
        self.paridades = (
            paridades if paridades is not None else [{"ticker": "AL30", "paridad": 78.0}]
        )
        self.tabla_precios = tabla_precios
        self.columna_snapshot = columna_snapshot
        self.lecturas: list[str] = []

    async def fetchrow(self, query: str, *args: Any) -> Any:
        if "corridas_ingesta" in query:
            self.lecturas.append("corrida")
            return self.corrida
        self.lecturas.append("health")
        return {"tabla_existe": self.tabla_precios, "columna_existe": self.columna_snapshot}

    async def fetchval(self, query: str, *args: Any) -> Any:
        self.lecturas.append("snapshot")
        return self.snapshot

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        # Las tres consultas nombran `resumen` o se le parecen, así que se rutea por lo distintivo
        # de cada una. Discriminar paridades por `"paridad" in query` dejó de servir cuando F-038
        # sumó la columna `paridad` a `COLUMNAS` del universo: las dos consultas la nombran. Lo que
        # las separa es la forma — la de paridades pide exactamente esas dos columnas
        # (`SQL_PARIDADES` en `app/calendario/lectura.py`), la del universo joinea `instrumentos`.
        if "cashflow" in query:
            self.lecturas.append("cashflow")
            return self.cashflow
        if "SELECT ticker, paridad" in query:
            self.lecturas.append("paridades")
            return self.paridades
        self.lecturas.append("universo")
        return self.universo

    def veces(self, que: str) -> int:
        return self.lecturas.count(que)


async def pedir(conn: FakeConexionEstado, cache: CacheDelAnalisis | None = None, **kwargs: Any):
    return await estado_del_dato(
        conn,
        get_settings(),
        cache=cache or CacheDelAnalisis(),
        hoy=HOY,
        ahora=kwargs.pop("ahora", AHORA),
        **kwargs,
    )


class TestLaHoraDelDato:
    """GWT-2: un snapshot de las 11:00 mirado a las 11:15 sigue diciendo 11:00."""

    async def test_declara_la_hora_del_snapshot_y_no_la_del_reloj(self) -> None:
        estado = await pedir(FakeConexionEstado())

        assert estado.dato["capturado_en"] == SNAPSHOT.isoformat()
        assert estado.dato["capturado_en"] != AHORA.isoformat()

    async def test_declara_la_demora_de_la_fuente(self) -> None:
        """Los 20 minutos de la API abierta de BYMA salen de settings, no de una constante."""
        estado = await pedir(FakeConexionEstado())

        assert estado.dato["demora"]["minutos"] == get_settings().byma_demora_minutos == 20
        assert "BYMA" in estado.dato["demora"]["fuente"]

    async def test_hasta_que_momento_del_mercado_refleja_el_dato(self) -> None:
        """El número que contesta la pregunta real: 11:00 menos 20 minutos es el mercado de 10:40.

        Sin esta resta, un precio capturado a las 11:00 se lee como el precio de las 11:00, y no lo
        es: es el de las 10:40 publicado a las 11:00.
        """
        estado = await pedir(FakeConexionEstado())

        assert estado.dato["dato_valido_hasta"] == (SNAPSHOT - timedelta(minutes=20)).isoformat()

    async def test_la_hora_de_la_consulta_viaja_aparte_y_no_reemplaza_a_ninguna(self) -> None:
        estado = await pedir(FakeConexionEstado())

        assert estado.consultado_en == AHORA
        assert estado.dato["antiguedad_minutos"] == 15

    async def test_sin_snapshot_las_horas_quedan_vacias_y_no_en_cero(self) -> None:
        """No saber hace cuánto se capturó el dato no es haberlo capturado recién."""
        estado = await pedir(FakeConexionEstado(snapshot=None))

        assert estado.dato["capturado_en"] is None
        assert estado.dato["dato_valido_hasta"] is None
        assert estado.dato["antiguedad_minutos"] is None
        # La demora sale igual: es un atributo de la fuente, no de la corrida.
        assert estado.dato["demora"]["minutos"] == 20


class TestAlertasDelEstado:
    async def test_alerta_cuando_no_hay_ninguna_corrida_registrada(self) -> None:
        """El caso de la base real hoy: hay precios del 06/08 y `corridas_ingesta` está vacía."""
        estado = await pedir(FakeConexionEstado(corrida=None))

        alerta = next(a for a in estado.alertas if a["codigo"] == CODIGO_SIN_CORRIDA)
        assert alerta["severidad"] == Severidad.ADVERTENCIA.value
        assert alerta["accion_requerida"]
        assert estado.corrida is None

    async def test_no_alerta_de_corrida_cuando_hay_una(self) -> None:
        estado = await pedir(FakeConexionEstado(corrida=fila_corrida()))

        assert not any(a["codigo"] == CODIGO_SIN_CORRIDA for a in estado.alertas)
        assert estado.corrida is not None
        assert estado.corrida["id"] == 7
        assert estado.corrida["filas_por_fuente"] == {"byma": 2894, "iamc": 241}

    async def test_la_corrida_no_repite_sus_alertas_dentro_de_si_misma(self) -> None:
        """Una alerta se cuenta una sola vez: si viajara en los dos lugares se podría ver en uno
        y no en el otro según qué parte del payload se mire."""
        conn = FakeConexionEstado(corrida=fila_corrida(alertas=[fuente_caida("BYMA", "timeout")]))

        estado = await pedir(conn)

        assert "alertas" not in (estado.corrida or {})
        assert sum(1 for a in estado.alertas if a["codigo"] == "fuente_no_disponible") == 1

    async def test_alerta_cuando_no_hay_dato_de_mercado(self) -> None:
        """Sin precios no hay universo ni rendimiento: es error, no advertencia."""
        estado = await pedir(FakeConexionEstado(snapshot=None, tabla_precios=False))

        alerta = next(a for a in estado.alertas if a["codigo"] == CODIGO_SIN_DATO_DE_MERCADO)
        assert alerta["severidad"] == Severidad.ERROR.value

    async def test_las_alertas_de_la_corrida_se_distinguen_de_las_del_estado(self) -> None:
        """Lo que falló al **traer** el dato y lo que falta en el dato ya traído no son lo mismo."""
        conn = FakeConexionEstado(
            corrida=fila_corrida(alertas=[credencial_vencida("Docta", "Regenerar el link.")])
        )

        estado = await pedir(conn)

        origenes = {a["codigo"]: a["origen"] for a in estado.alertas}
        assert origenes[CODIGO_CREDENCIAL_VENCIDA] == ORIGEN_INGESTA
        assert origenes["cobertura_del_calendario"] == ORIGEN_ESTADO

    async def test_una_alerta_guardada_a_medias_no_tumba_la_barra(self) -> None:
        """`alertas` es `jsonb`: PostgreSQL no garantiza su forma, y sin barra quedan seis pantallas
        sin poder decir si el dato sirve."""
        corrida = fila_corrida()
        corrida["alertas"] = json.dumps([{"codigo": "raro"}, "esto no es una alerta", {}])

        estado = await pedir(FakeConexionEstado(corrida=corrida))

        assert not any(a["codigo"] == "raro" for a in estado.alertas)


class TestOrdenDeLasAlertas:
    def test_los_errores_van_antes_que_las_advertencias_y_que_la_informacion(self) -> None:
        """`Severidad` es un `StrEnum`: ordenarlas con `<` daría advertencia, error, info."""
        alertas = [
            {"severidad": "info", "codigo": "c", "accion_requerida": None},
            {"severidad": "advertencia", "codigo": "b", "accion_requerida": None},
            {"severidad": "error", "codigo": "a", "accion_requerida": None},
        ]

        assert [a["codigo"] for a in ordenar(alertas)] == ["a", "b", "c"]

    def test_dentro_del_mismo_nivel_manda_la_que_espera_una_acción(self) -> None:
        """Entre dos errores, el que se arregla a mano va antes que el que se arregla solo."""
        alertas = [
            {"severidad": "error", "codigo": "caida", "accion_requerida": None},
            {"severidad": "error", "codigo": "credencial", "accion_requerida": "Renovarla."},
        ]

        assert [a["codigo"] for a in ordenar(alertas)] == ["credencial", "caida"]

    def test_una_severidad_desconocida_va_al_final_y_no_al_principio(self) -> None:
        """No puede escalar sola al tope y empujar un error real hacia abajo."""
        alertas = [
            {"severidad": "catastrofe", "codigo": "nueva", "accion_requerida": None},
            {"severidad": "info", "codigo": "conocida", "accion_requerida": None},
        ]

        assert [a["codigo"] for a in ordenar(alertas)] == ["conocida", "nueva"]

    async def test_la_peor_severidad_resume_lo_que_la_barra_pinta(self) -> None:
        conn = FakeConexionEstado(corrida=fila_corrida(alertas=[fuente_caida("BYMA", "timeout")]))

        estado = await pedir(conn)

        assert estado.peor_severidad == Severidad.ERROR.value
        resumen = estado.como_dict()["resumen"]
        assert resumen["por_severidad"]["error"] >= 1
        assert resumen["alertas"] == len(estado.alertas)
        assert estado.alertas[0]["severidad"] == Severidad.ERROR.value


class TestFuentesEnLaRespuesta:
    async def test_credencial_vencida_y_fuente_caida_llegan_separadas_a_la_barra(self) -> None:
        """GWT-4, punta a punta: la barra recibe las dos en montones distintos."""
        conn = FakeConexionEstado(
            corrida=fila_corrida(
                alertas=[
                    credencial_vencida("Docta", "Regenerar el link firmado."),
                    fuente_caida("BYMA", "timeout tras 5 intentos"),
                ]
            )
        )

        estado = await pedir(conn)

        assert estado.fuentes["hay_credencial_vencida"] is True
        assert estado.fuentes["hay_fuente_caida"] is True
        assert estado.fuentes["requiere_intervencion"] is True


class TestDescartes:
    async def test_los_descartes_viajan_con_su_motivo_y_el_valor_que_los_disparo(self) -> None:
        """GWT-3: sin el valor y el umbral, el ticker solo no permite auditar el corte."""
        # Dos especies de la misma emisión: una con el precio mal escalado, la otra sana.
        conn = FakeConexionEstado(
            universo=[
                fila_universo(ticker="VSCQO", tir=0.0675),
                fila_universo(ticker="VSCQD", tir=346_279.17),
            ]
        )

        estado = await pedir(conn)

        descartes = estado.analisis.como_dict()["descartes"]
        assert descartes["total"] == 1
        [descarte] = descartes["items"]
        assert descarte["ticker"] == "VSCQD"
        assert descarte["motivo"] == "especie_incoherente"
        assert descarte["rendimiento"] == pytest.approx(346_279.17)
        assert descarte["ticker_referencia"] == "VSCQO"
        assert descartes["truncado"] is False

    async def test_el_universo_declara_lo_que_la_sanidad_no_llega_a_mirar(self) -> None:
        """Un cero de descartes no es "el dato está sano" si medio universo no tiene tipo de tasa.

        Es exactamente lo que pasa contra la base real: la sanidad descarta cero, y los dos únicos
        rendimientos imposibles del universo caen en `sin_segmento`, donde no hay techo contra el
        cual compararlos.
        """
        conn = FakeConexionEstado(
            universo=[
                fila_universo(ticker="AL30"),
                fila_universo(ticker="VE32P", tipo_tasa=None, tir=6.14),
            ]
        )

        estado = await pedir(conn)

        assert estado.analisis.universo["descartados"] == 0
        assert estado.analisis.universo["sin_segmento"] == 1


class TestCosto:
    async def test_la_mitad_barata_se_lee_en_cada_consulta(self) -> None:
        """La hora del dato tiene que ser la de ahora aunque el análisis venga del caché."""
        conn = FakeConexionEstado(corrida=fila_corrida())
        cache = CacheDelAnalisis()

        await pedir(conn, cache)
        await pedir(conn, cache)

        assert conn.veces("corrida") == 2
        assert conn.veces("snapshot") == 2

    async def test_el_universo_no_se_relee_mientras_la_corrida_sea_la_misma(self) -> None:
        """La propiedad por la que este endpoint puede estar en las seis pantallas."""
        conn = FakeConexionEstado(corrida=fila_corrida())
        cache = CacheDelAnalisis()

        primera = await pedir(conn, cache)
        segunda = await pedir(conn, cache)

        assert primera.desde_cache is False
        assert segunda.desde_cache is True
        assert conn.veces("universo") == 1
        assert conn.veces("cashflow") == 1

    async def test_una_corrida_nueva_invalida_el_analisis(self) -> None:
        """Cuando más importa que la barra diga la verdad, no puede servir la foto anterior."""
        conn = FakeConexionEstado(corrida=fila_corrida(id_=7))
        cache = CacheDelAnalisis()

        await pedir(conn, cache)
        conn.corrida = fila_corrida(id_=8)
        segunda = await pedir(conn, cache)

        assert segunda.desde_cache is False
        assert conn.veces("universo") == 2

    async def test_un_snapshot_nuevo_invalida_el_analisis_aunque_no_haya_corrida(self) -> None:
        """Con `corridas_ingesta` vacía, la hora del snapshot es lo único que identifica al dato."""
        conn = FakeConexionEstado(corrida=None)
        cache = CacheDelAnalisis()

        await pedir(conn, cache)
        conn.snapshot = SNAPSHOT + timedelta(minutes=15)
        segunda = await pedir(conn, cache)

        assert segunda.desde_cache is False
        assert conn.veces("universo") == 2

    async def test_el_analisis_declara_cuando_se_calculo_y_cuanto_tardo(self) -> None:
        """Si la barra sirve dato cacheado, tiene que poder decir de cuándo es."""
        estado = await pedir(FakeConexionEstado())

        costo = estado.como_dict()["costo"]
        assert costo["desde_cache"] is False
        assert costo["analisis_duracion_ms"] >= 0
        assert costo["analisis_calculado_en"]

    async def test_no_sale_a_la_red_y_lo_declara(self) -> None:
        """El contraste del tipo de cambio es lo único de este cálculo que saldría a Internet.

        Que no se evalúe no se deja implícito en un `null`: `null` más la alerta que lo acompaña se
        leen como "se intentó y no se pudo", que mandaría a alguien a revisar si BYMA está andando.
        """
        estado = await pedir(FakeConexionEstado())

        contraste = estado.analisis.tipo_de_cambio["contraste_evaluado"]
        assert contraste["evaluado"] is False
        assert "universo/tipo-de-cambio" in str(contraste["donde_verlo"])


class TestCorridaAtrasada:
    """La ingesta que se detiene sin avisar — el caso que motivó la alerta (27/08/2026)."""

    def test_una_rueda_perdida_se_tolera(self) -> None:
        # Un cron que se saltea un disparo y engancha el siguiente no es una falla: el refresh
        # siguiente trae lo mismo que habría traído el que faltó.
        from datetime import UTC, datetime

        from app.core.config import Settings
        from app.estado.servicio import _alertas_del_estado

        ajustes = Settings(
            supabase_url="https://x.supabase.co",
            supabase_anon_key="a",
            supabase_service_role_key="b",
            database_url="postgresql://u:p@h:5432/d",
        )
        corrida = {"iniciado_en": datetime(2026, 8, 26, 14, 30, tzinfo=UTC)}
        ahora = datetime(2026, 8, 27, 18, 0, tzinfo=UTC)
        alertas = _alertas_del_estado(corrida, [], ajustes, ahora)
        assert [a.codigo for a in alertas] == []

    def test_dos_ruedas_perdidas_alertan_con_la_fecha_de_la_ultima(self) -> None:
        from datetime import UTC, datetime

        from app.core.config import Settings
        from app.estado.alertas import CODIGO_CORRIDA_ATRASADA
        from app.estado.servicio import _alertas_del_estado

        ajustes = Settings(
            supabase_url="https://x.supabase.co",
            supabase_anon_key="a",
            supabase_service_role_key="b",
            database_url="postgresql://u:p@h:5432/d",
        )
        # Lunes 24 la última corrida; jueves 27 ya se perdieron martes, miércoles y jueves.
        corrida = {"iniciado_en": datetime(2026, 8, 24, 14, 30, tzinfo=UTC)}
        ahora = datetime(2026, 8, 27, 18, 0, tzinfo=UTC)
        alertas = _alertas_del_estado(corrida, [], ajustes, ahora)
        assert [a.codigo for a in alertas] == [CODIGO_CORRIDA_ATRASADA]
        assert alertas[0].detalle["ruedas_perdidas"] == 3

    def test_el_fin_de_semana_no_dispara_la_alerta(self) -> None:
        # Del viernes al lunes pasan 60 horas y cero ruedas: contar en días daría un falso positivo
        # todos los lunes a la mañana.
        from datetime import UTC, datetime

        from app.core.config import Settings
        from app.estado.servicio import _alertas_del_estado

        ajustes = Settings(
            supabase_url="https://x.supabase.co",
            supabase_anon_key="a",
            supabase_service_role_key="b",
            database_url="postgresql://u:p@h:5432/d",
        )
        corrida = {"iniciado_en": datetime(2026, 8, 21, 20, 0, tzinfo=UTC)}  # viernes
        ahora = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
        alertas = _alertas_del_estado(corrida, [], ajustes, ahora)
        assert [a.codigo for a in alertas] == []
