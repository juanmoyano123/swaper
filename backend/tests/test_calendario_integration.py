"""F-015 contra la base real. Marcado `integration`, fuera de la corrida por defecto.

Lo que sólo se puede verificar acá es que las dos consultas de `lectura.py` entren por la puerta:
que `public.cashflow` tenga las columnas que la matemática pide y que `public.resumen` traiga la
paridad con un tipo que `a_numero` sepa leer. Los tests offline prueban los números sobre datos
armados; éste prueba que el dato de verdad los alimente.

**Las aserciones son sobre invariantes, no sobre números del día.** Cuántos instrumentos entran al
calendario depende de la corrida de ingesta que haya pasado último y de cuánta paridad publicó IAMC
esa mañana, y un test que fijara ese número fallaría cada día por la razón equivocada. Lo que sí
tiene que valer siempre es que los doce meses estén, que renta y amortización no se mezclen y que
ningún instrumento entre al calendario sin haber encontrado su cronograma por raíz de emisión.
"""

from pathlib import Path

import asyncpg
import pytest

from app.calendario.grilla import HORIZONTE_MESES
from app.calendario.servicio import calendario_de_cartera, calendario_del_universo

RAIZ_REPO = Path(__file__).resolve().parents[2]


def _dsn() -> str:
    from dotenv import dotenv_values

    dsn = dotenv_values(RAIZ_REPO / ".env").get("DATABASE_URL")
    if not dsn:
        pytest.skip("sin DATABASE_URL en el .env de la raíz")
    return dsn


@pytest.fixture
async def conexion():
    conn = await asyncpg.connect(_dsn(), timeout=10.0)
    try:
        yield conn
    finally:
        await conn.close()


@pytest.fixture
async def calendario(conexion):
    return await calendario_del_universo(conexion)


@pytest.mark.integration
async def test_las_dos_consultas_alcanzan_para_armar_el_calendario(calendario) -> None:
    """Si `lectura` pidiera una columna que no existe, esto falla con un error de SQL; si la fuente
    cambiara de tipos, falla al no poder calcular ningún flujo."""
    assert len(calendario.meses) == HORIZONTE_MESES
    assert calendario.flujos.evaluados > 0
    assert len(calendario.flujos.tickers) > 0


@pytest.mark.integration
async def test_el_cruce_por_raiz_encuentra_cronograma_para_el_universo_real(calendario) -> None:
    """La cobertura declarada en `docs/esquema-datos.md` es del 97 % de las emisiones. Lo que se
    exige acá es mucho menos —que la mayoría encuentre cronograma— porque el número exacto depende
    de la ingesta del día; lo que no puede pasar es que el lookup deje de encontrar."""
    con_cronograma = calendario.flujos.evaluados - len(calendario.flujos.sin_cronograma)
    assert con_cronograma > calendario.flujos.evaluados / 2


@pytest.mark.integration
async def test_ningun_instrumento_entra_al_calendario_sin_su_cronograma(calendario) -> None:
    """El complemento del test anterior: que el lookup no encuentre de más. Un ticker que quedó
    nombrado como faltante no puede además tener flujos."""
    sin_cronograma = set(calendario.flujos.sin_cronograma)
    assert sin_cronograma & calendario.flujos.tickers == set()


@pytest.mark.integration
async def test_los_doce_meses_vienen_completos_y_en_orden(calendario) -> None:
    etiquetas = [m.etiqueta for m in calendario.meses]
    assert len(etiquetas) == HORIZONTE_MESES
    assert len(set(etiquetas)) == HORIZONTE_MESES
    assert calendario.meses[0].anio * 12 + calendario.meses[0].mes == (
        calendario.hoy.year * 12 + calendario.hoy.month + 1
    )


@pytest.mark.integration
async def test_la_grilla_del_universo_declara_cuanto_del_universo_cubre(calendario) -> None:
    """El invariante que la alerta existe para sostener: la grilla nunca sale sin decir qué parte
    del universo está mostrando.

    Contra la base del 7 de agosto de 2026 cubre 70 de 431 emisiones (16 %), y ninguno de los 360
    faltantes declara rendimiento o duración — así que sin esta alerta la respuesta salía con la
    lista vacía. El número exacto depende de la corrida de ingesta del día; lo que se exige acá es
    que el número esté y que cierre contra el resumen.
    """
    alerta = next(a for a in calendario.alertas if a.codigo == "cobertura_del_calendario")
    detalle = alerta.detalle
    assert detalle["emisiones"] == calendario.flujos.evaluados
    assert detalle["con_calendario"] == len(calendario.flujos.tickers)
    assert detalle["emisiones"] == (
        detalle["con_calendario"]
        + detalle["sin_paridad"]
        + detalle["sin_cronograma"]
        + detalle["vencidos"]
    )


@pytest.mark.integration
async def test_la_grilla_del_universo_no_declara_plata(calendario) -> None:
    """Sin montos no hay totales: sumar fracciones de instrumentos distintos no daría plata."""
    assert calendario.renta_anual is None
    assert all(mes.renta is None for mes in calendario.meses)


@pytest.mark.integration
async def test_una_cartera_real_devuelve_renta_y_amortizacion_separadas(conexion) -> None:
    """Se arma con instrumentos que el propio universo del día tiene con flujos, para que el test no
    dependa de que un ticker elegido a mano siga cotizando."""
    universo = await calendario_del_universo(conexion)
    tickers = sorted(universo.flujos.tickers)[:3]
    if not tickers:
        pytest.skip("el universo del día no tiene ningún instrumento con flujos")

    cartera = await calendario_de_cartera(conexion, dict.fromkeys(tickers, 100_000.0))

    assert cartera.con_montos is True
    assert cartera.monedas
    for mes in cartera.meses:
        assert mes.renta is not None
        assert mes.amortizacion is not None
        assert set(mes.renta) == set(cartera.monedas)
        for instrumento in mes.instrumentos:
            # El invariante que la spec exige: los dos números existen aparte y ninguno contiene al
            # otro. Un instrumento que sólo amortiza tiene renta cero, no renta igual a su capital.
            assert instrumento.renta is not None
            assert instrumento.amortizacion is not None


@pytest.mark.integration
async def test_las_cuatro_posiciones_del_gwt_o_se_calculan_o_se_nombran(conexion) -> None:
    """El invariante que importa: una posición nunca sale de la grilla en silencio.

    RUCED, SBC2D, CS47D y LOC5D son las cuatro del GWT-4 de la spec. Contra la base del 7 de agosto
    de 2026 **ninguna se puede calcular**, porque IAMC publicó las métricas del día en la especie O
    de cada emisión (RUCEO, SBC2O, CS47O, LOC5O) y la paridad viaja con ellas. Eso puede cambiar
    mañana con otra corrida de ingesta, así que lo que se exige no es el resultado sino la
    honestidad: o el instrumento tiene flujos, o está nombrado en una alerta con su motivo.
    """
    tickers = ["CS47D", "LOC5D", "RUCED", "SBC2D"]
    cartera = await calendario_de_cartera(conexion, dict.fromkeys(tickers, 100_000.0))

    nombrados = {
        ticker
        for alerta in cartera.alertas
        for ticker in (
            list(alerta.detalle.get("motivos", {})) + list(alerta.detalle.get("tickers", []))
        )
    }
    for ticker in tickers:
        assert ticker in cartera.flujos.tickers or ticker in nombrados


@pytest.mark.integration
async def test_una_posicion_que_no_existe_se_nombra_en_vez_de_desaparecer(conexion) -> None:
    cartera = await calendario_de_cartera(conexion, {"NOEXISTE": 100_000.0})
    codigos = {a.codigo for a in cartera.alertas}
    assert "posicion_fuera_del_universo" in codigos
