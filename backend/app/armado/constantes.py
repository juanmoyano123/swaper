"""Las constantes del armado, portadas tal cual de `tools/armar_cartera.py:40-89`.

`PERFILES` y `SECTORES_EXENTOS` **no están acá**: F-019 los importa de `app.concentracion.perfiles`,
que ya los porta con `min_sectores` agregado por F-020. Duplicarlos acá haría que "moderado"
significara dos cosas distintas según qué pantalla lo mire — el mismo razonamiento que ya escribe el
docstring de `perfiles.py`.
"""

# Cuánto rendimiento se tolera resignar para ganar un mes de cobro nuevo. 0.5pp es el mismo
# umbral con el que la mesa evalúa un swap: por debajo de eso la diferencia de tasa no justifica
# mover nada, así que ahí sí conviene desempatar por calendario.
BANDA_RENDIMIENTO = 0.005

# Mix objetivo por objetivo de cobertura, en % del total.
MIX_COBERTURA: dict[str, dict[str, float]] = {
    "devaluacion": {"usd_hard": 70, "dollar_linked": 30},
    "inflacion": {"cer": 100},
    "tasa-pesos": {"tasa_fija": 60, "badlar": 20, "tamar": 20},
    "mixta": {"usd_hard": 50, "cer": 25, "tasa_fija": 15, "dollar_linked": 10},
}

# Rango de duration (años) por horizonte. Los rangos se solapan a propósito: la frontera entre corto
# y mediano plazo no es rígida.
HORIZONTES: dict[str, tuple[float, float]] = {
    "corto": (0.0, 2.0),
    "medio": (1.5, 5.0),
    "largo": (4.0, 99.0),
}
