# F-031 — Vector de riesgo de seis ejes

## Spec (plan.md:1490-1538)

El perfil de riesgo de una cartera es un **vector de seis ejes, no un score**: duración, crédito,
legislación, liquidez, concentración y moneda. Cada eje con su métrica, su unidad y su cobertura
de dato declarada al lado. Nunca se colapsan en un número único. Se rinde igual para la cartera
cargada, la que se está construyendo y cualquier propuesta futura. Donde falta la calificación se
usan y se declaran los proxies ya calibrados; **la calificación nunca se usa como filtro
automático**.

```
GIVEN una cartera cualquiera
WHEN se muestra su perfil de riesgo
THEN aparecen seis ejes separados, y no existe en la interfaz ningún número único de riesgo ni
     control que los combine

GIVEN el eje de crédito
WHEN se lo muestra
THEN lleva al lado la cobertura de calificación de la cartera, y las posiciones sin calificación
     figuran como tales

GIVEN una cartera con posiciones sin calificación
WHEN el asesor arma o rota
THEN la calificación no filtra automáticamente ningún candidato; los proxies usados están
     declarados

GIVEN GD30, AE38 y TZX26 en la cartera
WHEN se calcula el eje de concentración
THEN los tres cuentan bajo la clave única SOBERANO_AR

GIVEN una cartera cargada, una en construcción y una propuesta
WHEN se muestran los tres perfiles
THEN los seis ejes se calculan y se presentan igual en los tres casos
```

Depende de F-005, F-009, F-012, F-020, F-030 — todas cerradas. Riesgo R5 (`plan.md:2722`): la
calificación existe para el 39 % del universo, y es tentador rellenarla — no se hace nunca. Riesgo
R12 (`plan.md:2774`): "F-031 es un servicio único consumido por los tres" perfiles. Por eso esta
feature es **una lib pura + un componente de presentación, compartidos**, no un panel por pantalla
con su propia lógica.

## Qué ya dejó la base común de la tanda

1. `EspecieUniverso` (backend) y `Especie` (frontend, `@/lib/cartera/esquemaEspecie`) ya exponen
   `calificacion: string | null` — texto libre de `condiciones_emision`, 359 de 823 tickers
   curados (39 %). **No se toca ni se ordena**: se agrupa por string exacto.
2. Stubs montados y con sus props ya fijadas — **no editar los archivos que los montan**:
   - `features/armador/components/PanelRiesgo.tsx` — `return null`, sin props (arma las suyas
     adentro, mismo patrón que `PanelConcentracion`). Montado en `ArmadorPage.tsx` después de
     `<PanelConcentracion />`.
   - `features/cartera-diagnostico/components/SeccionRiesgo.tsx` — `return null`, props ya
     fijadas: `{ posiciones: { ticker: string; peso: number }[]; perfil: NombreDePerfil }`.
     Montado en `DiagnosticoCartera.tsx` después de `<SeccionConcentracion />`, recibiendo
     `posicionesConPeso` y `perfil` que ya existen ahí.

## Archivos (dueño único: F-031)

- `frontend/src/lib/cartera/riesgo.ts` — nuevo, lib pura, sin red.
- `frontend/src/lib/cartera/__tests__/riesgo.test.ts` — nuevo.
- `frontend/src/components/VectorDeRiesgo.tsx` — nuevo, presentacional puro.
- `frontend/src/components/__tests__/VectorDeRiesgo.test.tsx` — nuevo.
- `frontend/src/features/armador/components/PanelRiesgo.tsx` — reemplaza el `return null`.
- `frontend/src/features/armador/__tests__/PanelRiesgo.test.tsx` — nuevo.
- `frontend/src/features/cartera-diagnostico/components/SeccionRiesgo.tsx` — reemplaza el
  `return null`. La firma de props **no se cambia** (la fijó la base común).
- `frontend/src/features/cartera-diagnostico/__tests__/SeccionRiesgo.test.tsx` — nuevo.

Sin cambios backend. Sin cambios en `queryKeys.ts` (se reusan las claves existentes de
`useEspeciesUniverso`/`useConcentracion`).

## `lib/cartera/riesgo.ts` — el vector

Patrón exacto de `metricas.ts`: tipos de entrada **estructurales**, no importados de ninguna
feature, para que armador, diagnóstico y una futura propuesta (F-033+) pasen su tipo más
específico sin adaptar nada.

```ts
export type IdDeEje = 'duracion' | 'credito' | 'legislacion' | 'liquidez' | 'concentracion' | 'moneda'

/** Lo que el vector necesita de una especie del universo, sin importar de dónde salió. */
export interface EspecieRiesgo {
  ticker: string
  segmento: string
  naturaleza: string
  naturaleza_nombre: string
  clase_activo: string
  duracion: number | null
  ley: string | null
  volumen_usd: number | null
  calificacion: string | null
  dato_sano: boolean
}

/** Una posición con su peso, sin importar si viene del armador, del diagnóstico o de una
 *  propuesta que todavía no existe — es la misma forma que ya usan `useConcentracion` y
 *  `rendimientosPorNaturaleza`. */
export interface PosicionConPeso {
  ticker: string
  peso: number
}

export interface TramoDeEje {
  nombre: string
  valor: number
  unidad: 'pp' | 'percentil'
  sinDato: boolean
  /** El tope del perfil contra el que se mide este tramo, cuando aplica (eje concentración). */
  tope: number | null
}

export interface GrupoDeEje {
  titulo: string
  tramos: TramoDeEje[]
}

export interface CoberturaDeEje {
  conDato: number
  posiciones: number
  pesoConDato: number
  pesoTotal: number
  /** Faltantes estructurales declarados: "sin calificación", "spread aún no disponible", etc. */
  notas: string[]
}

export interface EjeDeRiesgo {
  id: IdDeEje
  nombre: string
  /** Métrica escalar del eje, o `null` cuando el eje es puramente compositivo o no se pudo medir. */
  valor: number | null
  unidad: 'años' | 'percentil' | 'pp' | null
  grupos: GrupoDeEje[]
  cobertura: CoberturaDeEje
}

export function vectorDeRiesgo(
  posiciones: PosicionConPeso[],
  porTicker: ReadonlyMap<string, EspecieRiesgo>,
  concentracion: Concentracion | null,  // de @/lib/cartera/esquemaConcentracion, o null si no hay
): EjeDeRiesgo[]  // SIEMPRE seis, orden fijo: duracion, credito, legislacion, liquidez, concentracion, moneda
```

No existe en ningún tipo un campo que agregue los seis — es la garantía estructural del GWT-1: no
hay dónde poner un score aunque alguien quisiera.

### Preprocesamiento común

Sumar pesos por ticker repetido (mismo criterio que `_sumar_por_ticker` del backend). Un ticker
sin especie en `porTicker` (fuera del universo de renta fija) cuenta como **sin dato en los seis
ejes**, y se nombra en cada `cobertura.notas`: `"N posición(es) fuera del universo de renta
fija"`.

### Eje por eje

1. **Duración** (`unidad: 'años'`). `valor = Σ(duracion·peso) / Σ(peso con duracion)` sobre
   posiciones con `duracion !== null`. Un solo grupo, sin tramos (o un tramo único con el propio
   valor — decisión de implementación menor). **Difiere a propósito de `plazoPromedio()`**
   (`@/lib/cartera/metricas`), que divide por 100 y trata el peso sin dato como si pesara cero en
   vez de excluirlo del promedio: acá se pondera sólo sobre el peso *con* duración, y la nota de
   cobertura dice explícitamente "sobre el X % del peso con duración informada" para que las dos
   cifras convivan en las mismas pantallas sin contradecirse en silencio.
2. **Crédito** (`valor: null`, es compositivo). Dos grupos:
   - `"Clase"`: tramos por `clase_activo` (soberano/subsoberano/corporativo — mismo vocabulario
     que `categoria_credito` del CLI), cobertura 100 %.
   - `"Calificación"`: un tramo por string exacto de `calificacion` (orden por peso descendente,
     **nunca alfabético ni por severidad** — no hay escala canónica) + un tramo
     `"sin calificación"` con `sinDato: true`. `cobertura.conDato` = posiciones con calificación
     no nula. `cobertura.notas` incluye, cuando `conDato < posiciones`: *"sin calificación en N
     posiciones: el armado y las rotaciones usan los proxies del perfil (tope de rendimiento del
     segmento, percentil de liquidez, topes de concentración) — la calificación nunca filtra"*
     (satisface el GWT-3 literalmente).
3. **Legislación** (`unidad: 'pp'`). `valor` = peso bajo ley extranjera. Conjunto exacto, calcado
   de `tools/detectar_swaps.py:81-82`: `LEY_LOCAL = 'Ley Argentina'`,
   `LEYES_EXTRANJERAS = new Set(['Ley N.Y.', 'Ley Europea', 'Extranjera'])`. Un grupo único con
   tramos por string crudo de `ley` (incluye `"ley no informada"` con `sinDato: true` — cubre
   tanto lo nunca informado como las 12 especies con ley en conflicto, que el backend ya manda con
   `ley: null`). Un valor de `ley` fuera de los dos conjuntos conocidos no se fuerza a ninguno de
   los dos lados del escalar: queda fuera del `valor` agregado y se nombra en `notas` (no se
   silencia ni se asume local).
4. **Liquidez** (`unidad: 'percentil'`). Percentil de `volumen_usd` de cada posición **dentro de
   su propio segmento**, sobre las especies sanas (`dato_sano && volumen_usd !== null`) de ese
   segmento en `porTicker.values()`: `100 · (#especies del segmento con volumen_usd ≤ v) / n`. El
   `valor` del eje es el percentil ponderado por peso de cartera — agregación defendible porque el
   percentil es adimensional (0-100 en cualquier segmento) — y **la agregación se muestra
   abierta**: un `GrupoDeEje` con un tramo por segmento (percentil ponderado de ese segmento,
   `unidad: 'percentil'`), para que el número global nunca sea lo único visible. `notas` declara
   el faltante estructural: *"spread bid/ask: la tabla existe pero no viaja por el API todavía —
   llega con F-035"*.
5. **Concentración** (`unidad: 'pp'`). **No se recalcula nada** — lee el `Concentracion` que ya
   llegó por `useConcentracion` (cache-hit con el panel de F-020/F-030 gracias a la misma
   queryKey). `valor` = el máximo `peso` entre los topes de tipo `soberano` y `emisor` de
   `concentracion.topes`. Un `GrupoDeEje` con dos tramos: `"máximo por crédito"` (el tope de mayor
   peso entre soberano/emisor, con `tope` = su límite) y `"máximo por sector"` (ídem tipo
   `sector`), más `"sin sector informado"` = `concentracion.sectores.peso_sin_sector` con
   `sinDato: true`. `SOBERANO_AR` llega hecho del backend en `concentracion.topes` (GWT-4, ya
   verificado por los tests de F-020 — este eje sólo lo lee). Si `concentracion === null`: `valor:
   null`, `grupos: []`, `notas: ["eje no medido: sin respuesta del servicio de concentración"]` —
   el hueco se declara, nunca se estima.
6. **Moneda** (`valor: null`, es compositivo). Reusa `rendimientosPorNaturaleza` de
   `@/lib/cartera/metricas`, adaptando `posiciones` a `PosicionPonderada` con
   `pesoReal: null` (para que `pesoDe()` caiga a `peso`, que es lo único que este eje tiene) y
   `porTicker` a `EspecieMetricas` (subconjunto estructural de `EspecieRiesgo`: ya cumple). Un
   grupo con un tramo por naturaleza (`nombre: r.nombre`, `valor: r.pctCartera`); se descarta
   `rendimientoPond` — este eje mide composición, no rendimiento. Cobertura 100 % por
   construcción: la naturaleza sale del segmento, que toda especie sana tiene.

## `components/VectorDeRiesgo.tsx`

Presentacional puro, sin hooks: `({ ejes }: { ejes: EjeDeRiesgo[] })`. **Seis barras paralelas,
nunca radar** (`claude-docs/progress/boceto.html:242-245`: "el área de un radar se lee como
puntaje"). Por eje, una fila: nombre + valor formateado (mono, con `fmtNumero`/`fmtPct`/`SIN_DATO`
según `unidad`) + pista con barra + línea de cobertura (`"318 de 927 con calificación (34%)"` o
equivalente, usando `cobertura`). Escala de la barra, por eje y declarada en el componente (no en
la lib — es presentación):
- duración: `valor / 10` años, tope 1.
- liquidez: `valor / 100` (ya es percentil).
- concentración: `valor / tope` del tramo de mayor peso, estilo `FilaDeTope` de
  `PanelConcentracion.tsx` (línea vertical marcando el tope).
- crédito y moneda (compositivos): mini-tramos apilados, mismo lenguaje visual que
  `DistribucionBarras` (reusarlo directamente para el grupo, en vez de reinventar una barra
  apilada — cada `GrupoDeEje.tramos` ya tiene la forma casi idéntica a `TramoDistribucion`, sólo
  cambia `valor` por `peso` al mapear).
- legislación: barra simple `valor / 100`.

Estética: contenedor de `Panel.tsx`, "el aviso se tiñe, el fondo no" (mismo criterio que
`PanelConcentracion`). **No existe ningún elemento del componente que combine los seis** — ni una
suma, ni un promedio, ni un color único de "riesgo total" (GWT-1, verificado también en el test
del componente).

## Wrappers — una pantalla cada uno

**`PanelRiesgo.tsx`** (armador): mismo patrón que `PanelConcentracion.tsx` —
`useCarteraResuelta()` → `posiciones = resueltas.map(r => ({ ticker: r.ticker, peso: r.pesoReal ??
r.peso }))` con su propia leyenda de peso (reusar `leyendaDelPeso` local, calcado del patrón de
`PanelConcentracion:159-166`); selector de perfil propio (`useState<NombreDePerfil>('moderado')`);
`useConcentracion(posiciones, perfil)` (cache-hit con `PanelConcentracion` por firma+perfil
idénticos — el mismo asesor viendo los dos paneles no duplica el pedido); `useEspeciesUniverso()`
para `porTicker`; `vectorDeRiesgo(posiciones, porTicker, consulta.data ?? null)` →
`<VectorDeRiesgo ejes={...} />`. Estado vacío igual al de `PanelConcentracion` ("sin posiciones de
renta fija").

**`SeccionRiesgo.tsx`** (diagnóstico): recibe `posiciones` y `perfil` ya resueltos por el padre
(props fijadas en base común — **no cambiar la firma**). Llama `useEspeciesUniverso()` +
`useConcentracion(posiciones, perfil)` (ambos deduplicados por TanStack contra lo que
`DiagnosticoCartera` ya pidió para su propia `SeccionConcentracion`, misma firma) → misma lib,
mismo componente que el armador. Si `posiciones.length === 0`, `return null` (mismo criterio que
el resto de las secciones de `DiagnosticoCartera`).

## Cómo se verifica "los tres perfiles se presentan igual" (GWT-5) sin que la propuesta exista

La cartera propuesta (F-033+) todavía no tiene código, pero su forma sí: va a ser una lista
`{ticker, peso}[]`, igual que las otras dos. El test de la lib construye la misma composición por
las tres formas — la del armador (con `pesoReal` colapsado a `peso` como hace `PanelRiesgo`), la
del diagnóstico (`posicionesConPeso` con `peso: pesoReal`), y una "propuesta" cruda
`{ticker, peso}[]` armada a mano sin pasar por ningún hook — y afirma `deepEqual` de los tres
`vectorDeRiesgo(...)` resultantes. La igualdad queda garantizada por construcción: es la misma
función pura llamada tres veces, no tres implementaciones que puedan divergir.

## Edge cases (todos con test)

- Posición cuyo ticker no está en `porTicker` (fuera del universo, o renta variable): sin dato en
  los seis ejes, contada y nombrada en cada `cobertura.notas`.
- Ninguna posición con calificación: eje crédito con un único tramo `"sin calificación"` al 100 %,
  nota de proxies presente.
- Ninguna posición con `ley` conocida (todas `null`): eje legislación con tramo
  `"ley no informada"` al 100 %, `valor: null` o `0` con nota — decidir y documentar en el código
  cuál, sin ambigüedad para quien lo lea después.
- Segmento con una sola especie sana en el universo: el percentil de liquidez de esa especie
  contra sí misma es 100 — no es un bug, es la definición; no se agrega un piso mínimo de tamaño
  de muestra en la lib (eso es cosa del motor de F-032, no de este eje descriptivo).
- `concentracion` en `isPending` o `isError`: eje "no medido", declarado, nunca estimado con un
  valor a mitad de camino.
- Cartera con GD30 + AE38 + TZX26: el eje concentración muestra `SOBERANO_AR` como una sola clave
  (GWT-4) — se verifica con un payload de `Concentracion` real/realista, no inventado a medias.
- Cartera vacía (`posiciones.length === 0`): la lib no se llama (los wrappers cortan antes,
  igual que `PanelConcentracion`); si se llamara igual, `vectorDeRiesgo([], ...)` debe devolver
  los seis ejes con cobertura en cero, no tirar.

## Zonas prohibidas

Todo backend (esta feature no lo toca). `src/lib/cartera/esquemaEspecie.ts`,
`esquemaConcentracion.ts`, `metricas.ts`, `renta.ts`, los hooks de `src/lib/cartera/hooks/`, y
`queryKeys.ts` (se importa, no se edita). `ArmadorPage.tsx`, `DiagnosticoCartera.tsx` (ya
tienen el montaje hecho por la base común). `features/armador/**` fuera de `PanelRiesgo.tsx` y su
test. `features/cartera-diagnostico/**` fuera de `SeccionRiesgo.tsx` y su test. Todo lo de F-032
(`backend/app/rotaciones/**`, `backend/app/api/v1/rotaciones.py`).

## Verificación

```
cd frontend
npx vitest run src/lib/cartera/__tests__/riesgo.test.ts src/components/__tests__/VectorDeRiesgo.test.tsx src/features/armador/__tests__/PanelRiesgo.test.tsx src/features/cartera-diagnostico/__tests__/SeccionRiesgo.test.tsx
npx tsc -b
npm run lint
```

Manual: cargar la misma composición (3-4 tickers reales, alguno soberano) en `/armador` y en
`/optimizador` → el vector de seis ejes debe mostrar los mismos valores y la misma cobertura en
las dos pantallas, con `SOBERANO_AR` colapsado si hay más de un prefijo del Tesoro.
