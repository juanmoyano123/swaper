"""Límites de concentración de una cartera en construcción — F-020.

Montado vacío por la base común de la Tanda 9, con el criterio que documenta `router.py`: se
monta antes de soltar los agentes para que ninguno tenga que editar el router raíz.

F-020 agrega acá `POST /concentracion`, que recibe las posiciones con su peso y el perfil, y
devuelve el estado de cada tope —soberano, por emisor y por sector—, la distribución por sector,
ley y naturaleza de tasa, y las advertencias. El cálculo vive en `app/concentracion/`, puro y sin
base; este módulo sólo lo expone.

## Por qué va por POST y con las posiciones explícitas

Mismo contrato que `POST /calendario/cartera`, y por las mismas dos razones. Va por POST porque lo
que entra son decenas de pares ticker/peso: meterlos en la URL los expondría en cada log de acceso
y chocaría con el límite de largo antes de lo que parece. Y las posiciones viajan **explícitas y no
por identificador de cartera** porque este servicio mide lo que se le da: sirve igual para una
cartera guardada, para una propuesta que todavía no existe y para el "antes y después" de un swap.

El perfil va por query string y no en el cuerpo: es el parámetro contra el que se mide, no parte de
la cartera. La misma cartera se puede pedir contra los tres perfiles y son tres respuestas
distintas del mismo objeto.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.deps import get_db
from app.concentracion.servicio import Posicion, evaluar_concentracion
from app.universo.servicio import sanear_universo

router = APIRouter(tags=["concentracion"])

MAX_POSICIONES = 500

# Los tres perfiles, escritos como `Literal` para que un perfil inventado muera en la validación con
# 422 y no adentro del servicio. `test_concentracion_api` verifica que esta lista y las claves de
# `PERFILES` sigan siendo la misma: si alguien agrega un cuarto perfil y se olvida de acá, el
# endpoint lo rechazaría sin que ningún otro test se entere.
NombreDePerfil = Literal["conservador", "moderado", "agresivo"]


class PosicionEntrada(BaseModel):
    """Una posición de la cartera: qué especie y cuánto pesa.

    Es **la especie** y no la emisión, igual que en el calendario: el asesor tiene RUCED o RUCEO, y
    buscar la emisión en vez de la especie haría desaparecer del panel la posición que sí tiene.
    """

    ticker: str = Field(min_length=1, max_length=20)
    peso: float = Field(ge=0)
    """En puntos porcentuales (16.5 = 16,5 %), tal como los declara el armador. **No se normalizan
    a 100**: si la cartera no suma 100, eso se mide tal cual y se declara — es la misma regla con la
    que F-018 muestra la ponderación pedida y la real sin hacerlas coincidir."""


class CarteraEntrada(BaseModel):
    posiciones: list[PosicionEntrada] = Field(min_length=1, max_length=MAX_POSICIONES)


@router.post(
    "/concentracion",
    summary="Los topes de concentración y la distribución de una cartera, contra un perfil",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def concentracion(
    conn: Annotated[object, Depends(get_db)],
    entrada: CarteraEntrada,
    perfil: Annotated[
        NombreDePerfil, Query(description="Contra qué perfil se miden los topes.")
    ] = "moderado",
) -> dict[str, object]:
    """El estado de cada tope, la distribución en tres cortes y las advertencias.

    **Informa, no bloquea**: la respuesta es siempre 200 aunque haya topes excedidos. Un tope roto
    no es un error del pedido — es un hecho de la cartera que el asesor tiene que ver antes de
    proponerla, y devolver 4xx obligaría al frontend a tratar como falla lo que es el resultado.

    El universo llega **saneado** y en su vista viva: saneado porque medir la concentración de una
    especie cuyo precio está mal escalado propagaría el error de F-010, y viva porque la posición
    que el asesor tiene es la especie, no la emisión.

    Las posiciones que no están en el universo de renta fija —FCI, acciones, un ticker mal escrito—
    **no participan de ningún tope** y se nombran con cuánto pesan: medir el resto y presentarlo
    como el total sería declarar una cobertura que no se tiene.
    """
    saneado = await sanear_universo(conn)
    resultado = evaluar_concentracion(
        [Posicion(ticker=p.ticker, peso=p.peso) for p in entrada.posiciones],
        saneado.especies,
        perfil,
    )
    return resultado.como_dict()
