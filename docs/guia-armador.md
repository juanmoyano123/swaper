# Guía del Armador — cómo se llega a una cartera armada

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

La pantalla tiene **seis secciones**, cada una con un color de borde distinto para reconocerla de
un vistazo, y todas se pueden **plegar** haciendo clic en su título (aparece un resumen de una
línea cuando están cerradas, así nunca perdés de vista qué hay adentro). A la derecha queda fija
una **columna de resumen** con los números clave de la cartera, para no tener que scrollear hasta
el final cada vez que querés chequear cómo va.

La cartera final combina dos partes que se arman por separado pero comparten el mismo 100%:
- **Renta fija** (bonos, ONs, letras): se elige en Cordillera, se pondera en Cartera.
- **Renta variable** (acciones, CEDEARs): se elige y se pondera en su propia sección, al final.

Una cartera puede ser sólo de renta fija, sólo de renta variable, o mixta.

---

## Las seis secciones, en orden

### 1. Cordillera (borde azul)

> *"Elegí bonos por mes de cobro, o filtrá la oferta antes de mirar la grilla."*

Es el punto de partida si la cartera lleva renta fija. Si vas a armar una cartera sólo de
acciones/CEDEARs, podés saltar directo a la sección **Renta variable**, al final.

**Qué muestra:**
- Una fila de **cobertura**, arriba de todo: doce casilleros, uno por mes, que dicen si la
  selección actual cubre ese mes (✓ verde), si nadie del universo paga ahí (`·` gris, no es un
  problema — no hay nada para elegir), o si hay papeles que pagan pero ninguno está en tu cartera
  todavía (`—` rojo, ahí sí hay algo para elegir).
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
  (ticker, cupón, TIR con su unidad rotulada, año de vencimiento, calificación).

**Cómo se elige:** hacés clic en la tarjeta de un papel y entra a la cartera. Como el mismo ticker
puede pagar en varios meses, **se ilumina en todos los meses en que paga a la vez** — es la forma
de ver de un vistazo si un bono ayuda a repartir el año o se amontona donde ya tenés cobertura.
Un segundo clic (desde cualquiera de los meses en que aparece) lo saca.

### 2. Armado asistido (borde verde azulado) — opcional

> *"Precarga una cartera de arranque a partir del mandato del cliente; después se edita a mano,
> papel por papel, en la sección Cartera."*

Un atajo para no elegir papel por papel desde cero. Se completan cinco datos:

| Campo | Opciones |
|---|---|
| Monto a invertir | un número, en la moneda de referencia elegida |
| Moneda de referencia | cualquiera / dólares / pesos |
| Objetivo de cobertura | mixta (balanceada) / devaluación / inflación / tasa en pesos |
| Perfil | conservador / moderado / agresivo |
| Horizonte | corto / medio / largo |

Al tocar **"Armar cartera asistida"**, el motor arma una cartera completa con esos parámetros y
**reemplaza lo que hubiera cargado** — es un punto de partida, no algo que se suma a lo que ya
elegiste a mano en Cordillera. Después de armada, se sigue editando papel por papel como
cualquier otra, en la sección Cartera.

Si preferís armar todo a mano desde Cordillera, esta sección se puede ignorar por completo (y
plegar, para que no ocupe lugar).

### 3. Cartera (borde violeta)

> *"Ponderación pedida y ponderación real de los bonos elegidos arriba: si no coinciden, se
> muestra tal cual. Las acciones y CEDEARs comparten el mismo 100% pero se ponderan aparte, en
> Renta variable — no aparecen en esta tabla."*

Acá se le pone plata a lo que elegiste en Cordillera (o precargó el Armado asistido). Es una
tabla, una fila por bono:

- **Ticker + moneda** de cotización.
- **Emisor · VN · invertido · calificación** — el valor nominal y lo invertido salen de calcular
  precio cada 100 de VN; si falta el precio o el tipo de cambio, se muestra `s/d`, nunca un cero
  disfrazado. Si la lámina no está informada, aparece un campo para cargarla a mano.
- **% pedido** — un input editable: acá se define qué porción de la cartera **entera** (no sólo
  de esta tabla) le corresponde a cada bono.
- **% real** — lo que efectivamente terminó pesando después de redondear al múltiplo de lámina y
  convertir con el tipo de cambio del día. Si difiere del pedido en más de 0,6 puntos porcentuales,
  se resalta — nunca se ajusta solo.
- Un **mini-calendario** de doce celdas (en qué meses paga) y un botón para sacarlo de la cartera.

**En la cabecera:**
- **Σ pedida total (incl. RV)** — la suma de TODOS los % pedidos, bonos y acciones juntos, contra
  el 100%. Si no suma 100 (algo muy común mientras se está armando), se resalta en ámbar — no se
  normaliza sola, y eso es intencional: la diferencia queda a la vista.
- **Invertido** / **Invertido ajustado** — el monto real, antes y después de redondear a lámina.
- **Monto total (USD)** — el capital total a invertir. Sin cargarlo acá, no hay con qué calcular
  nominales.
- **Equiponderar** (reparte 100% en partes iguales entre todo lo cargado) y **Vaciar**.

### 4. Calendario de pagos (borde acero)

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

### 5. Análisis (borde índigo)

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

### 6. Renta variable (borde malva)

> *"Acciones y CEDEARs, con su propio % pedido sobre el mismo 100% de la cartera. Se suman al
> monto total pero no a la renta ni a los rendimientos de arriba — son otra clase de instrumento."*

El bloque de acciones y CEDEARs, separado del resto porque una acción no tiene TIR, ni duración,
ni cupón — meterla en los cálculos de renta fija sería inventar un dato que no existe.

- **Cabecera**: subtotal de renta fija (USD), subtotal de renta variable (USD), total de la
  cartera, y el **mix RF/RV** — tanto el pedido (sobre los % que cargaste) como el real (sobre lo
  efectivamente invertido), que pueden no coincidir.
- **Tarjetas de lo ya elegido**: ticker, nombre de la empresa (cuando está disponible — depende de
  un enriquecimiento periódico contra Yahoo Finance, así que puede faltar), variación del día, y
  un **% pedido editable** igual que en la tabla de Cartera, más el % real dentro del bloque.
  "Div. est." siempre dice `s/d`: no hay fuente de dividendos, y no se estima.
- **Buscador**: por ticker o por nombre de la empresa, con filtros de **sector** y **rubro**
  (cuando el dato de perfil de empresa ya está cargado — si no, esos selects sólo ofrecen "todos").
  Radio Acciones / CEDEARs para elegir el universo.

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

1. **(Opcional) Usá Armado asistido** si querés un punto de partida rápido: cargá monto, moneda,
   objetivo, perfil y horizonte, y tocá "Armar cartera asistida". Si preferís armar todo a mano,
   saltá este paso.

2. **Elegí bonos en Cordillera.** Usá los filtros para acotar el universo (segmento, duración,
   liquidez, sector, emisor, ley, calificación, TIR mínima) y hacé clic en las tarjetas de los
   papeles que quieras. Mirá la fila de cobertura de arriba para ver qué meses todavía están sin
   cubrir, y priorizá papeles que paguen ahí.

3. **Andá a Cartera.** Cargá el **monto total** a invertir. Ajustá el **% pedido** de cada bono
   (o usá "Equiponderar" para repartir parejo). Mirá la Σ de la cabecera: si no da 100%, se ve en
   ámbar — seguí ajustando hasta que cierre, o dejalo así si es intencional.

4. **Si la cartera lleva acciones o CEDEARs, andá a Renta variable.** Buscá por ticker o nombre,
   agregalos, y asignales su **% pedido** — comparte el mismo 100% que la renta fija de arriba,
   así que si sumás acciones tenés que volver a mirar la Σ de Cartera (o el mix RF/RV de la
   columna de resumen) para que las dos partes cierren juntas.

5. **Revisá Calendario de pagos** para confirmar que los cupones caigan repartidos — es el
   objetivo original de la herramienta. Si hay meses flacos, volvé al paso 2 y buscá un bono que
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
posiciones de renta fija y variable, sus ponderaciones, y los cuatro paneles de Análisis que la
validan. Como todavía no hay forma de guardarla desde la aplicación, para conservarla o
compartirla con el cliente hay que documentarla a mano (captura de pantalla, o copiar los datos)
hasta que la feature de persistencia (F-041) esté construida.
