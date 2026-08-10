"""`app.armado.renta_variable.armar_renta_variable` — el bloque de renta variable del armado
asistido, probado puro y sin base. Ver el docstring del módulo para el algoritmo completo; acá se
prueba cada paso por separado con fixtures armadas a mano.
"""

import pytest

from app.armado.renta_variable import (
    CODIGO_RV_SIN_CANDIDATOS,
    CODIGO_RV_SIN_PERFIL_SECTORIAL,
    CODIGO_RV_SIN_VOLUMEN_USD,
    armar_renta_variable,
)
from app.renta_variable.especies import EspecieRentaVariable


def _especie(
    ticker: str,
    *,
    volumen_usd: float | None,
    sector: str | None = None,
    clase_activo: str = "accion",
) -> EspecieRentaVariable:
    """Una especie mínima: sólo lo que le importa a `armar_renta_variable` -- el resto de los
    campos de `EspecieRentaVariable` no participa del ranking ni de la selección."""
    return EspecieRentaVariable(
        ticker=ticker,
        clase_activo=clase_activo,
        precio=100.0,
        moneda_cotizacion="USD",
        cierre_anterior=None,
        variacion=None,
        volumen=volumen_usd,
        volumen_usd=volumen_usd,
        px_bid=None,
        px_ask=None,
        operaciones=None,
        sector=sector,
    )


def test_pct_rv_no_positivo_no_arma_nada() -> None:
    especies = [_especie("GGAL", volumen_usd=1000.0)]
    posiciones, alertas = armar_renta_variable(
        especies, pct_rv=0.0, n_rv=5, monto_total=100_000
    )
    assert posiciones == []
    assert alertas == []


def test_n_rv_no_positivo_no_arma_nada() -> None:
    especies = [_especie("GGAL", volumen_usd=1000.0)]
    posiciones, alertas = armar_renta_variable(
        especies, pct_rv=25.0, n_rv=0, monto_total=100_000
    )
    assert posiciones == []
    assert alertas == []


def test_es_deterministico_y_desempata_por_ticker_alfabetico() -> None:
    """Dos especies con el mismo `volumen_usd` desempatan por ticker ascendente, siempre."""
    especies = [
        _especie("ZETA", volumen_usd=500.0, sector="Sector A"),
        _especie("ALFA", volumen_usd=500.0, sector="Sector B"),
    ]
    primera = armar_renta_variable(especies, pct_rv=20.0, n_rv=2, monto_total=100_000)
    segunda = armar_renta_variable(
        list(reversed(especies)), pct_rv=20.0, n_rv=2, monto_total=100_000
    )

    assert primera == segunda
    tickers = [p.ticker for p in primera[0]]
    assert tickers == ["ALFA", "ZETA"]


def test_descarta_especies_sin_volumen_usd_y_alerta() -> None:
    especies = [
        _especie("GGAL", volumen_usd=1000.0, sector="Bancos"),
        _especie("SINVOL", volumen_usd=None, sector="Bancos"),
    ]
    posiciones, alertas = armar_renta_variable(
        especies, pct_rv=20.0, n_rv=5, monto_total=100_000
    )

    tickers = {p.ticker for p in posiciones}
    assert "SINVOL" not in tickers
    assert "GGAL" in tickers
    codigos = {a.codigo for a in alertas}
    assert CODIGO_RV_SIN_VOLUMEN_USD in codigos
    alerta = next(a for a in alertas if a.codigo == CODIGO_RV_SIN_VOLUMEN_USD)
    assert alerta.detalle["cantidad"] == 1


def test_sin_especies_descartadas_no_hay_alerta_de_volumen() -> None:
    especies = [_especie("GGAL", volumen_usd=1000.0, sector="Bancos")]
    _, alertas = armar_renta_variable(especies, pct_rv=20.0, n_rv=1, monto_total=100_000)
    assert all(a.codigo != CODIGO_RV_SIN_VOLUMEN_USD for a in alertas)


def test_tematica_filtra_por_igualdad_exacta_de_sector() -> None:
    especies = [
        _especie("GGAL", volumen_usd=1000.0, sector="Bancos"),
        _especie("YPFD", volumen_usd=900.0, sector="O&G"),
        _especie("PAMP", volumen_usd=800.0, sector="Energía"),
    ]
    posiciones, _ = armar_renta_variable(
        especies, pct_rv=20.0, n_rv=5, sector_rv="O&G", monto_total=100_000
    )
    assert {p.ticker for p in posiciones} == {"YPFD"}


def test_tematica_sin_matches_da_rv_sin_candidatos() -> None:
    especies = [_especie("GGAL", volumen_usd=1000.0, sector="Bancos")]
    posiciones, alertas = armar_renta_variable(
        especies, pct_rv=20.0, n_rv=5, sector_rv="Inexistente", monto_total=100_000
    )
    assert posiciones == []
    assert [a.codigo for a in alertas] == [CODIGO_RV_SIN_CANDIDATOS]


def test_sector_none_queda_afuera_con_tematica_activa() -> None:
    especies = [
        _especie("GGAL", volumen_usd=1000.0, sector=None),
        _especie("YPFD", volumen_usd=900.0, sector="O&G"),
    ]
    posiciones, _ = armar_renta_variable(
        especies, pct_rv=20.0, n_rv=5, sector_rv="O&G", monto_total=100_000
    )
    assert {p.ticker for p in posiciones} == {"YPFD"}


def test_sector_none_se_admite_sin_tematica() -> None:
    especies = [
        _especie("GGAL", volumen_usd=1000.0, sector=None),
        _especie("YPFD", volumen_usd=900.0, sector="O&G"),
    ]
    posiciones, _ = armar_renta_variable(especies, pct_rv=20.0, n_rv=5, monto_total=100_000)
    assert {p.ticker for p in posiciones} == {"GGAL", "YPFD"}


def test_universo_real_sin_perfiles_arma_igual_por_liquidez_pura() -> None:
    """El estado real de hoy: `public.perfil_renta_variable` está vacía (0 filas, el job de
    Yahoo nunca corrió), así que TODAS las especies de renta variable llegan con `sector=None`.
    No es un caso borde raro -- es el camino que se ejecuta en cada corrida hasta que el job
    corra. La primera pasada (sector nuevo) queda vacía siempre y todo se decide en la segunda,
    por orden de liquidez pura, sin romper nada."""
    especies = [
        _especie("GGAL", volumen_usd=1000.0, sector=None),
        _especie("YPFD", volumen_usd=900.0, sector=None),
        _especie("PAMP", volumen_usd=800.0, sector=None),
        _especie("AAPL", volumen_usd=700.0, sector=None, clase_activo="cedear"),
        _especie("TSLA", volumen_usd=600.0, sector=None, clase_activo="cedear"),
    ]
    posiciones, alertas = armar_renta_variable(especies, pct_rv=25.0, n_rv=3, monto_total=100_000)

    # Se eligen las tres de mayor liquidez, ni una de sector distinto entra antes que una de
    # más volumen: sin dato de sector no hay "sector nuevo" que preferir.
    assert [p.ticker for p in posiciones] == ["GGAL", "YPFD", "PAMP"]
    assert sum(p.pct_cartera for p in posiciones) == pytest.approx(25.0)
    assert [a.codigo for a in alertas] == [CODIGO_RV_SIN_PERFIL_SECTORIAL]


def test_universo_real_sin_perfiles_con_tematica_activa_no_tiene_ningun_match() -> None:
    """Mismo estado real, pero con `sector_rv` explícito: sin un solo sector informado, ninguna
    especie puede afirmarse que pertenece a la temática (regla 1), así que el bloque de renta
    variable queda vacío y declarado -- no hay ningún candidato que armar_renta_variable pueda
    inventar para llenarlo."""
    especies = [
        _especie("GGAL", volumen_usd=1000.0, sector=None),
        _especie("YPFD", volumen_usd=900.0, sector=None),
    ]
    posiciones, alertas = armar_renta_variable(
        especies, pct_rv=25.0, n_rv=3, sector_rv="Bancos", monto_total=100_000
    )
    assert posiciones == []
    assert [a.codigo for a in alertas] == [CODIGO_RV_SIN_CANDIDATOS]


def test_diversifica_por_sector_en_la_primera_pasada() -> None:
    """Con más candidatos que `n_rv`, la primera pasada prioriza un sector nuevo por sobre el
    mejor volumen dentro de un sector ya representado."""
    especies = [
        _especie("BANCO_A", volumen_usd=1000.0, sector="Bancos"),
        _especie("BANCO_B", volumen_usd=900.0, sector="Bancos"),
        _especie("ENERGIA_A", volumen_usd=500.0, sector="Energía"),
    ]
    posiciones, _ = armar_renta_variable(especies, pct_rv=20.0, n_rv=2, monto_total=100_000)

    tickers = {p.ticker for p in posiciones}
    assert tickers == {"BANCO_A", "ENERGIA_A"}


def test_segunda_pasada_completa_cuando_no_alcanzan_los_sectores_nuevos() -> None:
    """Sólo dos sectores disponibles pero se piden tres posiciones: la segunda pasada completa
    con lo que quedó, en el mismo orden de liquidez."""
    especies = [
        _especie("BANCO_A", volumen_usd=1000.0, sector="Bancos"),
        _especie("BANCO_B", volumen_usd=900.0, sector="Bancos"),
        _especie("ENERGIA_A", volumen_usd=500.0, sector="Energía"),
    ]
    posiciones, _ = armar_renta_variable(especies, pct_rv=30.0, n_rv=3, monto_total=100_000)

    assert {p.ticker for p in posiciones} == {"BANCO_A", "ENERGIA_A", "BANCO_B"}


def test_menos_candidatos_que_n_rv_arma_con_lo_que_hay() -> None:
    especies = [_especie("GGAL", volumen_usd=1000.0, sector="Bancos")]
    posiciones, _ = armar_renta_variable(especies, pct_rv=20.0, n_rv=5, monto_total=100_000)
    assert len(posiciones) == 1


def test_todas_sin_sector_da_alerta_de_perfil_sectorial() -> None:
    especies = [
        _especie("GGAL", volumen_usd=1000.0, sector=None),
        _especie("YPFD", volumen_usd=900.0, sector=None),
    ]
    posiciones, alertas = armar_renta_variable(especies, pct_rv=20.0, n_rv=2, monto_total=100_000)

    assert len(posiciones) == 2
    codigos = {a.codigo for a in alertas}
    assert CODIGO_RV_SIN_PERFIL_SECTORIAL in codigos


def test_con_algun_sector_conocido_no_hay_alerta_de_perfil_sectorial() -> None:
    especies = [_especie("GGAL", volumen_usd=1000.0, sector="Bancos")]
    _, alertas = armar_renta_variable(especies, pct_rv=20.0, n_rv=1, monto_total=100_000)
    assert all(a.codigo != CODIGO_RV_SIN_PERFIL_SECTORIAL for a in alertas)


def test_universo_vacio_da_rv_sin_candidatos() -> None:
    posiciones, alertas = armar_renta_variable([], pct_rv=20.0, n_rv=5, monto_total=100_000)
    assert posiciones == []
    assert [a.codigo for a in alertas] == [CODIGO_RV_SIN_CANDIDATOS]


def test_equiponderacion_exacta_dentro_del_bloque() -> None:
    especies = [
        _especie("GGAL", volumen_usd=1000.0, sector="Bancos"),
        _especie("YPFD", volumen_usd=900.0, sector="O&G"),
        _especie("PAMP", volumen_usd=800.0, sector="Energía"),
    ]
    posiciones, _ = armar_renta_variable(
        especies, pct_rv=30.0, n_rv=3, monto_total=100_000
    )

    assert len(posiciones) == 3
    for posicion in posiciones:
        assert posicion.pct_cartera == 10.0
        assert posicion.monto == 10_000.0
        assert posicion.clase == "renta_variable"
    assert sum(p.pct_cartera for p in posiciones) == 30.0
