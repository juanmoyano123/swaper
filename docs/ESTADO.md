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
> 2. **Las fuentes cambian**, y desde entonces cambiaron otra vez. Hoy (26/08/2026) son cinco:
>    data912 para el precio, BYMA para el universo y como precio de respaldo, SEC EDGAR para la
>    clasificación de renta variable, CNV para prospectos, y CAFCI para fondos. Docta se dio de
>    baja el 12/08 e IAMC se eliminó el 26/08; el cronograma de pagos quedó sin fuente viva y su
>    conjunto está cerrado. Ver la entrada del 26/08/2026 al final.
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

## 08/08/2026 — El scheduler queda prendido, y por qué recién ahora

Una pregunta del usuario destapó el agujero: la curva soberana entera mostraba `s/d` en TIR,
duración y paridad, incluidos AL30D y GD30D, que operan todos los días.

**No fallaba el cálculo: fallaba la frescura.** El último snapshot era del miércoles 06/08 19:24 y
F-051 —la feature que calcula las métricas propias— se mergeó el jueves 07/08 17:37. Ninguna
consolidación corrió entre medio, así que en la base había **cero métricas propias**: las 240 TIR
visibles venían todas de IAMC (`fuente = byma+iamc`), que sólo publica ONs. De ahí que los 112
soberanos tuvieran 107 precios y ni una sola TIR.

Verificado contra el motor real, con el cronograma que la base ya tenía: **AL30D a 56,53 da TIR
7,5181 %, duración 1,93 y paridad 88,28 %**. El cálculo andaba; el dato no estaba escrito.

Medido cuánto se llena en la próxima corrida, aplicando en SQL las mismas tres condiciones que
`fuente_de_metricas` evalúa: **221 especies calculables con la celda hoy vacía**. El resto queda
vacío por razones que ya están decididas — 498 por moneda cruzada (regla 3), 169 por naturaleza
fuera del cálculo (CER, dollar-linked, badlar, tamar), 54 porque no operaron ese día, y 535 sin
tipo de tasa, de las cuales **sólo 18 tienen precio**: el hueco real es mucho más chico de lo que
el número grande sugiere.

**La lección no es el snapshot viejo, es que no se veía.** Una feature de métricas estuvo mergeada
24 horas, con 911 tests en verde, y la pantalla siguió mostrando lo de antes sin nada que dijera
"estás viendo una corrida anterior a este cálculo". La barra de estado declara la fecha del
snapshot, pero no que el motor cambió después. **Una corrida vieja no se distingue en pantalla de
una corrida sin resultado.** Queda anotado como pendiente de diseño.

**Por qué se prende ahora y no antes.** `ingesta_habilitada` estaba en `False` desde F-008. Encender
el scheduler antes del guardia de día hábil habría reproducido el snapshot degradado del sábado
—466 filas sin un solo precio— **todos los fines de semana, solo**. Con el guardia puesto el 08/08,
encenderlo es seguro: verificado que un sábado a las 17:00 `en_ventana_de_rueda` da `False` y tanto
`proxima_matinal` como `proximo_refresh` saltan al lunes 10/08.

**Se prende por `.env` (`INGESTA_HABILITADA=true`) y no cambiando el default de `Settings`**, que
sigue en `False` a propósito: si el default fuera `True`, cada corrida de pytest y cada `uvicorn
--reload` local arrancaría un job de fondo escribiendo en la base.

Contraste empírico del día, que es lo que justificó no forzar la corrida el sábado: BYMA devolvió
**4 filas, todas con precio 0** contra las ~2.900 de un día hábil.

### Pendiente que abre esto: retención de snapshots

Medido el 08/08: 4 snapshots pesan 1776 kB, o sea **~444 kB cada uno**. Con refresh cada 15 minutos
de 11:00 a 17:00 son ~25 snapshots por día hábil, ~11 MB diarios. **Hay que decidir una política de
retención antes de que la base se llene**; hoy no existe ninguna y nada borra un snapshot viejo.

> **Resuelto el 10/08/2026** — ver "La serie histórica se apaga" más abajo. La decisión fue no
> guardar serie: queda una fila por ticker.

## 08/08/2026 — data912 pasa a ser la fuente primaria de precios, BYMA de respaldo

El mismo día del punto anterior, mirando la pantalla en vivo, el usuario preguntó por qué el
monitor mostraba `s/d` masivo con el mercado cerrado en vez del último precio operado. La causa no
era la frescura de arriba: **BYMA sólo publica lo que operó ese día**, y la vista `resumen` toma la
fila más nueva por ticker — un papel que no operó ayer queda vacío hoy, aunque haya cotizado el
viernes. Es un problema de memoria, no de fecha.

`data912.com` —la misma API pública que usa el monitor de mesa (su API, no su base; la regla 10
sigue intacta)— arrastra el último cierre conocido de cada especie aunque no haya operado. Medido
en vivo un sábado: devuelve las 827 especies de renta fija con precio, contra las 609 que BYMA
tenía frescas de la última rueda.

**Se probó en una rama aparte (`experimento/data912`) antes de tocar `develop`**, con la condición
explícita del usuario: "si me convence lo mergeamos, si no la borramos". Diseño: `data912` primero
por ticker, **BYMA de respaldo** — nadie desaparece de la pantalla, porque data912 solo cubre datos
de renta fija y variable en Argentina y no todo lo que BYMA publica (AEC2D, por ejemplo, no existe
en ninguna de sus cinco tramos). Cada precio queda rotulado con su procedencia real en la columna
`fuente`, ahora expuesta en la vista `resumen`: `data912` (operó en la sesión), `data912-arrastre`
(precio de una sesión anterior, de fecha que la fuente no declara — regla 11, se rotula y no se
oculta) o `byma` (respaldo), compuesto con `+calculo`/`+iamc` como ya hacía la columna. La moneda de
cotización **nunca sale de data912** —no la declara— sino de la que BYMA ya persistió para ese
ticker alguna vez; sin eso, un ticker nuevo-para-data912 quedaría sin poder calcular nada.

**Validado con una corrida forzada real contra la base**, no sólo con tests: la renta fija con
precio subió de 609 a 790 (41 % → 52 %) y con TIR calculada de 240 a 494 — más del doble, y de esas,
435 son precios arrastrados que antes eran `s/d` puro. De paso la corrida detectó que **el token de
Docta está vencido**, sin relación con este cambio — quedó registrado en el snapshot de esa corrida.

Revisión visual del usuario en desarrollo, aprobada. Mergeado a `develop` con 954 tests backend /
337 frontend en verde, `ruff` y `tsc` limpios.

**Pendiente que este cambio no resuelve:** el rollback de la vista `resumen` (por si hiciera falta
revertir la migración a mano) hereda el límite de `CREATE OR REPLACE VIEW` de no poder quitar una
columna del medio — está documentado en el propio archivo del rollback. Y la barra de estado ahora
declara la demora de BYMA como peor caso conocido, porque data912 no publica la suya; sigue sin
haber una demora **por fila** cuando un precio viene arrastrado de una fecha desconocida.

## 10/08/2026 — La serie histórica se apaga: la base deja de crecer sola

Con el scheduler prendido desde el 08/08, la pregunta del usuario fue por qué la base sube todo el
tiempo. La respuesta es la que este documento ya había anotado como pendiente sin dueño: `precios` y
`puntas` tienen PK `(ticker, capturado_en)` y el INSERT es plano, así que **cada corrida agregaba una
tanda entera en vez de pisar la anterior**. Medido: ~2.900 filas cada 15 minutos, ~72.500 filas y
~11 MB por día hábil, creciendo para siempre.

**La decisión fue no guardar serie.** No es una optimización: es que nadie la usaba. La herramienta
sirve para armar carteras —consultar un precio, mirar la TIR, decidir si conviene comprar— y no para
hacer seguimiento; el usuario lo dijo con todas las letras. El único dato histórico que el producto
necesita es el precio al que se armó una cartera, y ese ya tiene su lugar desde la migración
inicial: `posiciones.precio_compra` y `posiciones.fecha_compra`.

Verificado antes de tocar nada: **nada en el sistema lee más de un snapshot**. La vista `resumen`
usa `LEFT JOIN LATERAL … ORDER BY capturado_en DESC LIMIT 1`, las dos lecturas de `puntas` hacen lo
mismo, `health.py` pide un `MAX`, y la variación diaria del monitor sale de la columna
`cierre_anterior` que trae BYMA —no de comparar snapshots—. La única serie temporal del producto es
la sparkline de la ficha de renta variable, que se alimenta de Yahoo en vivo.

### La trampa: la poda es POR TICKER, y esto no es negociable

`DELETE FROM precios WHERE capturado_en < (SELECT max(capturado_en) FROM precios)` parece la forma
obvia y **rompe el producto**. BYMA sólo publica lo que operó, así que una especie que no cotizó en
la última corrida tiene su fila más nueva días atrás. Medido sobre la base real ese día: de **3.176
tickers, 291 estaban en esa situación y 28 de ellos con precio**. Ese DELETE los dejaría sin ninguna
fila y, como `resumen` los toma con LEFT JOIN LATERAL, saldrían publicados con precio, TIR, paridad
y volumen en NULL.

La forma correcta —`sql_poda()` en `app/ingesta/consolidacion/persistencia.py`— correlaciona por
ticker: `WHERE p.capturado_en < (SELECT max(q.capturado_en) FROM … q WHERE q.ticker = p.ticker)`.
Hay un test que lo fija (`test_la_poda_se_correlaciona_por_ticker_y_no_contra_el_maximo_global`)
justamente para que nadie lo "simplifique" después.

Otras dos propiedades del bloque de poda, ambas testeadas: **va después de escribir** (podar primero
dejaría a la base sin foto si la corrida fallara a mitad de camino) y **en su propia transacción**
(un fallo borrando no puede tirar abajo una escritura que salió bien; se reporta como advertencia).

### El flag, y qué NO es

`SERIE_HISTORICA_HABILITADA`, default `False`. En `True` vuelve el comportamiento anterior bit por
bit: el código de la serie quedó implementado y testeado a pedido del usuario, porque a futuro puede
servir.

**No confundir con `INGESTA_HABILITADA`.** Los precios se siguen actualizando cada 15 minutos; lo
que se apaga es la acumulación, no la ingesta. Apagar la otra variable dejaría el universo congelado.

### Resultado medido

| | Antes | Después |
|---|---|---|
| Filas en `precios` | 33.882 (12 snapshots) | 3.176 (una por ticker) |
| Filas en `puntas` | 39.520 (13 snapshots) | 3.683 |
| Tamaño de las dos tablas | 6.176 kB + 6.152 kB | 504 kB + 480 kB |
| Base entera | 25 MB | 17 MB |
| Crecimiento diario | ~11 MB | ~0 |

Los `DELETE` los ejecutó la propia corrida siguiente, no una limpieza a mano: el backend corría con
`--reload`, tomó el código nuevo y podó solo. El espacio se recuperó con `VACUUM FULL` sobre las dos
tablas —un `VACUUM` normal libera las filas para reuso pero no devuelve el archivo al sistema—.

Control post-borrado: los tickers que conservan cotización vieja (AXIA y BF47O del 08/08, BU3S6 y
D10Y7 del 10/08 a las 14:30, entre otros) **siguen publicando su precio en `resumen`**, y el
monitor mantiene los mismos 1.324 precios y 428 TIR que antes de podar.

## 23/08/2026 — Yahoo Finance sale del proyecto

Decisión del dueño del producto: *"yahoo quiero sacarlo del proyecto, no pude hacerlo funcionar. No
quiero tener nada de yahoo en el proyecto hasta nuevo aviso."* Se eliminó la huella entera —cliente,
variable de entorno, job de enriquecimiento, endpoint que lo disparaba, bloque `externo` de la ficha
de renta variable, y los esquemas y componentes del frontend que lo consumían—. Lo que queda escrito
de Yahoo en este documento y en `claude-docs/` es historia de cuándo y por qué se construyó, no
estado actual.

**El disparador es viejo y está medido.** `YAHOO_HABILITADO` estaba apagado desde el 08/08/2026 por
HTTP 429 sostenido sobre toda la conexión —verificado con `curl` puro, fuera de nuestro código, en
los tres endpoints, incluido el que entrega el crumb sin pedir credencial y sin `Retry-After`—. Es
decir: al momento de sacarlo era código muerto que no aportaba un solo dato.

**Qué se pierde, nombrado.** PER trailing y forward, precio sobre libros, beta, ganancia por acción,
valor empresa, capitalización, país, sector, industria, empleados y sitio web. Ninguno se sustituye
por otra fuente ni se estima: donde había un campo de Yahoo ahora no hay campo (regla 1).

**Qué no se pierde.** El nombre de la empresa, la actividad y el rubro salen de la SEC; apertura,
máximo, mínimo y VWAP de BYMA; el histórico de cierres de data912. La ficha de renta variable queda
con tres bloques —propio (BYMA), histórico (data912) y estados contables (SEC)—, cada uno rotulado
con su fuente.

**Lo que la diversificación sectorial de renta variable usa hoy es `sic_oficina` de la SEC**, no el
sector de Yahoo, y eso ya era así desde el 13/08/2026. Cuando ningún papel elegido tiene rubro
informado, el armado lo declara con la alerta `rv_sin_perfil_sectorial` en vez de sustituirlo.

**Columnas de base que quedaron huérfanas y NO se borraron:** en `public.perfil_renta_variable`,
`nombre_corto`, `sector`, `industria` y `pais` — sólo las escribía el job de Yahoo, hoy nada las
escribe y nada las lee. Están vacías en producción (la tabla nunca se pobló). Se dejan en su lugar
a propósito: las migraciones ya aplicadas no se tocan.

---

## 26/08/2026 — Relevamiento completo: se cierran los jobs, se programa la ingesta y se declara lo que no se calcula

Revisión de todo el proyecto pedida por el dueño del producto, con cuatro preguntas: qué está roto,
qué pasa con CORS, por qué no se calculan todas las TIR, y si las fuentes son las oficiales.

**Las fuentes son las que tienen que ser.** BYMA (universo, metadata, precio de respaldo), data912
(precio primario y el histórico on-demand), SEC EDGAR (clasificación sectorial, ficha de CEDEAR,
calendario de balances) y CNV (prospectos de ON, enlace a la cartera de FCI) están las cuatro
integradas y con tests. CAFCI se suma como quinta —ninguna de las otras cubre fondos— y quedó
prendida: la feature estaba cerrada desde el 23/08 pero `CAFCI_HABILITADO` nunca se había cargado,
así que el segmento FCI del monitor corría vacío.

### Los endpoints de ingesta estaban abiertos a internet

`POST /api/v1/jobs/*` y `POST /api/v1/consolidar` disparan corridas completas contra BYMA y escriben
en la base, y no pedían ninguna credencial: con la URL del deploy alcanzaba para forzar una ingesta.
Ahora pasan por `cron_o_asesor` (`backend/app/api/deps.py`), que acepta dos credenciales por el
mismo header `Authorization`: el secreto del cron o el JWT de un asesor logueado.

El secreto se compara primero y con `compare_digest`. Primero, porque probar el JWT antes mandaría
el `CRON_SECRET` a decodificar contra el JWKS de Supabase en cada tick, dejando un "token inválido"
periódico en el log, indistinguible de un intento real de entrar. Con `compare_digest`, porque `==`
corta en el primer byte distinto y ese tiempo desigual permite adivinar un secreto de a un carácter.

**`CRON_SECRET` es opcional y su ausencia cierra, no abre**: sin la variable esa rama ni se evalúa y
los endpoints sólo se abren con sesión de asesor. No hay default posible que no sea un secreto
conocido, y un deploy al que se le olvidó la variable tiene que quedar cerrado.

### La ingesta programada nunca había corrido

`corridas_ingesta` estaba vacía: todo el dato del sistema había entrado por corridas manuales, sin
traza de fuente ni fecha. El motivo es estructural: `Scheduler` vive en el `lifespan` del proceso
ASGI y una función serverless muere entre requests, así que en Vercel nunca arrancó (y de haber
arrancado, cada instancia habría corrido su propia copia).

Los crons de Vercel en plan Hobby corren **una vez por día y sin minuto exacto** (verificado contra
la cuenta: `billing.plan = hobby`), así que un refresh cada 20 minutos ni siquiera deploya. La
programación quedó en `.github/workflows/ingesta.yml`, que le pega por HTTP a dos endpoints GET
nuevos —`GET /api/v1/jobs/cron/{matinal,refresh}`— con el secreto compartido. GET y no POST porque
es lo único que hacen los disparadores de cron. Si el proyecto pasa a Pro, el bloque `crons` de
`vercel.json` reemplaza el workflow sin tocar el backend: los endpoints son los mismos.

Dos guardas nuevas, las dos respondiendo **200 y no 4xx**:

- **Fuera de la ventana de rueda** (11:00 a 17:00 ART, días hábiles) la corrida se omite con su
  motivo. El cron de GitHub es best-effort y puede disparar tarde; un cron que "falla" cada feriado
  y cada tick tardío enseña a ignorar el log, y una alerta que nadie mira no es una alerta.
- **Advisory lock de Postgres** (`pg_try_advisory_lock`) contra el solapamiento. Dos corridas
  simultáneas no se corrompían —`persistir` upsertea— pero intercalaban `capturado_en` y duplicaban
  filas de `corridas_ingesta`.

Verificado de punta a punta el 26/08: el workflow autentica, el backend acepta, y la respuesta
`{"omitida": true, "motivo": "fuera de la ventana de rueda"}` llega como aviso, no como fallo.

### Por qué no se calculaban todas las TIR

De las 816 emisiones con cronograma, 310 quedan fuera **por naturaleza de tasa** —CER, dollar-linked,
badlar y tamar— y eso es correcto y está documentado: sus flujos no alcanzan para la unidad que el
segmento reporta. Lo que sí eran defectos:

**El segmento de tasa fija calculaba su TIR y la tiraba.** `rendimiento_declarado` devolvía `tna`
para ese segmento, y `tna` no tiene fuente en ningún lado del sistema: se escribe `None` siempre. La
TIR se resolvía, se persistía en `precios.tir`, y la pantalla mostraba `s/d` porque el frontend sólo
lee `rendimiento`. Ahora ese segmento declara su TIR bajo **naturaleza propia `tir_ea_ars`** — no la
`tna_nominal_ars` que compartía con badlar y tamar. La naturaleza separada no es cosmética: bajo la
vieja, el número habría quedado promediable con TNAs y rotulado "TNA $" en todo el frontend, que es
exactamente lo que la regla 2 prohíbe. Badlar y tamar siguen en `tna_nominal_ars`, sin número y
declarado: su TNA sigue sin fuente y una TIR no la reemplaza.

Medido contra la base el 26/08: el segmento pasó de 0 a 8 rendimientos declarados sobre 25 especies
(las 17 restantes no tienen precio del día). El total del universo pasó de 212 a 220.

**Las especies sin `tipo_tasa` desaparecían sin motivo ni alerta.** `fuente_de_metricas` tenía un
tercer destino, `FUENTE_IAMC`, adonde caían las especies sin tipo de tasa y las de naturaleza sin
regla declarada. Mientras IAMC publicaba por ellas era razonable; con IAMC pausado desde el 13/08
pasó a ser un faltante silencioso —el `armado.py` las devolvía `None` **sin anotar motivo**—, que es
justo lo que la regla 1 prohíbe. Hoy hay dos destinos y nada más: se calcula, o queda fuera con su
porqué. Una naturaleza sin regla cae en `naturaleza_desconocida` y entra a la alerta con nombre y
apellido.

**El techo del solver cortaba rendimientos reales.** `TASA_TECHO` estaba en 10.0 (1000 % efectivo
anual): un bono a 20 días al 60 % de paridad anualiza por encima y salía `tir_sobre_techo`, sin
número, cuando el dato es aritmética válida —el antecedente es SNSBO rindiendo 245 %, dato correcto—.
Pasó a 100.0. Quién decide si un rendimiento es creíble es la sanidad por segmento, que rotula y
deja el número a la vista; el solver, que lo vacía, no puede ser ese filtro.

**Motivos mal rotulados y un contador inflado.** `precio <= 0` y "residual contradictorio" se
reportaban los dos como `vencida` —un bono vivo con precio 0 no está vencido, y un residual que no
cierra es un problema del dato, no del calendario—. Y `ResultadoMetricas.calculadas` sumaba
incondicionalmente, así que el número que se reportaba como "cuántas se calcularon" incluía las que
habían fallado.

**Un pago perdido en el CSV del cronograma.** `data/output/cashflow_completo.csv` traía en la fila
de CO26 del 29/01/2024 un `_x000d_` —el retorno de carro que Excel escribe codificado— pegado al
campo `capital`. `float()` fallaba, el pago se descartaba en silencio, y como el residual se deriva
de `100 - Σ capital` de los pagos cobrados, CO26 quedaba con un residual de 6,25 contra el 3,125 que
declara la fuente: fuera de tolerancia, descartado por `residual_contradictorio`, sin métricas.

El valor se restauró, y **no por analogía con las otras filas**: la propia fila lo confirma
aritméticamente (`capital + interés = cash_flow`, 3,125 + 0,66797 = 3,79297 exacto) y la tabla
`public.cashflow` lo tiene sano. Con la fila reparada el residual derivado vuelve a dar 3,125, igual
al declarado. Es una reparación de codificación, no una imputación. El archivo se respaldó antes y
el diff es de una sola fila.

### CORS

El default de `cors_origins` apuntaba sólo a `swappt.netlify.app`, el deploy anterior. **No estaba
rompiendo nada**: en Vercel los rewrites de `vercel.json` sirven frontend y backend bajo el mismo
host, así que las llamadas son same-origin y el middleware ni se ejercita. Pero era el default
equivocado para el día que el backend se mude, que es el único escenario donde este middleware
existe. Ahora incluye el dominio de Vercel, y **se conserva el de Netlify**: ese deploy sigue vivo
(responde 200), contra lo que decía el relevamiento inicial.

Dos ajustes más en el middleware: se expone `X-Request-ID` —el backend lo emite y el cliente lo lee
para poder nombrar un error al reportarlo; sin exponerlo, en cross-origin vuelve `null` en silencio—
y sale `allow_credentials`, que sobraba: la sesión viaja en el header `Authorization`, no en cookie.

### IAMC se elimina del código

Estaba pausado desde el 13/08 y su única función viva era tapar el agujero de `FUENTE_IAMC`. Se
borró el paquete entero, su endpoint de subida y su flag. **Se eliminó código, no dato**: la ley, la
moneda de pago, el emisor y la estructura de cupón que IAMC escribió siguen en la base, protegidos
por el `COALESCE` del upsert, porque son atributos de la emisión que no envejecen. `convexidad` y
`fecha_metricas` quedan como columnas declaradas y vacías —era lo que ya pasaba con la pausa activa—.
Las menciones a IAMC que quedan en docstrings explican de dónde vino un dato persistido, y se
conservan a propósito (regla 11).

### Correcciones al registro previo

- **`perfil_renta_variable` no está vacía**: tiene 1641 papeles de SEC EDGAR, 870 con clasificación
  SIC. El pendiente registrado el 23/08 ("el job nunca corrió en producción") ya no aplica. Lo que
  sigue vacío es la columna `sector`, que era de Yahoo y hoy nadie escribe; la clasificación viva
  está en `sic_codigo` / `sic_titulo` / `division_cadena`.
- **`.env.example` declaraba 15 minutos de refresh**; el valor real es 20 desde el 23/08. Se
  corrigió, y se agregaron `INGESTA_HABILITADA`, `CAFCI_HABILITADO`, `CNV_HABILITADO` y
  `CRON_SECRET`, que el backend leía sin que el ejemplo las nombrara.
- Se sacaron del `.env` las cuatro variables `DOCTA_*`, residuo de una fuente dada de baja el 12/08.
- Un test nuevo (`backend/tests/test_dependencias_declaradas.py`) impide que `pyproject.toml` y
  `requirements.txt` declaren versiones distintas: ese desfasaje tumbó el deploy del 26/08 y nada lo
  verificaba.
