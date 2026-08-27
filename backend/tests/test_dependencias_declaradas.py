"""Que `pyproject.toml` y `requirements.txt` no se separen — guardia de deploy.

El backend declara sus dependencias en dos lados y cada uno lo lee alguien distinto: Vercel instala
desde `[project.dependencies]` de `pyproject.toml` (y **ignora** `requirements.txt` cuando existe esa
sección) y el Dockerfile hace `pip install -r requirements.txt`. Ese desdoblamiento ya costó una
producción caída el 26/08/2026: `pyproject.toml` tenía la sección `[project]` sin `dependencies`,
Vercel resolvió cero paquetes y la función murió en el primer `from fastapi import FastAPI`.

Lo que este test cuida no es que las listas sean iguales —no lo son, `requirements.txt` es el freeze
completo del venv con transitivas y herramientas de desarrollo— sino que **ninguna dependencia
directa esté declarada en dos versiones distintas**, y que ninguna esté sólo en el freeze. Sin esto,
agregar una librería y anotarla nada más que en `requirements.txt` pasa todos los tests locales,
pasa el build de Docker, y explota recién en el deploy.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PYPROJECT = RAIZ / "pyproject.toml"
REQUIREMENTS = RAIZ / "requirements.txt"


def _normalizar(nombre: str) -> str:
    """PEP 503: `PyJWT`, `pyjwt` y `py_jwt` son el mismo paquete para pip, y hay que compararlos igual."""
    return nombre.strip().lower().replace("_", "-").replace(".", "-")


def _pineadas_de_pyproject() -> dict[str, str]:
    datos = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    pineadas: dict[str, str] = {}
    for linea in datos["project"]["dependencies"]:
        nombre, _, version = linea.partition("==")
        # Una dependencia sin `==` no es comparable contra el freeze; se declara acá para que el
        # fallo diga qué pasó en vez de saltar un KeyError más adelante.
        assert version, f"{linea!r} en pyproject.toml no está pineada con `==`"
        pineadas[_normalizar(nombre)] = version.strip()
    return pineadas


def _pineadas_de_requirements() -> dict[str, str]:
    pineadas: dict[str, str] = {}
    for cruda in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        linea = cruda.split("#")[0].strip()
        if not linea or linea.startswith("-"):
            continue
        nombre, _, version = linea.partition("==")
        if version:
            pineadas[_normalizar(nombre)] = version.strip()
    return pineadas


def test_toda_dependencia_directa_esta_en_el_freeze() -> None:
    """Lo que Vercel instala tiene que existir también en el entorno donde corren los tests."""
    faltantes = sorted(set(_pineadas_de_pyproject()) - set(_pineadas_de_requirements()))
    assert not faltantes, (
        f"Estas dependencias están en pyproject.toml y no en requirements.txt: {faltantes}. "
        "Agregalas al freeze o el entorno de tests deja de parecerse al de producción."
    )


def test_las_dos_listas_declaran_la_misma_version() -> None:
    """Dos versiones para el mismo paquete significa que el deploy corre algo que nadie probó."""
    freeze = _pineadas_de_requirements()
    discordantes = {
        paquete: (version, freeze[paquete])
        for paquete, version in _pineadas_de_pyproject().items()
        if paquete in freeze and freeze[paquete] != version
    }
    assert not discordantes, (
        "Versiones distintas entre pyproject.toml y requirements.txt "
        f"(paquete: pyproject vs requirements): {discordantes}"
    )
