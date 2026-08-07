"""Router raíz de la versión 1 del API.

Cada feature agrega su módulo en `app/api/v1/` y lo monta acá. El prefijo `/api/v1` se aplica
una sola vez, en `create_app()`: ninguna ruta lo repite y por lo tanto ninguna puede olvidarlo.

Los routers de las tres fuentes ya están montados aunque todavía no expongan rutas. Es a propósito:
se construyen en paralelo, y si cada una tuviera que agregarse acá al terminar, las tres editarían
este archivo a la vez. `calendario` (F-015) y `posiciones` (F-029) están montados por lo mismo.
`instrumentos` (F-039) también: la Tanda 7 la construye junto a F-018, que es frontend puro.
`renta_variable` (F-052) es de la Tanda 8b y sigue el mismo criterio: se monta vacío antes de
soltar los agentes para que ninguno de los cuatro tenga que tocar este archivo.
"""

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    byma,
    calendario,
    condiciones,
    consolidar,
    docta,
    estado,
    health,
    iamc,
    instrumentos,
    jobs,
    posiciones,
    renta_variable,
    universo,
)

router = APIRouter()
router.include_router(health.router)
router.include_router(byma.router)
router.include_router(iamc.router)
router.include_router(docta.router)
router.include_router(consolidar.router)
router.include_router(jobs.router)
router.include_router(auth.router)
router.include_router(condiciones.router)
router.include_router(universo.router)
router.include_router(calendario.router)
router.include_router(posiciones.router)
router.include_router(estado.router)
router.include_router(instrumentos.router)
router.include_router(renta_variable.router)
