# Diseño To-Be — Ingesta y consolidación del universo de instrumentos

Quick Win diseñado: **A — Ingesta y consolidación del universo de instrumentos** (pasos 2+3 del process map).

## Reto (HMW)

> ¿Cómo podríamos tener siempre a mano un universo de instrumentos limpio, actualizado y confiable — sin perder horas cruzando CSVs a mano cada vez que hay que analizar algo?

## Ideas consideradas

1. **ETL con reglas fijas (script Python)** — sin IA. **Elegida.**
2. Orquestador no-code (n8n/Make) + Google Sheets destino — descartada (depende de infraestructura externa innecesaria).
3. Mapeo de columnas asistido por IA ante cambios de formato — descartada por ahora, queda como mejora futura si el riesgo de formato roto se materializa seguido.
4. Agente orquestador (Claude) sobre tools determinísticas — descartada como núcleo: el usuario prefiere procesamiento de datos puro, sin razonamiento de IA en la lógica. El agente puede seguir usándose para disparar el script y comunicar resultados, pero la lógica es 100% determinística.
5. Estandarizar primero el proceso humano (Excel + Power Query) — descartada, no resuelve la base para construir el motor de swap (Opportunity B) después.
6. Google Sheets + Apps Script — descartada, no aporta sobre la opción elegida y suma dependencia externa.

**Decisión del usuario**: nada de IA "que razone" — el objetivo es análisis de datos duros con Python, determinístico.

## Flujo To-Be

**Trigger**: manual. El usuario descarga los CSV de doctacapital.com (corporativos hard-dollar, subsoberanos hard-dollar, acciones, CEDEARs, opciones, FCI) a una carpeta fija con nombres de archivo estables, y corre el script `tools/consolidar_universo.py` (directamente o pidiéndoselo al agente).

1. **Lectura y validación de schema**: se abre cada CSV y se chequea que las columnas esperadas estén presentes. Si a un archivo le falta o le sobra una columna respecto a lo esperado, no se sigue de largo: se registra una alerta puntual para ese archivo y se lo saltea, pero se sigue procesando el resto.
2. **Normalización**: conversión de formatos (`"7,40%"` → `0.074`, fechas a formato estándar, montos a numérico).
3. **Etiquetado por clase de activo**: cada instrumento se taggea según el archivo de origen (bono soberano, subsoberano, ON/corporativo, acción, CEDEAR, opción, FCI) y, donde aplica, por tipo de tasa (Tasa Fija / CER / Dólar Linked / Tamar / Badlar / Globales-Bonares / Bopreal-BCRA).
4. **Cruce con oferta Balanz**: se cruza contra una whitelist mantenida por el usuario (CSV con los tickers que Balanz ofrece), marcando cada instrumento como disponible o no.
5. **Consolidación**: unificación en un único dataset (`universo_consolidado.xlsx`, una hoja por clase + una hoja resumen) con columnas comunes (ticker, clase, TIR, duration, ley, moneda de pago, tipo de tasa, calificación, volumen, vencimiento, disponible en Balanz) más las específicas de cada clase.
6. **Log de corrida**: resumen de instrumentos por clase, altas/bajas respecto a la corrida anterior, y alertas de formato si las hubo.
7. **Output**: Excel consolidado + resumen de la corrida.

## Stress test — casos borde

| Escenario | Comportamiento esperado del sistema |
|---|---|
| Un CSV llega con columnas renombradas/faltantes | Loggear qué archivo y qué columna no matcheó; saltear solo ese archivo; seguir con el resto |
| El mismo ticker aparece en dos archivos con datos distintos | Marcar como duplicado para revisión manual, no quedarse con un valor "al azar" |
| La whitelist de Balanz no existe o está vacía | Advertir explícitamente que no se pudo filtrar por disponibilidad; nunca asumir todo/nada disponible |
| Un valor numérico no se puede parsear (TIR corrupta, celda vacía) | La fila queda en el output con flag "revisar"; no se descarta ni se fuerza un valor por defecto |
| Se corre el script dos veces el mismo día | Idempotente: la corrida nueva sobrescribe/actualiza el consolidado, no duplica filas |

Principio general: ningún caso falla en silencio — todo termina en un log visible.

## Comparación As-Is vs To-Be

| Paso | Antes (As-Is) | Después (To-Be) | Ahorro |
|---|---|---|---|
| Cruce CSV vs oferta Balanz | Manual, instrumento por instrumento | Automático vía whitelist | Alto |
| Normalización de datos (%, fechas, comas) | Manual en Excel | Automático | Alto |
| Consolidación en dataset único | Rehecho a mano cada vez | Un comando | Alto |
| Detección de formato roto en la fuente | No se detectaba, o tarde | Alerta explícita e inmediata | Medio-alto (evita análisis con datos malos) |
| Descarga de los CSV | Manual | Sigue manual (no hay API pública confirmada) | — |

**Ahorro total estimado**: pendiente de cuantificar en horas/mes tras las primeras semanas de uso — a revisar como métrica de éxito en la Fase 4.

## Rol humano residual

- Descargar los CSV de doctacapital (sigue siendo manual, no hay API confirmada).
- Mantener actualizada la whitelist de instrumentos ofrecidos por Balanz.
- Revisar las filas marcadas como "duplicado" o "revisar" antes de usarlas en un análisis.
- Todo el análisis de decisión (swap, armado de cartera) sigue siendo responsabilidad del usuario — este Quick Win solo deja la data lista, no decide nada.
