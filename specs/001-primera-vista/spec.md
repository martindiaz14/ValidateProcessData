# Spec 001 — Primera vista: carga, validación y reporte básico
Estado: aprobada

## Contexto y objetivo
Las empresas necesitan subir un archivo de datos (CSV o JSON) y obtener de inmediato un
informe de calidad: cuántas filas son válidas, cuáles tienen problemas y una visión
general de los datos. Esta primera vista entrega ese flujo end-to-end mínimo para poder
ver y probar el sistema en el navegador.

## Usuarios
- Analista/empresa que sube un archivo de datos y quiere validar su calidad.

## Historias de usuario
- HU-1. Como analista, quiero subir un archivo CSV o JSON para validar sus filas.
- HU-2. Como analista, quiero ver un resumen de validación (total, válidas, inválidas)
  para saber de un vistazo la calidad del archivo.
- HU-3. Como analista, quiero ver los errores por fila (fila, columna, motivo) para
  corregir el origen.
- HU-4. Como analista, quiero ver una gráfica con la distribución de válidas/inválidas
  y las métricas numéricas para presentar el resultado.

## Definiciones
- Esquema de calidad: documento JSON que el usuario aporta y que define los campos
  esperados del archivo, con `nombre`, `tipo` (`texto`, `numero`, `fecha`, `booleano`) y
  `requerido` (true/false).
- Fila válida: fila que cumple el esquema (campos requeridos presentes y no vacíos, y
  tipo correcto). Fila inválida: fila con algún incumplimiento.

## Requisitos funcionales
- RF-1: CUANDO el analista envía un archivo CSV o JSON junto con un esquema de calidad,
  EL SISTEMA valida cada fila contra ese esquema y devuelve el resultado de validación.
- RF-2: CUANDO el archivo se valida, EL SISTEMA devuelve un resumen con: total de filas,
  número de válidas y número de inválidas.
- RF-3: CUANDO hay filas inválidas, EL SISTEMA devuelve la lista de errores con número de
  fila, nombre de columna y motivo.
- RF-4: EL SISTEMA calcula métricas numéricas básicas (suma y media) de la primera
  columna de tipo `numero` definida en el esquema.
- RF-5: CUANDO el analista carga un archivo, EL SISTEMA registra la carga (nombre,
  fecha, recuento) en la base de datos local.
- RF-6: SI el archivo está vacío, no se puede leer o el esquema es inválido, ENTONCES EL
  SISTEMA devuelve un error claro en español sin guardar nada.
- RF-7: EL SISTEMA muestra la interfaz en español y es usable en móvil (responsive).

## Requisitos no funcionales
- RNF-1: El procesamiento ocurre en el servidor; el navegador solo envía el archivo y
  pinta el resultado.
- RNF-2: Ningún dato sale del equipo del usuario (SQLite local, sin servicios externos).
- RNF-3: El backend se prueba con pytest; la lógica de validación se prueba sin HTTP.

## Casos límite
- Archivo vacío (0 filas).
- Archivo sin las columnas definidas en el esquema.
- Filas con celdas vacías o nulas.
- Valores que no coinciden con el tipo del esquema (p. ej. texto donde se espera número).
- Esquema sin campos, con tipos desconocidos o mal formado.
- Archivo con extensión no soportada (ni .csv ni .json).

## Fuera de alcance
- Autenticación, usuarios o multiempresa.
- Guardar o reutilizar esquemas entre sesiones.
- Gráficas avanzadas o exportación de reportes.

## Criterios de finalización
- Se puede subir un archivo y un esquema, y ver resumen, errores y gráfica en el
  navegador.
- `pytest` pasa para services y endpoints.
- La interfaz se ve bien en escritorio y móvil.

## Dudas abiertas
- (ninguna)
