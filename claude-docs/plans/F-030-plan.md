# F-030 — Valuación y diagnóstico de la cartera cargada

## Spec (plan.md:1447-1486)

Valora la cartera a precios de hoy y devuelve su descripción tal como está: renta mes a mes, meses
vacíos, rendimientos abiertos por naturaleza de tasa, plazo promedio, concentración por emisor y
por sector. Reusa exactamente los mismos servicios que el armador —F-015, F-020, F-021, F-022—
así que la cartera cargada y la que se está armando se leen con la misma vara.

```
GIVEN una cartera cargada con posiciones resueltas
WHEN se la valora
THEN cada posición usa el precio del snapshot vigente, y la barra de estado declara la hora de ese
     snapshot y su demora

GIVEN la misma composición cargada por F-028 y armada a mano en el armador
WHEN se comparan los dos diagnósticos
THEN producen los mismos números, porque usan los mismos servicios de cálculo

GIVEN una cartera cargada con posiciones no resueltas
WHEN se la valora
THEN el monto no resuelto queda fuera de los cálculos de renta y rendimiento, y el diagnóstico lo
     declara

GIVEN una cartera cargada
WHEN se muestra su calendario
THEN los meses sin cobertura aparecen con cero explícito
```

Depende de F-013, F-021, F-022, F-029 — todas cerradas. Riesgo R12 (`plan.md:2774`): "si los seis
ejes se calculan distinto en el armador, en el diagnóstico y en la propuesta, las tres carteras
dejan de leerse con la misma vara". Por eso la base común de esta tanda movió `rendimientos.ts`,
`renta.ts`, los esquemas de calendario/especie/concentración y sus hooks a `src/lib/cartera/`:
**esta feature tiene que importar de ahí, no reimplementar ni copiar**.

## Dónde se monta

`features/cartera-ingreso/components/CarteraConfirmada.tsx` ya tiene el stub `DiagnosticoCartera`
montado debajo de `<ResolucionCartera posiciones={posiciones} />`, recibiendo las mismas
`posiciones: PosicionCruda[]`. **No tocar `CarteraConfirmada.tsx`.**

El flujo real: `OptimizadorPage` → `IngresoCarteraPanel` (F-028) → `CarteraConfirmada` →
`ResolucionCartera` (F-029) + `DiagnosticoCartera` (esta feature), las dos hermanas, cada una
resuelve por su cuenta lo que necesita. `ResolucionCartera.tsx` lo dice en su propio docstring:
"Lo que acá NO va, y va en F-030: el precio de cada posición y el valor de la cartera, la renta
mes a mes contra el calendario, los rendimientos abiertos por naturaleza de tasa, el plazo
promedio y la concentración por emisor y por sector." **No hay ruta nueva, no se toca
`app/rutas.tsx`.**

## Archivos (todos nuevos, dueño único: `features/cartera-diagnostico/`)

- `components/DiagnosticoCartera.tsx` — reemplaza el stub.
- `hooks/useCarteraCargadaValuada.ts` — nuevo.
- `lib/valuacion.ts` — nuevo, función pura.
- `lib/schema.ts` — sólo si hace falta un tipo propio; los contratos de calendario/concentración
  se importan de `@/lib/cartera/*`, no se redefinen.
- `__tests__/valuacion.test.ts`, `__tests__/DiagnosticoCartera.test.tsx`,
  `__tests__/paridad.test.ts` — nuevos.

## `lib/valuacion.ts` — el adaptador

El contrato de entrada de F-029 (`features/cartera-resolucion/lib/schema.ts::PosicionResuelta`)
**no trae rendimiento, duración, precio ni peso** — sólo `nominal`, `monto`, `segmento`,
`naturaleza`, `clase_activo`, `resuelta`, `motivo`. Hay que cruzarlo contra el universo (`Especie`
de `@/lib/cartera/esquemaEspecie`, vía `useEspeciesUniverso` compartido) para obtener precio y
moneda de cotización, y ahí sí calcular monto invertido y peso — el mismo trabajo que
`features/armador/lib/resolver.ts::resolver()` hace para el mandato del armador, pero partiendo
de nominales ya declarados en vez de un peso pedido.

```ts
export type MotivoExclusionValuacion =
  | 'no_resuelta'
  | 'sin_nominal'
  | 'sin_precio'
  | 'sin_tipo_de_cambio'

export interface PosicionValuada {
  ticker: string
  invertido: number       // en la moneda de cotización de la especie
  invertidoUsd: number
  pesoReal: number         // invertidoUsd / Σ invertidoUsd * 100
}

export interface PosicionExcluidaValuacion {
  id: string
  motivo: MotivoExclusionValuacion
  /** El monto tal como vino del resumen cargado, sin convertir — su moneda no está declarada
   *  (regla 1: no se infiere). Sólo presente cuando la posición declaró monto. */
  montoDeclarado: number | null
}

export interface CarteraValuada {
  valuadas: PosicionValuada[]
  excluidas: PosicionExcluidaValuacion[]
  totalInvertidoUsd: number
}

export function valuarCartera(
  posiciones: PosicionResuelta[],       // de features/cartera-resolucion/lib/schema
  porTicker: ReadonlyMap<string, Especie>,  // de @/lib/cartera/esquemaEspecie
  tipoDeCambio: number | null,
): CarteraValuada
```

Reglas de exclusión, en este orden (una posición cae en el primer motivo que aplique):
1. `!resuelta || ticker === null` → `no_resuelta`.
2. `resuelta` pero `nominal === null` → `sin_nominal`. **No se deriva un nominal de `monto`**: la
   moneda en la que vino ese monto no está declarada en el resumen cargado (a diferencia del
   armador, que siempre trabaja en USD por construcción), así que convertirlo sería inventar una
   moneda (regla 1). `montoDeclarado` se reporta tal cual, sin convertir.
3. `especie.precio === null` → `sin_precio`.
4. `especie.moneda_cotizacion === 'ars'` (normalizado a minúscula, mismo casing que
   `useCarteraResuelta.ts:76-77`) y `tipoDeCambio === null` → `sin_tipo_de_cambio`.
5. Si pasa las cuatro: `invertido = nominal * precio / 100` (misma fórmula que
   `resolver.ts:89`), `invertidoUsd` = `invertido` directo si cotiza en USD, `invertido /
   tipoDeCambio` si cotiza en ARS (dividir, no multiplicar — inverso de `resolver.ts:91` porque
   acá se parte de nominal conocido, no de un objetivo en USD: verificar contra un caso concreto
   en el test, con un TC de ejemplo tipo 1050).

`pesoReal` se calcula sobre `Σ invertidoUsd` de las valuadas únicamente, igual criterio que
`resolver.ts:105-111`.

Un ticker duplicado en dos filas (dos posiciones con el mismo `ticker` resuelto) se valúa fila por
fila, sin fusionar — cada fila es una posición distinta del resumen que cargó el asesor.

## `hooks/useCarteraCargadaValuada.ts`

```ts
export function useCarteraCargadaValuada(posiciones: PosicionCruda[]) {
  const resolucion = useResolucionCartera(posiciones)   // de features/cartera-resolucion/hooks, import existente
  const especies = useEspeciesUniverso()                 // de @/lib/cartera/hooks, compartido
  const tipoDeCambio = useTipoDeCambio()                 // de @/lib/cartera/hooks, compartido

  const porTicker = useMemo(() => { /* Map<ticker, Especie>, igual que useCarteraResuelta */ }, [especies.data])
  const tcValor = tipoDeCambio.data?.tipo_de_cambio.valor ?? null

  const valuacion = useMemo(
    () => resolucion.data ? valuarCartera(resolucion.data.posiciones, porTicker, tcValor) : null,
    [resolucion.data, porTicker, tcValor],
  )

  return { resolucion, valuacion, tipoDeCambio: tcValor, porTicker, cargando, error }
}
```

No se toca `useCarteraResuelta.ts` ni `ArmadorProvider`/`carteraStore.tsx` — este hook es
independiente, mismo patrón (`useMemo` sobre queries de TanStack) pero sin store.

## `components/DiagnosticoCartera.tsx`

Reemplaza el `return null` del stub (firma ya fijada por la base común:
`{ posiciones: PosicionCruda[] }`).

1. `useCarteraCargadaValuada(posiciones)`.
2. Barra de estado del dato: **no se re-declara**. `BarraEstadoDato` (F-013) ya está montada
   globalmente en `AppLayout.tsx` y cubre "hora del snapshot y demora" para toda la app — el GWT-1
   de esta ficha se satisface por composición, no agregando una segunda barra local.
3. `valuadas.length === 0` → mensaje ("cartera no valuable: ninguna posición tiene nominal, precio
   y tipo de cambio a la vez", con el detalle de motivos si hay excluidas) y no se llama a ningún
   endpoint (los hooks compartidos ya tienen `enabled: length > 0`).
4. Con `valuadas.length > 0`:
   - `posicionesParaCalendario = valuadas.map(v => ({ ticker: v.ticker, monto: v.invertido }))` →
     `useCalendarioCartera(posicionesParaCalendario)` (hook compartido) → renta mes a mes con la
     misma UI que `PanelRenta` (reusar `columnasDeCordillera`/`calcularRentaAnualPorMoneda` de
     `@/lib/cartera/renta`, y si conviene, extraer la presentación visual de `PanelRentaCordillera`
     a algo reusable — o replicar su JSX citándolo como referencia, decisión de implementación).
   - `posicionesConPeso = valuadas.map(v => ({ ticker: v.ticker, peso: v.pesoReal }))` →
     `useConcentracion(posicionesConPeso, perfil)` (hook compartido) → mismo `Veredicto` visual que
     `PanelConcentracion` (reusar o replicar citando como referencia).
   - Rendimientos por naturaleza y plazo promedio: `rendimientosPorNaturaleza(valuadas, porTicker)`
     / `plazoPromedio(valuadas, porTicker)` de `@/lib/cartera/metricas` — `valuadas` ya cumple la
     forma estructural `PosicionPonderada` (`ticker`, `peso` ausente pero `pesoReal` presente:
     usar `{ ticker, peso: pesoReal, pesoReal }` al llamar, o extender `PosicionValuada` con
     `peso: pesoReal` desde `valuacion.ts` para que encaje sin adaptar en el componente).
5. Excluidas: sección declarativa (no oculta, mismo principio que `ResolucionCartera.tsx`) —
   cuántas por motivo, y `montoDeclaradoExcluido` = Σ de `montoDeclarado` de las excluidas, con la
   leyenda "en la moneda en que vino el resumen, que no se declara" (mismo texto que usa F-029
   para lo no resuelto).
6. Meses sin renta: cero explícito — ya lo garantiza `columnasDeCordillera` (`mes.renta?.[moneda]
   ?? 0`), no hace falta lógica adicional; el GWT-4 se cumple por reuso de esa función.

## Test de paridad R12 (`__tests__/paridad.test.ts`) — criterio de aceptación ejecutable

Construye un universo fixture con 3-4 especies. Arma la **misma tenencia física** (mismos
tickers, mismos nominales) por las dos vías:
- **Armador**: `resolver(entradas, montoTotalUsd, tc)` de `features/armador/lib/resolver`
  (import de sólo lectura — archivo congelado de otra feature, pero un test puede leerlo).
- **Diagnóstico**: `valuarCartera(posicionesF029Simuladas, porTicker, tc)` de `lib/valuacion.ts`,
  con `posicionesF029Simuladas` construidas a mano con los mismos nominales que las entradas del
  armador.

Afirma:
1. `pesoReal` de cada ticker coincide entre las dos salidas (`toBeCloseTo`, no `toEqual` — pueden
   diferir en el orden de operaciones de redondeo por lámina del armador, que el diagnóstico no
   aplica).
2. `rendimientosPorNaturaleza(...)`, `plazoPromedio(...)`, `sensibilidadPorSegmento(...)` —
   **las mismas tres funciones de `@/lib/cartera/metricas`**, llamadas una vez con la salida del
   armador y otra con la del diagnóstico — devuelven resultados `toEqual`.
3. El cuerpo que cada vía construiría para `POST /calendario/cartera` y `POST /concentracion`
   (`{ticker, monto}` / `{ticker, peso}`) es idéntico posición por posición — sin mockear red, sólo
   comparando los arrays de entrada a los hooks compartidos.

Si (1)-(3) pasan, el GWT-2 de la ficha ("mismos números porque mismos servicios") queda verificado
por construcción y no por inspección visual.

## Edge cases (todos con test)

- Ninguna posición valuable → declarado, sin llamar a `/calendario/cartera` ni `/concentracion`.
- Sólo-monto sin nominal → excluida como `sin_nominal`, monto declarado sin convertir.
- TC implícito `null` con posiciones ARS → excluidas como `sin_tipo_de_cambio`, declaradas.
- Ticker duplicado en dos filas → valuado por fila, no fusionado.
- Posiciones no resueltas (F-029) → excluidas como `no_resuelta`, ya vienen declaradas por
  `ResolucionCartera` arriba; el diagnóstico las vuelve a excluir de sus propios cálculos sin
  duplicar el mensaje de F-029.
- Meses sin renta → cero explícito, verificado contra `columnasDeCordillera`.
- Resultado en cero en cualquier métrica agregada → se explica (posiciones excluidas contadas), no
  se acepta en silencio.

## Zonas prohibidas

`CarteraConfirmada.tsx`, todo `src/lib/cartera/` (se importa, no se edita), `features/armador/**`
completo (incluido `useCarteraResuelta.ts` y el store — no se tocan ni se reusan directamente, el
diagnóstico tiene su propio hook), `features/cartera-resolucion/**` (se importa
`useResolucionCartera`, `PosicionResuelta`, `firmaDeCartera` de ahí — sólo lectura, no se edita),
`app/rutas.tsx`, backend entero.

## Verificación

```
cd frontend
npx vitest run src/features/cartera-diagnostico
npx tsc -b
npm run lint
```

Manual: en `/optimizador`, cargar una cartera con al menos 3 tickers reales del universo. El
diagnóstico debe mostrar renta mes a mes, rendimientos por naturaleza (4 tarjetas), plazo
promedio y concentración, con las mismas cifras que arma esa composición en `/armador`.
