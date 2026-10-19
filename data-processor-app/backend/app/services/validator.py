"""Lógica de validación de filas contra las reglas del esquema.

Funciones puras: misma entrada, misma salida. Sin HTTP ni base de datos,
para poder probarlas directamente con pytest.
"""
import re
from datetime import date, datetime
from typing import Any, Optional, Union

from app.schemas.quality import FieldCheck, HistogramBin, Metrics, QualitySchema, RowError, ValidationResult

# Máximo de filas devueltas en la vista previa
# (spec 003: se conserva en 50 y solo sirve para el fallback de `preparar_muestra`)
LIMITE_MUESTRA = 50

# Mapeo de tokens de formato de fecha (estilo JS) a strftime (Python)
_TOKENS_FECHA = [
    ("YYYY", "%Y"), ("MM", "%m"), ("DD", "%d"),
    ("HH", "%H"), ("mm", "%M"), ("ss", "%S"),
]

# Sinónimos de tipos admitidos
_TIPOS_NUMERO = {"float", "int", "integer", "number", "double", "numero"}
_TIPOS_TEXTO = {"string", "text", "texto"}
_TIPOS_FECHA = {"date", "fecha"}
_TIPOS_BOOLEANO = {"boolean", "bool", "booleano"}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_rows(
    rows: list[dict], schema: Union[list[FieldCheck], QualitySchema]
) -> ValidationResult:
    """Valida cada fila. Acepta reglas normalizadas o un QualitySchema compacto."""
    checks = _a_checks(schema)
    errores: list[RowError] = []
    validas = 0

    for indice, fila in enumerate(rows, start=1):
        motivos = _validar_fila(fila, checks)
        if motivos:
            for columna, motivo in motivos:
                errores.append(RowError(fila=indice, columna=columna, motivo=motivo))
        else:
            validas += 1

    total = len(rows)
    return ValidationResult(
        total_filas=total,
        validas=validas,
        invalidas=total - validas,
        errores=errores,
        metricas=_calcular_metricas(rows, checks),
        columnas=_columnas(rows),
        muestra=_muestra(rows),
    )


def _columnas(rows: list[dict]) -> list[str]:
    """Unión de nombres de columna en orden de primera aparición."""
    columnas: list[str] = []
    vistas: set[str] = set()
    for fila in rows:
        if isinstance(fila, dict):
            for clave in fila.keys():
                if clave not in vistas:
                    vistas.add(clave)
                    columnas.append(clave)
    return columnas


def _muestra(rows: list[dict]) -> list[dict]:
    """Primeras filas (hasta LIMITE_MUESTRA) para la vista previa."""
    return [dict(fila) for fila in rows[:LIMITE_MUESTRA] if isinstance(fila, dict)]


def _a_checks(schema: Union[list[FieldCheck], QualitySchema]) -> list[FieldCheck]:
    """Convierte el esquema compacto a reglas normalizadas si hace falta."""
    if isinstance(schema, list):
        return schema
    return [
        FieldCheck(nombre=c.nombre, requerido=c.requerido, tipo=c.tipo)
        for c in schema.campos
    ]


def _validar_fila(fila: dict, checks: list[FieldCheck]) -> list[tuple[str, str]]:
    """Devuelve la lista de (columna, motivo) para una fila."""
    problemas: list[tuple[str, str]] = []
    for check in checks:
        valor = fila.get(check.nombre)
        vacio = valor is None or (isinstance(valor, str) and not valor.strip())

        if vacio:
            if check.requerido:
                problemas.append((check.nombre, "Campo requerido ausente o vacío"))
            continue

        motivo = _revisar_valor(valor, check)
        if motivo:
            problemas.append((check.nombre, motivo))
    return problemas


def _revisar_valor(valor: Any, check: FieldCheck) -> Optional[str]:
    """Comprueba un valor contra su regla. Devuelve el motivo del error o None."""
    tipo = (check.tipo or "").lower()

    if tipo in _TIPOS_NUMERO:
        num = _a_numero(valor)
        if num is None:
            return f"Tipo incorrecto: se esperaba {check.tipo}"
        if check.min_value is not None and num < check.min_value:
            return f"Valor menor que el mínimo {check.min_value:g}"
        if check.max_value is not None and num > check.max_value:
            return f"Valor mayor que el máximo {check.max_value:g}"
        return None

    if tipo in _TIPOS_TEXTO:
        if not isinstance(valor, str):
            return f"Tipo incorrecto: se esperaba {check.tipo}"
        if check.pattern and not re.match(check.pattern, valor):
            return f"No cumple el patrón {check.pattern}"
        return None

    if tipo == "email":
        if not isinstance(valor, str) or not _EMAIL_RE.match(valor):
            return "Correo electrónico inválido"
        return None

    if tipo in _TIPOS_FECHA:
        formato = check.date_format or "YYYY-MM-DD"
        if not _es_fecha(valor, _a_strftime(formato)):
            return f"Fecha inválida (se esperaba formato {formato})"
        return None

    if tipo == "enum":
        if check.allowed_values is not None and valor not in check.allowed_values:
            permitidos = ", ".join(str(v) for v in check.allowed_values)
            return f"Valor no permitido: debe ser uno de [{permitidos}]"
        return None

    if tipo in _TIPOS_BOOLEANO:
        if not (isinstance(valor, bool) or str(valor).lower() in ("true", "false")):
            return "Valor booleano inválido"
        return None

    # Tipo desconocido: solo se exige presencia (ya comprobada)
    return None


def _a_numero(valor: Any) -> Optional[float]:
    """Convierte un valor a número; devuelve None si no es numérico."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    try:
        return float(str(valor))
    except (TypeError, ValueError):
        return None


def _a_strftime(formato: str) -> str:
    """Convierte un formato de fecha estilo JS (YYYY-MM-DD) a strftime."""
    salida = formato
    for token, reemplazo in _TOKENS_FECHA:
        salida = salida.replace(token, reemplazo)
    return salida


def _es_fecha(valor: Any, formato: str = "%Y-%m-%d") -> bool:
    """Comprueba si un valor es una fecha válida con el formato dado."""
    if isinstance(valor, (datetime, date)):
        return True
    try:
        datetime.strptime(str(valor).strip(), formato)
        return True
    except (TypeError, ValueError):
        return False


def _calcular_metricas(rows: list[dict], checks: list[FieldCheck]) -> Metrics:
    """Suma y media de la primera columna numérica definida en el esquema."""
    columna_num = next(
        (c.nombre for c in checks if c.tipo.lower() in _TIPOS_NUMERO), None
    )
    if not columna_num:
        return Metrics()

    valores: list[float] = []
    for fila in rows:
        num = _a_numero(fila.get(columna_num))
        if num is not None:
            valores.append(num)

    if not valores:
        return Metrics(columna=columna_num)

    return Metrics(
        columna=columna_num,
        suma=sum(valores),
        media=sum(valores) / len(valores),
        histograma=_histograma(valores),
    )


def _histograma(valores: list[float], n_tramos: int = 6) -> list[HistogramBin]:
    """Divide los valores en tramos iguales y cuenta cuántos caen en cada uno."""
    minimo, maximo = min(valores), max(valores)
    if maximo == minimo:
        return [HistogramBin(min=minimo, max=maximo, cantidad=len(valores))]

    ancho = (maximo - minimo) / n_tramos
    conteos = [0] * n_tramos
    for valor in valores:
        idx = int((valor - minimo) / ancho)
        if idx >= n_tramos:
            idx = n_tramos - 1
        conteos[idx] += 1

    tramos: list[HistogramBin] = []
    for i, cantidad in enumerate(conteos):
        tramos.append(
            HistogramBin(
                min=minimo + i * ancho,
                max=minimo + (i + 1) * ancho,
                cantidad=cantidad,
            )
        )
    return tramos
