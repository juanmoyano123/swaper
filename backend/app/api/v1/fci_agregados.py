"""Endpoints agregados de FCI — F-067 (categorías, gestoras).

Router montado vacío junto con la base común de la Tanda 2 (23/08/2026), antes de soltar los
agentes de F-067 y F-046 en paralelo: mismo criterio que `renta_variable.py` en la Tanda 8b — el
archivo que ambas features comparten (`router.py`) se toca una sola vez, a mano, para que ninguna
de las dos tenga que editarlo.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/fci/agregados", tags=["fci"])
