# Tareas — Spec 003: Auto-corrección y corrección manual

Verificación de backend tras cada tarea: `python -m pytest` desde
`data-processor-app/backend/` (los 189 tests actuales deben seguir en verde).
Cifra vigente y final: **189 tests** (medida por QA); las cifras 191 y 193 que
aparecen en el «Hecho cuando» de T15 y T16 son expectativas históricas de
planificación de esas tareas, no la cifra final.

Protocolo del usuario: **UNA tarea por vez** — se ejecuta una sola tarea, se para
y se pide confirmación del usuario antes de pasar a la siguiente.

Estado: **T1-T17 COMPLETADAS — SPEC 003 COMPLETA** (auto-corrección, corrección
manual y vista previa de errores; T16: backend «sin límite» — `preparar_muestra`
sin tope y `limite_muestra` eliminado/ignorado — y T17: frontend sin campo de
límite, contador «X filas con errores o correcciones · Y incidencias» siempre
visible y aviso ≥2.000 filas — **189 tests en verde**, ver `MEMORY.md`). Las
revisiones con límite de T13-T15 quedan SUPERADAS por el cambio aprobado «sin
límite: todas las filas de interés + contador y aviso por volumen» (decisión 24).
Queda la revisión final del usuario de la spec.

- [x] **T1. Modelos y limpieza básica.** RF-2, RF-3, RF-4, RF-8, RF-9 (base), RNF-1
  - Alcance: `backend/app/schemas/quality.py` (nuevo modelo `Correccion` con
    `fila`, `columna`, `antes`, `despues`, `tipo`; campos nuevos de `ValidationResult`
    `correcciones`, `filas_corregidas`, `descarga_corregida_disponible` con sus
    valores por defecto). Nuevo `backend/app/services/normalizer.py` con
    `normalizar_filas` (pipeline de una entrada por celda: limpieza → vacío →
    minúsculas) y los pasos de espacios/invisibles, correo en minúsculas y
    marcadores de vacío. Nuevo `backend/tests/test_normalizer.py`.
  - Hecho cuando: `pytest` pasa con los 36 actuales + los nuevos, que cubren:
    espacios iniciales/finales/internos, espacio duro U+00A0 y caracteres de ancho
    cero, celda solo de espacios/invisibles SIN registro de corrección, correo a
    minúsculas, `N/A`, `#N/A`, `N.A.`, `null`, `-`, `--`, `sin dato` en columna no
    requerida → vacío con tipo `vacio` y en columna requerida sin transformar,
    columna fuera del esquema intacta, filas de entrada no modificadas (copia) y
    una sola entrada por celda con `antes` = valor crudo y `tipo` del último paso
    que modificó.
- [x] **T2. Números y fechas.** RF-5, RF-6
  - Alcance: `backend/app/services/normalizer.py` (pasos `numero` y `fecha`,
    `_deducir_convencion_fechas` con pre-paso por columna); `tests/test_normalizer.py`
    ampliado con los casos límite de la spec.
  - Hecho cuando: `pytest` pasa cubriendo: `1.234,56` y `1,234.56` → `1234.56`,
    `1.234.567` → `1234567`, `1.23`/`1,2345`/`12,5` como decimales, `1,234` y
    `12,345` ambiguos sin corregir, `1.234.56` no inequívoco sin corregir, `hola`
    sin tocar, `1.234` no reinterpreto; fechas: convención día/mes
    (`25/12/2026` + `01/10/2026` → `2026-10-01`), convención mes/día
    (`05/13/2026` + `01/10/2026` → `2026-01-10`), columna sin convención sin
    corregir ambiguos, convenciones en conflicto → sin convención, lectura única
    contraria sin corregir, `31/02/2026`, año de 2 dígitos y año al principio sin
    tocar; serialización: `despues` numérico (entero sin decimales si no hay
    parte decimal) para `numero` y texto en el formato de la regla para `fecha`.
- [x] **T3. Enums, rastro ordenado y resumen corregido.** RF-7, RF-9 (completo), RF-10
  - Alcance: `backend/app/services/normalizer.py` (paso `enum` con distancia de
    edición propia, función orquestadora `corregir_filas` con el orden de la lista
    de `correcciones`); `tests/test_normalizer.py` ampliado.
  - Hecho cuando: `pytest` pasa cubriendo: `aprobado ` → `APROBADO` (coincidencia
    insensible a mayúsculas/espacios en su forma exacta), `APROBAD0` → `APROBADO`
    (distancia ≤ 1), `CA` con permitidos `CAT` y `CAR` sin corregir,
    `  APROBAD0  ` → UNA sola entrada tipo `enum`; orden de `correcciones` (fila
    ascendente, orden de columnas del archivo, automática antes que manual) y sus
    casos de serialización del contrato; RF-10: fila corregida y conforme cuenta
    como válida, fila corregida pero fuera de rango sigue inválida con su
    corrección registrada; `corregir_filas(autocorreccion=False)` devuelve filas
    originales y `correcciones=[]`.
- [x] **T4. Ediciones manuales.** RF-17 (backend), RF-18, RF-9 (tipo `manual`)
  - Alcance: `backend/app/services/normalizer.py` con `aplicar_ediciones`; nuevo
    `backend/tests/test_ediciones.py`.
  - Hecho cuando: `pytest` pasa cubriendo: edición aplicada DESPUÉS de la
    normalización (dos entradas en `correcciones`, la manual con `antes` = valor ya
    corregido), misma celda dos veces en el lote → dos entradas aplicadas en orden,
    fila fuera de rango → `ValueError` con mensaje en español, columna fuera del
    esquema → `ValueError` con mensaje en español, vaciar un campo requerido →
    `validate_rows` devuelve "Campo requerido", ediciones con autocorrección
    apagada → solo entradas `manual`, lote vacío → sin cambios, `despues` de
    `manual` serializado como TEXTO (el valor llega como texto) y la celda editada
    en `filas_corregidas` con la representación de `muestra` (número si la celda es
    numérica, texto para las fechas).
- [x] **T5. Endpoint con autocorrección y ediciones.** RF-1, RF-12 (servidor), RF-14 (campos de respuesta), RF-17, RF-18, RNF-5, RNF-7
  - Alcance: `backend/app/api/v1/endpoints/upload.py` (campos de formulario
    `autocorreccion` y `ediciones`, validación del JSON del lote → 400 en español
    sin validar, llamada a `corregir_filas`, relleno de `correcciones`,
    `filas_corregidas` —si hay correcciones o el archivo es `.xlsx`— y
    `descarga_corregida_disponible` con el tope de 100.000 filas);
    `backend/tests/test_upload_endpoint.py` ampliado. `validator.py` y
    `parser.py` sin cambios.
  - Hecho cuando: `pytest` pasa (36 actuales + nuevos) cubriendo: petición sin los
    campos nuevos idéntica a la actual (compatibilidad), campo `autocorreccion`
    ausente → sin autocorrección (RF-1), `autocorreccion=false` → mismos contadores y
    errores que hoy con `correcciones=[]`, `ediciones` por multipart aplicadas, JSON de ediciones
    malformado → 400 en español, fila/columna inválidas → 400 en español sin
    validar, `filas_corregidas` vacío cuando no hay correcciones en un CSV/JSON y
    relleno aunque no las haya si el archivo es `.xlsx`, tope de filas con
    `limite` pequeño (monkeypatch) → `filas_corregidas=[]` y
    `descarga_corregida_disponible=false` (único motivo del flag en `false`), y el
    registro de carga sigue persistiéndose en SQLite.
- [x] **T6. Archivo de ejemplo de autocorrección e interruptor.** RF-12, RF-15
  (parte); ejemplifica RF-3 a RF-8
  - Alcance: **Nuevos** `backend/ejemplo_autocorreccion.csv` y
    `backend/ejemplo_autocorreccion_esquema.json` (archivos de ejemplo aprobados por
    el usuario; nombres al estilo de los ya existentes en `backend/`:
    `ejemplo_datos.csv` con `ejemplo_esquema.json`), con errores de formato que SÍ
    se corrigen —espacios sobrantes e internos, espacio duro U+00A0, `1.234,56`,
    enum en minúsculas `aprobado `, `n/a` en una columna no requerida y fechas con
    `25/12/2026` junto a `01/10/2026` (la primera aporta la convención día/mes y la
    segunda se corrige con ella)— y errores que NO se corrigen —`1,234` ambiguo,
    correo mal formado de verdad, texto donde debería haber número y enum a
    distancia > 1—, con los valores que llevan coma entre comillas para que el CSV
    no se parta; `frontend/components/FileUploader.js` (interruptor
    "Autocorrección" activado por defecto, con etiqueta y ayuda en español, y paso
    del estado al callback de validación); `frontend/app.js` (añade
    `autocorreccion=true|false` al `FormData` de todas las validaciones).
  - Hecho cuando: el CSV y su esquema existen y, subidos juntos con la
    autocorrección activada, producen correcciones de todos los tipos corregibles
    listados arriba y dejan sin corregir (visibles en rojo) los no corregibles; en
    el navegador contra la API real, con el interruptor apagado la respuesta trae
    `correcciones=[]` para ese archivo y con él encendido trae correcciones; el
    interruptor se ve bien y es cómodo de usar a 1280px y 375px; `pytest` sigue en
    verde.
- [x] **T7. Vista previa editable y aplicar cambios.** RF-11, RF-16, RF-17 (navegador), RF-15
  - Alcance: `frontend/components/RowPreview.js` (celdas corregidas en ámbar con
    tooltip de escritorio, rojo por encima, celdas editables solo con error o
    corregidas en las 50 primeras filas, botón "Aplicar cambios y revalidar");
    `frontend/app.js` (Map de ediciones pendientes, envío del lote en `ediciones`,
    limpieza al recibir respuesta, avisos en español al descartar); `frontend/components/FileUploader.js`
    (callback de cambio de archivo/esquema que limpia pendientes con aviso);
    `frontend/index.html` (contenedor `#aviso`).
  - Hecho cuando: en el navegador a 1280px y 375px: la celda corregida se ve en
    ámbar y al pasar el cursor muestra el valor "antes", la celda con error se ve en
    rojo (el error manda sobre el ámbar), solo las celdas con error o corregidas de
    las 50 primeras filas abren un input con el valor actual (vaciarlo deja la celda
    vacía) y las válidas no son editables, la celda editada se marca como pendiente
    y el botón "Aplicar cambios y revalidar" se habilita, al aplicar se revalida
    todo y la edición aparece como `manual` en `correcciones`, pulsar "Validar" con
    pendientes valida sin ellas mostrando aviso en español, y cambiar el archivo o
    el esquema con pendientes las limpia mostrando aviso.
- [x] **T8. Sección "Correcciones aplicadas" y contadores.** RF-13, RF-15
  - Alcance: `frontend/app.js` (función `renderCorrecciones`, como
    `renderErrores`); `frontend/components/ValidationSummary.js` (contadores);
    `frontend/index.html` (contenedor `#correcciones`).
  - Hecho cuando: en el navegador: el resumen muestra "N celdas autocorregidas" y,
    si las hay, "M ediciones manuales" (con N y M según el cóputo del contrato); la
    sección lista fila, columna, antes → después y tipo distinguiendo automáticas
    de manuales, con las PRIMERAS 50 entradas y la nota "mostrando X de Y"; sin
    correcciones no aparece ni la sección ni los contadores; la tabla es legible y
    usable a 1280px y 375px (scroll horizontal).
- [x] **T9. Bloque "Descargas".** RF-14, RF-15, RNF-3
  - Alcance: `frontend/components/ExportButtons.js` (bloque "Descargas" con los 5
    botones y sus etiquetas, CSV/JSON corregidos desde `filas_corregidas` respetando
    `columnas`, original desde el `File` de la última validación, generación desde
    el original cuando no hay `filas_corregidas` —solo en CSV/JSON sin correcciones—
    y uso de `filas_corregidas` para un `.xlsx` sin correcciones, estado
    deshabilitado con aviso —solo por el tope de filas—); `frontend/app.js` (pasa
    el archivo validado).
  - Hecho cuando: en el navegador: los 5 botones con las etiquetas exactas del
    RF-14; "Archivo original" descarga bytes idénticos a los subidos; "Archivo
    corregido (CSV)" tiene cabecera igual a `columnas`, TODAS las filas, números con
    punto decimal y sin separadores de miles; "Archivo corregido (JSON)" contiene
    todas las filas; en un CSV/JSON sin correcciones la corregida coincide con la
    normal; subiendo un `.xlsx` sin correcciones (p. ej. `ejemplo_datos.xlsx`)
    ambos botones corregidos se descargan desde `filas_corregidas` en CSV/JSON
    (conversión Excel → CSV/JSON); con `descarga_corregida_disponible=false`
    (comprobable forzando el flag en la respuesta o subiendo más de 100.000 filas)
    los dos botones corregidos aparecen deshabilitados con aviso en español (ese es
    el ÚNICO motivo por el que se deshabilitan); `pytest` sigue en verde.
- [x] **T10. Verificación integral.** RNF-6, criterios de finalización
  - Alcance: sin cambios de código salvo los arreglos menores que descubra la
    verificación; actualización de `MEMORY.md`.
  - Hecho cuando: `python -m pytest` completo en verde (36 actuales + los nuevos) y
    recorrido en navegador contra la API real a 1280px y 375px con
    `ejemplo_autocorreccion.csv` y su esquema: se cumplen los 5 criterios de
    finalización de la spec (resumen + sección de correcciones auditable con nota
    "mostrando X de Y"; vista previa con ámbar/rojo y edición manual revalidada
    como corrección manual; descargas normal y corregida (CSV y JSON) etiquetadas,
    incluida la de un `.xlsx` sin correcciones, que se sirve desde
    `filas_corregidas`; con el interruptor apagado no se autocorrige pero las
    ediciones manuales siguen funcionando; todo en español y responsive) y
    `MEMORY.md` queda actualizado (estado, decisiones y errores a evitar).
- [x] **T11. Vista previa de errores: backend `muestra`/`muestra_filas`.** RF-11
  (backend), RNF-5 (excepción `muestra`), RNF-6
  - Alcance: `backend/app/schemas/quality.py` (campo `muestra_filas: list[int]`
    con valor por defecto vacío); `backend/app/services/normalizer.py`
    (`preparar_muestra`, pura, con `LIMITE_MUESTRA` importado de `validator.py`
    sin modificarlo); `backend/app/api/v1/endpoints/upload.py` (tras
    `validate_rows`, pisa `result.muestra` y rellena `result.muestra_filas`
    llamando a `preparar_muestra(filas, result.errores, correcciones)`);
    `backend/tests/test_normalizer.py` y `backend/tests/test_upload_endpoint.py`
    ampliados. `validator.py` (`_muestra()`, `LIMITE_MUESTRA`) y `parser.py`
    INTACTOS. Sin archivos nuevos.
  - Hecho cuando: `python -m pytest` pasa con los 171 actuales sin tocar más los
    nuevos, que cubren: (a) filas de interés (fila con error residual o alguna
    corrección) en orden ascendente y con tope 50; (b) `muestra_filas` paralelo a
    `muestra` (mismo orden y longitud, enteros 1-based reales, p. ej.
    `[80, 900]`); (c) sin filas de interés → fallback: `muestra` = primeras 50 y
    `muestra_filas` = `[1, 2, …, N]`; (d) con errores solo en las filas 80 y 900,
    la respuesta trae esas dos filas con sus números y una edición
    `{"fila": 900, ...}` se aplica sin 400 (RF-18); (e) los tests previos de
    `muestra` (`test_preview_and_excel.py`, `test_upload_endpoint.py`) siguen en
    verde sin modificarse. `pytest` completo en verde antes de pasar a T12 (y
    confirmación del usuario antes de continuar).
- [x] **T12. Vista previa de errores: frontend y verificación en navegador.**
  RF-11, RF-15, RF-16 (navegador), HU-8
  - Alcance: `frontend/components/RowPreview.js` (número de fila desde
    `muestra_filas[i]` en lugar de `i + 1` para la columna "#", las claves
    `fila:columna` del rojo/ámbar y el `fila: <n>` de las ediciones; títulos
    "Vista previa de errores" / "Vista previa de filas"; nota "Mostrando X de Y
    filas con errores o correcciones." con la Y derivada de la unión `errores` ∪
    `correcciones`, solo si X < Y; en fallback ninguna celda editable);
    `frontend/app.js` solo si hace falta para interpretar los campos (sin cambios
    en la sección de correcciones ni en las descargas). Sin archivos nuevos; los
    CSV de prueba de la verificación se generan temporales fuera del repo.
  - Hecho cuando: en el navegador contra la API real a 1280px y 375px: (1) con un
    CSV temporal de 900 filas con errores solo en las filas 80 y 900, la vista
    previa empieza en la 80, muestra ambas con su "#" real, no aparece la nota
    (2 de 2) y la edición de la fila 900 se aplica viajando `fila: 900`; (2) con
    un CSV cuyos problemas son solo corregibles (todo ámbar, sin rojo) el título
    es "Vista previa de errores" y editar una celda corregida funciona; (3) con un
    CSV limpio el título es "Vista previa de filas", sale la nota de hoy y ninguna
    celda abre input; (4) con más de 50 filas de interés salen las 50 primeras de
    interés con la nota "Mostrando 50 de N filas con errores o correcciones.";
    `python -m pytest` sigue en verde; `MEMORY.md` queda actualizado (estado,
    decisiones y errores a evitar).
- [x] **T13. Límite de incidencias: backend `preparar_muestra` + `limite_muestra`.**
  RF-11 (presupuesto y campo), RNF-5 (campo opcional con defecto 50), RF-16
  (servidor), RNF-6
  - Alcance: `backend/app/services/normalizer.py` (`preparar_muestra` pasa de
    tope de filas a presupuesto de INCIDENCIAS: una por celda de la unión
    `errores` ∪ `correcciones` —una celda con error Y corrección cuenta 1—, fila
    que no cabe entera se incluye COMPLETA si cabe alguna de sus incidencias,
    nunca se parte; parámetro `limite_incidencias` ya recortado); 
    `backend/app/api/v1/endpoints/upload.py` (lee `limite_muestra` del multipart
    como texto y lo recorta: no numérico → 50, `< 1` → 1, `> 1000` → 1000, nunca
    400; lo pasa a `preparar_muestra`); `backend/tests/test_normalizer.py` y
    `backend/tests/test_upload_endpoint.py` ampliados. `validator.py`
    (`_muestra()`, `LIMITE_MUESTRA`, solo para el fallback) y `parser.py`
    INTACTOS. Sin archivos nuevos.
  - Hecho cuando: `python -m pytest` pasa con los 179 actuales sin tocar más los
    nuevos, que cubren: (e) celda con error Y corrección → 1 incidencia; (f)
    límite 50 y fila con 100 incidencias → la fila se muestra COMPLETA; (g)
    límite 5 → solo las filas necesarias; (h) `limite_muestra` ausente o vacío →
    presupuesto 50 (la respuesta es idéntica a la de hoy); (i) `0`/`-5` → 1,
    `5000` → 1000, `abc` → 50 y la petición NO devuelve 400; (j) límite mayor que
    las incidencias → todo cabe y sin nota; (k) sin incidencias → fallback de las
    primeras 50 filas con `muestra_filas = [1, 2, …, N]` (el campo no se aplica);
    (l) los tests (a)-(d) de la vista previa siguen en verde sin modificarse.
    `pytest` completo en verde antes de pasar a T14 (y confirmación del usuario
    antes de continuar).
- [x] **T14. Límite de incidencias: frontend y verificación en navegador.**
  RF-11, RF-15, RF-16 (navegador), HU-8
  - Alcance: `frontend/components/FileUploader.js` (campo numérico «Máximo de
    incidencias en la vista previa» junto al interruptor de autocorrección:
    etiqueta y ayuda en español, valor por defecto visible 50, `min=1`
    `max=1000`, usable a 375px, y paso del estado al callback de validación);
    `frontend/app.js` (añade `limite_muestra` al `FormData` de TODAS las
    validaciones, incluida la de "Aplicar cambios y revalidar", leyendo el valor
    actual del campo en cada envío); `frontend/components/RowPreview.js`
    (título "Vista Previa de Errores" / "Vista previa de filas" y nota nueva
    "Mostrando X de Y incidencias en N de M filas." con X/Y/N/M derivados del
    cruce `errores` ∪ `correcciones`, solo si queda algo fuera). Sin archivos
    nuevos; los CSV de prueba se generan temporales fuera del repo.
  - Hecho cuando: en el navegador contra la API real a 1280px y 375px: (1) el
    campo se ve junto al interruptor con el 50 por defecto, es cómodo de escribir
    y se ve bien en móvil; (2) con límite 5 en un archivo con más incidencias, la
    vista previa se recorta y aparece la nota "Mostrando X de Y incidencias en N
    de M filas."; (3) valores tontos (vacío, 0, letras) no rompen la petición y
    la respuesta usa 50 o el recorte; (4) cambiar el límite y pulsar "Aplicar
    cambios y revalidar" aplica el valor nuevo (arrastra el límite actual);
    (5) el título es "Vista Previa de Errores" con incidencias y "Vista previa de
    filas" en un archivo limpio (fallback, nada editable), y la edición con
    `fila: <n>` real sigue funcionando; `python -m pytest` sigue en verde;
    `MEMORY.md` queda actualizado (estado, decisiones y errores a evitar).
- [x] **T15. Límite por FILAS: backend `preparar_muestra` por filas de interés.**
  RF-11 (tope por filas y campo), RNF-5 (campo opcional con defecto 50), RF-16
  (servidor), RNF-6
  - Alcance: `backend/app/services/normalizer.py` (`preparar_muestra` pasa de
    presupuesto de INCIDENCIAS a tope de FILAS de interés: los números de la
    unión `errores` ∪ `correcciones` en orden de fila hasta `limite_filas` —una
    fila consume 1 aunque tenga 1 o 100 incidencias y se muestra siempre entera,
    sin presupuesto por celda—; el parámetro renombra de `limite_incidencias` a
    `limite_filas`, ya recortado; el backend NO calcula el recuento de
    incidencias); `backend/app/api/v1/endpoints/upload.py` (solo pasa el límite
    con el nombre nuevo; el recorte de `limite_muestra` NO cambia: no numérico →
    50, `< 1` → 1, `> 1000` → 1000, nunca 400);
    `backend/tests/test_normalizer.py` y `backend/tests/test_upload_endpoint.py`
    (los tests del presupuesto de incidencias se reescriben a la semántica por
    filas). `validator.py` (`_muestra()`, `LIMITE_MUESTRA`, solo para el
    fallback) y `parser.py` INTACTOS. Sin archivos nuevos.
  - Hecho cuando: `python -m pytest` pasa con los 191 actuales (expectativa de
    T15; la cifra vigente y final es 189) adaptando solo lo
    necesario, que cubren: (e) una fila con 100 incidencias consume 1 sola FILA
    (p. ej. límite 2 → la fila se muestra ENTERA); (f) 1000 filas con un error
    cada una y límite 50 → las filas de interés 1..50; (g) límite 5 → la vista
    previa se recorta a 5 filas de interés; (h) `limite_muestra` ausente o vacío
    → 50 filas (la respuesta sigue siendo la de hoy); (i) `0`/`-5` → 1, `5000`
    → 1000, `abc` → 50 y la petición NO devuelve 400; (j) límite mayor que las
    filas de interés → todo cabe; (k) sin filas de interés → fallback de las
    primeras 50 filas con `muestra_filas = [1, 2, …, N]` (el campo no se aplica);
    (l) `muestra_filas` sigue paralelo a `muestra` (enteros 1-based reales); y
    ningún test del presupuesto de incidencias queda en rojo (se reescriben o
    se eliminan). `pytest` completo en verde antes de pasar a T16 (y
    confirmación del usuario antes de continuar).
- [x] **T16. Sin límite: backend `preparar_muestra` sin tope e ignorar `limite_muestra`.**
  RF-11 (todas las filas de interés), RNF-5 (campo eliminado ignorado), RF-16
  (servidor), RNF-6
  - Alcance: `backend/app/services/normalizer.py` (`preparar_muestra` se queda
    SIN parámetro de límite: devuelve TODAS las filas de interés de la unión
    `errores` ∪ `correcciones` en orden de fila; se elimina `limite_filas`; el
    fallback sigue siendo las primeras 50 filas con `LIMITE_MUESTRA`);
    `backend/app/api/v1/endpoints/upload.py` (deja de leer y de recortar
    `limite_muestra` del multipart —si llega, se ignora, nunca un 400— y llama
    `preparar_muestra(filas, result.errores, correcciones)`);
    `backend/tests/test_normalizer.py` y `backend/tests/test_upload_endpoint.py`
    (los tests del tope por filas de T15 se reescriben a la nueva semántica).
    `validator.py` (`_muestra()`, `LIMITE_MUESTRA`, solo para el fallback) y
    `parser.py` INTACTOS. Sin archivos nuevos.
  - Hecho cuando: `python -m pytest` pasa con los 193 actuales (expectativa de
    T16; la cifra vigente y final es 189) adaptando solo
    lo necesario, que cubren: (e) 1000 filas con un error cada una → `muestra`
    trae las 1000 (sin tope); (f) una fila con 100 incidencias → se muestra
    ENTERA como 1 fila de interés; (g) petición que aún envía `limite_muestra`
    (vacío, 0, letras o un entero) → NO devuelve 400 y la respuesta trae
    TODAS las filas de interés; (h) sin filas de interés → fallback de las
    primeras 50 filas con `muestra_filas = [1, 2, …, N]` (intacto); (i)
    `muestra_filas` sigue paralelo a `muestra` sin tope (enteros 1-based
    reales, p. ej. `[80, 900]`); y ningún test del tope por filas queda en
    rojo (se reescriben o se eliminan). `pytest` completo en verde antes de
    pasar a T17 (y confirmación del usuario antes de continuar).
- [x] **T17. Sin límite: frontend — campo eliminado, contador siempre visible y aviso por volumen.**
  RF-11, RF-15, RF-16 (navegador), HU-8
  - Alcance: `frontend/components/FileUploader.js` (ELIMINA el campo numérico
    y su ayuda de la vista previa; el formulario se queda con el interruptor
    de autocorrección y lo de siempre); `frontend/app.js` (deja de agregar
    `limite_muestra` al `FormData`, también en la revalidación);
    `frontend/components/RowPreview.js` (contador SIEMPRE encima de la tabla
    cuando hay filas de interés: "X filas con errores o correcciones · Y
    incidencias" con singular correcto, X e Y derivados del cruce `errores` ∪
    `correcciones`; aviso NO bloqueante "Esta vista previa tiene N filas con
    errores o correcciones; puede tardar en mostrarse." cuando X ≥ 2.000; en
    fallback, sin contador). Sin archivos nuevos; los CSV de prueba se generan
    temporales fuera del repo.
  - Hecho cuando: en el navegador contra la API real a 1280px y 375px: (1) el
    campo «Máximo de filas en la vista previa» ya no existe y la revalidación
    NO envía `limite_muestra` (comprobado en la pestaña de red); (2) con un
    archivo con errores, el contador se ve SIEMPRE sobre la tabla con X e Y
    reales (incluido el caso "solo correcciones": ámbar sin rojo); (3) con un
    CSV temporal de más de 2.000 filas de interés, el aviso de volumen queda
    visible sobre la tabla y el renderizado NO se bloquea (siguen editándose
    celdas); (4) con un CSV limpio, el título es "Vista previa de filas", NO
    hay contador, salen las primeras 50 filas y nada es editable; (5) la
    edición con `fila: <n>` real sigue funcionando en archivos grandes;
    `python -m pytest` sigue en verde; `MEMORY.md` queda actualizado (estado,
    decisiones y errores a evitar).
