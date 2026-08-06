"""Endpoints de sesión y contexto de usuario (F-014).

El grueso de la autenticación no vive acá: Supabase Auth maneja el login desde el frontend con la
anon key, y el backend sólo valida el JWT que le llega (`app/api/deps.get_usuario_actual`, que
verifica contra `app/core/seguridad.py`). Lo que corresponda exponer sobre esa sesión va en este
módulo.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_usuario_actual
from app.core.seguridad import UsuarioAutenticado

router = APIRouter(tags=["autenticación"])


class UsuarioActualResponse(BaseModel):
    id: str
    email: str | None


@router.get(
    "/auth/me",
    response_model=UsuarioActualResponse,
    summary="Quién es el asesor de la sesión actual",
    responses={
        401: {"description": "No hay sesión válida"},
        503: {"description": "Falta configurar SUPABASE_JWT_SECRET"},
    },
)
async def usuario_actual(
    usuario: Annotated[UsuarioAutenticado, Depends(get_usuario_actual)],
) -> UsuarioActualResponse:
    """Confirma la sesión y devuelve el `id` del asesor.

    El frontend lo usa para verificar contra el backend que el token que guarda todavía es
    válido —por ejemplo al recuperar una sesión persistida—, sin tener que decodificarlo del lado
    del cliente para saberlo.
    """
    return UsuarioActualResponse(id=str(usuario.id), email=usuario.email)
