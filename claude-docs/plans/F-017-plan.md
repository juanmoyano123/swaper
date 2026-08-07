# Feature Plan: F-017 — Filtros de la grilla

## Overview
- **Source**: spec en `claude-docs/planning/plan.md` (líneas ~866–903, "#### F-017 — Filtros de la
  grilla") · diseño Cordillera A7 en `claude-docs/planning/design-system.md`
- **Complexity**: M — sin backend; cruce cliente grilla × universo + una barra de filtros
- **Modo**: plan prescriptivo. Si algo no cierra contra la realidad del código, **frenar y
  reportar**, no improvisar.

## Qué es

Barra de filtros **siempre visible** sobre la grilla de doce meses del armador: segmento, horizonte
de duración, percentil de liquidez, sector, emisor, ley y frecuencia de cupón. Botón de limpiar que
los quita todos de una vez, y conteo de sobrevivientes a la vista. El filtro de segmento es
especial: se trabaja un segmento por vez, **o** con la unidad declarada por renglón — no existe un
estado en el que la grilla mezcle una TIR en dólares con una TNA en pesos sin decir cuál es cuál.
El output es el subconjunto del universo que alimenta la grilla (input de F-019).

La fila de la grilla (`InstrumentoDelMes`) no trae segmento, ley, sector, duración, emisor ni
volumen — pero el armador ya trae el universo entero (`useEspeciesUniverso`, F-018), que sí los
tiene. **F-017 cruza grilla × universo por ticker, del lado del cliente.** No hay endpoint nuevo.

## GWT (criterios de aceptación, literales del plan)

```
GIVEN la grilla sin filtro de segmento
WHEN se la muestra
THEN cada columna de rendimiento declara su unidad, o bien la grilla exige elegir un segmento antes
     de mostrar rendimientos

GIVEN el filtro de segmento en CER
WHEN se leen los rendimientos de la grilla
THEN todos están expresados como tasa real, con la unidad declarada en el encabezado

GIVEN filtros de duración, liquidez y sector aplicados simultáneamente
WHEN se los aplica
THEN el conteo de instrumentos resultantes está visible, y el botón de limpiar los quita todos de
     una vez

GIVEN un filtro por ley
WHEN hay instrumentos sin ley informada
THEN quedan agrupados como "ley no informada" y no se los asigna a ninguna de las dos leyes
```

Sobre GWT-1: `RenglonPapel.tsx` **ya** rotula el rendimiento de cada renglón con
`unidadDeNaturaleza(instrumento.naturaleza)` ("11,23% TIR USD"). O sea que la primera rama del GWT
se cumple por renglón: sin segmento elegido la grilla se muestra igual, con la unidad declarada en
cada fila. Con segmento elegido (GWT-2), además, la barra declara la unidad única del segmento.

## Parte 0 — Precondiciones (verificar ANTES de escribir una línea)

1. `esquemaEspecie` en `frontend/src/features/armador/lib/schema.ts` tiene que tener ya el campo
   `sector: z.string().nullable()`. Lo agrega la **base común de la tanda 8b** junto con `lamina`
   (backend: LEFT JOIN a `condiciones_emision` en `app/universo/lectura.py`; hoy — al escribir este
   plan — no existe ni en el backend ni en el esquema). Si al arrancar no está: **FRENAR y
   reportar**. F-017 **no** lo agrega por su cuenta — `lib/schema.ts` lo edita F-024 en paralelo y
   está prohibido acá (ver PROHIBIDO tocar).
2. `frontend/src/components/SelectorSegmento.tsx` sigue exportando `SelectorSegmento`,
   `nombreSegmento`, `unidadDeNaturaleza`, `ordenarSegmentos`. Se consume, no se edita. Si la base
   común le agregó claves `accion`/`cedear` a `NOMBRE_SEGMENTO` (para F-052), no afecta: las
   pestañas de F-017 salen del dato (segmentos presentes en el cruce), que es renta fija — nunca se
   ofrecen pestañas de renta variable ni se hardcodea la lista.
3. `useEspeciesUniverso` (`hooks/useEspeciesUniverso.ts`) y `traerUniversoEntero`
   (`lib/especies.ts`) existen tal como los dejó F-018. Se reusan tal cual.

## Parte 1 — `frontend/src/features/armador/lib/filtros.ts` (archivo nuevo)

La lógica pura, sin React. **Portada** del patrón de
`frontend/src/features/monitor/components/FiltrosNumericos.tsx` (F-038) — portada y no importada:
`features/monitor/**` está prohibido para el armador (mismo precedente formal que documentan
`armador/lib/schema.ts`, `armador/lib/especies.ts` y `claude-docs/plans/F-018-plan.md`: lo del
monitor se redefine acá, no se importa). Dejar esa justificación en el docstring del módulo.

Exports (firmas exactas):

```ts
export interface FiltrosArmador {
  /** null = todos los segmentos, con la unidad declarada por renglón (GWT-1). */
  segmento: string | null
  /** Input controlado en años; '' = sin filtro. */
  duracionMax: string
  /** Percentil mínimo de volumen_usd; '' = sin filtro. */
  liquidezMin: '' | '25' | '50' | '75'
  sector: string | null
  emisor: string | null
  /** Clave de ley del universo, o LEY_NO_INFORMADA. null = sin filtro. */
  ley: string | null
  /** Cantidad exacta de meses con pago de renta en la ventana; '' = sin filtro. */
  pagos: string
}

export const LEY_NO_INFORMADA = 'ley_no_informada'
export const FILTROS_ARMADOR_VACIOS: FiltrosArmador   // todo en null / ''
export function hayFiltrosActivos(filtros: FiltrosArmador): boolean

/** Meses de la ventana (0–12) en que cada ticker paga renta: pct_renta > 0. */
export function contarPagosPorTicker(meses: MesDelCalendario[]): Map<string, number>

/** Percentil (0–100] por ticker, por rango sobre volumen_usd — ver reglas abajo. */
export function percentilesDeLiquidez(especies: Especie[]): Map<string, number>

export function pasaFiltros(
  dato: { especie: Especie | undefined; pagos: number; percentil: number | undefined },
  filtros: FiltrosArmador,
): boolean

export function filtrarMeses(
  meses: MesDelCalendario[],
  cruce: Map<string, Especie>,
  filtros: FiltrosArmador,
): { meses: MesDelCalendario[]; total: number; visibles: number; sinCruce: number }
```

Reglas de la lógica — no negociables:

- **Frecuencia de cupón: no existe como dato de la emisión** en ninguna fuente ni endpoint. Se
  **deriva del propio calendario cargado**: `contarPagosPorTicker` cuenta los meses de la ventana en
  que el ticker figura con `pct_renta > 0`. Se rotula siempre como **observada sobre la ventana de
  doce meses** ("pagos de renta en los próximos 12 meses"), nunca traducida a "mensual /
  trimestral / anual": un ticker con un solo pago en la ventana no se declara "anual" porque la
  ventana no alcanza para afirmarlo (regla 1: no inventar).
- **Percentil de liquidez: sobre `volumen_usd`** (el normalizado de F-012), **nunca** sobre
  `volumen` crudo — el crudo viene en la moneda de cotización de cada especie y compararlo entre
  monedas viola la regla 3. El conjunto sobre el que se calcula se declara: las especies del cruce
  (tickers presentes en la grilla) con `volumen_usd != null`. Fórmula por rango:
  `percentil(t) = 100 * |{s : volumen_usd(s) <= volumen_usd(t)}| / |conjunto|`. Una especie con
  `volumen_usd: null` no entra al conjunto y **no pasa** un filtro de liquidez activo (no se puede
  afirmar que un dato que no existe supera un percentil), pero sin ese filtro se muestra igual.
- **Ley (GWT-4)**: `especie.ley === null` matchea **sólo** la opción `LEY_NO_INFORMADA`; jamás se
  lo asigna a ninguna de las dos leyes. Mismo trato para sector y emisor null ("sin dato"): regla 1.
- **Campo null contra filtro activo**: no pasa; sin ese filtro, se muestra (es la misma regla y el
  mismo porqué que `pasaFiltros` del monitor — copiar también la justificación en el docstring).
- **Ticker sin cruce** (está en la grilla pero no en el universo): no pasa **ningún** filtro que
  dependa del universo (segmento, duración, liquidez, sector, emisor, ley); el de pagos sí lo pasa,
  porque se deriva del calendario. `filtrarMeses` los cuenta en `sinCruce` para que la UI los
  declare — no desaparecen en silencio.
- `filtrarMeses` construye meses nuevos: reemplaza `instrumentos` por los sobrevivientes y
  **recalcula `con_renta` y `con_amortizacion` sobre los sobrevivientes**, pero **no toca
  `sin_renta`**: ese flag describe el universo ("nadie paga este mes"), no el filtro, y pisarlo
  haría mentir el rótulo "sin pagos en el universo" de la columna. `total`/`visibles` cuentan
  tickers distintos de la ventana, antes y después del filtro.
- Duración: comparar contra `especie.duracion` en años, tal cual (acá no hay división por 100 —
  esa conversión del monitor es sólo para rendimiento, que en F-017 no se filtra).

**Ojo**: el comentario viejo del store menciona "rendimiento mín/máx". La ficha de F-017 **no**
lista rendimiento entre los filtros — manda la ficha. No agregar filtros de rendimiento; si algo
parece exigirlos, FRENAR y reportar.

## Parte 2 — `frontend/src/features/armador/store/carteraStore.tsx` (modificar)

Es el archivo que el propio código reserva para esto ("F-017 agrega acá los filtros de A7 …",
línea ~34; el docstring dice que F-017 amplía este shape en vez de armar un store paralelo).

- En `EstadoArmador`: reemplazar ese comentario por `filtros: FiltrosArmador` (import de
  `../lib/filtros`). En `ESTADO_INICIAL`: `filtros: FILTROS_ARMADOR_VACIOS`.
- Dos acciones nuevas en `AccionArmador`, el reducer y `AccionesArmador` (mismo patrón que las
  existentes, identidades memoizadas):
  - `fijarFiltros: (filtros: FiltrosArmador) => void` — pisa el objeto entero (mismo patrón
    `onCambio({ ...valores, campo })` que usa el monitor: el llamador arma el objeto).
  - `limpiarFiltros: () => void` — vuelve a `FILTROS_ARMADOR_VACIOS` de una sola vez (GWT-3).
- **Los filtros no tocan `pos`, `selMes` ni `montoTotal`**: filtran la oferta, no la cartera. Un
  papel ya seleccionado cuyo renglón quede tapado por un filtro sigue en la cartera y en
  `CarteraEditable`. Ninguna acción de filtro puede sacar posiciones.
- Actualizar la primera línea del docstring del módulo (F-017 ya no es "por hacer").

## Parte 3 — `frontend/src/features/armador/components/FiltrosGrilla.tsx` (archivo nuevo)

La barra, siempre visible. Lee `filtros` con `useArmador()` y escribe con
`fijarFiltros`/`limpiarFiltros` de `useArmadorAcciones()`. Props (todo derivado se lo pasa el
contenedor de la Parte 4):

```ts
export function FiltrosGrilla({ opciones, conteo, deshabilitado }: {
  opciones: {
    segmentos: Array<{ clave: string; naturaleza: string }>
    sectores: string[]; emisores: string[]; leyes: string[]; pagos: number[]
  }
  conteo: { visibles: number; total: number; sinCruce: number }
  /** true mientras el universo carga o si falló: los filtros se declaran no disponibles. */
  deshabilitado: boolean
})
```

- **Segmento**: un botón "Todos" (con `aria-pressed`, leyenda "unidad declarada por renglón")
  seguido de `<SelectorSegmento segmentos={claves} activo={filtros.segmento ?? ''} onCambio={...}>`
  — `SelectorSegmento` se consume tal cual (no admite pestaña "todos" y **no se edita**; por eso el
  botón "Todos" va aparte). Las claves son las presentes en `opciones.segmentos` (derivadas del
  cruce): sólo renta fija, la que la grilla realmente tiene. Con segmento activo, al lado de la
  barra va el encabezado de unidad exigido por GWT-2: `unidad: {unidadDeNaturaleza(naturaleza)}`.
  Clic en la pestaña ya activa vuelve a "Todos" (misma mecánica de des-selección que el resto de
  la pantalla) — o, si se prefiere, sólo el botón "Todos" des-selecciona; elegir una y testearla.
- **Duración**: input numérico controlado "Duración máx. (años)", `''` = sin filtro (portar el
  patrón visual de `FiltrosNumericos` del monitor).
- **Liquidez**: select "Liquidez mín." con opciones `todos / ≥ p25 / ≥ p50 / ≥ p75`, rotulado de
  forma que declare el conjunto: "percentil de volumen USD, sobre el universo a la vista".
- **Sector / Emisor / Ley / Pagos**: selects con opciones derivadas del cruce (`opciones`),
  ordenadas alfabéticamente; primera opción "todos". El de ley incluye la opción
  **"ley no informada"** (`LEY_NO_INFORMADA`) cuando hay especies con `ley: null` (GWT-4). El de
  pagos se rotula "Pagos de renta (ventana 12 m)" con los conteos observados como opciones.
- **Botón "limpiar filtros"** → `limpiarFiltros()`.
- **Conteo SIEMPRE visible**: "{visibles} de {total} papeles pasan los filtros" (GWT-3). Cuando
  `sinCruce > 0`, al lado en `var(--dim)`: "{sinCruce} sin ficha en el universo: no filtrables".
- `deshabilitado`: inputs con `disabled` y una leyenda que explique por qué ("cargando el universo
  para poder filtrar" / "el universo no cargó: filtros no disponibles"). El filtro de pagos puede
  quedar activo (no depende del universo) — decisión del implementador, pero declarada.

## Parte 4 — `frontend/src/features/armador/components/GrillaFiltrada.tsx` (archivo nuevo)

El contenedor que hace el cruce y decide qué meses ve la grilla.

```ts
export function GrillaFiltrada({ meses }: { meses: MesDelCalendario[] })
```

- `useArmador()` → `filtros`; `useEspeciesUniverso()` → el universo (React Query ya cachea; es la
  misma consulta que usa `CarteraEditable`, no se duplica el fetch).
- Con `useMemo`: tickers de la ventana → `cruce: Map<ticker, Especie>` (restringido a esos
  tickers) → `percentilesDeLiquidez` + `contarPagosPorTicker` + opciones de los selects (segmentos
  con su naturaleza, sectores, emisores, leyes y conteos de pagos presentes en el cruce) →
  `filtrarMeses(meses, cruce, filtros)`.
- **Universo pendiente o con error**: la grilla **no** depende del universo — se renderiza con los
  `meses` sin filtrar, y `FiltrosGrilla` va con `deshabilitado` y su leyenda. Nunca aplicar
  filtros a medias con un universo incompleto: o se filtra con el universo entero, o no se filtra
  y se declara. (Esto además mantiene verdes los tests existentes de `ArmadorPage.test.tsx`, cuyo
  mock de fetch no responde `/especies`.)
- **Cero sobrevivientes** (`visibles === 0` con `hayFiltrosActivos`): en lugar de la grilla se
  muestra un bloque explícito — "Ningún papel de la ventana pasa los filtros activos (0 de
  {total})." — con el botón de limpiar a mano. **No** dibujar doce columnas vacías: sus rótulos
  dirían "sin pagos en el universo", que sería falso. El cero se explica, no se acepta mudo.
- Render normal: `<FiltrosGrilla …/>` + `<GrillaDoceMeses meses={filtrado.meses}/>` +
  `<DetalleMes meses={filtrado.meses}/>`. `DetalleMes` recibe los meses **filtrados** para que el
  detalle del mes muestre lo mismo que la grilla — su archivo no se toca, sólo se muda el call
  site (Parte 5). `GrillaDoceMeses` y `RenglonPapel` **no se editan**: dibujan lo que reciben.

## Parte 5 — `frontend/src/features/armador/ArmadorPage.tsx` (modificar, mínimo)

Dentro de `<ArmadorProvider>` (el docstring lo reserva: "F-017 va a agregar más adentro de este
mismo provider, no al lado"): reemplazar las dos líneas
`<GrillaDoceMeses meses={consulta.data.meses} />` y `<DetalleMes meses={consulta.data.meses} />`
por `<GrillaFiltrada meses={consulta.data.meses} />`. `CoberturaSeleccion` sigue recibiendo los
meses **sin filtrar**: la cobertura habla de la cartera contra el universo real, y un filtro de
vista no puede hacer aparecer huecos de cobertura falsos. `AlertasCalendario` y `CarteraEditable`
quedan igual. Actualizar la frase del docstring sobre F-017.

## PROHIBIDO tocar

- `frontend/src/features/monitor/**` — zona ajena; su lógica se **porta**, no se importa.
- `frontend/src/lib/api/queryKeys.ts` — sólo lectura en todos los planes vigentes (no hace falta
  clave nueva: se reusa la consulta de `useEspeciesUniverso`).
- `frontend/src/components/SelectorSegmento.tsx` — base común: se consume, no se edita.
- `frontend/src/features/armador/components/CarteraEditable.tsx`, `lib/resolver.ts` y
  `lib/schema.ts` — **los toca F-024 en paralelo**. Si `sector` no está en `esquemaEspecie`,
  aplica la Parte 0: FRENAR, no agregarlo acá.
- `GrillaDoceMeses.tsx`, `RenglonPapel.tsx`, `DetalleMes.tsx`, `CoberturaSeleccion.tsx`,
  `AlertasCalendario.tsx` — se consumen tal cual; si el plan parece exigir editarlos, FRENAR.
- Tests ajenos: `ArmadorPage.test.tsx`, `CarteraEditable.test.tsx`, `resolver.test.ts`. Si uno se
  rompe, es señal de que la grilla dejó de renderizar sin universo — corregir el código, no el test.
- **El backend entero** (`backend/**`) — F-017 es 100 % frontend; `lectura.py` y `segmentacion.py`
  los toca la base común de la tanda 8b.
- `package.json` (sin dependencias nuevas) · nada de `git add` / `git commit`.

## Reglas del dominio que esta pantalla NO puede violar

1. **No inventar un dato**: la frecuencia es observada sobre la ventana y así se rotula; null no
   pasa filtros activos pero no se esconde; ley null = "ley no informada", nunca una de las dos;
   los tickers sin cruce se cuentan y declaran.
2. **Naturalezas no se mezclan sin declarar**: o un segmento por vez con la unidad en el
   encabezado, o todos con la unidad declarada por renglón (que `RenglonPapel` ya garantiza).
   Jamás un estado intermedio.
3. **Nada se compara entre monedas sin normalizar**: el percentil de liquidez es sobre
   `volumen_usd`, nunca sobre `volumen` crudo, y declara su conjunto.
4. **El cero se explica**: cero sobrevivientes → mensaje con el conteo y la salida (limpiar), no
   una grilla vacía que parezca "sin pagos en el universo".
5. **Los filtros filtran la oferta, no la cartera**: `pos` es intocable para cualquier acción de
   filtro; una posición elegida no desaparece porque un filtro la tape.

## Test Strategy

`frontend/src/features/armador/__tests__/` — patrón existente: `vi.mock('@/lib/supabase')` +
`vi.stubGlobal('fetch', …)` ruteado por URL (copiar el `responderCon` de `CarteraEditable.test.tsx`,
que ya responde `/emisiones/especies` con `{ items, next_cursor: null }`), fixture de 12 meses
desde el "hoy" 07/08/2026 (la ventana septiembre 2026–agosto 2027 de `ArmadorPage.test.tsx`).

1. **`carteraStore.test.tsx` (extender — es el archivo de F-017 para la mecánica)**: agregar
   filtros al `Arnes` (mostrar `JSON.stringify(filtros)` en un testid, botones que llamen
   `fijarFiltros`/`limpiarFiltros`). Tests: `fijarFiltros` pisa el objeto; `limpiarFiltros` vuelve
   a `FILTROS_ARMADOR_VACIOS` de una sola vez; ninguna acción de filtro modifica `pos`.
2. **`__tests__/filtros.test.ts` (nuevo)**: lógica pura — percentil por rango (conjunto declarado,
   `volumen_usd: null` fuera del conjunto y no pasa filtro activo); `contarPagosPorTicker` cuenta
   sólo meses con `pct_renta > 0`; null contra filtro activo no pasa / sin filtro pasa; ticker sin
   cruce contado en `sinCruce`; `filtrarMeses` recalcula `con_renta` y no toca `sin_renta`.
3. **`__tests__/FiltrosGrilla.test.tsx` (nuevo, monta `ArmadorPage`)** — un test por GWT:
   - **GWT-1**: sin segmento elegido, la barra dice "unidad declarada por renglón" y los renglones
     muestran su unidad ("TIR USD" para AL30, la del CER para el papel CER del fixture).
   - **GWT-2**: clic en la pestaña CER → sólo quedan papeles CER y el encabezado de la barra
     muestra "Tasa real CER" (`unidadDeNaturaleza('tasa_real_cer')`).
   - **GWT-3**: aplicar duración + liquidez + sector a la vez → el conteo "N de M" está visible y
     es correcto; clic en limpiar → todos los filtros vuelven a vacío y el conteo vuelve a "M de M".
   - **GWT-4**: una especie con `ley: null`: con filtro "ley = ARG" no aparece; con filtro
     "ley no informada" aparece; no existe combinación en que figure bajo una ley concreta.
   - **Cero explicado**: filtros que nadie pasa → mensaje "0 de M" con explicación y botón de
     limpiar; no se renderizan las doce columnas.
   - **Universo caído**: `/emisiones/especies` responde 500 → la grilla se muestra sin filtrar y
     la barra declara que los filtros no están disponibles.

## Comandos de verificación

```
cd /Users/jeroniki/Documents/Github/10-Swaper/frontend
npx vitest run src/features/armador
npm run lint
```

**No correr la suite entera del frontend** (F-024 y otras features trabajan en paralelo en esta
misma carpeta y repo); la corre el cierre de la tanda.

## Al terminar, reportar

Archivos creados/modificados, resultado textual de los dos comandos, y cualquier punto donde el
plan no cerró contra la realidad del código —empezando por la precondición de `sector` en
`esquemaEspecie`— y qué se hizo (que debe ser: frenar esa parte y reportarla, no improvisar).
