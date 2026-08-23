# Plan de Producto — 10-Swaper

Fase 2 del pipeline. Fecha: 05/08/2026.
Inputs: `product-definition.md` (Fase 1A), `idea-brief.md` (Fase −1), `CLAUDE.md` (reglas del dominio).
Output que consume: `/init-project` (Fase 4) y `/build-feature` (Fase 5).

---

## 0. Resumen ejecutivo

| | |
|---|---|
| Features totales | 56 (F-001 … F-056) |
| Stage 1 | 42 |
| Foundation (obligatorias en Stage 1) | 3 |
| Stage 2 | 11 |
| Esfuerzo Stage 1 | 185 person-days *(estimación)* |
| Esfuerzo Stage 2 | 72 person-days *(estimación)* |
| Ciclos de Stage 1 | 4 |
| Feature crítica | **F-002** (esquema de datos) — desbloquea 24 features de forma directa o transitiva |

Las 13 features conceptuales del `product-definition.md` (F1–F13) se descomponen acá en unidades
construibles por `/build-feature`: cada F-0NN es una unidad con lógica, superficie de API o UI, y
tests propios. **No se agregó alcance nuevo**: cada F-0NN traza a una F1–F13 del documento de
producto o a un requisito Foundation explícito.

Las 10 reglas del dominio de `CLAUDE.md` no son criterios de aceptación opcionales: aparecen como
acceptance criteria verificables dentro de las features donde se materializan, y están mapeadas en
la sección 9.

---

## 1. User personas

### Persona 1 — Marina, asesora financiera de la ALyC (persona primaria)

**Contexto.** Empleada de la ALyC. Atiende una cartera de clientes minoristas. Trabaja todo el día
con la misma pantalla abierta y opera en las tres monedas de liquidación: pesos, dólar MEP y dólar
cable. No es trader ni analista cuantitativo.

**Jobs to be done**
- *Cuando* un cliente me pregunta "¿cuánto voy a cobrar y cuándo?", *quiero* llegar a la reunión con
  un calendario mes a mes en plata real, *para* vender certeza de cobro y no una tasa abstracta.
- *Cuando* armo una cartera nueva, *quiero* elegir los papeles desde el mes que necesito cubrir,
  *para* no descubrir después de comprar que toda la renta cae en marzo y septiembre.
- *Cuando* el cliente me pide más rendimiento, *quiero* poder decirle en la misma frase qué está
  pagando por ese rendimiento, *para* que la decisión sea suya y quede documentada.

**Flujo de uso principal.** Flujo A (armar desde cero) y Flujo C (consulta de mercado a la mañana).

**Métricas de éxito de la persona**
- Tiempo de armado de una cartera desde cero: hoy es trabajo de planilla; objetivo declarado del
  producto es que ocurra en una sesión. *(No hay medición de línea de base en los inputs — se mide
  desde la primera semana de uso.)*
- Cantidad de meses sin cobertura en las carteras que produce: la métrica que el producto existe
  para bajar.
- Cero números en pantalla que no pueda rastrear hasta un dato de fuente.

---

### Persona 2 — Damián, asesor independiente que opera a través de la ALyC

**Contexto.** No es empleado; opera a través de la ALyC. No tiene acceso al monitor interno de la
mesa ni a los Excel de carteras sugeridas — su alternativa real hoy son screeners públicos y su
propia planilla. Trabaja con menos infraestructura y más volumen de clientes chicos.

**Jobs to be done**
- *Cuando* llega un cliente con una cartera armada en otro lado, *quiero* diagnosticarla en minutos,
  *para* poder ofrecer una mejora sin invertir horas de trabajo manual que no puedo facturar.
- *Cuando* comparo instrumentos, *quiero* el universo completo y no una lista curada a mano, *para*
  no depender del criterio de otro sobre qué papeles existen.
- *Cuando* uso una herramienta que no es mía, *quiero* que mis carteras sean mías y de nadie más,
  *para* poder trabajar con tranquilidad sobre un sistema compartido.

**Flujo de uso principal.** Flujo B (optimizar una cartera existente).

**Métricas de éxito de la persona**
- Carteras existentes diagnosticadas por mes: hoy es cero, porque no se hace.
- Tasa de tickers resueltos contra el universo al pegar un resumen de cuenta.
- Aislamiento verificable: nunca ve una cartera que no es suya (RLS, no filtro de cliente).

---

### Persona 3 — Sergio, jefe de mesa (persona de revisión)

**Contexto.** No arma carteras todos los días: revisa las propuestas que arman los asesores antes de
que salgan. Es quien tiene que poder defender una propuesta si el cliente o el compliance la
cuestiona. Es también quien ya conoce la pantalla "Cuponera" del monitor interno y va a comparar
contra ella.

**Jobs to be done**
- *Cuando* reviso una propuesta, *quiero* ver la contrapartida de riesgo declarada al lado de cada
  mejora de TIR, *para* aprobarla o devolverla en un vistazo y no reconstruir el razonamiento.
- *Cuando* un número me llama la atención, *quiero* saber de qué fuente salió, de qué hora, y qué
  cobertura tiene ese campo, *para* poder responder por él.
- *Cuando* comparo dos propuestas de dos asesores distintos, *quiero* que estén medidas con la misma
  vara, *para* que la diferencia sea de criterio y no de método.

**Flujo de uso principal.** Reapertura de carteras guardadas (F-041) y lectura del vector de seis
ejes (F-031) sobre propuestas ajenas. *Nota: la visibilidad de carteras de terceros es Stage 2 — en
Stage 1 la revisión ocurre sobre el export (F-042) o sesión compartida.*

**Métricas de éxito de la persona**
- Propuestas devueltas por falta de fundamento: objetivo, que baje a cero.
- Reproducibilidad: una cartera guardada hace tres semanas se reabre y muestra exactamente los
  números con los que se presentó.

---

## 2. Escala de RICE declarada

Para que los scores sean comparables y auditables, la escala se declara. **La cantidad de usuarios
no está en los inputs**: se usa una base estimada y se marca como tal.

- **Reach** = sesiones de asesor por mes que tocan la feature. Base estimada: **400 sesiones/mes**
  (20 asesores × 20 ruedas). *Es una estimación, no un dato de los inputs.* Una feature que toca
  todas las sesiones tiene R = 400; una que sólo aparece en el Flujo B tiene R ≈ 200.
- **Impact** — 3 = masivo (sin esto el producto no existe), 2 = alto, 1 = medio, 0,5 = bajo,
  0,25 = mínimo.
- **Confidence** — 100 % = lógica ya construida y verificada contra fuente real, o contrato de
  fuente verificado empíricamente; 80 % = camino claro con incógnita de implementación; 50 % =
  depende de una fuente o un parsing no verificado; 25 % = sin fuente conocida.
- **Effort** — person-days de un desarrollador fullstack, incluyendo tests.
- **Score** = (R × I × C) / E.

---

## 3. Catálogo de features

Cada ficha: etiqueta, traza a la feature conceptual del `product-definition.md`, descripción, input,
output, dependencias, RICE y acceptance criteria.

---

### Bloque A — Foundation

---

#### F-001 — Esqueleto de servicio backend

**Etiqueta:** Foundation (obligatoria en Stage 1) · **Traza a:** requisito Foundation

**Descripción.** Servicio FastAPI con todo lo que después es carísimo retrofitear: prefijo `/api/v1/`
en cada ruta, `GET /health` que verifica conectividad a PostgreSQL y devuelve la hora del último
snapshot de mercado, logs en JSON estructurado a stdout con `request_id`, contrato de error uniforme,
paginación por cursor en toda colección, y `Dockerfile` con la imagen que después se despliega en
Fly.io o Railway. Los secretos (URL y claves de Supabase, token de Docta) se leen exclusivamente de
`.env` vía Pydantic Settings, y el arranque falla ruidosamente si falta alguno. Es la primera cosa
que se construye porque toda otra feature de backend se monta encima.

**Input:** nada — es la raíz del árbol de dependencias.
**Output:** aplicación desplegable, contrato de API versionado, paginación y logging que todas las
demás features heredan sin volver a decidirlos.
**Depende de:** —
**Habilita:** F-002, F-004, F-005, F-006, F-008, y transitivamente todo el backend.

**RICE:** R = 400 · I = 3 · C = 100 % · E = 3 → **Score 400**

```
GIVEN el servicio levantado con base de datos accesible
WHEN se hace GET /api/v1/health
THEN responde 200 con el estado de PostgreSQL y el timestamp del último snapshot de mercado

GIVEN una variable de entorno obligatoria ausente de .env
WHEN el servicio arranca
THEN falla en el arranque nombrando la variable faltante, y no levanta en modo degradado

GIVEN un endpoint de colección con más resultados que el tamaño de página
WHEN se lo consulta sin parámetros
THEN devuelve la primera página con cursor de continuación, nunca el conjunto completo

GIVEN cualquier request al servicio
WHEN se procesa
THEN se emite una línea de log JSON con request_id, ruta, status y duración, y ningún secreto
```

---

#### F-002 — Esquema de datos y migraciones

**Etiqueta:** Foundation (obligatoria en Stage 1) · **Traza a:** F1 + F3 + requisito Foundation

**Descripción.** Modelo de datos completo en PostgreSQL/Supabase, con migraciones versionadas. Dos
familias de tablas con reglas distintas. **Mercado, compartido y sin RLS de lectura:**
`instrumentos`, `precios`, `puntas`, `cashflow`, `condiciones_emision` — el universo es el mismo para
todos. **Usuario, con `user_id` FK obligatoria y Row Level Security:** `carteras`, `posiciones`,
`propuestas`. El esquema de mercado **replica el contrato de salida del `Resumen` actual y de
`cashflow_completo.csv`**, que es lo que permite reusar el 85 % del motor sin tocarlo. Cada valor de
`condiciones_emision` lleva `origen` y `fecha` en la misma fila que el valor.

**Input:** las columnas del universo consolidado actual y de `cashflow_completo.csv`; el listado de
campos de BYMA, IAMC y Docta de la sección de fuentes.
**Output:** base de datos migrable, tipos TypeScript generados, y el contrato de persistencia que
consume todo el backend.
**Depende de:** F-001
**Habilita:** F-007, F-009, F-014, F-015, F-041, y transitivamente todo lo que persiste.

**RICE:** R = 400 · I = 3 · C = 100 % · E = 4 → **Score 300**

```
GIVEN el esquema migrado desde cero
WHEN se inspeccionan las tablas carteras, posiciones y propuestas
THEN todas tienen user_id NOT NULL con FK a auth.users y RLS habilitada

GIVEN una fila de condiciones_emision con lamina cargada
WHEN se la consulta
THEN trae origen y fecha en la misma fila, y ninguno de los dos es nulo

GIVEN el esquema de instrumentos y cashflow
WHEN se compara contra las columnas del Resumen actual y de cashflow_completo.csv
THEN cada columna del contrato anterior tiene su correspondencia, y las que no existan están
     documentadas como bajas explícitas

GIVEN una migración aplicada
WHEN se corre el rollback
THEN el esquema vuelve al estado anterior sin pérdida de las tablas de mercado
```

---

#### F-003 — Esqueleto de aplicación frontend

**Etiqueta:** Foundation (obligatoria en Stage 1) · **Traza a:** requisito Foundation

**Descripción.** SPA con React 19 + TypeScript + Vite: ruteo, layout de las seis pantallas
esenciales, cliente de API tipado contra `/api/v1/`, TanStack Query configurado con la política de
invalidación que después usa cada refresh de precios, Tailwind con los tokens del design system, y
tema oscuro por defecto con opción de claro. Incluye el manejo global de errores y estados de carga,
para que ninguna feature posterior reinvente cómo se ve un fetch que falla. Sin renderizado en
servidor: es una herramienta interna, no hay SEO ni primera carga fría que optimizar.

**Input:** contrato de API de F-001; `design-system.md` de la Fase 3 cuando exista.
**Output:** aplicación navegable con las rutas vacías, cliente de datos, y las convenciones de UI que
heredan todas las pantallas.
**Depende de:** F-001
**Habilita:** F-013, F-014, F-016, F-038, y transitivamente toda la UI.

**RICE:** R = 400 · I = 3 · C = 100 % · E = 3 → **Score 400**

```
GIVEN la aplicación levantada
WHEN se navega a cada una de las seis rutas principales
THEN cada una renderiza su layout sin errores de consola

GIVEN un endpoint de la API que devuelve error
WHEN una vista lo consulta
THEN se muestra el estado de error global con el mensaje del contrato, y no una pantalla en blanco

GIVEN el tema oscuro por defecto
WHEN el usuario alterna a claro
THEN la preferencia persiste entre recargas
```

---

### Bloque B — Ingesta y consolidación del universo (F1)

---

#### F-004 — Cliente de la API abierta de BYMA

**Etiqueta:** Stage 1 · **Traza a:** F1

**Descripción.** Cliente HTTP de `open.bymadata.com.ar` que consume por POST y sin token los cinco
endpoints verificados el 05/08/2026: `negociable-obligations` (4.909 filas), `public-bonds` (189),
`cedears` (2.267), `general-equity` (189) e `index-price` (16). Normaliza los campos de la rueda
—`bidPrice`/`offerPrice` con cantidades, `denominationCcy`, `settlementType`, `closingPrice`, `vwap`,
`volume`, `volumeAmount`, `numberOfOrders`, `maturityDate`— a un modelo interno tipado. La moneda de
cotización **se lee de `denominationCcy`**, nunca se infiere del sufijo del ticker. Registra la
demora declarada de 20 minutos como atributo del snapshot, no como nota al pie.

**Input:** los cinco endpoints de BYMA.
**Output:** snapshot de rueda normalizado: precios, puntas, volumen, moneda de cotización, especies y
plazos de liquidación, más las 16 filas de `index-price` para el contraste de F-012.
**Depende de:** F-001
**Habilita:** F-007, F-012, F-026

**RICE:** R = 400 · I = 3 · C = 100 % · E = 4 → **Score 300**

```
GIVEN los cinco endpoints de BYMA disponibles
WHEN corre la ingesta de rueda
THEN se obtienen las cinco respuestas por POST sin token y el conteo de filas de cada una queda
     registrado en el snapshot

GIVEN un instrumento con denominationCcy = "USD" y ticker sin sufijo D ni C
WHEN se normaliza
THEN la moneda de cotización queda en USD por el campo declarado, y en ningún punto del código se
     deriva del sufijo del ticker

GIVEN un endpoint de BYMA que responde 401
WHEN corre la ingesta
THEN ese endpoint queda marcado como no disponible con su código, los otros cuatro se ingieren
     igual, y la barra de estado del dato lo declara

GIVEN un snapshot ingerido
WHEN se lo consulta
THEN expone la hora de captura y la demora declarada de 20 minutos como atributos propios
```

---

#### F-005 — Parser del informe diario de IAMC

**Etiqueta:** Stage 1 · **Traza a:** F1
**Estado: CONSUMO PAUSADO el 13/08/2026 — el código quedó entero.** A diferencia de F-006, acá no
se borró nada: el parser, el almacén y `POST /api/v1/iamc/informe` siguen en el repo y con sus
tests. Lo que se apagó es el consumo, con `IAMC_HABILITADO` (default `false`).

**Por qué.** El informe llegaba por subida manual y no se descargaba solo: cada corrida volvía a
parsear el último archivo cargado, que en producción terminó teniendo ocho días. Y no se declaraba
en ninguna parte —ni `/estado-del-dato` ni la ficha exponen la fecha del informe—, así que el
asesor veía una TIR del 05/08 al lado de un precio del 12/08 sin ningún rótulo. Un dato viejo sin
declarar es peor que un dato ausente.

**Qué corta la pausa.** Dos cosas, y la segunda es la que la hace efectiva: la lectura del informe,
y **el arrastre de las métricas ya guardadas** (`metricas_previas`). Sin lo segundo la TIR del
último informe se seguiría publicando para siempre.

**Costo medido** (968 especies, corrida #113): las emisiones con rendimiento bajan de 283 a 248
—se pierden 4 hard-dollar sin especie en dólares, 19 dollar-linked y 12 tamar—, y la convexidad y
el valor residual quedan vacías. Las otras 182 especies que tomaban su TIR de IAMC tienen una
hermana en dólares que sí se calcula. **No se pierden** ley, moneda de pago, emisor ni estructura
de cupón: el upsert los protege con COALESCE y son atributos de la emisión, que no envejecen.

**Cómo se retoma:** F-055 (descarga automática). Prender `IAMC_HABILITADO=true` alcanza para volver
al comportamiento anterior, pero eso solo devolvería también el problema del dato viejo.

**Descripción.** Extracción estructurada del informe diario de deuda corporativa de IAMC (PDF,
~260 ONs). Aporta lo que BYMA no tiene: emisor con nombre completo, ley y moneda de pago, estructura
del cupón, tasa, frecuencia, próximo cupón, próximo pago de capital, valor residual, paridad, valor
técnico, TIR, duración modificada, convexidad, vida promedio y volumen medio de 20 ruedas. **Ley y
moneda de pago se leen del título de la sección del informe, no de una columna inferida** — esa
distinción es la que evita repetir el episodio de "Ley Inglesa". Si el layout del PDF cambia y una
sección no se reconoce, el parser falla ruidosamente en vez de producir filas parciales.

**Input:** informe diario de IAMC del día.
**Output:** atributos del instrumento por raíz de ticker, con la ley y la moneda de pago trazadas a
la sección de la que salieron.
**Depende de:** F-001
**Habilita:** F-007, F-031

**RICE:** R = 400 · I = 2 · C = 50 % · E = 8 → **Score 50**
*Confidence 50 %: el parsing del PDF no está verificado en los inputs; el contenido del informe sí. Es
el score más bajo de todo el Ciclo 1, y aun así la feature es obligatoria: es la única fuente de
emisor, ley y moneda de pago. El RICE mide eficiencia, no necesidad.*

```
GIVEN un informe de IAMC con sus secciones por ley y moneda de pago
WHEN se lo parsea
THEN cada ON hereda la ley y la moneda de pago del título de su sección, y el parser registra de qué
     sección salió cada valor

GIVEN un informe cuyo layout cambió y tiene una sección no reconocida
WHEN se lo parsea
THEN el parser aborta con el detalle de la sección no reconocida, y no persiste filas parciales

GIVEN un campo numérico ausente para una ON del informe
WHEN se lo normaliza
THEN queda vacío y se contabiliza en la cobertura del campo, y no se completa por inferencia ni por
     el valor del día anterior
```

---

#### F-006 — Cliente del feed de cashflow de Docta

**Etiqueta:** Stage 1 · **Traza a:** F1 (hueco de datos declarado, DECIDIDO 05/08/2026)
**Estado: DADA DE BAJA el 12/08/2026 — la fuente es paga y el dueño del producto decidió no
pagarla.** El código del cliente, la ingesta, el endpoint y las variables de entorno se borraron.
El cronograma que Docta ya había traído **queda persistido en `public.cashflow` y se sigue usando**:
`corrida.py` lo lee en cada pasada, así que el calendario de doce meses, la clasificación por tipo
de tasa y las métricas propias de F-051 siguen funcionando igual. Lo que se perdió es la
actualización: una emisión que empiece a cotizar de ahora en más entra sin cronograma y se declara
faltante, nunca clasificada por analogía (regla 1). **Reponer una fuente de cronogramas es trabajo
pendiente** — R1 de la sección de riesgos se materializó por decisión, no por falla.
La ficha original queda abajo como registro de lo que se construyó.

**Descripción.** Único consumo de Docta que queda en el producto: el cronograma completo de pagos
futuros por ticker desde `/api/cash-flow`, con 97 % de cobertura de las emisiones. Es el corazón del
producto: sin el calendario completo, F-015 se degrada a "el próximo pago de cada bono" y la grilla
de doce meses deja de existir. El cliente maneja las trampas conocidas del feed: **HTTP 500 "Error al
verificar el token" significa token vencido y se regenera desde Docta Terminal**, mientras que un
timeout o un 5xx distinto significa API caída — son dos alertas separadas porque la acción que
requieren es distinta. Cero filas erráticas se resuelven con hasta 5 reintentos con espera creciente,
y la ventana `fromDate` es móvil, no hardcodeada.

**Input:** endpoint tokenizado de Docta; token desde `.env`.
**Output:** cronograma completo de pagos por ticker, separando interés de capital.
**Depende de:** F-001
**Habilita:** F-007, F-015, F-040

**RICE:** R = 400 · I = 3 · C = 80 % · E = 4 → **Score 240**

```
GIVEN el feed de Docta respondiendo HTTP 500 con "Error al verificar el token"
WHEN corre la ingesta
THEN se emite la alerta "token vencido — regenerar desde Docta Terminal", distinta de la alerta de
     API caída, y la ingesta conserva el último cashflow válido

GIVEN el feed de Docta con timeout o un 5xx que no es el de token
WHEN corre la ingesta
THEN se emite la alerta "API de cashflow no disponible", distinta de la de token vencido

GIVEN una respuesta con cero filas de forma errática
WHEN corre la ingesta
THEN reintenta hasta 5 veces con espera creciente antes de declarar el fallo

GIVEN una ventana temporal de consulta
WHEN se arma el request
THEN fromDate se calcula relativo a la fecha de corrida, y no hay ninguna fecha hardcodeada
```

---

#### F-007 — Consolidador multi-fuente con precedencia por campo

**Etiqueta:** Stage 1 · **Traza a:** F1

**Descripción.** Une las tres fuentes en la única base de mercado del producto, **por la raíz del
ticker**, porque ley, moneda de pago y estructura son atributos de la emisión y no de la especie. La
precedencia está declarada campo por campo y es la decisión del 05/08/2026: **BYMA** aporta precios,
puntas, volumen, moneda de cotización, especies y plazos de liquidación; **IAMC** aporta emisor, ley,
moneda de pago, estructura, TIR, duración, convexidad y próximos pagos; **Docta** aporta únicamente
el cronograma completo. Ningún campo se completa desde una fuente que no es la declarada para ese
campo. Reemplaza a `consolidar_universo.py`, conservando su contrato de salida.

**Input:** salidas de F-004, F-005 y F-006.
**Output:** tablas `instrumentos`, `precios`, `puntas`, `cashflow` pobladas, con `fuente` por campo y
métricas de cobertura por campo.
**Depende de:** F-002, F-004, F-005, F-006
**Habilita:** F-008, F-009, F-010, F-013

**RICE:** R = 400 · I = 3 · C = 80 % · E = 6 → **Score 160**

```
GIVEN un bono presente en BYMA con sus tres especies y en IAMC con su raíz
WHEN se consolida
THEN las tres especies heredan ley, moneda de pago y estructura de la raíz, y cada una conserva su
     propio precio, punta y moneda de cotización

GIVEN un instrumento presente en BYMA pero ausente del informe de IAMC
WHEN se consolida
THEN queda en el universo con precio y punta, con ley y moneda de pago vacías, y suma al contador
     de cobertura faltante del campo

GIVEN la TIR presente tanto en IAMC como calculable desde otra fuente
WHEN se consolida
THEN se persiste la de IAMC por precedencia declarada, y el campo fuente lo registra

GIVEN el universo consolidado
WHEN se compara su esquema contra el contrato del Resumen anterior
THEN los consumidores del universo (segmentos.py, cupones.py, mercado.py) leen sin modificación
```

---

#### F-008 — Job programado de ingesta y refresh de rueda

**Etiqueta:** Stage 1 · **Traza a:** F1

**Descripción.** Orquestación temporal del pipeline: una corrida completa a la mañana (BYMA + IAMC +
Docta + consolidación + integridad) y refrescos de precios y puntas durante la rueda, que sólo tocan
BYMA porque IAMC es diario y el cashflow no cambia intradiario. Cada corrida deja un registro
auditable —hora de inicio, duración, filas por fuente, alertas emitidas— que alimenta la barra de
estado del dato. Si una fuente falla, la corrida no se aborta entera: se persiste lo que sí llegó y
se declara lo que no.

**Input:** F-004, F-005, F-006, F-007 como pasos orquestados.
**Output:** snapshots de mercado con periodicidad; historial de corridas.
**Depende de:** F-007
**Habilita:** F-013

**RICE:** R = 400 · I = 2 · C = 100 % · E = 3 → **Score 266,7**

```
GIVEN la corrida matinal programada
WHEN se ejecuta
THEN corre las tres fuentes, la consolidación y la capa de integridad en ese orden, y registra la
     corrida con hora, duración y filas por fuente

GIVEN un refresh intra-rueda
WHEN se ejecuta
THEN actualiza precios y puntas desde BYMA sin volver a consultar IAMC ni Docta

GIVEN una corrida en la que IAMC falla y BYMA responde
WHEN termina
THEN los precios quedan actualizados, los atributos de instrumento conservan el último valor válido
     con su fecha, y la corrida se marca como parcial con el detalle de la fuente caída
```

---

#### F-009 — `condiciones_emision`: semilla, herencia entre especies y conflictos

**Etiqueta:** Stage 1 · **Traza a:** F1 + F7 (resolución de la cuestión abierta N.º 2)

**Descripción.** La tabla que aloja el dato curado del producto: ley, moneda de pago, lámina,
calificación, sector y emisor, con `origen` y `fecha` en cada valor. Se siembra migrando
`condiciones_estaticas.csv` (272 tickers) y `condiciones_monitor.csv` (526 tickers), cada valor con
su origen declarado, y el `data/condiciones_emision.csv` curado de 823 tickers que el proyecto trata
como irrecuperable. Implementa la **herencia entre especies** —si AL30 tiene la lámina, AL30D y AL30C
la tienen— y la **detección de conflictos**: si dos especies de la misma emisión declaran valores
distintos, no se elige fuente por cuenta propia, se vacían las dos y se reporta. Reemplaza a
`merge_condiciones.py` y `aplicar_sectores.py` conservando su lógica.

**Input:** los CSV de semilla; el universo consolidado de F-007.
**Output:** `condiciones_emision` poblada y consultable, cobertura por campo, y lista de conflictos.
**Depende de:** F-002, F-007
**Habilita:** F-013, F-020, F-024, F-025, F-031, F-039

**RICE:** R = 400 · I = 2 · C = 100 % · E = 4 → **Score 200**

```
GIVEN AL30 con lámina informada y AL30D y AL30C sin ella
WHEN corre la herencia entre especies
THEN AL30D y AL30C quedan con la lámina de AL30 y con origen "herencia de AL30"

GIVEN dos especies de la misma emisión que declaran láminas distintas
WHEN corre la detección de conflictos
THEN las dos quedan vacías, el conflicto se reporta con los dos valores en pugna, y el sistema no
     elige ninguno

GIVEN los CSV de semilla migrados
WHEN se consulta la cobertura de lámina
THEN el conteo reportado se corresponde con los valores efectivamente cargados y su origen, sin
     ninguna fila completada por inferencia
```

---

### Bloque C — Capa de integridad del dato (F2)

---

#### F-010 — Sanidad del dato en dos capas

**Etiqueta:** Stage 1 · **Traza a:** F2

**Descripción.** Envuelve como servicio la lógica ya verificada de `segmentos.py`. **Primera capa,
coherencia entre especies del mismo bono:** un bono tiene UNA TIR, y cuando una especie se despega de
las otras por más de 100 pp, esa especie tiene el precio mal escalado — VSCQD figuraba con
34.627.917 % mientras VSCQO, el mismo bono, rendía 6,75 %. **Segunda capa, techo de lo posible por
segmento y en la unidad de cada segmento:** hard-dollar y dólar-linked 300 %, CER 100 % de tasa
*real*, tasa fija/Badlar/Tamar 500 % de TNA *nominal*. Los topes son holgados a propósito: SNSBO
rinde 245 % en dólares y es dato **correcto** —bono a 80 días cotizando al 78 % de su valor técnico—
y un umbral ajustado lo mataría junto con la basura. Cada descarte se registra con su motivo.

**Input:** universo consolidado de F-007, con su segmentación.
**Output:** universo saneado; lista de descartados con ticker, motivo y valor que disparó el descarte.
**Depende de:** F-007
**Habilita:** F-011, F-012, F-013, F-015, F-038

**RICE:** R = 400 · I = 3 · C = 100 % · E = 3 → **Score 400**

```
GIVEN VSCQD con TIR de 34.627.917 % y VSCQO del mismo bono con 6,75 %
WHEN corre la coherencia entre especies
THEN VSCQD se descarta por despegue mayor a 100 pp, VSCQO se conserva, y el descarte queda listado
     con su motivo

GIVEN SNSBO con 245 % de TIR en dólares, bono a 80 días al 78 % de su valor técnico
WHEN corre el techo por segmento
THEN SNSBO NO se descarta, porque el tope de hard-dollar es 300 %

GIVEN un instrumento CER con tasa real de 150 %
WHEN corre el techo por segmento
THEN se descarta contra el tope de 100 % de tasa real, y no contra el de 300 % de hard-dollar

GIVEN un instrumento de tasa fija con TNA nominal de 480 %
WHEN corre el techo por segmento
THEN se conserva, porque el tope de TNA nominal es 500 %
```

---

#### F-011 — Deduplicación de especies de liquidación

**Etiqueta:** Stage 1 · **Traza a:** F2

**Descripción.** MR46O, MR46D y MR46C son el mismo bono: comprar dos es comprar el mismo bono creyendo
que se diversifica. La deduplicación **no es un descarte, es una doble vista**: las especies se
colapsan a una fila por emisión para el armador y para el cómputo de concentración, y se conservan
vivas e individuales para el optimizador, porque los swaps de perfil rotan justamente entre especies
de la misma emisión (MEP → Cable). El servicio expone las dos vistas del mismo universo con la clave
de emisión explícita en ambas.

**Input:** universo saneado de F-010.
**Output:** vista colapsada por emisión y vista viva por especie, ambas con clave de emisión.
**Depende de:** F-010
**Habilita:** F-015, F-020, F-032, F-039

**RICE:** R = 400 · I = 2 · C = 100 % · E = 2 → **Score 400**

```
GIVEN MR46O, MR46D y MR46C en el universo
WHEN se pide la vista colapsada del armador
THEN aparece una sola fila para la emisión MR46, con la clave de emisión explícita

GIVEN las mismas tres especies
WHEN se pide la vista viva del optimizador
THEN aparecen las tres filas individuales, cada una con su precio, su punta y su moneda de cotización

GIVEN una cartera que ya tiene MR46D
WHEN el asesor intenta agregar MR46C desde el armador
THEN el sistema advierte que es la misma emisión y que no suma diversificación
```

---

#### F-012 — Tipo de cambio implícito, normalización de volumen y contraste

**Etiqueta:** Stage 1 · **Traza a:** F2 (resolución de la cuestión abierta N.º 3)

**Descripción.** El tipo de cambio **se deriva del propio universo, nunca de una fuente externa**: la
misma emisión cotiza en pesos y en dólares, y ese cociente es el tipo de cambio al que opera el
mercado. Se toma la mediana sobre todas las emisiones que cotizan en las dos puntas, con **mínimo de
20 pares**; con menos, no se normaliza y se declara. Se usa la especie D (MEP) como referencia y sólo
se cae a la C (Cable) si no hay MEP, porque los separa el canje (~3,5 %) y mezclarlos ensuciaría la
mediana. Con ese tipo de cambio se normaliza `volume`/`volumeAmount` a dólares antes de comparar
liquidez: la especie en pesos de un bono muestra ~1.500× más volumen que su especie en dólares por el
tipo de cambio, no por operarse más. El `index-price` de BYMA entra como **control de contraste, no
como fuente**: si el implícito difiere del índice publicado más allá del umbral, sale alerta.

**Input:** universo saneado de F-010; `index-price` de F-004.
**Output:** tipo de cambio implícito con su cantidad de pares y su dispersión; volumen normalizado a
dólares; alerta de contraste.
**Depende de:** F-010
**Habilita:** F-013, F-031, F-038

**RICE:** R = 400 · I = 2 · C = 100 % · E = 3 → **Score 266,7**

```
GIVEN un universo con al menos 20 emisiones que cotizan en pesos y en MEP
WHEN se calcula el tipo de cambio implícito
THEN se toma la mediana de los cocientes usando la especie D, y se reporta la cantidad de pares y la
     dispersión intercuartil

GIVEN un universo con menos de 20 pares disponibles
WHEN se calcula el tipo de cambio
THEN no se normaliza nada, y la barra de estado del dato declara que la comparación entre monedas no
     está disponible

GIVEN una emisión sin especie D pero con especie C
WHEN se arma la muestra de pares
THEN se usa la C sólo para esa emisión, y el hecho queda registrado, porque MEP y Cable son tipos de
     cambio distintos

GIVEN el implícito derivado y el índice publicado en index-price
WHEN difieren más allá del umbral configurado
THEN se emite alerta de contraste, y el implícito se conserva como fuente

GIVEN un bono con especie en pesos y especie en dólares
WHEN se comparan sus volúmenes
THEN los dos están expresados en dólares antes de la comparación
```

---

#### F-013 — Barra de estado del dato

**Etiqueta:** Stage 1 · **Traza a:** F2

**Descripción.** No es infraestructura: es una feature de producto, porque su salida es visible en
pantalla y es la que hace que la regla "cuando falta un dato, lo dice" deje de ser decorativa. Franja
global y siempre visible, transversal a las seis pantallas, con: hora del último refresh, **demora
declarada de la fuente (BYMA abierta tiene 20 minutos)**, cantidad de instrumentos descartados por
sanidad con el detalle desplegable, cobertura de cada campo crítico, alertas de token vencido versus
API caída, y la alerta de contraste del tipo de cambio. La lista de alertas que hoy se acumula en una
hoja "Alertas" del Excel pasa acá como array estructurado; el contenido no cambia.

**Input:** registro de corridas de F-008, descartes de F-010, cobertura de F-007 y F-009, alertas de
F-006 y F-012.
**Output:** componente global de UI y endpoint que lo alimenta.
**Depende de:** F-003, F-008, F-009, F-010, F-012
**Habilita:** F-016, F-030, F-038

**RICE:** R = 400 · I = 2 · C = 100 % · E = 4 → **Score 200**

```
GIVEN cualquier pantalla de la aplicación
WHEN se la abre
THEN la barra de estado del dato está visible, sin necesidad de navegar a ninguna parte

GIVEN un snapshot de BYMA de las 11:00
WHEN se lo muestra a las 11:15
THEN la barra declara la hora del snapshot y la demora de 20 minutos de la fuente, no la hora actual
     como si fuera el dato

GIVEN 14 instrumentos descartados por sanidad en la última corrida
WHEN el asesor despliega el detalle
THEN ve los 14 tickers con el motivo de descarte y el valor que lo disparó

GIVEN el token de Docta vencido
WHEN se abre cualquier pantalla
THEN la barra muestra la alerta de token vencido con su acción, distinguida de una caída de API
```

---

#### F-051 — Métricas propias: TIR, duración y paridad calculadas

**Etiqueta:** Stage 1 · **Traza a:** F2 (agregada 08/2026, tras auditar cómo resuelve esto el
monitor de mesa: calcula en el cliente con precio en vivo + flujos curados a mano; acá los dos
insumos ya están en la base, de fuentes vivas)

**Descripción.** Hoy `tir`, `duration` y `paridad` se **ingieren** del informe de IAMC, ticker
exacto: ~234 ONs publicadas sobre ~2.180 en el universo, y las especies D y C siempre vacías porque
IAMC nombra una sola especie por emisión. El faltante no es de insumos: el precio por especie ya
llega de BYMA (F-004) y el cronograma contractual completo de Docta (F-006), y la matemática de
paridad/valor técnico/flujos por peso ya está portada y verificada en `cupones.py`. Esta feature
cierra la cuenta: **TIR, duración modificada y paridad calculadas por especie** —cada especie
contra su propio precio, en la moneda de ese precio, vía paridad y sin tipo de cambio— para toda
emisión con cronograma. Es determinístico (regla 6) y no inventa nada (regla 1): sin precio operado
o sin cronograma, el campo queda vacío y la especie nombrada en la alerta de cobertura. Cada
segmento se calcula en su propia unidad (regla 2); si el flujo disponible no permite la unidad del
segmento, esas especies quedan fuera del cálculo y alertadas — jamás se les reporta una tasa de otra
naturaleza. **IAMC pasa de fuente a contraste**, el mismo patrón que F-012 aplica al Índice Dólar
de BYMA: donde ambos existen, una divergencia sobre el umbral emite alerta y el cálculo propio se
conserva como dato. La tabla de precedencia de `armado.py` cambia: estas tres columnas pasan de
"IAMC, ticker exacto" a "cálculo propio, especie".

**El cálculo exige que el precio y el flujo estén en la misma moneda** (decisión del 08/08/2026, al
diseñar la feature). Descontar un flujo en dólares contra un precio en pesos requeriría un tipo de
cambio, y derivarlo de la propia emisión —el MEP de F-012— equivale a copiar la TIR de la especie
hermana, que la regla 1 prohíbe. Por eso AL30D y AL30C se calculan y AL30 no; para las especies en
pesos de emisiones en dólares **IAMC sigue siendo fuente donde publica**, y donde no publica el
campo queda vacío y la especie nombrada. Es un híbrido declarado por especie, no una excepción
silenciosa: la fuente de cada fila viaja en la columna `fuente`.

**Input:** precio por especie de F-004; cronograma de F-006; métricas publicadas de F-005 como
contraste. (No consume el universo saneado de F-010: ese se lee de la vista `resumen`, que es la
salida de esta misma consolidación — F-051 corre adentro del armado, sobre las filas de BYMA y el
cronograma de Docta.)
**Output:** `tir`, `duration` y `paridad` calculadas por especie; cobertura y alertas de faltantes;
alerta de contraste contra IAMC.
**Depende de:** F-006, F-010
**Habilita:** F-040 (le deja escrita la matemática de descuento) y multiplica la cobertura que ya
consumen F-016, F-021, F-030, F-038 y F-039 sin cambiarles el contrato

**RICE:** R = 400 · I = 2 · C = 80 % · E = 4 → **Score 160,0**

```
GIVEN una especie cuyo precio del día está en la misma moneda que el flujo de su cronograma
WHEN corre la consolidación
THEN tir, duración y paridad salen del cálculo propio sobre el flujo contractual, por especie —
     AL30D contra su precio en dólares y AL30C contra el suyo, sin pasar por un tipo de cambio

GIVEN una especie cuyo precio está en otra moneda que su flujo (AL30 en pesos, flujo en dólares)
WHEN corre el cálculo
THEN no se calcula ni se deriva de la hermana; queda con la métrica de IAMC si IAMC la publica, y
     vacía y nombrada en la alerta si no

GIVEN una especie que no operó hoy o una emisión sin cronograma
WHEN corre el cálculo
THEN el campo queda vacío y la especie aparece nombrada en la alerta de cobertura; no se estima ni
     se copia de otra especie de la misma emisión

GIVEN un ticker que IAMC también publica
WHEN la métrica propia difiere de la publicada más allá del umbral configurado
THEN se emite alerta de contraste y el cálculo propio se conserva como dato

GIVEN un segmento cuya naturaleza de tasa no puede calcularse con el flujo disponible
WHEN corre el cálculo
THEN esas especies quedan fuera, alertadas, y nunca se les reporta una tasa de otra naturaleza
```

---

### Bloque D — Autenticación (F3)

---

#### F-014 — Autenticación por invitación y aislamiento por asesor

**Etiqueta:** Stage 1 · **Traza a:** F3

**Descripción.** Login con Supabase Auth, email y contraseña, **por invitación y sin registro
abierto**. Cada asesor ve exclusivamente sus propias carteras, y ese aislamiento se aplica con Row
Level Security en PostgreSQL, **no con filtros del lado del cliente**. La base de mercado, en cambio,
es compartida y única: el universo, los precios y las condiciones de emisión son los mismos para
todos, y también lo es la lámina que un asesor carga a mano. Incluye guard de rutas en el frontend,
manejo de sesión y expiración.

**Input:** esquema con `user_id` y RLS de F-002.
**Output:** sesión autenticada; contexto de usuario en backend y frontend; aislamiento verificable.
**Depende de:** F-002, F-003
**Habilita:** F-018, F-041

**RICE:** R = 400 · I = 2 · C = 100 % · E = 4 → **Score 200**

```
GIVEN un visitante sin invitación
WHEN intenta registrarse
THEN no existe formulario de registro abierto y el acceso es denegado

GIVEN el asesor A con una cartera guardada y el asesor B autenticado
WHEN B consulta la API de carteras directamente, salteando el frontend
THEN no recibe la cartera de A, porque la restricción es de RLS y no de filtro de cliente

GIVEN un asesor autenticado
WHEN consulta el universo de mercado
THEN ve exactamente los mismos instrumentos, precios y condiciones que cualquier otro asesor

GIVEN una sesión expirada
WHEN se intenta una operación
THEN se redirige al login sin perder silenciosamente el trabajo en curso
```

---

### Bloque E — Calendario-selector (F4)

---

#### F-015 — API del calendario de doce meses

**Etiqueta:** Stage 1 · **Traza a:** F4

**Descripción.** Servicio que convierte el cronograma completo de pagos en la grilla de doce meses:
por cada mes, los instrumentos que pagan, cuánto pagan, su TIR y su vencimiento. **Amortización y
renta se distinguen y no se suman**: cobrar amortización no es renta, y el motor ya lo separa con
`pct_interes` y `pct_capital`. Los meses sin pagos devuelven cero explícito, no ausencia — un cero
vale más que una celda faltante cuando lo que se evalúa es la continuidad del ingreso. Es envoltura
de `cupones.py`, cuya matemática reproduce exacto los nominales de RUCED, SBC2D, CS47D y LOC5D
contra el Excel real de la mesa.

**Input:** cashflow de F-006 vía F-007; universo saneado y colapsado de F-010 y F-011.
**Output:** estructura de doce meses con instrumentos, monto de renta, monto de amortización, TIR y
vencimiento por instrumento.
**Depende de:** F-006, F-010, F-011
**Habilita:** F-016, F-021, F-036

**RICE:** R = 380 · I = 3 · C = 100 % · E = 4 → **Score 285**

```
GIVEN un bono que paga cupón en marzo y septiembre
WHEN se pide el calendario de doce meses
THEN el bono aparece en marzo y en septiembre, con el mismo identificador de emisión en las dos

GIVEN un mes en el que ningún instrumento del universo filtrado paga
WHEN se pide el calendario
THEN ese mes viene presente con valor cero, no ausente

GIVEN un bono amortizing que en un mes paga interés y capital
WHEN se pide el calendario
THEN el monto de renta y el de amortización vienen en campos separados, y el total de renta del mes
     no incluye la amortización

GIVEN las posiciones de RUCED, SBC2D, CS47D y LOC5D del Excel real de la mesa
WHEN se calculan sus nominales con la matemática de cupones
THEN los cuatro reproducen exacto los del Excel
```

---

#### F-016 — Grilla-selector de doce meses

**Etiqueta:** Stage 1 · **Traza a:** F4 — **la feature central: sin esta mecánica el producto no existe**

**Descripción.** La pantalla que invierte el producto: el calendario es la entrada, no la salida.
Grilla de doce tarjetas, una por mes. Cada tarjeta lista los papeles que pagan renta ese mes con
ticker, moneda de liquidación, cuánto paga de cupón, TIR y año de vencimiento — los tres criterios de
selección, en orden: TIR, cupón, frecuencia. Al hacer clic, el papel entra a la cartera y **se ilumina
simultáneamente en todos los meses en que paga**, así la cobertura del año se lee de un vistazo. Los
meses sin cobertura quedan visualmente marcados. Trabaja sobre la vista colapsada: un papel, una
emisión.

**Input:** calendario de F-015; selección actual de la cartera de F-018.
**Output:** selección de posiciones que alimenta la cartera; estado visual de cobertura del año.
**Depende de:** F-013, F-015
**Habilita:** F-017, F-018

**RICE:** R = 380 · I = 3 · C = 80 % · E = 8 → **Score 114**

```
GIVEN la grilla de doce meses cargada
WHEN el asesor hace clic en un papel que paga en marzo, julio y noviembre
THEN el papel entra a la cartera y queda iluminado en las tres tarjetas simultáneamente

GIVEN un papel ya seleccionado
WHEN el asesor vuelve a hacer clic sobre él en cualquiera de sus meses
THEN sale de la cartera y se apaga en todos los meses a la vez

GIVEN una cartera en la que ningún papel paga en febrero
WHEN se mira la grilla
THEN la tarjeta de febrero está marcada como mes sin cobertura de forma visualmente distinguible

GIVEN un papel listado en una tarjeta
WHEN se lee su renglón
THEN muestra ticker, moneda de liquidación, monto del cupón, TIR y año de vencimiento en una sola
     línea
```

---

#### F-017 — Filtros de la grilla

**Etiqueta:** Stage 1 · **Traza a:** F4

**Descripción.** Barra de filtros sobre la grilla de doce meses: segmento, horizonte de duración,
percentil de liquidez, sector, emisor, ley y frecuencia de cupón. El filtro de segmento es especial:
**se trabaja un segmento por vez, o con la unidad declarada por columna** — no hay estado en el que la
grilla mezcle una TIR en dólares con una TNA nominal sin decir cuál es cuál. Los filtros son siempre
visibles, tienen botón de limpiar, y el conteo de instrumentos que sobreviven al filtro está a la
vista.

**Input:** universo filtrable de F-010; percentiles de liquidez normalizada de F-012; sector, emisor y
ley de F-009.
**Output:** subconjunto del universo que alimenta la grilla.
**Depende de:** F-016
**Habilita:** F-019

**RICE:** R = 350 · I = 2 · C = 80 % · E = 5 → **Score 112**

```
GIVEN la grilla sin filtro de segmento
WHEN se la muestra
THEN cada columna de rendimiento declara su unidad, o bien la grilla exige elegir un segmento antes
     de mostrar rendimientos

GIVEN el filtro de segmento en CER
WHEN se leen los rendimientos de la grilla
THEN todos están expresados como tasa real, con la unidad declarada en el encabezado

GIVEN filtros de duración, liquidez y sector aplicados simultáneamente
WHEN se los aplica
THEN el conteo de instrumentos resultantes está visible, y el botón de limpiar los quita todos de
     una vez

GIVEN un filtro por ley
WHEN hay instrumentos sin ley informada
THEN quedan agrupados como "ley no informada" y no se los asigna a ninguna de las dos leyes
```

---

### Bloque F — Cartera editable (F5)

---

#### F-018 — Cartera editable y ponderación

**Etiqueta:** Stage 1 · **Traza a:** F5

**Descripción.** El panel donde vive la cartera en construcción. Tabla editable con una fila por
posición: ticker, emisor, sector, precio, monto, ponderación deseada, lámina, valor nominal asignado,
porcentaje real y meses en que paga. Se edita el peso por porcentaje o por monto, se quita, se
reordena. Botones de equiponderar y vaciar. Muestra el total acumulado de ponderación y el invertido
real al lado, **porque no coinciden**. Es el estado central del Flujo A: el calendario selecciona,
pero sin ponderación editable no hay cartera. Los FCI se cargan acá como línea con peso y sin precio:
CAFCI publica el valor de cuotaparte y desde el 13/08/2026 esa fuente está verificada (F-057), pero
**valuarlos dentro de una cartera es F-046** y necesita además composición del fondo y un tipo de
cambio propio, que todavía no hay. Hasta entonces, la línea sigue sin precio en Stage 1.

**Input:** selecciones de F-016; precios del universo.
**Output:** cartera en construcción, que es el input de F-020, F-021, F-022, F-023, F-024, F-041.
**Depende de:** F-014, F-016
**Habilita:** F-019, F-020, F-021, F-024, F-026, F-041

**RICE:** R = 350 · I = 3 · C = 80 % · E = 6 → **Score 140**

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

---

#### F-019 — Armado asistido

**Etiqueta:** Stage 1 · **Traza a:** F5

**Descripción.** Botón que precarga una cartera de arranque a partir de monto, moneda de referencia,
objetivo de cobertura (devaluación / inflación / tasa en pesos / mixta), perfil (conservador /
moderado / agresivo) y horizonte (corto / medio / largo). El asesor la toma como punto de partida y
la edita a mano sobre el calendario — no es un resultado final. Es envoltura de las funciones ya
escritas y verificadas de `armar_cartera.py`: `resolver_mix`, `candidatos_del_segmento`,
`elegir_siguiente` y `armar`, con 15 casos de regresión. Lo que se descarta es la cáscara: `main()`
con argparse y `exportar_excel()` con openpyxl; los flags de CLI pasan a ser un modelo Pydantic.

El armado no solo respeta los topes: **reparte**. `resolver_mix` ya distribuye por naturaleza de
tasa según el objetivo de cobertura; se suma un criterio determinístico de reparto sectorial:
entre candidatos comparables, `elegir_siguiente` prefiere el de un sector aún no representado en
la cartera, y cada perfil declara un **mínimo de sectores distintos** (el parámetro
`min_sectores` de `PERFILES`, definido en F-020 y calibrado contra el universo real — el tramo
hard-dollar tiene a O&G con ~40 % de las ONs y un mínimo demasiado exigente dejaría sin
candidatos). Si el universo no alcanza para cumplir el mínimo, la cartera sale igual y **se
declara qué quedó concentrado y por qué** — nunca se rellena con instrumentos de otra naturaleza
ni se inventa diversificación.

**Input:** parámetros de la cartera; universo filtrado de F-017; `min_sectores` de F-020.
**Output:** cartera de arranque cargada en el panel editable de F-018.
**Depende de:** F-017, F-018, F-020
**Habilita:** —

**RICE:** R = 250 · I = 2 · C = 100 % · E = 6 → **Score 83,3**

```
GIVEN los parámetros monto, moneda de referencia, objetivo, perfil y horizonte
WHEN el asesor pide armado asistido
THEN se precarga una cartera en el panel editable, editable posición por posición como cualquier otra

GIVEN los 15 casos de regresión de armar_cartera.py
WHEN se corren contra el servicio envuelto
THEN los 15 producen el mismo resultado que la versión de línea de comandos

GIVEN un objetivo de cobertura para el que no hay candidatos suficientes en el universo
WHEN se pide el armado asistido
THEN el sistema devuelve la cartera parcial y declara qué parte del objetivo no pudo cubrir, sin
     rellenar con instrumentos de otra naturaleza

GIVEN un perfil con min_sectores = 4 y un universo con candidatos comparables de 6 sectores
WHEN se pide el armado asistido
THEN la cartera resultante contiene posiciones de al menos 4 sectores distintos, sin contar
     Soberano ni Subsoberano, que ya los acota el tope soberano

GIVEN un objetivo de cobertura cuyo universo elegible tiene un solo sector corporativo
WHEN se pide el armado asistido
THEN la cartera sale con ese sector y una advertencia que nombra el mínimo incumplido y la
     causa, sin bloquear ni rellenar
```

---

#### F-020 — Límites de concentración en vivo

**Etiqueta:** Stage 1 · **Traza a:** F5

**Descripción.** Los topes se muestran y se advierten con cada cambio de la cartera, con el criterio
ya calibrado en `verificar_concentracion`: tope por emisor corporativo, **tope separado para el riesgo
soberano** y tope por sector, con Soberano y Subsoberano exentos del tope sectorial porque ya los
acota el tope soberano. El Tesoro emite bajo muchos prefijos —GD, AE, DIC, TZX, TY3— y todos son el
mismo crédito: se agrupan bajo la clave única **`SOBERANO_AR`**. Sin esta separación, una cartera
100 % soberana pasaba como diversificada. La advertencia no bloquea: informa.

Junto a los topes se muestra la **distribución** de la cartera en tres cortes: por sector, por
legislación (ley N.Y. / ley Argentina, el proxy de país en renta fija) y por naturaleza de tasa.
Cuando la cartera queda por debajo del mínimo de sectores del perfil se advierte igual que con un
tope excedido: **informa, no bloquea**. Las posiciones sin sector figuran como "sector no
informado", nunca repartidas entre los conocidos.

**Input:** cartera de F-018; clave de riesgo y sector del universo; ley de F-009; naturaleza de
tasa de la segmentación; vista colapsada de F-011.
**Output:** estado de cumplimiento por tope, distribución por sector / ley / naturaleza de tasa y
advertencias en vivo. Define `min_sectores` en `PERFILES`; F-019 lo reusa en la selección.
**Depende de:** F-009, F-011, F-018
**Habilita:** F-019, F-031

**RICE:** R = 350 · I = 2 · C = 100 % · E = 4 → **Score 175**

```
GIVEN una cartera con GD30, AE38 y TZX26
WHEN se calcula la concentración
THEN los tres se agrupan bajo la clave SOBERANO_AR y se miden contra el tope soberano, no contra el
     tope por emisor corporativo

GIVEN una cartera 100 % soberana
WHEN se calcula la concentración
THEN se advierte el exceso del tope soberano, y en ningún caso figura como diversificada

GIVEN una cartera con exceso de un emisor corporativo
WHEN se supera el tope
THEN se advierte nombrando el emisor y el exceso, y la posición se puede dejar igual

GIVEN una cartera con posiciones de clase Soberano y Subsoberano
WHEN se calcula el tope por sector
THEN esas posiciones quedan exentas del tope sectorial

GIVEN una cartera dentro de todos los topes pero con solo 2 sectores en perfil moderado
WHEN se evalúan los límites en vivo
THEN se advierte que la cartera está por debajo del mínimo de sectores del perfil, nombrando
     los sectores presentes y su peso

GIVEN posiciones sin sector informado
WHEN se muestra la distribución por sector
THEN aparecen agrupadas como "sector no informado" con su porcentaje
```

---

### Bloque G — Panel de renta y métricas (F6)

---

#### F-021 — Panel de renta mensual y renta anual sobre lo invertido

**Etiqueta:** Stage 1 · **Traza a:** F6

**Descripción.** El feedback en vivo que convierte al calendario en selector y no en consulta. Renta
mes a mes **en plata real** según el nominal asignado —no en porcentaje, no cada 100 de valor
nominal—, el total anual, y destacado el **total anual de cupones sobre lo invertido**, con la cuenta
a la vista. Ese número es el que el asesor le dice al cliente: es el ingreso por cupones, separado de
cualquier ganancia de capital, que es incierta. Los totales se expresan en la moneda de referencia
declarada de la cartera y **también desagregados por moneda de cobro**, porque un cupón en pesos y uno
en dólares no son el mismo peso hasta que se declara el tipo de cambio usado. Incluye meses sin
cobertura, mes más flaco y mes más fuerte.

**Input:** cartera de F-018; calendario de F-015; tipo de cambio de F-012.
**Output:** renta mensual, total anual, ratio sobre lo invertido, desagregación por moneda de cobro.
**Depende de:** F-015, F-018
**Habilita:** F-030, F-036

**RICE:** R = 380 · I = 3 · C = 100 % · E = 4 → **Score 285**

```
GIVEN una cartera con nominales asignados
WHEN se muestra el panel de renta
THEN cada mes muestra el monto en plata real que el cliente va a cobrar, no un porcentaje ni un
     monto cada 100 de valor nominal

GIVEN una cartera de US$ 99.999,11 invertidos que cobra US$ 7.173,92 de cupones en el año
WHEN se muestra la renta anual sobre lo invertido
THEN muestra 7,17 % con la cuenta visible: sólo cupones, monto de cupones sobre monto invertido

GIVEN una cartera con cupones en pesos y en dólares
WHEN se muestra el total mensual
THEN aparece en la moneda de referencia declarada y también desagregado por moneda de cobro, con el
     tipo de cambio usado declarado

GIVEN el asesor agrega una posición
WHEN termina el clic
THEN la renta mensual, el total anual y el ratio sobre lo invertido se actualizan sin recargar la
     pantalla

GIVEN una cartera con un bono amortizing
WHEN se calcula la renta anual sobre lo invertido
THEN la amortización no entra en el numerador
```

---

#### F-022 — Rendimientos por naturaleza de tasa y plazo promedio

**Etiqueta:** Stage 1 · **Traza a:** F6

**Descripción.** **Cuatro números, nunca uno solo:** TIR en dólares, rendimiento dólar-linked, tasa
real sobre CER y TNA nominal en pesos. La pantalla **no ofrece la opción de colapsarlos en un
promedio**, porque ese promedio no significa nada: son magnitudes de unidades distintas. Cada número
viene con la porción de la cartera sobre la que se calcula. La duración ponderada se etiqueta como
*plazo promedio* y la sensibilidad de precio se reporta **por segmento, no agregada**: la duración
modificada es elasticidad respecto de la tasa propia de cada segmento, y sumarlas cruzaría
naturalezas.

**Input:** cartera de F-018; segmentación y métricas del universo.
**Output:** cuatro rendimientos ponderados abiertos, plazo promedio, sensibilidad por segmento.
**Depende de:** F-018
**Habilita:** F-030, F-033, F-034

**RICE:** R = 350 · I = 2 · C = 100 % · E = 4 → **Score 175**

```
GIVEN una cartera con posiciones hard-dollar, CER y tasa fija en pesos
WHEN se muestran los rendimientos
THEN aparecen tres números separados con su unidad declarada y la porción de cartera de cada uno, y
     no existe control de UI que los promedie

GIVEN una cartera 100 % hard-dollar
WHEN se muestran los rendimientos
THEN los otros tres aparecen explícitamente en cero por ciento de la cartera, no ausentes

GIVEN una cartera con posiciones en dos segmentos
WHEN se muestra la sensibilidad de precio
THEN aparece una sensibilidad por segmento, y no un único número agregado

GIVEN posiciones sin TIR ni duración informadas
WHEN se calcula el rendimiento ponderado
THEN quedan excluidas del cálculo y el panel declara qué porcentaje de la cartera quedó fuera
```

---

#### F-023 — Composición y curva TIR/duración

**Etiqueta:** Stage 1 · **Traza a:** F6

**Descripción.** Composición de la cartera por emisor, sector, clase de activo (soberano /
subsoberano / ON) y segmento. Y la **curva TIR/duración del segmento activo**, con las posiciones de
la cartera marcadas sobre la nube de candidatos del mismo segmento: es la herramienta que muestra de
un golpe qué papel está barato o caro para su plazo. Un segmento por gráfico, con la unidad del eje
declarada — nunca dos naturalezas de tasa en el mismo par de ejes.

**Input:** cartera de F-018; universo del segmento activo.
**Output:** gráficos de composición y dispersión TIR/duración.
**Depende de:** F-018
**Habilita:** —

**RICE:** R = 300 · I = 1 · C = 80 % · E = 5 → **Score 48**

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

---

### Bloque H — Lámina mínima (F7)

---

#### F-024 — Redondeo por lámina y diferencia entre pedido y real

**Etiqueta:** Stage 1 · **Traza a:** F7

**Descripción.** Cuando la lámina está informada, el sistema redondea el valor nominal al múltiplo
correspondiente y **muestra la diferencia entre la ponderación pedida y la real** — que es justamente
lo que hace que difieran: una posición pedida al 16,5 % puede terminar en 17,6 % real, y eso se ve.
Cuando **no** está informada, no redondea y **no asume 1, ni 1.000, ni ningún default de mercado**:
marca la posición como *lámina no informada*, la excluye del total ajustado, y el resumen dice cuántas
posiciones y qué porcentaje de la cartera quedaron sin ajustar. Un default de lámina produciría
nominales que parecen correctos y no lo son, en la pantalla que el asesor lleva a la reunión.

**Input:** cartera de F-018; lámina de F-009.
**Output:** valores nominales redondeados, porcentaje real por posición, marca de lámina faltante y
resumen de cobertura de ajuste.
**Depende de:** F-009, F-018
**Habilita:** F-025

**RICE:** R = 300 · I = 2 · C = 100 % · E = 3 → **Score 200**

```
GIVEN una posición pedida al 16,5 % con lámina informada
WHEN se calcula el nominal
THEN se redondea al múltiplo de la lámina y la pantalla muestra el 16,5 % pedido y el porcentaje real
     resultante, los dos a la vista

GIVEN una posición cuya emisión no tiene lámina informada
WHEN se calcula el nominal
THEN no se redondea, la posición se marca como "lámina no informada", y no se asume ningún valor por
     defecto

GIVEN una cartera con dos de siete posiciones sin lámina
WHEN se muestra el resumen
THEN declara cuántas posiciones y qué porcentaje de la cartera quedaron fuera del total ajustado
```

---

#### F-025 — Carga asistida de lámina con trazabilidad

**Etiqueta:** Stage 1 · **Traza a:** F7

**Descripción.** Cuando el asesor se topa con una posición sin lámina, tipea el valor en la misma
pantalla, sin salir del armador. Lo que tipea queda guardado con **origen `carga manual` y fecha**, se
propaga a las otras especies de la misma emisión —la lámina es atributo de la emisión, no de la
especie— y queda disponible para todos los asesores. La cobertura crece por uso, que es el único
mecanismo de crecimiento que no requiere inventar nada. Si el valor cargado entra en conflicto con uno
existente de otro origen, se aplica la detección de conflictos de F-009: no se elige, se reporta.

**Input:** posición marcada sin lámina en F-024; valor tipeado por el asesor.
**Output:** `condiciones_emision` actualizada con origen y fecha, propagada entre especies.
**Depende de:** F-024
**Habilita:** —

**RICE:** R = 200 · I = 1 · C = 80 % · E = 3 → **Score 53,3**

```
GIVEN una posición marcada como lámina no informada
WHEN el asesor tipea la lámina en la misma pantalla
THEN la posición se recalcula con redondeo y el valor queda guardado con origen "carga manual" y la
     fecha

GIVEN una lámina cargada a mano para la especie D de una emisión
WHEN se consultan las otras especies de la misma emisión
THEN heredan la lámina con el origen trazado a la carga manual original

GIVEN una lámina cargada por el asesor A
WHEN el asesor B abre una cartera con esa emisión
THEN ve la lámina cargada, porque condiciones_emision es compartida

GIVEN una lámina cargada a mano que contradice una ya existente de otro origen
WHEN se guarda
THEN se reporta el conflicto con los dos valores y sus orígenes, y el sistema no elige uno
```

---

### Bloque I — Renta variable (F8)

---

#### F-026 — Bloque de renta variable separado

**Etiqueta:** Stage 1 · **Traza a:** F8

**Descripción.** Acciones locales (69 verificadas) y CEDEARs (683 verificados) con su precio y su
volumen, en una sección propia del armador con su propio total. **Sin TIR, sin duración y sin
cashflow: no se mezcla con la renta fija en ningún cálculo.** El bloque suma al monto total de la
cartera pero **no al cálculo de renta ni a los rendimientos ponderados**. La frontera ya vive en un
solo lugar del motor —`cargar_universo()` devuelve renta fija y nada más; la renta variable se pide
aparte y a propósito— y la interfaz la replica. Existe porque la cartera estándar del cliente es
60-70 / 30-40 y una propuesta que sólo cubre renta fija no es la que el asesor lleva a la reunión.

Cada acción y CEDEAR lleva **país de la empresa o índice de referencia**, como dato recopilado con
origen y fecha declarados (mismo tratamiento que `condiciones_emision`: si falta, queda vacío y se
alerta — no se infiere del ticker). El bloque muestra su propia **distribución por país y por
rubro**, separada de la de renta fija: acá sí se puede diversificar geográficamente, y es donde el
criterio de reparto tiene más universo.

**Input:** `cedears` y `general-equity` de F-004; cartera de F-018.
**Output:** posiciones de renta variable con su total propio, integradas al monto de la cartera y
excluidas de todo cálculo de renta fija.
**Depende de:** F-004, F-018
**Habilita:** F-027

**RICE:** R = 300 · I = 2 · C = 80 % · E = 6 → **Score 80**

```
GIVEN una cartera con 65 % de renta fija y 35 % de renta variable
WHEN se calcula la renta anual sobre lo invertido
THEN el denominador y el numerador consideran únicamente la porción de renta fija, y el criterio está
     declarado en pantalla

GIVEN una posición de renta variable
WHEN se la mira en la tabla
THEN no tiene columna de TIR, ni de duración, ni de cupón

GIVEN una cartera mixta
WHEN se muestran los rendimientos ponderados por naturaleza de tasa
THEN la renta variable no participa de ninguno de los cuatro

GIVEN una cartera mixta
WHEN se muestra el monto total
THEN incluye las dos porciones, cada una con su subtotal identificado

GIVEN un CEDEAR con país de la empresa recopilado
WHEN se muestra el bloque de renta variable
THEN la distribución por país lo incluye con su peso dentro del bloque, sin mezclarse con la
     renta fija

GIVEN una acción sin país ni índice recopilado
WHEN se muestra la distribución por país
THEN figura como "país no informado", y en ningún caso se le asigna uno derivado del ticker
```

---

#### F-027 — Calendario de presentación de balances

**Etiqueta:** Stage 1 · **Traza a:** F8

**Descripción.** El equivalente del cupón del lado de la renta variable: en qué mes cada CEDEAR
presenta balance. La renta variable del producto son sólo CEDEARs (la Tanda 20, `a2ca43c`, sacó las
acciones locales de la UI y del armado), y un CEDEAR es una empresa que cotiza en EEUU: **una sola
fuente alcanza, SEC EDGAR** (`data.sec.gov`, gratuita, sin clave; cliente ya escrito en
`backend/app/externos/sec.py`) — no hace falta CNV, porque no hay ningún emisor local que cubrir. La
CNV queda para Stage 2 (F-054), sin tocar esta feature. EDGAR registra lo ya presentado, no un
calendario a futuro; el patrón mensual es estable y es lo que se necesita, y **la pantalla lo declara
como patrón histórico, no como fecha confirmada**. Se muestra en su propia grilla, nunca superpuesto a
la de cupones, porque un balance no es un cobro.

**Input:** tickers de CEDEARs de F-026; SEC EDGAR (`submissions/CIK{cik}.json` para el historial de
presentaciones; el puente ticker→CIK ya está resuelto vía `company_tickers.json`, el mismo mapeo que
usa `sec.py`).
**Output:** patrón mensual de presentación por emisor, declarado como histórico.
**Depende de:** F-026
**Habilita:** —

**RICE:** R = 200 · I = 1 · C = 85 % · E = 4 → **Score 42,5**
*Confidence 85 % (subió de 50 %): con la CNV fuera de alcance, la única fuente es SEC EDGAR, ya
integrada al proyecto (cliente y mapeo ticker→CIK reutilizables de `sec.py`/F-054). Lo único no
verificado en vivo todavía es el endpoint `submissions` para derivar el patrón mensual.*

```
GIVEN un CEDEAR con historial de presentaciones en EDGAR
WHEN se muestra su calendario de balances
THEN muestra el patrón mensual derivado de las presentaciones ya hechas, etiquetado como patrón
     histórico y no como fecha confirmada

GIVEN un CEDEAR sin historial resoluble en EDGAR (sin CIK mapeado, o sin presentaciones)
WHEN se muestra su calendario
THEN queda vacío y declarado como sin dato, y no se le proyecta un patrón por analogía con otros
     emisores

GIVEN una cartera mixta
WHEN se muestran el calendario de cupones y el de balances
THEN están en grillas separadas y sus montos no se suman entre sí
```

---

### Bloque J — Carga y diagnóstico de cartera existente (F9)

---

#### F-028 — Ingreso de cartera existente por tres vías

**Etiqueta:** Stage 1 · **Traza a:** F9

**Descripción.** La puerta de entrada del Flujo B. Tres vías: **pegar desde el portapapeles** —que es
el formato en que llega el resumen de cuenta—, **subir un CSV o Excel**, o **cargar posición por
posición** a mano. El parseo del pegado tolera las variantes de formato del resumen de cuenta
(separadores, decimales con coma, columnas en distinto orden) y muestra una previsualización de lo que
entendió antes de confirmar. Todo lo que entra se valida en el borde con Zod: nada llega al motor sin
esquema.

**Input:** texto pegado, archivo, o carga manual.
**Output:** lista de posiciones crudas con ticker declarado y nominal o monto, lista para resolver.
**Depende de:** F-003
**Habilita:** F-029

**RICE:** R = 200 · I = 3 · C = 80 % · E = 5 → **Score 96**

```
GIVEN un resumen de cuenta pegado desde el portapapeles con decimales con coma
WHEN se lo parsea
THEN se muestra la previsualización de las posiciones interpretadas antes de confirmar, con la
     cantidad de filas leídas

GIVEN un archivo CSV con columnas en distinto orden al esperado
WHEN se lo sube
THEN el sistema pide el mapeo de columnas en vez de asumir el orden

GIVEN una fila con un valor no numérico en el campo de nominal
WHEN se valida
THEN la fila se marca como inválida con el motivo, y no se la descarta en silencio ni se la
     interpreta como cero
```

---

#### F-029 — Resolución de tickers contra el universo

**Etiqueta:** Stage 1 · **Traza a:** F9

**Descripción.** Cada ticker declarado se resuelve contra el universo: se identifica la emisión, la
especie y el plazo de liquidación. Los que no se reconocen **se marcan sin descartarlos en silencio**:
quedan en la cartera como posición no resuelta, con su monto, y el diagnóstico declara qué porcentaje
de la cartera quedó sin resolver. Es la aplicación directa de la regla de no inventar: un ticker que
no está en el universo no se aproxima al más parecido, y en particular **no se deriva por manipulación
de strings** — ese camino ya produjo 121 tickers inexistentes que hubo que revertir.

**Input:** posiciones crudas de F-028; universo con especies vivas de F-011.
**Output:** posiciones resueltas con su instrumento; posiciones no resueltas marcadas.
**Depende de:** F-011, F-028
**Habilita:** F-030

**RICE:** R = 200 · I = 2 · C = 80 % · E = 3 → **Score 106,7**

```
GIVEN una posición con ticker presente en el universo
WHEN se la resuelve
THEN queda vinculada a la emisión, la especie y el plazo de liquidación correctos

GIVEN una posición con ticker que no existe en el universo
WHEN se la resuelve
THEN queda marcada como no reconocida, permanece en la cartera con su monto, y no se la reemplaza
     por el ticker más parecido

GIVEN una cartera con 2 de 11 posiciones no resueltas
WHEN se muestra el diagnóstico
THEN declara la cantidad y el porcentaje del monto de la cartera que quedó sin resolver

GIVEN un ticker de especie que no existe pero cuya raíz sí
WHEN se lo resuelve
THEN no se genera la especie por derivación de sufijo; queda no reconocido
```

---

#### F-030 — Valuación y diagnóstico de la cartera cargada

**Etiqueta:** Stage 1 · **Traza a:** F9

**Descripción.** Valora la cartera a precios de hoy y devuelve su descripción tal como está: renta mes
a mes, meses vacíos, rendimientos abiertos por naturaleza de tasa, plazo promedio, concentración por
emisor y por sector. Reusa exactamente los mismos servicios que el armador —F-015, F-020, F-021,
F-022— así que la cartera cargada y la que se está armando se leen con la misma vara. El diagnóstico
solo ya tiene valor comercial: hoy nadie lo hace porque son horas de trabajo manual.

**Input:** posiciones resueltas de F-029; precios de hoy.
**Output:** diagnóstico completo de la cartera existente, comparable con el de una cartera armada.
**Depende de:** F-013, F-021, F-022, F-029
**Habilita:** F-031, F-032

**RICE:** R = 200 · I = 3 · C = 100 % · E = 4 → **Score 150**

```
GIVEN una cartera cargada con posiciones resueltas
WHEN se la valora
THEN cada posición usa el precio del snapshot vigente, y la barra de estado declara la hora de ese
     snapshot y su demora

GIVEN la misma composición cargada por F-028 y armada a mano en el armador
WHEN se comparan los dos diagnósticos
THEN producen los mismos números, porque usan los mismos servicios de cálculo

GIVEN una cartera cargada con posiciones no resueltas
WHEN se la valora
THEN el monto no resuelto queda fuera de los cálculos de renta y rendimiento, y el diagnóstico lo
     declara

GIVEN una cartera cargada
WHEN se muestra su calendario
THEN los meses sin cobertura aparecen con cero explícito
```

---

### Bloque K — Riesgo en seis ejes (F10)

---

#### F-031 — Vector de riesgo de seis ejes

**Etiqueta:** Stage 1 · **Traza a:** F10 (resolución de la cuestión abierta N.º 1)

**Descripción.** El perfil de riesgo de una cartera es un **vector de seis ejes, no un score**:
duración, crédito, legislación, liquidez, concentración y moneda. Cada eje con su métrica, su unidad y
**su cobertura de dato declarada al lado**: duración modificada ponderada en años (618 de 927 con TIR
y duración); clase soberano/subsoberano/corporativo más calificación cuando existe (clase 100 %,
**calificación 359 de 927, 39 %**); porcentaje bajo ley extranjera vs argentina (691 de 927, 75 %);
percentil de volumen en dólares dentro del segmento más spread bid/ask (674 de 927 con spread);
máximo por clave de riesgo con `SOBERANO_AR` como clave única y por sector (100 % por emisor, sector
efectivo 903 de 927); y composición por naturaleza de tasa (100 %). **Nunca se colapsan en un número
único** — un score exigiría ponderar años contra una calificación que sólo existe para el 39 % del
universo, y eso sería un juicio inventado presentado como dato. Se rinden igual para la cartera
cargada, la que se está construyendo y cualquier propuesta. Donde falta la calificación se usan —y se
declaran— los proxies ya calibrados: tope de rendimiento sobre los pares del segmento, percentil de
liquidez y concentración máxima. **La calificación nunca se usa como filtro automático.**

**Input:** cartera (cargada o en construcción); ley y calificación de F-009; liquidez normalizada de
F-012; concentración de F-020; segmentación.
**Output:** seis ejes con su métrica, su unidad y su cobertura; visualización comparable.
**Depende de:** F-005, F-009, F-012, F-020, F-030
**Habilita:** F-033, F-034, F-036, F-037

**RICE:** R = 250 · I = 3 · C = 80 % · E = 6 → **Score 100**

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
THEN la calificación no filtra automáticamente ningún candidato; los proxies usados están declarados

GIVEN GD30, AE38 y TZX26 en la cartera
WHEN se calcula el eje de concentración
THEN los tres cuentan bajo la clave única SOBERANO_AR

GIVEN una cartera cargada, una en construcción y una propuesta
WHEN se muestran los tres perfiles
THEN los seis ejes se calculan y se presentan igual en los tres casos
```

---

### Bloque L — Optimizador de rotaciones (F11)

---

#### F-032 — Motor de rotaciones intra-segmento

**Etiqueta:** Stage 1 · **Traza a:** F11

**Descripción.** Envoltura como servicio de `detectar_swaps.py`: `evaluar_par`, `detectar`,
`tabla_spread_legislacion` y `hoja_sensibilidad` se conservan; se descarta la cáscara de argparse y
openpyxl. Genera el conjunto de rotaciones candidatas **dentro del mismo segmento**: un cruce CER →
hard-dollar es una visión macro humana, no un swap, y el motor no lo propone. Trabaja sobre la vista
viva de especies, porque los swaps de perfil rotan entre especies de la misma emisión (MEP → Cable).
Incluye el ranking de destinos con filtro de liquidez y de rendimiento mínimo. Está validado contra
swaps que la mesa efectivamente ejecutó — TLCWO → TLCMO.

**Input:** cartera diagnosticada de F-030; universo con especies vivas de F-011.
**Output:** rotaciones candidatas origen → destino con su delta de rendimiento y sus deltas por eje.
**Depende de:** F-011, F-030
**Habilita:** F-033, F-034, F-035

**RICE:** R = 200 · I = 3 · C = 100 % · E = 6 → **Score 100**

```
GIVEN una posición en un bono CER
WHEN se generan rotaciones candidatas
THEN todos los destinos propuestos son del segmento CER, y ninguno es hard-dollar, dólar-linked ni
     tasa nominal en pesos

GIVEN el swap TLCWO → TLCMO que la mesa ejecutó
WHEN se corre el motor sobre la cartera de origen
THEN esa rotación aparece entre las candidatas

GIVEN una posición en la especie MEP de una emisión
WHEN se generan rotaciones
THEN la especie Cable de la misma emisión es un destino válido, porque el optimizador trabaja sobre
     la vista viva

GIVEN un destino candidato por debajo del filtro de liquidez o de rendimiento mínimo
WHEN se rankean los destinos
THEN queda excluido del ranking
```

---

#### F-033 — Modo "mantener la TIR y bajar el riesgo"

**Etiqueta:** Stage 1 · **Traza a:** F11

**Descripción.** El asesor elige **cuál de los seis ejes minimizar** — el default es **duración**,
porque es el único eje con cobertura casi total sobre los instrumentos que efectivamente cotizan y el
más medible sin depender de un dato que falta. El sistema propone destinos que cumplen las tres
condiciones a la vez: **(a)** mejoran estrictamente el eje elegido, **(b)** **no empeoran ninguno de
los otros cinco** —criterio de no-empeoramiento, no de compensación— y **(c)** mantienen el
rendimiento dentro de una banda de **±0,5 pp**, la misma que el motor ya usa para considerar dos
candidatos parejos. Si no hay ningún destino que cumpla las tres, el sistema **dice que no hay
propuesta** en vez de relajar la restricción en silencio.

**Input:** rotaciones candidatas de F-032; vector de seis ejes de F-031; eje primario elegido.
**Output:** propuestas que satisfacen las tres condiciones, o la declaración explícita de que no hay.
**Depende de:** F-022, F-031, F-032
**Habilita:** F-036

**RICE:** R = 180 · I = 2 · C = 80 % · E = 5 → **Score 57,6**

```
GIVEN el modo bajar riesgo sin eje elegido
WHEN se abre
THEN el eje primario viene preseleccionado en duración, y se puede cambiar a cualquiera de los otros
     cinco

GIVEN una rotación que baja duración pero sube concentración
WHEN se evalúa contra el criterio de no-empeoramiento
THEN se descarta, porque empeora uno de los otros cinco ejes

GIVEN una rotación que baja duración, no empeora los otros cinco, y cambia el rendimiento en 0,8 pp
WHEN se evalúa
THEN se descarta por salir de la banda de ±0,5 pp

GIVEN una cartera para la que ningún destino cumple las tres condiciones
WHEN se pide el modo bajar riesgo
THEN el sistema declara que no hay propuesta, y no muestra alternativas con la restricción relajada
```

---

#### F-034 — Modo "subir la TIR declarando la contrapartida"

**Etiqueta:** Stage 1 · **Traza a:** F11

**Descripción.** Propone rotaciones que suben el rendimiento, y **cada propuesta lleva, en la misma
fila, el eje o los ejes que empeoran y en cuánto**: "+180 bps de TIR / duración +2,3 años / ley ARG en
vez de NY". **Nunca se propone una mejora de TIR sin nombrar su contrapartida** — la fila no se puede
renderizar sin ella. Si una rotación sube el rendimiento y no empeora ningún eje, se lo declara
igual, porque es información y no un vacío. La contrapartida se expresa en la unidad de cada eje, no
en un puntaje.

**Input:** rotaciones candidatas de F-032; vector de seis ejes de F-031.
**Output:** propuestas de mejora de rendimiento con su contrapartida nombrada y cuantificada.
**Depende de:** F-022, F-031, F-032
**Habilita:** F-036

**RICE:** R = 180 · I = 3 · C = 80 % · E = 5 → **Score 86,4**

```
GIVEN una rotación que sube 180 bps de TIR, alarga la duración 2,3 años y cambia ley NY por ley ARG
WHEN se la muestra
THEN la misma fila declara los tres datos: la mejora, el delta de duración en años y el cambio de ley

GIVEN una propuesta de mejora de TIR cuyos deltas por eje no se pudieron calcular
WHEN se intenta mostrarla
THEN no se muestra, porque no hay mejora de TIR sin contrapartida nombrada

GIVEN una rotación que sube la TIR sin empeorar ningún eje
WHEN se la muestra
THEN declara explícitamente que ningún eje empeora, en vez de dejar la columna en blanco

GIVEN un eje cuya cobertura de dato es parcial para la posición
WHEN se declara la contrapartida sobre ese eje
THEN la cobertura faltante se declara junto al delta
```

---

#### F-035 — Costo real de rotar y aviso de cupón próximo

**Etiqueta:** Stage 1 · **Traza a:** F11

**Descripción.** Cada propuesta trae el costo real de rotar, que **no es sólo el arancel**: la rotación
paga el **spread bid/ask en las dos patas**. Con las puntas reales el costo mediano medido pasó de
1,50 % a **3,10 %**, y **12 de 51 rotaciones superaban el 5 %** — el motor venía proponiendo swaps que
en la práctica no convenían, y sin este cálculo el optimizador es una fuente de malas
recomendaciones. Reusa `mercado.py`; lo único que cambia es de dónde vienen las puntas: BYMA publica
`bidPrice`/`offerPrice` en el mismo endpoint que el precio, lo que **elimina la dependencia de
data912** y mejora la cobertura de spread. Trae además el **aviso de cupón próximo**: rotar tres días
antes de cobrar tiene un costo que no está en el precio.

**Input:** propuestas de F-032; puntas de F-004; calendario de F-015.
**Output:** costo de rotación por propuesta, desagregado en arancel y spread por pata; aviso de cupón.
**Depende de:** F-032
**Habilita:** F-036

**RICE:** R = 180 · I = 3 · C = 100 % · E = 3 → **Score 180**

```
GIVEN una rotación entre dos instrumentos con puntas vivas
WHEN se calcula su costo
THEN el costo declara arancel y spread bid/ask de la pata de venta y de la pata de compra por
     separado

GIVEN una rotación cuyo costo total supera el 5 %
WHEN se la muestra
THEN queda marcada como costo elevado, con el porcentaje a la vista

GIVEN un instrumento sin dos puntas vivas
WHEN se calcula el costo de rotarlo
THEN el spread se declara como no disponible y la propuesta se marca como de costo no verificable, y
     no se asume un spread por defecto

GIVEN una posición que cobra cupón dentro de la ventana de aviso
WHEN se propone rotarla
THEN la propuesta muestra el aviso de cupón próximo con la fecha del cobro
```

---

#### F-036 — Aceptación rotación por rotación y efecto sobre el calendario

**Etiqueta:** Stage 1 · **Traza a:** F11

**Descripción.** El asesor acepta o descarta **una rotación por vez**, y con cada decisión ve moverse
el calendario de doce meses y los seis ejes de riesgo. Cada propuesta declara además su **efecto sobre
el calendario**: qué mes se llena y qué mes se vacía — que es la razón de ser del producto del lado
del optimizador, porque desconcentrar el calendario de cobros es el objetivo, no un efecto lateral.
El estado es reversible: una rotación aceptada se puede deshacer y todo vuelve.

**Input:** propuestas de F-033, F-034 y F-035; calendario de F-015; ejes de F-031.
**Output:** cartera propuesta acumulada; calendario y ejes actualizados en vivo.
**Depende de:** F-015, F-021, F-031, F-033, F-034, F-035
**Habilita:** F-037

**RICE:** R = 180 · I = 2 · C = 80 % · E = 5 → **Score 57,6**

```
GIVEN una propuesta de rotación
WHEN se la muestra
THEN declara qué mes del calendario se llena y qué mes se vacía si se acepta

GIVEN el asesor acepta una rotación
WHEN termina la acción
THEN el calendario de doce meses y los seis ejes se actualizan, y las propuestas restantes se
     recalculan sobre la cartera resultante

GIVEN una rotación aceptada
WHEN el asesor la deshace
THEN la cartera, el calendario y los seis ejes vuelven al estado anterior

GIVEN el asesor descarta una rotación
WHEN sigue trabajando
THEN esa rotación no vuelve a proponerse en la misma sesión
```

---

#### F-037 — Comparación de la cartera original contra la propuesta

**Etiqueta:** Stage 1 · **Traza a:** F11

**Descripción.** Al final del Flujo B, las dos carteras lado a lado: la original y la propuesta, con
la renta mes a mes de cada una, los rendimientos abiertos por naturaleza de tasa, los seis ejes y el
costo total de rotación acumulado. Las diferencias de cobertura mensual y de renta anual están
marcadas. Es la pantalla que el jefe de mesa lee para aprobar o devolver, y por eso las dos columnas
se miden exactamente con la misma vara.

**Input:** cartera original de F-030; cartera propuesta de F-036.
**Output:** comparación lado a lado con deltas por métrica y por mes.
**Depende de:** F-031, F-036
**Habilita:** F-041

**RICE:** R = 180 · I = 2 · C = 80 % · E = 4 → **Score 72**

```
GIVEN una cartera original y una propuesta
WHEN se las compara
THEN cada métrica aparece en las dos columnas calculada con el mismo servicio, y el delta está
     explícito

GIVEN una comparación
WHEN se mira la renta mensual
THEN los meses que pasaron de cero a cubierto y los que pasaron de cubierto a cero están marcados

GIVEN una comparación
WHEN se mira el resultado neto
THEN el costo total de rotación acumulado está a la vista junto a la mejora de renta o de rendimiento
```

---

### Bloque M — Monitor de mercado y ficha de instrumento (F12)

---

#### F-038 — Monitor de mercado

**Etiqueta:** Stage 1 · **Traza a:** F12

**Descripción.** La pantalla de entrada diaria: el universo por segmento, con filtros y orden, para
consultar sin armar nada — el uso de "abro la herramienta a la mañana y miro cómo está el mercado".
Grilla densa de ~1.700 filas con ordenamiento y filtrado del lado del cliente sobre datos paginados.
Navegación de dos niveles: sección arriba, segmento debajo, y **nunca dos segmentos a la vez**, que es
como se respeta la regla de las unidades. Barra de filtros numéricos siempre visible (TIR mínima y
máxima, duración mínima y máxima, familia, limpiar) y la curva TIR/duración del segmento activo con
las alertas del día.

**Input:** universo saneado de F-010; liquidez normalizada de F-012; barra de estado de F-013.
**Output:** vista de consulta del universo; punto de entrada a la ficha de instrumento.
**Depende de:** F-003, F-010, F-012, F-013
**Habilita:** F-039

**RICE:** R = 400 · I = 2 · C = 80 % · E = 6 → **Score 106,7**

```
GIVEN el monitor abierto
WHEN se lo mira
THEN hay un solo segmento activo por vez, y la unidad de la columna de rendimiento corresponde a ese
     segmento

GIVEN una grilla con ~1.700 filas
WHEN el asesor ordena por una columna y aplica dos filtros numéricos
THEN la respuesta es inmediata y el conteo de filas resultantes está visible

GIVEN el monitor abierto a la mañana
WHEN se lo mira
THEN la barra de estado del dato muestra la hora del snapshot, la demora de la fuente, los descartes
     por sanidad del día y la cobertura de los campos críticos

GIVEN una fila del monitor
WHEN se hace clic
THEN se abre la ficha del instrumento
```

---

#### F-039 — Ficha de instrumento

**Etiqueta:** Stage 1 · **Traza a:** F12

**Descripción.** El destino natural de cada ticker que aparece en el armador y en el optimizador.
Muestra las condiciones de emisión —emisor, ley, moneda de pago, estructura del cupón, tasa,
frecuencia, lámina, calificación cuando existe—, **las tres especies de liquidación con sus precios y
puntas**, y el flujo de fondos completo hasta el vencimiento. Cada campo con su origen y, cuando
falta, con la marca de faltante en vez del vacío silencioso. Desde acá se agrega el instrumento a una
cartera nueva.

**Input:** `condiciones_emision` de F-009; especies vivas de F-011; cashflow de F-006.
**Output:** ficha completa; acción de agregar a cartera.
**Depende de:** F-009, F-011, F-038
**Habilita:** F-040

**RICE:** R = 350 · I = 2 · C = 80 % · E = 5 → **Score 112**

```
GIVEN un bono con tres especies de liquidación
WHEN se abre su ficha
THEN las tres aparecen con su precio, sus dos puntas y su moneda de cotización, sin sumarse ni
     promediarse entre sí

GIVEN un bono sin calificación crediticia
WHEN se abre su ficha
THEN el campo aparece marcado como no informado, y no vacío ni inferido de la clase del emisor

GIVEN un bono con cashflow disponible
WHEN se abre su ficha
THEN muestra el flujo de fondos completo hasta el vencimiento, distinguiendo interés de amortización

GIVEN cada condición de emisión mostrada
WHEN se la consulta
THEN trae su origen y su fecha
```

---

#### F-040 — Sensibilidad del precio por repricing completo

**Etiqueta:** Stage 1 · **Traza a:** F12

**Descripción.** La sensibilidad del precio a movimientos de la TIR del instrumento se calcula por
**repricing completo del cashflow contractual**, no por aproximación lineal de duración: en bonos
largos la aproximación subestima fuerte la suba ante compresiones grandes, y esos son justamente los
escenarios que interesan. El método está verificado contra una tabla externa con desvío máximo de
**0,12 pp sobre movimientos de hasta +91 %**. Reusa `cupones.py`, que ya implementa el repricing por
descuento completo. Se muestra como tabla de escenarios sobre la TIR propia del instrumento, nunca
sobre una tasa de otro segmento.

**Input:** cashflow del instrumento; TIR vigente.
**Output:** tabla de precio ante escenarios de movimiento de la TIR.
**Depende de:** F-006, F-039
**Habilita:** —

**RICE:** R = 200 · I = 1 · C = 100 % · E = 3 → **Score 66,7**

```
GIVEN un bono con cashflow completo
WHEN se calcula la sensibilidad
THEN el precio de cada escenario sale de descontar el cashflow contractual a la TIR del escenario, y
     no de multiplicar por la duración modificada

GIVEN la tabla externa de verificación con movimientos de hasta +91 %
WHEN se corre el repricing
THEN el desvío máximo contra esa tabla es de 0,12 pp

GIVEN un instrumento sin cashflow disponible
WHEN se pide la sensibilidad
THEN se declara que no se puede calcular, y no se cae a la aproximación por duración
```

---

#### F-052 — Renta variable en el monitor

**Etiqueta:** Stage 1 · **Traza a:** F12 (agregada 08/2026)

**Descripción.** El monitor de F-038 muestra sólo renta fija: sus pestañas se organizan por
naturaleza de rendimiento, y una acción no tiene TIR. Pero los datos de renta variable **ya están
en la base** —acciones del panel líder y general, y CEDEARs, de los endpoints de BYMA (F-004)— y
el propio endpoint de segmentos ya los cuenta como excluidos (`renta_variable: 1417`). Esta
feature agrega las pestañas de **acciones** y **CEDEARs** al monitor, con columnas propias de
renta variable: precio, moneda de cotización, variación, volumen y puntas, **sin columna de
rendimiento** — no existe una TIR de acción y no se muestra otra cosa en su lugar (regla 2).
Toda comparación u orden por volumen usa el volumen normalizado a dólares de F-012, nunca los
nominales crudos en monedas mezcladas (regla 3). Lo que BYMA no publica para una especie queda
vacío y contado en cobertura (regla 1). Reusa la grilla virtualizada, el orden y los filtros de
F-038. Los `sin_segmento` (renta fija sin tipo de tasa reconocible) **no** entran acá: siguen
contados y declarados como hasta ahora.

**Lo que la exploración del código corrigió** (08/08/2026): el backend **no** es "un filtro más".
La renta variable se descarta *antes* de segmentar —`Segmentacion.renta_variable` es un contador,
no una lista, y `EspecieUniverso` no admite una especie sin naturaleza de tasa—, así que las filas
nunca llegan al endpoint de universo. La feature necesita **lectura y endpoint propios** sobre el
universo ya consolidado, con el mismo patrón que usa `posiciones/lectura.py`, que lee directo por
esta misma razón. Dos consecuencias más: las **puntas** ya se persisten para toda la rueda (RV
incluida) pero ninguna lectura las expone todavía, así que esta feature estrena ese lector; y la
**variación** exige guardar el cierre anterior, que BYMA publica (`previousClosingPrice`) y el
normalizador ya captura, pero la consolidación descarta al persistir. Se agrega la columna
`cierre_anterior` a `precios` (migración chica) en vez de mostrar una columna vacía: es dato
publicado, no derivado, y de paso queda disponible para renta fija.

**Input:** universo consolidado con acciones y CEDEARs (F-004 vía F-007); volumen normalizado de
F-012; monitor de F-038.
**Output:** pestañas de acciones y CEDEARs en el monitor, con sus columnas propias; lector de
puntas y cierre anterior persistido.
**Depende de:** F-011, F-012, F-038 · **corre después de F-051**, que toca la misma consolidación
**Habilita:** F-026 (le deja los componentes de fila y columnas de renta variable)

**RICE:** R = 400 · I = 1 · C = 80 % · E = 3 → **Score 106,7**

```
GIVEN el monitor abierto
WHEN se elige la pestaña de acciones o la de CEDEARs
THEN las columnas son las de renta variable —precio, variación, volumen, puntas— y no hay columna
     de rendimiento: ni TIR, ni nada presentado en su lugar

GIVEN un CEDEAR que cotiza en pesos y en dólares
WHEN se ordena o compara por volumen
THEN la comparación usa el volumen normalizado a dólares, nunca los nominales crudos de monedas
     distintas

GIVEN un campo que BYMA no publica para una especie
WHEN se muestra la fila
THEN la celda queda vacía y contada en la cobertura; no se completa por analogía ni se calcula
     desde otra especie

GIVEN las pestañas nuevas junto a las de renta fija
WHEN se mira el conteo del monitor
THEN los instrumentos que siguen fuera (sin_segmento) están declarados con su cantidad, igual que
     antes
```

---

#### F-053 — Ficha del activo de renta variable

**Etiqueta:** Stage 1 · **Traza a:** F8 · **Agregada el 08/08/2026**

**Descripción.** Una acción o un CEDEAR en nuestro monitor son hoy cuatro números: ticker, precio,
variación y volumen. No hay forma de saber **qué empresa es**, en qué sector opera ni de qué país,
y esos son los datos con los que un asesor decide en renta variable — donde no hay TIR ni cronograma
que mirar. La ficha se abre desde la fila (el gesto ya existe: `useAbrirInstrumento`) como drawer
sobre la tabla, el mismo mecanismo de `state.fondo` que ya usa la renta fija.

**El dato viene de Yahoo Finance**, que es la única fuente verificada que lo publica para el
mercado local. Verificado el 08/08/2026: `MSFT.BA` en Yahoo **es el CEDEAR** —precio en ARS, bolsa
BUE— y su perfil es el de la empresa subyacente, así que la consulta es siempre `TICKER.BA` con el
ticker que ya tenemos de BYMA: **no se deriva ni se mapea nada** (regla 11). La respuesta se acepta
sólo si declara la bolsa BUE y el símbolo pedido; si no, la ficha dice que no hay dato, nunca
muestra el de otro instrumento.

**Lo que NO entra, y no es negociable.** Yahoo publica recomendación de analistas (`STRONG_BUY`),
precio objetivo y consenso. Eso es opinión de terceros, no dato duro, y la **regla 6** del dominio
mantiene el análisis determinístico y sin juicio ajeno presentado como información. Tampoco se
traducen los valores propietarios de Yahoo: "Financial Services" y "Banks - Regional" se muestran
como Yahoo los declara, con la fuente y la fecha de captura a la vista (**regla 11**).

**Dos niveles de disponibilidad, medidos.** El endpoint de cotización e histórico responde sin
autenticación; el de perfil y valuación exige un mecanismo de cookie+crumb no documentado que Yahoo
ya endureció una vez. El diseño degrada: si el segundo nivel falla, el primero sigue; si Yahoo
entero no responde, la ficha muestra lo nuestro —precio, cierre anterior, puntas, operaciones de
BYMA— y **declara que el bloque externo no está disponible**. Ninguna pantalla nuestra depende de
que Yahoo esté vivo.

**Input:** ticker de renta variable del monitor (F-052); precio y puntas de BYMA ya persistidos;
Yahoo Finance como fuente externa.
**Output:** ficha con bloque propio (BYMA) y bloque externo rotulado (Yahoo), con caché por TTL.
**Depende de:** F-039 (el drawer y su navegación), F-052 (las pestañas y la tabla)
**Habilita:** la distribución por país y rubro de F-026, hoy sin fuente

**RICE:** R = 300 · I = 2 · C = 70 % · E = 3 → **Score 140**
*Confidence 70 % por la fragilidad de la fuente: los endpoints funcionan hoy pero no son
contractuales.*

```
GIVEN una acción local en el monitor
WHEN se hace clic en su fila
THEN se abre la ficha con el nombre de la empresa, el precio de BYMA y el bloque de Yahoo rotulado
     con su fuente y la fecha de captura

GIVEN un CEDEAR
WHEN se pide su ficha
THEN se consulta el mismo ticker con sufijo .BA, sin derivar el símbolo del subyacente, y el perfil
     que se muestra es el de la empresa emisora

GIVEN una respuesta de Yahoo que declara una bolsa distinta de BUE o un símbolo que no es el pedido
WHEN se arma la ficha
THEN el bloque externo queda vacío y declarado; en ningún caso se muestran los datos recibidos

GIVEN Yahoo caído o el mecanismo de autenticación roto
WHEN se pide una ficha
THEN la ficha responde igual con los datos de BYMA y declara que el bloque externo no está
     disponible; ninguna pantalla del producto se rompe

GIVEN los datos de recomendación y precio objetivo que Yahoo publica
WHEN se muestra la ficha
THEN no aparecen: son opinión de terceros y el producto no presenta juicio ajeno como dato

GIVEN un campo del perfil que Yahoo declara en su propio vocabulario
WHEN se muestra en la ficha
THEN se muestra tal como la fuente lo declara, sin traducir, con la fuente identificada
```

---

### Bloque N — Mis carteras (F13)

---

#### F-041 — Guardar, listar, reabrir y revaluar carteras

**Etiqueta:** Stage 1 · **Traza a:** F13

**Descripción.** Sin persistencia el producto es una calculadora de una sesión y el login no tendría
objeto. Listado de las carteras guardadas del asesor con nombre, fecha, monto, moneda de referencia y
un resumen de una línea. Cada cartera se guarda **con los precios del momento en que se guardó** —una
propuesta tiene que poder reproducirse tal como se presentó— y se puede reabrir para valuarla a
precios de hoy, **con la diferencia explícita**. Se guardan carteras, no clientes: los objetivos del
cliente son parámetros de la cartera, no un registro que persiste.

**Input:** cartera de F-018 o propuesta de F-037; snapshot de precios vigente.
**Output:** carteras persistidas con precios congelados; listado; revaluación con delta.
**Depende de:** F-014, F-018, F-037
**Habilita:** F-042

**RICE:** R = 300 · I = 3 · C = 100 % · E = 5 → **Score 180**

```
GIVEN una cartera guardada hace tres semanas
WHEN se la reabre
THEN muestra por defecto los precios y los números con los que se guardó, no los de hoy

GIVEN una cartera guardada
WHEN el asesor pide revaluarla a precios de hoy
THEN muestra las dos valuaciones y la diferencia explícita, con la fecha de cada snapshot

GIVEN el listado de carteras del asesor A
WHEN el asesor B se autentica
THEN no ve ninguna cartera de A

GIVEN una cartera guardada
WHEN se la inspecciona
THEN no contiene ningún campo de identificación de cliente: nombre, contacto ni historial
```

---

#### F-042 — Exportación a Excel y PDF

**Etiqueta:** Stage 1 · **Traza a:** F13

**Descripción.** Exportación de la cartera y del diagnóstico como **documento interno de trabajo** — el
asesor arma la presentación final al cliente por su cuenta. El export lleva todo lo que la pantalla
lleva y con el mismo criterio: los rendimientos abiertos por naturaleza de tasa y nunca promediados,
los seis ejes con su cobertura, las posiciones sin lámina declaradas, y el pie con la hora del
snapshot y la demora de la fuente. Un export que perdiera esas declaraciones sería peor que no
exportar, porque circula fuera de la pantalla que las contextualiza.

**Input:** cartera guardada o en curso de F-041.
**Output:** archivo Excel y archivo PDF.
**Depende de:** F-041
**Habilita:** —

**RICE:** R = 250 · I = 2 · C = 80 % · E = 4 → **Score 100**

```
GIVEN una cartera con posiciones de tres naturalezas de tasa
WHEN se la exporta
THEN el archivo trae los rendimientos abiertos por naturaleza, y ninguna celda los promedia

GIVEN una cartera con posiciones sin lámina informada
WHEN se la exporta
THEN el archivo las declara como tales y reporta el porcentaje sin ajustar

GIVEN cualquier export
WHEN se lo abre
THEN el pie declara la hora del snapshot de precios y la demora de la fuente
```

---

### Bloque O — Stage 2

---

#### F-043 — Gestión de clientes y CRM

**Etiqueta:** Stage 2 · **Traza a:** "Fuera del MVP"

**Descripción.** Ficha de cliente, asociación de carteras a clientes, y los datos que Stage 1 excluye
deliberadamente. Es la feature que convierte "se guardan carteras" en "se guardan clientes", y por eso
está explícitamente fuera del MVP: el producto se define por lo que no es tanto como por lo que es.
Requiere resolver dónde viven los datos de clientes reales, que por regla del proyecto **no entran al
repositorio**.

**Input:** F-041 en producción con uso real.
**Output:** entidad cliente con sus carteras asociadas.
**Depende de:** F-041
**Habilita:** F-044

**RICE:** R = 300 · I = 2 · C = 50 % · E = 15 → **Score 20**

```
GIVEN un cliente creado
WHEN se le asocian carteras
THEN el listado del asesor puede filtrarse por cliente sin cambiar el cálculo de ninguna cartera

GIVEN datos de clientes reales
WHEN se los persiste
THEN nunca quedan en el repositorio de código
```

---

#### F-044 — Historial de propuestas y seguimiento de performance

**Etiqueta:** Stage 2 · **Traza a:** "Fuera del MVP"

**Descripción.** Registro de las propuestas presentadas a lo largo del tiempo y comparación de lo
propuesto contra lo que efectivamente pasó. Depende de tener clientes (F-043) y de acumular meses de
carteras guardadas. La performance se reporta con **TWR y MWR, las dos por separado**: TWR mide la
estrategia contra su benchmark neutralizando aportes y retiros; MWR —la TIR del cliente— mide lo que
efectivamente le pasó a su plata con el timing de sus aportes. Ambas en la moneda de referencia de la
cartera, y en términos reales si es en pesos.

**Input:** F-043; histórico de carteras y snapshots.
**Output:** línea de tiempo de propuestas con su evolución.
**Depende de:** F-043
**Habilita:** —

**RICE:** R = 250 · I = 2 · C = 50 % · E = 10 → **Score 25**

```
GIVEN una propuesta presentada hace seis meses
WHEN se la revisa hoy
THEN se ve la valuación de entonces y la de hoy, con los snapshots de cada fecha declarados
```

---

#### F-045 — Colocaciones primarias

**Etiqueta:** Stage 2 · **Traza a:** "Fuera del MVP"

**Descripción.** Instrumentos que todavía no cotizan: licitaciones primarias que el asesor quiere
evaluar antes de que exista precio de mercado. Incluye el recuadro de simulación de un instrumento
inexistente sobre la curva TIR/duración.

**Input:** condiciones de la colocación cargadas a mano.
**Output:** instrumento simulado evaluable junto a los reales, marcado como no cotizante.
**Depende de:** F-038
**Habilita:** —

**RICE:** R = 150 · I = 2 · C = 50 % · E = 10 → **Score 15**

```
GIVEN un instrumento simulado con ticker, TIR y duración tipeados
WHEN se lo agrega a la curva
THEN aparece junto a los reales, visualmente marcado como simulado y no cotizante
```

---

#### F-046 — Fondos comunes de inversión valuables en cartera

**Etiqueta:** Stage 2 · **Traza a:** "Fuera del MVP"

**Descripción.** FCI **valuables e integrables al cálculo de una cartera**: dejan de ser línea con
peso y sin precio (F-018) y pasan a valuarse como cualquier otra posición.

**La fuente apareció.** Hasta el 13/08/2026 esta ficha decía "siguen sin fuente", y ese "verificado el
30/07/2026" se había medido **contra Docta y data912** —las fuentes ya conectadas—, no contra el
universo de fuentes posibles. CAFCI nunca se había mirado. Se verificó en vivo el 13/08/2026 y sirve:
publica valor de cuotaparte diario por fondo y clase, sin clave. El detalle de la fuente, sus
endpoints y sus salvedades viven en **F-057**, que es la que la ingiere.

**Lo que sigue faltando, y por qué esta ficha no se cierra con F-057.** Valuar no es mostrar. Una
posición en FCI dentro de una cartera necesita tres cosas que la planilla diaria **no** da:

- **Composición del fondo.** Sin look-through, un FCI dentro de una cartera es una caja negra para los
  límites de concentración (F-020) y para el vector de riesgo de seis ejes (F-031). Un fondo de renta
  fija soberana argentina es, por transparencia, exposición a `SOBERANO_AR` — pero si no se ve adentro,
  la cartera lo cuenta como una línea diversificada y la regla 4 queda burlada por omisión.
- **Un tipo de cambio propio para los fondos no-ARS.** La columna `Reexp.Pesos` de la planilla **no
  sirve** (ver F-057): el TC que aplica difiere entre fondos de la misma moneda. Por regla 3 el TC se
  deriva del propio universo, y un FCI no cotiza en dos monedas, así que no hay cociente del cual
  derivarlo. Queda por definir qué TC del universo se le aplica y declararlo.
- **El calendario de cupones.** La regla 5 hace del cronograma criterio de armado. Un FCI no tiene
  cronograma contractual, así que una cartera con FCI tiene un porcentaje del capital que no aporta
  ningún mes al calendario. Eso hay que mostrarlo como hueco declarado, no como ausencia silenciosa.

**Input:** valor de cuotaparte de F-057; una fuente de composición de cartera de FCI, todavía no
identificada; el TC del universo de F-012.
**Output:** FCI valuables e integrables al cálculo, con su opacidad declarada donde no haya
look-through.
**Depende de:** F-018, F-057, F-012
**Habilita:** —

**RICE:** R = 200 · I = 2 · C = 60 % · E = 8 → **Score 30**
*Confidence 60 %: el precio ya tiene fuente verificada (F-057), y el esfuerzo baja de 12 a 8 porque
la ingesta la resuelve esa feature. Lo que sostiene el 40 % de incertidumbre es la composición del
fondo, sin fuente identificada al 13/08/2026.*

```
GIVEN un FCI en una cartera y su valor de cuotaparte del día
WHEN se valúa la cartera
THEN la posición se valúa con el valor de cuotaparte publicado, con su fecha declarada

GIVEN un FCI sin composición conocida
WHEN se calculan los límites de concentración y el vector de riesgo
THEN el porcentaje que representa el FCI se declara como exposición no atribuible, y no se reparte
     entre los emisores conocidos ni se cuenta como una línea diversificada

GIVEN un FCI en moneda distinta de la de la cartera
WHEN se lo valúa
THEN se usa el tipo de cambio derivado del universo, nombrando el par que lo produjo, y nunca la
     columna Reexp.Pesos de la planilla de CAFCI

GIVEN una cartera con una posición en FCI
WHEN se arma el calendario de doce meses
THEN el capital colocado en FCI se muestra como porción sin cronograma contractual, declarada
```

---

#### F-047 — Opciones

**Etiqueta:** Stage 2 · **Traza a:** "Fuera del MVP"

**Descripción.** Instrumentos con opcionalidad. Fuera del MVP y del alcance del motor actual, que no
modela payoffs no lineales.

**Input:** por definir.
**Output:** por definir.
**Depende de:** —
**Habilita:** —

**RICE:** R = 80 · I = 1 · C = 50 % · E = 10 → **Score 4**

```
GIVEN una posición en opciones
WHEN se la carga en Stage 1
THEN queda como posición no resuelta y declarada, sin cálculo asociado
```

---

#### F-048 — Alertas y notificaciones

**Etiqueta:** Stage 2 · **Traza a:** "Fuera del MVP"

**Descripción.** Avisos proactivos: un mes de la cartera que quedó sin cobertura, una rotación que
apareció, un cupón que se cobra la semana que viene. En Stage 1 toda la señalización es en pantalla
(F-013); acá pasa a ser push.

**Input:** eventos de las corridas de ingesta y de las carteras guardadas.
**Output:** notificaciones configurables por asesor.
**Depende de:** F-041
**Habilita:** —

**RICE:** R = 300 · I = 1 · C = 80 % · E = 6 → **Score 40**

```
GIVEN una cartera guardada con un cupón a cobrar en 7 días
WHEN corre la evaluación de alertas
THEN el asesor dueño de esa cartera recibe el aviso, y ningún otro asesor lo recibe
```

---

#### F-049 — Comparación de carteras entre sí

**Etiqueta:** Stage 2 · **Traza a:** "Fuera del MVP"

**Descripción.** Comparar dos o más carteras guardadas lado a lado, más allá del par original/propuesta
que F-037 ya resuelve. Útil para el jefe de mesa que revisa propuestas de asesores distintos.

**Input:** carteras guardadas de F-041.
**Output:** comparación n a n con la misma vara.
**Depende de:** F-037, F-041
**Habilita:** —

**RICE:** R = 200 · I = 1 · C = 80 % · E = 4 → **Score 40**

```
GIVEN dos carteras guardadas en fechas distintas
WHEN se las compara
THEN los precios usados se declaran por cartera y la comparación advierte si los snapshots difieren
```

---

#### F-050 — Migración a la API Market Data oficial de BYMA

**Etiqueta:** Stage 2 · **Traza a:** "Fuera del MVP"

**Descripción.** Reemplazo del feed abierto demorado 20 minutos por la API Market Data oficial, que
según BYMA no requiere homologación y se solicita a `marketdata@byma.com.ar`. Elimina la demora
declarada. El cliente de F-004 se diseña con la interfaz de fuente desacoplada justamente para que
esta migración sea un cambio de implementación y no de arquitectura.

**Input:** acceso concedido a la API Market Data.
**Output:** snapshots sin demora; la barra de estado del dato deja de declarar 20 minutos.
**Depende de:** F-004
**Habilita:** —

**RICE:** R = 400 · I = 2 · C = 50 % · E = 5 → **Score 80**
*Confidence 50 %: la concesión del acceso no está confirmada en los inputs.*

```
GIVEN el acceso a la API oficial concedido
WHEN se cambia la implementación de la fuente de rueda
THEN el consolidador y todo lo que consume el universo no requieren modificación

GIVEN la fuente sin demora activa
WHEN se muestra la barra de estado del dato
THEN declara la demora real de la nueva fuente, no la de 20 minutos de la anterior
```

---

#### F-054 — Información pública del emisor desde CNV y SEC

**Etiqueta:** Stage 2 · **Traza a:** "Fuera del MVP"

**Descripción.** Al seleccionar un ticker se abre un modal con los números duros del último balance
del emisor, extraídos del regulador que le corresponde: **CNV** para emisores argentinos (ONs y
acciones locales), **SEC** para CEDEARs y emisores extranjeros. Cuatro magnitudes: resultado del
ejercicio, patrimonio neto, deuda financiera / EBITDA y liquidez corriente.

**Complementa el eje crédito** del vector de seis ejes: se muestra al lado de la calificación, con su
propia fuente y su propia fecha, y **no se combina en un score compuesto** (regla 7). Es el insumo
para nombrar el riesgo que se asume al mejorar una TIR (regla 8).

La investigación de fuentes está cerrada y verificada en vivo:
**`claude-docs/planning/investigacion-cnv-sec.md`**. Lo esencial:

- Las páginas de CNV son **HTML servido** — `curl` plano alcanza, no hace falta navegador headless.
- El balance viene como **XML embebido** con el plan de cuentas estandarizado de la CNV, y los códigos
  `8000000–8000029` traen **los ratios ya calculados y declarados por el emisor** (EBITDA, LIQUIDEZ,
  DEUDA FINANCIERA/EBITDA, SOLVENCIA, ROE, ROA). Se toman como los publica la fuente (regla 11).
- La SEC expone **XBRL gratis y sin clave** (`data.sec.gov/api/xbrl/companyfacts/`), pero hay que leer
  **`us-gaap` y `ifrs-full`**: los foreign private issuers reportan bajo IFRS y con sólo `us-gaap`
  aparecen falsamente vacíos.
- El puente ticker → emisor sale de las **tablas de valuación de Bienes Personales de AFIP/ARCA**
  (ticker, denominación, CUIT, clase). BYMA no sirve —`securityDesc` viene vacío— y derivar la clase
  del número del ticker **se descartó por medición**: funciona para Cresud y no para IRSA.
- **Cero IA en runtime**: `httpx` + parsers determinísticos, punta a punta (regla 6).

**Input:** ticker del monitor, del armador o de la ficha; tabla de valuación AFIP/ARCA.
**Output:** modal con los números del emisor, cada uno con fuente, fecha y —cuando corresponde— la
aclaración de si lo declaró el emisor o lo derivamos nosotros.
**Depende de:** F-039 (el drawer y su navegación), F-031 (el eje crédito al que acompaña)
**Habilita:** —

**RICE:** R = 300 · I = 2 · C = 80 % · E = 8 → **Score 60**
*Confidence 80 %: las dos fuentes están verificadas en vivo; queda abierto el 503 de
`blob.cnv.gov.ar` para los prospectos y el 14 % de emisiones sin nombre de emisor.*

**Ejecución.** En esta fase corre **estrictamente a pedido**. La tarea programada diaria es Stage 2.
Antes de implementar se hace un paso a paso conjunto con links reales —un emisor de CNV y uno de la
SEC— para validar el flujo contra la fuente.

```
GIVEN una ON de un emisor argentino con ficha en CNV
WHEN se abre el modal del ticker
THEN los cuatro números salen del último balance publicado, cada uno con su fecha de presentación

GIVEN un emisor cuyo balance declara los ratios en los códigos 8000000-8000029
WHEN se muestra deuda financiera / EBITDA y liquidez corriente
THEN se muestra el valor tal como lo declaró el emisor, sin recalcularlo

GIVEN un CEDEAR de un foreign private issuer que reporta bajo IFRS
WHEN se consulta companyfacts de la SEC
THEN se leen las etiquetas de ifrs-full y el emisor no aparece como sin datos

GIVEN un banco, que no publica balance clasificado por naturaleza
WHEN se muestra liquidez corriente
THEN dice "no aplica" y no un faltante

GIVEN un ticker cuya emisión no tiene nombre de emisor en condiciones_emision.csv
WHEN se abre el modal
THEN el espacio va vacío y el faltante se declara con nombre y apellido; no se infiere el emisor
```

---

#### F-055 — Descarga automática del informe diario de IAMC

**Etiqueta:** Stage 2 · **Traza a:** F1 (reactiva F-005)

**Descripción.** IAMC se pausó el 13/08/2026 porque el informe llegaba a mano y envejecía. Esta
feature lo reactiva sacando la parte manual: la corrida matinal baja el informe del día antes de
parsearlo, y si no lo consigue **lo declara** en vez de reusar el anterior en silencio.

El flujo está verificado en vivo (13/08/2026) y no necesita navegador headless ni credencial:

```
GET iamc.com.ar/Informe/InformeDiarioDeudaCorporativa{DDMMAAAA}/
  → href a iamcweb.prod.ingecloud.com/TempFiles/{uuid}.pdf
GET ese PDF → 200 · application/pdf · ~7 MB
```

Se probó con tres fechas distintas (12/08, 05/08, 03/08) y cada una resolvió a un PDF propio, así
que la fecha en la URL manda de verdad. El `{uuid}` es efímero: se resuelve en cada corrida, no se
guarda.

Lo que hoy falta y esta feature agrega, además de la descarga: **exponer la fecha del informe**. La
columna `fecha_metricas` ya existe en `precios` pero no llega ni a `/estado-del-dato` ni a la ficha
del instrumento. Sin eso, un día que la descarga falle vuelve el problema original —una TIR vieja
sin rótulo—, así que las dos cosas van juntas.

**Input:** la web pública de IAMC.
**Output:** informe del día parseado en cada corrida matinal, con su fecha declarada en pantalla.
**Depende de:** F-005 (el parser, que quedó entero), F-008 (la corrida programada)
**Habilita:** devuelve las 35 emisiones con rendimiento, la convexidad y el valor residual

**RICE:** R = 300 · I = 2 · C = 90 % · E = 3 → **Score 180**
*Confidence 90 %: el flujo de descarga está verificado en vivo; el riesgo es que IAMC cambie el
HTML de la página, que es el mismo riesgo que ya corre el parser del PDF.*

```
GIVEN la corrida matinal y el informe del día publicado en IAMC
WHEN corre la ingesta
THEN lo descarga, lo parsea y el universo queda con las métricas de hoy

GIVEN IAMC sin publicar todavía el informe del día
WHEN corre la ingesta
THEN se conserva el último informe válido y la pantalla declara de qué fecha es, con su antigüedad

GIVEN un informe cuya fecha es anterior a la de la corrida
WHEN se muestran TIR, duración, paridad o convexidad
THEN cada una declara la fecha del informe del que salió, no la del snapshot de precios
```

---

#### F-056 — Índice CER del BCRA: tasa real de los ajustables

**Etiqueta:** Stage 2 · **Traza a:** F1

**Descripción.** Las especies CER quedan hoy sin rendimiento **de ninguna fuente** —ni cálculo
propio ni IAMC—: el cronograma trae los montos contractuales sin el coeficiente y el precio en
pesos sí lo incorpora, así que descontar uno contra otro mezclaría una punta ajustada con otra que
no lo está (ver `NATURALEZAS_FUERA` en `ingesta/consolidacion/metricas.py`). Son **48 especies**
medidas en la corrida #113.

Falta un solo dato, y es público. Verificado en vivo el 13/08/2026:
`api.bcra.gob.ar/estadisticas/v4.0/monetarias/30` — "Coeficiente de estabilización de referencia
(base 2.2.02=1)", API abierta, sin clave, serie diaria, con valores publicados hasta el 15/08.

Con el índice, ajustar el flujo y descontarlo contra el precio en pesos da la **tasa real**, que es
la unidad del segmento. **No requiere ningún supuesto**: el CER es un índice oficial, no una
proyección. Es ganancia neta de cobertura — habilita rendimiento donde hoy no hay nada, no repone
lo que se perdió al pausar IAMC.

La tasa real no se promedia ni comparte eje con una TIR en dólares ni con una TNA nominal
(regla 2): entra como su propia naturaleza, como ya lo hacen las demás.

**Input:** la variable 30 de la API de estadísticas monetarias del BCRA.
**Output:** tasa real para las especies CER, abierta por naturaleza.
**Depende de:** F-051 (la matemática de descuento ya escrita)
**Habilita:** —

**RICE:** R = 250 · I = 2 · C = 90 % · E = 4 → **Score 112,5**
*Confidence 90 %: la fuente está verificada en vivo; queda por confirmar la convención exacta de
qué fecha de CER aplica a cada cupón.*

```
GIVEN el índice CER del BCRA ingerido y una especie CER con precio y cronograma
WHEN se calculan las métricas
THEN devuelve tasa real, rotulada como tasa real y nunca como TIR en dólares

GIVEN el CER sin actualizar para la fecha que un cupón necesita
WHEN se calcula esa especie
THEN queda sin rendimiento con el motivo declarado; no se interpola ni se arrastra el último
```

---

#### F-057 — FCI en el monitor, con CAFCI como fuente

**Etiqueta:** Stage 2 · **Traza a:** F12 (extiende F-038)

**Descripción.** Los fondos comunes entran al monitor **como segmento propio**, para mirarlos — no
para valuar carteras, que es F-046. Es la primera vez que el producto muestra un FCI con un número
adelante.

**Segmento propio, no filas nuevas en la grilla de bonos.** F-038 navega con un solo segmento activo
por vez y la columna de rendimiento toma la unidad de ese segmento. Un FCI no tiene TIR ni duración:
tiene **variación de cuotaparte**, que es otra naturaleza. Por regla 2 no comparte eje ni columna con
una TIR en dólares, una tasa real CER o una TNA en pesos, y por eso entra como segmento con sus
propias columnas en vez de sumarse a la grilla existente.

**La fuente, verificada en vivo el 13/08/2026.** Sin clave, sin homologación y sin navegador headless:

```
GET https://api.pub.cafci.org.ar/pb_get
  → 200 · application/vnd.openxmlformats-officedocument.spreadsheetml.sheet · ~946 KB
  → content-disposition: attachment; filename="20260812_Planilla_Diaria_A.xlsx"
```

Trae **4.233 filas** (una por fondo × clase) × **47 columnas**, agrupadas en secciones por tipo de
renta × moneda: Renta Variable, Renta Fija, Renta Mixta, PyMEs, Infraestructura, Retorno Total, ASG,
RG900, Mercado de Dinero y Fondos Cerrados. Por fila: valor de cuotaparte actual y del día hábil
anterior con su variación, variación acumulada al mes, al año y a doce meses, cantidad de cuotapartes,
patrimonio, market share, plazo de liquidación, las seis comisiones y honorarios, mínimo de inversión,
calificación, Código CAFCI, Código CNV, sociedad gerente y sociedad depositaria.

**La fecha del dato viene en el nombre del archivo**, que es el problema que F-055 tuvo que resolver
aparte para IAMC: acá `20260812_` la declara la propia fuente. La planilla del día trae el cierre del
día hábil anterior — el valor de cuotaparte se publica al cierre, y ese desfasaje se muestra, no se
disimula.

**No hay histórico.** `pb_get` ignora todo parámetro que se le pase —se probó `?fecha=`, `?date=`,
`?f=` y `?tipo=`, y las cuatro devuelven el mismo archivo del último día hábil—. El `?d=` que usa la
propia web de CAFCI es cache-busting, no selector de fecha. La serie se construye acumulando
snapshots en cada corrida, igual que ya se hace con precios; el día que la corrida falle, esa fecha
queda como hueco declarado y no se interpola.

**Las cuatro salvedades, que son las reglas del proyecto aplicadas a esta fuente.**

- **`USB` no se traduce.** Las monedas vienen `ARS` (2.967 filas), `USD` (1.139) y `USB` (127). `USB`
  no existe en ISO 4217: es un código propietario de CAFCI. Que la sección se llame "Dólar
  Estadounidense Billete" **sugiere** qué es, pero el rótulo de una sección no es una especificación
  publicada. Se muestra `USB` y todo número que dependa de interpretarlo va vacío — es el mismo
  criterio que ya rige para `EXT` de BYMA (regla 11).
- **La columna `Reexp.Pesos` no se ingiere.** Se midió su cociente contra el valor original en las
  1.262 filas no-ARS y **el tipo de cambio implícito no es único**: 1526,68 · 1525,38 · 1491,50 según
  el fondo. Es un TC de fuente externa, inconsistente entre filas y no auditable, y la regla 3 exige
  derivar el TC del propio universo. Se descarta la columna entera; los fondos no-ARS se muestran en
  su moneda de cotización, sin convertir.
- **`Moneda` y `Moneda Fondo` son columnas distintas y no coinciden** —ARS 2.967 contra 3.149, USD
  1.139 contra 963, USB 127 contra 121—. CAFCI no publica en qué se diferencian. Se ingieren las dos,
  se muestra la que corresponde al eje de clasificación y la discrepancia se declara donde exista; no
  se elige una "correcta" por criterio propio.
- **`Plazo Liq.` trae centinelas sin documentar**: además de 0, 1, 2, 3, 5 y 10 días aparecen `999`
  (15 filas), `9999` (5), `99999` (1) y `-1` (4). No se traducen a "no aplica" ni a "indefinido": se
  muestra el valor tal como viene, y si no es un plazo interpretable el espacio de "días para
  rescatar" va vacío.

**Lo que la propia fuente declara sobre sí misma, y va en pantalla.** El reporte se rotula *"Planilla
Diaria (Valores sujetos a revisión)"* y cierra con esta advertencia: *"Los rendimientos atribuidos en
el informe a los distintos Fondos han sido calculados sin tener en consideración los pagos de
distribución de utilidades que pudieran haber ocurrido"*. Las dos cosas se muestran junto a las
variaciones — un fondo que distribuyó utilidades tiene la variación subestimada, y el asesor tiene que
verlo. La calificación viene en 1.992 de 4.233 filas (47 %); el resto se marca como no informada, no
como vacía.

**Nada de esto pasa por el consolidador del universo.** Un FCI no es una especie negociable con puntas
y volumen: no se deduplica contra tickers (F-011), no entra a la sanidad de precios de renta fija
(F-010) ni al cálculo de TIR (F-051). Tabla propia, ingesta propia, segmento propio.

**Input:** la planilla diaria pública de CAFCI.
**Output:** segmento FCI en el monitor, con valor de cuotaparte, variaciones, patrimonio, costos y
plazo de liquidación, cada campo con su fecha y sus salvedades declaradas.
**Depende de:** F-038 (el monitor y su navegación por segmento), F-013 (la barra de estado del dato),
F-008 (la corrida programada)
**Habilita:** F-046

**RICE:** R = 300 · I = 2 · C = 85 % · E = 6 → **Score 85**
*Confidence 85 %: la fuente se descargó y se parseó punta a punta el 13/08/2026 —no sólo se verificó
que respondiera—, y no requiere clave. El 15 % restante es el mismo riesgo que ya corre el parser de
IAMC: que CAFCI cambie el layout del XLSX, que acá tiene encabezado en dos filas con celdas combinadas
y filas de sección intercaladas entre los datos.*

**Ejecución.** Antes de implementar conviene un paso a paso conjunto sobre la planilla real, como se
acordó para F-054: qué columnas de las 47 entran al monitor y cuáles quedan afuera es una decisión de
producto, no de ingesta.

```
GIVEN la corrida matinal y la planilla diaria publicada por CAFCI
WHEN corre la ingesta
THEN el segmento FCI del monitor queda con los valores de esa planilla, y la pantalla declara la
     fecha que trae el nombre del archivo

GIVEN CAFCI sin publicar todavía la planilla del día
WHEN corre la ingesta
THEN se conserva la última planilla válida y la pantalla declara de qué fecha es, con su antigüedad

GIVEN el segmento FCI activo en el monitor
WHEN se lo mira
THEN la columna de rendimiento es variación de cuotaparte, nunca TIR, y no hay ninguna fila de renta
     fija ni de renta variable en la misma grilla

GIVEN un fondo con moneda USB
WHEN se lo muestra
THEN dice USB, no dice "dólar billete", y no se convierte a pesos por ninguna vía

GIVEN un fondo en moneda distinta de ARS
WHEN se muestra su valor de cuotaparte
THEN se muestra en su moneda, y la columna Reexp.Pesos de la fuente no se usa ni se guarda

GIVEN las variaciones de cuotaparte de cualquier fondo
WHEN se las muestra
THEN va visible la advertencia de la fuente de que no consideran distribución de utilidades

GIVEN un fondo cuyo Plazo Liq. viene 999, 9999, 99999 o -1
WHEN se muestra el plazo de rescate
THEN el espacio va vacío y el faltante se declara; no se traduce a "no aplica" ni a "indefinido"

GIVEN un fondo sin calificación en la planilla
WHEN se abre el segmento
THEN el campo aparece marcado como no informado, y no vacío ni inferido del tipo de renta
```

---

### Bloque P — Paridad competitiva con Docta Terminal (F-058 … F-070)

Salen del relevamiento de `app.docta.com.ar` del 13/08/2026, documentado en
**`claude-docs/planning/analisis-docta.md`**. Ese archivo tiene el mapa de las 32 rutas, las 78
columnas de sus tablas y —lo que más importa— el cruce de cada feature contra el dato que necesita y
contra si lo tenemos.

**Tres cosas que el relevamiento dejó claras y valen para todo el bloque.**

Primero, **tres de estas features dependen de tener serie, no de conseguir una fuente** (F-061, F-062
y el flujo neto de F-067). La acumulación propia ya está resuelta y no hay nada que decidir:
`public.precios` tiene `PRIMARY KEY (ticker, capturado_en)`, así que cada corrida agrega fila en vez
de pisar y la historia se viene guardando desde la primera. Para **acciones y CEDEARs** hay además
historia externa disponible hoy —data912 da hasta 23 años, ya hay cliente en
`backend/app/externos/data912.py`—, pero con el contrato de `app/externos/`: se consulta al hacer
clic, se muestra rotulada con su fuente y **no se persiste ni se mezcla con nuestro dato**. Para
**bonos** no hay equivalente, y la curva histórica de TIR no podría venir de afuera aunque lo hubiera:
la TIR es cálculo nuestro contra el cronograma. De ahí sale la regla común a todo el bloque: cada
gráfico declara desde qué fecha hay datos, en vez de arrancar donde le convenga.

Segundo, **buena parte de lo que Docta hace ya está planificado acá**: el calendario consolidado es
F-015/F-016, el screener con filtros es F-017, la exportación es F-042, las opciones son F-047, y la
ficha de instrumento es F-039. Este bloque sólo contiene lo que **no** estaba.

Tercero, **nada de lo que ofrecen resuelve el Flujo B.** Tienen monitor, calculadoras y registro de
tenencias; no tienen un optimizador que proponga rotaciones con su costo real y su contrapartida de
riesgo nombrada. El diferenciador del proyecto sigue en pie.

---

#### F-058 — Carry trade: calculadora, tabla y breakeven

**Etiqueta:** Stage 2 · **Traza a:** análisis Docta §2.1

**Descripción.** La operación más consultada del mercado local: vender dólares, comprar un instrumento
en pesos, mantenerlo al vencimiento y recomprar dólares. Tres piezas.

**La calculadora.** Entradas: ticker, tipo de cambio inicial, nominales, precio del bono y el tipo de
cambio al vencimiento en dos escenarios. Salidas: valor final por cada tipo de cambio, tasa directa y
TIR. El supuesto de la operación va escrito en pantalla, no implícito en el número.

**La tabla.** Una fila por instrumento del segmento: vencimiento, días al vencimiento, retorno total,
máxima variación tolerable, spread contra el tipo de cambio y precio de salida.

**La curva de breakeven.** El tipo de cambio al cual el carry deja de convenir, por instrumento. Es la
regla 8 hecha gráfico: no muestra una ganancia sin mostrar a qué tipo de cambio se evapora.

**El escenario lo tipea el asesor.** Docta publica bandas proyectadas con un supuesto de inflación
propio; **eso no se replica**. Se muestran las bandas **publicadas** por el BCRA, y el tipo de cambio
futuro es un input del asesor, rotulado como supuesto suyo. Un número que depende de un supuesto se
muestra junto al supuesto que lo produjo, o no se muestra.

**Input:** universo con precios; cronograma contractual; bandas cambiarias publicadas por el BCRA.
**Output:** calculadora, tabla y curva de breakeven por segmento.
**Depende de:** F-051 (TIR y cronograma), F-012 (tipo de cambio implícito), F-056 (el cliente de la
API del BCRA, que esta feature reusa)
**Habilita:** —

**RICE:** R = 300 · I = 3 · C = 70 % · E = 8 → **Score 78,8**
*Confidence 70 %: la aritmética es nuestra y el cronograma está, pero la serie de bandas cambiarias
del BCRA no se verificó en vivo todavía. La API de estadísticas monetarias ya está probada para el
CER (F-056), así que el riesgo es de disponibilidad de la serie, no de acceso.*

```
GIVEN un ticker, nominales y un tipo de cambio de salida tipeado por el asesor
WHEN se calcula el carry
THEN devuelve valor final, tasa directa y TIR, y declara en pantalla que el tipo de cambio de salida
     es un supuesto del asesor y no un dato de mercado

GIVEN la curva de breakeven de un segmento
WHEN se la mira
THEN cada instrumento muestra el tipo de cambio al cual su carry se anula, y ningún instrumento de
     otra naturaleza de tasa aparece en la misma curva

GIVEN las bandas cambiarias del BCRA
WHEN se las grafica
THEN se muestran las publicadas, con su fecha; ninguna banda proyectada se dibuja como si fuera dato

GIVEN un instrumento sin cronograma contractual
WHEN se arma la tabla de carry
THEN queda fuera con el motivo declarado, y no se le estima el flujo
```

---

#### F-059 — Comparador de dos instrumentos con la misma vara

**Etiqueta:** Stage 2 · **Traza a:** análisis Docta §2.2 · absorbe la candidata "spread por
legislación" de la sección 11

**Descripción.** Dos instrumentos lado a lado, medidos con la misma convención y con la diferencia
explícita. El par canónico es AL30 contra GD30 —misma emisión, distinta legislación—, y de ahí sale el
spread por ley que la sección 11 ya tenía anotado como candidata.

Cuatro paneles: **cashflows superpuestos**, **evolución de ambos** más la serie del cociente, la
**calculadora comparativa**, y las **diferencias**.

La calculadora expone las convenciones como parámetros en vez de esconderlas: fecha de operación, tipo
de liquidación (CI / 24hs) y convención de tasa. Devuelve por instrumento precio dirty, paridad, TIR,
TNA, duración, intereses corridos y días al vencimiento; y después **Diferencia TIR** y **Diferencia
TNA**, que son el número que el asesor busca.

**Las combinaciones rápidas son parte de la feature**, no decoración: pares preseleccionados que valen
la pena mirar —Bonar contra Global del mismo año, CER contra dólar linked, ONs del mismo sector—.
Ninguna se arma derivando familia del prefijo del ticker: se arman sobre `subtipo`, que ya distingue
global de bonar por ley, y sobre `sector` de `condiciones_emision`.

**Sólo compara lo comparable.** Dos instrumentos de distinta naturaleza de tasa pueden ponerse lado a
lado —es útil ver una CER contra una dólar linked— pero **la diferencia de TIR no se calcula entre
naturalezas distintas**: ahí el campo va vacío y dice por qué. La regla 2 no se suspende porque las
dos columnas entren en la misma pantalla.

**Input:** universo con precios; cronograma; `subtipo` y `sector`.
**Output:** panel comparativo de dos instrumentos con diferencias explícitas.
**Depende de:** F-051, F-039
**Habilita:** —

**RICE:** R = 350 · I = 3 · C = 90 % · E = 5 → **Score 189**
*Confidence 90 %: toda la matemática ya está escrita en F-051 y el cronograma está persistido. Lo
único nuevo es la presentación y las convenciones de liquidación.*

```
GIVEN dos bonos hard dollar del mismo vencimiento y distinta ley
WHEN se los compara
THEN muestra las dos TIR, las dos duraciones y la diferencia en puntos básicos, con la ley de cada uno
     visible al lado del número

GIVEN dos instrumentos de distinta naturaleza de tasa
WHEN se los pone lado a lado
THEN cada columna muestra su rendimiento rotulado con su naturaleza, y la fila de diferencia de TIR
     va vacía declarando que no son unidades comparables

GIVEN una fecha de operación y un tipo de liquidación elegidos
WHEN se recalcula
THEN los intereses corridos y el precio dirty de los dos instrumentos usan esa misma convención, y la
     convención usada queda visible

GIVEN un par sugerido por las combinaciones rápidas
WHEN se lo abre
THEN el emparejamiento sale de subtipo y sector declarados, nunca del prefijo del ticker
```

---

#### F-060 — Navegación por categoría de emisor × naturaleza de tasa

**Etiqueta:** Stage 2 · **Traza a:** análisis Docta §1

**Descripción.** El monitor de F-038 navega por segmento. Docta navega por **categoría de emisor ×
naturaleza de tasa** —soberanos / subsoberanos / corporativos, cruzado con hard dollar, tasa fija, CER,
UVA, dollar linked, badlar, tamar y bopreal—, con una pantalla por combinación.

Es un eje más fino que el nuestro y **es el mismo criterio de la regla 2 llevado a la navegación**: si
dos instrumentos no comparten unidad de rendimiento, no comparten pantalla. Que un competidor con años
de uso haya llegado a la misma estructura por su cuenta es la mejor validación que tiene esa decisión.

Adoptarlo es barato: `tipo_tasa` ya sale del cronograma y `subtipo_de()` ya distingue por ley. Lo que
falta es la navegación de dos ejes y que cada combinación vacía se declare como vacía en vez de
mostrar una tabla en blanco.

**Input:** universo consolidado con `tipo_tasa` y `subtipo`.
**Output:** navegación de dos ejes en el monitor, con conteo por celda.
**Depende de:** F-038
**Habilita:** F-062

**RICE:** R = 400 · I = 2 · C = 90 % · E = 3 → **Score 240**

```
GIVEN el monitor abierto
WHEN se elige categoría de emisor y naturaleza de tasa
THEN la grilla muestra sólo esa combinación, y la columna de rendimiento lleva la unidad de esa
     naturaleza

GIVEN una combinación sin instrumentos
WHEN se la selecciona
THEN se declara que no hay instrumentos en esa combinación, con el conteo en cero visible

GIVEN un instrumento sin tipo_tasa declarado
WHEN se arma la navegación
THEN cae en una celda de "naturaleza no declarada" y se cuenta ahí; no se lo asigna por parecido
```

---

#### F-061 — Rendimientos históricos por ventana temporal

**Etiqueta:** Stage 2 · **Traza a:** análisis Docta §4, fila 15

**Descripción.** Variación acumulada por ticker en ventanas de 1 día, 1 semana, 1 mes, 3 meses, 6
meses, 1 año y año a la fecha, en pesos y en dólares, y —para bonos— con precio clean o dirty.

**Depende de tiempo, no de una fuente.** La serie se construye con los cierres diarios que persiste
F-073. Ojo: la versión original de esta ficha decía que `precios` "ya acumula una fila por especie y
por corrida", y eso es falso desde que la poda de consolidación deja una sola fila por ticker
(`serie_historica_habilitada=false`, su default) — sin F-073 esta feature no tiene insumo. Una
ventana de un año exige un año de cierres: hasta entonces la ventana existe pero se declara
incompleta, con la fecha del primer cierre a la vista. **No se rellena** con precios reconstruidos ni
empalmando la serie de un tercero.

**El histórico de data912 no sirve para esta feature, y conviene decir por qué.** Cubre acciones y
CEDEARs con años de profundidad, pero su contrato (`app/externos/`) es consulta por especie al hacer
clic, sin persistir ni mezclar con nuestro dato. Un ranking por ventana sobre el panel entero exigiría
una consulta por cada especie y produciría una tabla que mezcla serie externa con serie propia. Sirve
para el sparkline de una ficha; no para esta grilla.

**Input:** serie de cierres diarios persistida por F-073.
**Output:** tabla de rendimientos por ventana, por segmento.
**Depende de:** F-073, F-012 (para la vista en dólares)
**Habilita:** —

**RICE:** R = 300 · I = 2 · C = 60 % · E = 5 → **Score 72**
*Confidence 60 %: la implementación es simple; la incertidumbre es cuándo hay suficiente historia
para que la pantalla sirva.*

```
GIVEN una ventana temporal más larga que la historia acumulada
WHEN se la muestra
THEN el valor va vacío y declara desde qué fecha hay datos; no se calcula sobre una ventana parcial
     presentándola como completa

GIVEN la vista en dólares
WHEN se convierte la serie
THEN se usa el tipo de cambio derivado del universo de cada fecha, nombrando el par, y no el de hoy
     aplicado a toda la serie
```

---

#### F-062 — Curva histórica del segmento

**Etiqueta:** Stage 2 · **Traza a:** análisis Docta §4, fila 16

**Descripción.** Cómo se movió la curva TIR/duración de un segmento a lo largo del tiempo: la foto de
F-023 convertida en película. Sirve para ver si una TIR alta es alta contra el propio historial del
instrumento o sólo contra sus pares de hoy.

Misma restricción que F-061: **se dibuja desde la primera corrida guardada y el eje lo dice**. Una
curva histórica de tres semanas es ruido con ejes.

**Input:** serie de TIR y duración por ticker persistida por F-073.
**Output:** curva del segmento con selector de fecha y comparación contra hoy.
**Depende de:** F-073, F-023, F-060
**Habilita:** —

**RICE:** R = 250 · I = 2 · C = 60 % · E = 4 → **Score 75**

```
GIVEN una fecha anterior a la primera corrida guardada
WHEN se la elige en el selector
THEN no se dibuja nada y se declara desde cuándo hay datos

GIVEN una curva de un segmento en dos fechas
WHEN se las superpone
THEN las dos son de la misma naturaleza de tasa, y la fecha de cada una está rotulada sobre su serie
```

---

#### F-063 — Heatmap del panel

**Etiqueta:** Stage 2 · **Traza a:** análisis Docta §1

**Descripción.** La variación del día como mapa de calor, dimensionado por volumen operado. Docta lo
tiene en acciones, CEDEARs, futuros, opciones y bonos. Es lectura de un vistazo: qué se movió hoy y
cuánto se operó.

No agrega ningún dato que el monitor no tenga; agrega velocidad de lectura. Por eso el Impact es 1.

**Input:** snapshot del día contra el cierre anterior.
**Output:** heatmap por panel, con la variación y el volumen.
**Depende de:** F-038
**Habilita:** —

**RICE:** R = 250 · I = 1 · C = 90 % · E = 3 → **Score 75**

```
GIVEN el heatmap de un panel
WHEN se lo mira
THEN el color codifica variación del día y el tamaño codifica volumen operado, con la escala de las
     dos cosas visible

GIVEN un instrumento sin cierre anterior con el cual comparar
WHEN se arma el heatmap
THEN aparece en gris declarado como sin variación calculable, y no como variación cero
```

---

#### F-064 — Watchlist

**Etiqueta:** Stage 2 · **Traza a:** análisis Docta §1

**Descripción.** Un conjunto de tickers marcados por el asesor, que atraviesa todas las pantallas. No
tiene lógica financiera: es persistencia por asesor y un filtro. La razón por la que puntúa alto no es
su valor sino su costo: sale casi gratis sobre el aislamiento de F-014.

**Input:** selección del asesor.
**Output:** lista propia por asesor, filtrable en el monitor.
**Depende de:** F-014, F-038
**Habilita:** —

**RICE:** R = 300 · I = 1 · C = 100 % · E = 2 → **Score 150**

```
GIVEN dos asesores con watchlists distintas
WHEN cada uno consulta la suya
THEN ninguno ve la del otro, verificado consultando la API directamente
```

---

#### F-065 — Cauciones

**Etiqueta:** Stage 2 · **Traza a:** análisis Docta §4, fila 9

**Descripción.** La curva de tasas de caución por plazo. Es el instrumento de liquidez de corto del
mercado local y la referencia contra la cual se mide si conviene quedarse corto.

**Hay que ingerirlo.** La ingesta usa cinco endpoints de BYMA —`negociable-obligations`,
`public-bonds`, `cedears`, `general-equity`, `leading-equity`— y el de cauciones no está entre ellos.
Verificar si BYMA lo publica en la API abierta es el primer paso, y **si no lo publica, la feature no
se construye**: no hay caución que derivar de otra cosa.

**Input:** panel de cauciones de BYMA, por verificar.
**Output:** curva de tasas por plazo.
**Depende de:** F-004
**Habilita:** —

**RICE:** R = 200 · I = 1 · C = 60 % · E = 4 → **Score 30**
*Confidence 60 %: no se verificó que BYMA publique cauciones en la API abierta.*

```
GIVEN el panel de cauciones ingerido
WHEN se muestra la curva
THEN cada punto lleva su plazo y su volumen, y la tasa se muestra en la convención que publica la
     fuente, sin anualizar por cuenta propia

GIVEN que BYMA no publica cauciones en la API abierta
WHEN se planifica el ciclo
THEN la feature no se construye y la ausencia se declara; no se deriva la tasa de otra fuente
```

---

#### F-066 — Futuros de dólar

**Etiqueta:** Stage 2 · **Traza a:** análisis Docta §4, fila 10

**Descripción.** La curva de futuros de dólar con su tasa implícita por contrato. Es el complemento
natural de F-058: el carry trade se mide contra lo que el mercado ya está pagando por cubrirse.

**Fuente por identificar.** No está en los cinco endpoints que ingerimos y no se verificó si BYMA lo
publica. La tasa implícita **se calcula** contra el spot derivado de nuestro propio universo (regla 3),
nunca contra un tipo de cambio de fuente externa.

**Input:** una fuente de futuros de dólar, por identificar.
**Output:** curva de futuros con tasa implícita por contrato.
**Depende de:** F-004, F-012
**Habilita:** —

**RICE:** R = 200 · I = 1 · C = 50 % · E = 4 → **Score 25**
*Confidence 50 %: sin fuente verificada al 13/08/2026.*

```
GIVEN la curva de futuros y el spot derivado del universo
WHEN se calcula la tasa implícita de cada contrato
THEN se declara contra qué par se derivó el spot, y no se usa ningún tipo de cambio externo
```

---

#### F-067 — FCI: comparador, categorías y gestoras

**Etiqueta:** Stage 2 · **Traza a:** análisis Docta §1 · extiende F-057

**Descripción.** Tres vistas más sobre los datos que F-057 ya ingiere, sin fuente nueva:

- **Comparador** de fondos lado a lado, con la misma lógica de F-059.
- **Categorías**: AUM por categoría, participación y cantidad de fondos. Sale de agregar la planilla
  por su columna de clasificación.
- **Gestoras**: lo mismo por sociedad gerente, más el flujo neto a 30 días y en el año.

**El flujo neto no sale de la planilla.** Es la diferencia de patrimonio entre dos fechas, así que
depende de historia acumulada igual que F-061. Las otras dos vistas funcionan desde la primera corrida;
el flujo aparece cuando haya treinta días guardados, y hasta entonces la columna se declara vacía.

**Input:** la planilla diaria de CAFCI ingerida por F-057.
**Output:** comparador, agregado por categoría y agregado por gestora.
**Depende de:** F-057, F-059
**Habilita:** —

**RICE:** R = 250 · I = 2 · C = 85 % · E = 5 → **Score 85**

```
GIVEN menos de treinta días de planillas acumuladas
WHEN se muestra el flujo neto de una gestora
THEN la columna va vacía y declara desde qué fecha hay datos; no se calcula sobre la ventana parcial

GIVEN el agregado por categoría
WHEN se suma el AUM
THEN sólo se suman fondos de la misma moneda, y la moneda del total está rotulada; los fondos USB no
     se suman con los USD

GIVEN dos fondos de categorías distintas
WHEN se los compara
THEN sus variaciones se muestran lado a lado sin calcular diferencia, porque no son la misma unidad
```

---

#### F-068 — Panel de dólar y spreads

**Etiqueta:** Stage 2 · **Traza a:** análisis Docta §1 · promueve la candidata de la sección 11

**Descripción.** Los tipos de cambio implícitos que **F-012 ya calcula desde el Ciclo 1 y que no se
muestran en ninguna pantalla**. Es la feature de mejor relación valor/esfuerzo de todo el bloque: el
cálculo está hecho y verificado —0,14 % de desvío contra el Índice Dólar de BYMA—, falta la pantalla.

Cada tarjeta muestra el número **junto al par que lo produjo** (`AL30 ÷ AL30D`), que es lo que lo hace
auditable en vez de mágico. Rotular por el par y no por "MEP" o "cable" no es un detalle de estilo: es
la regla 11: nombrarlos sería declarar una interpretación que la fuente no publica.

Incluye la serie histórica del spread entre implícitos a medida que se acumule, con la misma
restricción de F-061.

**Input:** tipos de cambio implícitos de F-012.
**Output:** panel con las tarjetas de cada implícito y su spread, cada una nombrando su par.
**Depende de:** F-012, F-038
**Habilita:** —

**RICE:** R = 400 · I = 2 · C = 100 % · E = 3 → **Score 266,7**

```
GIVEN una tarjeta de tipo de cambio implícito
WHEN se la muestra
THEN dice el par que lo produjo y el precio de cada pata, y no lo rotula con un nombre de mercado que
     la fuente no declara

GIVEN el Índice Dólar publicado por BYMA
WHEN se lo muestra
THEN aparece como contraste con su fuente declarada, nunca como el origen del número propio
```

---

#### F-069 — Top ganadores y perdedores del día

**Etiqueta:** Stage 2 · **Traza a:** análisis Docta §1

**Descripción.** Los diez que más subieron y los diez que más bajaron, por panel. Es la puerta de
entrada de la mañana: qué pasó hoy, antes de buscar nada en particular.

**Se rankea dentro del panel, nunca entre paneles.** Un ranking que mezcle un bono en pesos con un
CEDEAR en dólares compara variaciones que no son la misma cosa.

**Input:** snapshot del día contra el cierre anterior.
**Output:** dos listas por panel.
**Depende de:** F-038
**Habilita:** —

**RICE:** R = 300 · I = 1 · C = 100 % · E = 2 → **Score 150**

```
GIVEN los rankings del día
WHEN se los arma
THEN cada uno se calcula dentro de un panel y de una moneda de cotización, y el rótulo lo declara

GIVEN un instrumento sin volumen operado en el día
WHEN se arma el ranking
THEN queda fuera, porque una variación sin operaciones no es un movimiento de mercado
```

---

#### F-070 — Tenencias con P&L por lote

**Etiqueta:** Stage 2 · **Traza a:** análisis Docta §2.3 · **decisión de producto pendiente**

**Descripción.** Registro de compras y ventas con posición consolidada, valor total, resultado diario y
ganancia no realizada, con costo por lote.

**Esta ficha se anota, pero no se recomienda sin decisión previa.** El riesgo R16 del plan dice que
*"se guardan carteras, no clientes"* es una frontera de producto y que las fronteras se erosionan de a
un campo por vez. Un registro de transacciones con resultado por lote no es el armador: es seguimiento
de posiciones reales, y empuja el producto hacia el CRM (F-043) y hacia el back-office —que es
justamente el otro producto de Docta, DPM, y otro negocio—.

Además arrastra una obligación nueva: el resultado por lote exige guardar **precio y fecha de cada
operación de un cliente real**, y eso son datos que por regla del proyecto no entran al repositorio y
hoy no se persisten en ninguna forma.

Si se construye, va **después** de F-043 y no antes: el orden inverso deja transacciones huérfanas sin
a quién pertenecer.

**Input:** operaciones cargadas por el asesor; precios del universo.
**Output:** posición consolidada con resultado realizado y no realizado.
**Depende de:** F-041, F-043
**Habilita:** —

**RICE:** R = 200 · I = 2 · C = 40 % · E = 12 → **Score 13,3**
*Confidence 40 %: no es incertidumbre técnica sino de producto — no está decidido que el producto deba
hacer esto, y el plan tiene una frontera declarada que lo desaconseja.*

```
GIVEN una posición con tres compras a precios distintos y una venta
WHEN se calcula el resultado realizado
THEN el criterio de imputación de lotes está declarado en pantalla, y el mismo criterio se usa en
     todos los cálculos

GIVEN datos de operaciones de un cliente real
WHEN se los persiste
THEN nunca quedan en el repositorio de código
```

---

#### F-071 — Calculadora de canjes y prorrateo de órdenes a mesa

**Etiqueta:** Stage 2 · **Traza a:** herramienta operativa real del asesor (Excel de canjes/ops),
relevada el 17/08/2026 — no viene de una F1-F13 del `product-definition.md` ni del análisis Docta,
sino de cómo el asesor ya arma y comunica operaciones hoy.

**Descripción.** Dos calculadoras chicas, hoy en un Excel personal, que el asesor usa para pasarle
operaciones a la mesa más rápido y con menos error de cálculo a mano. Se relevaron celda por celda
(fórmulas reales, no sólo los valores) contra el archivo `Libro.xlsx` del asesor y se verificaron
contra sus propios resultados.

**1) Canje MEP↔Cable.** Dos bloques espejados (MEP a Cable / Cable a MEP). El asesor carga el monto
en USD, el precio que da la mesa (spread, puede ser negativo) y la comisión del IFA; la calculadora
devuelve el precio final al cliente (mesa + comisión) y cuánto USD del otro tipo se le acredita:
`Monto × (1 − precio final)` en el sentido MEP→Cable, `Monto × (1 + precio final)` en el sentido
inverso — el signo se invierte porque la operación va para el otro lado. La comisión bruta del IFA
sale aparte, sin componer con el precio: `Monto × Comisión`.

**2) Prorrateo de una orden entre cuentas ("Ops").** El asesor carga, por ticker, el precio de mesa
y la comisión (de ahí sale el precio cliente); carga cada cuenta con su comitente y su disponible en
ARS; y para cada combinación cuenta+activo asigna un % del disponible de esa cuenta. La calculadora
trunca — nunca redondea para arriba — cuántos VN entran en ese monto (`REDONDEAR.MENOS(monto /
precio cliente, 0)`), declara el remanente en pesos que quedó sin poder colocarse por el truncamiento,
y sólo corre la cuenta si está marcada para operar. Al final suma el VN de todas las cuentas que
operan un mismo ticker, arma el texto de la orden ("Comprar 6.657 VN AO28") para pasarle a la mesa, y
al lado desglosa cuánto de ese total le corresponde a cada cuenta, para poder verificar el reparto
antes de mandarlo.

**El dato de cuentas es dato de cliente real.** El bloque de "Cuentas y Disponible" del prorrateador
carga número de comitente, razón social/cuenta y disponible en ARS de clientes reales — exactamente
el tipo de dato que la regla del proyecto excluye del repositorio. La feature se diseña para que ese
bloque **viva sólo en el estado de la sesión del navegador, sin persistirse en la base**: se carga a
mano cada vez que se arma una orden, igual que hoy en el Excel, y desaparece al cerrar. Si en algún
momento se quiere guardar una lista de cuentas recurrente, eso es una extensión posterior que primero
necesita resolver dónde viven esos datos (la misma pregunta abierta que tiene F-043), no algo que esta
feature resuelve de arranque.

**Input:** precio de mesa, comisión y monto cargados a mano por el asesor (dato operativo del momento,
no viene del universo de mercado); comitente, cuenta y disponible ARS cargados a mano por sesión.
**Output:** precio final al cliente y monto acreditado en el canje; VN a comprar por cuenta y por
ticker, remanente declarado, y el texto de la orden consolidada para la mesa.
**Depende de:** F-014 (aislamiento por asesor: cada sesión es de un único asesor)
**Habilita:** —

**RICE:** R = 350 · I = 3 · C = 90 % · E = 6 → **Score 157,5**
*Confidence 90 %: la lógica entera —cada fórmula— ya está validada en el Excel que el asesor usa a
diario en producción; lo que no está probado es la UI y, sobre todo, no persistir el dato de cliente.*

```
GIVEN un canje MEP a Cable con precio mesa -2,00 % y comisión 1,50 %
WHEN se calcula
THEN el precio final al cliente es -0,50 % y el USD Cable a acreditar es el monto multiplicado por
     (1 - precio final), igual que en el Excel de referencia

GIVEN una orden de un ticker repartida entre varias cuentas con % asignado distinto
WHEN se calcula el VN por cuenta
THEN cada cuenta trunca su propio VN hacia abajo, nunca hacia arriba, y el remanente en pesos que
     no se pudo colocar por el truncamiento queda declarado, no descartado en silencio

GIVEN una cuenta no marcada para operar
WHEN se agrega el total de VN a comprar de ese ticker
THEN esa cuenta no suma al total ni aparece en la orden para la mesa

GIVEN el total de VN a comprar de un ticker entre todas las cuentas que operan
WHEN se arma el texto para pasarle a la mesa
THEN el desglose por cuenta al lado sigue sumando exactamente ese total

GIVEN comitente, cuenta y disponible ARS de un cliente real cargados en el prorrateador
WHEN se cierra la sesión o se recarga la página
THEN esos datos no quedan persistidos en la base ni en ningún archivo del repositorio
```

---

#### F-072 — Prospecto de emisión de ONs, vía CNV

**Etiqueta:** Stage 2 · **Traza a:** pedido del usuario del 17/08/2026 — subconjunto de F-054
(información pública del emisor) promovido a feature propia, porque es otra fuente y otro cliente
aunque comparta el puente emisor→CUIT.

**Descripción.** En la ficha de una ON corporativa aparece el bloque de documentos que la CNV publica
del emisor: prospectos, suplementos de prospecto, avisos de suscripción, avisos de resultado, avisos
de pago, programas globales, informes trimestrales. El asesor los ve listados y se baja el PDF real
—el mismo archivo que la CNV sirve—, sin salir de la aplicación.

**El 503 estaba mal pedido, no cerrado.** La investigación previa
(`claude-docs/planning/investigacion-cnv-sec.md`) había dejado el prospecto como pendiente por un HTTP
503 en `blob.cnv.gov.ar`. Leyendo el `site.bo.min.js` del propio sitio de la CNV se reconstruyó el
intercambio que usa la página, **público y sin login**: primero
`GET aif2.cnv.gov.ar/api/ValetKeyProvider/GetPublicValetKey/{guid}?operation=DownloadBlob`, que
devuelve un token temporal (`valetKeyData`), y después `POST blob.cnv.gov.ar/BlobWebService.svc/
DownloadBlob/{guid}` con ese token **como body form-urlencoded** —en JSON contesta 400— que devuelve
el PDF crudo. Verificado punta a punta con `curl` plano: el Suplemento de Prospecto de YPF Luz Clase
XXIV bajó como PDF real de 1.398.576 bytes, que es el "1.33 MB" que la propia CNV declara en los
metadatos del archivo. El `guid` que sirve es el del archivo adjunto, no el `uuid` de la presentación.

**Dos detalles del listado que fallan en silencio.** El listado sale de
`GET cnv.gov.ar/SitioWeb/Empresas/Empresa/{cuit}?formType=EMISIO&fdesde=1/1/2015`, HTML servido, sin
navegador headless. El **CUIT va sin guiones** y **`fdesde` es obligatorio**: sin eso la ruta contesta
HTTP 200 con la página genérica de últimas colocaciones en lugar de los documentos del emisor pedido
—no es un error, es la página equivocada—. El cliente detecta ese caso y lo declara en vez de
reportar "sin documentos", que sería mostrar un faltante inventado.

**No se empareja documento con clase o serie del ticker.** La investigación original ya había medido
que no hay regla general para derivar la clase del número de ticker (funciona para Cresud, no para
IRSA), y se sumó evidencia nueva: un mismo suplemento puede cubrir varias clases a la vez ("Clase XIX
& XX"). Los documentos van todos, **agrupados por tipo tal como la CNV los declara** (regla 11), y el
asesor elige a ojo.

**El puente emisor→CUIT.** Ninguna fuente que el producto ya consume trae el CUIT, así que se curó una
vez a `data/emisores_cuit.csv` (105 nombres) con `tools/curar_emisores_cuit.py`, en tres fuentes en
cascada: el **Listado Completo de Emisoras por Régimen** que la CNV publica como XLSX (~531 emisoras
con CUIT, razón social y categoría — ojo: `openpyxl` en modo `read_only` ve sólo 4 filas porque el
XLSX viene sin metadatos de dimensión, hay que abrirlo en modo normal para ver las 534); el
`AutoComplete` del buscador, para las grafías que el listado escribe distinto; y confirmaciones
manuales, **cada una verificada contra los documentos reales del CUIT candidato** —Cresud: 264 de 386
documentos mencionan CRESUD; IRSA: 248 de 342—, nunca por parecido de nombre.

**Estado: construida y verificada en vivo el 17/08/2026.** Cobertura medida sobre el universo vivo:
**277 de 373 emisiones ON (74 %)** resuelven su CUIT y muestran documentos; sobre las emisiones que sí
tienen emisor declarado, la cobertura es del **98 %**. La feature queda detrás del flag
`CNV_HABILITADO`, **default apagado** —mismo patrón que `YAHOO_HABILITADO` e `IAMC_HABILITADO`—, con
cache de 1 día por CUIT.

**Lo que falta, declarado.** Las **89 emisiones sin emisor declarado en ninguna fuente** son la deuda
vieja de `condiciones_emision.csv`, que se rescató incompleto: sin nombre no hay qué buscar en la CNV,
así que no es un límite del puente. El camino para cerrarlo ya está identificado y es la **tabla de
valuación de Bienes Personales de AFIP/ARCA**, que publica ticker, denominación y CUIT por especie y
por lo tanto resuelve nombre y CUIT juntos, de fuente oficial y por ticker — la misma fuente que F-054
necesita. Es la próxima tarea, separada de ésta. Aparte quedan **5 emisores con ambigüedad real** en
`data/emisores_cuit_pendientes.csv`: EDESA y Havanna tienen dos sociedades cada uno en la CNV
—distribuidora y holding— sin evidencia de cuál emite; BNA y Banco Provincia son bancos públicos sin
ficha EMISIO consultable; y Farmacity no tiene candidato en ninguna de las tres fuentes. Ninguno se
resuelve adivinando.

**Input:** ticker de una ON corporativa desde la ficha de instrumento; `data/emisores_cuit.csv` para
el puente emisor→CUIT.
**Output:** listado de documentos del emisor agrupado por tipo, con fecha y link, y descarga del PDF
con el nombre real del archivo tal como lo publica la CNV.
**Depende de:** F-039 (la ficha de instrumento donde vive el bloque)
**Habilita:** F-054 (comparte el puente emisor→CUIT y el cliente HTTP de la CNV)

**RICE:** R = 350 · I = 3 · C = 100 % · E = 6 → **Score 175,0**
*Confidence 100 %: no queda nada por descubrir — la feature está construida y verificada contra la
fuente real, con el PDF bajado y contrastado contra el tamaño que la CNV declara.*

```
GIVEN una ON corporativa cuyo emisor tiene CUIT curado
WHEN se abre su ficha de instrumento
THEN los documentos aparecen agrupados por tipo tal como la CNV los declara, sin emparejarlos con la
     clase ni la serie del ticker

GIVEN un documento del listado
WHEN el asesor lo descarga
THEN baja el PDF real que sirve la CNV, con el nombre de archivo que la fuente le puso

GIVEN una ON cuyo emisor no tiene CUIT curado, o la fuente está apagada por flag, o la CNV devolvió la
      página genérica en vez de la del emisor
WHEN se abre su ficha
THEN el bloque declara la ausencia con su motivo y no dice "sin documentos"

GIVEN un bono soberano o una letra
WHEN se abre su ficha
THEN el bloque de prospecto no se muestra, porque el Tesoro no presenta ante la CNV
```

---

#### F-073 — Serie diaria de cierres persistida

**Etiqueta:** Stage 2 · **Traza a:** análisis de los skills de asesoramiento del 23/08/2026
(asesor-financiero/IAEF y asesor-fundamental-senior), contrastado contra la capacidad ya
implementada — la matemática determinística de los skills se baja a features; el juicio queda en
los skills, fuera de la app.

**Descripción.** Un cierre por especie por día hábil, persistido en la base y nunca podado. Hoy no
existe: la poda de consolidación deja **una sola fila por ticker** (la última), así que el producto
no acumula historia propia de precios — y sin historia no hay volatilidad, correlaciones, beta,
Sharpe, drawdown ni las ventanas de F-061/F-062, cuyas fichas asumían una acumulación que en la
práctica no ocurre.

**Prender `serie_historica_habilitada` no es la solución.** Ese flag revive la acumulación
**intradiaria**: ~2.900 filas cada 15 minutos, ~11 MB por día hábil sin nada que las borre — el
motivo exacto por el que se apagó (ver el comentario en `config.py`). Lo que la estadística
necesita es otra cosa: **el último snapshot de cada fecha se conserva, los intradiarios se siguen
podando**. Un cierre diario del universo entero son ~2.900 filas por día hábil, ~700 mil filas por
año: trivial. Si se implementa como poda con memoria de fechas o como tabla `cierres_diarios`
aparte lo decide el plan de la feature.

**La historia empieza cuando se prende, y eso se declara.** No se reconstruye hacia atrás con
series de terceros ni con precios inferidos (regla 11): el primer día con la feature activa es el
primer punto de la serie, y toda consulta declara desde qué fecha hay datos. Por eso es la más
urgente del lote aunque su UI sea nula: cada día que pasa apagada es un día de historia que no se
recupera.

**Input:** los precios que la corrida programada de F-008 ya trae cada 15 minutos.
**Output:** serie de cierres diarios por especie (precio, TIR, duración, paridad del cierre), con
fecha de inicio de la historia declarada.
**Depende de:** F-008
**Habilita:** F-061, F-062, F-075

**RICE:** R = 300 · I = 2 · C = 90 % · E = 3 → **Score 180,0**
*Confidence 90 %: la ingesta y la tabla ya existen; el único riesgo es el detalle de qué snapshot
cuenta como "cierre" en un mercado que corta a las 17:00 con corridas cada 15 minutos.*

```
GIVEN varias corridas del mismo día hábil
WHEN corre la poda
THEN del día queda sólo el último snapshot, y los cierres de los días anteriores no se tocan

GIVEN una consulta sobre la serie de una especie
WHEN la historia acumulada es más corta que la ventana pedida
THEN se declara desde qué fecha hay datos y no se rellena hacia atrás con fuentes de terceros ni
     precios reconstruidos

GIVEN el flag intradiario `serie_historica_habilitada` en false
WHEN la feature está activa
THEN el cierre diario se persiste igual: son mecanismos independientes y el flag intradiario sigue
     significando lo que siempre significó
```

---

#### F-074 — Convexidad propia

**Etiqueta:** Stage 2 · **Traza a:** análisis de los skills de asesoramiento del 23/08/2026 — la
asimetría precio-TIR (principio 2 de Malkiel) que el material IAEF enseña, calculada sobre el dato
propio.

**Descripción.** La columna `convexidad` existe en `precios` desde F-007, pero sólo la llenaba
IAMC y quedó huérfana con la pausa del 13/08/2026. Se calcula de forma propia, con el mismo insumo
y el mismo criterio que la TIR y la duración de F-051: el cronograma contractual contra el precio
publicado, aritmética sobre datos duros. Completa la sensibilidad de F-040: la duración modificada
aproxima lineal, la convexidad corrige la asimetría (la suba de precio cuando la TIR baja es mayor
que la caída cuando sube).

**Sólo donde ya hay TIR propia.** La regla de F-051 aplica intacta: precio y flujo en la misma
moneda. Donde la TIR propia no se calcula (CER, dollar-linked, badlar, tamar), la convexidad
tampoco, y el espacio va vacío con su motivo — no se aproxima desde otra métrica.

**Input:** cronograma y TIR propia ya calculados por F-051.
**Output:** convexidad por especie en la columna que ya existe, con fuente propia rotulada.
**Depende de:** F-051
**Habilita:** —

**RICE:** R = 250 · I = 1 · C = 90 % · E = 2 → **Score 112,5**
*Confidence 90 %: es la derivada segunda del mismo valor presente que ya se resuelve; el módulo,
los tests de paridad y la columna destino ya existen.*

```
GIVEN una especie con TIR propia calculada
WHEN corre el cálculo de métricas
THEN la convexidad sale del mismo cronograma y precio que la TIR, con la fuente propia rotulada

GIVEN una especie sin TIR propia (precio y flujo en distinta moneda)
WHEN se muestra su ficha
THEN la convexidad va vacía con el motivo declarado, no aproximada desde otra métrica ni arrastrada
     del último informe de IAMC
```

---

#### F-075 — Estadística de cartera

**Etiqueta:** Stage 2 · **Traza a:** análisis de los skills de asesoramiento del 23/08/2026 —
gestión de carteras del material IAEF (volatilidad, correlación, beta, Sharpe) con insumo propio.

**Descripción.** Sobre una cartera guardada o cargada: volatilidad de cada posición y de la
cartera (desvío de los retornos diarios de la serie propia, anualizado), matriz de correlaciones
entre posiciones, beta contra el índice que BYMA publica, y Sharpe. Es el complemento estadístico
del riesgo composicional que ya existe: el vector de seis ejes (F-031) dice *qué* riesgos hay; esto
mide *cuánto se movió* de verdad.

**Cada métrica por separado, nunca un score.** La regla 7 aplica entera: no hay nota compuesta ni
semáforo que combine volatilidad con concentración. Y la diversificación se muestra como lo que
es: correlaciones medidas sobre fechas comunes de la serie propia — con la advertencia del material
en pantalla: las correlaciones se rompen en crisis, medirlas no las congela.

**El Sharpe necesita una tasa libre de riesgo, y ésa no es un dato: es un supuesto.** El asesor la
elige y queda rotulada junto al resultado, como los supuestos de F-076. Sin tasa elegida, no hay
Sharpe — no hay default silencioso.

**Ventanas incompletas, declaradas.** Mismo criterio que F-061: la estadística vale desde que
F-073 acumula. Una volatilidad anualizada sobre tres semanas de historia es ruido con decimales, y
se declara como incompleta en vez de mostrarse como si fuera un año.

**Input:** serie diaria de F-073; composición de la cartera (F-018/F-041); índice de referencia de
la ingesta BYMA.
**Output:** volatilidad por posición y de cartera, matriz de correlaciones, beta y Sharpe con su
supuesto declarado, cada una con su ventana y su fecha de inicio de datos.
**Depende de:** F-073, F-041
**Habilita:** —

**RICE:** R = 250 · I = 2 · C = 60 % · E = 8 → **Score 37,5**
*Confidence 60 %: la matemática es estándar; la incertidumbre es cuándo hay historia suficiente
para que el resultado signifique algo — la misma espera que F-061.*

```
GIVEN una cartera cuya historia acumulada es menor que la ventana pedida
WHEN se calculan las métricas
THEN cada una declara la ventana real usada y desde cuándo hay datos, y no se presenta una ventana
     parcial como completa

GIVEN dos posiciones con series de largo distinto
WHEN se calcula su correlación
THEN se usan sólo las fechas comunes de la serie propia, sin empalmar con series de terceros

GIVEN todas las métricas calculadas
WHEN se muestran
THEN aparecen por separado, sin componerse en un score único ni en un semáforo agregado

GIVEN el cálculo de Sharpe
WHEN el asesor no eligió tasa libre de riesgo
THEN no se calcula, y cuando la elige, la tasa queda rotulada como supuesto junto al resultado
```

---

#### F-076 — Calculadora de valuación con supuestos declarados

**Etiqueta:** Stage 2 · **Traza a:** análisis de los skills de asesoramiento del 23/08/2026 — el
método fundamental (DCF, Gordon-Shapiro, múltiplos) convertido en calculadora, no en oráculo.

**Descripción.** Una calculadora de valuación de renta variable donde **el asesor pone los
supuestos y la herramienta hace la aritmética**: DCF (flujos proyectados, tasa de descuento, valor
terminal), Gordon-Shapiro (P₀ = D₁/(k−g)) y múltiplos (PER, EV/EBITDA, P/B) con sensibilidad
automática de ±1 punto en k y en g. Es la forma de tener el método fundamental de los skills
adentro de la app sin romper la regla 11: un DCF automático necesitaría inventar g y k — acá los
inventa el asesor, a sabiendas, y el sistema los rotula como suyos.

**Los supuestos viajan pegados al resultado.** En pantalla y en cualquier exporte, el número sale
acompañado de los supuestos que lo produjeron y de quién los declaró. Nunca se muestra un valor
intrínseco como si fuera un dato de mercado, y la herramienta **no emite recomendación, rating ni
precio objetivo**: eso es juicio, y el juicio quedó explícitamente fuera de la app.

**Precarga lo duro, deja en blanco lo que falta.** Para CEDEARs con datos de la SEC (F-053) se
precargan EPS, ingresos y los ratios ya calculados, cada uno con su fuente y su ejercicio; lo que
la fuente no da, va en blanco para que el asesor lo complete o lo deje vacío. Para acciones sin
fundamentals disponibles, la calculadora arranca vacía: sirve igual, porque el valor está en la
aritmética y la sensibilidad, no en adivinar los inputs.

**Input:** supuestos cargados por el asesor; datos duros de SEC precargados donde existen.
**Output:** valor por acción según cada método, tabla de sensibilidad k×g, y el bloque de supuestos
declarados que acompaña al resultado en pantalla y en exportes.
**Depende de:** F-053
**Habilita:** —

**RICE:** R = 200 · I = 2 · C = 70 % · E = 8 → **Score 35,0**
*Confidence 70 %: la aritmética es cerrada y verificable contra el material del curso; la
incertidumbre es de producto — cuánto la usa un asesor cuya operación diaria es renta fija.*

```
GIVEN supuestos g y k cargados por el asesor
WHEN se calcula el valor
THEN el resultado aparece con la tabla de sensibilidad de ±1 punto en cada supuesto, y los
     supuestos quedan rotulados como declarados por el asesor, en pantalla y en el exporte

GIVEN g mayor o igual que k
WHEN se intenta Gordon-Shapiro
THEN no se calcula y se explica por qué la fórmula no admite ese caso, en vez de devolver un número
     sin sentido

GIVEN un CEDEAR con datos de la SEC disponibles
WHEN se abre la calculadora
THEN los datos duros aparecen precargados con su fuente y ejercicio, y lo que la fuente no publica
     va en blanco — nunca estimado por el sistema

GIVEN cualquier resultado de la calculadora
WHEN se muestra o exporta
THEN no se presenta como recomendación, rating ni precio objetivo del sistema
```

---

#### F-077 — Perfilado formal del inversor

**Etiqueta:** Stage 2 · **Traza a:** análisis de los skills de asesoramiento del 23/08/2026 — el
cuestionario de perfil de riesgo del material IAEF, mapeado a los tres perfiles que el producto ya
usa.

**Descripción.** El cuestionario de seis preguntas del material del curso (reacción a una caída
del 15 %, preferencia rentabilidad/seguridad, % histórico en renta variable, actitud frente al
mercado accionario, tolerancia al endeudamiento, frecuencia de seguimiento) como formulario, con
mapeo **determinístico** de las respuestas a los tres perfiles que `concentracion/perfiles.py` ya
define: conservador, moderado, agresivo. Hoy el asesor elige el perfil a ojo en un selector; con
esto puede además documentar de dónde salió.

**El resultado se documenta, no se supone.** Quedan guardadas las respuestas, el perfil resultante
y la fecha — el criterio del material: el test queda escrito. Con respuestas incompletas no se
asigna perfil (regla 1: no se rellena el hueco con un default); se declara incompleto y listo.

**Sin datos del cliente, hasta que exista F-043.** El cuestionario se guarda asociado al asesor
(RLS de F-014) y opcionalmente a una cartera, sin nombre ni dato identificatorio del titular —
ésos tienen prohibido entrar al repositorio y todavía no tienen dónde vivir. Cuando F-043 exista,
el perfil documentado se asocia a la entidad cliente.

**Input:** las seis respuestas del cuestionario.
**Output:** perfil asignado con las respuestas y la fecha documentadas, precargable en el armador
(que sigue permitiendo elegir otro perfil a mano).
**Depende de:** F-014
**Habilita:** F-043 (le entrega el perfil documentado que la ficha de cliente va a mostrar)

**RICE:** R = 300 · I = 2 · C = 80 % · E = 5 → **Score 96,0**
*Confidence 80 %: el cuestionario y los tres perfiles destino ya existen; la incertidumbre es el
mapeo respuestas→perfil, que el material trae como criterio (primera opción conservadora, última
agresiva) pero no como tabla cerrada.*

```
GIVEN las seis preguntas respondidas
WHEN se calcula el perfil
THEN el mapeo es determinístico y el resultado queda documentado con las respuestas y la fecha

GIVEN un cuestionario con respuestas incompletas
WHEN se intenta asignar perfil
THEN no se asigna ninguno por default: se declara incompleto y se señalan las preguntas que faltan

GIVEN un perfil documentado
WHEN el asesor abre el armador
THEN puede precargarlo, y elegir a mano un perfil distinto sigue siendo posible

GIVEN el cuestionario guardado
WHEN se persiste
THEN no incluye nombre ni dato identificatorio del titular hasta que F-043 defina dónde viven los
     datos de clientes
```

---

**Nota de alcance del lote F-073–F-077.** Del análisis de los skills se bajó a features la capa de
matemática determinística, y **sólo** ésa. Tesis de inversión, ratings comprar/mantener/vender,
precios objetivo automáticos y scores compuestos de riesgo **no entran a la app**: chocan con las
reglas 1 (un DCF automático inventa sus supuestos), 6 (la lógica de análisis es determinística), 7
(el riesgo es un vector, no un número) y 11 (no se muestra interpretación en lugar del dato). Esa
capa de juicio ya tiene dónde vivir: los skills de asesoramiento, fuera del producto, consumiendo
los números verificables que la app produce. Los estados contables de emisores argentinos desde la
CNV quedan como investigación pendiente —parsing grande, resultado incierto—, no como feature.

---

## 4. Tabla de RICE ordenada

| # | ID | Feature | Etiqueta | R | I | C | E | Score |
|---|---|---|---|---|---|---|---|---|
| 1 | F-001 | Esqueleto de servicio backend | Foundation | 400 | 3 | 100 % | 3 | **400,0** |
| 2 | F-003 | Esqueleto de aplicación frontend | Foundation | 400 | 3 | 100 % | 3 | **400,0** |
| 3 | F-010 | Sanidad del dato en dos capas | Stage 1 | 400 | 3 | 100 % | 3 | **400,0** |
| 4 | F-011 | Deduplicación de especies | Stage 1 | 400 | 2 | 100 % | 2 | **400,0** |
| 5 | F-002 | Esquema de datos y migraciones | Foundation | 400 | 3 | 100 % | 4 | **300,0** |
| 6 | F-004 | Cliente de la API abierta de BYMA | Stage 1 | 400 | 3 | 100 % | 4 | **300,0** |
| 7 | F-015 | API del calendario de doce meses | Stage 1 | 380 | 3 | 100 % | 4 | 285,0 |
| 8 | F-021 | Panel de renta y renta anual | Stage 1 | 380 | 3 | 100 % | 4 | 285,0 |
| 9 | F-008 | Job programado de ingesta | Stage 1 | 400 | 2 | 100 % | 3 | 266,7 |
| 10 | F-012 | Tipo de cambio implícito y normalización | Stage 1 | 400 | 2 | 100 % | 3 | 266,7 |
| 11 | F-068 | Panel de dólar y spreads | Stage 2 | 400 | 2 | 100 % | 3 | 266,7 |
| 12 | F-006 | Cliente del feed de cashflow de Docta | Stage 1 | 400 | 3 | 80 % | 4 | 240,0 |
| 13 | F-060 | Navegación por emisor × naturaleza | Stage 2 | 400 | 2 | 90 % | 3 | 240,0 |
| 14 | F-009 | condiciones_emision: semilla y herencia | Stage 1 | 400 | 2 | 100 % | 4 | 200,0 |
| 15 | F-013 | Barra de estado del dato | Stage 1 | 400 | 2 | 100 % | 4 | 200,0 |
| 16 | F-014 | Autenticación y aislamiento por asesor | Stage 1 | 400 | 2 | 100 % | 4 | 200,0 |
| 17 | F-024 | Redondeo por lámina y diferencia | Stage 1 | 300 | 2 | 100 % | 3 | 200,0 |
| 18 | F-059 | Comparador de dos instrumentos | Stage 2 | 350 | 3 | 90 % | 5 | 189,0 |
| 19 | F-035 | Costo real de rotar y cupón próximo | Stage 1 | 180 | 3 | 100 % | 3 | 180,0 |
| 20 | F-041 | Guardar, listar, reabrir y revaluar | Stage 1 | 300 | 3 | 100 % | 5 | 180,0 |
| 21 | F-055 | Descarga automática del informe de IAMC | Stage 2 | 300 | 2 | 90 % | 3 | 180,0 |
| 22 | F-073 | Serie diaria de cierres persistida | Stage 2 | 300 | 2 | 90 % | 3 | 180,0 |
| 23 | F-020 | Límites de concentración en vivo | Stage 1 | 350 | 2 | 100 % | 4 | 175,0 |
| 24 | F-022 | Rendimientos por naturaleza y plazo | Stage 1 | 350 | 2 | 100 % | 4 | 175,0 |
| 25 | F-072 | Prospecto de emisión de ONs, vía CNV | Stage 2 | 350 | 3 | 100 % | 6 | 175,0 |
| 26 | F-007 | Consolidador multi-fuente | Stage 1 | 400 | 3 | 80 % | 6 | 160,0 |
| 27 | F-051 | Métricas propias: TIR, duración y paridad | Stage 1 | 400 | 2 | 80 % | 4 | 160,0 |
| 28 | F-071 | Calculadora de canjes y prorrateo de órdenes a mesa | Stage 2 | 350 | 3 | 90 % | 6 | 157,5 |
| 29 | F-030 | Valuación y diagnóstico de cartera | Stage 1 | 200 | 3 | 100 % | 4 | 150,0 |
| 30 | F-064 | Watchlist | Stage 2 | 300 | 1 | 100 % | 2 | 150,0 |
| 31 | F-069 | Top ganadores y perdedores | Stage 2 | 300 | 1 | 100 % | 2 | 150,0 |
| 32 | F-018 | Cartera editable y ponderación | Stage 1 | 350 | 3 | 80 % | 6 | 140,0 |
| 33 | F-053 | Ficha del activo de renta variable | Stage 1 | 300 | 2 | 70 % | 3 | 140,0 |
| 34 | F-016 | Grilla-selector de doce meses | Stage 1 | 380 | 3 | 80 % | 8 | 114,0 |
| 35 | F-056 | Índice CER del BCRA: tasa real | Stage 2 | 250 | 2 | 90 % | 4 | 112,5 |
| 36 | F-074 | Convexidad propia | Stage 2 | 250 | 1 | 90 % | 2 | 112,5 |
| 37 | F-017 | Filtros de la grilla | Stage 1 | 350 | 2 | 80 % | 5 | 112,0 |
| 38 | F-039 | Ficha de instrumento | Stage 1 | 350 | 2 | 80 % | 5 | 112,0 |
| 39 | F-029 | Resolución de tickers | Stage 1 | 200 | 2 | 80 % | 3 | 106,7 |
| 40 | F-038 | Monitor de mercado | Stage 1 | 400 | 2 | 80 % | 6 | 106,7 |
| 41 | F-052 | Renta variable en el monitor | Stage 1 | 400 | 1 | 80 % | 3 | 106,7 |
| 42 | F-031 | Vector de riesgo de seis ejes | Stage 1 | 250 | 3 | 80 % | 6 | 100,0 |
| 43 | F-032 | Motor de rotaciones intra-segmento | Stage 1 | 200 | 3 | 100 % | 6 | 100,0 |
| 44 | F-042 | Exportación a Excel y PDF | Stage 1 | 250 | 2 | 80 % | 4 | 100,0 |
| 45 | F-028 | Ingreso de cartera por tres vías | Stage 1 | 200 | 3 | 80 % | 5 | 96,0 |
| 46 | F-077 | Perfilado formal del inversor | Stage 2 | 300 | 2 | 80 % | 5 | 96,0 |
| 47 | F-034 | Modo subir TIR con contrapartida | Stage 1 | 180 | 3 | 80 % | 5 | 86,4 |
| 48 | F-057 | FCI en el monitor (CAFCI) | Stage 2 | 300 | 2 | 85 % | 6 | 85,0 |
| 49 | F-067 | FCI: comparador, categorías y gestoras | Stage 2 | 250 | 2 | 85 % | 5 | 85,0 |
| 50 | F-019 | Armado asistido | Stage 1 | 250 | 2 | 100 % | 6 | 83,3 |
| 51 | F-026 | Bloque de renta variable | Stage 1 | 300 | 2 | 80 % | 6 | 80,0 |
| 52 | F-050 | API Market Data oficial de BYMA | Stage 2 | 400 | 2 | 50 % | 5 | 80,0 |
| 53 | F-058 | Carry trade: calculadora y breakeven | Stage 2 | 300 | 3 | 70 % | 8 | 78,8 |
| 54 | F-062 | Curva histórica del segmento | Stage 2 | 250 | 2 | 60 % | 4 | 75,0 |
| 55 | F-063 | Heatmap del panel | Stage 2 | 250 | 1 | 90 % | 3 | 75,0 |
| 56 | F-037 | Comparación original contra propuesta | Stage 1 | 180 | 2 | 80 % | 4 | 72,0 |
| 57 | F-061 | Rendimientos históricos por ventana | Stage 2 | 300 | 2 | 60 % | 5 | 72,0 |
| 58 | F-040 | Sensibilidad por repricing completo | Stage 1 | 200 | 1 | 100 % | 3 | 66,7 |
| 59 | F-054 | Info pública del emisor (CNV y SEC) | Stage 2 | 300 | 2 | 80 % | 8 | 60,0 |
| 60 | F-033 | Modo bajar riesgo | Stage 1 | 180 | 2 | 80 % | 5 | 57,6 |
| 61 | F-036 | Aceptación rotación por rotación | Stage 1 | 180 | 2 | 80 % | 5 | 57,6 |
| 62 | F-025 | Carga asistida de lámina | Stage 1 | 200 | 1 | 80 % | 3 | 53,3 |
| 63 | F-005 | Parser del informe diario de IAMC | Stage 1 | 400 | 2 | 50 % | 8 | 50,0 |
| 64 | F-023 | Composición y curva TIR/duración | Stage 1 | 300 | 1 | 80 % | 5 | 48,0 |
| 65 | F-048 | Alertas y notificaciones | Stage 2 | 300 | 1 | 80 % | 6 | 40,0 |
| 66 | F-049 | Comparación de carteras entre sí | Stage 2 | 200 | 1 | 80 % | 4 | 40,0 |
| 67 | F-075 | Estadística de cartera | Stage 2 | 250 | 2 | 60 % | 8 | 37,5 |
| 68 | F-076 | Calculadora de valuación con supuestos declarados | Stage 2 | 200 | 2 | 70 % | 8 | 35,0 |
| 69 | F-046 | FCI valuables en cartera | Stage 2 | 200 | 2 | 60 % | 8 | 30,0 |
| 70 | F-065 | Cauciones | Stage 2 | 200 | 1 | 60 % | 4 | 30,0 |
| 71 | F-044 | Historial de propuestas | Stage 2 | 250 | 2 | 50 % | 10 | 25,0 |
| 72 | F-066 | Futuros de dólar | Stage 2 | 200 | 1 | 50 % | 4 | 25,0 |
| 73 | F-043 | Gestión de clientes y CRM | Stage 2 | 300 | 2 | 50 % | 15 | 20,0 |
| 74 | F-027 | Calendario de balances (sólo CEDEARs, vía SEC) | Stage 1 | 200 | 1 | 85 % | 4 | 42,5 |
| 75 | F-045 | Colocaciones primarias | Stage 2 | 150 | 2 | 50 % | 10 | 15,0 |
| 76 | F-070 | Tenencias con P&L por lote | Stage 2 | 200 | 2 | 40 % | 12 | 13,3 |
| 77 | F-047 | Opciones | Stage 2 | 80 | 1 | 50 % | 10 | 4,0 |

**Cómo se lee esta tabla.** El RICE ordena por eficiencia, no por secuencia. Las features de más
score son las Foundation y las de ingesta: mucho alcance sobre poco esfuerzo, porque reusan lógica ya
verificada. Las del optimizador puntúan bajo por su Reach acotado al Flujo B, y **eso no las hace
opcionales**: el usuario declaró el optimizador como mitad no negociable del producto. El RICE informa
el orden dentro de un ciclo; la etiqueta Stage 1 / Stage 2 decide qué se construye.

---

## 5. Tech stack, con la justificación de cada pieza

El stack ya está decidido en `product-definition.md`. Acá va por qué cada pieza es la correcta, no una
reapertura de la decisión.

### Frontend — React 19 + TypeScript + Vite (SPA)

- **SPA sin renderizado en servidor.** Es una herramienta interna con login por invitación: no hay SEO
  que ganar ni primera carga fría que optimizar. SSR agregaría una capa de servidor a mantener para
  cero beneficio.
- **TypeScript.** El dominio tiene unidades que no se pueden mezclar —TIR en dólares, tasa real, TNA
  nominal— y el tipado es la primera línea de defensa contra sumar dos cosas que no se suman. Los tipos
  del esquema se generan desde Supabase, así que la base de datos y el frontend no pueden divergir en
  silencio.
- **TanStack Query.** Los precios se refrescan durante la rueda y toda la pantalla depende de un
  snapshot con hora. La invalidación coordinada es exactamente el problema que resuelve; hacerla a mano
  produciría paneles con datos de momentos distintos, que es el error que la barra de estado del dato
  existe para hacer imposible.
- **TanStack Table.** El monitor tiene ~1.700 filas con ordenamiento y filtrado. Es una grilla densa,
  no una lista.
- **Tailwind CSS.** Densidad alta de información sin decoración: la interfaz de trabajo del asesor
  necesita control fino de espaciado, no una librería de componentes con opinión propia.
- **Recharts.** Curva TIR/duración y renta mensual. Suficiente para los dos gráficos que el producto
  necesita, sin el peso de d3 a mano.
- **Zod.** Todo lo que entra por carga de cartera (F-028) se valida en el borde. Un resumen de cuenta
  pegado es entrada no confiable por definición.

### Backend — Python 3.12 + FastAPI

- **Python, porque el motor ya está escrito y verificado en Python.** No es una preferencia de
  lenguaje: reescribir `segmentos.py`, `cupones.py` y `mercado.py` en otro lenguaje significaría
  reverificarlos contra el Excel de la mesa, contra los swaps ejecutados y contra la tabla de
  repricing. Ese trabajo ya está hecho y no se paga dos veces.
- **FastAPI.** Los parámetros que hoy son flags de argparse pasan a ser modelos Pydantic con
  validación y documentación automática. El desacople de `armar_cartera.py` y `detectar_swaps.py` es
  casi mecánico con este modelo.
- **pandas ya es dependencia.** Los DataFrames que hoy van a hojas de Excel se serializan a JSON.
- **El pipeline de ingesta corre como job del mismo servicio**, así comparte el modelo de datos, la
  configuración y el logging.

### Base de datos — Supabase (PostgreSQL + Auth + RLS)

- **RLS y no filtros de aplicación.** El aislamiento entre asesores es una garantía, no una
  convención. Con RLS, un bug en el frontend no filtra la cartera de otro asesor.
- **Auth incluida, por invitación.** No hay que construir gestión de sesiones para un puñado de
  usuarios internos.
- **PostgreSQL.** El esquema replica el contrato del universo consolidado actual, lo que permite que
  los módulos reusados no se enteren del cambio de fuente.
- **Es más barato construirlo con RLS desde la primera tabla que retrofitearlo** sobre datos
  existentes: por eso F-002 es Foundation y no una feature de seguridad posterior.

### Hosting

- **Stage 1:** frontend en Vercel o Cloudflare Pages, backend FastAPI containerizado en Fly.io o
  Railway, Supabase managed. Cero operaciones y costo mínimo, que es lo que corresponde a un producto
  con un puñado de usuarios internos.
- **Stage 2:** AWS (ECS Fargate + RDS), cuando el volumen y los requisitos de retención lo justifiquen.
  Es una migración de infraestructura, no de arquitectura: el `Dockerfile` de F-001 es el mismo.

---

## 6. Arquitectura por etapa

### Stage 1

```
┌─────────────────────────────────────────────────────────────┐
│  SPA React 19 + TS (Vercel / Cloudflare Pages)              │
│  Armador · Optimizador · Monitor · Mis carteras · Ficha     │
│  ── barra de estado del dato, transversal (F-013) ──        │
└───────────────────────────┬─────────────────────────────────┘
                            │  /api/v1/  (JSON, paginado)
┌───────────────────────────┴─────────────────────────────────┐
│  FastAPI (Fly.io / Railway) — Dockerfile, JSON logs, /health│
│                                                              │
│  Servicios de cálculo (envoltura del motor)                 │
│    segmentos.py · cupones.py · mercado.py     REUSO 55 %    │
│    armar_cartera.py · detectar_swaps.py       ENVUELTO 30 % │
│                                                              │
│  Pipeline de ingesta (job programado)                        │
│    BYMA ──┐                                                  │
│    IAMC ──┼─► consolidador multi-fuente ─► integridad ─► DB │
│    Docta ─┘   (reescrito, 15 %)                              │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────┴─────────────────────────────────┐
│  Supabase — PostgreSQL + Auth + RLS                          │
│  Mercado (compartido): instrumentos, precios, puntas,        │
│                        cashflow, condiciones_emision         │
│  Usuario (RLS, user_id FK): carteras, posiciones, propuestas │
└──────────────────────────────────────────────────────────────┘
```

### Rol del motor existente

Esta es una decisión de producto con impacto real en el plazo, no un detalle de implementación. De ella
depende que el esfuerzo de Stage 1 sea el estimado y no el doble.

**Se reusa tal cual, sin tocar la lógica (~55 %).** Estos módulos entran envueltos en un servicio, con
sus funciones intactas y sus tests como tests de regresión del servicio:

| Módulo | Qué aporta | Features que lo consumen |
|---|---|---|
| `segmentos.py` | Segmentación en seis segmentos y cuatro naturalezas de tasa; sanidad en dos capas; deduplicación de especies; tipo de cambio implícito; normalización de volumen a dólares; agrupación por clave de riesgo con el soberano aparte. **El módulo más crítico y el más verificado.** | F-010, F-011, F-012, F-020, F-031 |
| `cupones.py` | Flujos por peso; calendario de doce meses; valor técnico; frecuencia de cobro; repricing por descuento completo. | F-015, F-021, F-035, F-040 |
| `mercado.py` | Puntas bid/ask y costo real de rotar. **Sólo cambia de dónde vienen las puntas**: BYMA las publica en el mismo endpoint que el precio, lo que elimina la dependencia de data912 y mejora la cobertura de spread. | F-035 |

**Se envuelve como servicio: el núcleo se conserva, el entorno se reemplaza (~30 %).**

| Módulo | Qué se conserva | Qué se descarta | Features |
|---|---|---|---|
| `armar_cartera.py` | `resolver_mix`, `candidatos_del_segmento`, `elegir_siguiente`, `armar`, `verificar_concentracion`, `resumir` | `main()` con argparse; `exportar()`/`exportar_excel()` con openpyxl; lectura desde archivos en disco | F-019, F-020 |
| `detectar_swaps.py` | `evaluar_par`, `detectar`, `tabla_spread_legislacion`, `hoja_sensibilidad` | Misma cáscara | F-032, F-033, F-034 |

Los flags de CLI pasan a ser un modelo Pydantic; los DataFrames que hoy van a hojas de Excel se
serializan. **El trabajo es de desacople, no de reescritura.** La lista de alertas que hoy se acumula
en una hoja "Alertas" pasa a ser un array estructurado en la respuesta, y la interfaz la renderiza en
F-013. El contenido no cambia.

**Se reescribe (~15 %).**

| Módulo | Por qué | Reemplazo |
|---|---|---|
| `consolidar_universo.py` | Está atado a la API de Docta: tres links tokenizados que devuelven Excel por HTTP, con `fromDate` hardcodeado. **Y no se corre hoy**: sobrescribiría el universo dejando vacías las columnas de condiciones. | F-004 + F-005 + F-006 + F-007, escribiendo a PostgreSQL. **Conserva el contrato de salida**, y eso es lo que permite reusar el 85 % restante. |
| `merge_condiciones.py` | Opera sobre CSV en disco | F-009, como operación sobre la tabla `condiciones_emision`, conservando la herencia entre especies y la detección de conflictos que vacía lo contradictorio y lo reporta |
| `aplicar_sectores.py` | Ídem | F-009 |

### Stage 2

Los cambios de Stage 2 son de alcance de producto (F-043 … F-049) y de infraestructura (AWS: ECS
Fargate + RDS), **no de arquitectura**. Dos puntos de diseño de Stage 1 existen para que esto sea
cierto: el `Dockerfile` de F-001, que hace que el hosting sea intercambiable, y la interfaz de fuente
desacoplada de F-004, que hace que la migración a la API Market Data oficial (F-050) sea un cambio de
implementación.

Las fuentes que Stage 2 suma —CNV y SEC (F-054), la descarga de IAMC (F-055), el CER del BCRA
(F-056) y CAFCI (F-057)— entran por esa misma interfaz y **ninguna toca el consolidador del
universo**. La de CAFCI es la más separada de todas: un FCI no es una especie negociable, así que no
se deduplica, no pasa por la sanidad de precios de renta fija ni por el cálculo de TIR. Tabla propia,
ingesta propia, segmento propio en el monitor.

---

## 7. Execution Map

### Paralelas desde el día 1 (sin dependencias)

Sólo **F-001** no depende de nada. Es la raíz literal del árbol: el esqueleto de servicio con el
contrato de API, el logging y la configuración que todo lo demás asume. Es la única feature que no se
puede paralelizar contra nada, y por eso conviene que sea la más corta posible.

**Inmediatamente después de F-001 se abren cuatro frentes en paralelo:** F-002 (datos), F-003
(frontend), F-004 (BYMA), F-005 (IAMC) y F-006 (Docta) — cinco features que no se tocan entre sí.

### Tracks de desarrollo

**Track A — Datos y persistencia** (crítico, bloquea todo)
```
F-001 → F-002 → F-007 → F-008 → F-013
                  └───→ F-009 → F-024 → F-025
```

**Track B — Fuentes** (tres sub-tracks paralelos entre sí, convergen en F-007)
```
F-001 → F-004 ─┐
F-001 → F-005 ─┼─→ F-007
F-001 → F-006 ─┘
```

**Track C — Integridad** (arranca cuando F-007 cierra)
```
F-007 → F-010 → F-011 → F-015 → F-016 → F-017 → F-019
          └───→ F-012                       ↑
                              F-020 ────────┘  (min_sectores)
```

**Track D — Frontend y auth** (paralelo total a A/B/C hasta F-013)
```
F-001 → F-003 → F-014 → F-018 → F-020
          └───→ F-013 → F-038 → F-039 → F-040
          └───→ F-028 → F-029
```

**Track E — Armador** (converge C + D)
```
F-016 + F-018 → F-021 → F-022 → F-023
                  └───→ F-024 → F-025
                  └───→ F-026 → F-027
```

**Track F — Optimizador** (el track más profundo; arranca cuando el diagnóstico existe)
```
F-029 + F-021 + F-022 → F-030 → F-031 → F-033 ─┐
                          └───→ F-032 → F-034 ─┼→ F-036 → F-037
                                  └───→ F-035 ─┘
```

**Track G — Persistencia de usuario** (cola de todo)
```
F-018 + F-037 → F-041 → F-042
```

### No pueden correr en paralelo entre sí

Pares y grupos que tocan el mismo modelo, la misma tabla o el mismo componente compartido, y que hay
que serializar aunque el grafo de dependencias no lo exija:

| Grupo | Recurso compartido | Por qué |
|---|---|---|
| F-007 · F-009 | Tablas `instrumentos` y `condiciones_emision` | Las dos escriben condiciones de emisión; si corren a la vez, la herencia entre especies opera sobre datos a medio consolidar |
| F-010 · F-011 · F-012 | Envoltura de `segmentos.py` | Las tres exponen el mismo módulo como servicio; construirlas en paralelo produce tres envolturas incompatibles |
| F-016 · F-017 · F-018 | Estado de la cartera en el armador | Comparten el mismo store de UI; en paralelo se pisan el modelo de estado |
| F-021 · F-022 · F-023 | Servicio de métricas de cartera | Mismo endpoint de resumen; conviene una sola vez y bien |
| F-024 · F-025 | Tabla `condiciones_emision`, campo `lamina` | F-025 escribe lo que F-024 lee |
| F-033 · F-034 | Servicio de propuestas y el contrato de la fila de propuesta | Comparten el modelo de salida; si divergen, F-036 tiene que reconciliar dos formatos |
| F-030 · F-031 | Servicio de diagnóstico | F-031 extiende la salida de F-030 |
| F-038 · F-039 | Grilla del monitor y navegación a la ficha | Misma pantalla, mismo ruteo |

### Resumen ejecutivo del Execution Map

- **Features de Stage 1 (incluyendo Foundation):** 42
- **Features que pueden arrancarse el día 1:** 1 (F-001). A partir del día 4, **5 en paralelo**
  (F-002, F-003, F-004, F-005, F-006).
- **Tracks independientes:** 7 (A a G), con 3 sub-tracks paralelos dentro del Track B.
- **Feature crítica — la que más desbloquea:** **F-002 (esquema de datos y migraciones)**. Es
  prerrequisito directo de F-007, F-009 y F-014, y transitivamente de 24 de las 42 features de
  Stage 1. Un error de modelado acá se paga en cada ciclo posterior.
- **Camino crítico (la cadena más larga):**
  `F-001 → F-002 → F-007 → F-010 → F-011 → F-015 → F-016 → F-018 → F-021 → F-030 → F-031 → F-033 → F-036 → F-037 → F-041 → F-042`
  — 16 features encadenadas, **73 person-days**. Ninguna paralelización lo acorta; sólo achicar sus
  eslabones lo hace.
- **Cuello de botella conocido:** F-016 (grilla-selector, 8 pd) es la feature de UI más pesada y está
  sobre el camino crítico. Depende además de `design-system.md`, que es output de la Fase 3. **Si la
  Fase 3 no está lista cuando el Ciclo 2 arranca, F-016 se bloquea y el camino crítico se estira.**

---

## 8. Ciclos y timeline

Cuatro ciclos para Stage 1. Ningún ciclo supera las 12 features. La estimación de calendario asume un
desarrollador a tiempo completo, 5 person-days por semana — **la dedicación real no está en los inputs,
así que el calendario es una derivación de los person-days y no un compromiso**.

### Ciclo 1 — Cimientos e ingesta (12 features · 47 pd · ~9,5 semanas)

F-001, F-002, F-003, F-004, F-005, F-006, F-007, F-008, F-009, F-010, F-011, F-012

Al final de este ciclo hay una base de mercado poblada, saneada, deduplicada y normalizada, que se
refresca sola. No hay pantalla que un asesor pueda usar todavía.

> **Milestone 1 — "El universo existe y es confiable."**
> Criterio de salida: la corrida matinal completa termina sin intervención; VSCQD se descarta y VSCQO
> se conserva; SNSBO sobrevive; MR46O/D/C se colapsan en el armador y viven en el optimizador; el tipo
> de cambio implícito se calcula con ≥ 20 pares y se contrasta contra `index-price`; el token vencido
> de Docta produce una alerta distinta de la de API caída.

### Ciclo 2 — Armador completo (12 features · 55 pd · ~11 semanas)

F-013, F-014, F-015, F-016, F-017, F-018, F-019, F-020, F-021, F-022, F-023, F-024

Al final de este ciclo el **Flujo A está completo y es usable en producción**. Es el ciclo de mayor
riesgo de cronograma porque concentra la UI pesada.

> **Milestone 2 — "Un asesor arma una cartera desde el calendario y se lleva el número a la reunión."**
> Criterio de salida: un asesor autenticado entra, filtra por segmento, elige papeles desde la grilla
> de doce meses, ve la iluminación multi-mes, ajusta pesos, ve la diferencia entre ponderación pedida
> y real, y lee la renta anual sobre lo invertido con la cuenta a la vista. Los cuatro rendimientos
> aparecen abiertos y no hay control que los promedie.
> **Dependencia externa: `design-system.md` (Fase 3) tiene que estar listo antes de que empiece este
> ciclo.**

### Ciclo 3 — Renta variable, carga y diagnóstico (9 features · 41 pd · ~8 semanas)

F-025, F-026, F-027, F-028, F-029, F-030, F-031, F-032, F-035

Al final de este ciclo la cartera del cliente se carga, se valora y se diagnostica con los seis ejes,
y el motor de rotaciones produce candidatas con su costo real. Falta la capa de decisión.

> **Milestone 3 — "El diagnóstico de una cartera ajena tarda minutos y no horas."**
> Criterio de salida: un resumen de cuenta pegado se resuelve contra el universo con los no
> reconocidos marcados; el diagnóstico produce los mismos números que si la cartera se hubiera armado
> a mano; los seis ejes aparecen con su cobertura declarada y no hay score compuesto en ninguna
> pantalla; el costo mediano de rotación se calcula con el spread en las dos patas.

### Ciclo 4 — Optimizador, monitor y persistencia (9 features · 42 pd · ~8,5 semanas)

F-033, F-034, F-036, F-037, F-038, F-039, F-040, F-041, F-042

Al final de este ciclo **Stage 1 está completo**: los tres flujos funcionan de punta a punta.

> **Milestone 4 — "Stage 1 completo: los tres flujos cierran."**
> Criterio de salida: el modo bajar riesgo respeta el no-empeoramiento de los cinco ejes restantes y
> dice "no hay propuesta" cuando corresponde; ninguna propuesta de mejora de TIR se renderiza sin su
> contrapartida nombrada; el monitor sirve la consulta de la mañana con un segmento por vez; una
> cartera guardada se reabre con los precios con los que se guardó y se revalúa con la diferencia
> explícita; el export declara snapshot y demora en el pie.

### Totales

| Ciclo | Features | Person-days | Semanas (est.) | Acumulado |
|---|---|---|---|---|
| 1 — Cimientos e ingesta | 12 | 47 | ~9,5 | ~9,5 |
| 2 — Armador completo | 12 | 55 | ~11 | ~20,5 |
| 3 — RV, carga y diagnóstico | 9 | 41 | ~8 | ~28,5 |
| 4 — Optimizador y persistencia | 9 | 42 | ~8,5 | ~37 |
| **Stage 1** | **42** | **185** | **~37 semanas** | |
| Stage 2 (32 features) | 32 | 187 | ~37 | |

**~37 semanas de un desarrollador a tiempo completo para Stage 1.** El camino crítico son 73 pd de esos
185: con un segundo desarrollador, el piso teórico de compresión es **~15 semanas**, y el cuello real
sería F-016 más la disponibilidad del design system.

---

## 9. Riesgos y mitigaciones

### Riesgos de datos y fuentes

**R1 — El token de Docta vence y se lleva puesto el corazón del producto.**
**Se materializó el 12/08/2026, y por decisión: la fuente es paga y se dio de baja.** La mitigación
descrita abajo resultó ser la que sostiene el producto — el cronograma persistido quedó como fuente
única, y el calendario, la clasificación por tipo de tasa y las métricas de F-051 siguen en pie
sobre él. El riesgo vivo ya no es que el token venza sino que **el conjunto de cronogramas está
cerrado**: toda emisión nueva entra sin flujo contractual. Conseguir una fuente de reemplazo —CNV
es el candidato a evaluar, ver F-054— es trabajo pendiente y sin fecha.

El cronograma completo de pagos —97 % de cobertura— salía sólo de Docta, y sin él la grilla de doce
meses deja de existir. El token vence y los tres links lo comparten.
*Mitigación:* F-006 distingue **HTTP 500 "Error al verificar el token" (vencido, se regenera desde
Docta Terminal)** de un timeout o un 5xx distinto (API caída), porque la acción que requieren es
distinta. La alerta llega a la barra de estado del dato (F-013) con la acción concreta. Además, el
último cashflow válido se conserva con su fecha: el producto sigue funcionando declarando que el
calendario es de ayer, en vez de quedarse en blanco.
*Lo que no se hace:* proyectar el calendario desde la estructura del cupón de IAMC. Funcionaría para
bullets de cupón fijo y fallaría en los amortizing con escalera, que son mayoría entre las ONs
locales. Proyectarlos sería inventar.

**R2 — La demora de 20 minutos de BYMA convierte cualquier número en histórico.**
El feed abierto tiene 20 minutos de demora declarada. Un asesor que decide sobre un precio de hace 20
minutos y no lo sabe está decidiendo mal.
*Mitigación:* la demora es un atributo del snapshot (F-004), no una nota al pie, y la barra de estado
del dato la declara en todas las pantallas (F-013). La salida es F-050: la API Market Data oficial, que
según BYMA no requiere homologación y se solicita a `marketdata@byma.com.ar`. F-004 se diseña con la
fuente desacoplada para que esa migración sea un cambio de implementación.

**R3 — Endpoints de BYMA que hoy responden 401.**
No todos los endpoints de la API abierta responden igual; algunos dan 401.
*Mitigación:* F-004 aísla cada endpoint: uno que falla no aborta la corrida de los otros cuatro, queda
registrado con su código, y la barra de estado declara qué parte del universo no se pudo refrescar. Se
verifica el conteo de filas contra el verificado el 05/08/2026 (4.909 / 189 / 2.267 / 189 / 16) y una
desviación grande dispara alerta.

**R4 — IAMC es un PDF, y los PDF cambian de layout.**
Es la única fuente de emisor, ley, moneda de pago y estructura. Un cambio de formato rompe el parser, y
un parser que "tolera" el cambio produce filas parciales que parecen datos.
*Mitigación:* F-005 falla ruidosamente ante una sección no reconocida en vez de persistir filas
parciales, y ley y moneda de pago se leen del **título de la sección**, no de una columna inferida —
que es exactamente lo que evita repetir el episodio de "Ley Inglesa". Es el riesgo con la Confidence
más baja de todo el Stage 1 (50 %) y por eso su Effort está estimado en 8 pd.

**R5 — La calificación crediticia existe para el 39 % del universo (359 de 927).**
Es la cobertura más baja de los seis ejes de riesgo, y es tentador rellenarla.
*Mitigación:* la cobertura se declara al lado del eje (F-031), la calificación **nunca se usa como
filtro automático**, y donde falta se usan y se declaran los proxies ya calibrados: tope de rendimiento
sobre los pares del segmento, percentil de liquidez y concentración máxima. El análisis crediticio
sigue siendo del asesor. **No se construye un score compuesto** — ponderar años contra una calificación
que existe para el 39 % sería un juicio inventado presentado como dato.

**R6 — La lámina mínima no tiene fuente pública sistemática (568 de 927, 61 %).**
Sin lámina no se redondea, y sin redondeo la ponderación pedida y la real no difieren — que es
justamente el dato que la pantalla existe para mostrar.
*Mitigación:* F-024 no asume ningún default; marca la posición y la excluye del total ajustado. F-025
hace que la cobertura crezca por uso, con origen y fecha en cada valor y propagación entre especies.
Camino de ampliación conocido, no supuesto: los avisos de suscripción y prospectos de la CNV traen la
lámina por emisión, pero es carga manual por instrumento y **no se asume que la CNV lo exponga
programáticamente**.

**R7 — Discrepancia entre los conteos del universo: 937 vs 927.**
`product-definition.md` habla de 937 instrumentos de renta fija en la propuesta de valor y de 927 como
denominador de todas las coberturas.
*Mitigación:* se resuelve empíricamente en F-007, contando el universo consolidado real y publicando
el conteo en la barra de estado del dato. **No se reconcilia por elección: se mide.** Hasta que se
mida, cada cobertura se reporta con el denominador con el que fue medida.

**R8 — `consolidar_universo.py` sobrescribiría el universo dejando vacías las condiciones.**
Es una regla del proyecto: no se corre hasta que el ingestor se reescriba.
*Mitigación:* F-007 es el reemplazo, y la semilla de F-009 preserva `condiciones_estaticas.csv`,
`condiciones_monitor.csv` y el `condiciones_emision.csv` curado de 823 tickers, que el proyecto trata
como **irrecuperable**. El Ciclo 1 no toca el script viejo.

### Riesgos técnicos

**R9 — El desacople del motor resulta ser reescritura encubierta.**
El plan asume que envolver `armar_cartera.py` y `detectar_swaps.py` es trabajo de desacople (~30 % del
código) y no de reescritura. Si las funciones tienen estado global o dependencias de disco más
enredadas de lo previsto, el esfuerzo de F-019, F-032, F-033 y F-034 se dispara.
*Mitigación:* los 15 casos de regresión de `armar_cartera.py` y el swap TLCWO → TLCMO son los tests de
aceptación del servicio envuelto (F-019, F-032). Si el servicio no los reproduce, el desacople está
mal hecho y se detecta en el ciclo, no al final.

**R10 — El contrato de salida del universo se rompe y arrastra el 85 % reusado.**
El reuso del motor depende de que el esquema de PostgreSQL replique las columnas del `Resumen` actual y
de `cashflow_completo.csv`.
*Mitigación:* está como acceptance criteria explícito de F-002 y F-007. Cualquier baja de columna se
documenta como baja explícita, no como omisión.

**R11 — Performance de la grilla del monitor con ~1.700 filas.**
Ordenamiento y filtrado sobre esa cantidad de filas con render por fila degrada la experiencia de la
pantalla que se usa todos los días.
*Mitigación:* TanStack Table con virtualización, paginación por cursor desde F-001, y el conteo de
filas resultantes como criterio de aceptación de F-038.

**R12 — Los seis ejes se calculan distinto en el armador, en el diagnóstico y en la propuesta.**
Si divergen, las tres carteras dejan de leerse con la misma vara y la comparación pierde sentido.
*Mitigación:* F-031 es un servicio único consumido por los tres, y el criterio de aceptación de F-030
es explícito: la misma composición cargada y armada produce los mismos números.

### Riesgos de producto

**R13 — La grilla-selector no resulta mejor que la "Cuponera" que la mesa ya tiene.**
La Cuponera funciona bien y es la referencia. Si F-016 es sólo distinta y no mejor, el producto pierde
su diferenciador principal.
*Mitigación:* los diferenciadores están definidos y son verificables, no estéticos: universo completo
en vez de lista curada, las tres especies en vez de sólo las que liquidan en dólares, renta variable,
partir de una cartera existente, y sugerencias además de cálculo. Cada uno es una feature con
acceptance criteria. La Fase 3 (`design-system.md`) explora cinco direcciones antes de comprometerse.

**R14 — Sin el design system, el Ciclo 2 se bloquea.**
F-016 es 8 pd de UI sobre el camino crítico y depende de `design-system.md`, output de la Fase 3, que
ocurre fuera de la terminal.
*Mitigación:* la Fase 3 tiene que estar cerrada antes de que arranque el Ciclo 2. El Ciclo 1 no tiene
ninguna feature de UI más allá del esqueleto de F-003, así que hay ~9,5 semanas de margen. Está
declarado como criterio de entrada del Milestone 2.

**R15 — El optimizador propone rotaciones que en la práctica no convienen.**
Ya pasó: con las puntas reales el costo mediano pasó de 1,50 % a 3,10 %, y **12 de 51 rotaciones
superaban el 5 %**. Un optimizador sin costo real es una fuente de malas recomendaciones con apariencia
de análisis.
*Mitigación:* F-035 es prerrequisito de F-036: ninguna propuesta llega a la pantalla de aceptación sin
su costo desagregado en arancel y spread por pata. Las que superan el 5 % se marcan. Donde no hay dos
puntas vivas, el costo se declara no verificable y **no se asume un spread por defecto**.

**R16 — El producto se vuelve un CRM por acumulación.**
"Se guardan carteras, no clientes" es una frontera de producto, y las fronteras se erosionan de a un
campo por vez.
*Mitigación:* está como acceptance criteria de F-041 —una cartera guardada no contiene ningún campo de
identificación de cliente— y el CRM es F-043, explícitamente Stage 2.

**R17 — Adopción: los asesores tienen su planilla y su monitor.**
La alternativa no es "nada", es un flujo de trabajo que ya funciona.
*Mitigación:* el Flujo C (monitor de mercado, F-038) existe justamente para ser el punto de entrada
diario de bajo compromiso, y el Flujo B (diagnóstico de cartera ajena) entrega valor sin pedir que el
asesor cambie cómo arma. **No hay dato de adopción en los inputs**: se mide desde el primer uso real.

### Riesgos de seguridad y operación

**R18 — Fuga de carteras entre asesores.**
*Mitigación:* RLS en PostgreSQL desde F-002, verificada en F-014 con un criterio de aceptación que
saltea el frontend y consulta la API directamente.

**R19 — Secretos en el repositorio.**
El token de Docta y las claves de Supabase son los dos secretos vivos del proyecto.
*Mitigación:* Pydantic Settings desde `.env` únicamente (F-001), con arranque fallido si falta alguno,
y logs JSON que no emiten secretos.

**R20 — Datos de clientes reales en el repositorio.**
*Mitigación:* regla del proyecto — van a `~/Documents/IFA-confidencial/`. En Stage 1 el producto no
persiste identificación de clientes (F-041), lo que reduce la superficie a cero por diseño.

### Trazabilidad de las reglas del dominio

Cada regla de `CLAUDE.md` está materializada en features con criterios verificables:

| Regla | Features donde vive |
|---|---|
| 1. Nunca inventar un dato | F-005, F-007, F-009, F-017, F-023, F-024, F-027, F-029, F-035, F-039, F-040 |
| 2. No promediar rendimientos de distinta naturaleza | F-017, F-022, F-023, F-042, F-057 |
| 3. Nada se compara entre monedas sin normalizar | F-004, F-012, F-021, F-057 |
| 4. Riesgo soberano bajo `SOBERANO_AR` | F-020, F-031 |
| 5. Calendario de cupones como criterio de armado | F-015, F-016, F-021, F-036 |
| 6. Lógica determinística, sin IA | Todo el motor: F-010 … F-035 |
| 7. Riesgo como vector de seis ejes, sin score | F-031, F-033, F-034 |
| 8. Nunca mejora de TIR sin nombrar el riesgo | F-034 |
| 9. No filtrar por disponibilidad en Balanz | Ausencia deliberada: ninguna feature introduce whitelist |
| 10. No conectarse a `mesaifa.netlify.app` | Ausencia deliberada: ninguna fuente del pipeline lo referencia |
| 11. No suponer nada en la representación del dato | F-039, F-054, F-057 — los códigos propietarios de cada fuente se muestran sin traducir: `EXT` de BYMA, `USB` y los centinelas de `Plazo Liq.` de CAFCI |

---

## 10. Success metrics

Ninguna de estas métricas tiene línea de base en los inputs. **Todas son objetivos a medir desde el
primer uso real, no proyecciones.**

### Métricas de producto — ¿resuelve el problema que lo originó?

| Métrica | Definición | Objetivo | Cómo se mide |
|---|---|---|---|
| **Meses sin cobertura por cartera** | Cantidad de meses del año con renta cero en las carteras producidas con la herramienta | Bajar respecto de las carteras que el asesor traía | Se calcula en F-021 sobre cada cartera guardada |
| **Carteras existentes diagnosticadas** | Flujo B completado por mes | > 0 desde el primer mes — hoy es cero, porque son horas de trabajo manual | Conteo de F-030 ejecutadas |
| **Rotaciones aceptadas sobre propuestas** | Tasa de aceptación en F-036 | Una tasa muy baja indica propuestas irrelevantes; una muy alta, criterios demasiado laxos | F-036 |
| **Carteras guardadas por asesor activo** | Persistencia real de uso | Creciente | F-041 |

### Métricas de confiabilidad del dato — ¿se puede confiar en lo que muestra?

| Métrica | Definición | Objetivo | Cómo se mide |
|---|---|---|---|
| **Cobertura de lámina** | Instrumentos con lámina informada sobre el universo | Creciente desde el 61 % sembrado (568 de 927), por carga asistida | F-009 / F-025 |
| **Cobertura de spread** | Instrumentos con dos puntas vivas | Mayor que los 674 de 927 actuales, por el cambio de data912 a BYMA | F-035 |
| **Instrumentos descartados por sanidad** | Cantidad y motivo por corrida | Estable; un salto indica cambio de formato en una fuente | F-010 / F-013 |
| **Desvío del tipo de cambio implícito contra `index-price`** | Diferencia porcentual por corrida | Del orden del 0,14 % ya verificado contra fuente externa (1.530,90 vs 1.533) | F-012 |
| **Corridas de ingesta completas sin intervención** | Corridas exitosas sobre corridas programadas | Alto; las fallas se atribuyen a token vencido o API caída, distinguidas | F-008 / F-006 |
| **Números sin trazabilidad en pantalla** | Valores mostrados sin origen ni cobertura declarada | **Cero.** Es una condición de aceptación, no una métrica a optimizar | Revisión por pantalla |

### Métricas de ingeniería

| Métrica | Objetivo |
|---|---|
| Casos de regresión del motor que pasan tras el desacople | 15 de 15 en `armar_cartera.py`; TLCWO → TLCMO en `detectar_swaps.py`; RUCED, SBC2D, CS47D y LOC5D exactos en `cupones.py`; ≤ 0,12 pp de desvío en el repricing |
| Latencia de la grilla del monitor con ~1.700 filas | Ordenar y filtrar sin degradación perceptible |
| Fugas de datos entre asesores | Cero, verificado consultando la API directamente |
| Features de Stage 1 entregadas por ciclo | Según el plan de la sección 8 |

---

## 11. Candidatas del relevamiento de monitores (08/08/2026)

Salieron de recorrer el panel de Balanz y el Monitor Mesa IFA como **referencia visual** (regla 10:
de `mesaifa.netlify.app` no se toma dato, sólo se mira cómo presenta). Ninguna se construyó en esa
sesión — lo que se hizo fue mejorar lo ya entregado, sin adelantar features de tandas futuras.

**Lo que ya tiene dueño y espera su turno.** Estas ideas no son features nuevas: son detalles de
presentación para features que ya están planificadas, y se anotan en su ficha para que quien las
construya no tenga que redescubrirlos.

| Idea observada | Feature | Tanda |
|---|---|---|
| Curva TIR vs duration como scatter, con la familia (Bonares / Globales / Bopreal) por color y los tickers rotulados sobre los puntos | F-023 | 11 |
| Panel de distribución con barras por sector, ley y naturaleza de tasa | F-020 | 9 |
| Frecuencia de pago y días al próximo cupón como columnas de grilla, no sólo de ficha (regla 5 hecha columna) | F-021 | 9 |
| Renta variable en el armador reusando `TablaRentaVariable` y `SelectorMoneda` de `components/` | F-026 | 9 |

**Candidatas sin feature asignada.** Valen la pena y no están en el roadmap; entran por RICE cuando
se decida, no antes.

| Candidata | Por qué vale | Qué haría falta |
|---|---|---|
| **Matriz de sensibilidad multi-instrumento**: una fila por bono, una columna por TIR objetivo (−5 % a +5 %), con heatmap | F-040 ya calcula el repricing de un instrumento contra escenarios; esto es la misma cuenta sobre una familia entera, que es como se mira en la mesa | Extender el endpoint de sensibilidad a varios tickers; agrupar por familia y **nunca mezclar familias en una misma tabla** (regla 2) |
| **Badge de familia** (Bonares / Globales / Bopreal) en la grilla | Agrupa sin gastar una pestaña | **Salvedad de la regla 11**: derivarla del prefijo del ticker es manipulación de strings. Sólo entra si `subtipo` la declara — `subtipo_de()` ya distingue global de bonar por ley, así que hay de dónde |

**Dos candidatas dejaron esta tabla el 13/08/2026**, promovidas a feature por el relevamiento de Docta:
el **spread por legislación** quedó absorbido por **F-059** —es el caso particular de comparar dos
instrumentos con la misma vara— y las **tarjetas de tipo de cambio implícito** son ahora **F-068**, que
puntúa 266,7 y es de las más altas del plan: el cálculo ya está hecho y verificado desde F-012, sólo
falta la pantalla.

**Lo que no se copia, y por qué.** El panel de Balanz abre la solapa de Corporativos en una landing
comercial con ONs destacadas y botón "Invertir". Es su selección de producto: exactamente la
whitelist de disponibilidad que la **regla 9** prohíbe reintroducir. Nosotros mostramos todo lo
negociable. Tampoco se copian los botones de comprar y vender: acá no se opera.

---

*Fin del plan. Próxima fase: 3 — Claude Design → `claude-docs/planning/design-system.md`.*
