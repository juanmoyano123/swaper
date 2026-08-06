# Process Map (As-Is) — Búsqueda de instrumentos para armado de carteras y swaps

## Información general

| Campo | Valor |
|-------|-------|
| **Nombre del proceso** | Búsqueda y análisis de ONs, bonos, letras y otros instrumentos para armado de carteras a medida y detección de swaps |
| **Objetivo** (¿qué entrega al final?) | Un análisis/documento interno (no entregable a cliente) que identifica: (a) instrumentos candidatos a rotación (swap) con mejor retorno a igual o menor riesgo, y/o (b) una propuesta de asignación de cartera por clase de activo según el objetivo del cliente/asesor |
| **Frecuencia** | Diaria / "always-on" — no se dispara por un hecho puntual único, sino que el usuario necesita mantener el universo de instrumentos actualizado para responder cualquier consulta en cualquier momento |
| **Volumen** | Variable — depende de consultas entrantes + revisión proactiva diaria |
| **Tiempo total promedio por ejecución** | Alto (no cuantificado en horas exactas) — el usuario indica que le lleva bastante tiempo porque no tiene un método sistemático para hacerlo hoy |
| **Personas involucradas** | Principalmente el usuario. El equipo (grupo de WhatsApp de research) aporta ideas de swap ya elaboradas que pueden usarse como input adicional |
| **Herramientas usadas** | Plataforma Balanz, doctacapital.com (descarga de CSV/Excel de monitoreo), Excel, WhatsApp (grupo de research del equipo) |
| **Dolor principal hoy** (en una frase) | Descargar y cruzar manualmente varios archivos CSV distintos (por categoría de instrumento) contra lo que ofrece Balanz, y comparar variables (TIR, duration, riesgo crediticio, moneda, liquidez) instrumento por instrumento a mano |

---

## Restricción clave de diseño (confirmada por el usuario)

El análisis **no debe basarse en búsqueda libre en la web**. Las fuentes válidas son:
1. Los archivos que el usuario provee directamente (CSVs exportados de doctacapital.com, exports de Balanz).
2. Fuentes cuya confiabilidad se acuerde de antemano explícitamente.

No se debe scrapear ni consultar sitios no verificados para completar datos de instrumentos.

---

## Pasos del proceso

| # | Paso | Entrada | Acción | Salida | Responsable | Herramienta | Formato del input |
|---|------|---------|--------|--------|-------------|-------------|--------------------|
| 1 | Disparo | Consulta de cliente / consulta de asesor productor / detección propia de TIR baja o negativa / cobro de cupón a reinvertir / idea de swap compartida por el equipo en WhatsApp | Se identifica la necesidad: armar cartera nueva, rotar (swap) instrumentos, o reinvertir un cupón cobrado | Objetivo definido (armar / rotar / reinvertir) | Usuario | WhatsApp, mail, plataforma Balanz | Mensaje, consulta verbal, dato visto en pantalla |
| 2 | Descarga de universo de instrumentos | Sitio doctacapital.com | Descarga de CSV/Excel de "monitoreo" por categoría: corporativos hard-dollar (ONs), subsoberanos hard-dollar, acciones, CEDEARs, opciones, FCI | Set de archivos CSV con precio, TIR, duration, ley, calificación crediticia, vencimiento, moneda de pago, volumen, etc. | Usuario | doctacapital.com | CSV descargable |
| 3 | Consulta de oferta propia | Plataforma Balanz | Verificación de qué instrumentos del universo descargado están efectivamente disponibles para operar en Balanz | Universo filtrado a "lo que ofrecemos" | Usuario | Plataforma Balanz | Consulta manual en plataforma |
| 4a | **[Camino Swap]** Detección de oportunidad | CSVs de monitoreo (TIR, duration, ley, moneda, calificación, volumen por instrumento) + eventualmente ideas ya elaboradas por el equipo vía WhatsApp | Búsqueda de instrumentos con TIR baja/negativa y comparación contra alternativas de duration y riesgo crediticio similar, evaluando también ley (ARG/NY), moneda de pago (MEP/Cable), indexación (CER/dólar-linked/tasa fija/hard-dollar), liquidez (volumen) y costo de la operación (arancel ~0.75%) vs. beneficio esperado | Lista de pares "rotar X → Y" con TIR origen/destino, vencimientos, y costo de comisión estimado vs. beneficio | Usuario (a veces con aporte del equipo) | Excel manual, comparación visual tipo gráfico TIR vs Duration | Análisis manual, sin plantilla fija |
| 4b | **[Camino Cartera nueva]** Definición de perfil | Conversación con cliente/asesor: objetivo (CP/MP/LP), monto, moneda, apetito de riesgo, necesidad de renta mensual vs. crecimiento, o necesidad de cobertura de un riesgo específico (cambiario, regional, crediticio, inflación) | Definición de % objetivo por clase de activo (ej. 75% Renta Fija / 25% Renta Variable, combinando FCI + CEDEARs + Bonos + ONs) | Estructura de asignación por clase de activo | Usuario | Criterio propio / plantilla en Excel | Definición manual |
| 5 | Selección de instrumentos dentro de cada clase | Universo filtrado (paso 3) + variables clave (TIR, duration, calificación crediticia, sector, ley, moneda, indexación, liquidez) | Selección de instrumentos concretos dentro de cada clase, buscando diversificación por sector/emisor y ponderación adecuada, y (si aplica) alineación con el riesgo específico a cubrir | Lista de instrumentos con nominales, monto, % del total | Usuario | Excel manual | — |
| 6 | Armado del análisis interno | Datos de los pasos 4/5 | Consolidación en un documento/Excel de trabajo con distribución, calendario de cobros estimado, TNA/TIR promedio, duration promedio — **de uso interno del usuario**, no un entregable pulido | Excel/documento interno con el análisis y la propuesta de asignación | Usuario | Excel | — |
| 7 | (Opcional, fuera de alcance) Armado de entregable para cliente | Análisis interno del paso 6 | Cuando corresponde presentar a un cliente/asesor, el usuario arma la presentación final (PPTX) **por su cuenta**, a partir del análisis interno | Presentación/PPTX para cliente | Usuario | PowerPoint | — |

> **Nota de alcance**: los pasos 6 y 7 tienen distinto nivel de automatización deseado. El usuario solo necesita automatizar hasta el paso 6 (análisis interno). El armado del entregable pulido para cliente (paso 7) lo sigue haciendo manualmente y queda **fuera del alcance** de esta automatización.

---

## Observaciones por paso

- **Paso 1**: el grupo de WhatsApp del equipo de research es una fuente adicional de ideas de swap ya elaboradas (con gráfico TIR vs Duration, instrumento origen/destino, comisión estimada). Se puede usar como input válido cuando el usuario lo pega/comparte explícitamente — no implica scraping ni búsqueda libre.
- **Paso 2-3**: cuello de botella principal — descargar manualmente ~6-7 CSV distintos de doctacapital y cruzarlos a mano con la oferta de Balanz.
- **Paso 4a**: criterio de swap del equipo, ya formalizable: diferencial de TIR + duration similar + misma calidad crediticia + moneda de pago (evitar costo implícito de canje ARS→Cable) + liquidez suficiente + que el beneficio supere el costo de arancel de la operación (~0.75%).
- **Paso 4b/5**: existe una plantilla madura de armado de cartera (Excel "Propuesta Base 7-26"), con distribución por clase de activo, sector y calificación crediticia. Extensión deseada: armar carteras **por tipo de cobertura de riesgo** (cambiario, regional, crediticio, inflación) — es una extensión del criterio de selección, no un proceso nuevo.
- **Paso 6**: la salida esperada de la automatización. El usuario después, si necesita un entregable prolijo, lo arma él mismo (paso 7, fuera de alcance).
- **Riesgo crediticio**: la calificación que trae el CSV de doctacapital es el punto de partida. El usuario hace después, manualmente, un análisis crediticio interno más profundo — la automatización no debe intentar reemplazar ese análisis profundo, solo surtir la calificación base y dejarla disponible.

## Criterios de riesgo confirmados para clasificar instrumentos (a formalizar en Fase 3)

1. **Riesgo regional/legal**: ley de emisión (ARG vs NY) para bonos/ONs; país de la empresa subyacente para acciones/CEDEARs.
2. **Riesgo cambiario**: moneda de pago del instrumento (MEP vs Cable).
3. **Tipo de tasa/indexación** *(confirmado, con la segmentación real que usa doctacapital para bonos soberanos)*: Tasa Fija, CER, Dólar Linked, Tamar, Badlar, Globales/Bonares (hard-dollar), Bopreal/BCRA. Esta misma lógica de segmentación por tasa aplica como variable de análisis, no solo a soberanos — hay que verificar si ONs/subsoberanos tienen la misma taxonomía en doctacapital.
4. **Riesgo de liquidez** *(propuesto, a confirmar)*: volumen operado (tradeVolume/effectiveVolume).
5. **Riesgo de concentración** *(propuesto, a confirmar)*: por emisor y por sector.
6. **Riesgo crediticio**: calificación del instrumento/emisor (dato base de doctacapital + análisis interno posterior del usuario, fuera de alcance de la automatización).

---

## Variantes del proceso

- **Variante Swap** (paso 4a): dispara por TIR baja detectada por el usuario o sugerida por el equipo.
- **Variante Cartera nueva** (paso 4b): dispara por consulta de cliente/asesor sin cartera previa, incluyendo el caso de armado por cobertura de un riesgo específico.
- **Variante Reinversión de cupón**: híbrida — hay que decidir dónde reinvertir un monto ya definido por el cobro de un cupón; similar a "cartera nueva" pero con el monto fijo de entrada.

---

## Preguntas pendientes / a verificar

- Tiempo exacto que insume cada ejecución del proceso (se sabe que es "mucho", pero no está cuantificado en horas — se puede estimar en Fase 2 con un rango).
- Confirmar si los criterios propuestos de liquidez y concentración se suman tal cual al set de variables de análisis.
- Verificar si ONs y subsoberanos tienen la misma taxonomía por tipo de tasa (Tasa Fija / CER / Dólar Linked / Tamar / Badlar) que los soberanos, o si ese desglose es exclusivo de la sección "Soberanos" de doctacapital.
- Definir con qué frecuencia real se re-descargan los CSV de doctacapital (¿diaria, varias veces al día?) para dimensionar el paso de actualización de datos.
