"""Traducción curada al español de la clasificación SIC, en dos niveles — F-079, fase 1.

## Qué traduce esto y por qué no es una interpretación nuestra

`data/sic_sectores.csv` traduce el major group SIC de dos dígitos —el mismo nivel que
`app/externos/sic.py::major_group_de` calcula, y que el SIC Manual de OSHA
(`osha.gov/data/sic-manual`) publica bajo un nombre en inglés por código—. `data/sic_rubros.csv`
traduce `sic_titulo`, el título de cuatro dígitos que ya persiste `perfil_renta_variable` tal como
lo publica la SEC. En los dos casos el inglés que se traduce es el nombre oficial de un estándar
publicado, no un código propietario que inventemos cómo leer (regla 11) — es el mismo argumento que
justifica `app/renta_variable/regiones.py` para el M49 de la ONU.

## El gate de validación humana

Los dos CSV los valida el dueño del producto antes de cargarse — mismo patrón que
`data/paises_cedears.csv` en F-078 (`app/renta_variable/paises.py`). **Ninguno de los dos existe
todavía.** Mientras no exista, este módulo no falla ni loggea error: `sector_de` y `rubro_de`
devuelven `None` para todo, que es el mismo estado esperado que `pais_cedear` corriendo con cero
filas — el sistema entero sigue funcionando con el fallback que decide el consumidor
(`especies.py`): sector sin traducir muestra el código de dos dígitos (un estándar se lee), rubro
específico sin traducir muestra `sic_titulo` en inglés (es la fuente, no nuestra interpretación).

## Qué NO hace este módulo

No fabrica ninguna traducción a partir de otra ni de la estructura del código: sin fila en el CSV
para ese `major_group` o ese `sic_codigo`, la respuesta es `None`. El fallback declarado vive en el
consumidor, no acá — este módulo sólo sabe leer lo que el curado ya validó.
"""

import csv
from functools import lru_cache
from pathlib import Path

import structlog

from app.core.config import ENV_FILE, Settings, get_settings
from app.externos.sic import major_group_de

logger = structlog.get_logger()

_RAIZ_REPO = ENV_FILE.parent

_COLUMNA_SECTOR = "major_group"
_COLUMNA_RUBRO = "sic_codigo"
_COLUMNA_ETIQUETA = "etiqueta_es"


def ruta_sic_sectores(settings: Settings) -> Path:
    ruta = Path(settings.sic_sectores_csv)
    return ruta if ruta.is_absolute() else _RAIZ_REPO / ruta


def ruta_sic_rubros(settings: Settings) -> Path:
    ruta = Path(settings.sic_rubros_csv)
    return ruta if ruta.is_absolute() else _RAIZ_REPO / ruta


@lru_cache(maxsize=8)
def _leer_etiquetas(ruta_str: str, columna_codigo: str, ancho: int) -> dict[str, str]:
    """`{código zfill(ancho): etiqueta_es}` de un CSV de traducción curada.

    Cacheado por `(ruta, columna, ancho)`: el artefacto es curado y versionado, no cambia durante
    la vida del proceso, así que releerlo en cada especie de cada request sería trabajo repetido
    sin motivo. La clave incluye la ruta como string para que un test que apunta a otro archivo
    (otro `tmp_path`) no pise la caché de otro test ni de otro proceso.

    Archivo ausente ⇒ dict vacío, sin log de error — es el estado esperado hasta que el dueño valide
    el curado (mismo criterio que `pais_cedear` con 0 filas). Columnas faltantes o fila con código
    no numérico o etiqueta vacía ⇒ se descarta con un log de `info`, no de error: no hay job ni
    alertas acá, es lectura pura para un consumidor que ya tiene su propio fallback.
    """
    ruta = Path(ruta_str)
    if not ruta.is_file():
        return {}

    # utf-8-sig y no utf-8: el CSV se edita en planillas que dejan BOM al principio, mismo motivo
    # que `paises.py`.
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        columnas = set(lector.fieldnames or ())
        if not {columna_codigo, _COLUMNA_ETIQUETA}.issubset(columnas):
            logger.info(
                "sic_es_csv_sin_columnas_esperadas",
                archivo=ruta.name,
                columnas=sorted(columnas),
            )
            return {}

        etiquetas: dict[str, str] = {}
        for fila in lector:
            crudo = (fila.get(columna_codigo) or "").strip()
            etiqueta = (fila.get(_COLUMNA_ETIQUETA) or "").strip()
            if not crudo.isdigit() or not etiqueta:
                logger.info(
                    "sic_es_fila_descartada",
                    archivo=ruta.name,
                    columna=columna_codigo,
                    valor=crudo,
                )
                continue
            etiquetas[crudo.zfill(ancho)] = etiqueta
        return etiquetas


def sector_de(sic_codigo: str | None) -> str | None:
    """La etiqueta ES del sector (major group SIC de 2 dígitos) de un `sic_codigo`, o `None`.

    `None` si falta `sic_codigo`, si no tiene major group afirmable (`major_group_de`), si el CSV
    de sectores no existe todavía, o si ese major group no tiene fila en el curado. Los cuatro
    casos son el mismo desde el punto de vista del asesor: no hay traducción, y el consumidor
    decide el fallback (mostrar el código crudo). Mismo patrón que
    `app/fci/enlaces.py::enlace_composicion_cnv`: lee la settings vigente en vez de recibirla, para
    que cada especie no tenga que arrastrarla en la firma.
    """
    grupo = major_group_de(sic_codigo)
    if grupo is None:
        return None
    etiquetas = _leer_etiquetas(str(ruta_sic_sectores(get_settings())), _COLUMNA_SECTOR, 2)
    return etiquetas.get(grupo)


def rubro_de(sic_codigo: str | None) -> str | None:
    """La etiqueta ES del rubro específico (título SIC de 4 dígitos) de un `sic_codigo`, o `None`.

    `None` si falta `sic_codigo`, si no es numérico, si el CSV de rubros no existe todavía, o si
    ese código no tiene fila en el curado. El fallback declarado (`sic_titulo` en inglés, tal como
    lo publica la SEC) lo decide el consumidor, no este módulo.
    """
    if sic_codigo is None:
        return None
    texto = str(sic_codigo).strip()
    if not texto.isdigit():
        return None
    etiquetas = _leer_etiquetas(str(ruta_sic_rubros(get_settings())), _COLUMNA_RUBRO, 4)
    return etiquetas.get(texto.zfill(4))
