"""Modelos Pydantic: esquemas de calidad y resultado de validación.

Se admiten dos formatos de esquema:
- Enriquecido (el habitual): {"table_name": ..., "rules": {campo: {type, ...}}}
- Compacto: {"campos": [{nombre, tipo, requerido}]}
Ambos se normalizan a FieldCheck para que el validador sea único.
"""
from dataclasses import dataclass
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator

# Tipos de dato del esquema compacto
TipoCampo = Literal["texto", "numero", "fecha", "booleano"]


class FieldSpec(BaseModel):
    """Definición de un campo en el esquema compacto."""
    nombre: str = Field(..., min_length=1, description="Nombre de la columna")
    tipo: TipoCampo = Field(..., description="Tipo de dato del campo")
    requerido: bool = Field(True, description="Si el campo debe estar siempre presente")

    @field_validator("nombre")
    @classmethod
    def nombre_no_vacio(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El nombre del campo no puede estar vacío")
        return v.strip()


class QualitySchema(BaseModel):
    """Esquema compacto: {"campos": [...]}. Ver RulesSchema para el enriquecido."""
    campos: list[FieldSpec] = Field(..., min_length=1)

    @field_validator("campos")
    @classmethod
    def campos_no_vacios(cls, v: list[FieldSpec]) -> list[FieldSpec]:
        if not v:
            raise ValueError("El esquema debe definir al menos un campo")
        return v


class FieldRule(BaseModel):
    """Regla de validación de un campo en el esquema enriquecido."""
    type: str = Field(..., description="Tipo: string, float, date, email, enum, ...")
    required: bool = False
    pattern: Optional[str] = Field(None, description="Expresión regular (para string)")
    min_value: Optional[float] = Field(None, description="Mínimo permitido (numérico)")
    max_value: Optional[float] = Field(None, description="Máximo permitido (numérico)")
    format: Optional[str] = Field(None, description="Formato de fecha, p. ej. YYYY-MM-DD")
    allowed_values: Optional[list[Any]] = Field(
        None, description="Valores permitidos (para enum)"
    )


class RulesSchema(BaseModel):
    """Esquema enriquecido: {"table_name": ..., "rules": {campo: regla}}."""
    table_name: Optional[str] = None
    rules: dict[str, FieldRule]

    @field_validator("rules")
    @classmethod
    def rules_no_vacias(cls, v: dict[str, FieldRule]) -> dict[str, FieldRule]:
        if not v:
            raise ValueError("El esquema debe definir al menos una regla")
        return v


@dataclass
class FieldCheck:
    """Regla normalizada que usa el validador (común a ambos formatos)."""
    nombre: str
    requerido: bool
    tipo: str
    pattern: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    date_format: Optional[str] = None
    allowed_values: Optional[list[Any]] = None


def parse_schema(payload: Any) -> tuple[Optional[str], list[FieldCheck]]:
    """Detecta el formato del esquema y devuelve (tabla, reglas normalizadas).

    Lanza ValueError con mensaje en español si no coincide con ningún formato.
    """
    if not isinstance(payload, dict):
        raise ValueError("El esquema debe ser un objeto JSON.")

    if "rules" in payload:
        rs = RulesSchema.model_validate(payload)
        checks = [
            FieldCheck(
                nombre=nombre,
                requerido=regla.required,
                tipo=regla.type,
                pattern=regla.pattern,
                min_value=regla.min_value,
                max_value=regla.max_value,
                date_format=regla.format,
                allowed_values=regla.allowed_values,
            )
            for nombre, regla in rs.rules.items()
        ]
        return rs.table_name, checks

    if "campos" in payload:
        qs = QualitySchema.model_validate(payload)
        checks = [
            FieldCheck(nombre=c.nombre, requerido=c.requerido, tipo=c.tipo)
            for c in qs.campos
        ]
        return None, checks

    raise ValueError(
        'El esquema debe tener "rules" (enriquecido) o "campos" (compacto).'
    )


class RowError(BaseModel):
    """Error de una fila concreta del archivo."""
    fila: int = Field(..., description="Número de fila (1-based)")
    columna: str = Field(..., description="Columna con el problema")
    motivo: str = Field(..., description="Motivo del error en español")


class HistogramBin(BaseModel):
    """Tramo del histograma de una columna numérica."""
    min: float
    max: float
    cantidad: int


class Metrics(BaseModel):
    """Métricas numéricas de la primera columna numérica del esquema."""
    columna: Optional[str] = None
    suma: Optional[float] = None
    media: Optional[float] = None
    histograma: Optional[list[HistogramBin]] = None


class Correccion(BaseModel):
    """Entrada del rastro de auditoría de una celda corregida (RF-9)."""
    fila: int = Field(..., description="Número de fila (1-based)")
    columna: str = Field(..., description="Columna corregida")
    antes: str = Field(..., description="Valor original crudo de la celda")
    despues: Union[str, float, int] = Field(
        ..., description="Valor tras la corrección (texto o número)"
    )
    tipo: str = Field(
        ..., description="Tipo de corrección (vocabulario cerrado del contrato)"
    )


class ValidationResult(BaseModel):
    """Resultado completo de la validación de un archivo."""
    total_filas: int
    validas: int
    invalidas: int
    errores: list[RowError]
    metricas: Metrics
    columnas: list[str] = []
    muestra: list[dict] = []
    muestra_filas: list[int] = []
    correcciones: list[Correccion] = []
    filas_corregidas: list[dict] = []
    descarga_corregida_disponible: bool = True


class EntornoRespuesta(BaseModel):
    """Entorno de despliegue (RF-1): modo y límite de subida vigente."""
    modo: Literal["nube", "local"]
    limite_mb: int
