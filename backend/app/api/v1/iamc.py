"""Rutas de la ingesta de IAMC — F-005.

El informe lo sube una persona desde el navegador: un `<input type="file">` arma el cuerpo como
`multipart/form-data`, así que el endpoint recibe un `UploadFile` en vez del cuerpo binario crudo
que planteaba el plan original. Ese plan había descartado multipart porque exigía
`python-multipart`, que en ese momento no estaba instalada; ya lo está (ver `requirements.txt`),
así que no hay motivo para pedirle a quien sube el archivo que arme el POST a mano. El contrato de
`parsear_informe` —bytes de un PDF— es el mismo sea cual sea el transporte.
"""

from typing import Annotated

import structlog
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import get_settings
from app.ingesta.iamc.almacen import guardar_informe
from app.ingesta.iamc.parser import InformeInvalido, parsear_informe

router = APIRouter(tags=["iamc"])
logger = structlog.get_logger()

TAMANO_MAXIMO_BYTES = 25 * 1024 * 1024
"""25 MB: la muestra real pesa 7. Da margen 3x sin aceptar cualquier archivo como si fuera el
informe."""

FIRMA_PDF = b"%PDF-"


@router.post("/iamc/informe")
async def subir_informe(
    archivo: Annotated[UploadFile, File(description="El PDF diario de deuda corporativa de IAMC")],
) -> dict[str, object]:
    """Sube y parsea el informe diario de IAMC.

    curl -F "archivo=@iamc-deuda-corporativa-2026-08-05.pdf;type=application/pdf" \\
         localhost:8000/api/v1/iamc/informe
    """
    if archivo.content_type != "application/pdf":
        raise HTTPException(
            400,
            f"se esperaba un PDF (Content-Type: application/pdf), llegó {archivo.content_type!r}",
        )

    contenido = await archivo.read()

    if not contenido:
        raise HTTPException(400, "el archivo llegó vacío")
    if len(contenido) > TAMANO_MAXIMO_BYTES:
        raise HTTPException(
            413, f"el archivo pesa más de {TAMANO_MAXIMO_BYTES // (1024 * 1024)} MB"
        )
    if not contenido.startswith(FIRMA_PDF):
        # No se chequea la extensión del filename: lo que importa es el contenido, y el magic
        # number es el dato real, no lo que diga el nombre que mandó el navegador.
        raise HTTPException(400, "el archivo no es un PDF (no empieza con la firma %PDF-)")

    try:
        resultado = parsear_informe(contenido)
    except InformeInvalido as exc:
        # El PDF se guarda igual, como evidencia para diagnosticar el cambio de layout — guardar
        # el archivo no es persistir filas, y acá no se persiste ninguna.
        guardar_informe(contenido, rechazado=True)
        logger.warning("informe_iamc_rechazado", motivo=str(exc), **exc.detalle)
        raise HTTPException(422, f"el informe no se pudo parsear: {exc}") from exc

    ruta = guardar_informe(contenido, fecha_informe=resultado.fecha_informe)

    # El endpoint sigue aceptando y parseando el informe con IAMC pausado —guardarlo deja el
    # almacén listo para cuando se reactive— pero la respuesta tiene que decir que la corrida no
    # lo va a consumir. Sin esto, subir un archivo y no ver el universo cambiar parece un bug.
    consumido = get_settings().iamc_habilitado

    return {
        "archivo": ruta.name,
        "fecha_informe": resultado.fecha_informe.isoformat(),
        "snapshot": resultado.snapshot.como_dict(),
        "consumido_por_la_corrida": consumido,
        "aviso": (
            None
            if consumido
            else (
                "El informe quedó guardado pero el consumo de IAMC está pausado: la corrida no lo "
                "va a leer y el universo no va a cambiar. Para reactivarlo, IAMC_HABILITADO=true."
            )
        ),
    }
