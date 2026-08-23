# Progreso — 10-Swaper

Generado desde `claude-docs/planning/plan.md` (Fase 2) al correr `/init-project`.
Estado inicial: las 50 features arrancaban en **pendiente**. Este archivo se actualiza a mano o
desde `/build-feature` a medida que cada una se implementa.

**Estado al 23/08/2026 — Stage 1 cerrado (44 de 44), Stage 2 abierto (1 de 32).** El catálogo
creció de 50 a 77 features desde que se generó este archivo; la tabla de Stage 2 se reconcilió
contra `plan.md` el 23/08/2026. Lo que está trabado hoy **no es código sino dato**: ver
"Pendientes de datos y decisiones" al final.

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
| F-017 | Filtros de la grilla | Stage 1 | 112,0 | completada |
| F-018 | Cartera editable y ponderación | Stage 1 | 140,0 | completada |
| F-019 | Armado asistido | Stage 1 | 83,3 | completada |
| F-020 | Límites de concentración en vivo | Stage 1 | 175,0 | completada |
| F-021 | Panel de renta y renta anual | Stage 1 | 285,0 | completada |
| F-022 | Rendimientos por naturaleza y plazo | Stage 1 | 175,0 | completada |
| F-023 | Composición y curva TIR/duración | Stage 1 | 48,0 | completada |
| F-024 | Redondeo por lámina y diferencia | Stage 1 | 200,0 | completada |

> Milestone 2 — "Un asesor arma una cartera desde el calendario y se lleva el número a la
> reunión." Depende de `claude-docs/planning/design-system.md` (Fase 3, ya bajado).

## Ciclo 3 — Renta variable, carga y diagnóstico (9 features · ~8 semanas)

| ID | Feature | Etiqueta | RICE | Estado |
|---|---|---|---|---|
| F-025 | Carga asistida de lámina | Stage 1 | 53,3 | completada |
| F-026 | Bloque de renta variable | Stage 1 | 80,0 | completada |
| F-027 | Calendario de balances (sólo CEDEARs, vía SEC) | Stage 1 | 42,5 | **completada** |
| F-028 | Ingreso de cartera por tres vías | Stage 1 | 96,0 | completada |
| F-029 | Resolución de tickers | Stage 1 | 106,7 | completada |
| F-030 | Valuación y diagnóstico de cartera | Stage 1 | 150,0 | completada |
| F-031 | Vector de riesgo de seis ejes | Stage 1 | 100,0 | **completada** |
| F-032 | Motor de rotaciones intra-segmento | Stage 1 | 100,0 | **completada** |
| F-035 | Costo real de rotar y cupón próximo | Stage 1 | 180,0 | **completada** |

> Milestone 3 — "El diagnóstico de una cartera ajena tarda minutos y no horas."

## Ciclo 4 — Optimizador, monitor y persistencia (9 features · ~8,5 semanas)

| ID | Feature | Etiqueta | RICE | Estado |
|---|---|---|---|---|
| F-033 | Modo bajar riesgo | Stage 1 | 57,6 | **completada** |
| F-034 | Modo subir TIR con contrapartida | Stage 1 | 86,4 | **completada** |
| F-036 | Aceptación rotación por rotación | Stage 1 | 57,6 | **completada** |
| F-037 | Comparación original contra propuesta | Stage 1 | 72,0 | **completada** |
| F-038 | Monitor de mercado | Stage 1 | 106,7 | completada |
| F-039 | Ficha de instrumento | Stage 1 | 112,0 | completada |
| F-040 | Sensibilidad por repricing completo | Stage 1 | 66,7 | **completada** |
| F-041 | Guardar, listar, reabrir y revaluar | Stage 1 | 180,0 | **completada** |
| F-042 | Exportación a Excel y PDF | Stage 1 | 100,0 | **completada** |
| F-051 | Métricas propias: TIR, duración y paridad | Stage 1 | 160,0 | **completada** |
| F-052 | Renta variable en el monitor | Stage 1 | 106,7 | **completada** |
| F-053 | Ficha del activo de renta variable | Stage 1 | 140,0 | **completada** |

> Milestone 4 — "Stage 1 completo: los tres flujos cierran."
>
> F-051 y F-052 se agregaron el 08/08/2026, después de auditar cómo resuelve estas dos cosas el
> monitor de mesa. El plan pasó de 42 a 44 features de Stage 1.

## Stage 2 — 32 features, ordenadas por RICE (~187 pd · ~37 semanas)

Reconciliado el 23/08/2026 contra `claude-docs/planning/plan.md`. La tabla anterior tenía 8
features: era la foto del catálogo al cerrar la Fase 2, y quedó vieja cuando el catálogo creció con
F-054…F-057 (Bloque O), F-058…F-070 (Bloque P, paridad competitiva con Docta), F-071 y F-072, y
F-073…F-077 (motor analítico determinístico). Estado medido contra el código, no contra los
mensajes de commit.

| ID | Feature | RICE | Estado |
|---|---|---|---|
| F-068 | Panel de dólar y spreads | 266,7 | pendiente |
| F-060 | Navegación por emisor × naturaleza de tasa | 240,0 | pendiente |
| F-059 | Comparador de dos instrumentos | 189,0 | pendiente |
| F-055 | Descarga automática del informe de IAMC | 180,0 | pendiente |
| F-073 | Serie diaria de cierres persistida | 180,0 | pendiente |
| F-072 | Prospecto de emisión de ONs, vía CNV | 175,0 | **completada** |
| F-071 | Calculadora de canjes y prorrateo de órdenes | 157,5 | pendiente |
| F-064 | Watchlist | 150,0 | pendiente |
| F-069 | Top ganadores y perdedores del día | 150,0 | pendiente |
| F-056 | Índice CER del BCRA: tasa real | 112,5 | pendiente |
| F-074 | Convexidad propia | 112,5 | pendiente |
| F-077 | Perfilado formal del inversor | 96,0 | pendiente |
| F-057 | FCI en el monitor (CAFCI) | 85,0 | pendiente |
| F-067 | FCI: comparador, categorías y gestoras | 85,0 | pendiente |
| F-050 | API Market Data oficial de BYMA | 80,0 | pendiente |
| F-058 | Carry trade: calculadora y breakeven | 78,8 | pendiente |
| F-062 | Curva histórica del segmento | 75,0 | pendiente |
| F-063 | Heatmap del panel | 75,0 | pendiente |
| F-061 | Rendimientos históricos por ventana | 72,0 | pendiente |
| F-054 | Info pública del emisor (CNV y SEC) | 60,0 | **parcial** |
| F-048 | Alertas y notificaciones | 40,0 | pendiente |
| F-049 | Comparación de carteras entre sí | 40,0 | pendiente |
| F-075 | Estadística de cartera | 37,5 | pendiente |
| F-076 | Calculadora de valuación con supuestos declarados | 35,0 | pendiente |
| F-046 | FCI valuables en cartera | 30,0 | pendiente |
| F-065 | Cauciones | 30,0 | pendiente |
| F-044 | Historial de propuestas | 25,0 | pendiente |
| F-066 | Futuros de dólar | 25,0 | pendiente |
| F-043 | Gestión de clientes y CRM | 20,0 | pendiente |
| F-045 | Colocaciones primarias | 15,0 | pendiente |
| F-070 | Tenencias con P&L por lote | 13,3 | pendiente |
| F-047 | Opciones | 4,0 | pendiente |

**Tres aclaraciones de estado que no se leen de la tabla:**

- **F-072 está en producción** desde el 17/08/2026 (`backend/app/externos/cnv.py`,
  `app/api/v1/instrumentos.py`, `frontend/src/features/instrumento/`), detrás del flag
  `CNV_HABILITADO` con default apagado. Cobertura medida: 307 de 373 emisiones ON resuelven CUIT y
  llegan a documentos. Quedan 6 emisores sin candidato en
  `data/emisores_cuit_pendientes.csv` (BNA, Banco Provincia, EDESA, Farmacity, Havanna).
- **F-054 está a la mitad.** La pata SEC existe (`app/externos/sec_ficha.py`,
  `sec_ficha_parser.py`, `renta_variable/ratios_sec.py`, `sec_calendario.py`); la pata CNV de
  información del emisor sigue pendiente, aunque F-072 ya le dejó construido el cliente HTTP y el
  puente emisor→CUIT.
- **F-057 NO está hecha, pese al nombre del commit.** El commit `47c040a` se llama
  `feat: F-057 (FCI en el monitor, CAFCI)…` pero tocó únicamente `plan.md` y `analisis-docta.md`:
  no hay una sola referencia a CAFCI en `backend/app` ni en `frontend/src` (verificado el
  23/08/2026). Era documentación del catálogo, no implementación.

## Totales

| Ciclo | Features | Person-days | Semanas (est.) | Acumulado |
|---|---|---|---|---|
| 1 — Cimientos e ingesta | 12 | 47 | ~9,5 | ~9,5 |
| 2 — Armador completo | 12 | 55 | ~11 | ~20,5 |
| 3 — RV, carga y diagnóstico | 9 | 41 | ~8 | ~28,5 |
| 4 — Optimizador y persistencia | 9 | 42 | ~8,5 | ~37 |
| **Stage 1** | **44** | **185** | **~37 semanas** | **cerrado el 16/08/2026** |
| Stage 2 | 32 | 187 | ~37 | 1 de 32 hecha (F-072) |

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

**Tanda 8a cerrada el 08/08/2026 — F-051 (métricas propias), sola.** La tanda 8 se partió en dos al
planificarla: F-051 modifica la consolidación y deja escrita la matemática de descuento que F-040
consume, así que ir en paralelo habría significado escribirla dos veces. 748 tests offline (eran
692). Van **22 de 44 features de Stage 1**.

- **El resultado, medido contra la base real**: la renta fija pasa de 240 especies con TIR a **284
  calculadas**, y por primera vez las especies D y C tienen métricas — hoy son exactamente cero,
  porque IAMC nombra una sola especie por emisión. El par que resume la feature es AE38C con 10,41 %
  y AE38D con 9,59 %: el mismo bono, cada especie contra su propio precio.
- **Lo que queda afuera, y por qué**: 300 especies por moneda cruzada (cotizan en pesos y pagan en
  dólares: descontarlas pediría un tipo de cambio que sólo sale de su hermana), 46 CER, 66 dólar
  linked, 49 tamar y 8 badlar por naturaleza del flujo, y 189 sin precio del día. Las tres cosas se
  cuentan y se nombran en alertas propias. **CER se verificó sobre el dato, no se supuso**: el
  cronograma trae los montos contractuales sin el coeficiente —TX26 paga 2 % semestral sobre un
  residual de 100 exacto— mientras el precio en pesos sí lo incorpora.
- **El ciclo de imports era peor de lo que decía el plan.** Importar `app.ingesta.consolidacion.raiz`
  igual ejecuta el `__init__` del paquete, que importa `armado`: cambiar la línea no alcanzaba. Se
  resolvió moviendo `raiz_emision` a `app/ingesta/raiz.py`, que es donde corresponde — es una
  función hoja sin dependencias y vivía dentro del paquete que necesitaba importarla de vuelta.
- **Un defecto que el plan anticipó y estaba a punto de morder**: el refresh intradiario le pasaba a
  `armar_consolidacion` unas filas con sólo `ticker` y `type`. Con el armado nuevo eso se habría
  indexado como cronograma vacío y **cada refresco habría dejado la fila de precios sin TIR**, que
  la vista publica porque toma una sola fila por ticker. Ahora lee el cronograma entero, y el efecto
  buscado es que cada refresco recalcule las métricas contra el precio vivo.
- **Dos ceros explicados** (regla de la casa): la primera medición dio cero TIR calculadas dos veces
  seguidas, y las dos veces fue la medición y no el código — el consolidado versionado no tiene
  columna de moneda de cotización, y `asyncpg` devuelve los `numeric` como `Decimal`, que el
  normalizador descarta (la misma trampa del fix de la lámina). El contraste contra IAMC dio cero
  divergencias porque la medición se hizo sin informe: se ejercita en los tests, y en producción
  recién tiene con qué contrastar cuando se suba el PDF del día.
- **La medición se hizo en sólo lectura**: no se corrió la consolidación contra la base. Las
  métricas aparecen en la vista con la próxima corrida matinal.

**Tanda 8b cerrada el 08/08/2026** — F-017 (filtros) ∥ F-024 (lámina) ∥ F-040 (sensibilidad) ∥
F-052 (renta variable en el monitor), las cuatro en paralelo con un commit por feature. 793 tests
offline en el backend y 254 en el frontend. Van **26 de 44 features de Stage 1**, y el Milestone 2
queda a tiro: el armador filtra la grilla y calcula nominales reales, el monitor muestra todo el
universo y la ficha tiene su tabla de sensibilidad.

- **La verificación de cierre pasó a la primera**, a diferencia de la tanda 7. `tsc -b` del proyecto
  entero en cero al primer intento. La diferencia la hizo la base común: esta vez incluyó los campos
  de datos compartidos (`lamina`, `sector`) y no sólo routers y componentes.
- **Los tres frenos de los agentes fueron hallazgos reales, no falsos positivos.** F-017 frenó
  porque `sector` faltaba en el schema zod del armador — un punto de contacto que la base común no
  había cubierto. F-040 frenó porque su panel nuevo agrega una cuarta query y el test de la ficha de
  F-039, que tiene prohibido tocar, sólo mockeaba tres rutas. F-052 frenó porque el plan pedía un
  texto que sus props declaradas no alcanzaban a producir. Los tres los resolvió el orquestador, que
  es a quien le corresponden los archivos compartidos. **El patrón de "frenar y reportar" se pagó.**
- **El único error de coordinación fue del orquestador**: editó `lib/schema.ts` mientras F-024 lo
  tenía abierto y el campo quedó duplicado. Sin consecuencia porque era idéntico y en TypeScript la
  segunda clave pisa a la primera, pero con un tipo distinto habría sido un bug difícil de ver.
  **Confirma la regla en vez de desmentirla**: los archivos con dueño activo no se tocan, ni siquiera
  para un cambio de una línea.
- **F-052 adaptó su plan dos veces y las dos con razón.** El rollback de su migración usa
  `CREATE OR REPLACE VIEW` y no `DROP` + `CREATE`, porque la migración de subida tampoco dropea la
  vista y el guardián estructural de `test_migraciones.py` lo habría leído como tirar abajo algo que
  esa migración nunca creó.
- **Migración `20260807231600_f052_cierre_anterior.sql`: aplicada.** Verificado el 08/08/2026 contra
  la base: `cierre_anterior` existe en `precios` y en `resumen`. El código ya la asumía
  —`persistencia.py` la incluye en el INSERT y el endpoint de renta variable la lee de la vista—,
  así que sin ella la consolidación habría fallado.
  **Pero la columna está en cero en los cuatro snapshots existentes**, todos anteriores a la
  migración: ninguna consolidación corrió desde que se aplicó. La variación diaria del monitor de
  renta variable queda vacía —correctamente vacía, no en cero— hasta la primera matinal que corra
  con la columna presente.

Siguiente paso: la **tanda 9 — F-020 (concentración) ∥ F-021 (panel de renta) ∥ F-026 (renta
variable en el armador)**. F-026 hereda de F-052 los componentes `TablaRentaVariable`,
`FilaRentaVariable` y `PLANTILLA_COLUMNAS_RV`, que quedaron en `frontend/src/components/`
justamente para eso.

**Tanda 9 cerrada el 08/08/2026** — F-020 (concentración) ∥ F-021 (panel de renta) ∥ F-026 (renta
variable en el armador) ∥ **F-053** (ficha del activo con Yahoo, agregada al planificar la tanda),
las cuatro en paralelo con un commit por feature. **911 tests offline en el backend y 337 en el
frontend.** Van **30 de 45 features de Stage 1**, y con esto el armador dejó de ser una grilla con
una tabla: muestra cuánto cobra la cartera, qué riesgo concentra y qué parte no es renta fija.

- **Paso previo de base, antes de soltar agentes.** Se borró el snapshot degradado del sábado —466
  filas con **cero precios y cero TIR**, medido antes de tocar nada— y se agregó el guardia de día
  hábil: `en_ventana_de_rueda` sólo miraba la hora, y `proxima_matinal`/`proximo_refresh` desde el
  viernes devolvían el sábado. El scheduler habría degradado el snapshot solo, todos los fines de
  semana, apenas se habilitara. `/consolidar` fuera de rueda ahora exige `forzar=true` explícito.
  **Los feriados bursátiles no se modelan y está declarado**: no hay fuente programática confiable
  y hardcodear una lista sería inventar un dato que se desactualiza en silencio.
- **La lección nueva de esta tanda es de git, no de arquitectura: los agentes comparten el índice.**
  F-026 lo descubrió cuando F-021 commiteó primero y arrastró sus archivos ya `staged`. No hubo
  pérdida —se reconciliaron— pero el mecanismo es serio: un `git add -A` de cualquier agente puede
  tragarse el trabajo a medio terminar de otro. **A partir de acá se commitea con pathspec
  explícito.** Está escrito en `plan-ejecucion-tandas.md`.
- **El error de coordinación fue del orquestador, otra vez, y del mismo tipo que en la 8b.** La base
  común dejó los tres paneles cableados en **un solo archivo** (`PanelesDeLaCartera.tsx`), o sea un
  archivo con tres dueños — exactamente lo que la regla de "un dueño por archivo" existe para
  evitar. Costó una colisión de edición y un minuto de `HEAD` importando un archivo todavía sin
  commitear. **La próxima base común da un archivo por feature, aunque sean tres líneas cada uno.**
- **F-021 resultó casi sólo frontend y F-020 casi el doble de lo que decía su ficha.** El calendario
  ya devolvía la renta en plata por moneda y `renta_anual` ya excluía amortización por
  construcción; en cambio `verificar_concentracion` y `PERFILES` vivían sólo en `tools/`, que el
  backend no importa. Es el mismo patrón que la 8a con la matemática de TIR: lo que la ficha
  describe como "ya calibrado" puede no estar donde el backend lo pueda usar.
- **La divergencia deliberada contra el motor, medida:** el motor propaga sector por moda dentro del
  grupo de emisor a **487 especies** que la fuente no informa; el backend no lo hace. Medido: de
  1.509 especies de renta fija, 780 tienen sector y **cero se recuperan por emisor curado** — la
  única vía sería el prefijo de 3 letras del ticker, que es inferir del ticker, que es lo que la
  regla 1 prohíbe. El costo es real y **está declarado en pantalla**: el panel dice qué porcentaje
  de la cartera no informa sector y no cuenta para el mínimo. **El arreglo de verdad no es
  inferirlo, es curar `condiciones_emision`.**
- **F-053 excluyó un módulo entero de Yahoo en vez de filtrarle campos**, y el razonamiento mejora
  lo que se le había pedido: `financialData` mezcla márgenes y ROE —dato duro— con `targetMeanPrice`
  y `recommendationKey` —opinión—. Pedirlo y descartar campos deja el juicio ajeno adentro del
  proceso aunque no se muestre; no pedirlo lo mantiene afuera. Sólo viaja `assetProfile`.

**Tanda 10 cerrada el 09/08/2026** — F-019 (armado asistido) ∥ F-022 (rendimientos) ∥ F-025 (carga
de lámina), las tres en paralelo con un commit por feature. **1060 tests offline en el backend y
378 en el frontend.** Van **33 de 42 features de Stage 1**. Antes de abrir la tanda se commiteó
aparte el rediseño pendiente de F-017 (filtro de fábrica TIR≥6%/cupones + grilla en tarjetas por
mes, que venía del cierre de la Tanda 6): la regla "una tanda no arranca hasta que la anterior
tiene tests en verde y commit" se aplicó también a trabajo suelto, no sólo a tandas formales.

- **F-019 es el port más grande de la serie hasta ahora**, y encontró dos correcciones reales
  contra su propio plan, no contra el motor: (1) el endpoint no puede pasarle `saneado.especies`
  (la vista viva, una fila por especie de liquidación) a `armar()` — el propio motor exige
  `dedup=True` porque comprar AL30 y AL30D es comprar el mismo bono dos veces creyendo que se
  diversifica; la corrección usa `saneado.emisiones().colapsado()`, que su propio docstring ya
  llama "la vista del armador". (2) El fixture versionado (`universo_consolidado.xlsx`) es
  anterior a F-012 y no tiene `moneda_cotizacion`, así que el test de paridad tuvo que aislar el
  universo de entrada para comparar específicamente el algoritmo de selección y no arrastrar un
  problema del snapshot. La paridad contra `tools/armar_cartera.py` dio 13 de 15 escenarios
  idénticos ticker por ticker; los otros 2 difieren en como máximo 2 tickers cada uno, y es la
  firma esperada del reparto sectorial nuevo (GWT-4/5), que por diseño a veces elige distinto de
  la selección pura por rendimiento del motor original.
- **La divergencia de `min_sectores` entre fichas, declarada y no resuelta por decisión.** El GWT
  de F-019 dice que Soberano y Subsoberano no cuentan para el mínimo sectorial; el docstring de
  `app/concentracion/perfiles.py` (F-020) dice que sí cuentan como "sector presente" aunque estén
  exentos del tope. F-019 siguió el GWT literal de su propia ficha y no tocó `concentracion/`: la
  divergencia entre las dos pantallas queda declarada, no unificada por esta feature.
- **F-025 encontró y corrigió una landmine de persistencia que el propio plan alertaba pero no
  resolvía del todo**: escribir sólo la lámina con el upsert existente de `condiciones/` pisaría
  con NULL las otras cinco columnas curadas de la fila (ley, sector, calificación, emisor, moneda
  de pago). La escritura quedó en un UPDATE nuevo, acotado a las tres columnas de lámina. También
  encontró que FastAPI no levanta con una función que a veces devuelve `dict` y a veces
  `JSONResponse` (para el 409 de conflicto) sin `response_model=None` — mismo patrón que ya usaba
  `health.py` para su propio caso de respuesta mixta.
- **F-022 es la única de las tres 100 % frontend**, confirmando la lectura del plan de tandas: el
  dato ya estaba completo en `useCarteraResuelta` desde la Tanda 9 y no hizo falta abrir la deuda
  de "un solo servicio de métricas de cartera" (`plan.md:2581`) antes de tiempo — esa deuda sigue
  para cuando F-023 la fuerce, en la Tanda 11.
- **Primer uso de `useMutation` en el repo**, introducido por F-025 y reusado por F-019 al llegar
  segundo a esa parte del código: hasta esta tanda todo el frontend usaba `useQuery`, incluso para
  los POST-que-son-lectura (`/concentracion`, `/calendario/cartera`). Es el primer POST que
  realmente muta estado del servidor desde el armador.

**Tanda 11 cerrada el 09/08/2026** — F-023 (composición y curva TIR/duración) ∥ F-030 (valuación y
diagnóstico de la cartera cargada), en paralelo con un commit por feature. **430 tests offline en
el frontend (46 archivos) y 1060 en el backend.** Van **35 de 42 features de Stage 1**.

- **La deuda de `plan.md:2581` ("servicio de métricas de cartera, una sola vez y bien") se saldó
  en la base común**, antes de soltar los agentes: `rendimientos.ts`, `renta.ts`, los esquemas de
  calendario/especie/concentración y sus cuatro hooks de TanStack Query se movieron de
  `features/armador/lib` y `features/armador/hooks` a `frontend/src/lib/cartera/`, compartido
  entre el armador y el diagnóstico. No hizo falta un endpoint de resumen backend — la deuda era
  de duplicación frontend, no de cálculo faltante. Los ~25 importadores del armador no se tocaron:
  cada archivo original quedó como shim de re-export de una línea, y la suite existente lo
  verificó sin editar un test.
- **F-030 depende de esa base común para su propio criterio de aceptación.** El riesgo R12
  (`plan.md:2774`, "la misma composición cargada y armada produce los mismos números") se verifica
  con un test de paridad (`cartera-diagnostico/__tests__/paridad.test.ts`) que arma la misma
  tenencia física por `resolver()` del armador y por `valuarCartera()` del diagnóstico, y compara
  los resultados de `rendimientosPorNaturaleza`/`plazoPromedio`/`sensibilidadPorSegmento` — las
  mismas funciones de `@/lib/cartera/metricas` — sobre las dos salidas. Dio exacto, sin
  divergencia de floats.
- **F-030 tuvo que resolver un adaptador que el plan dejó como diseño, no como código**: el
  contrato de F-029 (`PosicionResuelta`) no trae precio, rendimiento ni duración — sólo lo que el
  asesor declaró y lo que el backend pudo vincular. `lib/valuacion.ts::valuarCartera()` cruza esas
  posiciones contra el universo y aplica cuatro motivos de exclusión en orden
  (`no_resuelta` → `sin_nominal` → `sin_precio` → `sin_tipo_de_cambio`); un monto sin nominal
  nunca se convierte a dólares, porque el resumen cargado no declara en qué moneda vino ese monto
  (regla 1).
- **F-023 tuvo que resolver dos cosas que el plan marcó explícitamente como "decisión de
  implementación"**: (1) qué segmento abre la curva por defecto — no puede leerse `[0]` de la
  composición por segmento, porque ese corte no abre `usd_hard` en sus tres pestañas de crédito
  (soberano/subsoberano/ON); se calculó aparte, con la clave de crédito expandida y el peso de
  cartera por pestaña. (2) qué moneda de cotización muestra la nube cuando una emisión tiene
  hermanas — se eligió la moneda con más especies del segmento/clase activo, mismo mecanismo que
  ya usa el monitor, sin agregar un segundo selector visible.
- **Un test de F-019 (`useArmadoAsistido.test.ts`) estaba roto desde el cierre de la Tanda 10**,
  sin relación con esta tanda: fallaba de forma determinística ya en el commit `2312f26`,
  verificado reproduciéndolo en un worktree de ese commit. `await mutateAsync().catch()` resuelve
  antes de que React confirme `isError` — el mismo caso que `useCargarLamina.test.ts` (F-025) ya
  cubre con `waitFor`, patrón que este test no había seguido. Se corrigió como commit aparte, fuera
  de F-023 y F-030.

**Tanda 12 cerrada el 09/08/2026** — F-031 (vector de riesgo de seis ejes) ∥ F-032 (motor de
rotaciones intra-segmento), en paralelo con un commit por feature. **470 tests offline en el
frontend (50 archivos) y 1087 en el backend.** Van **37 de 42 features de Stage 1**.

- **F-031 es un servicio compartido, no un panel por pantalla**: `src/lib/cartera/riesgo.ts` (lib
  pura) + `src/components/VectorDeRiesgo.tsx` (seis barras paralelas, nunca radar — el área de un
  radar se lee como puntaje) se montan tal cual en `PanelRiesgo` (armador) y `SeccionRiesgo`
  (diagnóstico), sin una segunda implementación. El riesgo R12 ("los tres perfiles se calculan
  distinto") se verifica con un test que arma la misma composición por las tres formas posibles
  —armador, diagnóstico y una "propuesta" cruda que todavía no existe como feature— y afirma
  igualdad exacta de los seis ejes entre las tres.
- **El eje de concentración no recalcula nada**: lee el `Concentracion` que ya llegó por
  `useConcentracion` (cache-hit con el panel de F-020/F-030 por la misma firma), así que
  `SOBERANO_AR` llega hecho del backend y el eje sólo lo muestra.
- **El eje de calificación agrupa por string exacto y nunca ordena** (39 % de cobertura, regla 11
  y riesgo R5): cuando falta, declara en pantalla los tres proxies que la reemplazan (tope de
  rendimiento del segmento, percentil de liquidez, topes de concentración) — la calificación no
  filtra en ningún lado del sistema, ni acá ni en F-032.
- **F-032 envuelve `detectar_swaps.py` en `backend/app/rotaciones/`**, sobre la vista viva del
  universo (sin deduplicar, porque los swaps de perfil rotan entre especies de la misma emisión —
  MEP → Cable). Los parámetros del motor (percentil de liquidez, tope anti-distress) salen de
  `PERFILES`: con `perfil=moderado` reproduce los defaults del CLI, así que la paridad contra el
  motor sale sin ajustar nada a mano.
- **El test de paridad dio exacto sobre el consolidado versionado**: 1806 candidatas idénticas en
  las dos implementaciones, y el swap que la mesa efectivamente ejecutó (TLCWO → TLCMO) aparece en
  las dos — riesgo R9 cerrado con evidencia, no por inspección. Contra la base **viva** (no el
  snapshot versionado) TLCWO ya no propone TLCMO porque el mercado se movió desde que se armó el
  consolidado; no es una regresión, es exactamente el caso que el plan previó, y la fixture
  sintética del motor puro sigue afirmando el caso como aceptación de respaldo.
- **F-032 no incluye costo real de rotar** (arancel, spread bid/ask, payback): toda respuesta trae
  la alerta `costo_rotacion_no_calculado` para que la ausencia se declare en vez de leerse como
  costo cero — llega con F-035 (tanda 13). Tampoco hay UI todavía: la pantalla de rotaciones es
  F-036 (tanda 15); esta tanda es sólo el servicio y su contrato.
- **El Bopreal se separa del resto del Tesoro sólo para "mismo emisor" en un swap** (`BCRA` en vez
  de `SOBERANO_AR`, porque lo emite el Central y no el Tesoro), sin tocar cómo lo agrupa
  concentración (F-020) — es una clave de riesgo distinta para una pregunta distinta, documentado
  como divergencia deliberada del mismo dato.
- **Base común de la tanda**: `EspecieUniverso` ganó `calificacion` (de `condiciones_emision`, como
  la lámina — `instrumentos.calificacion` está en NULL para todo el universo) y `tipo_tasa`
  (se leía para segmentar y se descartaba). Los dos campos los necesitaban las dos features, así
  que fueron al punto de contacto único antes de soltar los agentes. Trece fixtures de test de
  features previas que armaban un `Especie` completo necesitaron un campo más
  (`calificacion: null`) para seguir tipando — ajuste mecánico, sin tocar ningún test funcional.

**Tanda 13 cerrada el 09/08/2026** — F-033 (modo bajar riesgo) ∥ F-035 (costo real de rotar), en
paralelo con un commit por feature. **502 tests offline en el frontend (54 archivos) y 1104 en el
backend.** Van **39 de 42 features de Stage 1**.

- **La salvedad no se activó**: declaraba que si F-035 tocaba el contrato de la fila de
  propuesta, iba primero y sola. F-035 sí lo tocó —`Candidata.como_dict()` ganó el bloque `costo`
  y `cupon.fecha`—, pero F-033 quedó **100 % frontend**, filtro puro sobre las candidatas de
  F-032, sin leer ni modelar ese bloque: su esquema zod en modo strip (default) tolera la clave
  `costo` presente o ausente. Los conjuntos de archivos fueron disjuntos (backend vs. frontend),
  así que el paralelismo corrió sin fricción.
- **F-035 lee `public.puntas`, que ya la puebla BYMA** — el cambio data912→BYMA del spec ya había
  ocurrido en la ingesta (F-004/F-007); F-035 sólo agregó la primera lectura desde rotaciones,
  con el mismo molde `LEFT JOIN LATERAL` que `renta_variable/lectura.py`. Filas con `fuente`
  terminada en `-arrastre` (fecha de libro incierta) cuentan como sin punta.
- **La política ante el spread faltante diverge del CLI a propósito, y queda documentada**:
  `tools/mercado.py` cuenta un spread ausente como cero y devuelve un piso; F-035 en cambio deja
  la propuesta `verificable=false` con `total_pct=null` — nunca un default silencioso (regla 1).
  El ejemplo numérico de la spec original no cerraba aritméticamente contra su propia fórmula
  textual; se priorizó la fórmula, verificada por paridad contra `tools/mercado.py`.
- **F-033 reusa `vectorDeRiesgo` (F-031) sin duplicar su aritmética**: evalúa primero los cinco
  ejes locales (duración, crédito, legislación, liquidez, moneda) sin red, y sólo dispara
  `POST /concentracion` simulado para las candidatas que sobreviven esa etapa. Crédito y moneda
  son compositivos y no son medibles como eje primario — elegidos así, el modo lo declara en vez
  de devolver una lista vacía sin motivo.
- **El signo del eje legislación se resolvió leyendo `motor.py`, no el texto de la spec**: la
  consigna era autocontradictoria en su redacción; `mejora_ley` en el motor de F-032 define
  mejorar como pasar a ley extranjera, y F-033 replicó ese criterio con un test que lo fija.
- **Base común de la tanda**: `claves.mercado.rotaciones` en `queryKeys.ts` y `firmaDePesos`
  exportada de `useConcentracion.ts` (antes privada) — F-033 las necesitaba para que las
  concentraciones simuladas compartieran caché con el diagnóstico. Los dos archivos, un commit,
  antes de soltar los agentes.

**Rediseño integral del Armador, cerrado el 09/08/2026 — trabajo suelto entre tandas, seis etapas
commiteadas por separado.** No es una feature de `plan.md`: lo pidió el dueño del producto sobre
la pantalla ya construida (jerarquía visual rota, todo el mismo verde, sin forma de plegar una
sección, flujo renta fija/variable no integrado). Se hizo aparte de la tanda 14 siguiendo el
precedente de F-017 — un archivo con muchos dueños simultáneos (`ArmadorPage.tsx` y casi todos sus
`components/`) no es terreno para paralelismo de agentes.

- **Etapa 1 — paleta categórica**: seis tokens `--cat1..--cat6` (dark+light) en `index.css`;
  `DistribucionBarras` colorea por índice de tramo en vez de un solo verde para todo;
  `VectorDeRiesgo` y el tope de `PanelConcentracion` pasan a `--medida` (medición, no selección);
  `.rotulo` de `--ac` a `--dim`; disciplina `--ac`/`--pos` (mismo hex hoy, uso clasificado).
- **Etapa 2 — secciones plegables**: `SeccionDeArmador` gana `id`/`acento`/`resumen`, con el
  estado de plegado en `localStorage` (`lib/plegado.ts`) — no en el store de la cartera, porque
  F-041 va a persistir su forma exacta y una preferencia de UI no le pertenece. Borde izquierdo de
  3px por sección (cat1 a cat6, en orden) como separación visual.
- **Etapa 3 — % editable para renta variable**: `fijarPeso` del store ya era agnóstico de clase,
  pero sólo `CarteraEditable` lo llamaba y filtra RV. `BloqueRentaVariable` gana su propio input
  de "% pedido"; nueva `lib/mix.ts` (`sumaPesos`/`mixPedido`) declara el mix RF/RV pedido y real
  en las dos cabeceras, sin normalizar cuando no suma 100.
- **Etapa 4 — perfil de empresa (backend)**: tabla `perfil_renta_variable` (migración aplicada al
  proyecto real) poblada por `POST /api/v1/jobs/perfiles-renta-variable`, contra un método liviano
  de Yahoo (`ClienteYahoo.perfil_de_empresa` — chart de un día, no el año completo de
  `bloque_externo`) que corta al primer 429 sin insistir. Job incremental, `limite` por corrida.
- **Etapa 5 — filtros**: calificación (multiselect literal + `CALIFICACION_NO_INFORMADA`, nunca
  ordenada — cuatro calificadoras sin escala común) en la grilla de renta fija; sector/rubro +
  búsqueda por nombre en el bloque de renta variable, alimentados por la Etapa 4.
- **Etapa 6 — columna de KPIs (A9)**: `ColumnaKpis` fija a la derecha (`.layout-armador`,
  `.columna-kpis` en `index.css` — sticky sólo arriba de 1280px), reusando los mismos hooks que
  `PanelRenta`/`PanelRendimientos`/`lib/mix.ts`. "Lo que falta" declara sólo lo derivable de datos
  existentes (meses sin cobertura, posiciones sin resolver) — el mandato del cliente (A1 del
  design system) queda fuera: alcance de producto nuevo, sin feature ni fuente de datos.

532 tests de frontend (508 → 532) y 1130 de backend (1104 → 1130) en verde, tsc/build/lint
limpios en las seis etapas. Verificado a mano contra el backend real en cada una.

**Rediseño del flujo renta fija / renta variable del Armador, cerrado el 10/08/2026 — trabajo
suelto entre tandas, diez commits.** Segunda mitad del rediseño de arriba: aquélla arregló la
jerarquía visual de la pantalla, ésta arregla el flujo. Tampoco es una feature de `plan.md`, y por
el mismo motivo se hizo serializada y no en paralelo — `ArmadorPage.tsx` y sus `components/` los
tocan todos los cambios. **623 tests de frontend (532 → 623, 62 archivos) y 1160 de backend
(1130 → 1160)**, tsc/build/lint limpios. Van **39 de 42 features de Stage 1**: el conteo no se
mueve porque nada de esto es una feature.

**Ojo con el rótulo**: los comentarios del código nuevo dicen "Tanda 13", pero ese número ya lo
tiene la tanda F-033 ∥ F-035 de acá arriba. Es trabajo suelto entre tandas, como el rediseño; el
nombre en el código quedó, el número no vale.

- **Rebalanceo pro-rata** (`features/armador/lib/rebalanceo.ts`): agregar o quitar una posición
  reparte proporcionalmente entre las que quedan, y la cartera vuelve a sumar 100,0 exacto. Antes
  agregar daba `100/(n+1)` a la nueva sin tocar el resto y quitar dejaba el hueco sin repartir —
  en una cartera mixta eso significaba que sacar toda la renta variable no devolvía ese 25% a
  ninguna parte. El reparto se hace en **décimas enteras con el método del resto mayor** (1000
  décimas, sobrante a los restos más grandes, desempate por peso y luego por orden de entrada):
  sumar floats de a 0,1 acumula error y con quince posiciones el total termina en
  99,99999999999999. **`fijarPeso` es la única acción que no rebalancea, a propósito**: editar un
  porcentaje a mano es una intención sobre esa posición, no una orden de mover a las demás — y la
  cabecera ya marca en ámbar cuando la suma se desvía.
- **El monto dejó de estar duplicado** (`PanelArmadoAsistido.tsx`): había dos campos "monto" sin
  relación entre sí. El del asistido viajaba al backend y se descartaba al cargar el resultado; el
  de la cartera era el único que los resolvers usaban. Ahora los dos son vistas del mismo
  `montoTotal` del store.
- **Armado asistido RF+RV** (`backend/app/armado/renta_variable.py` nuevo, `api/v1/armado.py`
  extendido): `POST /api/v1/armado` acepta `pct_rv` (default por perfil desde `PCT_RV_PERFIL` —
  conservador 0 / moderado 25 / agresivo 60, calcados de `referencia/carteras-sugeridas-ifa.xlsx`)
  y `sector_rv`. Devuelve cada posición con `clase: "renta_fija" | "renta_variable"` y un
  `pct_rv_aplicado`. **El motor `armar()` no se tocó**: la paridad con `tools/armar_cartera.py`
  queda intacta y la composición de los dos bloques vive en el endpoint. La renta variable no puede
  armarse dentro de `motor.py` porque `EspecieUniverso` no representa una acción (`.naturaleza`
  busca un segmento que no existe), así que tiene su propio tipo y su propio criterio: **liquidez
  (`volumen_usd`) descendente con diversificación sectorial en dos pasadas**, empate por ticker.
  Una especie sin `volumen_usd` no participa —no se le asume cero, regla 1— y con temática activa
  una especie sin sector tampoco: no se puede afirmar que pertenezca.
- **Badges de clase** (`components/BadgeClase.tsx`): SOB / SUB / ON / ACC / CEDEAR al lado del
  ticker en grilla, cartera y renta variable. `clase_activo` es vocabulario curado del proyecto
  (lo asigna `ingesta/consolidacion/clasificacion.py`), no un código propietario de una fuente, así
  que traducir los cinco valores conocidos es leer lo que la fuente declara. **Un sexto valor se
  mostraría crudo y sin color** en vez de entrar a la categoría más parecida (regla 11).
- **La cartera se lee entera y por bloques** (`CarteraEditable.tsx`, `lib/bloques.ts`): la tabla
  dejó de listar sólo renta fija en orden de incorporación. Ahora muestra la cartera completa
  agrupada en cinco bloques con subtotal pedido —soberanos y subsoberanos, corporativos, fondos,
  sin clasificar, renta variable—, que es el formato del Excel de la mesa. **El "% real" pasó a
  medirse contra la cartera entera y no contra cada bloque**: cada uno resuelve su invertido con
  otra aritmética (lámina y precio cada 100 VN contra unidades enteras) y apilarlos bajo la misma
  columna daba porcentajes que no sumaban a nada. En la fila de una acción va la denominación de la
  empresa donde el bono muestra el emisor, y la columna de pagos dice **"no aplica"**, no `s/d`: una
  acción no tiene cronograma, el dato no falta, no existe.
- **Atajos temáticos** (`lib/tematicas.ts`, `components/ChipsTematicos.tsx`): Energía, Financieras,
  Tecnológicas y Cobertura inflación precargan de un clic los filtros de renta fija y el sector de
  renta variable a la vez. **Los sectores de RF están verificados uno por uno contra
  `data/condiciones_emision.csv`** — un preset que filtrara por un sector inexistente devolvería
  cero sin explicar por qué. "Tecnológicas" declara que arma **sólo renta variable** porque el
  universo de bonos no tiene emisores tecnológicos, y no se aproxima con Telecomunicaciones, que es
  otra cosa. El chip se apaga cuando los filtros dejan de coincidir con lo que dejó puesto, pero no
  deshace nada.
- **Las bajadas declaran los dos caminos** (`ArmadorPage.tsx`): se reescribieron para decir que el
  asistido (un botón) y el manual (Cordillera + Renta variable con temáticas) llegan a la misma
  cartera y que los dos terminan en la sección Cartera. `docs/guia-armador.md` se reorganizó en esos
  dos caminos.

**Tarea pendiente que este trabajo dejó a la vista: el job de perfiles de Yahoo nunca corrió.**
`public.perfil_renta_variable` está **vacía en producción (0 filas)** mientras `instrumentos` tiene
434 acciones y 1.205 CEDEARs. La tabla y el job (`POST /api/v1/jobs/perfiles-renta-variable`) los
dejó construidos la Etapa 4 del rediseño anterior; lo que falta es correrlo. Consecuencias
prácticas, las dos declaradas en pantalla y ninguna un bug: los filtros por sector y rubro del
buscador de renta variable no encuentran nada, y **la diversificación sectorial del armado asistido
no puede aplicarse** — arma por liquidez pura y lo dice con la alerta `rv_sin_perfil_sectorial`.

**Tanda 14 cerrada el 10/08/2026** — F-034 (modo "subir la TIR declarando la contrapartida"), sola.
**652 tests offline en el frontend (64 archivos) y 1.165 en el backend.** Van **40 de 42 features de
Stage 1**; quedan F-027 (fuera de tanda) y el camino crítico 15–18.

- **F-034 salió 100 % frontend, como F-033, y por un motivo que estaba en el propio contrato**:
  `candidata.tipo == "mejora_rendimiento"` (d_rend ≥ 0,5pp) es el **complemento exacto** de la banda
  de ±0,5pp con la que F-033 filtra. Los dos modos particionan el mismo conjunto de candidatas de
  F-032 sin solaparse, así que no hizo falta ni un parámetro nuevo en `POST /rotaciones`. Se ve en
  la pantalla real: con una cartera AL30D+AO27D, F-033 descarta las seis por "el rendimiento se
  mueve más de 0,5%" y F-034 muestra exactamente esas seis.
- **Los dos modos deciden distinto y por eso no comparten el tipo de salida.** F-033 **filtra** (el
  eje primario mejora, los otros cinco no empeoran); F-034 **declara** (nada se descarta por
  empeorar: empeorar es lo que hay para mostrar). Lo que sí se unificó, pensando en F-036, es el
  vocabulario por eje — `lib/rotaciones/ejes.ts`, con los signos, los estados y los motivos de
  descarte que antes eran privados de `bajarRiesgo.ts`.
- **El criterio que concilia los dos GWT que parecían tirar para lados opuestos** (uno dice que sin
  deltas la fila no se muestra, otro que la cobertura parcial se declara al lado del delta): un
  faltante **en las puntas** de la rotación mata la fila —sin dato en la punta el delta no es
  atribuible a la rotación, y mostrarla afirmaría que ese eje no empeora, que es distinto de no
  saberlo—; un faltante **en el resto de la cartera** no la mata, porque el delta agregado existe.
- **Un cambio de emisor cuenta como contrapartida aunque ningún número empeore.** Crédito no tiene
  métrica escalar (regla 7), así que "no empeoró" no se puede afirmar: se nombra el cambio con las
  calificaciones tal como las trae la fuente, ausencia incluida ("sin calificación → A1 (FIX)").
- **Primera UI del costo de rotar.** F-035 había cerrado sin pantalla: el bloque `costo` viajaba en
  cada candidata y el modo strip de Zod lo descartaba en silencio. Ahora cada fila de los dos modos
  declara total, arancel y payback, o dice que no es verificable cuando falta una punta. De paso se
  corrigieron dos textos que habían quedado mintiendo desde ese cierre ("el costo todavía no se
  calcula", "el spread llega con F-035").
- **Bug de producción encontrado al verificar contra el backend real, y arreglado**: `POST
  /api/v1/rotaciones` devolvía **500** en cuanto una candidata tenía las dos puntas vivas —
  `public.puntas` guarda `numeric`, asyncpg lo entrega como `Decimal` y `calcular_costo` lo suma con
  el arancel, que es `float`. Ninguna suite lo veía porque todos los fixtures de F-035 pasan floats.
  En los hechos el endpoint venía roto desde que F-035 empezó a leer puntas: **F-033 tampoco
  funcionaba end-to-end**. La conversión va en `puntas.py`, donde la firma promete `float | None`
  desde el principio, con un test que usa `Decimal` como lo hace la base.
- **Lección de verificación**: los tests de `SeccionBajarRiesgo` mockeaban siempre `candidatas: []`,
  así que la fila de propuesta nunca se había renderizado en una suite y el parseo del contrato no
  estaba ejercitado desde la pantalla. Un test verde no dice nada sobre el camino que no recorre.

**La serie histórica de precios se apagó el 10/08/2026 — trabajo suelto entre tandas, un commit.**
No es una feature de `plan.md`: salió de que el usuario preguntó por qué la base crecía sola.
`precios` y `puntas` acumulaban ~2.900 filas cada 15 minutos y nada las borraba (~11 MB por día
hábil). Se verificó que **nada del producto lee más de un snapshot** —la vista `resumen` y las dos
lecturas de puntas piden la fila más reciente por ticker, y la variación diaria sale de la columna
`cierre_anterior` de BYMA— así que lo acumulado no lo usaba nadie.

- **La decisión fue de producto, no de infraestructura**: la herramienta sirve para armar carteras,
  no para hacer seguimiento. El único histórico que el producto necesita es el precio al que se armó
  una cartera, y ya tiene su lugar en `posiciones.precio_compra` desde la migración inicial.
- **El flag `SERIE_HISTORICA_HABILITADA` (default false) deja el código de la serie utilizable**, a
  pedido del usuario. En true vuelve el comportamiento anterior bit por bit, con test que lo fija.
- **La poda es por ticker y eso es la feature entera.** El DELETE contra el máximo global de la tabla
  parece equivalente y rompe el producto: 291 de 3.176 tickers tenían su última cotización en un
  snapshot anterior (28 con precio), y habrían quedado publicados con precio y TIR en NULL. Hay un
  test que impide reintroducirlo.
- Resultado: `precios` de 33.882 filas a 3.176, la base de 25 MB a 17 MB, crecimiento diario a cero.
  Los DELETE los ejecutó la propia corrida siguiente —el backend corría con `--reload` y tomó el
  código—, y el espacio se recuperó con `VACUUM FULL`. Detalle completo en `docs/ESTADO.md`.

**F-036 — aceptación rotación por rotación (tanda 15, sola) — completada 10/08/2026.** Salió 100 %
frontend, como F-033/F-034: los tres endpoints que necesitaba (`/rotaciones`, `/concentracion`,
`/calendario/cartera`) ya existían. Verificado en vivo contra el backend real, no sólo con tests.

- **El estado guarda decisiones, nunca carteras derivadas.** `PlanRotacionProvider` (Context +
  `useReducer`, mismo patrón que `carteraStore.tsx` del armador) sólo persiste la pila de
  `Candidata` aceptadas y el set de claves descartadas; la cartera acumulada, los montos y las
  claves excluidas se recalculan siempre desde ahí. Por eso **deshacer** es sacar el último elemento
  de la pila y todo vuelve exacto — sin snapshot que pueda desincronizarse. Verificado en pantalla:
  aceptar AL30D→CP38O y deshacer devolvió la TIR, la duración y las tres propuestas originales bit
  por bit.
- **Deshacer es LIFO puro**, a propósito: las aceptaciones se encadenan (el destino de una puede ser
  el origen de la siguiente), así que deshacer una del medio dejaría a las posteriores con un origen
  que ya no está en la cartera. Sólo la última aceptada tiene botón.
- **El efecto de calendario (GWT-1) se calcula por fila**, comparando el calendario de la cartera
  actual contra el simulado de esa candidata, mes por mes y **moneda por moneda por separado** —
  nunca se suma entre monedas para decidir qué mes "se llena" (regla 3). Visto en producción: "Si se
  acepta: se llena Noviembre 2026 (USD) · se llena Mayo 2027 (USD) · se vacía Enero 2027 (USD) · se
  vacía Julio 2027 (USD)".
- **Aceptar recalcula sobre la cartera resultante de verdad**, no en apariencia: al aceptar
  AL30D→CP38O, las propuestas restantes pasaron a partir de `CP38O→...` (nuevo origen), y las que
  partían de AL30D desaparecieron porque ese ticker ya no está en la cartera.
- **La rotación inversa y lo descartado no vuelven a proponerse en la sesión** (GWT-3/GWT-4):
  `clavesExcluidas = descartadas ∪ inversas de aceptadas` se pasa a `useBajarRiesgo`/`useSubirTir`,
  que las filtra **antes** de evaluar y las cuenta aparte de los descartes por eje — mezclarlas
  habría hecho mentir a `ResumenDescartes` (un "descarte" por decisión del asesor no es un descarte
  por no cumplir un criterio).
- **`Cordillera` (el gráfico de barras del calendario) se extrajo** de `DiagnosticoCartera.tsx` a
  `components/Cordillera.tsx` para que el panel de cartera propuesta la reuse tal cual — una sola
  implementación. Los seis ejes de la propuesta reusan `SeccionRiesgo` (F-031) directo, sin
  reimplementar nada de riesgo.

**F-037 — comparación original contra propuesta (tanda 16, sola) — completada 10/08/2026.** También
100 % frontend: ningún endpoint nuevo, sólo un consumidor más de lo que F-036 ya pedía. Verificado
en vivo contra el backend real: AL30D solo, aceptar AL30D→BGC4D, deshacer, con los seis ejes y las
cuatro naturalezas leyéndose en las dos columnas.

- **"Misma vara" es consecuencia de la implementación, no una promesa**: las dos columnas de
  `ComparacionCarteras` llaman a las mismas funciones puras (`rendimientosPorNaturaleza`,
  `vectorDeRiesgo`, `calcularRentaAnualPorMoneda`) con las posiciones de cada lado — no hay una
  segunda fórmula que pueda divergir de la primera. Visto en pantalla: "TIR en dólares (hard
  dollar): 7,67% → 10,32%" con las cuatro naturalezas y los seis ejes presentes en las dos columnas,
  cada eje con su delta ("Duración: 1,9 años → 0,2 años (Δ -1,7)"; "Crédito: s/d → s/d" para los
  ejes compositivos, sin inventar un valor donde no hay).
- **El costo total se lleva a plata, nunca se suman porcentajes.** `costoAcumulado` toma el
  `total_pct` (F-035) de cada pata y lo aplica sobre el monto **encadenado** de esa pata —no el
  monto original—, normalizado a USD con el tipo de cambio implícito (regla 3). Lo no verificable o
  no convertible se declara con el par nombrado y sale del total, nunca se omite en silencio.
  Visto en producción: "Costo total de rotación acumulado: US$ 152,87".
- **El delta de los seis ejes no lleva color de mejora/empeora**, a diferencia de la renta y el
  rendimiento: "menor duración" o "mayor liquidez" no son universalmente mejores o peores (el
  percentil de liquidez, por ejemplo, es mejor cuanto más alto; la concentración, cuanto más bajo),
  así que pintarlo en verde/rojo habría inventado un juicio que la regla 7 prohíbe. El delta se
  declara en su unidad, neutro.
- **El diff de calendario mes a mes (GWT-2) reusa el núcleo de F-036** (`diffMesAMes`, extraído de
  `diffCalendario` sin cambiar su comportamiento) en una variante nueva, `diffCalendarioCarteras`,
  que compara la cartera original completa contra la propuesta en vez de una cartera contra la
  simulación de una sola candidata. Los meses se marcan en la cordillera propuesta, moneda por
  moneda, con `Cordillera`'s nueva prop opcional `marcas`. Visto en producción: "▲ 11/2026",
  "▼ 01/2027", "▼ 07/2027" en la cordillera, más la frase "Meses que cambian de cobertura: se llena
  Noviembre 2026 (USD) · se vacía Enero 2027 (USD) · se vacía Julio 2027 (USD)."
- **`PlanDeRotacion` se podó a su identidad real** — la lista de aceptadas, el costo por rotación y
  Deshacer—: el calendario y los seis ejes de la propuesta que mostraba en F-036 pasaron enteros a
  `ComparacionCarteras`, donde conviven con los de la cartera original medidos con la misma vara.
  Mostrarlos en los dos lugares habría sido el mismo dato dos veces.
- **Deshacer sigue devolviendo todo exacto**, ahora incluida la comparación: deshacer la única
  aceptada hizo desaparecer `ComparacionCarteras` entera y devolvió las tres propuestas originales
  (incluida la que se acababa de aceptar) a la lista de "Subir la TIR".

### Tanda 17 cerrada el 10/08/2026 — F-041 (guardar, listar, reabrir y revaluar carteras), sola

Cierra el Ciclo 4 salvo F-042. Verificado en el navegador contra el proyecto real de Supabase
(`xnkdsrzgxmceectenajp`), guardando, reabriendo, revaluando, reabriendo en el armador y borrando
una cartera de cada origen. Consumió F-018 y F-037.

- **Persistencia vía PostgREST + RLS desde el frontend, no vía FastAPI**: saldó la deuda declarada
  al cerrar la Tanda 1 (línea de abajo) sin tocar el backend. `frontend/src/lib/supabase.ts`
  (F-014, anon key) es el único cliente de Supabase; F-041 fue su primer consumidor de tablas de
  usuario — hasta acá el cliente sólo se usaba para `auth`. El pool del backend sigue conectado
  como `postgres` (`rolbypassrls=true`) y sigue sin servir ninguna tabla de usuario.
- **El snapshot es `jsonb`, no columnas**: `carteras` ganó `origen`, `moneda_referencia`, `monto`,
  `resumen`, `snapshot_en` (denormalizadas, para que el listado nunca baje un snapshot) y
  `snapshot` (el estado congelado entero, unión discriminada por `origen` — `cargada` o
  `armador` —, `z.strictObject` en todos los niveles propios). Normalizar en `posiciones` habría
  exigido soltar su FK a `instrumentos` (rompe con tickers inválidos y con FCI) y adivinar columnas
  que difieren por origen — mismo criterio que ya regía `propuestas.payload`. `posiciones` y
  `propuestas` quedaron sin usar.
- **`user_id` se completa solo**: `ALTER COLUMN user_id SET DEFAULT auth.uid()` — el INSERT del
  frontend no lo manda, PostgREST lo toma del JWT y la policy `WITH CHECK` lo sigue verificando.
- **GWT-1 (reabrir muestra lo guardado, no lo de hoy) es consecuencia de la implementación, no una
  promesa**: `VistaCongelada` renderiza exclusivamente el `snapshot`; verificado en el navegador
  con la fila real de Supabase, sin ningún request de mercado hasta tocar "Revaluar a hoy". Ese
  botón recién ahí monta `useCarteraCargadaValuada` (origen `cargada`, el mismo hook del pipeline
  vivo) o el universo + tipo de cambio de hoy (origen `armador`), y compara con `compararValuaciones`
  — delta por posición sólo si la moneda coincide en las dos puntas, total en USD con el TC de cada
  punta declarado, faltantes nombrados nunca estimados. Visto en producción, origen armador: "Total:
  US$ 9.485,02 → US$ 9.483,71 (Δ US$ -1,31)" con cada ticker abierto y su delta o su motivo.
- **"Abrir en el armador" rehidrata sólo el mandato**, no la foto valuada: `cargarCartera` +
  `fijarMontoTotal` sobre las mismas posiciones y el mismo capital objetivo guardados —el armador
  recalcula todo con precios de hoy, que es lo que "seguir trabajando" pide—. Verificado: la
  cartera reabierta mostró los mismos % pedidos por ticker que tenía al guardar.
  **Sólo entra para origen `armador`**; rehidratar el origen `cargada` (`CarteraConfirmada` +
  `PlanRotacionProvider` con estado inicial) queda fuera de alcance, deuda declarada — ningún GWT
  lo pedía y el snapshot ya guarda el plan de rotaciones validable con `esquemaCandidata`.
- **GWT-3 (aislamiento entre asesores) verificado por SQL, no sólo por la policy en el papel**: con
  `set local role authenticated` + `request.jwt.claims` simulando dos `sub` distintos, el asesor B
  ve 0 filas de una cartera de A, y un INSERT de B con `user_id` de A explícito lo rechaza
  `insufficient_privilege: new row violates row-level security policy for table "carteras"`.
- **GWT-4 (sin campos de cliente) verificado en una fila real**: `jsonb_object_keys(snapshot)` de
  la cartera guardada en el navegador dio exactamente `{origen, version, resueltas, posiciones,
  tipoDeCambio, montoTotalUsd, totalInvertidoUsd}` — la whitelist declarada, nada más.

### Tanda 21 cerrada el 16/08/2026 — F-027 (calendario de balances), sola: cierra Stage 1

Última feature pendiente del MVP. Alcance recortado el mismo día por el dueño del producto: sin
CNV (queda para Stage 2, F-054) — la renta variable del producto son sólo CEDEARs desde la Tanda
20, y un CEDEAR cotiza en EEUU, así que **SEC EDGAR alcanza solo**.

- **La fuente se verificó en vivo antes de escribir código**, contra Apple (filer doméstico) y
  Vale (foreign private issuer, el caso más ruidoso: 840 `6-K` en la ventana). `filings.recent`
  de `submissions/CIK.json` alcanza sin paginar — cubre 11 años para Apple y los últimos cinco
  `20-F` para Vale — y la ventana realmente cubierta se declara en la respuesta.
- **Los `6-K` de un foreign private issuer no se clasifican.** Medido: `core_type` dice "6-K" en
  839 de 840, `isXBRLNumeric` viene en 0/`None` en todos — la SEC no distingue cuáles traen un
  estado contable. Estos emisores quedan en `solo_anual=true` con su nota, mismo concepto que ya
  usaba la ficha de F-053 para el mismo tipo de emisor.
- **Cliente nuevo (`externos/sec_calendario.py`), no se tocó `sec_ficha.py`**: su `_filings()`
  corta a propósito en 1 anual + 3 intermedios (lo que necesita la ficha); acá hace falta recorrer
  la lista entera para derivar un patrón, que es un problema distinto.
- **On-demand, sin persistencia**, por el contrato de `app/externos/` y el mismo criterio que
  F-054: caché de 24 h por papel, sin migración ni job ni tabla nueva.
- **Endpoint nuevo `POST /renta-variable/balances`**, papeles ya resueltos en el cuerpo (no
  tickers de especie) — el llamador es el bloque de renta variable, que ya sabe el papel de cada
  posición. Verificado en vivo contra la SEC real después de implementar: AAPL con patrón
  trimestral completo, VALE con `solo_anual` y su nota, un papel inexistente declarado ausente —
  los tres coinciden con lo medido en la investigación previa.
- **1.264 tests backend (13 nuevos) y 983 frontend (44 nuevos)**, todos verdes. La única falla de
  la corrida completa (`test_migraciones.py`, una migración de la Tanda 12) es preexistente y no
  la tocó esta tanda — confirmado corriéndola contra el working tree sin estos cambios.

**Lo que esta tanda NO pudo verificar:** la extensión de Chrome no estaba conectada en esta
sesión, así que el flujo no se recorrió a ojo en el navegador (el checklist habitual de estas
tandas). El respaldo es la cobertura de tests más la verificación por `curl` contra la SEC real y
contra el backend local ya corriendo (con recarga automática, tomó el código nuevo sin reiniciar).

---

### Tanda 20 cerrada el 13/08/2026 — clasificación de la renta variable (sin ficha de plan.md)

Pedido directo del dueño del producto: *"es necesario saber la acción a qué se dedica, rubro, qué
provee, qué rol cumple en el proceso productivo, y si es un ETF cuál es la estrategia de inversión
que respalda el armado de esos portafolios"*. Verificado contra la SEC real y en el navegador.

- **La fuente pasó de Yahoo Finance a la SEC.** Yahoo bloqueó el endpoint de perfil (429 sostenido,
  medido con `curl` puro fuera de nuestro código) y `perfil_renta_variable` tenía **cero** filas: los
  dos selects del buscador nunca ofrecieron una opción y los presets temáticos filtraban contra un
  campo vacío. `data.sec.gov` responde sin clave, sin bloqueo y con contrato publicado.
- **Se clasifica por papel, no por especie.** Preguntarle a la SEC por `AAPL`, `AAPLC` y `AAPLD`
  serían tres pedidos para escribir tres filas idénticas. Lo habilitó el agrupamiento de la tanda
  anterior (`app/renta_variable/agrupamiento.py`).
- **Resultado medido**: 1.641 filas escritas, 870 con código SIC, 123 fondos con estrategia, 1.074
  con nombre de empresa y 993 con ratio de conversión.
- **El eslabón productivo sale de la división del SIC Manual**, que es estructura oficial de la
  taxonomía (10-14 extracción, 20-39 manufactura, 52-59 comercio minorista, 60-67 finanzas). Lo que
  el pedido llamaba "qué rol cumple esa materia prima en el proceso productivo" **no se escribió**:
  no tiene fuente y sería inventar.
- **La estrategia de los ETFs sale del nombre que publica BYMA**, no de la SEC: de 25 ETFs sólo dos
  tienen CIK, `SPY` y `QQQ` traen el SIC vacío y `GLD` trae `6221 Commodity Contracts Brokers`, que
  describe el vehículo legal y no dice nada de qué compra el fondo.
- **El bug que hacía que el job no avanzara**, encontrado corriéndolo: los papeles que la SEC no
  lista no se guardaban y volvían a la cola en cada corrida. Nueve tandas de 100 bajaron los
  pendientes de 1.539 a 1.536. La fila vacía **se escribe igual**: es el registro de que ya se
  preguntó y no está.
- **Un error de la fuente, declarado y no resuelto**: el PDF de BYMA publica `XLU` con dos nombres
  distintos (ciberseguridad y Utilities). No hay forma de saber cuál es el bueno, así que el código
  entero se descarta con alerta — mismo criterio que los conflictos del artefacto curado.

**Lo que esta tanda NO logró:** las **acciones argentinas siguen sin clasificar**. La SEC lista 21
de 245 (sólo las que tienen ADR) contra 315 de 427 CEDEARs; su fuente es la CNV y espera a F-054.
Se declaran vacías en pantalla, no se completan por analogía.

**Deuda chica, medida:** 7 de los 413 papeles del PDF de BYMA no se reconocen como fondos porque la
fuente publica el nombre truncado y se le cae la marca — `SPDR S&P 500` (SPY), `SPDR DOW JONES
INDUSTRIAL` (DIA), `ISHARES MSCI EMERGING MARKET` (EEM), `ISHARES MSCI BRAZIL CAP` (EWZ),
`ARK INNOVATION` (ARKK), `VANGUARD DIVIDEND APPRECIATION` (VIG) y `iShares U.S. Aerospace & Defense`
(ITA). Reconocerlos exigiría tratar "SPDR" o "iShares" como marca de fondo, que es conocimiento
nuestro y no algo que la fuente declare.

---

### Tanda 19 cerrada el 13/08/2026 — rediseño del flujo del armador (sin ficha de plan.md)

No es una feature del PRD: sale de un pedido directo del dueño del producto sobre el flujo de
armado. Verificado en el navegador contra el backend local y el proyecto real de Supabase.

- **El objetivo RF/RV dejó de ser estado local del panel y pasó al store** (`objetivoRv`). Era un
  `useState` que se perdía al plegar la sección, pero es el mandato del cliente: la cartera se
  sigue comparando contra él mientras el asesor edita pesos a mano. `null` (sin objetivo) y `0`
  (pidió cero acciones) son cosas distintas, igual que en `pct_rv` del backend. El desvío se
  muestra en `ColumnaKpis` con tolerancia de medio punto — el ruido de redondear a un decimal.
- **La sección "Armador de cartera" concentra el mandato completo**: monto, % RF/RV, rendimiento
  mínimo, plazo máximo, periodicidad de cupón, calificación y temática. Verificado en vivo: el
  rendimiento mínimo escribe el mismo `filtros.tirMin` que la barra de la grilla (los dos en 6) y
  además viaja como `min_rend` al `POST /armado` — que el backend aceptaba desde F-019 y el
  frontend nunca había expuesto.
- **`vencimientoMax` es un filtro nuevo y no reemplaza a `duracionMax`**: un amortizing a 2038 con
  cupones grandes tiene duración corta y plazo largo. Medido en vivo: plazo ≤ 3 años deja 26 de
  133 papeles donde sin él pasaban 51.
- **La periodicidad de cupón sale del cronograma contractual**, no de la ventana de doce meses
  —`filtros.ts` ya documentaba por qué eso último no alcanza—. Se expone `frecuencia_por_raiz`
  (F-032) en `/universo/emisiones/especies`. Medido sobre 969 especies: 542 semestral, 172
  trimestral, 111 al vencimiento, 11 mensual, 7 anual, 1 bimestral, 125 sin cronograma. En vivo,
  filtrar "mensual" deja 1 de 133 papeles.
- **El orden de las secciones lo decide quien arma.** Las seis salieron del JSX a un registro
  (`lib/secciones.tsx`) y se apilan según `useOrdenSecciones`, persistido en `localStorage` con el
  mismo criterio que el plegado. Verificado en vivo: subir Renta variable dos lugares y recargar
  la página la deja donde se la dejó. **El acento de color viaja con la sección, no con la
  posición** — si dependiera del lugar, mover una le cambiaría el color y se perdería la
  referencia visual.
- **Reemplazar una sugerencia de renta variable**: la tarjeta suma "cambiar", que saca la posición
  y deja el buscador enfocado y pre-filtrado por su sector. Sin perfil de empresa cargado no
  filtra nada, en vez de inventar una equivalencia.

**Lo que esta tanda NO logró:** el job de perfiles de empresa (`POST /jobs/perfiles-renta-variable`)
**no pudo correr**: Yahoo devolvió HTTP 429 desde el primer pedido en las 8 tandas que se
intentaron, con 0 tickers procesados sobre 1.641 pendientes. El filtro temático de renta variable
sigue sin datos y la UI lo sigue declarando (`SIN_PERFILES_DE_EMPRESA`). Es la misma deuda de
antes, no una nueva. **Resuelto en la tanda 20 cambiando de fuente, no destrabando Yahoo**: el
rubro pasó a la SEC y el filtro dejó de estar vacío. El bloqueo de Yahoo sigue en pie.

---

### Tanda 18 cerrada el 10/08/2026 — F-042 (exportación a Excel y PDF), sola

Cierra el Ciclo 4 entero y el camino crítico del plan. Consumió F-041. Verificado en el
navegador contra el backend real y el proyecto real de Supabase: cartera armada con posiciones
reales → guardada → reabierta en `/carteras/:id` → exportada a Excel y a PDF, los dos archivos
abiertos y leídos con `openpyxl`/`pdfplumber` para confirmar contenido, no sólo que el archivo
existiera.

- **El export siempre lee un `SnapshotCartera`**, guardado o armado en vivo: un solo
  `modeloDesdeSnapshot()` cubre los dos orígenes que pide la spec ("cartera guardada o en
  curso"). `write-excel-file` y `jspdf`/`jspdf-autotable` se cargan con `import()` dinámico
  sólo al hacer click — confirmado con `npm run build` que quedan en chunks separados
  (`browser-*.js`, `jspdf.es.min-*.js`, `html2canvas-*.js`) del bundle principal.
- **El snapshot de F-041 no traía nada de lo que los GWT piden** (rendimiento, naturaleza,
  lámina, vector de riesgo, calendario): se le agregó un bloque `mercado` opcional dentro de
  `version: 1` — no una versión nueva — así que una fila guardada antes de esta feature sigue
  parseando, con `mercado === undefined`, y el export declara el faltante por nombre en vez de
  recalcularlo con precios de hoy (eso sería "Revaluar a hoy", otra función).
- **GWT-1 verificado con datos reales**: la hoja "Rendimientos" trae las cuatro naturalezas
  siempre abiertas, cada una con su propio rendimiento ponderado — TIR en dólares con dato, las
  otras tres en `s/d` (número crudo, no texto, cuando hay dato; texto `s/d` cuando no) — y
  ninguna celda ni fila las combina. El PDF replica exactamente la misma tabla.
- **GWT-2 verificado con datos reales**: la hoja "Declaraciones" cuenta las posiciones sin
  lámina informada y el % de la cartera sin ajustar (`0 posición(es) sin lámina informada
  (0,00%)` con la única posición de la prueba, que sí tenía lámina); el caso con lámina
  faltante está cubierto por test unitario sobre `declaracionLamina()`.
- **GWT-3 verificado con datos reales, incluso con paginación**: el PDF de la prueba salió en 2
  páginas y el pie — `Precios capturados: 10/08/2026, 17:00 · Demora de la fuente: 20 min
  (BYMA...) · Generado: 10/08/2026, 18:43` — apareció en las dos, dibujado al final recorriendo
  `getNumberOfPages()` en vez de con el hook de página de `autoTable`, para no depender de qué
  sección cayó en qué hoja.
- **Cierra design-system.md:118-123**: `ColumnaKpis` del armador ganó el flujo mes por mes (una
  tabla por moneda de cobro, nunca una fila que sume monedas distintas) y el botón "Descargar
  propuesta", los dos pendientes desde la Etapa 6 del rediseño.
- **Deuda encontrada y saldada en el propio cierre**: el dev server de Vite tenía cacheados los
  deps de antes de instalar `write-excel-file`/`jspdf`/`jspdf-autotable` — el `import()` dinámico
  fallaba con `Failed to fetch dynamically imported module` sin ningún error de código de por
  medio. Se resuelve reiniciando el servidor (o borrando `frontend/node_modules/.vite`) después
  de instalar una dependencia nueva; no es un bug de F-042, pero conviene tenerlo presente para
  la próxima instalación de paquete con el server ya corriendo.

Con esto se cierra el Ciclo 4 y el camino crítico completo (F-001→F-042) del plan.

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
  **Saldada al cerrar la tanda 17 (F-041, 10/08/2026)**: se optó por la primera salida — el
  frontend lee y escribe `carteras` directo contra PostgREST con el JWT del asesor
  (`frontend/src/lib/supabase.ts`), sin pasar por `/api/v1/`. El pool del backend sigue con el
  mismo rol y sigue sin servir ninguna tabla de usuario; la deuda no se resolvió tocándolo, se
  esquivó por diseño.

### Lo que F-007 dejó pendiente, declarado

- **`tna` está vacía en todo el universo.** Venía del endpoint de Rendimiento de Bonos de Docta, que
  ya no se consume. El motor la usa para el rendimiento de tasa fija. La corrida lo alerta.
- **~450 especies de `public-bonds` quedan fuera del universo** por no tener cronograma que declare
  su clase. Son casi todas las X/Y/Z que BYMA publica como segundo trío de cada soberano y que el
  consolidado histórico nunca tuvo; sus puntas sí se guardan.
- **La ley y la moneda de pago cubren 592 de 2.894 instrumentos**, que son las 242 emisiones del
  informe de IAMC con sus especies. El resto llega con F-009.

---

## Pendientes de datos y decisiones — al 23/08/2026

Cerrado Stage 1, lo que traba el producto **no es código sino dato y decisiones**. Las tres
primeras son funcionalidad ya construida que no se está usando.

**1. El job de perfiles de renta variable nunca corrió.** `public.perfil_renta_variable` tiene 0
filas contra 434 acciones y 1.205 CEDEARs en el universo. Consecuencia concreta: los filtros por
sector y rubro no encuentran nada, y **la diversificación sectorial del armado asistido no se
aplica** (alerta `rv_sin_perfil_sectorial`). Es dato faltante, no un bug: el código está. Agravante:
`YAHOO_HABILITADO` está apagado desde el 429 sostenido del 08/08/2026, así que la fuente de sector,
país y rubro está cortada — sin resolver eso, el job no tiene de dónde traer los perfiles.

**2. La ingesta programada nunca corrió de verdad.** `corridas_ingesta` está vacía: todo el dato
entró por corridas manuales, sin traza de fuente ni fecha (alerta `sin_corrida_registrada`). F-008
está implementada; lo que falta es ponerla a correr en el entorno que corresponda.

**3. Falta una decisión del dueño del producto: el umbral de "dato viejo".** Hoy
`antiguedad_minutos` viaja crudo, sin alerta, porque nadie fijó a partir de cuántos minutos un
precio deja de servir para armar. Es criterio de negocio, no técnico, y bloquea la alerta.

**4. Fuentes pausadas por flag, con su feature de reactivación identificada:**

| Flag | Desde | Qué se pierde | Se destraba con |
|---|---|---|---|
| `IAMC_HABILITADO=false` | 13/08/2026 | 35 emisiones con rendimiento (283 → 248), convexidad, valor residual | F-055 (descarga automática) |
| `YAHOO_HABILITADO=false` | 08/08/2026 | PER, valor libro, beta, país, rubro, empleados | sin feature asignada — ver punto 1 |
| `CNV_HABILITADO=false` | 17/08/2026 | prospectos de ON (default apagado por diseño; `.env` local lo tiene en true) | ninguna: es el flag normal de la feature |

**5. La serie histórica de precios no se acumula.** La poda de consolidación deja una fila por
ticker, así que el producto no tiene historia propia: sin ella no hay volatilidad, correlaciones,
beta ni Sharpe, y F-061/F-062 no tienen insumo. Se destraba con **F-073**, y es el único pendiente
del backlog donde postergar tiene un costo que no se recupera: la historia empieza el día que se
prende.

**6. El cronograma de pagos no tiene fuente viva** desde la baja de Docta (12/08/2026). El conjunto
de `public.cashflow` quedó cerrado y es irrecuperable: toda emisión que empiece a cotizar de ahora
en más entra sin cronograma, sin tipo de tasa y sin métricas propias, declarada faltante.

**7. Coberturas parciales declaradas** (no bloquean, quedan a la vista): bid/ask en 674 de 927
instrumentos del motor · calificación en 359 de 927 · lámina en 568 de 927 · 236 instrumentos sin
ley ni moneda de pago · 6 emisores sin CUIT resoluble en `data/emisores_cuit_pendientes.csv` ·
`tna` vacía en las 2.894 filas · cobertura del calendario en 70 de 431 emisiones.
