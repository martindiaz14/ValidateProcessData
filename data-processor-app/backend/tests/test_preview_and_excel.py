"""Tests de las mejoras: vista previa, histograma y entrada Excel."""
import io

import pytest
from openpyxl import Workbook

from app.schemas.quality import FieldCheck
from app.services.parser import parse_file
from app.services.validator import validate_rows

CHECKS = [
    FieldCheck(nombre="nombre", requerido=True, tipo="texto"),
    FieldCheck(nombre="monto", requerido=True, tipo="numero"),
]


def _xlsx(filas: list[list]) -> bytes:
    """Construye un .xlsx en memoria a partir de una lista de filas."""
    wb = Workbook()
    ws = wb.active
    for fila in filas:
        ws.append(fila)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parse_excel():
    contenido = _xlsx(
        [["nombre", "monto"], ["Empresa A", 100], ["Empresa B", 200]]
    )
    filas = parse_file(contenido, "datos.xlsx")
    assert len(filas) == 2
    assert filas[0]["nombre"] == "Empresa A"
    assert filas[1]["monto"] == 200


def test_excel_vacio():
    with pytest.raises(ValueError, match="vacío"):
        parse_file(b"", "datos.xlsx")


def test_extension_excel_minusculas():
    contenido = _xlsx([["nombre", "monto"], ["A", 1]])
    filas = parse_file(contenido, "DATOS.XLSX")
    assert len(filas) == 1


def test_columnas_y_muestra():
    rows = [{"nombre": "A", "monto": 1}, {"nombre": "B", "monto": 2}]
    r = validate_rows(rows, CHECKS)
    assert r.columnas == ["nombre", "monto"]
    assert len(r.muestra) == 2
    assert r.muestra[0]["nombre"] == "A"


def test_muestra_limitada_a_50():
    rows = [{"nombre": f"X{i}", "monto": i} for i in range(60)]
    r = validate_rows(rows, CHECKS)
    assert r.total_filas == 60
    assert len(r.muestra) == 50


def test_histograma_suma_al_total():
    rows = [{"nombre": "A", "monto": v} for v in [10, 20, 30, 40, 50, 60]]
    r = validate_rows(rows, CHECKS)
    hist = r.metricas.histograma
    assert hist is not None
    assert sum(b.cantidad for b in hist) == 6


def test_histograma_valores_iguales():
    rows = [{"nombre": "A", "monto": 5}, {"nombre": "B", "monto": 5}]
    r = validate_rows(rows, CHECKS)
    hist = r.metricas.histograma
    assert len(hist) == 1
    assert hist[0].cantidad == 2


def test_histograma_sin_columna_numerica():
    checks = [FieldCheck(nombre="nombre", requerido=True, tipo="texto")]
    r = validate_rows([{"nombre": "A"}], checks)
    assert r.metricas.histograma is None
