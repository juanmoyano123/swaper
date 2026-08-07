# Feature Plan: F-038 — Monitor de mercado

## Overview
- **Source**: spec en `claude-docs/planning/plan.md` (líneas ~1715–1753) · diseño Cordillera v2 en
  `claude-docs/planning/design-system.md` (patrón A7: universo)
- **Complexity**: M — backend mecánico + una tabla densa con virtualización
- **Modo**: plan prescriptivo. Si algo no cierra contra la realidad del código, **frenar y
  reportar**, no improvisar.

## Qué es

La pantalla de entrada diaria: el universo por segmento, con orden y filtros, para consultar sin
armar nada. **Un solo segmento activo por vez** — así se respeta la regla de que rendimientos de
distinta naturaleza no comparten columna. Grilla densa (~1.500 filas de renta fija en total),
orden y filtros del lado del cliente sobre datos paginados, conteo de filas visible, curva
rendimiento/duración del segmento activo, y clic en fila → ficha del instrumento.

## GWT (criterios de aceptación, literales del plan)

```
GIVEN el monitor abierto
WHEN se lo mira
THEN hay un solo segmento activo por vez, y la unidad de la columna de rendimiento corresponde a ese segmento

GIVEN una grilla con ~1.700 filas
WHEN el asesor ordena por una columna y aplica dos filtros numéricos
THEN la respuesta es inmediata y el conteo de filas resultantes está visible

GIVEN el monitor abierto a la mañana
WHEN se lo mira
THEN la barra de estado del dato muestra la hora del snapshot, la demora de la fuente, los descartes
     por sanidad del día y la cobertura de los campos críticos

GIVEN una fila del monitor
WHEN se hace clic
THEN se abre la ficha del instrumento
```

GWT-3 **ya está cumplido**: `BarraEstadoDato` (F-013) se monta en `AppLayout` para las seis
pantallas. No construir nada para eso.

## Parte 1 — Backend (archivos propios de esta feature; F-016 no los toca)

### 1a. `paridad` viaja por el universo
La vista `public.resumen` tiene `paridad` (la lee `backend/app/calendario/lectura.py`) pero no
viaja por los endpoints de universo. Agregarla es mecánico:
- `backend/app/universo/lectura.py` → `"paridad"` en `COLUMNAS` (con un comentario de una línea:
  F-038, el monitor la muestra).
- `backend/app/universo/segmentacion.py` → campo `paridad: float | None` en `EspecieUniverso`,
  poblado en el constructor del armado (usar el mismo `a_numero(fila.get("paridad"))` que usan
  tir/tna), y la clave `"paridad"` en `como_dict()`.
- **Cuidado**: revisar si otros constructores de `EspecieUniverso` en tests fallan por el campo
  nuevo; darle default `None` para no romper.
- Si es `NULL` en la vista, viaja `null`. No se calcula, no se estima.

### 1b. `?segmento=` en `/universo/emisiones/especies`
En `backend/app/api/v1/universo.py`, endpoint `vista_viva`: parámetro opcional
`segmento: str | None = Query(None, description=...)`. Se aplica **antes** del cursor:
```python
listado = dedup.vivo()
if segmento is not None:
    listado = [e for e in listado if e.segmento == segmento]
```
Un segmento inexistente devuelve página vacía, no 404: pedir un segmento sin especies hoy es una
consulta válida con respuesta vacía.

### 1c. `GET /universo/segmentos` — de dónde saca las pestañas el frontend
Endpoint nuevo, chico, en el mismo router:
```jsonc
{
  "segmentos": [ { "clave": "usd_hard", "nombre": "<DESC_SEGMENTO[clave]>",
                   "naturaleza": "tir_usd", "naturaleza_nombre": "...",
                   "especies": 712 } ],   // sólo los presentes en el universo del día, conteo real
  "renta_variable": 1417,   // cuántos instrumentos quedaron fuera por ser RV
  "sin_segmento": 535       // cuántos no tienen tipo de tasa reconocible
}
```
Reusa `sanear_universo(conn)` + `.emisiones().vivo()` igual que `vista_viva`; los nombres salen de
`DESC_SEGMENTO` / `NATURALEZA_TASA` / `NOMBRE_NATURALEZA` de `segmentacion.py` — **no duplicar esos
diccionarios**. `renta_variable` y `sin_segmento` viajan porque el monitor los declara: lo que no
está en ninguna pestaña no puede desaparecer en silencio.

### 1d. Tests backend
En los archivos de test existentes del universo (`backend/tests/`, buscar los de
`universo`/`especies`): paridad presente en la fila (y `None` cuando la vista trae `NULL`),
filtro `?segmento=` (sólo especies de ese segmento; segmento inexistente → items vacío),
`/segmentos` (forma, conteos, y que un segmento sin especies no aparece). Seguir el patrón de los
tests offline existentes (mock de conexión, sin Postgres).

## Parte 2 — Frontend (`frontend/src/features/monitor/`)

### Dato
- `hooks/useSegmentos.ts` — `useQuery` de `/api/v1/universo/segmentos`. Decisión tomada sobre la
  clave: `queryKey: [...claves.mercado.todas, 'segmentos']` — cuelga del prefijo `mercado` (así el
  refresh de precios la invalida) sin editar `queryKeys.ts`, que está prohibido. No inventar otra
  clave ni usar `claves.mercado.universo('segmentos')` (eso significaría "el universo del segmento
  llamado segmentos", que es falso).
- `hooks/useUniversoSegmento.ts` — trae **todas** las páginas del segmento activo:
  `useQuery({ queryKey: claves.mercado.universo(segmento), queryFn })` donde `queryFn` hace un
  bucle: `apiFetch('/api/v1/universo/emisiones/especies?limit=200&segmento=...', esquemaPagina(esquemaEspecie))`
  siguiendo `next_cursor` (query param `cursor=`) hasta `null`, concatenando `items`. Tope de
  seguridad: 30 páginas → si se alcanza, error explícito, nunca resultado silenciosamente
  truncado. `staleTime` con `TIEMPOS.mercado`. (`usePaginaQuery` existe pero es de scroll manual;
  acá se necesita el segmento entero para ordenar y filtrar del lado del cliente — no usarlo.)
- `lib/schema.ts` — zod de la fila (campos reales de `EspecieUniverso.como_dict()` + los dos del
  endpoint): `ticker, emision, sufijo_liquidacion, clase_activo, segmento, naturaleza,
  naturaleza_nombre, rendimiento, duracion, vencimiento, ley, moneda_cupon, emisor, precio,
  moneda_cotizacion, volumen, volumen_usd, paridad, dato_sano, hermanas`. Numéricos nullable;
  `esquemaPagina` viene de `@/lib/api/schemas`. Y el zod de `/segmentos`.

### UI
- `MonitorPage.tsx` (modificar el existente, reemplaza el `EstadoVacio`):
  - `<SelectorSegmento>` de `@/components/SelectorSegmento` con las claves de `/segmentos`;
    segmento activo en `useState`, default: el primero del orden. Debajo del selector, en 11 px
    `var(--dim)`, la declaración de lo que no está en ninguna pestaña: "1.417 de renta variable y
    535 sin segmento no se muestran acá" (con los números reales del endpoint).
  - `FiltrosNumericos` + conteo + `TablaUniverso` + `CurvaSegmento`.
- `components/FiltrosNumericos.tsx` — cuatro inputs numéricos (rendimiento mín / máx — el rótulo
  usa `unidadDeNaturaleza(naturaleza)` del segmento activo —, duración máx) y botón limpiar.
  Inputs controlados; vacío = sin filtro. **Una fila con `rendimiento: null` no pasa un filtro de
  rendimiento** (no se puede afirmar que cumple), pero sin filtros activos se muestra siempre.
- `components/TablaUniverso.tsx` — la tabla densa:
  - Columnas: ticker (mono) + ley · emisor · precio (mono, con `moneda_cotizacion`) · rendimiento
    (mono, cabecera rotulada con la unidad del segmento) · duración · paridad · volumen USD
    (`fmtCompacto`) · vencimiento. Todo numérico `className="mono"` y alineado a la derecha;
    `null` → `s/d` (`SIN_DATO` de `@/lib/fmt`). `dato_sano: false` → fila con opacidad reducida y
    title "descartado por sanidad" (sigue visible: el descarte se declara, no se esconde).
  - Orden por clic en cabecera (asc/desc/ninguno), indicador ▲/▼. Orden y filtros con `useMemo`
    sobre las filas ya cargadas — inmediato porque no re-fetchea. `null` siempre al final del
    orden, ascendente o descendente.
  - **Virtualización con `@tanstack/react-virtual`** (`useVirtualizer`, ya instalado): contenedor
    con alto fijo (~520 px) y `overflow: auto`, filas absolutas de altura fija (~30 px). Es la
    mitigación R11 del plan.
  - Conteo SIEMPRE visible: "N de M especies" (filtradas / total del segmento) — es criterio de
    aceptación.
  - Clic en fila → `useAbrirInstrumento()` de `@/features/instrumento/useAbrirInstrumento`
    (GWT-4; el drawer ya existe, la ficha completa la hace F-039 — no tocarla).
- `components/CurvaSegmento.tsx` — scatter rendimiento (y) vs duración (x) del segmento activo,
  **sólo filas con ambos números** y una nota al pie: "N especies sin rendimiento o duración no
  están en la curva" cuando N > 0. Usar `recharts` (`ScatterChart`, ya instalado); ejes rotulados
  con la unidad del segmento y "duración (años)". Un solo segmento por gráfico, siempre.
- `__tests__/` — ver Test Strategy.

### PROHIBIDO tocar
`app/__tests__/rutas.test.tsx` · `lib/api/queryKeys.ts` · `components/MiniCalendario.tsx` ·
`components/SelectorSegmento.tsx` (se consume, no se edita) · `package.json` · **cualquier archivo
de `features/armador/`** · `backend/app/calendario/**` · nada de `git add`/`git commit` · el
backend no importa de `tools/`.

## Reglas del dominio que esta pantalla NO puede violar
1. Un segmento a la vez; la columna de rendimiento declara su unidad en la cabecera.
2. Nunca una columna con naturalezas mezcladas; nunca un promedio de rendimientos.
3. `null` → `s/d`. La TIR de los soberanos (AL30, GD30, AE38) es `NULL` hoy: se muestra `s/d`,
   no se tapa la fila ni se rellena.
4. Volumen comparable = `volumen_usd`; el crudo existe para auditar, no para la columna principal.
5. Lo excluido se declara (RV, sin segmento, filas fuera de la curva, filas descartadas).

## Test Strategy
Backend: pytest offline, patrón de los tests de universo existentes.
Frontend (patrón `features/estado-dato/__tests__/`): mock supabase + `vi.stubGlobal('fetch', ...)`
que responda `/segmentos` y dos páginas de `/especies` (con `next_cursor` la primera, `null` la
segunda) para probar el bucle:
- GWT-1: cambiar de segmento cambia el rótulo de la unidad en la cabecera y en los filtros.
- GWT-2: orden por rendimiento + dos filtros → filas correctas y conteo "N de M" actualizado.
- GWT-4: clic en una fila navega a `/instrumento/:ticker` (render con `MemoryRouter`, asertar la
  navegación).
- `rendimiento: null` → `s/d` en la celda, fila excluida del filtro de rendimiento y de la curva,
  y contada en la nota de la curva.
- El bucle de páginas concatena items y corta en `next_cursor: null`.
- Schema: campo faltante → `contract_mismatch`.

## Comandos de verificación
```
Backend (cd /Users/jeroniki/Documents/Github/10-Swaper/backend):
  source venv/bin/activate
  python -m pytest tests/ -x -q -m "not integracion"   # ajustar al marcador real del repo
  ruff check . && ruff format --check .
Frontend (cd /Users/jeroniki/Documents/Github/10-Swaper/frontend):
  npx vitest run src/features/monitor
  npm run lint
```
No correr la suite entera del frontend (otra feature trabaja en paralelo); la corre el cierre.

## Al terminar, reportar
Archivos creados/modificados, resultado textual de los comandos, y cualquier punto donde el plan
no cerró contra la realidad y qué se hizo (que debe ser: frenar esa parte y reportarla).
