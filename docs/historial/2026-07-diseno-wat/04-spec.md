# Automation Spec — Consolidador de Universo de Instrumentos

## Resumen ejecutivo

**Nombre de la automatización**: Consolidador de Universo de Instrumentos (`consolidar_universo`)

**Qué hace**: toma los CSV que el usuario descarga de doctacapital.com (bonos soberanos, subsoberanos, ONs/corporativos, acciones, CEDEARs, opciones, FCI), los valida, normaliza y cruza contra la lista de instrumentos que ofrece Balanz, y devuelve un único dataset limpio (`universo_consolidado.xlsx`) con todas las variables clave por instrumento, listo para analizar.

**Qué problema resuelve**: elimina el cruce manual, diario, de ~6-7 archivos CSV distintos contra la oferta de Balanz — el cuello de botella más pesado del proceso de armado de carteras y detección de swaps (identificado en `01-process-map.md` y priorizado como Quick Win en `02-scorecard.md`).

**Ahorro estimado**:
- Tiempo: pendiente de cuantificar tras las primeras semanas de uso (el usuario reportó que hoy es "mucho tiempo" pero sin cifra exacta).
- Otros beneficios: reduce el riesgo de analizar con datos desactualizados o mal cruzados; deja base lista para construir el motor de detección de swaps (Opportunity B, próximo ciclo).

---

## Trigger

| Campo | Valor |
|-------|-------|
| **Tipo** | Manual |
| **Origen específico** | El usuario descarga los CSV de doctacapital.com a una carpeta fija (`data/raw/`) y ejecuta el script, o le pide al agente ("Claude") que lo corra |
| **Filtros previos** | Ninguno — el script arranca con lo que encuentre en `data/raw/` en el momento de la ejecución |
| **Frecuencia esperada** | Diaria (uso "always-on"), a discreción del usuario — no hay horario fijo definido todavía |

---

## Pasos detallados

### Paso 1 — Lectura y validación de schema

- **Acción**: leer los CSV presentes en `data/raw/` (solo los que el usuario haya cargado ese día — **no todos son obligatorios**, ver nota de flexibilidad más abajo) y verificar que las columnas coincidan con el schema definido para ese tipo de archivo.
- **Input**: archivos CSV, cada uno matcheado por prefijo de nombre (ignorando el sufijo `" (1)"`, `" (2)"` que agrega el navegador en re-descargas):

  | Archivo (prefijo) | Clase de activo | Tipo de tasa | Columnas clave |
  |---|---|---|---|
  | `monitoreo_soberanos_hard-dollar` | bono_soberano | Hard-Dollar (Globales/Bonares — distinguibles por la columna `law`: Ley Argentina = Bonares, Ley N.Y. = Globales) | `ticker, tir, duration, vt, paridad, maturity, couponCurrency, isinCode, priceClean, residualValue, law, ...` |
  | `monitoreo_soberanos_fixed-rate` | bono_soberano | Tasa Fija | `ticker, tna, tea, tem, dtm, maturity, paridad, couponCurrency, ...` (usa `tna/tea/tem/dtm` en vez de `tir/duration`) |
  | `monitoreo_soberanos_cer` | bono_soberano | CER | `ticker, tir, duration, maturity, paridad, ...` (sin `law`) |
  | `monitoreo_soberanos_dollar-linked` | bono_soberano | Dólar Linked | `ticker, tir, duration, maturity, paridad, ...` (sin `law`) |
  | `monitoreo_soberanos_badlar` | bono_soberano | Badlar | `ticker, tir, duration, maturity, paridad, margen, ...` (sin `law`) |
  | `monitoreo_soberanos_bopreal` | bono_soberano | Bopreal/BCRA | `ticker, tir, duration, maturity, couponCurrency, isinCode, ...` (sin `law`) |
  | `monitoreo_corporativos_hard-dollar` | on_corporativo | Hard-Dollar (única variante disponible para ONs) | `ticker, underlying, tir, duration, vt, paridad, maturity, couponCurrency, isinCode, priceClean, residualValue, law, ...` |
  | `monitoreo_subsoberanos_hard-dollar` | bono_subsoberano | Hard-Dollar (única variante disponible) | mismas columnas que corporativos, **sin** `law` |
  | `monitoreo_acciones` | accion | — | `ticker, lastPrice, closingPrice, variation, tradeVolume, effectiveVolume, bidPrice, bidSize, offerPrice, offerSize` |
  | `monitoreo_cedears` | cedear | — | `ticker, lastPrice, closingPrice, variation, tradeVolume, effectiveVolume, ..., sector, country, moneda` |
  | `monitoreo_opciones` | opcion | — | `ticker, mainTicker, type, underlyingPrice, strike, moneda, lastPrice, ...` |
  | `fci_screener_*` (timestamp variable) | fci | — | `Fondo, Gestora, AUM (ARS), Ret 1D, Ret 7D, Ret 30D, Ret YTD, Ret 1Y, Edad (días), Último cierre` |

  > **Categoría "Tamar"** mencionada como filtro en doctacapital pero sin archivo de ejemplo cargado — si el usuario la usa alguna vez, hay que sumarla al mapeo antes de esa primera corrida (no se asume su schema sin verlo).

- **Lógica**: por cada archivo presente, comparar el header real contra el schema esperado de su tipo. Si falta o sobra una columna respecto a lo esperado, no procesar ese archivo — registrar la alerta y continuar con el resto. Un archivo **ausente** no es un error (ver nota de flexibilidad).
- **Output**: dict en memoria `{tipo_instrumento_tasa: DataFrame}` para los archivos presentes que pasaron validación + lista de alertas por archivo que falló validación.
- **Herramienta sugerida**: Python + pandas (`pd.read_csv`), matcheo de archivos con `glob` sobre el prefijo.

**Nota de flexibilidad (pedido explícito del usuario)**: el usuario no siempre necesita analizar todas las categorías (ej. algunos días no le interesan opciones o bonos CER). El script debe funcionar correctamente con **cualquier subconjunto** de los archivos listados arriba presentes en `data/raw/` — no exige un set completo. El consolidado y el log solo reportan sobre lo que efectivamente se cargó.

### Paso 2 — Normalización

- **Acción**: convertir campos con formato "humano" a tipos de dato limpios.
- **Input**: DataFrames del paso 1.
- **Lógica**:
  - Porcentajes con coma decimal (`"7,40%"`, `"-4,7%"`) → float (`0.074`, `-0.047`).
  - Fechas (`30/09/2037`, o `datetime` en Excel) → `datetime` estándar.
  - Montos y volúmenes → float/int, removiendo separadores de miles si los hubiera.
  - Si un valor no puede parsearse, la celda queda `NaN` y la fila se marca con flag `revisar = True` (no se descarta ni se fuerza un default).
- **Output**: DataFrames normalizados.
- **Herramienta sugerida**: Python + pandas (parsing con `str.replace` + `pd.to_numeric`/`pd.to_datetime`, `errors="coerce"` + flag posterior).

### Paso 3 — Etiquetado por clase de activo y tipo de tasa

- **Acción**: taggear cada fila con su clase de activo (`bono_soberano`, `bono_subsoberano`, `on_corporativo`, `accion`, `cedear`, `opcion`, `fci`) y, para bonos soberanos, su tipo de tasa (`hard-dollar`, `fixed-rate`, `cer`, `dollar-linked`, `badlar`, `bopreal`).
- **Input**: DataFrames del paso 2 + nombre del archivo de origen (ya normalizado sin el sufijo `" (1)"`).
- **Lógica**: mapeo fijo `prefijo_de_archivo → (clase_activo, tipo_tasa)`, confirmado por el usuario y documentado en la tabla del Paso 1 — el nombre del archivo **es** la fuente de esta clasificación (así es como el usuario descarga desde doctacapital), no se infiere del ticker. Para bonos hard-dollar, distinguir Globales vs Bonares a partir de la columna `law` (`Ley N.Y.` = Globales, `Ley Argentina` = Bonares).
- **Output**: DataFrames con columnas `clase_activo` y `tipo_tasa` agregadas.
- **Herramienta sugerida**: Python (diccionario de mapeo simple, definido junto a la tabla del Paso 1).

### Paso 4 — Cruce con oferta Balanz

- **Acción**: marcar cada instrumento como disponible o no en Balanz.
- **Input**: DataFrames etiquetados + `data/whitelist_balanz.csv` (archivo mantenido manualmente por el usuario, con al menos la columna `ticker`).
- **Lógica**: join por `ticker` contra la whitelist. Si la whitelist no existe o está vacía, no se filtra — se agrega la columna `disponible_balanz = "no verificado"` y se emite una alerta.
- **Output**: DataFrames con columna `disponible_balanz` (`sí` / `no` / `no verificado`).
- **Herramienta sugerida**: Python + pandas (`merge`).

### Paso 5 — Consolidación

- **Acción**: unificar todos los DataFrames en un único archivo Excel.
- **Input**: DataFrames del paso 4.
- **Lógica**: una hoja por clase de activo + una hoja "Resumen" con columnas comunes (`ticker, clase_activo, tir, duration, ley, moneda_pago, calificacion, volumen, vencimiento, disponible_balanz, revisar`) para los instrumentos de renta fija, y estructura equivalente simplificada para acciones/CEDEARs/FCI/opciones.
- **Output**: `data/output/universo_consolidado.xlsx`.
- **Herramienta sugerida**: Python + pandas/openpyxl (`ExcelWriter`).

### Paso 6 — Log de corrida

- **Acción**: generar un resumen textual de la ejecución.
- **Input**: resultado de los pasos 1-5.
- **Lógica**: contar instrumentos por clase, comparar contra la corrida anterior (si existe un consolidado previo guardado) para listar altas/bajas, y listar las alertas de formato del paso 1 y las filas marcadas `revisar` del paso 2.
- **Output**: log impreso en consola + guardado en `data/output/log_YYYY-MM-DD.txt`.
- **Herramienta sugerida**: Python (`print` + escritura de archivo de texto).

---

## Condiciones y ramificaciones

**Camino feliz**: Paso 1 → 2 → 3 → 4 → 5 → 6 → fin OK, `universo_consolidado.xlsx` actualizado.

**Manejo de excepciones**:
- Si una categoría de archivo (ej. opciones, soberanos CER) simplemente no está presente en `data/raw/`: **no es un error**, es el uso normal esperado — el consolidado se genera igual con lo que sí está, sin alertas por lo ausente (Paso 1).
- Si un CSV tiene columnas faltantes/renombradas respecto al schema esperado para su tipo: se loggea el archivo y la discrepancia exacta, se saltea solo ese archivo, se sigue con el resto (Paso 1).
- Si el mismo ticker aparece en dos archivos con datos distintos: se marca como `duplicado` en el output para revisión manual, no se descarta ninguna versión automáticamente.
- Si `data/whitelist_balanz.csv` no existe o está vacía: se marca `disponible_balanz = "no verificado"` en todas las filas y se loggea la advertencia (Paso 4).
- Si un valor numérico no puede parsearse: la fila queda con flag `revisar = True`, no se fuerza un valor por defecto (Paso 2).
- Si se corre el script dos veces el mismo día: el output se sobrescribe (no se duplican filas); el log de la corrida anterior se conserva con su propio timestamp.
- Si `data/raw/` está vacía o no existe: el script no genera un consolidado vacío silenciosamente — corta la ejecución con un mensaje claro pidiendo verificar la carpeta.

> Ningún error pasa en silencio — todo termina en el log de corrida, visible para el usuario.

---

## Recursos necesarios

- [ ] Python 3 instalado, con `pandas` y `openpyxl` (`pip install pandas openpyxl`)
- [ ] Carpeta `data/raw/` creada, donde el usuario deposita los CSV descargados de doctacapital con los nombres esperados
- [ ] Archivo `data/whitelist_balanz.csv` creado y mantenido por el usuario (columna mínima: `ticker`)
- [ ] Estructura de carpetas `tools/`, `data/`, `workflows/` en el repo (ya alineado con el framework WAT de `CLAUDE.md`)

No requiere credenciales de API ni cuentas pagas — todo corre localmente sobre archivos que el usuario ya descarga.

---

## Herramienta recomendada

**Elección**: Script Python local (sin orquestador no-code, sin IA generativa en la lógica), integrado como `tools/consolidar_universo.py` dentro del framework WAT ya definido en `CLAUDE.md`.

**Justificación**: el trigger es manual (no hay mail/webhook/formulario que disparar), no hay integraciones entre múltiples SaaS que conectar (todo el input son archivos locales), y el usuario pidió explícitamente evitar IA que "razone" — solo procesamiento de datos duro. Un script Python con pandas resuelve esto con el menor esfuerzo y sin costo recurrente. Zapier/Make/n8n agregarían una capa de orquestación innecesaria para un flujo que corre localmente sobre archivos; Power Automate no aplica (no hay stack Microsoft de por medio); Claude como motor de la lógica no aplica porque no hay texto libre que interpretar ni decisión en lenguaje natural en este Quick Win — su rol se limita a orquestar la ejecución del script y comunicar el resultado si el usuario se lo pide conversacionalmente.

**Alternativas consideradas y por qué se descartaron**: ver sección "Ideas consideradas" en `03-disenio-tobe.md`.

---

## Métricas de éxito

| Métrica | Tipo | Cómo medirla | Meta inicial |
|---------|------|--------------|---------------|
| Tiempo por corrida (descarga → consolidado listo) | Cuantitativa | Cronometrar antes/después de usar el script durante 2 semanas | Reducir a minutos lo que hoy toma "mucho tiempo" |
| Alertas de formato detectadas vs. errores que antes pasaban desapercibidos | Cuantitativa | Contar alertas en el log de corrida | Que el usuario confirme que las alertas son útiles y no ruido |
| Filas marcadas `revisar` por corrida | Cuantitativa | Conteo en el output | Tendiendo a bajo con el tiempo, salvo problemas reales de la fuente |
| Confianza del usuario en usar el consolidado sin re-chequear a mano | Cualitativa | Pregunta directa al usuario tras 2-3 semanas de uso | Sí, sin re-chequeo manual sistemático |

---

## Plan de testeo

### Casos felices a probar
1. Correr con los 6 CSV de ejemplo que ya están en `excels/` (nombres reales, datos reales) y confirmar que el consolidado sale correcto.
2. Correr sin `data/whitelist_balanz.csv` y confirmar que marca `no verificado` en vez de fallar.
3. Correr dos veces seguidas y confirmar que no duplica filas.

### Casos borde a probar
1. Editar a mano un CSV para sacarle una columna y confirmar que el script lo detecta, alerta y sigue con el resto.
2. Insertar un valor de TIR corrupto (texto en vez de número) y confirmar que la fila queda flageada `revisar`, no descartada.
3. Duplicar un ticker entre dos archivos con TIR distinta y confirmar que queda marcado `duplicado`.
4. Correr con un subconjunto parcial (ej. sin `monitoreo_opciones` ni `monitoreo_soberanos_cer`) y confirmar que el consolidado sale bien igual, sin alertas por las categorías ausentes.
5. Correr con un archivo re-descargado con sufijo `" (1)"` en el nombre y confirmar que se detecta igual que el original.

### Cómo validar la salida
- Comparar manualmente una muestra de 5-10 instrumentos del consolidado contra los CSV originales, para confirmar que la normalización (porcentajes, fechas) es correcta.

### Rollout sugerido
- **Semana 1**: correr en paralelo al proceso manual actual, comparar resultados.
- **Semana 2**: usar el consolidado como única fuente para el análisis diario, mantener supervisión activa.
- **Semana 3-4**: revisar métricas de éxito, ajustar schema/alertas según lo que haya fallado.
- **Mes 2+**: evaluar si arrancar el diseño de Opportunity B (motor de detección de swaps) sobre esta base.

---

## Notas finales

- **Quién mantiene esta automatización si se rompe**: el usuario, con ayuda del agente (Claude/Claude Code) para diagnosticar y ajustar el script cuando doctacapital cambie un formato.
- **Qué pasa si el responsable se va o cambia de rol**: el script y el workflow quedan documentados en el repo (`tools/`, `workflows/`, y este spec) — cualquiera con Python básico puede retomarlo.
- **Frecuencia de revisión sugerida**: revisar el schema esperado cada vez que doctacapital cambie visiblemente su plataforma de exportación, o cuando el log de corrida muestre alertas repetidas.
- **Próximas mejoras posibles (fuera del v1)**:
  - Automatizar la descarga de los CSV si doctacapital habilita algún acceso programático (hoy no confirmado).
  - Mapeo de columnas asistido por IA como fallback ante cambios de formato (idea 3 de la Fase 3), si el mantenimiento manual del schema se vuelve muy frecuente.
  - Construir el motor de detección de swaps (Opportunity B) sobre este universo consolidado.
  - Extender a Opportunity C (armado de cartera nueva por perfil + cobertura de riesgos).
