"""Los límites de concentración de una cartera, en vivo — F-020.

**El riesgo no es un número, es un vector de seis ejes.** Es la regla 7 del proyecto, y este paquete
es donde se ve: no hay un score de riesgo compuesto ni lo va a haber. Hay topes por crédito
—soberano por un lado, cada emisor corporativo por el otro— y un tope por sector, y los tres se
muestran abiertos porque un mismo peso puede estar bien en uno y mal en otro, y cada uno se arregla
moviendo una posición distinta.

**Y ninguno bloquea.** La ficha de la feature lo dice en una línea: *"la advertencia no bloquea:
informa"*. El asesor puede dejar la cartera como está y proponerla; lo que no puede es no enterarse.

## La forma del paquete

    perfiles.py   los tres perfiles del motor, con `min_sectores` agregado por esta feature.
    riesgo.py     de qué crédito es cada especie: grupo de emisor y clave de riesgo. Puro.
    alertas.py    qué advertir, con el exceso a la vista además del peso.
    servicio.py   la evaluación: topes, distribución y advertencias. → `Concentracion`. Puro.

No hay `lectura.py`: este paquete no consulta nada. El universo llega saneado desde
`app/universo/servicio.py` y las posiciones desde el cuerpo del request, así que
`evaluar_concentracion` es una función pura y el endpoint es lo único que toca la base.

## Las tres cosas que este paquete no negocia

1. **El Tesoro es un solo crédito** (regla 4 del dominio). Todas sus emisiones —GD, AE, DIC, TZX,
   TY3— van bajo `SOBERANO_AR` y contra un tope propio. Agruparlas por prefijo dejaba pasar una
   cartera íntegramente soberana como diversificada.
2. **Los pesos se miden como vienen.** No se normalizan a 100: si la cartera no suma 100, eso se
   mide tal cual y se declara, igual que hace la tabla de F-018 con la ponderación pedida contra la
   real.
3. **Lo que no tiene sector se muestra como lo que es.** No se reparte entre los sectores conocidos
   ni cuenta para el mínimo de diversificación: no se acredita diversificación con un dato que no
   está (reglas 1 y 11 del dominio).

El port contra `tools/armar_cartera.py` lo cuida `tests/test_concentracion_paridad_motor.py`, con la
única divergencia deliberada —el motor propaga el sector por moda dentro del grupo de emisor y acá
no— declarada en su docstring.
"""

from app.concentracion.perfiles import (
    NOMBRES_DE_PERFIL,
    PERFILES,
    SECTORES_EXENTOS,
    SOBERANO_AR,
    Perfil,
    sector_computable,
)
from app.concentracion.riesgo import RiesgoDeEspecie, clave_riesgo, derivar_riesgo, grupo_emisor
from app.concentracion.servicio import (
    Concentracion,
    EstadoDeTope,
    Posicion,
    TipoDeTope,
    Tramo,
    evaluar_concentracion,
)

__all__ = [
    "NOMBRES_DE_PERFIL",
    "PERFILES",
    "SECTORES_EXENTOS",
    "SOBERANO_AR",
    "Concentracion",
    "EstadoDeTope",
    "Perfil",
    "Posicion",
    "RiesgoDeEspecie",
    "TipoDeTope",
    "Tramo",
    "clave_riesgo",
    "derivar_riesgo",
    "evaluar_concentracion",
    "grupo_emisor",
    "sector_computable",
]
