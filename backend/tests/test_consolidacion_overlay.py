"""El overlay que cruza BYMA con data912 por ticker — experimento data912.

Lo que se prueba no es que un precio nuevo aparezca: es que **sólo** se pise lo que el diseño dice
que se pisa (precio/volumen/libro), que la metadata de BYMA nunca se toque, y que un ticker que
sólo trae data912 entre sin inventar una moneda que nadie declaró.
"""

from app.ingesta.byma.normalizacion import normalizar_fila_rueda
from app.ingesta.consolidacion.overlay import CODIGO_CONTRASTE_FUENTES, aplicar_overlay
from app.ingesta.data912.normalizacion import normalizar_fila_live


def especie_byma(ticker: str, *, moneda="USD", plazo="2", ultimo=100.0, monto=1000.0, **extra):
    crudo = {
        "symbol": ticker,
        "denominationCcy": moneda,
        "settlementType": plazo,
        "trade": ultimo,
        "volumeAmount": monto,
        "bidPrice": 99.0,
        "offerPrice": 101.0,
        "numberOfOrders": 5,
        "maturityDate": "2030-07-09",
        **extra,
    }
    return normalizar_fila_rueda(crudo)


def especie_live(ticker: str, *, ultimo=100.0, operaciones=1, monto=1000.0, **extra):
    crudo = {
        "symbol": ticker,
        "c": ultimo,
        "v": monto,
        "q_op": operaciones,
        "px_bid": (ultimo - 1) if ultimo is not None else None,
        "q_bid": 1,
        "px_ask": (ultimo + 1) if ultimo is not None else None,
        "q_ask": 1,
        "pct_change": 0.0,
        **extra,
    }
    return normalizar_fila_live(crudo)


# --- Ticker sólo en BYMA -------------------------------------------------------------------------


def test_ticker_solo_en_byma_queda_intacto_y_cae_a_byma():
    byma = {"public-bonds": [especie_byma("AEC2D")]}
    resultado = aplicar_overlay(byma, {})

    (fila,) = resultado.especies_por_endpoint["public-bonds"]
    assert "origen_precio" not in fila
    assert fila["precio_ultimo"] == 100.0
    assert resultado.conteos == {
        "pisados": 0,
        "arrastres": 0,
        "solo_data912": 0,
        "sin_precio_data912": 0,
        "contrastes": 0,
    }
    assert resultado.alertas == []


# --- Ticker en ambas fuentes -----------------------------------------------------------------


def test_ticker_en_ambas_con_operaciones_pisa_y_rotula_data912():
    byma = {"public-bonds": [especie_byma("AL30D", ultimo=56.9, moneda="USD")]}
    live = {"arg_bonds": [especie_live("AL30D", ultimo=56.52, operaciones=29004)]}

    resultado = aplicar_overlay(byma, live)

    (fila,) = resultado.especies_por_endpoint["public-bonds"]
    assert fila["precio_ultimo"] == 56.52
    assert fila["origen_precio"] == "data912"
    assert fila["moneda_cotizacion"] == "USD", "la metadata sigue siendo de BYMA"
    assert fila["plazo_liquidacion"] == "2"
    assert fila["vencimiento"] == "2030-07-09"
    assert resultado.conteos["pisados"] == 1


def test_ticker_en_ambas_sin_operaciones_pisa_y_rotula_arrastre():
    byma = {"negociable-obligations": [especie_byma("AFCHD", ultimo=103.1)]}
    live = {"arg_corp": [especie_live("AFCHD", ultimo=103.1, operaciones=0, monto=0)]}

    resultado = aplicar_overlay(byma, live)

    (fila,) = resultado.especies_por_endpoint["negociable-obligations"]
    assert fila["origen_precio"] == "data912-arrastre"
    assert resultado.conteos["arrastres"] == 1
    assert resultado.conteos["pisados"] == 0


def test_precio_data912_cero_o_ausente_no_toca_la_fila_de_byma():
    byma = {"public-bonds": [especie_byma("AEC2D", ultimo=100.0)]}
    live = {"arg_bonds": [especie_live("AEC2D", ultimo=0.0, operaciones=0)]}

    resultado = aplicar_overlay(byma, live)

    (fila,) = resultado.especies_por_endpoint["public-bonds"]
    assert "origen_precio" not in fila
    assert fila["precio_ultimo"] == 100.0
    assert resultado.conteos["sin_precio_data912"] == 1
    assert resultado.conteos["pisados"] == 0
    assert resultado.conteos["arrastres"] == 0


def test_pisa_todas_las_filas_del_ticker_cuando_viene_en_dos_plazos():
    """AL30D en plazo 1 y plazo 2: el overlay pisa las dos, la elección de plazo la sigue haciendo
    `_elegir_por_plazo` río abajo sin que el overlay tenga que reimplementarla."""
    byma = {
        "public-bonds": [
            especie_byma("AL30D", plazo="1", ultimo=56.0, monto=10.0),
            especie_byma("AL30D", plazo="2", ultimo=56.9, monto=5000.0),
        ]
    }
    live = {"arg_bonds": [especie_live("AL30D", ultimo=56.52, operaciones=29004)]}

    resultado = aplicar_overlay(byma, live)

    filas = resultado.especies_por_endpoint["public-bonds"]
    assert len(filas) == 2
    assert all(f["precio_ultimo"] == 56.52 for f in filas)
    assert all(f["origen_precio"] == "data912" for f in filas)


# --- Ticker sólo en data912 ------------------------------------------------------------------


def test_ticker_solo_en_data912_entra_al_endpoint_mapeado_del_tramo():
    live = {"arg_corp": [especie_live("NUEVO1", ultimo=101.0)]}

    resultado = aplicar_overlay({}, live)

    assert resultado.conteos["solo_data912"] == 1
    (fila,) = resultado.especies_por_endpoint["negociable-obligations"]
    assert fila["ticker"] == "NUEVO1"
    assert fila["precio_ultimo"] == 101.0
    assert fila["moneda_cotizacion"] is None, "sin moneda previa, no se inventa ninguna"
    assert fila["origen_precio"] == "data912"


def test_ticker_solo_en_data912_hereda_la_moneda_previa_sin_inventar_nada_mas():
    live = {"arg_bonds": [especie_live("AE38D", ultimo=81.2)]}

    resultado = aplicar_overlay({}, live, monedas_previas={"AE38D": "USD"})

    (fila,) = resultado.especies_por_endpoint["public-bonds"]
    assert fila["moneda_cotizacion"] == "USD"
    assert fila["plazo_liquidacion"] is None
    assert fila["vencimiento"] is None


def test_ticker_solo_en_data912_sin_precio_valido_no_entra():
    live = {"arg_stocks": [especie_live("FANTASMA", ultimo=None, operaciones=None)]}

    resultado = aplicar_overlay({}, live)

    assert resultado.especies_por_endpoint == {}
    assert resultado.conteos["solo_data912"] == 0


def test_cada_tramo_mapea_a_su_endpoint_de_byma():
    live = {
        "arg_bonds": [especie_live("A", ultimo=1.0)],
        "arg_corp": [especie_live("B", ultimo=1.0)],
        "arg_notes": [especie_live("C", ultimo=1.0)],
        "arg_cedears": [especie_live("D", ultimo=1.0)],
        "arg_stocks": [especie_live("E", ultimo=1.0)],
    }
    resultado = aplicar_overlay({}, live)
    endpoints = {ep for ep, filas in resultado.especies_por_endpoint.items() if filas}
    assert endpoints == {
        "public-bonds",
        "lebacs",
        "negociable-obligations",
        "cedears",
        "general-equity",
    }, "arg_notes va a lebacs desde el 28/08/2026: sus 25 tickers son todos de ese panel"


# --- Contraste entre fuentes -------------------------------------------------------------------


def test_contraste_mas_alla_de_la_tolerancia_genera_una_alerta_info_y_conserva_data912():
    byma = {"public-bonds": [especie_byma("AL30D", ultimo=50.0)]}
    live = {"arg_bonds": [especie_live("AL30D", ultimo=56.52, operaciones=1)]}

    resultado = aplicar_overlay(byma, live)

    (fila,) = resultado.especies_por_endpoint["public-bonds"]
    assert fila["precio_ultimo"] == 56.52, "se conserva el de data912 aunque contrasten"
    assert resultado.conteos["contrastes"] == 1
    (alerta,) = resultado.alertas
    assert alerta.codigo == CODIGO_CONTRASTE_FUENTES
    assert alerta.severidad.value == "info"
    assert alerta.detalle["muestra"][0]["ticker"] == "AL30D"


def test_diferencia_dentro_de_la_tolerancia_no_alerta():
    byma = {"public-bonds": [especie_byma("AL30D", ultimo=56.0)]}
    live = {"arg_bonds": [especie_live("AL30D", ultimo=56.5, operaciones=1)]}

    resultado = aplicar_overlay(byma, live)

    assert resultado.alertas == []
    assert resultado.conteos["contrastes"] == 0


# --- Determinismo -----------------------------------------------------------------------------


def test_determinismo_cuando_un_ticker_repite_entre_tramos():
    """No debería pasar en la práctica, pero si data912 repitiera un ticker entre tramos, la
    elección tiene que ser estable: gana operaciones>0, y a igualdad el tramo alfabético."""
    live = {
        "arg_stocks": [especie_live("X", ultimo=10.0, operaciones=0)],
        "arg_cedears": [especie_live("X", ultimo=20.0, operaciones=5)],
    }
    resultado = aplicar_overlay({}, live)
    (fila,) = resultado.especies_por_endpoint["cedears"]
    assert fila["precio_ultimo"] == 20.0, "gana la fila con operaciones, sea cual sea el tramo"
