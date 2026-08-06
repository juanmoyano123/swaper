"""Corrida real contra el feed de Docta. Excluida por defecto (`-m 'not integration'` en
`pyproject.toml`); se salta si no hay `DOCTA_CASHFLOW_URL` en el entorno.

Si el token está vencido, el assert que falla lo dice con el mensaje operativo — es información
para ir a regenerar el link en Docta Terminal, no un bug de esta feature.
"""

import os

import pytest

from app.core.config import get_settings
from app.ingesta.docta.ingesta import ingerir_cashflow
from app.ingesta.docta.normalizacion import COLUMNAS_CONTRACTUALES

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("DOCTA_CASHFLOW_URL"),
        reason="requiere DOCTA_CASHFLOW_URL configurado en el entorno",
    ),
]


async def test_la_ingesta_real_trae_el_cashflow_completo() -> None:
    get_settings.cache_clear()
    settings = get_settings()

    resultado = await ingerir_cashflow(settings)

    if resultado.filas is None:
        alertas = ", ".join(a.mensaje for a in resultado.snapshot.alertas)
        pytest.fail(
            f"la ingesta real no trajo cashflow — puede ser el token vencido, regenerar en "
            f"Docta Terminal. Alertas: {alertas}"
        )

    assert len(resultado.filas) > 1_000
    assert set(COLUMNAS_CONTRACTUALES) <= resultado.filas[0].keys()
    assert resultado.snapshot.completo is True
