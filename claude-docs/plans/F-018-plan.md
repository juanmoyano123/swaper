# Feature Plan: F-018 — Cartera editable y ponderación

## Overview
- **Source**: spec en `claude-docs/planning/plan.md` (líneas ~842–878) · diseño Cordillera v2 en
  `claude-docs/planning/design-system.md` (panel A8, motor `resolver`, reglas de estado)
- **Complexity**: L — es el estado central del armador, sobre el camino crítico
- **Modo**: plan prescriptivo. Las decisiones ya están tomadas; el trabajo es transcribirlas. Si
  algo no cierra contra la realidad del código, **frenar esa parte y reportarla**, no improvisar.
- **Puramente frontend**: los dos endpoints que se necesitan (`POST /api/v1/calendario/cartera`,
  `GET /api/v1/universo/tipo-de-cambio`) ya existen. No se toca el backend.

## Qué es

El panel donde vive la cartera en construcción, dentro de `ArmadorPage` (junto a la grilla de
F-016). Tabla editable: ticker, moneda, monto invertido, ponderación pedida (editable), ponderación
real (la que resulta de redondear a lámina), mini-calendario de en qué meses paga. Se equipondera,
se vacía, se ve cuánto suma la ponderación pedida y cuánto está invertido en realidad — **porque no
coinciden**, y la pantalla lo muestra en vez de normalizar en silencio.

## GWT (criterios de aceptación, literales del plan)

```
GIVEN una cartera con tres posiciones
WHEN el asesor cambia el peso de una por porcentaje
THEN el monto de esa posición se recalcula y el total acumulado de ponderación se actualiza en vivo

GIVEN una cartera con pesos que suman 97,4 %
WHEN se la mira
THEN el total muestra 97,4 % y el invertido real al lado, sin normalizar a 100 % en silencio

GIVEN una cartera con posiciones
WHEN el asesor presiona equiponderar
THEN todas las posiciones quedan con el mismo peso deseado, y el porcentaje real sigue difiriendo
     donde la lámina obliga a redondear

GIVEN una línea de FCI cargada con peso y sin precio
WHEN se calcula el total de la cartera
THEN la línea suma al peso, se declara como sin precio, y no participa de ningún cálculo de renta
     ni de rendimiento
```

**Sobre GWT-3 en esta tanda**: la lámina real por ticker todavía no está cableada (la trae F-024,
tanda 8, desde `condiciones_emision`). El motor `resolver` recibe la lámina como parámetro, así que
la mecánica de redondeo se verifica con lámina de fixture en los tests. En pantalla, sin lámina
conocida, la posición muestra "lámina s/d" y no se le aplica redondeo (su VN objetivo se muestra tal
cual, sin piso ni recorte) — no se inventa una lámina por defecto.

## Archivo de referencia — el store que se extiende

`frontend/src/features/armador/store/carteraStore.tsx` (F-016, ya en el repo). Leerlo completo
antes de tocarlo: **su propio docstring dice que F-018 lo extiende, no arma un store paralelo**, y
marca los puntos exactos de extensión con comentarios `// F-018 agrega acá`.

### Cambios en `carteraStore.tsx`

```ts
export interface PosicionArmador {
  ticker: string
  /** Ponderación pedida, en puntos porcentuales (16.5 = 16,5%). Al agregar un papel nuevo se
   *  asigna 100/(n+1) redondeado a un decimal; los pesos de los demás NO se tocan — por eso la
   *  suma puede no dar 100, y eso se muestra, no se corrige solo. */
  peso: number
  /** true para una línea de FCI: tiene peso pero no precio, y queda fuera de todo cálculo de
   *  renta o rendimiento (GWT-4). Se agrega con una acción propia, no con alternarPapel. */
  esFci: boolean
}

interface EstadoArmador {
  pos: PosicionArmador[]
  selMes: number | null
  /** Capital total a invertir, en dólares. 0 hasta que el asesor lo carga; con 0 no hay objetivo
   *  que repartir y el motor resolver no corre (ver lib/resolver.ts). */
  montoTotal: number
}
```

Acciones nuevas, en el **mismo** `useMemo` sin deps que ya existe (para no romper la garantía de
identidad estable que el docstring actual documenta):
- `fijarPeso(ticker, peso)` — pisa el peso pedido de esa posición, no toca las demás.
- `fijarMontoTotal(monto)`.
- `equiponderar()` — pone `100 / n` a **todas**, ponderado a un decimal.
- `vaciar()` — `pos: []`.
- `agregarFci(nombre, peso)` — agrega una posición con `esFci: true`, ticker = el nombre cargado.

`alternarPapel` cambia: al agregar, el peso nuevo es `100/(n+1)` redondeado a un decimal (`n` = la
cantidad de posiciones ANTES de agregar), `esFci: false`; al sacar, sale como hoy. Los pesos de las
posiciones existentes no se recalculan.

**No agregar nada que el plan no pida** (nominales resueltos con lámina real, moneda de operación):
eso es de F-024 y F-019 respectivamente.

## El motor `resolver` — función pura, sin red

Nuevo archivo `frontend/src/features/armador/lib/resolver.ts`. Porta el pseudocódigo del design
system tal cual, adaptado a lo que hoy se puede calcular (sin moneda de operación todavía, un solo
tipo de cambio implícito para todo lo que cotiza en pesos):

```ts
export interface EntradaResolver {
  ticker: string
  peso: number                    // pedido, en puntos porcentuales
  precio: number | null           // en la moneda de cotización de la especie; null = FCI o sin precio
  monedaCotizacion: 'usd' | 'ars' | string
  lamina: number | null           // null = sin dato, no se redondea
  esFci: boolean
}

export interface PosicionResuelta {
  ticker: string
  peso: number
  vn: number | null                 // null si no se pudo calcular (sin precio, sin monto total)
  invertido: number | null          // en la moneda de cotización de la especie
  invertidoUsd: number | null       // normalizado con el TC implícito si la especie cotiza en ARS
  pesoReal: number | null           // invertidoUsd / Σ invertidoUsd * 100
  laminaConocida: boolean
}

export function resolver(
  posiciones: EntradaResolver[],
  montoTotalUsd: number,
  tipoDeCambio: number | null,      // MEP implícito de F-012; null = no disponible hoy
): PosicionResuelta[]
```

Reglas exactas:
- FCI (`esFci: true`) o sin precio: `vn: null`, `invertido: null`, `invertidoUsd: null`,
  `pesoReal: null` — la línea NO entra en el denominador de `pesoReal` de las demás (GWT-4: "no
  participa de ningún cálculo").
- `objetivoUsd = montoTotalUsd * peso / 100`.
- Si `monedaCotizacion === 'usd'`: `objetivo = objetivoUsd`.
- Si `monedaCotizacion === 'ars'`: si `tipoDeCambio === null`, la posición no se puede resolver
  (`vn: null`, declarada "sin tipo de cambio" — nunca se inventa uno externo, regla 3 del
  proyecto); si no, `objetivo = objetivoUsd * tipoDeCambio`.
- Con `lamina !== null`: `vn = Math.floor(objetivo / (precio / 100) / lamina) * lamina` (siempre
  hacia abajo, nunca redondeo normal). Con `lamina === null`: `vn = objetivo / (precio / 100)` sin
  pisar a ningún múltiplo, y `laminaConocida: false` — la fila lo declara.
- `invertido = vn * precio / 100`; `invertidoUsd = monedaCotizacion === 'ars' && tipoDeCambio ? invertido / tipoDeCambio : invertido`.
- `pesoReal`: sobre la suma de `invertidoUsd` de las posiciones que sí lo tienen (no-FCI, con
  precio, con VN resuelto). Si esa suma es 0, todos los `pesoReal` son `null`.
- Con `montoTotalUsd === 0`: todo `vn/invertido/pesoReal = null` (no hay objetivo que repartir).

Testear la función aislada, con fixtures de lámina conocida y desconocida — así se verifica GWT-3
sin depender de que el dato real llegue.

## Componentes

### `armador/components/CarteraEditable.tsx` (+ subcomponente de fila)
Diseño A8. Grid de fila: `minmax(70px,86px) 1fr 52px 62px 52px 22px`.
- Col 1: ticker (mono) + moneda de cotización (`--dim`).
- Col 2: emisor si está disponible (de la especie — ver abajo de dónde sale), si no el ticker
  repetido; debajo, VN e invertido en mono chico.
- Col 3: input numérico de peso pedido, mono, color `--ac`, `onChange → fijarPeso`.
- Col 4: peso real (`s/d` si `pesoReal === null`), con `title` explicando el porqué cuando difiere
  del pedido por más de 0,6 pp ("redondeado a lámina de N" o "sin lámina conocida" según el caso).
  Ese texto en `--ac2` cuando `Math.abs(pesoReal - peso) > 0.6`.
- Col 5: `<MiniCalendario>` con los meses en que el ticker paga, derivado del calendario de cartera
  (ver hook abajo) — si la query de calendario todavía no resolvió, celdas vacías (no bloquea el
  render de la tabla).
- Col 6: botón `×` → `alternarPapel(ticker)` (ya existe, saca la posición).
- Fila de FCI: mismo grid, precio/VN/invertido en `s/d`, peso real `s/d` con el motivo GWT-4.

Cabecera del panel: Σ de pesos pedidos (en `--ac2` si `≠ 100`, tolerancia 0,05), invertido total
(suma de `invertido` en USD normalizado, o "s/d" si no hay ninguna posición resuelta), botón
"Equiponderar" (→ `equiponderar()`), botón "Vaciar" (→ `vaciar()`, con confirmación simple si
`pos.length > 0` — un `window.confirm` está bien acá, es una acción destructiva local, no de red).

### De dónde sale precio/lámina/emisor por ticker
No hay endpoint "dame estas 5 especies". Usar `GET /api/v1/universo/emisiones/especies?segmento=`
sería traer de más. Decisión: pedir **todas las páginas de `/emisiones/especies` sin filtro de
segmento** una sola vez (igual bucle de cursor que ya usa `features/monitor/hooks/useUniversoSegmento.ts`
— leerlo como patrón, NO importarlo: `features/monitor/**` está prohibido para este agente; portar
la misma lógica de bucle localmente en `armador/lib/`), y armar un `Map<ticker, Especie>` en
memoria con `useMemo`. Es aceptable acá porque el número de posiciones de una cartera es chico y el
armador ya paga el costo de traer el universo en el monitor — no es un endpoint nuevo, es reuso del
mismo contrato de página que ya existe. Tipar la fila con el mismo shape de `EspecieUniverso` que
expone `/emisiones/especies` (mismo `zod` que usa el monitor, redefinido localmente en
`armador/lib/schema.ts` — no importar el de `features/monitor/`).

`lamina` **no está en `EspecieUniverso`** hoy (la trae F-024 vía `condiciones_emision`, tanda 8).
Por eso el fetch de especies alcanza para precio/moneda/emisor pero **no** para lámina: pasar
`lamina: null` siempre en esta tanda. No inventar un valor.

### Calendario de cartera
`armador/lib/firmaDeCartera.ts` — mismo patrón que
`features/cartera-resolucion/lib/resolverCartera.ts::firmaDeCartera` (leerlo, NO importar esa
carpeta): `posiciones.map(p => \`${p.ticker}:${p.peso}\`).join('|')`.

`armador/hooks/useCalendarioCartera.ts`:
```ts
export function useCalendarioCartera(posiciones: { ticker: string; monto: number }[]) {
  const firma = firmaDeCartera(posiciones)
  return useQuery({
    queryKey: claves.mercado.calendarioCartera(firma),
    queryFn: () => apiFetch('/api/v1/calendario/cartera?detalle=true', esquemaCalendarioUniverso, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ posiciones: posiciones.map(p => ({ ticker: p.ticker, monto: p.monto })) }),
    }),
    enabled: posiciones.length > 0,   // el endpoint da 422 con lista vacía — nunca se llama vacía
    ...TIEMPOS.mercado,
    retry: false,
  })
}
```
`esquemaCalendarioUniverso` se **importa** de `armador/lib/schema.ts` (ya existe de F-016, tipa la
respuesta exacta que este POST también devuelve — no crear un schema nuevo).

`monto` por posición para el body: el `invertido` que calculó `resolver` (en la moneda de
cotización de la especie, que es lo que el endpoint espera — confirmar contra el docstring de
`PosicionEntrada` en `backend/app/api/v1/calendario.py` si hay dudas, es de solo lectura). Excluir
del body las posiciones con `invertido === null` (FCI o sin poder resolver) — mandar monto 0 o null
violaría el contrato (`monto: float = Field(gt=0)`).

Mostrar `AlertasCalendario` (componente ya existente de F-016, **importarlo**, no reescribirlo) con
las alertas de esta respuesta — incluida `fuera_del_universo` si el asesor cargó algo que no está
en el universo del día.

### Modify
- `ArmadorPage.tsx` — agregar `<CarteraEditable>` dentro del `<ArmadorProvider>` existente, junto a
  los componentes de F-016 (no reemplazarlos). Orden sugerido: grilla arriba, cartera editable
  debajo (o al lado, si el layout lo permite con lo que hay) — la maqueta exacta de layout de dos
  columnas (A7 izquierda / A8+A9 derecha) es de una tanda de refinamiento visual posterior; esta
  tanda prioriza que los datos y las acciones existan y sean correctos.

## PROHIBIDO tocar
`features/instrumento/**` · `features/monitor/**` (sólo lectura de referencia, nunca import) ·
cualquier archivo del backend · `app/__tests__/rutas.test.tsx` · `lib/api/queryKeys.ts` ·
`components/MiniCalendario.tsx` / `SelectorSegmento.tsx` (se consumen, no se editan) ·
`package.json` · nada de `git add`/`git commit`.

## Reglas del dominio que esta pantalla NO puede violar
1. Lámina desconocida → se declara, nunca se asume un default.
2. Ningún total mezcla monedas sin pasar por el TC implícito de F-012; sin TC, se declara.
3. Σ de pesos pedidos ≠ 100 se muestra tal cual, nunca se normaliza en silencio.
4. FCI: peso sí, todo lo demás `s/d` y fuera de cualquier cálculo de renta/rendimiento.
5. `null` → `s/d` con `SIN_DATO` de `@/lib/fmt`.

## Test Strategy
- `lib/resolver.test.ts`: función pura. Casos: peso→VN con lámina; sin lámina (declarado, sin
  redondeo); FCI excluido del denominador de `pesoReal`; especie en ARS sin TC → `vn: null`;
  `montoTotal: 0` → todo `null`; los 4 GWT armados como fixtures de extremo a extremo sobre
  `resolver` + el store.
- `store/carteraStore.test.tsx` (extender el existente, no reescribir): `fijarPeso` no toca otras
  posiciones; `equiponderar` reparte `100/n` igual a todas; `vaciar` deja `pos: []`;
  `alternarPapel` asigna `100/(n+1)` al agregar sin tocar las demás.
- `components/CarteraEditable.test.tsx` (patrón `features/estado-dato/__tests__/`, mock de fetch):
  Σ en `--ac2` cuando ≠ 100 (assert por texto/estilo, no por color exacto); fila FCI con las
  columnas en `s/d`; diferencia pedido/real visible cuando supera 0,6 pp.

## Comandos de verificación
```
cd /Users/jeroniki/Documents/Github/10-Swaper/frontend
npx vitest run src/features/armador
npm run lint
npx tsc --noEmit
```
No correr la suite completa del frontend (F-039 trabaja en paralelo); la corre el cierre de tanda.

## Al terminar, reportar
Archivos creados/modificados, salida real de los tres comandos, y cualquier punto donde el plan no
cerró contra el código real y qué se hizo (debe ser: frenar esa parte y reportarla).
