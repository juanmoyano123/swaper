# Idea Brief — Armador y Optimizador de Carteras

Fecha: 05/08/2026

## Problema que resuelve

Un asesor de renta fija no le vende a su cliente una tasa: le vende **certeza de cobro**.
La pregunta que el cliente hace es "¿cuánto voy a cobrar y cuándo", y la respuesta —el
calendario de cupones— es el argumento de venta central del producto.

Pero **hoy ese calendario se descubre, no se diseña.** Todas las herramientas disponibles
lo calculan al final, cuando la cartera ya está armada:

- Los Excel de carteras sugeridas de la mesa traen el flujo de fondos como una hoja más, y
  con precios de meses atrás.
- El monitor interno muestra el calendario, pero es sólo de lectura.
- Los screeners de mercado ordenan por TIR y vencimiento; en qué mes paga cada bono es un
  dato al que hay que entrar papel por papel.

La consecuencia es concreta y se repite: **carteras donde toda la renta cae en uno o dos
meses del año**, porque nadie eligió que fuera así — simplemente los bonos con mejor TIR
pagaban todos en marzo y septiembre. El asesor se entera cuando ya compró.

Hay un segundo problema, del mismo origen. Cuando llega un cliente con una cartera armada
en otro lado, evaluarla contra las alternativas del mercado es trabajo manual de horas. En
la práctica no se hace, y las oportunidades de mejora pasan de largo.

## Usuario objetivo

**Asesores financieros de una ALyC argentina** y asesores independientes que operan a
través de ella.

No son traders ni analistas cuantitativos: son personas que atienden clientes minoristas y
necesitan llegar a una reunión con una propuesta defendible. Trabajan todo el día con la
misma pantalla y operan en las tres monedas de liquidación (pesos, dólar MEP y dólar
cable).

Su cliente típico se declara arriesgado y se comporta conservador. Por eso la cartera
estándar es **60-70% renta fija / 30-40% renta variable**, y por eso el flujo de cupones
—no la ganancia de capital— es lo que sostiene la conversación.

## Solución — Funcionalidad principal

**El calendario de cupones es el selector, no el reporte.**

El asesor ve los doce meses del año con los papeles que pagan en cada uno —ticker, cuánto
paga de cupón, TIR y vencimiento— y arma la cartera **eligiendo desde el mes que necesita
cubrir**. Al seleccionar un papel se ilumina en todos los meses en que paga, así que la
cobertura del año se lee de un vistazo.

Mientras arma, ve actualizarse en vivo: la renta mes a mes en plata real, el **total anual
de cupones sobre lo invertido**, la TIR y duración ponderadas, y la composición por emisor
e industria.

Sin esa mecánica el producto no existe. Todo lo demás es accesorio.

## Diferenciadores

**Contra la pantalla "Cuponera" que la mesa ya tiene** —que es la referencia más cercana y
funciona bien—: universo completo en vez de una lista curada a mano, las tres especies de
cada bono en vez de sólo las que liquidan en dólares, renta variable además de renta fija,
capacidad de partir de una cartera existente, y sugerencias en vez de sólo cálculo.

**Contra los Excel de carteras sugeridas**: precios de hoy en vez de una foto de hace
meses. Es una herramienta, no un documento que envejece.

**Contra los screeners de mercado**: el calendario es la puerta de entrada. En cualquier
otro lado es un dato al que hay que ir a buscar.

**Dos reglas del dominio que la herramienta respeta y las planillas no:**

1. **No mezcla naturalezas de tasa.** Una TIR del 7% en dólares, una tasa real del 4% sobre
   CER y una TNA del 40% en pesos no se promedian ni comparten eje. Se trabaja un segmento
   por vez, con la unidad declarada.
2. **Cuando falta un dato, lo dice.** No estima, no completa por inferencia, no deja la
   celda vacía en silencio. El asesor tiene que saber sobre qué está decidiendo.

## MVP — Producto Mínimo Viable

Dos herramientas sobre una misma base de datos de mercado. **Queda explícitamente afuera
todo lo que sea CRM**: no hay ficha de cliente, ni historial de contactos, ni seguimiento
comercial. Los objetivos del cliente se cargan como parámetros de la cartera que se está
armando, no como un registro que persiste.

- **F-core 1 — Universo de mercado.** Ingesta diaria y durante la rueda desde la API
  abierta de BYMA (precios, puntas, volumen, moneda de cotización, las tres especies) y
  desde el informe diario de IAMC (emisor, ley, estructura del cupón, TIR, duración,
  próximos pagos). Ver "Fuentes de datos".
- **F-core 2 — Armador desde el calendario.** La pantalla descrita arriba: grilla de doce
  meses, selección por clic, cartera editable con ponderación, ajuste por lámina mínima, y
  el panel de renta anual garantizada.
- **F-core 3 — Optimizador de cartera existente.** Se carga un portafolio y devuelve
  propuestas de rebalanceo en **dos modos**:
  - *Mantener la TIR y bajar el riesgo.*
  - *Subir la TIR, **declarando qué riesgo se asume a cambio*** — mayor duración, peor
    calidad crediticia, ley argentina en vez de neoyorquina, menos liquidez o más
    concentración por emisor. Nunca se propone una mejora de TIR sin nombrar su
    contrapartida.
- **F-core 4 — Renta variable.** Acciones y CEDEARs con su calendario de presentación de
  balances, que es el equivalente del cupón del lado de la renta variable. Sin TIR, sin
  duración y sin cashflow: no se mezcla con la renta fija en ningún cálculo.
- **F-core 5 — Login y carteras guardadas.** Autenticación con Supabase desde el arranque.
  Cada asesor ve y guarda sus propias carteras. Se guardan carteras, no clientes.

**Fuera del MVP:** gestión de clientes, historial de propuestas, seguimiento de
performance, colocaciones primarias, fondos comunes de inversión.

## Flujos principales

**Flujo A — Armar una cartera desde cero**

1. El asesor entra y elige "cartera nueva".
2. Define los parámetros: monto, moneda, horizonte, y contra qué riesgos quiere cubrirse.
3. Cae en el calendario de cupones filtrado por esos parámetros.
4. Va eligiendo papeles mes a mes, viendo cómo se llena el año y cómo cambia la renta.
5. Ajusta las ponderaciones; el sistema redondea al múltiplo de la lámina mínima y muestra
   la diferencia entre lo pedido y lo real.
6. Agrega la porción de renta variable.
7. Revisa el resumen: renta anual garantizada, TIR, duración, concentración, meses sin
   cobertura.
8. Guarda y exporta la propuesta.

**Flujo B — Optimizar una cartera existente**

1. El asesor carga el portafolio que trae el cliente.
2. El sistema lo valora a precios de hoy y lo describe: TIR, duración, calendario, riesgos
   concentrados, meses vacíos.
3. Muestra dos conjuntos de propuestas: bajar riesgo manteniendo TIR, y subir TIR con el
   riesgo asumido declarado.
4. El asesor acepta o descarta rotación por rotación, viendo el efecto en el calendario.
5. Compara la cartera original contra la propuesta, lado a lado.
6. Guarda y exporta.

## Pantallas esenciales

1. **Login**
2. **Armador** — calendario selector, cartera editable, panel de renta, composición, curva
   TIR/duración
3. **Optimizador** — carga del portafolio, diagnóstico, propuestas de rotación, comparación
   antes/después
4. **Monitor de mercado** — el universo por segmento, con filtros, para consultar sin armar
5. **Mis carteras** — listado de las carteras guardadas del asesor
6. **Detalle de instrumento** — ficha con condiciones de emisión y flujo de fondos completo

## Fuentes de datos

Las dos son públicas y gratuitas, y **se complementan sin superponerse**: BYMA da la rueda,
IAMC da el instrumento. Se unen por la raíz del ticker, porque ley, moneda de pago y
estructura son atributos de la emisión y no de la especie.

**BYMA — API abierta.** Base `https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/`.
Responde por POST sin token ni registro. Verificado el 05/08/2026:

| Endpoint | Filas |
|---|---|
| `negociable-obligations` | 4.909 |
| `public-bonds` | 189 |
| `cedears` | 2.267 |
| `general-equity` | 189 |
| `index-price` | 16 (incluye Índice Dólar BYMA y CCL) |

Campos por instrumento: `bidPrice` / `offerPrice` con sus cantidades, `denominationCcy`
(ARS / USD / EXT — **la moneda de cotización viene declarada**, no hay que inferirla del
sufijo del ticker), `settlementType` (contado inmediato o 24 horas), `closingPrice`,
`vwap`, `volume`, `volumeAmount`, `numberOfOrders`, `maturityDate`.

Limitación: **20 minutos de demora**. El tiempo real va por la *API Market Data* oficial,
que según BYMA no requiere homologación y se solicita a `marketdata@byma.com.ar`.

**IAMC — informe diario de deuda corporativa** (PDF, ~260 ONs). Aporta lo que BYMA no
tiene: emisor con nombre completo, **ley y moneda de pago —que son el título de la sección
del informe, no una columna inferida—**, estructura del cupón, tasa, frecuencia, fecha del
próximo cupón y del próximo pago de capital, valor residual, paridad, valor técnico, TIR,
duración modificada, convexidad, vida promedio y volumen medio de 20 ruedas.

**SEC EDGAR** (`data.sec.gov`, gratuita, sin clave) para las fechas de balances de los
CEDEARs de empresas estadounidenses. Registra lo ya presentado, no un calendario a futuro,
pero el patrón mensual es estable y es lo que se necesita. Para emisores argentinos, la
CNV.

**Sin fuente conocida:** calificación crediticia y lámina mínima. La lámina es necesaria
para redondear los nominales, así que hay que resolverla antes de la Fase 2.

## Stack tecnológico

- **Frontend:** React + TypeScript. Aplicación de una sola página; el renderizado en
  servidor no aporta en una herramienta interna.
- **Backend:** Python. Toda la lógica financiera —segmentación, cálculo de cupones,
  armado y optimización de carteras— vive acá, expuesta como API. Es la decisión correcta
  además porque ese motor **ya está escrito y verificado** contra el Excel real de la mesa
  y contra swaps efectivamente ejecutados.
- **Base de datos y autenticación:** Supabase (PostgreSQL).
- **Hosting:** a definir en la Fase 2.

## Nota sobre el motor existente

Este proyecto no arranca en cero. Hay un motor de cálculo en Python ya construido y
verificado: segmentación en seis naturalezas de tasa, matemática de cupones que reproduce
exacto los nominales del Excel real de la mesa, detección de rotaciones validada contra
swaps que la mesa efectivamente ejecutó, normalización de monedas y control de integridad
del dato. La Fase 2 tiene que decidir qué se conserva como servicio y qué se reescribe.

## Cuestiones abiertas para la Fase 1

1. **"Reducir el riesgo" no es una sola cosa.** Duración, crédito, legislación, liquidez,
   concentración y moneda son riesgos distintos y a veces se mueven en sentidos opuestos.
   El optimizador necesita una definición operativa, o que el asesor elija cuál minimizar.
2. **Falta la lámina mínima**, y sin ella no se puede redondear el nominal — que es
   justamente lo que hace que la ponderación pedida y la real difieran.
3. **De dónde sale el tipo de cambio.** El motor actual lo deriva del propio universo (la
   misma emisión cotiza en pesos y en dólares) y por regla nunca lo toma de afuera. BYMA
   publica su propio Índice Dólar y CCL. Es un cambio de criterio a decidir.
