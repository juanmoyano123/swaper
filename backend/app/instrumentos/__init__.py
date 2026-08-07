"""La ficha de instrumento: todo lo que se sabe de UN ticker — F-039.

Contra `app/universo/` (el universo entero paginado) y `app/condiciones/` (el dato curado como
colección), este paquete responde una pregunta puntual: dado un ticker, sus hermanas de
liquidación, sus condiciones de emisión con origen y fecha, y su cronograma de pagos. No trae
lógica propia — reusa `sanear_universo`, `app.condiciones.persistencia` y `app.calendario.cupones`
tal como están — así que es angosto a propósito: sólo `ficha_de`, que es lo único que tenía sentido
extraer de `app/api/v1/instrumentos.py`.
"""

from app.instrumentos.servicio import ficha_de

__all__ = ["ficha_de"]
