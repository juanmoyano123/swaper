"""El andamiaje que comparten las tres fuentes.

Lo que se prueba acá no es una feature: son las decisiones que las tres tienen que respetar por
igual, y que si se rompen se rompen en silencio. Que un cero no se confunda con un dato faltante,
que una credencial vencida no se reintente cinco veces, y que una respuesta vacía sí.
"""

import httpx
import pytest

from app.ingesta.alertas import Alerta, Severidad, credencial_vencida, fuente_caida
from app.ingesta.cobertura import medir_cobertura
from app.ingesta.http import (
    CredencialVencida,
    ErrorDeFuente,
    Reintentos,
    con_reintentos,
    pedir,
)
from app.ingesta.snapshot import Snapshot

# --- Alertas: lo que las distingue es qué hay que hacer ----------------------------------------


def test_una_credencial_vencida_dice_como_renovarla() -> None:
    alerta = credencial_vencida("Docta", "Regenerar el link en Docta Terminal y actualizar .env")

    assert alerta.severidad is Severidad.ERROR
    assert alerta.accion_requerida, "sin acción, nadie sabe que hay que ir a regenerar el token"


def test_una_fuente_caida_no_pide_accion_humana() -> None:
    """Es la contracara: esperar es la respuesta correcta, y pedir una acción confundiría."""
    alerta = fuente_caida("BYMA", "timeout")

    assert alerta.severidad is Severidad.ERROR
    assert alerta.accion_requerida is None


def test_las_dos_situaciones_tienen_codigos_distintos() -> None:
    """El código es lo que permite contarlas y filtrarlas por separado más adelante."""
    assert credencial_vencida("Docta", "x").codigo != fuente_caida("Docta", "y").codigo


def test_la_alerta_se_serializa_entera() -> None:
    alerta = Alerta(codigo="x", mensaje="m", accion_requerida="a", detalle={"endpoint": "bonos"})
    d = alerta.como_dict()

    assert d["codigo"] == "x"
    assert d["accion_requerida"] == "a"
    assert d["detalle"] == {"endpoint": "bonos"}


# --- Cobertura: cero no es lo mismo que sin dato ------------------------------------------------


def test_un_cero_cuenta_como_dato_presente() -> None:
    """Un bono que no operó tiene volumen cero. Contarlo como faltante lo escondería."""
    filas = [{"volumen": 0}, {"volumen": 0.0}, {"volumen": 150}]

    (cobertura,) = medir_cobertura(filas, ["volumen"])

    assert cobertura.presentes == 3
    assert cobertura.faltantes == 0


def test_vacio_nulo_y_nan_cuentan_como_faltantes() -> None:
    filas = [{"tir": None}, {"tir": float("nan")}, {"tir": ""}, {"tir": "   "}, {"tir": 7.2}]

    (cobertura,) = medir_cobertura(filas, ["tir"])

    assert cobertura.presentes == 1
    assert cobertura.faltantes == 4
    assert cobertura.porcentaje == 20.0


def test_un_campo_que_ninguna_fila_trae_reporta_cero_de_n() -> None:
    """Es el caso que importa: si el campo se dedujera de los datos, este campo no aparecería."""
    filas = [{"ticker": "AL30"}, {"ticker": "GD30"}]

    (cobertura,) = medir_cobertura(filas, ["calificacion"])

    assert cobertura.presentes == 0
    assert cobertura.total == 2


def test_sin_filas_la_cobertura_es_cero_y_no_cien() -> None:
    """Ninguna fila no significa cobertura perfecta; significa que no hay nada que reportar."""
    (cobertura,) = medir_cobertura([], ["tir"])

    assert cobertura.total == 0
    assert cobertura.porcentaje == 0.0


# --- Snapshot ----------------------------------------------------------------------------------


def test_el_snapshot_descuenta_la_demora_declarada() -> None:
    """Un precio con veinte minutos de atraso presentado como actual es un dato mal rotulado."""
    snapshot = Snapshot(fuente="BYMA", demora_declarada_minutos=20)

    diferencia = snapshot.capturado_en - snapshot.dato_valido_hasta

    assert diferencia.total_seconds() == 20 * 60


def test_una_corrida_con_errores_no_esta_completa() -> None:
    snapshot = Snapshot(fuente="BYMA")
    snapshot.registrar_tramo("public-bonds", 1106)
    assert snapshot.completo

    snapshot.alertar(fuente_caida("BYMA", "timeout"))
    assert not snapshot.completo


def test_una_corrida_sin_filas_tampoco_esta_completa() -> None:
    assert not Snapshot(fuente="BYMA").completo


def test_el_conteo_por_tramo_permite_ver_lo_que_falta() -> None:
    """Es lo que delata una página que no se pidió: el total no cierra contra el de la fuente."""
    snapshot = Snapshot(fuente="BYMA")
    snapshot.registrar_tramo("public-bonds", 1106)
    snapshot.registrar_tramo("cedears", 2107)

    assert snapshot.total_filas == 3213
    assert snapshot.como_dict()["filas_por_tramo"] == {"public-bonds": 1106, "cedears": 2107}


# --- Reintentos --------------------------------------------------------------------------------


async def test_una_respuesta_vacia_se_reintenta_y_termina_saliendo_bien() -> None:
    """El caso medido: la consulta que devuelve cero filas trae datos segundos después."""
    intentos = {"n": 0}

    async def operacion() -> str:
        intentos["n"] += 1
        if intentos["n"] < 3:
            raise ErrorDeFuente("la fuente devolvió cero filas")
        return "datos"

    async def no_dormir(_: float) -> None:
        return None

    resultado = await con_reintentos(operacion, descripcion="prueba", dormir=no_dormir)

    assert resultado == "datos"
    assert intentos["n"] == 3


async def test_una_credencial_vencida_no_se_reintenta() -> None:
    """Ninguna cantidad de intentos va a arreglar un token vencido: sólo demora el aviso."""
    intentos = {"n": 0}

    async def operacion() -> str:
        intentos["n"] += 1
        raise CredencialVencida("token vencido")

    async def no_dormir(_: float) -> None:
        return None

    with pytest.raises(CredencialVencida):
        await con_reintentos(operacion, descripcion="prueba", dormir=no_dormir)

    assert intentos["n"] == 1, "se reintentó algo que no se puede arreglar reintentando"


async def test_se_agotan_los_intentos_y_falla_con_el_ultimo_motivo() -> None:
    async def operacion() -> str:
        raise ErrorDeFuente("la fuente devolvió cero filas")

    async def no_dormir(_: float) -> None:
        return None

    with pytest.raises(ErrorDeFuente, match="5 intentos"):
        await con_reintentos(operacion, descripcion="prueba", dormir=no_dormir)


def test_la_espera_crece_entre_intentos() -> None:
    """Reintentar de inmediato contra un endpoint que se recupera lo vuelve a tumbar."""
    politica = Reintentos()

    esperas = [politica.espera(i) for i in range(1, 5)]

    assert esperas == [3, 6, 9, 12]


# --- Traducción de respuestas HTTP -------------------------------------------------------------


async def _responder(status: int, cuerpo: bytes = b"") -> httpx.Response:
    transporte = httpx.MockTransport(lambda _: httpx.Response(status, content=cuerpo))
    async with httpx.AsyncClient(transport=transporte) as cliente:
        return await pedir(cliente, "GET", "https://fuente.test/x", fuente="Prueba")


async def test_un_500_que_menciona_el_token_es_credencial_vencida() -> None:
    """La fuente de cashflow responde 500, no 401, cuando el token venció. Está verificado."""
    with pytest.raises(CredencialVencida):
        await _responder(500, b"Error al verificar el token")


async def test_un_500_cualquiera_es_una_caida_reintentable() -> None:
    with pytest.raises(ErrorDeFuente) as exc:
        await _responder(500, b"Internal Server Error")

    assert not isinstance(exc.value, CredencialVencida)
    assert exc.value.reintentable


async def test_un_401_es_credencial_vencida() -> None:
    with pytest.raises(CredencialVencida):
        await _responder(401)


async def test_un_404_no_se_reintenta() -> None:
    """Un pedido mal armado da siempre lo mismo: reintentarlo sólo demora el error."""
    with pytest.raises(ErrorDeFuente) as exc:
        await _responder(404)

    assert not exc.value.reintentable


async def test_un_timeout_se_traduce_a_error_de_fuente() -> None:
    def caer(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("tardó demasiado")

    async with httpx.AsyncClient(transport=httpx.MockTransport(caer)) as cliente:
        with pytest.raises(ErrorDeFuente, match="timeout"):
            await pedir(cliente, "GET", "https://fuente.test/x", fuente="Prueba")


async def test_una_respuesta_vacia_puede_declararse_fallo() -> None:
    """Cada fuente decide qué es "vacío"; la política de reintento es la misma para todas."""
    transporte = httpx.MockTransport(lambda _: httpx.Response(200, json=[]))

    async with httpx.AsyncClient(transport=transporte) as cliente:
        with pytest.raises(ErrorDeFuente, match="cero filas"):
            await pedir(
                cliente,
                "GET",
                "https://fuente.test/x",
                fuente="Prueba",
                vacio_es_fallo=lambda r: r.json() == [],
            )
