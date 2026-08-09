"""Motor de rotaciones intra-segmento — F-032.

Montado vacío por la base común de la Tanda 12, con el criterio que documenta `router.py`: se
monta antes de soltar los agentes para que ninguno tenga que editar el router raíz.

F-032 agrega acá `POST /rotaciones`, con el mismo contrato que `POST /concentracion`: posiciones
explícitas por cuerpo (nunca por identificador de cartera) y perfil por query string. El motor
vive en `app/rotaciones/`, envoltura de `tools/detectar_swaps.py`; este módulo sólo lo expone.
"""

from fastapi import APIRouter

router = APIRouter(tags=["rotaciones"])
