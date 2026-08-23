"""El endpoint de concentración — F-020, `POST /api/v1/concentracion`.

Lo que se prueba acá es el **contrato HTTP**: qué viaja, qué se rechaza y qué pasa sin base. La
matemática de los topes y la distribución ya está probada sin levantar nada en
`test_concentracion_servicio`, así que este archivo no la vuelve a recorrer.
"""

from typing import Any, get_args

import pytest

from app.api.v1.concentracion import MAX_POSICIONES, NombreDePerfil
from app.concentracion.perfiles import PERFILES, SOBERANO_AR
from tests.conftest import cliente

RUTA = "/api/v1/concentracion"

# Un universo chico con lo que hace falta para que la respuesta tenga los tres tipos de tope: dos
# emisiones del Tesoro bajo prefijos distintos, dos ONs del mismo emisor y una de otro sector.
FILAS_UNIVERSO: list[dict[str, Any]] = [
    {"ticker": "GD30", "clase_activo": "bono_soberano", "tipo_tasa": "hard-dollar", "tir": 0.10,
     "sector": "Soberano", "law": "Ley N.Y.", "lastPrice": 70.0, "moneda_cotizacion": "USD"},
    {"ticker": "AE38", "clase_activo": "bono_soberano", "tipo_tasa": "hard-dollar", "tir": 0.11,
     "sector": "Soberano", "law": "Ley Argentina", "lastPrice": 65.0, "moneda_cotizacion": "USD"},
    {"ticker": "YMCHO", "clase_activo": "on_corporativo", "tipo_tasa": "hard-dollar", "tir": 0.08,
     "sector": "O&G", "underlying": "YPF S.A.", "law": "Ley N.Y.", "lastPrice": 99.0,
     "moneda_cotizacion": "USD"},
    {"ticker": "YMCIO", "clase_activo": "on_corporativo", "tipo_tasa": "hard-dollar", "tir": 0.08,
     "sector": "O&G", "underlying": "YPF S.A.", "law": "Ley N.Y.", "lastPrice": 98.0,
     "moneda_cotizacion": "USD"},
    {"ticker": "BNCAO", "clase_activo": "on_corporativo", "tipo_tasa": "badlar", "tna": 0.40,
     "sector": "Financiera", "underlying": "Banco Ejemplo", "lastPrice": 101.0,
     "moneda_cotizacion": "ARS"},
]


class FakeConexionConcentracion:
    """Conexión falsa con una sola consulta: este endpoint lee el universo y nada más.

    Que sólo haya una es parte del contrato y no un detalle del fake: la evaluación es pura, así
    que si algún día apareciera una segunda consulta acá, sería porque el cálculo dejó de serlo.
    """

    def __init__(self, universo: list[dict[str, Any]] | None = None) -> None:
        self.universo = FILAS_UNIVERSO if universo is None else universo
        self.consultas: list[str] = []

    async def fetch(self, query: str, *_: Any) -> list[dict[str, Any]]:
        self.consultas.append(query)
        return self.universo


@pytest.fixture
def app_con_universo(crear_app):
    def _crear(**kwargs):
        return crear_app(FakeConexionConcentracion(**kwargs))

    return _crear


def cuerpo_con(*posiciones: tuple[str, float]) -> dict[str, Any]:
    return {"posiciones": [{"ticker": t, "peso": p} for t, p in posiciones]}


async def test_devuelve_los_tres_tipos_de_tope_con_su_estado(app_con_universo) -> None:
    async with cliente(app_con_universo()) as http:
        pedido = cuerpo_con(("GD30", 40), ("YMCHO", 30), ("BNCAO", 30))
        respuesta = await http.post(RUTA, json=pedido)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    tipos = {tope["tipo"] for tope in cuerpo["topes"]}
    assert tipos == {"soberano", "emisor", "sector"}
    assert {"sector", "ley", "naturaleza"} == set(cuerpo["distribucion"])


async def test_el_perfil_por_defecto_es_moderado(app_con_universo) -> None:
    async with cliente(app_con_universo()) as http:
        cuerpo = (await http.post(RUTA, json=cuerpo_con(("GD30", 100)))).json()

    assert cuerpo["perfil"] == "moderado"
    assert cuerpo["limites"] == PERFILES["moderado"]


async def test_el_perfil_cambia_el_veredicto_sobre_la_misma_cartera(app_con_universo) -> None:
    """Un 60 % soberano pasa el tope del conservador (50 %) y no el del moderado (65 %)."""
    async with cliente(app_con_universo()) as http:
        pedido = cuerpo_con(("GD30", 60), ("YMCHO", 15), ("BNCAO", 25))
        moderado = (await http.post(RUTA, json=pedido, params={"perfil": "moderado"})).json()
        conservador = (await http.post(RUTA, json=pedido, params={"perfil": "conservador"})).json()

    soberano = next(t for t in moderado["topes"] if t["clave"] == SOBERANO_AR)
    assert soberano["excedido"] is False
    soberano = next(t for t in conservador["topes"] if t["clave"] == SOBERANO_AR)
    assert soberano["excedido"] is True


async def test_un_tope_excedido_responde_200_porque_informa_y_no_bloquea(app_con_universo) -> None:
    """La ficha: 'la advertencia no bloquea: informa'. Un 4xx obligaría al frontend a tratar como
    falla del pedido lo que es el resultado de la medición."""
    async with cliente(app_con_universo()) as http:
        respuesta = await http.post(RUTA, json=cuerpo_con(("GD30", 90), ("YMCHO", 10)))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["excedidos"] > 0
    assert all(alerta["accion_requerida"] is None for alerta in cuerpo["alertas"])


async def test_un_perfil_inventado_se_rechaza_en_la_validacion(app_con_universo) -> None:
    async with cliente(app_con_universo()) as http:
        pedido = cuerpo_con(("GD30", 100))
        respuesta = await http.post(RUTA, json=pedido, params={"perfil": "prudente"})

    assert respuesta.status_code == 422


def test_la_lista_de_perfiles_del_endpoint_es_la_de_los_perfiles() -> None:
    """El `Literal` del endpoint y las claves de `PERFILES` tienen que ser lo mismo: un perfil
    agregado en un solo lado sería un 422 sobre un perfil que existe."""
    assert set(get_args(NombreDePerfil)) == set(PERFILES)


async def test_una_cartera_vacia_se_rechaza(app_con_universo) -> None:
    async with cliente(app_con_universo()) as http:
        respuesta = await http.post(RUTA, json={"posiciones": []})

    assert respuesta.status_code == 422


async def test_una_cartera_mas_larga_que_el_maximo_se_rechaza(app_con_universo) -> None:
    demasiadas = [("GD30", 1.0)] * (MAX_POSICIONES + 1)
    async with cliente(app_con_universo()) as http:
        respuesta = await http.post(RUTA, json=cuerpo_con(*demasiadas))

    assert respuesta.status_code == 422


async def test_un_peso_negativo_se_rechaza(app_con_universo) -> None:
    """Cero sí se acepta —una posición todavía sin ponderar es un estado legítimo del armador—,
    pero un peso negativo no es una cartera: restaría concentración."""
    async with cliente(app_con_universo()) as http:
        assert (await http.post(RUTA, json=cuerpo_con(("GD30", 0)))).status_code == 200
        assert (await http.post(RUTA, json=cuerpo_con(("GD30", -10)))).status_code == 422


async def test_las_posiciones_fuera_del_universo_viajan_nombradas(app_con_universo) -> None:
    async with cliente(app_con_universo()) as http:
        cuerpo = (await http.post(RUTA, json=cuerpo_con(("GD30", 70), ("FCIALGO", 30)))).json()

    assert cuerpo["fuera_del_universo"] == ["FCIALGO"]
    assert cuerpo["peso"] == {"declarado": 100.0, "medido": 70.0}


async def test_sin_base_de_datos_responde_503(crear_app) -> None:
    async with cliente(crear_app(None)) as http:
        respuesta = await http.post(RUTA, json=cuerpo_con(("GD30", 100)))

    assert respuesta.status_code == 503


async def test_el_endpoint_hace_una_sola_consulta(crear_app) -> None:
    """La evaluación es pura: lo único que sale a la base es el universo."""
    conexion = FakeConexionConcentracion()
    async with cliente(crear_app(conexion)) as http:
        await http.post(RUTA, json=cuerpo_con(("GD30", 100)))

    assert len(conexion.consultas) == 1


# --- F-046: un FCI valuado entra al peso medido, nunca a un tope ----------------------------------


async def test_un_fci_valuado_entra_al_peso_medido_y_no_a_fuera_del_universo(app_con_universo) -> None:
    async with cliente(app_con_universo()) as http:
        pedido = {
            "posiciones": [
                {"ticker": "GD30", "peso": 70},
                {"ticker": "Fondo Renta Fija Ejemplo", "peso": 30, "es_fci": True},
            ]
        }
        cuerpo = (await http.post(RUTA, json=pedido)).json()

    assert cuerpo["peso"] == {"declarado": 100.0, "medido": 100.0}
    assert cuerpo["fuera_del_universo"] == []
    assert cuerpo["fci"] == ["Fondo Renta Fija Ejemplo"]
    assert "exposicion_fci_no_atribuible" in {a["codigo"] for a in cuerpo["alertas"]}


async def test_el_nombre_de_un_fondo_no_se_corta_por_el_limite_de_un_ticker(app_con_universo) -> None:
    """Un ticker de renta fija mide hasta 6 caracteres; un fondo de `public.fci` llega a 88
    (medido el 23/08/2026). El límite tiene que cubrir el nombre real, no sólo el ticker."""
    nombre_largo = "BAVSA Renta Balanceado IX - Clase A de Suscripción Inicial Ejemplo"
    assert len(nombre_largo) > 20
    async with cliente(app_con_universo()) as http:
        pedido = {"posiciones": [{"ticker": nombre_largo, "peso": 100, "es_fci": True}]}
        respuesta = await http.post(RUTA, json=pedido)

    assert respuesta.status_code == 200
    assert respuesta.json()["fci"] == [nombre_largo]
