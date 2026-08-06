"""Elegir el último informe subido: de qué archivo sale el dato cuando nadie sube nada hoy.

La consolidación no puede pedirle el informe a IAMC —llega por subida manual— así que vuelve a
parsear el último aceptado. Cuál es "el último" tiene que ser una regla y no una casualidad del
sistema de archivos.
"""

import pytest

from app.core.config import get_settings
from app.ingesta.iamc.almacen import guardar_informe, ultimo_informe


@pytest.fixture(autouse=True)
def _directorio_en_tmp(tmp_path, monkeypatch):
    """El almacén apunta a un temporal: los tests no tocan `fuentes/` del repo."""
    settings = get_settings()
    monkeypatch.setattr(settings, "iamc_directorio", str(tmp_path))
    return tmp_path


def test_sin_informes_devuelve_none() -> None:
    assert ultimo_informe() is None


def test_devuelve_el_de_la_fecha_mas_reciente() -> None:
    from datetime import date

    guardar_informe(b"%PDF-viejo", fecha_informe=date(2026, 7, 30))
    guardar_informe(b"%PDF-nuevo", fecha_informe=date(2026, 8, 5))
    guardar_informe(b"%PDF-medio", fecha_informe=date(2026, 8, 1))

    ruta, contenido = ultimo_informe()

    assert contenido == b"%PDF-nuevo"
    assert ruta.name == "iamc-deuda-corporativa-2026-08-05.pdf"


def test_la_fecha_sale_del_nombre_y_no_de_la_modificacion(_directorio_en_tmp) -> None:
    """Un archivo copiado o restaurado cambia de mtime sin cambiar de contenido."""
    import os
    from datetime import date

    viejo = guardar_informe(b"%PDF-viejo", fecha_informe=date(2026, 7, 30))
    guardar_informe(b"%PDF-nuevo", fecha_informe=date(2026, 8, 5))
    # El informe viejo pasa a ser el más recientemente tocado.
    os.utime(viejo, (2_000_000_000, 2_000_000_000))

    _, contenido = ultimo_informe()

    assert contenido == b"%PDF-nuevo", "eligió por mtime en vez de por la fecha del informe"


def test_un_informe_rechazado_no_se_consume_como_dato() -> None:
    """Se guardan para diagnosticar un cambio de layout, no para alimentar la consolidación."""
    from datetime import date

    guardar_informe(b"%PDF-bueno", fecha_informe=date(2026, 8, 5))
    guardar_informe(b"esto-no-es-un-pdf", rechazado=True)

    ruta, contenido = ultimo_informe()

    assert contenido == b"%PDF-bueno"
    assert "rechazado" not in ruta.name


def test_solo_hay_rechazados_y_devuelve_none() -> None:
    guardar_informe(b"esto-no-es-un-pdf", rechazado=True)

    assert ultimo_informe() is None
