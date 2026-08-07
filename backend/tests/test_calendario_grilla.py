"""La grilla de doce meses — F-015. Tres de los cuatro GWT de la spec se prueban acá.

- GWT-1: un bono que paga en marzo y en septiembre aparece en los dos meses, con la misma emisión.
- GWT-2: un mes en el que nadie paga viene presente con cero, no ausente.
- GWT-3: renta y amortización van en campos separados y el total de renta no incluye amortización.

El GWT-4 —reproducir los nominales de RUCED, SBC2D, CS47D y LOC5D— vive en
`test_calendario_paridad_motor.py`, con la aclaración de contra qué se lo verificó realmente.

Todo esto corre sin base y sin red: la grilla es una función pura sobre flujos ya calculados.
"""

from datetime import date

import pytest

from app.calendario.cupones import FlujoPorPeso, Flujos
from app.calendario.grilla import HORIZONTE_MESES, armar_calendario, ventana
from app.universo.segmentacion import EspecieUniverso

HOY = date(2026, 8, 7)


def especie(ticker: str, *, segmento: str = "usd_hard", raiz: str | None = None) -> EspecieUniverso:
    return EspecieUniverso(
        ticker=ticker,
        raiz=raiz if raiz is not None else ticker[:-1],
        clase_activo="on_corporativo",
        segmento=segmento,
        rendimiento=0.10,
        duracion=2.0,
        vencimiento=date(2030, 3, 1),
    )


def flujo(
    ticker: str, fecha: str, *, renta: float = 0.0, amortizacion: float = 0.0
) -> FlujoPorPeso:
    return FlujoPorPeso(
        ticker=ticker,
        fecha=date.fromisoformat(fecha),
        pct_renta=renta,
        pct_amortizacion=amortizacion,
        pct_total=renta + amortizacion,
    )


def grilla(flujos: list[FlujoPorPeso], especies: list[EspecieUniverso], **kwargs):
    return armar_calendario(Flujos(flujos=flujos, evaluados=len(especies)), especies, HOY, **kwargs)


# --- La ventana: doce meses, arrancando el mes que viene ------------------------------------------


def test_la_ventana_arranca_el_mes_que_viene_y_dura_doce_meses() -> None:
    """Los cupones de este mes anteriores a hoy ya se cobraron: dejar el mes en curso en la grilla
    lo marcaría como mes sin renta casi todos los días del mes."""
    assert ventana(HOY) == [
        (2026, 9),
        (2026, 10),
        (2026, 11),
        (2026, 12),
        (2027, 1),
        (2027, 2),
        (2027, 3),
        (2027, 4),
        (2027, 5),
        (2027, 6),
        (2027, 7),
        (2027, 8),
    ]


def test_un_pago_que_todavia_falta_de_este_mes_queda_fuera_de_la_ventana_y_se_cuenta() -> None:
    """Es la consecuencia declarada del criterio, y por eso no se pierde en silencio: se cuenta en
    `pendientes_este_mes` para que la diferencia no aparezca como un descuadre sin origen."""
    calendario = grilla([flujo("RUCED", "2026-08-20", renta=0.03)], [especie("RUCED")])

    assert calendario.pendientes_este_mes == 1
    assert all(m.instrumentos == [] for m in calendario.meses)


def test_un_pago_posterior_a_los_doce_meses_no_entra() -> None:
    calendario = grilla([flujo("RUCED", "2027-09-01", renta=0.03)], [especie("RUCED")])
    assert calendario.resumen()["instrumentos"] == 0


# --- GWT-1: el mismo bono en dos meses, con la misma emisión --------------------------------------


def test_un_bono_que_paga_en_marzo_y_septiembre_aparece_en_los_dos_meses() -> None:
    """GWT-1. Y con la misma clave de emisión en los dos, para que quien mire la grilla vea que es
    el mismo crédito cobrando dos veces sin volver a cortar el ticker por su cuenta."""
    calendario = grilla(
        [
            flujo("RUCED", "2026-09-01", renta=0.035),
            flujo("RUCED", "2027-03-01", renta=0.035),
        ],
        [especie("RUCED")],
    )

    meses_con_pago = {m.etiqueta: m for m in calendario.meses if m.instrumentos}
    assert set(meses_con_pago) == {"09/2026", "03/2027"}
    assert [m.instrumentos[0].emision for m in meses_con_pago.values()] == ["RUCE", "RUCE"]
    assert [m.instrumentos[0].ticker for m in meses_con_pago.values()] == ["RUCED", "RUCED"]


def test_dos_pagos_del_mismo_bono_en_el_mismo_mes_son_una_linea_con_dos_fechas() -> None:
    """La grilla contesta "quién me paga en marzo", no "cuántas transferencias entran en marzo"."""
    calendario = grilla(
        [
            flujo("RUCED", "2026-09-01", renta=0.02),
            flujo("RUCED", "2026-09-20", renta=0.01),
        ],
        [especie("RUCED")],
    )

    septiembre = calendario.meses[0]
    assert len(septiembre.instrumentos) == 1
    assert septiembre.instrumentos[0].pct_renta == pytest.approx(0.03)
    assert [f.isoformat() for f in septiembre.instrumentos[0].fechas] == [
        "2026-09-01",
        "2026-09-20",
    ]


# --- GWT-2: los meses vacíos vienen con cero explícito --------------------------------------------


def test_los_doce_meses_estan_siempre_aunque_no_pague_nadie() -> None:
    """GWT-2. Un cero vale más que una celda faltante cuando lo que se evalúa es la continuidad del
    ingreso: es justamente el mes vacío el que hay que ver."""
    calendario = grilla([flujo("RUCED", "2026-09-01", renta=0.035)], [especie("RUCED")])

    assert len(calendario.meses) == HORIZONTE_MESES
    vacio = calendario.meses[1]
    assert vacio.etiqueta == "10/2026"
    assert vacio.instrumentos == []
    assert vacio.con_renta == 0
    assert vacio.sin_renta is True


def test_un_calendario_sin_ningun_pago_igual_trae_los_doce_meses() -> None:
    calendario = grilla([], [especie("RUCED")])
    assert len(calendario.meses) == HORIZONTE_MESES
    assert calendario.meses_sin_renta == [m.etiqueta for m in calendario.meses]


def test_con_montos_el_mes_vacio_dice_cero_en_todas_las_monedas_de_la_cartera() -> None:
    """Omitir la moneda en el mes que no se cobra nada la haría desaparecer justo donde el asesor
    tiene que ver el hueco."""
    calendario = grilla(
        [flujo("RUCED", "2026-09-01", renta=0.035)],
        [especie("RUCED"), especie("S30J6", segmento="tasa_fija", raiz="S30J6")],
        montos={"RUCED": 100_000.0, "S30J6": 50_000.0},
    )

    octubre = calendario.meses[1]
    assert octubre.renta == {"ars": 0.0, "usd": 0.0}
    assert octubre.amortizacion == {"ars": 0.0, "usd": 0.0}


# --- GWT-3: renta y amortización no se suman ------------------------------------------------------


def test_renta_y_amortizacion_van_en_campos_separados_y_no_se_suman() -> None:
    """GWT-3. Cobrar amortización no es renta: es la devolución del capital prestado."""
    calendario = grilla(
        [flujo("RUCED", "2026-09-01", renta=0.02, amortizacion=0.25)],
        [especie("RUCED")],
        montos={"RUCED": 100_000.0},
    )

    septiembre = calendario.meses[0]
    instrumento = septiembre.instrumentos[0]
    assert instrumento.renta == pytest.approx(2_000.0)
    assert instrumento.amortizacion == pytest.approx(25_000.0)
    assert septiembre.renta == {"usd": pytest.approx(2_000.0)}
    assert septiembre.amortizacion == {"usd": pytest.approx(25_000.0)}
    assert calendario.renta_anual == {"usd": pytest.approx(2_000.0)}


def test_un_mes_en_el_que_solo_se_amortiza_es_un_mes_sin_renta() -> None:
    """Es el caso que la regla vuelve visible: el mes entra plata, pero no es renta, y la grilla
    tiene que marcarlo como hueco igual."""
    calendario = grilla(
        [flujo("RUCED", "2026-09-01", amortizacion=0.5)],
        [especie("RUCED")],
        montos={"RUCED": 100_000.0},
    )

    septiembre = calendario.meses[0]
    assert septiembre.con_amortizacion == 1
    assert septiembre.con_renta == 0
    assert septiembre.sin_renta is True
    assert "09/2026" in calendario.meses_sin_renta


# --- Las monedas no se suman entre sí -------------------------------------------------------------


def test_los_totales_del_mes_no_suman_pesos_con_dolares() -> None:
    """Cada `pct` es adimensional, así que al multiplicarlo por el monto el resultado queda en la
    moneda de esa posición. Un total único sería la regla 3 rota en el último paso."""
    calendario = grilla(
        [
            flujo("RUCED", "2026-09-01", renta=0.02),
            flujo("S30J6", "2026-09-01", renta=0.10),
        ],
        [especie("RUCED"), especie("S30J6", segmento="tasa_fija", raiz="S30J6")],
        montos={"RUCED": 100_000.0, "S30J6": 1_000_000.0},
    )

    assert calendario.meses[0].renta == {
        "usd": pytest.approx(2_000.0),
        "ars": pytest.approx(100_000.0),
    }


def test_cada_instrumento_declara_su_moneda_de_cobro_y_su_naturaleza_de_tasa() -> None:
    """Un dólar linked cobra **en pesos** aunque siga al dólar, y su rendimiento no es una TIR en
    dólares: por eso las dos cosas viajan juntas y ninguna se deduce del sufijo del ticker."""
    calendario = grilla(
        [flujo("TVPPD", "2026-09-01", renta=0.02)],
        [especie("TVPPD", segmento="dollar_linked")],
        montos={"TVPPD": 100_000.0},
    )

    instrumento = calendario.meses[0].instrumentos[0]
    assert instrumento.moneda == "ars"
    assert instrumento.naturaleza == "tir_dolar_linked"
    assert instrumento.como_dict()["naturaleza_nombre"] == "Rendimiento dólar linked"


# --- Sin montos no hay plata, y se dice ----------------------------------------------------------


def test_sin_montos_la_grilla_habla_en_fracciones_y_no_inventa_totales() -> None:
    """Sumar fracciones de instrumentos distintos daría "cuánto rendiría poner un peso en cada uno",
    que nadie pidió y que se leería como si fuera renta."""
    calendario = grilla(
        [
            flujo("RUCED", "2026-09-01", renta=0.02),
            flujo("S30J6", "2026-09-01", renta=0.10),
        ],
        [especie("RUCED"), especie("S30J6", segmento="tasa_fija", raiz="S30J6")],
    )

    septiembre = calendario.meses[0]
    assert septiembre.renta is None
    assert septiembre.con_renta == 2
    assert [i.pct_renta for i in septiembre.instrumentos] == [
        pytest.approx(0.02),
        pytest.approx(0.10),
    ]
    assert all(i.renta is None for i in septiembre.instrumentos)
    assert calendario.renta_anual is None
    assert calendario.resumen()["con_montos"] is False


def test_con_montos_solo_entran_los_tickers_de_la_cartera() -> None:
    """El resto del universo sigue teniendo flujos calculados, pero no es de esta cartera."""
    calendario = grilla(
        [
            flujo("RUCED", "2026-09-01", renta=0.02),
            flujo("SBC2D", "2026-09-01", renta=0.03),
        ],
        [especie("RUCED"), especie("SBC2D")],
        montos={"RUCED": 100_000.0},
    )

    assert [i.ticker for i in calendario.meses[0].instrumentos] == ["RUCED"]


def test_el_detalle_se_puede_sacar_sin_perder_los_meses() -> None:
    """Sin detalle se va la lista de instrumentos y queda el mes: el mes vacío es el dato."""
    calendario = grilla([flujo("RUCED", "2026-09-01", renta=0.02)], [especie("RUCED")])
    cuerpo = calendario.como_dict(detalle=False)

    assert len(cuerpo["meses"]) == HORIZONTE_MESES
    assert all("instrumentos" not in mes for mes in cuerpo["meses"])
    assert cuerpo["meses"][0]["con_renta"] == 1
