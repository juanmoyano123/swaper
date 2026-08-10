"""El job de enriquecimiento — Etapa 4 del rediseño del armador, sin salir a la red.

Un cliente falso devuelve resultados fijados a mano por ticker: así se prueba el orden de proceso,
la pausa entre tickers, el corte al 429 y qué se persiste, sin depender de Yahoo ni del reloj real.
"""

from datetime import UTC, datetime

from app.externos.yahoo import ResultadoPerfilEmpresa
from app.renta_variable.enriquecimiento import enriquecer_perfiles
from tests.conftest import FakeConexionEscritura

CAPTURADO = datetime(2026, 8, 9, tzinfo=UTC)


def resultado(
    ticker: str, *, disponible: bool = True, status: int | None = None, motivo: str | None = None
) -> ResultadoPerfilEmpresa:
    return ResultadoPerfilEmpresa(
        disponible=disponible,
        motivo=motivo,
        status=status,
        nombre_corto=f"{ticker} corto" if disponible else None,
        nombre_largo=f"{ticker} largo" if disponible else None,
        pais="Argentina" if disponible else None,
        sector="Financial Services" if disponible else None,
        industria="Banks" if disponible else None,
        capturado_en=CAPTURADO,
    )


class _ClienteFalso:
    def __init__(self, respuestas: dict[str, ResultadoPerfilEmpresa]) -> None:
        self._respuestas = respuestas
        self.pedidos: list[str] = []

    async def perfil_de_empresa(self, ticker: str) -> ResultadoPerfilEmpresa:
        self.pedidos.append(ticker)
        return self._respuestas[ticker]


async def _no_dormir(_: float) -> None:
    return None


async def test_enriquece_cada_ticker_pendiente_y_persiste_uno_por_uno() -> None:
    conn = FakeConexionEscritura(metricas_previas=[{"ticker": "GGAL"}, {"ticker": "PAMP"}])
    cliente = _ClienteFalso({"GGAL": resultado("GGAL"), "PAMP": resultado("PAMP")})
    pausas: list[float] = []

    async def dormir(segundos: float) -> None:
        pausas.append(segundos)

    resumen = await enriquecer_perfiles(conn, cliente, dormir=dormir)

    assert cliente.pedidos == ["GGAL", "PAMP"]
    assert resumen.pendientes == 2
    assert resumen.procesados == 2
    assert resumen.guardados == 2
    assert resumen.cortado_por_limite_de_fuente is False
    assert resumen.motivo_corte is None
    assert len(conn.filas_de("perfil_renta_variable")) == 2
    # Pausa entre el primero y el segundo, ninguna después del último.
    assert pausas == [1.0]


async def test_un_ticker_sin_dato_no_se_persiste_pero_sigue_con_el_resto() -> None:
    conn = FakeConexionEscritura(metricas_previas=[{"ticker": "GGAL"}, {"ticker": "PAMP"}])
    cliente = _ClienteFalso(
        {
            "GGAL": resultado("GGAL", disponible=False, motivo="no disponible"),
            "PAMP": resultado("PAMP"),
        }
    )

    resumen = await enriquecer_perfiles(conn, cliente, dormir=_no_dormir)

    assert resumen.procesados == 2
    assert resumen.guardados == 1
    filas = conn.filas_de("perfil_renta_variable")
    assert len(filas) == 1 and filas[0][0] == "PAMP"


async def test_corta_al_primer_429_y_declara_por_que_sin_seguir_con_el_resto() -> None:
    conn = FakeConexionEscritura(
        metricas_previas=[{"ticker": "GGAL"}, {"ticker": "PAMP"}, {"ticker": "YPFD"}]
    )
    cliente = _ClienteFalso(
        {
            "GGAL": resultado("GGAL"),
            "PAMP": resultado(
                "PAMP", disponible=False, status=429, motivo="Yahoo Finance está limitando"
            ),
            "YPFD": resultado("YPFD"),
        }
    )

    resumen = await enriquecer_perfiles(conn, cliente, dormir=_no_dormir)

    # Se corta en PAMP: YPFD ni se pide.
    assert cliente.pedidos == ["GGAL", "PAMP"]
    assert resumen.cortado_por_limite_de_fuente is True
    assert resumen.motivo_corte == "Yahoo Finance está limitando"
    assert resumen.procesados == 1
    assert resumen.guardados == 1
    assert len(conn.filas_de("perfil_renta_variable")) == 1


async def test_el_limite_deja_el_resto_pendiente_para_la_proxima_corrida() -> None:
    conn = FakeConexionEscritura(
        metricas_previas=[{"ticker": "GGAL"}, {"ticker": "PAMP"}, {"ticker": "YPFD"}]
    )
    cliente = _ClienteFalso(
        {"GGAL": resultado("GGAL"), "PAMP": resultado("PAMP"), "YPFD": resultado("YPFD")}
    )

    resumen = await enriquecer_perfiles(conn, cliente, dormir=_no_dormir, limite=2)

    assert cliente.pedidos == ["GGAL", "PAMP"]
    assert resumen.pendientes == 3
    assert resumen.procesados == 2
    assert resumen.guardados == 2
