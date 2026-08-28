"""El barrido de emisores: la precedencia, la herencia por raíz y la ley que no se traduce.

El test que más importa es el de la precedencia, y no es el más obvio. En lectura,
`_resolver_emisor` de `app/universo/segmentacion.py` hace que `instrumentos.underlying` **gane**
sobre el dato curado.
Así que un barrido que escribiera el emisor de la ficha en una especie que el curado ya cubre no la
completaría: la pisaría en pantalla, invirtiendo en silencio la precedencia declarada. Nada rompe,
nada falla, y el asesor ve otro emisor. De ahí que haya tests de las dos mitades de la guarda —el
LEFT JOIN que arma la cola y el gate por campo al escribir—.

El segundo es el de la ley. `'Extranjera'` no se mapea, y no por prudencia: medido el 28/08/2026,
de las 36 especies que la declaran, 8 no son ley de Nueva York (una es de ley inglesa y siete
declaran ley mixta). Traducirla habría escrito un dato falso en el 22 % de los casos.
"""

from datetime import UTC, datetime
from typing import Any

import pytest

import app.instrumentos.emisores as modulo
from app.externos.byma_ficha import FichaEspecie
from app.instrumentos.emisores import (
    LEY_POR_VALOR_DE_FICHA,
    SQL_GUARDAR,
    SQL_PENDIENTES,
    completar_emisores,
)

AHORA = datetime(2026, 8, 28, 14, 0, tzinfo=UTC)


class FakeConexion:
    """Sirve la cola de pendientes que el test declara y guarda cada escritura.

    `falla_en` corta la corrida en la enésima escritura, para poder afirmar que lo anterior quedó.
    """

    def __init__(self, pendientes: list[dict[str, Any]], *, falla_en: int | None = None) -> None:
        self._pendientes = pendientes
        self.escrituras: list[tuple[Any, ...]] = []
        self._falla_en = falla_en

    async def fetch(self, _query: str, *_args: Any) -> list[dict[str, Any]]:
        return self._pendientes

    async def execute(self, _query: str, *args: Any) -> None:
        if self._falla_en is not None and len(self.escrituras) == self._falla_en:
            raise RuntimeError("la conexión se cayó a mitad de tanda")
        self.escrituras.append(args)

    def escritura_de(self, ticker: str) -> tuple[Any, ...]:
        return next(a for a in self.escrituras if a[0] == ticker)

    @property
    def tickers_escritos(self) -> list[str]:
        return [a[0] for a in self.escrituras]


def _pendiente(
    ticker: str,
    *,
    tipo_tasa: str | None = None,
    law: str | None = None,
    falta_emisor: bool = True,
    falta_ley: bool = True,
) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "tipo_tasa": tipo_tasa,
        "law": law,
        "falta_emisor": falta_emisor,
        "falta_ley": falta_ley,
    }


def _ficha(ticker: str, emisor: str | None = None, ley: str | None = None) -> FichaEspecie:
    return FichaEspecie(ticker=ticker, emisor=emisor, ley_cruda=ley, denominacion="Clase I")


async def _no_esperar(_segundos: float) -> None:
    return None


def _con_fichas(monkeypatch, fichas: dict[str, FichaEspecie | None]) -> None:
    async def falsa(symbols, **_kwargs):
        return {s: fichas[s] for s in symbols if s in fichas}

    monkeypatch.setattr(modulo, "traer_fichas", falsa)


def _sin_bolsar(monkeypatch) -> None:
    async def falsa(_cliente, _ticker):
        return None

    monkeypatch.setattr(modulo, "emisor_bolsar", falsa)


async def _correr(conn: Any, **extra: Any):
    return await completar_emisores(conn, dormir=_no_esperar, ahora=lambda: AHORA, **extra)


# Índices de los parámetros de `SQL_GUARDAR`, para que los asserts se lean.
TICKER, EMISOR, LEY, DENOMINACION, SUBTIPO, CONSULTADA_EN = range(6)


# --- La precedencia -------------------------------------------------------------------------------


async def test_solo_llena_vacios_y_nunca_pisa(monkeypatch) -> None:
    """La segunda mitad de la guarda: si el curado ya cubre el campo, se escribe `None`.

    No alcanza con dejar la especie fuera de la cola, porque una especie entra a la tanda apenas le
    falte **alguno** de los dos campos: YMCXO viene por la ley y su emisor ya está cubierto.
    """
    conn = FakeConexion([_pendiente("YMCXO", falta_emisor=False, falta_ley=True)])
    _con_fichas(monkeypatch, {"YMCXO": _ficha("YMCXO", emisor="YPF S.A.", ley="Nacional")})
    _sin_bolsar(monkeypatch)

    resumen = await _correr(conn)

    escritura = conn.escritura_de("YMCXO")
    assert escritura[EMISOR] is None, "el emisor del curado no se pisa"
    assert escritura[LEY] == "Ley Argentina"
    assert resumen.con_emisor == 0
    assert resumen.con_ley == 1


async def test_la_cola_excluye_lo_que_el_curado_ya_cubre() -> None:
    """La primera mitad de la guarda, y la que sostiene la precedencia entera.

    Se afirma sobre el SQL y no sobre un resultado porque la exclusión **es** el LEFT JOIN: sin
    base de datos no hay forma de ejercitarlo, y simplificar esta consulta a `i.underlying IS NULL`
    invertiría la precedencia sin que nada más en la suite se entere.
    """
    assert "LEFT JOIN public.condiciones_emision" in SQL_PENDIENTES
    assert "i.underlying IS NULL AND ce.underlying IS NULL" in SQL_PENDIENTES
    assert "i.law IS NULL AND ce.ley IS NULL" in SQL_PENDIENTES


async def test_la_escritura_es_de_relleno_y_no_de_reemplazo() -> None:
    """Entre que se leyó la cola y que se escribe la tanda, otra corrida pudo tocar la fila. El
    `COALESCE` es lo que hace que llegar segundo no sea pisar."""
    for columna in ("underlying", "law", "denominacion", "subtipo"):
        assert f"{columna} = COALESCE({columna}," in " ".join(SQL_GUARDAR.split())


# --- La ley ---------------------------------------------------------------------------------------


async def test_una_ley_fuera_de_vocabulario_queda_vacia_y_contada(monkeypatch) -> None:
    """`'Extranjera'` nombra un conjunto y el vocabulario cerrado sólo tiene `'Ley N.Y.'`. Elegir
    ese miembro sería decidir por la fuente: medido, el 22 % de esos casos no es ley de N.Y."""
    conn = FakeConexion([_pendiente("GD30", tipo_tasa="hard-dollar")])
    _con_fichas(
        monkeypatch, {"GD30": _ficha("GD30", emisor="Gobierno Nacional", ley="Extranjera")}
    )
    _sin_bolsar(monkeypatch)

    resumen = await _correr(conn)

    escritura = conn.escritura_de("GD30")
    assert escritura[LEY] is None
    assert escritura[EMISOR] == "Gobierno Nacional", "el emisor sí se escribe: no depende de la ley"
    assert resumen.ley_fuera_de_vocabulario == 1
    assert resumen.con_ley == 0


async def test_extranjera_no_esta_en_la_tabla_de_equivalencias() -> None:
    """Contra que alguien la agregue "para completar más": el porqué está en el docstring del
    módulo, con la medición."""
    assert LEY_POR_VALOR_DE_FICHA == {"Nacional": "Ley Argentina"}


async def test_el_subtipo_se_deriva_cuando_llega_la_ley(monkeypatch) -> None:
    conn = FakeConexion([_pendiente("AL30", tipo_tasa="hard-dollar")])
    _con_fichas(monkeypatch, {"AL30": _ficha("AL30", emisor="Gobierno Nacional", ley="Nacional")})
    _sin_bolsar(monkeypatch)

    await _correr(conn)

    escritura = conn.escritura_de("AL30")
    assert escritura[LEY] == "Ley Argentina"
    assert escritura[SUBTIPO] == "bonar"


async def test_sin_ley_no_hay_subtipo(monkeypatch) -> None:
    conn = FakeConexion([_pendiente("YMCXO", tipo_tasa="hard-dollar")])
    _con_fichas(monkeypatch, {"YMCXO": _ficha("YMCXO", emisor="YPF S.A.")})
    _sin_bolsar(monkeypatch)

    await _correr(conn)

    assert conn.escritura_de("YMCXO")[SUBTIPO] is None


# --- La herencia por raíz -------------------------------------------------------------------------


async def test_hereda_de_una_hermana_con_ficha(monkeypatch) -> None:
    """Emisor y ley son atributos de la emisión: AL30 y AL30D son el mismo bono."""
    conn = FakeConexion([_pendiente("AL30"), _pendiente("AL30D", tipo_tasa="hard-dollar")])
    _con_fichas(
        monkeypatch,
        {"AL30": _ficha("AL30", emisor="Gobierno Nacional", ley="Nacional"), "AL30D": None},
    )
    _sin_bolsar(monkeypatch)

    resumen = await _correr(conn)

    assert conn.escritura_de("AL30D")[EMISOR] == "Gobierno Nacional"
    assert conn.escritura_de("AL30D")[LEY] == "Ley Argentina"
    assert resumen.heredados_por_raiz == 1


async def test_no_reconstruye_raices_que_raiz_emision_no_produce(monkeypatch) -> None:
    """BYMA publica AL30X/Y/Z, un segundo trío del mismo bono. Cortarles la X para llegar a AL30
    sería derivar un ticker de otro por manipulación de strings — el error que costó revertir 121
    tickers inventados (`app/ingesta/raiz.py`)."""
    conn = FakeConexion([_pendiente("AL30"), _pendiente("AL30X")])
    _con_fichas(
        monkeypatch,
        {"AL30": _ficha("AL30", emisor="Gobierno Nacional", ley="Nacional"), "AL30X": None},
    )
    _sin_bolsar(monkeypatch)

    resumen = await _correr(conn)

    assert conn.escritura_de("AL30X")[EMISOR] is None
    assert resumen.heredados_por_raiz == 0


async def test_hermanas_que_se_contradicen_no_heredan(monkeypatch) -> None:
    """Hoy no pasa —cero raíces con dos emisores, medido—, y la guarda existe para que el día que
    pase el resultado sea una celda vacía y no la hermana que el orden puso adelante."""
    conn = FakeConexion(
        [_pendiente("MR46O"), _pendiente("MR46D"), _pendiente("MR46C")]
    )
    _con_fichas(
        monkeypatch,
        {
            "MR46O": _ficha("MR46O", emisor="UNA S.A."),
            "MR46D": _ficha("MR46D", emisor="OTRA S.A."),
            "MR46C": None,
        },
    )
    _sin_bolsar(monkeypatch)

    await _correr(conn)

    assert conn.escritura_de("MR46C")[EMISOR] is None


# --- El fallback de Bolsar ------------------------------------------------------------------------


async def test_bolsar_solo_para_las_especies_con_sufijo_o(monkeypatch) -> None:
    """Medido: Bolsar responde por 50 de 50 de las `O` y por 0 de 49 de las `C`/`D`. Pedirle por
    una `D` es gastar un pedido para nada."""
    conn = FakeConexion([_pendiente("TSC3O"), _pendiente("TSC3D")])
    _con_fichas(monkeypatch, {"TSC3O": None, "TSC3D": None})
    consultados: list[str] = []

    async def falsa(_cliente, ticker):
        consultados.append(ticker)
        return "TRANSPORTADORA DE GAS DEL SUR S.A."

    monkeypatch.setattr(modulo, "emisor_bolsar", falsa)

    resumen = await _correr(conn)

    assert consultados == ["TSC3O"]
    assert conn.escritura_de("TSC3O")[EMISOR] == "TRANSPORTADORA DE GAS DEL SUR S.A."
    assert conn.escritura_de("TSC3D")[EMISOR] is None
    assert resumen.via_bolsar == 1


# --- El avance ------------------------------------------------------------------------------------


async def test_marca_la_consulta_aunque_no_haya_dato(monkeypatch) -> None:
    """Sin esta marca los pendientes no bajan nunca: el antecedente son las nueve tandas de 100
    papeles que bajaron los pendientes de la SEC de 1.539 a 1.536 (13/08/2026)."""
    conn = FakeConexion([_pendiente("OPCION")])
    _con_fichas(monkeypatch, {"OPCION": None})
    _sin_bolsar(monkeypatch)

    resumen = await _correr(conn)

    escritura = conn.escritura_de("OPCION")
    assert escritura[EMISOR] is None
    assert escritura[CONSULTADA_EN] == AHORA
    assert resumen.sin_dato == 1
    assert resumen.procesados == 1


async def test_la_especie_que_no_contesto_no_queda_marcada(monkeypatch) -> None:
    """Ausente del dict de fichas = no se le pudo preguntar. Marcarla convertiría un corte de red
    en un faltante definitivo."""
    conn = FakeConexion([_pendiente("YMCXO"), _pendiente("ROTA")])
    _con_fichas(monkeypatch, {"YMCXO": _ficha("YMCXO", emisor="YPF S.A.")})
    _sin_bolsar(monkeypatch)

    resumen = await _correr(conn)

    assert conn.tickers_escritos == ["YMCXO"]
    assert resumen.procesados == 1
    assert resumen.pendientes == 2


async def test_un_corte_a_mitad_de_tanda_conserva_lo_guardado(monkeypatch) -> None:
    """Es la razón de escribir de a una y no en lote: la corrida siguiente arranca donde ésta
    murió, en vez de repetir toda la tanda."""
    conn = FakeConexion(
        [_pendiente("AAA"), _pendiente("BBB"), _pendiente("CCC")], falla_en=2
    )
    _con_fichas(
        monkeypatch,
        {t: _ficha(t, emisor=f"{t} S.A.") for t in ("AAA", "BBB", "CCC")},
    )
    _sin_bolsar(monkeypatch)

    with pytest.raises(RuntimeError):
        await _correr(conn)

    assert conn.tickers_escritos == ["AAA", "BBB"]


async def test_respeta_el_limite_de_la_tanda(monkeypatch) -> None:
    conn = FakeConexion([_pendiente(f"T{i:03d}") for i in range(10)])
    _con_fichas(monkeypatch, {f"T{i:03d}": _ficha(f"T{i:03d}", emisor="X S.A.") for i in range(10)})
    _sin_bolsar(monkeypatch)

    resumen = await _correr(conn, limite=4)

    assert len(conn.escrituras) == 4
    assert resumen.pendientes == 10
    assert resumen.procesados == 4


async def test_sin_pendientes_no_le_pega_a_la_fuente(monkeypatch) -> None:
    conn = FakeConexion([])

    async def explotar(*_a, **_k):
        raise AssertionError("no hay que consultar la fuente sin pendientes")

    monkeypatch.setattr(modulo, "traer_fichas", explotar)

    resumen = await _correr(conn)

    assert resumen.como_dict()["procesados"] == 0
    assert conn.escrituras == []
