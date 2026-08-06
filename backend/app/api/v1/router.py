"""Router raíz de la versión 1 del API.

Cada feature agrega su módulo en `app/api/v1/` y lo monta acá. El prefijo `/api/v1` se aplica
una sola vez, en `create_app()`: ninguna ruta lo repite y por lo tanto ninguna puede olvidarlo.
"""

from fastapi import APIRouter

from app.api.v1 import health

router = APIRouter()
router.include_router(health.router)
