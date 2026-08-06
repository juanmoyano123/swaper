# Prompt para la Fase 3 — alternativas de interfaz

Insumo de Claude Design. Su salida es `design-system.md`, en esta misma carpeta, que después
consume `/build-feature` en la Fase 5.

Copiar y pegar todo lo que está debajo de la línea. Está escrito para funcionar solo, sin que
quien lo reciba tenga que abrir ningún link ni conocer el proyecto.

---

Necesito que diseñes **5 alternativas de interfaz distintas** para una aplicación web
financiera. No quiero 5 versiones de la misma pantalla con otros colores: quiero 5 maneras
genuinamente diferentes de resolver el mismo problema, cada una con una tesis explícita sobre
cómo debería trabajar el usuario.

## Quién la usa y para qué

La usan **asesores financieros de una ALyC argentina** (agente de liquidación y compensación).
No son traders: arman carteras de inversión a medida para sus clientes minoristas y las siguen
en el tiempo. Trabajan todo el día con esta pantalla.

La herramienta hace dos cosas, y la interfaz tiene que resolver las dos:

**1. Armar una cartera nueva.** El asesor carga qué busca el cliente —objetivos, contra qué
riesgos quiere estar cubierto, horizonte, moneda, monto— y arma la cartera moviendo
instrumentos, viendo **en vivo** cómo cambia el resultado a medida que agrega, saca o cambia
el peso de cada posición.

**2. Mejorar una cartera que ya existe.** Llega un cliente con una cartera armada en otro
lado. El sistema la lee y propone rotaciones concretas: subir rendimiento a igual o menor
riesgo, y sobre todo **desconcentrar el calendario de cobros**.

## El concepto central: la cuponera

Esto es lo más importante del pedido y lo que diferencia a esta herramienta de un screener
común.

Un bono paga cupones en fechas fijas. Si un cliente tiene seis bonos y los seis pagan en marzo
y septiembre, cobra dos veces al año y no cobra nada los otros diez meses. El trabajo del
asesor es **elegir los bonos de forma que el cobro caiga repartido a lo largo del año**,
idealmente todos los meses. A eso se lo llama "armar la cuponera".

La previsibilidad y la continuidad del flujo de fondos es el argumento de venta central de la
renta fija. Por eso el calendario de cobros no es un reporte que se mira al final: es **el
criterio de armado**, y tiene que estar visible y reaccionar en vivo mientras el asesor arma
la cartera. Si agrega un bono que paga en un mes ya cubierto, tiene que verlo en el momento;
si cubre un mes que estaba en cero, también.

Cada una de las 5 alternativas tiene que tomar una posición distinta sobre **dónde vive la
cuponera en la pantalla** y cuánto protagonismo tiene.

## Composición típica de una cartera

- **60-70% renta fija** (bonos soberanos, provinciales y obligaciones negociables
  corporativas) — es de donde sale la cuponera.
- **30-40% renta variable** (acciones argentinas y CEDEARs, que son certificados que
  representan acciones del exterior como Apple o Google).

El perfil del inversor argentino tiende fuerte a la conservación, aun cuando el cliente se
declare arriesgado. La interfaz no debería empujar al riesgo.

Para la renta variable no hay cupones, pero sí un equivalente útil: **las fechas de
presentación de balances trimestrales**. Sirven al mismo propósito de "qué pasa cada mes con
lo que tengo".

## Los datos disponibles

**Por instrumento de renta fija:** ticker, emisor, ley de emisión (Argentina o Nueva York),
moneda de emisión y moneda de pago, estructura del cupón (tasa fija, step up, cupón cero),
tasa, frecuencia de pago, fecha del próximo cupón, fecha del próximo pago de capital, valor
residual, paridad, valor técnico, TIR, duración modificada, convexidad, vida promedio y
volumen medio operado.

**Del mercado, actualizado durante la rueda:** precio de compra y de venta (las dos puntas),
último operado, apertura, máximo, mínimo, cierre anterior, volumen en cantidad y en monto,
precio promedio ponderado, y cantidad de órdenes.

**Por instrumento de renta variable:** los mismos datos de mercado, sin nada de lo anterior —
una acción no tiene TIR, ni duración, ni cupones.

## Reglas del dominio que la interfaz no puede romper

No son preferencias estéticas. Son restricciones del negocio, y una interfaz que las viole
está mal aunque se vea bien.

1. **Los rendimientos de distinta naturaleza nunca van en el mismo eje ni se promedian.** Hay
   seis segmentos y cada uno mide una cosa distinta: dólar hard (TIR en dólares), CER (tasa
   real sobre inflación), tasa fija en pesos (TNA nominal), dólar linked, Badlar y Tamar
   (tasas variables). Una TIR del 7% en dólares y una TNA del 40% en pesos no son comparables.
   Cualquier gráfico de rendimiento tiene que ser **de un segmento por vez**, con la unidad
   declarada.

2. **El mismo bono cotiza en tres monedas.** Un bono se opera en pesos, en dólar MEP y en
   dólar cable, y son tres tickers distintos del mismo instrumento (por ejemplo AL30, AL30D y
   AL30C). El asesor opera en las tres y necesita ver y comparar las tres, sin que la interfaz
   las mezcle ni las sume.

3. **Cuando falta un dato, se muestra que falta.** Nunca se estima, ni se rellena, ni se deja
   la celda vacía sin decir nada. La cobertura de datos es parcial y el asesor tiene que saber
   sobre qué está decidiendo.

4. **Esto es una pantalla interna de trabajo, no un entregable al cliente.** El asesor arma la
   presentación final por su cuenta. La densidad de información está bien; la decoración
   sobra.

## La referencia de dinámica

Existe un monitor interno que los asesores ya usan y del que quiero conservar el **modo de
trabajar**, no el aspecto. Lo describo porque no vas a poder verlo:

- Barra superior fija con un indicador de "en vivo" y una cuenta regresiva de segundos hasta
  el próximo refresco de precios.
- **Dos niveles de navegación**: una fila de secciones (Monitor / Carteras / Colocaciones /
  Fondos / Calendario de flujos) y debajo una fila de segmentos (Soberanos / Subsoberanos /
  ON / Tasa fija / CER / Tamar / Dólar linked / Acciones / CEDEARs). Nunca se ven dos
  segmentos a la vez — así se respeta la regla 1.
- Una fila de **tarjetas con los números del día** (dólar MEP, dólar cable, el canje entre
  ambos, el de mayor volumen, el que más subió, el que más bajó). Cada tarjeta muestra de qué
  par de tickers sale el número, así que el dato es auditable de un vistazo.
- Una **barra de filtros numéricos** siempre visible: TIR mínima y máxima, duración mínima y
  máxima, familia, y un botón de limpiar.
- Al lado, un recuadro para **simular un instrumento que todavía no existe**: se escribe un
  ticker, una TIR y una duración, y aparece en el gráfico junto a los reales. Sirve para
  evaluar una licitación primaria antes de que cotice.
- Un **gráfico de dispersión de TIR contra duración** con cada bono etiquetado, agrupado por
  familia y con una curva de tendencia por familia. Es la herramienta principal: se ve de un
  golpe qué papel está barato o caro para su plazo.
- Un **botón de cámara en cada panel** para copiarlo como imagen y mandarlo por chat. Los
  asesores comparten paneles sueltos todo el día.
- El **calendario de flujos** es una grilla mensual tipo almanaque: cada día lista los tickers
  que pagan, con color distinto según sea renta o amortización. Debajo, al elegir un ticker,
  se abre su flujo de fondos completo.
- Tema oscuro por defecto, con opción de claro.

Lo que quiero conservar: la sensación de estar frente a algo vivo, la densidad alta de
información sin sentirse abarrotado, los filtros siempre a mano, el poder simular sobre lo
real, y el compartir un panel en un click.

## La pantalla de armado que ya existe, y que es el punto de partida

Dentro de ese mismo monitor hay una pantalla llamada **"Cartera Cuponera"** que ya resuelve
buena parte del problema. La describo con precisión porque **es la referencia principal**:
todo lo que diseñes tiene que ser tan bueno como esto o mejor, no distinto por ser distinto.

Su bajada dice: *"Armá una cartera orientada a renta en USD con pagos de cupón a lo largo del
año, eligiendo entre los papeles habilitados."*

**El calendario ES el selector.** Ocupa la mitad superior de la pantalla: una grilla de doce
tarjetas, una por mes, tres por fila. Cada tarjeta lista los papeles que pagan cupón ese mes,
y cada renglón muestra, en una sola línea: el ticker, en qué moneda liquida (MEP o Cable),
**cuánto paga de cupón**, la TIR y el año de vencimiento. Arriba dice "Tocá un papel para
sumarlo a la cartera".

Eso es lo central: **el asesor elige mirando el mes que necesita cubrir**. No busca en una
tabla y después chequea cuándo paga — ve el calendario, encuentra el mes vacío, y ahí mismo
elige entre los papeles que pagan en ese mes comparando cupón, TIR y vencimiento. El mismo
papel aparece en todos los meses en que paga, y al seleccionarlo se ilumina en todos a la vez,
así que la cobertura del año se lee de un vistazo.

Los tres criterios de selección, en ese orden de importancia: **la TIR, cuánto paga de cupón, y
con qué frecuencia paga.**

**Debajo, la cartera en construcción**, como tabla editable:

- Un monto total y una columna de ponderación **editable por posición**, con el total
  acumulado ("Σ 100.0%") y el invertido real al lado, porque no coinciden.
- Botones de **"Equiponderar"** y **"Vaciar"**.
- Por posición: ticker, empresa, industria, precio, monto, ponderación deseada, **lámina
  mínima**, **valor nominal asignado**, **porcentaje real**, y **en qué meses paga cupón**.
- El detalle que hace la diferencia: la ponderación que pide el asesor y la que efectivamente
  queda **no son iguales**, porque el valor nominal se redondea hacia abajo al múltiplo de la
  lámina mínima. La pantalla muestra las dos y no esconde la diferencia. Una posición pedida
  al 16,5% puede terminar en 17,6% real, y eso se ve.

**Los tres indicadores de la cartera**, en tarjetas grandes: TIR ponderada, duración ponderada
y cantidad de papeles.

**La composición**: una torta por posición y unas barras de distribución por industria.

**Y el panel que es la razón de ser de todo esto: el flujo de fondos.** Una tabla mes por mes
con qué ticker paga y cuánto, en plata real según el nominal asignado —no en porcentaje, no
cada 100 de valor nominal, en dólares que el cliente va a cobrar. Abajo, el **total anual** y,
destacada, la **renta anual sobre lo invertido**, con la cuenta a la vista: "sólo cupones ·
US$ 7.173,92 / US$ 99.999,11 = 7,17%".

Ese último número es el que el asesor le dice al cliente. **Es el ingreso garantizado por
cupones**, separado de cualquier ganancia de capital, que es incierta. Tiene que estar siempre
presente y actualizarse en vivo con cada papel que se agrega o se saca.

Cierra con un scatter de TIR contra duración de las posiciones elegidas, y dos botones:
descargar la propuesta y copiar la pantalla como imagen.

## Lo que esa pantalla todavía no resuelve

Acá es donde tenés que aportar. Cada una de las 5 alternativas debería atacar al menos tres de
estos huecos:

1. **No hay cliente.** No se cargan objetivos ni contra qué riesgos quiere cubrirse, y no queda
   registro de nada. Cada cartera se arma desde cero y se pierde.
2. **Sólo hay obligaciones negociables corporativas en dólares.** Faltan los bonos soberanos y
   provinciales, y faltan los otros cinco segmentos de tasa.
3. **No hay renta variable.** La cartera real lleva 30-40% en acciones y CEDEARs, y ahí el
   equivalente del cupón es el calendario de balances trimestrales.
4. **No se puede partir de una cartera existente.** Hoy siempre se arranca vacío. El caso más
   frecuente es que el cliente ya tenga papeles y haya que mejorarlos.
5. **No propone nada.** El asesor tiene que darse cuenta solo de que le falta cubrir marzo. El
   sistema podría señalarlo, y podría sugerir qué rotación desconcentra el año.
6. **Los papeles son una lista curada a mano.** Tendría que trabajar sobre el universo
   completo, con filtros.

## Qué te pido

**5 direcciones de diseño distintas.** Cada una con:

1. **Una tesis en una frase** — qué asume esta alternativa sobre cómo trabaja el asesor. Las 5
   tesis tienen que ser incompatibles entre sí; si dos se podrían combinar sin fricción, no
   son 5 alternativas, son una con variantes.
2. **La pantalla principal**, diseñada y navegable, con datos de ejemplo realistas (tickers y
   números argentinos plausibles, nunca "Lorem ipsum" ni "Bono A").
3. **Qué hacés con el calendario-selector.** Es el hallazgo de la pantalla actual y el corazón
   del flujo. Podés conservarlo, reemplazarlo por algo mejor o subordinarlo a otra cosa — pero
   si lo tocás, justificá qué ganás, porque hoy funciona.
4. **Cómo se pasa de "armar una cartera nueva" a "mejorar una que ya existe"** — si son dos
   pantallas, dos modos, o la misma cosa.
5. **Cómo entra la renta variable** sin romper la regla de que no tiene TIR ni cupones.
6. **Qué sacrifica.** Toda decisión de diseño resigna algo. Decilo.

Direcciones que vale la pena explorar, aunque no te limites a estas:

- El calendario deja de ser una grilla de doce cajas y pasa a ser una **línea de tiempo con
  altura**, donde cada mes muestra cuánta plata entra, no sólo qué papeles pagan. El hueco de
  cobertura se ve como un valle.
- Una **mesa de trabajo** donde la cartera en construcción vive fija a un costado y todo lo
  demás —calendario, universo, curva— es material que se arrastra hacia ella.
- **Arrancar por el objetivo, no por los papeles**: el asesor declara "este cliente necesita
  US$ 800 por mes en dólares, sin riesgo soberano", y el sistema arma un borrador que después
  se retoca a mano sobre el calendario.
- **Dos carteras siempre lado a lado**: la que el cliente tiene y la propuesta, con las
  diferencias de cobertura mensual y de renta anual marcadas. Armar es un caso particular de
  comparar, contra una cartera vacía.
- La **curva de TIR contra duración al centro**, y la cartera se arma haciendo clic sobre los
  puntos; el calendario aparece como consecuencia de lo elegido, no como punto de partida.

**Formato:** cada alternativa como una página HTML autocontenida y funcional (sin recursos
externos), con tema claro y oscuro. Después de las 5, una comparación breve y una
recomendación fundamentada.

**Idioma:** todo en español argentino, incluida la terminología financiera.
