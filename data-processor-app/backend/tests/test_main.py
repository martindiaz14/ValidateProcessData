"""Tests de import de la aplicación (RF-5): montaje condicional del frontend.

El seam de prueba es la VARIABLE DE ENTORNO `FRONTEND_DIR` con un SUBPROCESO
(import limpio de la app, sin depender del estado del proceso de test): si el
directorio no existe, la app se importa igual, la API sigue viva y la raíz
da 404 (bundle de Vercel sin frontend); con el valor por defecto, la raíz
sigue sirviendo el index.html de siempre.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent

# Variables que no deben condicionar el resultado del subproceso
SUCIAS = ("VERCEL", "MAX_UPLOAD_MB", "MAX_FILAS_NUBE", "FRONTEND_DIR")

# Código del subproceso: importa la app, le pregunta a la API y a la raíz, y
# devuelve un JSON por stdout (una línea marcada para ignorar otros avisos)
CODIGO = """
import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
api = client.get("/api/v1/entorno")
raiz = client.get("/")
print("SALIDA-TEST:" + json.dumps({
    "api_estado": api.status_code,
    "api_modo": api.json().get("modo"),
    "raiz_estado": raiz.status_code,
    "raiz_tipo": raiz.headers.get("content-type", ""),
    "raiz_es_html": "<html" in raiz.text.lower(),
    "raiz_titulo": "Plataforma de Procesamiento y Validacion de Reportes" in raiz.text
                   or "Plataforma de Procesamiento y Validación de Reportes" in raiz.text,
}))
"""


def _entorno_limpio(ruta_bd: Path) -> dict:
    """Entorno del subproceso: sin VERCEL/MAX_* ni FRONTEND_DIR heredados y
    con la BD aislada en un SQLite temporal FUERA del repo."""
    entorno = {k: v for k, v in os.environ.items() if k not in SUCIAS}
    entorno["DATABASE_URL"] = f"sqlite:///{ruta_bd}"
    return entorno


def _ejecutar_subproceso(entorno: dict) -> dict:
    """Lanza `python -c CODIGO` en el backend y devuelve el JSON parseado."""
    proceso = subprocess.run(
        [sys.executable, "-c", CODIGO],
        cwd=str(BACKEND),
        env=entorno,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proceso.returncode == 0, (
        f"el subproceso falló (import sin frontend debe funcionar):\n{proceso.stderr}"
    )
    for linea in proceso.stdout.splitlines():
        if linea.startswith("SALIDA-TEST:"):
            return json.loads(linea.removeprefix("SALIDA-TEST:"))
    raise AssertionError(f"el subproceso no devolvió su JSON:\n{proceso.stdout}")


def _bd_temporal() -> Path:
    """Ruta nueva (aún inexistente) para el SQLite temporal del subproceso."""
    return Path(tempfile.gettempdir()) / f"test_main_t3_{os.getpid()}.sqlite3"


def _borrar_si_existe(ruta: Path) -> None:
    ruta.unlink(missing_ok=True)


def test_import_seguro_sin_frontend_api_viva_y_raiz_404():
    # Escenario A (RF-5): FRONTEND_DIR a un directorio INEXISTENTE (temporal
    # fuera del repo) → el import NO lanza, la API responde y la raíz da 404
    ruta_bd = _bd_temporal()
    entorno = _entorno_limpio(ruta_bd)
    entorno["FRONTEND_DIR"] = str(
        Path(tempfile.gettempdir()) / "test_main_t3_no_existe"
    )
    try:
        salida = _ejecutar_subproceso(entorno)
    finally:
        _borrar_si_existe(ruta_bd)

    assert salida["api_estado"] == 200
    assert salida["api_modo"] == "local"  # sin VERCEL heredado
    assert salida["raiz_estado"] == 404  # sin montar estáticos
    assert not salida["raiz_es_html"]


def test_frontend_por_defecto_sigue_servido():
    # Escenario B: sin FRONTEND_DIR (defecto = frontend real) → la raíz
    # sirve el index.html de siempre (200, text/html y su título)
    ruta_bd = _bd_temporal()
    entorno = _entorno_limpio(ruta_bd)
    try:
        salida = _ejecutar_subproceso(entorno)
    finally:
        _borrar_si_existe(ruta_bd)

    assert salida["raiz_estado"] == 200
    assert "text/html" in salida["raiz_tipo"]
    assert salida["raiz_es_html"] is True
    assert salida["raiz_titulo"] is True
