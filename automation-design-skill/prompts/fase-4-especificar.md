# Prompts — Fase 4: Especificar para implementación

---

## Prompt 1 — Generar el blueprint completo

Convertir el diseño To-Be en spec implementable.

```
Te paso el diseño To-Be que armamos:

[pegar flujo de Fase 3]

Convertilo en un spec técnico estructurado con las siguientes secciones:

## Resumen ejecutivo
2 párrafos: qué hace la automatización, qué problema resuelve, qué ahorro genera.

## Trigger
Qué dispara el flujo. Especificar:
- Tipo (mail entrante / webhook / formulario / cron / mensaje en canal)
- Detalles del evento (filtros, asunto, remitente, etc.)

## Pasos detallados
Por cada paso del flujo, una sub-sección con:
- **Acción**: qué hace
- **Input**: estructura del dato que recibe (campos, formato, ejemplo si ayuda)
- **Lógica**: transformación / decisión / llamada a IA / regla
- **Output**: qué genera el paso, formato
- **Herramienta sugerida**: nombre concreto (Gmail node, OpenAI call, etc.)

## Condiciones y ramificaciones
Si el flujo tiene if/else, listarlos explícitamente. Cubrir el "happy path" y los caminos de excepción.

## Recursos necesarios
Lista de credenciales / cuentas / APIs / accesos que el usuario tiene que tener listas antes de construirlo.

## Métricas de éxito
2-4 indicadores con cómo medirlos:
- Cuantitativos (tiempo ahorrado, % de aciertos, volumen procesado)
- Cualitativos (satisfacción del usuario, reducción de errores reportados)

## Plan de testeo
Cómo probar el flujo antes de ponerlo en producción:
- Casos felices a probar
- Casos borde a probar
- Cómo validar que la salida es correcta

Devolvé todo el spec en Markdown estructurado.
```

---

## Prompt 2 — Elegir la herramienta

Después del spec, justificar la elección de plataforma.

```
Para el spec que armamos, recomendame UNA herramienta concreta para construirlo, eligiendo entre:
- Zapier
- Make
- n8n
- Power Automate
- Claude (agente / API directa)
- Combinación de varias

Justificá en 4-6 líneas:
- Por qué esta y no las otras
- Qué ventaja específica aporta para ESTE flujo (no respuestas genéricas)
- Qué tendría que cambiar para que la decisión fuera otra

Considerá: complejidad del flujo, integraciones necesarias, volumen estimado, perfil técnico del usuario, costo aproximado.
```

---

## Prompt 3 — Traducir un paso del spec a la herramienta

Útil al sentarse a construir, paso por paso.

```
En la herramienta [Make / n8n / Zapier / Claude / etc.], ¿cómo se construye este paso?

Paso del spec:
- Acción: [pegar]
- Input: [pegar]
- Lógica: [pegar]
- Output: [pegar]

Decime:
1. Qué nodo / módulo / acción usar
2. Qué configuración va en cada campo principal
3. Si requiere algún input previo (mapeo de datos del paso anterior)
4. Errores comunes al construir este tipo de paso

Si hay variantes según la herramienta, elegí la más simple.
```

---

## Prompt 4 — Checklist de pre-implementación

Validar que todo está listo antes de construir.

```
Antes de construir esta automatización, revisame el checklist:

1. ¿Tengo todas las credenciales y accesos listados en "Recursos necesarios"?
2. ¿El proceso As-Is está suficientemente estable como para automatizarlo (no va a cambiar la semana próxima)?
3. ¿Tengo definidas las métricas de éxito y cómo voy a medirlas?
4. ¿Tengo a quién notificar / escalar cuando la automatización detecte un caso que no puede manejar?
5. ¿Tengo un plan B si la automatización falla totalmente (vuelvo a hacerlo a mano sin perder data)?
6. ¿Estoy poniendo esto en un entorno donde puedo testear sin afectar datos reales primero?

Para los puntos donde diga "no", ayudame a resolver eso antes de construir.
```

---

## Prompt 5 — Después de implementar: medir y mejorar

Cerrar el ciclo.

```
Pasaron [X] semanas desde que puse en producción la automatización "[nombre]".

Datos que tengo:
- Volumen procesado: [N ejecuciones]
- Casos manejados automáticamente sin intervención: [N o %]
- Casos que escalaron a humano: [N o %]
- Errores o casos raros que noté: [descripción]
- Feedback de usuarios afectados: [si aplica]

Ayudame a:
1. Evaluar si está cumpliendo las métricas de éxito que definí
2. Identificar qué ajustes haría falta (prompt mejor, regla nueva, paso adicional)
3. Decidir si conviene escalar este patrón a otros procesos similares
```
