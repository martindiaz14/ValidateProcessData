"""Tests del entorno de despliegue: helpers de config y GET /api/v1/entorno (RF-1)."""
from fastapi.testclient import TestClient

from app.core.config import (
    BASE_DIR,
    _entero_estricto,
    _url_base_datos,
    es_modo_nube,
    limite_filas_nube,
    limite_mb,
)
from app.main import app

client = TestClient(app)

# Variables que el entorno real del desarrollador podría traer puestas
SUCIOS = ("VERCEL", "MAX_UPLOAD_MB", "MAX_FILAS_NUBE", "DATABASE_URL")


def _limpiar_entorno(monkeypatch) -> None:
    """Quita las variables de la spec para que ningún test contamine a otro."""
    for nombre in SUCIOS:
        monkeypatch.delenv(nombre, raising=False)


# --- Parseo estricto (_entero_estricto) ---------------------------------------

def test_entero_estricto_contrato():
    # strip + solo dígitos + entero >= 1; cualquier otra cosa → defecto (None)
    assert _entero_estricto("8") == 8
    assert _entero_estricto(" 8 ") == 8
    assert _entero_estricto("2000") == 2000
    for malo in ("0", "-3", "4.5", "4,5", "abc", "", None, "  "):
        assert _entero_estricto(malo) is None


# --- Modo (VERCEL) ------------------------------------------------------------

def test_modo_nube_con_vercel(monkeypatch):
    _limpiar_entorno(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")
    assert es_modo_nube() is True


def test_modo_local_sin_vercel(monkeypatch):
    _limpiar_entorno(monkeypatch)
    assert es_modo_nube() is False


def test_modo_local_con_vercel_vacio(monkeypatch):
    _limpiar_entorno(monkeypatch)
    monkeypatch.setenv("VERCEL", "")
    assert es_modo_nube() is False


# --- limite_mb: parseo estricto y clamp --------------------------------------

def test_limbite_mb_local_defecto_10(monkeypatch):
    _limpiar_entorno(monkeypatch)
    assert limite_mb() == 10


def test_limbite_mb_local_valores_validos(monkeypatch):
    _limpiar_entorno(monkeypatch)
    monkeypatch.setenv("MAX_UPLOAD_MB", "8")
    assert limite_mb() == 8
    monkeypatch.setenv("MAX_UPLOAD_MB", " 8 ")  # strip
    assert limite_mb() == 8


def test_limbite_mb_local_invalidos_dan_defecto(monkeypatch):
    _limpiar_entorno(monkeypatch)
    for valor in ("0", "-3", "4.5", "4,5", "abc", ""):
        monkeypatch.setenv("MAX_UPLOAD_MB", valor)
        assert limite_mb() == 10


def test_limbite_mb_nube_defecto_4(monkeypatch):
    _limpiar_entorno(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")
    assert limite_mb() == 4
    monkeypatch.setenv("MAX_UPLOAD_MB", "abc")
    assert limite_mb() == 4


def test_limbite_mb_nube_clamp_a_4(monkeypatch):
    _limpiar_entorno(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("MAX_UPLOAD_MB", "8")  # válido, pero el tope de nube manda
    assert limite_mb() == 4


# --- limite_filas_nube ---------------------------------------------------------

def test_limbite_filas_nube_valido(monkeypatch):
    _limpiar_entorno(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("MAX_FILAS_NUBE", "500")
    assert limite_filas_nube() == 500


def test_limbite_filas_nube_invalido_dan_defecto(monkeypatch):
    _limpiar_entorno(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")
    for valor in ("0", "-10", "abc"):
        monkeypatch.setenv("MAX_FILAS_NUBE", valor)
        assert limite_filas_nube() == 2000


def test_limbite_filas_nube_sin_variable(monkeypatch):
    _limpiar_entorno(monkeypatch)
    assert limite_filas_nube() == 2000


# --- _url_base_datos (RF-7) ---------------------------------------------------

def test_url_bd_en_nube_va_a_tmp():
    assert _url_base_datos({"VERCEL": "1"}, BASE_DIR) == "sqlite:////tmp/data.sqlite3"


def test_url_bd_local_es_la_de_hoy():
    assert _url_base_datos({}, BASE_DIR) == f"sqlite:///{BASE_DIR / 'data.sqlite3'}"


def test_url_bd_explicita_se_respeta():
    # Con DATABASE_URL explícita manda ella, aunque esté VERCEL
    assert (
        _url_base_datos({"DATABASE_URL": "sqlite:///otra.db"}, BASE_DIR)
        == "sqlite:///otra.db"
    )
    assert (
        _url_base_datos({"VERCEL": "1", "DATABASE_URL": "sqlite:///otra.db"}, BASE_DIR)
        == "sqlite:///otra.db"
    )


# --- GET /api/v1/entorno (contrato RF-1) --------------------------------------

def test_entorno_local_por_defecto(monkeypatch):
    _limpiar_entorno(monkeypatch)
    r = client.get("/api/v1/entorno")
    assert r.status_code == 200
    assert r.json() == {"modo": "local", "limite_mb": 10}


def test_entorno_nube_por_defecto(monkeypatch):
    _limpiar_entorno(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")
    r = client.get("/api/v1/entorno")
    assert r.status_code == 200
    assert r.json() == {"modo": "nube", "limite_mb": 4}


def test_entorno_solo_los_dos_campos_del_contrato(monkeypatch):
    _limpiar_entorno(monkeypatch)
    r = client.get("/api/v1/entorno")
    assert set(r.json()) == {"modo", "limite_mb"}


def test_entorno_limbite_valido_y_espacios(monkeypatch):
    _limpiar_entorno(monkeypatch)
    monkeypatch.setenv("MAX_UPLOAD_MB", "8")
    assert client.get("/api/v1/entorno").json()["limite_mb"] == 8
    monkeypatch.setenv("MAX_UPLOAD_MB", " 8 ")
    assert client.get("/api/v1/entorno").json()["limite_mb"] == 8


def test_entorno_limbite_invalido_nunca_500(monkeypatch):
    _limpiar_entorno(monkeypatch)
    for valor in ("0", "-3", "4.5", "4,5", "abc", ""):
        monkeypatch.setenv("MAX_UPLOAD_MB", valor)
        r = client.get("/api/v1/entorno")
        assert r.status_code == 200
        assert r.json() == {"modo": "local", "limite_mb": 10}
    # y en nube el defecto es 4, jamás un error
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("MAX_UPLOAD_MB", "basura")
    r = client.get("/api/v1/entorno")
    assert r.status_code == 200
    assert r.json() == {"modo": "nube", "limite_mb": 4}


def test_entorno_nube_con_limbite_8_se_recorta(monkeypatch):
    _limpiar_entorno(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("MAX_UPLOAD_MB", "8")
    r = client.get("/api/v1/entorno")
    assert r.status_code == 200
    assert r.json() == {"modo": "nube", "limite_mb": 4}
