"""El cliente de la ficha técnica de BYMA: qué transporta, qué no traduce y cómo falla.

Todo con `respx`. Los cuerpos son recortes de respuestas reales verificadas en vivo el 28/08/2026
—AL30 y YMCXO— y no shapes inventados: la forma de `{"content":…,"data":[…],"empty":…}` y el hecho
de que los campos que la fuente no declara vengan como cadena vacía y no como `null` son los dos
detalles que este cliente tiene que absorber.
"""

import asyncio

import pytest
import respx
from httpx import Response

from app.externos.byma_ficha import URL_FICHA, FichaEspecie, traer_ficha, traer_fichas
from app.ingesta.http import ErrorDeFuente, crear_cliente

# Recorte de la ficha real de AL30. Se conservan sólo los campos que el cliente lee más `paisLey`,
# que existe en la fuente y a propósito no se lee.
FICHA_AL30 = {
    "emisor": "Gobierno Nacional",
    "ley": "Nacional",
    "paisLey": "",
    "denominacion": "BONOS DE LA REPÚBLICA ARGENTINA EN DÓLARES ESTADOUNIDENSES STEP UP 2030",
    "codigoIsin": "ARARGE3209S6",
}

# La de YMCXO: una ON con emisor y sin ley. Es el caso mayoritario (724 de 915 medidas).
FICHA_YMCXO = {
    "emisor": "YPF S.A.",
    "ley": "",
    "denominacion": "Clase XXXI",
}


async def _no_esperar(_segundos: float) -> None:
    """La escalera de reintentos de `con_reintentos` son 30 segundos reales. Acá no se esperan."""


def _respuesta(fila: dict | None) -> Response:
    if fila is None:
        return Response(200, json={"content": {}, "data": [], "empty": True})
    return Response(200, json={"content": {}, "data": [fila], "empty": False})


# --- Lo que se transporta ------------------------------------------------------------------------


@respx.mock
async def test_normaliza_la_ficha_tal_cual_la_declara_la_fuente() -> None:
    respx.post(URL_FICHA).mock(return_value=_respuesta(FICHA_AL30))

    async with crear_cliente() as cliente:
        ficha = await traer_ficha(cliente, "AL30")

    assert ficha == FichaEspecie(
        ticker="AL30",
        emisor="Gobierno Nacional",
        ley_cruda="Nacional",
        denominacion=(
            "BONOS DE LA REPÚBLICA ARGENTINA EN DÓLARES ESTADOUNIDENSES STEP UP 2030"
        ),
    )


@respx.mock
async def test_la_ley_viaja_sin_traducir() -> None:
    """`'Extranjera'` no es ninguno de los dos valores que acepta la columna `law`, y el cliente no
    es quien decide qué hacer con eso: lo entrega tal cual para que la traducción viva donde está su
    evidencia (`app/instrumentos/emisores.py`)."""
    respx.post(URL_FICHA).mock(return_value=_respuesta({**FICHA_AL30, "ley": "Extranjera"}))

    async with crear_cliente() as cliente:
        ficha = await traer_ficha(cliente, "GD30")

    assert ficha is not None
    assert ficha.ley_cruda == "Extranjera"


@respx.mock
async def test_la_cadena_vacia_de_la_fuente_llega_como_faltante() -> None:
    """La ficha usa `''` y no `null` para lo que no declara. Hacia adentro son lo mismo."""
    respx.post(URL_FICHA).mock(return_value=_respuesta(FICHA_YMCXO))

    async with crear_cliente() as cliente:
        ficha = await traer_ficha(cliente, "YMCXO")

    assert ficha is not None
    assert ficha.emisor == "YPF S.A."
    assert ficha.ley_cruda is None


# --- Cuando no hay ficha -------------------------------------------------------------------------


@respx.mock
async def test_sin_ficha_devuelve_none_sin_reintentar() -> None:
    """`data: []` es una respuesta legítima —TY36O no tiene ficha— y no un fallo de la fuente.

    El conteo de llamadas es la mitad importante del test: tratarlo como vacío-reintentable, que es
    lo que hacen los paneles de cotizaciones, multiplicaría por cinco el barrido para llegar a la
    misma respuesta.
    """
    ruta = respx.post(URL_FICHA).mock(return_value=_respuesta(None))

    async with crear_cliente() as cliente:
        ficha = await traer_ficha(cliente, "TY36O")

    assert ficha is None
    assert ruta.call_count == 1


@respx.mock
async def test_un_200_que_no_es_json_no_se_adivina() -> None:
    respx.post(URL_FICHA).mock(return_value=Response(200, text="<html>mantenimiento</html>"))

    async with crear_cliente() as cliente:
        assert await traer_ficha(cliente, "AL30") is None


@respx.mock
async def test_un_fallo_de_la_fuente_se_propaga() -> None:
    """La diferencia entre "BYMA no lo publica" y "BYMA no contestó" es la que impide que un corte
    de red se persista como un faltante definitivo."""
    respx.post(URL_FICHA).mock(return_value=Response(500))

    async with crear_cliente() as cliente:
        with pytest.raises(ErrorDeFuente):
            await traer_ficha(cliente, "AL30", dormir=_no_esperar)


@respx.mock
async def test_la_especie_que_fallo_no_aparece_en_el_dict() -> None:
    """Ausente del dict = no se le pudo preguntar. Es lo que hace que el job no la marque como
    consultada y vuelva a intentarlo en la corrida siguiente."""

    def responder(request):
        cuerpo = request.read().decode()
        if "ROTA" in cuerpo:
            return Response(500)
        return _respuesta(FICHA_YMCXO)

    respx.post(URL_FICHA).mock(side_effect=responder)

    async with crear_cliente() as cliente:
        fichas = await traer_fichas(["YMCXO", "ROTA"], cliente=cliente, dormir=_no_esperar)

    assert "ROTA" not in fichas
    assert fichas["YMCXO"] is not None


# --- La concurrencia -----------------------------------------------------------------------------


@respx.mock
async def test_el_semaforo_limita_los_pedidos_en_vuelo() -> None:
    """Sin el semáforo, `gather` largaría los 4.000 símbolos del universo de una sola vez."""
    en_vuelo = 0
    pico = 0

    async def responder(request):
        nonlocal en_vuelo, pico
        en_vuelo += 1
        pico = max(pico, en_vuelo)
        # Cede el control para que los demás pedidos puedan entrar si el semáforo los deja.
        await asyncio.sleep(0)
        en_vuelo -= 1
        return _respuesta(FICHA_YMCXO)

    respx.post(URL_FICHA).mock(side_effect=responder)

    async with crear_cliente() as cliente:
        fichas = await traer_fichas(
            [f"T{i:03d}" for i in range(20)], concurrencia=3, cliente=cliente
        )

    assert len(fichas) == 20
    assert pico <= 3


async def test_sin_simbolos_no_le_pega_a_la_fuente() -> None:
    assert await traer_fichas([]) == {}
