# Tareas — Spec 002: Mejoras de utilidad

- [x] **T1. Vista previa de filas.** RF-1
  - Hecho cuando: `ValidationResult` incluye `columnas` y `muestra` (50 filas) y la
    interfaz pinta la tabla con las celdas fallidas en rojo.
- [x] **T2. Editor de esquema en línea.** RF-2
  - Hecho cuando: el input de archivo de esquema se sustituye por un textarea con aviso
    de JSON válido/no válido y botón "Cargar ejemplo".
- [x] **T3. Exportación de resultados.** RF-3
  - Hecho cuando: botones para descargar errores (CSV) y reporte (JSON) vía Blob local.
- [x] **T4. Más gráficas.** RF-4, RF-5
  - Hecho cuando: hay gráfica de errores por columna e histograma de la columna numérica.
- [x] **T5. Entrada Excel (.xlsx).** RF-6, RF-7
  - Hecho cuando: `parse_file` lee .xlsx con openpyxl y el input acepta .xlsx.
- [x] **T6. Verificación end-to-end.** RNF-4
  - Hecho cuando: `pytest` pasa y la app funciona en el navegador (escritorio y móvil)
    con CSV, JSON y .xlsx reales.

## Notas de verificación (2026-10-14)
- `pytest`: 36 tests en verde (10 nuevos: Excel, vista previa, histograma).
- Navegador: ejemplo `.xlsx` → 10 filas, 3 válidas, 7 inválidas; 3 gráficas, vista previa
  con celdas en rojo y tabla de errores. Correcto en escritorio (1280px) y móvil (375px).
- Añadida librería `openpyxl` (solo lectura local de Excel, aprobada por el usuario).
