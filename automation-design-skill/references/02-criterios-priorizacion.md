# Criterios de priorización

Cómo decidir qué automatizar primero, qué postergar, y qué no automatizar.

---

## La matriz Impacto vs Esfuerzo

Toda idea de automatización se ubica en uno de cuatro cuadrantes:

|                  | **Bajo esfuerzo**             | **Alto esfuerzo**            |
|------------------|-------------------------------|-------------------------------|
| **Alto impacto** | ✅ **Quick Win** — empezar acá | 🚧 **Proyecto estratégico** — planificar |
| **Bajo impacto** | ⚙️ **Mejora menor** — si sobra tiempo | ❌ **No vale la pena** — descartar |

### Cómo estimar impacto

Pensar en al menos uno de estos vectores:

- **Tiempo ahorrado por mes** (horas × frecuencia). Una tarea de 30 min que se hace 20 veces al mes ahorra 10 horas mensuales — eso es alto.
- **Reducción de errores**: si la tarea manual falla y eso cuesta caro (re-trabajo, clientes molestos, multas, contabilidad rota), automatizar mejora la calidad.
- **Velocidad de respuesta**: si el cliente o el usuario interno espera y eso impacta su experiencia, ahorrar minutos puede valer mucho.
- **Escalabilidad**: si el volumen va a crecer 5-10x el año que viene, automatizar prepara para eso. Si va a quedar estable y bajo, importa menos.
- **Energía mental liberada**: a veces el valor no está en el tiempo cronométrico sino en el alivio de no tener que pensar en eso.

### Cómo estimar esfuerzo

Pensar en:

- **Complejidad técnica**: ¿es disparar un trigger simple, o requiere lógica con ramificaciones, scraping, modelos entrenados?
- **Disponibilidad de herramientas**: ¿ya existe la integración (Gmail ↔ Sheets vía Zapier), o hay que construirla?
- **Dependencias externas**: ¿depende de IT, de un proveedor, de cambiar políticas internas?
- **Costo monetario**: APIs pagas, suscripciones a plataformas, créditos de IA.
- **Curva de aprendizaje**: si nunca usé la herramienta, súmale tiempo de aprendizaje.
- **Riesgo de implementación**: ¿qué pasa si el automatismo se rompe? ¿cuán crítico es?

---

## Score de Quick Win (fórmula numérica)

Cuando hay varias ideas y no es obvio cuál priorizar, asignar puntaje 1-5 a cada dimensión:

```
Score = (Impacto + Urgencia) − (Esfuerzo + Riesgo + Dependencias)
```

| Dimensión        | 1                   | 3                  | 5                       |
|------------------|---------------------|--------------------|-------------------------|
| **Impacto**      | Marginal            | Notable            | Transformador           |
| **Urgencia**     | Puede esperar meses | Conviene este mes  | Urgente, duele cada día |
| **Esfuerzo**     | Horas               | Días               | Semanas                 |
| **Riesgo**       | Casi nulo           | Manejable          | Datos sensibles, alto impacto si falla |
| **Dependencias** | Solo yo             | Depende de 1 persona | Depende de IT/múltiples áreas |

- **Score ≥ 5**: candidato fuerte a Quick Win.
- **Score 0-4**: probablemente proyecto estratégico — planificar pero no apurar.
- **Score < 0**: no automatizar por ahora.

> El score es una guía, no un dictamen. A veces conviene tirar la tabla y elegir por intuición ("esto me está consumiendo, lo automatizo aunque el score no sea el más alto"). La fórmula sirve para tener una conversación estructurada, no para tomar la decisión sola.

---

## Criterios de automatizabilidad (¿se puede automatizar?)

Independiente de si conviene, hay que ver si técnicamente se puede. Una tarea es candidata fuerte cuando cumple varios de estos:

✅ **Tiene reglas claras**: las decisiones se pueden expresar como if/else. "Si el monto es menor a X y el cliente es de tipo Y, aprobar".

✅ **La información está digital y estructurada**: viene en mail, formulario, Excel, base de datos. Si está en papel o en la cabeza de alguien, primero hay que digitalizarla.

✅ **Los inputs tienen formato estable**: las facturas del proveedor X siempre se ven igual. Si cada input es un caos distinto, automatizar es más caro.

✅ **El output puede validarse automáticamente**: hay forma de chequear que la automatización hizo bien su trabajo. Si solo se valida con criterio humano, el costo de mantenerla es alto.

✅ **El volumen justifica el esfuerzo**: hay suficiente repetición para que valga la pena montar el sistema.

### Cuándo NO es buena candidata

❌ **Requiere juicio subjetivo complejo**: evaluar un diseño creativo, negociar precio, decidir un ascenso.

❌ **Cada caso es muy distinto**: si no hay patrón, no hay nada que automatizar — solo asistir.

❌ **El proceso está mal definido o cambia seguido**: primero estabilizarlo, después automatizar.

❌ **Los datos son demasiado sensibles para pasar por sistemas externos**: pueden existir restricciones de compliance, secreto profesional, etc.

❌ **El costo del error es altísimo y la confianza en el sistema sería baja**: en esos casos, asistir al humano puede ser mejor que reemplazarlo.

---

## Cuándo IA generativa vs reglas simples

Una vez decidido que algo se automatiza, queda elegir el "tipo" de automatización. No todo necesita IA.

### Usar IA generativa (GPT/Claude) cuando:

- Hay **texto libre en la entrada** que hay que interpretar (mails de clientes, descripciones, comentarios).
- Hay que **generar contenido** (resúmenes, redacción de respuestas, emails personalizados).
- Hay que **clasificar texto** en categorías donde no hay reglas obvias (sentimiento, urgencia, tema).
- Hay que **extraer datos estructurados de documentos no estructurados** (facturas, contratos, CVs).

### Usar lógica determinística / reglas cuando:

- Las decisiones siguen un árbol claro de if/else.
- Los inputs ya vienen estructurados (formulario, base de datos, API).
- Las consecuencias de equivocarse son altas y se quiere control total.
- Es más barato y rápido (no se paga API ni se gasta tokens).

### Usar agentes con tools / function calling cuando:

- Hay que **encadenar varias acciones** que dependen de lo que devolvió la anterior.
- La IA necesita **consultar sistemas externos** (buscar en una base, llamar a una API, leer un archivo).
- El flujo no es lineal y puede ramificarse según contexto.

### Una pauta práctica

Empezar pensando "¿se puede hacer con reglas?". Si sí, hacerlo con reglas. Solo cuando aparece **texto libre que entender** o **decisión que requiere lenguaje**, meter IA generativa. Esto ahorra costos, latencia y errores impredecibles.

---

## La trampa del "automatizo todo"

Una vez que el usuario engancha con esta metodología, la tentación es automatizar cada paso. Recordar:

- **El humano agrega valor real en algunos pasos.** Pelearlos por ahorrar 2 minutos no compensa la pérdida de control o sentido del trabajo.
- **Toda automatización tiene mantenimiento.** APIs que cambian, prompts que se desactualizan, edge cases nuevos. Cada automatismo es deuda técnica futura.
- **Mejor 3 automatizaciones que funcionan al 100% que 10 al 60%.** Lo último genera más fricción que ahorro.

Si el usuario quiere "automatizar todo el proceso", redirigirlo: identifiquemos los 2-3 pasos donde la automatización aporta más valor, y los demás se quedan como están (o se simplifican sin necesidad de tecnología).
