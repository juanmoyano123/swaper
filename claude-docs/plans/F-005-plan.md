# Feature Plan: F-005 — Parser del informe diario de IAMC

## Overview

- **Source:** `claude-docs/planning/plan.md` (ficha F-005, líneas 303–340) + base común de ingesta
  en `backend/app/ingesta/` + **estudio empírico del PDF real**
  `fuentes/iamc-deuda-corporativa-2026-08-05.pdf` (versionado en git — los worktrees lo tienen),
  hecho con pdfplumber el 06/08/2026. Todo lo que este plan afirma sobre el layout está medido
  sobre ese archivo, no supuesto.
- **Complejidad:** L (la spec le asigna esfuerzo 8, el doble que F-004/F-006, y confianza 50 %).
- **Estimación:** 2–3 días. La mecánica de extracción está verificada (ver abajo); el costo está
  en la robustez del contrato de secciones y en los tests.
- **Depende de:** F-001 (terminada). **Habilita:** F-007 (consolidador), F-031.
- **Branch:** `feature/F-005`, un solo commit al cierre.
- **Decisión del usuario (05/08/2026):** el informe **se sube a mano**. No hay descarga automática
  que construir: esta feature expone un endpoint de subida del PDF y el parser.
- **Ejecución en paralelo con F-004 y F-006:** no se toca ningún archivo compartido. Todo lo nuevo
  vive en `app/ingesta/iamc/` y las rutas van únicamente en `app/api/v1/iamc.py`, que ya existe y
  ya está montado.

### Anatomía verificada del PDF (muestra del 05/08/2026)

Es un export de Power BI: 20 páginas apaisadas de 996×576 pt. Cada página lleva en su segunda
línea de texto un **título de sección con la fecha del informe** (`DEUDA CORPORATIVA EN USD - LEY
NY 05-Aug-26`). Secciones encontradas, con su conteo real de filas de datos:

| Título (sin la fecha) | Páginas | Filas | Columnas | Ley / moneda de pago |
|---|---|---|---|---|
| `DEUDA CORPORATIVA EN USD - LEY NY` | 1–2 | 40 | 23 | del título: Ley N.Y. / USD |
| `SENSIBILIDAD DEUDA CORPORATIVA EN USD - LEY NY` | 3 | — | — | sin datos tabulares (gráfico) |
| `CURVA DEUDA CORPORATIVA EN USD - LEY NY` | 4 | — | — | sin datos tabulares (gráfico) |
| `DEUDA CORPORATIVA EN USD - LEY ARG` | 5–13 | 146 | 23 | del título: Ley Argentina / USD |
| `SENSIBILIDAD DEUDA CORPORATIVA EN USD - LEY ARG` | 14 | — | — | gráfico |
| `CURVA DEUDA CORPORATIVA EN USD - LEY ARG` | 15 | — | — | gráfico |
| `BONOS EN USD - PAGADEROS EN PESOS - TASA FIJA - LEY ARG` | 16–17 | 20 | 22 | del título: Ley Argentina / ARS |
| `BONOS EN USD - PAGADEROS EN PESOS - CUPÓN CERO` | 18 | 17 | 21 | **de columnas explícitas** `Ley` y `Moneda Pago` |
| `CURVA OBLIGACIONES NEGOCIABLES EN USD - PAGADERAS EN PESOS` | 19 | — | — | gráfico |
| `DEUDA CORPORATIVA - EMITIDA Y PAGADERA EN PESOS` | 20 | 11 | 23 | ley: **no declarada en ningún lado** / ARS |

**Total: 234 filas de datos** (la spec estimaba ~260; el número real de la muestra es éste).

Mecánica de extracción verificada con pdfplumber:

1. `page.find_tables()` devuelve 1–2 tablas por página; cuando hay 2, la segunda es un artefacto
   chico del encabezado "Power BI Desktop" (bbox de ~16 pt de alto). **Se elige la tabla de mayor
   área de bbox.**
2. La grilla cruda tiene ~64–67 columnas fantasma (casi todas `None`), pero **las celdas reales
   caen en índices de columna estables dentro de la página**: la fila de headers y las filas de
   datos usan exactamente los mismos índices. Filtrando `None`/`""`, la fila de headers de la
   sección LEY NY tiene exactamente 23 celdas (`Ticker`, `Emisor`, `Monto\nEmitido\nUSD`, …,
   `ADTV 20\nRuedas\nARS`) y cada fila de datos tiene 23 celdas alineadas una a una.
3. **Emisores multilínea generan filas de continuación**: `MCC3O | PECOM SERVICIOS | …` seguida
   (a 1–3 filas de distancia, con filas vacías en el medio) de una fila con **una sola celda no
   vacía, ubicada en el índice de columna del Emisor** (`ENERGIA S.A.U`). La regla de detección es
   posicional, no textual.
4. Basura conocida: una fila con un único glifo `` (ícono de Power BI) en un índice de
   columna que no es el del emisor; filas totalmente vacías; una fila-artefacto con 2 celdas
   (`Ticker` + `ADTV…`) antes de la fila de headers real.
5. Los headers a veces llegan **truncados o partidos** por el ancho de celda: `Fecha\nVencimie`,
   `Estructura\nCup`, `Vencimient\no`. La validación de headers tiene que tolerar truncamiento,
   no exigir igualdad exacta (decisión 4).
6. **Los números vienen en formato anglosajón, no argentino**: coma para miles, punto decimal,
   sufijo `M` de millones, `%` pegado (`1,100M`, `2,064.08M`, `156250.0`, `7.92%`, `-0.93%`,
   `141.62%`). Las fechas vienen `dd-MMM-yy` con meses en inglés (`30-Jun-26`, `05-Aug-26`). Esto
   contradice el supuesto de "números en formato argentino": la normalización se escribe para lo
   que el PDF trae de verdad.
7. En la sección CUPÓN CERO las columnas explícitas traen: `Ley` = `ARG`, `Moneda Emision` =
   `USD`, `Moneda Pago` = `ARS` (coherente con el título "BONOS EN USD - PAGADEROS EN PESOS").

## Implementation Approach

**Parser por catálogo de secciones + mecánica de tabla separada de la interpretación.** Cuatro
capas dentro de `app/ingesta/iamc/`:

1. `secciones.py` — el **catálogo declarativo**: para cada título conocido, sus headers esperados
   en orden, de dónde salen ley y moneda de pago (título o columna), y si es una sección de datos
   o un gráfico que se saltea. Un título que no está en el catálogo **no se parsea: se aborta**.
   Éste es el archivo que se edita el día que IAMC cambie el layout.
2. `tablas.py` — la mecánica pdfplumber pura: elegir la tabla de mayor área, encontrar la fila de
   headers, mapear índice de columna → header, clasificar cada fila (datos / continuación /
   basura conocida / no reconocida). No sabe nada de bonos: entrega filas como listas de celdas
   alineadas a headers.
3. `normalizacion.py` — funciones puras de celda → valor tipado: números anglosajones, fechas
   `dd-MMM-yy`, mapeo de códigos de ley. Un valor que no parsea queda `None` y se reporta — nunca
   se adivina.
4. `parser.py` — la orquestación: recorre páginas, clasifica títulos contra el catálogo, junta
   filas por sección, aplica ley/moneda según lo que la sección declara, arma el `Snapshot` con
   filas por sección y cobertura por campo, y **aborta con `InformeInvalido` ante cualquier
   sección o fila no reconocida, sin devolver filas parciales**.

El endpoint (`app/api/v1/iamc.py`) recibe el PDF como **cuerpo binario crudo**
(`Content-Type: application/pdf`), lo valida, lo guarda en el directorio de config y corre el
parser.

**Alternativas descartadas:**

- *`page.extract_text()` + regex por línea*: descartado. El texto plano parte los emisores
  multilínea de forma ambigua y pega columnas entre sí (verificado: las líneas de texto truncan y
  reordenan celdas). La grilla de `find_tables()` con índices de columna estables es
  estrictamente más confiable, y está medida.
- *`extract_table()` con settings de líneas explícitas afinados a mano*: innecesario — la
  detección por defecto ya alinea headers y datos en los mismos índices (verificado en las 5
  secciones de datos). Afinar settings sería robustez especulativa contra un layout que no es el
  real.
- *Subida multipart (`UploadFile`)*: descartada porque exige `python-multipart`, que **no está
  instalado**, y la regla del encargo es no agregar dependencias. El cuerpo binario crudo hace lo
  mismo con menos piezas (`curl --data-binary`, `fetch` con blob). Si una feature de UI futura
  quiere multipart, esa feature evalúa la dependencia (queda anotado en Riesgos).
- *Derivar la raíz del ticker en F-005*: descartado explícitamente. La ficha dice "atributos por
  raíz de ticker", pero cortar strings de tickers ya produjo 121 tickers inexistentes una vez
  (CLAUDE.md, regla 1). F-005 entrega **el ticker tal como IAMC lo publica**; agrupar por raíz es
  responsabilidad de F-007, que ya declara "por la raíz del ticker" como su propia lógica con su
  propia regla de especies.
- *Persistir filas en la base*: no en F-005. El límite con F-007 es el mismo que en las otras dos
  fuentes: esta feature entrega `ResultadoInforme` en memoria (y el PDF guardado en disco); quien
  escribe tablas es F-007.

## File Structure

### Crear

```
backend/app/ingesta/iamc/__init__.py         Exporta parsear_informe, ResultadoInforme, InformeInvalido
backend/app/ingesta/iamc/secciones.py        Catálogo declarativo de secciones conocidas (títulos, headers, origen de ley/moneda)
backend/app/ingesta/iamc/tablas.py           Mecánica pdfplumber: tabla mayor, headers, clasificación de filas, continuaciones
backend/app/ingesta/iamc/normalizacion.py    Números anglosajones, fechas dd-MMM-yy inglés, mapeo de ley, texto limpio
backend/app/ingesta/iamc/parser.py           Orquestación página→sección→filas, Snapshot, cobertura, aborto InformeInvalido
backend/app/ingesta/iamc/almacen.py          Resolución del directorio de config y guardado del PDF subido
backend/tests/test_iamc_normalizacion.py     Números, fechas, ley, faltantes (GWT-3)
backend/tests/test_iamc_tablas.py            Clasificación de filas con grillas sintéticas (continuaciones, basura, headers truncados)
backend/tests/test_iamc_parser.py            Contra el PDF real de fuentes/ + aborto por sección desconocida (GWT-1, GWT-2)
backend/tests/test_iamc_api.py               Endpoint: validaciones del archivo, subida feliz, 422 de aborto
```

### Modificar

```
backend/app/api/v1/iamc.py                   Agregar POST /iamc/informe (el archivo es propiedad de F-005)
```

**Nada más.** No se toca `router.py`, `config.py` (las variables ya existen), `requirements.txt`,
`pyproject.toml`, ni nada de `app/ingesta/` fuera de `iamc/`.

## Dependency Map

**De la base común (`app/ingesta/`):**

- `snapshot.Snapshot` — tipo de retorno; `filas_por_tramo` con una entrada por sección de datos.
- `alertas.formato_inesperado()` y el modelo `Alerta` — para valores que no parsean y
  discrepancias; **no se define ningún modelo de alerta propio**. No hacen falta códigos nuevos:
  los casos de F-005 son todos `formato_inesperado` o `campo_sin_cobertura` (la cobertura ya lo
  mide) — si durante la implementación apareciera un caso que no calza, se agrega la constante en
  `iamc/parser.py` siguiendo la convención.
- `cobertura.medir_cobertura()` — sobre las filas normalizadas.
- De `http.py` **no se usa nada**: acá no hay red. Ésa es una diferencia deliberada con F-004 y
  F-006.

**De `app/core/`:** `config.get_settings().iamc_directorio` (ya existe, default `"fuentes"`); el
contrato de error uniforme de `errors.py` (los `HTTPException` que lance el endpoint salen con esa
forma sola — no hay nada que hacer).

**Precedente de código:** `tools/merge_condiciones.py` — `MAPA_LEY = {"ARG": "Ley Argentina",
"NY": "Ley N.Y."}` con la regla *"cualquier valor que no esté acá se reporta y no se carga: es
preferible un hueco a un dato mal traducido"*. El mapeo de la columna `Ley` de la sección CUPÓN
CERO usa exactamente esos valores canónicos y esa regla (transcriptos a `iamc/normalizacion.py`;
no se importa desde `tools/`, que es el motor pre-Fase 4).

**Paquetes (ya instalados):** `pdfplumber`. No se agrega ninguna dependencia
(`python-multipart` explícitamente evitado, ver Approach).

## Edge Cases & Technical Decisions

1. **El catálogo de secciones es cerrado y el default es abortar** (GWT-2). `secciones.py`
   declara los cinco títulos de datos y los patrones de las páginas-gráfico (títulos que empiezan
   con `SENSIBILIDAD ` o `CURVA `, que se **reconocen y se saltean** — saltear no es ignorar: son
   parte del layout conocido). Cualquier página cuyo título no matchee ninguna de las dos listas →
   `InformeInvalido` con detalle `{"pagina": n, "titulo": ...}` y **cero filas devueltas**, aunque
   otras secciones ya se hubieran parseado bien. La justificación es la del episodio "Ley
   Inglesa": una sección nueva podría declarar una ley o moneda distinta, y parsear "lo conocido"
   ignorando lo nuevo produciría un universo silenciosamente incompleto con atributos posiblemente
   mal heredados. `InformeInvalido` es una excepción propia del paquete (no hereda de
   `ErrorDeFuente`: esto no es una fuente HTTP caída, es un contrato de layout roto).

2. **Ley y moneda de pago salen de donde la sección las declara — y de ningún otro lado**
   (GWT-1, regla 1 del dominio). Por sección:
   - LEY NY → `ley="Ley N.Y."`, `moneda_pago="USD"`; LEY ARG → `ley="Ley Argentina"`,
     `moneda_pago="USD"`; PAGADEROS EN PESOS - TASA FIJA - LEY ARG → `ley="Ley Argentina"`,
     `moneda_pago="ARS"`. Los tres, del título; los valores canónicos son los de `MAPA_LEY`.
   - CUPÓN CERO → ley y moneda de pago se leen **de las columnas explícitas** `Ley` y
     `Moneda Pago` de cada fila (eso es dato declarado por la fuente, no inferido). El código
     `ARG`/`NY` se traduce con el mapeo canónico; un valor fuera del mapeo → campo `None` +
     alerta `formato_inesperado` con el valor crudo en el detalle (hueco antes que traducción
     inventada). Como el título además declara "PAGADEROS EN PESOS", si la columna `Moneda Pago`
     de una fila difiere de `ARS` se emite alerta ADVERTENCIA con la discrepancia y **se conserva
     el valor de la columna** (el dato por fila es más específico que el rótulo de la sección; la
     discrepancia queda declarada, no resuelta en silencio).
   - EMITIDA Y PAGADERA EN PESOS → `moneda_pago="ARS"` del título; **la ley no está declarada en
     ningún lado del PDF para esta sección** (ni título ni columna — verificado), así que
     `ley=None` para sus 11 filas y el hueco lo cuenta la cobertura. Casi seguro son Ley
     Argentina, y justamente por eso es el caso de manual de la regla 1: "casi seguro" no es un
     dato.
   - **Trazabilidad**: cada fila lleva `seccion` (el título original, sin la fecha). Eso cumple
     "el parser registra de qué sección salió cada valor" — ley y moneda son función de
     (sección, columnas), y la sección viaja con la fila.

3. **Clasificación de filas de la grilla, en este orden** (en `tablas.py`, por página):
   1. Fila de headers: contiene la celda `Ticker` y es la fila con más celdas no vacías de la
      página. Define el mapeo índice de columna → header **de esa página** (se re-deriva por
      página, no se asume que los índices coinciden entre páginas).
   2. Fila de datos: tiene celda en el índice del `Ticker` que matchea `^[A-Z0-9]{4,6}$` y al
      menos la mitad de las celdas esperadas. Se mapea celda a celda por índice; un índice sin
      celda → campo `None`.
   3. Fila de continuación: **exactamente una** celda no vacía, ubicada en el índice de columna
      del `Emisor` → se concatena (con espacio) al emisor de la última fila de datos. Si no hay
      fila de datos previa, es formato inesperado (caso 5).
   4. Basura conocida que se ignora: filas vacías; filas de una sola celda en un índice que no es
      el del emisor cuyo contenido es un glifo de icono (rango Unicode de uso privado, como el
      `` observado) o los artefactos del encabezado (`Power BI Desktop`, el título, la
      fila-artefacto de 2 celdas `Ticker`+`ADTV`).
   5. Cualquier otra fila con 3 o más celdas no vacías que no clasifique como ninguna de las
      anteriores → `InformeInvalido` con detalle (página, índice de fila, primeras celdas). Una
      fila que "parece datos pero no encaja" es el síntoma temprano de un cambio de layout, y el
      contrato de esta feature es fallar ruidosamente, no absorber.

4. **Validación de headers tolerante a truncamiento, estricta en orden y cantidad.** Para cada
   sección el catálogo declara la lista ordenada de headers esperados. La comparación normaliza
   (minúsculas, sin saltos de línea ni caracteres no alfanuméricos) y acepta que **el observado
   sea prefijo del esperado o viceversa** con un mínimo de 4 caracteres (cubre `fechavencimie` vs
   `fechavencimiento`, `estructuracup` vs `estructuracupon`). La cantidad de headers tiene que
   ser exacta (23/22/21/23 según sección) y el matcheo es posicional — `Frecuencia` (cupón) y
   `Frecuencia Pago` (capital) existen a la vez, así que matchear por nombre sin posición sería
   ambiguo. Cualquier desvío → `InformeInvalido` con la columna y lo que se encontró.

5. **Normalización de valores — anglosajona, porque eso es lo que el PDF trae** (hallazgo 6):
   - `_numero("2,064.08M")` → `2_064_080_000.0` (coma de miles fuera, `M` = ×10⁶);
     `_numero("7.92%")` → `7.92` (los porcentajes se entregan en puntos porcentuales, documentado
     en el docstring del campo); `_numero("-0.93%")` → `-0.93`; `_numero("156250.0")` →
     `156250.0`; `_numero("")` / celda ausente → `None`.
   - `_fecha("30-Jun-26")` → `date(2026, 6, 30)` con mapa de meses inglés explícito (sin
     depender del locale del proceso); año de dos dígitos → `20xx`.
   - Un valor que no parsea → `None` + alerta ADVERTENCIA `formato_inesperado` con
     `{"seccion", "ticker", "campo", "valor_crudo"}`. No aborta (GWT-3 pide contabilizar el
     faltante, y un solo valor ilegible no es un cambio de layout), pero tampoco se estima ni se
     copia del día anterior — queda hueco y contado.
   - `0` numérico es dato presente (misma regla que `cobertura._esta_presente`): un volumen de
     `0.00M` es una ON que no operó, no un faltante.

6. **Campos canónicos de la fila normalizada.** Comunes a todas las secciones (con `None` donde
   la sección no trae la columna): `ticker`, `emisor`, `seccion`, `ley`, `moneda_pago`,
   `fecha_informe`, `monto_emitido` (absoluto, en la moneda que el header declara —
   `moneda_monto_emitido` `"USD"`/`"ARS"` según la sección), `fecha_emision`,
   `fecha_vencimiento`, `estructura_cupon`, `indice_cupon` (sólo pesos), `frecuencia_cupon`,
   `proximo_cupon`, `tasa_cupon_vigente`, `current_yield`, `interes_corrido`, `valor_residual`,
   `cuotas_capital`, `frecuencia_pago_capital`, `proximo_pago_capital`, `cierre_ars`,
   `paridad_pct`, `valor_tecnico`, `tir` (YTM), `duracion_modificada` (DM), `convexidad` (CX),
   `vida_promedio` (WAL; la sección de pesos no la publica → `None`),
   `volumen_promedio_20r_ars` (ADTV 20 ruedas), `moneda_emision` (sólo cupón cero). Dos casos con
   origen declarado que no es una celda: en la sección TASA FIJA (22 columnas, sin columna
   `Estructura`) `estructura_cupon="Tasa Fija"` **sale del título**, que lo declara literalmente
   — mismo estatus que la ley; y `fecha_informe` sale del título de la página.
   Como en F-004, las filas son `TypedDict` (dicts en runtime): `medir_cobertura` las consume
   directo y la serialización es trivial.

7. **La fecha del informe se extrae y se verifica.** Se parsea del título de cada página
   (`05-Aug-26`). Si las páginas del mismo PDF declaran fechas distintas → alerta ADVERTENCIA
   (informe ensamblado raro; se usa la de la primera página de datos). La fecha va en cada fila
   (`fecha_informe`), en la respuesta del endpoint y en el nombre del archivo guardado. El
   `Snapshot` usa `demora_declarada_minutos=0` — la vejez del dato de IAMC no se mide en minutos
   de rueda sino por `fecha_informe`, que viaja aparte; declarar una demora en minutos acá sería
   etiquetar mal el dato.

8. **Endpoint de subida: `POST /iamc/informe`, cuerpo binario crudo.** Validaciones en orden:
   - Cuerpo vacío o `Content-Type` distinto de `application/pdf` → 400 (contrato de error
     uniforme).
   - Más de **25 MB** → 413. La muestra pesa 7 MB; 25 da margen 3× sin aceptar cualquier cosa.
     Constante módulo-local con el porqué.
   - Primeros bytes distintos de `%PDF-` → 400 (la extensión no se chequea: no hay filename en un
     cuerpo crudo; el magic number es el dato real).
   - PDF que pdfplumber no puede abrir → 422 con mensaje claro.
   - Sección/fila no reconocida (`InformeInvalido`) → **422** con el detalle en el contrato de
     error, **sin filas devueltas ni persistidas**; el archivo se guarda igual como
     `iamc-rechazado-<timestamp>.pdf` para poder diagnosticar el cambio de layout (guardar el PDF
     no es persistir filas: es evidencia).
   - Éxito → 200 con `{"archivo": ..., "fecha_informe": ..., "snapshot": snapshot.como_dict()}`
     (sin las 234 filas: la respuesta es para ver el estado de la corrida; las filas las consume
     F-007 por función).
   `curl` de referencia (va en el docstring del endpoint):
   `curl -X POST --data-binary @informe.pdf -H 'Content-Type: application/pdf' localhost:8000/api/v1/iamc/informe`

9. **Guardado del PDF** (`almacen.py`). `settings.iamc_directorio` (`"fuentes"`) se resuelve, si
   es relativo, **contra la raíz del repo** (mismo criterio que `ENV_FILE` en `config.py`:
   desde la ubicación del archivo, no desde el cwd, que cambia entre uvicorn/pytest/Docker); un
   path absoluto se usa tal cual. Se crea el directorio si no existe. Nombre:
   `iamc-deuda-corporativa-<fecha_informe ISO>.pdf` — igual convención que la muestra existente.
   Subir dos veces el informe del mismo día **sobreescribe** (idempotente: es el mismo informe;
   versionar subidas repetidas sería inventar un historial que no existe). En tests, el directorio
   se redirige con `monkeypatch.setenv("IAMC_DIRECTORIO", tmp_path)` — por eso la resolución vive
   en una función y no inline.

10. **Snapshot y cobertura.** `Snapshot(fuente="IAMC")`; `filas_por_tramo` con una entrada por
    sección de datos (las cinco, con su conteo — es el análogo del conteo por endpoint de F-004 y
    lo que delata una sección que vino vacía). Cobertura medida sobre las 234 filas para:
    `emisor, ley, moneda_pago, estructura_cupon, tasa_cupon_vigente, proximo_cupon,
    proximo_pago_capital, valor_residual, paridad_pct, valor_tecnico, tir, duracion_modificada,
    convexidad, vida_promedio, volumen_promedio_20r_ars, cierre_ars`. Sobre la muestra real, la
    ley da 223/234 (los 11 de pesos sin ley) — ese hueco **debe verse** en la cobertura, es el
    sistema funcionando.

11. **El resultado es un tipo propio del paquete.** `ResultadoInforme` (dataclass congelada):
    `filas: list[FilaInforme]`, `fecha_informe: date`, `snapshot: Snapshot`. `parsear_informe`
    recibe `bytes` (no un path): el endpoint le pasa el cuerpo, los tests le pasan el archivo
    leído, y F-007 podrá dispararlo desde donde quiera.

12. **Logging.** `logger.info("informe_iamc_parseado", filas=..., secciones=...,
    fecha_informe=...)` y `logger.warning("informe_iamc_rechazado", pagina=..., titulo=...)`.
    Nunca el contenido del PDF ni paths de usuario; acá no hay tokens pero la disciplina es la
    misma que en las otras fuentes.

## Test Strategy

Convenciones del proyecto: nombres en castellano como frase completa, docstring de módulo que
nombra el criterio cubierto, async sin decorador. **El PDF real está versionado en
`fuentes/iamc-deuda-corporativa-2026-08-05.pdf`**, así que los tests de parser corren contra el
informe verdadero sin red y sin marker `integration` (el archivo existe en cualquier worktree). El
diseño de `parser.py` separa la iteración de páginas de pdfplumber de la lógica de secciones,
para poder testear el aborto con páginas sintéticas sin fabricar PDFs.

### GWT de la spec → verificación

1. **GWT-1** — *cada ON hereda ley y moneda del título de su sección, y el parser registra de qué
   sección salió*: en `test_iamc_parser.py`, contra el PDF real:
   `test_cada_on_hereda_ley_y_moneda_del_titulo_de_su_seccion` — PLC7O (pág. 1) sale con
   `ley="Ley N.Y."`, `moneda_pago="USD"`, `seccion="DEUDA CORPORATIVA EN USD - LEY NY"`; PLC4O
   (pág. 5) con `ley="Ley Argentina"`; PNRCO (pág. 16) con `moneda_pago="ARS"`; LMS6O (cupón
   cero) con `ley="Ley Argentina"` **desde la columna** y `moneda_pago="ARS"`; RVS1O (pesos) con
   `ley is None` y `moneda_pago="ARS"`. Y
   `test_la_seccion_de_pesos_no_declara_ley_y_el_hueco_se_cuenta`: cobertura de `ley` = 223/234.

2. **GWT-2** — *layout cambiado / sección no reconocida → aborta con detalle y no persiste filas
   parciales*: `test_una_seccion_desconocida_aborta_el_informe_entero_sin_filas_parciales` — con
   páginas sintéticas (una sección válida con filas + una página con título
   `"DEUDA CORPORATIVA EN EUR - LEY FRANCESA"`), `parsear_informe` (por su función interna de
   páginas) lanza `InformeInvalido` cuyo detalle nombra el título y la página, y no hay ningún
   resultado con filas. Más `test_una_fila_con_forma_desconocida_tambien_aborta` (fila de 5
   celdas que no es datos ni continuación) y
   `test_las_paginas_de_sensibilidad_y_curva_se_saltean_sin_abortar` (contra el PDF real: las 7
   páginas de gráficos no aportan filas ni alertas).

3. **GWT-3** — *campo numérico ausente → vacío, contado en cobertura, sin inferencia*: en
   `test_iamc_normalizacion.py`: `test_un_campo_ausente_queda_none_y_no_se_completa` y
   `test_un_valor_ilegible_queda_none_y_se_alerta_con_el_valor_crudo`; en el parser,
   `test_un_faltante_se_cuenta_en_la_cobertura_del_campo` con una grilla sintética donde a una
   fila le falta la TIR → cobertura `tir` = n−1/n, fila presente, campo `None`.

### Tests de mecánica

- `test_iamc_normalizacion.py`: `_numero` — `"1,100M"` → `1.1e9`, `"7.92%"` → `7.92`,
  `"-0.93%"` → `-0.93`, `"156250.0"` → `156250.0`, `"0.00M"` → `0.0` (presente, no faltante),
  `""` → `None`; `_fecha` — `"30-Jun-26"`, `"05-Aug-26"`, ilegible → `None`; mapeo de ley —
  `"ARG"` → `"Ley Argentina"`, `"NY"` → `"Ley N.Y."`, `"UK"` → `None` + alerta (el episodio "Ley
  Inglesa" convertido en test de regresión).
- `test_iamc_tablas.py` (grillas sintéticas que imitan la salida real de pdfplumber, con índices
  de columna dispersos y `None` intercalados): la continuación en el índice del emisor se
  concatena (`PECOM SERVICIOS` + `ENERGIA S.A.U`); el glifo `` se ignora; la fila-artefacto
  de 2 celdas no se toma como header; headers truncados (`Fecha\nVencimie`) validan; header con
  22 celdas donde se esperaban 23 → `InformeInvalido`.
- `test_iamc_parser.py` contra el PDF real (el test de humo más valioso del paquete):
  `test_el_informe_real_del_5_de_agosto_produce_234_filas_en_5_secciones` — 234 filas,
  `filas_por_tramo` == {LEY NY: 40, LEY ARG: 146, TASA FIJA: 20, CUPÓN CERO: 17, PESOS: 11},
  `fecha_informe == date(2026, 8, 5)`, `snapshot.completo is True`, emisores multilínea enteros
  (`"PECOM SERVICIOS ENERGIA S.A.U"` en MCC3O), y ningún ticker duplicado.
- `test_iamc_api.py` (httpx `ASGITransport` como en `conftest.py`): cuerpo no-PDF → 400; cuerpo
  de 26 MB → 413; PDF válido chico (el real) → 200 con snapshot y archivo guardado en el
  directorio redirigido a `tmp_path` con el nombre `iamc-deuda-corporativa-2026-08-05.pdf`;
  `parsear_informe` monkeypatcheado para lanzar `InformeInvalido` → 422 con el contrato de error
  y el detalle de la sección.

## Verificación end-to-end

Desde `backend/`, con el venv activado:

```bash
ruff check app/ingesta/iamc app/api/v1/iamc.py tests/test_iamc_*.py    # 0 errores
pytest tests/test_iamc_normalizacion.py tests/test_iamc_tablas.py \
       tests/test_iamc_parser.py tests/test_iamc_api.py -v
pytest                                                                  # la suite entera verde
```

Verificación manual con el backend levantado:

```bash
curl -s -X POST --data-binary @../fuentes/iamc-deuda-corporativa-2026-08-05.pdf \
     -H 'Content-Type: application/pdf' \
     localhost:8000/api/v1/iamc/informe | python3 -m json.tool
```

Se espera: 200, `fecha_informe: "2026-08-05"`, `snapshot.filas_por_tramo` con las cinco secciones
(40/146/20/17/11), `completo: true`, cobertura con `ley` en 223/234, y el PDF guardado en
`fuentes/`. Después, un negativo rápido:
`curl -s -X POST --data-binary "hola" -H 'Content-Type: application/pdf' ...` → 400 con el
contrato de error.

Cierre: `/simplify` sobre los archivos modificados, commit único en `feature/F-005`.

## Riesgos

Esta feature tiene confianza 50 % en la spec por una razón real: **hay una sola muestra del PDF**.
Ser honesto con eso:

1. **N=1.** Todo el catálogo está calibrado contra el informe del 05/08/2026. El informe de otro
   día puede traer otra cantidad de páginas por sección (eso ya está cubierto: las secciones se
   detectan por título, no por número de página) o una sección estacional nueva (eso aborta por
   diseño, que es el comportamiento pedido — el costo es que la primera subida de un layout nuevo
   requiere tocar `secciones.py`). **Plan B declarado:** si al segundo o tercer informe real el
   aborto resulta demasiado frecuente por variaciones menores (un header que cambia de nombre, una
   columna que se agrega al final), la relajación correcta es por sección en el catálogo, nunca un
   modo "parsear lo que se pueda".
2. **La detección de tablas de pdfplumber depende de las líneas del export de Power BI.** Si IAMC
   regenera el reporte con otro tema visual (sin bordes de celda), `find_tables()` puede dejar de
   ver la grilla. Se detecta solo (0 filas donde el catálogo espera datos → `InformeInvalido`).
   Plan B: extracción por `extract_words()` con clustering por coordenada x de los headers — más
   código, mismo contrato; no se construye ahora porque el layout real actual no lo necesita.
3. **El PDF pesa 7 MB y el parseo tarda segundos** (~2–4 s medidos en exploración). El endpoint es
   síncrono dentro del request y el parseo de pdfplumber es CPU-bound: para una subida manual
   diaria es aceptable; si bloqueara el event loop de forma molesta, la mejora es
   `run_in_executor` — decisión local al endpoint, sin cambio de contrato.
4. **Multipart quedó afuera para no agregar `python-multipart`.** Si la UI de F-013+ quiere subir
   el informe con un form multipart, esa feature deberá o bien agregar la dependencia (decisión
   suya, declarada) o bien mandar el binario crudo con `fetch`. El contrato de F-005 (bytes de un
   PDF) sirve igual para las dos.
5. **La sección de pesos queda sin ley** (11 filas). No es un bug de esta feature: es el dato que
   la fuente no declara. F-007/F-009 son quienes pueden completarlo desde `condiciones_emision`
   con su propia precedencia. Si alguien "arregla" esto en F-005 infiriendo Ley Argentina, está
   repitiendo el incidente que motivó la regla 1.
