"""Escribe la planilla de CAFCI en la base: wipe-and-replace transaccional.

Decisión del dueño del producto (23/08/2026): el producto no acumula series históricas. Cada
corrida borra `public.fci` entero y vuelve a insertar, en la misma transacción que reescribe el
singleton `public.fci_planilla`. Es seguro: nada tiene FK hacia `fci` (las carteras congelan su
propio snapshot en jsonb), y con MVCC de Postgres ningún lector ve la tabla vacía a mitad de camino
— o ve la foto anterior completa, o ve la nueva completa.
"""

from collections.abc import Sequence
from datetime import date, datetime
from typing import Any

from app.ingesta.cafci.parser import FilaFci

TAMANO_LOTE = 500

COLUMNAS_FCI: tuple[str, ...] = (
    "codigo_cafci",
    "fondo",
    "codigo_cnv",
    "seccion",
    "tipo_renta",
    "moneda",
    "region",
    "horizonte",
    "fecha_vcp",
    "vcp",
    "vcp_anterior",
    "var_diaria_pct",
    "var_mes_pct",
    "var_anio_pct",
    "var_12m_pct",
    "cuotapartes",
    "cuotapartes_anterior",
    "patrimonio",
    "patrimonio_anterior",
    "market_share",
    "gerente",
    "depositaria",
    "calificacion",
    "calificado",
    "tipo_dinero",
    "comision_ingreso",
    "honorarios_adm_sg",
    "honorarios_adm_sd",
    "gastos_ord_gestion",
    "comision_rescate",
    "comision_transferencia",
    "honorarios_exito",
    "moneda_fondo",
    "plazo_liq",
    "minimo_inversion",
    "fuente",
    "capturado_en",
)

_PLACEHOLDERS = ", ".join(f"${i + 1}" for i in range(len(COLUMNAS_FCI)))
SQL_INSERTAR_FCI = (
    f"INSERT INTO public.fci ({', '.join(COLUMNAS_FCI)}) VALUES ({_PLACEHOLDERS})"
)

SQL_UPSERT_PLANILLA = """
INSERT INTO public.fci_planilla
    (id, fecha_planilla, fecha_cierre_anterior, fecha_base_mes, fecha_base_anio, fecha_base_12m,
     total_filas, capturado_en)
VALUES (true, $1, $2, $3, $4, $5, $6, $7)
ON CONFLICT (id) DO UPDATE SET
    fecha_planilla = EXCLUDED.fecha_planilla,
    fecha_cierre_anterior = EXCLUDED.fecha_cierre_anterior,
    fecha_base_mes = EXCLUDED.fecha_base_mes,
    fecha_base_anio = EXCLUDED.fecha_base_anio,
    fecha_base_12m = EXCLUDED.fecha_base_12m,
    total_filas = EXCLUDED.total_filas,
    capturado_en = EXCLUDED.capturado_en
"""


def _tupla(fila: FilaFci, *, fuente: str, capturado_en: datetime) -> tuple[Any, ...]:
    return (
        fila.codigo_cafci,
        fila.fondo,
        fila.codigo_cnv,
        fila.seccion,
        fila.tipo_renta,
        fila.moneda,
        fila.region,
        fila.horizonte,
        fila.fecha_vcp,
        fila.vcp,
        fila.vcp_anterior,
        fila.var_diaria_pct,
        fila.var_mes_pct,
        fila.var_anio_pct,
        fila.var_12m_pct,
        fila.cuotapartes,
        fila.cuotapartes_anterior,
        fila.patrimonio,
        fila.patrimonio_anterior,
        fila.market_share,
        fila.gerente,
        fila.depositaria,
        fila.calificacion,
        fila.calificado,
        fila.tipo_dinero,
        fila.comision_ingreso,
        fila.honorarios_adm_sg,
        fila.honorarios_adm_sd,
        fila.gastos_ord_gestion,
        fila.comision_rescate,
        fila.comision_transferencia,
        fila.honorarios_exito,
        fila.moneda_fondo,
        fila.plazo_liq,
        fila.minimo_inversion,
        fuente,
        capturado_en,
    )


async def _escribir_lotes(conn: Any, sql: str, tuplas: Sequence[tuple[Any, ...]]) -> None:
    for inicio in range(0, len(tuplas), TAMANO_LOTE):
        await conn.executemany(sql, tuplas[inicio : inicio + TAMANO_LOTE])


async def reescribir_fci(
    conn: Any,
    filas: Sequence[FilaFci],
    *,
    fecha_planilla: date,
    fecha_cierre_anterior: date | None,
    fecha_base_mes: date | None,
    fecha_base_anio: date | None,
    fecha_base_12m: date | None,
    capturado_en: datetime,
    fuente: str = "cafci",
) -> int:
    """Borra `fci` entero y vuelve a insertar, junto con el singleton `fci_planilla`, en una sola
    transacción. Devuelve la cantidad de filas escritas."""
    tuplas = [_tupla(fila, fuente=fuente, capturado_en=capturado_en) for fila in filas]

    async with conn.transaction():
        await conn.execute("DELETE FROM public.fci")
        await _escribir_lotes(conn, SQL_INSERTAR_FCI, tuplas)
        await conn.execute(
            SQL_UPSERT_PLANILLA,
            fecha_planilla,
            fecha_cierre_anterior,
            fecha_base_mes,
            fecha_base_anio,
            fecha_base_12m,
            len(filas),
            capturado_en,
        )

    return len(filas)
