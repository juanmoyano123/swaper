# Plan de ejecución en tandas — Stage 1

**Fecha:** 06/08/2026 · **Aprobado por:** Jero · **Estado al escribirse:** F-001 a F-007 completadas
y mergeadas a `develop`, base poblada (2.894 instrumentos), 246 tests offline + 38 de integración
en verde.

## De dónde sale este documento

Es la derivación operativa de `claude-docs/planning/plan.md` (Fase 2), específicamente de:

- La **sección 7 (Execution Map)**: tracks A–G y el grafo de dependencias ficha por ficha.
- La **tabla "No pueden correr en paralelo entre sí"** de esa misma sección: los 8 grupos que
  comparten tabla, módulo o componente y se serializan aunque el grafo no lo exija.
- El **criterio del usuario (06/08/2026)**: *"si no estás seguro de si se pisa una feature con la
  otra, las hacemos por separado y en orden"*. Toda duda de solape se resolvió serializando; las
  dudas concretas y cómo se resolvieron están al final.

Este documento **no reemplaza** a `plan.md` (las specs GWT viven allá) ni a
`progress/PROGRESS.md` (el estado por feature vive allá). Sólo fija **el orden y el agrupamiento
de ejecución**. Si contradice a `plan.md` en una dependencia, gana `plan.md` y hay que corregir acá.

## Reglas de trabajo (validadas en el lote F-004/005/006)

1. **Una tanda no arranca hasta que la anterior tiene tests en verde y commit.**
2. **Base común primero**: antes de soltar agentes en paralelo dentro de una tanda, se crean a mano
   los puntos de contacto (routers vacíos, slots de UI, stores, dependencias compartidas) para que
   ningún agente invente su propia versión ni colisionen en archivos.
3. Dentro de una tanda, cada feature trabaja en sus propios archivos. Si al planificar una feature
   aparece un archivo compartido no previsto, esa feature **sale de la tanda y se hace después, sola**.
4. Al cerrar cada tanda se actualiza `PROGRESS.md` y la tabla de estado de este documento.

## Las tandas

### Fase A — Cerrar el universo (Milestone 1: "El universo existe y es confiable")

| Tanda | Features | Por qué no se pisan | Estado |
|---|---|---|---|
| 1 | **F-008** (job de ingesta) ∥ **F-014** (auth) ∥ **F-028** (carga de cartera) | Tres áreas sin un archivo en común: F-008 en `backend/app/jobs/`, F-014 en auth/RLS + guard de rutas del frontend, F-028 frontend puro (depende sólo de F-003) | **completada 06/08/2026** |
| 2 | **F-009** (condiciones_emision) ∥ **F-010** (sanidad) | Tablas y módulos distintos: F-009 escribe `condiciones_emision`; F-010 envuelve la sanidad de `segmentos.py`, que no lee ley ni lámina | **completada 06/08/2026** |
| 3 | **F-011** (dedup) — **sola** | El plan manda serializar F-010·F-011·F-012: las tres exponen `segmentos.py` como servicio | pendiente |
| 4 | **F-012** (FX implícito) ∥ **F-015** (API calendario) ∥ **F-029** (resolución tickers) | F-012 extiende la envoltura ya creada en 2–3; F-015 envuelve `cupones.py` (otro módulo); F-029 es un servicio nuevo de matching | pendiente |
| 5 | **F-013** (barra de estado) — **sola** | Nada más tiene dependencias listas en este punto; es transversal a todas las pantallas y conviene que nadie la pise | pendiente |

### Fase B — Las pantallas grandes (Milestone 2: "Un asesor arma una cartera desde el calendario")

| Tanda | Features | Por qué no se pisan | Estado |
|---|---|---|---|
| 6 | **F-016** (grilla 12 meses) ∥ **F-038** (monitor) | Pantallas y rutas distintas. F-038 estaba en el Ciclo 4 del plan pero sus dependencias (F-003, F-010, F-012, F-013) ya están al llegar acá: se adelanta para tener la primera pantalla con datos reales | pendiente |
| 7 | **F-018** (cartera editable) ∥ **F-039** (ficha) | F-018 no puede ir con F-016/F-017 (mismo store del armador, mandato del plan); F-039 no puede ir con F-038 (misma pantalla y navegación). Cruzadas entre sí, cero contacto | pendiente |
| 8 | **F-017** (filtros) ∥ **F-024** (redondeo lámina) ∥ **F-040** (sensibilidad) | Barra de filtros de la grilla / cálculo backend de nominales / tabla de repricing dentro de la ficha | pendiente |
| 9 | **F-020** (concentración) ∥ **F-021** (panel de renta) ∥ **F-026** (renta variable) | Tres paneles distintos del armador, tres servicios backend distintos (`verificar_concentracion`, `cupones.py`, equity de BYMA). Alcance ampliado (08/2026): F-020 suma el panel de distribución por sector/ley/naturaleza de tasa, define `min_sectores` en `PERFILES` y advierte cuando no se cumple; F-026 suma el dato recopilado país/índice y la distribución por país del bloque. Ver duda de solape 6 | pendiente |
| 10 | **F-019** (armado asistido) ∥ **F-022** (rendimientos) ∥ **F-025** (carga de lámina) | F-022 recién acá porque comparte el servicio de métricas con F-021 (tanda 9); F-025 recién acá porque escribe lo que F-024 (tanda 8) lee. Alcance ampliado (08/2026): F-019 suma el criterio de reparto sectorial — reusa el `min_sectores` que F-020 (tanda 9) definió en `PERFILES` y agrega el desempate por sector no representado en `elegir_siguiente`; por eso F-019 ahora también depende de F-020, lo que esta secuencia ya respetaba | pendiente |

### Fase C — Diagnóstico y optimizador (Milestones 3 y 4)

| Tanda | Features | Por qué | Estado |
|---|---|---|---|
| 11 | **F-023** (curva TIR/duración) ∥ **F-030** (diagnóstico) | F-023 cierra el trío de métricas (serializado tras F-022); F-030 reusa servicios ya hechos sin modificarlos | pendiente |
| 12 | **F-031** (vector de riesgo) ∥ **F-032** (motor de rotaciones) | F-031 después de F-030 porque extiende su salida (mandato del plan); F-032 envuelve `detectar_swaps.py`, módulo aparte | pendiente |
| 13 | **F-033** (bajar riesgo) ∥ **F-035** (costo real) | Módulos distintos. **Salvedad**: si al planificar F-035 resulta que también toca el contrato de la fila de propuesta, F-035 va primero y sola | pendiente |
| 14 | **F-034** (subir TIR) — sola | Comparte el contrato de la fila de propuesta con F-033 (mandato del plan) | pendiente |
| 15 | **F-036** (aceptación por rotación) — sola | Consume F-033 + F-034 + F-035 | pendiente |
| 16 | **F-037** (comparación original/propuesta) — sola | Consume F-036 | pendiente |
| 17 | **F-041** (guardar/reabrir carteras) — sola | Consume F-037 | pendiente |
| 18 | **F-042** (export Excel/PDF) — sola | Consume F-041 | pendiente |

Las tandas 14–18 son el camino crítico del plan: cada una consume la salida de la anterior y no hay
paralelismo posible.

**Fuera de tanda:** **F-027** (calendario de balances) queda para el final o a demanda — RICE 16,7 y
confidence 50 % porque la disponibilidad programática de las fechas de CNV no está verificada.

## Dudas de solape y cómo se resolvieron (siempre por lo conservador)

1. **F-008 y F-009 no van juntas** aunque no comparten tablas: las dos extienden el pipeline de la
   corrida (una lo orquesta, la otra le agrega un paso). En `PROGRESS.md` se había sugerido
   paralelizarlas; con el criterio conservador del 06/08 quedan en tandas separadas.
2. **F-020 y F-024 separadas** (tandas 9 y 8) aunque el plan no las lista como conflicto: las dos
   agregan elementos a la tabla de la cartera de F-018.
3. **F-033 ∥ F-035** con salvedad declarada en la tanda 13.
4. **F-011, F-013, F-034 y toda la cola 15–18 van solas.**
5. **F-038 y F-039 adelantadas** del Ciclo 4 a las tandas 6–7: sus dependencias ya están y son las
   pantallas que muestran datos; no rompen ningún orden del plan porque el grafo lo permite.
6. **F-020 y F-026 siguen juntas en la tanda 9** pese al alcance ampliado (08/2026): las dos
   muestran ahora un panel de distribución (F-020 por sector/ley/naturaleza en renta fija, F-026
   por país/rubro en renta variable). Se resuelve con la regla 2: el componente de distribución
   compartido se crea a mano antes de soltar la tanda. Si al planificar aparece más contacto que
   ese componente, F-026 sale de la tanda y va después, sola (regla 3).

## Lo que enseñó la Tanda 1 (aplicar en las que siguen)

- **La base común funcionó.** Los routers vacíos (`jobs.py`, `auth.py`) y los settings creados por
  adelantado en `config.py` evitaron que dos agentes editaran `router.py` y `config.py` a la vez.
  El scaffold de F-003 ya traía los huecos declarados con el número de feature adentro
  (`RequiereSesion.tsx`, el panel "Cartera del cliente" de `OptimizadorPage`), así que ninguna de
  las tres necesitó tocar `rutas.tsx`.
- **Lo que sí colisionó fueron los manifiestos de dependencias**, que no estaban previstos:
  `requirements.txt` (PyJWT de F-014 y tzdata de F-008) y `package.json`. Se resolvió separando las
  líneas al commitear. **En las próximas tandas: preinstalar las dependencias previsibles junto con
  el resto de la base común**, como se hizo con `@supabase/supabase-js`.
- **Los agentes no commitean.** Con las tres features en el mismo working tree, un `git add -A` de
  cualquiera se lleva el trabajo de los otros. Implementan y dejan los tests en verde; los commits
  se hacen al cerrar la tanda, uno por feature.
- **Verificar, no confiar en el reporte.** Dos agentes reportaron el mismo comando con resultados
  distintos (el build del frontend fallaba para uno y pasaba para el otro, porque el segundo
  terminó después). La suite se corre de nuevo al cerrar la tanda.

## Lo que enseñó la Tanda 2 (confirma y corrige a la Tanda 1)

- **La lección de la Tanda 1 se aplicó y funcionó.** Antes de soltar los agentes se verificó que
  `pandas` y `numpy` ya estaban en `requirements.txt`, así que ninguna feature necesitó tocar un
  manifiesto de dependencias y la colisión que hubo en la tanda anterior no se repitió. Confirmado:
  **la base común tiene que incluir las dependencias, no sólo los routers y los settings.**
- **Los constructores de alertas son un punto de contacto y hay que preverlos.** Las dos features
  reportan hallazgos y las dos iban a editar `ingesta/alertas.py`. Se escribieron por adelantado los
  tres constructores (`condiciones_en_conflicto`, `especie_incoherente`, `rendimiento_fuera_de_rango`)
  y ninguna tuvo que tocar el archivo. **Agregar `alertas.py` a la lista de base común de las tandas
  que siguen.**
- **Decirle a la feature que es la primera de una serie cambia lo que construye.** A F-010 se le
  avisó que F-011 y F-012 heredan el paquete `universo/`, y dejó la forma documentada con el punto
  de enganche de cada una. Eso es lo que hace barata a la Tanda 3.
- **Un agente puede quedar idle sin entregar el reporte.** Pasó con F-010. No se insistió: se
  verificó todo contra la base directamente, que además es la regla que dejó la Tanda 1. Los números
  que después se contrastaron contra su plan coincidían exactamente.
- **Un cero hay que explicarlo, no aceptarlo.** F-010 descarta cero instrumentos. Podía ser un
  universo sano o un port roto, y la diferencia importa. Se verificó contra la base hasta poder
  decir por qué: la capa 1 es estructuralmente inerte por la precedencia de F-007, y la capa 2 no
  tiene a quién descartar porque el máximo comparable está debajo de su tope. **Pedirle a cada
  feature que declare qué pasa cuando su resultado es cero.**

## Cifras

18 tandas para 35 features. Las fases A y B concentran el paralelismo: 27 features en 10 tandas.
La estimación de esfuerzo por feature está en la tabla RICE de `plan.md`, sección 4.

## Cómo retomar en una sesión nueva

1. Leer este documento y `progress/PROGRESS.md` para saber qué tanda sigue.
2. La spec GWT de cada feature está en `planning/plan.md`, sección 3.
3. Confirmar con el usuario antes de arrancar la tanda (regla de la casa: se propone, él da el ok)
   y preguntarle si la quiere con `--plan` (Fable planifica, Opus ejecuta) o directa.
4. Al cerrar la tanda: tests en verde, commit, actualizar `PROGRESS.md` y la columna Estado de acá.
