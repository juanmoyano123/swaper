"""Las dos corridas del job de F-008: la matinal completa y el refresh intra-rueda.

La matinal reusa `consolidar()` de F-007 tal cual (ver `tests/test_consolidar_endpoint.py` para la
orquestación de las tres fuentes) y acá se prueba lo que F-008 le agrega: el registro de la
corrida y la clasificación en completa/parcial/fallida.

El refresh es la parte nueva de verdad: arma su propio `Consolidacion` sin volver a pedirle nada a
IAMC ni a Docta, sólo persiste precios y puntas, y clasifica `public-bonds` (soberanos y
subsoberanos) usando el `type` que ya quedó guardado en `cashflow` de una corrida anterior.
"""

import httpx
import pytest
import respx

from app.core.config import get_settings
from app.jobs.corridas import corrida_matinal, refresh_intra_rueda
from tests.conftest import FakeConexionEscritura

BYMA_URL = "https://byma-test.local/free"
DATA912_URL = "https://data912-test.local"

ENDPOINTS_BYMA = (
    "negociable-obligations",
    "public-bonds",
    "cedears",
    "general-equity",
    "leading-equity",
    "index-price",
)

TRAMOS_DATA912 = ("arg_bonds", "arg_corp", "arg_notes", "arg_cedears", "arg_stocks")


async def _no_dormir(_: float) -> None:
    return None


class _FakeConexionConRegistro(FakeConexionEscritura):
    """`FakeConexionEscritura.fetchrow()` no sabe nada de `corridas_ingesta`: devuelve el par
    `tabla_existe`/`columna_existe` que usa `db/health.py`. Acá se intercepta el `INSERT ...
    RETURNING` que hace `registrar_corrida()` y se arma la fila con los mismos argumentos que
    recibió, para que las dos corridas (matinal y refresh) puedan registrar de verdad contra esta
    conexión falsa."""

    async def fetchrow(self, query: str, *args):
        if "INSERT INTO public.corridas_ingesta" in query:
            self._registrar(query)
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
        return await super().fetchrow(query, *args)


class _FakeConexionRefresh(_FakeConexionConRegistro):
    """`FakeConexionEscritura.fetch()` siempre devuelve `metricas_previas`, sin mirar la query, y
    el refresh hace tres `fetch()` distintos (métricas previas, tickers existentes, tipos de
    cronograma). Acá se despachan por el texto de la consulta, que es la única forma de distinguir
    -las tres pasan por `conn.fetch`, no por métodos separados.
    """

    def __init__(self, *, tickers_existentes=None, tipos_cronograma=None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._tickers_existentes = tickers_existentes or []
        self._tipos_cronograma = tipos_cronograma or []

    async def fetch(self, query: str, *args) -> list:
        self._registrar(query)
        if "FROM public.instrumentos" in query:
            return [{"ticker": t} for t in self._tickers_existentes]
        if "FROM public.cashflow" in query:
            return self._tipos_cronograma
        return self.metricas_previas


@pytest.fixture
def settings_de_prueba(tmp_path, monkeypatch):
    """`iamc_directorio` va a `tmp_path` y no al default (`fuentes/` en la raíz del repo), que
    tiene un PDF real: sin esto, `corrida_matinal` lo parsearía de verdad y el resultado de la
    corrida dejaría de ser determinístico. El almacén lee del caché de `get_settings()`, no del
    objeto que se le pasa a la corrida, así que hay que parchear las dos cosas -mismo patrón que
    `tests/test_consolidar_endpoint.py`."""
    settings = get_settings().model_copy(
        update={
            "byma_base_url": BYMA_URL,
            "iamc_directorio": str(tmp_path),
            "data912_base_url": DATA912_URL,
        }
    )
    monkeypatch.setattr(get_settings(), "iamc_directorio", str(tmp_path))
    return settings


def _montar_byma(mapa: dict[str, list[dict]]) -> None:
    for endpoint in ENDPOINTS_BYMA:
        filas = mapa.get(endpoint, [])
        respx.post(f"{BYMA_URL}/{endpoint}").mock(
            return_value=httpx.Response(200, json=filas or [{"symbol": f"RELLENO-{endpoint}"}])
        )


def _montar_byma_caido() -> None:
    for endpoint in ENDPOINTS_BYMA:
        respx.post(f"{BYMA_URL}/{endpoint}").mock(return_value=httpx.Response(500))


def _montar_data912(mapa: dict[str, list[dict]] | None = None) -> None:
    """Experimento data912: relleno con precio 0 por defecto — nunca pisa nada (mismo criterio
    que `test_consolidar_endpoint.py::_montar_data912`)."""
    mapa = mapa or {}
    for tramo in TRAMOS_DATA912:
        filas = mapa.get(tramo, [])
        respx.get(f"{DATA912_URL}/live/{tramo}").mock(
            return_value=httpx.Response(200, json=filas or [{"symbol": f"RELLENO-{tramo}", "c": 0}])
        )


def _montar_data912_caido() -> None:
    for tramo in TRAMOS_DATA912:
        respx.get(f"{DATA912_URL}/live/{tramo}").mock(return_value=httpx.Response(500))


ESPECIE_ON = {
    "symbol": "PLC7O",
    "denominationCcy": "ARS",
    "settlementType": "2",
    "trade": 156460.0,
    "volumeAmount": 1000.0,
    "bidPrice": 156000.0,
    "offerPrice": 157000.0,
    "maturityDate": "2030-07-09",
}

ESPECIE_SOBERANA = {
    "symbol": "AL30",
    "denominationCcy": "ARS",
    "settlementType": "2",
    "trade": 60000.0,
    "volumeAmount": 500.0,
    "bidPrice": 59500.0,
    "offerPrice": 60500.0,
    "maturityDate": "2030-07-09",
}


# --- corrida_matinal --------------------------------------------------------------------------
# La orquestación de las tres fuentes ya está probada en test_consolidar_endpoint.py; acá sólo lo
# que F-008 agrega arriba de `consolidar()`.


async def test_corrida_matinal_registra_parcial_con_solo_byma(settings_de_prueba) -> None:
    conn = _FakeConexionConRegistro()
    with respx.mock:
        _montar_byma({"negociable-obligations": [ESPECIE_ON]})
        _montar_data912()

        corrida = await corrida_matinal(conn, settings_de_prueba, dormir=_no_dormir)

    assert corrida["tipo"] == "matinal"
    # Docta no está configurado en absoluto en `settings_de_prueba` (sin token ni URL) y no hay
    # informe de IAMC en `tmp_path`: esta corrida siempre sale parcial, con sólo BYMA.
    assert corrida["estado"] == "parcial"
    assert "byma" in corrida["filas_por_fuente"]
    assert corrida["duracion_ms"] >= 0
    assert conn.escribio_en("instrumentos")


async def test_corrida_matinal_registra_fallida_cuando_byma_esta_caido(settings_de_prueba) -> None:
    conn = _FakeConexionConRegistro()
    with respx.mock:
        _montar_byma_caido()
        # data912 también caído: la intención del test es "ninguna fuente real está disponible",
        # y con data912 arriba (aunque sea con relleno) el estado sube a parcial — hallazgo real
        # del experimento, no un artefacto: una segunda fuente que sí responde cambia el
        # diagnóstico de la corrida, y eso es exactamente lo que tiene que pasar en producción.
        _montar_data912_caido()

        corrida = await corrida_matinal(conn, settings_de_prueba, dormir=_no_dormir)

    # BYMA no aportó nada e IAMC/Docta tampoco están configurados: no hay una sola fuente
    # completa, pero tampoco hay evidencia de que "algo" haya llegado -> fallida.
    assert corrida["estado"] == "fallida"
    assert corrida["filas_por_fuente"]["byma"] == 0


async def test_corrida_matinal_persiste_las_alertas_de_las_fuentes(settings_de_prueba) -> None:
    conn = _FakeConexionConRegistro()
    with respx.mock:
        _montar_byma_caido()
        _montar_data912()

        corrida = await corrida_matinal(conn, settings_de_prueba, dormir=_no_dormir)

    codigos = {a["codigo"] for a in corrida["alertas"]}
    assert "fuente_no_disponible" in codigos


async def test_data912_arriba_sube_el_estado_de_fallida_a_parcial_con_byma_caido(
    settings_de_prueba,
) -> None:
    """El reverso del test anterior: si BYMA cae pero data912 responde, la corrida ya no es
    `fallida` — llegó algo, aunque sea sin metadata de BYMA."""
    conn = _FakeConexionConRegistro()
    with respx.mock:
        _montar_byma_caido()
        _montar_data912({"arg_corp": [{"symbol": "NUEVO1", "c": 101.0, "q_op": 3}]})

        corrida = await corrida_matinal(conn, settings_de_prueba, dormir=_no_dormir)

    assert corrida["estado"] == "parcial"
    assert corrida["filas_por_fuente"]["data912"] >= 1


async def test_corrida_matinal_registra_data912_en_filas_por_fuente(settings_de_prueba) -> None:
    """Experimento data912: la matinal (que pasa por `consolidar()`) ve la fuente nueva; el
    refresh intra-rueda —abajo— no la usa, por diseño (fuera del alcance del experimento)."""
    conn = _FakeConexionConRegistro()
    with respx.mock:
        _montar_byma({"negociable-obligations": [ESPECIE_ON]})
        _montar_data912({"arg_corp": [{"symbol": "PLC7O", "c": 200.0, "q_op": 5}]})

        corrida = await corrida_matinal(conn, settings_de_prueba, dormir=_no_dormir)

    assert "data912" in corrida["filas_por_fuente"]
    assert corrida["filas_por_fuente"]["data912"] >= 1


# --- refresh_intra_rueda -----------------------------------------------------------------------


async def test_refresh_solo_escribe_precios_y_puntas(settings_de_prueba) -> None:
    conn = _FakeConexionRefresh(tickers_existentes=["PLC7O"])
    with respx.mock:
        _montar_byma({"negociable-obligations": [ESPECIE_ON]})

        corrida = await refresh_intra_rueda(conn, settings_de_prueba, dormir=_no_dormir)

    assert corrida["tipo"] == "refresh"
    assert conn.escribio_en("precios")
    assert conn.escribio_en("puntas")
    assert not conn.escribio_en("instrumentos")
    assert not conn.escribio_en("cashflow")
    assert set(corrida["filas_por_fuente"]) == {"byma"}


async def test_refresh_clasifica_soberanos_con_el_cronograma_ya_persistido(
    settings_de_prueba,
) -> None:
    """`public-bonds` sólo se clasifica por el `type` del cronograma. El refresh no vuelve a
    pedírselo a Docta: lo lee de `cashflow`, que ya quedó escrito por una corrida matinal previa."""
    conn = _FakeConexionRefresh(
        tickers_existentes=["AL30"],
        tipos_cronograma=[{"ticker": "AL30", "type": "HARD_DOLLAR"}],
    )
    with respx.mock:
        _montar_byma({"public-bonds": [ESPECIE_SOBERANA]})

        await refresh_intra_rueda(conn, settings_de_prueba, dormir=_no_dormir)

    tickers_con_precio = {fila[0] for fila in conn.filas_de("precios")}
    assert "AL30" in tickers_con_precio


async def test_refresh_sin_cronograma_no_clasifica_public_bonds(settings_de_prueba) -> None:
    """El contraste del test anterior: sin el `type` persistido, `public-bonds` no tiene cómo
    saber si es soberano o subsoberano y queda fuera del universo -mismo comportamiento que la
    corrida matinal sin Docta."""
    conn = _FakeConexionRefresh(tickers_existentes=["AL30"], tipos_cronograma=[])
    with respx.mock:
        _montar_byma({"public-bonds": [ESPECIE_SOBERANA]})

        await refresh_intra_rueda(conn, settings_de_prueba, dormir=_no_dormir)

    tickers_con_precio = {fila[0] for fila in conn.filas_de("precios")}
    assert "AL30" not in tickers_con_precio
    # La punta se guarda igual: `puntas` no tiene FK y por eso no depende de la clasificación.
    tickers_con_punta = {fila[0] for fila in conn.filas_de("puntas")}
    assert "AL30" in tickers_con_punta


async def test_refresh_descarta_precio_fuera_del_universo_y_alerta(settings_de_prueba) -> None:
    """`instrumentos` no tiene a PLC7O todavía (no corrió la matinal): su precio no se guarda con
    un FK apuntando a nada, y la corrida lo declara en vez de reventar el lote entero."""
    conn = _FakeConexionRefresh(tickers_existentes=[])
    with respx.mock:
        _montar_byma({"negociable-obligations": [ESPECIE_ON]})

        corrida = await refresh_intra_rueda(conn, settings_de_prueba, dormir=_no_dormir)

    assert not conn.escribio_en("precios")
    codigos = {a["codigo"] for a in corrida["alertas"]}
    assert "ticker_fuera_de_universo" in codigos


async def test_refresh_no_llama_a_iamc_ni_a_docta(settings_de_prueba) -> None:
    """Si el código intentara pedirle algo a otra fuente, `respx.mock()` -que sólo tiene montado
    BYMA acá- reventaría con un request no simulado. Que el refresh termine sin error es la
    prueba."""
    conn = _FakeConexionRefresh(tickers_existentes=["PLC7O"])
    with respx.mock:
        _montar_byma({"negociable-obligations": [ESPECIE_ON]})

        corrida = await refresh_intra_rueda(conn, settings_de_prueba, dormir=_no_dormir)

    assert corrida["estado"] in {"completa", "parcial", "fallida"}


async def test_refresh_estado_completa_cuando_byma_responde_bien(settings_de_prueba) -> None:
    conn = _FakeConexionRefresh(tickers_existentes=["PLC7O"])
    with respx.mock:
        _montar_byma({"negociable-obligations": [ESPECIE_ON]})

        corrida = await refresh_intra_rueda(conn, settings_de_prueba, dormir=_no_dormir)

    assert corrida["estado"] == "completa"


async def test_refresh_estado_fallida_cuando_byma_esta_caido(settings_de_prueba) -> None:
    conn = _FakeConexionRefresh(tickers_existentes=["PLC7O"])
    with respx.mock:
        _montar_byma_caido()

        corrida = await refresh_intra_rueda(conn, settings_de_prueba, dormir=_no_dormir)

    assert corrida["estado"] == "fallida"
    assert corrida["filas_por_fuente"]["byma"] == 0
