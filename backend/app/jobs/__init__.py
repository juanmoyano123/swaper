"""F-008 · Orquestación temporal del pipeline de ingesta.

Superficie pública mínima, igual que el resto de `app.ingesta`: `Scheduler` es lo que arranca y
para el loop de fondo desde `main.py`, y las dos corridas son lo que un disparo manual (el
endpoint de `app/api/v1/jobs.py`) o el propio scheduler invocan.
"""

from app.jobs.corridas import corrida_matinal, refresh_intra_rueda
from app.jobs.scheduler import Scheduler

__all__ = ["Scheduler", "corrida_matinal", "refresh_intra_rueda"]
