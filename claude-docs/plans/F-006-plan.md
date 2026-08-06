# Feature Plan: F-006 — Cliente del feed de cashflow de Docta

## Overview

- **Source:** `claude-docs/planning/plan.md` (ficha F-006, líneas 344–381) + base común de ingesta
  en `backend/app/ingesta/` + **`tools/consolidar_universo.py`**, que consume este mismo feed
  desde hace meses y es el precedente probado + verificación empírica del feed real (06/08/2026).
- **Complejidad:** S/M
- **Estimación:** 1 día. Es la más acotada de las tres fuentes: un solo endpoint, y la mitad de la
  lógica difícil (reintentos, detección de token vencido) ya vive en la base común.
- **Depende de:** F-001 (terminada). **Habilita:** F-007 (consolidador), F-015 (grilla de doce
  meses — el corazón del producto), F-040.
- **Branch:** `feature/F-006`, un solo commit al cierre.
- **Ejecución en paralelo con F-004 y F-005:** no se toca ningún archivo compartido. Todo lo nuevo
  vive en `app/ingesta/docta/` y las rutas van únicamente en `app/api/v1/docta.py`, que ya existe
  y ya está montado.

### Hechos verificados contra el feed real (06/08/2026)

- **El token está vigente**: `DOCTA_CASHFLOW_URL` respondió HTTP 200 con 2,5 MB de Excel.
- **6.150 filas y 12 columnas**: las 9 del contrato conocido — `ticker`, `type`, `issue_date`,
  `payment_date`, `capital`, `interest_rate`, `interest_amount`, `residual_value`, `cash_flow` —
  más **tres no documentadas**: `days_convention`, `theoretical_payment_date`,
  `theoretical_days_before`. Qué se hace con esas tres: decisión 6.
- Las trampas conocidas del feed están documentadas en `pedir_excel()` y
  `url_con_ventana_movil()` de `tools/consolidar_universo.py`, con mediciones: el HTTP **500**
  con cuerpo "Error al verificar el token" es token vencido (no un 401); la misma consulta que
  devuelve 0 filas trae 1.660 segundos después (inestabilidad, no regla de fechas); el link
  generado por Docta Terminal trae `fromDate` **hardcodeado al día en que se generó**, y al
  envejecer el feed devuelve 0 filas **sin error**.

## Implementation Approach

**Reescritura async fina sobre la base común, transcribiendo del motor sólo lo que es de
ingesta.** El criterio de qué se reusa y qué no, función por función de
`tools/consolidar_universo.py` (no se importa nada desde `tools/` — es el motor pre-Fase 4 y va a
morir; se transcribe con su porqué):

| Pieza del motor | Destino en F-006 |
|---|---|
| `pedir_excel()` (líneas 129–186): reintentos, espera creciente, timeout 90 s, vacío reintentable, detección de token por cuerpo | **Ya está en la base**: `http.con_reintentos` + `http.pedir` + `http._detectar_credencial_vencida` implementan exactamente esa política. F-006 sólo aporta la operación "bajar y parsear el Excel" que se le pasa a `con_reintentos`. |
| `url_con_ventana_movil()` (206–220): reescribe `fromDate` a hoy−15 con regex | **Se transcribe** a `docta/url.py` como función pura, con el docstring que explica el porqué (el link envejece y devuelve 0 filas sin error). Es el GWT-4. |
| `cargar_cashflow_resumen()` (263–292): deriva `residualValue` y `maturity` por ticker | **No se copia.** Eso es consolidación: lo hace F-007 sobre las filas que F-006 entrega. Copiarlo acá duplicaría la regla en dos lugares. |
| `guardar_cashflow_completo()` (295–312): persiste CSV | **No se copia.** F-006 no persiste nada; las columnas que esa función esperaba son la base del contrato de 9 columnas (decisión 5). |
| `SUBMARKET_MAP` (62–85) | **No aplica**: el feed de cashflow no trae `submarket`. Es material de F-007. |
| Chequeo de `DOCTA_API_TOKEN` y expansión `${VAR}` del parser de `.env` casero (111–126) | Se reemplaza por la expansión explícita del placeholder en la URL (decisión 2) — pydantic-settings **no** expande `${DOCTA_API_TOKEN}` como sí lo hacía el parser casero del motor. |

**Alternativas descartadas:**

- *Importar `tools/consolidar_universo.py` como librería*: descartado. Es sync (urllib), lee
  `.env` con parser propio, escribe a disco y mezcla ingesta con consolidación. El plan de
  producto dice que el motor "se reusa, se envuelve o se reescribe" según `product-definition.md`;
  para esta pieza la respuesta es transcribir la lógica de ingesta y dejar morir el resto.
- *Parsear el Excel en streaming / fuera del event loop con executor*: descartado por ahora; son
  2,5 MB y `pd.read_excel` tarda menos de ~2 s. Si el bloqueo del event loop molestara en F-008,
  `run_in_executor` es un cambio local a `cliente.py`.
- *Persistir "el último cashflow válido" en F-006*: descartado — ver decisión 8, que define el
  límite exacto con F-007.

## File Structure

### Crear

```
backend/app/ingesta/docta/__init__.py        Exporta ingerir_cashflow, ResultadoCashflow, ConfiguracionFaltante
backend/app/ingesta/docta/url.py             url_con_ventana_movil() + expansión del placeholder ${DOCTA_API_TOKEN}
backend/app/ingesta/docta/cliente.py         Descarga del Excel vía base http + parseo pandas + "vacío es fallo"
backend/app/ingesta/docta/normalizacion.py   Validación de las 9 columnas contractuales, tipado, extras passthrough
backend/app/ingesta/docta/ingesta.py         Orquestación: URL efectiva, descarga, Snapshot, cobertura, alertas
backend/tests/test_docta_url.py              Ventana móvil (GWT-4) y expansión del token
backend/tests/test_docta_ingesta.py          GWT-1/2/3: token vencido vs caída vs vacío errático (respx)
backend/tests/test_docta_normalizacion.py    Columnas contractuales, extras, tipos, faltantes
backend/tests/test_docta_integracion.py      Un test marcado integration contra el feed real
```

### Modificar

```
backend/app/api/v1/docta.py                  Agregar POST /docta/ingesta (el archivo es propiedad de F-006)
```

**Nada más.** No se toca `router.py`, `config.py` (las cuatro variables de Docta ya existen),
`requirements.txt`, `pyproject.toml`, ni nada de `app/ingesta/` fuera de `docta/`.

## Dependency Map

**De la base común (`app/ingesta/`):**

- `http.crear_cliente()`, `http.pedir()`, `http.con_reintentos()` — todo el tránsito. La
  detección de token vencido (500 + "token" en el cuerpo) **ya está implementada** en
  `http._detectar_credencial_vencida` y sale como `CredencialVencida`, no reintentable. F-006 no
  la reimplementa: la captura.
- `http.ErrorDeFuente` / `http.CredencialVencida` — el `except` de la orquestación distingue por
  tipo, que es exactamente el GWT-1 vs GWT-2.
- `snapshot.Snapshot`, `alertas.credencial_vencida()`, `alertas.fuente_caida()`,
  `alertas.respuesta_vacia()`, `alertas.formato_inesperado()`, `cobertura.medir_cobertura()`.
  Ningún modelo ni código de alerta propio.

**De `app/core/config.py` (ya existen):** `docta_cashflow_url`, `docta_api_token` (los otros dos
links de Docta — yield y serie de precios — **no se consumen**: la ficha es explícita en que el
cashflow es el único consumo de Docta que queda en el producto).

**Paquetes (ya instalados):** `httpx`, `pandas`, `openpyxl` (el Excel es binario xlsx), `respx`
(tests). No se agrega ninguna dependencia.

## Edge Cases & Technical Decisions

1. **La URL nunca se loguea ni viaja en alertas.** El link de Docta lleva el token embebido en la
   query string y el redactor de secretos **no tapa un campo llamado `url`** (limitación
   documentada del proyecto). Regla absoluta en todo el paquete: los logs y los `detalle` de las
   alertas identifican la fuente como `"Docta cash-flow"` y llevan status/intentos/filas — jamás
   la URL, ni entera ni recortada. `pedir()` de la base ya respeta esto; la orquestación también
   tiene que hacerlo en sus propios eventos.

2. **URL efectiva = configurada → expandida → con ventana móvil.** En `docta/url.py`:
   - Si `docta_cashflow_url` es `None` o vacía → `ConfiguracionFaltante` (excepción del paquete);
     el endpoint la convierte en **503** con mensaje que nombra la variable (`DOCTA_CASHFLOW_URL`)
     — el mismo espíritu de `config.py`: un servicio a medio configurar falla nombrando lo que
     falta.
   - Si la URL contiene el placeholder literal `${DOCTA_API_TOKEN}` se expande con
     `settings.docta_api_token` (así están escritos los links en `.env`, y el parser casero del
     motor lo expandía; pydantic-settings **no** lo hace — sin esta expansión el request iría con
     el placeholder crudo y daría token inválido). Placeholder presente y token ausente →
     `ConfiguracionFaltante` nombrando `DOCTA_API_TOKEN`.
   - `url_con_ventana_movil(url, dias=15)`: si la URL trae `fromDate=`, se reescribe a
     `date.today() − 15 días` con el mismo regex del motor; si no lo trae, se devuelve intacta.
     **Ninguna fecha hardcodeada en el código** (GWT-4): la única fecha es relativa a la corrida.
     Los 15 días son la constante medida del motor (ventana amplia que absorbe la inestabilidad
     de la serie), con su porqué en el docstring.

3. **"Bajar el Excel" es una sola operación reintentable.** En `cliente.py`, la operación que se
   pasa a `con_reintentos` hace: `pedir(cliente, "GET", url, fuente="Docta cash-flow")` → parsear
   `pd.read_excel(io.BytesIO(respuesta.content), sheet_name=None)` → tomar la primera hoja con
   filas. Dentro de la operación, **dos condiciones son fallo reintentable** (`ErrorDeFuente`):
   el cuerpo no es un Excel válido (pasó en el motor: HTML de error con status 200) y el Excel
   con cero filas (la inestabilidad errática medida — GWT-3). `CredencialVencida` sale de
   `pedir()` y **corta sin reintentar** porque la base la marca no reintentable: cinco reintentos
   contra un token vencido son cinco esperas inútiles.

4. **Tres fallos, tres alertas distintas — porque la acción que piden es distinta** (GWT-1/2). La
   orquestación captura y traduce:
   - `CredencialVencida` → `alertas.credencial_vencida("Docta", "Regenerar el link en Docta
     Terminal ('Generar Link') y actualizar las DOCTA_*_URL en .env — el token nuevo sirve para
     los tres links")`. La `accion_requerida` es literalmente la instrucción operativa del motor:
     alguien tiene que ir a hacer algo; esperar no lo arregla.
   - `ErrorDeFuente` con motivo de cero filas tras agotar intentos →
     `alertas.respuesta_vacia("Docta cash-flow", intentos=5)`.
   - Cualquier otro `ErrorDeFuente` agotado (timeout, 5xx genérico, cuerpo ilegible) →
     `alertas.fuente_caida("Docta cash-flow", motivo, status=...)` con `accion_requerida=None` —
     se arregla esperando, y decirle a alguien que actúe lo mandaría a regenerar un token sano.

5. **Contrato de columnas: 9 obligatorias, validadas antes de normalizar.** Las nueve del
   contrato conocido (las que `guardar_cashflow_completo` del motor exigía para poder separar
   renta de amortización, más las de identidad y fechas). Si falta cualquiera →
   `alertas.formato_inesperado("Docta cash-flow", "faltan columnas X, Y")` y **resultado sin
   filas** (mismo criterio que `validar_columnas` del motor: un cashflow al que no se le puede
   separar interés de capital no sirve para la grilla de F-015; entregarlo a medias sería peor
   que declararlo). La separación interés/capital que pide el output de la ficha ya viene dada
   por las columnas `capital` / `interest_amount` / `cash_flow` — F-006 las entrega tipadas, no
   deriva nada.

6. **Las tres columnas no documentadas se conservan como passthrough, sin promesa de contrato.**
   `days_convention`, `theoretical_payment_date`, `theoretical_days_before` (y cualquier otra
   columna futura) viajan en las filas tal como llegan, sin tipado propio ni cobertura medida.
   Justificación: descartarlas tiraría dato declarado por la fuente (y `days_convention` es
   potencialmente valioso para el cálculo de cupones de F-015); pero promoverlas a contrato
   exigiría entender su semántica, que la fuente no documenta — eso sería un juicio inventado.
   Conservar-sin-prometer deja la decisión a F-007 con el dato a la vista. Queda documentado en
   el docstring de `normalizacion.py` con los tres nombres observados el 06/08/2026.

7. **Normalización tipada, huecos como `None`.** `ticker` y `type` → `str` sin espacios;
   `issue_date` y `payment_date` → `date` (el Excel las trae como datetime de pandas; `NaT` →
   `None`); `capital`, `interest_rate`, `interest_amount`, `residual_value`, `cash_flow` →
   `float` (`NaN` → `None`; un `0.0` real se conserva — un pago de capital 0 en una fecha de
   cupón puro es dato, no hueco). Las filas son `dict[str, object]` (no `TypedDict`: el
   passthrough de columnas desconocidas lo impide) con las 9 claves contractuales garantizadas
   presentes.

8. **"Conservar el último cashflow válido": el límite exacto entre F-006 y F-007.** F-006 **no
   persiste nada** — la base de mercado la escribe F-007 y la orquesta F-008. Lo que F-006 aporta
   para que ese criterio sea cumplible es la distinción en su tipo de retorno:
   `ResultadoCashflow` (dataclass congelada) con `filas: list[dict] | None` y
   `snapshot: Snapshot`. **`filas=None` significa "esta corrida no trajo un cashflow usable"**
   (token vencido, fuente caída, vacío agotado, columnas rotas) y es distinguible de una lista
   con filas. El contrato, documentado en el docstring de `ResultadoCashflow`: *quien persiste
   sólo escribe cuando `filas is not None`; ante `None` conserva lo último persistido y propaga
   las alertas del snapshot*. Cero filas "legítimas" no existen como éxito: un universo con 97 %
   de cobertura de emisiones no puede tener cashflow vacío, por eso el vacío es siempre fallo.

9. **Snapshot y cobertura.** `Snapshot(fuente="Docta", demora_declarada_minutos=0)` — el
   cashflow es un cronograma contractual, no un precio con demora de rueda; declarar demora acá
   etiquetaría mal el dato. `filas_por_tramo = {"cash-flow": n}` (un solo tramo: un solo
   endpoint). En fallo total, el tramo queda en 0 y la alerta lo explica. Cobertura medida sobre
   las 9 columnas contractuales — `interest_rate` y `residual_value` son las que
   históricamente vienen con huecos y F-015 necesita saber cuánto puede proyectar.

10. **Endpoint HTTP: `POST /docta/ingesta`.** POST porque dispara una acción. Responde **200 con
    `{"snapshot": snapshot.como_dict()}`** aunque la fuente haya fallado (la corrida corrió; su
    estado lo declaran `completo` y las alertas — mismo criterio que F-004). Las 6.150 filas no
    viajan en la respuesta. **503** sólo para `ConfiguracionFaltante` (el servicio no está en
    condiciones de intentar la corrida). Logging:
    `logger.info("ingesta_docta_termino", filas=..., completo=...)` y
    `logger.warning("docta_token_vencido")` — sin URL, siempre.

## Test Strategy

Convenciones del proyecto: nombres en castellano como frase completa, docstring de módulo con el
criterio cubierto, async sin decorador, `respx` para la red, `dormir` inyectado como corrutina
nula. Fixture clave en `test_docta_ingesta.py`: `excel_de_cashflow(filas)` — arma bytes xlsx en
memoria con `pandas.DataFrame(...).to_excel(BytesIO, ...)` (openpyxl ya instalado), con las 12
columnas reales por defecto. La URL de prueba lleva un token falso embebido para poder assertar
que nunca aparece en logs ni alertas.

### GWT de la spec → verificación

1. **GWT-1** — *HTTP 500 "Error al verificar el token" → alerta de token vencido, distinta de la
   de API caída, y la ingesta conserva el último cashflow válido*:
   `test_un_500_de_token_vencido_alerta_regenerar_y_no_reintenta`: respx responde 500 con cuerpo
   `"Error al verificar el token"` → exactamente **1** llamada (no se reintenta), alerta con
   `codigo == CODIGO_CREDENCIAL_VENCIDA`, `accion_requerida` que menciona "Docta Terminal", y
   `resultado.filas is None` — que es la mitad de "conservar el último válido" que le toca a
   F-006 (la otra mitad es el contrato documentado para quien persiste, verificado por
   `test_el_resultado_distingue_fallo_de_lista_de_filas`: un éxito nunca tiene `filas=None` y un
   fallo nunca tiene lista).

2. **GWT-2** — *timeout o 5xx que no es de token → alerta de API caída, distinta de la de
   token*: `test_un_timeout_alerta_fuente_caida_y_no_credencial` (respx con
   `side_effect=httpx.TimeoutException`) y `test_un_500_generico_se_reintenta_y_alerta_fuente_caida`
   (5 llamadas contadas): en ambos, `codigo == CODIGO_FUENTE_CAIDA`,
   `accion_requerida is None`, y los códigos de GWT-1 y GWT-2 son distintos entre sí
   (`test_token_vencido_y_api_caida_tienen_codigos_distintos`).

3. **GWT-3** — *cero filas erráticas → hasta 5 reintentos con espera creciente*:
   `test_un_excel_vacio_erratico_se_reintenta_hasta_que_trae_filas`: respx devuelve dos veces un
   xlsx sin filas y a la tercera uno con filas → 3 llamadas, resultado con filas, sin alertas de
   error; las esperas pedidas a `dormir` fueron `[3, 6]`.
   `test_cinco_vacios_seguidos_declaran_respuesta_vacia`: 5 llamadas y alerta
   `CODIGO_RESPUESTA_VACIA`.

4. **GWT-4** — *`fromDate` relativo a la corrida, sin fecha hardcodeada*: en
   `test_docta_url.py`, `test_from_date_se_reescribe_a_quince_dias_antes_de_hoy`: una URL con
   `fromDate=2026-01-01` sale con `fromDate == date.today() − 15 días` (el test lo calcula
   relativo, nunca un literal); `test_una_url_sin_from_date_queda_intacta`; y en
   `test_docta_ingesta.py` se asserta sobre la request capturada por respx que el `fromDate`
   que viajó es el reescrito.

### Tests de mecánica

- `test_docta_url.py` además: `${DOCTA_API_TOKEN}` se expande con el token de settings; URL
  ausente → `ConfiguracionFaltante` que nombra `DOCTA_CASHFLOW_URL`; placeholder sin token →
  `ConfiguracionFaltante` que nombra `DOCTA_API_TOKEN`.
- `test_docta_normalizacion.py`: faltan columnas contractuales → `formato_inesperado` con los
  nombres exactos y `filas is None`; las tres columnas extra viajan intactas en las filas;
  `NaN` → `None` pero `0.0` se conserva (cobertura lo cuenta presente); fechas de pandas →
  `date`; un cuerpo que no es Excel se reintenta y agota como fuente caída.
- `test_docta_ingesta.py` además: `test_el_token_no_aparece_en_ningun_log_ni_alerta` — con
  logging capturado (mismo mecanismo que los tests de F-001) y el token falso embebido en la URL
  de prueba, se asserta que el token no aparece en ninguna línea de log ni en ningún
  `como_dict()` de alerta o snapshot. Es el test de la decisión 1 y el más importante del
  paquete después de los GWT.
- Endpoint: 200 con snapshot en éxito y en fallo de fuente; 503 con el contrato de error cuando
  falta la config (settings sin `DOCTA_CASHFLOW_URL`, vía `monkeypatch.delenv` +
  `get_settings.cache_clear()` como hace `conftest.py`).

### Integración (marcada, excluida por defecto)

- `test_docta_integracion.py` — `@pytest.mark.integration` + `skipif` si no hay
  `DOCTA_CASHFLOW_URL` en el entorno: corre `ingerir_cashflow()` real y asserta `filas` no
  vacías (>1.000), las 9 columnas contractuales presentes en la primera fila, y
  `snapshot.completo is True`. Si falla con la alerta de token, el mensaje del assert lo dice
  ("el token venció — regenerar en Docta Terminal"), que es información operativa, no un bug.

## Verificación end-to-end

Desde `backend/`, con el venv activado:

```bash
ruff check app/ingesta/docta app/api/v1/docta.py tests/test_docta_*.py   # 0 errores
pytest tests/test_docta_url.py tests/test_docta_normalizacion.py tests/test_docta_ingesta.py -v
pytest -m integration tests/test_docta_integracion.py -v                  # con red y .env real
pytest                                                                     # la suite entera verde
```

Verificación manual con el backend levantado (requiere `.env` con las variables de Docta):

```bash
curl -s -X POST localhost:8000/api/v1/docta/ingesta | python3 -m json.tool
```

Se espera: `snapshot.fuente == "Docta"`, `filas_por_tramo == {"cash-flow": ~6150}`,
`completo == true`, cobertura de las 9 columnas, y **ninguna URL en el log del backend**.
Negativo rápido: renombrar temporalmente `DOCTA_CASHFLOW_URL` en `.env` y reiniciar → el endpoint
responde 503 nombrando la variable (y se restaura el `.env`).

Cierre: `/simplify` sobre los archivos modificados, commit único en `feature/F-006`.

## Riesgos

1. **El token vence sin aviso** (es el modo de fallo más frecuente del feed en la historia del
   motor). Está cubierto por diseño: alerta con acción operativa exacta, sin reintentos inútiles.
   El riesgo residual es humano — que nadie mire las alertas — y eso lo resuelven la barra de
   estado del dato (F-013) y el registro de corridas (F-008), no esta feature.
2. **Las 12 columnas de hoy pueden volver a cambiar** (las 3 extra aparecieron sin anuncio). Las
   obligatorias están validadas y el passthrough absorbe adiciones; una **remoción** de columna
   contractual da `formato_inesperado` y resultado sin filas, que es el comportamiento correcto
   pero deja al producto sin cashflow fresco hasta que se resuelva. Mitigación: la alerta nombra
   las columnas exactas que faltan.
3. **El regex de la ventana móvil supone el formato `fromDate=YYYY-MM-DD` en la query.** Si Docta
   cambia el formato del link, la reescritura no matchea y la URL viaja como esté — con el
   `fromDate` viejo, el feed degenera en 0 filas sin error, que el pipeline sí declara
   (`respuesta_vacia` tras 5 intentos). No es silencioso, pero el diagnóstico pide leer la
   alerta; queda anotado en el docstring de `url.py`.
4. **`pd.read_excel` sobre 2,5 MB bloquea el event loop ~1–2 s.** Aceptable para una corrida
   batch; si F-008 lo sufre, `run_in_executor` es un cambio local sin efecto en el contrato.
