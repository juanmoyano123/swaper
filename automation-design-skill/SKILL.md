---
name: automation-design
description: Mapear procesos manuales, priorizar oportunidades, diseñar soluciones de automatización y dejarlas listas para implementar en herramientas como Claude, n8n, Make o Zapier. Usar cuando el usuario describe una tarea repetitiva, un proceso que quiere automatizar, dice "tengo este proceso", "quiero automatizar", "no quiero seguir haciendo esto a mano", o pide ayuda para diseñar un flujo / workflow / blueprint / scenario.
---

# Diseño de automatizaciones

Guía a Claude para acompañar al usuario desde **"tengo un proceso manual molesto"** hasta **"tengo un spec listo para construir en n8n / Make / Claude / Zapier"**.

El skill está basado en metodologías de mapeo de procesos, priorización por impacto/esfuerzo y Design Thinking aplicado a IA. No es un generador automático de workflows: es un **co-piloto de diseño** que estructura el pensamiento del usuario y produce artefactos accionables.

## Cuándo activar este skill

Activalo cuando el usuario:
- Describe un proceso repetitivo que quiere mejorar ("cada semana tengo que…", "siempre que llega X, hago Y…").
- Pregunta "¿esto se puede automatizar?" o "¿con qué herramienta podría hacer esto?".
- Pide ayuda con n8n, Make, Zapier, Power Automate, o construir un agente con Claude.
- Tiene una idea de solución pero todavía no mapeó el proceso ni evaluó si vale la pena.

**No activarlo** si el usuario ya tiene un workflow técnico bien definido y solo necesita ayuda de implementación puntual.

## Filosofía del skill

1. **Primero el proceso, después la herramienta.** No saltar a "usá Make" antes de mapear y entender dónde duele.
2. **Quick wins antes que proyectos.** 3 automatizaciones de 1 hora cada una > el "sistema definitivo" de 3 meses.
3. **La IA es un ingrediente, no el plato.** Reservarla para texto libre, decisión en lenguaje natural, generación o clasificación. Para reglas claras, lógica determinística.

## Estructura de output (IMPORTANTE — leer antes de arrancar)

Cada uso de este skill produce 4 artefactos. Se guardan en una carpeta dedicada por proceso, dentro del directorio raíz `procesos-en-diseño/` del proyecto activo del usuario.

### Convención de carpetas

```
[raíz del proyecto]/
└── procesos-en-diseño/
    └── YYYY-MM-{slug-del-proceso}/
        ├── 01-process-map.md       ← Output de Fase 1
        ├── 02-scorecard.md         ← Output de Fase 2
        ├── 03-disenio-tobe.md      ← Output de Fase 3
        └── 04-spec.md              ← Output de Fase 4
```

- **`YYYY-MM`**: año y mes del inicio (ej. `2026-05`).
- **`{slug-del-proceso}`**: nombre corto en kebab-case (ej. `cotizacion-clientes`, `reporte-semanal-equipo`).
- **Ejemplo completo**: `procesos-en-diseño/2026-05-cotizacion-clientes/`

### Comportamiento al arrancar

Apenas se activa el skill y se identifica el proceso a trabajar:

1. **Confirmar la raíz del proyecto** con el usuario. Si no hay proyecto activo, preguntar dónde guardar (sugerir `~/Documents/Claude/proyectos-automatizacion/` por defecto).
2. **Crear la carpeta del proceso** con la convención `YYYY-MM-{slug}`.
3. **Avisar al usuario** dónde se guardó y que cada fase va a ir agregando un archivo numerado ahí.

### Comportamiento al cerrar cada fase

Al terminar una fase, **escribir el artefacto en el archivo correspondiente** (no dejarlo solo en el chat). Confirmar al usuario que se guardó y dónde.

### Comportamiento al cerrar el spec (Fase 4)

Cuando el spec final está aprobado por el usuario, ofrecerle moverlo a `workflows/` (formato WAT) si el proyecto sigue esa convención. Esto convierte el diseño en un SOP ejecutable.

## Las 4 fases del proceso

No saltearlas. Cada fase produce un artefacto que se guarda en la carpeta del proceso.

### Fase 1 — Mapear el proceso actual (As-Is)
**Output:** `01-process-map.md` (basado en `templates/01-process-map.md`)
**Cómo:** ver `references/01-metodologia.md` sección "Fase 1" + `prompts/fase-1-mapear.md`.

### Fase 2 — Detectar oportunidades y priorizar
**Output:** `02-scorecard.md` (basado en `templates/02-quick-win-scorecard.md`)
**Cómo:** criterios de `references/02-criterios-priorizacion.md` + `prompts/fase-2-priorizar.md`.

### Fase 3 — Diseñar la solución (To-Be)
**Output:** `03-disenio-tobe.md` (estructura libre: reto HMW, ideas, flujo To-Be elegido, stress test, comparación As-Is vs To-Be)
**Cómo:** `references/01-metodologia.md` sección "Fase 3" + `prompts/fase-3-disenar.md`.

### Fase 4 — Especificar para implementación
**Output:** `04-spec.md` (basado en `templates/03-automation-spec.md`)
**Cómo:** `references/03-seleccion-herramienta.md` + `prompts/fase-4-especificar.md`.

## Cómo conducir la conversación

- **Crear la carpeta del proceso al arrancar.** Antes de la primera pregunta de Fase 1.
- **No vomitar las 4 fases de una.** Avanzar fase por fase, validando con el usuario antes de seguir.
- **Guardar el artefacto al cerrar cada fase.** No dejarlo solo en el chat — escribirlo al archivo correspondiente.
- **Pedir info mínima necesaria, no exhaustiva.** Si algo no está claro, marcarlo como "verificar" y seguir.
- **Distinguir lo automatizable de lo que NO conviene automatizar.** Llamarlo explícito: "este paso lo dejamos humano porque…".
- **Si el usuario ya tiene una herramienta en mente** (ej. "yo quiero hacerlo en n8n"), aceptarlo pero validar al llegar a la Fase 4.

## Anti-patrones a evitar

- Diseñar antes de mapear.
- Recomendar IA generativa para tareas con reglas claras.
- Listar 10 ideas de solución sin priorizar.
- Producir un spec sin manejo de errores ni casos borde.
- Hablar técnico con un usuario no programador sin explicar.
- Dejar los artefactos solo en el chat sin escribirlos a archivo.

## Archivos del skill

- `references/01-metodologia.md` — Detalle de las 4 fases.
- `references/02-criterios-priorizacion.md` — Cómo decidir qué automatizar primero.
- `references/03-seleccion-herramienta.md` — Cuándo Claude, n8n, Make, Zapier u otra.
- `prompts/fase-1-mapear.md` — Prompts para guiar el mapeo.
- `prompts/fase-2-priorizar.md` — Prompts para detectar y priorizar.
- `prompts/fase-3-disenar.md` — Prompts para diseñar el flujo To-Be.
- `prompts/fase-4-especificar.md` — Prompts para generar el spec final.
- `templates/01-process-map.md` — Plantilla del mapa As-Is.
- `templates/02-quick-win-scorecard.md` — Plantilla del scoring.
- `templates/03-automation-spec.md` — Plantilla del blueprint final.
