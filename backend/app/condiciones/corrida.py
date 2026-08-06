"""Una siembra completa: leer el artefacto curado, resolver la emisión, escribir y medir.

No es una ingesta y por eso no vive en `ingesta/`: no hay fuente a la que pedirle nada, no hay red
que pueda fallar y no hay reloj del que dependa el resultado. Sembrar dos veces seguidas da lo
mismo, lo cual es también lo que la hace segura de reejecutar.

**Si no hay filas, no se escribe.** Es el guardia que separa "el artefacto dice que no sabemos
nada" de "el artefacto no se pudo leer". El segundo caso, escrito, dejaría la tabla intacta pero la
corrida cantando éxito; sin escribir nada y con la alerta arriba, se ve.

**Los conflictos viajan en la respuesta y no a una tabla.** No hay dónde persistirlos —el esquema
de F-002 no tiene tabla de conflictos y esta feature no agrega migraciones—, y tampoco haría falta
para lo que el criterio pide: que el conflicto se reporte con los dos valores en pugna. El
antecedente de `tools/merge_condiciones.py` acumulaba los conflictos en un CSV aparte justamente
porque una vez vaciado el valor, la corrida siguiente ya no lo detecta. Acá no pasa: la semilla se
vuelve a leer entera del artefacto en cada corrida, así que un conflicto se sigue reportando
mientras siga estando en el CSV.
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import structlog
from starlette.concurrency import run_in_threadpool

from app.condiciones.persistencia import (
    CoberturaCurada,
    EscrituraSemilla,
    contar_curados_fuera_del_universo,
    medir_cobertura_curada,
    persistir_semilla,
)
from app.condiciones.resolucion import Resolucion, resolver
from app.condiciones.semilla import CAMPOS, FECHA_ARTEFACTO, Semilla, leer_semilla
from app.core.config import ENV_FILE, Settings
from app.ingesta.cobertura import medir_cobertura

logger = structlog.get_logger()

# La ruta relativa se resuelve contra la raíz del repo y no contra el cwd, que cambia según se
# arranque con uvicorn, pytest o Docker. Mismo criterio que `iamc/almacen.py`.
_RAIZ_REPO = ENV_FILE.parent


def ruta_semilla(settings: Settings) -> Path:
    ruta = Path(settings.condiciones_csv)
    return ruta if ruta.is_absolute() else _RAIZ_REPO / ruta


@dataclass(frozen=True, slots=True)
class ResultadoSemilla:
    """Lo que la siembra deja para reportar.

    No lleva las 823 filas: ya están en la base. Lleva lo que hace falta para saber si la semilla
    sirve —cuánto se cargó, con qué origen, qué quedó en conflicto y qué salió mal—, el mismo
    criterio que la respuesta de la consolidación de F-007.
    """

    semilla: Semilla
    resolucion: Resolucion
    escritura: EscrituraSemilla
    cobertura: list[CoberturaCurada]
    curados_fuera_del_universo: int

    def como_dict(self) -> dict[str, object]:
        alertas = [
            *self.semilla.alertas,
            *self.resolucion.alertas,
            *self.escritura.alertas,
        ]
        # Cobertura del artefacto en sí, que es una pregunta distinta de la cobertura del universo:
        # ésta dice cuánto sabe el curado de sus propias 823 especies.
        cobertura_semilla = medir_cobertura(
            (
                {campo: valor.valor for campo, valor in fila.valores.items()}
                for fila in self.resolucion.filas
            ),
            CAMPOS,
        )
        return {
            "archivo": self.semilla.archivo,
            "fecha_artefacto": self.semilla.fecha.isoformat(),
            "especies_en_la_semilla": len(self.semilla.filas),
            "escrito": {"condiciones_emision": self.escritura.filas},
            "heredados_por_campo": self.resolucion.heredados_por_campo,
            "vaciados_por_conflicto": self.resolucion.vaciados_por_campo,
            "cobertura_semilla": [c.como_dict() for c in cobertura_semilla],
            "cobertura_universo": [c.como_dict() for c in self.cobertura],
            "curados_fuera_del_universo": self.curados_fuera_del_universo,
            "conflictos": [c.como_dict() for c in self.resolucion.conflictos],
            "alertas": [a.como_dict() for a in alertas],
        }


async def sembrar(
    conn,
    settings: Settings,
    *,
    fecha_artefacto: date = FECHA_ARTEFACTO,
) -> ResultadoSemilla:
    """Siembra `condiciones_emision` desde el artefacto curado y devuelve qué quedó cargado.

    `fecha_artefacto` se puede pasar para poder ejercitar la siembra sin depender de la constante,
    pero no es configuración de entorno a propósito: la fecha del artefacto es un hecho del repo,
    no algo que un deploy deba poder cambiar.
    """
    ruta = ruta_semilla(settings)
    # Lectura de archivo síncrona: en el event loop bloquearía al resto del servicio.
    semilla = await run_in_threadpool(leer_semilla, ruta, fecha_artefacto)

    resolucion = resolver(semilla.filas)
    escritura = await persistir_semilla(conn, resolucion.filas)

    cobertura = await medir_cobertura_curada(conn)
    fuera = await contar_curados_fuera_del_universo(conn)

    logger.info(
        "semilla_condiciones_termino",
        archivo=semilla.archivo,
        especies=len(semilla.filas),
        escritas=escritura.filas,
        conflictos=len(resolucion.conflictos),
        alertas=len(semilla.alertas) + len(resolucion.alertas) + len(escritura.alertas),
    )
    return ResultadoSemilla(
        semilla=semilla,
        resolucion=resolucion,
        escritura=escritura,
        cobertura=cobertura,
        curados_fuera_del_universo=fuera,
    )
