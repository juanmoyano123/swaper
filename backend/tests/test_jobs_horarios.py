"""Cálculo de horarios del scheduler: puro, sin reloj real.

Todos los horarios salen de `settings_de_prueba` y son **valores de prueba, no la configuración de
producción**: acá se prueba la aritmética del scheduler, y por eso el fixture los fija en vez de
leer los defaults. Se conserva el 09:00 histórico justamente para que estos tests no se muevan
cuando cambie la hora real —hoy 11:30, ver el porqué en `app/core/config.py`—.

La versión anterior de este docstring decía que la ventana la documentaba `product-definition.md`.
No es así: ninguna spec del proyecto fija una hora, el plan sólo habla de "la corrida matinal
programada". La hora fue una decisión de implementación, y conviene que se lea como tal.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.core.config import get_settings
from app.jobs.horarios import en_ventana_de_rueda, es_dia_habil, proxima_matinal, proximo_refresh

TZ = ZoneInfo("America/Argentina/Buenos_Aires")

# Los tests de aritmética horaria usan el jueves 06/08/2026 y el viernes 07/08 a propósito: son
# días hábiles, así que el chequeo de día de semana no los altera. El fin de semana siguiente
# —sábado 08 y domingo 09— es el que ejercita el guardia.


@pytest.fixture
def settings_de_prueba():
    return get_settings().model_copy(
        update={
            "ingesta_zona_horaria": "America/Argentina/Buenos_Aires",
            "ingesta_hora_matinal": "09:00",
            "ingesta_refresh_minutos": 15,
            "ingesta_rueda_desde": "11:00",
            "ingesta_rueda_hasta": "17:00",
        }
    )


def _local(año, mes, dia, hora, minuto) -> datetime:
    return datetime(año, mes, dia, hora, minuto, tzinfo=TZ)


# --- proxima_matinal ------------------------------------------------------------------------


def test_antes_de_la_hora_matinal_es_hoy(settings_de_prueba) -> None:
    resultado = proxima_matinal(_local(2026, 8, 6, 8, 59), settings_de_prueba)
    assert resultado == _local(2026, 8, 6, 9, 0)


def test_justo_a_la_hora_matinal_pasa_a_manana(settings_de_prueba) -> None:
    """Ya se disparó, así que el próximo objetivo es el de mañana, no el mismo instante otra vez."""
    resultado = proxima_matinal(_local(2026, 8, 6, 9, 0), settings_de_prueba)
    assert resultado == _local(2026, 8, 7, 9, 0)


def test_despues_de_la_hora_matinal_es_manana(settings_de_prueba) -> None:
    resultado = proxima_matinal(_local(2026, 8, 6, 15, 0), settings_de_prueba)
    assert resultado == _local(2026, 8, 7, 9, 0)


def test_convierte_desde_otra_zona_horaria(settings_de_prueba) -> None:
    """08:59 en Buenos Aires son las 11:59 UTC: el cálculo tiene que hacerse en hora local."""
    desde_utc = datetime(2026, 8, 6, 11, 59, tzinfo=ZoneInfo("UTC"))
    resultado = proxima_matinal(desde_utc, settings_de_prueba)
    assert resultado == _local(2026, 8, 6, 9, 0)


# --- proximo_refresh -------------------------------------------------------------------------


def test_antes_de_que_abra_la_rueda_el_proximo_es_la_apertura(settings_de_prueba) -> None:
    resultado = proximo_refresh(_local(2026, 8, 6, 9, 30), settings_de_prueba)
    assert resultado == _local(2026, 8, 6, 11, 0)


def test_dentro_de_la_rueda_el_proximo_es_el_siguiente_multiplo(settings_de_prueba) -> None:
    resultado = proximo_refresh(_local(2026, 8, 6, 11, 5), settings_de_prueba)
    assert resultado == _local(2026, 8, 6, 11, 15)


def test_justo_en_un_multiplo_el_proximo_es_el_siguiente(settings_de_prueba) -> None:
    """A las 11:15 en punto ya tocó ese refresh: el próximo es 11:30, no el mismo instante."""
    resultado = proximo_refresh(_local(2026, 8, 6, 11, 15), settings_de_prueba)
    assert resultado == _local(2026, 8, 6, 11, 30)


def test_al_cierre_de_la_rueda_pasa_a_la_apertura_de_manana(settings_de_prueba) -> None:
    resultado = proximo_refresh(_local(2026, 8, 6, 17, 0), settings_de_prueba)
    assert resultado == _local(2026, 8, 7, 11, 0)


def test_despues_del_cierre_pasa_a_la_apertura_de_manana(settings_de_prueba) -> None:
    resultado = proximo_refresh(_local(2026, 8, 6, 20, 0), settings_de_prueba)
    assert resultado == _local(2026, 8, 7, 11, 0)


def test_el_ultimo_tick_exacto_cae_en_el_cierre(settings_de_prueba) -> None:
    """11:00-17:00 son 360 minutos, múltiplo exacto de 15: el último tick cae justo en el cierre."""
    resultado = proximo_refresh(_local(2026, 8, 6, 16, 50), settings_de_prueba)
    assert resultado == _local(2026, 8, 6, 17, 0)


def test_un_tick_que_se_pasaria_del_cierre_pasa_a_manana(settings_de_prueba) -> None:
    """Cierre a las 16:50: el múltiplo de 15 después de las 16:45 cae a las 17:00, que ya pasó el
    cierre, así que el próximo evento es la apertura de mañana."""
    settings = settings_de_prueba.model_copy(update={"ingesta_rueda_hasta": "16:50"})
    resultado = proximo_refresh(_local(2026, 8, 6, 16, 46), settings)
    assert resultado == _local(2026, 8, 7, 11, 0)


# --- en_ventana_de_rueda ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("hora", "minuto", "esperado"),
    [
        (10, 59, False),
        (11, 0, True),
        (14, 0, True),
        (17, 0, True),
        (17, 1, False),
    ],
)
def test_en_ventana_de_rueda(settings_de_prueba, hora, minuto, esperado) -> None:
    assert en_ventana_de_rueda(_local(2026, 8, 6, hora, minuto), settings_de_prueba) is esperado


# --- El guardia de día hábil (08/08/2026) ----------------------------------------------------
#
# Hasta esta fecha las tres funciones sólo miraban la hora. Una corrida disparada un sábado a las
# 14:12 pasó el chequeo y escribió 466 filas sin un solo precio, dejando el indicador de frescura
# declarando el sábado sobre datos del miércoles. El scheduler habría repetido eso solo, todos los
# fines de semana, apenas se habilitara.


@pytest.mark.parametrize(
    ("dia", "nombre", "esperado"),
    [(6, "jueves", True), (7, "viernes", True), (8, "sábado", False), (9, "domingo", False)],
)
def test_es_dia_habil(dia, nombre, esperado) -> None:
    from datetime import date

    assert es_dia_habil(date(2026, 8, dia)) is esperado, nombre


@pytest.mark.parametrize("dia", [8, 9])
def test_el_fin_de_semana_nunca_esta_en_ventana(settings_de_prueba, dia) -> None:
    """14:00 está en el medio de la rueda, pero un sábado no hay rueda."""
    assert en_ventana_de_rueda(_local(2026, 8, dia, 14, 0), settings_de_prueba) is False


def test_el_viernes_despues_de_la_matinal_apunta_al_lunes(settings_de_prueba) -> None:
    """El salto no es de un día: viernes 15:00 → lunes 09:00, salteando el fin de semana."""
    resultado = proxima_matinal(_local(2026, 8, 7, 15, 0), settings_de_prueba)
    assert resultado == _local(2026, 8, 10, 9, 0)


def test_un_sabado_temprano_la_matinal_no_es_ese_mismo_dia(settings_de_prueba) -> None:
    """Sin el chequeo de día, las 08:00 del sábado devolvían las 09:00 del sábado: una corrida
    contra un mercado cerrado, y encima antes de que nadie la viera."""
    resultado = proxima_matinal(_local(2026, 8, 8, 8, 0), settings_de_prueba)
    assert resultado == _local(2026, 8, 10, 9, 0)


def test_el_viernes_al_cierre_el_refresh_pasa_al_lunes(settings_de_prueba) -> None:
    resultado = proximo_refresh(_local(2026, 8, 7, 17, 0), settings_de_prueba)
    assert resultado == _local(2026, 8, 10, 11, 0)


@pytest.mark.parametrize(("dia", "hora"), [(8, 9), (8, 14), (9, 20)])
def test_en_fin_de_semana_el_refresh_apunta_al_lunes(settings_de_prueba, dia, hora) -> None:
    """A cualquier hora del fin de semana —antes, durante o después del horario de rueda— el
    próximo tick es la apertura del lunes."""
    resultado = proximo_refresh(_local(2026, 8, dia, hora, 0), settings_de_prueba)
    assert resultado == _local(2026, 8, 10, 11, 0)
