# Plan — Spec 003: Auto-corrección y corrección manual

Punto de partida (MEMORY.md): 36 tests en verde; backend FastAPI + SQLAlchemy con
`Session` síncrona; frontend vanilla sin build; verificación visual en navegador a
1280px y 375px. `validate_rows(rows, checks)` y `parse_file(content, filename)` no
cambian de firma.

Notas de plantilla:
- Ninguna función nueva necesita la fecha actual (`hoy`) como parámetro: la
  autocorrección es determinista (Definiciones de la spec), misma entrada → mismas
  correcciones, sin estado global.
- Tests de backend: `pytest` desde `data-processor-app/backend/`. No aplica
  `node --test` ni ningún test runner de JavaScript: la constitución (regla 4) y el
  RNF-6 piden verificar el frontend en el navegador contra la API real, sin
  frameworks de testing en JS.

## Archivos y responsabilidades (y RF que cubre cada uno)

- **Nuevo** `backend/app/services/normalizer.py` → normalización automática
  (RF-1 a RF-8), rastro de correcciones y su orden (RF-9), ediciones manuales
  (RF-17, RF-18), condiciones de envío de `filas_corregidas` (correcciones o
  `.xlsx`) con su tope de filas (RNF-7) y `preparar_muestra` (filas de interés
  de la vista previa, RF-11). Lógica pura, sin HTTP ni BD
  (RNF-1), coste lineal (RNF-4), sin librerías nuevas (RNF-3).
- `backend/app/schemas/quality.py` → modelo `Correccion` y los campos nuevos de
  `ValidationResult` (`correcciones`, `filas_corregidas`,
  `descarga_corregida_disponible` y `muestra_filas`), todos con valor por defecto
  (RF-9, RF-11, RF-14, RNF-5).
- `backend/app/services/validator.py` → **SIN CAMBIOS** (incluidos `_muestra()` y
  `LIMITE_MUESTRA`, intocables por regla del proyecto). Ya calcula resumen, errores
  y métricas sobre las filas que recibe; su `muestra` (primeras 50) se pisa en el
  endpoint con las filas de interés (RF-11) y `LIMITE_MUESTRA` solo se importa
  como constante.
- `backend/app/services/parser.py` → **SIN CAMBIOS**.
- `backend/app/api/v1/endpoints/upload.py` → campos de formulario `autocorreccion` y
  `ediciones` (RF-12, RF-17), validación del lote con 400 en español (RF-18),
  composición normalizar → validar, relleno de los campos nuevos de la respuesta
  (RF-9, RF-14), tope de filas (RNF-7) y composición de `muestra`/`muestra_filas`
  con `preparar_muestra` sobre `result.errores` y `correcciones` (RF-11);
  compatibilidad de la respuesta (RNF-5). El
  registro de carga sigue guardando solo recuentos (RNF-2, nota histórica de RF-17).
- `frontend/components/FileUploader.js` → interruptor "Autocorrección" activado por
  defecto (RF-12) y callback de cambio de entrada para descartar ediciones pendientes
  (RF-16).
- `frontend/app.js` → estado de ediciones pendientes, envío en las dos peticiones,
  avisos en español, sección "Correcciones aplicadas" y conexión de todos los
  componentes (RF-13, RF-16, RF-17, RF-15).
- `frontend/components/RowPreview.js` → títulos "Vista previa de errores" /
  "Vista previa de filas", número de fila real desde `muestra_filas`, nota
  "mostrando X de Y" con la Y derivada de `errores` ∪ `correcciones`, celdas
  corregidas en ámbar con tooltip, errores en rojo por encima, celdas editables
  por su `fila: <n>` real (en fallback, ninguna) y botón "Aplicar cambios y
  revalidar" (RF-11, RF-16, RF-15).
- `frontend/components/ValidationSummary.js` → contadores "N celdas autocorregidas" y
  "M ediciones manuales" (RF-13).
- `frontend/components/ExportButtons.js` → bloque "Descargas" con los 5 botones y la
  generación de la versión corregida (RF-14, RNF-3).
- `frontend/index.html` → contenedores nuevos (`#correcciones`, `#aviso`) (RF-13).
- **Nuevos** `backend/ejemplo_autocorreccion.csv` y
  `backend/ejemplo_autocorreccion_esquema.json` → archivo de ejemplo de esta spec
  (errores de formato que sí se corrigen y otros que no) para los criterios de
  finalización y la verificación en navegador (RF-3 a RF-8, RF-14). Creados con el
  permiso explícito del usuario (AGENTS.md pide preguntar antes de crear archivos).
- Tests: **nuevos** `backend/tests/test_normalizer.py` y
  `backend/tests/test_ediciones.py`; **ampliado** `backend/tests/test_upload_endpoint.py`
  (RNF-6). Los archivos nuevos están pre-aprobados al aprobar este plan (AGENTS.md
  pide preguntar antes de crear archivos).

## Enfoque técnico

### Backend: normalización (RF-1 a RF-9)
Un módulo nuevo `services/normalizer.py` recorre las filas y devuelve SIEMPRE una
copia corregida + el rastro de correcciones. Por cada fila y **solo para las
columnas definidas en el esquema** (RF-2), el valor pasa por un pipeline en el orden
fijo del contrato:

```
limpieza (espacios/invisibles) → vacio → minusculas (email) → enum → numero/fecha
```

- Cada paso solo actúa si aplica a la regla de la columna y solo genera registro si
  modifica el valor; una celda con varios pasos deja UNA sola entrada con el `tipo`
  del último paso que modificó y `antes` = el valor crudo original (RF-9).
- Si tras la limpieza el valor queda vacío (solo espacios/invisibles), no hay
  registro: el validador actual ya lo trata como vacío (RF-3).
- La convención de fechas de columna se deduce UNA vez (pre-paso por columna de
  fecha) clasificando sus valores de lectura única en `día/mes`, `mes/día`, "en
  conflicto" (→ sin convención) o "sin evidencia"; después la pasada de
  normalización la aplica a los ambiguos según las reglas (a)/(b)/(c) del RF-6.
  Interpretación confirmada del RNF-4: los dos pasos son de coste lineal (una
  pasada por columna de fecha y una por celda, cada valor con número constante de
  revisiones), que es lo que basta para "sin degradar de forma apreciable".
- Números: sólo conversión con patrón inequívoco (RF-5); ambiguos y textos sin
  sentido se quedan como están para que el validador emita su error habitual.
- Enums: coincidencia exacta insensible a mayúsculas/espacios y, si no, único
  candidato a distancia de edición ≤ 1 (RF-7); con dos candidatos no se corrige.
- Marcadores de vacío solo en columnas NO requeridas (RF-8).

### Backend: ediciones manuales (RF-17, RF-18)
`aplicar_ediciones` valida el lote ANTES de tocar nada: fila entero 1..N y columna
presente en el esquema, si no `ValueError` con mensaje en español que el endpoint
traduce a 400 sin validar. Después aplica las ediciones **en orden del lote** sobre
la copia YA normalizada, dejando una entrada `manual` por aplicación (una misma
celda repetida se apila y cada cambio queda registrado con su `antes`). El
`despues` de una entrada `manual` se serializa como TEXTO (el valor llega como
texto en la petición) y, en cambio, en `filas_corregidas` la celda editada
conserva la representación de `muestra` (número si la celda es numérica, texto
para las fechas).

### Backend: endpoint (RF-1, RF-12, RF-14, RF-17)
```python
# upload.py (pseudocódigo)
filas, correcciones = corregir_filas(rows, reglas, autocorreccion, ediciones)  # ValueError → 400
result = validate_rows(filas, reglas)       # RF-10: resumen/errores/métricas/muestra corregidos
result.correcciones = correcciones           # ya ordenada (RF-9)
es_xlsx = filename.lower().endswith(".xlsx")  # .xlsx siempre necesita filas_corregidas
result.filas_corregidas, result.descarga_corregida_disponible = \
    preparar_descarga_corregida(filas, correcciones, es_xlsx)
# registro de carga igual que hoy (una fila nueva por petición, solo recuentos)
```
Peticiones sin `autocorreccion` ni `ediciones` producen la respuesta de hoy más los
campos nuevos con sus valores por defecto (RNF-5). `filas_corregidas` se envía cuando
hay correcciones O cuando el archivo subido es `.xlsx` (aunque no las haya, porque el
navegador no puede regenerar un .xlsx); si no hay correcciones y el archivo NO es
`.xlsx`, se envía vacío y la corregida se genera en el navegador desde el original.
Sea cual sea el formato, si el archivo supera las 100.000 filas se envía vacío;
`descarga_corregida_disponible` es `false` SOLO por ese tope (RNF-7).

### Backend y frontend: vista previa de errores (RF-11, RF-15, RF-16; revisión aprobada)
Punto de partida de esta revisión: 171 tests en verde y la spec 003 ya
implementada (T1-T10); `validator.py` y `parser.py` siguen intactos.

- **Backend**: `preparar_muestra(filas, errores, correcciones)` (pura, en
  `normalizer.py`, con `LIMITE_MUESTRA` importado de `validator.py` sin tocarlo)
  devuelve `(muestra, muestra_filas)`: los números de fila 1-based que aparecen en
  `errores` O en `correcciones` (unión = filas de interés), ordenados y con tope
  50; `muestra` trae esos objetos de fila y `muestra_filas` sus números, con la
  misma longitud y el mismo orden. Si la unión está vacía → fallback: las primeras
  50 filas de siempre y `muestra_filas = [1, 2, …, N]` (idéntico a hoy). El
  endpoint la llama DESPUÉS de `validate_rows` (usa `result.errores` y
  `correcciones`), pisa `result.muestra` y rellena `result.muestra_filas`; la
  composición vive en `upload.py` y la lógica pura en el servicio (ver decisión 18).
- **Total de interés (la Y de la nota)**: no viaja en ningún campo; el navegador
  lo deriva como el número de filas distintas de la unión `errores` ∪
  `correcciones`, que llegan completas en la respuesta (cubre el caso "solo
  correcciones", ámbar sin rojo).
- **Frontend**: `RowPreview.js` deja de infierir `numFila = i + 1` y usa
  `muestra_filas[i]`: eso alimenta la columna "#", las claves `fila:columna` del
  rojo/ámbar y el `fila: <n>` que viaja en las ediciones (una fila 200 o 900 que
  entre en el tope se edita con su número real, RF-18). Título "Vista previa de
  errores" cuando hay filas de interés y "Vista previa de filas" en fallback (con
  la nota de hoy); con más de 50 filas de interés, nota "Mostrando X de Y filas
  con errores o correcciones." solo si X < Y.
- **Edición**: editables SOLO las celdas con error o corregidas de las filas
  mostradas (hasta 50 de interés); en fallback ninguna celda es editable (RF-16).
  El Map de pendientes, "Aplicar cambios y revalidar", la sección de correcciones
  y las descargas no cambian (T7-T9 intactos).

#### Revisión aprobada: límite por incidencias editable (RF-11, RF-15, RF-16)
(Semántica sustituida por la revisión siguiente —tope por FILAS de interés—;
queda como histórico de T13-T14.)
Punto de partida: 179 tests en verde (T1-T12 implementadas); `validator.py` y
`parser.py` siguen intactos.

- **Backend**: `preparar_muestra` deja de contar filas y cuenta INCIDENCIAS con
  un presupuesto parametrizado: recorre las celdas de la unión `errores` ∪
  `correcciones` en orden de fila, **una incidencia por celda** (una celda con
  error Y corrección cuenta 1 sola) y añade filas mientras sus incidencias
  quepan; si una fila no cabe entera pero al menos una de sus incidencias cabe,
  se añade la fila COMPLETA (nunca se parte). Firma con
  `limite_incidencias: int = LIMITE_MUESTRA` (ya recortado por el endpoint);
  sin ninguna incidencia → fallback de siempre (primeras 50 filas,
  `muestra_filas = [1, 2, …, N]`, el límite no se aplica).
- **Endpoint**: `upload.py` lee `limite_muestra` del multipart como texto y lo
  recorta él mismo: no numérico → 50; `< 1` → 1; `> 1000` → 1000 (nunca 400;
  el campo ausente también da 50). Después llama a
  `preparar_muestra(filas, result.errores, correcciones, limite_incidencias=…)` y
  pisa `result.muestra` / `result.muestra_filas` como en T11.
- **Frontend**: `FileUploader.js` añade junto al interruptor un campo numérico
  «Máximo de incidencias en la vista previa» (etiqueta y ayuda en español,
  defecto visible 50, `min=1` `max=1000`, usable a 375px) y `app.js` lo agrega al
  `FormData` como `limite_muestra` en TODAS las validaciones, incluida la de
  "Aplicar cambios y revalidar"; **lo que viaja es el valor de la interfaz en
  ese momento** (si el analista lo cambia entre validaciones, viaja el nuevo).
- **Nota y título**: `RowPreview.js` calcula del cruce `errores` ∪
  `correcciones` las incidencias totales (Y), las filas de interés (M) y las
  visibles (N) y pinta "Mostrando X de Y incidencias en N de M filas." solo si
  queda algo fuera (X = incidencias de las filas visibles, que puede superar el
  límite por la última fila). Título "Vista Previa de Errores" cuando hay
  incidencias y "Vista previa de filas" en fallback (con la nota de hoy).
  `muestra_filas`, la edición con `fila: <n>` real, la sección de correcciones y
  las descargas no cambian.

#### Revisión aprobada: límite por FILAS de interés editable (RF-11, RF-15, RF-16)
(Semántica sustituida por la revisión siguiente —«sin límite: todas las filas
de interés + contador y aviso»—; queda como histórico de T15, cuyo frontend
—etiqueta del campo— nunca llegó a implementarse.)
Punto de partida: 191 tests en verde (T1-T14 implementadas); `validator.py` y
`parser.py` siguen intactos. Esta revisión SUSTITUYE la semántica de presupuesto
de incidencias de la revisión anterior (que queda arriba como histórico): el
usuario confirmó que el campo decide CUÁNTAS FILAS se ven, no cuántas
incidencias —«yo te pedí que sea un máximo de filas editable por el usuario,
pero que la vista previa siga siendo de los errores»—.

- **Backend**: `preparar_muestra` vuelve a contar FILAS de interés: recorre los
  números de la unión `errores` ∪ `correcciones` en orden de fila y añade filas
  hasta alcanzar N (una fila consume 1 aunque tenga 1 o 100 incidencias y se
  muestra siempre entera; sin presupuesto por celda ni regla de fila completa).
  Firma con `limite_filas: int = LIMITE_MUESTRA` (ya recortado por el endpoint;
  renombra al `limite_incidencias` de la revisión anterior). El backend NO
  calcula el recuento de incidencias (informativo, sin campo nuevo). Sin ninguna
  fila de interés → fallback de siempre (primeras 50 filas,
  `muestra_filas = [1, 2, …, N]`, el campo no se aplica).
- **Endpoint**: el recorte de `limite_muestra` NO cambia (mismo texto, mismo
  rango 1-1000, nunca 400); solo cambia el nombre del parámetro al llamar a
  `preparar_muestra(filas, result.errores, correcciones, limite_filas=…)`.
- **Frontend**: `FileUploader.js` solo cambia la etiqueta y la ayuda del campo
  («Máximo de filas en la vista previa»); `app.js` no cambia (el límite ya viaja
  en todas las validaciones, incluida la revalidación, y se lee del DOM en cada
  envío); `RowPreview.js` calcula del cruce `errores` ∪ `correcciones` las
  filas de interés (Y), las filas visibles (X) y las incidencias totales (Z,
  informativo) y pinta "Mostrando X de Y filas con errores o correcciones (Z
  incidencias)." solo si X < Y.
- **Título y edición intactos**: "Vista Previa de Errores" cuando hay filas de
  interés y "Vista previa de filas" en fallback; editables las celdas con error
  o corregidas de las filas visibles y ninguna en fallback (RF-16); la vista
  previa SIGUE siendo solo de filas con error/corrección (el campo no la
  convierte en vista general del archivo).

#### Revisión aprobada: sin límite — todas las filas de interés + contador y aviso (RF-11, RF-15, RF-16)
Punto de partida: 193 tests en verde (T1-T15 implementadas); `validator.py` y
`parser.py` siguen intactos. Esta revisión SUSTITUYE el campo de límite de las
dos revisiones anteriores (incidencias y filas; quedan arriba como histórico):
el usuario eligió «sin límite: mostrar todas + contador» —«sigo sin saber por
qué no es una buena idea que en vez de ser un límite haya un contador de filas
con errores»— tras explicarle el motivo de rendimiento.

- **Backend**: `preparar_muestra(rows, errores, correcciones)` SIN ningún
  parámetro de límite: devuelve TODAS las filas de interés de la unión
  `errores` ∪ `correcciones` en orden de fila (se elimina `limite_filas`).
  Sin ninguna fila de interés → fallback de siempre (primeras 50 filas con
  `LIMITE_MUESTRA`, `muestra_filas = [1, 2, …, N]`). El backend NO calcula el
  contador ni el aviso (los deriva el navegador del cruce completo, sin campo
  nuevo).
- **Endpoint**: `upload.py` deja de leer y de recortar `limite_muestra` del
  multipart; SI un cliente antiguo lo envía, el campo se IGNORA (nunca un 400
  por él) y la respuesta trae todas las filas de interés. La llamada pasa a
  `preparar_muestra(filas, result.errores, correcciones)` y pisa
  `result.muestra` / `result.muestra_filas` como en T11.
- **Frontend**: `FileUploader.js` ELIMINA el campo numérico y su ayuda (el
  formulario queda con el interruptor de autocorrección y lo de siempre);
  `app.js` deja de agregar `limite_muestra` al `FormData` (también en la
  revalidación); `RowPreview.js` pinta SIEMPRE, encima de la tabla, el
  contador "X filas con errores o correcciones · Y incidencias" (X = filas de
  interés = las visibles; Y = incidencias totales, celda con error Y corrección
  cuenta 1; singular correcto) derivado del cruce `errores` ∪
  `correcciones`, y cuando X ≥ 2.000 añade el aviso NO bloqueante "Esta vista
  previa tiene N filas con errores o correcciones; puede tardar en mostrarse."
- **Título, contador y edición intactos**: "Vista Previa de Errores" cuando
  hay filas de interés y "Vista previa de filas" en fallback (SIN contador);
  editables las celdas con error o corregidas de todas las filas visibles y
  ninguna en fallback (RF-16); la vista previa sigue siendo solo de filas con
  error/corrección.

### Frontend: interruptor (RF-12)
`FileUploader.js` añade el interruptor "Autocorrección" (por defecto activado) y
pasa su estado a `app.js`, que lo agrega al `FormData` como `autocorreccion=true|false`
en TODAS las peticiones de validación. El interruptor controla solo la normalización:
las ediciones manuales viajan siempre que existan.

### Frontend: vista previa editable (RF-11, RF-16, RF-17)
- `app.js` mantiene `edicionesPendientes` (Map `"fila:columna"`) y el `File` de la
  última validación; `RowPreview.js` recibe callbacks (`onEdicion`, `onAplicar`).
- Clases de celda: rojo si tiene error (gana), ámbar si tiene entrada en
  `correcciones` y no falla, con `title` = `antes` de la primera entrada de la celda
  (tooltip de escritorio; en táctil no se muestra y el "antes" se consulta en la
  sección de correcciones, RF-11).
- Editables solo las celdas con error o corregidas dentro de las primeras 50 filas
  (la `muestra`); al confirmar se marca la celda como pendiente (aro azul) y se
  habilita el botón "Aplicar cambios y revalidar", ÚNICO punto que envía
  `ediciones` (JSON.stringify del Map).
- Al recibir la respuesta se limpia el Map y se repinta todo (RF-17). "Validar"
  con pendientes las descarta con aviso; cambiar archivo o esquema desde
  `FileUploader` (listener delegado en el contenedor) las limpia con aviso. Los
  avisos van en un contenedor propio (`#aviso`) para no ocultar resultados.

### Frontend: sección de correcciones (RF-13)
`renderCorrecciones()` en `app.js` (mismo patrón que `renderErrores`) pinta en
`#correcciones` la tabla fila · columna · antes → después · tipo, con badge que
distingue automática/manual, máximo las primeras 50 entradas y nota "mostrando X de
Y". `ValidationSummary.js` añade los contadores: entradas con `tipo != manual` →
"N celdas autocorregidas"; con `tipo == manual` → "M ediciones manuales".

### Frontend: descargas (RF-14)
Bloque "Descargas" con 5 botones:
- "Archivo original": los bytes del `File` de la última validación (Blob, sin
  endpoint nuevo, RNF-3).
- "Archivo corregido (CSV)": cabecera = `columnas` de la respuesta, una fila por
  elemento de `filas_corregidas`, números con `String(valor)` (punto decimal y sin
  separadores de miles), vacíos como celda vacía, comillas al estilo RFC-4180 y BOM
  como el CSV de errores actual.
- "Archivo corregido (JSON)": `JSON.stringify(filas_corregidas, null, 2)`.
- "Informe de errores (CSV)" y "Informe de errores (JSON)": los botones actuales con
  las etiquetas del RF-14.
- Si `filas_corregidas` viene vacío (no hubo correcciones y el archivo NO es
  `.xlsx`), la corregida se genera del original en el navegador: `JSON.parse`
  para .json, parser CSV propio mínimo para .csv (necesario para CSV→JSON). Un
  `.xlsx` sin correcciones trae `filas_corregidas` relleno, así que su corregida
  sale de ahí en CSV/JSON (y de paso convierte Excel → CSV/JSON) y no se usa el
  parser propio. Si `descarga_corregida_disponible` es `false` (solo por el tope
  de 100.000 filas), los dos botones corregidos quedan deshabilitados con aviso
  en español.

## Funciones puras (firmas aproximadas)

```python
# app/services/normalizer.py
LIMITE_FILAS_CORREGIDAS = 100_000

def normalizar_filas(rows: list[dict], checks: list[FieldCheck]
                     ) -> tuple[list[dict], list[Correccion]]:
    """Copia de las filas con las normalizaciones automáticas (RF-1..RF-8) y su
    rastro. No modifica `rows`."""

def aplicar_ediciones(rows: list[dict], ediciones: list[dict], checks: list[FieldCheck]
                      ) -> tuple[list[dict], list[Correccion]]:
    """Aplica el lote manual sobre una copia, en orden (RF-17). Lanza ValueError
    con mensaje en español si la fila no existe o la columna no está en el
    esquema (RF-18)."""

def corregir_filas(rows: list[dict], checks: list[FieldCheck],
                   autocorreccion: bool = True,
                   ediciones: Optional[list[dict]] = None
                   ) -> tuple[list[dict], list[Correccion]]:
    """Orquesta: copia → automática (si activa) → manual → lista ordenada (RF-9)."""

def preparar_descarga_corregida(rows: list[dict], correcciones: list[Correccion],
                                es_xlsx: bool = False,
                                limite: int = LIMITE_FILAS_CORREGIDAS
                                ) -> tuple[list[dict], bool]:
    """(filas_corregidas, descarga_corregida_disponible): envía las filas si hay
    correcciones O si `es_xlsx` (aunque no las haya); si no, vienen vacías y el
    navegador genera la corregida del original. El tope de filas (RNF-7) las vacía
    SIEMPRE, sea cual sea el formato, y es el ÚNICO motivo del flag en `false`. El
    límite es parámetro para poder probarlo con un valor pequeño."""

def preparar_muestra(rows: list[dict], errores: list[RowError],
                     correcciones: list[Correccion]
                     ) -> tuple[list[dict], list[int]]:
    """(muestra, muestra_filas) de la vista previa (RF-11): TODAS las filas
    de interés —las de la unión errores ∪ correcciones en orden de fila—
    sin tope de filas (decisión «sin límite»; se elimina `limite_filas`).
    Sin filas de interés → fallback: primeras LIMITE_MUESTRA filas y
    [1..N]. El contador y el aviso por volumen NO se calculan aquí (los
    deriva el navegador del cruce completo). Importa LIMITE_MUESTRA de
    validator.py sin modificarlo."""

# internas (también puras y testeables)
def _deducir_convencion_fechas(valores: list) -> Optional[str]   # RF-6
def _normalizar_valor(valor, check, convencion) -> tuple[Any, Optional[str]]  # (valor, tipo)
def _distancia_edicion(a: str, b: str) -> int                    # Levenshtein propio, RF-7
```

`validator.py`, `parser.py` y la firma de `validate_rows` quedan intactos.

## Orden de implementación y por qué

De dentro hacia fuera: **modelos → normalizador puro → ediciones puras → endpoint →
UI por capas (interruptor → vista previa editable → sección de correcciones →
descargas) → verificación integral**.

- La lógica pura es la parte con más reglas y casos límite y la más barata de
  probar: se hacen primero con pytest, sin levantar servidor ni tocar la UI.
- Cada paso deja `pytest` en verde sin depender de la capa siguiente; los 36 tests
  actuales actúan de red de seguridad desde la primera tarea (por eso
  `validator.py` no se toca y la corrección vive en un módulo nuevo).
- El endpoint se hace cuando el servicio ya está probado: solo compone.
- La UI siempre se prueba contra un backend ya funcional; dentro de la UI se va del
  menos al más dependiente: el interruptor no toca resultados, la vista previa
  necesita el endpoint de ediciones, la sección pinta campos que ya viajan y las
  descargas consumen la respuesta completa.

## Decisiones técnicas (con la alternativa descartada)

1. **Módulo nuevo `services/normalizer.py`**: descartado meter la normalización en
   `validator.py` (mezclaría corregir y validar y obligaría a tocar la firma de
   `validate_rows`, poniendo en riesgo los 36 tests).
2. **`validate_rows` sin cambios; la composición vive en `corregir_filas` y el
   endpoint solo la llama**: descartado añadir parámetros `autocorreccion`/`ediciones`
   a `validate_rows` (rompe todos los llamadas existentes y la separación
   "endpoints solo enrutan" de la constitución).
3. **Funciones no mutantes (devuelven copia nueva)**: descartado corregir in place
   (el RF-1/RNF-2 exige trabajar sobre una copia y así se testea con un assert del
   estilo "las filas de entrada no cambian").
4. **`Correccion` como modelo Pydantic en `schemas/quality.py`**: descartado un
   dataclass en el servicio (habría que convertirlo en el endpoint y la respuesta
   ya es Pydantic).
5. **Convención de fechas deducida en un pre-paso por columna**: descartada una
   convención fija día/mes (incorrecta para archivos con mes/día) y pedirla al
   usuario (el RF-6 la deduce de los datos).
6. **Distancia de edición propia (~15 líneas de Levenshtein)**: descartado
   `difflib.SequenceMatcher` (su `ratio()` no es distancia de edición y no garantiza
   el umbral "≤ 1 exactamente" del RF-7) y `rapidfuzz` (librería nueva, prohibida
   por RNF-3 y fuera de alcance de la spec).
7. **`ediciones` como texto JSON en un campo del multipart**: descartado un endpoint
   aparte (RF-17 pide el lote en la MISMA petición de validación) y campos
   repetidos del formulario (`fila[]`, `columna[]`... difíciles de emparejar de
   forma fiable).
8. **`autocorreccion: bool = Form(False)`** (default `false` por decisión del
   usuario: campo ausente = sin autocorrección, RF-1; la UI envía `true` explícito):
   descartado query param (la spec lo
   define como campo del formulario) y string libre (Pydantic parsea `true`/`false`).
9. **Orden de `correcciones` con clave `(fila, índice de columna en el archivo,
   es_manual, índice en el lote)`**: descartado confiar en el orden de recolección
   (se rompe con ediciones duplicadas y con columnas fuera de orden en el lote).
10. **Tope de filas en constante del servicio con `limite` como parámetro**:
    descartado un número fijo dentro del endpoint (habría que generar 100.001 filas
    para probarlo; con `monkeypatch`/argumento se prueba con 10).
11. **Estado de ediciones pendientes en `app.js` (Map)**: descartado guardarlo
    dentro de `RowPreview` (lo necesita también el botón "Validar", el aviso al
    cambiar entradas y la construcción del `FormData`).
12. **Descargas desde el `File` en memoria y desde `filas_corregidas`**:
    descartado un endpoint de descarga (RNF-3 lo prohíbe) y reconstruir desde
    `muestra` (solo trae 50 filas).
13. **Sin correcciones en un CSV/JSON, la versión corregida se genera en el
    navegador desde el original** (parser CSV propio mínimo para CSV→JSON);
    **excepción decidida por el usuario: para `.xlsx` sí se envía
    `filas_corregidas` aunque no haya correcciones**, porque el navegador no
    puede regenerar un .xlsx sin librerías nuevas (y de paso convierte
    Excel → CSV/JSON). Descartado enviar `filas_corregidas` siempre para todos
    los formatos (encarecería todas las respuestas sin necesidad).
14. **Las descargas corresponden a la ÚLTIMA validación** (el `File` se guarda al
    enviar, no al hacer clic): descartado leer el input en el momento de descargar
    (mezclaría un archivo sin validar con la respuesta anterior); el bloque muestra
    el nombre del archivo validado.
15. **Sección de correcciones renderizada en `app.js`**: descartado un componente
    nuevo en `components/` (AGENTS.md pide preguntar antes de crear archivos y ya
    existe el precedente de `renderErrores` en `app.js`).
16. **Ámbar para cualquier celda con entrada en `correcciones` (automática o
    manual), con el rojo por encima**: descartado ámbar solo para automáticas
    (HU-6/HU-7 piden que las manuales queden auditadas igual).
17. **`muestra` cambia de semántica (filas de interés) + campo paralelo
    `muestra_filas`**: descartado un campo nuevo `filas_interes` manteniendo
    `muestra` intacto (duplicaría hasta 50 filas en la respuesta y dejaría dos
    fuentes para la misma tabla) y descartado meter el número de fila dentro de
    cada objeto de `muestra` (rompería la forma {columna: valor} y la paridad con
    `filas_corregidas` que pide el contrato). Fallback: sin filas de interés
    `muestra` es el de hoy, por eso los 171 tests siguen en verde sin tocarse.
18. **El filtrado se compone en el endpoint (`upload.py`) con una función pura
    `preparar_muestra` en `normalizer.py`**: descartado el cómputo inline en el
    endpoint (la constitución dice que los endpoints solo enrutan y no sería
    unit-testeable) y descartado meterlo en `validator.py` (regla del proyecto:
    `_muestra()`, `LIMITE_MUESTRA` y `validate_rows` quedan intactos).
19. **El total de filas de interés (Y de la nota) lo deriva el navegador de
    `errores` ∪ `correcciones`**: descartado un campo nuevo `total_filas_interes`
    (ambas listas ya llegan completas, así que sería dato duplicado y un campo
    más que mantener en el contrato).
20. **Presupuesto de INCIDENCIAS parametrizado en `preparar_muestra`**
    (SUPERSEDA por la decisión 23; histórico de T13-T14)
    (`limite_incidencias`, defecto `LIMITE_MUESTRA`): descartado mantener el tope
    de filas (el usuario pidió contar errores, no filas: una fila con 3 errores
    consume 3) y descartado una constante fija (el usuario quiere elegirlo en la
    interfaz). La unidad es la celda de la unión `errores` ∪ `correcciones`:
    contar entradas duplicaría la celda con error Y corrección.
21. **Recorte del `limite_muestra` en el endpoint, sin 400**: `upload.py` lo
    parsea como texto y recorta (no numérico → 50, `< 1` → 1, `> 1000` → 1000).
    Descartado un 400 en español (rompería peticiones de clientes antiguos y no
    aporta: el campo solo acota la vista) y descartado el rango abierto (una
    petición con 10 millones podría pedir una tabla enorme).
22. **La revalidación envía el valor del campo en ese momento**: descartado
    congelar el valor de la primera validación (si el analista ajusta el límite
    y aplica cambios, espera verlo aplicado) y descartado un valor por archivo
    (el campo vive en el formulario, no en el estado de resultados).
23. **El tope vuelve a contar FILAS de interés (sustituye a la decisión 20)**:
    (SUPERSEDA por la decisión 24; histórico de T15)
    descartado mantener el presupuesto de incidencias (el usuario confirmó con
    sus palabras que el campo es «un máximo de filas editable por el usuario,
    pero que la vista previa siga siendo de los errores») y descartado aplicar
    el límite a las filas del archivo (convertiría la vista previa en vista
    general; solo se acota cuántas filas de interés se ven). El recuento de
    incidencias queda como dato informativo en la nota del navegador (Z), sin
    campo nuevo en la respuesta (decisión 19) y sin cálculo en el backend.
24. **Sin límite: todas las filas de interés + contador (sustituye a las
    decisiones 20 y 23)**: descartado mantener cualquier tope editable de la
    vista previa (decisión del usuario: «sin límite: mostrar todas +
    contador») y descartado un tope fijo en filas (también quiere verlas
    todas). El recuento de filas de interés (X) e incidencias (Y) lo deriva
    el navegador de `errores` ∪ `correcciones` (decisión 19), el campo
    `limite_muestra` se elimina de la petición y su llegada se ignora sin 400
    (RNF-5) y la protección de rendimiento es un aviso NO bloqueante desde
    2.000 filas de interés (umbral por el volumen de celdas del DOM, ~20.000
    con 10 columnas), no una negativa a mostrar los datos.

## Riesgos y mitigación

1. **Compatibilidad de la API (RNF-5)**: campos nuevos opcionales con valores por
   defecto + test de petición sin los campos nuevos que compara con lo actual.
2. **Regresión de los 36 tests**: `validator.py` y `parser.py` intactos, lógica en
   módulo nuevo y `pytest` completo tras cada tarea.
3. **Tamaño de respuesta (RNF-7)**: `filas_corregidas` con correcciones o con
   `.xlsx` (aunque no haya correcciones), y con tope de 100.000 filas que la
   vacía sea cual sea el formato; límite de 10 MB intacto. `correcciones` no se
   acota porque la spec lo define así (el tope solo cubre `filas_corregidas`; hoy
   `errores` ya es ilimitado) y la UI solo pinta 50 entradas.
4. **Rendimiento de la normalización (RNF-4)**: recorrido lineal por fila/columna
   más el pre-paso de convención por columna de fecha (también lineal); sin regex
   catastróficas; Levenshtein solo contra el `allowed_values` de la columna.
5. **Rendimiento del DOM**: vista previa limitada a 50 filas, sección de
   correcciones con 50 entradas como máximo; al editar solo se toca la celda y el
   botón (sin repintar la tabla entera en cada tecla).
6. **Móvil (RF-15)**: tablas con scroll horizontal (`overflow-x-auto`), botones en
   `flex-wrap`, sin tooltip en táctil; comprobación a 375px incluida la edición y la
   sección de correcciones.
7. **Descarga corregida con formato distinto al original**: parser CSV propio
   mínimo para CSV→JSON; el caso `.xlsx` sin correcciones NO se genera en el
   navegador: se resuelve enviando `filas_corregidas` desde el backend (decisión
   del usuario), que además convierte Excel → CSV/JSON.
8. **Lote de ediciones inválido**: validación estricta en el servicio y 400 en
   español antes de validar (RF-18); el frontend siempre envía JSON de
   `JSON.stringify`.
9. **Histórico de cargas**: el modelo `Upload` no cambia; cada petición (incluidas
   las revalidaciones) inserta una fila nueva solo con recuentos, como ya ocurre
   (RF-17, RNF-2).
10. **Compatibilidad de `muestra` (única excepción a RNF-5)**: el cambio de
    semántica es consciente y documentado; frontend y backend se despliegan en la
    MISMA entrega (un cliente que asumiera "posición + 1" solo acertaría en el
    fallback) y `muestra_filas` viaja con valor por defecto `[]`.
11. **Tests previos que asumen el orden/posición de `muestra`**
    (`test_preview_and_excel.py`, `test_upload_endpoint.py`): el fallback conserva
    el comportamiento actual cuando no hay filas de interés y los casos con filas
    de interés empiezan en la fila 1, así que siguen en verde sin modificarse; se
    verifica con el `pytest` completo tras T11 antes de tocar el frontend.
12. **No romper T7-T9 (edición, sección de correcciones, descargas)**: la edición
    pasa a usar el número de fila real (`fila: <n>`) en lugar de `posición + 1`,
    pero el Map de pendientes, `renderCorrecciones`, `ExportButtons` y el resto de
    la respuesta no cambian; las descargas siguen apoyándose en `filas_corregidas`
    y en el `File`, nunca en `muestra` (decisión 12).
13. **Compatibilidad del campo nuevo (RNF-5)**: `limite_muestra` es opcional con
    defecto 50, así que una petición sin él muestra lo mismo que hoy (presupuesto
    de 50 incidencias); el endpoint tolera el campo ausente, vacío o basura
    (recorte, nunca 400) y los 179 tests previos siguen en verde sin tocarse.
14. **Fallback y edición intactos**: el presupuesto no se aplica en el caso de
    reserva (sin incidencias → primeras 50 filas, nada editable) y la edición
    sigue enviando `fila: <n>` real desde `muestra_filas`; el riesgo es que el
    nuevo bucle de presupuesto cambie el orden o la paridad de `muestra_filas`,
    cubierto con los tests (a)-(d) existentes re-ejecutados en verde.
15. **La revalidación arrastra el límite actual**: "Aplicar cambios y revalidar"
    envía el valor del campo en ese momento (decisión 22); el navegador debe
    leer el input al montar el `FormData` (no cachearlo al enviar la primera
    petición) y comprobarlo en la verificación (cambiar el límite y revalidar).
16. **La vista previa no debe volverse vista general**: el campo solo acota
    cuántas FILAS DE INTERÉS se muestran (sigue saliendo solo error/corrección
    en orden de fila, nunca filas válidas); se verifica en navegador con un
    archivo que tenga filas válidas intercaladas entre las de interés.
17. **Compatibilidad del campo (RNF-5)**: `limite_muestra` conserva nombre,
    defecto 50 y recorte, así que una petición sin él muestra hasta 50 filas de
    interés (con el defecto, el máximo visible sigue siendo el de hoy) y los 191
    tests previos siguen en verde sin tocarse.
18. **La revalidación sigue arrastrando el límite actual** (re-confirmado en
    esta revisión): "Aplicar cambios y revalidar" debe leer el input al montar
    el `FormData`; comprobado en navegador cambiando el límite y revalidando.
19. **No romper T7-T14**: el cambio toca el interior de `preparar_muestra`, la
    etiqueta/ayuda del campo y el texto de la nota; el Map de pendientes, la
    sección de correcciones, las descargas, `muestra_filas` y la edición con
    `fila: <n>` real no cambian; los tests de vista previa (a)-(d) y (l)
    existentes actúan de red de seguridad (191 en verde).
20. **Rendimiento del DOM con miles de filas**: la vista previa ya no se
    acota, así que miles de filas con errores pueden relentizar el pintado;
    mitigación elegida por el usuario: aviso NO bloqueante desde 2.000 filas
    de interés (el renderizado nunca se suspende) y una edición que sigue
    tocando solo la celda y el botón (riesgo 5).
21. **Tamaño de respuesta (RNF-7)**: `muestra` ya no está acotada por filas;
    la cota práctica es el límite de subida de 10 MB (ningún archivo que entre
    por upload puede superarlo) y el tope de 100.000 filas sigue protegiendo
    solo `filas_corregidas`.
22. **No romper T7-T15**: el cambio toca el interior de `preparar_muestra`,
    la lectura de `limite_muestra` en `upload.py`, el campo de
    `FileUploader.js` y el texto de la nota; el Map de pendientes, la sección
    de correcciones, las descargas, `muestra_filas` y la edición con
    `fila: <n>` real no cambian; los tests de vista previa (a)-(d) existentes
    actúan de red de seguridad (193 en verde).
23. **Compatibilidad del campo eliminado (RNF-5)**: `limite_muestra` se ignora
    si llega (nunca un 400 por él), así que un cliente antiguo solo observa
    que `muestra` trae más filas de interés (cambio de semántica ya
    documentado en la nota de compatibilidad de la spec).

## Estrategia de verificación

### Con `pytest` (desde `data-processor-app/backend/`)
- **Unitarios puros del normalizador** (`tests/test_normalizer.py`): un bloque por
  tipo de normalización (espacios/invisibles, correo, marcadores de vacío, números,
  fechas, enums) con TODOS los casos límite de la spec; una-entrada-por-celda con el
  `tipo` del último paso; orden y serialización de `correcciones` (texto vs número);
  no mutación de la entrada; columnas fuera del esquema intactas; RF-10 (fila
  corregida conforme cuenta como válida, corregida pero aún fuera de regla sigue
  inválida con su corrección registrada); `preparar_descarga_corregida` (con
  correcciones, sin correcciones con y sin `es_xlsx`, y tope con `limite` pequeño).
  Cubre RF-1 a RF-10, RNF-1, RNF-4.
- **Unitarios de ediciones** (`tests/test_ediciones.py`): aplicación sobre valores ya
  normalizados, duplicados en orden, fila/columna inválidas → `ValueError` en
  español, vaciar un campo requerido, lote vacío, autocorrección apagada con
  ediciones, `despues` de `manual` como TEXTO y su celda en `filas_corregidas` con
  la representación de `muestra` (número si la celda es numérica, texto para las
  fechas). Cubre RF-17, RF-18, RF-9 (tipo `manual`).
- **Integración de endpoint** (`tests/test_upload_endpoint.py` ampliado): petición
  sin campos nuevos idéntica a hoy (compatibilidad), `autocorreccion` por defecto y
  apagada, `ediciones` por multipart, 400 en español con JSON malformado o
  fila/columna inválidas, presencia/ausencia de `filas_corregidas` (con
  correcciones → presente; sin correcciones en CSV/JSON → vacío; sin correcciones en
  `.xlsx` → presente), tope de 100.000 filas con `limite` pequeño (monkeypatch) →
  vacío y flag en `false` (único motivo), registro de carga seguido. Cubre RF-1,
  RF-12 (servidor), RF-14, RNF-5, RNF-7.
- **Vista previa de errores** (`tests/test_normalizer.py` con `preparar_muestra` +
  `tests/test_upload_endpoint.py` con la respuesta completa): (a) filas de interés
  (fila con error residual o alguna corrección) en orden ascendente y SIN
  tope (todas; p. ej. 1000 filas de interés → 1000 entradas en `muestra`);
  (b) `muestra_filas` paralelo a `muestra` (mismo orden y longitud, enteros 1-based
  reales, p. ej. `[80, 900]`); (c) sin filas de interés → fallback: `muestra` =
  primeras 50 y `muestra_filas` = `[1, 2, …, N]`; (d) con errores solo en las filas
  80 y 900, la respuesta trae esas dos filas con sus números y una edición
  `{"fila": 900, ...}` se aplica sin 400 (RF-18). Cubre RF-11 (backend), RNF-5
  (excepción `muestra`).
- **Sin límite: todas las filas de interés** (mismos dos archivos de tests,
  adaptados; los tests del tope por filas de T15 se reescriben a la nueva
  semántica): (e) 1000 filas con un error cada una → `muestra` trae las 1000
  (sin tope); (f) una fila con 100 incidencias → se muestra ENTERA como 1 fila
  de interés; (g) petición que aún envía `limite_muestra` (vacío, 0, letras o
  un entero) → NO hay 400 y la respuesta trae todas las filas de interés (el
  campo se ignora); (h) sin filas de interés → fallback de las primeras 50
  filas con `muestra_filas = [1, 2, …, N]` (intacto); (i) `muestra_filas` sigue
  paralelo a `muestra` sin tope (enteros 1-based reales). Cubre RF-11, RF-16
  (servidor), RNF-5 (campo eliminado ignorado).
- **Regresión**: los 36 tests actuales sin modificar (RNF-6).

### En el navegador (Chrome DevTools, API real con `--reload`; 1280px y 375px)
- Interruptor on/off con el mismo archivo: cambian `correcciones` y el resumen
  (RF-12, HU-1/HU-5).
- Archivo de ejemplo nuevo (`ejemplo_autocorreccion.csv` con
  `ejemplo_autocorreccion_esquema.json`), que trae errores de formato que se
  corrigen y otros que no: resumen con contadores, sección "Correcciones
  aplicadas" con nota "mostrando X de Y" y detalle antes → después (RF-13, HU-2).
- Vista previa: celdas corregidas en ámbar con tooltip en escritorio, errores en
  rojo (gana), edición manual de una celda con error y de una corregida, marcado de
  pendiente, "Aplicar cambios y revalidar" revalida todo y la edición aparece como
  `manual` (RF-11, RF-16, RF-17, HU-3/HU-6/HU-7).
- Vista previa de errores (casos de la spec, con CSV temporales generados con
  Python FUERA del repositorio durante la verificación, sin crear archivos en el
  proyecto): (1) errores solo en las filas 80 y 900 → la tabla empieza en la 80,
  muestra ambas con su "#" real, no sale la nota (2 de 2) y la edición de la fila
  900 se aplica viajando `fila: 900`; (2) archivo con problemas solo corregibles →
  todo queda ámbar sin rojo y el título sigue siendo "Vista Previa de Errores",
  editando una celda corregida funciona; (3) archivo sin errores ni correcciones →
  título "Vista previa de filas", la nota de hoy y ninguna celda abre input;
  (4) más de 50 filas de interés → se ven TODAS con el contador "X filas con
  errores o correcciones · Y incidencias"; (5) un CSV temporal de más de 2.000
  filas de interés → el aviso "Esta vista previa tiene N filas con errores o
  correcciones; puede tardar en mostrarse." queda visible sobre la tabla y el
  renderizado no se bloquea (RF-11, RF-16, HU-8).
- Campo eliminado y contador: el formulario YA NO tiene el campo «Máximo de
  filas en la vista previa» (solo el interruptor y lo de siempre) y la
  revalidación ya no envía `limite_muestra` (comprobable en la pestaña de
  red); el contador se ve SIEMPRE sobre la tabla cuando hay filas de interés
  (a 1280px y 375px) y NO aparece en el fallback (archivo limpio, título
  "Vista previa de filas") (RF-11, RF-15, RF-16).
- Avisos: "Validar" con pendientes las descarta con aviso; cambiar archivo o
  esquema con pendientes las limpia con aviso (RF-16).
- Descargas: original byte idéntica, corregida CSV (cabecera = `columnas`, números
  con punto y sin miles, todas las filas) y JSON; en un CSV/JSON sin correcciones
  la corregida coincide con la normal; subiendo un `.xlsx` sin correcciones (p. ej.
  `ejemplo_datos.xlsx`) `filas_corregidas` viene relleno y la corregida se descarga
  en CSV/JSON (conversión Excel → CSV/JSON); con el flag en `false` (tope de filas)
  los botones corregidos deshabilitados con aviso (RF-14).
- Responsive: todo lo anterior comprobado a 1280px y a 375px (RF-15).
