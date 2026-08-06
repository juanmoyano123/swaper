"""Endpoints de sesión y contexto de usuario (F-014).

Router vacío a propósito, por la misma razón que `jobs.py`: montarlo desde ya evita que dos
features del mismo lote editen `router.py` a la vez.

El grueso de la autenticación no vive acá: Supabase Auth maneja el login desde el frontend con la
anon key, y el backend sólo valida el JWT que le llega. Lo que corresponda exponer —el perfil del
usuario de la sesión, por ejemplo— va en este módulo.
"""

from fastapi import APIRouter

router = APIRouter()
