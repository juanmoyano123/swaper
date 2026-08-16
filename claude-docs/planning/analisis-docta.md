# Análisis competitivo — Docta Terminal

**Relevado el 13/08/2026** · Insumo de las features F-058 a F-070 del Bloque O (Stage 2).

---

## 0. Qué se relevó, y qué no

Docta vende **dos productos distintos**, y este análisis mira sólo uno:

| Producto | Qué es | ¿Se analiza? |
|---|---|---|
| **Terminal** (`app.docta.com.ar`) | Monitor de mercado + herramientas de análisis, con plan free y Pro a $44.900/mes | **Sí.** Es lo que se parece a 10-Swaper |
| **DPM** (`docta.com.ar`) | Infraestructura para ALyC: AUM consolidado, comisiones auditables, portal del comitente, agentes de IA | No. Es un producto de back-office institucional, otro negocio |

**Método.** HTML servido de las rutas públicas del dashboard, más los 84 chunks JavaScript del bundle
de Next.js —los mismos que recibe el navegador de cualquier visitante—. De ahí salen el mapa de rutas,
las 78 claves de columna de las tablas y los rótulos de la interfaz.

**Límite deliberado.** El bundle referencia su API de datos en `docto-api-production.fly.dev`.
**No se sondeó, y no se debe sondear.** Sirve datos de un producto pago del que el proyecto se dio de
baja el 12/08/2026; extraerle datos sería saltear el paywall, que es una cosa distinta de replicar
funcionalidad. Para este análisis alcanza con saber *qué* muestran, no con obtener sus números.

**Qué se replica y qué no.** Las funcionalidades no son de nadie: un carry trade es aritmética
pública. Lo que no se copia es la expresión —código, textos, disposición visual—. Las features de
abajo describen *qué hace* cada herramienta, no cómo se ve.

---

## 1. Mapa de la aplicación

**32 rutas**, agrupadas en nueve secciones.

| Sección | Rutas | Qué hace |
|---|---|---|
| **Bonos** | `/bonos/general/{categoría}/{tasa}` + `/heatmap`, `/historical-curve`, `/calendar`; `/bonos/performance` | Monitor por segmento con cuatro vistas |
| **Acciones** | `/acciones/general` + `/heatmap`; `/acciones/performance` | Monitor y rendimientos |
| **CEDEARs** | `/cedears/general` + `/heatmap`; `/cedears/performance` | Ídem |
| **FCI** | `/fci/general`, `/comparador`, `/categorias`, `/gestoras` | Explorador, comparador, y agregados por categoría y por gestora |
| **Cauciones** | `/cauciones/general` | Curva de tasas de caución por plazo |
| **Futuros** | `/futuros/dolar` + `/heatmap` | Futuros de dólar |
| **Opciones** | `/opciones/stocks` + `/heatmap` | Calls y puts sobre acciones |
| **Herramientas** | `/carry-trade`, `/relative`, `/comparador`, `/performance`, `/calendar` | Las cinco herramientas de análisis |
| **Personal** | `/portfolios`, `/watchlist` | Carteras y seguimiento |

### La taxonomía de bonos: 3 categorías × 7 naturalezas de tasa

```
soberanos    → hard-dollar · fixed-rate · cer · uva · dollar-linked · badlar · tamar · bopreal
subsoberanos → hard-dollar · fixed-rate · cer ·       dollar-linked · badlar · tamar
corporativos → hard-dollar · fixed-rate · cer · uva · dollar-linked ·          tamar
```

**Este es el hallazgo más importante del relevamiento.** Docta navega **por naturaleza de tasa**, con
una pantalla por combinación y sin mezclar nunca dos en la misma tabla. Es, exactamente, la regla 2 de
este proyecto convertida en estructura de navegación — y confirma que la decisión de F-038 ("nunca dos
segmentos a la vez") no es una limitación autoimpuesta sino la forma correcta de presentar el
mercado local. Un competidor con años de uso llegó a la misma conclusión por su cuenta.

Su eje de agrupación es más fino que el nuestro: nosotros separamos por segmento, ellos por
`categoría de emisor × naturaleza de tasa`. Eso es una mejora concreta y adoptable (F-060).

---

## 2. Las tres herramientas que pediste

### 2.1 Carry trade (`/carry-trade`)

Tres piezas:

**Calculadora de carry potencial.** Entradas: ticker · tipo de cambio inicial (MEP / CCL / Oficial) ·
nominales · último precio del bono · tipo de cambio al vencimiento, en dos escenarios (inferior y
superior). Salidas: valor final en MEP, CCL y Oficial · tasa directa · TIR. Más un modo "carry custom".
El supuesto está escrito en pantalla: *"vender dólares a dólar MEP, comprar y mantener el bono hasta el
vencimiento y luego recomprar dólares a los valores de las columnas"*.

**Tabla de carry.** Una fila por instrumento: vencimiento · días al vencimiento · retorno total ·
máxima variación posible · spread contra el tipo de cambio · precio finish · precio · banda superior ·
banda inferior.

**Dos gráficos.** Spread, y **curva de breakeven**: el tipo de cambio al cual el carry deja de
convenir. El bundle trae escenarios preconfigurados —`Carry 1300`, `1400`, `1500`, `1600`— y una nota:
*"bandas proyectadas con inflación del 1%"*.

> **Acá hay una proyección, y es de ellos.** Proyectar las bandas cambiarias con un supuesto de
> inflación es inventar un dato futuro. Nosotros podemos mostrar las bandas **publicadas** por el BCRA
> y dejar que el asesor tipee el escenario que quiera; lo que no hacemos es publicar una banda
> proyectada como si fuera dato. Es la regla 1 aplicada al futuro en vez de al pasado.

### 2.2 Análisis relativo (`/relative`) — la "calculadora de bonos"

Compara **dos instrumentos** lado a lado. El ejemplo por defecto es AL30 contra GD30, que es el par
canónico de legislación local contra extranjera.

- Selector de submercado y de los dos tickers, con **combinaciones rápidas** ya armadas: *Soberanos ·
  Hard Dólar Cable / Dólares / Pesos*, *CER vs. Dólar Linked*, *ONs Energéticas · Dólar*, *ONs de YPF ·
  Dólar*, *Globales / Bonares*.
- **Cashflow de los dos**, superpuestos.
- **Evolución** de ambos más la serie del **relativo** (el cociente).
- **Calculadora comparativa**, con parámetros de convención: fecha de operación · tipo de liquidación
  (CI / 24hs) · convención de tasa (TNA 30/360). Devuelve, para cada uno: precio dirty · paridad · TIR ·
  TNA 30/360 · duración · intereses corridos · días al vencimiento · variación · fecha de liquidación.
  Y las diferencias: **Diferencia TIR**, **Diferencia TNA**.

Esto es la feature más valiosa del relevamiento para 10-Swaper, porque la **candidata "spread por
legislación"** que ya estaba anotada en la sección 11 del plan es un caso particular de esto. Y encima
resuelve la regla 8 —no proponer una mejora de TIR sin nombrar el riesgo— mostrando las dos patas con
la misma vara y la diferencia explícita.

### 2.3 Portfolios (`/portfolios`)

Registro de tenencias con compras y ventas, posición consolidada, valor total, **P&L diario**,
**ganancia no realizada**, y bonos + acciones + CEDEARs + FCI en una sola vista. La landing de DPM
declara **FIFO automatizado** para el cálculo de P&L.

> **Esto choca con una frontera de producto ya decidida.** El riesgo R16 del plan dice que "se guardan
> carteras, no clientes" y que las fronteras se erosionan de a un campo por vez. Un registro de
> transacciones con P&L por lote **no es el armador**: es una herramienta de seguimiento de posiciones
> reales, que empuja hacia el CRM (F-043) y hacia el back-office (que es el otro producto de Docta,
> DPM). Se propone igual como F-070, pero explícitamente marcado como decisión de producto pendiente,
> no como continuación natural.

---

## 3. Las 78 columnas de sus tablas

Extraídas de las definiciones de tabla del bundle. Ordenadas por qué las alimenta.

| Grupo | Columnas |
|---|---|
| **Punta y precio** | `bidPrice` `bidSize` `offerPrice` `offerSize` `lastPrice` `closingPrice` `currentPrice` `market_price` `tradeVolume` `effectiveVolume` `variation` |
| **Bono** | `priceClean` `interesCorrido` `residualValue` `maturity_date` `dtm` `nominalInterestRate` `effectiveInterestRate` `impliedInterestRate` `couponCurrency` `isinCode` `issuer` `metadata.value.law` `metadata.value.issuer` `metadata.value.maturity_date` |
| **Cashflow** | `payment_date` `cash_flow` `adj_capital` `adj_interest_amount` |
| **Carry** | `lower_band` `upper_band` `potential_spread` `px_finish` `tna_range` `range_return` `margen` `forwardTem` |
| **Performance** | `performance.{1D,1W,1M,1Y,YTD}` y su `.return` · `oneWeekPct` `oneMonthPct` `threeMonthsPct` `sixMonthsPct` `oneYearPct` `ytdPct` `dollar_variation` `ticker_return` |
| **FCI** | `aum` `aum_at_end` `fund_name` `manager_name` `fund_count` `share_pct` `net_flow_30d` `net_flow_ytd` `category` `age_days` |
| **Opciones** | `strike` `openInterest` `underlyingPrice` |
| **Clasificación** | `ticker` `cleanTicker` `mainTicker` `specie` `type` `subAssetClass` `sector` `country` `currency` |

**Lo que llama la atención por ausencia.** No hay convexidad, ni Sharpe, ni VaR, ni beta, ni tracking
error, ni score de riesgo compuesto. El Terminal se queda en métricas contractuales y de precio. Es la
misma decisión que la regla 7 de este proyecto.

**`metadata.value.law` y `metadata.value.issuer` existen en su app.** La memoria del proyecto dice que
la API de Docta no exponía ley ni emisor —cierto para el link tokenizado que se contrataba—, pero su
propio producto sí los tiene. Nosotros los conseguimos por IAMC y por `condiciones_emision.csv`, así
que no es un hueco: es la confirmación de que ese dato es parte del mínimo indispensable.

---

## 4. El mapeo que decide qué se puede replicar

Cada feature contra el dato que necesita y contra lo que tenemos.

| # | Feature de Docta | Dato que necesita | ¿Lo tenemos? |
|---|---|---|---|
| 1 | Monitor por naturaleza de tasa | Clasificación por tipo de tasa | **Sí.** `tipo_tasa` del cronograma; `subtipo_de()` ya distingue por ley |
| 2 | Calculadora comparativa de dos bonos | Cronograma + precio + convenciones | **Sí.** F-051 ya resuelve TIR, duración y paridad |
| 3 | Cashflow comparado | Cronograma contractual | **Sí**, con el conjunto cerrado de `cashflow_completo.csv` |
| 4 | Calendario consolidado de pagos | Cronograma | **Sí.** Es F-015 / F-016, ya planificado |
| 5 | Screener con filtros | Universo saneado | **Sí.** Es F-017 |
| 6 | Exportar a Excel | — | **Sí.** Es F-042 |
| 7 | Carry trade | Bandas cambiarias del BCRA | **Falta una fuente.** La API del BCRA ya está verificada para el CER (F-056); las bandas hay que verificarlas |
| 8 | Dólar y spreads (MEP / CCL / canje) | Pares de la misma emisión en dos monedas | **Sí.** F-012 ya lo calcula y no se muestra en ninguna pantalla |
| 9 | Cauciones | Panel de cauciones de BYMA | **Falta ingerirlo.** Usamos 5 endpoints; el de cauciones no está entre ellos |
| 10 | Futuros de dólar | Fuente de futuros | **Falta.** No está en los 5 endpoints; hay que verificar si BYMA lo publica |
| 11 | Opciones | Panel de opciones de BYMA | **Falta ingerirlo.** Ya es F-047, con alcance por definir |
| 12 | FCI: explorador y comparador | Valor de cuotaparte | **Sí, desde el 13/08/2026** — CAFCI, F-057 |
| 13 | FCI: categorías y gestoras (AUM, share) | AUM y gestora por fondo | **Sí.** La planilla de CAFCI trae `patrimonio`, `market share` y sociedad gerente |
| 14 | FCI: flujo neto 30D / YTD | Serie de patrimonio | **No hoy.** Requiere histórico acumulado |
| 15 | Rendimientos históricos por ventana | Serie de precios | **No hoy.** Ver abajo |
| 16 | Curva histórica del segmento | Serie de TIR por ticker | **No hoy.** Ídem |
| 17 | Evolución y relativo de dos tickers | Serie de precios | **No hoy.** Ídem |
| 18 | Heatmap del día | Variación diaria | **Sí.** Sale del snapshot contra el cierre anterior |
| 19 | Top 10 ganadores / perdedores | Variación diaria | **Sí.** Ídem |
| 20 | Watchlist | — | **Sí.** Es sólo persistencia por asesor |
| 21 | Portfolios con P&L y FIFO | Transacciones del asesor | **Sí técnicamente**, pero es decisión de producto (ver 2.3) |
| 22 | Docta AI | — | **No se replica.** Regla 6 |

### El hallazgo estructural: falta tiempo para los bonos, no para la renta variable

Las filas 14 a 17 —**cuatro features**— no dependen de conseguir una fuente sino de tener serie. Pero
el diagnóstico se parte en dos, y conviene no confundirlos.

**La acumulación propia ya está resuelta, y no hay nada que decidir.** `public.precios` tiene
`PRIMARY KEY (ticker, capturado_en)`: cada corrida escribe una fila nueva por especie en vez de pisar
la anterior, así que la historia se viene guardando sola desde la primera corrida. La única variable
es cuánta profundidad haya acumulado para cuando estas features se construyan.

**Para acciones y CEDEARs hay historia externa disponible hoy.** Verificado en vivo el 13/08/2026:
data912 expone `GET /historical/{stocks|cedears}/{ticker}` con **hasta 23 años** para acciones
argentinas (88 % de cobertura) y una mediana de ~6 años para CEDEARs (53 %). Ya hay cliente escrito
en `backend/app/externos/data912.py`. Su contrato es explícito y **acota para qué sirve**: se consulta
por especie al hacer clic, se muestra rotulado con su fuente y su hora, y **nunca se persiste ni se
mezcla con nuestro dato**. Alcanza para un sparkline o una serie de evolución de renta variable; no
alcanza para armar rankings por ventana sobre el panel entero, que exigiría una consulta por especie.

**Para bonos no hay equivalente**, y encima la curva histórica de TIR (fila 16) no podría venir de
afuera aunque existiera la fuente: la TIR es cálculo nuestro contra el cronograma persistido, así que
su serie sólo puede salir de haberla calculado y guardado cada día.

Dos consecuencias que sí valen para el plan:

1. **Las features de histórico se planifican con su fecha de disponibilidad, no sólo con su esfuerzo.**
   Una curva histórica construida sobre tres semanas de datos no es una curva histórica; es ruido con
   ejes. El criterio de aceptación tiene que incluir la ventana mínima y declarar en pantalla desde
   cuándo hay datos.
2. **No se rellena el hueco.** Ni con precios de cierre reconstruidos, ni interpolando, ni empalmando
   la serie de un tercero con la nuestra —que además es lo que el contrato de `app/externos/` ya
   prohíbe—. Un gráfico que arranca en la fecha de la primera corrida y lo dice es honesto; uno que
   arranca antes es inventado.

---

## 5. Lo que no se copia, y por qué

- **Docta AI.** Su propuesta central es "agentes de IA con contexto completo del mercado y de cada
  cartera". La regla 6 de este proyecto es explícita y salió de una decisión del usuario: *"No busco
  algo que razone, sino que analice datos y me devuelva un análisis de datos duros"*. No se replica.
- **Las bandas proyectadas con inflación supuesta.** Ver 2.1. Las bandas publicadas sí; la proyección
  no.
- **El muro de pago por métrica.** Docta reserva para Pro cosas como el selector de ticker del panel
  relative o la exportación de imágenes. Es su modelo de negocio, no una decisión de producto que
  tengamos que imitar.
- **DPM entero.** AUM consolidado por productor, comisiones auditables, portal del comitente: es
  back-office de ALyC, un producto distinto del que estamos construyendo.

---

## 6. Lo que este relevamiento confirma del plan actual

Vale anotarlo, porque es la mitad útil de un análisis competitivo:

- **La navegación por naturaleza de tasa es correcta** — llegaron a lo mismo (sección 1).
- **No construir un score de riesgo compuesto es correcto** — ellos tampoco lo hacen (sección 3).
- **Ley y emisor son datos indispensables, no un lujo** — los tienen en su modelo (sección 3).
- **El calendario de cupones como pantalla propia es correcto** — es una de sus cinco herramientas.
- **Nada de lo que ofrecen resuelve el Flujo B** (diagnosticar y optimizar una cartera existente con
  rotaciones acotadas y costo real de rotar). Tienen monitor, tienen calculadoras y tienen registro de
  tenencias, pero no un optimizador que proponga swaps con su contrapartida de riesgo nombrada. **Ese
  sigue siendo el diferenciador de 10-Swaper**, y este relevamiento no encontró nada que lo discuta.

---

*Relevado el 13/08/2026 sobre `app.docta.com.ar` y `docta.com.ar`. Deriva en las features F-058 a
F-070 del Bloque O.*
