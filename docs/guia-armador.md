Qu# Guía del Armador — cómo se llega a una cartera armada

Esta guía explica la pestaña **Armador** (`/armador`): qué hace cada sección y en qué orden
conviene recorrerlas para terminar con una cartera armada. No es una spec técnica — para eso está
`claude-docs/planning/design-system.md` y el código en `frontend/src/features/armador/`.

**Importante antes de empezar**: hoy el Armador arma la cartera **en memoria, durante la
sesión**. No existe todavía un botón "Guardar" — persistir, listar y reabrir carteras es una
feature futura (F-041, tanda 17, no construida). Si recargás la página o cerrás la pestaña, la
cartera se pierde. El "resultado final" de esta guía es la cartera armada *en pantalla*, lista
para exportar a mano o revisar con el cliente — no un registro guardado en la base.

## La idea general

El Armador invierte el orden habitual de armar una cartera: en vez de elegir bonos y después
mirar cuándo cobran, la pantalla arranca mostrando **los doce meses del año** y vos elegís papeles
para que los cupones caigan repartidos — esa es la "Cordillera" que le da nombre al diseño.

Hay **dos caminos que llegan a la misma cartera**:

- **El camino asistido**: cargás el mandato del cliente y un botón arma la cartera entera —bonos y
  acciones— de una. Después la editás posición por posición.
- **El camino manual**: elegís vos los bonos en Cordillera y las acciones en Renta variable, papel
  por papel.

Los dos terminan en la **sección Cartera**, que es donde la cartera se pondera y se lee completa.
No son excluyentes: lo normal es arrancar por el asistido y afinar a mano, o arrancar a mano y no
tocar el asistido nunca.

La pantalla tiene **seis secciones**, cada una con un color de borde distinto para reconocerla de
un vistazo, y todas se pueden **plegar** haciendo clic en su título (aparece un resumen de una
línea cuando están cerradas, así nunca perdés de vista qué hay adentro). A la derecha queda fija
una **columna de resumen** con los números clave de la cartera, para no tener que scrollear hasta
el final cada vez que querés chequear cómo va.

### El monto se carga una sola vez

El **monto total (USD)** es el capital a invertir y es **uno solo para toda la pantalla**: da lo
mismo si lo cargás en el campo del Armado asistido o en el de la cabecera de Cartera, porque son
dos vistas del mismo dato y se actualizan juntos. Sin monto cargado no hay con qué calcular
nominales, y el botón del armado asistido queda deshabilitado.

### Los badges de clase

Al lado de cada ticker —en la grilla, en la cartera y en el bloque de renta variable— aparece una
sigla que dice qué es ese papel:

| Sigla | Qué es |
|---|---|
| `SOB` | Bono soberano |
| `SUB` | Bono subsoberano (provincial, municipal) |
| `ON` | Obligación negociable |
| `ACC` | Acción |
| `CEDEAR` | CEDEAR |

`AL30` y `YMCXO` se leen igual si no sabés de memoria cuál es del Tesoro y cuál corporativo, y el
riesgo de crédito detrás de cada uno no tiene nada que ver. Si algún día apareciera una clase que
no está en esta tabla, se muestra **su código crudo y sin color**: no se la mete a la fuerza en la
categoría más parecida.

---

## Camino 1 — Armado asistido (borde verde azulado)

> *"Camino asistido: con el mandato del cliente arma una cartera entera de arranque y la carga en
> Cartera, donde se edita posición por posición. Reemplaza lo que hubiera cargado."*

Un atajo para no elegir papel por papel desde cero. Se completan estos datos:

| Campo | Opciones |
|---|---|
| Monto a invertir (USD) | un número — es el mismo monto que la cabecera de Cartera |
| Moneda de referencia | cualquiera / dólares / pesos |
| Objetivo de cobertura | mixta (balanceada) / devaluación / inflación / tasa en pesos |
| Perfil | conservador / moderado / agresivo |
| Horizonte | corto / medio / largo |
| % renta variable | qué porción de la cartera va a acciones y CEDEARs |
| Temática (acciones) | opcional: Energía, Financieras, Tecnológicas |

**El % de renta variable arranca con el default del perfil** —conservador 0%, moderado 25%,
agresivo 60%, calcados del Excel de referencia de la mesa— y se puede pisar a mano. Debajo del
formulario, una línea dice sobre qué porcentaje se van a armar los bonos.

Al tocar **"Armar cartera asistida"** se arma la cartera **completa**: la renta fija sobre el
porcentaje que le queda, y la renta variable sobre el `% renta variable` pedido. Las acciones se
eligen **por liquidez** (volumen en dólares, de mayor a menor), tratando de no repetir sector.
El resultado **reemplaza lo que hubiera cargado** — es un punto de partida, no algo que se suma a
lo que ya elegiste a mano.

Debajo del botón queda una línea de resultado: cuántas posiciones se precargaron, con qué perfil,
cuántos sectores quedaron representados y qué % de renta variable se aplicó efectivamente.

**Un aviso que vas a ver mientras falte el dato**: la diversificación por rubro de las acciones
**no puede aplicarse** cuando ninguno de los papeles elegidos tiene rubro informado. El rubro sale
de la clasificación de la SEC, que cubre el 74 % de los CEDEARs y el 9 % de las acciones
argentinas; para el resto no hay fuente todavía. Cuando falta, la selección se hace por liquidez
pura y la pantalla lo declara con una alerta (`rv_sin_perfil_sectorial`). Es un faltante de dato
declarado, no un error de armado.

---

## Camino 2 — Armarla a mano

### Cordillera (borde azul) — la renta fija

> *"Camino manual: elegí bonos por mes de cobro. Los atajos temáticos filtran de un clic los dos
> lados de la cartera —bonos acá y acciones en Renta variable— y después afinás con los filtros."*

Es el punto de partida si la cartera lleva renta fija. Si vas a armar una cartera sólo de
acciones/CEDEARs, podés saltar directo a **Renta variable**.

**Qué muestra:**
- Una fila de **cobertura**, arriba de todo: doce casilleros, uno por mes, que dicen si la
  selección actual cubre ese mes (✓ verde), si nadie del universo paga ahí (`·` gris, no es un
  problema — no hay nada para elegir), o si hay papeles que pagan pero ninguno está en tu cartera
  todavía (`—` rojo, ahí sí hay algo para elegir).
- Los **atajos temáticos**: una fila de chips —**Energía**, **Financieras**, **Tecnológicas**,
  **Cobertura inflación**— que de un clic precargan los filtros de bonos **y** el rubro del
  buscador de acciones a la vez. Son un punto de partida, no un modo: los filtros quedan abajo, a
  la vista y editables, y el chip se apaga solo apenas tocás uno a mano (seguir mostrando "Energía"
  prendido sobre una grilla que ya muestra otra cosa sería mentir sobre el estado). Pasando el
  mouse por encima, cada chip dice exactamente qué precarga.

  Dos aclaraciones que los chips hacen explícitas: **"Tecnológicas" arma sólo renta variable**,
  porque el universo de bonos no tiene emisores tecnológicos y Telecomunicaciones no es lo mismo;
  y **"Cobertura inflación" no filtra las acciones**, porque una acción no ajusta por inflación
  por contrato y no hay sector que cubra eso.
- Una **barra de filtros**, siempre visible, para acotar el universo antes de mirar la grilla:
  - **Segmento** (tabs: Dólar hard / CER / Tasa fija $ / Dólar linked / Badlar / Tamar…) — nunca
    dos segmentos a la vez, porque cada uno mide el rendimiento en una unidad distinta (TIR en
    dólares, tasa real, TNA…) y mezclarlas no tiene sentido.
  - **Duración máx. (años)**, **Liquidez mín.** (percentil de volumen en dólares), **Sector**,
    **Emisor**, **Ley** (incluye la opción "ley no informada" para lo que la fuente no declara),
    **Calificación** (multiselect — cada calificadora usa su propia escala, así que se filtra por
    el valor exacto, nunca ordenado de mejor a peor), **Pagos de renta** (cuántas veces paga en la
    ventana de doce meses) y **TIR mín.** (sólo se aplica a los segmentos que tienen TIR).
  - El checkbox **"Sólo con cupones"** saca los bullets al descuento (que no pagan renta en el
    camino, sólo al vencimiento).
  - Por defecto la pantalla arranca filtrando TIR ≥ 6% y sólo con cupones — sin eso, la grilla sin
    filtrar apila más de mil papeles. **"Limpiar filtros"** saca todo, incluido ese default.
- La **grilla de doce meses**: un panel por mes, con las tarjetas de los papeles que pagan ahí
  (ticker, badge de clase, cupón, TIR con su unidad rotulada, año de vencimiento, calificación).

**Cómo se elige:** hacés clic en la tarjeta de un papel y entra a la cartera. Como el mismo ticker
puede pagar en varios meses, **se ilumina en todos los meses en que paga a la vez** — es la forma
de ver de un vistazo si un bono ayuda a repartir el año o se amontona donde ya tenés cobertura.
Un segundo clic (desde cualquiera de los meses en que aparece) lo saca.

### Renta variable (borde malva) — las acciones y CEDEARs

> *"El buscador para sumar acciones y CEDEARs a la cartera. Ya cargadas se editan también desde
> Cartera, arriba. No suman a la renta ni a los rendimientos: una acción no tiene cupón ni TIR."*

Esta sección es **el buscador**: donde se eligen las acciones. Una vez cargadas, sus porcentajes se
pueden editar tanto acá como en la tabla de Cartera, que las muestra en su propio bloque.

- **Buscador**: por ticker o por nombre de la empresa, con radio Acciones / CEDEARs para elegir el
  universo, y filtros de **rubro (SEC)** y **eslabón productivo**. Los dos salen de la
  clasificación de la SEC y sólo ofrecen los valores que los papeles de esa clase declaran: si
  ninguno está clasificado, sólo ofrecen "todos" y la pantalla lo declara, en vez de mostrar una
  lista vacía que se leería como "no hay papeles de este rubro".
- **Cabecera**: subtotal de renta fija (USD), subtotal de renta variable (USD), total de la
  cartera, y el **mix RF/RV** — tanto el pedido (sobre los % que cargaste) como el real (sobre lo
  efectivamente invertido), que pueden no coincidir.
- **Tarjetas de lo ya elegido**: ticker, badge de clase, nombre de la empresa (cuando está
  disponible), variación del día, y un **% pedido editable**. "Div. est." siempre dice `s/d`: no
  hay fuente de dividendos, y no se estima.

La renta variable se lleva su porción del mismo 100% que la renta fija, pero **no entra en los
cálculos de renta ni de rendimientos**: una acción no tiene TIR, ni duración, ni cupón, y meterla
ahí sería inventar un dato que no existe.

---

## Donde terminan los dos caminos

### Cartera (borde violeta) — la cartera entera, por bloques

> *"La cartera entera, agrupada por clase de activo y con subtotal por bloque: soberanos,
> corporativos, fondos y acciones sobre el mismo 100%. El % pedido se edita acá; agregar o sacar
> una posición reparte el resto pro-rata."*

Acá se le pone plata a todo lo elegido, venga del camino que venga. **La tabla muestra la cartera
completa** —renta fija y renta variable juntas— agrupada por clase de activo, que es el formato del
Excel de la mesa. Los bloques, siempre en este orden, y cada uno con **su subtotal pedido** a la
derecha del título:

1. **Soberanos y subsoberanos**
2. **Corporativos**
3. **Fondos comunes**
4. **Sin clasificar**
5. **Renta variable**

Un bloque sin posiciones no se muestra.

**Cada fila de renta fija** trae:

- **Ticker + badge de clase + moneda** de cotización.
- **Emisor · VN · invertido · calificación** — el valor nominal y lo invertido salen de calcular
  precio cada 100 de VN; si falta el precio o el tipo de cambio, se muestra `s/d`, nunca un cero
  disfrazado. Si la lámina no está informada, aparece un campo para cargarla a mano.
- **% pedido** — un input editable: qué porción de la cartera **entera** le corresponde a ese papel.
- **% real** — lo que efectivamente terminó pesando después de redondear al múltiplo de lámina y
  convertir con el tipo de cambio del día, **medido contra la cartera entera** (no contra su
  bloque). Si difiere del pedido en más de 0,6 puntos porcentuales, se resalta — nunca se ajusta
  solo.
- Un **mini-calendario** de doce celdas (en qué meses paga) y un botón para sacarlo de la cartera.

**Las filas de renta variable** son distintas donde tienen que serlo: donde el bono muestra el
emisor va la **denominación de la empresa**, la cantidad va en unidades enteras (una acción no
tiene valor nominal), y la columna de pagos dice **"no aplica"** en vez de `s/d` — una acción no
tiene cronograma de cupones: el dato no falta, no existe.

**En la cabecera:**
- **Σ pedida total** — la suma de TODOS los % pedidos, bonos y acciones juntos, contra el 100%. Si
  no suma 100, se resalta en ámbar — no se normaliza sola, y eso es intencional.
- **Invertido** / **Invertido ajustado** — el monto real, antes y después de redondear a lámina.
- **Monto total (USD)** — el capital a invertir (el mismo del Armado asistido).
- **Equiponderar** (reparte 100% en partes iguales entre todo lo cargado) y **Vaciar**.

### El rebalanceo automático

**Agregar o sacar una posición reparte el resto proporcionalmente entre las que quedan**, y la
cartera vuelve a sumar 100,0 exacto. Si tenías 25% en acciones y las sacás todas, ese 25% se
reparte entre los bonos que quedan, respetando sus proporciones — no queda un hueco.

La única acción que **no** rebalancea es **editar un % a mano**: eso es una intención explícita
sobre esa posición y no una orden de mover a las demás, así que la Σ de la cabecera puede irse de
100 y se marca en ámbar. Es la señal, y es a propósito. "Equiponderar" y el armado asistido también
dejan la suma en 100,0 exacto.

### Calendario de pagos (borde acero)

> *"Cómo cae la renta mes a mes, sólo de la parte de renta fija — una acción no tiene cupón que
> calendarizar."*

Dos gráficos de barras de doce meses, **nunca sumados ni mezclados**:
- **Cordillera en dólares** — la renta en USD, mes a mes.
- **Cordillera en pesos** — su propia escala, aparte. Los cobros en pesos nunca se convierten ni
  se suman a los dólares.

Al hacer clic en una columna se abre el **detalle del mes**: qué papel paga, cuánto y en qué
fecha exacta, agrupado por moneda de cobro. Debajo, la **renta anual** sobre lo invertido, una
tarjeta por moneda, con la cuenta expuesta (`US$ X / US$ Y = Z%`).

Es la sección para chequear visualmente si el objetivo de "cupones repartidos a lo largo del año"
se cumplió, o si hay meses flacos que conviene reforzar volviendo a Cordillera.

### Análisis (borde índigo)

> *"Rendimientos, composición, concentración y riesgo de la cartera armada hasta acá — incluye lo
> pedido en Cartera y en Renta variable."*

Cuatro paneles, uno debajo del otro:

- **Rendimientos** — cuatro tarjetas, **una por naturaleza de tasa** (TIR en dólares, dólar
  linked, tasa real CER, TNA en pesos), nunca promediadas entre sí: son magnitudes distintas y no
  hay ni va a haber un número que las combine. Más el plazo promedio (sí se agrega, porque los
  años son una unidad comparable) y la sensibilidad de precio por segmento.
- **Composición** — cómo se reparte la cartera por clase de activo, segmento y emisor (barras de
  colores distintos, ya no todo verde), más una curva de TIR contra duración.
- **Concentración** — los topes por emisor, por riesgo soberano (agrupa todos los prefijos del
  Tesoro bajo una sola clave) y por sector, con advertencia si algo se pasa.
- **Riesgo** — el vector de **seis ejes** (duración, crédito, legislación, liquidez, concentración,
  moneda), siempre como seis barras separadas — nunca un score único que los combine.

Esta sección es donde se valida la cartera antes de darla por terminada: acá aparecen los
excesos de concentración, el riesgo real y si los rendimientos tienen sentido para el perfil del
cliente.

---

## La columna de resumen (siempre visible, a la derecha)

No hace falta abrir ninguna sección para ver:

- **Renta anual en dólares** — el número grande, con la cuenta expuesta debajo.
- Cuatro KPIs en grilla: **meses cubiertos** (n/12), **qué tan parejo** está repartido el año,
  **TIR ponderada** (sólo la parte en dólares hard — nunca mezclada con otra naturaleza) y
  **duración + mix RF/RV**.
- **"Lo que falta"** — avisos accionables: qué meses todavía no tienen cobertura (con un enlace
  que te lleva directo a ese mes en la grilla) y si hay posiciones que no se pudieron resolver
  (por falta de precio o tipo de cambio). Cuando no queda nada pendiente, lo dice.

En pantallas angostas (menos de 1280px de ancho) esta columna deja de estar fija y pasa a ser un
bloque más, al final de la página.

---

## Paso a paso para armar una cartera de punta a punta

### Si arrancás por el camino asistido

1. **Cargá el monto** y el mandato del cliente en Armado asistido: moneda, objetivo, perfil,
   horizonte. Revisá el **% de renta variable** que trajo el perfil y pisalo si el mandato dice
   otra cosa. Si el cliente pide una temática, elegila en "Temática (acciones)".

2. **Tocá "Armar cartera asistida".** Queda la cartera entera cargada —bonos y acciones— en la
   sección Cartera, agrupada por bloques, sumando 100,0.

3. **Editala en Cartera.** Ajustá el **% pedido** de lo que quieras mover, sacá lo que no te
   convence (el resto se reparte solo) y sumá papeles desde Cordillera o desde Renta variable si
   falta algo. Seguí desde el paso 4 de abajo.

### Si la armás a mano

1. **Cargá el monto total** en la cabecera de Cartera (o en Armado asistido: es el mismo campo).

2. **Elegí bonos en Cordillera.** Si la cartera tiene una temática, arrancá por el chip
   correspondiente y después afiná con los filtros (segmento, duración, liquidez, sector, emisor,
   ley, calificación, TIR mínima). Hacé clic en las tarjetas de los papeles que quieras. Mirá la
   fila de cobertura de arriba para ver qué meses todavía están sin cubrir, y priorizá papeles que
   paguen ahí.

3. **Si la cartera lleva acciones o CEDEARs, andá a Renta variable.** Buscá por ticker o nombre y
   agregalas. Aparecen en su propio bloque dentro de la tabla de Cartera, sobre el mismo 100%.

### Desde acá, los dos caminos son el mismo

4. **Ajustá las ponderaciones en Cartera.** Mirá los subtotales por bloque —es la forma rápida de
   ver si el mix soberano/corporativo/acciones es el que pediste— y la Σ de la cabecera. Recordá
   que editar un % a mano no rebalancea nada: si la Σ se va de 100 y queda en ámbar, hay que
   cerrarla a mano o usar "Equiponderar".

5. **Revisá Calendario de pagos** para confirmar que los cupones caigan repartidos — es el
   objetivo original de la herramienta. Si hay meses flacos, volvé a Cordillera y buscá un bono que
   pague justo ahí.

6. **Revisá Análisis** antes de dar la cartera por terminada: los cuatro rendimientos por
   naturaleza (nunca un promedio), la composición, si algún tope de concentración se pasó, y el
   vector de seis ejes de riesgo. Si algo no cierra con el perfil del cliente, volvé a Cordillera
   o a Renta variable y ajustá.

7. **Chequeá la columna de resumen** en cualquier momento del proceso — es el atajo para saber
   "¿cómo voy?" sin tener que abrir cada sección, y "Lo que falta" te dice exactamente qué mes
   necesita cobertura todavía.

8. **Plegá las secciones que no estés usando.** Si estás enfocado en ajustar ponderaciones, plegá
   Cordillera y Análisis para que no ocupen pantalla — el resumen de una línea sigue visible, y
   los datos no se pierden al plegar (siguen viviendo en la sesión, sólo se ocultan de la vista).

El resultado final es la cartera tal como queda en pantalla al terminar este recorrido: las
posiciones de renta fija y variable en sus bloques, sus ponderaciones, y los cuatro paneles de
Análisis que la validan. Como todavía no hay forma de guardarla desde la aplicación, para
conservarla o compartirla con el cliente hay que documentarla a mano (captura de pantalla, o copiar
los datos) hasta que la feature de persistencia (F-041) esté construida.
