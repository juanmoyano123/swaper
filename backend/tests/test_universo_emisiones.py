"""La doble vista del universo: qué especies son el mismo bono y cuál lo representa — F-011.

Los tres GWT de la feature se prueban acá, sin base y sin HTTP, porque las tres son decisiones de
dominio y no de transporte. El tercero —la advertencia de duplicado— es de servicio: el armador
todavía no existe, y lo que tiene que estar listo para cuando exista es la respuesta, no la
pantalla.
"""

from datetime import date

import pytest

from app.universo.emisiones import (
    CODIGO_EMISION_NO_COLAPSADA,
    CODIGO_ESPECIES_COLAPSADAS,
    CODIGO_MISMA_EMISION,
    CODIGO_RENDIMIENTO_PERDIDO_AL_COLAPSAR,
    TOLERANCIA_DURACION,
    deduplicar,
)
from app.universo.segmentacion import EspecieUniverso, segmentar


def especie(
    ticker: str,
    *,
    duracion: float | None = 4.0,
    vencimiento: date | None = date(2046, 1, 9),
    ley: str | None = "Ley N.Y.",
    moneda_cupon: str | None = "MEP",
    emisor: str | None = "Tesoro Nacional",
    rendimiento: float | None = 0.13,
    segmento: str = "usd_hard",
) -> EspecieUniverso:
    """Una especie con todos los datos cargados, para que cada test cambie sólo lo que prueba."""
    raiz = ticker[:-1] if len(ticker) >= 4 and ticker[-1] in ("O", "D", "C") else ticker
    return EspecieUniverso(
        ticker=ticker,
        raiz=raiz,
        clase_activo="bono_soberano",
        segmento=segmento,
        rendimiento=rendimiento,
        duracion=duracion,
        vencimiento=vencimiento,
        ley=ley,
        moneda_cupon=moneda_cupon,
        emisor=emisor,
    )


MR46 = [especie("MR46O"), especie("MR46D"), especie("MR46C")]


@pytest.fixture
def mr46():
    return deduplicar(MR46)


# --- GWT-1: la vista colapsada del armador -------------------------------------------------------


def test_las_tres_especies_de_mr46_son_una_sola_fila_para_el_armador(mr46) -> None:
    """Comprar MR46O y MR46D es comprar el mismo bono dos veces creyendo que se diversifica."""
    colapsado = mr46.colapsado()
    assert len(colapsado) == 1
    assert colapsado[0].raiz == "MR46"


def test_la_fila_colapsada_lleva_la_clave_de_emision_explicita(mr46) -> None:
    """Sin la clave, el armador tendría que cortar el ticker para saber de qué bono habla."""
    (fila,) = mr46.colapsado()
    assert fila.como_dict()["emision"] == "MR46"
    assert mr46.emision_de("MR46O").raiz == "MR46"


def test_la_emision_conserva_de_que_especies_esta_hecha(mr46) -> None:
    """La fila cuenta una vez, pero el armador todavía tiene que poder elegir cuál compra."""
    emision = mr46.por_raiz["MR46"]
    assert emision.tickers == ["MR46C", "MR46D", "MR46O"]
    assert emision.colapsadas == 2


def test_una_emision_de_una_sola_especie_pasa_entera(mr46) -> None:
    dedup = deduplicar([especie("AL30")])
    assert [e.ticker for e in dedup.colapsado()] == ["AL30"]
    assert dedup.por_raiz["AL30"].colapsadas == 0


# --- GWT-2: la vista viva del optimizador --------------------------------------------------------


def test_las_tres_especies_siguen_vivas_para_el_optimizador(mr46) -> None:
    """Los swaps de perfil rotan entre especies de la misma emisión: de MEP a Cable. Una vista
    colapsada no los dejaría ni ver."""
    assert [e.ticker for e in mr46.vivo()] == ["MR46C", "MR46D", "MR46O"]


def test_cada_especie_viva_lleva_lo_suyo_y_su_clave_de_emision(mr46) -> None:
    filas = {e.ticker: e.como_dict() for e in mr46.vivo()}
    assert filas["MR46D"]["emision"] == "MR46"
    assert filas["MR46D"]["sufijo_liquidacion"] == "D"
    assert filas["MR46C"]["sufijo_liquidacion"] == "C"
    assert {f["rendimiento"] for f in filas.values()} == {0.13}


def test_la_vista_viva_no_filtra_lo_que_la_sanidad_descarto() -> None:
    """Deduplicar no es descartar. El descartado sigue en el universo para poder auditarlo."""
    dedup = deduplicar(MR46, descartados={"MR46D"})
    assert "MR46D" in {e.ticker for e in dedup.vivo()}


def test_las_hermanas_de_una_especie_son_las_otras_especies_del_mismo_bono(mr46) -> None:
    assert [e.ticker for e in mr46.hermanas("MR46D")] == ["MR46C", "MR46O"]
    assert mr46.hermanas("AL30") == []


# --- GWT-3: la advertencia de duplicado, que es servicio y no pantalla ---------------------------


def test_agregar_mr46c_a_una_cartera_que_ya_tiene_mr46d_no_suma_diversificacion(mr46) -> None:
    advertencia = mr46.advertencia_de_duplicado("MR46C", ["MR46D", "AL30"])
    assert advertencia is not None
    assert advertencia.codigo == CODIGO_MISMA_EMISION
    assert "MR46D" in advertencia.mensaje
    assert advertencia.detalle["emision"] == "MR46"
    assert advertencia.accion_requerida


def test_agregar_una_emision_que_la_cartera_no_tiene_no_advierte_nada(mr46) -> None:
    assert mr46.advertencia_de_duplicado("MR46C", ["AL30", "GD30D"]) is None


def test_una_especie_que_no_cotiza_igual_se_reconoce_como_de_la_emision(mr46) -> None:
    """El asesor pregunta por lo que quiere agregar, y eso puede ser una especie que hoy no está en
    el universo. Lo que se contesta es a qué emisión pertenecería."""
    dedup = deduplicar([especie("MR46O"), especie("MR46D")])
    advertencia = dedup.advertencia_de_duplicado("MR46C", ["MR46D"])
    assert advertencia is not None
    assert advertencia.detalle["ticker"] == "MR46C"


def test_no_se_advierte_duplicado_sobre_un_grupo_que_no_se_colapso() -> None:
    """Si el chequeo de duración dijo que no son la misma emisión, llamarlas duplicado sería tan
    falso como el error que la feature ataca: esas dos posiciones sí diversifican."""
    dedup = deduplicar([especie("XXXXO", duracion=2.0), especie("XXXXD", duracion=9.0)])
    assert dedup.advertencia_de_duplicado("XXXXD", ["XXXXO"]) is None


def test_la_especie_no_se_advierte_contra_si_misma(mr46) -> None:
    assert mr46.advertencia_de_duplicado("MR46D", ["MR46D"]) is None


# --- El chequeo de sanidad: misma emisión, misma duración ---------------------------------------


def test_dos_especies_con_duraciones_dispares_no_son_la_misma_emision() -> None:
    """Comparten raíz y nada más. Colapsarlas fusionaría dos bonos distintos en una sola fila, que
    es peor que duplicar uno."""
    dedup = deduplicar([especie("XXXXO", duracion=2.0), especie("XXXXD", duracion=9.0)])
    emision = dedup.por_raiz["XXXX"]
    assert not emision.colapsada
    assert emision.representante is None
    assert [e.ticker for e in dedup.colapsado()] == ["XXXXD", "XXXXO"]


def test_una_diferencia_dentro_del_cinco_por_ciento_si_colapsa() -> None:
    """4,0 contra 3,85 es la misma emisión con el dato redondeado distinto, no dos bonos."""
    dedup = deduplicar([especie("XXXXO", duracion=4.0), especie("XXXXD", duracion=3.85)])
    emision = dedup.por_raiz["XXXX"]
    assert emision.colapsada
    assert emision.dispersion_duracion == pytest.approx(0.0375)
    assert emision.dispersion_duracion < TOLERANCIA_DURACION


def test_sin_dos_duraciones_publicadas_no_hay_evidencia_en_contra_y_colapsa() -> None:
    """Hoy casi ninguna especie trae `duration`. Tratar el faltante como discordancia partiría en
    dos todas las emisiones del universo: no saber no es saber que son distintas."""
    dedup = deduplicar([especie("XXXXO", duracion=None), especie("XXXXD", duracion=4.0)])
    emision = dedup.por_raiz["XXXX"]
    assert emision.colapsada
    assert emision.dispersion_duracion is None


def test_las_duraciones_en_cero_no_dividen_por_cero() -> None:
    """El piso del divisor viene del motor. Dos ceros son la misma duración y el grupo colapsa; un
    cero contra un número negativo —que no es una duración— dispara la dispersión y el grupo no se
    fusiona, que es el lado correcto para caer ante la duda."""
    iguales = deduplicar([especie("XXXXO", duracion=0.0), especie("XXXXD", duracion=0.0)])
    assert iguales.por_raiz["XXXX"].colapsada

    imposible = deduplicar([especie("YYYYO", duracion=0.0), especie("YYYYD", duracion=-1.0)])
    assert not imposible.por_raiz["YYYY"].colapsada


# --- Quién representa a la emisión ---------------------------------------------------------------


def test_una_especie_descartada_por_la_sanidad_nunca_representa_a_su_emision() -> None:
    """Sería elegir como cara visible del bono a la especie con el precio mal escalado. Y gana
    contra la completitud: un dato roto no mejora por estar completo."""
    dedup = deduplicar(
        [
            especie("MR46C"),
            especie("MR46D", ley=None, moneda_cupon=None, emisor=None, vencimiento=None),
        ],
        descartados={"MR46C"},
    )
    assert dedup.por_raiz["MR46"].representante.ticker == "MR46D"


def test_a_igualdad_de_sanidad_gana_la_especie_de_datos_mas_completos() -> None:
    """Los cuatro campos son de la emisión: la especie que más tenga es la que mejor la describe."""
    dedup = deduplicar(
        [
            especie("MR46C", ley=None, moneda_cupon=None),
            especie("MR46D"),
            especie("MR46O", emisor=None),
        ]
    )
    assert dedup.por_raiz["MR46"].representante.ticker == "MR46D"


def test_el_desempate_es_estable_y_no_mira_volumen() -> None:
    """El hueco de F-012, explícito. El desempate por volumen exige el volumen normalizado a
    dólares: con el crudo siempre ganaría la especie en pesos por el tipo de cambio y no por
    liquidez. Mientras tanto desempata el ticker, que es arbitrario pero no miente ni cambia entre
    corridas."""
    representantes = {
        deduplicar(orden).por_raiz["MR46"].representante.ticker
        for orden in ([*MR46], list(reversed(MR46)), [MR46[1], MR46[2], MR46[0]])
    }
    assert representantes == {"MR46C"}


def test_todas_las_especies_descartadas_igual_dejan_una_fila() -> None:
    """La emisión no desaparece del armador porque su dato esté roto: eso lo decide `operables`."""
    dedup = deduplicar(MR46, descartados={"MR46C", "MR46D", "MR46O"})
    assert len(dedup.colapsado()) == 1


# --- El resumen y las alertas --------------------------------------------------------------------


def test_el_resumen_dice_cuantas_especies_se_colapsaron_y_cuantas_no() -> None:
    dedup = deduplicar(
        [*MR46, especie("XXXXO", duracion=2.0), especie("XXXXD", duracion=9.0), especie("AL30")]
    )
    resumen = dedup.resumen()
    assert resumen["especies"] == 6
    assert resumen["emisiones"] == 3
    assert resumen["especies_colapsadas"] == 2
    assert resumen["filas_colapsadas"] == 4  # MR46 + XXXXO + XXXXD + AL30
    assert resumen["no_colapsadas_por_duracion"] == {"cantidad": 1, "muestra": ["XXXX"]}


def test_el_resumen_declara_que_el_desempate_por_volumen_no_esta(mr46) -> None:
    """No es un detalle de implementación: quien lea el resumen tiene que saber que el
    representante se eligió sin mirar liquidez."""
    assert mr46.resumen()["desempate_por_volumen"] is False


def test_las_alertas_nombran_lo_que_se_colapso_y_lo_que_no() -> None:
    dedup = deduplicar([*MR46, especie("XXXXO", duracion=2.0), especie("XXXXD", duracion=9.0)])
    alertas = {a.codigo: a for a in dedup.alertas}
    assert alertas[CODIGO_ESPECIES_COLAPSADAS].detalle["especies"] == 2
    assert alertas[CODIGO_EMISION_NO_COLAPSADA].detalle["emisiones"] == ["XXXX"]
    assert alertas[CODIGO_EMISION_NO_COLAPSADA].accion_requerida


def test_se_alerta_cuando_la_fila_colapsada_pierde_el_rendimiento_de_la_emision() -> None:
    """El efecto medible del desempate pendiente: IAMC publica la TIR sólo en el ticker que su
    informe nombra, y si ése no gana el desempate la emisión queda sin rendimiento para el armador
    aunque el número exista en la vista viva. No se corrige —sería un criterio que el motor no
    tiene— pero no puede pasar en silencio."""
    dedup = deduplicar([especie("MR46C", rendimiento=None), especie("MR46O", rendimiento=0.13)])
    emision = dedup.por_raiz["MR46"]

    assert emision.representante.ticker == "MR46C"
    assert emision.perdio_el_rendimiento_al_colapsar
    assert dedup.resumen()["rendimiento_perdido_al_colapsar"] == {
        "cantidad": 1,
        "muestra": ["MR46"],
    }
    alerta = next(a for a in dedup.alertas if a.codigo == CODIGO_RENDIMIENTO_PERDIDO_AL_COLAPSAR)
    assert alerta.accion_requerida
    assert "MR46O" in {e.ticker for e in dedup.vivo()}


def test_no_se_alerta_si_la_emision_entera_no_tiene_rendimiento() -> None:
    """Una emisión que nadie cotiza no perdió nada al colapsar: no había número que perder, y
    contarla sería alertar sobre un faltante de la fuente disfrazado de problema del colapso."""
    dedup = deduplicar([especie("MR46C", rendimiento=None), especie("MR46O", rendimiento=None)])
    assert not dedup.por_raiz["MR46"].perdio_el_rendimiento_al_colapsar
    assert dedup.resumen()["rendimiento_perdido_al_colapsar"]["cantidad"] == 0


def test_un_universo_sin_especies_hermanas_no_alerta_nada() -> None:
    """Colapsar cero no es una novedad: alertarlo sería ruido en todas las corridas."""
    assert deduplicar([especie("AL30"), especie("GD30")]).alertas == []


def test_un_universo_vacio_no_rompe() -> None:
    dedup = deduplicar([])
    assert dedup.colapsado() == []
    assert dedup.vivo() == []
    assert dedup.resumen()["emisiones"] == 0


# --- Lo que la lectura tiene que traer para que todo esto funcione -------------------------------


def test_la_segmentacion_trae_los_campos_que_deciden_el_representante() -> None:
    """Si `lectura.COLUMNAS` dejara de pedir alguna, la completitud daría cero para todos y el
    representante se elegiría por el desempate. Esto lo detecta."""
    (fila,) = segmentar(
        [
            {
                "ticker": "MR46D",
                "clase_activo": "bono_soberano",
                "tipo_tasa": "hard-dollar",
                "tir": 0.1308,
                "tna": None,
                "duration": 6.4,
                "maturity": date(2046, 1, 9),
                "law": "Ley N.Y.",
                "couponCurrency": "MEP",
                "underlying": "Tesoro Nacional",
            }
        ]
    ).especies
    assert fila.duracion == 6.4
    assert fila.vencimiento == date(2046, 1, 9)
    assert (fila.ley, fila.moneda_cupon, fila.emisor) == ("Ley N.Y.", "MEP", "Tesoro Nacional")


def test_una_fila_sin_los_campos_nuevos_sigue_segmentando() -> None:
    """La vista puede traerlos vacíos y eso no es un error: se cuenta como menos completitud."""
    (fila,) = segmentar(
        [
            {
                "ticker": "AL30",
                "clase_activo": "bono_soberano",
                "tipo_tasa": "hard-dollar",
                "tir": 0.10,
                "tna": None,
            }
        ]
    ).especies
    assert fila.duracion is None
    assert fila.vencimiento is None
    assert fila.sufijo_liquidacion is None
