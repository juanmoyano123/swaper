# Prompts — Fase 1: Mapear el proceso

Prompts copiables para usar con Claude (o cualquier asistente) durante la fase de mapeo. Reemplazar lo que está entre corchetes `[...]`.

---

## Prompt 1 — Arranque del mapeo

Usar cuando el usuario quiere empezar a mapear un proceso pero no sabe cómo estructurar la información.

```
Quiero mapear un proceso que hago seguido para evaluar si lo puedo automatizar.

El proceso se llama: [nombre breve, ej. "Procesar facturas de proveedores"]

Lo que pasa hoy, en mis palabras: [descripción libre de 3-6 líneas — cómo arranca, qué hago, cómo termina]

Frecuencia: [diaria / semanal / mensual / irregular] — aproximadamente [N] veces por [período]
Tiempo que me lleva por ejecución: [X minutos / horas]
Personas que intervienen: [solo yo / yo + jefe / 3 áreas]
Herramientas que uso: [Gmail, Excel, sistema X, WhatsApp, etc.]

Ayudame a estructurar este proceso en pasos numerados, donde cada paso tenga:
- Qué entra (input)
- Qué acción se hace
- Qué sale (output)
- Quién lo hace
- Qué herramienta usa
- Formato del input (mail / PDF adjunto / fila de Excel / mensaje / etc.)

Devolvémelo como tabla. Si tenés dudas sobre algún paso, marcalo y preguntame.
```

---

## Prompt 2 — Profundización en un paso específico

Usar cuando un paso del mapa quedó vago.

```
En el proceso que estamos mapeando, el paso [N] ("[título del paso]") me quedó poco claro.

Lo que sé es: [descripción de lo que hace]

Ayudame a desgranarlo: ¿qué sub-pasos podría tener? ¿qué información necesito tener clara para automatizarlo después? Hacé preguntas específicas si necesitás info.
```

---

## Prompt 3 — Detectar dolor y cuellos de botella

Usar después de tener el mapa para hacer aflorar dónde duele.

```
Te paso el mapa del proceso que armamos:

[pegar la tabla del mapa]

Quiero que me ayudes a identificar:

1. ¿En qué pasos se acumula trabajo pendiente o hay demoras esperando a alguien?
2. ¿Qué pasos son los más propensos a error (porque son repetitivos, cansadores o tienen muchos detalles)?
3. ¿Qué pasaría con este proceso si el volumen se multiplicara por 10?
4. ¿Hay algún paso que dependa de una sola persona y bloquee al resto?
5. ¿Qué pasos son los que más "duelen" subjetivamente (los más aburridos, los que más posterga el equipo)?

Devolvémelo como lista comentada por paso.
```

---

## Prompt 4 — Validación del mapa

Cerrar la fase asegurando que el mapa refleja la realidad.

```
Repasemos el mapa final. ¿Hay algún paso que falte o esté mal descrito? ¿El orden es correcto? ¿Hay variantes del proceso que no contemplé (por ejemplo, cuando el cliente manda los datos por mail vs por WhatsApp)?
```
