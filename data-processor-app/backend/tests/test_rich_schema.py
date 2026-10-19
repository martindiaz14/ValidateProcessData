"""Tests del esquema enriquecido (formato "rules") y su validador."""
import pytest

from app.schemas.quality import parse_schema
from app.services.validator import validate_rows

# Esquema de ejemplo equivalente al del usuario (transacciones)
ESQUEMA_TRANSACCIONES = {
    "table_name": "transacciones_pagos",
    "rules": {
        "id_transaccion": {"type": "string", "pattern": r"^TX-\d{3,4}$", "required": True},
        "cliente_email": {"type": "email", "required": True},
        "monto": {"type": "float", "min_value": 0.01, "required": True},
        "fecha_pago": {"type": "date", "format": "YYYY-MM-DD", "required": True},
        "estado": {
            "type": "enum",
            "allowed_values": ["APROBADO", "PENDIENTE", "RECHAZADO"],
            "required": True,
        },
    },
}


def _checks():
    tabla, checks = parse_schema(ESQUEMA_TRANSACCIONES)
    assert tabla == "transacciones_pagos"
    return checks


def test_parse_schema_enriquecido():
    tabla, checks = parse_schema(ESQUEMA_TRANSACCIONES)
    assert tabla == "transacciones_pagos"
    assert len(checks) == 5
    assert {c.nombre for c in checks} == {
        "id_transaccion", "cliente_email", "monto", "fecha_pago", "estado",
    }


def test_fila_correcta():
    fila = {
        "id_transaccion": "TX-201",
        "cliente_email": "juan.perez@mail.com",
        "monto": 1500.50,
        "fecha_pago": "2026-10-01",
        "estado": "APROBADO",
    }
    r = validate_rows([fila], _checks())
    assert r.validas == 1
    assert r.invalidas == 0


def test_email_invalido():
    fila = {
        "id_transaccion": "TX-202",
        "cliente_email": "carlos.error.com",
        "monto": 2300.0,
        "fecha_pago": "2026-10-01",
        "estado": "PENDIENTE",
    }
    r = validate_rows([fila], _checks())
    assert r.invalidas == 1
    assert any("electrónico" in e.motivo for e in r.errores)


def test_monto_debajo_del_minimo():
    fila = {
        "id_transaccion": "TX-203",
        "cliente_email": "lucia@mail.com",
        "monto": -500.00,
        "fecha_pago": "2026-10-02",
        "estado": "APROBADO",
    }
    r = validate_rows([fila], _checks())
    assert r.invalidas == 1
    assert any("mínimo" in e.motivo for e in r.errores)


def test_fecha_formato_incorrecto():
    fila = {
        "id_transaccion": "TX-205",
        "cliente_email": "sofia@mail.com",
        "monto": 1200.0,
        "fecha_pago": "02-10-2026",
        "estado": "APROBADO",
    }
    r = validate_rows([fila], _checks())
    assert r.invalidas == 1
    assert any("formato" in e.motivo for e in r.errores)


def test_estado_fuera_del_enum():
    fila = {
        "id_transaccion": "TX-207",
        "cliente_email": "mario@mail.com",
        "monto": 3300.0,
        "fecha_pago": "2026-10-03",
        "estado": "DESCONOCIDO",
    }
    r = validate_rows([fila], _checks())
    assert r.invalidas == 1
    assert any("no permitido" in e.motivo for e in r.errores)


def test_patron_id_sin_guion():
    fila = {
        "id_transaccion": "TX217",
        "cliente_email": "gabriel@mail.com",
        "monto": 950.0,
        "fecha_pago": "2026-10-08",
        "estado": "APROBADO",
    }
    r = validate_rows([fila], _checks())
    assert r.invalidas == 1
    assert any("patrón" in e.motivo for e in r.errores)


def test_email_ausente_requerido():
    fila = {
        "id_transaccion": "TX-206",
        "cliente_email": "",
        "monto": 890.0,
        "fecha_pago": "2026-10-03",
        "estado": "PENDIENTE",
    }
    r = validate_rows([fila], _checks())
    assert r.invalidas == 1
    assert any("requerido" in e.motivo.lower() for e in r.errores)


def test_metricas_monto():
    filas = [
        {"id_transaccion": "TX-201", "cliente_email": "a@b.com", "monto": 100.0,
         "fecha_pago": "2026-10-01", "estado": "APROBADO"},
        {"id_transaccion": "TX-202", "cliente_email": "c@d.com", "monto": 200.0,
         "fecha_pago": "2026-10-01", "estado": "APROBADO"},
    ]
    r = validate_rows(filas, _checks())
    assert r.metricas.columna == "monto"
    assert r.metricas.suma == pytest.approx(300.0)
    assert r.metricas.media == pytest.approx(150.0)


def test_formato_desconocido_lanza_error():
    with pytest.raises(ValueError):
        parse_schema({"otra_cosa": True})
