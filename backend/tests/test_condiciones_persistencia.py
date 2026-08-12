"""El contrato de las sentencias y la medición de cobertura, sin levantar PostgreSQL.

Lo que se prueba acá no es que la base funcione —eso lo verifica el test de integración— sino que
el SQL diga lo que la feature necesita: que el upsert pise en vez de completar (porque vaciar por
conflicto es una decisión y un COALESCE la revertiría), que el triplete viaje entero, y que la
cobertura por origen se mida sobre la misma población que los presentes.
"""

from datetime import date
from typing import Any

from app.condiciones.persistencia import (
    COLUMNAS,
    HERENCIA_ENTRE_ESPECIES,
    CoberturaCurada,
    contar_curados_fuera_del_universo,
    medir_cobertura_curada,
    persistir_semilla,
    sql_upsert,
)
from app.condiciones.semilla import CAMPOS, Condiciones, Valor
from app.ingesta.cobertura import Cobertura
from tests.conftest import FakeConexionEscritura

FECHA = date(2026, 8, 5)
ORIGEN = "condiciones_emision.csv (curado)"


class FakeConexionCurada(FakeConexionEscritura):
    """Escribe como su base y además contesta las dos consultas de cobertura."""

    def __init__(
        self,
        *,
        presentes: dict[str, int] | None = None,
        filas_fetch: list[dict[str, Any]] | None = None,
        fuera_del_universo: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.presentes = presentes or {}
        self.filas_fetch = filas_fetch or []
        self.fuera_del_universo = fuera_del_universo

    async def fetchrow(self, query: str, *args: Any) -> Any:
        self._registrar(query)
        return self.presentes

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        self._registrar(query)
        return self.filas_fetch

    async def fetchval(self, query: str, *args: Any) -> Any:
        self._registrar(query)
        return self.fuera_del_universo


def _especie(ticker: str, **campos: object) -> Condiciones:
    return Condiciones(
        ticker=ticker,
        valores={
            campo: Valor(valor=valor, origen=ORIGEN, fecha=FECHA) for campo, valor in campos.items()
        },
    )


# --- El SQL -------------------------------------------------------------------------------------


def test_las_columnas_son_el_triplete_de_cada_campo_mas_el_ticker() -> None:
    assert COLUMNAS[0] == "ticker"
    assert len(COLUMNAS) == 1 + 3 * len(CAMPOS)
    for campo in CAMPOS:
        assert (campo, f"{campo}_origen", f"{campo}_fecha") == tuple(
            c for c in COLUMNAS if c == campo or c.startswith(f"{campo}_")
        )


def test_el_upsert_pisa_y_no_completa_con_coalesce() -> None:
    """Un COALESCE resucitaría el valor que la detección de conflictos acaba de vaciar."""
    sql = sql_upsert()

    assert "COALESCE" not in sql
    assert "lamina = EXCLUDED.lamina" in sql
    assert "lamina_origen = EXCLUDED.lamina_origen" in sql
    assert "ON CONFLICT (ticker) DO UPDATE" in sql


async def test_una_especie_sin_un_campo_escribe_tres_nulos_y_no_un_valor_sin_origen() -> None:
    conexion = FakeConexionCurada()

    await persistir_semilla(conexion, [_especie("AL30", ley="Ley Argentina")])

    (fila,) = conexion.filas_de("condiciones_emision")
    valores = dict(zip(COLUMNAS, fila, strict=True))
    assert (valores["ley"], valores["ley_origen"], valores["ley_fecha"]) == (
        "Ley Argentina",
        ORIGEN,
        FECHA,
    )
    assert (valores["lamina"], valores["lamina_origen"], valores["lamina_fecha"]) == (
        None,
        None,
        None,
    )


async def test_toda_la_semilla_va_en_una_sola_transaccion() -> None:
    conexion = FakeConexionCurada()

    escritura = await persistir_semilla(conexion, [_especie("AL30"), _especie("AL30D")])

    assert conexion.transacciones == ["begin", "commit"]
    assert escritura.filas == 2


async def test_una_semilla_vacia_no_escribe_nada() -> None:
    """Sin esto, un artefacto ilegible sería indistinguible de uno que no sabe nada."""
    conexion = FakeConexionCurada()

    escritura = await persistir_semilla(conexion, [])

    assert not conexion.escribio_en("condiciones_emision")
    assert escritura.filas == 0


async def test_un_fallo_de_escritura_vuelve_como_alerta_y_no_como_excepcion() -> None:
    conexion = FakeConexionCurada(fallar_en="condiciones_emision")

    escritura = await persistir_semilla(conexion, [_especie("AL30")])

    assert escritura.filas == 0
    (alerta,) = escritura.alertas
    assert "condiciones_emision" in alerta.mensaje
    assert conexion.transacciones == ["begin", "rollback"]


# --- La cobertura -------------------------------------------------------------------------------


async def test_la_cobertura_se_mide_sobre_el_universo_y_se_abre_por_origen() -> None:
    conexion = FakeConexionCurada(
        presentes={"total": 10, **dict.fromkeys(CAMPOS, 0), "lamina": 6},
        filas_fetch=[
            {"campo": "lamina", "origen": ORIGEN, "filas": 4},
            {"campo": "lamina", "origen": "herencia de AL30", "filas": 1},
            {"campo": "lamina", "origen": "herencia de MR46O", "filas": 1},
        ],
    )

    medida = {c.cobertura.campo: c for c in await medir_cobertura_curada(conexion)}

    assert medida["lamina"] == CoberturaCurada(
        cobertura=Cobertura(campo="lamina", presentes=6, total=10),
        por_origen={ORIGEN: 4, HERENCIA_ENTRE_ESPECIES: 2},
    )
    assert medida["lamina"].como_dict()["porcentaje"] == 60.0


async def test_los_origenes_suman_exactamente_los_presentes() -> None:
    """La propiedad que hace auditable el criterio: nada se completó por inferencia."""
    conexion = FakeConexionCurada(
        presentes={"total": 10, **dict.fromkeys(CAMPOS, 0), "sector": 5},
        filas_fetch=[
            {"campo": "sector", "origen": ORIGEN, "filas": 3},
            {"campo": "sector", "origen": "herencia de AEC2O", "filas": 2},
        ],
    )

    medida = {c.cobertura.campo: c for c in await medir_cobertura_curada(conexion)}

    assert sum(medida["sector"].por_origen.values()) == medida["sector"].cobertura.presentes


async def test_un_campo_que_nadie_tiene_reporta_cero_y_no_desaparece() -> None:
    conexion = FakeConexionCurada(presentes={"total": 10, **dict.fromkeys(CAMPOS, 0)})

    medida = {c.cobertura.campo: c for c in await medir_cobertura_curada(conexion)}

    assert set(medida) == set(CAMPOS)
    assert medida["calificacion"].cobertura.presentes == 0
    assert medida["calificacion"].por_origen == {}


async def test_los_curados_que_el_universo_todavia_no_vio_se_cuentan_aparte() -> None:
    """No son un error: la tabla no tiene FK justamente para que no se pierdan."""
    conexion = FakeConexionCurada(fuera_del_universo=37)

    assert await contar_curados_fuera_del_universo(conexion) == 37
