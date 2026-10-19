"""Tests de las ediciones manuales (services/normalizer.py: aplicar_ediciones).

Cubren los "hecho cuando" de T4: aplicación después de la normalización con
dos entradas (RF-17), celda repetida en orden, validación previa del lote con
ValueError en español (RF-18), vaciar un campo requerido, autocorrección
apagada con solo entradas `manual` (RF-9) y lote vacío.
"""
import copy

import pytest

from app.schemas.quality import FieldCheck
from app.services.normalizer import aplicar_ediciones, corregir_filas
from app.services.validator import validate_rows


def _checks() -> list[FieldCheck]:
    return [
        FieldCheck(nombre="estado", requerido=True, tipo="enum",
                   allowed_values=["APROBADO", "PENDIENTE"]),
        FieldCheck(nombre="nota", requerido=False, tipo="string"),
    ]


def _fila(**extra) -> dict:
    fila = {"estado": "APROBADO", "nota": "original"}
    fila.update(extra)
    return fila


# --- Aplicación y rastro (RF-17, RF-9 tipo manual) ----------------------------

def test_edicion_se_aplica_despues_de_la_normalizacion():
    rows = [{"estado": "aprobado ", "nota": "ok"}]  # la auto pasa antes: → APROBADO
    ediciones = [{"fila": 1, "columna": "estado", "valor": "PENDIENTE"}]
    filas, correcciones = corregir_filas(rows, _checks(), ediciones=ediciones)
    assert filas[0]["estado"] == "PENDIENTE"
    assert len(correcciones) == 2  # automática + manual
    automatica, manual = correcciones
    assert automatica.tipo == "enum"
    assert automatica.despues == "APROBADO"
    assert manual.tipo == "manual"
    assert manual.antes == "APROBADO"  # el valor YA corregido, no el crudo
    assert manual.despues == "PENDIENTE"
    assert isinstance(manual.despues, str)


def test_misma_celda_dos_veces_en_el_lote_se_apila_en_orden():
    rows = [{"estado": "APROBADO", "nota": "a"}]
    ediciones = [
        {"fila": 1, "columna": "nota", "valor": "b"},
        {"fila": 1, "columna": "nota", "valor": "c"},
    ]
    filas, correcciones = aplicar_ediciones(rows, ediciones, _checks())
    assert filas[0]["nota"] == "c"
    manuales = [c for c in correcciones if c.tipo == "manual"]
    assert [(c.antes, c.despues) for c in manuales] == [("a", "b"), ("b", "c")]


def test_despues_manual_es_texto_y_antes_el_valor_previo():
    checks = [FieldCheck(nombre="monto", requerido=True, tipo="float")]
    rows = [{"monto": "1.234,56"}]  # la auto lo convierte a 1234.56 (float)
    ediciones = [{"fila": 1, "columna": "monto", "valor": "99"}]
    filas, correcciones = corregir_filas(rows, checks, ediciones=ediciones)
    # El VALOR DE LA FILA va como número (columna numérica convertible, mismo
    # criterio que `muestra`/`filas_corregidas` del contrato de la API)
    assert filas[0]["monto"] == 99
    assert isinstance(filas[0]["monto"], int) and not isinstance(filas[0]["monto"], bool)
    manual = correcciones[-1]
    assert manual.antes == "1234.56"  # previo (número) serializado como texto
    assert manual.despues == "99"  # el rastro manual va SIEMPRE como texto
    assert isinstance(manual.despues, str)


def test_edicion_numerica_formato_latino_se_convierte_a_float():
    checks = [FieldCheck(nombre="monto", requerido=True, tipo="float")]
    rows = [{"monto": "10"}]
    ediciones = [{"fila": 1, "columna": "monto", "valor": "1.234,56"}]
    filas, correcciones = aplicar_ediciones(rows, ediciones, checks)
    assert filas[0]["monto"] == 1234.56
    assert isinstance(filas[0]["monto"], float)
    assert correcciones[0].despues == "1.234,56"  # el rastro sigue en texto


@pytest.mark.parametrize("valor", ["mil", "1,234", "12.34.56", ""])
def test_edicion_numerica_no_convertible_se_queda_como_texto(valor):
    checks = [FieldCheck(nombre="monto", requerido=True, tipo="float")]
    rows = [{"monto": "10"}]
    filas, correcciones = aplicar_ediciones(
        rows, [{"fila": 1, "columna": "monto", "valor": valor}], checks
    )
    # Texto tal cual: el validador emitirá su error correspondiente
    assert filas[0]["monto"] == valor
    assert isinstance(filas[0]["monto"], str)
    assert correcciones[0].despues == valor


def test_edicion_columna_fecha_es_texto():
    checks = [FieldCheck(nombre="fecha_pago", requerido=True, tipo="date")]
    rows = [{"fecha_pago": "2026-10-01"}]
    ediciones = [{"fila": 1, "columna": "fecha_pago", "valor": "01/02/2026"}]
    filas, correcciones = aplicar_ediciones(rows, ediciones, checks)
    # El contrato manda las fechas como TEXTO en muestra/filas_corregidas
    assert filas[0]["fecha_pago"] == "01/02/2026"
    assert isinstance(filas[0]["fecha_pago"], str)
    assert correcciones[0].despues == "01/02/2026"


def test_vaciar_un_campo_requerido_da_error_de_requerido():
    rows = [{"estado": "APROBADO", "nota": "ok"}]
    ediciones = [{"fila": 1, "columna": "estado", "valor": ""}]
    filas, correcciones = corregir_filas(rows, _checks(), ediciones=ediciones)
    assert filas[0]["estado"] == ""
    r = validate_rows(filas, _checks())
    assert r.invalidas == 1
    assert any("requerido" in e.motivo.lower() for e in r.errores)
    assert correcciones[-1].tipo == "manual"
    assert correcciones[-1].despues == ""


def test_autocorreccion_apagada_solo_entra_manuales():
    rows = [{"estado": "aprobado ", "nota": " x "}]
    ediciones = [{"fila": 1, "columna": "nota", "valor": "editada"}]
    filas, correcciones = corregir_filas(
        rows, _checks(), autocorreccion=False, ediciones=ediciones
    )
    assert filas[0]["estado"] == "aprobado "  # la normalización NO se aplicó
    assert filas[0]["nota"] == "editada"
    assert [c.tipo for c in correcciones] == ["manual"]
    assert correcciones[0].antes == " x "  # el valor original tal cual


def test_lote_vacio_sin_cambios():
    rows = [{"estado": "aprobado ", "nota": " x "}]
    original = copy.deepcopy(rows)
    filas, correcciones = aplicar_ediciones(rows, [], _checks())
    assert filas == original
    assert correcciones == []
    assert rows == original


def test_ediciones_no_modifican_las_filas_de_entrada():
    rows = [{"estado": "APROBADO", "nota": "a"}]
    original = copy.deepcopy(rows)
    filas, correcciones = aplicar_ediciones(
        rows, [{"fila": 1, "columna": "nota", "valor": "b"}], _checks()
    )
    assert rows == original  # entrada intacta
    assert filas[0]["nota"] == "b"
    assert filas[0] is not rows[0]  # es una copia


def test_ediciones_en_filas_distintas_sin_tocar_las_demas():
    rows = [{"estado": "APROBADO", "nota": "a"},
            {"estado": "PENDIENTE", "nota": "b"}]
    ediciones = [{"fila": 2, "columna": "nota", "valor": "editada"}]
    filas, _ = aplicar_ediciones(rows, ediciones, _checks())
    assert filas[0]["nota"] == "a"
    assert filas[1]["nota"] == "editada"


# --- Validación previa del lote (RF-18) ---------------------------------------

@pytest.mark.parametrize("fila", [0, -1, 2])
def test_fila_fuera_de_rango_lanza_value_error(fila):
    rows = [{"estado": "APROBADO", "nota": "a"}]
    with pytest.raises(ValueError, match="no existe"):
        aplicar_ediciones(
            rows, [{"fila": fila, "columna": "nota", "valor": "x"}], _checks()
        )


@pytest.mark.parametrize("fila", ["1", 1.5, None, True])
def test_fila_no_entera_lanza_value_error(fila):
    rows = [{"estado": "APROBADO", "nota": "a"}]
    with pytest.raises(ValueError, match="entero"):
        aplicar_ediciones(
            rows, [{"fila": fila, "columna": "nota", "valor": "x"}], _checks()
        )


def test_columna_fuera_del_esquema_lanza_value_error():
    rows = [{"estado": "APROBADO", "nota": "a"}]
    with pytest.raises(ValueError, match="esquema"):
        aplicar_ediciones(
            rows, [{"fila": 1, "columna": "inexistente", "valor": "x"}], _checks()
        )


@pytest.mark.parametrize("columna", ["", "   ", 7, None])
def test_columna_vacia_o_no_texto_lanza_value_error(columna):
    rows = [{"estado": "APROBADO", "nota": "a"}]
    with pytest.raises(ValueError, match="columna"):
        aplicar_ediciones(
            rows, [{"fila": 1, "columna": columna, "valor": "x"}], _checks()
        )


@pytest.mark.parametrize("valor", [123, None, 4.5])
def test_valor_no_texto_lanza_value_error(valor):
    rows = [{"estado": "APROBADO", "nota": "a"}]
    with pytest.raises(ValueError, match="valor"):
        aplicar_ediciones(
            rows, [{"fila": 1, "columna": "nota", "valor": valor}], _checks()
        )


def test_elemento_del_lote_no_objeto_lanza_value_error():
    rows = [{"estado": "APROBADO", "nota": "a"}]
    with pytest.raises(ValueError, match="edic"):
        aplicar_ediciones(rows, ["no soy un objeto"], _checks())


def test_lote_invalido_no_modifica_nada():
    rows = [{"estado": "APROBADO", "nota": "a"}, {"estado": "PENDIENTE", "nota": "b"}]
    original = copy.deepcopy(rows)
    ediciones = [
        {"fila": 1, "columna": "nota", "valor": "editada"},  # válida
        {"fila": 5, "columna": "nota", "valor": "x"},        # inválida
    ]
    with pytest.raises(ValueError):
        aplicar_ediciones(rows, ediciones, _checks())
    assert rows == original  # la validación del lote es PREVIA: nada aplicado


def test_lote_invalido_a_traves_de_corregir_filas_no_modifica_nada():
    rows = [{"estado": "aprobado ", "nota": " x "}]
    original = copy.deepcopy(rows)
    ediciones = [
        {"fila": 1, "columna": "nota", "valor": "editada"},  # válida
        {"fila": 1, "columna": "columna_rara", "valor": "x"},  # fuera de esquema
    ]
    with pytest.raises(ValueError):
        corregir_filas(rows, _checks(), ediciones=ediciones)
    assert rows == original
