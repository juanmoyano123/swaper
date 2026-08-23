from datetime import UTC, date, datetime

from tests.conftest import FakeConexionEscritura

from app.ingesta.cafci.almacen import reescribir_fci
from app.ingesta.cafci.parser import FilaFci


def _fila(codigo: str = "1", fondo: str = "Fondo de Prueba") -> FilaFci:
    return FilaFci(
        codigo_cafci=codigo,
        fondo=fondo,
        codigo_cnv="900",
        seccion="Renta Fija Peso Argentina",
        tipo_renta="renta_fija",
        moneda="ARS",
        region="Arg",
        horizonte="Med",
        fecha_vcp=date(2026, 8, 21),
        vcp=1234.5,
        vcp_anterior=1230.0,
        var_diaria_pct=0.4,
        var_mes_pct=1.2,
        var_anio_pct=10.5,
        var_12m_pct=15.0,
        cuotapartes=1000.0,
        cuotapartes_anterior=990.0,
        patrimonio=1_000_000.0,
        patrimonio_anterior=990_000.0,
        market_share=0.5,
        gerente="Gestora S.A.",
        depositaria="Banco Depositario",
        calificacion="AA",
        calificado="Si",
        tipo_dinero="Ahorro",
        comision_ingreso=0.0,
        honorarios_adm_sg=1.5,
        honorarios_adm_sd=0.2,
        gastos_ord_gestion=0.1,
        comision_rescate=0.0,
        comision_transferencia=0.0,
        honorarios_exito=0.0,
        moneda_fondo="ARS",
        plazo_liq=1,
        minimo_inversion=1000.0,
    )


def _sql_de(conn: FakeConexionEscritura, tabla_exacta: str) -> list[tuple[str, list]]:
    """Distingue `fci` de `fci_planilla`: el helper genérico de conftest (`sql_de`/`filas_de`)
    compara por substring, y `INTO public.fci_planilla` contiene `INTO public.fci` — hace falta un
    filtro exacto acá."""
    return [
        (query, args)
        for query, args in conn.escrituras
        if f"INTO public.{tabla_exacta} (" in query or f"INTO public.{tabla_exacta}\n" in query
    ]


async def test_escribe_las_filas_y_el_singleton_de_planilla() -> None:
    conn = FakeConexionEscritura()
    capturado_en = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)

    total = await reescribir_fci(
        conn,
        [_fila("1"), _fila("2", fondo="Otro Fondo")],
        fecha_planilla=date(2026, 8, 21),
        fecha_cierre_anterior=date(2026, 8, 20),
        fecha_base_mes=date(2026, 7, 31),
        fecha_base_anio=date(2025, 12, 30),
        fecha_base_12m=date(2025, 7, 31),
        capturado_en=capturado_en,
    )

    assert total == 2
    escrituras_fci = _sql_de(conn, "fci")
    filas_fci = [fila for _, args in escrituras_fci for fila in args]
    assert len(filas_fci) == 2

    escrituras_planilla = _sql_de(conn, "fci_planilla")
    assert len(escrituras_planilla) == 1


async def test_borra_la_tabla_antes_de_insertar() -> None:
    """El wipe-and-replace: hay un DELETE sin condición antes del INSERT, en la misma
    transacción."""
    conn = FakeConexionEscritura()
    await reescribir_fci(
        conn,
        [_fila()],
        fecha_planilla=date(2026, 8, 21),
        fecha_cierre_anterior=None,
        fecha_base_mes=None,
        fecha_base_anio=None,
        fecha_base_12m=None,
        capturado_en=datetime(2026, 8, 21, tzinfo=UTC),
    )

    deletes = [q for q, _ in conn.escrituras if q.strip().startswith("DELETE FROM public.fci")]
    assert len(deletes) == 1


async def test_todo_en_una_sola_transaccion() -> None:
    conn = FakeConexionEscritura()
    await reescribir_fci(
        conn,
        [_fila()],
        fecha_planilla=date(2026, 8, 21),
        fecha_cierre_anterior=None,
        fecha_base_mes=None,
        fecha_base_anio=None,
        fecha_base_12m=None,
        capturado_en=datetime(2026, 8, 21, tzinfo=UTC),
    )

    assert conn.transacciones == ["begin", "commit"]


async def test_una_lista_vacia_borra_igual_y_no_inserta_nada() -> None:
    """Una planilla parseada con cero fondos no debería llegar acá (el parser aborta antes), pero
    si llegara, el comportamiento correcto es dejar la tabla vacía, no lanzar."""
    conn = FakeConexionEscritura()
    total = await reescribir_fci(
        conn,
        [],
        fecha_planilla=date(2026, 8, 21),
        fecha_cierre_anterior=None,
        fecha_base_mes=None,
        fecha_base_anio=None,
        fecha_base_12m=None,
        capturado_en=datetime(2026, 8, 21, tzinfo=UTC),
    )
    assert total == 0
    assert any(q.strip().startswith("DELETE FROM public.fci") for q, _ in conn.escrituras)
