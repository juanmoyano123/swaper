"""Límites de concentración de una cartera en construcción — F-020.

Montado vacío por la base común de la Tanda 9, con el criterio que documenta `router.py`: se
monta antes de soltar los agentes para que ninguno tenga que editar el router raíz.

F-020 agrega acá `POST /concentracion`, que recibe las posiciones con su peso y el perfil, y
devuelve el estado de cada tope —soberano, por emisor y por sector—, la distribución por sector,
ley y naturaleza de tasa, y las advertencias. El cálculo vive en `app/concentracion/`, puro y sin
base; este módulo sólo lo expone.
"""

from fastapi import APIRouter

router = APIRouter(tags=["concentracion"])
