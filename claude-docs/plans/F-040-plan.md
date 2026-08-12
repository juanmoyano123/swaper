# Feature Plan: F-040 — Sensibilidad del precio por repricing completo

## Overview
- **Source**: spec en `claude-docs/planning/plan.md` (líneas ~1864–1896, "#### F-040") · verificación
  original del método en `docs/ESTADO.md` (línea ~254) · referencia del motor en `tools/cupones.py:308`
  (`retorno_por_tir`) y `tools/detectar_swaps.py:71` (escenarios) y `:511` (`hoja_sensibilidad`)
- **Complexity**: S/M — una función de matemática portada, un endpoint que copia un patrón existente,
  un panel nuevo en una ficha existente
- **Modo**: plan prescriptivo. Si algo no cierra contra la realidad del código, **frenar y
  reportar**, no improvisar.

## Qué es

En la ficha del instrumento (F-039) se agrega una tabla de escenarios: cuánto se movería el precio
del bono si su TIR comprimiera o se abriera N puntos básicos. El cálculo es **repricing completo del
cashflow contractual** —se descuentan todos los flujos futuros a la TIR del escenario y se compara
contra descontarlos a la TIR de hoy—, **nunca** la aproximación lineal por duración: en bonos largos
la aproximación subestima fuerte la suba ante compresiones grandes, y esos son justamente los
escenarios que interesan. La tabla se expresa siempre en la unidad de rendimiento del propio
instrumento, jamás en la de otro segmento. Sin cashflow o sin TIR descontable, se declara que no se
puede calcular, con motivo — no se estima, no se degrada a duración.

## GWT (criterios de aceptación, literales del plan)

```
GIVEN un bono con cashflow completo
WHEN se calcula la sensibilidad
THEN el precio de cada escenario sale de descontar el cashflow contractual a la TIR del escenario, y
     no de multiplicar por la duración modificada

GIVEN la tabla externa de verificación con movimientos de hasta +91 %
WHEN se corre el repricing
THEN el desvío máximo contra esa tabla es de 0,12 pp

GIVEN un instrumento sin cashflow disponible
WHEN se pide la sensibilidad
THEN se declara que no se puede calcular, y no se cae a la aproximación por duración
```

**Sobre GWT-2, verificado contra el repo (07/08/2026): la tabla externa NO está versionada.** La
verificación de 0,12 pp se hizo en su momento contra la tabla de sensibilidad del monitor de mesa
(`mesaifa.netlify.app` — ESTADO.md, "Validaciones contra fuentes externas": AL30, AL29, GD30, AE38,
AL41, GD46 × 3 escenarios), leyendo números publicados en pantalla. Ese monitor tiene **prohibida**
la conexión (regla 10) y los valores no quedaron guardados en `data/`, `referencia/` ni
`docs/historial/`. Por lo tanto GWT-2 **no se puede automatizar tal cual está escrito** y este plan
lo reemplaza por la cadena de dos eslabones que ya usa `tests/test_calendario_paridad_motor.py`:
el motor fue quien se verificó contra esa tabla, y acá se prueba que el port del backend reproduce
al motor exacto (sección Test Strategy). **No inventar un número de tolerancia sin fuente.**

## Precondición dura: F-051 tiene que estar cerrada

F-040 es de la tanda 8b y **consume** la matemática que F-051 (tanda 8a) dejó escrita en
`backend/app/calendario/metricas.py`: `anios_entre(desde, hasta)` (días/365,25),
`valor_presente(t, cf, tasa)`, y las constantes `TASA_PISO = -0.99` y `DIAS_POR_ANIO = 365.25`,
además de `duracion_modificada` que los tests usan como cota. **Al arrancar, lo primero**:

1. Verificar que `backend/app/calendario/metricas.py` existe y define `valor_presente` y
   `anios_entre`. Al momento de escribir este plan el archivo **todavía no existe** (F-051 está en
   la tanda anterior y aún no cerró): si al arrancar sigue sin existir, **FRENAR y reportar** —
   significa que F-051 no terminó y F-040 no puede empezar.
2. Leer las firmas reales de ese módulo antes de escribir una línea. Las firmas citadas en este plan
   salen del plan de F-051; si la realidad difiere (nombres, orden de parámetros), adaptarse a la
   realidad del código y decirlo en el reporte. Si difiere en semántica (por ejemplo, no hay ninguna
   función de valor presente), FRENAR y reportar.

**F-040 no reescribe ni modifica nada de lo que F-051 dejó**: sólo agrega una función nueva al final
del módulo (ver 1a). Agregar es aceptable porque F-051 ya cerró cuando esta feature corre; editar lo
existente no lo es.

## Parte 1 — Backend

### 1a. `retorno_por_tir` en `backend/app/calendario/metricas.py`

**Dónde**: se agrega al final de `metricas.py`, no en un módulo nuevo. Justificación: es matemática
de descuento pura y consume `valor_presente` + `anios_entre` + `TASA_PISO` de ese mismo archivo; un
módulo aparte partiría la matemática financiera del calendario en dos lugares y duplicaría o
importaría en cadena las mismas tres piezas. El archivo lo creó F-051, que ya cerró — agregarle una
función con su test es exactamente el mismo gesto que F-039 hizo sobre `instrumentos/`.

**Qué**: el port de `tools/cupones.py:308` (`retorno_por_tir`) a Python puro sobre `Sequence[Pago]`.
El motor usa pandas y **el backend tiene prohibido importar de `tools/`**; la matemática se copia
con su razón de ser, igual que hizo `app/calendario/cupones.py` (leer su docstring de cabecera).

```python
def retorno_por_tir(
    pagos: Sequence[Pago],
    tir_actual: float | None,
    deltas: Sequence[float],
    hoy: date,
) -> dict[float, float] | None:
    """Cuánto se movería el precio si la TIR del bono cambiara.

    Repricing completo del cashflow contractual, no una aproximación por duración: se descuentan
    todos los flujos futuros a la TIR nueva y se compara contra descontarlos a la TIR de hoy. En
    bonos largos la aproximación lineal subestima fuerte la suba ante compresiones grandes, y
    justamente esos son los escenarios que interesan (F-040). Port de `tools/cupones.py`.

    `deltas` en fracciones (-0.01 = comprime 100 bps). Devuelve {delta: retorno} o `None` si falta
    TIR, no quedan pagos futuros o el valor presente base no es positivo. Un delta que deje la tasa
    en `TASA_PISO` o por debajo se omite del resultado: descuento degenerado, no se reporta un
    número inventado.
    """
```

Cuerpo, calcado del motor (leerlo antes de escribir):
- `if tir_actual is None: return None` (el chequeo `pd.isna` del motor no aplica: acá no hay pandas).
- `futuros = [p for p in pagos if p.fecha > hoy]`; sin futuros → `None`.
- `t = [anios_entre(hoy, p.fecha) for p in futuros]` y `cf = [p.total for p in futuros]` — `total`
  es el `cash_flow` de la fuente, el mismo campo que usa el motor (`fut["cash_flow"]`). No se
  recalcula como capital + interés (ver docstring de `Pago`).
- `base = valor_presente(t, cf, tir_actual)`; `base <= 0` → `None`.
- Por cada `d` en `deltas`: `y = tir_actual + d`; `if y <= TASA_PISO: continue`;
  `out[d] = valor_presente(t, cf, y) / base - 1`.
- `return out or None`.

`Pago` se importa de `app.calendario.cupones` **sólo si `metricas.py` no lo importa ya** — leer sus
imports reales primero. No tocar ninguna función existente del archivo.

### 1b. Escenarios estándar

Los escenarios en bps son los del motor — `tools/detectar_swaps.py:71`:

```python
ESCENARIOS_TIR_DEFAULT = "-500,-400,-300,-200,-100,0,100,200"
```

Van como constante en `backend/app/api/v1/instrumentos.py` (el consumidor los fija, igual que el
motor los fija en `detectar_swaps` y no en `cupones`):

```python
# Escenarios de movimiento de la TIR, en bps. Los mismos del motor (tools/detectar_swaps.py:71):
# cinco compresiones, el escenario nulo y dos aperturas. El 0 no es decorativo — es la
# autoconsistencia del repricing a la vista (retorno exactamente 0).
ESCENARIOS_BPS: tuple[int, ...] = (-500, -400, -300, -200, -100, 0, 100, 200)
```

y se convierten a fracciones al llamar (`d / 10_000`).

### 1c. Endpoint `GET /instrumentos/{ticker}/sensibilidad`

En `backend/app/api/v1/instrumentos.py`, cuarto endpoint del router existente. **El patrón exacto a
copiar es `/cronograma`** (mismo archivo): `leer_cashflow(conn)` + `indexar_cronograma` +
`.pagos_de(raiz_emision(ticker))`, docstring con el porqué, `responses={503: ...}`. El router ya
está montado en `router.py` — **no tocar `router.py`**.

**La TIR vigente sale de la especie del universo saneado**, campo `rendimiento` (en **fracción**:
0.12 = 12 %), que con F-051 ya es cálculo propio para todo lo que tenga precio y cronograma en su
moneda. Para obtener la especie, agregar en el mismo archivo:

```python
async def _especie_de(conn: Any, ticker: str) -> EspecieUniverso | None:
    """La especie del universo saneado de hoy, o `None` si el ticker no está."""
    saneado = await sanear_universo(conn)
    return next((e for e in saneado.especies if e.ticker == ticker), None)
```

y reescribir el cuerpo de `_moneda_de_emision` para que la use (`especie = await _especie_de(...)`;
mismo comportamiento, cero duplicación). Importar `EspecieUniverso` de `app.universo.segmentacion`.

**Regla 2, crítica — qué TIR se puede descontar y cuál no.** `rendimiento` viene de
`rendimiento_declarado` (`backend/app/universo/segmentacion.py:100`): devuelve la magnitud del
segmento, y para `tasa_fija` esa magnitud es **TNA nominal**, que no es una tasa de descuento
efectiva anual — descontar flujos con ella sería usar una unidad que no corresponde. El criterio
prescripto, derivado de `NATURALEZA_TASA`:

- **Se calcula** cuando `especie.naturaleza` es `tir_usd`, `tir_dolar_linked` o `tasa_real_cer`:
  las tres son tasas efectivas anuales que descuentan el flujo contractual en su propia unidad. El
  cociente `VP(y+d)/VP(y)` usa los mismos flujos arriba y abajo, así que el resultado es un retorno
  porcentual del precio en la unidad del instrumento, sin conversión de moneda.
- **No se calcula y se declara** cuando `especie.naturaleza == "tna_nominal_ars"` (cubre
  `tasa_fija`, `badlar` y `tamar`). Dos razones, ambas van al motivo y al docstring: la TNA nominal
  no es una tasa efectiva descontable, y en badlar/tamar el cupón es flotante — el "cashflow
  contractual" cargado es una proyección con tasas asumidas, no un contrato fijo que se pueda
  repreciar. La respuesta correcta es no calcular y declararlo; **jamás** descontar con una unidad
  que no corresponde ni convertir la TNA a otra cosa.
- El escenario se expresa **siempre** en la unidad del instrumento (`naturaleza` /
  `naturaleza_nombre` viajan en la respuesta): un movimiento de −200 bps de un bono CER es sobre su
  tasa real, no sobre una TIR en dólares.

**Por qué esto no contradice a F-051, que excluye CER y dollar-linked.** No es una discrepancia
entre los dos planes: es que las dos features necesitan cosas distintas del mismo flujo. F-051
compara un valor presente contra un precio observado, y eso exige que los dos estén en la misma
unidad — con flujos contractuales sin ajustar por CER y un precio en pesos que sí lo incorpora, esa
igualdad no se puede plantear. F-040 devuelve un **cociente** de valores presentes del mismo flujo:
la unidad aparece en el numerador y en el denominador y se cancela, así que el retorno porcentual es
válido aunque el nivel absoluto del precio no sea calculable. Lo que F-040 sí necesita es una TIR
vigente en la unidad correcta, y para CER esa tasa real la publica IAMC. Si un día IAMC deja de
publicarla para un ticker, ese ticker cae en `calculable: false` con motivo `sin_tir`, que es la
rama que el plan ya prescribe — no hay que inventarle una tasa.

**Forma de la respuesta** (siempre 200 con la declaración; 503 lo maneja `get_db` como en los otros
tres endpoints):

```jsonc
{
  "ticker": "AL30D",
  "tir_actual": 0.121,            // fracción, en la unidad de `naturaleza`; null si no hay
  "naturaleza": "tir_usd",         // null si el ticker no está en el universo de hoy
  "naturaleza_nombre": "TIR en dólares (hard dollar)",
  "calculable": true,
  "motivo": null,                  // string con el porqué cuando calculable es false
  "escenarios": [                  // vacío cuando calculable es false
    { "delta_bps": -500, "tir_escenario": 0.071, "retorno": 0.1834 },
    { "delta_bps": 0,    "tir_escenario": 0.121, "retorno": 0.0 }
    // ... uno por cada escenario no omitido, en el orden de ESCENARIOS_BPS
  ],
  "omitidos_bps": []               // deltas cuya tasa quedaba <= TASA_PISO: se omiten y se declaran
}
```

`retorno` y `tir_escenario` viajan como fracciones crudas, sin redondear — el formateo es del
frontend, como en el resto del API.

**Cadena de decisiones del endpoint, en orden** (cada rama corta con `calculable: false`, su
`motivo`, `escenarios: []` y `omitidos_bps: []`):

1. `especie = await _especie_de(conn, ticker)` es `None` → motivo
   `"no está en el universo de hoy: no hay TIR vigente para descontar"`. **200 y no 404**: este
   endpoint responde una pregunta derivada y GWT-3 pide declaración con motivo; el 404 de "el
   ticker no existe" ya lo da la ficha (`GET /instrumentos/{ticker}`), que es quien afirma
   existencia. `naturaleza`/`naturaleza_nombre`/`tir_actual` van en `null`.
2. `especie.naturaleza == "tna_nominal_ars"` → motivo
   `"el rendimiento de este segmento es TNA nominal en pesos, no una tasa efectiva descontable: no se calcula"`.
3. `especie.rendimiento is None` → motivo `"sin TIR vigente publicada ni calculada hoy"`.
4. `pagos = indexar_cronograma(await leer_cashflow(conn)).pagos_de(raiz_emision(ticker))` vacío →
   motivo `"sin cronograma de pagos en la fuente"` (el mismo texto que `Flujos.motivo_de`). Es el
   GWT-3: **no se cae a la aproximación por duración**, ni acá ni en ninguna otra rama.
5. `hoy = date.today()` (misma convención `hoy or date.today()` que `app/calendario/servicio.py`).
   Si no hay ningún pago con `fecha > hoy` → motivo `"sin pagos futuros: la emisión ya venció"`.
6. `r = retorno_por_tir(pagos, especie.rendimiento, [d / 10_000 for d in ESCENARIOS_BPS], hoy)`.
   Si es `None` (base no positiva) → motivo
   `"valor presente no positivo a la TIR vigente: no hay base de repricing"`.
7. Éxito: `escenarios` con los deltas presentes en `r`, en el orden de `ESCENARIOS_BPS`, con
   `tir_escenario = especie.rendimiento + d`; `omitidos_bps` con los que la guardia del piso dejó
   afuera. Lo excluido se declara, no desaparece.

### 1d. Tests backend

Ver Test Strategy. No tocar ningún test existente salvo **agregar** casos a
`tests/test_instrumentos_api.py` (archivo propio de la ficha, nadie más lo toca en la tanda 8b).

## Parte 2 — Frontend (`frontend/src/features/instrumento/`)

### 2a. `lib/schema.ts` — el contrato

Agregar al final del archivo existente (no tocar los esquemas de F-039):

```ts
export const esquemaEscenarioSensibilidad = z.object({
  delta_bps: z.number(),
  /** Fracción en la unidad del instrumento, igual que `rendimiento`: multiplicar por 100 recién al formatear. */
  tir_escenario: z.number(),
  /** Fracción: 0.18 es +18 % de precio. Repricing completo, nunca duración por delta. */
  retorno: z.number(),
})

export const esquemaSensibilidad = z.object({
  ticker: z.string(),
  tir_actual: z.number().nullable(),
  naturaleza: z.string().nullable(),
  naturaleza_nombre: z.string().nullable(),
  calculable: z.boolean(),
  /** El porqué cuando no se puede calcular. Se muestra tal cual: la declaración es el dato. */
  motivo: z.string().nullable(),
  escenarios: z.array(esquemaEscenarioSensibilidad),
  omitidos_bps: z.array(z.number()),
})

export type Sensibilidad = z.infer<typeof esquemaSensibilidad>
```

### 2b. `hooks/useSensibilidadInstrumento.ts` — query independiente

Archivo nuevo, copiando el patrón de `hooks/useCronogramaInstrumento.ts` (docstring incluida, con
su porqué). **Query independiente con `retry: false` y su propio isPending/isError**: el módulo de
la ficha declara que sus queries son independientes — "una falla en el cronograma no puede tumbar
la ficha de precios" — y la sensibilidad entra al mismo régimen.

```ts
export function useSensibilidadInstrumento(ticker: string | undefined) {
  return useQuery({
    queryKey: [...claves.mercado.todas, 'sensibilidad', ticker ?? ''] as const,
    queryFn: () => apiFetch(`/api/v1/instrumentos/${ticker}/sensibilidad`, esquemaSensibilidad),
    enabled: ticker !== undefined,
    staleTime: TIEMPOS.mercado.staleTime,
    retry: false,
  })
}
```

**Decisión de clave, tomada**: cuelga del prefijo `mercado`, no de `referencia`. La sensibilidad
depende de la TIR vigente, que cambia con cada refresh de precios; `referencia` tiene
`staleTime: Infinity` (`frontend/src/app/queryClient.ts`) y dejaría en pantalla una tabla calculada
sobre una TIR vieja sin que nadie lo note. Es el criterio inverso —y por el mismo motivo— que llevó
al cronograma a `referencia` (cambia por ingesta, no por precio). **`queryKeys.ts` está PROHIBIDO
editar**: la clave se deriva del prefijo con el mismo gesto que `useSegmentos.ts`
(`[...claves.mercado.todas, 'segmentos']`) y `useCronogramaInstrumento.ts`. No usar
`claves.mercado.instrumento(ticker)` — esa es la clave de la ficha y las pisaría. `TIEMPOS` se
importa de `@/app/queryClient` como hace `useSegmentos`.

### 2c. `FichaInstrumento.tsx` — el quinto panel

Hoy tiene cuatro `<Panel>`: monedas, Ficha, Condiciones de emisión, Cronograma. F-040 agrega un
**quinto `<Panel rotulo="Sensibilidad">` inmediatamente después de Cronograma**, con su bloque:

- En `FichaInstrumento`, junto a las otras tres queries:
  `const sensibilidadQuery = useSensibilidadInstrumento(ticker)`.
- Al final del `<div>` contenedor:

```tsx
<Panel rotulo="Sensibilidad">
  <BloqueSensibilidad query={sensibilidadQuery} />
</Panel>
```

- `BloqueSensibilidad` (componente nuevo en el mismo archivo, patrón `BloqueCronograma`):
  - `isPending` → `<EstadoCarga que="la sensibilidad del precio" />`.
  - `isError` → `<EstadoError error={query.error} onRetry={() => void query.refetch()} />`.
  - `calculable: false` → `<EstadoVacio titulo="No se puede calcular la sensibilidad."
    detalle={motivo} />` con el motivo del backend tal cual. **Acá no se muestra ninguna
    alternativa**: ni duración × delta, ni un rango estimado. GWT-3.
  - Éxito → tabla `className="mono"` como la del cronograma, tres columnas:
    - **movimiento**: `delta_bps` con signo explícito (`+100 bps`, `−500 bps`; el 0 como `0 bps`).
    - **TIR escenario (unidad)**: cabecera rotulada con
      `unidadDeNaturaleza(data.naturaleza ?? '')` de `@/components/SelectorSegmento` (ya importado
      en este archivo) — la columna declara su unidad, siempre; valor
      `fmtPct(esc.tir_escenario * 100)`.
    - **retorno del precio**: `fmtPct(esc.retorno * 100)`.
    **Ojo con `fmtPct`** (`frontend/src/lib/fmt.ts`, verificado): recibe **puntos, no fracción**
    (7.27 → "7,27%"); la API manda fracciones, así que se multiplica por 100 **al formatear, nunca
    antes** — el mismo contrato que ya cumple `rendimiento` en `GrillaFicha`.
  - Nota al pie (mismo estilo 10.5 px `var(--dim)` que las otras):
    "Repricing completo del cashflow contractual a la TIR de cada escenario — no es la aproximación
    lineal por duración."
  - Si `omitidos_bps` no está vacío, segunda línea de nota: "N escenarios omitidos: la TIR
    resultante quedaría en −99 % o menos y el descuento degenera." Lo excluido se declara.
  - `SIN_DATO`/`NO_APLICA` no deberían hacer falta en la tabla (los escenarios que llegan siempre
    traen número); si un diseño intermedio los necesita, salen de `@/lib/fmt`, no de literales.

### 2d. Tests frontend

Archivo nuevo `frontend/src/features/instrumento/__tests__/Sensibilidad.test.tsx` — **no** editar
`FichaInstrumento.test.tsx` (es de F-039 y agranda el riesgo de conflicto). Copiar su patrón
completo: mock de `@/lib/supabase` sin sesión, `vi.stubGlobal('fetch', ...)` despachando por ruta
exacta; las fixtures de ficha/condiciones/cronograma se reescriben localmente (mínimas) más la ruta
nueva `/api/v1/instrumentos/{t}/sensibilidad`. Ver Test Strategy.

## PROHIBIDO tocar

- `tools/**` — se **lee** como referencia; el backend jamás importa de ahí (ni los archivos nuevos
  de `app/`; los tests sí pueden, siguiendo el mecanismo exacto de `test_calendario_paridad_motor.py`).
- Todo lo existente en `backend/app/calendario/metricas.py` (lo escribió F-051; sólo se **agrega**
  `retorno_por_tir` al final) · `backend/app/calendario/cupones.py`, `grilla.py`, `lectura.py`,
  `servicio.py`, `alertas.py` (se consumen, no se editan).
- `backend/app/api/v1/router.py` (el router de instrumentos ya está montado) ·
  `backend/app/universo/**` · `backend/app/ingesta/consolidacion/armado.py` (lo toca F-052).
- `backend/app/renta_variable/**` y cualquier migración: son de F-052.
- `frontend/src/lib/api/queryKeys.ts` · `frontend/src/features/instrumento/InstrumentoPage.tsx` ·
  `frontend/src/features/instrumento/InstrumentoDrawer.tsx` (el plan de F-039 los marca intocables).
- `frontend/src/features/instrumento/__tests__/FichaInstrumento.test.tsx` (de F-039; el test nuevo
  va en archivo propio) · `frontend/src/app/__tests__/rutas.test.tsx`.
- **`frontend/src/features/armador/**`** (F-017 y F-024 trabajan ahí en paralelo) ·
  **`frontend/src/features/monitor/**`** y **`frontend/src/components/**`** (F-052) — de monitor y
  components sólo se **importa** lo ya exportado (`Panel`, `SelectorSegmento` vía los imports que la
  ficha ya tiene), nunca se edita.
- `package.json` · `backend/requirements.txt` · `backend/pyproject.toml`.
- Nada de `git add` / `git commit`: el cierre de la tanda es de quien coordina.

Lo que F-040 **sí** toca y nadie más en la tanda 8b: `backend/app/api/v1/instrumentos.py`,
`backend/app/calendario/metricas.py` (sólo agregar), `backend/tests/test_instrumentos_api.py`,
tests nuevos de calendario, y `frontend/src/features/instrumento/**` (menos los tres archivos
prohibidos de arriba).

## Reglas del dominio que esta feature NO puede violar

1. **Regla 6**: el repricing es determinístico — descuento del flujo contractual, sin estimación.
2. **Regla 2**: la TIR del escenario y el retorno se expresan en la unidad del instrumento, con su
   rótulo; una TNA nominal no se descuenta ni se convierte — se declara que no se calcula.
3. **Regla 1**: sin cashflow, sin TIR o con descuento degenerado no hay número: hay declaración con
   motivo. No se cae a duración × delta (GWT-3), no se rellena, no se infiere.
4. Lo excluido se declara: los escenarios omitidos por el piso de tasa viajan en `omitidos_bps` y se
   nombran en pantalla.
5. El cronograma se busca por `raiz_emision(ticker)` — lookup, jamás generación de tickers.
6. Regla 10: la tabla del monitor de mesa no se consulta, no se scrapea, no se "reconstruye". La
   regresión es contra el motor versionado, que es la cadena de verificación legítima.

## Test Strategy

### Backend — matemática: `backend/tests/test_calendario_sensibilidad.py` (nuevo)

Patrón offline puro de `test_calendario_cupones.py`: `HOY = date(2026, 8, 7)` fija, helper `pago()`
local (o construir `Pago` directo), sin base de datos. Como la tabla de 0,12 pp no está versionada
(ver arriba), la verificación prescripta es:

1. **Autoconsistencia**: repricing a delta 0 devuelve retorno exactamente `0.0` (no "casi cero":
   `VP(y)/VP(y) - 1` es idénticamente cero).
2. **Signo**: suba de TIR (+100 bps) → retorno negativo; compresión (−100 bps) → positivo.
3. **Monotonía**: sobre los ocho deltas estándar, el retorno decrece estrictamente al crecer el
   delta.
4. **La duración modificada como cota, no como umbral**: con un bono largo (pagos a 5–10 años),
   comparar contra la aproximación lineal `−dur_mod × delta` calculada con `duracion_modificada`
   de `metricas.py` (leer su firma real; si no existe con ese nombre, FRENAR y reportar):
   - compresión grande (−300 bps): `retorno > dur_mod × 0.03` — el repricing da MÁS suba que la
     aproximación lineal, que es el argumento de la ficha;
   - suba grande (+200 bps, y el máximo disponible): `|retorno| < dur_mod × 0.02` — cae MENOS de lo
     que la recta dice.
   Las dos desigualdades son consecuencia exacta de la convexidad de un flujo positivo: no llevan
   tolerancia y **no se les inventa una**.
5. **Guardia del piso**: con `tir_actual = 0.02` y `deltas = (-1.02, 0.0)`, el resultado contiene
   sólo la clave `0.0` — el delta degenerado se omite, no da un número. Con todos los deltas
   degenerados, el resultado es `None`.
6. **Faltantes**: `tir_actual=None` → `None`; sin pagos futuros → `None`; todos los pagos pasados →
   `None`.

### Backend — regresión contra el motor (el sustituto declarado de GWT-2)

En el mismo archivo (o sección aparte), seguir **exactamente** el mecanismo de
`test_calendario_paridad_motor.py` — incluida su forma de importar `tools/` y de saltearse si los
archivos versionados no están—: sobre `data/output/cashflow_completo.csv`, para AL30, GD30, AE38 y
GD46 (raíces con cronograma versionado; verificar que estén, si alguna falta usar las que estén y
reportarlo) y una TIR fija por ticker (por ejemplo 0.12 — es un insumo, no un dato de mercado),
comparar `app.calendario.metricas.retorno_por_tir` contra `tools.cupones.retorno_por_tir` con los
ocho deltas estándar: **igualdad con `pytest.approx` al default**, porque es la misma matemática
sobre el mismo input. Documentar en el docstring del test la cadena: el motor es quien se verificó
contra la tabla de la mesa (0,12 pp, ESTADO.md); este test dice que el backend no se despegó del
motor. Ni más, ni menos.

### Backend — endpoint: agregar a `backend/tests/test_instrumentos_api.py`

`SENSIBILIDAD = "/api/v1/instrumentos/{ticker}/sensibilidad"`, sobre el
`FakeConexionInstrumentos` existente (despacha por SQL: universo y cashflow ya diferenciados):

- AL30D (usd_hard, `tir=0.121`, cashflow de AL30 presente) → 200, `calculable: true`,
  `naturaleza: "tir_usd"`, `tir_actual == 0.121`, ocho escenarios en orden, el de `delta_bps: 0`
  con `retorno == 0.0`, el de −100 positivo y el de +100 negativo, `omitidos_bps == []`.
- S30J6 (tasa_fija, TNA 0.35) → 200, `calculable: false`, el motivo menciona TNA nominal,
  `escenarios == []`. **Nunca** un número.
- `app_con_instrumentos(cashflow=[])` con AL30D → `calculable: false`, motivo
  `"sin cronograma de pagos en la fuente"` — y ningún campo con una estimación por duración.
- Ticker fuera del universo (`NOEXISTE`) → **200** con `calculable: false` y motivo, no 404.
- Universo custom con una especie usd_hard de `tir: None` → motivo de TIR faltante.
- `crear_app(None)` → 503.

### Frontend: `src/features/instrumento/__tests__/Sensibilidad.test.tsx`

Patrón de `FichaInstrumento.test.tsx` (mock supabase + `vi.stubGlobal('fetch', ...)` por ruta):

- Respuesta calculable → el panel "Sensibilidad" muestra la tabla; la cabecera de TIR incluye el
  rótulo de `unidadDeNaturaleza('tir_usd')` (importarla en el test y asertar contra su valor, no
  contra un literal duplicado); un retorno `0.1834` se ve formateado como porcentaje con coma
  (`18,34%`).
- `calculable: false` con motivo → el motivo está visible y **no** se renderiza ninguna tabla ni
  ningún número derivado de la duración.
- La ruta de sensibilidad respondiendo 500 → error sólo en ese panel; la ficha de precios y el
  cronograma siguen en pantalla (las queries son independientes).
- `omitidos_bps: [-500]` → la nota de escenarios omitidos está visible.
- Respuesta sin `escenarios` (campo faltante) → `contract_mismatch` (el error de schema de
  `apiFetch`), no un render con datos a medias.

## Comandos de verificación

```
Backend (cd /Users/jeroniki/Documents/Github/10-Swaper/backend):
  source venv/bin/activate
  python -m pytest tests/ -x -q      # pyproject ya trae addopts = "-m 'not integration'"
  ruff check . && ruff format --check .
Frontend (cd /Users/jeroniki/Documents/Github/10-Swaper/frontend):
  npx vitest run src/features/instrumento
  npm run lint
```

No correr la suite entera del frontend ni `vitest run` sin ruta (F-017, F-024 y F-052 trabajan en
paralelo); la corrida completa es del cierre de la tanda.

## Al terminar, reportar

- Archivos creados y modificados, con paths absolutos.
- Resultado textual de los cuatro comandos.
- La verificación de la precondición F-051: qué firmas reales tenía `metricas.py` y si alguna
  difirió de las citadas acá.
- Si la regresión contra el motor corrió sobre los cuatro tickers propuestos o hubo que sustituir
  alguno, y con qué números cerró.
- Cualquier punto donde el plan no cerró contra la realidad del código y qué se hizo — que debe
  ser: frenar esa parte y reportarla, no improvisar. En particular, dejar dicho una vez más que la
  tabla externa de 0,12 pp no está versionada y que GWT-2 quedó cubierto por la cadena
  motor→backend, no verificado contra la tabla original.
