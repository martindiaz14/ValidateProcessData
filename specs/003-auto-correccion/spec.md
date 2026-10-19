# Spec 003 — Auto-corrección y corrección manual
Estado: borrador (cambio «sin límite: todas las filas de interés + contador y aviso por volumen» pendiente de aprobación; los cambios anteriores de la vista previa de errores están implementados con 191 tests en verde)

## Contexto y objetivo
La spec 002 ya muestra al analista los errores con detalle, pero este tiene que
corregir el archivo a mano y volver a subirlo. Una gran parte de los errores son
"de formato" y se pueden arreglar de forma segura y automática: espacios de más,
mayúsculas y minúsculas, separadores de miles, fechas con otro formato, etc.
Esta spec añade autocorrección determinista, transparente y opcional: el sistema
normaliza los valores sobre una copia en memoria ANTES de validarlos e informa
de cada cambio (antes → después). Además, el analista puede corregir
manualmente las celdas que él elija y revalidar para ver cómo queda. Por
último, se permiten descargar DOS versiones del archivo: la normal (tal cual se
subió) y la corregida (con todas las correcciones aplicadas), sin tocar nunca
el archivo original del usuario.

## Usuarios
- Analista/empresa que sube un archivo con errores y quiere que el sistema los
  arregle solo dejando constancia, con opción de ajustar a mano lo que prefiera.

## Historias de usuario
- HU-1. Como analista, quiero activar la autocorrección para que el sistema
  limpie los valores mal formateados antes de validarlos.
- HU-2. Como analista, quiero ver qué celdas se corrigieron (fila, columna,
  antes → después) para poder auditar cada cambio.
- HU-3. Como analista, quiero distinguir en la vista previa las celdas
  corregidas de las que siguen con error.
- HU-4. Como analista, quiero descargar las dos versiones del archivo: la
  normal (tal cual la subí) y la corregida (con todas las correcciones).
- HU-5. Como analista, quiero desactivar la autocorrección para ver los
  errores tal cual vienen en el archivo original.
- HU-6. Como analista, quiero editar manualmente las celdas que yo elija (con
  error o ya autocorregidas) y revalidar para comprobar cómo quedan.
- HU-7. Como analista, quiero que las correcciones manuales también queden
  registradas, igual que las automáticas.
- HU-8. Como analista, quiero que la vista previa me muestre solo las
  filas con errores o correcciones («Vista Previa de Errores») para
  corregir de un vistazo sin tener que hacer scroll entre filas
  correctas.

## Definiciones
- Autocorrección: normalización determinista de celdas aplicada antes de
  validar, solo sobre una copia en memoria de las filas ya parseadas.
- Determinista: misma entrada y mismo esquema → mismas correcciones, sin azar,
  sin aprendizaje y sin servicios externos.
- Corrección manual: valor que el analista escribe directamente sobre una celda
  de la vista previa; se aplica después de la normalización automática y queda
  auditada igual que ella.
- Edición pendiente: cambio escrito en el navegador pero aún no enviado al
  servidor; todo el lote viaja en la siguiente revalidación.
- Corrección ambigua: valor con más de una lectura razonable; en ese caso NO
  se corrige y se conserva el error original. La única excepción son las
  fechas ambiguas de una columna con convención deducida (ver RF-6).
- Convención de fechas de columna: orden día/mes o mes/día que se deduce de
  los valores inequívocos (de lectura única) de esa misma columna y que se
  aplica a los valores ambiguos de la misma columna; si la columna no aporta
  evidencia única, la convención no existe (RF-6).
- Copia corregida: archivo CSV/JSON generado a partir de las filas ya
  corregidas; el archivo subido por el usuario jamás se modifica.
- Fila de interés: fila con al menos un error residual o al menos una
  corrección (automática o manual). Es lo único que muestra la vista
  previa cuando existe alguna (RF-11); una fila válida y sin correcciones
  no es de interés.
- Incidencia: celda (fila + columna) con error residual o con al menos una
  corrección (automática o manual); una celda con error Y corrección
  cuenta UNA sola. Es solo un dato informativo: su total se muestra
  SIEMPRE en el contador sobre la tabla de la vista previa (RF-11); no
  limita nada (ya no hay límite).

## Requisitos funcionales
- RF-1: MIENTRAS el analista valida con la autocorrección activada, EL
  SISTEMA aplica las normalizaciones a una copia en memoria de las filas
  antes de validarlas. SI la autocorrección está desactivada o no se envía la
  petición, ENTONCES el resultado es idéntico al actual (sin cambios).
- RF-2: EL SISTEMA solo normaliza celdas de las columnas definidas en el
  esquema; el resto de columnas se copian sin ningún cambio.
- RF-3: CUANDO un valor de una columna del esquema contiene espacios
  sobrantes (al inicio, al final o dobles internos) o caracteres invisibles
  (espacio duro U+00A0, caracteres de ancho cero), EL SISTEMA los elimina o
  colapsa antes de validar. SI el valor estaba formado solo por espacios o
  caracteres invisibles, ENTONCES no se genera registro de corrección (el
  validador actual ya lo trataba como vacío, ver RF-8).
- RF-4: CUANDO la regla de la columna es correo, EL SISTEMA pasa el valor a
  minúsculas. (La normalización de los enums por mayúsculas/minúsculas y
  espacios no vive aquí: está unificada en RF-7.)
- RF-5: CUANDO la regla de la columna es número y el valor es un texto con
  separadores de miles y/o decimal, EL SISTEMA lo convierte a número solo si
  el patrón de separadores es inequívoco, según esta regla:
  (a) si aparecen AMBOS separadores (`,` y `.`), el último separador es el
  decimal y todos los de la izquierda deben formar grupos de 3 dígitos
  (`1.234,56` y `1,234.56` → `1234.56`);
  (b) si aparece un solo tipo de separador repetido, todos deben formar
  grupos de 3 dígitos (`1.234.567` → `1234567`);
  (c) si aparece un único separador, es decimal, salvo que a la derecha haya
  exactamente 3 dígitos y a la izquierda entre 1 y 3: en ese caso la lectura
  como miles también es posible y el valor es ambiguo (`1,234`, `12,345`).
  SI el valor no encaja en ninguna de las formas anteriores (p. ej.
  `1.234.56`), ENTONCES no es inequívoco: no se corrige y se conserva el
  error original. El valor corregido es un NÚMERO: en la respuesta viaja como
  número (entero sin decimales si no hay parte decimal) y en la descarga CSV
  se escribe con punto decimal y sin separadores de miles.
- RF-6: CUANDO la regla de la columna es fecha y el valor son tres grupos
  separados por `/` o `-` con un año de 4 dígitos al final (p. ej.
  `DD/MM/AAAA` o `DD-MM-AAAA`), EL SISTEMA comprueba qué lecturas son fechas
  válidas (día/mes/año o mes/día/año) y actúa así:
  (a) si solo una lectura es válida (valor de lectura única) y esa lectura
  coincide con la convención de la columna —o la columna no tiene
  convención—, la aplica y convierte el valor al formato pedido por la regla
  (por defecto `AAAA-MM-DD`);
  (b) si las DOS lecturas son válidas (valor ambiguo, p. ej. `01/10/2026`),
  aplica la convención de la columna; SI la columna no tiene convención,
  ENTONCES no corrige y el valor sigue siendo error;
  (c) si la lectura única es CONTRARIA a la convención de la columna (p. ej.
  `01/13/2026` en una columna con convención día/mes), ENTONCES no corrige
  (se conserva el error) por ser conservador.
  La convención de la columna se deduce UNA sola vez a partir de sus valores
  de lectura única: si alguno solo es válido leyendo día/mes (p. ej.
  `25/12/2026`) la convención es día/mes; si alguno solo es válido leyendo
  mes/día (p. ej. `05/13/2026`) es mes/día. SI los valores inequívocos de la
  columna apuntan a convenciones distintas, ENTONCES la columna se considera
  sin convención (gana la convención con MÁS valores de lectura única de su
  orden; solo hay conflicto cuando hay EMPATE, p. ej. `25/12/2026` frente a
  `05/13/2026`; los ambiguos no se corrigen, pero los de lectura única en
  una columna sin convención sí se corrigen con su única lectura).
- RF-7: CUANDO la regla es enum y el valor no está permitido, EL SISTEMA lo
  sustituye por el valor permitido en estos casos, por este orden:
  (a) si tras ignorar mayúsculas/minúsculas y espacios coincide con
  EXACTAMENTE un valor permitido, usa ese valor en su forma exacta (p. ej.
  `aprobado ` → `APROBADO`);
  (b) si no, y hay EXACTAMENTE un valor permitido a distancia de edición ≤ 1
  del valor tal cual (p. ej. `APROBAD0` → `APROBADO`), usa ese valor.
  SI en cualquiera de los dos pasos hay más de un candidato posible,
  ENTONCES no corrige (ver el caso límite del enum con dos candidatos).
- RF-8: CUANDO la columna NO es requerida y el valor, tras la limpieza del
  RF-3, coincide (sin distinguir mayúsculas/minúsculas) con un marcador de
  vacío de la lista cerrada `n/a`, `#n/a`, `n.a.`, `na`, `null`, `none`,
  `-`, `--`, `sin dato`, `sin datos`, EL SISTEMA lo convierte en vacío.
  SI el campo es requerido, ENTONCES no lo transforma: el valor pasa al
  validador y aparece su error habitual (p. ej. tipo incorrecto en una
  columna numérica). La cadena vacía o de solo espacios YA cuenta como vacía
  en el validador actual, por lo que no genera entrada de corrección.
- RF-9: POR CADA corrección, ya sea automática o manual, EL SISTEMA registra
  fila (1-based), columna, valor antes, valor después y tipo de corrección, y
  la devuelve como entrada del campo `correcciones` (el vocabulario de
  `tipo`, la serialización y el orden exacto de la lista están en "Contrato
  de la API"). El rastro incluye tanto las normalizaciones automáticas como
  las ediciones manuales.
- RF-10: EL SISTEMA calcula el resumen (válidas/inválidas), la lista de
  errores, las métricas y la vista previa sobre los valores ya corregidos;
  una fila que tras corregir sigue incumpliendo una regla sigue contando
  como inválida.
- RF-11: EL SISTEMA muestra en la vista previa TODAS las filas de interés
  (error residual o alguna corrección, ver "Fila de interés"), en orden de
  fila ascendente y con su número de fila original en la columna "#",
  SIN tope de filas (decisión del usuario: «sin límite: mostrar todas +
  contador»); no existe ningún campo de límite en el formulario ni en la
  petición. EL SISTEMA muestra SIEMPRE, encima de la tabla, un contador
  con el formato "X filas con errores o correcciones · Y incidencias"
  (X = filas de interés, que son todas las visibles; Y = total de
  incidencias: celdas de la unión `errores` ∪ `correcciones`, donde una
  celda con error Y corrección cuenta UNA; singular correcto: "1 fila con
  errores o correcciones" y "· 1 incidencia"). X e Y NO viajan en ningún
  campo: el navegador los calcula de las listas COMPLETAS `errores` ∪
  `correcciones` (ver el Contrato de la API), de modo que también cuenta
  el caso "solo correcciones" (ámbar sin rojo). CUANDO X alcanza el
  umbral de 2.000 filas de interés, ENTONCES aparece, también encima de
  la tabla y SIN bloquear el renderizado, el aviso de seguridad "Esta
  vista previa tiene N filas con errores o correcciones; puede tardar en
  mostrarse." (N = X). SI ninguna fila es de interés, ENTONCES la vista
  previa trae las primeras 50 filas del archivo con la nota de hoy
  ("Mostrando las primeras 50 de 60 filas."), es decir, el comportamiento
  actual, y SIN contador (no hay errores ni correcciones que contar). El
  título de la sección es "Vista Previa de Errores" cuando hay filas de
  interés y "Vista previa de filas" cuando no las hay. DENTRO de las
  filas mostradas, EL SISTEMA distingue las celdas corregidas (resaltadas
  en ámbar) de las celdas con error (rojo, como hasta ahora); SI una celda
  está corregida pero sigue fallando, ENTONCES se muestra en rojo (gana el
  error). En escritorio, la celda ámbar muestra el valor original al
  pasar el cursor; EN móvil no hay tooltip, ENTONCES el valor "antes" se
  consulta en la sección "Correcciones aplicadas" (RF-13), que es
  responsive (RF-15) y cuyo tope de 50 ENTRADAS sigue siendo
  independiente. El tooltip es, por tanto, una mejora de escritorio.
- RF-12: EL SISTEMA permite activar o desactivar la autocorrección con un
  interruptor general en el formulario de carga; el interruptor viene
  activado por defecto y su estado viaja con la petición de validación. EL
  interruptor controla SOLO la normalización automática: las ediciones
  manuales se aplican siempre que se envíen.
- RF-13: EL SISTEMA muestra, cuando ha habido correcciones, un contador en el
  resumen ("N celdas autocorregidas" y, si las hay, "M ediciones manuales";
  N y M se computan según el "Contrato de la API") y una sección
  "Correcciones aplicadas" con la tabla fila, columna, antes → después y
  tipo, distinguiendo las automáticas de las manuales. La tabla muestra como
  mucho las PRIMERAS 50 entradas de `correcciones` (mismo orden que el campo)
  con la nota "mostrando X de Y" para no saturar la página; la lista completa
  está siempre en la respuesta y en la descarga corregida.
- RF-14: EL SISTEMA permite descargar DOS versiones del archivo: la normal
  (los bytes originales tal cual se subieron, generada en el navegador sin
  tocar el backend) y la corregida (generada en el navegador a partir del
  campo `filas_corregidas` de la respuesta —ver "Contrato de la API"—, en CSV
  y JSON, con TODAS las filas: las que sigan inválidas quedan como estén tras
  las correcciones). Los botones se agrupan bajo un bloque "Descargas" con
  etiquetas claramente distintas: "Archivo original", "Archivo corregido
  (CSV)", "Archivo corregido (JSON)", "Informe de errores (CSV)" e "Informe
  de errores (JSON)". CUANDO el archivo subido es `.xlsx` y no hay ninguna
  corrección, EL SISTEMA envía igualmente `filas_corregidas` (el navegador
  no puede regenerar un .xlsx sin librerías nuevas), de modo que la versión
  corregida —en CSV o JSON— está siempre disponible y, de paso, permite
  convertir un Excel a CSV/JSON. SI `descarga_corregida_disponible` es
  falso (solo cuando el archivo supera las 100.000 filas), ENTONCES los
  dos botones de la versión corregida aparecen deshabilitados con un
  aviso en español que explica el motivo.
- RF-15: EL SISTEMA muestra la interfaz en español y es usable en móvil
  (responsive), incluida la vista previa de errores (título, columna "#",
  contador, aviso por volumen, notas y tabla con scroll horizontal), la
  edición manual de celdas y la sección "Correcciones
  aplicadas".
- RF-16: EL SISTEMA permite editar directamente en la vista previa las celdas
  que tienen error o fueron corregidas (SOLO esas). Todo lo que muestre la
  Vista Previa de Errores es editable —decisión explícita del usuario—:
  las filas de interés que muestre la Vista Previa de Errores (RF-11, sin
  tope), con su
  número de fila real (un error de la fila 200 o 900 se edita con `fila:
  200` o `fila: 900`). SI la vista previa
  está en el caso de reserva (fallback, sin filas de interés), ENTONCES
  ninguna celda es editable (no hay nada que corregir). Al pulsar una
  celda editable se abre un campo con el
  valor actual (relleno; vaciarlo deja la celda vacía); el cambio se marca
  como pendiente en el navegador. EL botón "Aplicar cambios y revalidar" es
  el ÚNICO que envía las ediciones pendientes (RF-17); el botón "Validar"
  del formulario de carga envía una validación nueva SIN ediciones y, si
  hay ediciones pendientes, las descarta mostrando un aviso. Las celdas ya
  válidas no son editables.
- RF-17: CUANDO el analista aplica sus ediciones, EL SISTEMA envía el lote
  completo junto con el archivo y el esquema en la misma petición de
  validación; las ediciones se aplican sobre la copia en memoria DESPUÉS de
  la normalización automática y se revalida todo el conjunto: contadores,
  errores, métricas, gráficas, vista previa y lista de correcciones se
  recalculan. Al recibir la respuesta, los cambios pendientes se limpian y
  las celdas aplicadas aparecen como correcciones manuales. Nota: cada
  revalidación es otra petición de validación, por lo que inserta un registro
  NUEVO en el histórico de cargas (igual que hoy, guardando solo recuentos) y
  no modifica los anteriores.
- RF-18: SI una edición manual apunta a una fila que no existe o a una
  columna que no está en el esquema, ENTONCES EL SISTEMA devuelve un error
  claro en español sin validar; SI la misma celda aparece varias veces en el
  lote, ENTONCES se aplican en orden y se registra cada cambio.

## Requisitos no funcionales
- RNF-1: La normalización y la aplicación de las ediciones manuales viven en
  `backend/app/services/` como lógica pura (funciones de entrada a salida,
  sin HTTP ni base de datos) para probarlas directamente con pytest, según la
  constitución.
- RNF-2: La corrección se hace sobre una copia en memoria; el archivo subido
  no se escribe ni se modifica nunca, y no se persiste ningún dato nuevo en
  la base de datos (el registro de carga sigue guardando solo recuentos; ver
  la nota de histórico de RF-17).
- RNF-3: Ningún dato sale del equipo: sin servicios externos, sin LLM y sin
  librerías nuevas (la distancia de edición se resuelve con la stdlib o una
  implementación propia, p. ej. `difflib`). La descarga de la versión normal
  se hace en el navegador con el archivo que ya está en memoria, sin endpoint
  nuevo.
- RNF-4: La normalización recorre las filas en una sola pasada de coste
  lineal, sin degradar de forma apreciable la validación de archivos grandes
  (hasta el límite actual de 10 MB).
- RNF-5: La respuesta de la API se mantiene compatible: todos los campos
  nuevos (petición y respuesta) están definidos en "Contrato de la API", son
  opcionales con valores por defecto y un cliente antiguo que no los conoce
  sigue funcionando igual. ÚNICA excepción consciente y documentada en esta
  spec: `muestra`, cuyo cambio de semántica (filas de interés) afecta solo
  a esa definición; el frontend y el backend se despliegan juntos.
- RNF-6: `pytest` cubre cada tipo de normalización, la aplicación de ediciones
  manuales y sus casos límite; los 36 tests actuales siguen pasando. El
  flujo de edición en el navegador se verifica contra la API real
  (escritorio y móvil), como el resto del frontend, sin frameworks JS de
  testing.
- RNF-7: El volumen de la respuesta queda acotado: `filas_corregidas` se
  envía cuando hay correcciones o cuando el archivo subido es `.xlsx`
  (aunque no las haya, ver RF-14) y nunca si el archivo supera las 100.000
  filas (ese es el ÚNICO motivo por el que `descarga_corregida_disponible`
  pasa a `false`). El límite de subida de 10 MB sigue vigente: ningún
  archivo que entre por upload puede superar ese tamaño, y actúa como
  cota práctica también para `muestra` (que ya no está acotada por filas,
  decisión «sin límite»); el tope de 100.000 filas
  protege `filas_corregidas` cuando el archivo tiene muchas filas cortas.

## Contrato de la API (campos nuevos)
Todos los nombres nuevos van en `snake_case`, sin tildes ni espacios, en el
mismo estilo que los campos existentes de `ValidationResult` (`total_filas`,
`muestra`, `errores`, `metricas`, `columnas`) y con nombres de código en
inglés. Los textos visibles para el usuario (secciones, botones, avisos) sí
van en español; no son campos.

### Petición (mismos campos de formulario del endpoint de validación)
- `autocorreccion` (booleano, opcional, por defecto `false`): si el campo no
  se envía, no se normaliza (RF-1); la interfaz envía siempre su valor, con el
  interruptor activado por defecto (RF-12). Controla SOLO la normalización
  automática.
- `ediciones` (texto JSON opcional, por defecto lista vacía): lote de
  ediciones manuales del RF-17. Cada elemento es
  `{"fila": <entero 1-based>, "columna": <texto>, "valor": <texto o vacío>}`.
- `limite_muestra` (ELIMINADO en esta revisión): la vista previa ya no
  tiene límite editable (RF-11); la interfaz ya no envía este campo. SI
  un cliente antiguo lo sigue enviando, ENTONCES el servidor lo IGNORA
  sin error (nunca un 400 por este motivo) y devuelve todas las filas de
  interés (RNF-5).

### Respuesta (campos añadidos a `ValidationResult`)
- `correcciones` (lista, por defecto vacía): rastro de auditoría del RF-9.
  Cada entrada contiene:
  - `fila` (entero, 1-based), `columna` (texto), `antes` (texto, el valor
    original tal cual venía), `despues` (texto o número) y `tipo` (texto).
  - `tipo` tiene vocabulario cerrado: `espacios`, `invisibles`, `minusculas`,
    `enum`, `numero`, `fecha`, `vacio` (normalizaciones automáticas) y
    `manual` (ediciones del analista). Una celda con VARIAS normalizaciones
    automáticas genera UNA sola entrada, con el `tipo` de la última que
    modificó el valor; el orden de aplicación es: `espacios`/`invisibles` →
    `vacio` → `minusculas` → `enum` → `numero`/`fecha`.
  - `despues` se serializa como TEXTO para `espacios`, `invisibles`,
    `minusculas`, `enum`, `manual` (el valor llega como texto en la
    petición) y `vacio` (cadena vacía) y para `fecha` en el
    formato que pida la regla (por defecto `AAAA-MM-DD`); y como NÚMERO para
    `numero` (entero sin decimales si no hay parte decimal). En la descarga
    CSV los números se escriben con punto decimal y sin separadores de miles.
  - Orden de la lista: por `fila` ascendente; dentro de una fila, por el
    orden de aparición de las columnas en el archivo; en la misma celda, la
    entrada automática antes que la manual.
  - Cómputo de los contadores del RF-13: "N celdas autocorregidas" = número
    de entradas con `tipo` distinto de `manual`; "M ediciones manuales" =
    número de entradas con `tipo` `manual`. El campo incluye ambos tipos.
- `filas_corregidas` (lista de objetos {columna: valor}, por defecto
  vacía): TODAS las filas del archivo con los valores ya corregidos
  (normalización automática y ediciones manuales aplicadas), en el orden del
  archivo y con la misma representación de valores que `muestra` (las celdas
  numéricas corregidas como número, las fechas como texto `AAAA-MM-DD` y los
  vacíos como cadena vacía). Las celdas editadas a mano conservan ahí esa
  misma representación (número si la celda es numérica, texto para las
  fechas), aunque en `correcciones` su `despues` viaje como texto. Es la
  fuente única de la descarga corregida del RF-14; el navegador arma el CSV
  respetando el orden de `columnas` y el JSON igual que la respuesta. Se
  envía cuando `correcciones` no está vacío O cuando el archivo subido es
  `.xlsx`, aunque no haya correcciones (el navegador no puede regenerar un
  .xlsx sin librerías nuevas: así el botón "Archivo corregido" funciona
  siempre y, de paso, permite convertir Excel → CSV/JSON). Si no hay
  correcciones y el archivo NO es `.xlsx`, se envía vacío y la descarga
  corregida se genera en el navegador a partir del archivo original (sale
  idéntica). Para acotar el volumen, si el archivo supera las 100.000 filas
  se envía vacío sea cual sea su formato (RNF-7).
- `descarga_corregida_disponible` (booleano, por defecto `true`): pasa a
  `false` SOLO cuando `filas_corregidas` no se envió por el tope de
  100.000 filas (ya no por "no hay correcciones"); la interfaz deshabilita
  los botones de la versión corregida y lo explica en español (RF-14).

### Respuesta — cambio sobre un campo existente: `muestra` (spec 002) y su compañero `muestra_filas`
- `muestra` (lista de objetos {columna: valor}, SIN límite): trae TODAS
  las filas de interés (error residual o alguna corrección) en orden de
  fila ascendente, sin tope de filas (decisión «sin límite»). SI no hay
  ninguna fila de interés, ENTONCES trae las primeras 50 filas de siempre
  (fallback intacto: una subida limpia siempre muestra algo). La
  representación de los valores de cada
  fila NO cambia (la misma que hoy y la que pide `filas_corregidas`); solo
  cambia QUÉ filas contiene. El TOTAL de filas de interés (X) y el total
  de incidencias (Y) del contador del RF-11 NO viajan en
  ningún campo: el navegador los calcula de las listas COMPLETAS
  `errores` ∪ `correcciones`, que llegan completas en la respuesta; así
  el caso "solo correcciones" (ámbar sin rojo) también cuenta.
- `muestra_filas` (lista de enteros 1-based, por defecto vacía): número de
  fila original de cada entrada de `muestra`, SIEMPRE con la misma
  longitud y el mismo orden que `muestra` (en el caso de fallback es
  `[1, 2, …, N]`). El navegador la usa para pintar la columna "#" y para
  construir la clave `fila:columna` de los errores, las correcciones y las
  ediciones (RF-11, RF-16): `muestra` ya no empieza necesariamente en la
  fila 1.
- Nota de implementación: el endpoint de validación (`upload.py`) compone
  `muestra` con TODAS las filas de interés (a partir de `validate_rows` y
  de la lista `correcciones`), sin tope; SI no hay ninguna, usa
  `LIMITE_MUESTRA` (50) solo para el fallback. `validator.py`
  (`validate_rows`, `_muestra()`, `LIMITE_MUESTRA`) queda
  INTACTO (regla del proyecto: no tocarlo). El campo `limite_muestra` ya
  no se lee de la petición (si llega, se ignora). El contador y el aviso
  por volumen NO los calcula el backend: los deriva el navegador del
  cruce `errores` ∪ `correcciones`.
- Nota de compatibilidad (RNF-5): `limite_muestra` se ELIMINA de la
  petición y de la interfaz; un cliente antiguo que lo envíe no recibe
  ningún error y su valor se ignora (la respuesta trae todas las filas
  de interés). `muestra` es la ÚNICA excepción
  consciente a la compatibilidad (cambio de semántica documentado en esta
  spec) y `muestra_filas` es opcional con valor por defecto; el frontend y
  el backend se cambian en la misma entrega, porque un cliente que
  siguiera asumiendo "posición + 1" solo acertaría en el fallback. El RF-1
  de la spec 002 ya está enmendado para decir "las filas con error o
  corrección, y si no las hay, las primeras 50"; su RNF-2 ("limitada a
  las primeras 50 filas") queda cubierta en el caso de reserva (las
  primeras 50 filas) y, para las filas de interés, el usuario ha decidido
  explícitamente mostrar TODAS (excepción documentada en "Dudas
  cerradas").

## Casos límite
- Fecha — columna con convención día/mes: `25/12/2026` (inequívoca) y
  `01/10/2026` → esta se corrige como 1 de octubre (`2026-10-01`).
- Fecha — columna con convención mes/día: `05/13/2026` (inequívoca) y
  `01/10/2026` → esta se corrige como 10 de enero (`2026-01-10`).
- Fecha — columna sin convención (solo valores ambiguos, p. ej. `01/10/2026`
  y `03/04/2026`): no se corrige ninguno; siguen contando como error.
- Fecha — lectura única contraria a la convención: `01/13/2026` en una
  columna con convención día/mes no se corrige; en una columna sin
  convención sí se corrige como 13 de enero.
- Fecha — convenciones en conflicto: la columna trae valores inequívocos de
  los dos órdenes (p. ej. `25/12/2026` y `05/13/2026`) → se trata como
  columna sin convención y los ambiguos no se corrigen.
- Fechas imposibles (`31/02/2026`) no se corrigen y tampoco aportan
  convención a la columna.
- Fecha con el año de 2 dígitos o en otra posición (p. ej. `01/10/26`,
  `2026/10/01`) no se toca: sigue siendo error de formato.
- Números: `1,234` y `12,345` (separador único seguido de exactamente 3
  dígitos) son ambiguos y no se corrigen; `1.23`, `1,2345` y `12,5` se leen
  como decimales; `1.234,56` y `1,234.56` → `1234.56`; `1.234.567` →
  `1234567`; `1.234.56` no es inequívoco y no se corrige. Textos sin sentido
  numérico (`hola`) no se tocan: siguen siendo error de tipo. Nota: un
  `1.234` que no se corrige ya hoy valida como el número 1.234 (el
  validador actual lo acepta), no se reinterpreta como 1234.
- Enum con dos candidatos a distancia de edición ≤ 1: permitidos `CAT` y
  `CAR`, valor `CA` (a distancia 1 de ambos) no se corrige por ambigüedad.
- Marcadores de vacío: `N/A`, `n/a`, `#N/A`, `N.A.`, `null`, `-`, `--`,
  `sin dato` (comparados sin distinguir mayúsculas/minúsculas) en columna no
  requerida → vacío con entrada tipo `vacio`; en columna requerida no se
  vacían y el valor conserva su error original.
- Cadena vacía o de solo espacios: ya cuenta como vacía para el validador
  actual, por lo que no genera entrada de corrección.
- Celda con dos normalizaciones (`  APROBAD0  ` → `APROBADO`): una sola
  entrada en `correcciones`, con tipo `enum` y `antes` igual al texto sin
  limpiar.
- Celda autocorregida y luego editada a mano: dos entradas en
  `correcciones` (la automática y la manual, cuyo `antes` es el valor ya
  corregido).
- Celda que tras la corrección sigue sin cumplir la regla (p. ej. número
  fuera de rango tras limpiar separadores): se registra la corrección y
  también el error restante.
- Valor ya válido (p. ej. correo ya en minúsculas o fecha ya en formato):
  no se genera registro de corrección.
- Archivo sin columnas del esquema o con 0 filas: la autocorrección no
  cambia nada y no hay sección de correcciones.
- Autocorrección desactivada: la respuesta es idéntica a la actual
  (`correcciones` y `filas_corregidas` vacíos salvo en un `.xlsx`, donde
  `filas_corregidas` se envía aunque no haya correcciones), salvo que se
  envíen ediciones manuales.
- Edición manual que vacía un campo requerido: tras revalidar aparece el
  error "campo requerido"; la celda se muestra en rojo.
- Edición manual inválida (fila fuera de rango o columna fuera del
  esquema): error 400 en español, sin validar.
- Botón "Aplicar cambios y revalidar" sin ediciones pendientes: no hace
  nada (deshabilitado).
- Con ediciones pendientes, cambiar el archivo seleccionado o el esquema en
  el formulario: las ediciones pendientes se limpian (no se aplican contra
  datos ajenos) y se avisa al usuario.
- Con ediciones pendientes, pulsar "Validar": se descartan con aviso; solo
  "Aplicar cambios y revalidar" envía ediciones.
- Archivo con más de 100.000 filas (sea `.csv`, `.json` o `.xlsx`):
  `filas_corregidas` viene vacío y `descarga_corregida_disponible` es
  `false`; el resto del resultado (errores, contadores, `correcciones`) es
  normal.
- Descarga de la versión corregida cuando no hay ninguna corrección: si el
  archivo NO es `.xlsx`, su contenido coincide con el de la normal (se
  genera del original en el navegador y `filas_corregidas` viene vacío); si
  el archivo ES `.xlsx`, `filas_corregidas` se envía con todas las filas (el
  navegador no puede regenerar un .xlsx), la corregida se descarga en CSV o
  JSON y, de paso, se puede convertir Excel → CSV/JSON.
- Fila de interés lejana (p. ej. la 900 de un archivo de 1000): se
  muestra SIEMPRE (sin tope) y es editable con `fila: 900`.
- 1000 filas con un error cada una: se muestran las 1000 filas de
  interés completas (sin ninguna nota de recorte) y el contador indica
  "1000 filas con errores o correcciones · 1000 incidencias"; al ser
  menos de 2.000, NO aparece el aviso de volumen.
- 5000 filas con error: se muestran las 5000 y aparece el aviso "Esta
  vista previa tiene 5000 filas con errores o correcciones; puede tardar
  en mostrarse." (el renderizado no se bloquea).
- Una sola fila con 100 incidencias: se muestra la fila ENTERA y el
  contador dice "1 fila con errores o correcciones · 100 incidencias".
- Cliente antiguo que envía `limite_muestra`: el servidor lo ignora sin
  error (nunca un 400 por este motivo) y devuelve TODAS las filas de
  interés (RF-11, contrato).
- Fila válida y sin correcciones: no aparece en la vista previa aunque
  esté entre las primeras 50 del archivo; para revisarla se descarga el
  original.
- Archivo largo limpio (sin errores ni correcciones): comportamiento de
  hoy —las primeras 50 filas, título "Vista
  previa de filas", nota "Mostrando las primeras 50 de 60 filas.", SIN
  contador (no hay incidencias) y ninguna celda editable (RF-16)—.
- Errores solo en las filas 80 y 900: la vista previa empieza en la 80
  (no en la 1), no incluye ninguna fila válida, el contador dice "2
  filas con errores o correcciones · N incidencias" y la edición de la fila
  900 viaja con su número original (`fila: 900`) y se aplica sin error
  (RF-18).
- Archivo sin ningún error tras corregir (solo correcciones): la vista
  previa muestra únicamente las filas corregidas (ámbar) con el título
  "Vista Previa de Errores" y su contador, aunque ninguna celda esté en
  rojo.
- Vista previa con 0 filas (archivo vacío): no se pinta nada, como hoy.
- Cada "Aplicar cambios y revalidar" añade un registro nuevo al histórico de
  cargas (ver RF-17), sin tocar los anteriores.

## Fuera de alcance
- Imputación de valores aprendiendo de las celdas correctas de la columna
  (p. ej. rellenar un vacío con el valor más frecuente): fase 2 futura.
- LLM, servicios externos o cualquier envío de datos fuera del equipo.
- React, npm, pasos de build o librerías nuevas (ni rapidfuzz).
- Corregir errores de tipo reales (texto donde debería haber número) más allá
  de los formatos descritos.
- Normalizar columnas que no están en el esquema, valores booleanos y
  corrección de tildes/acentos.
- Edición manual de filas que no salen en la vista previa: las que no
  son de interés (válidas y sin correcciones); las filas de interés ya se
  muestran todas y son todas editables (RF-16).
- Buscar, filtrar o paginar filas en la vista previa (p. ej. ver una fila
  válida concreta): fuera de esta revisión.
- Formato .xls.

## Criterios de finalización
- Subiendo el archivo de ejemplo nuevo de esta spec (el de autocorrección,
  que trae errores de formato que SÍ se corrigen y otros que NO) con la
  autocorrección activada, el resumen muestra las celdas corregidas y la
  sección de correcciones permite auditar cada cambio antes → después
  (máximo 50 entradas visibles con la nota "mostrando X de Y").
- La vista previa (título "Vista Previa de Errores") muestra TODAS las
  filas con error o corregidas, con su número de fila original, y
  SIEMPRE encima de la tabla el contador "X filas con errores o
  correcciones · Y incidencias" (con el singular correcto); a partir de
  2.000 filas de interés aparece además, sin bloquear el renderizado, el
  aviso "Esta vista previa tiene N filas con errores o correcciones; puede
  tardar en mostrarse."; distingue celdas
  corregidas (ámbar) de celdas con error (rojo); al editar una celda a
  mano y aplicar los cambios, todo se revalida y la edición aparece como
  corrección manual. Con un archivo sin errores ni correcciones se ven las
  primeras 50 filas con el título de siempre ("Vista previa de filas"),
  SIN contador y ninguna celda es editable.
- El campo «Máximo de filas en la vista previa» NO existe: el formulario
  solo conserva el interruptor de autocorrección junto a sus entradas; el
  contador se ve y se usa bien a 375px; `pytest` cubre que una petición
  que aún envíe `limite_muestra` NO devuelve 400 e ignora el valor
  trayendo TODAS las filas de interés, que no hay tope (1000 errores en
  1000 filas → 1000 entradas en `muestra`) y que el fallback sigue
  trayendo las primeras 50; en el navegador se comprueba que el campo
  desapareció del formulario, que el contador se ve siempre sobre la
  tabla y que el aviso aparece con un archivo temporal (generado fuera
  del repo) de más de 2.000 filas de interés.
- `pytest` cubre la vista previa de errores: (a) las filas de interés
  salen en orden de fila y SIN tope (todas; p. ej. 1000 filas de interés
  → 1000 entradas en `muestra`);
  (b) `muestra_filas` va paralelo
  a `muestra` (mismo orden y longitud, números 1-based reales); (c) sin
  filas de interés, `muestra` es el fallback de las primeras 50 y
  `muestra_filas` es `[1, 2, …, N]`; (d) con errores solo en las filas 80
  y 900, `muestra` trae esas dos con sus números y la edición de la fila
  900 viaja como `fila: 900` y se aplica sin error (RF-18).
- Se pueden descargar las dos versiones con los botones etiquetados del
  bloque "Descargas": la normal idéntica a lo subido y la corregida (CSV y
  JSON) con todas las filas y las correcciones automáticas y manuales;
  subiendo un `.xlsx` sin ninguna corrección, la corregida se descarga
  igualmente (el navegador no puede regenerar un .xlsx) y sirve además para
  convertir Excel → CSV/JSON.
- Desactivando el interruptor, la autocorrección no se aplica (las ediciones
  manuales siguen funcionando).
- `pytest` pasa (actuales + nuevos) y la interfaz, incluida la edición
  manual, se ve bien en escritorio y móvil.

## Dudas cerradas y decisiones validadas
- Formato de la descarga corregida: CSV y JSON (ambos, como las
  exportaciones de la spec 002); la normal se descarga en el mismo formato
  en que se subió.
- Fechas ambiguas (decisión del usuario): se deduce la convención de la
  columna con sus valores inequívocos y se aplica a los valores ambiguos de
  esa misma columna; si la columna no tiene ningún valor inequívoco (o los
  tiene de los dos órdenes), la fecha ambigua queda como error (RF-6).
- Alcance de la edición manual (decisión EXPLÍCITA del usuario,
  confirmada en la revisión de QA): «todo lo que muestre la vista previa
  de errores es editable». Se mantiene el núcleo —SOLO celdas con error o
  ya corregidas— y el alcance deja de ser "las primeras 50 filas del
  archivo" para pasar a ser "TODAS las filas de interés del RF-11 (sin
  tope)": un
  error de la fila 200 o 900 SIEMPRE es editable, con su
  `fila: <n>` real. En fallback (sin filas de interés) no se edita nada
  (RF-16).
- Vista previa de errores (decisión del usuario, revisión anterior): la
  vista previa muestra solo las filas con error residual o con correcciones —ambas
  cuentan, rojo y ámbar— en orden de fila, con el contador y el aviso por
  volumen del RF-11 (ver RF-11); sin ninguna fila de interés se comporta
  como hoy
  (primeras 50 filas y título "Vista previa de filas"). Títulos exactos:
  "Vista Previa de Errores" / "Vista previa de filas". El número de fila
  original viaja en `muestra_filas` (ver Contrato de la API). El rastro de
  correcciones, los contadores, las métricas y las descargas no cambian.
- Sin límite: todas las filas de interés + contador (decisión del usuario,
  esta revisión, tras las revisiones anteriores con límite por incidencias
  y por filas; aclaración textual: «sigo sin saber por qué no es una
  buena idea que en vez de ser un límite haya un contador de filas con
  errores», elegida la opción "sin límite: mostrar todas + contador" tras
  explicarle el motivo de rendimiento en el navegador): la vista previa
  muestra TODAS las filas de interés y el campo de límite desaparece —se
  elimina `limite_muestra` de la petición y de la interfaz; si un cliente
  antiguo lo envía, se ignora sin error—. El contador "X filas con
  errores o correcciones · Y incidencias" está SIEMPRE visible sobre la
  tabla y, como protección de rendimiento, el aviso NO bloqueante «Esta
  vista previa tiene N filas con errores o correcciones; puede tardar en
  mostrarse.» aparece a partir de 2.000 filas de interés (umbral elegido
  porque, con ~10 columnas, son unas 20.000 celdas resaltadas y
  editables). El fallback (sin filas de interés) sigue trayendo las
  primeras 50 filas SIN contador. La sección "Correcciones aplicadas"
  sigue con su tope de 50 ENTRADAS independiente (RF-13 intacto).
- Botón que envía las ediciones (decisión de diseño de esta revisión): solo
  "Aplicar cambios y revalidar"; el "Validar" original nunca envía ediciones
  y las descarta con aviso para no aplicarlas contra datos ajenos.
- Archivo de ejemplo nuevo (decisión del usuario, archivos ya aprobados):
  `data-processor-app/backend/ejemplo_autocorreccion.csv` con su esquema
  (`ejemplo_autocorreccion_esquema.json`), porque el ejemplo actual no
  produce ninguna autocorrección y un criterio de finalización pide
  verificarla con "el archivo de ejemplo". Trae errores de formato que SÍ se
  corrigen (espacios sobrantes e internos, espacio duro U+00A0, `1.234,56`,
  enum en minúsculas, `n/a` en columna no requerida y fechas con valor de
  lectura única que aporta convención) y errores que NO se corrigen
  (`1,234` ambiguo, correo mal formado, texto donde debería haber número y
  enum a distancia > 1) para que el ejemplo sea realista.
- Descarga corregida siempre disponible (decisión del usuario): además de
  cuando hay correcciones, `filas_corregidas` se envía cuando el archivo
  subido es `.xlsx` aunque no haya ninguna, porque el navegador no puede
  regenerar un .xlsx sin librerías nuevas; así el botón "Archivo corregido"
  funciona siempre y, de paso, permite convertir Excel → CSV/JSON. El tope
  de 100.000 filas sigue aplicando y es el ÚNICO motivo por el que
  `descarga_corregida_disponible` pasa a `false`.
- Convención de fechas por mayoría estricta de valores de lectura única
  (empate → sin convención): decisión del usuario, porque hace alcanzables
  a la vez las reglas (b) y (c) del RF-6; con la lectura estricta
  ("cualquier inequívoco de orden distinto anula la convención"), un único
  valor contrario anularía la convención de toda la columna y la regla (c)
  (lectura única contraria) nunca se daría.
- Valor por defecto del campo `autocorreccion` = `false` cuando no se envía:
  decisión del usuario; el interruptor de la UI viene activado y envía `true`
  explícito, así la UX no cambia, pero una petición sin el campo sigue siendo
  idéntica a la actual (RF-1 y RNF-5 intactos).
