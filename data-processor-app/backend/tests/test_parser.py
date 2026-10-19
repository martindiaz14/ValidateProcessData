"""Tests del parser de archivos (services/parser.py)."""
import pytest

from app.services.parser import parse_file


def test_parse_csv():
    contenido = b"nombre,monto\nEmpresa A,100\nEmpresa B,200\n"
    filas = parse_file(contenido, "datos.csv")
    assert len(filas) == 2
    assert filas[0]["nombre"] == "Empresa A"


def test_parse_json_lista():
    contenido = b'[{"nombre": "A", "monto": 1}, {"nombre": "B", "monto": 2}]'
    filas = parse_file(contenido, "datos.json")
    assert len(filas) == 2


def test_parse_json_con_clave_filas():
    contenido = b'{"filas": [{"nombre": "A", "monto": 1}]}'
    filas = parse_file(contenido, "datos.json")
    assert len(filas) == 1


def test_extension_no_soportada():
    with pytest.raises(ValueError, match="soportada"):
        parse_file(b"contenido", "archivo.pdf")


def test_archivo_vacio_csv():
    with pytest.raises(ValueError, match="vacío"):
        parse_file(b"", "datos.csv")


def test_json_malformado():
    with pytest.raises(ValueError, match="JSON"):
        parse_file(b'{ Esto no es json', "datos.json")
