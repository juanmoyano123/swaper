# Estado del motor de cálculo

> **Qué es este documento.** El registro de qué se construyó, qué se verificó y contra qué
> fuente, del **motor de cálculo en Python** (`tools/`). Es la procedencia de todo lo que el
> producto da por cierto.
>
> **No describe el producto.** Desde el 05/08/2026 el proyecto es una aplicación web para
> asesores; para eso leé `README.md` y `claude-docs/planning/product-definition.md`. Acá el
> motor todavía se describe como la herramienta de línea de comandos que era, porque eso es
> lo que efectivamente se verificó.
>
> Última actualización del motor: 30/07/2026.
>
> **Tres cosas cambiaron desde entonces y no están reflejadas abajo:**
> 1. `data/condiciones_estaticas.csv` y `condiciones_monitor.csv` **ya no existen**. Sus datos
>    se rescataron a `data/condiciones_emision.csv` (823 tickers). Todo lo que este documento
>    diga sobre esos dos archivos es histórico.
> 2. **Las fuentes cambian**: BYMA (API abierta, sin token) para precios y puntas, IAMC para
>    las condiciones del instrumento, y Docta **sólo** para el cronograma de pagos.
> 3. **No correr `tools/consolidar_universo.py`**: fusiona desde un CSV borrado y dejaría el
>    universo sin ley, moneda, lámina, calificación ni sector.

## Resumen ejecutivo (27/07/2026)

**El núcleo está completo y operativo para el flujo diario**: correr el consolidador a la mañana, armar carteras y buscar swaps con datos frescos.

- Los dos pilares construidos, verificados con 15 casos de regresión.
- Matemática de cupones validada contra el Excel real del usuario (reproduce exacto los nominales de RUCED, SBC2D, CS47D, LOC5D).
- Swaper validado contra swaps reales de la mesa (TLCWO→TLCMO).
- Análisis de cupones integrado a ambos pilares: calendario de cobros como criterio de armado, aviso de cupón próximo antes de rotar.

### Qué se hizo en la segunda sesión

**Segmentación unificada** en `tools/segmentos.py`, compartida por los dos pilares. El motor de swaps ya no descarta Tamar, ONs dólar-linked ni subsoberanos en pesos: pasó de cubrir 4 segmentos a 6, y de descartar 112 tickers en silencio a alertarlos.

**Tres bugs de comparación entre monedas encontrados y corregidos.** Salieron de una pregunta del usuario: *"¿estás midiendo todo en la misma moneda? ¿peras con peras?"*.

1. `effectiveVolume` viene en monedas mezcladas, igual que `lastPrice` — la trampa ya documentada, pero para volumen nunca se había visto. La especie en pesos de un bono muestra ~1.500× más volumen que su especie en dólares por el tipo de cambio, no por operarse más. Rompía el filtro de liquidez del armador (descartaba el 37% de las especies MEP contra el 2% de las especies en pesos, o sea filtraba por moneda), el flag `mejora_volumen` del swaper y el desempate del deduplicador. **Arreglo**: todo a dólares, con el tipo de cambio derivado del propio universo.
2. Un corte de sanidad único sobre el rendimiento habría cruzado naturalezas de tasa. Va **por segmento**, en la unidad de cada uno.
3. La tabla de premio por legislación emparejaba cualquier Ley ARG contra cualquier Ley N.Y. del segmento, mezclando riesgo de crédito con legislación (daba 4.964 bps comparando una ON en distress contra un Global). Ahora exige **mismo emisor**.

**Sanidad del dato**: se descartan los rendimientos que no pueden ser ciertos (VSCQD figuraba con 34.627.917% mientras VSCQO, el mismo bono, rinde 6,75%). Ver "Sanidad del dato" más abajo.

**Funcionalidad nueva en el swaper**: frecuencia de cobro de cupones (columna, filtro y desempate), premio por legislación en bps contra la mediana de la curva, hoja de sensibilidad a compresión de TIR, `riesgo_nota` en tres categorías de crédito, topes anti-distress configurables por segmento.

**Calidad del ranking de destinos** (cierre de la sesión): dos filtros nuevos, ambos con criterios heredados del armador, cero umbrales inventados.

- `--percentil-liquidez` (default 25, el del perfil moderado): excluye destinos bajo ese percentil de volumen operado en USD dentro de su segmento. Antes, 24 de 51 propuestas apuntaban a GYC4C (USD 494 operados) e IRCJC (USD 196) — papeles sin contraparte cuya TIR alta era precio viejo. Solo filtra destinos; los orígenes ilíquidos se analizan igual. Con menos de 10 candidatos en el segmento no aplica y sale alerta.
- `--min-rend` (default 0%, mismo flag que el armador): no se propone rotar hacia una TIR negativa. Antes proponía AER9O → MGCEO con el destino rindiendo −3,8%, y MGCEO figuraba a la vez como origen a desarmar y destino recomendado.
- Con `--percentil-liquidez 0 --min-rend -999` el output es idéntico al anterior, hoja por hoja: los filtros son estrictamente aditivos.

**Herencia de condiciones entre especies** (consolidador): ley, moneda de pago, lámina y calificación son atributos de la emisión — AL30, AL30D y AL30C son el mismo bono. Si una especie tiene el dato, las otras lo heredan; si dos declaran valores distintos, no se elige: se alerta. Recuperó 137 leyes, 134 monedas, 67 láminas y 43 calificaciones sin fuente nueva.

**Poda de outputs** (`segmentos.podar_outputs`): se conservan los últimos 10 de cada tipo (carteras, swaps, logs). Una tanda de regresiones había dejado 200+ archivos que hubo que borrar a mano.

**Costo real de rotar** (`tools/mercado.py`). El motor contaba solo el arancel (1,5%) e ignoraba que la rotación paga el spread bid/ask en las dos patas. Con las puntas de data912 el costo mediano pasó de 1,50% a **3,10%**, y 12 de 51 rotaciones superan el 5%: el motor venía proponiendo swaps que en la práctica no convenían.

**Sectores revisados y cerrados.** Los 68 emisores de `sectores_a_revisar.csv` se validaron con el usuario. Correcciones aplicadas vía `tools/aplicar_sectores.py`: las 6 generadoras eléctricas (AES, Central Puerto, Generación Litoral, Generación Mediterránea, YPF LUZ, Tango Energy) pasaron de O&G a **Servicios** — su riesgo es tarifario y regulado, no de precio del crudo, y van con las distribuidoras; y Aeropuertos Argentina 2000 pasó de Construcción a **Infraestructura** (sector nuevo), porque es concesionaria, no constructora. 20 tickers reclasificados. El archivo de revisión se eliminó.

**Condiciones de emisión desde el export del monitor.** El botón "Exportar Excel" del monitor entrega 216 ONs con ley, moneda, calificación y lámina. Incorporado con `tools/merge_condiciones.py` (solo completa huecos; `--forzar` para pisar). Resultado: ley 267 → **640**, moneda 267 → **628**, y dos datos que antes no existían — lámina **585** y calificación **359**. La tabla de premio por legislación pasó de 9 a 16 pares.

**Dos errores míos de invención, detectados por el usuario y corregidos.** Los dos venían de la misma causa: completar con inferencia en vez de esperar el dato.

1. **Inventé una categoría de ley.** Traduje el código `ENG` de la base del monitor como "Ley Inglesa" y lo cargué en 3 tickers. La fuente solo publica **ARG y NY**. Verifiqué que "Ley Inglesa" no existía en el dato original y la revertí. `merge_condiciones.py` ahora rechaza y reporta cualquier código fuera del mapa en vez de traducirlo, y vacía las leyes fuera del vocabulario ARG/NY aunque no entren en conflicto con nada.
2. **Derivé tickers de especie por manipulación de strings.** Con solo el export de especies D disponible, generé las especies en pesos y Cable cortando la última letra y agregando O y C. Al llegar los otros dos exports se pudo auditar: de 216 derivaciones, **121 tickers Cable y 2 en pesos no existen**. El filtro contra el universo atajó parte, pero **88 tickers habían quedado con datos sin respaldo en ninguna fuente**. Se limpiaron y se rehizo todo desde los tres exports reales, sin derivar nada. La cobertura bajó (ley 639 → 554) y esa baja es el punto: es la diferencia entre cobertura inferida y cobertura respaldada.

**Los conflictos entre fuentes se resolvieron con el dato completo.** Con un solo export aparecían 15 emisiones donde las especies del mismo bono declaraban valores distintos (12 de moneda, 3 de ley). Con las tres especies publicadas quedó claro que el monitor es internamente consistente —DNCBD, DNCBO y DNCBC son las tres CABLE— y que el dato viejo cargado a mano era el equivocado. También quedó demostrado que **la moneda de pago es atributo de la emisión, no de la especie**. `data/conflictos_condiciones.csv` se eliminó: no queda ninguno. La detección sigue en `merge_condiciones.py` para futuras cargas: vacía lo contradictorio y lo acumula en ese archivo, sin elegir fuente por cuenta propia.

**Sobre data912**: se evaluó para recalcular la TIR con el último precio operado y **no aporta** — sus precios coinciden con Docta (572 de 576 con menos de 0,1% de diferencia; ambas fuentes leen BYMA), y donde Docta no publica precio es porque el instrumento no opera (de los 145 tickers exclusivos de data912, solo 6 registraron operaciones contra el 92% de los que Docta cubre). Lo que sí aporta, y Docta no tiene, son las puntas bid/ask.

**Orden sugerido de próximos pasos:**

1. Volver a exportar los tres Excels del monitor cuando incorpore más instrumentos: es el camino para cubrir los 373 que siguen sin ley.
2. Usar la herramienta unos días y ajustar con lo que aparezca.

## Qué es

Herramienta de análisis y automatización de renta fija argentina (bonos soberanos, subsoberanos y ONs). Desde el 30/07/2026 el universo incluye además **acciones locales y CEDEARs**, para poder replicar las carteras sugeridas por la mesa, que tienen renta variable (la Audaz es 80%).

**Las dos familias no se mezclan.** Una acción no tiene TIR, duration ni cashflow: no es comparable con un bono y no entra al armador ni al swaper. La frontera vive en un solo lugar, `segmentos.cargar_universo()`; la renta variable se pide aparte con `segmentos.cargar_renta_variable()`.

**Los FCI siguen sin fuente** — no hay submercado FCI en Docta ni cuotapartes en data912 (verificado 30/07/2026). Las carteras de la mesa los usan, así que van como línea con peso y sin precio. Opciones sigue fuera de alcance.

Usuario: asesor financiero en una ALyC argentina, da soporte de cartera a asesores independientes.

Framework WAT (`CLAUDE.md`): workflows en markdown, ejecución en Python determinístico, secretos en `.env`.

## Los dos pilares (ambos construidos y verificados)

| Pilar | Herramienta | Qué hace |
|---|---|---|
| **1. Armador de carteras** | `tools/armar_cartera.py` | Cartera por perfil/cobertura/horizonte, priorizando cobro mensual continuo |
| **2. Buscador de swaps** | `tools/detectar_swaps.py` | Detecta TIR baja/negativa y propone rotaciones a igual o menor riesgo |

Base de datos común: `tools/consolidar_universo.py` → `data/output/universo_consolidado.xlsx` (**1.689 instrumentos**: 937 de renta fija — 125 soberanos, 47 subsoberanos, 765 ONs — más 69 acciones y 683 CEDEARs) + `cashflow_completo.csv`.

Módulo transversal: `tools/cupones.py` — calendario de cobros, usado por ambos pilares.

## Comandos

```bash
# 1. Actualizar la base (correr primero, todos los días que se opere)
python3 tools/consolidar_universo.py

# 2. Armar una cartera
python3 tools/armar_cartera.py --monto 100000
python3 tools/armar_cartera.py --monto 50000 --perfil conservador --horizonte corto
python3 tools/armar_cartera.py --monto 80000 --cobertura devaluacion
python3 tools/armar_cartera.py --monto 80000 --mix "usd_hard=60,cer=40"

# 3. Buscar swaps
python3 tools/detectar_swaps.py                  # orígenes = TIR negativa
python3 tools/detectar_swaps.py --origen todos
python3 tools/detectar_swaps.py --cartera data/cartera.csv
```

Flags completos en `workflows/armar_cartera.md` y `workflows/detectar_swaps.md`.

## Decisiones de diseño que NO hay que revertir

1. **Solo datos que el usuario provee o fuentes acordadas.** Nada de scraping ni búsqueda web libre. Si falta un dato, se deja vacío y se alerta — **nunca se inventa**. (Antecedente: una vez inventé tickers para una whitelist de prueba y estuvo mal.)

2. **Lógica 100% determinística, sin IA en el análisis.** Pedido textual: *"no busco algo que razone, sino que analice datos y me devuelva un análisis de datos duros"*.

3. **Los rendimientos NO se promedian entre sí.** Una TIR en dólares, una tasa *real* sobre CER y una TNA *nominal* en pesos son unidades distintas. Se reportan abiertos en 4 naturalezas de tasa.

4. **El riesgo soberano se agrupa aparte.** El Tesoro emite bajo muchos prefijos (GD, AE, DIC, TZX, TY3…) y todos son el mismo crédito → clave única `SOBERANO_AR` con tope propio (`max_soberano`), separado del corporativo. Sin esto una cartera 100% soberana pasaba como diversificada.

5. **El calendario de cupones es CRITERIO DE ARMADO, no reporte.** Pedido textual: *"la predecibilidad del cashflow es la piedra fundamental sobre la que fomentamos la inversión en bonos"*. El armador desempata candidatos parejos (banda 0,5pp) por mes de cobro descubierto. Su Excel real lo confirma: hoja "Renta Fija pago mensual" con totales mensuales sin ningún mes en cero.

6. **El perfil no define el mix.** El mix sale del objetivo de **cobertura**; el perfil define la **calidad exigida** (tope de rendimiento, liquidez, concentración).

7. **Outputs = documentos internos**, no entregables a cliente. El usuario arma la presentación final por su cuenta.

8. **Avisar antes de escalar de modelo** a Fable/Opus.

9. **Nada se compara entre monedas sin normalizar.** Precio, volumen y cualquier magnitud en plata vienen en la moneda de cotización de cada especie. La segmentación ya garantiza que los rendimientos no crucen naturalezas de tasa; para las magnitudes en plata hay que llevarlas a una moneda común. El tipo de cambio se deriva del propio universo (la misma emisión cotiza en pesos y en dólares, y ese cociente es el MEP), nunca de una fuente externa.

10. **No se filtra por disponibilidad en Balanz.** Pedido explícito: se da por sentado que todo lo negociable está en Balanz. No reintroducir esa whitelist.

11. **10-Swaper NO se conecta al monitor de mesa** (`mesaifa.netlify.app`) ni a su base de datos, en ninguna forma. Pedido explícito del usuario. El monitor se compartió solo para evaluar qué ideas de análisis servían; `data912.com` es una API pública de terceros y sí se puede usar.

## Datos: de dónde sale cada cosa

> ⚠ **Esta sección es histórica.** Los dos CSV que menciona se borraron el 05/08/2026 y sus
> datos viven ahora en `data/condiciones_emision.csv`. Las fuentes del producto son BYMA,
> IAMC y Docta (sólo cashflow) — ver `README.md`. Se conserva el relato porque explica de
> dónde salió cada dato y por qué la cobertura es la que es.

**Exports de ONs del monitor de mesa** → `data/condiciones_monitor.csv` (**526 tickers**, era el archivo vivo): ley, moneda de pago, calificación y lámina mínima. Se incorporan con `tools/merge_condiciones.py --origen data/condiciones_monitor.csv`. Es una **extracción manual puntual**, no una conexión: la herramienta nunca consulta el monitor en tiempo de ejecución.

Para volver a ampliarlo hay que bajar del monitor los **tres** Excels, uno por especie (pesos, MEP y Cable): 216 D + 215 O + 95 C. Con uno solo hay que adivinar los tickers de las otras especies, y adivinar sale mal (ver más arriba). Los tres `.xlsx` originales se borraron el 30/07/2026 una vez verificado que sus 526 tickers estaban íntegros en el CSV: son fuente descartable, el CSV es el que importa.

**data912.com** (API publica de terceros, sin token, `tools/mercado.py`): puntas bid/ask. Es la unica fuente de spread; no aporta precios (ver más abajo). Sin relación con el monitor de mesa, al que el proyecto no se conecta.

**API de Docta** (`.env`, 3 links tokenizados generados en Docta Terminal → "Generar Link"):
- `/api/series` — precio y volumen
- `/api/yield-bonds` — TIR, TNA, duration, paridad
- `/api/cash-flow` — cupones (columnas necesarias: `ticker`, `payment_date`, `capital`, `interest_rate`, `interest_amount`, `residual_value`, `cash_flow`)

**Lo que la API NO expone** → `data/condiciones_estaticas.csv` (272 tickers, mantenido a mano):
`ticker, ley, moneda_pago, underlying, sector`

### Trampas conocidas de la API

- **`lastPrice` viene en monedas mezcladas.** La misma emisión cotiza en pesos sin sufijo y en dólares con sufijo D/C (AE38 = 127.360 pesos; PNDCD = 43,77 dólares). **Nunca dividir un monto por ese precio.** Se normaliza contra paridad × valor técnico, que es adimensional.
- **El cashflow indexa una sola especie por emisión** (RUCEO, no RUCED/RUCEC) → cruzar por raíz del ticker. Cobertura 97%.
- **HTTP 500 "Error al verificar el token" = token vencido** (401 sería inexistente). Los 3 links comparten token: regenerar uno y actualizar `.env` sirve para los tres.
- **La API devuelve 0 filas de forma errática**, sin regla de fechas. La misma consulta que responde vacía trae datos segundos después. Por eso: 5 reintentos con espera creciente.
- **El link de series trae `fromDate` hardcodeado** del día en que se generó → el script lo reescribe a una ventana móvil de 15 días. Sin eso el pipeline se rompía en silencio al envejecer el link.

## Estado de cobertura de datos

| Dato | Cobertura | Nota |
|---|---|---|
| TIR / duration | 618 / 927 | El resto no cotiza |
| Sector (dato crudo) | 423 / 927 (46%) | Lo que está cargado a mano en `condiciones_estaticas.csv` |
| Sector (efectivo) | 903 / 927 (97%) | Lo que las herramientas usan: el crudo **propagado por grupo de emisor** (mismo prefijo de ticker = mismo emisor = mismo sector). No inventa: extiende un dato cargado |
| Frecuencia de cupón | 783 / 927 (84%) | Derivada del cashflow; mensual/bimestral/trimestral/semestral/anual/al vencimiento |
| Ley (dato crudo) | 554 / 927 (60%) | `condiciones_estaticas.csv`. **Solo dos valores válidos**: Ley Argentina y Ley N.Y. |
| Ley (efectiva) | 691 / 927 (75%) | El crudo **heredado entre especies de la misma emisión** (AL30 tiene ley ⇒ AL30D y AL30C también: es el mismo bono). Lo hace el consolidador; si dos especies declaran valores distintos no elige — alerta |
| Moneda de pago | 686 / 927 (74%) | Dónde paga el bono (MEP/CCL). Atributo de la EMISIÓN ⇒ también se hereda entre especies |
| Lámina mínima | 568 / 927 (61%) | De los exports de ONs del monitor + herencia entre especies |
| Calificación | 359 / 927 (39%) | De los exports de ONs del monitor + herencia entre especies |
| Cashflow | 97% de las emisiones | — |

## Sanidad del dato

Al abrir la segmentación aparecieron rendimientos imposibles que antes quedaban tapados. Se resuelven en `segmentos.marcar_datos_sanos()` con dos capas, y **no es criterio económico: es integridad**. El tope anti-distress que controla el usuario opera dentro del rango de lo posible; esto descarta lo que directamente no puede ser cierto.

1. **Coherencia entre especies del mismo bono.** Un bono tiene una TIR, y sus especies O/D/C tienen que declararla igual (MR46D 13,08% vs MR46O 13,10%). Cuando una se despega por más de 100 pp, esa especie tiene el precio mal escalado. Descarta MGCEC, MGCED, MR43D, SNEAD, VSCQD. El umbral es de 100 pp y no menos porque hay discordancias legítimas: DICPD rinde 51 pp más que DICP y son datos válidos.
2. **Techo de lo posible por segmento**, en la unidad de cada uno: hard-dollar y dólar-linked 300%, CER 100% de tasa real, tasa fija / Badlar / Tamar 500% de TNA. Descarta CRCJO (134.731%).

**No todo rendimiento absurdo es dato roto.** SNSBO rinde 245% en dólares y es correcto: bono a 80 días cotizando al 78% de su valor técnico, donde la TIR anualizada explota por el plazo corto. Sus dos especies coinciden (245,5% y 212,8%), que es justamente lo que confirma que el dato es bueno. Por eso los topes son holgados: un umbral ajustado lo mataría junto con la basura.

Total descartado hoy: 6 instrumentos, todos con alerta explícita.

## Pendientes

1. **Cobertura de spread bid/ask**: hoy 674 de 927 instrumentos. Los que faltan no tienen dos puntas vivas, así que su costo de rotar sale como piso.
2. **Ampliar `condiciones_estaticas.csv`** — 236 instrumentos sin ley/moneda de pago (eran 373; la herencia entre especies recuperó 137 sin fuente nueva). Los que quedan no tienen el dato en NINGUNA especie (ej.: BA37/BB37 y sus especies). Camino: re-exportar los 3 Excels del monitor cuando crezca.
3. **6 tickers sin sector**: CY2BP (ON sin emisor informado), OZC8O, TLCKO, TVPA, TVPP, TVPY (5 no están en el universo).

## Limitaciones declaradas

- **Calificación crediticia parcial** (359/927) — no viene de la API; se carga desde el export de ONs del monitor. Se muestra y, cuando un swap cambia de emisor y las dos puntas la tienen, el salto de rating sale explícito en la nota de riesgo. **No se usa como filtro**: el análisis crediticio sigue siendo del usuario. Donde falta, la herramienta usa proxies: tope de rendimiento, percentil de liquidez y concentración máxima.
- **Lámina mínima parcial** (568/927) — se muestra como columna en ambos pilares, pero **los montos NO están ajustados a lámina**: hay que verificar al operar que la posición sea múltiplo. No se convierte automáticamente porque el monto del armador no tiene moneda unívoca y la conversión a nominales requiere el precio en la moneda de inversión.
- **Bonos ajustables** (CER, dólar linked, Badlar, Tamar): el calendario proyecta con el coeficiente de ajuste de hoy; el nominal futuro va a diferir.
- **Cobertura de inflación**: el universo CER argentino es casi íntegramente soberano → esa cartera siempre supera el tope soberano. Sale con alerta explícita, no es un bug.

## Mapa de archivos

```
tools/
  consolidar_universo.py   ingesta API → universo + cashflow  (SE REESCRIBE — no correr)
  segmentos.py             segmentacion, carga del universo, sanidad del dato,
                           normalizacion de volumen (COMPARTIDO por los 2 pilares)
  armar_cartera.py         pilar 1
  detectar_swaps.py        pilar 2
  cupones.py               calendario de cobros, frecuencia, repricing (compartido)
  mercado.py               puntas bid/ask -> costo real de rotar
  merge_condiciones.py     herencia entre especies y deteccion de conflictos
  aplicar_sectores.py      reclasificacion de sectores por emisor

workflows/                 SOPs operativos de cada herramienta
docs/historial/2026-07-diseno-wat/
  01-process-map.md  02-scorecard.md  03-disenio-tobe.md
  04-spec.md  05-spec-motor-swaps.md  06-spec-armador-cartera.md

data/
  condiciones_emision.csv   ley/moneda/lamina/calificacion/sector/emisor — 823 tickers,
                            rescatado del universo; sin fuente de origen viva
  output/                   universo y cashflow (versionados) + lo generado (regenerable)
.env                        token + links de Docta (gitignored)
```

**`merge_condiciones.py` y `aplicar_sectores.py` están rotos hoy**: apuntan a
`condiciones_estaticas.csv`, que ya no existe. Se conservan porque su lógica —herencia entre
especies, y vaciar lo contradictorio en vez de elegir fuente— se traslada a las operaciones
sobre la tabla `condiciones_emision` de Supabase.

## Verificación hecha

- 15 casos de regresión sobre el armador (3 perfiles × horizontes × monedas × coberturas + topes forzados) y el swaper: todos OK.
- La fórmula de nominales reproduce **exacto** los 4 casos del Excel real del usuario (RUCED, SBC2D, CS47D, LOC5D).
- RUCEO da 7,28% de renta a 12 meses contra cupón nominal de 7,5% — menor porque cotiza sobre la par, que es lo correcto.
- El swaper reproduce swaps reales de la mesa (TLCWO→TLCMO).
- Ambas herramientas degradan bien sin `cashflow_completo.csv`: siguen produciendo resultado y avisan qué falta.

### Validaciones contra fuentes externas (segunda sesión)

El monitor de mesa del usuario (`mesaifa.netlify.app`) sirvió como banco de pruebas independiente. **No estamos conectados a él** — se usaron sus números publicados para verificar los nuestros:

- **Repricing de sensibilidad**: reproduce su tabla de sensibilidad con desvío máximo de 0,12 pp sobre movimientos de hasta +91% (AL30, AL29, GD30, AE38, AL41, GD46 × 3 escenarios cada uno).
- **Tipo de cambio implícito**: nuestro cálculo derivado del universo da 1.530,90; el monitor muestra MEP $1.533. Diferencia 0,14%.
- **Premio por legislación**: AL30/GD30 nos da 122 bps (monitor 138), AE38/GD38 78 (86), AL35/GD35 52 (55), AL41/GD41 28 (30). Las diferencias son por precios de distinto momento del día.

### Regresión de la segunda sesión

- El refactor de segmentación se verificó en dos pasos: primero mover el código sin cambiar comportamiento (**15/15 carteras idénticas hoja por hoja**, incluida la hoja de Alertas), y recién después aplicar los cambios de fondo.
- Los cambios en las carteras tras arreglar el volumen están acotados y son explicables: la cantidad de posiciones no cambia en ningún caso, se sustituyen 1-2 por cartera, y las posiciones que liquidan en dólares pasan de 9 a 27 sobre los 15 casos — exactamente el sesgo que el bug producía.
- El swaper: TLCWO→TLCMO sigue saliendo con los mismos flags; aparecen 47 propuestas Tamar y 1 Badlar donde antes había cero; dos corridas consecutivas dan resultados idénticos.

### Qué declara BYMA y qué inferimos nosotros (08/08/2026)

Revisar el monitor en pantalla destapó que estábamos presentando una inferencia como si fuera dato:
`denominationCcy` toma tres valores y BYMA sólo documenta dos. `EXT` no es ISO 4217 y la fuente no
publica qué denota; lo que nosotros habíamos medido —su cociente contra la hermana en pesos da
≈1576 contra ≈1521 de la `USD`— sugiere el cable, pero estaba escrito en el código en modo
indicativo, como si lo hubiera dicho la fuente.

De ahí salió la **regla 11** de `CLAUDE.md`: no se supone ni se infiere nada en la representación de
datos; un código propietario de la fuente no se traduce; si no sabemos interpretarlo, el espacio va
en blanco y el faltante se declara.

El detalle completo —incluido el trío X/Y/Z, que son 419 de los 535 "sin segmento", y la pregunta
abierta sobre si estamos mezclando plazos de liquidación— está en
`docs/historial/2026-08-08-lo-que-byma-declara-y-lo-que-inferimos.md`.

Sacar la inferencia **no costó cobertura**: el tipo de cambio implícito conserva sus 462 pares y
sigue dando 1.521,53, porque cero emisiones tienen su único par por `EXT`. Lo que sí cambió es que
el volumen de 214 especies de renta fija y 341 de renta variable dejó de convertirse a dólares, y
que 63 de las 276 especies hard-dollar calculables dejaron de tener TIR propia. En pantalla el hueco
se resolvió **repartiendo en vez de rellenando**: el monitor elige una moneda por vez, y con una
sola moneda a la vista el volumen se muestra crudo sin convertir nada.

En la misma revisión se encontró que la ley y el emisor de la tabla curada no llegaban a ninguna
pantalla: la vista `resumen` los lee de `instrumentos`, donde IAMC sólo cargó lo que publica.
Cruzarlos subió la ley de 592 a 724 y el emisor de 720 a 823 sobre las 942 especies segmentadas.
Cuatro emisiones (PLC4, PN38, RC1C, YM39) tienen ley contradictoria entre las dos fuentes: **quedan
vacías y alertadas**, porque elegir ganador sin ir al prospecto sería inventar el eje de riesgo más
caro de equivocar.

## 08/08/2026 — Tanda 9: el armador dice cuánto cobra, qué concentra y qué no es renta fija

Cuatro features en paralelo (F-020 concentración, F-021 panel de renta, F-026 bloque de renta
variable, F-053 ficha del activo con Yahoo). 911 tests en el backend y 337 en el frontend; van 30
de 45 features de Stage 1.

**Antes de eso hubo que arreglar la rueda.** `en_ventana_de_rueda` sólo miraba la hora, así que un
sábado a las 14:00 pasaba el chequeo igual que un martes — y una corrida disparada a mano ese
sábado escribió 466 filas **sin un solo precio ni una sola TIR**, dejando el indicador de frescura
declarando el sábado sobre datos del miércoles. Las filas se borraron por su `capturado_en` exacto.
El scheduler habría repetido eso solo todos los fines de semana apenas se habilitara: `proxima_matinal`
y `proximo_refresh` desde el viernes también devolvían el sábado. Las tres funciones saltean ahora
al próximo día hábil, y `/consolidar` fuera de rueda exige `forzar=true`.

**Los feriados bursátiles no se modelan, y está escrito en el código.** No hay fuente programática
confiable del calendario de BYMA, y hardcodear una lista sería exactamente lo que la regla 1
prohíbe: un dato inventado que además se desactualiza en silencio. Un feriado entre semana sigue
produciendo una respuesta parcial, y ese caso pide un guardia de "la respuesta vino anormalmente
chica" que **queda anotado y sin construir**.

**La divergencia deliberada de F-020 contra el motor, medida de frente.** El motor propaga el sector
por moda dentro del grupo de emisor —prefijo de 3 letras del ticker— y así le asigna sector a 487
especies que la fuente no informa. El backend no lo hace. Medido sobre el universo real: de 1.509
especies de renta fija, 780 tienen sector, y **cero de las 729 restantes se recuperan por emisor
curado**; la única vía sería el prefijo, que es inferir del ticker. El prefijo resulta empíricamente
limpio (159 grupos con sector, **cero con sector contradictorio**), pero "no observamos
contradicciones entre los que conocemos" es la misma forma de evidencia que ya costó revertir 121
tickers. El costo es real —el tope sectorial mide sobre poco más de la mitad del universo— y **está
declarado en pantalla**: el panel dice qué porcentaje de la cartera no informa sector y no cuenta
para el mínimo. **El arreglo de verdad no es inferirlo: es curar `condiciones_emision`.**

**F-053 trae dato de Yahoo Finance, con dos límites escritos en el código.** No se muestran
recomendación de analistas, precio objetivo ni consenso: es opinión de terceros y la regla 6 mantiene
el análisis determinístico. Y la exclusión se hizo **no pidiendo el módulo** `financialData` en vez
de filtrarle campos, porque Yahoo mezcla ahí los márgenes y el ROE —dato duro— con el precio
objetivo; pedirlo y descartar después deja el juicio ajeno adentro del proceso aunque no se muestre.
Verificado en vivo que `MSFT.BA` en Yahoo **es el CEDEAR** y su perfil es el de la empresa
subyacente, así que la consulta es siempre `TICKER.BA` con el ticker que ya tenemos: no se deriva ni
se mapea nada. La respuesta se acepta sólo si declara bolsa `BUE` y el símbolo pedido.

Los endpoints de Yahoo **no son contractuales** —el de perfil exige un cookie+crumb no documentado
que Yahoo ya endureció una vez— y el diseño degrada: si la fuente externa falla, la ficha muestra lo
de BYMA y lo declara. Ninguna pantalla nuestra depende de que Yahoo esté vivo.
