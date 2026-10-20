"""Aplicación FastAPI: monta la API v1 y sirve el frontend estático."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.v1.api import api_router
from app.core.config import FRONTEND_DIR
from app.core.database import Base, engine

# Crear las tablas al arrancar
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Plataforma de Procesamiento y Validación de Reportes")

# La API va primero para que sus rutas tengan prioridad sobre el estático
app.include_router(api_router, prefix="/api/v1")

# El frontend estático (index.html, app.js, styles.css, components/).
# SOLO se monta si el directorio existe (comprobación en el momento del
# montaje, RF-5): en el bundle de Vercel puede no venir frontend y la app
# debe importar igual, con la API viva (la raíz daría 404). html=True sirve
# index.html al acceder a "/".
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
