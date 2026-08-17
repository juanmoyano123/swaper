"""La matemática de los cupones, sin base y sin red — F-015.

Acá se prueba lo que decide los números: el valor técnico con sus intereses corridos, el cruce del
universo contra el cronograma por raíz de emisión, y qué instrumento queda afuera y por qué. La
grilla de doce meses se prueba aparte, en `test_calendario_grilla.py`.

**El caso que más importa de este archivo es el que no calcula nada**: que un instrumento sin
cronograma quede afuera y salga nombrado, en vez de recibir el cronograma de un bono parecido.
"""

from datetime import date
from typing import Any

import pytest

from app.calendario.cupones import (
    RESIDUAL_ENTERO,
    componentes_valor_tecnico,
    flujos_por_peso,
    indexar_cronograma,
    indexar_paridades,
    valor_tecnico,
)
from app.universo.segmentacion import EspecieUniverso

HOY = date(2026, 8, 7)


def pago(
    ticker: str,
    fecha: str,
    *,
    capital: float = 0.0,
    interes: float = 0.0,
    total: float | None = None,
    residual: float | None = 100.0,
    emision: str | None = "2024-01-15",
) -> dict[str, Any]:
    """Una fila del cronograma tal como la devuelve la tabla `cashflow`."""
    return {
        "ticker": ticker,
        "payment_date": date.fromisoformat(fecha),
        "capital": capital,
        "interest_amount": interes,
        "cash_flow": capital + interes if total is None else total,
        "residual_value": residual,
        "issue_date": date.fromisoformat(emision) if emision else None,
    }


def especie(
    ticker: str,
    *,
    raiz: str | None = None,
    segmento: str = "usd_hard",
    rendimiento: float | None = 0.10,
    duracion: float | None = 2.0,
) -> EspecieUniverso:
    return EspecieUniverso(
        ticker=ticker,
        raiz=raiz if raiz is not None else ticker[:-1],
        clase_activo="on_corporativo",
        segmento=segmento,
        rendimiento=rendimiento,
        duracion=duracion,
    )


# --- Valor técnico: residual vivo más corridos ----------------------------------------------------


def test_un_bono_sin_pagos_futuros_no_proyecta_nada() -> None:
    """Un bono vencido no tiene valor técnico: no hay nada que descontar ni que cobrar."""
    cronograma = indexar_cronograma([pago("RUCEO", "2025-03-01", interes=5.0)])
    assert valor_tecnico(cronograma.pagos_de("RUCE"), HOY) is None


def test_un_bono_que_no_pago_ningun_cupon_arranca_con_los_cien_nominales_vivos() -> None:
    """Sin pagos pasados el residual es 100: el bono todavía no amortizó nada."""
    cronograma = indexar_cronograma(
        [pago("NUEVO", "2026-08-08", interes=0.0, emision="2026-08-07")]
    )
    assert valor_tecnico(cronograma.pagos_de("NUEV"), HOY) == RESIDUAL_ENTERO


def test_el_residual_sale_del_ultimo_pago_ya_ocurrido() -> None:
    """Un amortizing que ya devolvió la mitad vale la mitad, no 100.

    Es la razón por la que el cronograma se lee entero y no sólo del futuro: con los pagos pasados
    afuera, este bono se valuaría al doble y su cupón parecería la mitad de lo que es.
    """
    cronograma = indexar_cronograma(
        [
            pago("AMORO", "2026-02-01", capital=50.0, residual=50.0, emision=None),
            pago("AMORO", "2026-08-01", capital=0.0, residual=50.0, emision=None),
            pago("AMORO", "2027-02-01", capital=50.0, interes=0.0, residual=0.0, emision=None),
        ]
    )
    assert valor_tecnico(cronograma.pagos_de("AMOR"), HOY) == 50.0


def test_los_corridos_se_devengan_linealmente_entre_el_ultimo_pago_y_el_proximo() -> None:
    """A mitad de camino entre dos cupones, la mitad del próximo cupón ya está devengada."""
    cronograma = indexar_cronograma(
        [
            pago("LINEO", "2026-06-08", interes=4.0, residual=100.0, emision=None),
            pago("LINEO", "2026-10-07", interes=4.0, residual=100.0, emision=None),
        ]
    )
    vt = valor_tecnico(cronograma.pagos_de("LINE"), HOY)
    assert vt is not None
    # 60 de 121 días transcurridos sobre un cupón de 4.
    assert vt == pytest.approx(100.0 + 4.0 * 60 / 121)


def test_sin_pagos_pasados_ni_fecha_de_emision_se_asumen_cero_corridos() -> None:
    """El default subestima el precio sucio y nunca lo infla: es el lado prudente para caer."""
    cronograma = indexar_cronograma(
        [pago("SINFO", "2026-12-01", interes=4.0, emision=None, residual=100.0)]
    )
    assert valor_tecnico(cronograma.pagos_de("SINF"), HOY) == 100.0


def test_un_bono_con_el_residual_en_cero_no_proyecta_nada() -> None:
    """Residual cero es capital ya devuelto: no queda nominal vivo sobre el que calcular."""
    cronograma = indexar_cronograma(
        [
            pago("CEROO", "2026-06-01", capital=100.0, residual=0.0, emision=None),
            pago("CEROO", "2026-12-01", interes=1.0, residual=0.0, emision=None),
        ]
    )
    assert valor_tecnico(cronograma.pagos_de("CERO"), HOY) is None


# --- componentes_valor_tecnico: desglose y chequeo de coherencia (16/08/2026) ------------------


def test_los_componentes_abren_residual_vigente_y_cupon_corrido_por_separado() -> None:
    cronograma = indexar_cronograma(
        [
            pago("LINEO", "2026-06-08", interes=4.0, residual=100.0, emision=None),
            pago("LINEO", "2026-10-07", interes=4.0, residual=100.0, emision=None),
        ]
    )
    c = componentes_valor_tecnico(cronograma.pagos_de("LINE"), HOY)
    assert c.coherente is True
    assert c.residual_vigente == 100.0
    assert c.cupon_corrido == pytest.approx(4.0 * 60 / 121)
    assert c.valor_tecnico == pytest.approx(100.0 + 4.0 * 60 / 121)


def test_un_residual_clavado_en_100_mientras_el_bono_amortiza_es_incoherente() -> None:
    """El caso real: BDC33 amortiza 33,33 en un pago pasado y la fuente sigue declarando 100.

    100 - 33,33 de capital ya pagado != 100 declarado: la fuente se contradice en la misma tabla.
    Regla 1 — se deja vacío en vez de publicar un valor técnico sobreestimado.
    """
    cronograma = indexar_cronograma(
        [
            pago("BDC33", "2026-01-01", capital=33.33, residual=100.0, emision=None),
            pago("BDC33", "2027-01-01", interes=5.0, residual=100.0, emision=None),
        ]
    )
    c = componentes_valor_tecnico(cronograma.pagos_de("BDC33"), HOY)
    assert c.coherente is False
    assert c.residual_vigente is None
    assert c.cupon_corrido is None
    assert c.valor_tecnico is None
    assert valor_tecnico(cronograma.pagos_de("BDC33"), HOY) is None


def test_un_bullet_que_no_cierra_en_cero_al_vencimiento_no_dispara_el_chequeo() -> None:
    """El otro caso medido (80 tickers): la última fila no pone el residual en 0. Es inocuo porque
    esa fila no tiene pagos futuros — `componentes_valor_tecnico` corta antes de llegar al chequeo
    de coherencia, con el mismo criterio que "bono vencido no proyecta nada"."""
    cronograma = indexar_cronograma(
        [pago("BULLETO", "2025-01-01", capital=100.0, residual=5.0, emision=None)]
    )
    c = componentes_valor_tecnico(cronograma.pagos_de("BULLET"), HOY)
    assert c.coherente is True
    assert c.valor_tecnico is None  # vencido, no incoherente


def test_una_pequena_diferencia_de_redondeo_no_cuenta_como_incoherencia() -> None:
    """Tolerancia 0,01: la fuente redondea, y eso no es lo mismo que contradecirse."""
    cronograma = indexar_cronograma(
        [
            pago("REDO", "2026-01-01", capital=25.0, residual=75.005, emision=None),
            pago("REDO", "2027-01-01", interes=5.0, residual=75.0, emision=None),
        ]
    )
    c = componentes_valor_tecnico(cronograma.pagos_de("RED"), HOY)
    assert c.coherente is True
    assert c.residual_vigente == 75.005


# --- El cronograma se indexa por raíz, y lo incompleto se cuenta ----------------------------------


def test_el_cronograma_se_agrupa_por_raiz_de_emision_y_queda_ordenado_por_fecha() -> None:
    cronograma = indexar_cronograma(
        [
            pago("RUCEO", "2027-03-01", interes=3.0),
            pago("RUCEO", "2026-09-01", interes=3.0),
        ]
    )
    assert list(cronograma.por_raiz) == ["RUCE"]
    assert [p.fecha.isoformat() for p in cronograma.pagos_de("RUCE")] == [
        "2026-09-01",
        "2027-03-01",
    ]


def test_un_pago_sin_fecha_se_descarta_y_se_cuenta() -> None:
    """Un pago sin fecha no se puede ubicar en ningún mes, y ponerlo en uno cualquiera sería
    inventar el dato que falta."""
    fila = pago("RUCEO", "2027-03-01")
    fila["payment_date"] = None
    cronograma = indexar_cronograma([fila])
    assert cronograma.por_raiz == {}
    assert cronograma.sin_fecha == ["RUCEO"]


def test_un_pago_sin_monto_se_descarta_y_se_cuenta_en_vez_de_completarse_con_cero() -> None:
    """Un cero diría que ese día no se cobra nada, que es distinto de no saber cuánto se cobra."""
    fila = pago("RUCEO", "2027-03-01", interes=3.0)
    fila["interest_amount"] = None
    cronograma = indexar_cronograma([fila])
    assert cronograma.por_raiz == {}
    assert cronograma.sin_monto == ["RUCEO 2027-03-01"]


def test_la_paridad_que_no_es_numero_queda_en_none_y_no_en_cero() -> None:
    """Cero sería "cotiza a paridad cero", que es un dato. `None` es "no se sabe"."""
    paridades = indexar_paridades(
        [{"ticker": "RUCED", "paridad": 1.0055}, {"ticker": "SBC2D", "paridad": None}]
    )
    assert paridades == {"RUCED": 1.0055, "SBC2D": None}


# --- El cruce: un lookup por raíz que nunca genera un ticker --------------------------------------


def test_la_especie_encuentra_el_cronograma_de_su_emision_por_raiz() -> None:
    """El cashflow indexa RUCEO y el universo trae RUCED: es el caso que la raíz existe para
    resolver."""
    cronograma = indexar_cronograma([pago("RUCEO", "2027-03-01", interes=3.0)])
    flujos = flujos_por_peso([especie("RUCED")], cronograma, {"RUCED": 1.0}, HOY)

    assert [f.ticker for f in flujos.flujos] == ["RUCED"]
    assert flujos.sin_cronograma == []


def test_un_instrumento_sin_cronograma_queda_afuera_y_sale_nombrado() -> None:
    """No se le asigna el cronograma de un bono parecido: se lo nombra y se lo deja afuera.

    Es la regla 1 del proyecto en el punto exacto donde una vez se rompió — derivar tickers cortando
    strings produjo 121 tickers inexistentes que hubo que revertir.
    """
    cronograma = indexar_cronograma([pago("RUCEO", "2027-03-01", interes=3.0)])
    flujos = flujos_por_peso([especie("HUERF", raiz="HUERF")], cronograma, {"HUERF": 1.0}, HOY)

    assert flujos.flujos == []
    assert flujos.sin_cronograma == ["HUERF"]
    alerta = next(a for a in flujos.alertas if a.codigo == "instrumento_sin_cronograma")
    assert "HUERF" in alerta.mensaje
    assert alerta.detalle["tickers"] == ["HUERF"]


def test_un_instrumento_que_cotiza_sin_paridad_queda_afuera_y_sale_nombrado() -> None:
    """Sin paridad no hay precio sucio, y lo único que lo reemplazaría es un tipo de cambio traído
    de afuera — que es lo que la regla 3 prohíbe."""
    cronograma = indexar_cronograma([pago("RUCEO", "2027-03-01", interes=3.0)])
    flujos = flujos_por_peso([especie("RUCED")], cronograma, {"RUCED": None}, HOY)

    assert flujos.flujos == []
    assert flujos.sin_paridad == ["RUCED"]
    assert any(a.codigo == "instrumento_sin_paridad" for a in flujos.alertas)


def test_un_instrumento_que_no_cotiza_no_se_alerta_pero_tampoco_se_pierde() -> None:
    """Sin rendimiento ni duración no se lo alerta en la vista del universo —listarlos a todos haría
    un padrón que taparía los casos que importan, que es el criterio del motor— pero sí queda en el
    listado completo, porque en una cartera esa misma posición hay que nombrarla."""
    cronograma = indexar_cronograma([pago("RUCEO", "2027-03-01", interes=3.0)])
    flujos = flujos_por_peso(
        [especie("RUCED", rendimiento=None, duracion=None)], cronograma, {"RUCED": None}, HOY
    )

    assert flujos.sin_paridad == ["RUCED"]
    assert flujos.sin_paridad_que_cotizan == []
    assert flujos.alertas == []
    assert flujos.motivo_de("RUCED") == "sin paridad: no se puede pasar el cupón a plata"


def test_un_bono_vencido_se_cuenta_pero_no_se_alerta() -> None:
    """Que un bono haya terminado no es un faltante de dato: es un bono que terminó."""
    cronograma = indexar_cronograma([pago("VIEJO", "2025-03-01", interes=3.0)])
    flujos = flujos_por_peso([especie("VIEJO", raiz="VIEJ")], cronograma, {"VIEJO": 1.0}, HOY)

    assert flujos.vencidos == ["VIEJO"]
    assert flujos.alertas == []


# --- Los flujos son fracciones del monto invertido ------------------------------------------------


def test_el_pago_se_expresa_como_fraccion_del_precio_sucio() -> None:
    """`pct = pago / (paridad x valor técnico)`, que es adimensional y por eso no necesita ningún
    tipo de cambio."""
    cronograma = indexar_cronograma(
        [
            pago("BONOO", "2026-06-08", interes=4.0, residual=100.0, emision=None),
            pago("BONOO", "2026-10-07", capital=20.0, interes=4.0, residual=80.0, emision=None),
        ]
    )
    flujos = flujos_por_peso([especie("BONOD", raiz="BONO")], cronograma, {"BONOD": 0.98}, HOY)

    precio_sucio = 0.98 * (100.0 + 4.0 * 60 / 121)
    assert len(flujos.flujos) == 1
    unico = flujos.flujos[0]
    assert unico.pct_renta == pytest.approx(4.0 / precio_sucio)
    assert unico.pct_amortizacion == pytest.approx(20.0 / precio_sucio)
    assert unico.pct_total == pytest.approx(24.0 / precio_sucio)


def test_dos_especies_de_la_misma_emision_comparten_cronograma_y_no_paridad() -> None:
    """La paridad es de la especie: MR46O y MR46D cotizan a precios distintos en monedas distintas,
    y calcular una con la paridad de la otra daría un número que no es el de la posición que se
    tiene."""
    cronograma = indexar_cronograma(
        [pago("MR46O", "2027-03-01", interes=5.0, residual=100.0, emision=None)]
    )
    flujos = flujos_por_peso(
        [especie("MR46O", raiz="MR46"), especie("MR46D", raiz="MR46")],
        cronograma,
        {"MR46O": 1.0, "MR46D": 0.5},
        HOY,
    )

    por_ticker = {f.ticker: f.pct_renta for f in flujos.flujos}
    assert por_ticker["MR46D"] == pytest.approx(2 * por_ticker["MR46O"])


def test_los_pagos_ya_ocurridos_no_entran_a_los_flujos() -> None:
    cronograma = indexar_cronograma(
        [
            pago("BONOO", "2026-06-08", interes=4.0, residual=100.0, emision=None),
            pago("BONOO", "2027-06-08", interes=4.0, residual=100.0, emision=None),
        ]
    )
    flujos = flujos_por_peso([especie("BONOD", raiz="BONO")], cronograma, {"BONOD": 1.0}, HOY)

    assert [f.fecha.isoformat() for f in flujos.flujos] == ["2027-06-08"]
