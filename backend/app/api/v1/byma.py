"""Rutas de la ingesta de BYMA — F-004.

El router está vacío y ya montado en `router.py`: F-004 agrega sus rutas acá sin tocar ningún otro
archivo compartido.
"""

from fastapi import APIRouter

from app.ingesta.byma import ingerir_rueda

router = APIRouter(tags=["byma"])


@router.post("/byma/ingesta")
async def disparar_ingesta_byma() -> dict[str, object]:
    """Corre la ingesta de los cinco endpoints de BYMA y devuelve el snapshot de la corrida.

    POST porque dispara una acción con efectos (tránsito de red, corrida de ingesta), no una
    lectura. Devuelve 200 aunque haya endpoints caídos: la semántica de "la corrida corrió y esto
    es lo que declaró" vive en `snapshot.completo` y sus alertas, no en el status HTTP. Nunca
    viajan las filas -del orden de miles-: esta respuesta es para ver el estado de la corrida, no
    para transportar el universo.
    """
    resultado = await ingerir_rueda()
    return {"snapshot": resultado.snapshot.como_dict()}
