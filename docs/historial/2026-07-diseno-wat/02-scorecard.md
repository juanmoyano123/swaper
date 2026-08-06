# Quick Win Scorecard — Búsqueda de instrumentos para armado de carteras y swaps

## Clasificación de pasos

| # | Paso | Tipo de tarea | ¿Repetitiva? | ¿Escalable? | ¿Automatizable? | Justificación corta |
|---|------|---------------|---------------|-------------|-------------------|----------------------|
| 1 | Disparo | De espera / evento externo | ⚠️ | ✅ | ⚠️ Parcial | No es un "paso" automatizable en sí, pero la variante "detección propia de TIR baja" se resuelve como consecuencia de automatizar el paso 4a (motor de swap) |
| 2 | Descarga de universo (CSV doctacapital) | Repetitiva, cuello de botella | ✅ | ✅ | ✅ Sí | Archivos CSV con formato estable y estructurado, ideal para ETL simple |
| 3 | Consulta de oferta propia (Balanz) | Repetitiva | ✅ | ✅ | ⚠️ Parcial | No hay API de Balanz; se resuelve con una whitelist que el usuario mantiene y actualiza, respetando la restricción de "solo fuentes que el usuario provee" |
| 4a | Detección de swap | Reglas claras, cuello de botella | ✅ | ✅ | ✅ Sí | Comparar TIR/duration/ley/moneda/indexación/liquidez/costo de arancel es lógica determinística, no requiere IA generativa |
| 4b | Definición de perfil (cartera nueva) | Difusa (parte) + reglas claras (parte) | ⚠️ | ⚠️ | ⚠️ Parcial | Entender el objetivo del cliente es conversación humana; traducir "perfil → % por clase de activo" sí se puede reglar con plantillas |
| 5 | Selección de instrumentos por clase | Reglas claras | ✅ | ✅ | ✅ Sí | Filtrar y rankear candidatos por variables es automatizable; la elección final entre candidatos la sigue haciendo el usuario |
| 6 | Armado de análisis interno | Repetitiva, costosa en tiempo | ✅ | ✅ | ✅ Sí | Consolidar datos ya procesados en un output estructurado es mecánico una vez resueltos los pasos 2, 4a y 5 |
| 7 | Entregable a cliente | — | — | — | ❌ Fuera de alcance | Confirmado por el usuario: se sigue armando manualmente |

---

## Scoring de Quick Wins

**Fórmula**: `Score = (Impacto + Urgencia) − (Esfuerzo + Riesgo + Dependencias)`

| Oportunidad (paso o agrupación) | Impacto | Urgencia | Esfuerzo | Riesgo | Dependencias | **Score** | Categoría |
|---|---|---|---|---|---|---|---|
| **A. Ingesta y consolidación del universo de instrumentos** (pasos 2+3) | 5 | 5 | 2 | 1 | 1 | **6** | ✅ Quick Win |
| **B. Motor de detección de swaps** (paso 4a) | 5 | 4 | 3 | 2 | 1 | **3** | 🚧 Proyecto estratégico (pero es el corazón del valor de negocio) |
| **C. Armado de cartera nueva por perfil + cobertura de riesgo** (pasos 4b+5) | 4 | 3 | 4 | 2 | 1 | **0** | 🚧 Proyecto estratégico |
| **D. Documento de análisis interno consolidado** (paso 6) | 3 | 2 | 2 | 1 | 1 | **1** | 🚧 Proyecto estratégico / mejora menor |

**Nota sobre B**: queda justo debajo del umbral de Quick Win porque definir bien los umbrales de decisión (diferencial de TIR que justifica un swap, cómo ponderar duration vs riesgo crediticio) exige más esfuerzo que un ETL simple. Aun así es el paso de mayor valor de negocio. A y B están fuertemente encadenados: B necesita el universo consolidado que deja A, no son alternativas sino secuenciales.

---

## Decisión final

| Campo | Valor |
|-------|-------|
| **Quick Win elegido para Fase 3** | **A — Ingesta y consolidación del universo de instrumentos** (pasos 2+3 del process map) |
| **Por qué este y no otro** | Es el cuello de botella diario más pesado, tiene el score más alto, esfuerzo bajo (datos ya estructurados y con formato estable), y es prerrequisito técnico de B, C y D — sin un universo limpio y consolidado, el resto no puede construirse bien |
| **Resultado esperado en 2-4 semanas** | Un proceso que toma los CSV de doctacapital (corporativos hard-dollar, subsoberanos, acciones, CEDEARs, opciones, FCI) + la whitelist de lo que ofrece Balanz, y devuelve un universo limpio, unificado y con todas las variables clave por instrumento (TIR, duration, ley, moneda de pago, tipo de tasa/indexación, calificación, volumen), listo para analizar |
| **Riesgo principal a tener en cuenta** | doctacapital puede cambiar el formato de sus CSV (columnas, nombres) en algún momento y romper el ingest silenciosamente — el diseño debe validar el formato esperado y avisar si algo no matchea, en vez de fallar en silencio |

---

## Estado de ejecución (actualizado 26/07/2026)

- **A — Ingesta y consolidación** ✅ **Resuelto**. `tools/consolidar_universo.py`, ingesta 100% vía API de Docta (sin descarga manual). Genera `universo_consolidado.xlsx` (910 instrumentos) + `cashflow_completo.csv`. La whitelist de Balanz se descartó: es una ALyC con cobertura total del mercado local, el cruce no aportaba. Acciones, CEDEARs, opciones y FCI salieron del alcance — el proyecto es exclusivamente renta fija.
- **B — Motor de detección de swaps** ✅ **Resuelto**. `tools/detectar_swaps.py`, validado reproduciendo swaps reales de la mesa (TLCWO→TLCMO). Incluye chequeo de cupón próximo del bono a vender.
- **C — Armado de cartera por perfil + cobertura de riesgo** ✅ **Resuelto**. `tools/armar_cartera.py`. Cubre las 4 coberturas (devaluación, inflación, tasa en pesos, mixta), 3 perfiles y 3 horizontes, con control de concentración por emisor y de riesgo soberano agregado. Prioriza la continuidad del cobro mensual de cupones.
- **D — Documento de análisis interno consolidado** (paso 6): sin construir. Los Excel de salida de B y C cubren hoy la necesidad; el usuario arma el entregable al cliente por su cuenta.

### Extensión transversal: análisis de cupones ✅

`tools/cupones.py` — compartido por B y C. Se sumó después de cerrar ambos pilares, por pedido explícito: la previsibilidad del cashflow es la base sobre la que se fomenta la inversión en bonos, así que el calendario de cobros es criterio de armado, no reporte posterior.

## Pendientes reales

- **Ampliar la cobertura de `sector`**: hoy cubre 423 de 927 instrumentos (46%). Los 68 emisores corporativos clasificados están pendientes de revisión del usuario.
- **Unificar la segmentación** de `detectar_swaps.py` con la de `armar_cartera.py` (37 instrumentos hoy sin segmentar en el motor de swaps: Tamar, ONs dólar-linked, subsoberanos no hard-dollar).
