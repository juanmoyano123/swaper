"""`app.armado.renta_variable.armar_renta_variable` — el bloque de renta variable del armado
asistido, probado puro y sin base. Ver el docstring del módulo para el algoritmo completo; acá se
prueba cada paso por separado con fixtures armadas a mano.

## Por qué casi ningún test de acá manda `topes_rv`

`armar_renta_variable` sin `topes_rv` **no** aplica los defaults del perfil: los resuelve el
endpoint con `topes_del_perfil()` antes de llamar. Acá la ausencia es "sin ningún tope", que es el
comportamiento previo a F-078 bit a bit — por eso los tests que no están probando topes siguen
escritos igual que antes de esa feature y siguen valiendo como paridad.

## Por qué `_especie()` sigue aceptando `rubro` después de F-079

El eje "rubro" del armador topea por `sector_codigo` desde F-079, no por `sic_oficina` (ver
`EJES_RV` en el módulo). Acá se construye `EspecieRentaVariable` directo, sin pasar por
`armar_renta_variable` de `especies.py` (que deriva `sector_codigo` de `sic_codigo` vía
`major_group_de`), así que `_especie()` setea `sector_codigo` con el mismo valor que `rubro` a
propósito: preserva exactamente la partición por categoría que estos tests venían probando antes
de la migración (no son códigos SIC reales, son etiquetas de prueba como "Bancos" o "R1"). `rubro`
sigue seteando también `sic_oficina`, porque `FiltroRv.rubros` sigue filtrando por ahí sin cambios
(compatibilidad F-079) y varios tests de filtro dependen de esa dimensión. `sector` es un parámetro
aparte para los tests que prueban específicamente el fallback de la etiqueta ES en las alertas.
"""

import pytest

from app.armado.parametros import FiltroRv, TopesRv
from app.armado.renta_variable import (
    CODIGO_RV_SIN_CANDIDATOS,
    CODIGO_RV_SIN_PERFIL_SECTORIAL,
    CODIGO_RV_SIN_VOLUMEN_USD,
    CODIGO_RV_TOPE_EXCEDIDO,
    CODIGO_RV_TOPE_LIMITA_SELECCION,
    CODIGO_RV_TOPE_SIN_DATO_EN_EJE,
    TOPES_RV_DEFAULT,
    armar_renta_variable,
    topes_del_perfil,
)
from app.concentracion.perfiles import PERFILES
from app.renta_variable.especies import EspecieRentaVariable


def _especie(
    ticker: str,
    *,
    volumen_usd: float | None,
    rubro: str | None = None,
    sector: str | None = None,
    clase_activo: str = "accion",
    pais: str | None = None,
    region: str | None = None,
    mercado: str | None = None,
    moneda: str = "USD",
    sic_codigo: str | None = None,
    estrategia_etf: str | None = None,
    nombre_largo: str | None = None,
) -> EspecieRentaVariable:
    """Una especie mínima: sólo lo que le importa a `armar_renta_variable` -- el resto de los
    campos de `EspecieRentaVariable` no participa del ranking ni de la selección.

    `rubro` setea `sector_codigo` (el eje real desde F-079) y `sic_oficina` (lo que sigue filtrando
    `FiltroRv.rubros`) con el mismo valor -- ver el docstring del módulo. `sector` es aparte, para
    los tests de la etiqueta ES en el mensaje de alerta."""
    return EspecieRentaVariable(
        ticker=ticker,
        clase_activo=clase_activo,
        precio=100.0,
        moneda_cotizacion=moneda,
        cierre_anterior=None,
        variacion=None,
        volumen=volumen_usd,
        volumen_usd=volumen_usd,
        px_bid=None,
        px_ask=None,
        operaciones=None,
        nombre_largo=nombre_largo,
        sic_codigo=sic_codigo,
        sic_oficina=rubro,
        sector_codigo=rubro,
        sector=sector,
        estrategia_etf=estrategia_etf,
        mercado_origen=mercado,
        pais=pais,
        region=region,
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
        _especie("ZETA", volumen_usd=500.0, rubro="Sector A"),
        _especie("ALFA", volumen_usd=500.0, rubro="Sector B"),
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
        _especie("GGAL", volumen_usd=1000.0, rubro="Bancos"),
        _especie("SINVOL", volumen_usd=None, rubro="Bancos"),
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
    especies = [_especie("GGAL", volumen_usd=1000.0, rubro="Bancos")]
    _, alertas = armar_renta_variable(especies, pct_rv=20.0, n_rv=1, monto_total=100_000)
    assert all(a.codigo != CODIGO_RV_SIN_VOLUMEN_USD for a in alertas)


def test_tematica_filtra_por_igualdad_exacta_de_rubro() -> None:
    especies = [
        _especie("GGAL", volumen_usd=1000.0, rubro="Bancos"),
        _especie("YPFD", volumen_usd=900.0, rubro="O&G"),
        _especie("PAMP", volumen_usd=800.0, rubro="Energía"),
    ]
    posiciones, _ = armar_renta_variable(
        especies, pct_rv=20.0, n_rv=5, rubro_rv="O&G", monto_total=100_000
    )
    assert {p.ticker for p in posiciones} == {"YPFD"}


def test_tematica_sin_matches_da_rv_sin_candidatos() -> None:
    especies = [_especie("GGAL", volumen_usd=1000.0, rubro="Bancos")]
    posiciones, alertas = armar_renta_variable(
        especies, pct_rv=20.0, n_rv=5, rubro_rv="Inexistente", monto_total=100_000
    )
    assert posiciones == []
    assert [a.codigo for a in alertas] == [CODIGO_RV_SIN_CANDIDATOS]


def test_rubro_none_queda_afuera_con_tematica_activa() -> None:
    especies = [
        _especie("GGAL", volumen_usd=1000.0, rubro=None),
        _especie("YPFD", volumen_usd=900.0, rubro="O&G"),
    ]
    posiciones, _ = armar_renta_variable(
        especies, pct_rv=20.0, n_rv=5, rubro_rv="O&G", monto_total=100_000
    )
    assert {p.ticker for p in posiciones} == {"YPFD"}


def test_rubro_none_se_admite_sin_tematica() -> None:
    especies = [
        _especie("GGAL", volumen_usd=1000.0, rubro=None),
        _especie("YPFD", volumen_usd=900.0, rubro="O&G"),
    ]
    posiciones, _ = armar_renta_variable(especies, pct_rv=20.0, n_rv=5, monto_total=100_000)
    assert {p.ticker for p in posiciones} == {"GGAL", "YPFD"}


def test_universo_real_sin_perfiles_arma_igual_por_liquidez_pura() -> None:
    """El estado real de hoy: `public.perfil_renta_variable` está vacía (0 filas, el job de
    clasificación no corrió), así que TODAS las especies de renta variable llegan con `rubro=None`.
    No es un caso borde raro -- es el camino que se ejecuta en cada corrida hasta que el job
    corra. La primera pasada (rubro nuevo) queda vacía siempre y todo se decide en la segunda,
    por orden de liquidez pura, sin romper nada."""
    especies = [
        _especie("GGAL", volumen_usd=1000.0, rubro=None),
        _especie("YPFD", volumen_usd=900.0, rubro=None),
        _especie("PAMP", volumen_usd=800.0, rubro=None),
        _especie("AAPL", volumen_usd=700.0, rubro=None, clase_activo="cedear"),
        _especie("TSLA", volumen_usd=600.0, rubro=None, clase_activo="cedear"),
    ]
    posiciones, alertas = armar_renta_variable(especies, pct_rv=25.0, n_rv=3, monto_total=100_000)

    # Se eligen las tres de mayor liquidez, ni una de rubro distinto entra antes que una de
    # más volumen: sin dato de rubro no hay "rubro nuevo" que preferir.
    assert [p.ticker for p in posiciones] == ["GGAL", "YPFD", "PAMP"]
    assert sum(p.pct_cartera for p in posiciones) == pytest.approx(25.0)
    assert [a.codigo for a in alertas] == [CODIGO_RV_SIN_PERFIL_SECTORIAL]


def test_universo_real_sin_perfiles_con_tematica_activa_no_tiene_ningun_match() -> None:
    """Mismo estado real, pero con `rubro_rv` explícito: sin un solo rubro informado, ninguna
    especie puede afirmarse que pertenece a la temática (regla 1), así que el bloque de renta
    variable queda vacío y declarado -- no hay ningún candidato que armar_renta_variable pueda
    inventar para llenarlo."""
    especies = [
        _especie("GGAL", volumen_usd=1000.0, rubro=None),
        _especie("YPFD", volumen_usd=900.0, rubro=None),
    ]
    posiciones, alertas = armar_renta_variable(
        especies, pct_rv=25.0, n_rv=3, rubro_rv="Bancos", monto_total=100_000
    )
    assert posiciones == []
    assert [a.codigo for a in alertas] == [CODIGO_RV_SIN_CANDIDATOS]


def test_diversifica_por_rubro_en_la_primera_pasada() -> None:
    """Con más candidatos que `n_rv`, la primera pasada prioriza un rubro nuevo por sobre el
    mejor volumen dentro de un rubro ya representado."""
    especies = [
        _especie("BANCO_A", volumen_usd=1000.0, rubro="Bancos"),
        _especie("BANCO_B", volumen_usd=900.0, rubro="Bancos"),
        _especie("ENERGIA_A", volumen_usd=500.0, rubro="Energía"),
    ]
    posiciones, _ = armar_renta_variable(especies, pct_rv=20.0, n_rv=2, monto_total=100_000)

    tickers = {p.ticker for p in posiciones}
    assert tickers == {"BANCO_A", "ENERGIA_A"}


def test_segunda_pasada_completa_cuando_no_alcanzan_los_rubros_nuevos() -> None:
    """Sólo dos rubros disponibles pero se piden tres posiciones: la segunda pasada completa
    con lo que quedó, en el mismo orden de liquidez."""
    especies = [
        _especie("BANCO_A", volumen_usd=1000.0, rubro="Bancos"),
        _especie("BANCO_B", volumen_usd=900.0, rubro="Bancos"),
        _especie("ENERGIA_A", volumen_usd=500.0, rubro="Energía"),
    ]
    posiciones, _ = armar_renta_variable(especies, pct_rv=30.0, n_rv=3, monto_total=100_000)

    assert {p.ticker for p in posiciones} == {"BANCO_A", "ENERGIA_A", "BANCO_B"}


def test_menos_candidatos_que_n_rv_arma_con_lo_que_hay() -> None:
    especies = [_especie("GGAL", volumen_usd=1000.0, rubro="Bancos")]
    posiciones, _ = armar_renta_variable(especies, pct_rv=20.0, n_rv=5, monto_total=100_000)
    assert len(posiciones) == 1


def test_todas_sin_rubro_da_alerta_de_perfil_sectorial() -> None:
    especies = [
        _especie("GGAL", volumen_usd=1000.0, rubro=None),
        _especie("YPFD", volumen_usd=900.0, rubro=None),
    ]
    posiciones, alertas = armar_renta_variable(especies, pct_rv=20.0, n_rv=2, monto_total=100_000)

    assert len(posiciones) == 2
    codigos = {a.codigo for a in alertas}
    assert CODIGO_RV_SIN_PERFIL_SECTORIAL in codigos


def test_con_algun_rubro_conocido_no_hay_alerta_de_perfil_sectorial() -> None:
    especies = [_especie("GGAL", volumen_usd=1000.0, rubro="Bancos")]
    _, alertas = armar_renta_variable(especies, pct_rv=20.0, n_rv=1, monto_total=100_000)
    assert all(a.codigo != CODIGO_RV_SIN_PERFIL_SECTORIAL for a in alertas)


def test_universo_vacio_da_rv_sin_candidatos() -> None:
    posiciones, alertas = armar_renta_variable([], pct_rv=20.0, n_rv=5, monto_total=100_000)
    assert posiciones == []
    assert [a.codigo for a in alertas] == [CODIGO_RV_SIN_CANDIDATOS]


def test_equiponderacion_exacta_dentro_del_bloque() -> None:
    especies = [
        _especie("GGAL", volumen_usd=1000.0, rubro="Bancos"),
        _especie("YPFD", volumen_usd=900.0, rubro="O&G"),
        _especie("PAMP", volumen_usd=800.0, rubro="Energía"),
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


# --- Topes por eje (F-078) ---------------------------------------------------------------------
#
# Los defaults del perfil los resuelve el endpoint, no esta función: acá `topes_rv` se manda
# explícito para que cada test declare exactamente qué restricción está probando. Ver el docstring
# del módulo de tests.


def test_sin_topes_es_identico_a_no_mandarlos() -> None:
    """Paridad exacta con el comportamiento previo a F-078: `topes_rv=None` no es "los topes del
    perfil", es "ningún tope". Si esto se rompiera, todos los tests de arriba —que son los de
    antes de la feature— dejarían de valer como paridad."""
    especies = [
        _especie("BANCO_A", volumen_usd=1000.0, rubro="Bancos", mercado="NYSE", pais="US"),
        _especie("BANCO_B", volumen_usd=900.0, rubro="Bancos", mercado="NYSE", pais="US"),
        _especie("BANCO_C", volumen_usd=800.0, rubro="Bancos", mercado="NYSE", pais="US"),
    ]
    sin_kwarg = armar_renta_variable(especies, pct_rv=30.0, n_rv=3, monto_total=100_000)
    con_none = armar_renta_variable(
        especies, pct_rv=30.0, n_rv=3, monto_total=100_000, topes_rv=None
    )

    assert sin_kwarg == con_none
    # Y el resultado es el de siempre: tres papeles del mismo rubro, sin una sola alerta de tope.
    assert [p.ticker for p in sin_kwarg[0]] == ["BANCO_A", "BANCO_B", "BANCO_C"]
    assert sin_kwarg[1] == []


def test_cupo_lleno_saltea_al_candidato_y_sigue_con_el_siguiente() -> None:
    """El corazón del algoritmo: un candidato cuya categoría ya llenó el cupo no corta la
    selección, la deja pasar de largo. Sin tope se elegirían las dos de más volumen (NYSE_A y
    NYSE_B); con el cupo de mercado en 1, la segunda se saltea y entra la de NASDAQ."""
    especies = [
        _especie("NYSE_A", volumen_usd=1000.0, rubro="R1", mercado="NYSE"),
        _especie("NYSE_B", volumen_usd=900.0, rubro="R2", mercado="NYSE"),
        _especie("NASDAQ_C", volumen_usd=800.0, rubro="R3", mercado="NASDAQ"),
    ]
    sin_tope, _ = armar_renta_variable(especies, pct_rv=20.0, n_rv=2, monto_total=100_000)
    assert [p.ticker for p in sin_tope] == ["NYSE_A", "NYSE_B"]

    # 50 % de 2 posiciones = 1 papel por mercado.
    con_tope, alertas = armar_renta_variable(
        especies,
        pct_rv=20.0,
        n_rv=2,
        monto_total=100_000,
        topes_rv=TopesRv(max_pct_mercado=50),
    )
    assert [p.ticker for p in con_tope] == ["NYSE_A", "NASDAQ_C"]
    # Se llegó a las 2 pedidas, así que nada quedó limitado ni excedido.
    assert all(a.codigo != CODIGO_RV_TOPE_LIMITA_SELECCION for a in alertas)
    assert all(a.codigo != CODIGO_RV_TOPE_EXCEDIDO for a in alertas)


def test_tope_incumplible_declara_y_no_levanta_excepcion() -> None:
    """Todo el universo en un solo mercado y un tope que no lo admite: el bloque sale corto, las
    dos alertas lo explican y nada revienta. Un tope incumplible es un hecho del universo, no un
    pedido mal formado."""
    especies = [
        _especie("A", volumen_usd=1000.0, rubro="R1", mercado="NYSE"),
        _especie("B", volumen_usd=900.0, rubro="R2", mercado="NYSE"),
        _especie("C", volumen_usd=800.0, rubro="R3", mercado="NYSE"),
    ]
    posiciones, alertas = armar_renta_variable(
        especies,
        pct_rv=30.0,
        n_rv=3,
        monto_total=100_000,
        topes_rv=TopesRv(max_pct_mercado=34),
    )

    # 34 % de 3 = 1 papel: se arma con uno solo en vez de fallar.
    assert [p.ticker for p in posiciones] == ["A"]
    assert posiciones[0].pct_cartera == pytest.approx(30.0)

    limita = next(a for a in alertas if a.codigo == CODIGO_RV_TOPE_LIMITA_SELECCION)
    assert limita.detalle["pedidas"] == 3
    assert limita.detalle["elegidas"] == 1
    assert limita.detalle["topados"] == [{"eje": "mercado", "categorias": ["NYSE"]}]
    # El mensaje nombra el eje y la categoría: una alerta que dice "un tope se llenó" no le sirve
    # a nadie para decidir qué aflojar.
    assert "mercado de origen" in limita.mensaje
    assert "NYSE" in limita.mensaje

    # Y el peso real quedó por encima del tope, porque la posición única se lleva todo el bloque.
    excedido = next(a for a in alertas if a.codigo == CODIGO_RV_TOPE_EXCEDIDO)
    assert excedido.detalle["eje"] == "mercado"
    assert excedido.detalle["categoria"] == "NYSE"
    assert excedido.detalle["pct"] == pytest.approx(100.0)
    assert excedido.detalle["tope"] == 34
    assert "NYSE" in excedido.mensaje and "100,0 %" in excedido.mensaje


def test_el_exceso_post_seleccion_se_mide_sobre_los_pesos_que_quedaron() -> None:
    """Los cupos se reparten contra `n_rv`, pero los pesos se reparten contra lo que se eligió: dos
    de cuatro es 50 %, dos de dos es 100 %. Sin la verificación post-selección el tope se declararía
    cumplido mirando un denominador que la cartera no tiene."""
    especies = [
        _especie("NYSE_A", volumen_usd=1000.0, rubro="R1", mercado="NYSE"),
        _especie("NYSE_B", volumen_usd=900.0, rubro="R2", mercado="NYSE"),
    ]
    # 50 % de 4 = cupo 2, y los dos candidatos NYSE entran. Pero son las únicas 2 posiciones que
    # hay, así que NYSE termina siendo el 100 % del bloque y no el 50 % que el cupo prometía.
    _, alertas = armar_renta_variable(
        especies,
        pct_rv=20.0,
        n_rv=4,
        monto_total=100_000,
        topes_rv=TopesRv(max_pct_mercado=50),
    )
    excedido = next(a for a in alertas if a.codigo == CODIGO_RV_TOPE_EXCEDIDO)
    assert excedido.detalle["posiciones"] == 2
    assert excedido.detalle["total"] == 2
    assert excedido.detalle["pct"] == pytest.approx(100.0)
    # Faltaron candidatos, no cupo: nadie fue frenado por un tope, así que esa otra alerta no va.
    assert all(a.codigo != CODIGO_RV_TOPE_LIMITA_SELECCION for a in alertas)


def test_categoria_faltante_no_computa_contra_el_tope_pero_se_cuenta() -> None:
    """Criterio `sector_computable()` aplicado a los cinco ejes: no se acota lo que no se conoce.
    Con el cupo de país en 1, las dos especies sin país entran igual —si el faltante fuera una
    categoría más, la segunda habría quedado afuera— y `rv_tope_sin_dato_en_eje` declara sobre
    cuántas de cuántas posiciones se pudo medir el tope."""
    especies = [
        _especie("US_A", volumen_usd=1000.0, rubro="R1", pais="US"),
        _especie("SINPAIS_B", volumen_usd=900.0, rubro="R2", pais=None),
        _especie("SINPAIS_C", volumen_usd=800.0, rubro="R3", pais=None),
        _especie("US_D", volumen_usd=700.0, rubro="R4", pais="US"),
    ]
    # 50 % de 3 = cupo 1 por país.
    posiciones, alertas = armar_renta_variable(
        especies,
        pct_rv=30.0,
        n_rv=3,
        monto_total=100_000,
        topes_rv=TopesRv(max_pct_pais=50),
    )

    assert [p.ticker for p in posiciones] == ["US_A", "SINPAIS_B", "SINPAIS_C"]

    sin_dato = next(a for a in alertas if a.codigo == CODIGO_RV_TOPE_SIN_DATO_EN_EJE)
    assert sin_dato.detalle == {
        "eje": "pais",
        "medidas": 1,
        "total": 3,
        "sin_dato": 2,
        "tope": 50,
    }
    assert "sobre 1 de 3 posiciones" in sin_dato.mensaje
    assert "país" in sin_dato.mensaje


def test_un_eje_sin_ningun_dato_se_declara_igual() -> None:
    """El estado de hoy del eje país: `pais` es `None` en todo el universo hasta que aterrice el
    curado de F-078 Fase 3. El tope no acota nada y eso **se dice** -- si no, una cartera armada
    con el tope de país activo parecería haberlo cumplido."""
    especies = [_especie("A", volumen_usd=1000.0, rubro="R1")]
    _, alertas = armar_renta_variable(
        especies, pct_rv=20.0, n_rv=1, monto_total=100_000, topes_rv=TopesRv(max_pct_pais=40)
    )
    sin_dato = next(a for a in alertas if a.codigo == CODIGO_RV_TOPE_SIN_DATO_EN_EJE)
    assert sin_dato.detalle["medidas"] == 0
    assert sin_dato.detalle["total"] == 1


def test_un_tope_chico_acota_el_eje_en_vez_de_prohibirlo() -> None:
    """El `max(1, ...)` del cupo. Con 10 % sobre 4 posiciones, `floor` da 0: sin el piso, ninguna
    categoría podría llevarse ni un papel y el bloque saldría vacío por aritmética y no por falta
    de candidatos. Con el piso se arma, y el exceso que ese piso produce se declara."""
    especies = [
        _especie("A", volumen_usd=1000.0, rubro="R1"),
        _especie("B", volumen_usd=900.0, rubro="R2"),
        _especie("C", volumen_usd=800.0, rubro="R3"),
        _especie("D", volumen_usd=700.0, rubro="R4"),
    ]
    posiciones, alertas = armar_renta_variable(
        especies,
        pct_rv=40.0,
        n_rv=4,
        monto_total=100_000,
        topes_rv=TopesRv(max_pct_rubro=10),
    )

    assert [p.ticker for p in posiciones] == ["A", "B", "C", "D"]
    # Cada rubro pesa 25 % del bloque contra un tope del 10 %: cuatro excesos, uno por rubro.
    excedidos = [a for a in alertas if a.codigo == CODIGO_RV_TOPE_EXCEDIDO]
    assert {a.detalle["categoria"] for a in excedidos} == {"R1", "R2", "R3", "R4"}
    assert all(a.detalle["pct"] == pytest.approx(25.0) for a in excedidos)


def test_ningun_candidato_entra_en_los_topes_da_rv_sin_candidatos() -> None:
    """Caso límite del `max(1, ...)`: con el cupo en 1 y una sola categoría, la segunda pasada no
    tiene a quién agregar. Para quien lee la cartera el hecho es el mismo que un universo vacío
    —no hay bloque— así que se usa el mismo código, con el detalle de qué lo frenó."""
    especies = [
        _especie("A", volumen_usd=1000.0, rubro="R1", mercado="NYSE"),
        _especie("B", volumen_usd=900.0, rubro="R1", mercado="NYSE"),
    ]
    posiciones, alertas = armar_renta_variable(
        especies,
        pct_rv=20.0,
        n_rv=1,
        monto_total=100_000,
        topes_rv=TopesRv(max_pct_mercado=50),
    )
    # Con n_rv=1 el cupo es max(1, 0) = 1, así que A entra: el bloque no queda vacío.
    assert [p.ticker for p in posiciones] == ["A"]
    assert any(a.codigo == CODIGO_RV_TOPE_EXCEDIDO for a in alertas)


def test_dos_topes_a_la_vez_se_evaluan_los_dos() -> None:
    """Los ejes son independientes y ninguno le gana al otro: un candidato tiene que caber en
    todos. Es la regla 7 del dominio -- no hay score compuesto que pondere rubro contra mercado."""
    especies = [
        _especie("A", volumen_usd=1000.0, rubro="Tech", mercado="NASDAQ"),
        _especie("B", volumen_usd=900.0, rubro="Tech", mercado="NYSE"),
        _especie("C", volumen_usd=800.0, rubro="Energía", mercado="NASDAQ"),
        _especie("D", volumen_usd=700.0, rubro="Energía", mercado="NYSE"),
    ]
    # Cupo 1 en cada eje: A se lleva Tech y NASDAQ, así que B (Tech) y C (NASDAQ) quedan afuera.
    posiciones, alertas = armar_renta_variable(
        especies,
        pct_rv=20.0,
        n_rv=2,
        monto_total=100_000,
        topes_rv=TopesRv(max_pct_rubro=50, max_pct_mercado=50),
    )
    assert [p.ticker for p in posiciones] == ["A", "D"]
    assert all(a.codigo != CODIGO_RV_TOPE_LIMITA_SELECCION for a in alertas)


def test_el_tope_agrupa_el_mismo_mercado_escrito_de_dos_maneras() -> None:
    """`NYSE Arca` (81 papeles) y `NYSE ARCA` (12) son un solo mercado escrito de dos formas por la
    fuente: contarlos como dos categorías haría que el tope mida la mitad de la concentración real,
    que es el lado peligroso del error."""
    especies = [
        _especie("A", volumen_usd=1000.0, rubro="R1", mercado="NYSE Arca"),
        _especie("B", volumen_usd=900.0, rubro="R2", mercado="NYSE ARCA"),
        _especie("C", volumen_usd=800.0, rubro="R3", mercado="NASDAQ"),
    ]
    posiciones, alertas = armar_renta_variable(
        especies,
        pct_rv=20.0,
        n_rv=2,
        monto_total=100_000,
        topes_rv=TopesRv(max_pct_mercado=50),
    )
    assert [p.ticker for p in posiciones] == ["A", "C"]
    # La categoría se nombra con el literal de la fuente que se vio primero, no con la forma
    # plegada: el tope agrupa, pero no reescribe lo que BYMA publica.
    assert all(a.codigo != CODIGO_RV_TOPE_EXCEDIDO for a in alertas)


def test_es_deterministico_con_topes_y_filtro_activos() -> None:
    """Misma entrada, misma cartera y mismas alertas, corrido dos veces con el universo dado vuelta.
    No hay aleatoriedad en ninguna parte del camino: el orden sale de (volumen, ticker) y las
    alertas del orden fijo de `EJES_RV`."""
    especies = [
        _especie("A", volumen_usd=1000.0, rubro="Tech", mercado="NYSE", pais="US"),
        _especie("B", volumen_usd=1000.0, rubro="Tech", mercado="NASDAQ", pais="US"),
        _especie("C", volumen_usd=800.0, rubro="Energía", mercado="NYSE", pais="BR"),
        _especie("D", volumen_usd=800.0, rubro="Energía", mercado="NASDAQ", pais=None),
    ]
    topes = TopesRv(max_pct_rubro=50, max_pct_pais=50, max_pct_mercado=50)
    filtro = FiltroRv(mercados=["nyse", "nasdaq"])

    primera = armar_renta_variable(
        especies, pct_rv=30.0, n_rv=3, monto_total=100_000, topes_rv=topes, filtro_rv=filtro
    )
    segunda = armar_renta_variable(
        list(reversed(especies)),
        pct_rv=30.0,
        n_rv=3,
        monto_total=100_000,
        topes_rv=topes,
        filtro_rv=filtro,
    )
    assert primera == segunda
    # El recorrido, para que el resultado no sea un número mágico: A entra y se lleva Tech, US y
    # NYSE. B queda afuera por rubro. C tiene rubro y país libres pero NYSE lleno, así que se
    # saltea. D entra (Energía y NASDAQ libres; su país `None` no consume cupo). Quedan dos de las
    # tres pedidas y ningún candidato más cabe.
    assert [p.ticker for p in primera[0]] == ["A", "D"]
    codigos = [a.codigo for a in primera[1]]
    assert CODIGO_RV_TOPE_LIMITA_SELECCION in codigos


# --- Defaults por perfil -----------------------------------------------------------------------


def test_topes_del_perfil_devuelve_el_default_cuando_no_se_manda_nada() -> None:
    assert topes_del_perfil("moderado", None) == TOPES_RV_DEFAULT["moderado"]


def test_topes_del_perfil_no_completa_un_tope_parcial_con_el_default() -> None:
    """Lo que el llamador declara es la lista entera de lo que quiere acotar. Si se mergeara con el
    default, mandar `null` en un eje sería indistinguible de no mandarlo y apagar un eje pasaría a
    ser inexpresable."""
    pedido = TopesRv(max_pct_rubro=25)
    resuelto = topes_del_perfil("conservador", pedido)
    assert resuelto == pedido
    assert resuelto.max_pct_pais is None


@pytest.mark.parametrize("perfil", ["conservador", "moderado", "agresivo"])
def test_la_region_nunca_se_acota_mas_que_el_pais(perfil: str) -> None:
    """No es gusto, es aritmética: una región contiene países, así que su concentración nunca puede
    ser menor que la del país más grande que la integra. Un tope de región por debajo del de país
    se activaría siempre primero y volvería letra muerta al de país."""
    topes = TOPES_RV_DEFAULT[perfil]
    assert topes.max_pct_region is not None and topes.max_pct_pais is not None
    assert topes.max_pct_region >= topes.max_pct_pais


@pytest.mark.parametrize("perfil", ["conservador", "moderado", "agresivo"])
def test_el_tope_de_moneda_viene_apagado_en_los_tres_perfiles(perfil: str) -> None:
    """Medido el 28/08/2026: de las 286 especies CEDEAR candidatas en USD, 276 (96,5 %) son la
    hermana `D`/`C` de un papel que ya cotiza en pesos. Un tope de moneda no diversifica -- fuerza
    a comprar el mismo papel dos veces. El eje queda disponible y apagado de fábrica."""
    assert TOPES_RV_DEFAULT[perfil].max_pct_moneda is None


def test_los_topes_de_rubro_espejan_los_de_sector_de_renta_fija() -> None:
    """`conservador` tiene que significar lo mismo de los dos lados de la cartera, o el perfil pasa
    a significar dos cosas según qué mitad lo mire."""
    for perfil, topes in TOPES_RV_DEFAULT.items():
        assert topes.max_pct_rubro == PERFILES[perfil]["max_sector"]


# --- `FiltroRv` y la compatibilidad de `rubro_rv` ----------------------------------------------


def test_filtro_en_interseccion_exige_todas_las_dimensiones_declaradas() -> None:
    especies = [
        _especie("AMBAS", volumen_usd=1000.0, rubro="Tech", mercado="NASDAQ"),
        _especie("SOLO_RUBRO", volumen_usd=900.0, rubro="Tech", mercado="NYSE"),
        _especie("SOLO_MERCADO", volumen_usd=800.0, rubro="Energía", mercado="NASDAQ"),
    ]
    posiciones, _ = armar_renta_variable(
        especies,
        pct_rv=20.0,
        n_rv=5,
        monto_total=100_000,
        filtro_rv=FiltroRv(rubros=["Tech"], mercados=["NASDAQ"]),
    )
    assert [p.ticker for p in posiciones] == ["AMBAS"]


def test_filtro_en_union_alcanza_con_una_dimension() -> None:
    """El preset de metales preciosos: tres declaraciones de fuentes distintas —el metal físico de
    un ETF, el SIC 1040 de una minera y el nombre oficial de BYMA— y ninguna especie tiene las
    tres. Por eso la unión existe."""
    especies = [
        _especie("GLD", volumen_usd=1000.0, estrategia_etf="activo_fisico"),
        _especie("AEM", volumen_usd=900.0, sic_codigo="1040", rubro="Office of Manufacturing"),
        _especie("GDX", volumen_usd=800.0, nombre_largo="Van Eck Gold Miners ETF/USA"),
        _especie("XOM", volumen_usd=700.0, sic_codigo="1311", rubro="Office of Energy"),
    ]
    posiciones, _ = armar_renta_variable(
        especies,
        pct_rv=20.0,
        n_rv=5,
        monto_total=100_000,
        filtro_rv=FiltroRv(
            estrategias_etf=["activo_fisico"],
            sic_codigos=["1040"],
            palabras_en_nombre=["gold", "silver"],
            modo="union",
        ),
    )
    assert {p.ticker for p in posiciones} == {"GLD", "AEM", "GDX"}


def test_la_palabra_del_nombre_se_busca_entera_y_no_adentro_de_otra() -> None:
    """`gold` adentro de `Goldman` es el mismo bug que `etfs.py` ya tuvo con `ETF` adentro de
    `NETFLIX`. Goldman Sachs está en el universo de CEDEARs, así que no es un caso hipotético."""
    especies = [
        _especie("GS", volumen_usd=1000.0, nombre_largo="Goldman Sachs Group Inc"),
        _especie("GDX", volumen_usd=900.0, nombre_largo="Van Eck Gold Miners ETF/USA"),
    ]
    posiciones, _ = armar_renta_variable(
        especies,
        pct_rv=20.0,
        n_rv=5,
        monto_total=100_000,
        filtro_rv=FiltroRv(palabras_en_nombre=["gold"]),
    )
    assert [p.ticker for p in posiciones] == ["GDX"]


def test_el_filtro_de_mercado_no_distingue_mayusculas() -> None:
    """La fuente escribe `NYSE Arca` en 81 papeles y `NYSE ARCA` en 12: el asesor pide un mercado,
    no dos formas de escribirlo."""
    especies = [
        _especie("A", volumen_usd=1000.0, rubro="R1", mercado="NYSE ARCA"),
        _especie("B", volumen_usd=900.0, rubro="R2", mercado="NASDAQ"),
    ]
    posiciones, _ = armar_renta_variable(
        especies,
        pct_rv=20.0,
        n_rv=5,
        monto_total=100_000,
        filtro_rv=FiltroRv(mercados=["NYSE Arca"]),
    )
    assert [p.ticker for p in posiciones] == ["A"]


def test_un_dato_faltante_nunca_cumple_una_dimension_activa() -> None:
    """Mismo criterio que `rubro_rv` desde F-052: no se puede afirmar que una especie sin país
    pertenece al país pedido (regla 1). Vale para las seis dimensiones, no sólo para el rubro."""
    especies = [
        _especie("SINPAIS", volumen_usd=1000.0, rubro="R1", pais=None),
        _especie("CONPAIS", volumen_usd=900.0, rubro="R2", pais="US"),
    ]
    posiciones, _ = armar_renta_variable(
        especies, pct_rv=20.0, n_rv=5, monto_total=100_000, filtro_rv=FiltroRv(paises=["US"])
    )
    assert [p.ticker for p in posiciones] == ["CONPAIS"]


def test_un_filtro_sin_dimensiones_declaradas_no_filtra_nada() -> None:
    """Un preset vacío es un preset mal armado, no un universo vacío."""
    especies = [
        _especie("A", volumen_usd=1000.0, rubro="R1"),
        _especie("B", volumen_usd=900.0, rubro="R2"),
    ]
    posiciones, _ = armar_renta_variable(
        especies, pct_rv=20.0, n_rv=5, monto_total=100_000, filtro_rv=FiltroRv()
    )
    assert [p.ticker for p in posiciones] == ["A", "B"]


def test_el_rubro_rv_viejo_sigue_valiendo_junto_al_filtro_nuevo() -> None:
    """`rubro_rv` es un `filtro_rv` de una dimensión y un valor: se pliega adentro y se intersecta
    con el resto de lo que el filtro declare. Es el campo que el frontend viene mandando desde
    F-052 y sacarlo rompería el armador en producción por un renombre."""
    especies = [
        _especie("AMBAS", volumen_usd=1000.0, rubro="Tech", mercado="NASDAQ"),
        _especie("OTRO_MERCADO", volumen_usd=900.0, rubro="Tech", mercado="NYSE"),
        _especie("OTRO_RUBRO", volumen_usd=800.0, rubro="Energía", mercado="NASDAQ"),
    ]
    posiciones, _ = armar_renta_variable(
        especies,
        pct_rv=20.0,
        n_rv=5,
        monto_total=100_000,
        rubro_rv="Tech",
        filtro_rv=FiltroRv(mercados=["NASDAQ"]),
    )
    assert [p.ticker for p in posiciones] == ["AMBAS"]


def test_rubro_rv_y_filtro_rv_que_dicen_lo_mismo_no_son_conflicto() -> None:
    especies = [_especie("A", volumen_usd=1000.0, rubro="Tech")]
    posiciones, _ = armar_renta_variable(
        especies,
        pct_rv=20.0,
        n_rv=5,
        monto_total=100_000,
        rubro_rv="Tech",
        filtro_rv=FiltroRv(rubros=["Tech"]),
    )
    assert [p.ticker for p in posiciones] == ["A"]


def test_rubro_rv_que_contradice_al_filtro_no_elige_ninguno() -> None:
    """Mismo criterio que `condiciones_en_conflicto` en la ingesta: elegir exigiría una precedencia
    que nadie estableció. En el endpoint esto sale como 422."""
    especies = [_especie("A", volumen_usd=1000.0, rubro="Tech")]
    with pytest.raises(ValueError, match="contradice"):
        armar_renta_variable(
            especies,
            pct_rv=20.0,
            n_rv=5,
            monto_total=100_000,
            rubro_rv="Tech",
            filtro_rv=FiltroRv(rubros=["Energía"]),
        )


# --- El eje "rubro" mide `sector_codigo`, no `sic_oficina` (F-079) -------------------------------


def test_filtro_rv_sectores_filtra_por_sector_codigo_y_no_por_sic_oficina() -> None:
    """`sic_oficina` puede ser igual entre dos especies de sectores SIC distintos (oficinas
    ambiguas de la SEC): `filtro_rv.sectores` filtra por el código de major group, una dimensión
    aparte de `rubros`."""
    especies = [
        _especie("TECH", volumen_usd=1000.0, rubro="73"),
        _especie("PETROLEO", volumen_usd=900.0, rubro="29"),
    ]
    posiciones, _ = armar_renta_variable(
        especies,
        pct_rv=20.0,
        n_rv=5,
        monto_total=100_000,
        filtro_rv=FiltroRv(sectores=["73"]),
    )
    assert [p.ticker for p in posiciones] == ["TECH"]


def test_filtro_rv_sectores_un_dato_faltante_nunca_cumple() -> None:
    especies = [
        _especie("SIN_SIC", volumen_usd=1000.0),
        _especie("TECH", volumen_usd=900.0, rubro="73"),
    ]
    posiciones, _ = armar_renta_variable(
        especies,
        pct_rv=20.0,
        n_rv=5,
        monto_total=100_000,
        filtro_rv=FiltroRv(sectores=["73"]),
    )
    assert [p.ticker for p in posiciones] == ["TECH"]


def test_el_tope_de_rubro_topa_por_sector_codigo_y_no_por_sic_oficina() -> None:
    """Dos especies con el mismo `sic_oficina` pero distinto `sector_codigo` no comparten cupo, y
    dos con el mismo `sector_codigo` pero distinto `sic_oficina` sí lo comparten -- el tope mide el
    eje nuevo, no el viejo."""
    especies = [
        EspecieRentaVariable(
            ticker="A",
            clase_activo="cedear",
            precio=100.0,
            moneda_cotizacion="USD",
            cierre_anterior=None,
            variacion=None,
            volumen=1000.0,
            volumen_usd=1000.0,
            px_bid=None,
            px_ask=None,
            operaciones=None,
            sic_oficina="Office of Technology",
            sector_codigo="73",
        ),
        EspecieRentaVariable(
            ticker="B",
            clase_activo="cedear",
            precio=100.0,
            moneda_cotizacion="USD",
            cierre_anterior=None,
            variacion=None,
            volumen=900.0,
            volumen_usd=900.0,
            px_bid=None,
            px_ask=None,
            operaciones=None,
            sic_oficina="Office of Technology",
            sector_codigo="29",
        ),
    ]
    # Mismo `sic_oficina` en las dos, cupo de rubro en 1: si el tope todavía midiera `sic_oficina`
    # el candidato B quedaría afuera. Mide `sector_codigo`, que es distinto en las dos, así que
    # entran las dos.
    posiciones, alertas = armar_renta_variable(
        especies,
        pct_rv=20.0,
        n_rv=2,
        monto_total=100_000,
        topes_rv=TopesRv(max_pct_rubro=50),
    )
    assert {p.ticker for p in posiciones} == {"A", "B"}
    assert all(a.codigo != CODIGO_RV_TOPE_LIMITA_SELECCION for a in alertas)


def test_rv_sin_perfil_sectorial_mira_sector_codigo_y_no_sic_oficina() -> None:
    """Una especie con `sic_oficina` pero sin `sector_codigo` (sin `sic_codigo` que derivar) cuenta
    como "sin rubro" desde F-079: la alerta migró de eje junto con el resto del armador."""
    especie = EspecieRentaVariable(
        ticker="A",
        clase_activo="cedear",
        precio=100.0,
        moneda_cotizacion="USD",
        cierre_anterior=None,
        variacion=None,
        volumen=1000.0,
        volumen_usd=1000.0,
        px_bid=None,
        px_ask=None,
        operaciones=None,
        sic_oficina="Office of Technology",
        sector_codigo=None,
    )
    _, alertas = armar_renta_variable([especie], pct_rv=20.0, n_rv=1, monto_total=100_000)
    assert any(a.codigo == CODIGO_RV_SIN_PERFIL_SECTORIAL for a in alertas)


def test_rv_sin_perfil_sectorial_no_dispara_con_sector_codigo_aunque_falte_sic_oficina() -> None:
    especie = EspecieRentaVariable(
        ticker="A",
        clase_activo="cedear",
        precio=100.0,
        moneda_cotizacion="USD",
        cierre_anterior=None,
        variacion=None,
        volumen=1000.0,
        volumen_usd=1000.0,
        px_bid=None,
        px_ask=None,
        operaciones=None,
        sic_oficina=None,
        sector_codigo="73",
    )
    _, alertas = armar_renta_variable([especie], pct_rv=20.0, n_rv=1, monto_total=100_000)
    assert all(a.codigo != CODIGO_RV_SIN_PERFIL_SECTORIAL for a in alertas)


# --- La etiqueta ES del sector en el mensaje de las alertas de rubro (F-079) ---------------------


def test_la_alerta_de_tope_limitado_usa_la_etiqueta_es_del_sector_cuando_existe() -> None:
    especies = [
        _especie("A", volumen_usd=1000.0, rubro="73", sector="Software y datos"),
        _especie("B", volumen_usd=900.0, rubro="73", sector="Software y datos"),
    ]
    _, alertas = armar_renta_variable(
        especies,
        pct_rv=20.0,
        n_rv=2,
        monto_total=100_000,
        topes_rv=TopesRv(max_pct_rubro=50),
    )
    limita = next(a for a in alertas if a.codigo == CODIGO_RV_TOPE_LIMITA_SELECCION)
    assert "Software y datos" in limita.mensaje
    assert limita.detalle["topados"] == [{"eje": "rubro", "categorias": ["Software y datos"]}]


def test_la_alerta_de_tope_limitado_usa_el_codigo_crudo_sin_traduccion_curada() -> None:
    """Sin `sector` (sin CSV validado, o major group sin fila en el curado), la alerta muestra
    `sector_codigo` tal cual -- el mismo fallback declarado que `especies.py`."""
    especies = [
        _especie("A", volumen_usd=1000.0, rubro="73"),
        _especie("B", volumen_usd=900.0, rubro="73"),
    ]
    _, alertas = armar_renta_variable(
        especies,
        pct_rv=20.0,
        n_rv=2,
        monto_total=100_000,
        topes_rv=TopesRv(max_pct_rubro=50),
    )
    limita = next(a for a in alertas if a.codigo == CODIGO_RV_TOPE_LIMITA_SELECCION)
    assert "73" in limita.mensaje
    assert limita.detalle["topados"] == [{"eje": "rubro", "categorias": ["73"]}]


def test_la_alerta_de_tope_excedido_usa_la_etiqueta_es_del_sector_cuando_existe() -> None:
    especies = [
        _especie("A", volumen_usd=1000.0, rubro="73", sector="Software y datos", mercado="NYSE"),
        _especie("B", volumen_usd=900.0, rubro="73", sector="Software y datos", mercado="NYSE"),
    ]
    _, alertas = armar_renta_variable(
        especies,
        pct_rv=20.0,
        n_rv=2,
        monto_total=100_000,
        topes_rv=TopesRv(max_pct_rubro=34),
    )
    excedido = next(
        a for a in alertas if a.codigo == CODIGO_RV_TOPE_EXCEDIDO and a.detalle["eje"] == "rubro"
    )
    assert excedido.detalle["categoria"] == "Software y datos"
    assert "Software y datos" in excedido.mensaje


def test_otros_ejes_no_traducen_ni_con_sector_seteado() -> None:
    """La traducción ES sólo aplica al eje "rubro": el mercado sigue mostrando el literal de la
    fuente, nunca `especie.sector`."""
    especies = [
        _especie(
            "A", volumen_usd=1000.0, mercado="NYSE", sector="Software y datos", rubro="73"
        ),
        _especie(
            "B", volumen_usd=900.0, mercado="NYSE", sector="Software y datos", rubro="29"
        ),
    ]
    _, alertas = armar_renta_variable(
        especies,
        pct_rv=20.0,
        n_rv=2,
        monto_total=100_000,
        topes_rv=TopesRv(max_pct_mercado=34),
    )
    excedido = next(
        a for a in alertas if a.codigo == CODIGO_RV_TOPE_EXCEDIDO and a.detalle["eje"] == "mercado"
    )
    assert excedido.detalle["categoria"] == "NYSE"
