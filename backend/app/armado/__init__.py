"""El armado asistido: una cartera de arranque a partir del mandato del cliente — F-019.

Port de las cuatro funciones de `tools/armar_cartera.py` (`resolver_mix`, `candidatos_del_segmento`,
`elegir_siguiente`, `armar`) sin la cáscara de CLI. Sin pandas: el resto del backend fuera de
`ingesta/byma/` trabaja sobre listas y dataclasses, y este paquete sigue ese estilo.

## Reuso, no reimplementación

Los perfiles (`PERFILES`, `min_sectores`) y `sector_computable` vienen de
`app.concentracion.perfiles` — **no se copian acá**. La clave de riesgo (`clave_riesgo`,
`es_soberano`) viene de
`app.concentracion.riesgo`. Este paquete es lo nuevo: el algoritmo de selección y el criterio de
reparto sectorial que F-020 no tiene.

## La forma del paquete

    constantes.py   BANDA_RENDIMIENTO, MIX_COBERTURA, HORIZONTES — portados tal cual del motor.
    parametros.py   ParametrosArmado, el modelo Pydantic que reemplaza argparse.
    motor.py        resolver_mix, filtrar_por_moneda, candidatos_del_segmento, elegir_siguiente,
                     armar, percentil_lineal. → ResultadoArmado. Puro.

No hay `lectura.py`: el universo llega saneado desde `app/universo/servicio.py`, así que todo lo de
acá es función pura y el endpoint es lo único que toca la base.
"""
