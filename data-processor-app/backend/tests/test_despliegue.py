"""Tests de coherencia de los artefactos de despliegue en la raíz (RF-6, RNF-1).

Comprueban que los archivos de Vercel existen y cuadran entre sí (una sola
fuente de dependencias, catch-all con `rewrites` y no `routes` legacy, y la
cabecera noindex) y que `api/index.py` expone la app real de nube, todo sin
HTTP externo.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# tests/ → backend/ → data-processor-app/ → RAÍZ del repo
RAIZ = Path(__file__).resolve().parents[3]

FRONTEND_REAL = RAIZ / "data-processor-app" / "frontend"

# Variables que no deben condicionar el subproceso (se fijan o se limpian)
SUCIAS = ("VERCEL", "MAX_UPLOAD_MB", "MAX_FILAS_NUBE", "FRONTEND_DIR")


def test_requirements_raiz_es_una_referencia():
    # Una sola fuente de versiones: la raíz SOLO referencia el del backend
    ruta = RAIZ / "requirements.txt"
    assert ruta.is_file(), "falta requirements.txt en la raíz"
    lineas = [l.strip() for l in ruta.read_text(encoding="utf-8").splitlines()]
    assert "-r data-processor-app/backend/requirements.txt" in lineas


def test_vercel_json_parsea_y_cumple_el_contrato():
    ruta = RAIZ / "vercel.json"
    assert ruta.is_file(), "falta vercel.json en la raíz"
    datos = json.loads(ruta.read_text(encoding="utf-8"))

    assert datos["version"] == 2

    funcion = datos["functions"]["api/index.py"]
    assert funcion["maxDuration"] == 60
    assert funcion["memory"] == 1024
    # Globs POSITIVOS: solo .py del backend, su requirements y el frontend
    assert set(funcion["includeFiles"]) == {
        "data-processor-app/backend/app/**/*.py",
        "data-processor-app/backend/requirements.txt",
        "data-processor-app/frontend/**",
    }

    # Catch-all con `rewrites` (NO `routes`: es legacy y anularía `headers`)
    assert "routes" not in datos
    assert datos["rewrites"] == [{"source": "/(.*)", "destination": "/api/index"}]

    # Cabecera noindex en TODAS las rutas (RNF-3)
    assert {"source": "/(.*)", "headers": [{"key": "X-Robots-Tag", "value": "noindex"}]} in datos["headers"]


def test_api_index_importa_la_app_en_nube():
    # Subproceso desde la RAÍZ (como Vercel) con VERCEL=1: la entrada
    # api/index.py expone `app` y /api/v1/entorno responde el contrato nube
    codigo = (
        "import importlib.util, json\n"
        "spec = importlib.util.spec_from_file_location('entrada_vercel', 'api/index.py')\n"
        "modulo = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(modulo)\n"
        "from fastapi.testclient import TestClient\n"
        "r = TestClient(modulo.app).get('/api/v1/entorno')\n"
        "print('SALIDA-TEST:' + json.dumps({'estado': r.status_code, 'cuerpo': r.json()}))\n"
    )
    ruta_bd = Path(tempfile.gettempdir()) / f"test_despliegue_t4_{os.getpid()}.sqlite3"
    entorno = {k: v for k, v in os.environ.items() if k not in SUCIAS}
    entorno["VERCEL"] = "1"
    entorno["FRONTEND_DIR"] = str(FRONTEND_REAL)
    entorno["DATABASE_URL"] = f"sqlite:///{ruta_bd}"  # BD aislada, fuera del repo
    try:
        proceso = subprocess.run(
            [sys.executable, "-c", codigo],
            cwd=str(RAIZ),
            env=entorno,
            capture_output=True,
            text=True,
            timeout=60,
        )
    finally:
        ruta_bd.unlink(missing_ok=True)

    assert proceso.returncode == 0, f"api/index.py no importó limpio:\n{proceso.stderr}"
    for linea in proceso.stdout.splitlines():
        if linea.startswith("SALIDA-TEST:"):
            salida = json.loads(linea.removeprefix("SALIDA-TEST:"))
            assert salida["estado"] == 200
            assert salida["cuerpo"] == {"modo": "nube", "limite_mb": 4}
            return
    raise AssertionError(f"el subproceso no devolvió su JSON:\n{proceso.stdout}")
