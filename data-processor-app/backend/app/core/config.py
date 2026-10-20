"""Ajustes de la aplicación (lectura en tiempo de llamada, RF-1 de la spec 004)."""
import os
import re
from pathlib import Path
from typing import Mapping, Optional

# Carpeta base del backend
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Tamaños y topes del entorno (Definiciones de la spec 004)
MB = 1024 * 1024  # 1 MB = 1.048.576 bytes
LIMITE_MB_LOCAL = 10
LIMITE_MB_NUBE_TOPE = 4  # clamp: el cuerpo de Vercel admite 4,5 MB
LIMITE_FILAS_NUBE_DEFECTO = 2000


def _entero_estricto(valor) -> Optional[int]:
    """strip + número ENTERO >= 1; cualquier otra cosa → None (nunca lanza)."""
    if valor is None:
        return None
    texto = str(valor).strip()
    if re.fullmatch(r"[0-9]+", texto) is None:
        return None
    numero = int(texto)
    return numero if numero >= 1 else None


def es_modo_nube(env: Optional[Mapping[str, str]] = None) -> bool:
    """True SI la variable VERCEL existe con valor no vacío (defecto: local)."""
    fuente = os.environ if env is None else env
    return bool(fuente.get("VERCEL"))


def limite_mb(env: Optional[Mapping[str, str]] = None) -> int:
    """Límite de subida en MB: MAX_UPLOAD_MB con parseo estricto.

    Defecto 10 (local) / 4 (nube); en nube NUNCA supera 4 (clamp).
    Una configuración inválida devuelve el defecto, jamás lanza (RF-1).
    """
    fuente = os.environ if env is None else env
    nube = es_modo_nube(fuente)
    valor = _entero_estricto(fuente.get("MAX_UPLOAD_MB"))
    if valor is None:
        return LIMITE_MB_NUBE_TOPE if nube else LIMITE_MB_LOCAL
    return min(valor, LIMITE_MB_NUBE_TOPE) if nube else valor


def limite_filas_nube(env: Optional[Mapping[str, str]] = None) -> int:
    """Tope de filas de la demo: MAX_FILAS_NUBE estricta, defecto 2000.

    Solo lo consulta el modo nube; el modo local lo ignora (RF-8).
    """
    fuente = os.environ if env is None else env
    valor = _entero_estricto(fuente.get("MAX_FILAS_NUBE"))
    return LIMITE_FILAS_NUBE_DEFECTO if valor is None else valor


def _url_base_datos(env: Mapping[str, str], base_dir: Path) -> str:
    """DATABASE_URL explícita → se respeta; VERCEL → /tmp; si no, la de hoy."""
    explicita = env.get("DATABASE_URL")
    if explicita:
        return explicita
    if es_modo_nube(env):
        # FS efímero de Vercel: en local sería de solo lectura (RF-7)
        return "sqlite:////tmp/data.sqlite3"
    return f"sqlite:///{base_dir / 'data.sqlite3'}"


# Base de datos SQLite local (los datos no salen del equipo).
# Se resuelve al importar (database.py crea el motor aquí) con la pura
# _url_base_datos, testeable sin recargar el módulo.
DATABASE_URL = _url_base_datos(os.environ, BASE_DIR)

# Carpeta con el frontend estático que FastAPI sirve.
# Se puede sobrescribir con la variable de entorno FRONTEND_DIR (RF-5).
FRONTEND_DIR = Path(os.environ.get("FRONTEND_DIR") or (BASE_DIR.parent / "frontend"))
