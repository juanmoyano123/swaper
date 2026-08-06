# Template — Automation Spec

Plantilla del spec final implementable. Llenarla durante la Fase 4 una vez completado el diseño To-Be de la Fase 3.

Este documento debería ser autoexplicativo: alguien que no estuvo en las conversaciones previas debería poder leerlo y construir la automatización.

---

## Resumen ejecutivo

**Nombre de la automatización**:

**Qué hace** (2-3 frases):


**Qué problema resuelve**:


**Ahorro estimado**:
- Tiempo: ___ horas / mes
- Otros beneficios:

---

## Trigger

| Campo | Valor |
|-------|-------|
| **Tipo** | mail entrante / webhook / formulario / cron / mensaje en canal / manual |
| **Origen específico** | (ej: mail a soporte@empresa.com con asunto "Factura") |
| **Filtros previos** | (qué eventos sí y cuáles no disparan el flujo) |
| **Frecuencia esperada** | (X veces / día, hora pico) |

---

## Pasos detallados

### Paso 1 — [Nombre del paso]

- **Acción**: qué hace este paso
- **Input**: estructura del dato que recibe
  - Campos esperados:
  - Formato:
  - Ejemplo:
- **Lógica**: transformación, decisión, llamada a IA, regla
- **Output**: qué genera el paso, formato
- **Herramienta sugerida**: (ej. nodo Gmail de Make, llamada a OpenAI, Google Sheets)

### Paso 2 — [Nombre del paso]

- **Acción**:
- **Input**:
- **Lógica**:
- **Output**:
- **Herramienta sugerida**:

### Paso 3 — [Nombre del paso]

...

---

## Condiciones y ramificaciones

Si el flujo no es lineal, listar los caminos:

**Camino feliz**:
1. Paso 1 → Paso 2 → Paso 3 → fin OK

**Ramificación A** (condición: ___):
1. Paso 1 → Paso 2 → si [condición] → Paso 4 (manejo distinto)

**Manejo de excepciones**:
- Si falla la API externa: ___
- Si el input no se puede parsear: ___
- Si la IA devuelve algo inesperado: ___
- Si no hay datos: ___

> Regla general: ningún error debería pasar en silencio. Siempre debe haber notificación a un humano cuando se sale del happy path.

---

## Recursos necesarios

Lista de credenciales / cuentas / accesos / suscripciones que el usuario debe tener listos antes de construir.

- [ ] Cuenta de [herramienta de orquestación] activa
- [ ] API key de [servicio de IA] con créditos suficientes
- [ ] Acceso al sistema [X] (usuario / app password / OAuth)
- [ ] Permisos para escribir en [destino]
- [ ] Canal / inbox / sheet creado para resultados
- [ ] Persona o canal de escalado configurado para excepciones

---

## Herramienta recomendada

**Elección**: [Zapier / Make / n8n / Power Automate / Claude / combinación]

**Justificación** (4-6 líneas, específica para este flujo):


**Alternativas consideradas y por qué se descartaron**:


---

## Métricas de éxito

Cómo vamos a saber si la automatización funciona.

| Métrica | Tipo | Cómo medirla | Meta inicial |
|---------|------|--------------|---------------|
| Tiempo ahorrado por ejecución | Cuantitativa | Comparar duración antes/después | |
| % de casos manejados sin intervención humana | Cuantitativa | Conteo de escalados / total | |
| Errores reportados por usuarios | Cuantitativa | Tickets / quejas | |
| Satisfacción del equipo | Cualitativa | Pregunta directa a usuarios afectados | |

---

## Plan de testeo

Antes de poner en producción:

### Casos felices a probar
1.
2.
3.

### Casos borde a probar
1.
2.
3.

### Cómo validar la salida
-

### Rollout sugerido
- **Semana 1**: correr en paralelo al proceso manual, comparar resultados
- **Semana 2**: pasar a automático, mantener supervisión activa
- **Semana 3-4**: revisar métricas, ajustar
- **Mes 2+**: revisión periódica mensual

---

## Notas finales

- Quién mantiene esta automatización si se rompe:
- Qué pasa si el responsable se va o cambia de rol:
- Frecuencia de revisión sugerida:
- Próximas mejoras posibles (cosas que dejamos fuera del v1):
