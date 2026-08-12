"""Escribe lo que `resolucion.py` resolvió y mide qué quedó cubierto. Acá no se decide nada.

**El upsert pisa, no completa.** Es la diferencia de fondo con `ingesta/consolidacion/persistencia`,
donde el `DO UPDATE` protege cada columna con `COALESCE` para que una corrida sin IAMC no vacíe la
ley de todo el universo. Acá pasa lo contrario: vaciar un valor **es una decisión**, no una
ausencia. Cuando la detección de conflictos vacía la lámina de una emisión, un COALESCE la
resucitaría desde la corrida anterior y el producto seguiría publicando un valor que el sistema
acaba de declarar inusable. El triplete `valor / origen / fecha` se escribe siempre entero, que es
además lo que los CHECK de trazabilidad exigen.

**Una sola transacción para toda la semilla.** Son 823 filas de una única tabla y son un artefacto
coherente: media semilla escrita —unas emisiones con el conflicto ya vaciado y otras no— sería un
estado que nadie declaró y que no se distingue a simple vista de uno correcto. Es lo contrario del
criterio de F-007, donde cada bloque tiene su transacción porque las fuentes fallan por separado.

**Una semilla vacía no escribe nada.** Sin ese guardia, un artefacto que no se pudo leer sería
indistinguible de uno que no sabe nada: la corrida no tocaría la tabla en ninguno de los dos casos,
pero cantaría éxito. Con el guardia, la alerta de `semilla.py` queda sola arriba del resultado.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import structlog

from app.condiciones.resolucion import PREFIJO_HERENCIA
from app.condiciones.semilla import CAMPOS, CAMPOS_NUMERICOS, Condiciones
from app.ingesta.alertas import Alerta
from app.ingesta.cobertura import Cobertura

# Se reusa el constructor de alerta de F-007 en vez de escribir uno igual: "no se pudo escribir X"
# es el mismo hecho operativo y tiene que leerse igual venga de donde venga.
from app.ingesta.consolidacion.persistencia import escritura_fallida

logger = structlog.get_logger()

TABLA = "condiciones_emision"

HERENCIA_ENTRE_ESPECIES = "herencia entre especies"
"""Cómo se agrupan los orígenes heredados **en el reporte de cobertura**, no en la fila.

Cada valor heredado guarda a su donante con nombre y apellido (`herencia de AEC2O`) y así queda en
la tabla y en el listado del API. Pero en el agregado eso son doscientas claves con dos filas cada
una: un reporte que hay que leer entero para enterarse de que 381 sectores se heredaron. La
cobertura contesta *cuántos y por qué lo sabemos*; *de quién exactamente* lo contesta la fila.
"""

COLUMNAS: tuple[str, ...] = (
    "ticker",
    *(parte for campo in CAMPOS for parte in (campo, f"{campo}_origen", f"{campo}_fecha")),
)


def fila_para_api(fila: Mapping[str, Any]) -> dict[str, Any]:
    """La fila de `condiciones_emision` lista para serializar como JSON.

    `lamina` es `numeric` en Postgres y asyncpg la devuelve como `Decimal`, que el encoder del API
    serializa como string: `"1"` en vez de `1`, y el schema del frontend —que la declara numérica—
    la rechaza entera con `contract_mismatch`. Se convierte acá, en el borde, para que los dos
    endpoints que sirven esta fila (`GET /condiciones` y `GET /instrumentos/{ticker}/condiciones`)
    lo hagan igual.
    """
    como_json = dict(fila)
    for campo in CAMPOS_NUMERICOS:
        valor = como_json.get(campo)
        if isinstance(valor, Decimal):
            como_json[campo] = float(valor)
    return como_json


@dataclass(frozen=True, slots=True)
class EscrituraSemilla:
    """Cuántas filas quedaron y qué falló. Nunca lanza: los fallos son datos."""

    filas: int = 0
    alertas: list[Alerta] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CoberturaCurada:
    """Cobertura de un campo sobre el universo, abierta por el origen de cada valor.

    El origen no es decoración: el criterio de aceptación pide que el conteo se corresponda con
    los valores efectivamente cargados **y su origen**, sin ninguna fila completada por inferencia.
    Con la apertura se verifica de un vistazo que la suma de los orígenes da los presentes, y que
    no hay un tercer origen posible además del artefacto curado y la herencia entre especies.
    """

    cobertura: Cobertura
    por_origen: dict[str, int] = field(default_factory=dict)

    def como_dict(self) -> dict[str, object]:
        return {**self.cobertura.como_dict(), "por_origen": self.por_origen}


def sql_upsert() -> str:
    marcadores = ", ".join(f"${i}" for i in range(1, len(COLUMNAS) + 1))
    asignaciones = ", ".join(
        f"{columna} = EXCLUDED.{columna}" for columna in COLUMNAS if columna != "ticker"
    )
    return (
        f"INSERT INTO public.{TABLA} ({', '.join(COLUMNAS)}) "
        f"VALUES ({marcadores}) "
        f"ON CONFLICT (ticker) DO UPDATE SET {asignaciones}, actualizado_en = now()"
    )


def _tupla(fila: Condiciones) -> tuple[Any, ...]:
    """Una fila resuelta se aplana al triplete por campo que la tabla espera.

    Un campo que la especie no tiene sale como tres nulos, nunca como un valor sin origen: los
    CHECK de trazabilidad rechazarían la fila entera y con razón.
    """
    valores: list[Any] = [fila.ticker]
    for campo in CAMPOS:
        declarado = fila.valores.get(campo)
        if declarado is None:
            valores.extend((None, None, None))
        else:
            valores.extend((declarado.valor, declarado.origen, declarado.fecha))
    return tuple(valores)


async def persistir_semilla(conn: Any, filas: Sequence[Condiciones]) -> EscrituraSemilla:
    """Escribe las filas resueltas en una sola transacción.

    `conn` llega por parámetro y no de `app.state` para que la siembra se pueda disparar desde un
    job, igual que la consolidación de F-007.
    """
    if not filas:
        return EscrituraSemilla()

    try:
        async with conn.transaction():
            await conn.executemany(sql_upsert(), [_tupla(fila) for fila in filas])
    except Exception as exc:
        return EscrituraSemilla(
            alertas=[escritura_fallida(TABLA, f"{type(exc).__name__}: {exc}")],
        )

    logger.info("semilla_condiciones_persistida", filas=len(filas))
    return EscrituraSemilla(filas=len(filas))


def _sql_presentes() -> str:
    """Cuántos instrumentos del universo tienen cada campo curado.

    El LEFT JOIN sale de `instrumentos` y no de `condiciones_emision` a propósito: lo que hay que
    poder responder es "de las especies que el asesor ve, ¿cuántas tienen lámina?", y un curado que
    el universo todavía no conoce no aporta a esa respuesta. Que la tabla no tenga FK es lo que
    permite que ese curado exista igual, sin perderse.
    """
    conteos = ", ".join(f"count(c.{campo})::int AS {campo}" for campo in CAMPOS)
    return (
        f"SELECT count(*)::int AS total, {conteos} "
        f"FROM public.instrumentos i "
        f"LEFT JOIN public.{TABLA} c ON c.ticker = i.ticker"
    )


def _sql_origenes() -> str:
    """El origen de cada valor presente, sobre la misma población que `_sql_presentes`.

    Que las dos consultas recorran el mismo join es lo que hace verificable el criterio: la suma
    de los orígenes de un campo tiene que dar exactamente sus presentes. Contar los orígenes sobre
    la tabla entera daría un número más grande y nadie podría cruzarlos.
    """
    bloques = [
        f"SELECT '{campo}' AS campo, c.{campo}_origen AS origen, count(*)::int AS filas "
        f"FROM public.instrumentos i "
        f"JOIN public.{TABLA} c ON c.ticker = i.ticker "
        f"WHERE c.{campo} IS NOT NULL "
        f"GROUP BY c.{campo}_origen"
        for campo in CAMPOS
    ]
    return " UNION ALL ".join(bloques)


SQL_CURADOS_FUERA_DEL_UNIVERSO = f"""
SELECT count(*)::int
  FROM public.{TABLA} c
 WHERE NOT EXISTS (SELECT 1 FROM public.instrumentos i WHERE i.ticker = c.ticker)
"""


async def medir_cobertura_curada(conn: Any) -> list[CoberturaCurada]:
    """Cobertura de los seis campos curados sobre el universo, abierta por origen."""
    presentes = await conn.fetchrow(_sql_presentes())
    filas_origen = await conn.fetch(_sql_origenes())

    por_campo: dict[str, dict[str, int]] = {campo: {} for campo in CAMPOS}
    for fila in filas_origen:
        origen = fila["origen"]
        if origen.startswith(f"{PREFIJO_HERENCIA} "):
            origen = HERENCIA_ENTRE_ESPECIES
        contados = por_campo[fila["campo"]]
        contados[origen] = contados.get(origen, 0) + fila["filas"]

    total = presentes["total"]
    return [
        CoberturaCurada(
            cobertura=Cobertura(campo=campo, presentes=presentes[campo], total=total),
            por_origen=dict(sorted(por_campo[campo].items())),
        )
        for campo in CAMPOS
    ]


async def contar_curados_fuera_del_universo(conn: Any) -> int:
    """Especies curadas que el universo todavía no vio. No son un error: son dato guardado."""
    return await conn.fetchval(SQL_CURADOS_FUERA_DEL_UNIVERSO)
