"""Rutas de la ingesta de IAMC — F-005.

El informe llega por subida manual, así que acá vive el endpoint que lo recibe. El router está
vacío y ya montado en `router.py`.
"""

from fastapi import APIRouter

router = APIRouter(tags=["iamc"])
