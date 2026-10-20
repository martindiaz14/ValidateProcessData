"""Entrada ASGI de Vercel: expone la app FastAPI del backend."""
import sys
from pathlib import Path

# Raíz del bundle: <proyecto>/api/index.py → <proyecto>/data-processor-app/backend
BACKEND = Path(__file__).resolve().parent.parent / "data-processor-app" / "backend"
sys.path.insert(0, str(BACKEND))

from app.main import app  # noqa: E402  (el path debe montarse antes del import)
