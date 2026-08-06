"""Endpoints del job programado de ingesta (F-008).

Router vacío a propósito: se monta en `router.py` desde ya para que la feature que lo llene no
tenga que editar ese archivo mientras otra feature del mismo lote lo edita también. Es el mismo
patrón que se usó con los routers de las tres fuentes en F-004 a F-006.
"""

from fastapi import APIRouter

router = APIRouter()
