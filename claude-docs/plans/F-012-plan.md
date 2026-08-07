# Feature Plan: F-012 — Tipo de cambio implícito, normalización de volumen y contraste

## Contexto

- **Source:** `claude-docs/planning/plan.md` (ficha F-012) + `tools/segmentos.py:178-232`
  (`tipo_cambio_implicito`) y `:331-352` (el bloque de liquidez comparable).
- **Depende de:** F-010. **Habilita:** F-013, F-031, F-038. **Cierra el Ciclo 1.**
- **Complejidad:** M. El cálculo ya estaba resuelto y verificado; el trabajo fue portarlo, decidir
  de dónde sale la moneda de cotización y de dónde sale el índice de contraste, y cerrar el
  desempate que F-011 dejó abierto a la espera de este volumen.

Es la regla 3 del dominio hecha código: *"Nada se compara entre monedas sin normalizar. El tipo de
cambio se deriva del propio universo —la misma emisión cotiza en pesos y en dólares, y ese cociente
es el MEP—, nunca de una fuente externa."*

## Decisiones de diseño

### 1. La moneda de cotización se lee de `instrumentos`, no se deduce del sufijo del ticker

El motor deduce la moneda del sufijo (`D`/`C` → dólares, resto → pesos). **Acá se usa el
`denominationCcy` que declara BYMA**, que F-007 guardó en `instrumentos.moneda_cotizacion`.

No es una preferencia estética. Sobre el universo de hoy hay **seis especies con sufijo D declaradas
en ARS** —BA37D, BB37D, BC37D, SA24D y dos sin precio— y sus precios lo confirman sin ninguna duda:
121.100, 123.800, 117.010 no son precios en dólares. La regla del sufijo las habría tomado por
dólares y habría multiplicado su liquidez por ~1.500. Es exactamente el error que la feature existe
para evitar, cometido en la otra dirección.

`EXT` cuenta como dólar: es la denominación con la que BYMA publica la especie cable, y el cociente
contra su hermana en pesos da 1576 —un dólar cable—, no 1.

**Cuando la fuente no declara nada se cae a la regla del sufijo y se cuenta cuántas veces.** Es lo
único que este módulo supone, y por eso sale como alerta (`moneda_de_cotizacion_asumida`) con el
número exacto en vez de esconderse. Sobre la base de hoy la cobertura es del **100 %** y esa rama no
se toca; sobre el consolidado histórico, que no tiene la columna, se toca para las 937 especies.

**El emparejamiento sí es por sufijo, y eso no es lo mismo.** Cuál es la especie MEP y cuál la cable
es un hecho del ticker por convención de BYMA —F-011 ya lo estableció en `sufijo_liquidacion`— y la
ficha de la feature lo pide explícitamente. Lo que no se deduce del ticker es la *moneda*.

### 2. La moneda no está en la vista `resumen`, así que se trae con un `LEFT JOIN`

F-007 agregó `moneda_cotizacion` a `instrumentos` pero dejó el contrato de 21 columnas de la vista
intacto a propósito, para que el motor Python siguiera leyendo lo mismo. Meterla en la vista sería
un cambio de esquema.

El JOIN es seguro por una razón concreta: `instrumentos` tiene una fila por ticker y **no es una
serie temporal**, así que unirla no reintroduce el problema que la vista existe para resolver
—mezclar métricas de capturas distintas en la misma fila—, que sí aparecería si se unieran `precios`
o `puntas`. Es `LEFT` y no `INNER` para que una especie sin fila en `instrumentos` siga apareciendo
en el universo con la moneda vacía.

### 3. El `index-price` se pide vivo a BYMA y no se persiste

F-007 dejó `FilaIndice` explícitamente fuera del esquema. Las tres razones para pedirlo vivo:

1. **Persistirlo sería un cambio de esquema**, tomado por cuenta propia sobre una decisión que se
   tomó explícitamente en otra feature.
2. **El contraste es un control de hoy sobre un número de hoy.** El implícito sale de los precios de
   la última corrida; un índice guardado ayer contrastaría dos ruedas distintas y la diferencia
   hablaría del paso del tiempo, no de un error.
3. **Es una sola llamada, sin token y de 16 filas.** No hace falta traer el resto de la ingesta.

Vive en `app/universo/indice.py`, aislado del resto del paquete, que es puro. Cualquier fallo
—endpoint caído, timeout, formato inesperado— devuelve lista vacía y queda en el log: **el
contraste no puede tumbar el cálculo del implícito**, que sale del universo y no necesita a BYMA.

La petición va **en paralelo con la lectura de la vista** (`asyncio.gather`): son independientes
—una es SQL y la otra HTTP— y ese costo lo paga cada endpoint de `/universo`. Medido sobre el
universo real: 0,55 s en serie contra 0,20 s en paralelo.

### 4. `index-price` no publica ningún "Índice Dólar" — el contraste es `M` / `SPMERVDT`

La ficha del plan da por sentado que BYMA publica un índice dólar. **Verificado contra el endpoint
vivo: no lo publica.** Son 16 filas y ninguna lo es.

Lo que sí publica es el mismo panel en las dos monedas: `M` (S&P MERVAL, en pesos) y `SPMERVDT`
(S&P MERVAL USD). Su cociente es el tipo de cambio con el que BYMA valúa su propio índice, y ése es
el número contra el que se contrasta. Es tan derivado como el nuestro, sólo que de otro universo —
por eso contrasta y no alimenta.

La tolerancia es del **5 %**, fijada por encima del canje MEP/cable (~3,6 % medido). Si algún día
BYMA valuara su índice en dólares al cable en vez de al MEP, la diferencia saltaría por un spread
estructural conocido y no por un error; una alerta que grita por eso todos los días es una alerta
que nadie mira. Quedó como constante de módulo y no en `core/config.py`: hacerla configurable habría
sido tocar un archivo fuera de alcance sin que nadie lo haya pedido.

### 5. Sin tipo de cambio, el volumen queda vacío y no crudo

Es la única divergencia deliberada con el motor, que en un día sin pares deja `volumen_usd =
effectiveVolume`. Un número del que no se sabe la unidad no es comparable con otro, y devolverlo
igual sería ofrecer una comparación que no se puede hacer — el desempate por liquidez terminaría
ordenando pesos contra dólares. `None` significa "no se pudo normalizar", y en el desempate cuenta
como cero: una liquidez que no se conoce no puede ganarle a una que sí.

### 6. El volumen crudo sigue viajando junto al normalizado

`EspecieUniverso` lleva los dos, y los dos salen por el API. El crudo es lo que la fuente publicó y
el normalizado es lo que se deriva de él: esconder el primero haría imposible auditar el segundo.

### 7. Las alertas del tipo de cambio van a la misma lista que las de sanidad

`UniversoSaneado.alertas` ahora es `sanidad.alertas + cambio.alertas`. Quien las lee —la barra de
estado del dato, F-013— tiene una sola lista: un universo cuya liquidez no se puede comparar está
tan incompleto como uno con instrumentos descartados, y presentarlos en dos lugares distintos haría
que uno se mire menos que el otro.

Eso cambió el contrato que F-010 había asertado en tres tests, que se actualizaron declarando el
porqué. El caso testigo es el universo vacío: la sanidad no opina sobre él (`sanidad.alertas == []`)
pero F-012 sí, porque su alerta habla de lo que **no se puede hacer** con ese universo.

### 8. El orden dentro de `sanear` importa: el cambio se deriva antes de deduplicar

`segmentar → derivar tipo de cambio → normalizar volumen → evaluar sanidad`, y la deduplicación
cuelga de `UniversoSaneado.emisiones()`. Si el tipo de cambio se calculara después, el representante
de cada emisión se elegiría con la columna vacía y el desempate volvería a caer en el ticker sin que
nada lo dijera.

El implícito se deriva sobre el universo segmentado **entero, descartados incluidos**, que es el
mismo conjunto que usa el motor. No hace falta sacarles los descartes: la sanidad juzga el
*rendimiento* y no el precio, y contra un precio mal cargado ya protege el chequeo de rango.

### 9. Se cerró el desempate de F-011 tal como F-011 lo dejó escrito

`_prioridad` pasó de `(descartado, -completitud, ticker)` a
`(descartado, -completitud, -volumen_usd, ticker)`. No se tocó nada más de ese módulo, que era la
promesa del punto de enganche.

## Archivos

| Archivo | Qué es |
|---|---|
| `backend/app/universo/cambio.py` | **nuevo.** El implícito, el volumen en dólares y el contraste. Puro |
| `backend/app/universo/indice.py` | **nuevo.** De dónde sale el `index-price`. Lo único que toca la red |
| `backend/app/universo/lectura.py` | +2 columnas (`lastPrice`, `effectiveVolume`) y el `LEFT JOIN` a `instrumentos` |
| `backend/app/universo/segmentacion.py` | `EspecieUniverso` +4 campos: `precio`, `volumen`, `moneda_cotizacion`, `volumen_usd` |
| `backend/app/universo/servicio.py` | el orden de `sanear`, el campo `cambio` y las alertas unidas |
| `backend/app/universo/emisiones.py` | el cuarto criterio en `_prioridad`; `desempate_por_volumen` deja de ser constante |
| `backend/app/api/v1/universo.py` | `/universo/tipo-de-cambio` |
| `backend/tests/test_universo_cambio.py` | **nuevo.** Los cinco GWT y los bordes del motor. 24 tests |
| `backend/tests/test_universo_cambio_api.py` | **nuevo.** El contrato HTTP. 5 tests |
| `backend/tests/test_universo_indice.py` | **nuevo.** Que ningún fallo de BYMA se propague. 5 tests |
| `backend/tests/test_universo_cambio_integration.py` | **nuevo.** Contra la base y BYMA reales. 7 tests |
| `backend/tests/test_universo_emisiones.py` | el desempate por liquidez, reemplazando el hueco de F-011 |
| `backend/tests/test_universo_emisiones_paridad.py` | corre el camino de F-012 y afirma dónde difiere del motor |
| `backend/tests/test_universo_api.py`, `test_universo_servicio.py` | el contrato de alertas, actualizado |

## Lo que dijo el test de paridad: el motor pierde el volumen en punto flotante

F-011 dejó escrito que con el desempate por volumen los dos iban a elegir siempre lo mismo. Son
**272 de 279**, y las 7 que faltan no son un port mal hecho.

El motor no ordena por una tupla: ordena por `sano * 1e24 + completitud * 1e12 + volumen_usd` y se
queda con el `idxmax`. En float64 el espacio entre dos números representables alrededor de `1e24` es
**134.217.728**, y los volúmenes del consolidado llegan hasta 1,9e8: **casi todos caen por debajo de
un ulp y la suma los descarta enteros**. Cuando eso pasa las hermanas quedan con la misma clave bit
a bit e `idxmax` devuelve la primera fila, que en un universo ordenado por ticker es la alfabética.

Las 7 diferencias son exactamente los grupos donde el volumen sí debería haber decidido, y en los 7
el backend elige la especie **más operada**: BA7DD (333.383 USD) contra BA7DC (3.455), BB7DD
(115.402) contra BB7DC (80), y así con BC33, BPA7, BPB8, BPD7 y PUA6. Reproducir el redondeo para
que el número diera 279 sería portar el error, no el criterio. El test lo afirma al revés: exige que
**ninguna** diferencia sea un caso donde el backend eligió la menos líquida.

Esto es un hallazgo sobre `tools/segmentos.py` que conviene registrar aparte: su desempate por
volumen no funciona.

## Estado del universo real (07/08/2026)

Sobre las 2.894 filas de `resumen` → 942 especies segmentadas:

| | |
|---|---|
| Tipo de cambio implícito | **1.521,53** |
| Pares que lo formaron | **216** (mínimo exigido: 20) |
| Dispersión intercuartil | **0,37 %** |
| Emisiones que entraron por la especie C | **0** (todas las que tienen cable tienen también MEP) |
| Cocientes fuera de rango | **0** |
| Especies con la moneda asumida en vez de leída | **0** (cobertura de `denominationCcy`: 100 %) |
| Contraste: `M` / `SPMERVDT` publicado | **1.519,47** |
| Diferencia contra el implícito | **+0,14 %** (tolerancia: 5 %) |
| Alertas de la corrida | **ninguna** |

Ningún resultado dio cero por un problema de código. Los tres ceros de la tabla —cable, cocientes
imposibles, moneda asumida— son ceros del dato: hoy el universo está limpio en esos tres frentes, y
los tres caminos están cubiertos por tests puros que los ejercitan con universos armados a mano.

El contraste contra la mediana de los cocientes por especie C da **1.576,21**, un **3,6 %** por
encima del MEP. Es el canje, medido, y es la confirmación empírica de por qué la D es la referencia
y la C sólo el último recurso.

### El desempate por liquidez, medido

| | Antes (F-011) | Después (F-012) |
|---|---|---|
| Emisiones | 431 | 431 |
| Emisiones multiespecie | 299 | 299 |
| Emisiones que pierden el rendimiento al colapsar | **199** | **146** |
| Operables que sobreviven a la vista colapsada | **18** de 217 | **71** de 217 |

El representante cambió en **190** emisiones. Las 146 que siguen sin rendimiento se abren así:

- **28** son grupos donde **ninguna** especie se operó: el desempate no tiene con qué decidir y
  termina cayendo en el ticker.
- **118** son grupos donde la especie más líquida sencillamente **no es** la que IAMC nombra.

## La decisión que queda abierta

**Enchufar el volumen normalizado mejoró el número casi al cuádruple pero no lo resolvió.** Sigue
habiendo 146 de 431 emisiones que el armador no va a poder proponer aunque su rendimiento exista en
la vista viva.

No se avanzó más por cuenta propia. Preferir a la especie que publica rendimiento sería un **quinto
criterio que el motor no tiene**, y agregarlo sería cambiar el criterio de armado sin que nadie lo
haya decidido — la misma razón por la que F-011 no lo agregó. Lo que se hizo es dejar el número
medido y abierto, con la alerta `rendimiento_perdido_al_colapsar` actualizada para decir que el
desempate por volumen **ya está aplicado** y que lo que falta decidir es otra cosa.

Las dos salidas posibles, para quien las decida:

1. **Un quinto criterio explícito** que prefiera a la especie que publica rendimiento, aplicado
   sólo cuando las hermanas empatan en sanidad, completitud y liquidez.
2. **Propagar el rendimiento dentro de la emisión**: la TIR es de la emisión —no de la especie— y
   hoy IAMC la publica en una sola. Es más profundo y toca a F-010, que la usa para la coherencia
   entre especies, así que no es una decisión de esta feature.

## Riesgos

- **El contraste depende de que BYMA esté arriba en cada request.** Mitigado: `leer_indices`
  devuelve vacío ante cualquier fallo, y `test_universo_indice.py` prueba las tres familias de
  error. El implícito sale igual y se declara que no se lo pudo contrastar.
- **La llamada viva agrega latencia a todos los endpoints de `/universo`.** Es una sola petición de
  16 filas a un endpoint sin token, ~0,20 s, y va en paralelo con el SQL así que no suma al total.
  Si igual se vuelve molesta, la salida natural es persistir el índice con la corrida de ingesta,
  que es un cambio de esquema y por eso no se hizo acá.
- **El fallback de moneda por sufijo es una suposición.** Hoy no se usa (cobertura 100 %) y cuando
  se use sale alertado con el conteo. Si la cobertura de `denominationCcy` cayera, la alerta lo
  dice antes de que nadie lo note en un número raro.
- **El desempate por volumen depende del tipo de cambio.** En un día sin pares suficientes, todas
  las especies quedan sin `volumen_usd` y el representante vuelve a elegirse por ticker.
  `resumen()["desempate_por_volumen"]` lo declara por corrida en vez de darlo por sentado.
