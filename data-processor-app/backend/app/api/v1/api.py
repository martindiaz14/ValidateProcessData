"""Router de la API v1: agrupa los endpoints bajo /api/v1."""
from fastapi import APIRouter

from app.api.v1.endpoints import upload

api_router = APIRouter()
api_router.include_router(upload.router)
