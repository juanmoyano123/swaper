"""La corrida del universo saneado: leer, segmentar, sanear y reportar.

Acá se prueba lo que las dos capas por sí solas no cubren — que el universo descartado siga adentro,
que el resumen abra los conteos por segmento y que la lectura de la vista `resumen` se enganche con
las funciones puras sin perder nada por el camino.
"""

from typing import Any

import pytest

from app.universo.segmentacion import segmentar
from app.universo.servicio import sanear, sanear_universo

# Un universo chico con un caso de cada cosa: dos especies de un bono sano, la especie con el precio
# roto y su hermana buena, un CER imposible, un tasa fija enorme pero cierto, una acción y un bono
# cuyo tipo de tasa no se reconoce.
UNIVERSO: list[dict[str, Any]] = [
    {
        "ticker": "MR46O",
        "clase_activo": "bono_soberano",
        "tipo_tasa": "hard-dollar",
        "tir": 0.1310,
        "tna": None,
    },
    {
        "ticker": "MR46D",
        "clase_activo": "bono_soberano",
        "tipo_tasa": "hard-dollar",
        "tir": 0.1308,
        "tna": None,
    },
    {
        "ticker": "VSCQD",
        "clase_activo": "on_corporativo",
        "tipo_tasa": "hard-dollar",
        "tir": 346279.17,
        "tna": None,
    },
    {
        "ticker": "VSCQO",
        "clase_activo": "on_corporativo",
        "tipo_tasa": "hard-dollar",
        "tir": 0.0675,
        "tna": None,
    },
    {
        "ticker": "TXCER",
        "clase_activo": "bono_soberano",
        "tipo_tasa": "cer",
        "tir": 1.50,
        "tna": None,
    },
    {
        "ticker": "S30J6",
        "clase_activo": "bono_soberano",
        "tipo_tasa": "tasa-fija",
        "tir": 4.80,
        "tna": None,
    },
    {"ticker": "GGAL", "clase_activo": "accion", "tipo_tasa": None, "tir": None, "tna": None},
    {
        "ticker": "RAROO",
        "clase_activo": "on_corporativo",
        "tipo_tasa": "tasa-que-nadie-vio",
        "tir": 0.20,
        "tna": None,
    },
]


class FakeConexionLectura:
    """Conexión falsa con un universo fijo. Guarda el SQL para poder afirmar qué se leyó.

    Rutea la consulta del cronograma aparte: `/emisiones/especies` lee `public.cashflow` para
    derivar la periodicidad de cada emisión, y servirle el universo a esa consulta dejaría el campo
    siempre nulo — el test pasaría sin ejercitar nada.
    """

    def __init__(
        self, filas: list[dict[str, Any]], cashflow: list[dict[str, Any]] | None = None
    ) -> None:
        self.filas = filas
        self.cashflow = cashflow or []
        self.consultas: list[str] = []

    async def fetch(self, query: str, *_: Any) -> list[dict[str, Any]]:
        self.consultas.append(query)
        if "FROM public.cashflow" in query:
            return self.cashflow
        return self.filas


@pytest.fixture
def saneado():
    return sanear(segmentar(UNIVERSO), leidos=len(UNIVERSO))


# --- El universo saneado conserva lo que descarta ------------------------------------------------


def test_el_instrumento_descartado_sigue_en_el_universo(saneado) -> None:
    """Si desapareciera, nadie podría contestar por qué VSCQD no está. Lo que cambia es que no se
    propone, no que se borra."""
    assert "VSCQD" in {e.ticker for e in saneado.especies}
    assert "VSCQD" not in {e.ticker for e in saneado.operables()}


def test_operables_deja_afuera_lo_descartado_y_lo_que_no_tiene_rendimiento() -> None:
    universo = [
        {
            "ticker": "SINTIR",
            "clase_activo": "on_corporativo",
            "tipo_tasa": "hard-dollar",
            "tir": None,
            "tna": None,
        },
        {
            "ticker": "TXCER",
            "clase_activo": "bono_soberano",
            "tipo_tasa": "cer",
            "tir": 1.50,
            "tna": None,
        },
        {
            "ticker": "SNSBO",
            "clase_activo": "on_corporativo",
            "tipo_tasa": "hard-dollar",
            "tir": 2.455,
            "tna": None,
        },
    ]
    resultado = sanear(segmentar(universo), leidos=len(universo))
    assert [e.ticker for e in resultado.operables()] == ["SNSBO"]


# --- El resumen ---------------------------------------------------------------------------------


def test_el_resumen_separa_renta_variable_de_lo_que_no_se_pudo_segmentar(saneado) -> None:
    """Son dos cosas distintas: una acción nunca tuvo tasa, un bono sin tipo de tasa reconocido es
    un problema que hay que mirar."""
    resumen = saneado.resumen()
    assert resumen["renta_variable"] == 1
    assert resumen["sin_segmento"] == {"cantidad": 1, "muestra": ["RAROO"]}
    assert resumen["leidos"] == len(UNIVERSO)
    assert resumen["evaluados"] == 6


def test_el_resumen_abre_los_descartes_por_capa(saneado) -> None:
    assert saneado.resumen()["por_capa"] == {
        "especie_incoherente": 1,
        "rendimiento_fuera_de_rango": 1,
    }


def test_el_resumen_abre_los_conteos_por_segmento_con_su_unidad(saneado) -> None:
    """Seis descartes en CER y seis en tasa fija no son el mismo problema; el total los tapa."""
    por_segmento = {s["segmento"]: s for s in saneado.resumen()["por_segmento"]}
    assert por_segmento["cer"]["descartados"] == 1
    assert "CER" in por_segmento["cer"]["naturaleza"]
    assert por_segmento["tasa_fija"]["descartados"] == 0
    assert por_segmento["tasa_fija"]["naturaleza"] == "TIR efectiva anual en pesos"
    assert por_segmento["usd_hard"]["evaluados"] == 4


def test_como_dict_no_arrastra_la_coleccion_de_descartes(saneado) -> None:
    """El resumen contesta "¿sirve el universo de hoy?"; el listado es otro recurso, paginado."""
    payload = saneado.como_dict()
    assert set(payload) == {"resumen", "alertas"}
    codigos = [a["codigo"] for a in payload["alertas"]]
    assert codigos.count("especie_incoherente") == 1
    assert codigos.count("rendimiento_fuera_de_rango") == 1
    assert "descartes" not in payload


# --- Especies huérfanas (relevamiento de confiabilidad de datos, 16/08/2026) ---------------------

UNIVERSO_CON_HUERFANA: list[dict[str, Any]] = [
    {
        "ticker": "AL30O",
        "clase_activo": "bono_soberano",
        "tipo_tasa": "hard-dollar",
        "tir": 0.13,
        "tna": None,
        "capturado_en": "2026-08-16T11:30:00+00:00",
    },
    {
        "ticker": "VIEJOO",
        "clase_activo": "on_corporativo",
        "tipo_tasa": "hard-dollar",
        "tir": 0.10,
        "tna": None,
        "capturado_en": "2026-08-14T11:30:00+00:00",
    },
]


def test_una_huerfana_no_se_excluye_del_universo_ni_de_operables() -> None:
    """No se filtra, se declara: dejó de cotizar y sigue siendo auditable, mismo criterio que un
    descarte de sanidad."""
    saneado_huerfana = sanear(segmentar(UNIVERSO_CON_HUERFANA), leidos=len(UNIVERSO_CON_HUERFANA))

    assert saneado_huerfana.huerfanas == ["VIEJOO"]
    assert {e.ticker for e in saneado_huerfana.especies} == {"AL30O", "VIEJOO"}
    assert "VIEJOO" in {e.ticker for e in saneado_huerfana.operables()}


def test_una_huerfana_agrega_la_alerta_precio_desactualizado() -> None:
    saneado_huerfana = sanear(segmentar(UNIVERSO_CON_HUERFANA), leidos=len(UNIVERSO_CON_HUERFANA))

    alertas = {a.codigo: a for a in saneado_huerfana.alertas}
    assert "precio_desactualizado" in alertas
    assert alertas["precio_desactualizado"].detalle["tickers"] == ["VIEJOO"]
    assert saneado_huerfana.resumen()["huerfanas"] == 1


def test_sin_huerfanas_no_hay_alerta_de_precio_desactualizado(saneado) -> None:
    """`UNIVERSO` no trae `capturado_en` en ninguna fila: nada se marca por default."""
    assert saneado.huerfanas == []
    codigos = {a.codigo for a in saneado.alertas}
    assert "precio_desactualizado" not in codigos


# --- La lectura ---------------------------------------------------------------------------------


async def test_sanear_universo_lee_la_vista_resumen_entera() -> None:
    """La coherencia entre especies necesita ver todas las hermanas de una emisión a la vez: un
    universo traído de a pedazos daría un veredicto distinto por página."""
    conexion = FakeConexionLectura(UNIVERSO)
    resultado = await sanear_universo(conexion)

    (consulta,) = conexion.consultas
    assert "FROM public.resumen" in consulta
    assert "LIMIT" not in consulta.upper()
    assert resultado.leidos == len(UNIVERSO)
    assert resultado.sanidad.descartados == {"VSCQD", "TXCER"}


async def test_un_universo_vacio_no_rompe_ni_alerta() -> None:
    """Una base recién migrada devuelve cero filas y eso no es un error de sanidad.

    Lo que sí dice es que no hay tipo de cambio, y eso es distinto: sin especies no hay pares de
    los que derivarlo, así que la comparación de liquidez no está disponible. La sanidad no opina
    sobre un universo vacío; F-012 sí, porque su alerta habla de lo que no se puede hacer.
    """
    resultado = await sanear_universo(FakeConexionLectura([]))
    assert resultado.descartes == []
    assert resultado.sanidad.alertas == []
    assert [a.codigo for a in resultado.alertas] == ["tipo_de_cambio_sin_pares"]
    assert resultado.resumen()["evaluados"] == 0
