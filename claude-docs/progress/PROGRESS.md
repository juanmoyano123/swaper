# Progreso — 10-Swaper

Generado desde `claude-docs/planning/plan.md` (Fase 2) al correr `/init-project`.
Estado inicial: las 50 features arrancan en **pendiente**. Este archivo se actualiza a mano o
desde `/build-feature` a medida que cada una se implementa.

## Ciclo 1 — Cimientos e ingesta (12 features · ~9,5 semanas)

| ID | Feature | Etiqueta | RICE | Estado |
|---|---|---|---|---|
| F-001 | Esqueleto de servicio backend | Foundation | 400,0 | completada |
| F-002 | Esquema de datos y migraciones | Foundation | 300,0 | completada |
| F-003 | Esqueleto de aplicación frontend | Foundation | 400,0 | completada |
| F-004 | Cliente de la API abierta de BYMA | Stage 1 | 300,0 | completada |
| F-005 | Parser del informe diario de IAMC | Stage 1 | 50,0 | completada |
| F-006 | Cliente del feed de cashflow de Docta | Stage 1 | 240,0 | completada |
| F-007 | Consolidador multi-fuente | Stage 1 | 160,0 | completada |
| F-008 | Job programado de ingesta | Stage 1 | 266,7 | completada |
| F-009 | condiciones_emision: semilla y herencia | Stage 1 | 200,0 | completada |
| F-010 | Sanidad del dato en dos capas | Stage 1 | 400,0 | completada |
| F-011 | Deduplicación de especies | Stage 1 | 400,0 | completada |
| F-012 | Tipo de cambio implícito y normalización | Stage 1 | 266,7 | completada |

> Milestone 1 — "El universo existe y es confiable."

## Ciclo 2 — Armador completo (12 features · ~11 semanas)

| ID | Feature | Etiqueta | RICE | Estado |
|---|---|---|---|---|
| F-013 | Barra de estado del dato | Stage 1 | 200,0 | completada |
| F-014 | Autenticación y aislamiento por asesor | Stage 1 | 200,0 | completada |
| F-015 | API del calendario de doce meses | Stage 1 | 285,0 | completada |
| F-016 | Grilla-selector de doce meses | Stage 1 | 114,0 | completada |
| F-017 | Filtros de la grilla | Stage 1 | 112,0 | pendiente |
| F-018 | Cartera editable y ponderación | Stage 1 | 140,0 | completada |
| F-019 | Armado asistido | Stage 1 | 83,3 | pendiente |
| F-020 | Límites de concentración en vivo | Stage 1 | 175,0 | pendiente |
| F-021 | Panel de renta y renta anual | Stage 1 | 285,0 | pendiente |
| F-022 | Rendimientos por naturaleza y plazo | Stage 1 | 175,0 | pendiente |
| F-023 | Composición y curva TIR/duración | Stage 1 | 48,0 | pendiente |
| F-024 | Redondeo por lámina y diferencia | Stage 1 | 200,0 | pendiente |

> Milestone 2 — "Un asesor arma una cartera desde el calendario y se lleva el número a la
> reunión." Depende de `claude-docs/planning/design-system.md` (Fase 3, ya bajado).

## Ciclo 3 — Renta variable, carga y diagnóstico (9 features · ~8 semanas)

| ID | Feature | Etiqueta | RICE | Estado |
|---|---|---|---|---|
| F-025 | Carga asistida de lámina | Stage 1 | 53,3 | pendiente |
| F-026 | Bloque de renta variable | Stage 1 | 80,0 | pendiente |
| F-027 | Calendario de balances | Stage 1 | 16,7 | pendiente |
| F-028 | Ingreso de cartera por tres vías | Stage 1 | 96,0 | completada |
| F-029 | Resolución de tickers | Stage 1 | 106,7 | completada |
| F-030 | Valuación y diagnóstico de cartera | Stage 1 | 150,0 | pendiente |
| F-031 | Vector de riesgo de seis ejes | Stage 1 | 100,0 | pendiente |
| F-032 | Motor de rotaciones intra-segmento | Stage 1 | 100,0 | pendiente |
| F-035 | Costo real de rotar y cupón próximo | Stage 1 | 180,0 | pendiente |

> Milestone 3 — "El diagnóstico de una cartera ajena tarda minutos y no horas."

## Ciclo 4 — Optimizador, monitor y persistencia (9 features · ~8,5 semanas)

| ID | Feature | Etiqueta | RICE | Estado |
|---|---|---|---|---|
| F-033 | Modo bajar riesgo | Stage 1 | 57,6 | pendiente |
| F-034 | Modo subir TIR con contrapartida | Stage 1 | 86,4 | pendiente |
| F-036 | Aceptación rotación por rotación | Stage 1 | 57,6 | pendiente |
| F-037 | Comparación original contra propuesta | Stage 1 | 72,0 | pendiente |
| F-038 | Monitor de mercado | Stage 1 | 106,7 | completada |
| F-039 | Ficha de instrumento | Stage 1 | 112,0 | completada |
| F-040 | Sensibilidad por repricing completo | Stage 1 | 66,7 | pendiente |
| F-041 | Guardar, listar, reabrir y revaluar | Stage 1 | 180,0 | pendiente |
| F-042 | Exportación a Excel y PDF | Stage 1 | 100,0 | pendiente |

> Milestone 4 — "Stage 1 completo: los tres flujos cierran."

## Stage 2 — se activa después de validar con usuarios reales (8 features · ~14,5 semanas)

| ID | Feature | RICE | Estado |
|---|---|---|---|
| F-043 | Gestión de clientes y CRM | 20,0 | pendiente |
| F-044 | Historial de propuestas | 25,0 | pendiente |
| F-045 | Colocaciones primarias | 15,0 | pendiente |
| F-046 | FCI con fuente | 8,3 | pendiente |
| F-047 | Opciones | 4,0 | pendiente |
| F-048 | Alertas y notificaciones | 40,0 | pendiente |
| F-049 | Comparación de carteras entre sí | 40,0 | pendiente |
| F-050 | API Market Data oficial de BYMA | 80,0 | pendiente |

## Totales

| Ciclo | Features | Person-days | Semanas (est.) | Acumulado |
|---|---|---|---|---|
| 1 — Cimientos e ingesta | 12 | 47 | ~9,5 | ~9,5 |
| 2 — Armador completo | 12 | 55 | ~11 | ~20,5 |
| 3 — RV, carga y diagnóstico | 9 | 41 | ~8 | ~28,5 |
| 4 — Optimizador y persistencia | 9 | 42 | ~8,5 | ~37 |
| **Stage 1** | **42** | **185** | **~37 semanas** | |
| Stage 2 | 8 | 72 | ~14,5 | |

**La base está poblada.** F-007 corrió contra Supabase el 06/08/2026 y dejó 2.894 instrumentos,
2.894 precios, 3.344 puntas y 6.150 filas de cronograma, con el motor Python leyendo la vista
`resumen` sin que haya que tocarle una línea (GWT-4 verificado con un test de integración).

**El orden de ejecución de las features restantes está fijado en
`claude-docs/planning/plan-ejecucion-tandas.md`** (aprobado el 06/08/2026): 18 tandas con el
criterio de paralelizar sólo lo que con certeza no comparte archivos, tablas ni contratos, y
serializar toda duda.

**Tanda 1 cerrada el 06/08/2026** — F-008, F-014 y F-028 en paralelo, 313 tests offline y 45 de
integración en el backend, 96 en el frontend.

**Tanda 2 cerrada el 06/08/2026** — F-009 ∥ F-010, 428 tests offline y 58 de integración.

**Tanda 3 cerrada el 07/08/2026** — F-011 sola, 476 tests offline y 63 de integración.

**F-012 cerrada el 07/08/2026, y con ella el Ciclo 1: 12 de 12.** 517 tests offline y 69 de
integración. El milestone 1 —"El universo existe y es confiable"— está completo.

**Tanda 4 cerrada el 07/08/2026** — F-015 ∥ F-029, lo que quedaba después de que F-012 se hiciera
sola. 618 tests offline, 86 de integración y 116 en el frontend.

**Tanda 5 cerrada el 07/08/2026** — F-013 sola. 675 tests offline, 95 de integración y 143 en el
frontend. Van **17 de 42 features de Stage 1**, y con esta se destrabó el cuello de botella: las 25
que quedaban colgaban todas de F-013 por uno de dos caminos (F-016 → F-018 → el armador entero, o
F-038 → F-039 → F-040).

**Tanda 6 cerrada el 07/08/2026** — F-016 (grilla de doce meses) ∥ F-038 (monitor), **las dos
primeras pantallas con datos reales**. 681 tests offline, 97 de integración y 171 en el frontend.
Van **19 de 42 features de Stage 1**. Primera tanda ejecutada con Sonnet sobre planes prescriptivos
de Fable (`claude-docs/plans/F-016-plan.md` y `F-038-plan.md`), con verificación de cierre aparte:

- **Base común previa a los agentes** (la práctica de siempre): `MiniCalendario` y
  `SelectorSegmento` en `frontend/src/components/`, las claves de calendario en `queryKeys.ts` y
  `@tanstack/react-virtual` preinstalado. Cero colisiones de archivos entre los dos agentes.
- **F-016**: la grilla vive en `features/armador/` y crea el store (`store/carteraStore.tsx`,
  Context + reducer) que F-017 y F-018 extienden — el shape quedó documentado en el propio archivo.
  La iluminación multi-mes no se calcula: cada mes pinta contra el mismo `pos`. La cobertura
  distingue "ningún papel de la selección paga este mes" (rojo, accionable) de "nadie en el
  universo paga este mes" (gris, no hay nada que elegir). Las alertas del calendario se muestran
  completas, cobertura del 16 % incluida.
- **F-038**: el backend sumó `paridad` a la lectura del universo, `?segmento=` en
  `/emisiones/especies` y el endpoint `/universo/segmentos` para las pestañas. Verificado contra la
  base real: los conteos cierran exactos (942 en pestañas + 1.417 RV + 535 sin segmento = 2.894), y
  lo que no entra en ninguna pestaña **se declara en pantalla**, no desaparece. Los soberanos van
  con rendimiento `s/d`. Orden y filtros del lado del cliente sobre el segmento entero (bucle de
  cursor con tope explícito que falla fuerte en vez de truncar), virtualización con TanStack
  Virtual, conteo de filas siempre visible.
- **Dos correcciones del cierre**: el plan de F-016 copiaba mal el shape de alerta (las del
  calendario no llevan `origen` — el agente lo detectó y lo documentó en su schema), y la columna
  `paridad` nueva rompió el ruteo por contenido de la conexión falsa de los tests de estado
  (`if "paridad" in query` matcheaba ahora dos consultas): se afinó el discriminador al SQL exacto.
- **Unidades fijadas por test**: `rendimiento` y `paridad` viajan como fracción (los techos de
  sanidad lo confirman: 3.0 = 300 %) y las celdas muestran puntos porcentuales; hay un test que
  fija la conversión para que nadie la "corrija" después.

**Tanda 7 cerrada el 07/08/2026** — F-018 (cartera editable) ∥ F-039 (ficha de instrumento). **El
flujo de armado queda usable de punta a punta**: elegir de la grilla, ajustar pesos, ver el peso
real, y abrir la ficha de cualquier papel. 692 tests offline, 97 de integración y 202 en el
frontend. Van **21 de 42 features de Stage 1**. Segunda tanda con el ruteo Fable-planifica /
Sonnet-ejecuta, cero contacto entre las dos features (una es frontend puro sobre `features/armador/`,
la otra agrega un router de backend propio más `features/instrumento/`):

- **Base común**: `backend/app/api/v1/instrumentos.py` creado vacío y montado, igual que se hizo
  con `calendario` y `posiciones` en la Tanda 4 — así F-039 no toca `universo.py` ni
  `condiciones.py`, que ya usó F-038.
- **F-018**: extiende el store de F-016 con peso pedido, FCI y monto total; el motor de redondeo
  por lámina (`lib/resolver.ts`) queda escrito y testeado, pero **la lámina real todavía no está
  cableada** — eso lo trae F-024 en la Tanda 8, así que hoy toda posición muestra "lámina s/d" y no
  se redondea. El agente detectó y corrigió un desvío real: el backend manda `moneda_cotizacion`
  en mayúsculas (texto crudo de BYMA sin traducir) y el motor comparaba contra literales en
  minúscula — sin la normalización, ninguna posición real se hubiera resuelto nunca.
- **F-039**: tres endpoints de sólo lectura (`GET /instrumentos/{ticker}` con sus hermanas de
  liquidación, `/condiciones` con origen y fecha, `/cronograma` con los montos tal como vienen de
  la fuente). **Las puntas de compra/venta no existen en la fuente hoy** — el diseño original las
  simulaba con un spread inventado; no se portó, van `s/d` con el motivo declarado. Verificado
  contra la base real: AL30 resuelve sus hermanas AL30C/AL30D, la alerta
  `posicion_fuera_del_universo` se dispara con un ticker inexistente, y `moneda_cupon: null` en el
  cronograma de AL30 es la fuente sin ese dato, no un bug.
- **Un error real que atrapó la verificación de cierre, no los agentes**: los dos corrieron `tsc`
  aislado a su propia carpeta y salieron limpios, pero el `tsc -b` del proyecto completo encontró
  un error de tipos real en `FichaInstrumento.tsx` (un campo `string | number` pasado a una función
  que espera `number`) — invisible mientras las dos piezas no compilaban juntas. Se corrigió en el
  cierre.

Siguiente paso: **Tanda 8 — F-017 (filtros de la grilla) ∥ F-024 (redondeo por lámina) ∥ F-040
(sensibilidad por repricing)**. F-024 es la que le da a F-018 el dato de lámina que hoy falta.

### Lo que F-013 puso a la vista, y la decisión que dejó abierta

La barra no agregó datos nuevos: **hizo visible lo que seis servicios ya venían alertando y nadie
miraba.** Contra la base real muestra 4 advertencias y 2 informativas, ninguna de error.

- **`sin_corrida_registrada`** — hallazgo nuevo: `corridas_ingesta` está vacía. Todo lo que hay en la
  base entró por corridas manuales del endpoint de F-007, así que **el dato no tiene traza de qué
  fuente lo trajo ni cuándo**. El job de F-008 nunca corrió de verdad. Se destraba solo la primera
  vez que corra la ingesta programada de las 11:30.
- **`rendimiento_perdido_al_colapsar`** — las 146 emisiones que venían anotadas acá como deuda desde
  F-012, ahora con tickers en pantalla en vez de en un documento.
- **`cobertura_del_calendario`** — las 70 de 431 de la Tanda 4.
- **`campo_sin_cobertura`** — `tna` vacío en las 2.894 filas.

**⚠️ Decisión pendiente del usuario: no hay alerta de "el dato está viejo".** Sería la más obvia de
la barra y no existe a propósito: declararlo exige un umbral, y fijar ese umbral es decidir cuánta
desactualización es aceptable para operar — depende de si la rueda está abierta, de qué instrumento
y de para qué se lo mire. Nadie tomó esa decisión, así que `antiguedad_minutos` va crudo, con la
hora del snapshot y la demora declarada al lado. **Hay que preguntárselo al usuario**; es criterio
de dominio, no de código.

### Cómo se resolvió el costo de la barra, que era su riesgo de diseño

La barra se pide en cada carga de cada pantalla. Un endpoint que recalculara el universo entero
haría que todo el producto pague 2.894 filas más el cashflow por pantalla — la misma clase de
problema que el contraste de BYMA vivo le causó a siete endpoints en F-012.

Se cachea **por identidad de la corrida y no por reloj**: el análisis caro es función pura del
contenido de la base, así que con la misma última fila de `corridas_ingesta` y el mismo
`capturado_en` de `precios`, el resultado cacheado no es una aproximación sino el mismo resultado.
El TTL de 300 s es red de seguridad, no política. El costo viaja en la respuesta: **625 ms medidos**
contra la base real. Y **no hay red viva en el camino de la barra**.

### Lo que la Tanda 4 dejó a la vista, y necesita decisión

- **El calendario cubre 70 de las 431 emisiones (16 %).** 360 quedan afuera por no declarar paridad,
  y sin paridad no hay precio sucio: el cupón no se puede expresar como fracción del monto invertido
  sin traer un tipo de cambio de afuera, que es lo que la regla 3 prohíbe. **Es la cuarta
  manifestación de la misma causa raíz** —IAMC publica la paridad y las métricas sólo para el ticker
  exacto que su informe nombra— y por eso la alerta `cobertura_del_calendario` apunta la decisión a
  F-011: si la grilla tiene que cubrir más universo, lo que hay que decidir es qué especie representa
  a una emisión. Los doce meses igual dan cobertura completa con esos 70, así que **F-016 no está
  bloqueada**; lo que está limitado es de cuántos papeles se puede elegir.
- **El GWT-4 de F-015 quedó sin verificar, a propósito y por escrito.** Pide reproducir los nominales
  de RUCED, SBC2D, CS47D y LOC5D contra el Excel real de la mesa ("Propuesta Base 7-26"), y ese Excel
  no está en el repositorio. Lo que sí se verifica es que el backend reproduce al motor sobre el
  mismo input versionado. Es una cadena de dos eslabones y el primero no se re-verificó: **si aparece
  el Excel, ese test hay que cerrarlo**.
- **El plazo de liquidación viaja sin mapear**, como `"1"` o `"2"` de BYMA, que es como lo escribió
  F-007. Traducirlo a "contado inmediato" / "48 hs" sería inventar un mapeo que ninguna fuente del
  proyecto declara. Cuando alguna pantalla tenga que mostrarlo, hay que decidir el mapeo con el
  usuario y no derivarlo.

### La decisión que F-012 dejó abierta

Con el volumen normalizado enganchado en el desempate, las emisiones sin rendimiento en la vista
colapsada **bajaron de 199 a 146** sobre 431. Mejoró, pero no alcanza, y **no se inventó un criterio
para tapar el resto**. Queda por decidir si hace falta uno que prefiera a la especie que publica
rendimiento — con la contra de que sesgaría el representante hacia lo que IAMC elige reportar, que
no es necesariamente la especie más líquida. No corre apuro: el armador (F-018) todavía no existe.

### Lo que F-012 desmintió de su propia ficha

- **`index-price` no publica ningún «Índice Dólar»**, que era lo que la spec daba por sentado. Son
  16 filas y ninguna lo es. Se contrasta contra el cociente entre `M` y `SPMERVDT` —el mismo índice
  en las dos monedas—, que da 1.519,47 contra el implícito de 1.521,53: 0,14 % de diferencia.
- **La moneda de cotización se lee de `moneda_cotizacion`, no se deduce del sufijo del ticker.** Hay
  seis especies con sufijo D declaradas en ARS; la regla del sufijo —la del motor— les habría
  multiplicado la liquidez por 1.500.
- **El canje MEP/cable está medido**: 1.521,53 contra la especie D y 1.576,21 contra la C, 3,6 %.

### Fragilidad del suite que quedó a la vista

El test de integración de BYMA exige más de 3.000 filas y **falla antes de que abra la rueda**: a las
08:00 la fuente devuelve 0 CEDEARs, 0 bonos públicos y 12 ONs. No es un problema del código, pero
conviene saberlo antes de correr `pytest -m integration` a la mañana temprano — y vale revisar si la
corrida matinal de F-008, programada a las 09:00, no cae en la misma ventana vacía.

### Lo que la Tanda 3 dejó abierto, y necesita decisión

- **199 de las 431 emisiones quedan sin rendimiento en la vista colapsada.** El representante que
  elige el desempate no es la especie cuya TIR publica IAMC, así que en la vista del armador esas
  emisiones aparecen sin número y no se van a proponer. **El dato sigue entero en la vista viva**,
  y la corrida lo alerta en vez de esconderlo. Hay que decidir si lo resuelve el volumen normalizado
  de F-012 o si hace falta un criterio que prefiera a la especie que publica rendimiento. No corre
  apuro: el armador (F-018) todavía no existe.
- **El desempate por volumen quedó como hueco declarado.** El motor lo hace con volumen normalizado
  a dólares, que produce F-012. Usar `effectiveVolume` crudo haría ganar siempre a la especie en
  pesos por el tipo de cambio y no por liquidez — el bug que `segmentos.py` documenta. Mientras
  tanto desempata el ticker alfabético: arbitrario pero estable. El punto de enganche está marcado.
- **Una sola causa raíz deja inertes tres controles.** F-007 asigna las métricas por ticker sólo al
  ticker exacto que IAMC reporta (240 instrumentos con TIR y duración sobre 2.894). Por eso no puede
  dispararse la capa 1 de la sanidad de F-010, ni el chequeo del 5 % de duración de F-011, ni el
  desempate por rendimiento. Los tres están portados y testeados; lo que falta es dato, no código.

### Lo que la Tanda 2 dejó verificado, y lo que dejó abierto

- **La sanidad de F-010 descarta cero sobre el universo de hoy, y es correcto.** Verificado contra
  la base: de los 2.894 instrumentos, 1.417 son renta variable (salen antes de segmentar, no tienen
  tasa), 535 quedan sin segmento porque su tipo de tasa no se reconoce, y de los 942 comparables
  sólo 217 tienen rendimiento. El máximo entre los comparables es BPCSO con 275 % contra un tope de
  300 %. SNSBO, el caso que la spec nombra como dato correcto, sobrevive con 242 %.
- **La capa 1 no puede dispararse hoy, y no porque esté rota.** F-007 asigna la TIR sólo al ticker
  exacto que IAMC reporta, así que dos especies de la misma emisión nunca tienen las dos una TIR
  con la que discrepar. VSCQD —el caso de la spec, que figuraba con 34.627.917 %— hoy tiene TIR
  nula. El escenario venía del pipeline viejo de Excel, que propagaba los rendimientos por raíz. La
  capa está portada y testeada, pero va a marcar cero mientras la precedencia de F-007 siga así.
- **Los tres rendimientos más altos del universo no pasan por ningún tope**: VE32P (614 %), CAC4O
  (316 %) y PQCKO (228 %) están entre los 535 sin segmento, y sin segmento no hay tope que aplicar.
  Es fiel al motor original, que también los dejaba pasar. El hueco no es de F-010 sino de la
  cobertura de `tipo_tasa`, que viene del `type` de Docta.
- **El dato curado de F-009 todavía no llega a la vista `resumen`.** F-009 puebla
  `condiciones_emision` y mide cobertura leyendo `instrumentos`, pero no escribe `instrumentos` ni
  la vista los cruza. `docs/esquema-datos.md` declara que F-009 escribe las dos tablas; la spec de
  la feature pide sólo que la tabla quede "poblada y consultable", que es lo que está. **F-020
  (concentración por sector y ley) y F-024 (redondeo por lámina) necesitan que ese dato llegue al
  universo**, así que hay que decidir por dónde: extender la vista, o que la corrida de F-007
  propague desde `condiciones_emision`.
- La lámina de los bonos del Tesoro sigue en cero: el artefacto curado no la trae para ningún
  soberano. Es un hueco declarado, no uno que F-009 pueda llenar.

### Deuda declarada de la Tanda 1

- ~~**`SUPABASE_JWT_SECRET` está vacío en el `.env`.**~~ **Resuelto el 07/08/2026, y el pedido
  estaba mal planteado.** El proyecto firma con ES256 y su JWKS publica una clave EC: cargar ese
  secreto habría cambiado el 503 por el rechazo de toda sesión genuina. El backend ahora verifica
  contra la clave pública de `/auth/v1/.well-known/jwks.json` y **la variable ya no existe** — una
  firma asimétrica se verifica con una clave pública, así que no hay secreto que configurar.
- **El pool del backend se conecta con un rol que saltea RLS** (`postgres`, `rolbypassrls=true`).
  Hoy no se materializa porque ningún endpoint sirve tablas de usuario, pero **F-041 no puede
  exponer carteras por `/api/v1/` sin resolver esto antes**: o el frontend las lee directo de
  Supabase con el JWT del asesor, o la conexión asume el rol `authenticated` con el `sub` del
  token antes de la consulta. Verificado empíricamente al cerrar la tanda.

### Lo que F-007 dejó pendiente, declarado

- **`tna` está vacía en todo el universo.** Venía del endpoint de Rendimiento de Bonos de Docta, que
  ya no se consume. El motor la usa para el rendimiento de tasa fija. La corrida lo alerta.
- **~450 especies de `public-bonds` quedan fuera del universo** por no tener cronograma que declare
  su clase. Son casi todas las X/Y/Z que BYMA publica como segundo trío de cada soberano y que el
  consolidado histórico nunca tuvo; sus puntas sí se guardan.
- **La ley y la moneda de pago cubren 592 de 2.894 instrumentos**, que son las 242 emisiones del
  informe de IAMC con sus especies. El resto llega con F-009.
