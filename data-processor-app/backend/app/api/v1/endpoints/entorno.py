"""Endpoint de entorno: modo de despliegue y límite de subida vigente (RF-1)."""
from fastapi import APIRouter

from app.core.config import es_modo_nube, limite_mb
from app.schemas.quality import EntornoRespuesta

router = APIRouter()


@router.get("/entorno", response_model=EntornoRespuesta)
def leer_entorno() -> EntornoRespuesta:
    """`{"modo", "limite_mb"}` sin BD; una configuración inválida jamás da error."""
    return EntornoRespuesta(
        modo="nube" if es_modo_nube() else "local",
        limite_mb=limite_mb(),
    )
