# MEMORY.md — Plataforma de Procesamiento y Validación de Reportes
Memoria del proyecto entre sesiones. Máximo ~50 líneas: resume o elimina lo que no aporte.

## Estado actual
- Pivote: de web estática (diario) a app B2B full-stack. `docs/constitution.md` v3 (vanilla +
  FastAPI/SQLite); `AGENTS.md` acorde. `data-processor-app/backend/` (paquete `app/`) y
  `frontend/` vanilla. Ayuda contextual en `HelpModal.js`.
- Spec 001 COMPLETADA: carga CSV/JSON + esquema configurable + validación + reporte.
- Spec 002 COMPLETADA: celdas en rojo, editor de esquema en línea, exportación CSV/JSON,
  gráficas extra y Excel (.xlsx, openpyxl).
- Spec 003 COMPLETA (T1-T17): autocorrección (`normalizer.py`), edición manual, descargas
  normal/corregida y vista previa de errores (`muestra_filas`, títulos dictados).
  Vista previa SIN LÍMITE (decisión 24): `preparar_muestra` trae TODAS las filas de
  interés; el campo `limite_muestra` se ELIMINÓ de backend Y frontend (si un cliente
  antiguo lo envía, el backend lo ignora sin 400). Frontend: contador siempre visible
  «X filas con errores o correcciones · Y incidencias» (singular correcto; X/Y del
  cruce errores ∪ correcciones, derivados en el navegador) y aviso ámbar no bloqueante
  desde 2.000 filas; en fallback, sin contador. **189 tests en verde** (T16 redujo la
  colección: sin tests de recorte). Queda la revisión final del usuario.
- Mantenimiento: favicon inline e `id`/`name` en todos los controles; JSON de esquema byte a byte.
- Publicación: repositorio GitHub inicializado y publicado en `main`; mantener fuera la base
  `data.sqlite3`, bytecode `.pyc` y cachés porque son artefactos locales.

## Decisiones (y por qué)
- Frontend JS vanilla (sin React/npm/build); FastAPI + Pydantic v2 + Pandas + SQLAlchemy 2.0/
  SQLite + Uvicorn con `Session` síncrona. Esquema normalizado a `FieldCheck`; `validator.py`
  único; Texto → patrón con `ejemploAPatron()`; preview máx. 50 filas; exportaciones
  client-side; openpyxl solo lectura; .xls NO; `quality_schema` como campo.
- Spec 003, cerradas por el usuario: fechas por mayoría estricta (empate → sin convención);
  enum con Levenshtein propio (2+ candidatos → sin corregir); una entrada por celda con el tipo
  del último paso; SOLO columnas del esquema. `aplicar_ediciones` valida TODO el lote (ValueError
  → 400 español); `correcciones` ordenadas por (fila, columna en archivo, es_manual) + sorted
  estable. `autocorreccion: bool = Form(False)` (ausente = NO) y la UI envía `true|false`.
  Descarga corregida si hay correcciones O si es `.xlsx`; tope 100.000 filas = ÚNICO motivo de
  `descarga_corregida_disponible=false`. Edición manual SOLO en rojo/ámbar; solo «Aplicar» envía
  `ediciones`; «Validar» y cambios de archivo/esquema descartan pendientes con aviso; un 400 NO
  limpia. Fase 6: edición numérica → int/float (`_a_numero_manual`), no convertible → texto,
  fechas SIEMPRE TEXTO; «N celdas autocorregidas» aunque N=0 con correcciones. Ejemplo con
  marcador `sin datos` y no corregibles a propósito (`1,234`, `carlos.error.com`, `mil`,
  `DESCONOCIDO`). Descargas en cliente: original = MISMOS bytes (SHA-256), corregida desde
  `filas_corregidas` o regenerada (parser CSV propio RFC-4180).
- «Vista previa de errores» (T11+T12): `preparar_muestra` pura en `normalizer.py`
  (`validator.py`/`parser.py` intactos); nº de fila real de `muestra_filas[i]` (fallback `i+1`);
  Y = unión `errores` ∪ `correcciones`; fallback nada editable; `app.js` sin cambios. Título con
  mayúsculas dictado por el usuario (spec dejada por sincronizar).
- Límite de la vista previa: las revisiones de límite (incidencias T13/T14, filas
  T15) quedaron SUPERADAS por la decisión 24 del usuario («sin límite: todas las
  filas de interés + contador»). Estado actual: `preparar_muestra(rows, errores,
  correcciones)` SIN parámetro de tope (todas las filas de interés; fallback sin
  interés = primeras 50 con `LIMITE_MUESTRA`, único uso de la constante);
  `upload.py` ya no lee ni parsea `limite_muestra` (lo ignora, nunca 400; se
  eliminaron `_parsear_limite_muestra` y las constantes MIN/MAX); T17 cerró el
  frontend: sin `#limite-muestra`, sin helper `leerLimiteMuestra()`, sin
  `limite_muestra` en ningún FormData; contador y aviso por volumen derivados en
  `RowPreview.js` del cruce errores ∪ correcciones (celda con error Y corrección =
  1 incidencia). `LIMITE_MUESTRA` estaba a 1000 en disco (borrador propio
  contradictorio): restaurada a 50 con aprobación del usuario.

## Aprendizajes y errores a evitar
- pandas convierte `n/a`/`NA` a NaN en read_csv: usar otro marcador de la lista cerrada.
- El paso `numero` del normalizer corrige números CON separador (`10.5` → TODAS las filas); sin
  separador no. En CSVs de prueba "limpios" usar enteros o el interés se dispara.
- MCP: 375 reales solo con `emulate({viewport:"375x812x2,mobile,touch"})` (RECARGA la página);
  volver a escritorio: `emulate({pageId})` SIN viewport y después `resize_page`.
- MCP evaluate: NUNCA anidar backticks en la función de página; tras cada `reload` reinstanciar
  el capturador de `fetch`; con táctil los clics por uid fallan → eventos DOM; `\s` → `\\s`.
- Overflow a 375: `#chart`/`#chart-columnas` DECIDIDO no tocar (la tabla `#correcciones` sí
  recorta bien en su `overflow-x-auto`).
- Entre sesiones puede haber ediciones manuales en el código (p. ej. `LIMITE_MUESTRA` 50→1000):
  ejecutar `pytest` AL EMPEZAR antes de asumir en verde.
- Otros: frontmatter YAML de agentes se descarta si no parsea; `skills` exige Node ≥22.

## Próximos pasos
- Spec 003: **revisión final del usuario** (T1-T17 hechas y verificadas; navegador
  comprobado a 1280 y 375 contra la API real, incluidos el contador, el aviso ≥2.000
  y el fallback sin contador).
- Fijar modelo por defecto de la sesión principal (build) si se quiere Gemini ahí.
