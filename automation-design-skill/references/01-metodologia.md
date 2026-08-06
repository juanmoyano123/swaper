# Metodología — Las 4 fases en detalle

Este documento expande cómo trabajar cada fase. Leerlo antes de empezar la conversación con el usuario o cuando necesites recordar qué hacer en una fase específica.

---

## Fase 1 — Mapear el proceso actual (As-Is)

### Qué es

Un proceso es **Entrada → Acción → Salida**. Mapearlo es escribir la secuencia ordenada de pasos que ocurren hoy, con suficiente detalle para entender dónde duele, sin ahogarse en micro-pasos.

### Qué tiene que producir

Una tabla con una fila por paso y estas columnas mínimas:

| # | Paso | Entrada | Acción | Salida | Responsable | Herramienta | Formato del input |

Ver `templates/01-process-map.md`.

### Cómo conducir esta fase

1. **Acotar el proceso.** Pedirle al usuario que elija UN proceso específico (no "todo lo que hago"). Buen nivel: "Procesar las facturas que llegan por mail cada semana". Mal nivel: "La gestión administrativa".
2. **Pedir descripción narrativa libre primero.** Que cuente el proceso de corrido en sus palabras antes de meterlo en la tabla. Eso revela el cómo lo piensa él y captura matices que perdería si va directo a tabla.
3. **Convertir esa narrativa en pasos.** Mostrar la tabla parcialmente completada y pedir validación.
4. **Para cada paso, completar las columnas.** Si el usuario duda sobre el formato del input ("¿llega por mail o por Slack?"), marcarlo como "verificar" y seguir.
5. **Identificar el objetivo del proceso.** Una línea: "El resultado final que este proceso entrega es _____". Si no es claro, posiblemente el proceso esté mal definido.

### Qué información buscar activamente

- **Frecuencia**: ¿diaria, semanal, mensual, irregular?
- **Volumen**: ¿cuántas veces al mes/semana se ejecuta?
- **Duración por ejecución**: minutos / horas.
- **Dolor del usuario**: ¿qué es lo peor de hacer esto?
- **Errores comunes**: ¿qué se rompe? ¿qué hay que rehacer?
- **Variabilidad**: ¿cada ejecución es igual o varía mucho?
- **Personas involucradas**: ¿solo él, o pasa por varias manos?

### Señales de buen mapeo

- Cada paso tiene un verbo claro (recibir, validar, ingresar, enviar, revisar).
- Se puede identificar exactamente dónde termina un paso y empieza el siguiente.
- Las herramientas están nombradas (Gmail, Excel, CRM específico, no "el sistema").
- Los formatos de entrada/salida están claros (PDF adjunto, fila en planilla, mensaje de WhatsApp).

### Errores comunes a evitar

- **Mapear lo que debería ser, no lo que es.** Ej: si en la realidad la aprobación pasa por WhatsApp aunque oficialmente sea por mail, registrar WhatsApp.
- **Saltar a la solución mientras se mapea.** "Acá podríamos usar IA" — anotalo aparte para la Fase 3, no contamines el mapa.
- **Mezclar dos procesos distintos.** Si el usuario empieza a hablar de otro flujo, parar y elegir uno.

---

## Fase 2 — Detectar oportunidades y priorizar

### Qué es

Tomar el process map de la Fase 1 y, paso por paso, etiquetar qué tipo de tarea es y cuán automatizable resulta. Luego puntuar para sacar Quick Wins.

### Qué tiene que producir

Una tabla scorecard (ver `templates/02-quick-win-scorecard.md`) donde cada paso (o agrupación de pasos relacionados) tiene:
- Tipo de tarea
- ¿Repetitivo? ¿Escalable? ¿Reglas claras?
- Score de Quick Win
- Categoría: ✅ Quick Win / 🚧 Proyecto estratégico / ⚙️ Mejora menor / ❌ No automatizar

### Cómo conducir esta fase

1. **Etiquetar cada paso con un tipo.** Categorías típicas:
   - **Repetitiva** (hace lo mismo cada vez)
   - **De espera** (el proceso se atasca esperando respuesta de alguien)
   - **Costosa en tiempo** (consume horas de gente cara)
   - **Basada en reglas claras** (decisiones determinísticas)
   - **Difusa / subjetiva** (requiere juicio humano, no se automatiza)
   - **Cuello de botella** (donde se acumula trabajo pendiente)

2. **Para los pasos candidatos, puntuar.** Usar la fórmula y criterios de `references/02-criterios-priorizacion.md`.

3. **Validar con el usuario.** "Veo 3 quick wins acá: X, Y, Z. ¿Cuál te genera más dolor hoy?". La urgencia subjetiva pesa.

4. **Cerrar con una decisión.** "Vamos a diseñar la automatización de X primero". Sin esta decisión explícita, no avanzar a Fase 3.

### Decisión clave: ¿Automatizar o no?

No todo lo automatizable conviene automatizar. Aplicar este filtro:

- **Si la tarea ocurre <1 vez por mes y es rápida** → probablemente no vale la pena.
- **Si la tarea requiere criterio humano complejo** → mantener manual, quizá asistir con IA.
- **Si automatizar exige integrar con sistemas a los que no se tiene acceso** → escalar a IT o postergar.
- **Si automatizarla mal genera riesgos serios** (datos sensibles, transacciones financieras críticas) → priorizar diseño cuidadoso, no apurar.

---

## Fase 3 — Diseñar la solución (To-Be)

### Qué es

Para el Quick Win elegido en la Fase 2, definir cómo va a funcionar el flujo automatizado. Es un ejercicio de Design Thinking adaptado: empatizar con el usuario que va a usar la automatización, definir bien el problema, idear el flujo, prototipar mentalmente.

### Qué tiene que producir

Un diseño narrado del flujo To-Be con:
- Quién dispara el proceso y cómo
- Qué pasos va a hacer la máquina vs el humano
- Dónde queda IA explícita (interpretar texto, clasificar, generar respuesta) y dónde son reglas simples
- Manejo de excepciones (¿qué pasa si los datos no encajan?)
- Comparación As-Is vs To-Be

### Cómo conducir esta fase

1. **Reafirmar el problema con la pregunta "¿Cómo podríamos…?"**
   - Mal: "¿Cómo podríamos implementar un chatbot?"
   - Bien: "¿Cómo podríamos darle respuesta inmediata al cliente sin que tenga que llamarnos?"
   - Esto evita atarse a una solución prematuramente.

2. **Generar 3-5 ideas de cómo resolverlo.** No solo con IA. Algunas opciones típicas:
   - Plantilla / formulario estructurado que reemplaza texto libre
   - Disparador automático con reglas (sin IA)
   - Bot que sigue un árbol de decisiones
   - Agente con IA generativa que interpreta y responde
   - Integración entre dos sistemas sin tocar al usuario

3. **Elegir UNA idea para diseñar el flujo.** Criterio: la más simple que resuelve el 80% del problema.

4. **Dibujar el flujo paso a paso.** Usar lenguaje natural primero, ej:
   ```
   Trigger: llega un mail con asunto "Factura proveedor"
   1. Sistema extrae el PDF adjunto
   2. IA lee el PDF y saca: proveedor, monto, fecha, número
   3. Si el monto coincide con una orden de compra → marcar como verificada
   4. Si no coincide → mandar a revisión humana en Slack
   5. Si verificada → registrar en planilla y archivar PDF en carpeta correspondiente
   ```

5. **Pensar en los bordes.**
   - ¿Qué pasa si el PDF está mal escaneado?
   - ¿Qué pasa si el proveedor no está en la base?
   - ¿Cuándo NO automatizar y escalar a humano?

6. **Identificar el rol humano residual.** Casi siempre queda algo para el humano: supervisar, aprobar, manejar excepciones. Eso es bueno — no se trata de reemplazar a la persona, se trata de sacarle la parte aburrida.

### Comparación As-Is vs To-Be

Cerrar esta fase con una tabla simple:

| Paso | Antes (As-Is) | Después (To-Be) | Ahorro estimado |
|------|---------------|------------------|------------------|

Esto le da al usuario una visualización del valor antes de pasar a especificar la implementación.

---

## Fase 4 — Especificar para implementación

### Qué es

Pasar del diseño narrado al spec técnico que puede traducirse a una herramienta concreta. Es el artefacto que el usuario (o alguien más) va a usar para construir el workflow en n8n / Make / Claude / Zapier / Power Automate.

### Qué tiene que producir

Un automation spec (ver `templates/03-automation-spec.md`) con estas secciones:

1. **Resumen ejecutivo** (1-2 párrafos): qué hace la automatización y por qué.
2. **Trigger** (qué la dispara): mail, formulario, webhook, scheduler, mensaje, etc.
3. **Pasos detallados**, cada uno con:
   - Acción
   - Input que recibe (estructura/formato)
   - Lógica o transformación
   - Output que genera
   - Herramienta sugerida (sin atarse a una si hay alternativas)
4. **Condiciones / ramificaciones**: if/else, manejo de excepciones.
5. **Recursos necesarios**: credenciales de qué sistemas, accesos, claves de API.
6. **Herramienta recomendada y por qué**: aplicar criterios de `references/03-seleccion-herramienta.md`.
7. **Métricas de éxito**: cómo vamos a saber si funciona (tiempo ahorrado, % de aciertos, etc.).
8. **Plan de testeo**: cómo probarlo antes de poner en producción real.

### Cómo conducir esta fase

1. **Repasar el diseño To-Be y traducirlo a estructura formal.**
2. **Para cada paso, ser explícito sobre el formato de datos** que entra y sale. Esto es lo que más cuesta cuando se construye en una herramienta real.
3. **Decidir la herramienta** consultando `references/03-seleccion-herramienta.md`. Justificar la elección — no recomendar la herramienta "de moda".
4. **Listar los recursos** que el usuario va a necesitar conseguir (cuenta de OpenAI, acceso a la API de Gmail, etc.).
5. **Mostrar el spec completo al usuario y validarlo.** Ofrecer ajustar el nivel de detalle si quedó muy técnico o muy abstracto.

### Indicador de spec bien hecho

Si una persona técnica que no estuvo en las conversaciones anteriores puede leer el spec y ponerse a construir sin tener que volver a preguntar al usuario qué hace cada paso, el spec está bien.

### Qué NO incluir en esta fase

- Código real. Esto es un spec, no la implementación.
- Pseudocódigo extenso. Si hace falta lógica compleja, describirla en lenguaje natural y dejar que la herramienta o un desarrollador la traduzca.
- Justificaciones largas sobre por qué automatizar — eso ya quedó en las fases anteriores.

---

## Iteración entre fases

Las fases NO son lineales puras. Es esperable:

- En Fase 2, descubrir que el mapa de Fase 1 estaba incompleto → volver y completarlo.
- En Fase 3, darse cuenta que la idea elegida no funciona → volver a Fase 2 y elegir otro Quick Win.
- En Fase 4, ver que un paso es más complejo de lo previsto → revisar Fase 3.

Esto es normal y esperado. Lo importante es que cada fase tenga su artefacto cerrado antes de pasar a la siguiente — pero ese artefacto se puede revisar si la fase posterior obliga.
