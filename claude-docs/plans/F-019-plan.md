# Feature Plan: F-019 — Armado asistido

## Overview
- **Source**: spec en `claude-docs/planning/plan.md` (sección "#### F-019", líneas ~952–1004) ·
  A1 (mandato del cliente) en `design-system.md` como origen de los parámetros, sin mockup de
  botón dedicado · `claude-docs/planning/plan-ejecucion-tandas.md` (tanda 10, fila 53): alcance
  ampliado 08/2026, reusa `min_sectores` de F-020
- **Complexity**: L — es el port más grande de la tanda: cuatro funciones del motor
  (`resolver_mix`, `candidatos_del_segmento`, `elegir_siguiente`, `armar`) más el criterio nuevo de
  reparto sectorial
- **Modo**: plan prescriptivo. Si algo no cierra contra la realidad del código, **FRENAR y
  reportar**, no improvisar.

## Qué es

Botón que precarga una cartera de arranque a partir de: monto, moneda de referencia, objetivo de
cobertura (devaluación/inflación/tasa en pesos/mixta), perfil (conservador/moderado/agresivo) y
horizonte (corto/medio/largo). Es el punto de partida, no un resultado final: el asesor la sigue
editando a mano en `CarteraEditable` (F-018). Envuelve las funciones ya verificadas de
`tools/armar_cartera.py` (`resolver_mix`, `candidatos_del_segmento`, `elegir_siguiente`, `armar`),
descartando la cáscara de CLI (`argparse`, `exportar_excel` con openpyxl).

**Alcance ampliado (08/2026):** además de respetar los topes, el armado **reparte** por sector.
Entre candidatos comparables, `elegir_siguiente` prefiere el de un sector aún no representado en la
cartera; cada perfil declara un `min_sectores` (ya definido en `app/concentracion/perfiles.py` por
F-020: conservador=4, moderado=3, agresivo=2). Si el universo no alcanza para cumplirlo, la cartera
sale igual y se declara qué quedó concentrado y por qué — nunca se rellena con otra naturaleza.

## GWT (criterios de aceptación, literales del plan)

```
GIVEN los parámetros monto, moneda de referencia, objetivo, perfil y horizonte
WHEN el asesor pide armado asistido
THEN se precarga una cartera en el panel editable, editable posición por posición como cualquier otra

GIVEN los 15 casos de regresión de armar_cartera.py
WHEN se corren contra el servicio envuelto
THEN los 15 producen el mismo resultado que la versión de línea de comandos

GIVEN un objetivo de cobertura para el que no hay candidatos suficientes en el universo
WHEN se pide el armado asistido
THEN el sistema devuelve la cartera parcial y declara qué parte del objetivo no pudo cubrir, sin
     rellenar con instrumentos de otra naturaleza

GIVEN un perfil con min_sectores = 4 y un universo con candidatos comparables de 6 sectores
WHEN se pide el armado asistido
THEN la cartera resultante contiene posiciones de al menos 4 sectores distintos, sin contar
     Soberano ni Subsoberano, que ya los acota el tope soberano

GIVEN un objetivo de cobertura cuyo universo elegible tiene un solo sector corporativo
WHEN se pide el armado asistido
THEN la cartera sale con ese sector y una advertencia que nombra el mínimo incumplido y la
     causa, sin bloquear ni rellenar
```

**Nota sobre "los 15 casos de regresión":** no existe hoy un archivo con 15 fixtures nombradas —
es una cantidad objetivo, no una lista dada. Construir 15 escenarios representativos (combinaciones
de `perfil` × `horizonte` × `cobertura`/`mix` × `moneda`, incluyendo al menos un caso de cada
perfil, un `--mix` manual, un `--moneda usd`/`ars`, y un caso límite con `n_total` alto) y comparar
la salida del servicio envuelto contra `tools/armar_cartera.py::armar()` corrido directamente sobre
el mismo universo — mismo patrón que `backend/tests/test_concentracion_paridad_motor.py`.

## Reuso obligatorio — no reimplementar lo que ya existe

- **`app/concentracion/perfiles.py`**: `PERFILES` (los 6 campos, incluido `min_sectores`),
  `SECTORES_EXENTOS`, `sector_computable(sector)`. **Importar de acá, no copiar un segundo
  `PERFILES`** (el docstring del archivo lo exige explícitamente: *"F-019 los lee de acá"*).
- **`app/concentracion/riesgo.py`**: `derivar_riesgo(especies) -> dict[str, RiesgoDeEspecie]`,
  `RiesgoDeEspecie.clave_riesgo`/`.es_soberano`/`.nombre`. Es exactamente `fila["clave_riesgo"]` y
  `fila["es_soberano"]` del motor — no re-derivar `grupo_emisor`/`es_soberano` a mano en
  `app/armado/`.
- **`app/concentracion/servicio.py`**: `evaluar_concentracion` — **no** se llama desde `armar()`
  (el motor tiene su propio `verificar_concentracion` post-hoc, más simple), pero si el plan de
  implementación encuentra que reusar `evaluar_concentracion` para el chequeo final es más
  consistente que portar `verificar_concentracion` aparte, es una alternativa válida — decidir en
  la implementación y documentar la elección.
- **`app/universo/servicio.py::sanear_universo(conn)`** — mismo universo saneado que usa
  `concentracion.py`; **no** leer el universo por otra vía.
- **`app/universo/segmentacion.py`**: `EspecieUniverso` (`ticker`, `segmento`, `rendimiento`,
  `duracion`, `sector`, `emisor`, `volumen_usd`, `clase_activo`, `moneda_cotizacion`), y los mapas
  `MONEDA_SEGMENTO`, `NATURALEZA_TASA`, `NOMBRE_NATURALEZA` (ya en `segmentacion.py`, confirmar
  nombres exactos antes de importar — el motor los trae de `tools/segmentos.py` con los mismos
  nombres).

## `app/armado/` (paquete nuevo)

Sin pandas (el backend no lo usa fuera de `ingesta/docta/`; `concentracion/` y `calendario/` son
Python puro sobre listas/dataclasses — seguir ese estilo).

### `app/armado/constantes.py`
Portar tal cual, con el mismo razonamiento del motor en el docstring:
```python
BANDA_RENDIMIENTO = 0.005
MIX_COBERTURA: dict[str, dict[str, float]] = {
    "devaluacion": {"usd_hard": 70, "dollar_linked": 30},
    "inflacion": {"cer": 100},
    "tasa-pesos": {"tasa_fija": 60, "badlar": 20, "tamar": 20},
    "mixta": {"usd_hard": 50, "cer": 25, "tasa_fija": 15, "dollar_linked": 10},
}
HORIZONTES: dict[str, tuple[float, float]] = {
    "corto": (0.0, 2.0), "medio": (1.5, 5.0), "largo": (4.0, 99.0),
}
```
**No portar `PERFILES` ni `SECTORES_EXENTOS`**: importan de `app.concentracion.perfiles`.

### `app/armado/parametros.py` — el modelo Pydantic (reemplaza `argparse`)
Mapeo 1:1 de los flags del CLI (`tools/armar_cartera.py:558-580`), sacando lo que era de
exportación de archivo:

```python
class ParametrosArmado(BaseModel):
    monto: float = Field(gt=0)
    moneda: Literal["usd", "ars", "todas"] = "todas"
    horizonte: Literal["corto", "medio", "largo"] = "medio"
    perfil: Literal["conservador", "moderado", "agresivo"] = "moderado"
    cobertura: Literal["devaluacion", "inflacion", "tasa-pesos", "mixta"] | None = None
    mix: dict[str, float] | None = None
    """Ya parseado (no el string 'usd_hard=60,cer=40' de la CLI): el frontend arma el objeto
    directo, así que no hace falta reimplementar el parseo de texto acá."""
    n_total: int = Field(default=15, gt=0)
    min_rend: float = 0.0
    pago_mensual: bool = True
```
Validar en el modelo (o al entrar al servicio) que si `mix` viene, sus claves están en
`MONEDA_SEGMENTO` (equivalente al `sys.exit` del CLI, acá un 422). Los `max_emisor`/`max_sector`/
`max_soberano` **no se agregan** como override del CLI: la ficha no los menciona como parte del
input de F-019 (sólo monto/moneda/objetivo/perfil/horizonte) — si el perfil ya los trae, no hace
falta un override manual en esta feature. Si al implementar se ve que hace falta, frenar y
reportarlo en vez de agregarlo por cuenta propia.

### `app/armado/motor.py` — el port de las cuatro funciones

Firmas (sobre `Sequence[EspecieUniverso]` en vez de `DataFrame`, y sobre `dict[str, RiesgoDeEspecie]`
en vez de columnas `clave_riesgo`/`es_soberano`):

```python
def resolver_mix(params: ParametrosArmado) -> tuple[dict[str, float], str, list[Alerta]]
def filtrar_por_moneda(mix: dict[str, float], moneda: str) -> tuple[dict[str, float], list[Alerta]]
def candidatos_del_segmento(
    universo: Sequence[EspecieUniverso], segmento: str, perfil: Perfil, params: ParametrosArmado,
) -> list[EspecieUniverso]     # ya ordenados por rendimiento descendente
def elegir_siguiente(
    candidatos: list[EspecieUniverso], ya_elegidos: list[EspecieUniverso],
    riesgos: dict[str, RiesgoDeEspecie], peso_acumulado: dict[str, float],
    peso_posicion: float, perfil: Perfil, peso_sector: dict[str, float],
    sectores_presentes: set[str],
) -> EspecieUniverso | None
def armar(
    universo: Sequence[EspecieUniverso], mix: dict[str, float], perfil: Perfil,
    perfil_nombre: str, params: ParametrosArmado, riesgos: dict[str, RiesgoDeEspecie],
) -> ResultadoArmado
```

**El criterio de reparto sectorial nuevo, adentro de `elegir_siguiente`:** entre los candidatos
viables (los que no rompen tope de emisor/soberano/sector), si hay más de uno dentro de la
`BANDA_RENDIMIENTO` del mejor, preferir el de un sector que **todavía no esté en
`sectores_presentes`** (el set de sectores ya elegidos en la cartera hasta ahora, vía
`sector_computable`). Esto se combina con el desempate existente por calendario (mismo criterio de
banda, "no resignar tasa por ordenar"): el orden de prioridad dentro de la banda es 1) sector nuevo,
2) meses de cobro nuevos, 3) mejor rendimiento — documentar la decisión final en el código porque
el plan.md no especifica el orden exacto entre calendario y sector, sólo que los dos existen.

**Percentil de liquidez** (`candidatos_del_segmento`, filtro `percentil_liquidez`): el motor usa
`pd.Series.quantile(q)` con interpolación lineal (el default de pandas). Sin pandas, replicar
exactamente esa fórmula — **no** usar `statistics.quantiles` de la stdlib, que por default usa un
método distinto (exclusive/N+1) y daría un corte de liquidez diferente, rompiendo la paridad:
```python
def percentil_lineal(valores: list[float], q: float) -> float:
    ordenados = sorted(valores)
    n = len(ordenados)
    if n == 1:
        return ordenados[0]
    pos = q * (n - 1)
    lo, hi = int(pos), min(int(pos) + 1, n - 1)
    frac = pos - lo
    return ordenados[lo] + (ordenados[hi] - ordenados[lo]) * frac
```
Verificar contra `pandas.Series(valores).quantile(q)` en un test unitario antes de usarlo en
`candidatos_del_segmento` — si no coincide bit a bit en varios casos, frenar y reportar, no ajustar
a ojo.

**Desempate por calendario (`meses_de`/`pago_mensual`):** el motor usa
`cupones.meses_cubiertos(flujos, [ticker], hoy)` de `tools/cupones.py`, que el backend no tiene
portado. Antes de escribir un parser de cronograma nuevo, revisar si
`app/calendario/grilla.py::armar_calendario()`/`ventana()` (ya usado por F-015/F-016) puede dar,
para un ticker puntual, el conjunto de meses en los próximos 12 en que paga renta —
`Calendario.meses[i].instrumentos` trae `InstrumentoDelMes` por ticker con sus `fechas`. Si arma
sin fricción, reusarlo (una sola llamada a `armar_calendario` antes de entrar a `armar()`, indexada
por ticker). **Si no cierra limpio o exige un fetch adicional caro por candidato**, el criterio de
calendario puede degradarse a "no aplicar el desempate por meses" (dejar sólo sector + rendimiento)
— ningún GWT de F-019 prueba explícitamente el desempate por calendario, así que es la parte con
más margen para simplificar si hace falta, pero **declararlo en el reporte final**, no en silencio.

**`armar()`** — mismo algoritmo del motor (líneas 228-314): segmentos del mix ordenados de menor a
mayor peso, `n_objetivo = max(1, round(n_total * pct/100))`, acumuladores globales
`peso_acumulado`/`peso_sector`/`sectores_presentes`/`meses_ya_cubiertos`, alerta cuando un segmento
se queda sin candidatos o sin cupo, reescalado final a 100 % si algún segmento quedó vacío,
chequeo post-hoc de concentración. Agregar al final el **chequeo de `min_sectores`**: contar
`len(sectores_presentes)` (excluyendo `None` de `sector_computable`, que ya excluye Soberano/
Subsoberano de la cuenta salvo que se los considere "sector presente" — **atención**: el GWT-4 dice
*"sin contar Soberano ni Subsoberano, que ya los acota el tope soberano"*, mientras que el
docstring de `app/concentracion/perfiles.py` dice que un soberano *sí* cuenta como sector presente
para `min_sectores` en la lógica de F-020. **Son dos textos que no dicen lo mismo** — el de F-019
(plan.md, GWT literal) excluye Soberano/Subsoberano del conteo; el de F-020 (perfiles.py,
comentado como "es la exención del tope, no de la existencia") los incluye. Seguir el GWT literal
de **esta** ficha (F-019: no contar Soberano/Subsoberano) porque es el criterio de aceptación
explícito de esta feature; si eso diverge del comportamiento de F-020 en su propio panel, declararlo
en el reporte como una divergencia conocida entre las dos features, no resolverla por cuenta propia
tocando `app/concentracion/`.

Si `len(sectores_presentes)` (según el criterio de arriba) `< perfil["min_sectores"]`: agregar una
alerta nombrando el mínimo incumplido y cuántos sectores hay, **sin bloquear ni rellenar** (GWT-5).

### `ResultadoArmado` (dataclass, resultado de `armar()`)
```python
@dataclass(frozen=True, slots=True)
class PosicionArmada:
    ticker: str
    pct_cartera: float
    monto: float

@dataclass(frozen=True, slots=True)
class ResultadoArmado:
    posiciones: list[PosicionArmada]
    alertas: list[Alerta]
    mix_aplicado: dict[str, float]
    origen_mix: str
    perfil: str
    sectores_presentes: int
    min_sectores: int
```
`resumir()` (por naturaleza/segmento/emisor/sector, líneas 346-398 del motor) **no hace falta
portarlo para esta feature**: F-022 ya calcula rendimiento por naturaleza y plazo promedio en el
frontend sobre la cartera resultante, cualquiera sea su origen (manual o armada). No duplicar esa
matemática acá.

## Endpoint — `app/api/v1/armado.py` (el stub de la base común, F-019 lo completa)

```python
@router.post("", summary="Precarga una cartera de arranque a partir del mandato del cliente")
async def armado_asistido(
    conn: Annotated[object, Depends(get_db)],
    entrada: ParametrosArmado,
) -> dict[str, object]:
    saneado = await sanear_universo(conn)
    riesgos = derivar_riesgo(saneado.especies)
    mix, origen_mix, alertas_mix = resolver_mix(entrada)
    mix, alertas_moneda = filtrar_por_moneda(mix, entrada.moneda)
    resultado = armar(saneado.especies, mix, PERFILES[entrada.perfil], entrada.perfil, entrada, riesgos)
    return resultado.como_dict()
```
Siempre 200 — igual que `/concentracion`: una cartera parcial o con `min_sectores` incumplido es un
resultado válido del dominio, no un error HTTP. **`router.py` no se toca**: el router ya está
montado vacío por la base común.

## Frontend

### `frontend/src/features/armador/store/carteraStore.tsx`
Agregar una acción nueva al reducer (no reusar `alternarPapel` en loop — pisa pesos):
```ts
cargarCartera: (posiciones: PosicionArmador[]) => void
```
Reemplaza `pos` entero por las posiciones recibidas (con `clase: 'renta_fija'`, `peso: pct_cartera`
de cada `PosicionArmada`). No toca `montoTotal`, `selMes` ni `filtros`.

### `frontend/src/features/armador/hooks/useArmadoAsistido.ts` (nuevo)
`useMutation` (mismo criterio que F-025: no hay precedente en el repo, es parte de
`@tanstack/react-query` ya instalado) contra `POST /api/v1/armado`, body = los parámetros del
mandato. `onSuccess` llama `cargarCartera(resultado.posiciones)` — no invalida ninguna query de
mercado, esto no cambia el universo.

### `frontend/src/features/armador/components/PanelArmadoAsistido.tsx`
Reemplaza el stub. Formulario chico con los cinco parámetros del mandato (monto, moneda, objetivo
de cobertura, perfil, horizonte) — sin mockup dedicado en el design-system; el más cercano es A1
(Mandato del cliente), pero esa sección completa (chips de restricciones, "Filtrar universo por
mandato") **no** es esta feature: acá sólo entran los cinco campos que `ParametrosArmado` pide.
Botón "Armar cartera asistida" dispara la mutación. Mostrar las alertas de la respuesta (mix
degradado, segmento sin candidatos, `min_sectores` incumplido) igual que `AlertasCalendario` ya
muestra las suyas — mismo tratamiento visual, no inventar un tercero.

**Reemplazar, no fusionar**: si ya hay posiciones cargadas en `CarteraEditable` al pedir el armado
asistido, `cargarCartera` las reemplaza enteras (es "un punto de partida", no un agregado — así lo
dice la ficha). No pedir confirmación adicional: el asesor sigue pudiendo editar después.

## Reglas del dominio que esto NO puede violar

1. **Regla 1 — nunca inventar.** Cartera parcial cuando el universo no alcanza; nunca se rellena
   con otra naturaleza para completar el mix o el mínimo sectorial.
2. **Regla 4 — el riesgo soberano se agrupa aparte.** `clave_riesgo`/`SOBERANO_AR`, vía
   `derivar_riesgo`, no una concentración por prefijo.
3. **Regla 8 — nunca proponer sin nombrar el riesgo.** El chequeo de `min_sectores` incumplido y
   los topes excedidos post-reponderación se declaran con alerta explícita, no en silencio.
4. **Regla 11 — nada se supone.** El desempate por calendario, si se implementa, sólo actúa sobre
   tickers con cronograma real; nunca se infiere un mes de cobro.

## PROHIBIDO tocar

- `app/concentracion/perfiles.py`, `app/concentracion/riesgo.py` — se importan, no se editan ni se
  duplican sus constantes/funciones.
- `app/concentracion/servicio.py`, `app/api/v1/concentracion.py` — de F-020, no se tocan (salvo la
  alternativa documentada de reusar `evaluar_concentracion`, que es leer/llamar, no editar).
- `app/universo/**` — se consume `sanear_universo`, no se edita.
- `app/api/v1/router.py` — ya está montado por la base común; **no volver a tocarlo**.
- `frontend/src/features/armador/ArmadorPage.tsx`, `PanelesDeLaCartera.tsx`,
  `frontend/src/lib/api/queryKeys.ts` — congelados esta tanda. El stub `PanelArmadoAsistido.tsx` es
  el único archivo de montaje que se edita.
- `frontend/src/features/armador/components/CarteraEditable.tsx` — F-025 puede estar tocándolo en
  paralelo (input de lámina); F-019 no necesita editarlo, la tabla renderiza sola lo que
  `cargarCartera` deja en el store.
- `tools/armar_cartera.py` — es la referencia de paridad, se lee, no se edita.
- Nada de `git add` / `git commit`: el cierre de tanda lo hace otro.

## Test Strategy

### `backend/tests/test_armado_paridad_motor.py` (nuevo, patrón de `test_concentracion_paridad_motor.py`)
- Semilla fija, sobre `data/output/universo_consolidado.xlsx` (mismo consolidado que usa la
  paridad de concentración).
- **15 escenarios** (ver nota GWT arriba) comparando `armar()` del servicio contra
  `tools/armar_cartera.py::armar()` corrido en proceso sobre el mismo universo — mismas
  posiciones, mismos pesos, mismas alertas de concentración (dentro de la tolerancia de redondeo
  ya usada en `test_concentracion_paridad_motor.py`).
- Test aislado del percentil: `percentil_lineal` contra `pandas.Series.quantile()` en varios
  tamaños de muestra (par, impar, 1 elemento).

### `backend/tests/test_armado_min_sectores.py` (nuevo)
- Universo con candidatos comparables de 6 sectores, perfil `conservador` (`min_sectores=4`) →
  cartera con ≥4 sectores distintos, sin contar Soberano/Subsoberano (GWT-4).
- Universo elegible con un solo sector corporativo → cartera sale con ese sector y alerta nombrando
  el mínimo incumplido, sin bloquear (GWT-5).

### `backend/tests/test_armado_endpoint.py` (nuevo, patrón de `test_concentracion_api.py` si existe,
si no, patrón de cualquier endpoint POST del paquete)
- 200 con parámetros válidos, cartera parcial declarada cuando el universo no alcanza (GWT-3).
- `mix` con clave inválida → 422.
- `monto <= 0` → 422.

### Frontend
- `carteraStore.test.tsx`: `cargarCartera` reemplaza `pos` entero.
- `useArmadoAsistido.test.ts`: éxito llama `cargarCartera` con las posiciones mapeadas.
- `PanelArmadoAsistido.test.tsx`: envía los cinco parámetros, muestra alertas de la respuesta.

## Comandos de verificación

```
Backend (cd /Users/jeroniki/Documents/Github/10-Swaper/backend):
  source venv/bin/activate
  python -m pytest tests/ -x -q
  ruff check . && ruff format --check .

Frontend (cd /Users/jeroniki/Documents/Github/10-Swaper/frontend):
  npx vitest run src/features/armador
  npx tsc -b
  npm run lint
```

No correr la suite completa del frontend: F-022 y F-025 trabajan en paralelo sobre otros archivos
de la misma carpeta. La corrida completa la hace el cierre de la tanda.

## Al terminar, reportar

- Cuántos de los 15 escenarios de paridad se construyeron y si los 15 coinciden con el motor.
- Si `percentil_lineal` coincidió con `pandas.quantile` sin ajustes.
- Cómo quedó resuelto el desempate por calendario (portado, simplificado, u omitido) y por qué.
- Cómo quedó resuelto el conteo de `min_sectores` frente a la divergencia de texto entre el GWT de
  F-019 y el docstring de `app/concentracion/perfiles.py` (Soberano cuenta o no).
- Archivos creados/modificados y el resultado textual de los comandos.
- Cualquier punto donde el plan no cerró contra la realidad del código — frenar esa parte y
  reportarla, no improvisar.
