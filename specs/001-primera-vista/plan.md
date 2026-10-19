# Plan — Spec 001: Primera vista

## Archivos y responsabilidades
- `backend/app/core/config.py`: ajustes (ruta de la base de datos). RF-5.
- `backend/app/core/database.py`: motor SQLite y sesión async (SQLAlchemy 2.0). RF-5.
- `backend/app/models/upload.py`: modelo `Upload` (nombre, fecha, total, válidas,
  inválidas). RF-5.
- `backend/app/schemas/quality.py`: modelos Pydantic del esquema de calidad
  (`FieldSpec`, `QualitySchema`) y de la respuesta (`RowError`, `ValidationResult`).
  RF-1 a RF-4.
- `backend/app/services/parser.py`: `parse_file()` lee CSV/JSON y devuelve filas como
  lista de dicts. RF-1, RF-6.
- `backend/app/services/validator.py`: `validate_rows()` valida filas contra el esquema
  y calcula métricas. Función pura, sin HTTP ni BD. RF-1 a RF-4, RF-6.
- `backend/app/api/v1/endpoints/upload.py`: recibe archivo + esquema, llama a services
  y persiste el registro. RF-1, RF-5, RF-6.
- `backend/app/api/v1/api.py`: monta los routers bajo `/api/v1`.
- `backend/app/main.py`: app FastAPI, incluye API y sirve el frontend estático.
- `frontend/index.html`: estructura de la pantalla (carga, resumen, errores, gráfica).
  RF-7.
- `frontend/app.js`: lógica de interfaz; envía el archivo/esquema y pinta la respuesta.
- `frontend/components/`: `FileUploader.js`, `ValidationSummary.js`, `MetricsChart.js`.
- `backend/tests/test_validator.py`: tests de la lógica de validación. RNF-3.
- `backend/tests/test_parser.py`: tests del parseo de archivos. RNF-3.

## Funciones puras
- `validate_rows(rows: list[dict], schema: QualitySchema) -> ValidationResult`
  (misma salida para mismas entradas; sin fechas ni estado global).
- `parse_file(content: bytes, filename: str) -> list[dict]`.

## Algoritmo (pseudocódigo de validate_rows)
```
para cada campo del esquema si tipo == "numero" y no se ha elegido aún: num_col = campo
errores = []
validas = 0
para cada fila con índice i:
    motivos = []
    para cada campo del esquema:
        valor = fila.get(campo.nombre)
        si campo.requerido y (valor ausente o vacío): motivos.append("requerido")
        si valor presente y no coincide con campo.tipo: motivos.append("tipo incorrecto")
    si motivos: errores.append(RowError(fila=i+1, ...))
    si no: validas += 1
metricas = suma y media de num_col si existe
devolver ValidationResult(total, validas, invalidas, errores, metricas)
```

## Interfaz
- Pantalla única en `index.html`: dos zonas de carga (archivo de datos y esquema JSON),
  botón "Validar", y zona de resultados con tarjetas de resumen, lista de errores y
  gráfica de barras (Chart.js por CDN). Tailwind por CDN. Responsive.

## Decisiones (con alternativa descartada)
- Validación en `services/` pura y sin HTTP: descartado validar dentro del endpoint
  porque no se podría probar con pytest sin levantar servidor.
- Esquema como JSON subido/pegado por el usuario: descartadas columnas fijas (poco
  flexible) y esquema inferido (no valida tipos).
- Chart.js por CDN: descartado Recharts porque exige React (rompe la constitución).

## Estrategia de tests
- `pytest` sobre `validate_rows` y `parse_file`: casos de filas válidas, inválidas,
  celdas vacías, tipos incorrectos, esquema inválido y archivo ilegible. Cubre RF-1,
  RF-2, RF-3, RF-4, RF-6.
