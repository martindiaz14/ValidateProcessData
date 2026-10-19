# Tareas — Spec 001: Primera vista

- [x] **T1. Esquema de calidad (Pydantic).** RF-1, RF-2, RF-3, RF-4
  - Hecho cuando: `QualitySchema`, `FieldSpec`, `RowError` y `ValidationResult` están
    definidos y rechazan tipos desconocidos.
- [x] **T2. Parser de archivos.** RF-1, RF-6
  - Hecho cuando: `parse_file` lee CSV y JSON y lanza error en español con archivo vacío
    o extensión no soportada.
- [x] **T3. Validador de filas.** RF-1, RF-2, RF-3, RF-4, RF-6
  - Hecho cuando: `validate_rows` devuelve total, válidas, inválidas, errores por fila y
    métricas; y `pytest` pasa con los casos de la spec.
- [x] **T4. Modelo y base de datos.** RF-5
  - Hecho cuando: `Upload` persiste en SQLite y la sesión funciona.
- [x] **T5. Endpoint de carga.** RF-1, RF-5, RF-6
  - Hecho cuando: `POST /api/v1/upload` recibe archivo + esquema, valida, persiste y
    devuelve el resultado; y `pytest` cubre el endpoint.
- [x] **T6. Pantalla frontend.** RF-7
  - Hecho cuando: `index.html` + `app.js` + componentes permiten subir archivo y esquema,
    validar y ver resumen, errores y gráfica; se ve bien en móvil.
- [x] **T7. Verificación end-to-end.** RNF-1, RNF-3
  - Hecho cuando: `pytest` pasa completo y la app funciona en el navegador (escritorio y
    móvil) con un archivo de prueba real.

## Notas de verificación (2026-10-13)
- `pytest`: 18 tests en verde (validator, parser, endpoint).
- Navegador (Chrome DevTools): subida real de `ejemplo_datos.csv` + `ejemplo_esquema.json`
  → 5 filas, 3 válidas, 2 inválidas, 3 errores y gráfica; correcto en escritorio (1280px)
  y móvil (375px).
- Persistencia: registro de carga guardado en SQLite (`data.sqlite3`, tabla `uploads`).
