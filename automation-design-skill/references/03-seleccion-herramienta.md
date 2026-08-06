# Selección de herramienta

Cuándo recomendar Claude, n8n, Make, Zapier, Power Automate u otra opción. Y por qué.

---

## Mapa rápido por tipo de automatización

| Necesidad principal | Herramienta sugerida | Por qué |
|---------------------|----------------------|---------|
| Conectar 2-3 apps con un trigger simple | **Zapier** | Más fácil, librería enorme de integraciones, curva plana. |
| Flujo con múltiples ramificaciones, iteraciones, lógica visual | **Make (Integromat)** | Editor visual más potente, mejor manejo de arrays y data flow complejo. |
| Flujo complejo, self-hosted, control total, integración con APIs propias | **n8n** | Open source, se puede correr en propia infra, nodos custom. Más curva. |
| Entorno Microsoft (Outlook, Teams, SharePoint, Dynamics) | **Power Automate** | Integración nativa con stack MS, AI Builder para OCR/forms. |
| Conversación con texto libre, decisión en lenguaje natural, generación de contenido | **Claude (agente / API)** | Cuando el corazón del problema es lenguaje, no orquestación. |
| Lectura/extracción de datos de documentos no estructurados | **Claude + Make/n8n** o **Power Automate AI Builder** | Combinación de IA para entender + orquestador para mover datos. |
| Chatbot conversacional para usuarios | **Claude API + canal (WhatsApp/web)** o **Botmaker, Landbot, ManyChat** | Plataformas dedicadas si se quiere UI lista, API directa si se quiere control. |
| Robotización de UI legacy sin APIs | **UiPath, Power Automate Desktop** | RPA clásico: el bot mueve el mouse y tipea por el humano. |

---

## Cuándo usar Zapier

**Sí cuando:**
- El flujo es lineal: "cuando pasa X, hacer Y, después Z".
- Las apps involucradas tienen integración nativa en Zapier.
- El usuario nunca usó herramientas de automatización antes.
- Volumen bajo-medio (Zapier cobra por ejecución).

**No cuando:**
- El flujo necesita loops complejos, iterar sobre arrays, ramificaciones múltiples.
- Hay que procesar grandes volúmenes (se vuelve caro rápido).
- Se necesita lógica condicional anidada (Zapier la tiene pero es limitada).

---

## Cuándo usar Make

**Sí cuando:**
- El flujo tiene varias ramificaciones (if/else múltiples).
- Hay que iterar sobre listas (procesar 20 filas de un Excel, por ejemplo).
- El usuario quiere ver el flujo como un diagrama visual.
- Necesita debugging visual paso a paso de qué pasó en cada ejecución.
- Quiere conectar IA (OpenAI/Anthropic) como un nodo más del flujo.

**No cuando:**
- El usuario prefiere algo aún más simple (ir a Zapier).
- Necesita correr en su propia infraestructura por compliance (ir a n8n self-hosted).

---

## Cuándo usar n8n

**Sí cuando:**
- Se necesita self-hosting (datos sensibles, compliance, control total).
- El usuario o su equipo tiene perfil técnico y va a mantener el sistema.
- Se quiere flexibilidad total (nodos custom en JavaScript, integraciones propias).
- Se busca evitar costos por ejecución a largo plazo.

**No cuando:**
- El usuario es no-técnico y necesita algo que "funcione solo".
- No tiene infraestructura ni quien la administre.
- El flujo es simple y Zapier/Make alcanza.

---

## Cuándo usar Power Automate

**Sí cuando:**
- La organización ya está en el ecosistema Microsoft 365.
- Hay que automatizar tareas en Outlook, Teams, SharePoint, Excel Online, Dynamics.
- Se necesita RPA Desktop (automatizar apps Windows legacy).
- AI Builder cubre necesidades de OCR o forms con buena precisión.

**No cuando:**
- La organización no está en Microsoft (puede hacerse pero pierde la ventaja de integración nativa).
- Se busca flexibilidad de integraciones con herramientas modernas no-MS.

---

## Cuándo usar Claude directamente (sin orquestador)

A veces el "automatismo" no necesita un Zapier/Make en el medio: alcanza con un agente Claude bien configurado.

**Sí cuando:**
- El corazón del problema es procesar lenguaje (clasificar, resumir, responder, redactar).
- El usuario va a invocarlo manualmente o desde una interfaz simple (Cowork, Claude Code, app propia).
- Las acciones se pueden expresar como "tools" que Claude llama (function calling).
- No hay necesidad de un trigger continuo (mail entrante, formulario web).

**No cuando:**
- Hace falta un disparador automático en background (ahí necesitás orquestador).
- Hay que procesar volumen alto sin intervención (ahí Make/n8n son más baratos por ejecución).
- El flujo es lineal y determinístico (no aporta valor pagar tokens de IA).

### Patrón Claude + orquestador

Muy común y muy útil:

```
[Trigger] → [Make/n8n recibe] → [Llama a Claude para parte de lenguaje] → [Make/n8n hace acciones determinísticas con el output] → [Sale al sistema final]
```

Ejemplo: mail entrante → Make lo recibe → Claude lee y clasifica + extrae datos → Make actualiza un CRM y notifica por Slack.

---

## Decisión por perfil del usuario

| Perfil | Recomendación primaria |
|--------|------------------------|
| No-programador, organización chica, primera automatización | **Zapier** (o Make si necesita lógica) |
| No-programador con experiencia previa, casos complejos | **Make** |
| Equipo técnico, autonomía completa, self-hosted | **n8n** |
| Empresa Microsoft, compliance MS | **Power Automate** |
| Power user de IA, automatizaciones de productividad personal | **Claude (Cowork, Skills, API)** |

---

## Costo, una nota corta

Todos estos servicios tienen tiers gratuitos limitados y pricing por uso. Cuando el flujo va a ejecutarse miles de veces al mes, hay que hacer cuenta:

- **Zapier**: pricing por "tarea" (cada acción individual). Se encarece rápido con volumen.
- **Make**: pricing por operaciones. Suele ser más barato que Zapier para volumen.
- **n8n**: gratis si self-hosted; cloud tiene pricing propio.
- **Power Automate**: licencia por usuario o por flujo. Si la empresa ya paga M365, puede estar incluido en cierto nivel.
- **Claude API**: pricing por tokens (input + output). Para procesar mucho texto, sumar el costo en el cálculo.

> Para Quick Wins iniciales, el costo no suele ser bloqueante. Para escalar a producción, hay que dimensionar.

---

## Cómo justificar la elección en el spec

Cuando se cierre el spec en la Fase 4, no decir solo "usamos Make". Justificar en una línea:

> **Herramienta sugerida: Make.** Elegida porque el flujo tiene 3 ramificaciones (mail con OK / mail con error / sin respuesta tras 24h), iteración sobre filas de un Excel, e integración con OpenAI como nodo. Zapier no maneja bien iteración; n8n sería excesivo sin necesidad de self-hosting.

Eso le da al usuario contexto para defender la decisión y para reconsiderar si las condiciones cambian.
