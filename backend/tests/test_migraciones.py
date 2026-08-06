"""Guardas estructurales sobre los archivos de migración. Corren sin base de datos.

El criterio de aceptación dice que un rollback tiene que dejar las tablas de mercado en pie. Eso se
ensayó una vez contra la base real y quedó documentado en docs/esquema-datos.md, pero ensayarlo en
cada corrida sería destructivo. Lo que sí se puede verificar siempre es la propiedad que lo hace
cierto: que **cada rollback dropee únicamente objetos que creó su propia migración**.
"""

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
MIGRACIONES = RAIZ / "supabase" / "migrations"
ROLLBACKS = RAIZ / "supabase" / "rollbacks"

_CREA = re.compile(r"CREATE\s+(?:TABLE|VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?public\.(\w+)", re.I)
_DROPEA = re.compile(r"DROP\s+(?:TABLE|VIEW)\s+(?:IF\s+EXISTS\s+)?public\.(\w+)", re.I)
_VERSION_BORRADA = re.compile(r"schema_migrations\s+WHERE\s+version\s*=\s*'(\d+)'", re.I)


def _versiones() -> list[str]:
    """Timestamp de cada migración, tomado del nombre del archivo."""
    return sorted(archivo.name.split("_")[0] for archivo in MIGRACIONES.glob("*.sql"))


def _rollback_de(version: str) -> Path:
    coincidencias = list(ROLLBACKS.glob(f"{version}_*.sql"))
    assert len(coincidencias) == 1, f"la migración {version} no tiene un rollback único"
    return coincidencias[0]


def test_hay_migraciones() -> None:
    """Si el glob no encuentra nada, los tests de abajo pasarían vacíos y no probarían nada."""
    assert _versiones(), f"no hay migraciones en {MIGRACIONES}"


@pytest.mark.parametrize("version", _versiones())
def test_cada_migracion_tiene_su_rollback(version: str) -> None:
    assert _rollback_de(version).exists()


@pytest.mark.parametrize("version", _versiones())
def test_el_rollback_solo_toca_lo_que_creo_su_migracion(version: str) -> None:
    """Es la garantía de que tirar abajo lo de usuario no se lleva puesto el universo."""
    up = next(MIGRACIONES.glob(f"{version}_*.sql")).read_text(encoding="utf-8")
    down = _rollback_de(version).read_text(encoding="utf-8")

    creados = set(_CREA.findall(up))
    dropeados = set(_DROPEA.findall(down))

    ajenos = dropeados - creados
    assert not ajenos, f"el rollback de {version} dropea objetos que no creó: {sorted(ajenos)}"


@pytest.mark.parametrize("version", _versiones())
def test_el_rollback_deshace_todo_lo_que_creo_su_migracion(version: str) -> None:
    """Un rollback a medias deja la base en un estado que ninguna migración describe."""
    up = next(MIGRACIONES.glob(f"{version}_*.sql")).read_text(encoding="utf-8")
    down = _rollback_de(version).read_text(encoding="utf-8")

    huerfanos = set(_CREA.findall(up)) - set(_DROPEA.findall(down))
    assert not huerfanos, f"el rollback de {version} deja objetos sin borrar: {sorted(huerfanos)}"


@pytest.mark.parametrize("version", _versiones())
def test_el_rollback_borra_su_propia_fila_del_historial(version: str) -> None:
    """Con la versión de otra migración, el historial quedaría diciendo una mentira."""
    down = _rollback_de(version).read_text(encoding="utf-8")
    assert _VERSION_BORRADA.findall(down) == [version]
