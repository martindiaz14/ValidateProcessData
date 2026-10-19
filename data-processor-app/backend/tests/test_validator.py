"""Tests de la lógica de validación (services/validator.py)."""
import pytest

from app.schemas.quality import FieldSpec, QualitySchema
from app.services.validator import validate_rows


def _esquema() -> QualitySchema:
    return QualitySchema(
        campos=[
            FieldSpec(nombre="nombre", tipo="texto", requerido=True),
            FieldSpec(nombre="monto", tipo="numero", requerido=True),
            FieldSpec(nombre="fecha", tipo="fecha", requerido=False),
        ]
    )


def test_filas_validas():
    rows = [
        {"nombre": "Empresa A", "monto": 100, "fecha": "2026-01-01"},
        {"nombre": "Empresa B", "monto": 250.5, "fecha": "2026-02-01"},
    ]
    r = validate_rows(rows, _esquema())
    assert r.total_filas == 2
    assert r.validas == 2
    assert r.invalidas == 0
    assert r.errores == []


def test_fila_con_celda_vacia_requerida():
    rows = [{"nombre": "", "monto": 100}]
    r = validate_rows(rows, _esquema())
    assert r.validas == 0
    assert r.invalidas == 1
    assert any("requerido" in e.motivo.lower() for e in r.errores)


def test_tipo_incorrecto():
    rows = [{"nombre": "Empresa A", "monto": "no-numero"}]
    r = validate_rows(rows, _esquema())
    assert r.invalidas == 1
    assert any("tipo" in e.motivo.lower() for e in r.errores)


def test_metricas_suma_y_media():
    rows = [
        {"nombre": "A", "monto": 100},
        {"nombre": "B", "monto": 200},
        {"nombre": "C", "monto": 300},
    ]
    r = validate_rows(rows, _esquema())
    assert r.metricas.columna == "monto"
    assert r.metricas.suma == pytest.approx(600)
    assert r.metricas.media == pytest.approx(200)


def test_campo_no_requerido_ausente_no_es_error():
    rows = [{"nombre": "A", "monto": 100}]  # sin fecha (no requerida)
    r = validate_rows(rows, _esquema())
    assert r.validas == 1


def test_numero_booleano_no_es_numero():
    rows = [{"nombre": "A", "monto": True}]
    r = validate_rows(rows, _esquema())
    assert r.invalidas == 1


def test_archivo_sin_filas():
    r = validate_rows([], _esquema())
    assert r.total_filas == 0
    assert r.validas == 0
    assert r.invalidas == 0
