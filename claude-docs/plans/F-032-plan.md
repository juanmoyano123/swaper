# F-032 — Motor de rotaciones intra-segmento

## Spec (plan.md:1546-1583)

Envoltura como servicio de `tools/detectar_swaps.py`: `evaluar_par`, `detectar`,
`tabla_spread_legislacion` y `hoja_sensibilidad` se conservan; cae la cáscara de argparse y
openpyxl. Genera rotaciones candidatas **dentro del mismo segmento** — un cruce CER → hard-dollar
es visión macro humana, no un swap, y el motor no lo propone. Trabaja sobre la vista viva de
especies, porque los swaps de perfil rotan entre especies de la misma emisión (MEP → Cable).
Ranking con filtro de liquidez y de rendimiento mínimo. Validado contra el swap que la mesa
efectivamente ejecutó: TLCWO → TLCMO.

```
GIVEN una posición en un bono CER
WHEN se generan rotaciones candidatas
THEN todos los destinos propuestos son del segmento CER, y ninguno es hard-dollar, dólar-linked ni
     tasa nominal en pesos

GIVEN el swap TLCWO → TLCMO que la mesa ejecutó
WHEN se corre el motor sobre la cartera de origen
THEN esa rotación aparece entre las candidatas

GIVEN una posición en la especie MEP de una emisión
WHEN se generan rotaciones
THEN la especie Cable de la misma emisión es un destino válido, porque el optimizador trabaja
     sobre la vista viva

GIVEN un destino candidato por debajo del filtro de liquidez o de rendimiento mínimo
WHEN se rankean los destinos
THEN queda excluido del ranking
```

Depende de F-011, F-030 — cerradas. Riesgo R9 (`plan.md:2754`): "el desacople del motor resulta
ser reescritura encubierta" — se mitiga con un test de paridad contra el consolidado versionado y
el caso TLCWO→TLCMO como aceptación. Regla 8 del dominio: "nunca se propone una mejora de TIR sin
nombrar qué riesgo se asume a cambio" — es literalmente `riesgo_nota` en `evaluar_par`.

**Alcance de esta tanda, confirmado**: sin UI. La pantalla de rotaciones es F-036 (tanda 15); acá
sólo el servicio backend y su contrato. `hoja_sensibilidad` y `tabla_spread_legislacion` se
portan con tests y viajan **dentro de la respuesta** del único endpoint — no se exponen por
endpoints propios, porque no tienen consumidor todavía (mismo criterio que ya se aplicó con
`calificacion` en la tanda 11: no se construye plomería sin pantalla, salvo que la ficha explícita
la pida; acá la ficha pide conservar las funciones, no exponerlas sueltas).

## Qué ya dejó la base común de la tanda

1. `EspecieUniverso` gana `tipo_tasa: str | None` y `calificacion: str | None`. `tipo_tasa` es lo
   que separa Bopreal (BCRA) del resto del Tesoro en `clave_emisor_swap`; `calificacion` es lo que
   `riesgo_nota` muestra cuando cambia entre origen y destino — **nunca se ordena**.
2. Router vacío `backend/app/api/v1/rotaciones.py`, ya montado en `router.py` con
   `tags=["rotaciones"]`. **No tocar `router.py`.**

## Archivos (dueño único: F-032)

- `backend/app/rotaciones/__init__.py` — nuevo, vacío o con un docstring de paquete.
- `backend/app/rotaciones/constantes.py` — nuevo.
- `backend/app/rotaciones/emisores.py` — nuevo.
- `backend/app/rotaciones/legislacion.py` — nuevo.
- `backend/app/rotaciones/frecuencia.py` — nuevo.
- `backend/app/rotaciones/motor.py` — nuevo, el núcleo puro.
- `backend/app/rotaciones/servicio.py` — nuevo, orquestación con base.
- `backend/app/api/v1/rotaciones.py` — reemplaza el router vacío (agrega el endpoint).
- `backend/tests/test_rotaciones_motor.py` — nuevo.
- `backend/tests/test_rotaciones_api.py` — nuevo.
- `backend/tests/test_rotaciones_paridad_motor.py` — nuevo.

Sin cambios frontend. Sin cambios en `router.py`, `lectura.py`, `segmentacion.py` (ya los tocó la
base común).

## `constantes.py` — portadas de `tools/detectar_swaps.py`, con su porqué

```python
from dataclasses import dataclass
from app.concentracion.perfiles import PERFILES, NombreDePerfil  # o el tipo Literal equivalente

MIN_DTIR = 0.005            # 0.5 pp — CLI --min-dtir default
MAX_MAS_DURACION = 1.5      # años — CLI --max-mas-duration default
UMBRAL_NEUTRO = -0.003      # -0.3 pp — CLI --umbral-neutro default
FACTOR_VOLUMEN = 3.0        # CLI --factor-volumen default
TOP_N = 3                   # CLI --top-n default, por tipo
PERCENTIL_DISTRESS = 95     # CLI --percentil-distress default
MIN_OPERABLES_PERCENTIL = 10  # con menos, el percentil no dice nada
BANDA_RENDIMIENTO_PP = 0.5     # para ordenar destinos parejos
TOL_DURACION_LEY = 0.25        # años, para emparejar ley local vs extranjera
MIN_REND = 0.0              # CLI --min-rend default
DIAS_CUPON = 45             # CLI --dias-cupon default
ESCENARIOS_TIR = (-0.05, -0.04, -0.03, -0.02, -0.01, 0.0, 0.01, 0.02)  # bps: -500..+200

TOPE_DISTRESS_DEFAULT: dict[str, float] = {"usd_hard": 0.15}

LEY_LOCAL = "Ley Argentina"
LEYES_EXTRANJERAS = frozenset({"Ley N.Y.", "Ley Europea", "Extranjera"})


@dataclass(frozen=True, slots=True)
class ParametrosRotacion:
    """Los parámetros del motor para una corrida, derivados del perfil (D6 del plan de tanda)."""

    percentil_liquidez: float
    tope_distress: dict[str, float]

    @classmethod
    def de_perfil(cls, nombre: NombreDePerfil) -> "ParametrosRotacion":
        perfil = PERFILES[nombre]
        return cls(
            percentil_liquidez=float(perfil["percentil_liquidez"]),
            tope_distress={**TOPE_DISTRESS_DEFAULT, "usd_hard": perfil["tope_rend_usd"]},
        )
```

**Por qué el perfil `moderado` reproduce los defaults del CLI, verbatim**: `PERFILES["moderado"]`
trae `percentil_liquidez=25`, `tope_rend_usd=0.15` — exactamente `--percentil-liquidez 25` (CLI
default) y el `usd_hard: 0.15` de `TOPE_DISTRESS_DEFAULT`. Esto es lo que hace gratis la paridad
con perfil moderado en el test.

`es_extranjera(ley: str | None) -> bool` vive acá o en `legislacion.py` (decisión menor de
implementación) — `str(ley) in LEYES_EXTRANJERAS`, con `None` no perteneciendo a ningún conjunto.

## `emisores.py`

```python
def clave_emisor_swap(especie: EspecieUniverso, riesgos: Mapping[str, RiesgoDeEspecie]) -> str:
    """`'BCRA'` si `especie.tipo_tasa == 'bopreal'`, si no la `clave_riesgo` de `derivar_riesgo`.

    El Bopreal tiene `clase_activo='bono_soberano'` (por eso F-020 lo cuenta bajo `SOBERANO_AR`
    en concentración — esa decisión NO se toca), pero lo emite el BCRA y no el Tesoro. Para
    "mismo emisor" en un swap, Tesoro→Bopreal SÍ es cambio de emisor. Derivarlo del prefijo del
    ticker sería la inferencia que la regla 1 prohíbe; `tipo_tasa` es un dato declarado.
    """
    if especie.tipo_tasa == "bopreal":
        return "BCRA"
    return riesgos[especie.ticker].clave_riesgo


def nombre_emisor(especie: EspecieUniverso, clave: str) -> str:
    """Nombre para mostrar cuando `especie.emisor` es `None` (soberanos nunca lo traen)."""
    if especie.emisor is not None:
        return especie.emisor
    if clave == "SOBERANO_AR":
        return "Gobierno Argentino"
    if clave == "BCRA":
        return "BCRA"
    return f"(sin identificar: {clave})"
```

`riesgos = derivar_riesgo(especies)` se importa de `app.concentracion.riesgo` — **no se
reimplementa**, es el mismo import que ya usa `/armado`.

## `legislacion.py` — port de `tabla_spread_legislacion`

```python
@dataclass(frozen=True, slots=True)
class ParDeLey:
    segmento: str
    emisor: str
    ticker_local: str
    rinde_local: float
    ticker_extranjero: str
    ley_extranjera: str
    rinde_extranjero: float
    duracion_local: float
    duracion_extranjera: float
    premio_bps: int

def premio_por_legislacion(
    operables: Sequence[EspecieUniverso],
    claves_emisor: Mapping[str, str],   # ticker -> clave_emisor_swap
) -> tuple[list[ParDeLey], dict[str, int]]:
```

Mismo algoritmo que `tools/detectar_swaps.py:231-280`: para cada especie con `ley == LEY_LOCAL` y
`duracion is not None`, buscar pares con `ley in LEYES_EXTRANJERAS`, mismo `segmento`, misma
`clave_emisor_swap`, y `|duracion_extranjera - duracion_local| <= TOL_DURACION_LEY`; quedarse con
el de duración más parecida; `premio_bps = round((rinde_local - rinde_extranjero) * 10000)`.
Medianas por segmento (`nombre del segmento`, no la clave cruda — usar `DESC_SEGMENTO` si conviene
para legibilidad, o la clave cruda si simplifica: decisión menor, documentar la elegida).

## `frecuencia.py` — port de `frecuencia_pagos` y `proximo_cupon`

```python
ESCALA_FRECUENCIA = (
    (45, "mensual", 1), (75, "bimestral", 2), (135, "trimestral", 3),
    (225, "semestral", 6), (400, "anual", 12),
)
MESES_DESCONOCIDO = 99

def frecuencia_por_raiz(cronograma: Cronograma, hoy: date) -> dict[str, tuple[str, int]]:
    """{raiz: (etiqueta, meses)}, medida sobre los pagos FUTUROS de renta > 0 de cada raíz.

    Port de `tools/cupones.py::frecuencia_pagos`, adaptado a `Cronograma.por_raiz` (ya agrupado
    por raíz, a diferencia del cashflow crudo del CLI). Una raíz con menos de dos pagos futuros de
    renta > 0 y al menos uno → `('al vencimiento', MESES_DESCONOCIDO)`. Una raíz sin ningún pago
    futuro de renta no entra al dict (mismo criterio que el CLI: sale `NaN`/ausente, no un default).
    """

def proximo_cupon(flujos: Flujos, ticker: str, hoy: date) -> dict | None:
    """El próximo `FlujoPorPeso` futuro de `ticker` con `pct_renta > 0`, o `None`.

    Port de `tools/cupones.py::proximo_cupon`, adaptado a `Flujos.flujos` (ya construido por
    `flujos_por_peso`, que el servicio arma una sola vez) en vez de recorrer un DataFrame propio.
    """
```

`Cronograma` y `Flujos`/`FlujoPorPeso`/`flujos_por_peso` se importan de `app.calendario.cupones`
— no se reimplementan.

## `motor.py` — el corazón, puro

```python
@dataclass(frozen=True, slots=True)
class Candidata:
    tipo: str                     # "mejora_rendimiento" | "mejora_perfil"
    segmento: str
    origen: EspecieUniverso
    destino: EspecieUniverso
    emisor_origen: str
    emisor_destino: str
    d_rend_pp: float
    d_duracion: float | None
    mismo_emisor: bool
    pasa_a_cable: bool
    mejora_ley: bool
    empeora_ley: bool
    mejora_volumen: bool
    posible_distress: bool
    premio_ley_bps: int | None
    premio_ley_vs_mediana_bps: int | None
    riesgo_nota: str
    frec_meses: int
    cupon_dias: int | None
    cupon_pct: float | None
    cupon_nota: str | None

def evaluar_par(
    origen: EspecieUniverso, destino: EspecieUniverso, *,
    claves_emisor: Mapping[str, str], nombres_emisor: Mapping[str, str],
    frecuencias: Mapping[str, tuple[str, int]], flujos: Flujos, hoy: date,
    medianas_ley: Mapping[str, int], params: ParametrosRotacion,
) -> Candidata | None:
    ...

def detectar(
    origenes: Sequence[EspecieUniverso], universo_operable: Sequence[EspecieUniverso], *,
    contexto...,
) -> tuple[list[Candidata], list[Alerta]]:
    ...
```

Port línea a línea de `evaluar_par`/`detectar` (`tools/detectar_swaps.py:283-508`), **sin** el
bloque de costo/spread/payback (D8 — declarado aparte, no en la candidata) y sin exponer
`--frecuencia-cupon`/`--clase`/`--max-rend-destino` como parámetros (no pedidos por la ficha de
esta tanda). Se conserva textual:

- Corte duro: `d_dur = destino.duracion - origen.duracion` (si ambas existen); si
  `d_dur > MAX_MAS_DURACION` → `None`.
- `mismo_emisor = claves_emisor[origen.ticker] == claves_emisor[destino.ticker]`.
- `pasa_a_cable = origen.moneda_cupon in ('MEP', 'ARS') and destino.moneda_cupon == 'CCL'`.
- `mejora_ley = origen.ley == LEY_LOCAL and es_extranjera(destino.ley)`;
  `empeora_ley = es_extranjera(origen.ley) and destino.ley == LEY_LOCAL`.
- `mejora_volumen`: mismo criterio con `volumen_usd` de las dos especies y `FACTOR_VOLUMEN`.
- Tipo `"mejora_rendimiento"` si `d_rend >= MIN_DTIR`; si no, `"mejora_perfil"` si
  `mismo_emisor and d_rend >= UMBRAL_NEUTRO and (pasa_a_cable or mejora_ley or mejora_volumen)`;
  si ninguna, `None`.
- `riesgo_nota` (regla 8, textual, **sin ordenar calificaciones**):
  - `mismo_emisor` → `"mismo emisor — mismo riesgo crediticio"`.
  - si no, y cambia `categoria_credito` (soberano/subsoberano/corporativo, de `clase_activo`,
    mismo mapeo que `categoria_credito` del CLI) → `f"cambia riesgo {cat_o} → {cat_d} — verificar"`.
  - si no → `f"distinto emisor ({cat_d}) — verificar calidad crediticia"`.
  - si además `not mismo_emisor` y las dos calificaciones existen y difieren →
    `+ f" [{cal_o} → {cal_d}]"` (texto crudo, nunca un "sube/baja" inferido).
  - si `empeora_ley` → `+ " | ATENCION: pasa de Ley N.Y. a Ley Argentina"`.
- `posible_distress`: marcado por `detectar` sobre `destinos_ok` agrupados por segmento (percentil
  `PERCENTIL_DISTRESS` de `rendimiento`, sólo en segmentos con ≥ `MIN_OPERABLES_PERCENTIL`
  candidatos) — no descarta, señala.
- `cupon_nota`: `proximo_cupon(flujos, origen.ticker, hoy)`; si `dias <= DIAS_CUPON` y
  `pct_renta > 0`, nota de "conviene esperar al cobro" (texto calcado del CLI).

`detectar`:
1. `destinos_ok = universo_operable` (ver "Vista viva y operables" abajo), filtrado por
   `rendimiento > MIN_REND / 100`.
2. Piso de liquidez **por segmento**, con `percentil_lineal` (de `app.armado.motor`, no
   reimplementado) sobre `volumen_usd` de cada segmento con ≥ `MIN_OPERABLES_PERCENTIL`
   candidatos; segmentos más chicos quedan sin filtrar y se avisan con una alerta ("percentil no
   aplica, revisar a mano").
3. Para cada origen, candidatos = `destinos_ok` del mismo `segmento`, ticker distinto, con
   `rendimiento <= tope_distress[segmento]` cuando el segmento tiene tope (sólo `usd_hard` con
   perfil moderado — igual que el CLI); segmentos sin tope declarado entran igual, con alerta.
4. `evaluar_par` sobre cada candidato; orden `(banda de BANDA_RENDIMIENTO_PP, frec_meses,
   -d_rend_pp)`; `top_n = TOP_N` **por tipo** (mejora_rendimiento y mejora_perfil no compiten por
   cupo).

### Vista viva y operables

`origenes` = las especies de `saneado.especies` (la vista viva completa, **sin deduplicar**) cuyo
`ticker` está en la cartera pedida. Una posición del cliente sin `rendimiento` se salta como
origen con una alerta (mismo criterio que el CLI: `pd.isna(origen['rendimiento'])`) — **no mata
el pedido entero**, las demás posiciones se siguen evaluando.

`universo_operable` = `saneado.operables()` — **ya existe en `UniversoSaneado`**
(`backend/app/universo/servicio.py:110`, `rendimiento is not None and ticker not in
sanidad.descartados`) y es exactamente `filtrar_operables` del CLI; no se reimplementa. La
divergencia con el CLI —que además excluye por el flag `revisar`, que el backend no lee— se
declara en el test de paridad.

Las hermanas MEP/Cable de la misma emisión son destinos válidos por construcción: ni `origenes`
ni `universo_operable` deduplican por raíz.

## `servicio.py` — orquestación con base

```python
@dataclass(frozen=True, slots=True)
class ResultadoRotaciones:
    perfil: str
    parametros: ParametrosRotacion
    candidatas: list[Candidata]
    origenes_evaluados: list[str]
    fuera_del_universo: list[str]
    sin_rendimiento: list[str]
    premio_legislacion: tuple[list[ParDeLey], dict[str, int]]
    sensibilidad: list[dict]
    alertas: list[Alerta]

    def como_dict(self) -> dict[str, object]: ...

async def detectar_rotaciones(
    conn: Any, tickers: Sequence[str], perfil: NombreDePerfil, *, hoy: date | None = None,
) -> ResultadoRotaciones:
    hoy = hoy or date.today()
    saneado = await sanear_universo(conn)
    vivas = {e.ticker: e for e in saneado.especies}

    origenes = [vivas[t] for t in tickers if t in vivas]
    fuera_del_universo = [t for t in tickers if t not in vivas]
    origenes_con_rendimiento = [e for e in origenes if e.rendimiento is not None]
    sin_rendimiento = [e.ticker for e in origenes if e.rendimiento is None]

    riesgos = derivar_riesgo(saneado.especies)
    claves_emisor = {t: clave_emisor_swap(e, riesgos) for t, e in vivas.items()}
    nombres_emisor = {t: nombre_emisor(e, claves_emisor[t]) for t, e in vivas.items()}

    cronograma = indexar_cronograma(await leer_cashflow(conn))
    paridades = indexar_paridades(await leer_paridades(conn))
    flujos = flujos_por_peso(saneado.especies, cronograma, paridades, hoy)
    frecuencias = frecuencia_por_raiz(cronograma, hoy)

    params = ParametrosRotacion.de_perfil(perfil)
    candidatas, alertas = detectar(origenes_con_rendimiento, saneado.operables(), ...)

    operables = saneado.operables()
    premio = premio_por_legislacion(operables, claves_emisor)

    sensibilidad = _sensibilidad(candidatas, cronograma, hoy)

    alertas.append(_alerta_costo_no_calculado())  # D8, ver abajo — SIEMPRE presente

    return ResultadoRotaciones(...)
```

**`_alerta_costo_no_calculado()`** (D8):

```python
def _alerta_costo_no_calculado() -> Alerta:
    return Alerta(
        codigo="costo_rotacion_no_calculado",
        mensaje=(
            "El costo real de rotar (arancel y spread bid/ask de las dos patas) todavía no se "
            "calcula: llega con el costo real de rotar (tanda 13). Estas candidatas son sólo la "
            "mejora de rendimiento y de perfil, sin descontar lo que cuesta ejecutarlas."
        ),
        severidad=Severidad.INFO,
    )
```

**`_sensibilidad`** (D8, `hoja_sensibilidad` compuesta sobre el port ya hecho por F-040): para
cada ticker que aparece como origen o destino en `candidatas` (rol `SALE`/`ENTRA`, igual que el
CLI), `retorno_por_tir(cronograma.pagos_de(especie.raiz), especie.rendimiento, ESCENARIOS_TIR,
hoy)` de `app.calendario.metricas` — **no reimplementado**. Ticker sin cashflow o sin TIR: fuera,
contado en una nota (no en `alertas` estructuradas — el CLI lo trata como informativo de la hoja,
no como alerta de la corrida; decisión menor, documentar la elegida).

## Contrato de `POST /api/v1/rotaciones`

Mismo patrón que `POST /concentracion` (`api/v1/concentracion.py`): posiciones explícitas por
body, perfil por query, siempre 200.

```python
class OrigenEntrada(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)

class CarteraEntrada(BaseModel):
    posiciones: list[OrigenEntrada] = Field(min_length=1, max_length=500)

@router.post("/rotaciones")
async def rotaciones(
    conn: Annotated[Any, Depends(get_db)],
    entrada: CarteraEntrada,
    perfil: NombreDePerfil = "moderado",
) -> dict[str, object]:
    tickers = [p.ticker for p in entrada.posiciones]
    resultado = await detectar_rotaciones(conn, tickers, perfil)
    return resultado.como_dict()
```

`NombreDePerfil` como `Literal["conservador", "moderado", "agresivo"]` — mismo patrón que
`concentracion.py`, un perfil inventado muere en la validación con 422.

`como_dict()` de `ResultadoRotaciones`:

```
{
  "perfil": str,
  "parametros": {
    "percentil_liquidez": float, "tope_distress": {segmento: float},
    "min_dtir_pp": float, "max_mas_duracion": float, "umbral_neutro_pp": float,
    "top_n": int, "min_rend": float, "factor_volumen": float,
  },
  "candidatas": [{
    "tipo": "mejora_rendimiento" | "mejora_perfil",
    "segmento": str,
    "origen": {ticker, emisor, rendimiento, duracion, moneda_cupon, ley, calificacion, lamina,
               frecuencia_cupon, volumen_usd},
    "destino": {... mismos campos ...},
    "delta": {"rendimiento_pp": float, "duracion": float | null},
    "flags": {mismo_emisor, pasa_a_cable, mejora_ley, empeora_ley, mejora_volumen,
              posible_distress},
    "premio_ley": {"bps": int, "vs_mediana_bps": int | null} | null,
    "riesgo_nota": str,
    "cupon": {"dias": int, "pct": float, "nota": str} | null,
  }],
  "origenes_evaluados": [str],       // tickers de la cartera que sí entraron a evaluarse
  "fuera_del_universo": [str],
  "sin_rendimiento": [str],
  "premio_legislacion": {
    "pares": [{segmento, emisor, ticker_local, rinde_local, ticker_extranjero, ley_extranjera,
               rinde_extranjero, duracion_local, duracion_extranjera, premio_bps}],
    "medianas_bps": {segmento: int},
  },
  "sensibilidad": [{ticker, rol, segmento, tir_actual, duracion,
                     escenarios: {"-0.05": float, ..., "0.02": float}}],
  "alertas": [Alerta.como_dict(), ...]   // incluye SIEMPRE costo_rotacion_no_calculado
}
```

Mapeo de "deltas por eje" del output de la ficha, documentado en el docstring del módulo: duración
→ `delta.duracion`; crédito → `riesgo_nota` + `calificacion` de origen/destino; legislación →
`flags.mejora_ley`/`empeora_ley` + `premio_ley`; liquidez → `volumen_usd` de origen/destino +
`flags.mejora_volumen` (spread: ausente, declarado por `costo_rotacion_no_calculado`); moneda →
`moneda_cupon` de origen/destino + `flags.pasa_a_cable`; concentración → no es por par, es de
cartera completa — F-033/F-034 la componen llamando `POST /concentracion` con la cartera antes y
después (el mismo endpoint que ya acepta posiciones explícitas para eso, `plan.md:2774` lo previó).

## Qué se porta tal cual, qué se adapta, qué cae

- **Tal cual**: `evaluar_par`, `detectar` (menos costo/spread/payback y los parámetros CLI no
  expuestos), `tabla_spread_legislacion` → `premio_por_legislacion`.
- **Adaptado**: `preparar_universo` → ya no carga CSVs, recibe `saneado.especies`; sólo conserva
  su parte de decisión (`clave_emisor_swap`, nombres soberano/BCRA). `anotar_frecuencia_cupon` →
  `frecuencia_por_raiz`, sobre `Cronograma` en vez de cashflow crudo. `hoja_sensibilidad` → compone
  `retorno_por_tir` ya portado por F-040, no reimplementa el repricing.
- **Cae**: `cargar_cartera`, `parsear_topes`, `parsear_escenarios`, `exportar_excel`, `main`,
  todo el bloque de `argparse` (cáscara, la ficha lo dice explícito). `mercado.costo_rotacion` no
  se porta (F-035, tanda 13).

## Tests

### `test_rotaciones_motor.py` (puro, fixtures sintéticas de `EspecieUniverso`)

- GWT-1: origen en `segmento='cer'` → todos los destinos propuestos tienen `segmento='cer'`.
- GWT-3: origen y destino son hermanas de la misma emisión (mismo `raiz`, distinto `moneda_cupon`)
  → aparece como candidata tipo `mejora_perfil` con `pasa_a_cable=True` cuando corresponde.
- GWT-4: destino con `volumen_usd` bajo el percentil del segmento → excluido; destino con
  `rendimiento` bajo `min_rend` → excluido.
- Caso TLCWO→TLCMO con datos calcados del spec (`docs/historial/2026-07-diseno-wat/05-spec-motor-swaps.md`):
  mismo emisor, mejora de rendimiento marginal, cambio a CCL, ~3× volumen, ley N.Y. → tipo
  `mejora_perfil`.
- `riesgo_nota`: mismo emisor / cambia categoría de crédito / distinto emisor misma categoría;
  con calificaciones presentes y distintas → sufijo `[cal_o → cal_d]`; con ley que empeora →
  sufijo de atención. Ninguna calificación se ordena ni se compara con `<`/`>`.
- Tesoro → Bopreal: `clave_emisor_swap` distinta (`SOBERANO_AR` vs `BCRA`) → `mismo_emisor=False`.
- Segmento con menos de `MIN_OPERABLES_PERCENTIL` operables: sin filtro de percentil, con alerta.
- Corte de duración: destino con `duracion - origen.duracion > MAX_MAS_DURACION` → excluido.
- `top_n` por tipo: más de `TOP_N` candidatas de cada tipo para un mismo origen → sólo entran las
  mejores `TOP_N` de cada uno (no compiten entre tipos).
- Origen sin `rendimiento`: se salta, con alerta, sin frenar el resto de la cartera.

### `test_rotaciones_api.py`

- 200 siempre, incluso sin candidatas.
- 422 con perfil inventado, o con `posiciones: []`.
- Forma exacta del contrato (claves presentes, tipos).
- `fuera_del_universo` con un ticker inexistente.
- `costo_rotacion_no_calculado` presente en `alertas` en toda respuesta.

### `test_rotaciones_paridad_motor.py` (GWT-2, R9)

Mismo patrón que `test_concentracion_paridad_motor.py`/`test_armado_paridad_motor.py`: carga
`data/output/universo_consolidado.xlsx` + `cashflow_completo.csv` (el consolidado versionado), y
sobre esos mismos datos:
1. Corre `tools/detectar_swaps.py` con sus defaults (equivalentes al perfil `moderado`,
   `--sin-spread` para que el costo no entre en la comparación).
2. Corre el servicio backend (`detectar_rotaciones`) adaptando las mismas filas a
   `EspecieUniverso` (mismo adaptador que ya usan los otros tests de paridad).
3. Compara el conjunto `(origen, destino, tipo)` de las dos corridas y, para el subconjunto común,
   `d_rend_pp`/`d_duration`/`mismo_emisor`/`pasa_a_cable`/`mejora_ley`/`empeora_ley`.

**Aserción de aceptación**: con `tickers=['TLCWO']`, `'TLCMO'` aparece entre los destinos
candidatos en las dos implementaciones (ESTADO.md:262 confirma que el dato versionado lo sigue
produciendo). Si el consolidado versionado alguna vez dejara de traer ese par, la fixture
sintética del motor puro (arriba) es la aceptación de respaldo, y el docstring del test lo declara
así para que no se lea como una regresión cuando el dato cambie.

**Divergencias deliberadas, declaradas en el docstring** (patrón F-020):
- Costo/spread/payback no se comparan (F-035 no existe todavía).
- El flag `revisar` de `filtrar_operables` del CLI no existe en `saneado.operables()`: se
  neutraliza excluyendo esas filas de ambos lados antes de comparar.
- La propagación de sector no aplica (el motor de swaps no usa sector).

## Edge cases (todos con test)

- Cartera con un solo ticker, sin candidatas → `candidatas: []`, sin error, 200.
- Ticker de la cartera fuera del universo vivo → en `fuera_del_universo`, resto evaluado igual.
- Ticker sin `rendimiento` → en `sin_rendimiento`, resto evaluado igual.
- Segmento sin tope anti-distress declarado (todo salvo `usd_hard` en el perfil moderado) →
  destinos entran igual, marcados `posible_distress` cuando corresponde, con alerta.
- Sin cashflow para una raíz → sin frecuencia (`frec_meses = MESES_DESCONOCIDO`), sin cupón
  próximo, con alerta; el motor sigue.
- Ninguna posición con ley local o ninguna con ley extranjera comparable → `premio_legislacion`
  vacío, con alerta (mismo texto que el CLI).
- Todas las candidatas del mismo tipo para un origen → `top_n` corta por tipo, no en conjunto.

## Zonas prohibidas

Todo frontend (esta feature no lo toca). `router.py` (ya montado por la base común).
`backend/app/universo/**`, `backend/app/concentracion/**`, `backend/app/calendario/**`,
`backend/app/armado/**` (se importa de ahí — `derivar_riesgo`, `percentil_lineal`,
`retorno_por_tir`, `Cronograma`/`flujos_por_peso`, `sanear_universo` — nunca se edita).
`tools/**` (sólo lectura, para portar). Todo lo de F-031 (`frontend/src/lib/cartera/riesgo.ts`,
`frontend/src/components/VectorDeRiesgo.tsx`, `PanelRiesgo.tsx`, `SeccionRiesgo.tsx`).

## Verificación

```
cd backend
source venv/bin/activate
python -m pytest tests/test_rotaciones_motor.py tests/test_rotaciones_api.py -q
python -m pytest tests/test_rotaciones_paridad_motor.py -q -m integration  # si está marcado así
python -m pytest -q -m "not integration"   # suite completa offline
ruff check app/rotaciones backend/tests/test_rotaciones_*.py
ruff format --check app/rotaciones
```

Manual: `curl -X POST 'http://localhost:8000/api/v1/rotaciones?perfil=moderado' -H 'Content-Type: application/json' -d '{"posiciones":[{"ticker":"TLCWO"}]}'` — debe devolver 200 con al menos
una candidata hacia `TLCMO`, la alerta de costo no calculado siempre presente, y ningún campo de
costo real en la respuesta.
