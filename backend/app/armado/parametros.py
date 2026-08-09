"""`ParametrosArmado`: el modelo Pydantic que reemplaza el `argparse` de
`tools/armar_cartera.py:558-580`.

Mapeo 1:1 de los flags del CLI, sacando lo que era de exportación de archivo (`--max-emisor` /
`--max-sector` / `--max-soberano` no se agregan como override: la ficha de F-019 sólo pide
monto/moneda/objetivo/perfil/horizonte como input, y si el perfil ya trae sus topes no hace falta un
override manual acá).
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.universo.segmentacion import MONEDA_SEGMENTO


class ParametrosArmado(BaseModel):
    """El mandato del cliente, ya validado. Espejo de los argumentos de
    `armar_cartera.py::main()`."""

    monto: float = Field(gt=0)
    moneda: Literal["usd", "ars", "todas"] = "todas"
    horizonte: Literal["corto", "medio", "largo"] = "medio"
    perfil: Literal["conservador", "moderado", "agresivo"] = "moderado"
    cobertura: Literal["devaluacion", "inflacion", "tasa-pesos", "mixta"] | None = None
    mix: dict[str, float] | None = None
    """Ya parseado (no el string `'usd_hard=60,cer=40'` de la CLI): el frontend arma el objeto
    directo, así que no hace falta reimplementar el parseo de texto de `--mix` acá."""

    n_total: int = Field(default=15, gt=0)
    min_rend: float = 0.0
    pago_mensual: bool = True

    @model_validator(mode="after")
    def _validar_mix(self) -> "ParametrosArmado":
        """Equivalente al `sys.exit` del CLI ante un segmento desconocido, acá un 422."""
        if self.mix is not None:
            desconocidos = sorted(set(self.mix) - set(MONEDA_SEGMENTO))
            if desconocidos:
                raise ValueError(
                    f"segmento(s) desconocido(s) en mix: {', '.join(desconocidos)}. "
                    f"Válidos: {', '.join(sorted(MONEDA_SEGMENTO))}"
                )
        return self
