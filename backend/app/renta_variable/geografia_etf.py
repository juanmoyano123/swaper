"""El CSV curado de geografía de ETFs se vuelve filas con fuente y fecha — F-079, D3 / fase 2.

Calcado de `app/renta_variable/paises.py`, que es el patrón de siembra desde artefacto curado del
proyecto para dato por-papel con trazabilidad propia. Lo que cambia acá es qué se cura.

## Qué se cura acá, y por qué no más que esto

Un ETF geográfico hoy se muestra con el token crudo de su nombre (`region_etf`: "EAFE", "Emerging
Markets", "Japan") — un valor que no le dice nada a un asesor sin trasfondo de mercado. El dueño
decidió (29/08/2026, D3) curar por fondo **qué índice sigue** y **qué alcance declara el emisor de
ese índice**, en español y corto, más el país ISO cuando el fondo es de un solo país.

Lo que explícitamente **no** se cura es la composición completa de países de un índice
multi-país (qué % es Corea, qué % es Taiwán dentro de un EAFE o un Emerging Markets). Esa
composición cambia con cada rebalanceo del índice — es la misma lección que llevó a pausar el
consumo de IAMC (`IAMC_HABILITADO=false`, ver CLAUDE.md): un dato que envejece silenciosamente al
lado de un precio de hoy es peor que no tenerlo. `alcance` es la definición del ÍNDICE según su
propio emisor, no nuestra lectura de qué países lo componen hoy — eso no cambia con el rebalanceo.
`pais` sólo se completa para el puñado de fondos mono-país (EWJ → Japón, FXI → China), donde no hay
composición que envejezca porque el fondo es, por definición, un solo país.

## Trazabilidad por fila, no por artefacto

Mismo criterio que `paises.py`: cada fila se investigó una por una, así que cada una trae su
`fuente` (el emisor del índice, la página que declara el alcance) y su `verificado`. `indice` y
`alcance` son `NOT NULL` — un ETF sin esos dos datos no entra a la tabla, porque son la razón de
ser de la fila; `pais` sí puede quedar `NULL`, y es el valor correcto para todo fondo multi-país.

## El vocabulario cerrado sigue siendo `REGION_M49`

Igual que en `paises.py`: un `pais` que no sea una clave de
`app/renta_variable/regiones.py::REGION_M49` se descarta y se reporta. Reusar el mismo vocabulario
(y la misma función `region_de`) es a propósito — es el mismo eje que ya usa `pais_cedear`, y un
ETF mono-país comparte agrupamiento por región con un CEDEAR del mismo país sin que haya que
mapear nada.

## Se lee con el `csv` de la stdlib y no con pandas

Mismo motivo que `paises.py`: son ~10-15 filas de texto plano.
"""

import csv
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import structlog
from starlette.concurrency import run_in_threadpool

from app.core.config import ENV_FILE, Settings
from app.ingesta.alertas import Alerta, Severidad, formato_inesperado
from app.renta_variable.regiones import REGION_M49, region_de

logger = structlog.get_logger()

TABLA = "etf_geografia"

COLUMNAS: tuple[str, ...] = ("ticker_papel", "indice", "alcance", "pais", "fuente", "verificado")
"""Las seis que el CSV tiene que traer. `cargado_en` lo pone la base, no el artefacto."""

CODIGO_CURADO_AUSENTE = "etfs_geografia_no_encontrado"
CODIGO_PAIS_FUERA_DE_VOCABULARIO = "pais_fuera_de_vocabulario"
CODIGO_PAPEL_REPETIDO = "papel_repetido_en_curado"
CODIGO_FILA_SIN_TRAZA = "fila_curada_sin_trazabilidad"

ACCION_REVISAR_CSV = (
    "Revisar data/etfs_geografia.csv: cada fila lleva el índice que sigue el ETF, el alcance que "
    "declara el emisor de ese índice, el país ISO si es mono-país, la fuente y la fecha en que se "
    "verificó."
)

# La ruta relativa se resuelve contra la raíz del repo y no contra el cwd, que cambia según se
# arranque con uvicorn, pytest o Docker. Mismo criterio que `paises.py::ruta_paises`.
_RAIZ_REPO = ENV_FILE.parent


@dataclass(frozen=True, slots=True)
class FilaGeografiaEtf:
    """La geografía curada de un ETF, con lo que la declara y cuándo se verificó.

    `pais` en `None` es el caso normal — es un fondo multi-país, y su composición completa no se
    cura (envejece con cada rebalanceo). `indice` y `alcance` sí están siempre: son la razón de ser
    de la fila.
    """

    ticker_papel: str
    indice: str
    alcance: str
    pais: str | None
    fuente: str
    verificado: date

    @property
    def region(self) -> str | None:
        """La subregión M49 del país, derivada al leer. `None` para todo fondo multi-país (sin
        `pais`) y para uno cuyo país no está en el vocabulario — ver `regiones.py`."""
        return region_de(self.pais)


@dataclass(frozen=True, slots=True)
class CuradoGeografiaEtfs:
    """Lo que se pudo leer del artefacto, con lo descartado declarado al lado."""

    filas: list[FilaGeografiaEtf] = field(default_factory=list)
    alertas: list[Alerta] = field(default_factory=list)
    archivo: str | None = None
    descartados: dict[str, dict[str, str]] = field(default_factory=dict)
    """Qué se dejó afuera, por motivo y con nombre y apellido: `{codigo: {ticker: valor}}`."""


@dataclass(frozen=True, slots=True)
class ResumenSiembraGeografiaEtfs:
    """Lo que la siembra dejó cargado y lo que no, con los motivos separados."""

    cargados: int
    descartados: int
    sin_pais: int
    """Filas cargadas con `pais` vacío. **No son un fallo**: son el caso normal de un fondo
    multi-país, cuya composición completa no se cura a propósito (D3)."""
    archivo: str | None = None
    detalle_descartes: dict[str, dict[str, str]] = field(default_factory=dict)
    alertas: list[Alerta] = field(default_factory=list)

    def como_dict(self) -> dict[str, object]:
        return {
            "archivo": self.archivo,
            "cargados": self.cargados,
            "descartados": self.descartados,
            "sin_pais": self.sin_pais,
            "detalle_descartes": self.detalle_descartes,
            "alertas": [a.como_dict() for a in self.alertas],
        }


def ruta_geografia_etfs(settings: Settings) -> Path:
    ruta = Path(settings.etfs_geografia_csv)
    return ruta if ruta.is_absolute() else _RAIZ_REPO / ruta


def curado_ausente(ruta: Path) -> Alerta:
    """El archivo no está donde `settings.etfs_geografia_csv` dice.

    Es un ERROR y no una advertencia por el mismo motivo que en `paises.py`: sin artefacto no hay
    nada que sembrar, y una corrida que cantara éxito sobre cero filas sería indistinguible de un
    curado que todavía no empezó. Es el estado normal hasta que el dueño del producto valide la
    primera tanda (fase 7 del plan F-079).
    """
    return Alerta(
        codigo=CODIGO_CURADO_AUSENTE,
        mensaje=f"No se encontró el CSV curado de geografía de ETFs en {ruta}.",
        severidad=Severidad.ERROR,
        accion_requerida=(
            "Verificar ETFS_GEOGRAFIA_CSV. Si el curado todavía no se validó, el archivo no "
            "existe y no hay nada que sembrar: la geografía de cada ETF sigue mostrándose con el "
            "token crudo del nombre del fondo."
        ),
        detalle={"ruta": str(ruta)},
    )


def _descarte(codigo: str, motivo: str, valores: dict[str, str]) -> Alerta:
    """Filas que no se cargan, dichas con nombre y apellido. Mismo criterio que `paises.py`."""
    muestra = ", ".join(f"{papel}={valor!r}" for papel, valor in sorted(valores.items())[:8])
    return Alerta(
        codigo=codigo,
        mensaje=f"{len(valores)} papeles {motivo} ({muestra}): no se cargan.",
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=ACCION_REVISAR_CSV,
        detalle={"papeles": valores},
    )


def _leer_fecha(texto: str) -> date | None:
    """`verificado` en ISO (`2026-08-29`), o `None`. Mismo motivo que `paises.py`: un `08/09/2026`
    es ambiguo y adivinar cuál sería inventar la fecha del dato."""
    try:
        return date.fromisoformat(texto)
    except ValueError:
        return None


def leer_curado(ruta: Path) -> CuradoGeografiaEtfs:
    """Lee el CSV curado y devuelve una fila por papel, ya validada contra el vocabulario.

    Función pura: sin base, sin red y sin reloj. Nunca lanza — un archivo ausente o mal formado
    vuelve como alerta y con cero filas, que es lo que la siembra necesita para no escribir nada en
    vez de vaciar la tabla.
    """
    if not ruta.is_file():
        return CuradoGeografiaEtfs(alertas=[curado_ausente(ruta)])

    # utf-8-sig y no utf-8: el CSV se edita en planillas que dejan BOM al principio, y con utf-8 la
    # primera columna pasa a llamarse "﻿ticker_papel" y no matchea con nada.
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        faltantes = sorted(set(COLUMNAS) - set(lector.fieldnames or ()))
        if faltantes:
            return CuradoGeografiaEtfs(
                alertas=[
                    formato_inesperado(
                        "El curado de geografía de ETFs",
                        f"le faltan columnas ({', '.join(faltantes)})",
                        archivo=ruta.name,
                        faltantes=faltantes,
                    )
                ],
                archivo=ruta.name,
            )
        crudas = list(lector)

    filas: list[FilaGeografiaEtf] = []
    vistos: set[str] = set()
    descartados: dict[str, dict[str, str]] = {}

    def _descartar(codigo: str, papel: str, valor: str) -> None:
        descartados.setdefault(codigo, {})[papel] = valor

    for cruda in crudas:
        papel = (cruda.get("ticker_papel") or "").strip().upper()
        if not papel:
            continue
        if papel in vistos:
            # Se conserva la primera aparición y no se fusionan las dos filas: fusionar sería
            # decidir cuál de las dos geografías vale. Mismo criterio que `paises.py`.
            _descartar(CODIGO_PAPEL_REPETIDO, papel, (cruda.get("indice") or "").strip())
            continue
        vistos.add(papel)

        indice = (cruda.get("indice") or "").strip()
        alcance = (cruda.get("alcance") or "").strip()
        pais = (cruda.get("pais") or "").strip().upper()
        fuente = (cruda.get("fuente") or "").strip()
        verificado = _leer_fecha((cruda.get("verificado") or "").strip())

        if pais and pais not in REGION_M49:
            _descartar(CODIGO_PAIS_FUERA_DE_VOCABULARIO, papel, pais)
            continue
        if not indice or not alcance or not fuente or verificado is None:
            # La fila entera se cae: `indice` y `alcance` son la razón de ser de la fila, y una
            # fila sin fuente o sin fecha no se muestra (regla 11). El detalle dice cuál faltaba.
            _descartar(
                CODIGO_FILA_SIN_TRAZA,
                papel,
                f"indice={indice!r} alcance={alcance!r} fuente={fuente!r} "
                f"verificado={(cruda.get('verificado') or '').strip()!r}",
            )
            continue

        filas.append(
            FilaGeografiaEtf(
                ticker_papel=papel,
                indice=indice,
                alcance=alcance,
                pais=pais or None,
                fuente=fuente,
                verificado=verificado,
            )
        )

    motivos = {
        CODIGO_PAPEL_REPETIDO: "aparecen más de una vez en el curado",
        CODIGO_PAIS_FUERA_DE_VOCABULARIO: (
            "declaran un país que no es un código ISO 3166-1 alfa-2 con región M49 conocida"
        ),
        CODIGO_FILA_SIN_TRAZA: "no declaran índice, alcance, fuente o fecha de verificación",
    }
    alertas = [
        _descarte(codigo, motivos[codigo], valores)
        for codigo, valores in descartados.items()
        if valores
    ]

    return CuradoGeografiaEtfs(
        filas=filas, alertas=alertas, archivo=ruta.name, descartados=descartados
    )


SQL_UPSERT = (
    f"INSERT INTO public.{TABLA} (ticker_papel, indice, alcance, pais, fuente, verificado) "
    "VALUES ($1, $2, $3, $4, $5, $6) "
    "ON CONFLICT (ticker_papel) DO UPDATE SET "
    # Sin COALESCE y a propósito: el CSV es la fuente de verdad completa por fila, así que un
    # re-run pisa todo con el valor nuevo. Mismo criterio literal que `pais_cedear.pais` en
    # `paises.py` — acá se extiende a las seis columnas porque las seis vienen del mismo curado.
    "indice = EXCLUDED.indice, "
    "alcance = EXCLUDED.alcance, "
    "pais = EXCLUDED.pais, "
    "fuente = EXCLUDED.fuente, "
    "verificado = EXCLUDED.verificado, "
    "cargado_en = now()"
)

SQL_LEER = f"SELECT ticker_papel, indice, alcance, pais, fuente, verificado FROM public.{TABLA}"


async def persistir(conn: Any, filas: Sequence[FilaGeografiaEtf]) -> int:
    """Escribe el curado en una sola transacción y devuelve cuántas filas se escribieron.

    **No borra las filas que el CSV dejó de traer.** Un ticker que deja de estar en el CSV no se
    borra de la tabla: mismo criterio que `paises.py::persistir_paises` y que el resto del repo.
    """
    if not filas:
        return 0
    async with conn.transaction():
        await conn.executemany(
            SQL_UPSERT,
            [
                (f.ticker_papel, f.indice, f.alcance, f.pais, f.fuente, f.verificado)
                for f in filas
            ],
        )
    return len(filas)


async def sembrar_geografia_etfs(conn: Any, settings: Settings) -> int:
    """Siembra `public.etf_geografia` desde el CSV curado y devuelve cuántas filas quedaron
    cargadas.

    Idempotente: no hay reloj ni fuente externa en el medio, así que sembrar dos veces seguidas deja
    la misma tabla. Si el archivo no existe todavía —el estado normal hasta la primera tanda
    validada—, devuelve 0 sin explotar: mismo criterio que el resto del módulo.
    """
    ruta = ruta_geografia_etfs(settings)
    # Lectura de archivo síncrona: en el event loop bloquearía al resto del servicio.
    curado = await run_in_threadpool(leer_curado, ruta)

    cargados = await persistir(conn, curado.filas)

    descartados = sum(len(v) for v in curado.descartados.values())
    sin_pais = sum(1 for fila in curado.filas if fila.pais is None)

    logger.info(
        "siembra_geografia_etfs_termino",
        archivo=curado.archivo,
        cargados=cargados,
        descartados=descartados,
        sin_pais=sin_pais,
    )
    return cargados


async def leer_geografia_etfs(conn: Any) -> dict[str, FilaGeografiaEtf]:
    """El curado cargado, indexado por papel, para que la lectura de especies haga el join en
    memoria — mismo motivo que `paises.py::leer_paises`: es una tabla chica (~10-15 filas) y el
    join real es por papel, no por especie."""
    filas = await conn.fetch(SQL_LEER)
    return {
        fila["ticker_papel"]: FilaGeografiaEtf(
            ticker_papel=fila["ticker_papel"],
            indice=fila["indice"],
            alcance=fila["alcance"],
            pais=fila["pais"],
            fuente=fila["fuente"],
            verificado=fila["verificado"],
        )
        for fila in filas
    }
