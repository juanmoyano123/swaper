"""Estado del dato — F-013.

Lo que la barra global necesita para contestar una sola pregunta: **¿puedo confiar en lo que estoy
viendo en esta pantalla?**. No agrega ningún cálculo de dominio propio: junta lo que ya producen
F-008, F-009, F-010, F-011, F-012 y F-015, y lo presenta en un solo lugar visible.
"""

from app.estado.servicio import EstadoDelDato, estado_del_dato

__all__ = ["EstadoDelDato", "estado_del_dato"]
