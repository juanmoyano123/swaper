"""El tipo de cambio implícito, la normalización de volumen y el contraste — F-012.

Los cinco criterios de aceptación de la ficha, uno por uno, más los bordes que el motor resolvió a
los golpes y que el port tiene que seguir resolviendo igual: el cociente fuera de rango, la emisión
con dos tickers del mismo lado y el universo sin pares suficientes.

Todo acá es puro: sin base, sin red y sin reloj. El índice de contraste entra como una lista de
diccionarios, que es exactamente la forma de `FilaIndice`, para que probar el contraste no requiera
hablar con BYMA.
"""

from typing import Any

import pytest

from app.universo.cambio import (
    DISPERSION_ACEPTABLE,
    INDICE_EN_DOLARES,
    INDICE_EN_PESOS,
    MIN_PARES_FX,
    TOLERANCIA_CONTRASTE,
    contrastar,
    cotiza_en_dolares,
    cotiza_en_pesos,
    derivar_tipo_de_cambio,
    normalizar_volumen,
)
from app.universo.segmentacion import segmentar

# El tipo de cambio con el que se arman los universos de prueba. Es un número plausible de hoy: los
# chequeos de rango del módulo son 500 y 5000, así que un valor de juguete no probaría lo mismo.
FX = 1500.0


def par(
    raiz: str,
    *,
    precio_ars: float | None = 1500.0,
    precio_usd: float | None = 1.0,
    sufijo_usd: str = "D",
    volumen_ars: float | None = 0.0,
    volumen_usd: float | None = 0.0,
    moneda_ars: str | None = "ARS",
    moneda_usd: str | None = "USD",
) -> list[dict[str, Any]]:
    """Una emisión con su especie en pesos y su especie en dólares, como las lee la vista."""
    return [
        {
            "ticker": f"{raiz}O",
            "clase_activo": "on_corporativo",
            "tipo_tasa": "hard-dollar",
            "tir": 0.10,
            "lastPrice": precio_ars,
            "effectiveVolume": volumen_ars,
            "moneda_cotizacion": moneda_ars,
        },
        {
            "ticker": f"{raiz}{sufijo_usd}",
            "clase_activo": "on_corporativo",
            "tipo_tasa": "hard-dollar",
            "tir": 0.10,
            "lastPrice": precio_usd,
            "effectiveVolume": volumen_usd,
            "moneda_cotizacion": moneda_usd,
        },
    ]


def universo(pares: int = MIN_PARES_FX, **kwargs: Any) -> list:
    """`pares` emisiones que cotizan en las dos puntas, ya segmentadas."""
    filas = [f for i in range(pares) for f in par(f"E{i:03d}", **kwargs)]
    return segmentar(filas).especies


def indices(pesos: float, dolares: float) -> list[dict[str, Any]]:
    """Las filas de `index-price` que importan, con la forma que les da `normalizar_fila_indice`."""
    return [
        {"indice": INDICE_EN_PESOS, "valor": pesos},
        {"indice": INDICE_EN_DOLARES, "valor": dolares},
        {"indice": "SPBYCAP", "valor": 42650.36},
    ]


# --- GWT 1: con 20 pares o más sale la mediana, con sus pares y su dispersión --------------------


def test_con_veinte_pares_da_la_mediana_de_los_cocientes_y_reporta_la_muestra() -> None:
    """GIVEN un universo con al menos 20 emisiones en pesos y en MEP
    WHEN se calcula el tipo de cambio implícito
    THEN se toma la mediana de los cocientes usando la especie D, y se reporta la cantidad de pares
    y la dispersión intercuartil."""
    cambio = derivar_tipo_de_cambio(universo(MIN_PARES_FX))

    assert cambio.disponible
    assert cambio.valor == pytest.approx(FX)
    assert cambio.pares == MIN_PARES_FX
    assert cambio.dispersion == pytest.approx(0.0)


def test_la_mediana_no_se_mueve_por_un_precio_desactualizado() -> None:
    """Es la razón de usar mediana y no promedio: una punta vieja no puede correr el número.

    Se arma con un cociente absurdo pero dentro del rango posible, que es el caso difícil: uno
    fuera de rango lo atrapa el chequeo y no llega a la muestra.
    """
    especies = universo(MIN_PARES_FX) + segmentar(par("VIEJO", precio_ars=4500.0)).especies
    cambio = derivar_tipo_de_cambio(especies)

    assert cambio.valor == pytest.approx(FX)
    assert cambio.pares == MIN_PARES_FX + 1
    assert cambio.dispersion == pytest.approx(0.0), "el rango intercuartil también es robusto"


def test_la_dispersion_alta_se_alerta_pero_el_implicito_se_usa_igual() -> None:
    """El implícito disperso sigue siendo el mejor número que hay: lo que cambia es qué se sabe."""
    mitad = [
        *[f for i in range(10) for f in par(f"A{i:02d}", precio_ars=1400.0)],
        *[f for i in range(10) for f in par(f"B{i:02d}", precio_ars=1600.0)],
    ]
    cambio = derivar_tipo_de_cambio(segmentar(mitad).especies)

    assert cambio.disponible
    assert cambio.dispersion > DISPERSION_ACEPTABLE
    assert "tipo_de_cambio_disperso" in {a.codigo for a in cambio.alertas}


# --- GWT 2: con menos de 20 pares no se normaliza nada y se declara ------------------------------


def test_con_menos_de_veinte_pares_no_hay_tipo_de_cambio() -> None:
    """GIVEN un universo con menos de 20 pares disponibles
    WHEN se calcula el tipo de cambio
    THEN no se normaliza nada, y la barra de estado del dato declara que la comparación entre
    monedas no está disponible."""
    cambio = derivar_tipo_de_cambio(universo(MIN_PARES_FX - 1))

    assert not cambio.disponible
    assert cambio.valor is None
    assert cambio.pares == MIN_PARES_FX - 1
    alerta = next(a for a in cambio.alertas if a.codigo == "tipo_de_cambio_sin_pares")
    assert "no están disponibles" in alerta.mensaje
    assert alerta.detalle == {"pares": MIN_PARES_FX - 1, "minimo": MIN_PARES_FX}


def test_sin_tipo_de_cambio_la_especie_en_pesos_queda_sin_volumen_comparable() -> None:
    """Y no con su volumen crudo: un número del que no se sabe la unidad no es comparable.

    Es la única diferencia deliberada con el motor, que ahí deja el crudo. Dejarlo pasar haría que
    el desempate por liquidez ordenara pesos contra dólares en un día sin pares.
    """
    especies = universo(MIN_PARES_FX - 1, volumen_ars=15000.0, volumen_usd=10.0)
    normalizadas = normalizar_volumen(especies, derivar_tipo_de_cambio(especies))
    por_ticker = {e.ticker: e for e in normalizadas}

    assert por_ticker["E000O"].volumen_usd is None
    assert por_ticker["E000O"].volumen == 15000.0
    assert por_ticker["E000D"].volumen_usd == 10.0


# --- GWT 3: `EXT` no entra a la muestra, y quién quedó afuera se dice -----------------------------
#
# Reescrito el 08/08/2026 con la regla 11. Antes esta sección probaba lo contrario: que la especie C
# entrara como suplente cuando la emisión no tenía D. La medición que justificaba preferir la D
# —1521 contra 1576, un 3,6 % que las delata como cosas distintas— es hoy el argumento para
# excluirla del todo: para promediarla habría que saber que `EXT` denota dólares y BYMA no lo
# publica. No costó cobertura: cero emisiones del universo real tienen sólo par por `EXT`.


def test_la_emision_sin_usd_no_entra_a_la_muestra_y_se_dice_cuales_son() -> None:
    """GIVEN una emisión que cotiza en pesos y en `EXT` pero no en `USD`
    WHEN se arma la muestra de pares
    THEN no aporta cociente, y se la nombra: su precio existe, lo que falta es saber en qué unidad
    está el otro lado."""
    especies = (
        universo(MIN_PARES_FX) + segmentar(par("CABLE", sufijo_usd="C", moneda_usd="EXT")).especies
    )
    cambio = derivar_tipo_de_cambio(especies)

    assert cambio.par_sin_documentar == ["CABLE"]
    assert cambio.pares == MIN_PARES_FX, "la emisión sin USD no puede sumar un par"
    alerta = next(a for a in cambio.alertas if a.codigo == "tipo_de_cambio_par_sin_documentar")
    assert "CABLE" in alerta.mensaje


def test_la_especie_ext_no_entra_ni_siquiera_cuando_la_emision_tiene_usd() -> None:
    """El cociente contra la `EXT` daría otro número, y no sabemos cuál de los dos es el cambio."""
    con_las_tres = [
        *par("TRES"),
        {
            "ticker": "TRESC",
            "clase_activo": "on_corporativo",
            "tipo_tasa": "hard-dollar",
            "tir": 0.10,
            "lastPrice": 0.5,  # daría un cociente de 3000 si entrara
            "effectiveVolume": 0.0,
            "moneda_cotizacion": "EXT",
        },
    ]
    cambio = derivar_tipo_de_cambio(segmentar([*[f for f in con_las_tres]]).especies)

    assert cambio.pares == 1
    assert cambio.par_sin_documentar == [], "teniendo USD, la emisión no quedó sin par"
    assert cambio.moneda_sin_documentar == ["TRESC"], "pero la especie sí se cuenta"


def test_el_lado_del_par_lo_decide_la_moneda_declarada_y_no_el_sufijo() -> None:
    """El caso construido a mano, porque el universo real todavía no lo tiene.

    Las seis especies con sufijo D declaradas en `ARS` están hoy solas en su emisión, así que ni la
    regla vieja ni la nueva producen un par con ellas (verificado el 08/08/2026: `precio_imposible`
    da cero con las dos). Este test las pone con una hermana en pesos —el día que BYMA la publique—
    y fija qué tiene que pasar: la letra no manda, manda lo declarado. Sin esto, la regresión no se
    notaría hasta que la fuente cambiara.
    """
    disfrazada = [
        *par("MENTIRA"),  # el par legítimo: MENTIRAO en pesos y MENTIRAD en USD
        {
            "ticker": "TRAMPAD",  # sufijo D, pero la fuente la declara en pesos
            "clase_activo": "on_corporativo",
            "tipo_tasa": "hard-dollar",
            "tir": 0.10,
            "lastPrice": 121_100.0,
            "effectiveVolume": 0.0,
            "moneda_cotizacion": "ARS",
        },
    ]
    cambio = derivar_tipo_de_cambio(segmentar(disfrazada).especies)

    assert cambio.pares == 1, "sólo el par legítimo"
    assert cambio.precio_imposible == [], "la especie disfrazada no se acusa de tener el precio mal"


# --- GWT 4: el índice de BYMA contrasta, y el implícito se conserva como fuente ------------------


def test_el_contraste_no_dispara_cuando_el_indice_publicado_coincide() -> None:
    cambio = derivar_tipo_de_cambio(universo(), indices(3_000_000.0, 2_000.0))

    assert cambio.contraste is not None
    assert cambio.contraste.publicado == pytest.approx(1500.0)
    assert cambio.contraste.coincide
    assert "tipo_de_cambio_contraste" not in {a.codigo for a in cambio.alertas}


def test_si_difiere_del_indice_sale_alerta_y_el_implicito_sigue_siendo_la_fuente() -> None:
    """GIVEN el implícito derivado y el índice publicado en index-price
    WHEN difieren más allá del umbral configurado
    THEN se emite alerta de contraste, y el implícito se conserva como fuente."""
    cambio = derivar_tipo_de_cambio(universo(), indices(3_000_000.0, 1_500.0))

    assert cambio.valor == pytest.approx(FX), "el implícito no se toca"
    assert cambio.contraste is not None
    assert not cambio.contraste.coincide
    alerta = next(a for a in cambio.alertas if a.codigo == "tipo_de_cambio_contraste")
    assert "Se sigue usando el implícito" in alerta.mensaje


def test_la_tolerancia_deja_pasar_el_canje_entre_mep_y_cable() -> None:
    """Un ~3,6 % de diferencia es el canje, no un error: alertarlo todos los días es no alertar."""
    assert TOLERANCIA_CONTRASTE > 0.036


def test_sin_indices_el_implicito_sale_igual_y_se_declara_que_no_se_contrasto() -> None:
    """El contraste es un control. Que no esté no puede romper el cálculo ni invalidarlo."""
    cambio = derivar_tipo_de_cambio(universo(), indices=[])

    assert cambio.valor == pytest.approx(FX)
    assert cambio.contraste is None
    assert "tipo_de_cambio_sin_contraste" in {a.codigo for a in cambio.alertas}


def test_un_indice_en_dolares_en_cero_no_produce_un_contraste_infinito() -> None:
    """Dividir por él daría un número; ese número no sería un tipo de cambio."""
    assert contrastar(1500.0, indices(3_000_000.0, 0.0)) is None


def test_un_indice_que_viene_sin_valor_no_se_contrasta_contra_nada() -> None:
    assert contrastar(1500.0, [{"indice": INDICE_EN_PESOS, "valor": None}]) is None


# --- GWT 5: los volúmenes se comparan en dólares --------------------------------------------------


def test_las_dos_especies_de_un_bono_se_comparan_en_la_misma_moneda() -> None:
    """GIVEN un bono con especie en pesos y especie en dólares
    WHEN se comparan sus volúmenes
    THEN los dos están expresados en dólares antes de la comparación.

    El caso es el del motor: la especie en pesos muestra 1.500 veces más volumen que su hermana y
    las dos operaron lo mismo.
    """
    especies = universo(volumen_ars=15_000.0, volumen_usd=10.0)
    normalizadas = normalizar_volumen(especies, derivar_tipo_de_cambio(especies))
    por_ticker = {e.ticker: e for e in normalizadas}

    assert por_ticker["E000O"].volumen == 15_000.0
    assert por_ticker["E000O"].volumen_usd == pytest.approx(10.0)
    assert por_ticker["E000D"].volumen_usd == pytest.approx(10.0)


def test_el_volumen_crudo_no_se_pisa_al_normalizar() -> None:
    """Lo que la fuente publicó tiene que seguir estando: sin él no se puede auditar el derivado."""
    especies = universo(volumen_ars=15_000.0)
    normalizadas = normalizar_volumen(especies, derivar_tipo_de_cambio(especies))

    assert all(e.volumen is not None for e in normalizadas)


def test_una_especie_sin_volumen_publicado_no_recibe_un_cero_inventado() -> None:
    """No haber operado y no saber cuánto operó no son lo mismo, y no se pueden confundir acá."""
    especies = universo(volumen_ars=None)
    normalizadas = normalizar_volumen(especies, derivar_tipo_de_cambio(especies))

    assert {e.ticker: e for e in normalizadas}["E000O"].volumen_usd is None


# --- La moneda de cotización se lee, no se deduce -------------------------------------------------


def test_la_moneda_declarada_manda_sobre_el_sufijo_del_ticker() -> None:
    """El caso real: hay especies con sufijo D declaradas en pesos, y sus precios lo confirman.

    Tomarlas por dólares por el sufijo multiplicaría su liquidez por el tipo de cambio, que es
    exactamente el error que esta feature existe para evitar.
    """
    (en_pesos,) = segmentar(
        [
            {
                "ticker": "BA37D",
                "clase_activo": "bono_subsoberano",
                "tipo_tasa": "hard-dollar",
                "tir": 0.10,
                "lastPrice": 121_100.0,
                "effectiveVolume": 622_111_694.4,
                "moneda_cotizacion": "ARS",
            }
        ]
    ).especies

    assert not cotiza_en_dolares(en_pesos)


def test_ext_no_se_toma_por_dolar_porque_la_fuente_no_dice_que_lo_sea() -> None:
    """Invertido el 08/08/2026 por la regla 11. Antes este test afirmaba que `EXT` era el cable.

    Nadie en BYMA publica qué denota `EXT`: no es ISO 4217 como `ARS` y `USD`, es vocabulario propio
    de la fuente. Lo medido —cociente ≈1576 contra ≈1521 de la `USD`— *sugiere* otro dólar, y
    sugerir no es declarar. Ni se convierte su volumen ni entra al par del implícito.
    """
    (opaca,) = segmentar(
        [
            {
                "ticker": "MR46C",
                "clase_activo": "on_corporativo",
                "tipo_tasa": "hard-dollar",
                "tir": 0.10,
                "lastPrice": 1.0,
                "effectiveVolume": 10.0,
                "moneda_cotizacion": "EXT",
            }
        ]
    ).especies

    assert not cotiza_en_dolares(opaca)
    assert not cotiza_en_pesos(opaca), "tampoco es peso: el hueco es de tres ramas, no de dos"


def test_el_volumen_en_ext_queda_vacio_en_vez_de_dividirse_por_el_implicito() -> None:
    """El error que la tercera rama evita: `not cotiza_en_dolares` no significa "está en pesos".

    Con dos ramas, un monto en `EXT` caía del lado de los pesos y se dividía por ~1521, publicando
    un número mil quinientas veces más chico que el operado bajo un rótulo que decía dólares.
    """
    especies = universo(MIN_PARES_FX) + segmentar(
        [
            {
                "ticker": "OPACOC",
                "clase_activo": "on_corporativo",
                "tipo_tasa": "hard-dollar",
                "tir": 0.10,
                "lastPrice": 78.52,
                "effectiveVolume": 1_177_007.58,
                "moneda_cotizacion": "EXT",
            }
        ]
    ).especies
    cambio = derivar_tipo_de_cambio(especies)
    por_ticker = {e.ticker: e for e in normalizar_volumen(especies, cambio)}

    assert cambio.disponible, "el implícito existe: lo que falta es en qué unidad está este monto"
    assert por_ticker["OPACOC"].volumen_usd is None
    assert por_ticker["OPACOC"].volumen == 1_177_007.58, "el crudo se conserva para poder auditarlo"
    assert cambio.moneda_sin_documentar == ["OPACOC"]
    assert "moneda_de_cotizacion_sin_documentar" in {a.codigo for a in cambio.alertas}


def test_sin_moneda_declarada_no_se_deduce_del_sufijo_y_se_dice_cuantas_veces() -> None:
    """Invertido el 08/08/2026: antes se caía al sufijo y se contaba; ahora no se cae y se cuenta.

    La rama existía para el consolidado histórico, que no tiene la columna. Sobre la base de hoy la
    cobertura de `moneda_cotizacion` es del 100 %, así que sacarla no costó una sola conversión —y
    el día que la cobertura baje, el hueco se ve en vez de taparse con la letra del ticker.
    """
    especies = universo(moneda_ars=None, moneda_usd=None)
    cambio = derivar_tipo_de_cambio(especies)
    por_ticker = {e.ticker: e for e in normalizar_volumen(especies, cambio)}

    assert len(cambio.moneda_sin_declarar) == MIN_PARES_FX * 2
    assert not cotiza_en_dolares(por_ticker["E000D"]), "el sufijo D ya no alcanza"
    assert not cotiza_en_dolares(por_ticker["E000O"])
    assert por_ticker["E000D"].volumen_usd is None
    assert por_ticker["E000O"].volumen_usd is None
    assert not cambio.disponible, "sin monedas declaradas no hay de dónde sacar un par"
    assert "moneda_de_cotizacion_sin_declarar" in {a.codigo for a in cambio.alertas}


# --- Los bordes que el motor resolvió y el port tiene que seguir resolviendo ----------------------


def test_un_cociente_fuera_de_rango_no_es_un_tipo_de_cambio_y_se_nombra() -> None:
    """Es una de las dos puntas con el precio mal cargado. No entra a la mediana y se alerta."""
    especies = universo(MIN_PARES_FX) + segmentar(par("ROTO", precio_usd=0.001)).especies
    cambio = derivar_tipo_de_cambio(especies)

    assert cambio.precio_imposible == ["ROTO"]
    assert cambio.pares == MIN_PARES_FX
    alerta = next(a for a in cambio.alertas if a.codigo == "tipo_de_cambio_precio_imposible")
    assert "ROTO" in alerta.mensaje
    assert alerta.detalle["rango"] == [500.0, 5000.0]


def test_una_emision_con_dos_tickers_del_mismo_lado_se_saltea_entera() -> None:
    """Elegir cuál de los dos usar sería inventar, así que la emisión no aporta cociente."""
    duplicada = [
        *par("DOBLE"),
        {
            "ticker": "DOBLE",
            "clase_activo": "on_corporativo",
            "tipo_tasa": "hard-dollar",
            "tir": 0.10,
            "lastPrice": 1400.0,
            "effectiveVolume": 0.0,
            "moneda_cotizacion": "ARS",
        },
    ]
    cambio = derivar_tipo_de_cambio(segmentar(duplicada).especies)

    assert cambio.pares == 0


def test_un_precio_en_cero_o_negativo_no_forma_par() -> None:
    """Dividir por cero no da un tipo de cambio, y un precio negativo no es un precio."""
    especies = segmentar([*par("CERO", precio_usd=0.0), *par("NEG", precio_ars=-1500.0)]).especies

    assert derivar_tipo_de_cambio(especies).pares == 0


def test_el_universo_vacio_no_rompe_nada() -> None:
    cambio = derivar_tipo_de_cambio([])

    assert not cambio.disponible
    assert cambio.pares == 0
    assert normalizar_volumen([], cambio) == []


def test_el_resultado_viaja_entero_al_api() -> None:
    """El número solo no alcanza: sin los pares y la dispersión no se puede saber si creerle."""
    payload = derivar_tipo_de_cambio(universo(), indices(3_000_000.0, 2_000.0)).como_dict()

    assert payload["valor"] == pytest.approx(FX)
    assert payload["disponible"] is True
    assert payload["pares"] == MIN_PARES_FX
    assert payload["minimo_de_pares"] == MIN_PARES_FX
    assert payload["dispersion"] == pytest.approx(0.0)
    assert payload["contraste"]["coincide"] is True
    assert payload["contraste"]["indices"] == {
        INDICE_EN_PESOS: 3_000_000.0,
        INDICE_EN_DOLARES: 2_000.0,
    }
