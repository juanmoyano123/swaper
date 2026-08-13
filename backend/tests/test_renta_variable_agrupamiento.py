"""Qué especies de renta variable son el mismo papel.

Cada test de acá fija una decisión tomada con el dueño del producto el 13/08/2026, mirando los
datos reales del universo. El orden es el de las preguntas que fueron apareciendo: primero el caso
normal, después los cuatro casos borde que la regla simple no cubría.
"""

from app.renta_variable.agrupamiento import (
    NO_IDENTIFICADO,
    agrupar,
    aplicar_contraste,
    hermanas,
    verificar,
)

# El tipo de cambio implícito del universo el día que se midieron estos casos.
MEP = 1527.0
# El cable, ~4 % arriba del MEP por el canje.
CABLE = 1585.0


# --- El caso normal -------------------------------------------------------------------------------


def test_las_tres_especies_de_apple_son_el_mismo_papel() -> None:
    g = agrupar({"AAPL", "AAPLC", "AAPLD"})

    assert g["AAPL"].emision == "AAPL"
    assert g["AAPL"].sufijo_liquidacion is None
    assert (g["AAPLC"].emision, g["AAPLC"].sufijo_liquidacion) == ("AAPL", "C")
    assert (g["AAPLD"].emision, g["AAPLD"].sufijo_liquidacion) == ("AAPL", "D")


def test_las_hermanas_se_ven_desde_cualquiera_de_las_tres() -> None:
    g = agrupar({"AAPL", "AAPLC", "AAPLD"})

    assert hermanas(g, "AAPL") == ["AAPLC", "AAPLD"]
    assert hermanas(g, "AAPLD") == ["AAPL", "AAPLC"]


def test_un_papel_de_una_sola_especie_no_tiene_hermanas_y_es_su_propia_emision() -> None:
    g = agrupar({"AAPL"})

    assert g["AAPL"].emision == "AAPL"
    assert hermanas(g, "AAPL") == []


# --- Caso borde 1: el ticker con punto ------------------------------------------------------------


def test_barrick_con_punto_se_agrupa_igual() -> None:
    """`B.C` y `B.D` difieren de `B` en dos caracteres, no en una letra. Son el mismo papel: el
    cociente de sus precios da el tipo de cambio, medido el 13/08/2026."""
    g = agrupar({"B", "B.C", "B.D"})

    assert (g["B.C"].emision, g["B.C"].sufijo_liquidacion) == ("B", "C")
    assert (g["B.D"].emision, g["B.D"].sufijo_liquidacion) == ("B", "D")
    assert hermanas(g, "B") == ["B.C", "B.D"]


# --- Caso borde 2: el ticker propio que termina en C o D ------------------------------------------


def test_sandstorm_no_es_santander_en_mep() -> None:
    """`SAND` (Sandstorm Gold) termina en D y existe `SAN` (Santander): la regla de strings los
    uniría. El agrupamiento los propone y el contraste de precio los separa."""
    g = agrupar({"SAN", "SAND"})
    assert (g["SAND"].emision, g["SAND"].sufijo_liquidacion) == ("SAN", "D")

    # Dos empresas distintas: su cociente no puede dar el tipo de cambio.
    (contraste,) = verificar(
        g, precios={"SAN": 5000.0, "SAND": 20.0}, monedas={"SAN": "ARS"}, tipo_de_cambio=MEP
    )
    assert contraste.confirmado is False, "250 no es el MEP: no son el mismo papel"


def test_una_variante_de_verdad_queda_confirmada() -> None:
    g = agrupar({"AAPL", "AAPLD"})
    (contraste,) = verificar(
        g,
        precios={"AAPL": 24050.0, "AAPLD": 15.8},
        monedas={"AAPL": "ARS"},
        tipo_de_cambio=MEP,
    )
    assert contraste.confirmado is True
    assert abs(contraste.desvio) < 0.01, "1.522 contra un MEP de 1.527"


def test_el_cable_se_confirma_aunque_no_de_el_mep() -> None:
    """El cable cotiza ~4 % arriba del MEP por el canje. No es un desvío: es otro dólar."""
    g = agrupar({"AAPL", "AAPLC"})
    (contraste,) = verificar(
        g,
        precios={"AAPL": 24050.0, "AAPLC": 15.17},
        monedas={"AAPL": "ARS"},
        tipo_de_cambio=MEP,
    )
    assert contraste.confirmado is True
    assert contraste.cociente > MEP


def test_un_dolar_mas_barato_que_el_mep_no_se_confirma() -> None:
    """Por debajo del implícito no hay lectura posible: ni MEP ni cable."""
    g = agrupar({"XX", "XXD"})
    (contraste,) = verificar(
        g, precios={"XX": 1000.0, "XXD": 1.0}, monedas={"XX": "ARS"}, tipo_de_cambio=MEP
    )
    assert contraste.confirmado is False


def test_sin_precio_en_alguna_punta_no_se_reporta_nada() -> None:
    """No se puede medir, así que no se afirma ni que sí ni que no: el silencio no es una
    confirmación, y el llamador lo sabe."""
    g = agrupar({"AAPL", "AAPLD"})
    assert verificar(g, {"AAPL": None, "AAPLD": 15.8}, {"AAPL": "ARS"}, MEP) == []


def test_sin_tipo_de_cambio_no_se_verifica_nada() -> None:
    """Con el implícito sin derivar no hay contra qué contrastar. No se inventa un tipo de cambio
    para poder opinar (regla 1)."""
    g = agrupar({"AAPL", "AAPLD"})
    assert verificar(g, {"AAPL": 24050.0, "AAPLD": 15.8}, {"AAPL": "ARS"}, None) == []


# --- Caso borde 3: la terminación 3 ---------------------------------------------------------------


def test_ambev_y_ambev3_quedan_separados() -> None:
    """Decisión del 13/08/2026, con la tabla oficial de CEDEARs de BYMA: `ABEV` cotiza sobre el ADR
    de NASDAQ con ratio 1:3 y `ABEV3` sobre la acción de B3 con ratio 1:1. Misma empresa, distinto
    instrumento — fusionarlos mezclaría dos papeles que no valen lo mismo."""
    g = agrupar({"ABEV", "ABEV3"})

    assert g["ABEV3"].emision == "ABEV3", "es su propio papel, no una variante de ABEV"
    assert g["ABEV3"].sufijo_liquidacion is None
    assert hermanas(g, "ABEV") == []


def test_la_variante_en_mep_de_un_papel_brasileno_sigue_agrupando() -> None:
    """`ABEV3` es su propio papel, pero `ABEV3D` sí es ese papel en MEP."""
    g = agrupar({"ABEV3", "ABEV3D"})
    assert (g["ABEV3D"].emision, g["ABEV3D"].sufijo_liquidacion) == ("ABEV3", "D")


# --- Caso borde 4: la terminación B ---------------------------------------------------------------


def test_las_que_terminan_en_b_van_a_no_identificado() -> None:
    """Decisión del 13/08/2026. Se midió qué NO son —no son moneda (se apilan sobre C y D y heredan
    la suya), no son plazo (mismo plazo que su base)— y BYMA no documenta qué son. Ninguna de las
    105 del universo operó nunca."""
    g = agrupar({"AAPL", "AAPLB", "XOM", "XOMD", "XOMDB"})

    for ticker in ("AAPLB", "XOMDB"):
        assert g[ticker].emision == NO_IDENTIFICADO
        assert g[ticker].no_identificado is True


def test_lo_no_identificado_no_tiene_hermanas_entre_si() -> None:
    """Dos especies que no sabemos qué son no se pueden declarar hermanas: compartir el cajón de lo
    desconocido no las hace el mismo papel."""
    g = agrupar({"AAPL", "AAPLB", "XOM", "XOMB"})
    assert hermanas(g, "AAPLB") == []
    assert hermanas(g, "XOMB") == []


def test_lo_no_identificado_no_arrastra_a_su_base() -> None:
    """Que `AAPLB` no se sepa qué es no puede ensuciar a `AAPL`, que sí se sabe."""
    g = agrupar({"AAPL", "AAPLC", "AAPLD", "AAPLB"})

    assert g["AAPL"].emision == "AAPL"
    assert hermanas(g, "AAPL") == ["AAPLC", "AAPLD"], "la B no entra al papel"


def test_lo_no_identificado_no_se_verifica_contra_el_precio() -> None:
    """No tiene sentido preguntarle al mercado por algo que además nunca opera."""
    g = agrupar({"AAPL", "AAPLB"})
    assert verificar(g, {"AAPL": 24050.0, "AAPLB": 15.8}, {"AAPL": "ARS"}, MEP) == []


# --- El guardia de los tickers cortos -------------------------------------------------------------


def test_un_ticker_corto_que_termina_en_d_no_se_parte() -> None:
    """`DD` (DuPont) no es `D` en MEP: partirlo dejaría un cuerpo de una letra, que no es ticker."""
    g = agrupar({"DD"})
    assert g["DD"].emision == "DD"
    assert g["DD"].sufijo_liquidacion is None


def test_sin_la_especie_base_en_el_universo_no_se_agrupa() -> None:
    """`AAPLD` sola, sin `AAPL` presente, no se declara variante de un papel que no está."""
    g = agrupar({"AAPLD"})
    assert g["AAPLD"].emision == "AAPLD"
    assert g["AAPLD"].sufijo_liquidacion is None


# --- El veredicto del mercado se aplica -----------------------------------------------------------


def test_un_cociente_que_no_es_un_tipo_de_cambio_desarma_el_grupo() -> None:
    """`BBD` es Banco Bradesco y `BB` es Blackberry: su cociente da 0,9, que no es un dólar ni por
    asomo. Caso real del universo del 13/08/2026."""
    g = agrupar({"BB", "BBD"})
    assert g["BBD"].emision == "BB", "la regla de strings los une..."

    contrastes = verificar(g, {"BB": 4670.0, "BBD": 5200.0}, {"BB": "ARS"}, MEP)
    corregido, alertados = aplicar_contraste(g, contrastes)

    assert corregido["BBD"].emision == "BBD", "...y el mercado los separa"
    assert corregido["BBD"].sufijo_liquidacion is None
    assert alertados == []


def test_un_dolar_con_el_precio_corrido_se_conserva_y_se_alerta() -> None:
    """Un cociente de 1.477 contra un implícito de 1.527 sigue siendo un dólar: es una punta con el
    precio de hace un rato, no otro papel. Desagrupar acá volvería a partir un papel que sí es el
    mismo — por eso se conserva y sólo se avisa."""
    g = agrupar({"MOS", "MOSD"})
    contrastes = verificar(g, {"MOS": 100000.0, "MOSD": 67.66}, {"MOS": "ARS"}, MEP)
    corregido, alertados = aplicar_contraste(g, contrastes)

    assert corregido["MOSD"].emision == "MOS", "sigue agrupado"
    assert alertados == ["MOSD"], "pero queda declarado"


def test_lo_confirmado_no_se_toca_ni_se_alerta() -> None:
    g = agrupar({"AAPL", "AAPLD"})
    contrastes = verificar(g, {"AAPL": 24050.0, "AAPLD": 15.8}, {"AAPL": "ARS"}, MEP)
    corregido, alertados = aplicar_contraste(g, contrastes)

    assert corregido["AAPLD"].emision == "AAPL"
    assert alertados == []
