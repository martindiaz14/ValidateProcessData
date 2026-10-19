"""Tests de la normalización automática (services/normalizer.py).

Cubren los "hecho cuando" de T1: limpieza de espacios/invisibles, correo en
minúsculas, marcadores de vacío (RF-8), columnas fuera del esquema intactas,
no mutación de la entrada y una sola entrada por celda (RF-9 base).
"""
import copy

import pytest

from app.schemas.quality import Correccion, FieldCheck, Metrics, RowError, ValidationResult
from app.services.normalizer import (
    _distancia_edicion,
    _ordenar_correcciones,
    corregir_filas,
    normalizar_filas,
    preparar_muestra,
)
from app.services.validator import validate_rows


def _checks() -> list[FieldCheck]:
    """Esquema de prueba: una columna de cada tipo relevante para T1."""
    return [
        FieldCheck(nombre="nombre", requerido=True, tipo="string"),
        FieldCheck(nombre="email", requerido=True, tipo="email"),
        FieldCheck(nombre="nota", requerido=False, tipo="string"),
    ]


# --- Limpieza: espacios sobrantes (RF-3) -------------------------------------

def test_espacios_iniciales_y_finales():
    rows = [{"nombre": "  hola  "}]
    filas, correcciones = normalizar_filas(rows, _checks())
    assert filas[0]["nombre"] == "hola"
    assert len(correcciones) == 1
    c = correcciones[0]
    assert c.fila == 1
    assert c.columna == "nombre"
    assert c.antes == "  hola  "
    assert c.despues == "hola"
    assert c.tipo == "espacios"


def test_espacios_dobles_internos():
    rows = [{"nombre": "hola  mundo"}]
    filas, correcciones = normalizar_filas(rows, _checks())
    assert filas[0]["nombre"] == "hola mundo"
    assert correcciones[0].tipo == "espacios"


# --- Limpieza: caracteres invisibles (RF-3) ----------------------------------

def test_espacio_duro_u00a0_interno():
    rows = [{"nombre": "hola\u00a0mundo"}]
    filas, correcciones = normalizar_filas(rows, _checks())
    assert filas[0]["nombre"] == "hola mundo"
    assert correcciones[0].tipo == "invisibles"
    assert correcciones[0].antes == "hola\u00a0mundo"


def test_espacio_duro_u00a0_en_los_bordes():
    rows = [{"nombre": "\u00a0hola\u00a0"}]
    filas, correcciones = normalizar_filas(rows, _checks())
    assert filas[0]["nombre"] == "hola"
    assert correcciones[0].tipo == "invisibles"


def test_caracteres_de_ancho_cero():
    rows = [{"nombre": "hola\u200bmundo"}]  # espacio de ancho cero U+200B
    filas, correcciones = normalizar_filas(rows, _checks())
    assert filas[0]["nombre"] == "holamundo"
    assert correcciones[0].tipo == "invisibles"


def test_bom_y_ancho_cero_en_los_bordes():
    rows = [{"nombre": "\ufeffhola\u200b"}]  # BOM (U+FEFF) + U+200B
    filas, correcciones = normalizar_filas(rows, _checks())
    assert filas[0]["nombre"] == "hola"
    assert correcciones[0].tipo == "invisibles"


def test_celda_solo_de_espacios_sin_registro():
    rows = [{"nombre": "   "}]
    filas, correcciones = normalizar_filas(rows, _checks())
    assert filas[0]["nombre"] == ""  # ya contaba como vacía para el validador
    assert correcciones == []


def test_celda_solo_de_invisibles_sin_registro():
    rows = [{"nombre": "\u00a0 \u200b"}]
    filas, correcciones = normalizar_filas(rows, _checks())
    assert filas[0]["nombre"] == ""
    assert correcciones == []


# --- Correo en minúsculas (RF-4) ---------------------------------------------

def test_correo_a_minusculas():
    rows = [{"email": "Juan@MAIL.COM"}]
    filas, correcciones = normalizar_filas(rows, _checks())
    assert filas[0]["email"] == "juan@mail.com"
    assert correcciones[0].tipo == "minusculas"


def test_correo_ya_en_minusculas_sin_registro():
    rows = [{"email": "juan@mail.com"}]
    filas, correcciones = normalizar_filas(rows, _checks())
    assert filas[0]["email"] == "juan@mail.com"
    assert correcciones == []


def test_minusculas_no_se_aplica_a_columnas_no_email():
    rows = [{"nombre": "Empresa A"}]
    filas, correcciones = normalizar_filas(rows, _checks())
    assert filas[0]["nombre"] == "Empresa A"
    assert correcciones == []


# --- Marcadores de vacío (RF-8) ----------------------------------------------

MARCADORES = [
    "N/A", "n/a", "#N/A", "N.A.", "na", "null", "none", "-", "--",
    "sin dato", "sin datos", "Sin Dato",
]


@pytest.mark.parametrize("marcador", MARCADORES)
def test_marcador_en_columna_no_requerida_da_vacio(marcador):
    rows = [{"nota": marcador}]
    filas, correcciones = normalizar_filas(rows, _checks())
    assert filas[0]["nota"] == ""
    assert len(correcciones) == 1
    c = correcciones[0]
    assert c.columna == "nota"
    assert c.antes == marcador
    assert c.despues == ""
    assert c.tipo == "vacio"


def test_marcador_en_columna_requerida_no_se_transforma():
    rows = [{"nombre": "N/A"}]
    filas, correcciones = normalizar_filas(rows, _checks())
    assert filas[0]["nombre"] == "N/A"  # conserva su error original
    assert correcciones == []


def test_marcador_con_espacios_sobrantes_genera_una_sola_entrada():
    rows = [{"nota": "  null  "}]
    filas, correcciones = normalizar_filas(rows, _checks())
    assert filas[0]["nota"] == ""
    assert len(correcciones) == 1
    assert correcciones[0].antes == "  null  "  # antes = valor crudo original
    assert correcciones[0].tipo == "vacio"  # último paso que modificó


# --- Columnas fuera del esquema (RF-2) ---------------------------------------

def test_columna_fuera_del_esquema_intacta():
    rows = [{"nombre": "A", "email": "a@b.com", "extra": "  x  ", "otra": "N/A"}]
    filas, correcciones = normalizar_filas(rows, _checks())
    assert filas[0]["extra"] == "  x  "
    assert filas[0]["otra"] == "N/A"
    assert all(c.columna in ("nombre", "email", "nota") for c in correcciones)


# --- Copia y rastro (RF-1, RF-9) ---------------------------------------------

def test_no_modifica_las_filas_de_entrada():
    rows = [{"nombre": "  A  ", "nota": "n/a"}, {"email": "X@Y.COM"}]
    original = copy.deepcopy(rows)
    filas, correcciones = normalizar_filas(rows, _checks())
    assert rows == original  # la entrada no se toca
    assert filas is not rows
    assert filas[0] is not rows[0]
    assert filas[0]["nombre"] == "A"
    assert correcciones


def test_una_sola_entrada_por_celda_con_antes_crudo_y_tipo_final():
    # La celda pasa por limpieza (espacios) Y por minúsculas: UNA sola entrada
    # con el tipo del último paso que modificó y antes = valor crudo.
    rows = [{"email": "  JUAN@MAIL.COM  "}]
    _, correcciones = normalizar_filas(rows, _checks())
    assert len(correcciones) == 1
    c = correcciones[0]
    assert c.antes == "  JUAN@MAIL.COM  "
    assert c.despues == "juan@mail.com"
    assert c.tipo == "minusculas"


def test_numeros_de_fila_1_based_y_varias_filas():
    rows = [{"nombre": "ok"}, {"nombre": "  B  "}, {"nombre": "C"}]
    _, correcciones = normalizar_filas(rows, _checks())
    assert [c.fila for c in correcciones] == [2]


def test_valores_no_textuales_no_se_tocan():
    checks = [FieldCheck(nombre="monto", requerido=True, tipo="float")]
    rows = [{"monto": 1234}]
    filas, correcciones = normalizar_filas(rows, checks)
    assert filas[0]["monto"] == 1234
    assert correcciones == []


def test_clave_ausente_sigue_ausente():
    rows = [{"nombre": "A"}]  # sin email ni nota
    filas, correcciones = normalizar_filas(rows, _checks())
    assert "email" not in filas[0]
    assert "nota" not in filas[0]
    assert correcciones == []


# --- Números (RF-5) -----------------------------------------------------------

def _checks_numeros_fechas() -> list[FieldCheck]:
    return [
        FieldCheck(nombre="monto", requerido=True, tipo="float"),
        FieldCheck(nombre="fecha", requerido=False, tipo="date",
                   date_format="YYYY-MM-DD"),
        FieldCheck(nombre="texto", requerido=False, tipo="string"),
    ]


NUMEROS_QUE_SI_SE_CORRIGEN = [
    ("1.234,56", 1234.56),   # (a) ambos separadores: último es decimal
    ("1,234.56", 1234.56),   # (a)
    ("1.234.567", 1234567),  # (b) separador repetido: grupos de 3 → miles
    ("1.23", 1.23),          # (c) decimal
    ("1,2345", 1.2345),      # (c) decimal (4 dígitos a la derecha)
    ("12,5", 12.5),          # (c) decimal
]


@pytest.mark.parametrize("valor,esperado", NUMEROS_QUE_SI_SE_CORRIGEN)
def test_numeros_inequivocos(valor, esperado):
    rows = [{"monto": valor}]
    filas, correcciones = normalizar_filas(rows, _checks_numeros_fechas())
    assert filas[0]["monto"] == esperado
    assert len(correcciones) == 1
    c = correcciones[0]
    assert c.columna == "monto"
    assert c.antes == valor
    assert c.tipo == "numero"


def test_serializacion_despues_numero():
    rows = [{"monto": "1.234,56"}, {"monto": "1.234.567"}]
    _, correcciones = normalizar_filas(rows, _checks_numeros_fechas())
    assert isinstance(correcciones[0].despues, float)  # con parte decimal
    assert isinstance(correcciones[1].despues, int)    # sin parte decimal


NUMEROS_NO_CORREGIDOS = [
    "1,234",      # (c) ambiguo (también se podría leer como miles)
    "12,345",     # (c) ambiguo
    "1.234",      # (c) ambiguo: NO se reinterpreta como 1234
    "1.234.56",   # no encaja en ninguna forma inequívoca
    "hola",       # texto sin sentido numérico
    "12a34",      # con letras: sin sentido numérico
]


@pytest.mark.parametrize("valor", NUMEROS_NO_CORREGIDOS)
def test_numeros_ambiguos_o_invalidos_sin_corregir(valor):
    rows = [{"monto": valor}]
    filas, correcciones = normalizar_filas(rows, _checks_numeros_fechas())
    assert filas[0]["monto"] == valor  # intacto: el validador emitirá su error
    assert correcciones == []


def test_numero_con_espacios_una_sola_entrada():
    rows = [{"monto": "  1.234,56  "}]
    filas, correcciones = normalizar_filas(rows, _checks_numeros_fechas())
    assert filas[0]["monto"] == 1234.56
    assert len(correcciones) == 1
    assert correcciones[0].antes == "  1.234,56  "  # antes = crudo
    assert correcciones[0].tipo == "numero"  # el último paso que modificó gana


def test_numero_no_se_interpreta_en_columnas_no_numericas():
    rows = [{"texto": "1.234,56", "fecha": "2026-01-01"}]
    filas, correcciones = normalizar_filas(rows, _checks_numeros_fechas())
    assert filas[0]["texto"] == "1.234,56"
    assert correcciones == []


# --- Fechas (RF-6) ------------------------------------------------------------

def test_fecha_convencion_dia_mes():
    rows = [
        {"fecha": "25/12/2026"},  # lectura única día/mes: aporta la convención
        {"fecha": "01/10/2026"},  # ambigua: se corrige con la convención
    ]
    filas, correcciones = normalizar_filas(rows, _checks_numeros_fechas())
    assert filas[0]["fecha"] == "2026-12-25"
    assert filas[1]["fecha"] == "2026-10-01"  # 1 de octubre
    assert [c.tipo for c in correcciones] == ["fecha", "fecha"]
    assert correcciones[1].antes == "01/10/2026"
    assert all(isinstance(c.despues, str) for c in correcciones)


def test_fecha_convencion_mes_dia():
    rows = [
        {"fecha": "05/13/2026"},  # lectura única mes/día: aporta la convención
        {"fecha": "01/10/2026"},  # ambigua
    ]
    filas, correcciones = normalizar_filas(rows, _checks_numeros_fechas())
    assert filas[0]["fecha"] == "2026-05-13"
    assert filas[1]["fecha"] == "2026-01-10"  # 10 de enero


def test_fecha_columna_sin_convencion_no_corrige_ambiguas():
    rows = [{"fecha": "01/10/2026"}, {"fecha": "03/04/2026"}]
    filas, correcciones = normalizar_filas(rows, _checks_numeros_fechas())
    assert filas[0]["fecha"] == "01/10/2026"
    assert filas[1]["fecha"] == "03/04/2026"
    assert correcciones == []


def test_fecha_lectura_unica_en_columna_conflicto_si_se_corrige():
    rows = [
        {"fecha": "25/12/2026"},  # única día/mes
        {"fecha": "05/13/2026"},  # única mes/día → empate → sin convención
    ]
    # En columna sin convención, las de lectura única SÍ se corrigen con ella
    filas, correcciones = normalizar_filas(rows, _checks_numeros_fechas())
    assert filas[0]["fecha"] == "2026-12-25"
    assert filas[1]["fecha"] == "2026-05-13"
    assert [c.tipo for c in correcciones] == ["fecha", "fecha"]


def test_fecha_convenciones_en_conflicto_sin_convencion():
    rows = [
        {"fecha": "25/12/2026"},  # lectura única día/mes
        {"fecha": "05/13/2026"},  # lectura única mes/día → conflicto
        {"fecha": "01/10/2026"},  # ambigua: en conflicto NO se corrige
    ]
    filas, correcciones = normalizar_filas(rows, _checks_numeros_fechas())
    assert filas[0]["fecha"] == "2026-12-25"  # las de lectura única sí
    assert filas[1]["fecha"] == "2026-05-13"  # se corrigen con su única lectura
    assert filas[2]["fecha"] == "01/10/2026"  # la ambigua queda como error
    assert [c.fila for c in correcciones] == [1, 2]


def test_fecha_lectura_unica_contraria_sin_corregir():
    rows = [
        {"fecha": "25/12/2026"},   # única día/mes
        {"fecha": "26/12/2026"},   # única día/mes → mayoría → convención día/mes
        {"fecha": "01/13/2026"},   # única mes/día: contraria → no se toca
    ]
    filas, correcciones = normalizar_filas(rows, _checks_numeros_fechas())
    assert filas[0]["fecha"] == "2026-12-25"
    assert filas[1]["fecha"] == "2026-12-26"
    assert filas[2]["fecha"] == "01/13/2026"
    assert [c.fila for c in correcciones] == [1, 2]


def test_fecha_imposible_sin_correccion_y_sin_aportar_convencion():
    rows = [
        {"fecha": "31/02/2026"},   # imposible: no se corrige…
        {"fecha": "01/10/2026"},   # …ni aporta convención → ambigua sin corregir
    ]
    filas, correcciones = normalizar_filas(rows, _checks_numeros_fechas())
    assert filas[0]["fecha"] == "31/02/2026"
    assert filas[1]["fecha"] == "01/10/2026"
    assert correcciones == []


def test_fecha_anio_de_dos_digitos_sin_tocar():
    rows = [{"fecha": "01/10/26"}]
    filas, correcciones = normalizar_filas(rows, _checks_numeros_fechas())
    assert filas[0]["fecha"] == "01/10/26"
    assert correcciones == []


def test_fecha_anio_al_principio_sin_tocar():
    rows = [{"fecha": "2026/10/01"}]
    filas, correcciones = normalizar_filas(rows, _checks_numeros_fechas())
    assert filas[0]["fecha"] == "2026/10/01"
    assert correcciones == []


def test_fecha_se_convierte_al_formato_de_la_regla():
    checks = [FieldCheck(nombre="fecha", requerido=False, tipo="date",
                         date_format="DD-MM-YYYY")]
    rows = [{"fecha": "25/12/2026"}]
    filas, correcciones = normalizar_filas(rows, checks)
    assert filas[0]["fecha"] == "25-12-2026"
    assert correcciones[0].despues == "25-12-2026"
    assert isinstance(correcciones[0].despues, str)


def test_fecha_con_espacios_una_sola_entrada():
    rows = [{"fecha": "  25/12/2026  "}, {"fecha": "01/10/2026"}]
    filas, correcciones = normalizar_filas(rows, _checks_numeros_fechas())
    assert filas[0]["fecha"] == "2026-12-25"
    assert len(correcciones) == 2
    assert correcciones[0].antes == "  25/12/2026  "  # antes = crudo
    assert correcciones[0].tipo == "fecha"  # gana el último paso que modificó


def test_fecha_no_se_convierte_en_columnas_no_de_fecha():
    rows = [{"texto": "25/12/2026", "monto": 1}]
    filas, correcciones = normalizar_filas(rows, _checks_numeros_fechas())
    assert filas[0]["texto"] == "25/12/2026"
    assert correcciones == []


# --- Enums (RF-7) -------------------------------------------------------------

def _checks_enum() -> list[FieldCheck]:
    return [
        FieldCheck(nombre="estado", requerido=True, tipo="enum",
                   allowed_values=["APROBADO", "PENDIENTE", "RECHAZADO"]),
    ]


def test_enum_minusculas_y_espacios_a_forma_exacta():
    rows = [{"estado": "aprobado "}]
    filas, correcciones = normalizar_filas(rows, _checks_enum())
    assert filas[0]["estado"] == "APROBADO"
    assert len(correcciones) == 1
    c = correcciones[0]
    assert c.antes == "aprobado "
    assert c.despues == "APROBADO"
    assert c.tipo == "enum"


def test_enum_con_distancia_de_edicion_uno():
    rows = [{"estado": "APROBAD0"}]
    filas, correcciones = normalizar_filas(rows, _checks_enum())
    assert filas[0]["estado"] == "APROBADO"
    assert correcciones[0].tipo == "enum"


def test_enum_con_dos_candidatos_no_se_corrige():
    checks = [FieldCheck(nombre="estado", requerido=True, tipo="enum",
                         allowed_values=["CAT", "CAR"])]
    rows = [{"estado": "CA"}]  # a distancia 1 de CAT y de CAR → ambiguo
    filas, correcciones = normalizar_filas(rows, checks)
    assert filas[0]["estado"] == "CA"
    assert correcciones == []


def test_enum_dos_candidatos_a_distancia_uno_no_se_corrige():
    checks = [FieldCheck(nombre="estado", requerido=True, tipo="enum",
                         allowed_values=["LOG", "LOT"])]
    rows = [{"estado": "LO"}]  # a distancia 1 de LOG y de LOT → ambiguo
    filas, correcciones = normalizar_filas(rows, checks)
    assert filas[0]["estado"] == "LO"
    assert correcciones == []


def test_enum_espacios_con_distancia_uno_una_sola_entrada():
    rows = [{"estado": "  APROBAD0  "}]
    filas, correcciones = normalizar_filas(rows, _checks_enum())
    assert filas[0]["estado"] == "APROBADO"
    assert len(correcciones) == 1  # limpieza + enum = UNA sola entrada
    c = correcciones[0]
    assert c.antes == "  APROBAD0  "  # antes = texto crudo sin limpiar
    assert c.despues == "APROBADO"
    assert c.tipo == "enum"  # gana el último paso que modificó


def test_enum_valor_ya_valido_sin_registro():
    rows = [{"estado": "APROBADO"}]
    filas, correcciones = normalizar_filas(rows, _checks_enum())
    assert filas[0]["estado"] == "APROBADO"
    assert correcciones == []


def test_enum_espacios_sobrantes_en_valor_valido_solo_registra_espacios():
    rows = [{"estado": "  APROBADO  "}]
    filas, correcciones = normalizar_filas(rows, _checks_enum())
    assert filas[0]["estado"] == "APROBADO"
    assert len(correcciones) == 1
    assert correcciones[0].tipo == "espacios"  # el enum no modificó nada


def test_enum_no_se_aplica_a_columnas_no_enum():
    checks = [FieldCheck(nombre="nota", requerido=False, tipo="string")]
    rows = [{"nota": "aprobado "}]
    filas, correcciones = normalizar_filas(rows, checks)
    assert filas[0]["nota"] == "aprobado"  # solo limpieza, sin mayúsculas
    assert correcciones[0].tipo == "espacios"


def test_enum_sin_allowed_values_no_se_corrige():
    checks = [FieldCheck(nombre="estado", requerido=True, tipo="enum")]
    rows = [{"estado": "aprobado"}]
    filas, correcciones = normalizar_filas(rows, checks)
    assert filas[0]["estado"] == "aprobado"
    assert correcciones == []


# --- Distancia de edición (RF-7, Levenshtein propio) --------------------------

@pytest.mark.parametrize(
    "a,b,esperada",
    [
        ("APROBADO", "APROBADO", 0),
        ("APROBAD0", "APROBADO", 1),
        ("CA", "CAT", 1),
        ("CA", "CAR", 1),
        ("CAT", "CAR", 1),
        ("LOH", "LOG", 1),
        ("LOH", "LAG", 2),
        ("", "abc", 3),
        ("abc", "", 3),
        ("kitten", "sitting", 3),
    ],
)
def test_distancia_edicion(a, b, esperada):
    assert _distancia_edicion(a, b) == esperada


# --- Orquestador corregir_filas y orden del contrato (RF-9) -------------------

def _checks_mixed() -> list[FieldCheck]:
    # El esquema declara «a» antes que «b», al revés que el archivo de prueba
    return [
        FieldCheck(nombre="a", requerido=True, tipo="enum", allowed_values=["ALTO", "BAJO"]),
        FieldCheck(nombre="b", requerido=False, tipo="string"),
    ]


def test_corregir_filas_ordena_por_fila_y_por_columnas_del_archivo():
    rows = [
        {"b": " x ", "a": "alto "},   # el archivo trae b antes que a
        {"a": "bajo ", "b": " y"},
    ]
    filas, correcciones = corregir_filas(rows, _checks_mixed())
    assert filas[0] == {"b": "x", "a": "ALTO"}
    assert [(c.fila, c.columna, c.tipo) for c in correcciones] == [
        (1, "b", "espacios"),  # fila 1 → orden de columnas DEL ARCHIVO
        (1, "a", "enum"),
        (2, "b", "espacios"),  # fila ascendente
        (2, "a", "enum"),
    ]


def test_correccion_automatica_antes_que_manual_en_la_misma_celda():
    filas = [{"a": "x"}]
    correcciones = [
        Correccion(fila=1, columna="a", antes="X", despues="x2", tipo="manual"),
        Correccion(fila=1, columna="a", antes="x", despues="x2", tipo="manual"),
        Correccion(fila=1, columna="a", antes=" x", despues="x", tipo="espacios"),
    ]
    ordenadas = _ordenar_correcciones(filas, correcciones)
    assert [c.tipo for c in ordenadas] == ["espacios", "manual", "manual"]
    # las dos manuales conservan el orden del lote (clave de desempate)


def test_corregir_filas_sin_autocorreccion():
    rows = [{"a": "alto ", "b": " x "}]
    original = copy.deepcopy(rows)
    filas, correcciones = corregir_filas(rows, _checks_mixed(), autocorreccion=False)
    assert filas == original  # filas originales, sin tocar
    assert correcciones == []
    assert rows == original


def test_corregir_filas_por_defecto_aplica_la_autocorreccion():
    rows = [{"a": "alto ", "b": " x "}]
    filas, correcciones = corregir_filas(rows, _checks_mixed())  # sin flag
    assert filas[0] == {"a": "ALTO", "b": "x"}
    assert len(correcciones) == 2


def test_corregir_filas_no_modifica_las_filas_de_entrada():
    rows = [{"a": "alto ", "b": " x "}]
    original = copy.deepcopy(rows)
    corregir_filas(rows, _checks_mixed())
    assert rows == original


def test_serializacion_contrato_de_correcciones():
    checks = [
        FieldCheck(nombre="estado", requerido=True, tipo="enum",
                   allowed_values=["APROBADO"]),
        FieldCheck(nombre="monto", requerido=True, tipo="float"),
    ]
    rows = [{"estado": "aprobado ", "monto": "1.234,56"}]
    _, correcciones = corregir_filas(rows, checks)
    r = ValidationResult(
        total_filas=1, validas=0, invalidas=1, errores=[], metricas=Metrics(),
        correcciones=correcciones,
    )
    volcado = r.model_dump()["correcciones"]
    assert isinstance(volcado[0]["fila"], int)
    assert volcado[0]["columna"] == "estado"
    assert volcado[0]["despues"] == "APROBADO"            # texto para enum
    assert volcado[1]["columna"] == "monto"
    assert volcado[1]["despues"] == 1234.56               # número para numero
    assert not isinstance(volcado[1]["despues"], str)


# --- RF-10: resumen calculado sobre los valores corregidos --------------------

def test_rf10_fila_corregida_y_conforme_cuenta_como_valida():
    checks = [FieldCheck(nombre="estado", requerido=True, tipo="enum",
                         allowed_values=["APROBADO", "PENDIENTE"])]
    rows = [{"estado": "aprobado "}]
    filas, correcciones = corregir_filas(rows, checks)
    r = validate_rows(filas, checks)
    assert r.validas == 1
    assert r.invalidas == 0
    assert len(correcciones) == 1


def test_rf10_fila_corregida_pero_fuera_de_rango_sigue_invalida():
    checks = [FieldCheck(nombre="monto", requerido=True, tipo="float",
                         min_value=0.0, max_value=1000.0)]
    rows = [{"monto": "1.234,56"}]  # se corrige a 1234.56, fuera del máximo
    filas, correcciones = corregir_filas(rows, checks)
    r = validate_rows(filas, checks)
    assert r.invalidas == 1
    assert any("máximo" in e.motivo for e in r.errores)  # el error restante
    assert len(correcciones) == 1
    assert correcciones[0].tipo == "numero"  # la corrección también queda


def test_fecha_ya_en_su_formato_no_genera_registro():
    # Formato DD-MM-YYYY y valor ya en ese formato: corrección que no
    # modifica no debe generar entrada (caso límite "valor ya válido")
    checks = [FieldCheck(nombre="fecha", requerido=False, tipo="date",
                         date_format="DD-MM-YYYY")]
    rows = [{"fecha": "25/12/2026"}, {"fecha": "10-01-2026"}]
    filas, correcciones = normalizar_filas(rows, checks)
    assert filas[0]["fecha"] == "25-12-2026"
    assert filas[1]["fecha"] == "10-01-2026"
    assert [c.fila for c in correcciones] == [1]


# --- Compatibilidad de la respuesta (RNF-5) ----------------------------------

def test_validation_result_con_campos_nuevos_por_defecto():
    r = ValidationResult(
        total_filas=0, validas=0, invalidas=0, errores=[], metricas=Metrics()
    )
    assert r.correcciones == []
    assert r.filas_corregidas == []
    assert r.descarga_corregida_disponible is True


# --- Vista previa de errores: filas de interés (RF-11, T11) --------------------

def _error(fila: int, columna: str = "n") -> RowError:
    return RowError(fila=fila, columna=columna, motivo="Valor inválido")


def _correccion(fila: int, tipo: str = "espacios", columna: str = "n") -> Correccion:
    return Correccion(fila=fila, columna=columna, antes="a", despues="b", tipo=tipo)


def test_preparar_muestra_filas_de_interes_en_orden_ascendente():
    # Errores en las filas 8 y 2, correcciones en la 1 y en la 8 (duplicada)
    rows = [{"n": i} for i in range(1, 46)]  # la fila k lleva {"n": k}
    errores = [_error(8), _error(2)]
    correcciones = [_correccion(40), _correccion(1, "manual"), _correccion(8, "enum")]
    muestra, muestra_filas = preparar_muestra(rows, errores, correcciones)
    assert muestra_filas == [1, 2, 8, 40]  # unión ordenada, sin repetir filas
    assert len(muestra) == 4  # paralela a muestra_filas
    assert muestra[0] == {"n": 1}
    assert muestra[3] == {"n": 40}
    # La muestra son copias: tocarla no toca las filas de entrada
    muestra[0]["n"] = 999
    assert rows[0]["n"] == 1


def test_preparar_muestra_todas_las_filas_de_interes_aunque_hayan_muchas():
    # 70 filas de interés (de la 3 a la 72): salen TODAS (sin tope)
    rows = [{"n": i} for i in range(1, 74)]
    errores = [_error(n) for n in range(3, 73)]
    muestra, muestra_filas = preparar_muestra(rows, errores, [])
    assert muestra_filas == list(range(3, 73))
    assert len(muestra_filas) == 70
    assert muestra[0] == {"n": 3}  # empieza en la fila 3, no en la 1
    assert muestra[-1] == {"n": 72}


def test_preparar_muestra_filas_paralelas_con_numeros_reales():
    # Errores en las filas 80 y 900: números 1-based reales, mismo orden
    rows = [{"n": i} for i in range(1, 901)]
    errores = [_error(80), _error(900)]
    muestra, muestra_filas = preparar_muestra(rows, errores, [])
    assert muestra_filas == [80, 900]
    assert len(muestra) == len(muestra_filas)
    assert muestra[0] == {"n": 80}
    assert muestra[1] == {"n": 900}


def test_preparar_muestra_solo_correcciones_tambien_cuentan():
    # Sin errores: una fila SOLO corregida (ámbar) también es de interés (RF-11)
    rows = [{"n": i} for i in range(1, 7)]
    muestra, muestra_filas = preparar_muestra(
        rows, [], [_correccion(2), _correccion(5, "manual")]
    )
    assert muestra_filas == [2, 5]
    assert muestra == [{"n": 2}, {"n": 5}]


def test_preparar_muestra_fallback_sin_filas_de_interes():
    # Sin ninguna fila de interés: las primeras 50 de siempre y [1..N]
    rows = [{"n": i} for i in range(1, 61)]  # la fila k lleva {"n": k}
    muestra, muestra_filas = preparar_muestra(rows, [], [])
    assert len(muestra) == 50
    assert muestra_filas == list(range(1, 51))
    assert muestra[0] == {"n": 1}
    # Archivo corto: todas sus filas con sus números
    muestra, muestra_filas = preparar_muestra(rows[:3], [], [])
    assert muestra_filas == [1, 2, 3]
    assert len(muestra) == 3


# --- Vista previa sin tope: TODAS las filas de interés (RF-11, T16) -------------
# Filas de interés = filas con error residual O corrección. La vista previa las
# trae TODAS en orden de fila, sin parámetro de límite (decisión «sin límite»);
# el contador y el aviso por volumen los deriva el navegador, no el backend.

def test_fila_con_error_y_correccion_es_una_sola_fila_de_interes():
    # Fila 1 con error Y corrección en la MISMA celda → 1 sola fila de interés
    rows = [{"n": i} for i in range(1, 11)]
    errores = [_error(1)]
    correcciones = [_correccion(1, "manual"), _correccion(2)]
    muestra, muestra_filas = preparar_muestra(rows, errores, correcciones)
    assert muestra_filas == [1, 2]


def test_incidencias_en_columnas_distintas_sigue_siendo_una_sola_fila():
    # Fila 1 con incidencias en dos columnas distintas: es UNA fila de
    # interés y salen todas las que haya, sin tope
    rows = [{"n": i, "m": i} for i in range(1, 11)]
    errores = [_error(1)]
    correcciones = [_correccion(1, "manual", columna="m"), _correccion(2)]
    muestra, muestra_filas = preparar_muestra(rows, errores, correcciones)
    assert muestra_filas == [1, 2]


def test_diez_filas_de_interes_las_diez():
    # 10 filas de interés (pares) → salen las 10 (sin tope de filas)
    rows = [{"n": i} for i in range(1, 21)]
    errores = [_error(n) for n in range(2, 22, 2)]
    muestra, muestra_filas = preparar_muestra(rows, errores, [])
    assert muestra_filas == list(range(2, 22, 2))
    assert len(muestra) == 10
    assert muestra[0] == {"n": 2}


def test_fila_con_100_incidencias_es_una_fila_entera():
    # Una fila con 100 incidencias: 1 fila de interés, mostrada ENTERA
    rows = [{"n": i} for i in range(1, 6)]
    cien = [RowError(fila=1, columna=f"c{i}", motivo="m") for i in range(100)]
    muestra, muestra_filas = preparar_muestra(rows, cien + [_error(2)], [])
    assert muestra_filas == [1, 2]
    assert muestra[0] == {"n": 1}  # la fila entera, no una parte


def test_mil_filas_con_un_error_las_mil():
    # (e) 1000 filas con un error cada una → `muestra` trae las 1000 (sin tope)
    rows = [{"n": i} for i in range(1, 1001)]
    errores = [_error(n) for n in range(1, 1001)]
    muestra, muestra_filas = preparar_muestra(rows, errores, [])
    assert muestra_filas == list(range(1, 1001))
    assert len(muestra) == 1000
    assert muestra[0] == {"n": 1}
    assert muestra[999] == {"n": 1000}


def test_todas_las_filas_de_interes_sin_recorte():
    rows = [{"n": i} for i in range(1, 11)]
    muestra, muestra_filas = preparar_muestra(
        rows, [_error(2), _error(4)], [_correccion(7)]
    )
    assert muestra_filas == [2, 4, 7]


def test_fallback_sin_filas_de_interes_son_las_primeras_50():
    # (h) sin ninguna fila de interés: las primeras 50 de siempre y [1..N]
    rows = [{"n": i} for i in range(1, 61)]
    muestra, muestra_filas = preparar_muestra(rows, [], [])
    assert len(muestra) == 50
    assert muestra_filas == list(range(1, 51))
