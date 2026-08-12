# Feature Plan: F-051 — Métricas propias: TIR, duración y paridad calculadas

## Overview
- **Source**: ficha en `claude-docs/planning/plan.md` (buscar `#### F-051`) · diseño de arquitectura
  del 08/08/2026, verificado contra el código y contra `data/output/cashflow_completo.csv`
- **Complexity**: L — matemática nueva + recableado de la precedencia de la consolidación
- **Modo**: plan prescriptivo. Si algo no cierra contra la realidad del código, **frenar y
  reportar**, no improvisar. Esta feature va **sola en la tanda 8a**: nadie más está tocando el
  repo mientras corre.

## Qué es

Hoy `tir`, `duration` y `paridad` se **ingieren** del informe de IAMC por ticker exacto: ~234 ONs
sobre ~2.180, y las especies D y C siempre vacías porque IAMC nombra una sola especie por emisión.
Los insumos para calcularlas ya están: el precio por especie llega de BYMA (F-004) y el cronograma
contractual de Docta (F-006), los dos en memoria dentro de la misma corrida de consolidación.

Esta feature calcula las tres métricas por especie, **descontando el flujo contractual contra el
precio de esa especie, en la moneda de ese precio**. IAMC pasa de fuente a contraste: donde ambos
existen, una divergencia sobre el umbral emite alerta y el cálculo propio se conserva como dato.

**El híbrido, que es la decisión central**: se calcula sólo donde el precio y el flujo están en la
misma moneda. AL30D y AL30C sí; AL30 (cotiza en pesos, paga en dólares) no — descontarlo exigiría un
tipo de cambio, y derivarlo de la propia emisión es copiar la TIR de la hermana, que la regla 1
prohíbe. Para esas especies IAMC sigue siendo fuente donde publica, y donde no publica el campo
queda vacío y la especie nombrada. La fuente de cada fila viaja en la columna `fuente`.

## GWT (criterios de aceptación, literales de la ficha ya actualizada)

```
GIVEN una especie cuyo precio del día está en la misma moneda que el flujo de su cronograma
WHEN corre la consolidación
THEN tir, duración y paridad salen del cálculo propio sobre el flujo contractual, por especie —
     AL30D contra su precio en dólares y AL30C contra el suyo, sin pasar por un tipo de cambio

GIVEN una especie cuyo precio está en otra moneda que su flujo (AL30 en pesos, flujo en dólares)
WHEN corre el cálculo
THEN no se calcula ni se deriva de la hermana; queda con la métrica de IAMC si IAMC la publica, y
     vacía y nombrada en la alerta si no

GIVEN una especie que no operó hoy o una emisión sin cronograma
WHEN corre el cálculo
THEN el campo queda vacío y la especie aparece nombrada en la alerta de cobertura; no se estima ni
     se copia de otra especie de la misma emisión

GIVEN un ticker que IAMC también publica
WHEN la métrica propia difiere de la publicada más allá del umbral configurado
THEN se emite alerta de contraste y el cálculo propio se conserva como dato

GIVEN un segmento cuya naturaleza de tasa no puede calcularse con el flujo disponible
WHEN corre el cálculo
THEN esas especies quedan fuera, alertadas, y nunca se les reporta una tasa de otra naturaleza
```

---

## Paso 0 — PRIMERO Y SOLO: romper el ciclo de imports

**Sin esto nada de lo que sigue compila.** `backend/app/calendario/cupones.py:55` y
`backend/app/universo/segmentacion.py:29` hacen `from app.ingesta.consolidacion import raiz_emision`
—el `__init__` del paquete—. En cuanto `armado.py` (que vive adentro de ese paquete) importe
matemática de calendario, la cadena `consolidacion.__init__ → armado → calendario.metricas →
calendario.cupones → consolidacion.__init__` se cierra sobre un paquete a medio inicializar y tira
`ImportError`.

En los **dos** archivos, cambiar a la forma que ya usa `armado.py:52`:

```python
from app.ingesta.consolidacion.raiz import raiz_emision
```

Es una línea por archivo, sin cambio de comportamiento. Correr la suite completa después de este
paso, antes de escribir nada más: tiene que quedar igual de verde que antes.

---

## Parte 1 — `backend/app/calendario/metricas.py` (NUEVO): la matemática pura

Vive en `calendario/` junto a `cupones.py` porque es la continuación de esa matemática: opera sobre
`Pago` y sobre `valor_tecnico`. **F-040 (tanda 8b) importa de acá** — `valor_presente` y
`anios_entre` son exactamente lo que su repricing necesita. Dejar eso escrito en el docstring del
módulo, con el nombre de la feature, como hizo F-010 con F-011 y F-012.

Python puro, sin numpy ni scipy: determinismo (regla 6) y ~6.000 especies × ~60 iteraciones × ~20
flujos corre en menos de un segundo. No agregar dependencias.

### Constantes de módulo (no son settings — precedente explícito en `core/config.py:85-88`)
```python
DIAS_POR_ANIO = 365.25      # la convención del motor (tools/cupones.py:297)
TASA_PISO = -0.99           # la guardia del motor: por debajo el descuento es degenerado
TASA_TECHO = 10.0           # 1000 % TEA: por encima no se reporta un número, se reporta el motivo
TOLERANCIA_SOLVER = 1e-10
MAX_ITERACIONES = 200
```

### Firmas
```python
def anios_entre(desde: date, hasta: date) -> float
    # (hasta - desde).days / DIAS_POR_ANIO

def valor_presente(t: Sequence[float], cf: Sequence[float], tasa: float) -> float
    # sum(cf_i / (1 + tasa) ** t_i)
    # Firma espejo de tools/cupones.py::_valor_presente para que el port de F-040 sea 1:1.

def resolver_tir(t: Sequence[float], cf: Sequence[float], precio_sucio: float) -> float | None
def duracion_macaulay(t: Sequence[float], cf: Sequence[float], tasa: float) -> float | None
def duracion_modificada(t: Sequence[float], cf: Sequence[float], tasa: float) -> float | None
def paridad_de(precio_sucio: float, valor_tecnico: float) -> float | None

@dataclass(frozen=True, slots=True)
class MetricasEspecie:
    tir: float | None
    duration: float | None            # modificada, en años — la columna `duration` del contrato
    duration_macaulay: float | None   # no se persiste; queda para F-040 y para los tests
    paridad: float | None
    motivo: str | None                # None si salió todo

def metricas_de(pagos: Sequence[Pago], precio_sucio: float, hoy: date) -> MetricasEspecie
```

### Cómo se implementa cada una
- **`resolver_tir`**: bisección sobre `f(y) = valor_presente(t, cf, y) - precio_sucio`. Con todos los
  `cf > 0`, `f` es estrictamente decreciente, así que el bracket `[TASA_PISO + ε, TASA_TECHO]` o
  contiene la raíz o no hay solución reportable:
  - `f(piso) <= 0` → el precio está por encima de todo lo descontable → `None`, motivo
    `"tir_bajo_piso"`.
  - `f(techo) >= 0` → la TIR está arriba del techo → `None`, motivo `"tir_sobre_techo"`.
  - Corta por `|b - a| < TOLERANCIA_SOLVER` o al agotar `MAX_ITERACIONES` → `None`, motivo
    `"sin_convergencia"` (con bisección y bracket válido no debería pasar; la guardia es doctrina,
    no optimismo).
  - **Bisección y no Newton**: determinística, sin derivada, convergencia garantizada con bracket.
  - Devuelve **TEA (efectiva anual) en fracción**, en la moneda y la naturaleza de los flujos.
- **`duracion_macaulay`**: `sum(t_i · vp_i) / sum(vp_i)`, en años. `None` si el denominador no es
  positivo.
- **`duracion_modificada`**: `macaulay / (1 + tasa)` — la modificación coherente con el compounding
  anual efectivo de `(1+y)^t`. IAMC publica su duración modificada con su propia base; **documentar
  esa diferencia de convención en el docstring**, porque es lo que absorbe la tolerancia del
  contraste de la Parte 2.
- **`paridad_de`**: `precio_sucio / valor_tecnico`. `None` si el valor técnico es `None` o `<= 0`.
  Es adimensional **sólo si ambos están en la misma moneda**: esa precondición la garantiza el
  llamador y se documenta acá.
- **`metricas_de`** (orquestador): `valor_tecnico(pagos, hoy)` → paridad; pagos futuros → `(t, cf)`
  con `anios_entre` y `pago.total` → `resolver_tir` → las dos duraciones. Sin pagos futuros o con
  valor técnico `None` → todo `None`, motivo `"vencida"`. Si la TIR no resuelve, **la paridad se
  reporta igual** (no depende de la TIR) y `tir`/`duration` quedan en `None` con su motivo. Nunca
  lanza, nunca estima.

**El precio de BYMA es sucio** — verificado: `cupones.py:18-20` fija `precio sucio = paridad ×
valor técnico` y los tests validan AL30 contra el cierre. No hay ajuste por corridos que hacer.

---

## Parte 2 — `backend/app/ingesta/consolidacion/metricas.py` (NUEVO): la política

Separa la decisión de negocio (qué especie se calcula, con qué precedencia, cuándo se alerta) de la
matemática. Acá van la tabla por naturaleza, el contraste y las alertas.

### Tabla de decisión por naturaleza — el corazón de la feature

| tipo_tasa | ¿Se calcula? | Condición de la especie | Unidad reportada | Por qué |
|---|---|---|---|---|
| `hard-dollar`, `bopreal` | **Sí** | `moneda_cotizacion ∈ {USD, EXT}` | TEA en USD (fracción) | Flujos fijos en USD por 100 VN. Precio USD contra flujo USD: adimensional, sin FX. Es exactamente el hueco de hoy (especies D y C siempre vacías) |
| `hard-dollar`, `bopreal` en pesos | **No** | — | — | Precio ARS contra flujo USD exige un tipo de cambio (regla 3), y el MEP de la propia emisión sería copiar la TIR de la hermana (regla 1). Motivo `"moneda_cruzada"` |
| `tasa-fija` | **Sí** | `moneda_cotizacion == ARS` | TEA en ARS, en la columna `tir` | Flujos fijos en ARS. **`tna` NO se llena**: convertir TEA→TNA exige una convención de capitalización que ninguna fuente declara, e inventarla viola la regla 1. Precedente: IAMC ya publica TIR de ONs en pesos y se guarda en `tir` sin alimentar el rendimiento del segmento. Cupón cero (LECAP/BONCAP) es un solo flujo: el solver lo resuelve sin caso especial, y su Macaulay es exactamente `t` |
| `cer` | **No** | — | — | **Verificado en `data/output/cashflow_completo.csv`**: los flujos son contractuales, sin coeficiente CER (TX26 paga interés 1,0 = 2 % semestral sobre residual 100 exacto; el residual baja 100→80→60→40→20→0). El precio en pesos sí incorpora el CER. Sin el índice —que no se ingiere— no hay tasa real limpia, y reportar la nominal sería una tasa de otra naturaleza |
| `dollar-linked` | **No** | — | — | El pago en pesos depende del tipo de cambio de la fecha de pago: el flujo no está determinado en la moneda del precio |
| `badlar`, `tamar` | **No** | — | — | Los intereses futuros del feed son proyección a la tasa vigente, no montos contratados. Descontar una proyección es inventar |
| Sin cronograma / sin precio / vencida / TIR fuera del bracket | **No** | — | — | Campo vacío y especie nombrada. Jamás se copia de la hermana |

**Al implementar, verificar los valores literales de `tipo_tasa` contra
`backend/app/ingesta/consolidacion/clasificacion.py`** (`SUBMARKET_MAP`) y los de `moneda_cotizacion`
contra `backend/app/universo/cambio.py`. Si algún literal no coincide con esta tabla, frenar y
reportar — no adivinar el mapeo.

### Estructuras
```python
MONEDAS_DEL_FLUJO: dict[str, frozenset[str]]   # {"hard-dollar": {"USD","EXT"}, "bopreal": {...},
                                               #  "tasa-fija": {"ARS"}}
NATURALEZAS_FUERA: dict[str, str]              # tipo_tasa → motivo declarado, texto de la tabla

def fuente_de_metricas(tipo_tasa: str | None, moneda_cotizacion: str | None) -> str
    # "calculo" | "iamc" | "fuera"

@dataclass(frozen=True, slots=True)
class ContrasteMetricas:      # patrón de universo/cambio.py::Contraste (leerlo antes de escribir)
    raiz: str
    ticker_propio: str        # la especie calculada (D primero, C si no hay D — criterio de F-012)
    ticker_iamc: str          # la especie que IAMC nombra
    tir_propia / tir_iamc / duration_propia / duration_iamc / paridad_propia / paridad_iamc
    # props: divergencias() -> dict[str, dict], coincide -> bool, como_dict()

TOLERANCIA_TIR = 0.01        # 100 pb absolutos, ambas en fracción
TOLERANCIA_DURATION = 0.5    # años
TOLERANCIA_PARIDAD = 0.05    # espejo de TOLERANCIA_CONTRASTE de F-012

@dataclass
class ResultadoMetricas:      # acumulador de la pasada, patrón Flujos / TipoDeCambio
    calculadas: int
    por_motivo: dict[str, list[str]]      # motivo → tickers nombrados
    contrastes: list[ContrasteMetricas]
    @property
    def alertas(self) -> list[Alerta]
    def resumen(self) -> dict[str, object]
```

### El contraste contra IAMC
- **Qué se compara**: por raíz de emisión. Si IAMC nombra un ticker que nosotros calculamos (ONs en
  pesos a tasa fija: match exacto), se compara consigo mismo. Si IAMC nombra la especie en pesos de
  una emisión hard-dollar —el caso dominante: IAMC publica la pelada, nosotros calculamos la D—, se
  compara nuestra especie calculada contra el valor publicado de la hermana. Es legítimo porque
  TIR-USD, duración y paridad son magnitudes **de la emisión** (F-011 usa ese mismo hecho para
  validar agrupamientos); la diferencia residual es el canje MEP/cable, y el umbral se fija por
  encima de él.
- **Unidades, que es donde está la trampa**: la TIR propia sale en fracción; `FilaInforme["tir"]` y
  `paridad_pct` vienen en puntos porcentuales. **El módulo de contraste divide por 100 él mismo**,
  no depende de que otro lo haya hecho. `duracion_modificada` de IAMC ya está en años.
- **Umbrales**: 100 pb de TIR porque el canje (~3,6 % de precio) sobre una duración típica de 5-7
  años ya explica 50-70 pb, más base de días y hora de captura (IAMC cierra al final del día, BYMA
  es intradía). 0,5 años de duración porque la diferencia de convención de modificación mueve
  décimas. 0,05 de paridad, espejo de F-012 y por su misma razón documentada: una alerta que grita
  todos los días por un spread estructural es una alerta que nadie mira.

### Alertas (tres constructores nuevos)
Seguir la forma de `backend/app/ingesta/alertas.py` (leerlo antes) y el patrón de acumulador con
`.alertas` de `Flujos` / `TipoDeCambio`. Muestra acotada de tickers por motivo, como hace
`cambio.py` con su constante de muestra.

- `metricas_propias_sin_insumo` (ADVERTENCIA) — GWT-3. Detalle por motivo: `sin_precio`,
  `sin_cronograma`, `vencida`, `tir_bajo_piso`, `tir_sobre_techo`, `sin_convergencia`.
- `metricas_fuera_de_naturaleza` (ADVERTENCIA) — GWT-5. Los cuatro de `NATURALEZAS_FUERA` más
  `moneda_cruzada`. Deja explícito que a esas especies **no se les reporta tasa de otra naturaleza**.
- `metricas_contraste_iamc` (ADVERTENCIA) — GWT-4. Sólo si hay divergencias sobre el umbral. En el
  mensaje: el cálculo propio se conserva como dato.

---

## Parte 3 — Integración en la consolidación

### 3.1 `armado.py`
- **Docstring, líneas 9-17**: reescribir la tabla de precedencia. `tir`/`duration`/`paridad` pasan a
  "cálculo propio, especie" para las especies calculables y siguen en "IAMC, ticker exacto" para las
  que no lo son; `convexidad` y `residual_value` no cambian. Explicar el híbrido en el párrafo de
  abajo (hoy explica por qué la TIR no se hereda entre hermanas — ese motivo sigue vigente y se
  refuerza).
- `METRICAS_POR_TICKER` **queda como está**: sigue describiendo qué publica IAMC. Lo que cambia es
  quién lo consume.
- `_metricas_de(...)`: gana el dato de la decisión. Para una especie con fuente `"calculo"`, aplica
  IAMC y carry-over **sólo** a `convexidad` y `residual_value`; `fecha_metricas` sigue rotulando
  exclusivamente lo que salió de IAMC. **Regla dura: el cálculo propio nunca es pisado por IAMC ni
  por el carry-over.** Y al revés: para una especie calculable que hoy no tiene insumo, el campo
  queda vacío aunque IAMC lo publique (GWT-3 lo exige explícitamente).
- **Firma nueva** (rompe a propósito, para que ningún llamador quede sin decidir):
```python
def armar_consolidacion(
    *,
    especies_por_endpoint: dict[str, list[FilaRueda]],
    filas_iamc: list[FilaInforme] | None = None,
    filas_cashflow: list[dict[str, object]] | None = None,
    cronograma_persistido: list[dict[str, object]] | None = None,
    archivo_iamc: str | None = None,
    fecha_informe: date | None = None,
    metricas_previas: dict[str, dict[str, object]] | None = None,
    hoy: date,                      # keyword OBLIGATORIO, sin default
) -> Consolidacion
```
  "Sin base, sin red, sin reloj" se preserva: `hoy` se inyecta, no se consulta.
- Adentro: `pagos = filas_cashflow if filas_cashflow is not None else (cronograma_persistido or [])`
  y `cronograma = indexar_cronograma(pagos)`. **`_indice_cronograma` pasa a usar esa misma fuente**
  — mejora colateral: una corrida sin Docta deja de perder la clasificación de `public-bonds`.
- En el loop por ticker (l.350+), donde ya están `raiz`, `fila["precio_ultimo"]`,
  `fila["moneda_cotizacion"]` y el `tipo_tasa`: decidir la fuente; si es `"calculo"`, llamar
  `metricas_de(cronograma.pagos_de(raiz), precio, hoy)`; acumular en `ResultadoMetricas`; escribir
  en el dict de precios.
- Columna `fuente`: componer los términos presentes — `"byma"`, más `"+calculo"` si alguna de las
  tres salió del cálculo, más `"+iamc"` si hay `fecha_metricas`. (Verificado por grep: nadie
  consume ese string fuera de la tabla.)
- Al final de la pasada, sumar `resultado_metricas.alertas` a las alertas de la consolidación.
- `Consolidacion` **no cambia de forma**: alertas y cobertura ya viajan, y
  `CAMPOS_COBERTURA_PRECIOS` ya mide `tir`, `duration` y `paridad`.

### 3.2 `corrida.py`
- Mover `capturado_en = datetime.now(UTC)` **antes** de `armar_consolidacion` y pasar
  `hoy=capturado_en.date()`. Documentar la decisión: fecha UTC, coherente con el sello que lleva la
  fila; los jobs corren en horario diurno de Buenos Aires, donde la fecha UTC coincide con la local.
  Si algún día hay corridas nocturnas, este es el único punto a cambiar.
- Cuando Docta no entregó (`filas_cashflow is None`): leer el cronograma persistido y pasarlo como
  `cronograma_persistido`. **Semántica, documentarla**: el cronograma es contractual y no envejece,
  así que reusarlo no es presentar un dato viejo como nuevo — el precio sigue siendo el del día, y
  las métricas también. `filas_cashflow` queda en `None` para la persistencia, así el contrato de
  F-006 (bloque 3 conserva lo persistido) no cambia.

### 3.3 `persistencia.py`
- `SQL_METRICAS_PREVIAS` **no cambia**: su filtro `fecha_metricas IS NOT NULL` ya selecciona sólo
  filas con métricas de IAMC. El uso restringido lo decide `_metricas_de`.
- Nueva `leer_cashflow_persistido(conn)` con las nueve columnas del contrato (`ticker, type,
  issue_date, payment_date, capital, interest_rate, interest_amount, residual_value, cash_flow`).
- **Tablas, columnas, migraciones y la vista `resumen`: cero cambios.** `COLUMNAS_PRECIOS` ya tiene
  las tres columnas.

### 3.4 `jobs/corridas.py` + `jobs/universo.py` — el segundo llamador
`jobs/corridas.py` también llama `armar_consolidacion`, y hoy le pasa como `filas_cashflow` unas
filas que sólo tienen `ticker` y `type` (`SQL_TIPOS_CRONOGRAMA` en `jobs/universo.py:22`). **Si eso
se indexara como cronograma, cada refresco intradiario borraría las métricas.** Ensanchar ese lector
a las nueve columnas del contrato, renombrarlo (`leer_cronograma_persistido`) y compartirlo con
`persistencia.py` en vez de duplicarlo; el refresh lo pasa como `cronograma_persistido` (y sigue con
`filas_cashflow=None`, así no re-persiste el cronograma) más su `hoy=`.

**Esto no es sólo una defensa**: es la mejor consecuencia de la feature. La TIR, la duración y la
paridad se recalculan en cada refresco intradiario contra el precio vivo — que es exactamente el
comportamiento del monitor de mesa que originó la feature.

---

## PROHIBIDO tocar
`backend/app/universo/lectura.py` (los campos; la línea 29 de `segmentacion.py` sí, es el paso 0) ·
`backend/app/universo/sanidad.py` · `backend/app/universo/cambio.py` ·
`rendimiento_declarado` / `NATURALEZA_TASA` / `EspecieUniverso` en `segmentacion.py` ·
`backend/app/api/v1/**` · la vista `resumen` y cualquier migración · `frontend/**` · `tools/**`
(ni importarlo: se porta la convención, no el módulo) · `data/**` (sólo lectura, para los tests) ·
nada de `git add` / `git commit`.

**Tampoco**: llenar `tna`. Sigue en `None` con su alerta de cobertura, por la razón de la tabla.

## Reglas del dominio que esta feature NO puede violar
1. **Regla 1**: sin precio, sin cronograma o fuera del bracket → campo vacío y especie **nombrada**.
   Nunca un cero, nunca la métrica de la hermana, nunca una estimación.
2. **Regla 2**: cada segmento en su unidad. Lo que no se puede calcular en la unidad del segmento
   queda fuera y alertado — jamás se le reporta una tasa de otra naturaleza.
3. **Regla 3**: no se compara entre monedas sin normalizar, y acá directamente no se normaliza: si
   el precio y el flujo no comparten moneda, no se calcula.
4. **Regla 6**: determinístico. Bisección, tolerancia fija, sin heurísticas, sin azar. Dos corridas
   sobre el mismo insumo dan el mismo bit.
5. Lo excluido se declara: cada especie no calculada cae en un motivo y el motivo se cuenta.

## Test Strategy

Patrón offline de `backend/tests/`, fechas fijas, sin base. Leer `test_calendario_cupones.py` y
`test_consolidacion_armado.py` antes de escribir: las fábricas y el estilo de nombres en español ya
están definidos.

**`backend/tests/test_calendario_metricas.py` (nuevo)**
- Cupón cero con forma cerrada: precio `100/(1,05)²`, un flujo de 100 a dos años → `tir == 0,05`.
- Bono a la par: precio 100 con cupones planos → TIR ≈ la tasa del cupón.
- **Round-trip de autoconsistencia**: `valor_presente(t, cf, resolver_tir(t, cf, p)) == p` (±1e-8)
  sobre el cronograma real de AL30 leído de `data/output/cashflow_completo.csv` (versionado), con
  `HOY` fijo — mismo patrón de fecha fija y `pytest.skip` si falta el archivo que usa
  `test_calendario_paridad_motor.py`.
- Guardias: precio absurdamente alto → `None` + `"tir_bajo_piso"`; precio ínfimo → `None` +
  `"tir_sobre_techo"`.
- Sin pagos futuros → `motivo == "vencida"` y las cuatro métricas en `None`.
- Macaulay de un cupón cero es exactamente `t`; modificada es `macaulay/(1+y)`.
- Paridad `None` cuando el valor técnico es `None`; paridad reportada aunque la TIR no resuelva.
- **Determinismo**: dos corridas seguidas, igualdad estricta (no `approx`).

**`backend/tests/test_consolidacion_metricas.py` (nuevo)**
- La tabla por naturaleza, un test por fila: hard-dollar en USD calculada; hard-dollar en pesos →
  `moneda_cruzada`, no calculada; tasa fija en ARS calculada; CER, dollar-linked, badlar y tamar
  fuera, cada una con su motivo en la alerta (GWT-5).
- GWT-3: sin precio → vacío y nombrada; sin cronograma en la raíz → vacío y nombrada; y en los dos
  casos, la hermana calculada **no** le presta su valor.
- GWT-4: contraste divergente → alerta emitida y el valor propio conservado; contraste dentro del
  umbral → sin alerta; y un test específico de que las unidades se convierten (IAMC en puntos vs
  propio en fracción) — un contraste que "divergiría" por comparar 7,92 contra 0,0792 es el bug que
  este test existe para atrapar.
- El carry-over de IAMC no pisa un cálculo propio.
- `cronograma_persistido` produce métricas con `filas_cashflow=None` (el caso de la corrida sin
  Docta y el del refresh intradiario).
- `tna` sigue `None` con su alerta.

**Tests existentes que cambian de semántica** (`test_consolidacion_armado.py`)
- `test_la_tir_se_persiste_desde_el_informe_y_la_fuente_lo_registra` (l.201) se parte en dos: para
  una especie **no calculable**, IAMC sigue siendo fuente y `fuente` lo registra; para una
  **calculable**, la TIR sale del cálculo y `fuente` lleva `+calculo`.
- `test_la_tir_de_una_especie_no_se_copia_a_sus_hermanas` (l.218) cambia de ejemplo pero no de
  espíritu: AL30D calculada contra su precio en dólares, AL30 sin cálculo por moneda cruzada, y
  sigue verificando que nada viaja entre hermanas.
- El resto: `hoy=FECHA` mecánico en las ~20 llamadas a `armar_consolidacion` (también en
  `test_jobs_corridas.py`, `test_consolidar_endpoint.py` y `test_consolidacion_integration.py`).

**Regresión contra `tools/`: no aplica al solver.** Verificado: `tools/` **no tiene** cálculo de TIR
—`retorno_por_tir` *recibe* la TIR de IAMC como input—, así que no hay motor contra el cual
regresionar. Lo que sí queda atado al motor es la convención (`DIAS_POR_ANIO`, la forma de
`valor_presente`), vía el round-trip sobre el dato versionado. El contraste continuo de la TIR es
contra IAMC del día, que es justamente lo que el GWT-4 institucionaliza.

## Comandos de verificación
```
cd /Users/jeroniki/Documents/Github/10-Swaper/backend
source venv/bin/activate
python -m pytest tests/ -x -q            # el marcador de integración ya está en addopts
ruff check . && ruff format --check .
```
Correr la suite **después del paso 0** (tiene que quedar igual de verde) y de nuevo al terminar.
Como esta feature va sola en su tanda, acá sí se corre la suite entera del backend.

## Al terminar, reportar
Archivos creados y modificados; el resultado textual de los comandos; **la cobertura medida**:
cuántas especies quedaron con métricas propias, cuántas con IAMC, cuántas vacías y el desglose por
motivo. Y el contraste: cuántos tickers se pudieron contrastar contra IAMC, cuántos coincidieron y
cuántos divergieron, con ejemplos.

**Un cero se explica, no se acepta** (regla de la casa, aprendida en la tanda 2): si alguna categoría
da cero —cero divergencias, cero especies fuera por naturaleza, cero calculadas en un segmento—,
rastrear la causa hasta poder decir por qué, y reportarla. Y si algo del plan no cierra contra el
código real, frenar esa parte y reportarla en vez de improvisar.
