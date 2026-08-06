# Esquema de datos y contrato de persistencia

Creado en F-002 (2026-08-06). Define el modelo de datos en PostgreSQL/Supabase y, sobre todo, la
**correspondencia con el contrato de salida del motor Python**: la hoja `Resumen` de
`universo_consolidado.xlsx` y `cashflow_completo.csv`.

Esa correspondencia no es documentación decorativa. El proyecto reusa cerca del 85 % del motor sin
tocarlo, y ese reuso depende de que las columnas sigan llamándose igual y significando lo mismo. Si
alguien renombra una columna sin actualizar este documento, el que se rompe es el motor.

El esquema vive en `supabase/migrations/`. **Ninguna columna del contrato anterior se dio de baja.**

---

## Las tablas

**De mercado** — el universo es uno solo y es igual para todos los asesores:
`instrumentos`, `precios`, `puntas`, `cashflow`, `condiciones_emision`.

**De usuario** — con `user_id` obligatorio y Row Level Security:
`carteras`, `posiciones`, `propuestas`.

Más una vista, `resumen`, que reconstruye las 21 columnas del contrato del motor.

---

## Mapeo: hoja `Resumen` → esquema nuevo

Las 21 columnas de `COLUMNAS_RESUMEN` (`tools/consolidar_universo.py:100-105`). La vista
`public.resumen` las devuelve todas, en este orden y con estos nombres, así que un consumidor que
hoy lee el Excel puede leer la vista sin cambiar su lógica.

La partición es por naturaleza del dato: lo que identifica y clasifica a la especie va a
`instrumentos`; lo que cambia con cada rueda va a `precios`, que es una serie temporal.

| Columna del `Resumen` | Dónde vive ahora | Nota |
|---|---|---|
| `ticker` | `instrumentos.ticker` | clave de la especie |
| `clase_activo` | `instrumentos.clase_activo` | dominio cerrado por CHECK |
| `tipo_tasa` | `instrumentos.tipo_tasa` | vacío en acciones y CEDEARs: no tienen tasa |
| `subtipo` | `instrumentos.subtipo` | `global` / `bonar` |
| `underlying` | `instrumentos.underlying` | emisor |
| `sector` | `instrumentos.sector` | |
| `tir` | `precios.tir` | métrica del día |
| `tna` | `precios.tna` | métrica del día |
| `duration` | `precios.duration` | métrica del día |
| `maturity` | `instrumentos.maturity` | |
| `law` | `instrumentos.law` | **renombrada** desde `ley` en el CSV curado |
| `couponCurrency` | `instrumentos.coupon_currency` | **renombrada** desde `moneda_pago`; la vista la devuelve en camelCase |
| `lamina` | `instrumentos.lamina` | |
| `calificacion` | `instrumentos.calificacion` | |
| `paridad` | `precios.paridad` | métrica del día |
| `residualValue` | `precios.residual_value` | la vista la devuelve en camelCase |
| `lastPrice` | `precios.last_price` | la vista la devuelve en camelCase |
| `effectiveVolume` | `precios.effective_volume` | la vista la devuelve en camelCase |
| `revisar` | `instrumentos.revisar` | bandera de calidad |
| `duplicado` | `instrumentos.duplicado` | bandera de calidad |
| `archivo_origen` | `instrumentos.archivo_origen` | |

En la base los nombres son snake_case, que es la convención de PostgreSQL; el camelCase existe
únicamente en la vista, para no obligar al motor a cambiar.

### Columnas agregadas por F-007

Cuatro columnas que las fuentes declaran y que el `Resumen` no tenía. **No están en la vista**: el
contrato de 21 columnas se conserva intacto y quien las necesite consulta la tabla.

| Columna | Fuente | Por qué |
|---|---|---|
| `instrumentos.moneda_cotizacion` | BYMA (`denominationCcy`) | ARS/USD/EXT sin traducir. La regla "nada se compara entre monedas sin normalizar" se apoya acá. Distinta de `coupon_currency`, que es la moneda en que paga la emisión |
| `instrumentos.plazo_liquidacion` | BYMA (`settlementType`) | 1 o 2, sin mapear; es el plazo de la cotización que se guardó |
| `instrumentos.estructura_cupon` | IAMC | Tasa Fija, Cupon Cero, Tasa Variable, Step Up. Sin CHECK: es vocabulario de la fuente |
| `precios.convexidad` | IAMC | por ticker exacto, como la TIR y la duración |
| `precios.fecha_metricas` | IAMC | de qué informe salieron las métricas de esa fila |

El dominio de `instrumentos.coupon_currency` se amplió a `('MEP','CCL','USD','ARS')`. El CSV curado
distingue MEP de CCL —por dónde se cobra el dólar— y el informe de IAMC sólo declara USD o ARS.
Traducir USD a MEP sería elegir por la fuente: el informe no lo dice. Cada valor entra con la
granularidad que su fuente declaró y F-009 refina el grueso al fino.

### Bajas explícitas

**Ninguna columna del `Resumen` se dio de baja.** Las 21 tienen correspondencia.

Lo único que la base no guarda son dos cosas, y por la misma razón: son datos derivados, y guardar
un derivado es tener dos versiones de la misma verdad que se pueden contradecir.

- **`spread_pct`** — se calcula de `px_bid` y `px_ask` en `tools/mercado.py`. La base guarda las
  puntas; el spread se recalcula.
- **Todo lo que `tools/segmentos.py` deriva al cargar el universo**: `segmento`, `rendimiento`,
  `duration_aprox`, `moneda_cotizacion`, `fx_implicito`, `volumen_usd`, `grupo_emisor`, `emisor`,
  `clave_riesgo`, `raiz_emision`, `es_soberano`, `dato_sano`. Se calculan en memoria a partir de las
  columnas que sí están persistidas. En particular **`clave_riesgo`, con `SOBERANO_AR` como clave
  única del Tesoro, se sigue derivando en el motor**: no es una columna de la base.

Un dato que la fuente entrega y que el contrato actual no exporta: `accured_interest`
(`interesCorrido`). El consolidador lo lee pero no lo lleva al `Resumen`, así que queda fuera del
alcance de F-002. Si alguna feature lo necesita, se agrega a `precios` con una migración nueva.

---

## Mapeo: `cashflow_completo.csv` → `cashflow`

Las 9 columnas se replican con el mismo nombre y el mismo significado:
`ticker`, `type`, `issue_date`, `payment_date`, `capital`, `interest_rate`, `interest_amount`,
`residual_value`, `cash_flow`.

Dos cosas que hay que saber antes de consultar esta tabla:

- **Los montos son por 100 de valor nominal**, no por lámina ni por posición.
- **El cronograma indexa una sola especie por emisión** (RUCEO, no RUCED ni RUCEC). Para cruzar
  contra el universo hay que hacerlo **por raíz de ticker**, no por ticker. La cobertura es del 97 %
  de las emisiones.

La clave primaria es `(ticker, payment_date)`. Se verificó contra los 6111 pagos del archivo actual:
no hay un solo par repetido, porque la fuente consolida el capital y el interés del mismo día en una
única fila. Eso hace que la ingesta de F-007 pueda ser un upsert directo.

`type` es el submarket de la fuente y queda como texto libre, sin CHECK: la fuente agrega categorías
nuevas sin avisar, y un instrumento nuevo no debe hacer fallar la ingesta entera.

---

## Mapeo: `data/condiciones_emision.csv` → `condiciones_emision`

Las 7 columnas del CSV curado (823 tickers) conservan su nombre: `ticker`, `ley`, `moneda_pago`,
`lamina`, `calificacion`, `sector`, `underlying`. Los renombres a `law` y `couponCurrency` ocurren
más adelante, cuando el dato llega a `instrumentos`.

**Cada valor viaja con su origen y su fecha en la misma fila.** Los seis campos trazables tienen un
triplete: `ley` / `ley_origen` / `ley_fecha`, `lamina` / `lamina_origen` / `lamina_fecha`, y así.

La base lo exige por CHECK, un constraint por campo:

```sql
CONSTRAINT lamina_trazable CHECK (
    lamina IS NULL OR (lamina_origen IS NOT NULL AND lamina_fecha IS NOT NULL))
```

Un valor cargado sin decir de dónde salió es un dato sin respaldo. La base lo rechaza en vez de
confiar en que el que escribe se acuerde de completarlo.

La tabla **no tiene FK a `instrumentos`** a propósito: la semilla de F-009 trae tickers curados que
pueden existir antes de que la ingesta de mercado los vea, y perder una condición de emisión por eso
sería irrecuperable — el CSV se rescató después de que se borraran los archivos originales y no
tiene fuente viva.

La herencia entre especies (si AL30 tiene la ley, AL30D y AL30C la tienen) y la detección de
conflictos las implementa **F-009**. El esquema no las resuelve, pero tampoco las impide.

---

## Mapeo: puntas

| Fuente | Tabla |
|---|---|
| `ticker` | `puntas.ticker` |
| `px_bid` | `puntas.px_bid` |
| `px_ask` | `puntas.px_ask` |
| `operaciones` (`q_op`) | `puntas.operaciones` |
| `spread_pct` | *derivado, no se persiste* |

`puntas` **no tiene FK a `instrumentos`**, y es deliberado: la fuente publica tickers que no están
en nuestro universo, y descartarlos en la ingesta sería perder dato que mañana puede servir. El join
contra el universo lo hace el motor. No agregar la FK "para arreglarlo".

---

## Precedencia por campo (F-007)

Cada columna tiene **una sola fuente posible**, fijada en `backend/app/ingesta/consolidacion/`.
Ninguna se completa desde otra fuente, ni siquiera cuando la declarada falta.

| Columna | Fuente | Grano del dato |
|---|---|---|
| `moneda_cotizacion`, `plazo_liquidacion`, `maturity` | BYMA | la especie |
| `last_price`, `effective_volume`, `px_bid`, `px_ask` | BYMA | la especie |
| `law`, `coupon_currency`, `underlying`, `estructura_cupon` | IAMC | la emisión (raíz) |
| `tir`, `duration`, `paridad`, `convexidad`, `residual_value` | IAMC | el ticker exacto |
| `clase_activo`, `tipo_tasa` | Docta (`type`) | la emisión (raíz) |
| las 9 columnas de `cashflow` | Docta | el ticker exacto |
| `tna` | ninguna hoy | — |
| `lamina`, `calificacion`, `sector` de ONs | ninguna hasta F-009 | — |

**Dos granos para IAMC, y la diferencia es de fondo.** Ley y moneda de pago son atributos de la
emisión: AL30, AL30D y AL30C se pagan bajo la misma ley y por eso se heredan por raíz. La TIR no:
depende del precio de cada especie y de la moneda en que ese precio está. Escribir la TIR de AL30 en
AL30D sería inventar un número que nadie calculó.

**Una fila de `precios` tiene dos fechas.** `capturado_en` fecha el precio y el volumen, que salen de
la rueda de BYMA; `fecha_metricas` fecha la TIR, la duración, la paridad, la convexidad y el valor
residual, que salen del informe diario de IAMC. Cuando una corrida no tiene informe a mano se
conservan las últimas métricas conocidas **con la fecha de su informe**: sin ese rótulo sería
presentar el dato de un día como el de otro, y con él la fila dice exactamente qué muestra. Sin esto
el universo se vaciaba solo, porque la vista `resumen` arma cada fila con la fila de precios más
reciente y un refresco sin IAMC dejaba la TIR nula para todo el universo.

**Qué queda afuera del universo.** Una especie de `public-bonds` sin cronograma en Docta no entra a
`instrumentos`: `clase_activo` es NOT NULL y BYMA no distingue un bono del Tesoro de uno provincial
(`securitySubType` vale `'B'` en las 1106 filas). Son ~450 especies, casi todas las X/Y/Z que BYMA
publica como segundo trío de cada soberano y que el consolidado histórico nunca tuvo. **Sus puntas se
guardan igual** — para eso `puntas` no tiene FK.

---

## Contrato de persistencia: quién lee y quién escribe

| Quién | Lee | Escribe |
|---|---|---|
| `backend/app/db/health.py` | `precios.capturado_en` (el máximo) | — |
| Motor Python (`segmentos`, `cupones`, `mercado`) | vista `resumen`, `cashflow`, `puntas` | — |
| F-007 (ingesta multi-fuente) | `precios.fecha_metricas` y las métricas previas | `instrumentos`, `precios`, `puntas`, `cashflow` |
| F-009 (semilla y herencia) | `condiciones_emision` | `condiciones_emision`, `instrumentos` |
| Frontend (F-014 en adelante) | tablas de usuario vía PostgREST, con RLS | tablas de usuario, con RLS |

**`instrumentos` se actualiza sin pisar con nulos.** El upsert usa
`COALESCE(EXCLUDED.col, instrumentos.col)`, así que una corrida sin IAMC deja la ley y la moneda de
pago como estaban. Las excepciones son `revisar` y `duplicado`: son NOT NULL y se recalculan enteras
en cada corrida, porque con COALESCE una emisión que dejó de estar en conflicto quedaría marcada para
siempre.

**`duplicado` cambió de significado en F-007.** Antes marcaba un ticker repetido en la fuente; ahora
marca una especie que BYMA publica en los dos plazos de liquidación (1 y 2) y que entra una sola vez.
Son 2.087 de 2.894. Se conserva la del plazo 2 y, a igualdad, la que más operó; verificado que las
filas repetidas nunca difieren en moneda ni en vencimiento, sólo en precio y volumen.

**El health depende de nombres exactos.** `backend/app/db/health.py` consulta `public.precios` y su
columna `capturado_en`; las tiene como constantes, `TABLA_PRECIOS` y `COLUMNA_SNAPSHOT`. Si alguna
de las dos cambia de nombre, ese archivo es el único lugar del backend que hay que tocar.

**Sobre RLS y quién puede escribir.** Las tablas de mercado tienen RLS habilitada con una policy de
lectura abierta a cualquier usuario autenticado y **sin policies de escritura**: el universo se lee
igual para todos, pero nadie escribe a través de la API pública con la anon key. El backend escribe
por conexión directa como dueño de las tablas, y el dueño no pasa por RLS. Si algún día el backend
conectara con un rol que no sea el dueño, habría que agregarle policies de escritura o el atributo
`BYPASSRLS`; hoy no hace falta.

Las tablas de usuario tienen cuatro policies cada una (SELECT, INSERT, UPDATE, DELETE), todas contra
`auth.uid() = user_id`. Están separadas por operación en vez de una sola `FOR ALL` porque así queda
explícito que INSERT y UPDATE verifican también la fila que se escribe (`WITH CHECK`), no solo la
que se lee: sin eso, un asesor podría insertar una fila a nombre de otro.

`posiciones` repite `user_id` además de `cartera_id`. Es denormalización a propósito: la policy se
evalúa por fila, y sin esa columna cada lectura tendría que subir a la cartera para saber de quién
es.

---

## Migraciones y rollback

Las migraciones son archivos SQL versionados en `supabase/migrations/`, con el mismo formato de
nombre que usa la CLI de Supabase (`YYYYMMDDHHMMSS_nombre.sql`). Se aplican con la herramienta
`apply_migration` del MCP, que las registra en `supabase_migrations.schema_migrations`.

**El nombre del archivo tiene que coincidir con la versión registrada.** El servidor asigna la
versión al aplicar, así que después de aplicar conviene mirar el historial y renombrar el archivo si
hiciera falta. Si alguien más adelante usa la CLI, que primero corra `supabase link`: hacer
`db push` sin linkear puede duplicar versiones.

Cada migración tiene su rollback en `supabase/rollbacks/`, con el mismo nombre y sufijo `_down`.
Se aplican con `execute_sql`, no con `apply_migration`: un rollback no es una migración nueva. Cada
uno borra su propia fila del historial.

**Cada rollback deshace solo lo suyo.** Están separados en tres justamente por eso: tirar abajo las
tablas de usuario o la vista no toca una sola fila de mercado. El rollback de mercado, que sí borra
datos, corre último y falla si las otras migraciones siguen aplicadas — `posiciones` referencia
`instrumentos` y la vista lee de sus tablas. Ese orden forzado es deliberado: tirar abajo el
universo tiene que ser una decisión explícita, no un efecto colateral.

### Ensayo hecho el 2026-08-06

Con la base ya migrada y todavía sin datos, se aplicaron los rollbacks de la vista y de las tablas
de usuario. Las cinco tablas de mercado siguieron en pie (`to_regclass` no nulo para las cinco),
`carteras` y la vista desaparecieron, y al reaplicar quedó todo igual que antes: las mismas ocho
tablas, la misma vista, las mismas policies y el mismo historial de tres migraciones.

Es el criterio de aceptación 4 de F-002, verificado contra la base real.
