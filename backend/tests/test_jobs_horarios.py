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
from app.jobs.horarios import en_ventana_de_rueda, proxima_matinal, proximo_refresh

TZ = ZoneInfo("America/Argentina/Buenos_Aires")


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
