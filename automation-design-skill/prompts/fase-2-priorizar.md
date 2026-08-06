# Prompts — Fase 2: Detectar oportunidades y priorizar

---

## Prompt 1 — Clasificar cada paso

Usar después del mapa para etiquetar pasos según tipo de tarea.

```
Te paso el mapa de mi proceso:

[pegar tabla de Fase 1]

Para cada paso, clasificalo según:

a) Tipo de tarea:
   - Repetitiva (lo mismo cada vez)
   - De espera (el proceso se atasca esperando algo)
   - Costosa en tiempo (consume horas valiosas)
   - Basada en reglas claras (decisiones determinísticas)
   - Difusa / subjetiva (juicio humano)
   - Cuello de botella (donde se acumula pendiente)

b) ¿Es escalable hoy? (Si el volumen subiera x10, ¿el paso sigue funcionando?)

c) ¿Es automatizable con herramientas no-code o IA?
   - Sí, claramente
   - Parcialmente (algunas partes sí, otras requieren humano)
   - No (requiere criterio humano complejo)

Devolvémelo como tabla con una fila por paso y una columna por dimensión. Para cada "Sí" o "Parcial", agregá una línea de justificación corta.
```

---

## Prompt 2 — Score de Quick Win

Usar para puntuar cada oportunidad detectada.

```
De los pasos que clasificamos como automatizables, asigná a cada uno un puntaje de 1 a 5 en:

- Impacto (cuánto valor genera automatizarlo: tiempo ahorrado, errores reducidos, mejor experiencia)
- Urgencia (cuán doloroso es hoy hacerlo manual)
- Esfuerzo (cuánto cuesta implementarlo: tiempo, complejidad técnica)
- Riesgo (qué tan grave es si la automatización falla)
- Dependencias (cuántas personas/áreas externas hay que involucrar)

Calculá el score:
Score = (Impacto + Urgencia) − (Esfuerzo + Riesgo + Dependencias)

Devolvémelo como tabla ordenada de mayor a menor score, con una columna final de categoría:
- ✅ Quick Win si score ≥ 5
- 🚧 Proyecto estratégico si score entre 0 y 4
- ❌ No automatizar por ahora si score < 0
```

---

## Prompt 3 — Decisión final

Cerrar la fase eligiendo qué automatizar primero.

```
Con todo esto, recomendame 1 (máximo 2) Quick Win para empezar. Justificá:
- Por qué este y no los otros
- Qué resultado esperamos en 2-4 semanas
- Qué riesgo deberíamos tener en cuenta

Si hay dos casi empatados, ofrecé los dos y dejame elegir.
```

---

## Prompt 4 — Defender o descartar

Útil cuando el usuario tiene apego a una idea que el score no recomienda.

```
La opción "[nombre del paso/idea]" me sigue tentando aunque el score no la priorizó. Argumentá:

a) Si vale la pena rescatarla (por qué el score podría estar subestimándola)
b) O si conviene dejarla pendiente y por qué

Sé honesto, no me digas que sí solo para complacerme.
```
