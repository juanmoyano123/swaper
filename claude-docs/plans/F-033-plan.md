# F-033 — Modo "mantener la TIR y bajar el riesgo"

## Spec (tanda 13)

El asesor elige cuál de los seis ejes de riesgo (F-031) minimizar — default: duración, único eje
con cobertura casi total y el más medible. El sistema propone destinos de rotación (F-032) que
cumplen las tres condiciones a la vez: (a) mejoran estrictamente el eje elegido, (b) no empeoran
ninguno de los otros cinco (no-empeoramiento, no compensación), (c) mantienen el rendimiento
dentro de ±0,5pp (misma banda de `BANDA_RENDIMIENTO_PP` en
`backend/app/rotaciones/constantes.py:23`). Si ningún destino cumple las tres, se declara que no
hay propuesta, sin relajar la restricción en silencio.

## Qué se implementó

```
frontend/src/lib/rotaciones/
├── esquemaRotaciones.ts              # contrato de POST /rotaciones, modo strip
├── bajarRiesgo.ts                    # lib pura: las dos etapas + el veredicto final
├── hooks/
│   ├── useRotaciones.ts              # POST /rotaciones (TanStack Query)
│   └── useBajarRiesgo.ts             # orquesta rotaciones + vector actual + concentración
│                                        simulada de cada sobreviviente + evaluarBajarRiesgo
└── __tests__/
    ├── esquemaRotaciones.test.ts
    └── bajarRiesgo.test.ts

frontend/src/features/optimizador/components/
├── SeccionBajarRiesgo.tsx            # selector de eje + lista de propuestas / "no hay propuesta"
└── (test en frontend/src/features/optimizador/__tests__/SeccionBajarRiesgo.test.tsx)
```

Más una integración de dos líneas en `frontend/src/features/cartera-ingreso/components/
CarteraConfirmada.tsx` (detalle abajo, en "Desvío del plan").

## Decisiones de diseño propias

### 1. Cómo se evaluó duración/legislación/liquidez sin duplicar la aritmética de `riesgo.ts`

El plan dejaba dos caminos abiertos: (i) llamar a `vectorDeRiesgo()` con la concentración actual
como placeholder para la etapa local, o (ii) reimplementar la ponderación a mano. Se tomó (i), con
una variante: en vez de pasar la concentración *actual* como placeholder, se pasa `null`. El eje
concentración de esa llamada nunca se lee (se recalcula bien en la etapa 2, con la concentración
simulada real), así que el placeholder es indistinguible en su uso — pasar `null` evita que quien
lea el código más adelante piense por error que ese resultado de concentración tiene algún
significado. Queda documentado en el comentario de cabecera de `bajarRiesgo.ts` y en el punto donde
se llama.

### 2. Separación en dos etapas, tal como pedía el plan

- `evaluarEtapaLocal()` — pura, sin red: banda de rendimiento, duración, legislación, liquidez
  (vía `vectorDeRiesgo` con concentración `null`) y crédito (vía el flag `mismo_emisor` de la
  `Candidata`, nunca ordenando calificación — regla 7).
- `evaluarEtapaConcentracion()` — pura, sin red: recibe las sobrevivientes de la etapa local y un
  `Map<claveCandidata, Concentracion | null>` ya resuelto por el llamador. La lib nunca hace
  `fetch`; es `useBajarRiesgo.ts` el que pide, con `useQueries`, la concentración simulada de cada
  sobreviviente (una cartera simulada por candidata: peso del origen movido al destino), cacheada
  por la misma `firmaDePesos` + perfil que ya usa `useConcentracion` — dos candidatas que empujan a
  la misma cartera simulada, o una candidata cuya cartera simulada coincide con una concentración
  que `SeccionRiesgo` ya pidió, comparten caché en vez de repetir el POST.
- `evaluarBajarRiesgo()` encadena las dos para el caso en que ya se tienen todas las
  concentraciones simuladas (tests, y el hook una vez que sus `useQueries` resolvieron). Vuelve a
  correr la etapa local sobre la lista completa de candidatas en vez de recibir sólo las
  sobrevivientes: es barata (a lo sumo `TOP_N=3` candidatas por origen) y evita que el hook tenga
  que mantener sincronizados "sobrevivientes locales" con "candidatas completas" en dos llamadas
  distintas.

### 3. El signo del eje legislación

La consigna original tenía una ambigüedad real: decía "menos peso extranjero = mejor riesgo
jurisdiccional" y, en la misma frase, "mejora estricta = simulado > actual" — direcciones opuestas
si `valor` es el peso bajo ley extranjera (que es lo que `riesgo.ts` calcula). Se resolvió leyendo
`backend/app/rotaciones/motor.py` directamente, como pedía la consigna: `mejora_ley = origen.ley ==
LEY_LOCAL and es_extranjera(destino.ley)` — el motor llama "mejora" a pasar de Ley Argentina a Ley
N.Y., consistente con que la Ley N.Y. da más protección al tenedor frente a una reestructuración
unilateral. Se implementó esa dirección (mejora estricta = el peso bajo ley extranjera del
simulado es mayor que el del actual) y se dejó un test explícito
(`bajarRiesgo.test.ts` → "legislación como eje primario") que fija el comportamiento con un caso
concreto (Ley Argentina → Ley N.Y. es mejora), para que cualquier futura duda sobre el signo se
resuelva corriendo ese test en vez de releyendo la prosa ambigua.

### 4. A qué eje se le atribuye el descarte `fuera_de_banda`

`MotivoDescarte` no distingue un séptimo concepto para "rendimiento": el descarte por banda se
etiqueta con `eje: ejePrimario`, porque la banda es la contrapartida explícita de mejorar
*ese* eje (regla 8). Documentado en el comentario de `evaluarCandidataLocal`.

### 5. Empates (`simulado === actual`) en un eje no-primario

Se tratan como `no_empeora` (no bloquean), consistente con "no-empeoramiento, no compensación": un
empate no es una mejora, pero tampoco es un empeoramiento. Como eje *primario*, un empate no
satisface "mejora estrictamente" y descarta la candidata con motivo `empeora` (no hay un motivo
`sin_mejora` en el enum; se usó el más cercano semánticamente, ya que no es un problema de dato
faltante).

### 6. `credito`/`moneda` como eje primario

Se corta antes de tocar cualquier candidata: `resultadoNoMedible()` devuelve
`{hayPropuesta:false, noMedible:true, motivo: "..."}` sin evaluar nada, y la UI lo distingue
explícitamente del estado "no hay propuesta" (no es lo mismo "no es medible este eje" que "se
evaluó y no hay ninguna que sirva" — regla 11).

## Desvío del plan: integración en `CarteraConfirmada.tsx`

La instrucción original suponía que `CarteraConfirmada.tsx` iba a tener a mano `posicionesConPeso`
y `perfil` para pasarle a `SeccionBajarRiesgo`. Al leer el archivo, ninguno de los dos existe ahí:
las posiciones con peso y el estado de `perfil` los calcula `DiagnosticoCartera.tsx` puertas
adentro (`useCarteraCargadaValuada` + `useState` local), sin exponerlos hacia afuera, y
`DiagnosticoCartera.tsx` está fuera de mi columna (no autorizado a tocarlo).

Se resolvió dentro de `CarteraConfirmada.tsx`, sin tocar ningún archivo fuera de la columna
autorizada: llama a la misma `useCarteraCargadaValuada(posiciones)` que ya usa
`DiagnosticoCartera` (TanStack Query dedupea por clave — no dispara un segundo POST) para derivar
`posicionesConPeso`, y mantiene su **propio** `useState<NombreDePerfil>('moderado')`,
independiente del selector de perfil que vive dentro de `DiagnosticoCartera`. Es una decisión
consciente, no un accidente: medir concentración (el perfil de `DiagnosticoCartera`) y buscar
rotaciones (el perfil de `SeccionBajarRiesgo`) no tienen por qué compartir el mismo perfil elegido
en un momento dado — el asesor puede querer ver los topes contra "agresivo" y buscar rotaciones
más conservadoras, por ejemplo. Se agregó un selector de perfil propio, visible sólo cuando hay
posiciones valuadas.

No se tocó ningún otro archivo fuera de `frontend/src/lib/rotaciones/`,
`frontend/src/features/optimizador/` y `frontend/src/features/cartera-ingreso/components/
CarteraConfirmada.tsx`.

## Alcance NO cubierto (a propósito, declarado en la UI)

Sólo propuesta: sin botón de aceptar, sin efecto en el calendario de cupones ni en ninguna otra
pantalla, sin costo de rotar (arancel, spread) — eso es F-036 (tanda 15). El motor de F-032 ya
manda la alerta `costo_rotacion_no_calculado` en toda respuesta; `SeccionBajarRiesgo.tsx` lo
declara en un párrafo fijo arriba de las propuestas (regla 8: toda mejora nombra qué se resigna, y
"todavía no sabemos el costo" es parte de esa nominación).

## Verificación

```
cd frontend
npx vitest run src/lib/rotaciones src/features/optimizador
npx vitest run   # suite completa: 54 archivos, 502 tests, todos en verde
npx tsc -b        # sin errores
npx oxlint src/lib/rotaciones src/features/optimizador src/features/cartera-ingreso/components/CarteraConfirmada.tsx
  # un único warning heredado del patrón del repo (`vitest(require-mock-type-parameters)`),
  # presente también en SeccionRiesgo.test.tsx — no es una regresión de esta feature.
```

Manual: cargar una cartera con al menos dos posiciones del mismo segmento en `/optimizador`,
confirmar, y verificar que la sección "Mantener la TIR y bajar el riesgo" aparece debajo del
diagnóstico, con duración preseleccionada; cambiar el eje a legislación/liquidez/concentración y
confirmar que la lista de propuestas (o el mensaje de "no hay propuesta") cambia en consecuencia;
elegir crédito o moneda y confirmar que se ve el mensaje de "no medible", no una lista vacía.
