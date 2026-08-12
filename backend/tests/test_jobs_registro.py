"""El registro auditable de una corrida: qué SQL emite, cómo calcula la duración y cómo
serializa/deserializa `filas_por_fuente` y `alertas`, que son jsonb."""

import json
from datetime import UTC, datetime

from app.jobs.registro import listar_corridas, registrar_corrida, ultima_corrida


class _FakeConexionCorridas:
    """Conexión falsa que simula el `RETURNING` de un INSERT y el resultado de un SELECT."""

    def __init__(self, filas_por_select: list[dict] | None = None) -> None:
        self.filas_por_select = filas_por_select or []
        self.llamadas: list[tuple[str, tuple]] = []

    async def fetchrow(self, query: str, *args) -> dict | None:
        self.llamadas.append((query, args))
        if "INSERT INTO" in query:
            tipo, iniciado_en, finalizado_en, duracion_ms, filas, alertas, estado = args
            return {
                "id": 1,
                "tipo": tipo,
                "iniciado_en": iniciado_en,
                "finalizado_en": finalizado_en,
                "duracion_ms": duracion_ms,
                "filas_por_fuente": filas,
                "alertas": alertas,
                "estado": estado,
            }
        return self.filas_por_select[0] if self.filas_por_select else None

    async def fetch(self, query: str, *args) -> list[dict]:
        self.llamadas.append((query, args))
        return self.filas_por_select


def _corrida_de(inicio: datetime, fin: datetime) -> dict:
    return {
        "tipo": "matinal",
        "iniciado_en": inicio,
        "finalizado_en": fin,
        "filas_por_fuente": {"byma": 100, "iamc": 50},
        "alertas": [{"codigo": "fuente_no_disponible", "mensaje": "x"}],
        "estado": "parcial",
    }


async def test_registrar_corrida_calcula_la_duracion_en_milisegundos() -> None:
    conn = _FakeConexionCorridas()
    inicio = datetime(2026, 8, 6, 9, 0, 0, tzinfo=UTC)
    fin = datetime(2026, 8, 6, 9, 0, 3, 500000, tzinfo=UTC)

    resultado = await registrar_corrida(conn, **_corrida_de(inicio, fin))

    assert resultado["duracion_ms"] == 3500


async def test_registrar_corrida_serializa_filas_y_alertas_como_json() -> None:
    conn = _FakeConexionCorridas()
    inicio = datetime(2026, 8, 6, 9, 0, 0, tzinfo=UTC)
    fin = datetime(2026, 8, 6, 9, 0, 1, tzinfo=UTC)

    await registrar_corrida(conn, **_corrida_de(inicio, fin))

    (_, args) = conn.llamadas[0]
    filas_json, alertas_json = args[4], args[5]
    assert json.loads(filas_json) == {"byma": 100, "iamc": 50}
    assert json.loads(alertas_json) == [{"codigo": "fuente_no_disponible", "mensaje": "x"}]


async def test_registrar_corrida_devuelve_filas_y_alertas_ya_deserializadas() -> None:
    conn = _FakeConexionCorridas()
    inicio = datetime(2026, 8, 6, 9, 0, 0, tzinfo=UTC)
    fin = datetime(2026, 8, 6, 9, 0, 1, tzinfo=UTC)

    resultado = await registrar_corrida(conn, **_corrida_de(inicio, fin))

    assert resultado["filas_por_fuente"] == {"byma": 100, "iamc": 50}
    assert resultado["alertas"] == [{"codigo": "fuente_no_disponible", "mensaje": "x"}]
    assert resultado["iniciado_en"] == inicio.isoformat()


async def test_listar_corridas_deserializa_cada_fila() -> None:
    inicio = datetime(2026, 8, 6, 9, 0, 0, tzinfo=UTC)
    fin = datetime(2026, 8, 6, 9, 5, 0, tzinfo=UTC)
    fila_cruda = {
        "id": 7,
        "tipo": "refresh",
        "iniciado_en": inicio,
        "finalizado_en": fin,
        "duracion_ms": 300000,
        "filas_por_fuente": json.dumps({"byma": 10}),
        "alertas": json.dumps([]),
        "estado": "completa",
    }
    conn = _FakeConexionCorridas(filas_por_select=[fila_cruda])

    resultado = await listar_corridas(conn, limite=5)

    assert resultado == [
        {
            "id": 7,
            "tipo": "refresh",
            "iniciado_en": inicio.isoformat(),
            "finalizado_en": fin.isoformat(),
            "duracion_ms": 300000,
            "filas_por_fuente": {"byma": 10},
            "alertas": [],
            "estado": "completa",
        }
    ]
    (_query, args) = conn.llamadas[0]
    assert args == (5,)


async def test_ultima_corrida_devuelve_none_sin_historial() -> None:
    conn = _FakeConexionCorridas(filas_por_select=[])
    assert await ultima_corrida(conn) is None
