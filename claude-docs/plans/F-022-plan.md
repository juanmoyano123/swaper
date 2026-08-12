# Feature Plan: F-022 — Rendimientos por naturaleza de tasa y plazo promedio

## Overview
- **Source**: spec en `claude-docs/planning/plan.md` (sección "#### F-022", líneas ~1115–1152) ·
  design-system A9/A3/A7 (columna derecha fija, cordillera en pesos, universo) ·
  `claude-docs/planning/plan-ejecucion-tandas.md` (tanda 10, fila 53): "F-022 recién acá porque
  comparte el servicio de métricas con F-021 (tanda 9)"
- **Complexity**: S — es aritmética determinística en TS sobre datos que `useCarteraResuelta` ya
  trae; no hace falta backend nuevo
- **Modo**: plan prescriptivo. Si algo no cierra contra la realidad del código, **FRENAR y
  reportar**, no improvisar.

## Qué es

Cuatro números, nunca uno solo: TIR en dólares, rendimiento dólar-linked, tasa real sobre CER y TNA
nominal en pesos — los cuatro **siempre presentes** (0 % explícito si la cartera no tiene nada de
esa naturaleza, nunca ausentes) con la porción de cartera de cada uno. **Sin ningún control de UI
que los colapse en un promedio**: son magnitudes de unidades distintas y promediarlas no significa
nada (regla 2 del dominio). La duración ponderada se etiqueta **"plazo promedio"** (un solo número:
la duración es años, unidad comparable entre naturalezas — lo dice el propio motor en
`resumir()`: *"La duration si se puede ver agregada, porque mide sensibilidad temporal en la misma
unidad"*). La **sensibilidad de precio se reporta por segmento, no agregada** — acá "segmento" son
los seis de `MONEDA_SEGMENTO`/`DESC_SEGMENTO` (usd_hard, cer, tasa_fija, dollar_linked, badlar,
tamar), no las cuatro naturalezas: dos segmentos en pesos (tasa_fija y badlar, por ejemplo) tienen
la misma naturaleza (`tna_nominal_ars`) pero son curvas distintas y no se mezclan.

## GWT (criterios de aceptación, literales del plan)

```
GIVEN una cartera con posiciones hard-dollar, CER y tasa fija en pesos
WHEN se muestran los rendimientos
THEN aparecen tres números separados con su unidad declarada y la porción de cartera de cada uno, y
     no existe control de UI que los promedie

GIVEN una cartera 100 % hard-dollar
WHEN se muestran los rendimientos
THEN los otros tres aparecen explícitamente en cero por ciento de la cartera, no ausentes

GIVEN una cartera con posiciones en dos segmentos
WHEN se muestra la sensibilidad de precio
THEN aparece una sensibilidad por segmento, y no un único número agregado

GIVEN posiciones sin TIR ni duración informadas
WHEN se calcula el rendimiento ponderado
THEN quedan excluidas del cálculo y el panel declara qué porcentaje de la cartera quedó fuera
```

## De dónde salen los datos — verificado, no hace falta nada nuevo

`frontend/src/features/armador/hooks/useCarteraResuelta.ts` (base común de la tanda 9, ya en uso
por F-020/F-021) devuelve:
- `resueltas: PosicionResuelta[]` — `ticker`, `peso`, `pesoReal: number | null`,
  `invertidoUsd: number | null`, `laminaConocida`, `esFci`. **No** trae `rendimiento` ni
  `naturaleza`: eso vive en la especie.
- `porTicker: Map<string, Especie>` — `Especie` (de `lib/schema.ts`) trae
  `rendimiento: number | null`, `duracion: number | null`, `segmento: string`,
  `naturaleza: string`, `naturaleza_nombre: string`.

F-022 combina los dos por `ticker`, filtrado a **renta fija** (`posicionesRentaFija(pos)` de
`store/carteraStore.tsx`, mismo filtro que ya aplica `useCarteraResuelta`) — los FCI y la renta
variable no tienen naturaleza de tasa y quedan fuera de este panel (la RV tiene su propio bloque,
F-026, y la regla 2 sigue valiendo: "una acción no tiene TIR").

Sobre qué peso se pondera: **el mismo criterio que F-020/`PanelConcentracion`** —
`pesoReal ?? peso` (el real cuando está resuelto, el pedido si no). Reusar, no reinventar un tercer
criterio de peso en el panel de rendimientos.

Las cuatro naturalezas y sus rótulos ya están en `NATURALEZA_TASA`/`NOMBRE_NATURALEZA`
(`backend/app/universo/segmentacion.py`, reflejado en `naturaleza`/`naturaleza_nombre` de cada
`Especie`) y el rótulo corto para pantalla ya existe en
`frontend/src/components/SelectorSegmento.tsx::unidadDeNaturaleza()` (`tir_usd`→"TIR USD",
`tir_dolar_linked`→"TIR DL", `tasa_real_cer`→"Tasa real CER", `tna_nominal_ars`→"TNA $") — **reusar
esa función**, no declarar un cuarto mapa de rótulos.

## Puerto de referencia — `tools/armar_cartera.py::resumir()` (líneas 346–398)

Es el algoritmo a portar a TS, adaptado a los datos ya disponibles (no hace falta el DataFrame
completo, sólo posición + peso + rendimiento + duración + segmento/naturaleza):
- Por naturaleza: `peso = Σ peso_posición`; dentro del grupo, `w_i = peso_i / peso`;
  `rendimiento_pond = Σ (rendimiento_i * w_i)`.
- `dur_pond` (plazo promedio, global): `Σ (duracion_i * peso_i / 100)` sobre TODA la cartera de
  renta fija, sin agrupar.
- Por segmento (sensibilidad): mismo patrón de ponderación que por naturaleza, pero agrupado por
  `segmento` en vez de por `naturaleza`, usando `duracion` (duración modificada) como proxy de
  sensibilidad — no hay un endpoint de repricing por cartera (el de F-040,
  `/instrumentos/{ticker}/sensibilidad`, es por especie individual y no corresponde llamarlo N
  veces desde acá); la duración ponderada por segmento **es** la sensibilidad que F-022 pide, igual
  que la ficha lo permite ("duración modificada es elasticidad respecto de la tasa propia de cada
  segmento").

## `frontend/src/features/armador/lib/rendimientos.ts` (nuevo)

```ts
export interface RendimientoPorNaturaleza {
  naturaleza: string          // 'tir_usd' | 'tir_dolar_linked' | 'tasa_real_cer' | 'tna_nominal_ars'
  nombre: string               // naturaleza_nombre de la primera especie del grupo, o el fijo si no hay ninguna
  pctCartera: number           // % de la cartera (peso real/pedido) en esta naturaleza, 0 si no hay nada
  rendimientoPond: number | null   // null si pctCartera === 0 o si TODAS las posiciones del grupo están sin dato
  posiciones: number
  posicionesExcluidas: number      // sin rendimiento informado
  pctExcluido: number              // % de LA CARTERA TOTAL (no del grupo) que quedó fuera del cálculo por naturaleza sin dato
}

export interface SensibilidadPorSegmento {
  segmento: string
  pctCartera: number
  duracionPond: number | null      // igual criterio de exclusión que arriba, sobre `duracion`
  posiciones: number
  posicionesExcluidas: number
}

export function rendimientosPorNaturaleza(
  resueltas: PosicionResuelta[],
  porTicker: Map<string, Especie>,
): RendimientoPorNaturaleza[]     // siempre las 4, en el orden fijo tir_usd, tir_dolar_linked, tasa_real_cer, tna_nominal_ars

export function plazoPromedio(
  resueltas: PosicionResuelta[],
  porTicker: Map<string, Especie>,
): { anios: number | null; posicionesExcluidas: number }

export function sensibilidadPorSegmento(
  resueltas: PosicionResuelta[],
  porTicker: Map<string, Especie>,
): SensibilidadPorSegmento[]      // sólo los segmentos presentes en la cartera, ordenados por pctCartera desc
```

Reglas de exclusión (GWT-4), exactas:
- Una posición sin `rendimiento` (`null`) se excluye del `rendimientoPond` de su naturaleza, pero
  **sigue contando en `pctCartera`** de esa naturaleza (la plata está ahí, lo que falta es el dato
  de rendimiento) — si se la sacara de `pctCartera` también, la suma de las cuatro `pctCartera` ya
  no daría el 100 % de la cartera y esa discrepancia no está declarada en ningún lado.
- Si **todas** las posiciones de una naturaleza están sin rendimiento → `rendimientoPond: null`
  (nunca 0 — un cero sería un rendimiento real, y acá no hay ninguno calculado), `pctExcluido`
  igual a `pctCartera` de esa naturaleza.
- Mismo criterio para `duracion` en `plazoPromedio` y `sensibilidadPorSegmento`.
- Un `peso`/`pesoReal` de `null` (posición sin resolver) no aporta a ningún `pctCartera` — no hay
  con qué ponderar lo que no se sabe cuánto pesa; no es lo mismo que "sin rendimiento".

## `frontend/src/features/armador/components/PanelRendimientos.tsx`

Reemplaza el stub de la base común (`return null`). Sigue el patrón de `PanelRenta.tsx`: llama
`useCarteraResuelta()` una sola vez (React Query cachea, no duplica el fetch de F-020/F-021), pasa
`resueltas`/`porTicker` a las tres funciones de `lib/rendimientos.ts`, y renderiza:
1. **Cuatro tarjetas** (grid o fila, según lo que entre en el ancho del panel — no hay mockup de
   esto en el design-system, así que se resuelve con el estilo ya existente de tarjeta/Panel
   compacto de la carpeta), una por naturaleza, **siempre las cuatro visibles en el mismo orden**
   fijo, cada una con: rótulo corto (`unidadDeNaturaleza`), `fmtPct(rendimientoPond*100)` o
   `SIN_DATO` si es `null`, y `fmtPct(pctCartera)` de la cartera. Si `pctExcluido > 0`, una leyenda
   chica declarando cuántas posiciones/qué % quedó afuera del cálculo (no silencioso — regla 11).
2. **Plazo promedio**: un número (`fmtNumero(anios, 1)` + "años"), rotulado literalmente "Plazo
   promedio" (no "duración" — así lo pide la ficha), con la misma leyenda de exclusión si aplica.
3. **Sensibilidad por segmento**: una lista/tabla chica, un renglón por segmento presente, sin
   agregarlos en un único número. Usar `DESC_SEGMENTO`-equivalente del frontend si existe un mapa
   de nombres de segmento ya declarado (buscar en `SelectorSegmento.tsx` o `lib/schema.ts` antes de
   inventar un quinto mapa); si no existe, usar el `segmento` crudo como rótulo y declararlo en el
   reporte.

Sin control de colapsar/promediar: no agregar un toggle "ver promedio", ni un total que sume las
cuatro naturalezas o los segmentos — es justamente lo que el GWT-1 prohíbe.

## Reglas del dominio que esto NO puede violar

1. **Regla 2 — no promediar rendimientos de distinta naturaleza.** Las cuatro tarjetas nunca se
   combinan en un número. La duración/plazo sí se agrega (años es unidad comparable), la
   sensibilidad no se agrega entre segmentos (aunque comparta unidad temporal, la ficha pide
   explícitamente que no se agregue: cada segmento tiene su propia curva).
2. **Regla 11 — nada en blanco sin declarar.** `pctExcluido` visible cuando hay posiciones sin
   dato; `null` se muestra como `SIN_DATO` ("s/d"), nunca como 0.
3. Una naturaleza sin ninguna posición en la cartera se muestra en **0 %**, explícito, no se omite
   la tarjeta (GWT-2).

## PROHIBIDO tocar

- `frontend/src/features/armador/hooks/useCarteraResuelta.ts` — se consume tal cual, no se
  modifica su contrato (F-019 y F-025 pueden estar corriendo en paralelo sobre otras partes de la
  carpeta; este hook es de lectura compartida y no tiene dueño esta tanda, pero cambiar su forma
  rompería a F-020/F-021/F-026 que ya lo consumen).
- `backend/**` — F-022 no toca el backend. Si al implementar aparece que hace falta un dato que
  `Especie` no trae, **FRENAR y reportar** — no agregar un endpoint ni un campo nuevo por cuenta
  propia (eso reabriría la deuda de "servicio de métricas una sola vez" antes de tiempo, y F-023 en
  la tanda 11 es quien la va a forzar).
- `frontend/src/features/armador/store/carteraStore.tsx`, `ArmadorPage.tsx`,
  `PanelesDeLaCartera.tsx`, `frontend/src/lib/api/queryKeys.ts` — congelados/de otras features esta
  tanda. El stub `PanelRendimientos.tsx` es el único archivo de montaje que se edita.
- `frontend/src/features/armador/components/PanelRenta.tsx`,
  `components/PanelRentaCordillera.tsx`, `components/PanelRentaAnual.tsx`,
  `lib/renta.ts` — son de F-021 (tanda 9), no se tocan aunque el patrón se parezca.
- Nada de `git add` / `git commit`: el cierre de tanda lo hace otro.

## Test Strategy

### `frontend/src/features/armador/__tests__/rendimientos.test.ts` (motor puro)
- Cartera con las tres naturalezas del GWT-1 (hard-dollar, CER, tasa fija) → tres
  `rendimientoPond` numéricos con su `pctCartera`, y la cuarta (`tir_dolar_linked`) en
  `pctCartera: 0`, `rendimientoPond: null`.
- Cartera 100 % hard-dollar (GWT-2) → las tres naturalezas restantes en `pctCartera: 0`.
- Dos segmentos con posiciones → `sensibilidadPorSegmento` devuelve dos entradas, ninguna
  agregada (GWT-3).
- Posiciones sin `rendimiento`/`duracion` informados (GWT-4) → excluidas del `_pond`,
  `posicionesExcluidas` y `pctExcluido` correctos; si son todas las de una naturaleza →
  `rendimientoPond: null` con `pctExcluido` igual al `pctCartera` del grupo.
- Posición con `peso`/`pesoReal` null (sin resolver) → no aporta a `pctCartera` de ninguna
  naturaleza.
- Cartera vacía → las cuatro naturalezas en `pctCartera: 0`, `rendimientoPond: null`;
  `plazoPromedio` en `{ anios: null, posicionesExcluidas: 0 }`.

### `frontend/src/features/armador/__tests__/PanelRendimientos.test.tsx`
- Renderiza las cuatro tarjetas siempre, en el mismo orden, con `s/d` donde corresponda.
- La leyenda de exclusión aparece sólo cuando `pctExcluido > 0`.
- No hay ningún elemento (botón, toggle, número) que combine las cuatro naturalezas.

## Comandos de verificación

```
cd /Users/jeroniki/Documents/Github/10-Swaper/frontend
npx vitest run src/features/armador
npx tsc -b
npm run lint
```

No correr la suite completa: F-019 y F-025 trabajan en paralelo sobre otros archivos de la misma
carpeta. La corrida completa la hace el cierre de la tanda.

## Al terminar, reportar

- Si existía o no un mapa de nombres de segmento reusable para la tabla de sensibilidad, y qué se
  hizo si no existía.
- Archivos creados/modificados y el resultado textual de los comandos.
- Confirmación de que ningún control de UI permite promediar las cuatro naturalezas.
- Cualquier punto donde el plan no cerró contra la realidad del código — frenar esa parte y
  reportarla, no improvisar.
