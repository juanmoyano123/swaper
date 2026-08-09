# Feature Plan: F-025 — Carga asistida de lámina con trazabilidad

## Overview
- **Source**: spec en `claude-docs/planning/plan.md` (sección "#### F-025", líneas ~1232–1268) ·
  design-system no dibuja este mockup (sólo el consumo, ver más abajo) ·
  `claude-docs/planning/plan-ejecucion-tandas.md` (tanda 10, fila 53): "F-025 escribe lo que F-024
  lee"
- **Complexity**: M — el mecanismo de herencia/conflicto ya existe (`app/condiciones/resolucion.py`)
  y hay que reusarlo con cuidado; el riesgo real es de persistencia, no de lógica
- **Modo**: plan prescriptivo. Si algo no cierra contra la realidad del código, **FRENAR y
  reportar**, no improvisar.

## Qué es

El asesor ve en `CarteraEditable.tsx` una posición marcada `lámina no informada` (F-024). Tipea el
valor ahí mismo, sin salir del armador. Ese valor:
1. Se guarda en `condiciones_emision` con `lamina_origen = 'carga manual'` y `lamina_fecha` = hoy.
2. Se propaga a las demás especies de la misma emisión (AL30/AL30D/AL30C son el mismo bono — la
   lámina es atributo de la emisión) con origen `herencia de <ticker>`.
3. Queda visible para todos los asesores: `condiciones_emision` no tiene RLS por usuario.
4. Si contradice un valor ya existente de otro origen, se reporta el conflicto con los dos valores
   y no se elige ninguno (mismo mecanismo de F-009).

## GWT (criterios de aceptación, literales del plan)

```
GIVEN una posición marcada como lámina no informada
WHEN el asesor tipea la lámina en la misma pantalla
THEN la posición se recalcula con redondeo y el valor queda guardado con origen "carga manual" y la
     fecha

GIVEN una lámina cargada a mano para la especie D de una emisión
WHEN se consultan las otras especies de la misma emisión
THEN heredan la lámina con el origen trazado a la carga manual original

GIVEN una lámina cargada por el asesor A
WHEN el asesor B abre una cartera con esa emisión
THEN ve la lámina cargada, porque condiciones_emision es compartida

GIVEN una lámina cargada a mano que contradice una ya existente de otro origen
WHEN se guarda
THEN se reporta el conflicto con los dos valores y sus orígenes, y el sistema no elige uno
```

## Lo que ya existe y hay que reusar — no reescribir

- `app/condiciones/resolucion.py::resolver(filas: Sequence[Condiciones]) -> Resolucion` — función
  pura. Recibe **sólo valores declarados** (nunca heredados) por raíz de emisión y campo; si hay
  más de un valor distinto declarado para el mismo campo dentro de la misma raíz → `Conflicto`,
  vacía el campo en **todas** las especies en pugna y no elige; si hay exactamente uno → los demás
  lo heredan con origen `f"{PREFIJO_HERENCIA} {donante}"` (`PREFIJO_HERENCIA = "herencia de"`).
- `app/condiciones/semilla.py` — `Valor(valor, origen, fecha)`, `Condiciones(ticker, valores: dict[str, Valor])`,
  `CAMPOS = ("ley", "moneda_pago", "lamina", "calificacion", "sector", "underlying")`,
  `CAMPOS_NUMERICOS = frozenset({"lamina"})`.
- `app/ingesta/raiz.py::raiz_emision(ticker: str) -> str` — MR46O/MR46D/MR46C → MR46 (recorta la
  última letra sólo si es O/D/C y el ticker tiene 4+ caracteres).
- `app/ingesta/alertas.py::condiciones_en_conflicto(campo, raiz, valores, **detalle) -> Alerta`
  (código `condiciones_en_conflicto`) — ya la usa `resolver()` internamente.

## Lo que NO se reusa tal cual — el punto crítico de esta feature

**`app/condiciones/persistencia.py::persistir_semilla()` / `sql_upsert()` escriben la fila
ENTERA**: `_tupla(fila)` recorre los 6 `CAMPOS` y para cualquiera que no esté en `fila.valores`
escribe `(None, None, None)`. Está bien para la siembra completa (las 823 filas siempre traen los
6 campos, aunque sea vacíos), pero **acá se está corrigiendo un solo campo (`lamina`) de un
ticker**. Si se arma un `Condiciones(ticker, valores={"lamina": Valor(...)})` con sólo ese campo y
se llama a `sql_upsert()`/`persistir_semilla()`, el `ON CONFLICT DO UPDATE` **pisa con NULL** `ley`,
`moneda_pago`, `calificacion`, `sector` y `underlying` de esa fila. Sería borrar dato curado real
para escribir una lámina. **Prohibido llamar a `persistir_semilla` o `sql_upsert()` desde esta
feature.**

**La escritura correcta es un UPDATE acotado a las tres columnas de lámina**, nuevo, en
`app/condiciones/`:
```sql
UPDATE public.condiciones_emision
SET lamina = $1, lamina_origen = $2, lamina_fecha = $3, actualizado_en = now()
WHERE ticker = $4
```
(o `NULL, NULL, NULL` cuando `resolver()` decide vaciar por conflicto). Nunca tocar las otras 15
columnas de triplete.

## Diseño del endpoint y del flujo

### 1. `app/condiciones/carga_manual.py` (nuevo módulo, backend)

```python
ORIGEN_CARGA_MANUAL = "carga manual"

async def cargar_lamina_manual(conn, ticker: str, valor: float, hoy: date) -> ResultadoCargaManual
```

Pasos, todo dentro de una sola `conn.transaction()`:

1. **Encontrar el grupo de la emisión sin fetchear las 823 filas.** `raiz = raiz_emision(ticker)`.
   Los únicos candidatos posibles son `raiz`, `raiz+"O"`, `raiz+"D"`, `raiz+"C"` (el propio dominio
   de `raiz_emision`: sólo esas cuatro formas colapsan a la misma raíz). Un solo
   `SELECT ticker, ley, ley_origen, ley_fecha, moneda_pago, ..., lamina, lamina_origen,
   lamina_fecha, ..., underlying, underlying_origen, underlying_fecha FROM condiciones_emision
   WHERE ticker = ANY($1)` con esos 4 candidatos (usar `COLUMNAS` de `persistencia.py` para no
   listar las columnas a mano). Si `ticker` mismo no aparece en el resultado, la fila no existe
   todavía en `condiciones_emision` — **crearla implícitamente** (INSERT con sólo `ticker` +
   `lamina*`, el resto NULL; no es esta feature la que decide llenar los otros campos).
2. **Reconstruir sólo lo declarado, nunca lo heredado**, para cada fila del grupo: para cada campo
   de `CAMPOS`, si `<campo>_origen` es `NULL` o empieza con `PREFIJO_HERENCIA` ("herencia de"), esa
   fila NO declara ese campo (no entra en su `Condiciones.valores`); si tiene cualquier otro origen
   no nulo (incluida una carga manual anterior), sí entra. Esto es necesario para que `resolver()`
   no confunda "lo que esta fila heredó la vez pasada" con "lo que esta fila declara ahora": si se
   incluyera lo heredado como declarado, dos especies que heredaron el mismo valor de un tercero
   generarían un falso conflicto entre ellas.
3. **Inyectar la carga manual**: en la `Condiciones` del `ticker` recibido, fijar
   `valores["lamina"] = Valor(valor=valor, origen=ORIGEN_CARGA_MANUAL, fecha=hoy)` — pisa lo que
   ese ticker declarara antes para `lamina` (si venía de la semilla o de una carga manual previa;
   es exactamente la corrección que el asesor está pidiendo).
4. **`resolucion = resolver([Condiciones para cada ticker del grupo])`.** El campo `lamina` es el
   único que puede moverse (los otros 5 campos, si están, quedan intactos en la salida porque
   `resolver()` no toca lo que no cambia; igual sólo se van a **escribir** las tres columnas de
   lámina, así que no importa qué diga la resolución de los otros campos — no se persisten).
5. **Persistir sólo `lamina`** con el UPDATE acotado del punto anterior, una fila por ticker del
   grupo, dentro de la transacción:
   - Si `resolucion.conflictos` tiene una entrada para `campo == "lamina"`: escribir
     `NULL, NULL, NULL` para cada ticker del grupo que declaraba lámina (los que están en
     `conflicto.valores`), **no** escribir nada para los que no declaraban (ya estaban en NULL o
     heredaban de alguien que ahora quedó vacío — su lectura del universo ya lo reflejará solo).
   - Si no hay conflicto: escribir el triplete resuelto (`valor`, `origen`, `fecha`) de `lamina`
     para cada ticker del grupo que tiene una entrada de `lamina` en su `Condiciones` resuelta
     (el declarante y los que heredaron).
6. Devolver un resultado con: el ticker, el valor guardado (o `None` si hubo conflicto), y si hubo
   conflicto → el `Conflicto` tal cual lo devuelve `resolver()` (`campo`, `raiz`, `valores` con
   ticker→valor en pugna) para que el endpoint lo traduzca a alerta con los dos orígenes.

**Validación antes de tocar la base**: `valor` tiene que ser numérico y `> 0` (una lámina de 0 o
negativa no tiene sentido físico) — rechazar con 422 antes de abrir la transacción, no dejar que
Pydantic lo intente convertir solo (usar `Annotated[float, Field(gt=0)]`).

### 2. Endpoint — `app/api/v1/condiciones.py` (archivo compartido, un solo dueño esta tanda)

Agregar, sin tocar los tres endpoints existentes ni el router raíz:

```python
class CargaManualLamina(BaseModel):
    valor: Annotated[float, Field(gt=0)]

@router.post(
    "/{ticker}/lamina",
    summary="Carga manual de la lámina de una especie, con trazabilidad y propagación",
    responses={409: {"description": "La lámina cargada contradice un valor de otro origen"},
               503: {"description": "La base de datos no está disponible"}},
)
async def cargar_lamina(
    ticker: str,
    cuerpo: CargaManualLamina,
    conn: Annotated[object, Depends(get_db)],
) -> dict[str, object]:
    ...
```

Comportamiento HTTP: **200** con el resultado cuando se resuelve sin conflicto (trae `guardado:
true`, el triplete final, y qué otros tickers heredaron). **409** cuando `resolver()` detecta
conflicto — cuerpo con `guardado: false`, `conflicto: {campo: "lamina", emision: raiz, valores:
{ticker_a: valor_a, ticker_b: valor_b}}` (mismo shape que `Conflicto.como_dict()`) para que el
frontend pueda mostrar los dos valores y sus orígenes tal cual. No es un error de servidor: es un
resultado válido del dominio, por eso 409 y no 500, y por eso el cuerpo es informativo, no un
`detail` de FastAPI genérico.

`hoy` se saca de `date.today()` en el endpoint (no en el módulo puro, para que sea testeable
pasando una fecha fija).

## Frontend

### 3. `frontend/src/features/armador/hooks/useCargarLamina.ts` (nuevo)

`useMutation` de `@tanstack/react-query` (no hay precedente de `useMutation` en el repo — es parte
de la librería ya instalada, no una dependencia nueva). Firma:

```ts
export function useCargarLamina() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: { ticker: string; valor: number }) =>
      apiFetch(`/api/v1/condiciones/${encodeURIComponent(input.ticker)}/lamina`,
        esquemaResultadoCarga, { method: 'POST', headers: {...}, body: JSON.stringify({ valor: input.valor }) }),
    onSuccess: () => {
      // useEspeciesUniverso define su clave inline como ['mercado','universo','todas']
      // (no está en queryKeys.ts — archivo congelado esta tanda). Invalidar esa clave exacta.
      queryClient.invalidateQueries({ queryKey: ['mercado', 'universo', 'todas'] })
    },
  })
}
```

`apiFetch` no tira en 409: verificar en `lib/api/client.ts` si status ≥ 400 no-200 lanza una
excepción tipada o no — si `apiFetch` está pensado sólo para 2xx, esta llamada puede necesitar un
fetch más directo para poder leer el cuerpo del 409 en vez de recibir sólo una excepción genérica.
Revisar el archivo antes de decidir; si `apiFetch` no sirve para leer un cuerpo de error, escribir
la llamada a mano con el mismo patrón de auth (token de `supabase.auth.getSession()`) que usa
`apiFetch`, sin duplicar toda su lógica de reintentos si la tiene.

Esquema de respuesta (`lib/schemaCondiciones.ts`, nuevo, o agregar a `lib/schema.ts` si ya hay un
lugar natural — decidir en la implementación, no crear un tercer archivo de esquemas sin necesidad):
zod para `{ guardado: boolean; ticker: string; lamina?: number; conflicto?: {...} }`.

### 4. `frontend/src/features/armador/components/CarteraEditable.tsx`

En el `<span>` que hoy dice literal `lámina no informada` (color `--ac2`, dentro de `FilaCartera`):
reemplazarlo por un input inline chico (número, sin flechas, mismo tratamiento visual que los
demás inputs numéricos de la fila) + botón/Enter para confirmar. Mientras la mutación está en
curso, deshabilitar el input. En éxito, no hace falta manejar el estado local: la invalidación de
`useEspeciesUniverso` hace que `especie.lamina` deje de ser `null` y la fila vuelve a su render
normal (con `· lám. N`) sola. En conflicto (409), mostrar el mensaje con los dos valores y orígenes
en el lugar del input (no un alert del navegador — está prohibido disparar diálogos nativos), y
dejar el input disponible para reintentar con otro valor.

No tocar `GRID_FILA` ni la estructura de columnas: el input reemplaza el contenido del `<span>`
existente, no agrega una columna.

## Reglas del dominio que esto NO puede violar

1. **Regla 1 — nunca inventar.** Si el grupo de la emisión no existe todavía en
   `condiciones_emision`, se crea la fila con sólo lo que el asesor tipeó; no se completan los
   otros cinco campos con nada.
2. **F-009 — el sistema no elige entre dos orígenes en conflicto.** Ante conflicto, se vacía y se
   reporta con los dos valores y sus orígenes — nunca se prioriza "carga manual" sobre el curado ni
   al revés.
3. **La lámina es de la emisión, no de la especie** — por eso se propaga por `raiz_emision`, nunca
   por emisor (el docstring de `resolucion.py` ya midió que por emisor entraría en conflicto en
   decenas de casos).
4. **Trazabilidad completa siempre**: nunca se escribe `lamina` sin `lamina_origen` y
   `lamina_fecha` a la vez (lo exige el CHECK `lamina_trazable` de la migración; que el UPDATE
   acotado los escriba siempre los tres juntos, nunca uno solo).

## PROHIBIDO tocar

- `app/condiciones/persistencia.py::sql_upsert()` / `persistir_semilla()` — no se editan ni se
  llaman desde esta feature (ver la sección crítica arriba). Si hace falta un helper compartido,
  se agrega una función **nueva** al lado, no se modifica la existente (la sigue usando `sembrar`).
- `app/condiciones/resolucion.py` — se importa `resolver`, `PREFIJO_HERENCIA`, `Conflicto`, no se
  edita.
- `app/condiciones/semilla.py` — se importan `CAMPOS`, `Valor`, `Condiciones`, no se edita.
- `app/api/v1/router.py` — no hace falta: el endpoint cuelga de `condiciones.router`, ya montado.
- `app/universo/**`, `frontend/src/features/armador/store/carteraStore.tsx`,
  `frontend/src/features/armador/ArmadorPage.tsx`, `PanelesDeLaCartera.tsx`,
  `frontend/src/lib/api/queryKeys.ts` — congelados/de otras features esta tanda.
- `frontend/src/features/instrumento/**` — la ficha (F-039) sólo se mira como referencia.
- Nada de `git add` / `git commit`: el cierre de tanda lo hace otro.

## Test Strategy

### Backend — `backend/tests/test_condiciones_carga_manual.py` (nuevo)
- Emisión sin lámina en ninguna especie → cargar en AL30 → AL30 queda con
  `lamina_origen='carga manual'`, AL30D/AL30C (si existen en la fixture) heredan con
  `origen='herencia de AL30'` y la misma fecha.
- Emisión con lámina previa de otro origen igual a la nueva → no hay conflicto (mismo valor), se
  reescribe con origen `carga manual` igual (es una re-declaración, no una contradicción — decidir
  y documentar en el reporte si "igual valor, distinto origen" cuenta como conflicto según
  `resolver()`: por código, `distintos = {v.valor for v in declarados.values()}` compara sólo el
  `.valor`, así que dos orígenes con el mismo número **no** son conflicto).
- Emisión con lámina previa **distinta** de otro origen → 409, cuerpo con los dos valores
  (`carga manual` vs el origen anterior) y ningún `lamina*` cambia en la base (releer y comparar).
- Ticker sin fila en `condiciones_emision` → se crea con sólo el triplete de lámina, resto NULL.
- **No se pisan los otros 5 campos**: fixture con `ley='Ley N.Y.'` ya declarada en la fila →
  después de cargar la lámina, `ley` y `ley_origen` siguen intactos (éste es el test que habría
  fallado si se hubiera reusado `persistir_semilla` a ciegas).
- `valor <= 0` → 422, nada se escribe.
- Validación de que el helper de candidatos usa exactamente `{raiz, raiz+O, raiz+D, raiz+C}` y no
  un `LIKE` que capture tickers de otra emisión con el mismo prefijo.

### Frontend — `frontend/src/features/armador/__tests__/useCargarLamina.test.ts` y ajuste de
`CarteraEditable.test.tsx`
- Mock de fetch: éxito → invalida la query de universo (mock de `queryClient.invalidateQueries` o
  verificar refetch).
- Mock de fetch: 409 → el hook expone el conflicto (no lanza una excepción no manejada).
- `CarteraEditable`: fila con `lamina: null` muestra el input; tipear y confirmar dispara la
  mutación con el ticker y el valor correctos.

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

No correr la suite completa del frontend ni del backend fuera de lo propio: F-019 y F-022 trabajan
en paralelo. La corrida completa la hace el cierre de la tanda.

## Al terminar, reportar

- Si `apiFetch` sirve para leer el cuerpo de un 409 o hubo que escribir la llamada a mano, y por
  qué.
- Confirmación explícita de que el test "no se pisan los otros 5 campos" pasa.
- Cómo se resolvió "mismo valor, distinto origen" (¿conflicto o no?) y por qué, con el comportamiento
  real de `resolver()` verificado.
- Archivos creados/modificados y el resultado textual de los comandos.
- Cualquier punto donde el plan no cerró contra la realidad del código — frenar esa parte y
  reportarla, no improvisar.
