"""El endpoint de rotaciones — F-032, `POST /api/v1/rotaciones`.

Lo que se prueba acá es el **contrato HTTP**: qué viaja, qué se rechaza y qué pasa sin base. El
motor puro ya está probado sin levantar nada en `test_rotaciones_motor.py`, así que este archivo
no vuelve a recorrer su lógica.
"""

from typing import Any

import pytest

from app.api.v1.rotaciones import MAX_POSICIONES, NombreDePerfil
from app.concentracion.perfiles import PERFILES
from tests.conftest import cliente

RUTA = "/api/v1/rotaciones"

# Un universo chico con un par de segmentos y el caso TLCWO/TLCMO, para que la respuesta traiga
# al menos una candidata sin depender del consolidado real.
FILAS_UNIVERSO: list[dict[str, Any]] = [
    {
        "ticker": "TLCWO",
        "clase_activo": "on_corporativo",
        "tipo_tasa": "hard-dollar",
        "tir": 0.095,
        "duration": 2.5,
        "law": "Ley N.Y.",
        "couponCurrency": "MEP",
        "lastPrice": 80.0,
        "moneda_cotizacion": "ARS",
        "effectiveVolume": 500_000.0,
    },
    {
        "ticker": "TLCMO",
        "clase_activo": "on_corporativo",
        "tipo_tasa": "hard-dollar",
        "tir": 0.097,
        "duration": 2.5,
        "law": "Ley N.Y.",
        "couponCurrency": "CCL",
        "lastPrice": 79.0,
        "moneda_cotizacion": "USD",
        "effectiveVolume": 1_600_000.0,
    },
    {
        "ticker": "GD30",
        "clase_activo": "bono_soberano",
        "tipo_tasa": "hard-dollar",
        "tir": 0.10,
        "duration": 4.0,
        "law": "Ley Argentina",
        "couponCurrency": "ARS",
        "lastPrice": 70.0,
        "moneda_cotizacion": "ARS",
        "effectiveVolume": 900_000.0,
    },
]


class FakeConexionRotaciones:
    """Conexión falsa con las cuatro consultas que hace el servicio: universo, cashflow,
    paridades y puntas. Sin cashflow ni paridad el motor sigue andando (frecuencia/cupón quedan
    vacíos), y sin puntas ninguna candidata tiene costo verificable — por defecto las tres vienen
    vacías y sólo el universo trae filas."""

    def __init__(
        self,
        universo: list[dict[str, Any]] | None = None,
        cashflow: list[dict[str, Any]] | None = None,
        paridades: list[dict[str, Any]] | None = None,
        puntas: list[dict[str, Any]] | None = None,
    ) -> None:
        self.universo = FILAS_UNIVERSO if universo is None else universo
        self.cashflow = cashflow or []
        self.paridades = paridades or []
        self.puntas = puntas or []
        self.consultas: list[str] = []

    async def fetch(self, query: str, *_: Any) -> list[dict[str, Any]]:
        self.consultas.append(query)
        if "public.cashflow" in query:
            return self.cashflow
        if "public.puntas" in query:
            return self.puntas
        # La query de paridades pide sólo dos columnas ("SELECT ticker, paridad FROM ..."); la
        # del universo también toca `public.resumen` pero con la lista completa de columnas
        # entrecomilladas (`u."paridad"` entre otras), así que "SELECT ticker, paridad" alcanza
        # para distinguir una de la otra sin ambigüedad.
        if query.startswith("SELECT ticker, paridad"):
            return self.paridades
        return self.universo


@pytest.fixture
def app_con_universo(crear_app):
    def _crear(**kwargs):
        return crear_app(FakeConexionRotaciones(**kwargs))

    return _crear


def cuerpo_con(*tickers: str) -> dict[str, Any]:
    return {"posiciones": [{"ticker": t} for t in tickers]}


async def test_devuelve_200_con_al_menos_una_candidata_hacia_tlcmo(app_con_universo) -> None:
    async with cliente(app_con_universo()) as http:
        respuesta = await http.post(RUTA, json=cuerpo_con("TLCWO"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    destinos = {c["destino"]["ticker"] for c in cuerpo["candidatas"]}
    assert "TLCMO" in destinos


async def test_el_perfil_por_defecto_es_moderado(app_con_universo) -> None:
    async with cliente(app_con_universo()) as http:
        cuerpo = (await http.post(RUTA, json=cuerpo_con("TLCWO"))).json()

    assert cuerpo["perfil"] == "moderado"
    assert cuerpo["parametros"]["percentil_liquidez"] == PERFILES["moderado"]["percentil_liquidez"]


async def test_devuelve_200_incluso_sin_candidatas(app_con_universo) -> None:
    """Una cartera sin ninguna alternativa dentro de su segmento es un resultado válido, no un
    error del pedido."""
    async with cliente(app_con_universo()) as http:
        respuesta = await http.post(RUTA, json=cuerpo_con("GD30"))

    assert respuesta.status_code == 200
    assert respuesta.json()["candidatas"] == []


async def test_la_alerta_vieja_de_costo_no_calculado_ya_no_aparece_nunca(app_con_universo) -> None:
    """F-035 cierra el pendiente que dejaba F-032: ya no hay una candidata sin bloque de costo."""
    async with cliente(app_con_universo()) as http:
        con_candidatas = (await http.post(RUTA, json=cuerpo_con("TLCWO"))).json()
        sin_candidatas = (await http.post(RUTA, json=cuerpo_con("GD30"))).json()

    for cuerpo in (con_candidatas, sin_candidatas):
        codigos = {a["codigo"] for a in cuerpo["alertas"]}
        assert "costo_rotacion_no_calculado" not in codigos

    for candidata in con_candidatas["candidatas"]:
        assert "costo" in candidata


async def test_candidata_con_puntas_en_las_dos_patas_trae_costo_verificable(
    app_con_universo,
) -> None:
    # Puntas para las tres especies del universo: TLCWO también puede rotar hacia GD30 (mismo
    # segmento usd_hard, distinta categoría de crédito), y esa candidata no debe quedar sin punta.
    puntas = [
        {"ticker": "TLCWO", "px_bid": 79.0, "px_ask": 81.0, "fuente": "byma"},
        {"ticker": "TLCMO", "px_bid": 78.0, "px_ask": 80.0, "fuente": "byma"},
        {"ticker": "GD30", "px_bid": 69.0, "px_ask": 71.0, "fuente": "byma"},
    ]
    async with cliente(app_con_universo(puntas=puntas)) as http:
        cuerpo = (await http.post(RUTA, json=cuerpo_con("TLCWO"))).json()

    candidata = next(c for c in cuerpo["candidatas"] if c["destino"]["ticker"] == "TLCMO")
    costo = candidata["costo"]
    assert costo["verificable"] is True
    assert costo["total_pct"] is not None
    assert costo["spread_origen_pct"] is not None
    assert costo["spread_destino_pct"] is not None

    codigos = {a["codigo"] for a in cuerpo["alertas"]}
    assert "costo_no_verificable" not in codigos


async def test_candidata_sin_puntas_queda_no_verificable_con_alerta(app_con_universo) -> None:
    async with cliente(app_con_universo(puntas=[])) as http:
        cuerpo = (await http.post(RUTA, json=cuerpo_con("TLCWO"))).json()

    candidata = next(c for c in cuerpo["candidatas"] if c["destino"]["ticker"] == "TLCMO")
    costo = candidata["costo"]
    assert costo["verificable"] is False
    assert costo["total_pct"] is None
    assert costo["elevado"] is None
    assert costo["payback_meses"] is None

    codigos = {a["codigo"] for a in cuerpo["alertas"]}
    assert "costo_no_verificable" in codigos


async def test_puntas_de_arrastre_se_tratan_como_sin_punta(app_con_universo) -> None:
    puntas = [
        {"ticker": "TLCWO", "px_bid": 79.0, "px_ask": 81.0, "fuente": "byma-arrastre"},
        {"ticker": "TLCMO", "px_bid": 78.0, "px_ask": 80.0, "fuente": "byma"},
    ]
    async with cliente(app_con_universo(puntas=puntas)) as http:
        cuerpo = (await http.post(RUTA, json=cuerpo_con("TLCWO"))).json()

    candidata = next(c for c in cuerpo["candidatas"] if c["destino"]["ticker"] == "TLCMO")
    assert candidata["costo"]["verificable"] is False


async def test_un_perfil_inventado_se_rechaza_en_la_validacion(app_con_universo) -> None:
    async with cliente(app_con_universo()) as http:
        respuesta = await http.post(RUTA, json=cuerpo_con("TLCWO"), params={"perfil": "prudente"})

    assert respuesta.status_code == 422


def test_la_lista_de_perfiles_del_endpoint_es_la_de_los_perfiles() -> None:
    from typing import get_args

    assert set(get_args(NombreDePerfil)) == set(PERFILES)


async def test_una_cartera_vacia_se_rechaza(app_con_universo) -> None:
    async with cliente(app_con_universo()) as http:
        respuesta = await http.post(RUTA, json={"posiciones": []})

    assert respuesta.status_code == 422


async def test_una_cartera_mas_larga_que_el_maximo_se_rechaza(app_con_universo) -> None:
    demasiadas = [f"T{i}" for i in range(MAX_POSICIONES + 1)]
    async with cliente(app_con_universo()) as http:
        respuesta = await http.post(RUTA, json=cuerpo_con(*demasiadas))

    assert respuesta.status_code == 422


async def test_ticker_fuera_del_universo_viaja_nombrado(app_con_universo) -> None:
    async with cliente(app_con_universo()) as http:
        cuerpo = (await http.post(RUTA, json=cuerpo_con("TLCWO", "FCIALGO"))).json()

    assert cuerpo["fuera_del_universo"] == ["FCIALGO"]
    assert "TLCWO" in cuerpo["origenes_evaluados"]


async def test_sin_base_de_datos_responde_503(crear_app) -> None:
    async with cliente(crear_app(None)) as http:
        respuesta = await http.post(RUTA, json=cuerpo_con("TLCWO"))

    assert respuesta.status_code == 503


async def test_la_forma_del_contrato_trae_todas_las_claves_documentadas(app_con_universo) -> None:
    async with cliente(app_con_universo()) as http:
        cuerpo = (await http.post(RUTA, json=cuerpo_con("TLCWO"))).json()

    assert set(cuerpo) == {
        "perfil",
        "parametros",
        "candidatas",
        "origenes_evaluados",
        "fuera_del_universo",
        "sin_rendimiento",
        "premio_legislacion",
        "sensibilidad",
        "alertas",
    }
    assert set(cuerpo["premio_legislacion"]) == {"pares", "medianas_bps"}

    candidata = cuerpo["candidatas"][0]
    assert set(candidata) == {
        "tipo",
        "segmento",
        "origen",
        "destino",
        "delta",
        "flags",
        "premio_ley",
        "riesgo_nota",
        "cupon",
        "costo",
    }
    assert set(candidata["costo"]) == {
        "arancel_pct_por_pata",
        "spread_origen_pct",
        "spread_destino_pct",
        "total_pct",
        "verificable",
        "elevado",
        "payback_meses",
    }
    assert set(candidata["origen"]) == {
        "ticker",
        "emisor",
        "rendimiento",
        "duracion",
        "moneda_cupon",
        "ley",
        "calificacion",
        "lamina",
        "frecuencia_cupon",
        "volumen_usd",
    }
