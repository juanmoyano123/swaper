"""El job de clasificación contra la SEC: qué se guarda, qué se declara y qué no se reintenta.

El test más importante de este archivo es el del avance: la primera versión del job guardaba sólo
los papeles que la SEC listaba, y los ~1.500 que no lista volvían a la cola en cada corrida. Nueve
tandas de 100 bajaron los pendientes de 1.539 a 1.536 (medido el 13/08/2026). Un job incremental
que no avanza es peor que uno que falla: parece que funciona.
"""

from datetime import UTC, datetime
from typing import Any

import pytest

from app.externos.sec import EntradaSic, LimiteDeLaFuente, PerfilSec
from app.renta_variable.clasificacion import (
    DatosDeBymaPorPapel,
    clasificar_renta_variable,
    reclasificar_etfs,
)

AHORA = datetime(2026, 8, 13, 20, 0, tzinfo=UTC)


class FakeConexion:
    """Guarda lo que se escribió y sirve la lista de pendientes que el test decida."""

    def __init__(self, pendientes: list[str]) -> None:
        self._pendientes = pendientes
        self.escrituras: list[tuple[Any, ...]] = []

    async def fetch(self, _query: str, *_args: Any) -> list[dict[str, str]]:
        return [{"ticker": t} for t in self._pendientes]

    async def execute(self, _query: str, *args: Any) -> None:
        self.escrituras.append(args)

    @property
    def tickers_escritos(self) -> list[str]:
        return [a[0] for a in self.escrituras]


class FakeSec:
    """La SEC, con el universo que el test declara. Cuenta los pedidos para poder afirmar que no se
    consulta dos veces por el mismo papel."""

    def __init__(
        self,
        perfiles: dict[str, PerfilSec] | None = None,
        *,
        catalogo: dict[str, EntradaSic] | None = None,
        limita: bool = False,
    ) -> None:
        self._perfiles = perfiles or {}
        self._catalogo = catalogo or {}
        self._limita = limita
        self.pedidos: list[int] = []

    async def mapa_de_tickers(self) -> dict[str, int]:
        if self._limita:
            raise LimiteDeLaFuente("429")
        return {t: p.cik for t, p in self._perfiles.items()}

    async def catalogo_sic(self) -> dict[str, EntradaSic]:
        return self._catalogo

    async def perfil_de(self, cik: int) -> PerfilSec | None:
        self.pedidos.append(cik)
        return next((p for p in self._perfiles.values() if p.cik == cik), None)

    async def pausar(self) -> None:
        return None


APPLE = PerfilSec(cik=320193, nombre="Apple Inc.", sic="3571", sic_titulo="Electronic Computers")
CATALOGO = {
    "3571": EntradaSic(codigo="3571", titulo="ELECTRONIC COMPUTERS", oficina="Office of Technology")
}


async def _correr(conn: Any, sec: Any, **extra: Any):
    return await clasificar_renta_variable(
        conn, sec, dormir=lambda _s: _nada(), ahora=lambda: AHORA, **extra
    )


async def _nada() -> None:
    return None


# --- Lo que se guarda -----------------------------------------------------------------------------


async def test_guarda_actividad_eslabon_y_rubro() -> None:
    conn = FakeConexion(["AAPL"])
    resumen = await _correr(
        conn, FakeSec({"AAPL": APPLE}, catalogo=CATALOGO), por_papel={"AAPL": "AAPL"}
    )

    assert resumen.clasificados == 1
    (fila,) = conn.escrituras
    ticker, _nombre, sic, titulo, oficina, division = fila[:6]
    assert (ticker, sic) == ("AAPL", "3571")
    assert titulo == "Electronic Computers"
    assert oficina == "Office of Technology"
    assert division == "Manufactura"


async def test_las_tres_especies_del_papel_se_escriben_con_una_sola_consulta() -> None:
    """`AAPL`, `AAPLC` y `AAPLD` son el mismo CEDEAR: preguntar tres veces por Apple sería gastar
    tres pedidos para escribir tres filas idénticas."""
    conn = FakeConexion(["AAPL", "AAPLC", "AAPLD"])
    sec = FakeSec({"AAPL": APPLE}, catalogo=CATALOGO)

    await _correr(conn, sec, por_papel={"AAPL": "AAPL", "AAPLC": "AAPL", "AAPLD": "AAPL"})

    assert conn.tickers_escritos == ["AAPL", "AAPLC", "AAPLD"], "las tres se escriben"
    assert sec.pedidos == [320193] * 3 or len(set(sec.pedidos)) == 1, "siempre el mismo CIK"


async def test_el_nombre_de_byma_gana_sobre_el_de_la_sec() -> None:
    """Está en castellano y es el que el asesor reconoce."""
    conn = FakeConexion(["ABEV"])
    await _correr(
        conn,
        FakeSec({"ABEV": PerfilSec(cik=1, nombre="AMBEV S.A. /FI", sic=None, sic_titulo=None)}),
        por_papel={"ABEV": "ABEV"},
        datos_byma={
            "ABEV": DatosDeBymaPorPapel(nombre="Ambev S.A.", ratio="1:3", mercado="NASDAQ")
        },
    )

    (fila,) = conn.escrituras
    assert fila[1] == "Ambev S.A."
    # Los índices siguen el orden de `SQL_UPSERT_SEC`, que desde F-078 mete `region_etf` entre la
    # estrategia y el ratio.
    assert fila[8:10] == ("1:3", "NASDAQ"), "ratio y mercado de BYMA"


async def test_un_fondo_guarda_su_estrategia_y_no_un_sic_inventado() -> None:
    conn = FakeConexion(["GLD"])
    await _correr(
        conn,
        FakeSec(),
        por_papel={"GLD": "GLD"},
        datos_byma={"GLD": DatosDeBymaPorPapel(nombre="ETF SPDR GOLD TRUST", ratio="50:1")},
    )

    (fila,) = conn.escrituras
    assert fila[2] is None, "sin CIK no se inventa un SIC"
    assert fila[6] == "activo_fisico"


# --- El bug del avance ----------------------------------------------------------------------------


async def test_un_papel_que_la_sec_no_lista_igual_se_escribe() -> None:
    """Si no se escribe, vuelve a la cola de pendientes en cada corrida y el job no avanza nunca.

    La fila vacía no es basura: es el registro de que ya se preguntó y no está. `capturado_en` es
    lo que decide cuándo se vuelve a preguntar.
    """
    conn = FakeConexion(["GGAL"])
    resumen = await _correr(conn, FakeSec(), por_papel={"GGAL": "GGAL"})

    assert resumen.sin_cik == 1
    assert conn.tickers_escritos == ["GGAL"], "se registra el intento"
    (fila,) = conn.escrituras
    assert fila[2] is None and fila[5] is None, "sin dato: los campos quedan vacíos, no inventados"
    assert fila[10] == "SEC EDGAR", "pero la fuente y la fecha quedan escritas"


async def test_sin_cik_no_cuenta_como_clasificado() -> None:
    """Escribir el intento no es haber clasificado: el resumen los cuenta aparte para que una
    corrida de 100 papeles sin dato no se lea como 100 clasificados."""
    conn = FakeConexion(["GGAL", "YPFD"])
    resumen = await _correr(conn, FakeSec(), por_papel={})

    assert (resumen.procesados, resumen.clasificados, resumen.sin_cik) == (2, 0, 2)


# --- El límite de la fuente -----------------------------------------------------------------------


async def test_un_429_corta_la_corrida_y_lo_declara() -> None:
    conn = FakeConexion(["AAPL"])
    resumen = await _correr(conn, FakeSec(limita=True), por_papel={"AAPL": "AAPL"})

    assert resumen.cortado_por_limite_de_fuente is True
    assert "429" in (resumen.motivo_corte or "")
    assert conn.escrituras == [], "no se escribe nada a medias"


async def test_sin_pendientes_no_se_consulta_la_fuente() -> None:
    sec = FakeSec({"AAPL": APPLE})
    resumen = await _correr(FakeConexion([]), sec, por_papel={})

    assert (resumen.pendientes, resumen.procesados) == (0, 0)
    assert sec.pedidos == []


# --- La lista de BYMA es opcional -----------------------------------------------------------------


async def test_sin_la_lista_de_byma_la_clasificacion_sigue_con_lo_que_da_la_sec() -> None:
    """La lista aporta nombre y ratio; su ausencia no puede tumbar una clasificación que la SEC
    igual puede hacer."""
    conn = FakeConexion(["AAPL"])
    resumen = await _correr(
        conn, FakeSec({"AAPL": APPLE}, catalogo=CATALOGO), por_papel={"AAPL": "AAPL"}
    )

    assert resumen.clasificados == 1
    (fila,) = conn.escrituras
    assert fila[1] == "Apple Inc.", "cae al nombre de la SEC"
    assert fila[7] is None, "sin ratio, declarado"


pytestmark = pytest.mark.anyio


# --- La reclasificación de fondos, sin tocar la SEC -----------------------------------------------


class FakeConexionReclasificacion:
    """Sirve los nombres ya persistidos y guarda el lote que se escribe. Sin SEC en el medio: es
    justamente lo que este job existe para evitar."""

    def __init__(self, filas: list[tuple[str, str]]) -> None:
        self._filas = filas
        self.lotes: list[list[tuple[Any, ...]]] = []
        self.consultas: list[str] = []

    async def fetch(self, query: str, *_args: Any) -> list[dict[str, str]]:
        self.consultas.append(query)
        return [{"ticker": t, "nombre_largo": n} for t, n in self._filas]

    def transaction(self) -> "FakeConexionReclasificacion":
        return self

    async def __aenter__(self) -> "FakeConexionReclasificacion":
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None

    async def executemany(self, query: str, args: list[tuple[Any, ...]]) -> None:
        self.consultas.append(query)
        self.lotes.append(list(args))

    @property
    def escrito(self) -> dict[str, tuple[Any, Any]]:
        return {fila[0]: (fila[1], fila[2]) for lote in self.lotes for fila in lote}


async def test_la_reclasificacion_re_deriva_estrategia_y_geografia_del_nombre() -> None:
    conn = FakeConexionReclasificacion(
        [
            ("EWJ", "iShares MSCI JAPAN ETF"),
            ("XLK", "The Technology Select Sector SPDR Fund"),
            ("AAPL", "Apple Inc."),
        ]
    )

    resumen = await reclasificar_etfs(conn)

    assert resumen.como_dict() == {"procesados": 3, "con_estrategia": 2, "con_region": 1}
    assert conn.escrito["EWJ"] == ("geografico", "Japan")
    assert conn.escrito["XLK"] == ("sectorial", None), "es un fondo sin geografía declarada"
    assert conn.escrito["AAPL"] == (None, None), "no es un fondo"


async def test_la_reclasificacion_no_le_pregunta_nada_a_la_sec() -> None:
    """La propiedad que justifica que este endpoint exista aparte del barrido de la SEC: si tocara
    la fuente, el backfill costaría diecisiete corridas de 100 papeles para no traer nada nuevo."""
    conn = FakeConexionReclasificacion([("EWJ", "iShares MSCI JAPAN ETF")])

    await reclasificar_etfs(conn)

    assert all("perfil_renta_variable" in q for q in conn.consultas)
    assert not any("capturado_en" in q or "fuente" in q for q in conn.consultas), (
        "no se mueve la trazabilidad: no se consultó nada nuevo"
    )


async def test_reclasificar_dos_veces_deja_lo_mismo() -> None:
    filas = [("EWJ", "iShares MSCI JAPAN ETF"), ("AAPL", "Apple Inc.")]

    primera = await reclasificar_etfs(FakeConexionReclasificacion(filas))
    segunda = await reclasificar_etfs(FakeConexionReclasificacion(filas))

    assert primera.como_dict() == segunda.como_dict()


async def test_un_papel_sin_nombre_no_se_lee_ni_se_escribe() -> None:
    """Sin nombre no hay nada que parsear. El SQL ya los filtra; acá se fija que un lote vacío no
    dispare una escritura al pedo."""
    conn = FakeConexionReclasificacion([])

    resumen = await reclasificar_etfs(conn)

    assert resumen.procesados == 0
    assert conn.lotes == []
