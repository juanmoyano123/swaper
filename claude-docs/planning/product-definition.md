# Product Definition — 10-Swaper (Armador y Optimizador de Carteras)

Fecha: 05/08/2026
Input: idea-brief.md

---

## Descripción del producto

10-Swaper es una aplicación web para asesores financieros de una ALyC argentina que
convierte el **calendario de cupones en el selector de la cartera**, no en el reporte que
sale al final. El asesor ve los doce meses del año con los papeles que pagan en cada uno y
arma la cartera eligiendo desde el mes que necesita cubrir, viendo actualizarse en vivo la
renta mes a mes en plata real, el total anual de cupones sobre lo invertido y la
composición por emisor, sector y naturaleza de tasa.

Resuelve dos problemas del mismo origen. El primero: hoy el calendario **se descubre, no se
diseña** — los Excel de la mesa lo traen como una hoja más y con precios de meses atrás, el
monitor interno lo muestra pero es de sólo lectura, y los screeners ordenan por TIR y
vencimiento. La consecuencia se repite: carteras donde toda la renta cae en dos meses del
año porque nadie eligió que fuera así. El segundo: cuando llega un cliente con una cartera
armada en otro lado, evaluarla contra el mercado es trabajo manual de horas, así que en la
práctica no se hace.

El producto no arranca en cero. Hay un motor de cálculo en Python **construido y verificado
contra fuentes reales** (el Excel de la mesa, swaps efectivamente ejecutados por la mesa, y
los números publicados del monitor interno). 10-Swaper es, en buena medida, ponerle una
interfaz multiusuario y una base de datos a un motor que ya produce resultados correctos.

---

## Usuario objetivo

**Asesor financiero de una ALyC argentina**, y asesores independientes que operan a través
de ella.

**Qué es y qué no es.** No es trader ni analista cuantitativo. Atiende clientes minoristas y
necesita llegar a una reunión con una propuesta defendible. Trabaja todo el día con la misma
pantalla abierta y opera en las tres monedas de liquidación: pesos, dólar MEP y dólar cable.

**Su cliente típico se declara arriesgado y se comporta conservador.** Por eso la cartera
estándar es 60-70% renta fija / 30-40% renta variable, y por eso lo que sostiene la
conversación no es la ganancia de capital sino el flujo de cupones: la pregunta del cliente
es "¿cuánto voy a cobrar y cuándo?".

**Qué le vende al cliente.** Certeza de cobro. El calendario de cupones *es* el argumento de
venta, y por eso una cartera con toda la renta concentrada en marzo y septiembre es un
problema comercial, no sólo técnico.

**Qué exige de una herramienta.** Que sea determinística y auditable. Pedido textual
registrado en el proyecto: *"no busco algo que razone, sino que analice datos y me devuelva
un análisis de datos duros"*. Cualquier número que la pantalla muestre tiene que poder
rastrearse hasta un dato de fuente. No tolera que la herramienta complete un hueco por
inferencia.

**Restricción operativa relevante.** El proyecto tiene una regla dura y explícita: 10-Swaper
**no se conecta al monitor de mesa** (`mesaifa.netlify.app`) ni a su base de datos, en
ninguna forma. Los datos que hoy provienen de ahí son extracciones manuales puntuales, y así
se modelan en el producto.

---

## Propuesta de valor

**Contra la pantalla "Cuponera" que la mesa ya tiene** — la referencia más cercana, y que
funciona bien: universo completo (937 instrumentos de renta fija más 69 acciones y 683
CEDEARs, verificado) en vez de una lista curada a mano; las tres especies de liquidación de
cada bono en vez de sólo las que liquidan en dólares; renta variable además de renta fija;
capacidad de partir de una cartera existente; y sugerencias de rotación, no sólo cálculo.

**Contra los Excel de carteras sugeridas:** precios de hoy en vez de una foto de hace meses.
Es una herramienta, no un documento que envejece.

**Contra los screeners de mercado:** el calendario es la puerta de entrada. En cualquier otro
lado es un dato al que hay que ir a buscar papel por papel.

**Contra armarlo a mano en Excel:** dos reglas del dominio que la herramienta respeta y las
planillas no.

1. **No mezcla naturalezas de tasa.** Una TIR del 7% en dólares, una tasa *real* del 4% sobre
   CER y una TNA *nominal* del 40% en pesos son magnitudes de unidades distintas: no se
   promedian, no comparten eje y no entran al mismo ranking. El motor ya segmenta el universo
   en seis segmentos agrupados en cuatro naturalezas de tasa, y esa frontera es estructural,
   no una opción de visualización.
2. **Cuando falta un dato, lo dice.** No estima, no completa por inferencia, no deja la celda
   vacía en silencio. Esta regla tiene antecedente caro en el proyecto: dos episodios de
   invención (una categoría de ley que la fuente no publica, y 121 tickers derivados por
   manipulación de strings que no existían) se detectaron y revirtieron. La cobertura declarada
   bajó y esa baja es el punto: es la diferencia entre cobertura inferida y cobertura respaldada.

**Y una tercera, específica del optimizador:** nunca se propone una mejora de TIR sin nombrar
su contrapartida. Más TIR siempre se paga con algo — duración, crédito, jurisdicción, liquidez
o concentración — y el producto lo declara en la misma fila de la propuesta.

---

## MVP definido

Dos herramientas sobre una misma base de datos de mercado, con login multiusuario desde el
arranque. Queda **explícitamente afuera todo lo que sea CRM**: no hay ficha de cliente, ni
historial de contactos, ni seguimiento comercial. Los objetivos del cliente se cargan como
parámetros de la cartera que se está armando, no como un registro que persiste. **Se guardan
carteras, no clientes.**

### Features Stage 1

---

**F1 — Ingesta y consolidación del universo**

Pipeline que arma la única base de mercado del producto, corriendo una vez a la mañana y
refrescando precios durante la rueda. Une tres fuentes que se complementan sin superponerse:
**BYMA** (API abierta, POST sin token, verificada el 05/08/2026 — `negociable-obligations`
4.909 filas, `public-bonds` 189, `cedears` 2.267, `general-equity` 189, `index-price` 16) da
la rueda: `bidPrice`/`offerPrice` con cantidades, `denominationCcy` con la moneda de
cotización **declarada** (no hay que inferirla del sufijo del ticker), `settlementType`,
`closingPrice`, `vwap`, `volume`, `volumeAmount`, `numberOfOrders`, `maturityDate`. **IAMC**
(informe diario de deuda corporativa, ~260 ONs) da el instrumento: emisor con nombre completo,
ley y moneda de pago —que son el título de la sección del informe, no una columna inferida—,
estructura del cupón, tasa, frecuencia, próximo cupón, próximo pago de capital, valor
residual, paridad, valor técnico, TIR, duración modificada, convexidad, vida promedio y
volumen medio de 20 ruedas. **El feed de cashflow** aporta el cronograma completo de pagos
futuros por ticker (ver "Hueco de datos declarado" más abajo). Se unen por la raíz del ticker,
porque ley, moneda de pago y estructura son atributos de la emisión y no de la especie.

*Por qué Stage 1:* sin esto no hay producto. Todo lo demás lee de acá.

---

**F2 — Capa de integridad del dato**

No es una feature de infraestructura: es una feature de producto, porque su salida es visible
en pantalla. Aplica, en este orden, la lógica ya construida y verificada:

- **Sanidad en dos capas.** Coherencia entre especies del mismo bono (un bono tiene UNA TIR;
  cuando una especie se despega de las otras por más de 100 pp, esa especie tiene el precio mal
  escalado — VSCQD figuraba con 34.627.917% mientras VSCQO, el mismo bono, rendía 6,75%) y techo
  de lo posible **por segmento y en la unidad de cada segmento** (hard-dollar y dólar-linked
  300%, CER 100% de tasa *real*, tasa fija/Badlar/Tamar 500% de TNA *nominal*). Los topes son
  holgados a propósito: SNSBO rinde 245% en dólares y es dato **correcto** — bono a 80 días
  cotizando al 78% de su valor técnico. Un umbral ajustado lo mataría junto con la basura.
- **Deduplicación de especies de liquidación.** MR46O, MR46D y MR46C son el mismo bono; comprar
  dos es comprar el mismo bono creyendo que se diversifica. Se colapsan para el armador y se
  conservan vivas para el optimizador, porque los swaps de perfil rotan justamente entre
  especies de la misma emisión (MEP → Cable).
- **Normalización de monedas.** `volume`/`volumeAmount` viene en la moneda de cotización de cada
  especie, igual que el precio: la especie en pesos de un bono muestra ~1.500× más volumen que
  su especie en dólares por el tipo de cambio, no por operarse más. Todo se lleva a dólares
  antes de comparar liquidez.
- **Barra de estado del dato**, global y siempre visible: hora del último refresh, demora
  declarada de la fuente (BYMA abierta tiene **20 minutos de demora**), cantidad de instrumentos
  descartados por sanidad con el detalle, y cobertura de cada campo crítico.

*Por qué Stage 1:* la regla "cuando falta un dato, lo dice" es una promesa de producto. Sin la
capa que la implementa, la promesa es decorativa.

---

**F3 — Autenticación y espacio de trabajo por asesor**

Login con Supabase Auth (email + contraseña, con invitación; sin registro abierto). Cada asesor
ve exclusivamente sus propias carteras, aplicado con Row Level Security en PostgreSQL, no con
filtros del lado del cliente. La base de mercado, en cambio, es compartida y única: el universo,
los precios y las condiciones de emisión son los mismos para todos.

*Por qué Stage 1:* decisión ya tomada por el usuario. Además es más barato construirlo con RLS
desde la primera tabla que retrofitearlo sobre datos existentes.

---

**F4 — Calendario-selector de doce meses**

**La feature central: sin esta mecánica el producto no existe.** Grilla de doce meses. En cada
mes, los papeles que pagan renta ese mes con ticker, cuánto paga de cupón, TIR y vencimiento.
Al hacer clic en un papel entra a la cartera y **se ilumina simultáneamente en todos los meses
en que paga**, así la cobertura del año se lee de un vistazo. Los meses sin cobertura quedan
visualmente marcados: un cero explícito vale más que una celda ausente cuando lo que se evalúa
es la continuidad del ingreso.

Filtros sobre la grilla: segmento (obligatoriamente uno por vez o con la unidad declarada por
columna), horizonte de duración, percentil de liquidez, sector, emisor, ley, frecuencia de
cupón. Amortización y renta se distinguen: **cobrar amortización no es renta**, y el motor ya
lo separa (`pct_interes` vs `pct_capital`).

*Por qué Stage 1:* es la razón de ser del producto y el único diferenciador que ninguna
alternativa cubre.

---

**F5 — Cartera editable y ponderación**

Panel lateral con las posiciones elegidas. Se edita el peso de cada una (por porcentaje o por
monto), se quita, se reordena. Alternativamente, un botón de **armado asistido** que precarga
una cartera de arranque a partir de monto, moneda de referencia, objetivo de cobertura
(devaluación / inflación / tasa en pesos / mixta), perfil (conservador / moderado / agresivo) y
horizonte (corto / medio / largo) — el asesor la toma como punto de partida y la edita a mano.

Los límites de concentración se muestran y se advierten en vivo, con el criterio ya calibrado:
tope por emisor corporativo, **tope separado para el riesgo soberano** (el Tesoro emite bajo
muchos prefijos —GD, AE, DIC, TZX, TY3— y todos son el mismo crédito; sin esta separación una
cartera 100% soberana pasaba como diversificada) y tope por sector, con Soberano y Subsoberano
exentos porque ya los acota el tope soberano.

*Por qué Stage 1:* el calendario selecciona, pero sin ponderación editable no hay cartera; y el
armado asistido es lógica que ya está escrita y verificada con 15 casos de regresión.

---

**F6 — Panel de renta y métricas, con la unidad declarada**

Se actualiza con cada clic. Muestra:

- **Renta mes a mes en plata real** y el **total anual de cupones sobre lo invertido**, que es
  el número que el asesor lleva a la reunión. Sale de la matemática ya validada contra el Excel
  real de la mesa: reproduce **exacto** los nominales de RUCED, SBC2D, CS47D y LOC5D.
- **Rendimiento ponderado abierto por naturaleza de tasa** — cuatro números, nunca uno solo:
  TIR en dólares, rendimiento dólar-linked, tasa real sobre CER, TNA nominal en pesos. La
  pantalla no ofrece la opción de colapsarlos en un promedio, porque ese promedio no significa
  nada.
- **Duración ponderada** en años, etiquetada como *plazo promedio*. La sensibilidad de precio se
  reporta **por segmento**, no agregada: la duración modificada es elasticidad respecto de la
  tasa propia de cada segmento, y sumarlas cruzaría naturalezas.
- **Composición** por emisor, sector, clase de activo (soberano / subsoberano / ON) y segmento.
- **Curva TIR/duración** del segmento activo con las posiciones de la cartera marcadas sobre la
  nube de candidatos.
- **Meses sin cobertura**, mes más flaco y mes más fuerte.

Los totales mensuales se expresan en la moneda de referencia declarada de la cartera, y se
muestran **también desagregados por moneda de cobro**, porque un cupón en pesos y uno en dólares
no son el mismo peso hasta que se declara el tipo de cambio usado.

*Por qué Stage 1:* es el feedback en vivo que hace del calendario un selector y no una consulta.

---

**F7 — Lámina mínima: redondeo, declaración de faltante y carga asistida**

Cuando la lámina está informada, el sistema redondea el nominal al múltiplo correspondiente y
**muestra la diferencia entre la ponderación pedida y la real** — que es justamente lo que hace
que difieran. Cuando no está informada, no redondea, no asume 1 ni 1.000 ni ningún default de
mercado: marca la posición como *lámina no informada*, la excluye del total ajustado y ofrece un
campo para que el asesor la tipee. Lo que tipea queda guardado con su origen y su fecha, se
propaga a las otras especies de la misma emisión (la lámina es atributo de la emisión, no de la
especie) y queda disponible para todos los asesores. La cobertura crece por uso.

*Por qué Stage 1:* el paso 5 del flujo de armado depende de esto. Ver la resolución de la
cuestión abierta N.º 2 más abajo.

---

**F8 — Bloque de renta variable**

Acciones locales y CEDEARs con su precio, su volumen y su **calendario de presentación de
balances**, que es el equivalente del cupón del lado de la renta variable. Las fechas salen de
SEC EDGAR (`data.sec.gov`, gratuita, sin clave) para los CEDEARs de empresas estadounidenses y
de la CNV para emisores argentinos. EDGAR registra lo ya presentado, no un calendario a futuro;
el patrón mensual es estable y es lo que se necesita, y **la pantalla lo declara como patrón
histórico, no como fecha confirmada**.

**Sin TIR, sin duración y sin cashflow: no se mezcla con la renta fija en ningún cálculo.** La
frontera ya vive en un solo lugar del motor (`cargar_universo()` devuelve renta fija y nada más;
la renta variable se pide aparte y a propósito), y la interfaz la replica: el bloque de renta
variable es una sección separada con su propio total, que suma al monto de la cartera pero no al
cálculo de renta ni a los rendimientos ponderados.

*Por qué Stage 1:* decisión ya tomada por el usuario, y la cartera estándar del cliente es
60-70/30-40. Una propuesta que sólo cubre la renta fija no es la propuesta que el asesor lleva a
la reunión.

---

**F9 — Carga y valuación de cartera existente**

Tres vías de entrada: pegar desde el portapapeles (el formato en que llega el resumen de cuenta),
subir un CSV/Excel, o cargar posición por posición. El sistema resuelve los tickers contra el
universo, marca los que no reconoce **sin descartarlos en silencio**, y valora todo a precios de
hoy. Devuelve la descripción de la cartera tal como está: renta mes a mes, meses vacíos,
rendimientos por naturaleza de tasa, plazo promedio, concentración por emisor y por sector.

*Por qué Stage 1:* es la puerta de entrada de la mitad del producto (Flujo B). El diagnóstico
solo ya tiene valor comercial: hoy nadie lo hace porque son horas de trabajo manual.

---

**F10 — Diagnóstico de riesgo en seis ejes**

El perfil de riesgo de una cartera es un **vector de seis ejes, no un score**: duración, crédito,
legislación, liquidez, concentración y moneda. Cada eje con su métrica, su unidad y su cobertura
de dato declarada. Nunca se colapsan en un número único — un score compuesto tendría que ponderar
magnitudes de distinta naturaleza, que es exactamente lo que las reglas del dominio prohíben.

Los ejes se muestran igual para la cartera cargada, la cartera en construcción y cualquier
propuesta, así las tres se leen con la misma vara.

*Por qué Stage 1:* es la definición operativa de "riesgo" de la que depende el optimizador. Ver
la resolución de la cuestión abierta N.º 1.

---

**F11 — Optimizador de rotaciones, en dos modos**

Sobre la cartera cargada (o la que se está armando), propone rotaciones **dentro del mismo
segmento**: un cruce CER → hard-dollar es una visión macro humana, no un swap, y el motor no lo
propone. Dos modos:

- **Mantener la TIR y bajar el riesgo.** El asesor elige **cuál de los seis ejes minimizar**. El
  sistema propone destinos que mejoran estrictamente ese eje, **no empeoran ninguno de los otros
  cinco**, y mantienen el rendimiento dentro de una banda de ±0,5 pp — la misma banda que el motor
  ya usa para considerar dos candidatos parejos.
- **Subir la TIR declarando qué riesgo se asume a cambio.** Cada propuesta lleva, en la misma
  fila, el eje o los ejes que empeoran y en cuánto: "+180 bps de TIR / duración +2,3 años / ley
  ARG en vez de NY". **Nunca se propone una mejora de TIR sin nombrar su contrapartida.**

En los dos modos, cada propuesta trae el **costo real de rotar**, que no es sólo el arancel: la
rotación paga el spread bid/ask en las dos patas. Con las puntas reales el costo mediano medido
pasó de 1,50% a **3,10%**, y 12 de 51 rotaciones superaban el 5% — el motor venía proponiendo
swaps que en la práctica no convenían. También trae el aviso de **cupón próximo** (rotar tres días
antes de cobrar tiene un costo que no está en el precio) y el **efecto sobre el calendario**: qué
mes se llena, qué mes se vacía.

El asesor acepta o descarta **rotación por rotación**, y ve el calendario y los seis ejes moverse
con cada decisión. Al final, comparación de la cartera original contra la propuesta, lado a lado.

*Por qué Stage 1:* es la mitad del producto que el usuario declaró no negociable, y la lógica
—incluido el ranking de destinos con filtro de liquidez y de rendimiento mínimo— está construida
y validada contra swaps que la mesa efectivamente ejecutó (TLCWO→TLCMO).

---

**F12 — Monitor de mercado y detalle de instrumento**

El universo por segmento, con filtros y orden, para consultar sin armar nada: el uso de "abro la
herramienta a la mañana y miro cómo está el mercado". Cada fila abre la **ficha del instrumento**:
condiciones de emisión (emisor, ley, moneda de pago, estructura del cupón, tasa, frecuencia,
lámina, calificación cuando existe), las tres especies de liquidación con sus precios y puntas, el
flujo de fondos completo hasta el vencimiento, y la sensibilidad del precio a movimientos de su
TIR calculada por **repricing completo del cashflow contractual**, no por aproximación lineal de
duración (en bonos largos la aproximación subestima fuerte la suba ante compresiones grandes, y
esos son justamente los escenarios que interesan; el método está verificado contra una tabla
externa con desvío máximo de 0,12 pp sobre movimientos de hasta +91%).

*Por qué Stage 1:* es la pantalla de entrada diaria y el destino natural de cada ticker que
aparece en el armador y en el optimizador. Sin ella, el asesor sigue yendo a otra herramienta a
mirar la ficha.

---

**F13 — Mis carteras: guardar, versionar y exportar**

Listado de las carteras guardadas del asesor, con nombre, fecha, monto, moneda de referencia y un
resumen de una línea. Cada cartera se guarda **con los precios del momento en que se guardó** —
una propuesta tiene que poder reproducirse tal como se presentó— y se puede reabrir para valuarla
a precios de hoy, con la diferencia explícita. Exportación a Excel y a PDF como documento interno
de trabajo: el asesor arma la presentación final al cliente por su cuenta.

*Por qué Stage 1:* sin persistencia el producto es una calculadora de una sesión, y el login (F3)
no tendría objeto.

---

### Fuera del MVP (Stage 2)

Gestión de clientes y CRM, historial de propuestas y seguimiento de performance, colocaciones
primarias, fondos comunes de inversión (**siguen sin fuente** — verificado el 30/07/2026: no hay
submercado FCI ni cuotapartes en las fuentes disponibles; las carteras de la mesa los usan, así que
en el MVP van como línea con peso y sin precio), opciones, alertas y notificaciones, comparación de
carteras entre sí, y el reemplazo del feed demorado de 20 minutos por la API Market Data oficial de
BYMA (que según BYMA no requiere homologación y se solicita a `marketdata@byma.com.ar`).

---

## Diferenciadores

1. **El calendario es el selector.** En todas las alternativas —la Cuponera de la mesa incluida— el
   calendario es una salida. Acá es la entrada, y esa inversión es lo que evita el problema que
   origina el producto: nadie elige que toda la renta caiga en marzo y septiembre; les pasa.
2. **Un motor verificado contra la realidad, no contra sí mismo.** La matemática de cupones
   reproduce exacto los nominales del Excel real de la mesa (4 de 4 casos). El detector de swaps
   reproduce swaps que la mesa efectivamente ejecutó. El tipo de cambio implícito da 1.530,90 contra
   1.533 de una fuente externa independiente (0,14% de diferencia). El repricing reproduce una tabla
   externa con 0,12 pp de desvío máximo. Ninguna herramienta de este segmento publica su
   verificación.
3. **Las unidades se respetan.** Seis segmentos, cuatro naturalezas de tasa, y la prohibición
   estructural de promediarlas. Es la diferencia entre una herramienta y una planilla vistosa.
4. **Los huecos son visibles.** Cobertura declarada campo por campo, instrumentos descartados por
   sanidad listados con su motivo, y ninguna celda completada por inferencia. El asesor sabe sobre
   qué está decidiendo.
5. **La contrapartida siempre se nombra.** Ningún competidor propone una rotación diciendo qué se
   está pagando por la TIR extra.
6. **Las tres especies.** El mismo bono cotiza en pesos, MEP y Cable, y esas tres cotizaciones ni se
   suman ni se confunden con diversificación. El producto las trata correctamente en las dos
   direcciones: colapsadas para armar, vivas para rotar.

---

## Stack tecnológico recomendado

- **Frontend:** React 19 + TypeScript, SPA con Vite. Sin renderizado en servidor: es una herramienta
  interna, no hay SEO ni primera carga fría que optimizar. TanStack Query para el estado de servidor
  y la invalidación en cada refresh de precios; TanStack Table para las grillas densas (el monitor
  tiene ~1.700 filas con ordenamiento y filtrado); Tailwind CSS; Recharts para la curva TIR/duración
  y el gráfico de renta mensual. Zod para validar en el borde todo lo que entra por carga de cartera.
- **Backend:** Python 3.12 + FastAPI. Toda la lógica financiera vive acá, que además de correcto es
  lo barato: el motor ya está escrito en Python y verificado. pandas ya es dependencia. El pipeline
  de ingesta corre como job programado del mismo servicio.
- **Base de datos:** Supabase (PostgreSQL) + Supabase Auth + Row Level Security. Tablas de mercado
  compartidas (`instrumentos`, `precios`, `puntas`, `cashflow`, `condiciones_emision`) y tablas de
  usuario con RLS (`carteras`, `posiciones`, `propuestas`). `condiciones_emision` es la que recibe la
  carga asistida de láminas de F7, con columna de origen y fecha en cada valor.
- **Hosting Stage 1:** frontend en Vercel o Cloudflare Pages; backend FastAPI containerizado en
  Fly.io o Railway; Supabase managed. Cero operaciones y costo mínimo, que es lo que corresponde a un
  producto con un puñado de usuarios internos.
- **Hosting Stage 2:** AWS (ECS Fargate + RDS).

### Rol del motor existente — qué se reusa, qué se envuelve, qué se reescribe

Esta es una decisión de producto con impacto real en el plazo, no un detalle de implementación.

**Se reusa tal cual, sin tocar la lógica (~55% del código actual):**

- `segmentos.py` — segmentación en seis segmentos y cuatro naturalezas de tasa, sanidad del dato en
  dos capas, deduplicación de especies, tipo de cambio implícito, normalización de volumen a dólares,
  agrupación por clave de riesgo con el soberano aparte. Es el módulo más crítico y el más verificado.
- `cupones.py` — flujos por peso, calendario de doce meses, valor técnico, frecuencia de cobro,
  repricing por descuento completo. Alimenta F4, F6, F11 y F12 sin modificaciones.
- `mercado.py` — puntas bid/ask y costo real de rotar. Sólo cambia de dónde vienen las puntas: BYMA
  publica `bidPrice`/`offerPrice` en el mismo endpoint que el precio, lo que además **elimina la
  dependencia de data912** y mejora la cobertura de spread (hoy 674 de 927 instrumentos).

**Se envuelve como servicio: el núcleo se conserva, el entorno se reemplaza (~30%):**

- `armar_cartera.py` y `detectar_swaps.py`. Las funciones de cálculo —`resolver_mix`,
  `candidatos_del_segmento`, `elegir_siguiente`, `armar`, `verificar_concentracion`, `resumir`,
  `evaluar_par`, `detectar`, `tabla_spread_legislacion`, `hoja_sensibilidad`— se conservan. Lo que se
  descarta es la cáscara: `main()` con argparse, `exportar()`/`exportar_excel()` con openpyxl, y la
  lectura desde archivos en disco. En su lugar, endpoints FastAPI que reciben JSON y devuelven JSON.
  El trabajo es de desacople, no de reescritura: los parámetros que hoy son flags de CLI pasan a ser
  un modelo Pydantic, y los DataFrames que hoy van a hojas de Excel se serializan.
- La lista de alertas que hoy se acumula en una hoja "Alertas" pasa a ser un array estructurado en la
  respuesta, y la interfaz la renderiza en la barra de estado del dato (F2). El contenido no cambia.

**Se reescribe (~15%):**

- `consolidar_universo.py`. Está atado a la API de Docta: tres links tokenizados que devuelven Excel
  por HTTP, con sus trampas conocidas (HTTP 500 = token vencido, cero filas erráticas que exigen 5
  reintentos con espera creciente, `fromDate` hardcodeado que hay que reescribir a ventana móvil). El
  nuevo ingestor consume BYMA por POST sin token e IAMC del informe diario, y escribe a PostgreSQL en
  vez de a Excel. **Se conserva el contrato de salida**: el esquema de las tablas replica las columnas
  del `Resumen` actual y de `cashflow_completo.csv`, así todo lo que consume el universo no se entera
  del cambio de fuente. Esto es lo que permite reusar el 85% restante.
- `merge_condiciones.py` y `aplicar_sectores.py` pasan a ser operaciones sobre la tabla
  `condiciones_emision`, conservando su lógica de herencia entre especies y de detección de conflictos
  (que **vacía lo contradictorio y lo reporta, sin elegir fuente por cuenta propia**).
- Los `data/condiciones_estaticas.csv` (272 tickers) y `condiciones_monitor.csv` (526 tickers) se
  migran como semilla inicial de la tabla, cada valor con su origen declarado.

**Hueco de datos declarado.** BYMA no publica cronograma de pagos, e IAMC publica próximo cupón y
próximo pago de capital, no el calendario completo hasta el vencimiento. Pero **el calendario completo
es el corazón del producto**: sin él, F4 se degrada a "el próximo pago de cada bono" y la grilla de
doce meses deja de existir. Hoy ese dato viene del endpoint `/api/cash-flow` de Docta, con 97% de
cobertura de las emisiones. La resolución que propongo es **conservar ese feed como fuente de cashflow
en el MVP**, con BYMA e IAMC cubriendo precios, puntas y métricas del instrumento — es una ingesta
multi-fuente con precedencia declarada por campo, no un reemplazo. La alternativa —proyectar el
calendario desde la estructura del cupón publicada por IAMC— funciona para bullets de cupón fijo y
falla en los amortizing con escalera, que son mayoría entre las ONs locales; proyectarlos sería
inventar. **Esta es la única decisión de fuente que queda por confirmar con el usuario**, y conviene
cerrarla antes de la Fase 2 porque define si F4 entra completa al Stage 1.

---

## Flujos principales

### Flujo A — Armar una cartera desde cero

1. El asesor entra y elige "cartera nueva".
2. Define los parámetros: monto, moneda de referencia, horizonte, perfil y contra qué riesgo quiere
   cubrirse. Opcionalmente parte de un armado asistido.
3. Cae en el **calendario de doce meses** filtrado por esos parámetros.
4. Va eligiendo papeles mes a mes. Cada clic ilumina el papel en todos los meses en que paga y
   actualiza el panel de renta: cuánto se cobra cada mes, cuánto suma el año sobre lo invertido, qué
   meses siguen vacíos.
5. Ajusta las ponderaciones. Donde hay lámina informada, el sistema redondea al múltiplo y muestra la
   diferencia entre lo pedido y lo real; donde no la hay, lo declara y ofrece cargarla.
6. Agrega la porción de renta variable, en su bloque separado y con su calendario de balances.
7. Revisa el resumen: renta anual, rendimientos abiertos por naturaleza de tasa, plazo promedio,
   concentración por emisor y sector, meses sin cobertura, y las alertas de dato faltante o descartado.
8. Guarda y exporta.

### Flujo B — Optimizar una cartera existente

1. El asesor pega, sube o tipea el portafolio que trae el cliente. Los tickers que no se reconocen se
   marcan, no se descartan.
2. El sistema lo valora a precios de hoy y lo diagnostica: renta mes a mes, meses vacíos, rendimientos
   por naturaleza de tasa, plazo promedio y el **vector de seis ejes de riesgo**.
3. El asesor elige el modo. Si es *bajar riesgo*, elige además cuál de los seis ejes minimizar.
4. El sistema muestra las propuestas de rotación, cada una con su efecto sobre el calendario, su costo
   real de rotar (arancel + spread en las dos patas), el aviso de cupón próximo si corresponde, y —en
   el modo de subir TIR— la contrapartida nombrada.
5. Acepta o descarta rotación por rotación, viendo moverse el calendario y los seis ejes.
6. Compara la cartera original contra la propuesta, lado a lado.
7. Guarda y exporta.

### Flujo C — Consulta de mercado

1. El asesor abre la herramienta a la mañana y entra al **monitor**.
2. Elige un segmento y mira la curva TIR/duración con las alertas del día: qué se descartó por sanidad,
   qué cobertura tiene el dato, a qué hora se refrescó.
3. Abre la ficha de un instrumento: condiciones de emisión, tres especies, flujo de fondos completo,
   sensibilidad a movimientos de su TIR.
4. Desde ahí, lo agrega a una cartera nueva o busca en cuáles de sus carteras guardadas ya está.

---

## Pantallas esenciales

1. **Login** — email y contraseña por invitación. Sin registro abierto.
2. **Armador** — calendario selector de doce meses, cartera editable con ponderación, panel de renta,
   composición, curva TIR/duración, bloque de renta variable.
3. **Optimizador** — carga del portafolio, diagnóstico con los seis ejes, propuestas de rotación en dos
   modos, aceptación rotación por rotación, comparación antes/después.
4. **Monitor de mercado** — el universo por segmento, con filtros y orden, para consultar sin armar.
5. **Mis carteras** — listado de las carteras guardadas del asesor, con reapertura y revaluación.
6. **Detalle de instrumento** — ficha con condiciones de emisión, las tres especies, flujo de fondos
   completo y sensibilidad a la TIR.

Transversal a todas: **barra de estado del dato** con hora del último refresh, demora declarada de la
fuente, instrumentos descartados por sanidad y cobertura de los campos críticos. No es una pantalla,
está siempre visible.

---

## Resolución de las cuestiones abiertas

### 1. "Reducir el riesgo" no es una sola cosa — resolución: seis ejes, el asesor elige cuál minimizar, y el resto no puede empeorar

**Resolución.** No se construye un score de riesgo. El riesgo de una cartera se modela como un vector
de **seis ejes**, cada uno con su métrica, su unidad y su cobertura de dato declarada:

| Eje | Métrica | Fuente | Cobertura medida |
|---|---|---|---|
| Duración | Duración modificada ponderada, en años | IAMC / derivada del cashflow | 618 de 927 con TIR y duración; el resto no cotiza |
| Crédito | Clase (soberano / subsoberano / corporativo) + calificación cuando existe | Clase del universo; calificación de carga manual | Clase 100%; **calificación 359 de 927 (39%)** |
| Legislación | % de la cartera bajo ley extranjera vs ley argentina | IAMC (título de sección, no columna inferida) | 691 de 927 (75%) con herencia entre especies |
| Liquidez | Percentil de volumen operado **en dólares** dentro del segmento + spread bid/ask | BYMA | Volumen completo; spread según haya dos puntas vivas |
| Concentración | Máximo por clave de riesgo (grupo emisor, con `SOBERANO_AR` como clave única) y por sector | Derivada | 100% por emisor; sector efectivo 903 de 927 (97%) |
| Moneda | Composición por naturaleza de tasa: hard-dollar, dólar-linked, CER, tasa nominal en pesos | Segmentación | 100% |

**Cómo opera el modo "bajar riesgo":** el asesor elige **un eje primario** a minimizar. El default es
**duración**, por dos razones: es el único eje con cobertura casi total sobre los instrumentos que
efectivamente cotizan, y es el más medible sin depender de un dato que falta. El sistema propone
destinos que (a) mejoran estrictamente el eje elegido, (b) **no empeoran ninguno de los otros cinco**
—criterio de no-empeoramiento, no de compensación—, y (c) mantienen el rendimiento dentro de ±0,5 pp,
la banda que el motor ya usa para considerar dos candidatos parejos. Si no hay ningún destino que
cumpla las tres condiciones, el sistema **dice que no hay propuesta** en vez de relajar la restricción
en silencio.

**Fundamento.** Un score compuesto exigiría ponderar duración en años contra concentración en
porcentaje contra una calificación crediticia que sólo existe para el 39% del universo. Esa ponderación
sería un juicio de valor inventado, presentado como un número — exactamente lo que las dos reglas del
dominio prohíben. Además, los ejes se mueven en sentidos opuestos con frecuencia: bajar duración
suele significar subir concentración, porque el tramo corto de la curva tiene menos emisores. Un score
escondería ese trade-off; el vector lo muestra. Y hay precedente en el propio motor: los rendimientos
ya se reportan abiertos en cuatro naturalezas por la misma razón.

**Consecuencia de producto:** el eje "crédito" se muestra siempre con su cobertura al lado, y donde
falta la calificación el sistema usa —y lo declara— los proxies ya calibrados: tope de rendimiento
sobre los pares del segmento, percentil de liquidez y concentración máxima. La calificación **nunca se
usa como filtro automático**: el análisis crediticio sigue siendo del asesor.

### 2. Falta la lámina mínima — resolución: tabla propia con trazabilidad, sembrada con lo que hay, que crece por uso; y sin lámina no se redondea

**Resolución.** No existe fuente pública que publique la lámina mínima de forma sistemática, y no se va
a construir una por inferencia. La lámina se modela como **un dato del producto, no del mercado**:

- **Tabla `condiciones_emision` en Supabase**, con `lamina`, `origen` y `fecha` en cada valor. Se siembra
  con los **568 de 927 instrumentos (61%)** que ya están cargados, provenientes de la extracción manual
  de exports de ONs y de la herencia entre especies.
- **Herencia entre especies**, que ya está implementada y verificada: la lámina es atributo de la
  emisión, no de la especie. Si AL30 la tiene, AL30D y AL30C la tienen. Si dos especies declaran valores
  distintos, **no se elige**: se vacían las dos y se reporta el conflicto.
- **Carga asistida.** Cuando el asesor se topa con una posición sin lámina, tipea el valor en la misma
  pantalla. Queda guardado con origen `carga manual` y fecha, se propaga a las otras especies y queda
  disponible para todos los asesores. La cobertura crece con el uso, que es el único mecanismo de
  crecimiento que no requiere inventar nada.
- **Sin lámina, no se redondea.** La posición se marca *lámina no informada*, se excluye del total
  ajustado, y el resumen dice cuántas posiciones y qué porcentaje de la cartera quedaron sin ajustar.
  No se asume 1, ni 1.000, ni el mínimo habitual del segmento.

**Fundamento.** Es el mismo criterio que ya rige el proyecto y que tiene antecedente caro: los 121
tickers Cable derivados por manipulación de strings que no existían, y la categoría "Ley Inglesa" que la
fuente no publica. Un default de lámina sería el mismo error con otra ropa, y peor: produciría nominales
que parecen correctos y no lo son, en la pantalla que el asesor lleva a la reunión.

**Camino de ampliación conocido, no supuesto:** los avisos de suscripción y prospectos publicados en la
CNV traen la lámina por emisión. Es carga manual por instrumento, así que en el MVP se modela como flujo
de carga asistida, no como ingesta automática. Si en algún momento se verifica que la CNV expone eso de
forma consultable programáticamente, se agrega como fuente con su origen declarado — pero no se asume
que exista.

### 3. De dónde sale el tipo de cambio — resolución: se conserva el implícito derivado del universo como fuente, y el índice de BYMA entra como control de contraste

**Resolución.** No se cambia el criterio: el tipo de cambio se sigue derivando del propio universo. La
misma emisión cotiza en pesos (especie sin sufijo) y en dólares (especies D y C), y el cociente entre
esos dos precios **es** el tipo de cambio al que opera el mercado. Se toma la mediana sobre todas las
emisiones que cotizan en las dos puntas, con mínimo de 20 pares; con menos, no se normaliza y se declara.
Se usa la especie D (MEP) como referencia y sólo se cae a la C (Cable) si no hay MEP, porque MEP y Cable
son dos tipos de cambio distintos —los separa el canje, ~3,5%— y mezclarlos ensuciaría la mediana.

**Lo que sí cambia:** el `index-price` de BYMA (16 filas, incluye Índice Dólar BYMA y CCL) entra como
**control de contraste, no como fuente**. En cada corrida se compara el implícito derivado contra el
índice publicado; si difieren más de un umbral, sale alerta en la barra de estado del dato. Además,
tener el CCL publicado permite separar MEP de Cable con referencia externa en vez de sólo por
construcción interna.

**Fundamento.** Tres razones concretas. **Primera, está verificado:** el implícito derivado dio 1.530,90
contra 1.533 de una fuente externa independiente — 0,14% de diferencia. **Segunda, es el precio al que
el cliente efectivamente opera:** es el cociente de los precios de los bonos que están en la cartera, no
un índice de referencia calculado sobre otra canasta. **Tercera, es autoconsistente:** los precios, los
volúmenes y el tipo de cambio salen todos del mismo snapshot y del mismo momento, así que las
conversiones no introducen desfasajes temporales entre fuentes. Un índice externo tomado a otra hora
haría que el volumen normalizado de una especie dependa de un dato que no vino con ella.

**Por qué el contraste igual suma:** la única forma de detectar que la mediana implícita se rompió —por
precios desactualizados en una punta, por pocos pares o por una rueda ilíquida— es compararla contra algo
externo. El motor ya alerta cuando la dispersión intercuartil supera el 5%; el índice de BYMA agrega una
segunda red que no cuesta nada porque viene en el mismo endpoint que el resto de los datos.
