# Spec 002 — Mejoras de utilidad
Estado: aprobada

## Contexto y objetivo
La spec 001 validaba un archivo y mostraba resumen, errores y una gráfica. Para que la
herramienta sea más útil en el día a día se añaden: vista previa de las filas con las
celdas problemáticas resaltadas, editor de esquema en línea, exportación de resultados,
más gráficas y soporte de entrada Excel (.xlsx).

## Requisitos funcionales
- RF-1: EL SISTEMA muestra una vista previa de las filas con error o corrección
  («filas de interés») y, si no las hay, de las primeras 50 filas del archivo,
  con las celdas que fallan resaltadas, para localizar el error visualmente.
  (Enmendado por la spec 003: «vista previa de errores»; el tope de 50 se
  mantiene y sigue gobernado por RNF-2.)
- RF-2: EL SISTEMA permite escribir o pegar el esquema de calidad en un editor en línea
  (JSON) con aviso de validez mientras se edita; sin subir archivo de esquema.
- RF-3: EL SISTEMA permite descargar los errores como CSV y el reporte completo como
  JSON, sin salir del equipo.
- RF-4: EL SISTEMA muestra una gráfica adicional de errores agrupados por columna.
- RF-5: EL SISTEMA muestra un histograma de la primera columna numérica del esquema.
- RF-6: EL SISTEMA acepta archivos Excel .xlsx además de CSV y JSON.
- RF-7: SI el archivo está vacío, no se puede leer o el .xlsx es inválido, ENTONCES
  devuelve un error claro en español.

## Requisitos no funcionales
- RNF-1: La descarga de resultados se hace en el navegador (Blob); sin endpoint nuevo.
- RNF-2: La vista previa se limita a las primeras 50 filas para no saturar la interfaz.
- RNF-3: Ningún dato sale del equipo (openpyxl es una librería local de lectura).
- RNF-4: `pytest` cubre el .xlsx, la vista previa y el histograma.

## Casos límite
- Archivo .xlsx vacío o corrupto.
- Vista previa de un archivo con 0 filas.
- Histograma cuando no hay columna numérica o todos los valores son iguales.

## Fuera de alcance
- .xls (requiere xlrd), parquet u otros formatos.
- Edición de filas desde el navegador.

## Criterios de finalización
- Se puede pegar un esquema, subir CSV/JSON/XLSX, ver vista previa resaltada, histograma
  y errores por columna, y descargar CSV/JSON.
- `pytest` pasa (actuales + nuevos).
- La interfaz se ve bien en escritorio y móvil.
