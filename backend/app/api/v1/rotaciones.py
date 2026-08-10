"""Motor de rotaciones intra-segmento — F-032.

Montado vacío por la base común de la Tanda 12, con el criterio que documenta `router.py`: se
monta antes de soltar los agentes para que ninguno tenga que editar el router raíz.

F-032 agrega acá `POST /rotaciones`, con el mismo contrato que `POST /concentracion`: posiciones
explícitas por cuerpo (nunca por identificador de cartera) y perfil por query string. El motor
vive en `app/rotaciones/`, envoltura de `tools/detectar_swaps.py`; este módulo sólo lo expone.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.deps import get_db
from app.rotaciones.servicio import detectar_rotaciones

router = APIRouter(tags=["rotaciones"])

MAX_POSICIONES = 500

# Mismo criterio que `app/api/v1/concentracion.py`: un `Literal` propio en el endpoint, no
# importado de `app.concentracion.perfiles` (que no expone un tipo, sólo el dict `PERFILES`), así
# que un perfil inventado muere en la validación con 422 y no adentro del servicio.
NombreDePerfil = Literal["conservador", "moderado", "agresivo"]


class OrigenEntrada(BaseModel):
    """Una posición de origen: sólo el ticker. A diferencia de `/concentracion`, acá no hace falta
    el peso — el motor propone rotaciones por posición, no mide la cartera como conjunto."""

    ticker: str = Field(min_length=1, max_length=20)


class CarteraEntrada(BaseModel):
    posiciones: list[OrigenEntrada] = Field(min_length=1, max_length=MAX_POSICIONES)


@router.post(
    "/rotaciones",
    summary="Rotaciones candidatas dentro del mismo segmento, para cada posición de una cartera",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def rotaciones(
    conn: Annotated[object, Depends(get_db)],
    entrada: CarteraEntrada,
    perfil: Annotated[
        NombreDePerfil, Query(description="Contra qué perfil se derivan los filtros del motor.")
    ] = "moderado",
) -> dict[str, object]:
    """Las rotaciones candidatas de cada posición, más el premio por legislación de la curva y la
    hoja de sensibilidad de lo que aparece en las candidatas.

    **Siempre 200**, igual que `/concentracion` y `/armado`: no hay candidatas es un resultado
    válido (una cartera ya óptima, o sin alternativas dentro de su segmento), no un error del
    pedido. El único 422 es un perfil inventado o una cartera vacía.

    Cada candidata trae el costo real de rotar (arancel + spread bid/ask de las dos patas,
    F-035). Sin dos puntas vivas en alguna pata el costo no se calcula y la candidata queda
    `verificable=false`; la alerta `costo_no_verificable` avisa cuáles.
    """
    tickers = [p.ticker for p in entrada.posiciones]
    resultado = await detectar_rotaciones(conn, tickers, perfil)
    return resultado.como_dict()
