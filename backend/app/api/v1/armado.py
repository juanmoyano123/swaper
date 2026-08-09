"""Endpoints del armado asistido — F-019, Tanda 10.

Router vacío montado antes de soltar los agentes en paralelo: F-019 lo llena solo, y ninguno de
los otros dos agentes de la tanda (F-022, F-025) necesita tocar `router.py` para agregarlo.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/armado", tags=["armado"])
