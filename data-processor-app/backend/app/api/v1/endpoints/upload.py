"""Endpoint de carga: recibe archivo + esquema, valida y persiste el registro."""
import json
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.models.upload import Upload
from app.schemas.quality import ValidationResult, parse_schema
from app.services.normalizer import (
    corregir_filas,
    preparar_descarga_corregida,
    preparar_muestra,
)
from app.services.parser import parse_file
from app.services.validator import validate_rows

router = APIRouter()

MAX_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/upload", response_model=ValidationResult)
def upload_file(
    file: UploadFile,
    quality_schema: str = Form(...),
    autocorreccion: bool = Form(False),
    ediciones: Optional[str] = Form(None),
    session: Session = Depends(get_session),
):
    """Valida un archivo CSV/JSON contra el esquema de calidad y registra la carga.

    Si `autocorreccion` es true, los valores se normalizan sobre una copia
    antes de validar (RF-1); el campo `ediciones` trae el lote JSON de
    ediciones manuales (RF-17), que se aplican después de la normalización.
    El campo `limite_muestra` de versiones antiguas de la interfaz NO existe
    ya (RF-11, decisión «sin límite»): si un cliente antiguo lo envía, se
    IGNORA sin ningún error (RNF-5) y la vista previa trae todas las filas
    de interés.
    """
    # 1. Parsear el esquema que viene como cadena JSON en un campo de formulario
    try:
        payload = json.loads(quality_schema)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400, detail=f"El esquema no es JSON válido: {exc}"
        ) from exc

    try:
        _tabla, reglas = parse_schema(payload)
    except (ValueError, ValidationError) as exc:
        raise HTTPException(
            status_code=400, detail=f"Esquema de calidad inválido: {exc}"
        ) from exc

    # 2. Leer el archivo
    content = file.file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="El archivo supera el límite de 10 MB.")

    # 3. Parsear filas (parser lanza ValueError con mensaje en español)
    try:
        rows = parse_file(content, file.filename or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 4. Lote de ediciones manuales (RF-17): parsear ANTES de corregir
    lote = _parsear_ediciones(ediciones)

    # 5. Corregir (si procede) y validar sobre los valores ya corregidos (RF-10)
    try:
        filas, correcciones = corregir_filas(
            rows, reglas, autocorreccion=autocorreccion, ediciones=lote
        )
    except ValueError as exc:  # RF-18: lote inválido → 400 sin validar
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result: ValidationResult = validate_rows(filas, reglas)
    result.correcciones = correcciones

    # 6. Versión corregida para la descarga (RF-14, RNF-7): hace falta si hay
    #    correcciones o si el archivo es .xlsx; el tope de filas la vacía y
    #    apaga el flag (único motivo)
    es_xlsx = (file.filename or "").lower().endswith(".xlsx")
    result.filas_corregidas, result.descarga_corregida_disponible = (
        preparar_descarga_corregida(filas, correcciones, es_xlsx=es_xlsx)
    )

    # 7. Vista previa de errores (RF-11, sin límite): `muestra` trae TODAS
    #    las filas de interés (error residual o alguna corrección) y
    #    `muestra_filas` sus números 1-based; sin ninguna fila de interés el
    #    servicio devuelve el fallback de las primeras 50. El campo
    #    `limite_muestra` de clientes antiguos ya no se lee: se ignora
    result.muestra, result.muestra_filas = preparar_muestra(
        filas,
        result.errores,
        correcciones,
    )

    # 8. Persistir el registro de la carga
    registro = Upload(
        filename=file.filename or "sin_nombre",
        total_rows=result.total_filas,
        valid_rows=result.validas,
        invalid_rows=result.invalidas,
    )
    session.add(registro)
    session.commit()

    return result


def _parsear_ediciones(ediciones: Optional[str]) -> Optional[list]:
    """Parsea el campo `ediciones` (JSON del lote de ediciones manuales).

    Devuelve la lista del lote o None si no se envía. Lanza HTTPException
    400 con `detail` en español si el JSON está malformado o no es una lista
    (sin llegar a validar el archivo)."""
    if ediciones is None:
        return None
    try:
        lote = json.loads(ediciones)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"El lote de ediciones no es JSON válido: {exc}",
        ) from exc
    if not isinstance(lote, list):
        raise HTTPException(
            status_code=400,
            detail="El lote de ediciones debe ser una lista de objetos JSON.",
        )
    return lote
