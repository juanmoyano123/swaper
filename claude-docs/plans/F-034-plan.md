# Plan — F-034: Modo "subir la TIR declarando la contrapartida" (Tanda 14)

## Modelo de ejecución

**Planificado con Fable 5, ejecutar con Opus 5 (`claude-opus-5`)** — mismo workflow que las
tandas anteriores. Al arrancar la ejecución, guardar este plan en
`claude-docs/plans/F-034-plan.md` (formato del pipeline).

## Contexto

F-034 es la tanda 14 del plan de ejecución, la única feature de la tanda (comparte el contrato de
la fila de propuesta con F-033, mandato de `plan.md`). Spec en `claude-docs/planning/plan.md:1628`:
propone rotaciones que **suben el rendimiento**, y cada propuesta lleva **en la misma fila** los
ejes de riesgo que empeoran y en cuánto ("+1,80% de rendimiento / duración 3,5 → 5,8 años /
Ley N.Y. → Ley Argentina"). **Nunca una mejora de TIR sin contrapartida nombrada** — es la regla 8
del dominio hecha feature. GWT: (1) la fila declara mejora + todos los deltas; (2) deltas no
calculables → la fila no se muestra, pero se contabiliza por qué; (3) si ningún eje empeora, se
declara explícito, nunca columna en blanco; (4) cobertura parcial de dato se declara junto al delta.

**Verificado por exploración (dos agentes) y lectura directa:**
- **F-034 es 100% frontend.** `POST /api/v1/rotaciones` ya devuelve todo:
  `candidata.tipo === 'mejora_rendimiento'` (d_rend ≥ 0,5pp) es el complemento exacto de la banda
  ±0,5pp que usa F-033 — las dos features particionan el mismo conjunto sin solaparse. El backend
  no se toca.
- F-033 dejó el molde en tres capas: `lib/rotaciones/bajarRiesgo.ts` (lib pura),
  `hooks/useBajarRiesgo.ts` (orquestación TanStack con `useQueries` de concentraciones simuladas),
  `features/optimizador/components/SeccionBajarRiesgo.tsx` (sección montada en
  `CarteraConfirmada.tsx:64-82`).
- El zod (`esquemaRotaciones.ts`, modo strip) **no declara `costo`** — el bloque de F-035
  (arancel, spreads, total, verificable, elevado, payback) viaja y se descarta en silencio. F-035
  quedó sin UI; F-034 la estrena.
- Dos notas quedaron obsoletas al cerrar F-035: `SeccionBajarRiesgo.tsx:73-78` ("el costo todavía
  no se calcula") y `riesgo.ts:351` ("spread… llega con F-035"). Se corrigen acá.
- El memo `porTicker: Map<string, EspecieRiesgo>` está duplicado literal en
  `useBajarRiesgo.ts:48-65` y `SeccionRiesgo.tsx:33-50`; F-034 lo necesitaría por tercera vez →
  se extrae.

**Reglas duras aplicables:** 1 (nunca inventar un dato), 2 (naturalezas de tasa no comparten eje —
por eso la fila dice "Δ rendimiento", no "TIR", aunque el modo se llame así), 7 (el riesgo es un
vector de 6 ejes, jamás score), 8 (esta feature ES la regla), 11 (códigos no contemplados se
muestran literales).

## Decisiones de diseño

### D1 — Tipo nuevo `PropuestaSubirTir` sobre vocabulario compartido extraído; F-033 no se reescribe

No se generaliza `PropuestaBajarRiesgo`: F-033 tiene semántica de **filtro** (el eje primario debe
mejorar, el resto no empeorar) y F-034 de **declaración** (nada se filtra por empeorar; todo se
muestra con su contrapartida). Un tipo único acoplaría dos políticas distintas y F-036 heredaría
campos ambiguos. Lo que converge para F-036 es el **vocabulario por eje**: se extrae a
`lib/rotaciones/ejes.ts` (estados, signos, motivos de descarte, nombres, claves, cartera simulada)
y los dos modos lo comparten. `bajarRiesgo.ts` re-exporta lo que ya exportaba — **cero cambios en
imports externos ni en los tests de F-033** en el refactor.

### D2 — Qué mata la fila y qué se declara (conciliación GWT-2 / GWT-4)

**Criterio:** *un faltante en las PUNTAS de la rotación (origen/destino) para un eje medible mata
la fila — sin dato en la punta, el delta no es atribuible a la rotación (GWT-2, descarte
estructural contabilizado). Un faltante en el RESTO de la cartera no la mata: el delta agregado
existe y la cobertura parcial se declara junto al delta (GWT-4).*

- **Ejes medibles (delta requerido):** `duracion`, `legislacion`, `liquidez`, `concentracion`.
  Signos: los de `estadoPorValor` de F-033 (duración/concentración: menor=mejor;
  legislación/liquidez: mayor=mejor; legislación sigue a `mejora_ley` del motor: pasar a ley
  extranjera es la mejora).
  - `duracion`: exige `candidata.delta.duracion !== null` **además** de valores actual/simulado no
    nulos. Más estricto que F-033 a propósito: acá la fila ES el delta, y un promedio simulado que
    excluye en silencio la duración del destino violaría la regla 1.
  - `legislacion`: exige `origen.ley !== null && destino.ley !== null` (paridad exacta con
    `estadoLocal` de F-033). Si `origen.ley !== destino.ley`, la contrapartida lleva la nota
    literal `"{origen.ley} → {destino.ley}"` (regla 11 — leyes no reconocidas se muestran tal
    cual, sin delta inventado).
  - `liquidez`: exige `destino.volumen_usd !== null` (paridad F-033; el origen sin volumen no
    descarta, queda en cobertura).
  - `concentracion`: exige concentración simulada respondida y valores no nulos.
- **Ejes cualitativos (nunca descartan, siempre se declaran en palabras):**
  - `credito`: `flags.mismo_emisor` → "mismo emisor: el riesgo de crédito no cambia". Si cambia →
    `"cambia de emisor: {o.emisor} → {d.emisor} (calificación {o.calificacion ?? 'sin calificación'}
    → {d.calificacion ?? 'sin calificación'})"`. Calificación null NO descarta: crédito no tiene
    delta por regla 7; "sin calificación" es la declaración literal.
  - `moneda`: nota fija "mismo segmento: la naturaleza de la tasa no cambia" — no-empeorable por
    construcción (rotación intra-segmento, regla 2). Se declara sin calcular.
- **GWT-3:** `ningunEjeEmpeora = (ningún medible con estado 'empeora') && flags.mismo_emisor`. Si
  cambia de emisor sin empeorar ningún medible, la fila NO dice "ningún eje empeora": su
  contrapartida es el cambio de emisor. Nunca existe fila sin contrapartida nombrada.
- **Fuera de alcance ≠ descarte:** las `tipo === 'mejora_perfil'` no entran ni a propuestas ni a
  descartes — son insumo de F-033. El resumen de F-034 cuenta sólo `mejora_rendimiento`.

### D3 — Concentración simulada: dos etapas como F-033, pero la etapa 2 mide, no filtra

Etapa local (tipo + puntas + ejes locales) → `useQueries` de `POST /concentracion` sólo para
sobrevivientes → armado de filas. Única causa de descarte en etapa 2: `sin_dato`. Si la
concentración empeora, **se declara**, no se filtra. Clave
`claves.mercado.concentracion(firmaDePesos(simulada), perfil)` — comparte caché con F-033 y con
`SeccionRiesgo` (misma cartera simulada ⟹ un solo POST).

### D4 — Costo (F-035) en la fila: primera UI del costo

`costo` entra al zod como **nullable no-optional** (el backend siempre emite la clave desde
F-035). Formato:
- verificable con `total_pct`: `costo ~{fmtPct(total_pct,2)}` + si hay payback
  `· payback ~{fmtNumero(payback_meses,0)} meses`; en `--neg` si `elevado === true`.
- `!verificable`: "costo no verificable: falta punta de mercado en alguna pata — piso: arancel
  {fmtPct(arancel_pct_por_pata,2)} por pata" en `--sd` (regla 1: nunca cero inventado).
- `costo === null`: `costo: s/d`.

El mismo `NotaCosto` se agrega a la fila de F-033, lo que permite reescribir con verdad su párrafo
obsoleto.

### D5 — Reuso

- `lib/rotaciones/ejes.ts`: mover `TODOS_LOS_EJES`, `NOMBRES_EJE`, `claveCandidata`,
  `carteraSimuladaDeCandidata`, `sumarPorTicker`, `indexarPorId`, `EJES_LOCALES`; exportar lo que
  era privado: `EstadoEje`, `estadoPorValor`, `estadoLocal` (renombrada `estadoEjeLocal`),
  `MotivoDescarte`, `DescarteCandidata`. `bajarRiesgo.ts` re-exporta.
- `lib/cartera/hooks/useMapaRiesgo.ts`: envuelve `useEspeciesUniverso` + el memo `porTicker`;
  lo consumen `useBajarRiesgo`, `SeccionRiesgo` y el nuevo `useSubirTir`.
- `features/optimizador/components/compartidos.tsx`: `formatoValor`, `NotaCosto`,
  `ResumenDescartes` + `MOTIVO_LABEL` (movidos desde `SeccionBajarRiesgo`). Las filas
  (`FilaPropuesta` / `FilaSubirTir`) quedan separadas: estructuras distintas por diseño.

## Tipos nuevos (`lib/rotaciones/subirTir.ts`)

```ts
export interface CoberturaContrapartida {
  /** round(pesoConDato/pesoTotal*100) de EjeDeRiesgo.cobertura; null si pesoTotal === 0. */
  pctActual: number | null
  pctSimulada: number | null
  /** true si alguno de los dos < 100 — GWT-4: se declara junto al delta. */
  parcial: boolean
}

export interface EvaluacionEje {
  eje: IdDeEje
  /** Medibles: mejora|no_empeora|empeora (nunca sin_dato acá: eso descartó la fila antes).
   *  Crédito y moneda: 'cualitativo' siempre (regla 7: sin delta numérico). */
  estado: 'mejora' | 'no_empeora' | 'empeora' | 'cualitativo'
  valorActual: number | null      // null en cualitativos
  valorSimulado: number | null
  unidad: EjeDeRiesgo['unidad']
  cobertura: CoberturaContrapartida | null   // null en cualitativos
  /** Declaración literal: "{o.ley} → {d.ley}", cambio de emisor/calificación, naturaleza. */
  nota: string | null
}

export interface PropuestaSubirTir {
  candidata: Candidata
  /** SIEMPRE las 6, en el orden de ORDEN_EJES de riesgo.ts — regla 7: viaja el vector entero. */
  ejes: EvaluacionEje[]
  /** GWT-3: ningún medible empeora Y mismo emisor. La UI lo declara explícito. */
  ningunEjeEmpeora: boolean
}

export interface ResultadoSubirTir {
  hayPropuesta: boolean
  propuestas: PropuestaSubirTir[]       // orden del backend, no se reordena
  descartes: DescarteCandidata[]        // GWT-2, patrón ResumenDescartes
  /** mejora_rendimiento evaluadas (mostradas + descartadas). */
  evaluadas: number
}
```

Zod aditivo en `esquemaRotaciones.ts` (verificar nullabilidad de `arancel_pct_por_pata` contra
`backend/app/rotaciones/costos.py` antes de fijar):

```ts
export const esquemaCostoRotacion = z.object({
  arancel_pct_por_pata: z.number(),
  spread_origen_pct: z.number().nullable(),
  spread_destino_pct: z.number().nullable(),
  total_pct: z.number().nullable(),
  verificable: z.boolean(),
  elevado: z.boolean().nullable(),
  payback_meses: z.number().nullable(),
})
// en esquemaCandidata:  costo: esquemaCostoRotacion.nullable(),
```

`cupon` sigue sin declararse (no se usa; strip lo tolera).

## Lógica de evaluación (pseudocódigo prescriptivo)

```
evaluarEtapaLocalSubirTir(candidatas, vectorActual, posiciones, porTicker):
  elegibles = candidatas.filter(c => c.tipo === 'mejora_rendimiento')
  actual = indexarPorId(vectorActual)
  para cada c:
    sim = indexarPorId(vectorDeRiesgo(carteraSimuladaDeCandidata(posiciones, c), porTicker, null))
    eje = primerEjeSinDelta(c, actual, sim)
    eje !== null ? descartes.push({candidata: c, eje, motivo: 'sin_dato'}) : sobrevivientes.push(c)
  return { sobrevivientes, descartes, evaluadas: elegibles.length }

primerEjeSinDelta(c, actual, sim):          // orden fijo, un descarte por candidata (paridad F-033)
  c.delta.duracion === null                        → 'duracion'
  c.origen.ley === null || c.destino.ley === null  → 'legislacion'
  c.destino.volumen_usd === null                   → 'liquidez'
  para eje en ['duracion','legislacion','liquidez']:
    actual[eje].valor === null || sim[eje].valor === null → eje
  → null

evaluarSubirTir(candidatas, vectorActual, posiciones, porTicker, concentracionesSimuladas):
  local = evaluarEtapaLocalSubirTir(...)     // re-corre local, barato (TOP_N=3 por origen)
  para cada c en local.sobrevivientes:
    concSim = concentracionesSimuladas.get(claveCandidata(c)) ?? null
    sim = indexarPorId(vectorDeRiesgo(carteraSimuladaDeCandidata(posiciones, c), porTicker, concSim))
    actual.concentracion.valor === null || sim.concentracion.valor === null
      ? descartes.push({eje: 'concentracion', motivo: 'sin_dato'})
      : propuestas.push(armarPropuesta(c, actual, sim))
  return { hayPropuesta, propuestas, descartes: [...local.descartes, ...], evaluadas }

armarPropuesta(c, actual, sim):
  ejes = TODOS_LOS_EJES.map:
    medible (duracion|legislacion|liquidez|concentracion):
      estado = estadoPorValor(eje, actual[eje].valor, sim[eje].valor)   // non-null garantizado
      nota   = eje === 'legislacion' && c.origen.ley !== c.destino.ley
                 ? `${c.origen.ley} → ${c.destino.ley}` : null
      cobertura = coberturaDe(actual[eje].cobertura, sim[eje].cobertura)
    'credito':  estado 'cualitativo', nota según mismo_emisor (D2), valores/unidad/cobertura null
    'moneda':   estado 'cualitativo', nota fija (D2)
  ningunEjeEmpeora = !ejes.some(e => e.estado === 'empeora') && c.flags.mismo_emisor

coberturaDe(cobA, cobS):
  pct(x) = x.pesoTotal > 0 ? Math.round(100 * x.pesoConDato / x.pesoTotal) : null
  { pctActual, pctSimulada, parcial: (a !== null && a < 100) || (s !== null && s < 100) }
```

## Hook y UI

**`hooks/useSubirTir.ts`**: espejo de `useBajarRiesgo.ts` línea por línea, sin `ejePrimario`.
`useMapaRiesgo()` + `useConcentracion` + `useRotaciones` + `useQueries` idéntico
(`TIEMPOS.mercado`, `retry: false`) + `evaluarSubirTir` cuando `rotaciones.data &&
!cargandoConcentracion`. Devuelve `{ cargando, error, resultado }`.

**`components/SeccionSubirTir.tsx`**: `<section aria-label="Subir la TIR declarando la
contrapartida">`, hermana apilada debajo de `SeccionBajarRiesgo` en `CarteraConfirmada.tsx`
(mismo bloque condicional, mismo `perfil`; ajustar el label del select a algo neutro tipo
"Perfil para las rotaciones" — grep por tests que aserten el texto viejo). Fila (`FilaSubirTir`):

1. `{origen.ticker} → {destino.ticker}` (mono `--tx`) + `Δ rendimiento +{fmtPct(delta.rendimiento_pp, 2)}`
   (mono `--ac`) — "Δ rendimiento" y no "TIR", regla 2 (una tasa real CER no es una TIR en USD).
2. **La contrapartida** — `contrapartidas = ejes.filter(estado === 'empeora')` más crédito si
   `!mismo_emisor`:
   - Con contrapartidas: `"Contrapartida: duración 3,5 → 5,8 años · peso bajo ley extranjera
     100% → 0% (Ley N.Y. → Ley Argentina) · cambia de emisor: …"` — valores con `formatoValor`
     compartido; el copy de legislación siempre nombra "peso bajo ley extranjera" + nota literal
     de leyes, nunca "legislación sube/baja" a secas (riesgo de leerse como score, regla 7).
   - Con `ningunEjeEmpeora`: texto explícito "Ningún eje empeora: la mejora de rendimiento no
     tiene contrapartida en los seis ejes." (GWT-3).
3. (condicional, `--sd`) coberturas parciales: `"cobertura parcial: duración medida sobre el 80%
   del peso actual y el 75% del simulado"` (GWT-4).
4. `candidata.riesgo_nota` literal (`--dim`).
5. `<NotaCosto costo={candidata.costo} />` (D4).

Debajo de la lista, `ResumenDescartes` con encabezado propio: `"{evaluadas} rotaciones que suben
el rendimiento; {mostradas} mostradas, {descartadas} sin mostrar:"`. `MOTIVO_LABEL.sin_dato` en
este modo: "sin dato para calcular el delta". Sin `mejora_rendimiento` en la respuesta:
`role="status"` "El motor no encontró rotaciones que suban el rendimiento en esta cartera."

## Etapas

> Verificación por etapa desde `frontend/`: `npx vitest run && npx tsc -b && npx oxlint && npm
> run build`. Commit por etapa con pathspec explícito en `develop`.

### Etapa 1 — Refactor sin comportamiento
`ejes.ts` + `useMapaRiesgo.ts`; `bajarRiesgo.ts` re-exporta; `useBajarRiesgo.ts` y
`SeccionRiesgo.tsx` usan el hook nuevo. **Criterio de éxito: suite completa verde sin editar un
solo test.**

### Etapa 2 — Contrato de costo
`esquemaCostoRotacion` + `costo` nullable en `esquemaCandidata`. Actualizar fixtures que fallen el
parse (`esquemaRotaciones.test.ts`, payload mockeado de `SeccionBajarRiesgo.test.tsx`, factory
`candidata()` de `bajarRiesgo.test.ts` gana `costo: null` explícito). Casos de parse: costo
verificable, costo null.

### Etapa 3 — Costo visible en F-033 + notas obsoletas
`compartidos.tsx` (mover `formatoValor`, `ResumenDescartes`+`MOTIVO_LABEL`; crear `NotaCosto`);
`SeccionBajarRiesgo.tsx` suma `NotaCosto` a su fila y reescribe el párrafo 73-78 (sigue sin botón
de aceptar, pero el costo ya se declara por candidata); `riesgo.ts:351` corrige la nota del spread
(viaja en el costo por rotación, no entra al percentil). Grep por tests que aserten los textos
viejos.

### Etapa 4 — Lib pura + tests
`subirTir.ts` + `__tests__/subirTir.test.ts`. Factories copiados de `bajarRiesgo.test.ts` (no
acoplar los archivos), `tipo: 'mejora_rendimiento'` y `delta.rendimiento_pp: 1.8` por default.
Copiar el comentario-trampa del percentil de liquidez (mismo `porTicker` para vector actual y
evaluación — `bajarRiesgo.test.ts:106-110`).

### Etapa 5 — Hook + sección + montaje
`useSubirTir.ts`, `SeccionSubirTir.tsx`, montaje en `CarteraConfirmada.tsx`,
`__tests__/SeccionSubirTir.test.tsx` (mock supabase + `vi.stubGlobal` fetch con router por
substring: universo / `/rotaciones` / `/concentracion`; queries por rol y aria-label).

### Etapa 6 — Cierre
`PROGRESS.md` (F-034 completada + nota de decisiones), `plan-ejecucion-tandas.md` (tanda 14
completada), `docs/guia-armador.md` sólo si nombra el optimizador, nota en `design-system.md` si
la fila introduce patrones nuevos (NotaCosto).

## Mapeo GWT → tests

| GWT | Lib (`subirTir.test.ts`) | UI (`SeccionSubirTir.test.tsx`) |
|---|---|---|
| 1 | destino con duración 5,8 vs 3,5 y ley 'Ley Argentina' → duracion `empeora` (3.5→5.8, 'años'), legislacion `empeora` con nota `'Ley N.Y. → Ley Argentina'`, `ningunEjeEmpeora === false` | la fila muestra "+1,80%", "3,5 → 5,8 años" y "Ley N.Y. → Ley Argentina" juntos |
| 2 | `delta.duracion: null` → `propuestas: []`, descarte `{eje:'duracion', motivo:'sin_dato'}`, `evaluadas: 1`; variante concentración simulada null → descarte 'concentracion' | resumen "1 sin mostrar … sin dato para calcular el delta"; la fila no está en el DOM |
| 3 | destino mejora/iguala todo, mismo emisor → `ningunEjeEmpeora === true` | `getByText(/ningún eje empeora/i)` |
| 4 | tercera posición sin duración → propuesta presente, `cobertura.parcial === true` con pcts correctos | "cobertura parcial: duración …" en la fila |
| extra | `mejora_perfil` no entra ni a propuestas ni a descartes; cambio de emisor sin calificación → nota literal "sin calificación", `ningunEjeEmpeora === false`; moneda con nota siempre | costo verificable y no verificable renderizados |

## Riesgos

- **Igualdad flotante en `estadoPorValor`** (`simulado === actual` exacto): ruido de float puede
  volver un "no empeora" en contrapartida "+0,0". Acá no filtra (sólo muestra), así que se mantiene
  la paridad con F-033 sin epsilon; si QA muestra un "0,0", introducir el epsilon en `ejes.ts`
  para los dos modos a la vez.
- **Nullabilidad de `arancel_pct_por_pata`**: verificar el dataclass en `costos.py` antes de fijar
  el zod; si es nullable, el copy del piso cae a `SIN_DATO`.
- **Semántica invertida de legislación** (valor = peso bajo ley extranjera, mayor=mejor): el copy
  nunca dice "legislación baja/sube" a secas — siempre "peso bajo ley extranjera X% → Y%" + leyes
  literales.
- **Ley no reconocida** (ni local ni extranjera): el valor del eje la excluye (riesgo.ts) pero la
  nota literal la muestra igual — regla 11 sin delta inventado.
- **Tests de F-033 que asertan textos que se mueven** (párrafo obsoleto, `MOTIVO_LABEL`): grep
  antes de mover, actualizar uno a uno leyendo qué afirmaban.

## Verificación final

1. Suite completa: `npx vitest run` (frontend, hoy 625), `pytest` backend intacto (1160, cero
   cambios esperados), `tsc -b`, `oxlint`, `npm run build`.
2. Contra el backend real (venv + uvicorn): cargar una cartera en `/optimizador` y verificar que
   la sección nueva muestra propuestas `mejora_rendimiento` con contrapartida por eje, el costo de
   F-035 por primera vez en pantalla, y el resumen de descartes.
3. Navegador (claude-in-chrome): sección visible, aria-labels correctos, ningún texto "el costo no
   se calcula" remanente.
