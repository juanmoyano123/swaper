# Investigación — Información pública del emisor: CNV y SEC

Fecha: 12/08/2026. Estado: **investigación cerrada, feature sin planificar**.
Alimenta a: `plan.md` → F-054. Se desarrolla más adelante; esto es lo verificado hasta hoy.

Todo lo que sigue se midió contra las fuentes en vivo. Donde algo no se pudo verificar, dice que no
se pudo verificar — no hay supuestos disfrazados de hallazgos (regla 1 y regla 11).

---

## 1. Qué se quiere

Que al seleccionar un ticker en el monitor o en el armador se abra un modal con **la información
pública del emisor ya procesada**: los números duros de su último balance, con fuente y fecha, para
que el asesor no tenga que ir a buscarla al regulador.

No es un buscador de documentos: es **extracción de datos financieros duros**. Cuatro magnitudes
acordadas:

- resultado del ejercicio
- patrimonio neto
- deuda financiera / EBITDA
- liquidez corriente

**Cómo entra al producto.** Complementa el **eje crédito** del vector de seis ejes: se muestra al lado
de la calificación que ya existe, con su propia fuente y su propia fecha. **No se combina en un score
compuesto** — regla 7. Y nunca se propone una mejora de TIR sin nombrar el riesgo que se asume a
cambio (regla 8): estos números son insumo de esa frase, no un semáforo.

**Alcance del universo:** renta fija (ONs) **y** renta variable (acciones locales y CEDEARs).

- emisor argentino → **CNV**
- CEDEAR / emisor extranjero → **SEC**

---

## 2. CNV — verificado

### 2.1 Las páginas son HTML servido, no una SPA

Esto es el hallazgo que define el costo de la feature: **`curl` plano trae todo**. No hace falta
navegador headless, ni Playwright, ni renderizado. Se verificó tanto para el listado de
presentaciones como para el cuerpo de los balances.

### 2.2 Rutas

| Qué | URL |
|---|---|
| Buscador de empresas | `cnv.gov.ar/sitioweb/empresas?seccion=buscador` — **sólo autocomplete**, no lista |
| Ficha: información financiera | `cnv.gov.ar/SitioWeb/Empresas/Empresa/{CUIT}?formType=INFOFI` |
| Ficha: emisiones | `cnv.gov.ar/SitioWeb/Empresas/Empresa/{CUIT}?formType=EMISIO` |
| Presentación individual | `aif2.cnv.gov.ar/presentations/publicview/{uuid}` |
| Descarga de PDF (prospectos) | `blob.cnv.gov.ar/BlobWebService.svc/DownloadBlob/{id}` |

El buscador no acepta consulta programática por listado: se entra por **CUIT**, que es la llave real
de la ficha. De ahí el puente de la sección 4.

### 2.3 El balance viene como XML estructurado, no como tabla para parsear a ojo

Dentro del HTML de la presentación, cada renglón del estado contable está embebido así:

```xml
<fila>
  <propiedad id="Nro">1999999</propiedad>
  <propiedad id="Rubro">TOTAL DEL ACTIVO</propiedad>
  <propiedad id="Monto"> 6507496.00</propiedad>
</fila>
```

Los códigos de `Nro` son **el plan de cuentas estandarizado de la CNV**: el mismo código significa lo
mismo en todos los emisores. Eso convierte la extracción en un lookup por código, no en una
interpretación de textos libres.

### 2.4 La CNV publica los ratios ya calculados

Hallazgo importante: los códigos **8000000–8000029** son ratios que **declara el emisor y publica el
regulador**. Entre ellos:

`EBITDA` · `LIQUIDEZ` · `DEUDA FINANCIERA/EBITDA` · `SOLVENCIA` · `ROE` · `ROA` ·
`PRUEBA ACIDA` · `DU-PONT`

Dos de las cuatro magnitudes pedidas (deuda financiera/EBITDA y liquidez corriente) **vienen servidas
por la fuente**. Se toman como las publica y no se recalculan: es exactamente lo que manda la regla 11
—se muestra el dato de la fuente, no nuestra interpretación de él—, y además evita el riesgo de que
nuestro cálculo discrepe del que el emisor declaró ante el regulador.

### 2.5 Lo que no se pudo resolver

**Descarga de PDF de prospectos: HTTP 503**, dos intentos, en `blob.cnv.gov.ar`. Nunca se llegó a
bajar un prospecto. Queda pendiente para cuando se programe la feature: hay que determinar si es
intermitencia del servicio, si exige cabeceras o sesión, o si la ruta cambió.

Esto **no bloquea** la feature: los cuatro números pedidos salen de los estados contables, no del
prospecto. El prospecto agregaría las condiciones de la emisión (que hoy vienen de
`condiciones_emision.csv` e IAMC).

---

## 3. SEC — verificado

### 3.1 API XBRL, gratuita y sin clave

```
https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json
https://www.sec.gov/files/company_tickers.json      ← ticker → CIK
```

- No requiere API key.
- **Exige cabecera `User-Agent`** identificando quién consulta (es política de la SEC, no un truco).
- Límite ~10 requests/segundo.
- Devuelve JSON estructurado con la serie histórica completa de cada concepto contable.

### 3.2 La trampa: `us-gaap` no alcanza

Varios de los emisores que nos importan son **foreign private issuers** que presentan 20-F y reportan
bajo **IFRS**, no US GAAP. Buscarlos sólo en la taxonomía `us-gaap` los muestra como "sin datos"
cuando en realidad los datos están, bajo otros nombres. Se verificó con BSBR y RIO: aparecían vacíos y
no lo estaban.

Mapa de equivalencias verificado:

| Concepto | `us-gaap` | `ifrs-full` |
|---|---|---|
| Resultado del ejercicio | `NetIncomeLoss` | `ProfitLoss` |
| Patrimonio neto | `StockholdersEquity` | `Equity` |
| Activo corriente | `AssetsCurrent` | `CurrentAssets` |
| Pasivo corriente | `LiabilitiesCurrent` | `CurrentLiabilities` |

Aplicando el mapa, la medición dio **cero compañías sin datos**.

### 3.3 Dos asimetrías que hay que mostrar, no esconder

**EBITDA no es una etiqueta XBRL.** Es una medida non-GAAP: la SEC no la recibe como tal. Del lado
SEC habría que derivarla; del lado CNV viene **declarada por el emisor**. Son cosas distintas y el
modal tiene que decir cuál es cuál — no pueden aparecer en la misma columna como si fueran el mismo
dato.

**Los bancos no tienen balance clasificado.** No publican activo corriente / pasivo corriente porque
su balance no se ordena por naturaleza sino por liquidez decreciente. Para un banco, la liquidez
corriente es un **`no aplica` estructural**, no un dato faltante. Se declara así.

---

## 4. El puente: del ticker al emisor

Este fue el problema difícil. Un ticker de ON (`CS47`, `IRCFO`) no dice quién es el emisor ni cuál es
su CUIT, y la ficha de CNV se abre por CUIT.

### 4.1 Dos hipótesis descartadas, con la medición

**BYMA como puente → no sirve.** Los campos `securityDesc` y `description` de la API abierta **vienen
vacíos**. Verificado en vivo contra IRCFO.

**El número del ticker es el número de clase → no es una convención de mercado.** Para Cresud dio
10 de 10 (`CS47` = Clase XLVII). Pero los tickers de IRSA (`IRCFO`, `IRCJO`) **no tienen número** y la
CNV le lista Clase XV a XXV. Conclusión: la relación existe **por emisor**, no como regla general. No
se puede derivar — hacerlo sería exactamente el error de los 121 tickers inventados que ya costó una
reversión.

### 4.2 Lo que sí sirve: las tablas de valuación de AFIP/ARCA

Las tablas de valuación de **Bienes Personales** publican, para cada especie: **ticker, denominación,
CUIT y clase**. Es una fuente oficial que hace exactamente el puente que falta.

Se ubicó el PDF (ejercicios 2024 y 2025) pero **no está descargado en el repo**: se bajó a `/tmp`
durante la investigación y es efímero. **Hay que volver a bajarlo cuando se programe la feature.**

### 4.3 Cobertura medida

Midiendo por **emisión raíz** (no por ticker suelto) y sumando la búsqueda por nombre del emisor:

- **86 % resoluble** — se llega del ticker al emisor y de ahí a su ficha en CNV
- **14 % sin resolver** — no hay nombre de emisor en `condiciones_emision.csv`

Ese 14 % **es deuda de dato preexistente**, no una limitación de CNV ni de SEC:
`condiciones_emision.csv` está documentado en `CLAUDE.md` como irrecuperable —se rescató después de
que se borraran los CSV originales—. Se declara como faltante en pantalla (regla 1) y se completa
cuando se pueda, no se infiere.

---

## 5. Costo — por qué esto no es un gastadero de tokens

Preocupación explícita del dueño del producto, y la respuesta es concreta:

**Cero IA en runtime.** Todo el flujo es `httpx` + parsers determinísticos:

1. ticker → CUIT (tabla AFIP, cargada una vez)
2. CUIT → ficha CNV (`curl`)
3. ficha → UUID de la última presentación (parseo de HTML servido)
4. presentación → códigos de cuenta y ratios (parseo del XML embebido)
5. CEDEAR: ticker → CIK (`company_tickers.json`) → `companyfacts` (JSON)

Ni un solo paso necesita un modelo. Cumple la **regla 6** —"la lógica de análisis es determinística,
sin IA"— y por eso el costo operativo del flujo es tráfico HTTP, no tokens. Los tokens se gastan una
vez, escribiendo los parsers.

---

## 6. Decisiones de ejecución ya tomadas

- **En esta fase corre estrictamente a pedido.** Nada programado.
- **Stage 2:** pasa a tarea programada diaria.
- **Antes de implementar** se hace un paso a paso conjunto con links reales —un emisor de CNV y uno de
  la SEC— para validar el flujo de scrapeo contra la fuente antes de escribir código.

---

## 7. Pendientes concretos para cuando se planifique

1. Volver a bajar la tabla de valuación AFIP/ARCA (se perdió con `/tmp`).
2. Resolver el 503 de `blob.cnv.gov.ar` — o decidir que el prospecto queda fuera de alcance.
3. Definir qué se muestra para el 14 % sin emisor resuelto (faltante declarado, sin excepción).
4. Casos borde de CEDEAR → CIK.
5. Diseñar el modal: qué entra, cómo se declara la fuente y la fecha de cada número, y cómo se
   distingue lo declarado por el emisor de lo derivado por nosotros.
