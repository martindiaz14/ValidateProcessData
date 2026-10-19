"""Ajustes de la aplicación."""
import os
from pathlib import Path

# Carpeta base del backend
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Base de datos SQLite local (los datos no salen del equipo).
# Se puede sobrescribir con la variable de entorno DATABASE_URL.
DATABASE_URL = os.environ.get(
    "DATABASE_URL", f"sqlite:///{BASE_DIR / 'data.sqlite3'}"
)

# Carpeta con el frontend estático que FastAPI sirve
FRONTEND_DIR = BASE_DIR.parent / "frontend"
