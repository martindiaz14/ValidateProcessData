"""Parsing de archivos CSV, JSON y Excel a filas (lista de dicts).

Esta es lógica pura: no toca HTTP ni la base de datos.
"""
import io
import json

import pandas as pd


def parse_file(content: bytes, filename: str) -> list[dict]:
    """Lee el contenido de un archivo CSV o JSON y devuelve las filas.

    Lanza ValueError con un mensaje en español si el archivo está vacío,
    no se puede leer o la extensión no está soportada.
    """
    nombre = (filename or "").lower()

    if nombre.endswith(".csv"):
        return _parse_csv(content)
    if nombre.endswith(".json"):
        return _parse_json(content)
    if nombre.endswith(".xlsx"):
        return _parse_excel(content)

    raise ValueError(
        "Extensión no soportada. Usa un archivo .csv, .json o .xlsx."
    )


def _parse_csv(content: bytes) -> list[dict]:
    if not content.strip():
        raise ValueError("El archivo está vacío.")
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as exc:  # noqa: BLE001 - se traduce a mensaje claro
        raise ValueError(f"No se pudo leer el CSV: {exc}") from exc
    return _dataframe_a_filas(df)


def _parse_json(content: bytes) -> list[dict]:
    if not content.strip():
        raise ValueError("El archivo está vacío.")
    try:
        datos = json.loads(content.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"No se pudo leer el JSON: {exc}") from exc

    # Acepta tanto una lista de objetos como un objeto con la clave "filas"
    if isinstance(datos, dict):
        datos = datos.get("filas", datos.get("rows", datos))
    if not isinstance(datos, list):
        raise ValueError(
            "El JSON debe ser una lista de objetos (uno por fila)."
        )
    return [dict(item) for item in datos if isinstance(item, dict)]


def _parse_excel(content: bytes) -> list[dict]:
    if not content:
        raise ValueError("El archivo está vacío.")
    try:
        df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"No se pudo leer el Excel: {exc}") from exc
    return _dataframe_a_filas(df)


def _dataframe_a_filas(df: pd.DataFrame) -> list[dict]:
    # NaN de pandas -> None para un manejo uniforme de celdas vacías
    return json.loads(df.to_json(orient="records", date_format="iso"))