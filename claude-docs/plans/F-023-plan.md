# F-023 — Composición y curva TIR/duración

## Spec (plan.md:1155-1184)

Composición de la cartera por emisor, sector, clase de activo (soberano / subsoberano / ON) y
segmento. Curva TIR/duración del segmento activo: la nube de candidatos del segmento con las
posiciones de la cartera marcadas de forma distinguible. Un segmento por gráfico, unidad del eje
declarada — nunca dos naturalezas de tasa en el mismo par de ejes. Sector no informado agrupado
como "sector no informado", nunca repartido.

```
GIVEN una cartera con posiciones de dos segmentos
WHEN se muestra la curva TIR/duración
THEN se grafica un solo segmento por vez, con la unidad del eje de rendimiento declarada

GIVEN el segmento activo seleccionado
WHEN se muestra la curva
THEN las posiciones de la cartera están marcadas de forma distinguible sobre la nube de candidatos
     del mismo segmento

GIVEN posiciones con sector no informado
WHEN se muestra la composición por sector
THEN aparecen agrupadas como "sector no informado", con su porcentaje, y no repartidas entre los
     sectores conocidos
```

Depende de F-018 (hecha). Sin mockup en `design-system.md` — el relevamiento de monitores
(`plan.md:2898`) sugiere familia por color (Bonares/Globales/Bopreal), pero **queda fuera de
alcance**: `/universo/emisiones/especies` no expone `subtipo`, y derivarla del prefijo del ticker
está prohibido (regla 11, `plan.md:2909`).

## Dónde se monta

`ArmadorPage.tsx` ya tiene el stub `PanelComposicion` montado entre `PanelRendimientos` y
`PanelConcentracion` (base común de la tanda). **No tocar `ArmadorPage.tsx`.**

## Qué NO duplicar (crítico)

`PanelConcentracion.tsx` (F-020) ya muestra distribución por **sector**, ley y naturaleza, desde
`/concentracion`. El GWT-3 de esta ficha ("sector no informado agrupado, no repartido") **ya está
satisfecho por ese panel en la misma pantalla**. No se pide `/concentracion` de nuevo ni se
recalcula el corte por sector en el frontend — sería una segunda fuente del mismo hecho (riesgo
R12 de `plan.md:2774`: dos números del mismo dato). El plan prescriptivo de esta feature es
explícito: **`PanelComposicion` no toca sector.**

Lo que sí agrega, porque F-020 no lo muestra: **clase de activo**, **segmento** y **emisor**.

## Archivos

Todos nuevos, dueño único de esta feature:
- `frontend/src/features/armador/components/PanelComposicion.tsx` — reemplaza el stub.
- `frontend/src/features/armador/components/CurvaTirDuracion.tsx` — nuevo.
- `frontend/src/features/armador/lib/composicion.ts` — nuevo, funciones puras.
- `frontend/src/features/armador/__tests__/composicion.test.ts` — nuevo.
- `frontend/src/features/armador/__tests__/CurvaTirDuracion.test.tsx` — nuevo.
- `frontend/src/features/armador/__tests__/PanelComposicion.test.tsx` — nuevo.

## `lib/composicion.ts`

Tres funciones puras, mismo patrón que `lib/rendimientos.ts` (ahora shim de `@/lib/cartera/
metricas`, léelo como referencia de estilo): reciben `(resueltas: PosicionResuelta[], porTicker:
Map<string, Especie>)` — importar `PosicionResuelta` de `../lib/resolver` y `Especie` de
`../lib/schema` (sigue siendo el import correcto: `schema.ts` re-exporta `Especie` desde
`@/lib/cartera/esquemaEspecie`, no hace falta importar de `@/lib/cartera` directo).

```ts
export interface TramoComposicion {
  nombre: string
  peso: number
  sinDato?: boolean
}

export function composicionPorClase(resueltas, porTicker): TramoComposicion[]
export function composicionPorSegmento(resueltas, porTicker): TramoComposicion[]
export function composicionPorEmisor(resueltas, porTicker): TramoComposicion[]
```

Ponderación: `pesoReal ?? peso` — mismo criterio que `PanelConcentracion.tsx:76-81` (`posiciones =
resueltas.map(r => ({ ticker: r.ticker, peso: r.pesoReal ?? r.peso }))`, `conPesoReal` contado
para la leyenda). El panel muestra la misma leyenda que `PanelConcentracion` (`leyendaDelPeso`,
`PanelConcentracion.tsx:159-166`) — se puede portar la función tal cual, adaptada al nombre local,
o extraerse a `lib/composicion.ts` como helper compartido entre los dos textos.

**Por clase de activo**: agrupa por `especie.clase_activo`. Antes de agrupar, colapsa
`bono_soberano` en un único tramo (regla 4: todas las emisiones del Tesoro son un solo crédito,
`SOBERANO_AR`) — es aritmética sobre un dato declarado (`clase_activo === 'bono_soberano'`), no
inferencia. `clase_activo` no es nullable en `Especie`, así que este corte no tiene tramo
`sinDato`.

**Por segmento**: agrupa por `especie.segmento`, nombre vía `nombreSegmento()` de
`@/components/SelectorSegmento`. Tampoco nullable.

**Por emisor**: agrupa por `especie.emisor`. `emisor: string | null` — `null` va al tramo "emisor
no informado" (`sinDato: true`), nunca repartido entre los conocidos (regla 1). Ordenar por peso
descendente.

Una posición sin `porTicker.get(ticker)` (fuera del universo) se excluye de los tres cortes,
mismo criterio que `filas()` en `metricas.ts`.

## `components/CurvaTirDuracion.tsx`

Referencia de estilo: `features/monitor/components/CurvaSegmento.tsx` (no se importa — está fuera
de alcance tocarlo, ver D2 del plan de tanda). Esta versión necesita **dos series**, cosa que
`CurvaSegmento` no tiene:

```ts
export function CurvaTirDuracion({
  candidatos,   // Especie[] del segmento activo (universo completo, ya filtrado)
  cartera,      // Especie[] de las posiciones de la cartera en ese segmento
  naturaleza,   // string — para unidadDeNaturaleza()
}: { candidatos: Especie[]; cartera: Especie[]; naturaleza: string })
```

- Filtro igual a `CurvaSegmento`: sólo especies con `rendimiento !== null && duracion !== null`.
  Excluidas de cada serie contadas y declaradas al pie por separado ("N candidatos sin dato", "N
  posiciones de la cartera sin dato").
- Dos `<Scatter>` dentro del mismo `<ScatterChart>`: la nube con `fill="var(--dim)"` o `var(--ac2)`
  (color apagado, es el fondo), la serie de cartera con `fill="var(--ac)"` y **`<LabelList
  dataKey="ticker" />`** (recharts) para rotular el ticker sobre cada punto de cartera — la nube no
  se rotula, sería ilegible con cientos de puntos.
- Eje Y con `unidadDeNaturaleza(naturaleza)`, igual que `CurvaSegmento`.
- Tooltip propio (puede ser el mismo `TooltipPunto` adaptado para declarar de qué serie es el
  punto).
- `candidatos.length === 0` (segmento sin universo) → mensaje, no gráfico vacío, igual criterio
  que `CurvaSegmento.tsx:33-38`.
- Una posición de cartera cuyo ticker no aparece en `candidatos` (normal: `candidatos` es el
  universo del segmento *activo*, una posición de otro segmento no entra) simplemente no se
  grafica en esa vista — es correcto, no un bug: el usuario ve un segmento por vez.

## `components/PanelComposicion.tsx`

Reemplaza el `return null` del stub. Estructura:

1. `const { resueltas, porTicker } = useCarteraResuelta()` (hook existente, sin tocar).
2. `resueltas.length === 0` → mensaje vacío, mismo estilo que `PanelRendimientos.tsx:30-45`.
3. Tres `<DistribucionBarras>` (clase, segmento, emisor) — mismo componente que ya usa
   `PanelConcentracion`, import de `@/components/DistribucionBarras`.
4. Selector de segmento propio: `<SelectorSegmento segmentos={...} activo={...} onCambio={...} />`
   de `@/components/SelectorSegmento`. Los segmentos que se ofrecen son los **presentes en la
   cartera** (no el universo entero), expandidos por crédito con `expandirSegmentos()` — mismo
   criterio que el monitor, para que `usd_hard` no mezcle soberano/subsoberano/ON en una sola
   nube. Default: el de mayor peso (`composicionPorSegmento(...)[0]`, ya viene ordenado).
5. Con el segmento activo elegido: `useEspeciesUniverso()` (hook compartido, ya existe) filtrado
   por ese segmento (y por `clase_activo` si la clave viene partida por crédito — usar
   `segmentoDeClave()`/`claseDeClave()` de `SelectorSegmento`) → `candidatos`. Las posiciones de
   la cartera en ese mismo segmento → `cartera`. Pasar los dos a `<CurvaTirDuracion>`.
6. `naturaleza` para el eje: la de cualquier especie del segmento (todas comparten naturaleza
   dentro de un mismo `segmento`/`clase`, es el fundamento de `SEGMENTO_POR_CREDITO`).

**Filtrado de `useEspeciesUniverso()` por moneda de cotización, una vez por vez**: si el segmento
tiene hermanas (misma emisión cotizando en ARS y USD, o en distintos plazos de liquidación), no
filtrar por moneda haría aparecer 2-3 puntos por la misma emisión. Seguir el precedente del
monitor (`MonitorPage.tsx`): elegir la moneda de cotización dominante del segmento (o exponer un
segundo selector chico si el plan de la feature lo justifica al implementarse — decisión de
implementación, no bloqueante).

## Edge cases (todos con test)

- Cartera vacía o sin renta fija → mensaje, sin gráfico ni distribución.
- Segmento sin ningún candidato con rendimiento+duración → "no hay curva que dibujar" (mismo texto
  que `CurvaSegmento`).
- Posición de cartera sin dato en el segmento activo → no se marca en el scatter, se cuenta.
- Emisor no informado → tramo "emisor no informado", `sinDato: true`, nunca repartido.
- Todas las posiciones son `bono_soberano` con distintos prefijos (GD/AE/DIC/TZX/TY3) → un único
  tramo "Riesgo soberano" en composición por clase (regla 4).
- Ninguna posición tiene `pesoReal` (nada resuelto a precio) → se pondera por `peso`, leyenda lo
  dice.
- Sin familia por color: no se agrega ningún control de color por Bonares/Globales/Bopreal — está
  fuera de alcance (ver spec arriba).

## Zonas prohibidas

`ArmadorPage.tsx`, todo `src/lib/cartera/`, `features/monitor/**` (incluido `CurvaSegmento.tsx`,
que sirve sólo de referencia de lectura), `features/cartera-diagnostico/**`, cualquier archivo del
armador que no esté en la lista de "Archivos" arriba, `PanelConcentracion.tsx` (no se toca ni se
le agrega el corte de emisor/clase/segmento — vive en el panel nuevo).

## Verificación

```
cd frontend
npx vitest run src/features/armador
npx tsc -b
npm run lint
```

Manual: en `/armador`, con al menos una posición cargada, el panel de composición debe mostrar los
tres cortes nuevos (clase, segmento, emisor) y la curva del segmento con mayor peso, con la
cartera marcada y rotulada sobre la nube.
