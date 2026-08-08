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
| 3 | **F-011** (dedup) — **sola** | El plan manda serializar F-010·F-011·F-012: las tres exponen `segmentos.py` como servicio | **completada 07/08/2026** |
| 4 | **F-012** (FX implícito) ∥ **F-015** (API calendario) ∥ **F-029** (resolución tickers) | F-012 extiende la envoltura ya creada en 2–3; F-015 envuelve `cupones.py` (otro módulo); F-029 es un servicio nuevo de matching | **completada 07/08/2026** — F-012 se hizo sola por decisión del usuario, para cerrar el Ciclo 1; F-015 ∥ F-029 cerraron la tanda el mismo día |
| 5 | **F-013** (barra de estado) — **sola** | Nada más tiene dependencias listas en este punto; es transversal a todas las pantallas y conviene que nadie la pise | **completada 07/08/2026** |

### Fase B — Las pantallas grandes (Milestone 2: "Un asesor arma una cartera desde el calendario")

| Tanda | Features | Por qué no se pisan | Estado |
|---|---|---|---|
| 6 | **F-016** (grilla 12 meses) ∥ **F-038** (monitor) | Pantallas y rutas distintas. F-038 estaba en el Ciclo 4 del plan pero sus dependencias (F-003, F-010, F-012, F-013) ya están al llegar acá: se adelanta para tener la primera pantalla con datos reales | **completada 07/08/2026** — primera tanda ejecutada con Sonnet sobre planes prescriptivos de Fable; verificación de cierre aparte |
| 7 | **F-018** (cartera editable) ∥ **F-039** (ficha) | F-018 no puede ir con F-016/F-017 (mismo store del armador, mandato del plan); F-039 no puede ir con F-038 (misma pantalla y navegación). Cruzadas entre sí, cero contacto | **completada 07/08/2026** — segunda tanda Fable-planifica/Sonnet-ejecuta; verificación de cierre encontró un error de tipos real sólo visible con el proyecto completo compilando junto |
| 8a | **F-051** (métricas propias) — **sola** | La salvedad de la duda 7 se activó: F-051 **modifica** `cupones.py` (import circular), la firma de `armar_consolidacion` y `corrida.py`. Además deja escrita la matemática de descuento que F-040 consume; en paralelo las dos la escribirían por duplicado. Evidencia y diseño completo en `claude-docs/plans/F-051-plan.md` | **completada 08/08/2026** — 240 especies con TIR pasaron a 284 calculadas, y las D y C tienen métricas por primera vez. El arreglo del ciclo de imports fue más grande que el previsto: `raiz_emision` se movió a `app/ingesta/raiz.py` porque importar un submódulo igual ejecuta el `__init__` del paquete |
| 8b | **F-017** (filtros) ∥ **F-024** (redondeo lámina) ∥ **F-040** (sensibilidad) ∥ **F-052** (renta variable en el monitor) | Barra de filtros de la grilla / cablear la lámina real en la cartera / repricing en la ficha / pestañas de acciones y CEDEARs en el monitor. Después de la base común no comparten un archivo: F-017 y F-024 tocan `features/armador/` pero archivos distintos (store y barra nueva vs `CarteraEditable`+`resolver`); F-040 vive en la ficha y en `calendario/`; F-052 en el monitor y en un paquete backend nuevo. **Base común a mano antes de soltar agentes**: JOIN a `condiciones_emision` en `universo/lectura.py` + campos `lamina` y `sector` en `EspecieUniverso`; router vacío `api/v1/renta_variable.py`; claves `accion`/`cedear` en `SelectorSegmento` | **completada 08/08/2026** — las cuatro en paralelo, un commit por feature. La verificación de cierre pasó a la primera, a diferencia de la tanda 7. Queda una migración escrita y sin aplicar (`cierre_anterior`): hasta que corra, la consolidación falla contra la base |
| 9 | **F-020** (concentración) ∥ **F-021** (panel de renta) ∥ **F-026** (renta variable) ∥ **F-053** (ficha de RV con Yahoo) | Tres paneles distintos del armador más una ficha en el monitor. Alcance ajustado al planificar (08/08/2026): **F-026 pierde la distribución por país y rubro** —el dato no existe en BYMA ni en ningún curado, y la ficha exige "recopilado con origen y fecha declarados"; queda esperando a F-053, que lo habilita—. Con eso **se disuelve la duda de solape 6**: sin panel de distribución en F-026, las dos features dejan de compartir componente. **F-021 resultó casi sólo frontend**: `POST /calendario/cartera` ya devuelve la renta en plata por moneda y `renta_anual` ya excluye amortización por construcción. **F-020 resultó más grande**: `verificar_concentracion` y `PERFILES` viven sólo en `tools/`, que el backend no importa — hay que portarlos, como pasó con la matemática de TIR en la 8a. **F-053 entra como cuarto agente** (ver duda de solape 9) | pendiente |
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

   **Resuelta al planificar la tanda, y por un camino que no estaba previsto (08/08/2026): la
   duda se disolvió en vez de resolverse.** Medido contra el universo real, el dato que el panel
   de F-026 necesita —país de la empresa o índice de referencia— **no existe**:
   `EspecieRentaVariable` tiene ticker, precio, moneda, cierre anterior, variación, volumen,
   puntas y operaciones, y nada más; BYMA no publica país ni rubro ni siquiera el nombre de la
   empresa. La ficha exige el dato "recopilado con origen y fecha declarados, y si falta queda
   vacío y se alerta", así que construir el panel hoy sería una pantalla con "país no informado"
   en el 100 % de las 752 especies. **F-026 entra sin el panel**, que pasa a depender de F-053.
   Sin panel no hay componente compartido, y las dos features quedan sin ningún archivo en
   común. El `DistribucionBarras.tsx` de la base común se crea igual —lo usa F-020 para sus tres
   cortes— y queda listo para cuando F-026 recupere el suyo.
7. **F-051 va primera y sola: la salvedad se activó** (planteada y resuelta el 08/08/2026). La
   duda era si podía consumir `cupones.py` desde un módulo nuevo sin modificarlo. No puede, por
   tres razones verificadas contra el código: (a) `cupones.py:55` y `universo/segmentacion.py:29`
   importan `raiz_emision` del `__init__` del paquete de consolidación, así que en cuanto
   `armado.py` importe matemática de calendario la cadena se cierra sobre sí misma y da
   `ImportError` — hay que cambiar esas dos líneas; (b) `armar_consolidacion` es "sin base, sin
   red, sin reloj" y el valor técnico necesita la fecha: cambia la firma, y con ella `corrida.py`
   y `jobs/corridas.py`, que era un segundo llamador que nadie tenía anotado; (c) el solver de
   TIR, el valor presente y la duración no existen en el backend —sólo en `tools/`, que el
   backend no importa— y son exactamente lo que F-040 necesita: en paralelo, las dos features
   escribirían la misma matemática por duplicado. Serializando, F-040 la consume ya escrita y su
   insumo "TIR vigente" pasa de ~234 tickers a todo lo que tenga precio y cronograma en su
   moneda, sin cambio de contrato.
8. **F-052 pasa a la 8b y toca más de lo que decía la duda original** (revisada el 08/08/2026).
   Lo que se creía "un filtro más sobre el universo consolidado" no existe: la renta variable se
   descarta *antes* de segmentar y `Segmentacion.renta_variable` es un contador, no una lista, así
   que la feature necesita paquete y endpoint backend propios. Además agrega una migración
   (`cierre_anterior` en `precios`) y una línea en `armado.py` para la columna de variación —
   contacto real con F-051, resuelto por la serialización: F-052 corre después. Sigue en pie el
   riesgo hacia adelante: **F-026 (tanda 9)** también muestra renta variable, en el armador, y el
   armador tiene prohibido importar de `features/monitor/`. Por eso F-052 deja los componentes de
   fila y columnas de RV en `frontend/src/components/`, zona compartida — mismo criterio que el
   componente de distribución de la duda 6. Y lo que no se negocia: F-052 **no** agrega columna de
   rendimiento a sus pestañas "porque ahora hay TIR". Una acción no tiene TIR, y la regla 2 sigue
   valiendo aunque la TIR ahora exista para todo lo demás.
9. **F-053 entra a la tanda 9 como cuarto agente** (planteada y resuelta el 08/08/2026). Es una
   feature nueva, nacida de una pregunta del usuario sobre el monitor de referencia, y la duda
   era si podía correr con las otras tres. **Puede, y con margen**: vive en `features/instrumento/`
   y en un paquete backend nuevo (`app/externos/`), zonas que ninguna de las otras tres toca.
   El único roce aparente —la fila de la tabla de renta variable que abre la ficha— no es tal:
   `TablaRentaVariable` ya llama `useAbrirInstrumento` desde F-052, así que F-053 **no modifica
   la tabla ni el monitor**. Con F-026 la relación es de dependencia futura, no de contacto:
   F-053 habilita el dato país/rubro que F-026 va a necesitar cuando recupere su panel (duda 6),
   pero en esta tanda las dos son independientes.

   La salvedad que no se activó: F-053 toca `api/v1/renta_variable.py`, que F-052 creó. Como
   F-026 quedó sin backend en esta tanda, ese archivo tiene un solo dueño y no hace falta
   serializar.

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

## Lo que enseñó la Tanda 3

- **Serializar F-010·F-011·F-012 valió la pena, y se nota.** F-011 extendió el paquete que F-010
  dejó sin rehacer nada: agregó las columnas en `lectura.COLUMNAS` y en `EspecieUniverso`, y el
  resto del paquete no se enteró, exactamente como F-010 había documentado. Sale barato porque la
  primera de la serie escribió dónde se engancha la siguiente. **Repetir el patrón en la Tanda 4**,
  donde F-012 cierra la serie.
- **Revisar el criterio antes de soltar al agente evitó un bug conocido.** El desempate por volumen
  del motor usa volumen *normalizado a dólares*, que produce F-012 y todavía no existe. Con el
  volumen crudo siempre gana la especie en pesos por el tipo de cambio y no por liquidez. Se
  instruyó dejar el hueco declarado en vez de implementarlo con el número equivocado. **Cuando una
  feature porta lógica del motor, revisar de qué depende cada criterio antes de encargarla:** parte
  de lo portado puede necesitar una feature que todavía no está.
- **Un cero se explica dos veces si hace falta.** El chequeo del 5 % de duración no rechazó ningún
  grupo, igual que la capa 1 de F-010 no descartó nada, y por la misma causa: las métricas por
  ticker existen sólo para el ticker exacto que IAMC reporta. Rastrear el cero hasta la causa
  mostró que **son tres controles inertes por un único motivo**, que es un hallazgo de arquitectura
  y no tres rarezas sueltas.

## Lo que enseñó F-012 (cierre del Ciclo 1)

- **La serie F-010 · F-011 · F-012 cerró como se planeó, y el patrón se pagó tres veces.** Cada una
  dejó escrito por nombre dónde se enganchaba la siguiente: `lectura.py` decía *"falta `lastPrice` y
  `effectiveVolume`, que son de F-012"* y `_prioridad` decía *"acá se engancha F-012"*. La tercera
  feature no tuvo que decidir nada de arquitectura. **Repetir el patrón en cualquier serie
  serializada**: que la primera escriba el punto de entrada de las que siguen.
- **Los revisores automáticos de la feature encontraron dos defectos reales que el reporte no
  mencionó**, y hubo que verificarlos y arreglarlos a mano al cerrar: un `NaN` sin filtrar y una
  llamada de red viva metida en el punto de entrada compartido de siete endpoints. **Leer lo que
  reportan los revisores y comprobar que se hayan aplicado**, en vez de asumir que sí.
- **Una feature puede desmentir su propia ficha, y hay que dejarla.** F-012 midió contra la fuente
  real que `index-price` no publica ningún «Índice Dólar» —lo que la spec daba por sentado— y que
  seis especies con sufijo D cotizan en pesos, lo que rompe la regla del sufijo que usa el motor.
  Las dos cosas quedaron documentadas con el número medido en vez de seguir la ficha al pie.
- **Los tests de integración contra fuentes vivas son sensibles a la hora.** El de BYMA falla antes
  de que abra la rueda porque la fuente devuelve 896 filas contra las 3.000 que el test exige. No es
  un problema del código, pero hay que saberlo antes de leer un rojo como una regresión.

## Cifras

18 tandas para 35 features. Las fases A y B concentran el paralelismo: 27 features en 10 tandas.
La estimación de esfuerzo por feature está en la tabla RICE de `plan.md`, sección 4.

## Cómo retomar en una sesión nueva

1. Leer este documento y `progress/PROGRESS.md` para saber qué tanda sigue.
2. La spec GWT de cada feature está en `planning/plan.md`, sección 3.
3. Confirmar con el usuario antes de arrancar la tanda (regla de la casa: se propone, él da el ok)
   y preguntarle si la quiere con `--plan` (Fable planifica, Opus ejecuta) o directa.
4. Al cerrar la tanda: tests en verde, commit, actualizar `PROGRESS.md` y la columna Estado de acá.
