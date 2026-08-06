# Prompts — Fase 3: Diseñar la solución

---

## Prompt 1 — Formular el reto

Antes de idear soluciones, replantear el problema sin atarse a una herramienta.

```
El Quick Win que elegimos es: [descripción breve]

Reformulalo como una pregunta "¿Cómo podríamos…?" centrada en el resultado para el usuario o el proceso, NO en la solución técnica.

Ejemplo correcto: "¿Cómo podríamos darle respuesta inmediata al cliente sin que tenga que llamarnos?"
Ejemplo a evitar: "¿Cómo podríamos implementar un chatbot?"

Devolvé 2-3 variantes de la pregunta para elegir la mejor.
```

---

## Prompt 2 — Idear soluciones (brainstorming)

Generar opciones sin descartar ninguna todavía.

```
Para el reto: [pegar la pregunta "¿Cómo podríamos…?" elegida]

Generá 6 ideas distintas de cómo resolverlo, con esta diversidad:
- Al menos 1 que NO use IA (solo reglas / integración / formulario / plantilla)
- Al menos 2 que usen IA generativa (Claude, GPT)
- Al menos 1 que se enfoque en mejorar el proceso humano antes de meter tecnología
- Al menos 1 que sea "rara" o no convencional

Para cada idea:
- Nombre corto
- Descripción de 2-3 líneas
- Qué herramientas usaría (alto nivel: "un orquestador + IA", "formulario web + base de datos")
- Una limitación o riesgo principal

No las puntúes todavía, solo generalas.
```

---

## Prompt 3 — Elegir y desarrollar una idea

Filtrar y profundizar.

```
De las ideas generadas, elegí la que tenga la mejor relación valor / simplicidad para empezar.

Justificá la elección y desarrollá la idea como un flujo paso a paso en lenguaje natural:

1. ¿Qué dispara el flujo? (un mail, un mensaje, un horario, un formulario)
2. Cada paso intermedio: qué hace la máquina, qué hace el humano si interviene
3. ¿Qué pasa si los datos no encajan o algo falla? (manejo de excepciones)
4. ¿Qué se entrega al final?

Escribí el flujo como si se lo explicaras a un compañero que no estuvo en la conversación.
```

---

## Prompt 4 — Stress test del diseño

Detectar agujeros antes de pasar a especificar.

```
Para el flujo diseñado, pensá en 5 escenarios "borde" que podrían romperlo:
- ¿Qué pasa si el input viene mal formateado?
- ¿Qué pasa si una API externa está caída?
- ¿Qué pasa si la IA devuelve algo raro o incorrecto?
- ¿Qué pasa si llegan dos eventos simultáneos?
- ¿Qué pasa con datos que la automatización no contempla?

Para cada escenario, decí qué debería hacer el sistema (fallar silenciosamente NO es opción — debe avisar a un humano o tener un fallback).
```

---

## Prompt 5 — Comparación As-Is vs To-Be

Cerrar la fase visualizando el cambio.

```
Armá una tabla comparativa de 4-6 filas:

| Paso del proceso | Antes (As-Is) | Después (To-Be) | Tiempo ahorrado estimado |

Incluí solo los pasos donde la automatización cambia algo. Al final, calculá el ahorro total estimado por mes (horas × frecuencia).
```
