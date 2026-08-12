"""La carga manual de lámina, su propagación por emisión y el punto crítico de persistencia — F-025.

Sin base de verdad: una conexión falsa que sólo sabe `fetch`/`execute`/`transaction`, para poder
verificar el SQL y los argumentos exactos que se emiten — en particular, que nunca se pisan los
otros cinco campos curados de una fila al corregir sólo la lámina.
"""

from datetime import date
from typing import Any

from app.condiciones.carga_manual import (
    ORIGEN_CARGA_MANUAL,
    _candidatos,
    cargar_lamina_manual,
)
from app.condiciones.semilla import CAMPOS
from tests.conftest import cliente

HOY = date(2026, 8, 8)
ORIGEN_CURADO = "condiciones_emision.csv (curado)"
FECHA_CURADA = date(2026, 8, 5)


def _fila(ticker: str, **campos: tuple[object, str, date]) -> dict[str, Any]:
    """Una fila cruda de `condiciones_emision`. `campos` trae el triplete completo por campo
    declarado, p. ej. `ley=("Ley N.Y.", ORIGEN_CURADO, FECHA_CURADA)`; lo no mencionado sale `None`.
    """
    fila: dict[str, Any] = {"ticker": ticker}
    for campo in CAMPOS:
        if campo in campos:
            valor, origen, fecha = campos[campo]
        else:
            valor = origen = fecha = None
        fila[campo] = valor
        fila[f"{campo}_origen"] = origen
        fila[f"{campo}_fecha"] = fecha
    return fila


class _Transaccion:
    def __init__(self, conexion: "FakeConexionLamina") -> None:
        self._conexion = conexion

    async def __aenter__(self) -> "_Transaccion":
        self._conexion.transacciones.append("begin")
        return self

    async def __aexit__(self, exc_type: Any, *_: Any) -> bool:
        self._conexion.transacciones.append("rollback" if exc_type else "commit")
        return False


class FakeConexionLamina:
    """Conexión falsa con las filas de un grupo de emisión ya cargadas.

    `fetch` ignora el SQL y devuelve las filas de `self.filas` cuyo ticker esté en la lista de
    candidatos pedida: alcanza para estos tests, que arman el grupo entero a mano. `execute` aplica
    el efecto de cada sentencia sobre `self.filas` para poder releer y comparar como pide el plan.
    """

    def __init__(self, filas: list[dict[str, Any]]) -> None:
        self.filas: dict[str, dict[str, Any]] = {fila["ticker"]: fila for fila in filas}
        self.ejecutados: list[tuple[str, tuple[Any, ...]]] = []
        self.transacciones: list[str] = []

    def transaction(self) -> _Transaccion:
        return _Transaccion(self)

    async def fetch(self, query: str, candidatos: list[str]) -> list[dict[str, Any]]:
        return [self.filas[t] for t in candidatos if t in self.filas]

    async def execute(self, query: str, *args: Any) -> None:
        self.ejecutados.append((query, args))
        if "INSERT" in query:
            (ticker,) = args
            self.filas[ticker] = _fila(ticker)
        else:
            valor, origen, fecha, ticker = args
            fila = self.filas[ticker]
            fila["lamina"], fila["lamina_origen"], fila["lamina_fecha"] = valor, origen, fecha

    def updates_de_lamina(self) -> dict[str, tuple[Any, Any, Any]]:
        return {
            args[3]: (args[0], args[1], args[2])
            for query, args in self.ejecutados
            if "UPDATE" in query
        }


# --- El módulo puro ------------------------------------------------------------------------------


def test_los_candidatos_son_exactamente_la_raiz_y_sus_tres_sufijos_de_liquidacion() -> None:
    """No un `LIKE` que capturaría AL30X/AL30Y/AL30Z — otro trío del mismo bono, ver `raiz.py`."""
    assert _candidatos("AL30") == ["AL30", "AL30O", "AL30D", "AL30C"]


async def test_emision_sin_lamina_declarada_hereda_desde_la_carga_manual() -> None:
    """GWT-1 y GWT-2: AL30 queda con origen carga manual, AL30D/AL30C heredan de AL30."""
    conexion = FakeConexionLamina([_fila("AL30"), _fila("AL30D"), _fila("AL30C")])

    resultado = await cargar_lamina_manual(conexion, "AL30", 100.0, HOY)

    assert resultado.guardado is True
    esperado = (100.0, ORIGEN_CARGA_MANUAL, HOY)
    assert (resultado.lamina, resultado.origen, resultado.fecha) == esperado

    updates = conexion.updates_de_lamina()
    assert updates["AL30"] == (100.0, ORIGEN_CARGA_MANUAL, HOY)
    assert updates["AL30D"] == (100.0, "herencia de AL30", HOY)
    assert updates["AL30C"] == (100.0, "herencia de AL30", HOY)


async def test_mismo_valor_de_otro_origen_no_es_conflicto_y_se_redeclara_manual() -> None:
    """`resolver()` compara sólo `.valor`: mismo número, distinto origen, no es conflicto."""
    conexion = FakeConexionLamina([_fila("AL30", lamina=(100.0, ORIGEN_CURADO, FECHA_CURADA))])

    resultado = await cargar_lamina_manual(conexion, "AL30", 100.0, HOY)

    assert resultado.guardado is True
    assert resultado.conflicto is None
    assert (resultado.lamina, resultado.origen) == (100.0, ORIGEN_CARGA_MANUAL)
    assert conexion.updates_de_lamina()["AL30"] == (100.0, ORIGEN_CARGA_MANUAL, HOY)


async def test_valor_distinto_de_otro_origen_en_la_emision_da_conflicto_y_vacia_las_dos() -> None:
    """GWT-4: AL30D ya declara 500 (curado); cargar 1000 en AL30 contradice ese valor.

    El sistema no elige: `resolver()` vacía los dos declarantes y el conflicto se reporta con los
    dos valores y sus orígenes (mismo mecanismo de F-009, ver `test_condiciones_persistencia.py`).
    """
    conexion = FakeConexionLamina(
        [_fila("AL30"), _fila("AL30D", lamina=(500.0, ORIGEN_CURADO, FECHA_CURADA))]
    )

    resultado = await cargar_lamina_manual(conexion, "AL30", 1000.0, HOY)

    assert resultado.guardado is False
    assert resultado.conflicto is not None
    assert resultado.conflicto.como_dict() == {
        "campo": "lamina",
        "emision": "AL30",
        "valores": {"AL30": 1000.0, "AL30D": 500.0},
    }
    updates = conexion.updates_de_lamina()
    assert updates["AL30"] == (None, None, None)
    assert updates["AL30D"] == (None, None, None)


async def test_ticker_sin_fila_se_crea_con_solo_el_triplete_de_lamina() -> None:
    conexion = FakeConexionLamina([])

    resultado = await cargar_lamina_manual(conexion, "AL30", 100.0, HOY)

    assert resultado.guardado is True
    inserts = [args for query, args in conexion.ejecutados if "INSERT" in query]
    assert inserts == [("AL30",)]

    fila = conexion.filas["AL30"]
    assert (fila["lamina"], fila["lamina_origen"], fila["lamina_fecha"]) == (
        100.0,
        ORIGEN_CARGA_MANUAL,
        HOY,
    )
    for campo in CAMPOS:
        if campo == "lamina":
            continue
        assert fila[campo] is None
        assert fila[f"{campo}_origen"] is None


async def test_no_se_pisan_los_otros_cinco_campos_curados() -> None:
    """El test que habría fallado si se hubiera reusado `persistir_semilla`/`sql_upsert()`."""
    conexion = FakeConexionLamina(
        [
            _fila(
                "AL30",
                ley=("Ley N.Y.", ORIGEN_CURADO, FECHA_CURADA),
                moneda_pago=("MEP", ORIGEN_CURADO, FECHA_CURADA),
                calificacion=("AAA", ORIGEN_CURADO, FECHA_CURADA),
                sector=("Soberano", ORIGEN_CURADO, FECHA_CURADA),
                underlying=("Gobierno Argentino", ORIGEN_CURADO, FECHA_CURADA),
            )
        ]
    )

    await cargar_lamina_manual(conexion, "AL30", 100.0, HOY)

    fila = conexion.filas["AL30"]
    assert fila["ley"] == "Ley N.Y."
    assert fila["ley_origen"] == ORIGEN_CURADO
    assert fila["moneda_pago"] == "MEP"
    assert fila["calificacion"] == "AAA"
    assert fila["sector"] == "Soberano"
    assert fila["underlying"] == "Gobierno Argentino"
    # El UPDATE que se emitió está acotado a las tres columnas de lámina: nunca menciona las otras.
    for query, _ in conexion.ejecutados:
        assert "ley" not in query
        assert "sector" not in query
        assert "calificacion" not in query
        assert "underlying" not in query


async def test_no_arrastra_tickers_de_otra_serie_de_liquidacion_con_el_mismo_prefijo() -> None:
    """AL30X no es candidato de AL30 (ver `raiz.py`): no puede entrar en conflicto con él."""
    conexion = FakeConexionLamina(
        [_fila("AL30"), _fila("AL30X", lamina=(999.0, ORIGEN_CURADO, FECHA_CURADA))]
    )

    resultado = await cargar_lamina_manual(conexion, "AL30", 100.0, HOY)

    assert resultado.guardado is True
    assert resultado.lamina == 100.0
    assert "AL30X" not in conexion.updates_de_lamina()


# --- El endpoint ---------------------------------------------------------------------------------


async def test_post_lamina_devuelve_200_con_el_triplete_guardado_y_lo_heredado(crear_app) -> None:
    conexion = FakeConexionLamina([_fila("AL30"), _fila("AL30D")])

    async with cliente(crear_app(conexion)) as http:
        respuesta = await http.post("/api/v1/condiciones/AL30/lamina", json={"valor": 100})

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["guardado"] is True
    assert cuerpo["ticker"] == "AL30"
    assert cuerpo["lamina"] == 100.0
    assert cuerpo["lamina_origen"] == ORIGEN_CARGA_MANUAL
    assert cuerpo["lamina_fecha"] == date.today().isoformat()
    assert conexion.updates_de_lamina()["AL30D"] == (100.0, "herencia de AL30", date.today())


async def test_post_lamina_devuelve_409_con_los_dos_valores_en_pugna(crear_app) -> None:
    conexion = FakeConexionLamina(
        [_fila("AL30"), _fila("AL30D", lamina=(500.0, ORIGEN_CURADO, FECHA_CURADA))]
    )

    async with cliente(crear_app(conexion)) as http:
        respuesta = await http.post("/api/v1/condiciones/AL30/lamina", json={"valor": 1000})

    assert respuesta.status_code == 409
    cuerpo = respuesta.json()
    assert cuerpo["guardado"] is False
    assert cuerpo["conflicto"] == {
        "campo": "lamina",
        "emision": "AL30",
        "valores": {"AL30": 1000.0, "AL30D": 500.0},
    }


async def test_post_lamina_con_valor_no_positivo_da_422_y_no_escribe_nada(crear_app) -> None:
    conexion = FakeConexionLamina([_fila("AL30")])

    async with cliente(crear_app(conexion)) as http:
        respuesta = await http.post("/api/v1/condiciones/AL30/lamina", json={"valor": 0})

    assert respuesta.status_code == 422
    assert conexion.ejecutados == []


async def test_post_lamina_sin_base_da_503(crear_app) -> None:
    async with cliente(crear_app(None)) as http:
        respuesta = await http.post("/api/v1/condiciones/AL30/lamina", json={"valor": 100})

    assert respuesta.status_code == 503
