# Lo que BYMA declara y lo que inferimos nosotros

**08/08/2026.** Salió de revisar el monitor en pantalla y preguntar por qué la columna de precio
decía `ARS`, `EXT` y `USD` sin explicar cuál era cuál. La respuesta destapó que estábamos
presentando una inferencia como si fuera dato, y de ahí salió la **regla 11** de `CLAUDE.md`.

Este documento existe para que nadie tenga que volver a medirlo, y sobre todo para que nadie
"arregle" el hueco rellenándolo.

---

## `denominationCcy`: tres valores, dos documentados

BYMA publica la moneda de cotización de cada especie en `denominationCcy` y toma tres valores:

| valor | qué es | cobertura (08/08/2026) |
|---|---|---|
| `ARS` | Pesos argentinos. Código ISO 4217. | 1.351 instrumentos |
| `USD` | Dólares estadounidenses. Código ISO 4217. | 896 |
| `EXT` | **No documentado.** No es ISO 4217. | 647 |

La cobertura del campo es del **100 %**: ninguna especie llega sin declararlo.

### Qué se buscó y no se encontró

`EXT` no está explicado en ningún lado al que tengamos acceso: ni en la respuesta de la API, ni en
`docs/`, ni en `workflows/`, ni en los planes del producto. Lo único que había era nuestra propia
afirmación, escrita en `universo/cambio.py` y en `F-012-plan.md` **en modo indicativo**, como si
fuera un dato de la fuente. No lo era: era una conclusión nuestra que se había solidificado.

### Qué sí se midió

El cociente entre el precio de una especie y el de su hermana en pesos, por moneda declarada:

| moneda | mediana del cociente | pares |
|---|---|---|
| `USD` | **1.521,58** | 194 |
| `EXT` | **1.576,39** | 53 |

3,6 % de diferencia, que es exactamente el canje MEP/cable. O sea: `EXT` es *un* dólar, y muy
probablemente el cable. **Pero eso lo dedujimos nosotros del cociente, no lo declaró BYMA**, y esa
distinción es toda la regla 11.

### Corroboraciones externas (que tampoco son fuente)

- **Balanz** rotula su filtro de moneda como "Pesos / Dólar MEP / Dólar Cable" y la especie C cae en
  Cable. Es el criterio de un participante del mercado, no la declaración del mercado.
- **Balanz no publica TIR para ninguna especie C** (verificado sobre AE38C, AL30C, AL29C y S2G6C,
  todas con guión, mientras las de pesos y MEP muestran número). Llegan por su cuenta a la misma
  conclusión que nosotros: sobre la cable no se afirma un rendimiento.

## Qué se hizo con eso

Se sacó la inferencia de todos los lugares donde alimentaba un número mostrado:

- `EXT` no cuenta como dólar (`MONEDAS_EN_DOLARES`), así que **su volumen no se convierte**: queda
  vacío y se cuenta (214 especies de renta fija, 341 de renta variable).
- `EXT` no entra a la muestra del tipo de cambio implícito. **No costó nada**: cero emisiones tienen
  su único par por `EXT`, así que el implícito conserva sus 462 pares y sigue dando 1.521,53.
- `EXT` no habilita el cálculo de TIR, duración y paridad (`MONEDAS_DEL_FLUJO`). Cuesta 63 de las
  276 especies hard-dollar que tienen precio y cronograma; quedan 213.
- **Se dejó de deducir la moneda del sufijo del ticker** cuando la fuente no la declara. Hoy no
  cuesta nada (cobertura 100 %) y evita el error que ya estaba latente: hay **seis especies con
  sufijo D declaradas en `ARS`** —BA37D, BB37D, BC37D, SA24D y dos sin precio— con precios de
  121.100 y 123.800, que son pesos sin ninguna duda.

**En pantalla el hueco se resolvió repartiendo en vez de rellenando**: el monitor elige una moneda
por vez, así que el volumen se muestra crudo y no hace falta convertir nada.

---

## El trío X/Y/Z: 419 especies de las que no sabemos nada

BYMA publica, además del trío O/D/C de cada bono, un segundo trío con sufijos X, Y y Z. Sobre la
renta fija: **X → ARS (198), Y → USD (142), Z → EXT (79)**. Mismo vencimiento, mismas monedas.

`raiz_emision` (`backend/app/ingesta/raiz.py`) **no los corta a propósito**: derivar AL30 de AL30X
sería manipular strings para inventar un ticker, que es el error que costó revertir 121 tickers.
La consecuencia es que quedan sin cronograma, sin tipo de tasa y sin segmento — y por lo tanto
fuera del monitor.

**Son 419 de los 535 "sin segmento no se muestran acá" (78 %.)**

### La hipótesis que se probó y falló

Parecía razonable que O/D/C fuera un plazo de liquidación y X/Y/Z el otro. **No lo es**, por dos
mediciones independientes:

1. En nuestra base, `plazo_liquidacion` (el `settlementType` de BYMA) vale "1" y "2" en los dos
   tríos por igual.
2. En Balanz, cambiar el plazo de 24hs a CI muestra **los mismos tickers** —AE38, AE38C, AE38D— con
   otros precios y otros volúmenes. El plazo no vive en el ticker.

Qué son X/Y/Z sigue sin saberse, y por la regla 11 no se adivina.

---

## Pregunta abierta: ¿estamos mezclando plazos de liquidación?

Balanz muestra el mismo ticker bajo dos plazos (CI y 24hs) con **precios y volúmenes distintos**:
AE38 vale 1.235,30 a 24hs y 1.234,30 a CI, con 7.448 millones de volumen contra 1.288 millones.

Nuestra base tiene **una sola fila por ticker** (2.894 filas, 2.894 tickers en la última corrida),
de las cuales **2.758 son plazo "2" y 136 son plazo "1"**.

No sabemos si BYMA publica los dos plazos y nos quedamos con uno, o si el endpoint devuelve uno
solo. Si fuera lo primero, habría 136 especies cuyo precio y volumen vienen de un plazo distinto al
del resto, mezcladas en la misma lista sin distinción — el mismo problema de comparabilidad que la
moneda, en otro eje.

**Se responde mirando la respuesta cruda de una corrida de ingesta, no consultando la base.** Queda
pendiente.
