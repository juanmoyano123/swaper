"""Endpoints de renta variable — F-052. Router vacío, montado por adelantado.

Base común de la tanda 8b: el router se crea acá y se monta en `router.py` antes de soltar los
agentes, para que F-052 no tenga que editar un archivo que comparte con las otras tres features de
la tanda. Es la lección de la Tanda 1 — lo que colisionó no fue el código de las features, fueron
los archivos compartidos que ninguna había previsto.

**Por qué existe este módulo y no un parámetro más en `universo.py`.** La renta variable no está en
el listado del universo y no es un descuido: `segmentar()` la descarta *antes* de segmentar, porque
una acción no tiene TIR, ni duración, ni cronograma, y nunca fue comparable con un bono.
`Segmentacion.renta_variable` es un contador, no una lista — las filas se cuentan y se sueltan. Y
`EspecieUniverso` no puede representarlas: su `naturaleza` busca el segmento en `NATURALEZA_TASA` y
una acción no tiene ninguno.

Así que acá se lee aparte, con el mismo criterio que `posiciones/lectura.py` ya usa por esta misma
razón: SQL propio contra el universo consolidado, filtrando por `clase_activo`. El precedente está
escrito allá y conviene mirarlo antes de escribir el de acá.

**Lo que este recurso no va a tener nunca es una columna de rendimiento.** Ni TIR, ni nada puesto en
su lugar. Una acción no tiene TIR y presentar otra magnitud en esa columna sería exactamente lo que
la regla 2 prohíbe — y el hecho de que desde F-051 el universo de renta fija tenga TIR calculada no
cambia nada acá.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/renta-variable", tags=["renta variable"])

# F-052 monta acá `GET /especies?clase=accion|cedear`, paginado por cursor con el mismo patrón que
# `universo.vista_viva`. Ver `claude-docs/plans/F-052-plan.md`.
