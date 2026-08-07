"""Las dos capas de sanidad — F-010, sus cuatro criterios de aceptación y los bordes que los rodean.

Los tres últimos criterios de la spec son variaciones del mismo punto y por eso son tres: **el tope
se elige por segmento, y el segmento determina en qué unidad está el número que se compara.** Un
test que sólo verificara "descarta lo que supera 300" pasaría el de SNSBO y fallaría el espíritu de
los otros dos, así que cada uno de esos tests afirma además contra qué umbral se comparó y qué
habría pasado bajo el tope ajeno.

Los rendimientos van en fracción, que es como los guarda el contrato del `Resumen`: 0,0675 es
6,75 % y 346279,17 es 34.627.917 %.
"""

import pytest

from app.ingesta.alertas import (
    CODIGO_ESPECIE_INCOHERENTE,
    CODIGO_RENDIMIENTO_FUERA_DE_RANGO,
)
from app.ingesta.consolidacion import raiz_emision
from app.universo.sanidad import (
    DISCORDANCIA_ESPECIES,
    TOPE_SANIDAD_SEGMENTO,
    MotivoDescarte,
    evaluar_sanidad,
)
from app.universo.segmentacion import EspecieUniverso


def especie(ticker: str, segmento: str, rendimiento: float | None) -> EspecieUniverso:
    return EspecieUniverso(
        ticker=ticker,
        raiz=raiz_emision(ticker),
        clase_activo="on_corporativo",
        segmento=segmento,
        rendimiento=rendimiento,
    )


# --- GWT 1 · Coherencia entre especies del mismo bono -------------------------------------------


def test_la_especie_con_el_precio_mal_escalado_se_descarta_y_su_hermana_se_conserva() -> None:
    """GIVEN VSCQD con TIR de 34.627.917 % y VSCQO del mismo bono con 6,75 %
    WHEN corre la coherencia entre especies
    THEN VSCQD se descarta por despegue mayor a 100 pp, VSCQO se conserva, y el descarte queda
         listado con su motivo."""
    resultado = evaluar_sanidad(
        [
            especie("VSCQD", "usd_hard", 346279.17),
            especie("VSCQO", "usd_hard", 0.0675),
        ]
    )

    assert resultado.descartados == {"VSCQD"}
    assert resultado.es_sano("VSCQO")

    (descarte,) = resultado.descartes
    assert descarte.ticker == "VSCQD"
    assert descarte.motivo is MotivoDescarte.ESPECIE_INCOHERENTE
    assert descarte.rendimiento == pytest.approx(346279.17)
    assert descarte.umbral == DISCORDANCIA_ESPECIES
    # El descarte nombra a la hermana que sí tiene el precio bien: es lo que permite auditarlo.
    assert descarte.ticker_referencia == "VSCQO"
    assert descarte.rendimiento_referencia == pytest.approx(0.0675)


def test_una_discordancia_de_51_pp_entre_especies_es_dato_valido() -> None:
    """El umbral es 100 pp y no menos porque DICPD rinde 51 pp más que DICP y las dos son ciertas.
    Bajarlo mataría datos buenos con la excusa de limpiar."""
    resultado = evaluar_sanidad([especie("DICP", "cer", 0.12), especie("DICPD", "cer", 0.63)])
    assert resultado.descartes == []


def test_dos_especies_del_mismo_bono_que_declaran_casi_la_misma_tir_se_conservan() -> None:
    """MR46D 13,08 % vs MR46O 13,10 %: así se ve un bono con el dato bien."""
    resultado = evaluar_sanidad(
        [
            especie("MR46O", "usd_hard", 0.1310),
            especie("MR46D", "usd_hard", 0.1308),
            especie("MR46C", "usd_hard", 0.1309),
        ]
    )
    assert resultado.descartes == []


def test_una_emision_con_una_sola_especie_no_pasa_por_la_capa_de_coherencia() -> None:
    """Sin hermana contra la cual compararla no hay nada que decir: de eso se ocupa la capa 2."""
    resultado = evaluar_sanidad([especie("UNICA", "usd_hard", 0.50)])
    assert resultado.por_motivo(MotivoDescarte.ESPECIE_INCOHERENTE) == []


def test_solo_se_descarta_la_especie_que_se_despega_hacia_arriba() -> None:
    """El error que esta capa ataca —un precio mal escalado— infla la TIR. Una especie que rinde de
    menos está diciendo que cotiza más cara, que es un dato posible y no un error de escala."""
    resultado = evaluar_sanidad(
        [especie("AAAAO", "usd_hard", 0.05), especie("AAAAD", "usd_hard", 2.50)]
    )
    assert resultado.descartados == {"AAAAD"}


def test_el_piso_de_la_emision_es_el_minimo_y_no_el_promedio() -> None:
    """Con promedio, un valor de 34 millones por ciento arrastraría la referencia y dejaría de
    detectarse a sí mismo: las dos especies quedarían "cerca" del promedio que él mismo movió."""
    resultado = evaluar_sanidad(
        [
            especie("BBBBO", "usd_hard", 0.07),
            especie("BBBBD", "usd_hard", 346279.17),
        ]
    )
    assert resultado.descartados == {"BBBBD"}


# --- GWT 2 · El distress real no es un error de datos -------------------------------------------


def test_snsbo_al_245_por_ciento_en_dolares_no_se_descarta() -> None:
    """GIVEN SNSBO con 245 % de TIR en dólares, bono a 80 días al 78 % de su valor técnico
    WHEN corre el techo por segmento
    THEN SNSBO NO se descarta, porque el tope de hard-dollar es 300 %."""
    resultado = evaluar_sanidad([especie("SNSBO", "usd_hard", 2.455)])

    assert resultado.descartes == []
    assert resultado.es_sano("SNSBO")
    # El tope es holgado a propósito: tiene que dejar pasar el distress real.
    assert TOPE_SANIDAD_SEGMENTO["usd_hard"] == 3.0


# --- GWT 3 · El tope se elige por segmento, en la unidad del segmento ----------------------------


def test_un_cer_al_150_por_ciento_de_tasa_real_se_descarta_contra_su_propio_tope() -> None:
    """GIVEN un instrumento CER con tasa real de 150 %
    WHEN corre el techo por segmento
    THEN se descarta contra el tope de 100 % de tasa real, y no contra el de 300 % de
         hard-dollar."""
    resultado = evaluar_sanidad([especie("TXCER", "cer", 1.50)])

    (descarte,) = resultado.descartes
    assert descarte.motivo is MotivoDescarte.FUERA_DE_RANGO
    assert descarte.rendimiento == pytest.approx(1.50)
    # Lo que hace al test: se comparó contra 100 % de tasa REAL, no contra los 300 % del otro tope.
    assert descarte.umbral == TOPE_SANIDAD_SEGMENTO["cer"] == 1.0
    assert descarte.naturaleza == "tasa_real_cer"
    # Y el mismo número, bajo el tope de hard-dollar, no se habría descartado nunca.
    assert TOPE_SANIDAD_SEGMENTO["usd_hard"] > 1.50


# --- GWT 4 · Un número enorme en pesos puede ser perfectamente cierto ----------------------------


def test_una_tasa_fija_con_tna_nominal_del_480_por_ciento_se_conserva() -> None:
    """GIVEN un instrumento de tasa fija con TNA nominal de 480 %
    WHEN corre el techo por segmento
    THEN se conserva, porque el tope de TNA nominal es 500 %."""
    resultado = evaluar_sanidad([especie("S30J6", "tasa_fija", 4.80)])

    assert resultado.descartes == []
    assert TOPE_SANIDAD_SEGMENTO["tasa_fija"] == 5.0
    # El mismo 480 % medido contra el tope de hard-dollar habría muerto: por eso el tope es por
    # segmento y no uno solo. Un tope único descartaría de más en pesos y de menos en dólares.
    assert TOPE_SANIDAD_SEGMENTO["usd_hard"] < 4.80


def test_los_topes_en_pesos_son_iguales_entre_si_y_distintos_de_los_de_dolares() -> None:
    """Badlar, Tamar y tasa fija comparten unidad —TNA nominal en pesos— y por eso, tope."""
    assert (
        TOPE_SANIDAD_SEGMENTO["tasa_fija"]
        == TOPE_SANIDAD_SEGMENTO["badlar"]
        == TOPE_SANIDAD_SEGMENTO["tamar"]
        == 5.0
    )
    assert TOPE_SANIDAD_SEGMENTO["usd_hard"] == TOPE_SANIDAD_SEGMENTO["dollar_linked"] == 3.0


@pytest.mark.parametrize("segmento", sorted(TOPE_SANIDAD_SEGMENTO))
def test_el_valor_exacto_del_tope_todavia_es_dato_sano(segmento: str) -> None:
    """El corte es estrictamente mayor: un instrumento que rinde justo el tope se conserva."""
    tope = TOPE_SANIDAD_SEGMENTO[segmento]
    assert evaluar_sanidad([especie("JUSTO", segmento, tope)]).descartes == []
    assert evaluar_sanidad([especie("PASADO", segmento, tope * 1.01)]).descartes != []


# --- Qué NO hace la sanidad ---------------------------------------------------------------------


def test_una_especie_sin_rendimiento_no_se_descarta() -> None:
    """Un valor ausente no es un valor imposible. Tratarlo como descarte confundiría "no lo sé" con
    "es mentira"; que no se pueda proponer lo resuelve el filtro de operables, no la sanidad."""
    resultado = evaluar_sanidad(
        [especie("SINTIR", "usd_hard", None), especie("SINTIRD", "usd_hard", None)]
    )
    assert resultado.descartes == []
    assert resultado.es_sano("SINTIR")


def test_un_nan_que_se_colara_hasta_aca_tampoco_se_descarta() -> None:
    """Segundo cinturón del mismo error. `segmentacion.numero` traduce el `NaN` a `None`, pero la
    comparación de la capa 2 está escrita en positivo —"descartar lo que supera el techo"— para que
    un valor incomparable caiga del lado de conservar y no del lado de condenar."""
    resultado = evaluar_sanidad([especie("CONNAN", "usd_hard", float("nan"))])
    assert resultado.descartes == []


def test_el_descarte_no_corrige_ni_estima_nada() -> None:
    """El instrumento sigue en el universo con su valor original: se marca, no se toca."""
    rota = especie("VSCQD", "usd_hard", 346279.17)
    resultado = evaluar_sanidad([rota, especie("VSCQO", "usd_hard", 0.0675)])
    assert rota.rendimiento == pytest.approx(346279.17)
    assert resultado.descartes[0].rendimiento == pytest.approx(346279.17)


def test_un_instrumento_que_viola_las_dos_capas_se_lista_una_sola_vez() -> None:
    """Su valor absurdo viola además cualquier techo; contarlo dos veces haría creer que hay dos
    problemas. Gana la capa 1, que explica mejor qué pasó: nombra la especie hermana sana."""
    resultado = evaluar_sanidad(
        [
            especie("VSCQD", "usd_hard", 346279.17),
            especie("VSCQO", "usd_hard", 0.0675),
        ]
    )
    assert len(resultado.descartes) == 1
    assert resultado.por_motivo(MotivoDescarte.FUERA_DE_RANGO) == []


# --- Lo que se reporta --------------------------------------------------------------------------


def test_cada_capa_emite_su_propia_alerta_con_su_codigo() -> None:
    resultado = evaluar_sanidad(
        [
            especie("VSCQD", "usd_hard", 346279.17),
            especie("VSCQO", "usd_hard", 0.0675),
            especie("TXCER", "cer", 1.50),
        ]
    )
    codigos = {a.codigo for a in resultado.alertas}
    assert codigos == {CODIGO_ESPECIE_INCOHERENTE, CODIGO_RENDIMIENTO_FUERA_DE_RANGO}
    assert all("VSCQD" in a.mensaje or "TXCER" in a.mensaje for a in resultado.alertas)


def test_un_universo_sano_no_emite_alertas() -> None:
    resultado = evaluar_sanidad(
        [especie("MR46O", "usd_hard", 0.1310), especie("MR46D", "usd_hard", 0.1308)]
    )
    assert resultado.alertas == []
    assert resultado.evaluados == 2


def test_el_descarte_serializado_dice_contra_que_se_comparo_y_en_que_unidad() -> None:
    """Sin la unidad el valor no se puede leer: 4,8 es un descarte en CER y un dato sano en tasa
    fija, y quien audite el listado tiene que verlo sin ir a buscar la tabla de topes."""
    (descarte,) = evaluar_sanidad([especie("TXCER", "cer", 1.50)]).descartes
    como_dict = descarte.como_dict()
    assert como_dict["motivo"] == "rendimiento_fuera_de_rango"
    assert como_dict["umbral"] == 1.0
    assert como_dict["segmento"] == "cer"
    assert "CER" in str(como_dict["naturaleza_nombre"])


def test_los_descartes_vienen_ordenados_por_ticker() -> None:
    """El orden es la clave del cursor del endpoint: si no fuera estable, paginar saltearía."""
    resultado = evaluar_sanidad(
        [
            especie("ZZZZO", "cer", 1.50),
            especie("AAAAO", "cer", 1.60),
            especie("MMMMO", "cer", 1.70),
        ]
    )
    assert [d.ticker for d in resultado.descartes] == ["AAAAO", "MMMMO", "ZZZZO"]
