"""Carga asistida de la lámina de una especie, con trazabilidad y propagación — F-025.

La lámina es un atributo de la emisión, no de la especie (AL30/AL30D/AL30C son el mismo bono), así
que una carga manual se propaga a las demás especies con el mismo mecanismo de herencia/conflicto
que ya resuelve F-009 (`app/condiciones/resolucion.py::resolver`). Lo único nuevo acá es la
persistencia: **nunca se llama a `persistir_semilla`/`sql_upsert()`**, que reescriben la fila entera
y pisarían con NULL los otros cinco campos curados de cada ticker (`app/condiciones/persistencia.py`
explica por qué). Acá se corrige un solo campo de un ticker, así que se escribe sólo el triplete de
lámina, con un UPDATE acotado a esas tres columnas.

Si el ticker todavía no tiene fila en `condiciones_emision`, se crea una fila bare (sólo `ticker`,
el resto NULL) antes de resolver: así el resto del flujo — resolver y persistir — no necesita
distinguir INSERT de UPDATE, siempre hay una fila para actualizar.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.condiciones.persistencia import COLUMNAS, TABLA
from app.condiciones.resolucion import PREFIJO_HERENCIA, Conflicto, resolver
from app.condiciones.semilla import CAMPOS, Condiciones, Valor
from app.ingesta.raiz import raiz_emision

ORIGEN_CARGA_MANUAL = "carga manual"

SUFIJOS_ESPECIE = ("O", "D", "C")

SQL_GRUPO = f"SELECT {', '.join(COLUMNAS)} FROM public.{TABLA} WHERE ticker = ANY($1)"

SQL_CREAR_FILA_BARE = f"INSERT INTO public.{TABLA} (ticker) VALUES ($1)"

SQL_UPDATE_LAMINA = (
    f"UPDATE public.{TABLA} "
    f"SET lamina = $1, lamina_origen = $2, lamina_fecha = $3, actualizado_en = now() "
    f"WHERE ticker = $4"
)


def _candidatos(raiz: str) -> list[str]:
    return [raiz, *(f"{raiz}{sufijo}" for sufijo in SUFIJOS_ESPECIE)]


def _declarado(fila: Any) -> Condiciones:
    """Sólo lo que esta fila declara, nunca lo heredado.

    Un origen `NULL` o que empieza con `PREFIJO_HERENCIA` es lo que esta fila heredó la vez
    pasada, no lo que declara ahora: si entrara como declarado, dos especies que heredaron el
    mismo valor de un tercero generarían un falso conflicto entre ellas.
    """
    valores: dict[str, Valor] = {}
    for campo in CAMPOS:
        origen = fila[f"{campo}_origen"]
        if origen is None or origen.startswith(f"{PREFIJO_HERENCIA} "):
            continue
        valores[campo] = Valor(valor=fila[campo], origen=origen, fecha=fila[f"{campo}_fecha"])
    return Condiciones(ticker=fila["ticker"], valores=valores)


@dataclass(frozen=True, slots=True)
class ResultadoCargaManual:
    """El desenlace de una carga: guardada con su triplete, o en conflicto sin elegir ninguno."""

    ticker: str
    guardado: bool
    lamina: float | None = None
    origen: str | None = None
    fecha: date | None = None
    conflicto: Conflicto | None = None


async def cargar_lamina_manual(
    conn: Any, ticker: str, valor: float, hoy: date
) -> ResultadoCargaManual:
    """Carga la lámina de `ticker`, la propaga por emisión y la persiste — o reporta el conflicto.

    Todo dentro de una sola transacción: si algo falla a mitad de camino no queda una emisión con
    unas especies actualizadas y otras no.
    """
    raiz = raiz_emision(ticker)
    candidatos = _candidatos(raiz)

    async with conn.transaction():
        filas = await conn.fetch(SQL_GRUPO, candidatos)
        declaradas = {fila["ticker"]: _declarado(fila) for fila in filas}

        if ticker not in declaradas:
            await conn.execute(SQL_CREAR_FILA_BARE, ticker)
            declaradas[ticker] = Condiciones(ticker=ticker)

        propia = declaradas[ticker]
        nueva_lamina = Valor(valor=valor, origen=ORIGEN_CARGA_MANUAL, fecha=hoy)
        declaradas[ticker] = Condiciones(
            ticker=ticker, valores={**propia.valores, "lamina": nueva_lamina}
        )

        resolucion = resolver(list(declaradas.values()))
        conflicto_lamina = next((c for c in resolucion.conflictos if c.campo == "lamina"), None)

        if conflicto_lamina is not None:
            for declarante in conflicto_lamina.valores:
                await conn.execute(SQL_UPDATE_LAMINA, None, None, None, declarante)
            return ResultadoCargaManual(ticker=ticker, guardado=False, conflicto=conflicto_lamina)

        for fila_resuelta in resolucion.filas:
            lamina_resuelta = fila_resuelta.valores.get("lamina")
            if lamina_resuelta is None:
                continue
            await conn.execute(
                SQL_UPDATE_LAMINA,
                lamina_resuelta.valor,
                lamina_resuelta.origen,
                lamina_resuelta.fecha,
                fila_resuelta.ticker,
            )

        propia_resuelta = next(f for f in resolucion.filas if f.ticker == ticker).valores["lamina"]
        return ResultadoCargaManual(
            ticker=ticker,
            guardado=True,
            lamina=propia_resuelta.valor,
            origen=propia_resuelta.origen,
            fecha=propia_resuelta.fecha,
        )
