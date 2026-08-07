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
| F-012 | Tipo de cambio implícito y normalización | Stage 1 | 266,7 | pendiente |

> Milestone 1 — "El universo existe y es confiable."

## Ciclo 2 — Armador completo (12 features · ~11 semanas)

| ID | Feature | Etiqueta | RICE | Estado |
|---|---|---|---|---|
| F-013 | Barra de estado del dato | Stage 1 | 200,0 | pendiente |
| F-014 | Autenticación y aislamiento por asesor | Stage 1 | 200,0 | completada |
| F-015 | API del calendario de doce meses | Stage 1 | 285,0 | pendiente |
| F-016 | Grilla-selector de doce meses | Stage 1 | 114,0 | pendiente |
| F-017 | Filtros de la grilla | Stage 1 | 112,0 | pendiente |
| F-018 | Cartera editable y ponderación | Stage 1 | 140,0 | pendiente |
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
| F-029 | Resolución de tickers | Stage 1 | 106,7 | pendiente |
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
| F-038 | Monitor de mercado | Stage 1 | 106,7 | pendiente |
| F-039 | Ficha de instrumento | Stage 1 | 112,0 | pendiente |
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

**Tanda 3 cerrada el 07/08/2026** — F-011 sola, 476 tests offline y 63 de integración
(1 skipped preexistente). Siguiente paso: **Tanda 4 — F-012 (tipo de cambio implícito) ∥ F-015
(API del calendario) ∥ F-029 (resolución de tickers)**, que cierra el ciclo 1.

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
