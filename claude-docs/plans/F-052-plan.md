# Feature Plan: F-052 — Renta variable en el monitor

## Overview
- **Source**: ficha en `claude-docs/planning/plan.md` (líneas ~1900–1958, versión revisada el
  08/08/2026 con los hallazgos de la exploración) · duda 8 de
  `claude-docs/planning/plan-ejecucion-tandas.md` · monitor de F-038 (`claude-docs/plans/F-038-plan.md`)
- **Complexity**: M/L — paquete backend nuevo + migración chica + tabla compartida en el frontend
- **Modo**: plan prescriptivo. Si algo no cierra contra la realidad del código, **frenar y
  reportar**, no improvisar.
- **Orden**: corre en la tanda 8b, **después de F-051** (que toca la misma consolidación). En
  paralelo corren F-017/F-024 (`features/armador/`) y F-040 (`features/instrumento/`,
  `api/v1/instrumentos.py`, `calendario/`): F-052 no toca nada de eso.

## Qué es

Las pestañas de **acciones** y **CEDEARs** en el monitor de F-038. Los datos ya están en la base
(BYMA vía F-004/F-007), pero nunca llegan al endpoint de universo: `segmentar()` descarta la renta
variable **antes** de segmentar y `Segmentacion.renta_variable` es un contador, no una lista. Por
eso esta feature necesita **lectura y endpoint backend propios** (patrón `posiciones/lectura.py`,
que lee directo por esta misma razón), estrena el **lector de puntas** (la tabla `public.puntas` se
escribe para toda la rueda desde F-007 y ninguna lectura la expone), y persiste el **cierre
anterior** que BYMA publica (`previousClosingPrice`) y la consolidación hoy descarta — de ahí sale
la columna de variación, calculada, nunca estimada.

Columnas propias de renta variable: precio con su moneda de cotización, variación, volumen en
dólares y puntas. **Sin columna de rendimiento** — no existe la TIR de una acción y no se muestra
otra cosa en su lugar (regla 2). Orden y comparación por volumen, siempre sobre `volumen_usd`
(regla 3). Lo que BYMA no publica queda vacío y contado (regla 1). Los componentes de fila y
columnas van a `frontend/src/components/` (zona compartida) porque **F-026 (tanda 9) los hereda**
desde el armador, que tiene prohibido importar de `features/monitor/**` (precedente formal en
`claude-docs/plans/F-018-plan.md`).

## Precondiciones — verificar ANTES de escribir una línea

La base común de la tanda 8 tiene que haber dejado dos cosas. **Al momento de escribir este plan
(08/08/2026) ninguna de las dos existe todavía** — la fila de la tanda 8b en
`plan-ejecucion-tandas.md` las lista como base común *pendiente* — así que verificarlas es lo
primero:

1. `backend/app/api/v1/renta_variable.py` existe (router vacío) y está montado en
   `backend/app/api/v1/router.py`. **Si no existe o no está montado: FRENAR y reportar.** No
   crearlo ni montarlo por cuenta propia — `router.py` es archivo compartido de la tanda.
2. `frontend/src/components/SelectorSegmento.tsx` tiene las claves `accion` y `cedear` en
   `NOMBRE_SEGMENTO` y en `ORDEN` (al final del orden, después de los segmentos de renta fija).
   **Si no están: FRENAR y reportar.** No editarlo — es archivo compartido con F-017.

Además: F-051 ya debe estar cerrada (este plan agrega una línea a `armado.py` sin tocar su lógica
de métricas). Si el dict de `filas_precios` en `armado.py` no se encuentra donde este plan lo
describe, FRENAR y reportar en vez de adaptar.

## GWT (criterios de aceptación, literales del plan)

```
GIVEN el monitor abierto
WHEN se elige la pestaña de acciones o la de CEDEARs
THEN las columnas son las de renta variable —precio, variación, volumen, puntas— y no hay columna
     de rendimiento: ni TIR, ni nada presentado en su lugar

GIVEN un CEDEAR que cotiza en pesos y en dólares
WHEN se ordena o compara por volumen
THEN la comparación usa el volumen normalizado a dólares, nunca los nominales crudos de monedas
     distintas

GIVEN un campo que BYMA no publica para una especie
WHEN se muestra la fila
THEN la celda queda vacía y contada en la cobertura; no se completa por analogía ni se calcula
     desde otra especie

GIVEN las pestañas nuevas junto a las de renta fija
WHEN se mira el conteo del monitor
THEN los instrumentos que siguen fuera (sin_segmento) están declarados con su cantidad, igual que
     antes
```

## Parte 1 — Backend

### 1a. Migración: `cierre_anterior` en `precios` y en la vista `resumen`

Archivo nuevo en `supabase/migrations/` con el formato de nombre de las existentes
(`YYYYMMDDHHMMSS_f052_cierre_anterior.sql`, timestamp real del momento) y su rollback en
`supabase/rollbacks/` (`..._down.sql`), como hacen todas:

```sql
-- F-052 · El cierre anterior que BYMA publica y la consolidación descartaba.
--
-- `previousClosingPrice` ya llega normalizado (FilaRueda.precio_cierre_anterior) y se tiraba al
-- persistir. Se guarda porque es dato publicado, no derivado: la variación del monitor se calcula
-- (precio - cierre_anterior) / cierre_anterior sólo donde ambos existen, y donde falta queda
-- vacía y contada — nunca se estima desde el histórico propio de `precios`.
--
-- Rollback: supabase/rollbacks/<timestamp>_f052_cierre_anterior_down.sql

ALTER TABLE public.precios ADD COLUMN cierre_anterior numeric;

COMMENT ON COLUMN public.precios.cierre_anterior IS
    'previousClosingPrice de BYMA, en la moneda de cotización de la especie. NULL hasta la '
    'primera corrida posterior a esta migración: las filas históricas no lo tienen y no se '
    'rellena hacia atrás.';

-- La vista se reemplaza agregando la columna AL FINAL: CREATE OR REPLACE VIEW sólo admite
-- columnas nuevas al final, y los lectores existentes (motor incluido) leen por nombre, así que
-- pasar de 21 a 22 columnas no rompe a nadie.
CREATE OR REPLACE VIEW public.resumen
WITH (security_invoker = true) AS
SELECT
    i.ticker,
    i.clase_activo,
    i.tipo_tasa,
    i.subtipo,
    i.underlying,
    i.sector,
    p.tir,
    p.tna,
    p.duration,
    i.maturity,
    i.law,
    i.coupon_currency  AS "couponCurrency",
    i.lamina,
    i.calificacion,
    p.paridad,
    p.residual_value   AS "residualValue",
    p.last_price       AS "lastPrice",
    p.effective_volume AS "effectiveVolume",
    i.revisar,
    i.duplicado,
    i.archivo_origen,
    p.cierre_anterior
FROM public.instrumentos i
LEFT JOIN LATERAL (
    SELECT *
    FROM public.precios pr
    WHERE pr.ticker = i.ticker
    ORDER BY pr.capturado_en DESC
    LIMIT 1
) p ON true;
```

**Antes de copiarla**: comparar contra `supabase/migrations/20260806151206_vista_resumen.sql` por
si la base común o F-051 tocaron la vista después de escrito este plan. Si la vista actual difiere
del cuerpo de arriba en algo más que la columna nueva, FRENAR y reportar. El rollback recrea la
vista con las 21 columnas originales (`DROP VIEW public.resumen;` + el `CREATE VIEW` original) y
hace `ALTER TABLE public.precios DROP COLUMN cierre_anterior;`.

Aplicarla a la base con el flujo que use el repo (supabase CLI / MCP); si no hay acceso, dejarla
escrita y reportarlo — los tests son offline y no la necesitan.

### 1b. Persistir el cierre anterior (dos líneas, sin tocar nada más)

- `backend/app/ingesta/consolidacion/persistencia.py` → agregar `"cierre_anterior"` a
  `COLUMNAS_PRECIOS` (el orden dentro de la tupla no importa: `_tuplas` mapea por nombre y
  `sql_precios()` se genera de la tupla).
- `backend/app/ingesta/consolidacion/armado.py` → **una sola línea** en el dict que se agrega a
  `precios` dentro de `armar_consolidacion` (hoy líneas ~414–423, el bloque
  `precios.append({ "ticker": ticker, "last_price": ..., ... })`):

  ```python
  "cierre_anterior": _precio(fila["precio_cierre_anterior"]),
  ```

  El campo existe en `FilaRueda` (`app/ingesta/byma/normalizacion.py:33` y `:126`, capturado de
  `previousClosingPrice`). Pasa por `_precio()` por la misma razón que `last_price`: un cierre de
  cero no es un precio, es que no operó. **No tocar nada más de ese archivo**: ni `_metricas_de`,
  ni `metricas_previas`, ni ninguna lógica que F-051 haya dejado. Si el bloque no está donde se
  describe, FRENAR y reportar.

### 1c. Paquete nuevo `backend/app/renta_variable/`

El precedente exacto es `backend/app/posiciones/lectura.py`: SQL como constante, sin pasar por
`EspecieUniverso` (meter una acción ahí explota: `.naturaleza` hace
`NATURALEZA_TASA[self.segmento]` → `KeyError`). Tres archivos:

**`backend/app/renta_variable/__init__.py`**
```python
from app.renta_variable.especies import EspecieRentaVariable, armar_renta_variable
from app.renta_variable.lectura import leer_renta_variable

__all__ = ["EspecieRentaVariable", "armar_renta_variable", "leer_renta_variable"]
```

**`backend/app/renta_variable/lectura.py`** — sólo SQL, con un docstring que explique por qué
esta lectura existe (la RV sale antes de segmentar y nunca llega a `vista_viva`) y por qué estrena
el lector de puntas. Contenido:

```python
from typing import Any

from app.universo.segmentacion import CLASES_RENTA_VARIABLE

VISTA_UNIVERSO = "public.resumen"
TABLA_INSTRUMENTOS = "public.instrumentos"
TABLA_PUNTAS = "public.puntas"

# Lo que el monitor de renta variable muestra. `cierre_anterior` es la columna 22 de la vista
# (migración F-052); `moneda_cotizacion` no está en la vista y se trae de `instrumentos` con el
# mismo LEFT JOIN que usa `universo/lectura.py`; las puntas salen del último snapshot de
# `public.puntas` con el mismo LATERAL que la vista `resumen` usa para precios — primera lectura
# de esa tabla en todo el backend.
COLUMNAS_VISTA: tuple[str, ...] = ("ticker", "clase_activo", "lastPrice", "effectiveVolume", "cierre_anterior")
COLUMNAS_INSTRUMENTOS: tuple[str, ...] = ("moneda_cotizacion",)
COLUMNAS_PUNTAS: tuple[str, ...] = ("px_bid", "px_ask", "operaciones")

_SELECT = ", ".join(
    [f'u."{c}"' for c in COLUMNAS_VISTA]
    + [f'i."{c}"' for c in COLUMNAS_INSTRUMENTOS]
    + [f'pt."{c}"' for c in COLUMNAS_PUNTAS]
)

_CLASES = ", ".join(f"'{c}'" for c in CLASES_RENTA_VARIABLE)

SQL_RENTA_VARIABLE = (
    f"SELECT {_SELECT} FROM {VISTA_UNIVERSO} u "
    f"LEFT JOIN {TABLA_INSTRUMENTOS} i ON i.ticker = u.ticker "
    "LEFT JOIN LATERAL ("
    f"    SELECT px_bid, px_ask, operaciones FROM {TABLA_PUNTAS} p"
    "     WHERE p.ticker = u.ticker ORDER BY p.capturado_en DESC LIMIT 1"
    ") pt ON true "
    f"WHERE u.clase_activo IN ({_CLASES}) "
    "ORDER BY u.ticker"
)


async def leer_renta_variable(conn: Any) -> list[dict[str, Any]]:
    filas = await conn.fetch(SQL_RENTA_VARIABLE)
    return [dict(fila) for fila in filas]
```

(Identificadores entrecomillados por la misma regla que `universo/lectura.py`: `lastPrice` y
`effectiveVolume` vienen en camelCase.)

**`backend/app/renta_variable/especies.py`** — la lógica, pura, probable sin Postgres:

- `@dataclass(frozen=True, slots=True) class EspecieRentaVariable` con campos:
  `ticker: str`, `clase_activo: str`, `precio: float | None`,
  `moneda_cotizacion: str | None`, `cierre_anterior: float | None`,
  `variacion: float | None`, `volumen: float | None`, `volumen_usd: float | None`,
  `px_bid: float | None`, `px_ask: float | None`, `operaciones: int | None`, y un
  `como_dict()` que devuelve exactamente esas once claves. **Sin campo `rendimiento`, sin
  `naturaleza`, sin `segmento`**: la ausencia es el contrato (regla 2), no un TODO.
- `def variacion_diaria(precio: float | None, cierre_anterior: float | None) -> float | None` —
  `(precio - cierre_anterior) / cierre_anterior` como **fracción** (0.031 = +3,1%, misma
  convención que `rendimiento` y `paridad` en el resto del API) sólo si ambos son no-`None` y
  `cierre_anterior > 0`; en cualquier otro caso `None`. Nunca se estima desde otra especie ni
  desde el histórico propio.
- `def volumen_en_dolares(cambio: TipoDeCambio, volumen: float | None, moneda_cotizacion: str | None) -> float | None`:
  - `volumen is None` → `None`.
  - `moneda_cotizacion is None` → `None`. **Acá NO se cae a la regla del sufijo D/C** que usa
    `cambio.cotiza_en_dolares` para bonos: esa regla es de especies de liquidación de renta fija
    y aplicarla a una acción sería completar por analogía (regla 1). El faltante se cuenta.
  - `moneda_cotizacion.upper() in MONEDAS_EN_DOLARES` → `volumen` tal cual.
  - resto (ARS) → `cambio.a_dolares(volumen, en_dolares=False)` — que ya devuelve `None` si no
    hay tipo de cambio del día, nunca el crudo.

  Importar `TipoDeCambio` y `MONEDAS_EN_DOLARES` de `app.universo.cambio` (importar, no
  modificar: si hiciera falta una variante, vive acá, en el paquete nuevo).
- `def armar_renta_variable(filas, cambio: TipoDeCambio) -> list[EspecieRentaVariable]` — mapea
  los dicts de la lectura usando `a_numero` de `app.universo.segmentacion` para los numéricos
  (maneja `Decimal` de asyncpg y `NaN`), un helper local para textos (recortar espacios, vacío →
  `None` — no importar `_texto`, es privado de `segmentacion`), `int(...)` con guarda para
  `operaciones`, y calcula `variacion` y `volumen_usd` con las dos funciones de arriba.

### 1d. Endpoint en `backend/app/api/v1/renta_variable.py` (el router vacío de la base común)

`GET /api/v1/renta-variable/especies?clase=accion|cedear`, mismo patrón de cursor que
`universo.py::vista_viva`:

```python
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db
from app.core.pagination import CursorParams, Page, build_page
from app.renta_variable import armar_renta_variable, leer_renta_variable
from app.universo.servicio import sanear_universo

router = APIRouter(prefix="/renta-variable", tags=["renta-variable"])


@router.get(
    "/especies",
    summary="Las acciones y CEDEARs del día, con puntas, variación y volumen en dólares",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def especies(
    conn: Annotated[object, Depends(get_db)],
    params: Annotated[CursorParams, Depends()],
    clase: Annotated[Literal["accion", "cedear"], Query(description="...")],
) -> Page[dict[str, object]]:
    saneado = await sanear_universo(conn)  # sólo por .cambio: el FX del día sale del universo, regla 3
    filas = await leer_renta_variable(conn)
    listado = [e for e in armar_renta_variable(filas, saneado.cambio) if e.clase_activo == clase]

    desde = params.decoded_cursor()
    if desde is not None:
        ultimo = str(desde.get("ticker", ""))
        listado = [e for e in listado if e.ticker > ultimo]

    filas_api = [e.como_dict() for e in listado[: params.limit + 1]]
    return build_page(filas_api, params.limit, lambda f: {"ticker": f["ticker"]})
```

Docstring del endpoint: por qué el tipo de cambio viene de `sanear_universo(conn).cambio` (el MEP
implícito se deriva de la renta fija del propio universo — regla 3 — y no hay otra fuente), y que
una clase sin filas hoy devuelve página vacía, no 404. `clase` es obligatorio y `Literal`: sin él
o con otro valor, FastAPI responde 422 solo. El montaje en `router.py` **ya lo hizo la base
común** — no tocar ese archivo.

### 1e. Tests backend (offline, sin Postgres)

**`backend/tests/test_renta_variable_logica.py`** — la lógica pura, sin app:
- `variacion_diaria(103.1, 100.0)` ≈ `0.031`; con `cierre_anterior=None` → `None`; con
  `precio=None` → `None` (GWT-3: no se estima).
- `volumen_en_dolares` con un `TipoDeCambio(valor=1000.0, pares=25)` construido a mano: ARS
  1_500_000 → 1_500.0; USD 2_000 → 2_000.0; moneda `None` → `None`; con
  `TipoDeCambio()` (sin valor) el ARS da `None` y **no** el crudo (GWT-2).
- `armar_renta_variable` no produce ninguna clave `rendimiento`/`naturaleza`/`segmento` en
  `como_dict()` (GWT-1 del lado del dato).

**`backend/tests/test_renta_variable_api.py`** — contrato HTTP, patrón
`FakeConexionInstrumentos` de `test_instrumentos_api.py` (fake que despacha por SQL) sobre el
`crear_app` de `conftest.py`:

```python
class FakeConexionRentaVariable:
    def __init__(self, universo=None, renta_variable=None):
        ...
    async def fetch(self, query, *_):
        self.consultas.append(query)
        if "clase_activo IN" in query:   # la lectura de RV
            return self.renta_variable
        return self.universo             # sanear_universo (renta fija, para el FX)
```

Con `universo` = un par de bonos de `test_instrumentos_api.py` (menos de 20 pares ⇒ FX no
disponible: caso real y declarado) y `renta_variable` = filas dict con las nueve columnas de la
lectura. Tests:
- `?clase=accion` devuelve sólo las acciones; `?clase=cedear` sólo los CEDEARs.
- Ninguna fila trae clave `rendimiento` (GWT-1).
- Fila ARS sin FX del día → `volumen_usd: null`, nunca el crudo (GWT-2); fila USD lo conserva.
- Fila con `cierre_anterior: None` → `variacion: null` (GWT-3); con ambos → el cociente.
- Paginación: `limit=1` en una clase con dos filas → `next_cursor` no nulo y la segunda página
  trae la otra.
- `?clase=bono` → 422; sin `clase` → 422; clase válida sin filas → `items: []`, 200.
- Sin base (`crear_app(None)`) → 503.

**Consolidación** — agregar (no reescribir) en los archivos existentes:
- `backend/tests/test_consolidacion_armado.py`: una fila de rueda con
  `precio_cierre_anterior=100.0` termina con `cierre_anterior: 100.0` en `filas_precios`, y con
  `0.0` termina `None` (semántica `_precio`).
- `backend/tests/test_consolidacion_persistencia.py`: `"cierre_anterior"` está en
  `COLUMNAS_PRECIOS` y por lo tanto en el SQL de `sql_precios()`.

## Parte 2 — Frontend

### 2a. Compartido: `frontend/src/lib/rentaVariable.ts` (archivo nuevo)

Schema, fetch y hook juntos, en zona compartida, con esta nota en el docstring del archivo:
**"F-026 (renta variable en el armador, tanda 9) importa de acá: el armador tiene prohibido
importar de `features/monitor/**` (precedente F-018), así que nada de este archivo puede mudarse
adentro del monitor."**

- `export const esquemaEspecieRentaVariable = z.object({...})` — las once claves de
  `EspecieRentaVariable.como_dict()`: `ticker: z.string()`, `clase_activo: z.string()`, y
  `precio`, `cierre_anterior`, `variacion` (fracción: 0.031 = 3,1% — documentarlo igual que hace
  `esquemaEspecie` con `rendimiento`), `volumen`, `volumen_usd`, `px_bid`, `px_ask` como
  `z.number().nullable()`, `moneda_cotizacion: z.string().nullable()`,
  `operaciones: z.number().nullable()`. **Sin campo `rendimiento`**: si el backend algún día lo
  mandara, no viaja a la tabla.
- `export type EspecieRentaVariable = z.infer<...>`
- `traerClaseEntera(clase: string)` — el mismo bucle de cursor de
  `features/monitor/hooks/useUniversoSegmento.ts` (leerlo como patrón, copiarlo, **no**
  importarlo): `apiFetch('/api/v1/renta-variable/especies?limit=200&clase=...')` con
  `esquemaPagina(esquemaEspecieRentaVariable)` de `@/lib/api/schemas`, siguiendo `next_cursor`
  hasta `null`, tope de 30 páginas con error explícito (nunca resultado truncado en silencio).
- `export function useRentaVariable(clase: string)` — `useQuery` con
  `queryKey: [...claves.mercado.todas, 'renta-variable', clase]` (derivada del prefijo `mercado`
  como hace `useSegmentos.ts`; **`queryKeys.ts` no se edita**) y
  `staleTime: TIEMPOS.mercado.staleTime`.

### 2b. Compartido: `frontend/src/components/TablaRentaVariable.tsx` (archivo nuevo)

La grilla de renta variable, hermana de `features/monitor/components/TablaUniverso.tsx` (leerla
entera y copiar su mecánica: `useVirtualizer` con contenedor de 520px y filas de 32px, orden por
clic asc/desc/ninguno con indicador ▲/▼ y `null` **siempre al final**, conteo "N de M especies"
siempre visible). No importa nada de `features/**`: la navegación entra por prop. Docstring del
archivo: **"Zona compartida a propósito: el monitor (F-052) la monta hoy y el armador (F-026,
tanda 9) la reusa — F-026 se engancha acá, no en `features/monitor/`."**

Props exactas:

```tsx
export function TablaRentaVariable({
  especies,
  onAbrirTicker,
}: {
  especies: EspecieRentaVariable[]
  /** Qué hacer al clickear una fila. El monitor pasa useAbrirInstrumento(); F-026 pasará lo suyo. */
  onAbrirTicker: (ticker: string) => void
})
```

Exportar también `FilaRentaVariable` (la fila suelta, mismas celdas, para que F-026 pueda
componerla distinto) y `PLANTILLA_COLUMNAS_RV`.

Columnas, en orden, todas ordenables por clic (campo → clave del dato):
1. **ticker** (mono, izquierda) → `ticker`
2. **precio** (mono, derecha; `fmtNumero(precio)` + `moneda_cotizacion` en `var(--dim)` al lado,
   como la celda de precio de `TablaUniverso`) → `precio`
3. **variación** (mono, derecha; `fmtPct(variacion * 100)` — `fmtPct` recibe **puntos**,
   verificado en `lib/fmt.ts` — con signo `+` explícito cuando es positiva; color
   `var(--pos)` si `> 0`, `var(--neg)` si `< 0`; `null` → `SIN_DATO`) → `variacion`
4. **volumen USD** (mono, derecha; `fmtCompacto(volumen_usd)`) → `volumen_usd`. **No hay columna
   de volumen crudo**: el crudo viaja en el dato para auditar, la columna comparable es la
   normalizada (regla 3). Ordenar acá ordena por `volumen_usd`, con los `null` al final.
5. **compra** (mono, derecha; `fmtNumero(px_bid)`) → `px_bid`
6. **venta** (mono, derecha; `fmtNumero(px_ask)`) → `px_ask`
7. **operaciones** (mono, derecha; `fmtNumero(operaciones, 0)`) → `operaciones`

`SIN_DATO` (`s/d`) para todo `null` — nunca celda muda. **No hay columna de rendimiento, ni de
duración, ni de paridad, ni de vencimiento**, y no se agrega ninguna en su lugar.

Debajo del conteo, la **nota de cobertura** (11px, `var(--dim)`, sólo los términos con conteo
mayor a cero, calculados sobre `especies` con un `useMemo`):
`"N sin cierre anterior (sin variación) · M sin puntas · K sin volumen en dólares"`. Es el GWT-3:
lo vacío se cuenta, no se disimula. Si todos los conteos son cero, la nota no se muestra.

**Estados de cero, declarados y sin mentir:**
- `especies.length === 0` (una clase sin filas hoy): "0 de 0 especies" y un párrafo
  "No hay {acciones|CEDEARs} en el universo de hoy." — no es error ni pantalla rota.
- **Primer día después de la migración** (caso real: `cierre_anterior` arranca `NULL` para todas
  las filas históricas y se llena recién con la primera corrida de ingesta posterior): toda la
  columna variación muestra `s/d` y la nota dice "N sin cierre anterior (sin variación)" con N =
  total. No se calcula una variación desde el histórico propio de `precios` para taparlo.
- Cero especies con puntas (ninguna corrida escribió `puntas` aún): las dos columnas en `s/d` y
  contadas en la nota.
- Sin tipo de cambio del día: las filas ARS quedan con volumen USD `s/d`, contadas, y el orden
  por volumen USD las manda al final (null al final, como siempre).

### 2c. Monitor: `frontend/src/features/monitor/MonitorPage.tsx` (modificar)

- Claves de renta variable, junto a los imports:
  `const CLAVES_RENTA_VARIABLE = ['accion', 'cedear']`.
- Pestañas: al `SelectorSegmento` se le pasan las claves de `/segmentos` **más**
  `CLAVES_RENTA_VARIABLE` cuando `segmentos.data.renta_variable > 0` (una pestaña sin nada atrás
  no es una pestaña). `ordenarSegmentos` de la base común ya las manda al final. Los nombres los
  pone `NOMBRE_SEGMENTO` (base común); esta feature no los define.
- Bifurcación: si `CLAVES_RENTA_VARIABLE.includes(activo)` se monta un componente nuevo
  `RentaVariableDelMonitor` (en el mismo archivo o en
  `features/monitor/components/RentaVariableDelMonitor.tsx`, a criterio del builder) en lugar de
  `UniversoDelSegmento`. Ese wrapper: `useRentaVariable(activo)` de `@/lib/rentaVariable`, los
  mismos estados de pending/error con reintentar que ya usa `UniversoDelSegmento`, y
  `<TablaRentaVariable especies={...} onAbrirTicker={useAbrirInstrumento()} />`.
  **Sin `FiltrosNumericos`** (sus tres campos son rendimiento mín/máx y duración máx — magnitudes
  que la renta variable no tiene; no se inventa un filtro para llenar el hueco), **sin
  `CurvaSegmento`** (es rendimiento vs duración: no hay ejes que dibujar) y **sin
  `unidadDeNaturaleza`** (no hay naturaleza que rotular).
- El texto de exclusión (hoy líneas ~77–80: "N de renta variable y M sin segmento no se muestran
  acá") **cambia**: la renta variable ya se muestra. Queda:
  `"{fmtNumero(segmentos.data.sin_segmento, 0)} sin segmento no se muestran acá."` — GWT-4: los
  `sin_segmento` siguen declarados con su cantidad, igual que antes.
- El reset de filtros al cambiar de pestaña queda como está.

Nada más del monitor se toca: `TablaUniverso`, `FiltrosNumericos`, `CurvaSegmento`, hooks y
`lib/schema.ts` de renta fija quedan intactos.

### 2d. Tests frontend

**`frontend/src/features/monitor/__tests__/MonitorPage.test.tsx`** — una sola edición permitida:
la aserción literal de la línea ~247, `/1\.417 de renta variable y 535 sin/`, pasa a
`/535 sin segmento no se muestran acá/` (y verificar que ningún otro test del archivo dependa del
texto viejo). No tocar el resto: el stub de `offsetHeight`/`offsetWidth` (líneas ~25–33), el mock
de fetch y los GWT de F-038 quedan como están — con `renta_variable: 1417` en su
`segmentosResponse()` las pestañas nuevas aparecen, pero esos tests no interactúan con ellas.

**`frontend/src/features/monitor/__tests__/RentaVariable.test.tsx`** — archivo nuevo, patrón
calcado de `MonitorPage.test.tsx`: mismo `vi.mock('@/lib/supabase', ...)`, **mismo stub de
`offsetHeight` (520) / `offsetWidth` (800) en `beforeAll`** — sin él la virtualización no
renderiza ninguna fila en jsdom —, mismo `renderizar()` con `MemoryRouter` y `FichaFalsa`. El
mock de fetch responde `/api/v1/universo/segmentos` (con `renta_variable > 0`),
`/api/v1/universo/emisiones/especies` (una página mínima, para el segmento default) y
`/api/v1/renta-variable/especies` despachando por `clase`. Fixtures: dos acciones — GGAL en ARS
con `volumen: 1_500_000_000` pero `volumen_usd: 1_000_000`, y LOMA en USD con
`volumen: 2_000_000` y `volumen_usd: 2_000_000` — más una tercera con `cierre_anterior: null`,
`px_bid: null`, `px_ask: null`, `volumen_usd: null`.

Un test por GWT:
- **GWT-1**: clic en la pestaña de acciones → están las cabeceras precio / variación /
  volumen USD / compra / venta, y `screen.queryByText(/rendimiento/i)` y
  `screen.queryByText(/TIR/)` devuelven `null` — ni la columna ni nada en su lugar.
- **GWT-2**: orden desc por la cabecera "volumen USD" → LOMA (2,0 MM USD) queda antes que GGAL
  (1,0 MM USD) aunque el crudo de GGAL sea 750 veces mayor; la fila con `volumen_usd: null` queda
  última.
- **GWT-3**: la fila con `cierre_anterior: null` muestra `s/d` en variación, las puntas nulas
  muestran `s/d`, y la nota de cobertura declara "1 sin cierre anterior" y "1 sin puntas".
- **GWT-4**: con la pestaña de acciones activa, el texto "535 sin segmento no se muestran acá"
  sigue visible (los excluidos no desaparecen por mirar renta variable).
- Extra (mecánica heredada): clic en una fila navega a `ficha de GGAL`; el conteo "3 de 3
  especies" está visible.

## Lo que esta feature NO hace — leer antes de escribir una celda

- **NO agrega columna de rendimiento a las pestañas de renta variable. Ni TIR, ni "rendimiento
  estimado", ni la variación disfrazada de rendimiento, ni una columna vacía "para cuando
  haya".** Una acción no tiene TIR y la regla 2 sigue valiendo aunque F-051 haya hecho que la TIR
  exista para todo lo demás — es la línea innegociable de la duda 8 del plan de ejecución. El
  contrato del backend tampoco la manda: `EspecieRentaVariable` no tiene el campo.
- NO estima la variación cuando falta el cierre anterior (ni desde el histórico de `precios`, ni
  desde una hermana, ni desde otra especie). Vacía y contada.
- NO deduce la moneda de una acción por el sufijo del ticker: esa regla es de especies de
  liquidación de renta fija. Sin `moneda_cotizacion` declarada, `volumen_usd` es `null`.
- NO ordena ni compara por volumen crudo; la columna comparable es `volumen_usd`.
- NO mete la renta variable en `EspecieUniverso`, ni en `segmentar()`, ni en los endpoints de
  `/universo`: el paquete nuevo existe justamente para no tocar eso.
- NO trae tipo de cambio de una fuente externa: sale de `sanear_universo(conn).cambio`, siempre.
- NO toca los `sin_segmento`: siguen fuera y declarados, como hasta ahora.

## PROHIBIDO tocar

`backend/app/universo/segmentacion.py` · `backend/app/universo/cambio.py` ·
`backend/app/universo/lectura.py` · `backend/app/universo/servicio.py` ·
`backend/app/api/v1/universo.py` · `backend/app/api/v1/router.py` (la base común ya montó el
router de renta variable; si no lo hizo, FRENAR) · en `armado.py`, **todo salvo la única línea de
1b** — en particular la lógica de métricas que dejó F-051 (`_metricas_de`, `metricas_previas`,
`METRICAS_POR_TICKER`) · `backend/app/calendario/**` y `backend/app/api/v1/instrumentos.py`
(F-040 trabaja ahí) · `frontend/src/features/armador/**` (F-017 y F-024) ·
`frontend/src/features/instrumento/**` (F-040; `useAbrirInstrumento` se importa, no se edita) ·
`frontend/src/lib/api/queryKeys.ts` (derivar del prefijo `mercado`, como `useSegmentos.ts`) ·
`frontend/src/components/SelectorSegmento.tsx` (se consume; las claves las puso la base común) ·
`frontend/src/lib/fmt.ts` y `frontend/src/lib/claseActivo.ts` (se consumen) ·
`TablaUniverso.tsx`, `FiltrosNumericos.tsx`, `CurvaSegmento.tsx` y los hooks de renta fija del
monitor · `package.json` / `requirements.txt` (no hay dependencia nueva) ·
`app/__tests__/rutas.test.tsx` · nada de `git add` / `git commit` (los commits los hace el cierre
de la tanda) · el backend no importa de `tools/`.

## Reglas del dominio que esta pantalla NO puede violar

1. **Regla 1 — nunca inventar un dato.** Lo que BYMA no publica queda `null` en el API y `s/d` en
   la celda, contado en la nota de cobertura. Ni variación estimada, ni moneda deducida del
   ticker, ni volumen crudo haciéndose pasar por dólares.
2. **Regla 2 — naturalezas distintas no comparten columna.** La renta variable no tiene
   naturaleza de tasa: sus pestañas no tienen columna de rendimiento ni nada presentado en su
   lugar, y siguen siendo pestañas separadas — nunca una grilla mezclada con renta fija.
3. **Regla 3 — nada se compara entre monedas sin normalizar.** El orden por volumen es sobre
   `volumen_usd`, derivado con el MEP implícito del propio universo (`saneado.cambio`), jamás de
   una fuente externa.
4. **Lo excluido se declara.** Los `sin_segmento` siguen contados en el monitor; los faltantes de
   cierre anterior, puntas y volumen USD se cuentan bajo la tabla.
5. **El cierre anterior es dato publicado** (`previousClosingPrice`), la variación es un cociente
   entre dos datos publicados, y las dos cosas viajan juntas para que se pueda auditar una con la
   otra — igual que `volumen` y `volumen_usd`.

## Test Strategy

Un test por GWT, en las dos puntas:
- **Backend** (offline, patrón `backend/tests/`): lógica pura en
  `test_renta_variable_logica.py`, contrato HTTP en `test_renta_variable_api.py` con un fake que
  despacha por SQL (patrón `FakeConexionInstrumentos` de `test_instrumentos_api.py` sobre el
  `crear_app` de `conftest.py`), y los dos tests de consolidación de 1e. Detalle en 1e.
- **Frontend** (patrón `MonitorPage.test.tsx`, stub de `offsetHeight`/`offsetWidth` incluido):
  `RentaVariable.test.tsx` nuevo con un test por GWT, más la actualización de la aserción del
  texto de exclusión. Detalle en 2d.

## Comandos de verificación

```
Backend (cd /Users/jeroniki/Documents/Github/10-Swaper/backend):
  source venv/bin/activate
  python -m pytest tests/ -x -q        # pyproject ya trae addopts = "-m 'not integration'"
  ruff check . && ruff format --check .
Frontend (cd /Users/jeroniki/Documents/Github/10-Swaper/frontend):
  npx vitest run src/features/monitor
  npm run lint
```

No correr la suite entera del frontend ni `vitest run` sin filtro: F-017, F-024 y F-040 trabajan
en paralelo en este working tree y sus tests a medio hacer no son asunto de esta feature; la
suite completa la corre el cierre de la tanda.

## Al terminar, reportar

- Archivos creados y modificados (con la migración y su rollback nombrados con su timestamp
  real), y la confirmación explícita de las dos precondiciones de la base común.
- Resultado textual de los cuatro comandos.
- Si la migración se aplicó a la base o quedó sólo escrita, y qué pasó con la primera corrida
  posterior (si la hubo): cuántas filas quedaron con `cierre_anterior`.
- Cualquier punto donde el plan no cerró contra la realidad del código y qué se hizo — que debe
  ser: frenar esa parte y reportarla, no improvisar.
