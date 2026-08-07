"""Endpoints de resolución de posiciones contra el universo — F-029.

Router vacío a propósito, creado antes que la feature, por la misma razón que `calendario.py`:
F-015 y F-029 corren en paralelo y ninguna de las dos debe tocar `api/v1/router.py`.

**El prefijo es `/posiciones` y no `/carteras`.** Lo que esta feature resuelve son las posiciones
crudas que F-028 leyó del portapapeles o del archivo, y todavía no hay ninguna cartera guardada:
la persistencia de carteras es F-041, que va a querer `/carteras` para sí. Elegir el prefijo por
lo que el recurso es hoy evita tener que mudarlo cuando aparezca el otro.

**Es un POST aunque no escriba nada.** La cartera de un cliente entra en el cuerpo y no en la query
string por dos razones: son decenas de posiciones con monto —una URL con eso adentro se trunca— y,
sobre todo, una query string se persiste en los logs de acceso y en el historial del navegador, y
las tenencias de un cliente no van ahí.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_db
from app.posiciones import PosicionDeclarada, resolver_cartera

router = APIRouter(prefix="/posiciones", tags=["posiciones"])

# Tope de posiciones por pedido. Una cartera de un cliente son decenas; mil es holgado y evita que
# un pegado accidental de un archivo entero mande el universo completo de vuelta al backend.
MAXIMO_POSICIONES = 1000


class PosicionCrudaRequest(BaseModel):
    """Espeja `PosicionCruda` de F-028: lo que el asesor escribió, tal como lo escribió.

    `nominal` y `monto` son casilleros **independientes** y cualquiera de los dos puede venir en
    `null`: un resumen de cuenta puede traer uno, el otro o los dos. Ninguno se completa con cero
    acá — un faltante y un cero son estados distintos, y cuál es cuál cambia el porcentaje de
    cobertura que devuelve este endpoint.

    `valida` y `motivo` de `PosicionCruda` no entran: son el veredicto de F-028 sobre el formato de
    la fila, la resolución no depende de ellos, y recibirlos haría parecer que este servicio los
    revisó. Una fila que F-028 marcó inválida se manda igual, con el casillero ilegible en `null`.
    """

    id: str
    fila: int
    ticker_declarado: str
    nominal: float | None = None
    monto: float | None = None


class ResolverRequest(BaseModel):
    posiciones: list[PosicionCrudaRequest] = Field(max_length=MAXIMO_POSICIONES)


@router.post(
    "/resolver",
    summary="Vincula cada ticker declarado con su especie del universo, o lo marca no reconocido",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def resolver_posiciones(
    conn: Annotated[object, Depends(get_db)],
    cuerpo: ResolverRequest,
) -> dict[str, object]:
    """Resuelve la cartera cargada y devuelve el diagnóstico de cobertura.

    Cada posición vuelve con su ticker declarado **y** el resuelto, lado a lado: la emisión, la
    especie, su moneda de liquidación y el plazo. Las que no se reconocieron vuelven marcadas, con
    el motivo y con su monto intacto — **no se las reemplaza por el ticker más parecido y no se las
    descarta en silencio**, que es el punto entero de la feature.

    `cobertura` declara cuántas quedaron sin resolver y qué porcentaje del monto representan, junto
    con **sobre qué base se calculó ese porcentaje**: las posiciones que no declaran monto quedan
    afuera del cálculo y se cuentan aparte en vez de entrar como cero. Cuando ninguna declara monto,
    el porcentaje es `null` y no cero, y la cantidad sin resolver sigue siendo exacta.

    No escribe nada: guardar la cartera es F-041.
    """
    resultado = await resolver_cartera(
        conn,
        [
            PosicionDeclarada(
                id=p.id,
                fila=p.fila,
                ticker_declarado=p.ticker_declarado,
                nominal=p.nominal,
                monto=p.monto,
            )
            for p in cuerpo.posiciones
        ],
    )
    return resultado.como_dict()
