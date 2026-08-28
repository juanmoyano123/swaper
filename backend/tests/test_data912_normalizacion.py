"""Dict crudo → `FilaLive`, el rótulo de procedencia y la conversión a `FilaRueda` para tickers
que sólo existen en data912.
"""

from app.ingesta.data912.normalizacion import (
    ENDPOINT_BYMA_POR_TRAMO,
    como_fila_rueda,
    normalizar_fila_live,
    rotulo_de,
)


def _crudo(**overrides: object) -> dict[str, object]:
    base = {
        "symbol": "AL30D",
        "c": 56.5,
        "v": 85654946.0,
        "q_op": 29004,
        "px_bid": 56.4,
        "q_bid": 10,
        "px_ask": 56.52,
        "q_ask": 20,
        "pct_change": 0.08,
    }
    base.update(overrides)
    return base


def test_mapea_todos_los_campos() -> None:
    fila = normalizar_fila_live(_crudo())
    assert fila == {
        "ticker": "AL30D",
        "ultimo": 56.5,
        "monto": 85654946.0,
        "operaciones": 29004,
        "px_bid": 56.4,
        "cantidad_bid": 10,
        "px_ask": 56.52,
        "cantidad_ask": 20,
        "variacion_pct": 0.08,
    }


def test_el_cero_se_preserva_en_monto_y_operaciones() -> None:
    """Un bono que no operó tiene volumen y operaciones en cero, y eso es un dato: no se lo
    esconde como faltante."""
    fila = normalizar_fila_live(_crudo(v=0, q_op=0))
    assert fila["monto"] == 0.0
    assert fila["operaciones"] == 0


def test_ausente_o_vacio_es_none() -> None:
    fila = normalizar_fila_live({"symbol": "", "c": None})
    assert fila["ticker"] is None
    assert fila["ultimo"] is None
    assert fila["monto"] is None
    assert fila["operaciones"] is None


def test_rotulo_operacion_en_la_sesion() -> None:
    fila = normalizar_fila_live(_crudo(q_op=1))
    assert rotulo_de(fila) == "data912"


def test_rotulo_sin_operaciones_es_arrastre() -> None:
    fila = normalizar_fila_live(_crudo(q_op=0))
    assert rotulo_de(fila) == "data912-arrastre"


def test_rotulo_operaciones_ausente_es_arrastre() -> None:
    fila = normalizar_fila_live(_crudo(q_op=None))
    assert rotulo_de(fila) == "data912-arrastre"


def test_como_fila_rueda_deja_la_metadata_en_none() -> None:
    fila = normalizar_fila_live(_crudo())
    rueda = como_fila_rueda(fila)
    assert rueda["moneda_cotizacion"] is None
    assert rueda["plazo_liquidacion"] is None
    assert rueda["vencimiento"] is None
    assert rueda["descripcion"] is None
    assert rueda["subtipo"] is None
    assert rueda["mercado"] is None
    assert rueda["precio_cierre"] is None
    assert rueda["precio_cierre_anterior"] is None


def test_como_fila_rueda_completa_precio_libro_y_origen() -> None:
    fila = normalizar_fila_live(_crudo())
    rueda = como_fila_rueda(fila)
    assert rueda["ticker"] == "AL30D"
    assert rueda["precio_ultimo"] == 56.5
    assert rueda["monto_operado"] == 85654946.0
    assert rueda["operaciones"] == 29004
    assert rueda["precio_compra"] == 56.4
    assert rueda["cantidad_compra"] == 10
    assert rueda["precio_venta"] == 56.52
    assert rueda["cantidad_venta"] == 20
    assert rueda["origen_precio"] == "data912"


def test_como_fila_rueda_con_moneda_previa_la_usa_sin_inventar_nada_mas() -> None:
    fila = normalizar_fila_live(_crudo())
    rueda = como_fila_rueda(fila, moneda="USD")
    assert rueda["moneda_cotizacion"] == "USD"
    assert rueda["plazo_liquidacion"] is None


def test_como_fila_rueda_de_un_arrastre_se_rotula_arrastre() -> None:
    fila = normalizar_fila_live(_crudo(q_op=0))
    rueda = como_fila_rueda(fila)
    assert rueda["origen_precio"] == "data912-arrastre"


def test_endpoint_byma_por_tramo_cubre_los_cinco_tramos() -> None:
    from app.ingesta.data912.cliente import TRAMOS_LIVE

    assert set(ENDPOINT_BYMA_POR_TRAMO) == set(TRAMOS_LIVE)


def test_arg_notes_mapea_al_panel_de_letras() -> None:
    """Medido el 28/08/2026: los 25 tickers de `live/arg_notes` son todos del panel `lebacs`.

    Con el mapeo viejo a `public-bonds`, un ticker que BYMA trae por `lebacs` y data912 por
    `arg_notes` aparecía bajo dos endpoints y disparaba `CODIGO_ESPECIE_REPETIDA` todos los días
    por una repetición que sólo existía en este diccionario.
    """
    assert ENDPOINT_BYMA_POR_TRAMO["arg_notes"] == "lebacs"


def test_los_endpoints_del_mapeo_existen_en_la_ingesta_de_byma() -> None:
    """Un nombre que BYMA no publica dejaría al ticker sólo-data912 sin poder clasificarse."""
    from app.ingesta.byma.cliente import ENDPOINTS_ESPECIES

    assert set(ENDPOINT_BYMA_POR_TRAMO.values()) <= set(ENDPOINTS_ESPECIES)
