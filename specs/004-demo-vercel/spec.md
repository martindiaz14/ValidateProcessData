# Spec 004 — Demo pública en la nube (Vercel)

Estado: borrador (pendiente de aprobación)

## Contexto y objetivo
Las specs 001-003 dejan la herramienta completa y funcionando en local: se
arranca con uvicorn y todo el procesamiento ocurre en el equipo del usuario
(promesa de privacidad del artículo 5 de la constitución). El usuario quiere
dársela a usar por internet «sin la necesidad de instalar nada». Esta spec
prepara un DESPLIEGUE PÚBLICO de DEMOSTRACIÓN en Vercel: la misma aplicación
(sin npm, sin build, sin cambios de stack) accesible por una URL abierta y SIN
login, pensada para mostrar la herramienta, no para usarla con datos reales o
confidenciales.

En la nube los archivos se procesan en los servidores de Vercel, lo que choca
con el artículo 5 de la constitución («los datos no salen del equipo») y con el
límite de AGENTS.md («nunca subir datos a servicios externos»). Por eso esta
spec propone una ENMIENDA EXPLÍCITA (más abajo) que el usuario debe aprobar
junto con la spec. El modo local (uvicorn) queda exactamente igual que hoy.

Decisiones ya tomadas por el usuario (literales): «nube pública: Vercel»,
«acceso por internet público» (URL abierta), «sin login» y «adelante: demo
pública sin login», asumiendo el procesamiento en servidores de Vercel, el
límite del plan Hobby (solo no comercial; Pro si es uso comercial), disco
efímero y que una respuesta grande puede fallar.

## Usuarios
- Cualquier persona con navegador que abra la URL de la demo y quiera probar la
  herramienta sin instalar nada.
- El analista/empresa que sigue usándola en local: no ve ningún cambio (sin
  badge, sin banner, límite de 10 MB y datos que no salen de su equipo).

## Historias de usuario
- HU-9. Como visitante, quiero abrir la URL de la demo y validar un archivo
  desde el navegador, sin instalar nada, para probar la herramienta.
- HU-10. Como visitante, quiero ver un aviso claro de que estoy en modo demo y
  de que mis archivos se procesan en la nube, para subir solo lo que me
  convenga.

## Definiciones
- Modo nube (o modo demo): despliegue público en Vercel donde la petición
  llega a un servidor de Vercel, el backend corre en su runtime serverless y
  los archivos se procesan fuera del equipo del usuario; la interfaz lo
  identifica con el badge «Demo» y el banner de aviso.
- Modo local: arranque con uvicorn en el equipo del usuario, tal como hoy; los
  datos no salen de su equipo.
- Registro de cargas: fila de la tabla `uploads` con solo recuentos (total,
  válidas, inválidas y nombre del archivo); NUNCA guarda el contenido del
  archivo. En la nube vive en disco efímero y se descarta.
- MB: megabyte = 1.048.576 bytes (1024²), la definición que ya usa el backend
  (`10 * 1024 * 1024` en `upload.py`). Todas las cifras de MB de esta spec
  (límite, mensaje 413 y texto bajo el input) se leen en esta definición.
- Límite de subida: máximo de bytes que el backend acepta por petición; en
  nube lo marca el límite de cuerpo de Vercel (4,5 MB), por eso la demo baja
  el límite a 4 MB y en nube NUNCA se admite un límite efectivo mayor que
  4 MB (se recorta, RF-1).
- Entorno: la variable de entorno `VERCEL` (presente con valor no vacío en los
  despliegues de Vercel) que decide el modo; no se decide por hostname.
  `vercel dev` TAMBIÉN la define, incluso en desarrollo local, y por eso
  activa el modo nube al usar esa CLI (ver «Riesgos y limitaciones
  conocidas» para forzar el modo local).

## Requisitos funcionales
- RF-1: EL SISTEMA expone un endpoint `GET /api/v1/entorno` que devuelve
  `{"modo": "nube" | "local", "limite_mb": <entero>}`. EL valor de `modo` es
  "nube" SI la variable de entorno `VERCEL` existe con valor no vacío, y
  "local" en cualquier otro caso. EL valor de `limite_mb` se obtiene de la
  variable de entorno `MAX_UPLOAD_MB` con parseo ESTRICTO: se eliminan los
  espacios del principio y del final (strip) y el resto debe ser un número
  ENTERO ≥ 1; cualquier otro valor (`0`, `-3`, `4.5`, `4,5`, `abc`, vacío) se
  ignora y manda el defecto del modo (4 en nube, 10 en local). EN modo nube,
  `limite_mb` NUNCA supera 4: SI el valor válido es mayor que 4 (p. ej.
  `MAX_UPLOAD_MB=8`), ENTONCES se recorta (clamp) a 4 por el límite de cuerpo
  de Vercel (4,5 MB), quedando constancia en esta spec. EL SISTEMA NUNCA
  rechaza esta petición por configuración inválida. CUANDO el frontend
  carga, EL SISTEMA consulta este endpoint y actúa en consecuencia (RF-2,
  RF-3); SI la consulta falla, no responde o no trae JSON válido, ENTONCES la
  interfaz muestra el badge «Demo» y el banner (RF-2: ante la duda se avisa,
  nunca se oculta el aviso — decisión del usuario) y el límite real lo sigue
  aplicando siempre el backend.
- RF-2: CUANDO el entorno consultado es "nube", EL SISTEMA muestra en la
  interfaz un badge «Demo» junto al título de la página (con la ayuda al
  pasar el cursor «Modo demo: los archivos se procesan en la nube (Vercel),
  no en tu equipo.») y un banner discreto encima del formulario con el texto
  EXACTO «Modo demo (nube): los archivos que subas se procesan fuera de tu
  equipo, en los servidores de Vercel. No subas datos confidenciales.». SI el
  entorno es "local" Y la consulta responde correctamente, ENTONCES NO aparece
  ni el badge ni el banner en ningún momento; SI la consulta FALLA (RF-1),
  ENTONCES el badge y el banner se muestran igualmente: ante la duda se avisa
  y NUNCA se oculta el aviso de privacidad (decisión del usuario). SI el
  fallo ocurre con la interfaz en local, el texto de tamaño bajo el input
  (RF-3) usa el defecto de nube («Tamaño máximo del archivo: 4 MB.», opción
  más restrictiva y solo informativa: el límite real lo fija el backend con
  su 413).
- RF-3: EL SISTEMA acepta por archivo el número de megabytes (1024², ver
  «Definiciones») que indique `limite_mb` (RF-1): 4 MB en nube y 10 MB en
  local con la configuración por defecto. SI un archivo supera el límite
  vigente, ENTONCES responde 413 con el mensaje EXACTO «El archivo supera el
  límite de {N} MB.» (siendo {N} el límite vigente; en local por defecto sale
  «El archivo supera el límite de 10 MB.», idéntico al actual). EL SISTEMA
  muestra SIEMPRE visible, en ambos modos, el texto «Tamaño máximo del
  archivo: {N} MB.» con el mismo {N}, JUSTO DEBAJO del input de archivo del
  formulario de carga (ubicación exacta: no «en la ayuda», sino pegada al
  campo, siempre a la vista sin abrir nada). SI la interfaz muestra además un
  modal o textos de ayuda sobre la carga, ENTONCES usan el mismo {N} del
  texto (nunca cifras contradictorias).
- RF-4: EL SISTEMA trata el registro de la carga (RF-17 de la spec 003) como
  mejor esfuerzo (best-effort) EN AMBOS MODOS (local y nube): SI la escritura
  en la base de datos falla (disco lleno, sistema de archivos de solo
  lectura, disco efímero no escribible…), ENTONCES la validación se responde
  igual (200 con el resultado completo) y el fallo NO se convierte en un
  error 500 ni interrumpe el proceso. Justificación: UNA sola y única ruta
  de escritura para los dos modos, más robusta y testeable, en lugar de dos
  comportamientos distintos según el entorno (evita la contradicción entre
  RF-4 y RNF-4 detectada por QA).
- RF-5: EL SISTEMA define `FRONTEND_DIR` como configurable por variable de
  entorno (mismo patrón que `DATABASE_URL`), conservando el valor actual
  como defecto, y monta los archivos estáticos SOLO si ese directorio existe
  (comprobación `is_dir()` en el momento del montaje, no en tiempo de
  importación del módulo de configuración). SI `FRONTEND_DIR` apunta a un
  directorio inexistente (p. ej. el bundle de despliegue solo lleva el
  backend, o un test lo fija a un directorio inexistente), ENTONCES la
  aplicación se importa sin fallar y toda la API sigue respondiendo (la raíz
  "/" puede dar 404). EN modo local con el directorio por defecto, el montaje
  es el de hoy, sin cambios. Este mecanismo es el seam de prueba: se ejercita
  lanzando un SUBPROCESO con la variable de entorno fijada (import limpio de
  la aplicación), sin depender de estado del proceso de test.
- RF-6: EL SISTEMA se despliega en Vercel con artefactos de configuración, no
  convirtiendo el proyecto en una app npm: `vercel.json` (enrutado catch-all
  `/(.*)` a la función para replicar el comportamiento local de FastAPI,
  `maxDuration` 60 s, memoria 1024 MB y cabecera `X-Robots-Tag: noindex` en
  todas las rutas) más `api/index.py` (entrada ASGI que añade
  `data-processor-app/backend` al `sys.path` e importa la `app` de
  `app.main`, empaquetando con `includeFiles` el backend y el frontend). EL
  SISTEMA mantiene además, en la RAÍZ del repo, un manifiesto
  `requirements.txt` con una única línea: `-r data-processor-app/backend/requirements.txt`
  (referencia, NO copia: existe ya `data-processor-app/backend/requirements.txt`
  y así se conserva UNA sola fuente de versiones). Justificación: Vercel solo
  instala automáticamente las dependencias de Python desde un
  `requirements.txt` en la raíz del proyecto (no busca en subcarpetas); SIN
  ese manifiesto, `api/index.py` falla con `ModuleNotFoundError` (FastAPI,
  pandas, etc.) y la demo no arranca. EL HTML lleva además
  `<meta name="robots" content="noindex">` (RNF-3).
  EL SISTEMA mantiene `.gitignore` (`.venv/`, `__pycache__/`, `*.pyc`,
  `data.sqlite3`, `.pytest_cache/`, `*.log`) y `.vercelignore` para que ni el
  historial local ni la caché suban al repo ni al despliegue.
- RF-7: CUANDO la variable `VERCEL` está presente y no hay `DATABASE_URL`
  explícita, EL SISTEMA usa por defecto `sqlite:////tmp/data.sqlite3` (FS
  efímero de Vercel), de modo que `Base.metadata.create_all` del import no
  falla en el sistema de archivos de solo lectura. EN modo local, la base
  por defecto sigue siendo la de hoy (`backend/data.sqlite3`).
- RF-8: EL SISTEMA aplica un tope de 2.000 filas totales por archivo SOLO en
  modo nube (RF-1) y a TODA petición `/upload` en nube, INCLUIDAS las
  revalidaciones con el campo `ediciones` (mismo endpoint, misma comprobación
  antes de corregir/validar). El cómputo es de filas TOTALES de datos del
  archivo (sin contar la cabecera) medido TRAS `parse_file`; no importa cuántas
  filas sean «de interés» para la vista previa. CUANDO el modo es nube y una
  petición supera ese tope,
  ENTONCES el sistema responde 413 con el mensaje EXACTO «La demo en línea
  acepta hasta 2.000 filas por archivo. Para archivos más grandes, ejecuta la
  aplicación en local.» (siendo «2.000» el límite vigente formateado con
  separador de miles en español). El rechazo se aplica TRAS `parse_file`
  (cuando se conoce el número de filas de datos, sin contar la cabecera) y
  ANTES de `corregir_filas` y `validate_rows`, con lo que el archivo no se
  corrige ni se valida, sea cual sea la opción de autocorrección. EL código
  HTTP es **413** por coherencia con el rechazo por tamaño de bytes (RF-3):
  es el mismo caso («el archivo es demasiado grande para este entorno»), el
  frontend ya muestra el `detail` de un 413 con su mensaje y no abre una vía
  de error nueva (422 no se usa en los endpoints del proyecto). EN modo local
  NO existe tope de filas: solo rige el límite de 10 MB (RF-3) y la spec 003
  sigue íntegra. EL tope es configurable con la variable de entorno
  `MAX_FILAS_NUBE` (entero ≥ 1; por defecto 2000; un valor no válido se
  ignora y manda el defecto); en modo local la variable se ignora siempre.

## Requisitos no funcionales
- RNF-1: El despliegue no añade librerías nuevas, ni React, ni npm, ni ningún
  paso de build: la app que se despliega es la misma que corre en local
  (constitución art. 1, «stack fijo… sin React, sin npm, sin build»; el
  «sin librerías nuevas» es de `AGENTS.md`, sección «Límites», no de la
  constitución).
- RNF-2: Los 189 tests actuales (cifra medida por QA, la correcta) siguen en
  verde en local y se añaden tests de los RF de esta spec (detección de
  entorno, parseo y clamp de `MAX_UPLOAD_MB`, límite dinámico, tope de filas
  en nube, mejor esfuerzo del registro, import seguro y manifiesto de
  dependencias). Nota de alcance para el plan: este incluirá una TAREA
  DOCUMENTAL T0 (sin tocar código) que reconcilie la cifra 189 en
  `specs/003-auto-correccion/spec.md` (línea de Estado) y en
  `specs/003-auto-correccion/tasks.md` (donde aún figuran 191 y 193); T0 NO
  se ejecuta en esta fase de spec.
- RNF-3: La demo no debe indexarse, con dos comprobaciones separadas: (a) EN
  SIMULACIÓN local (`VERCEL=1` con uvicorn) es verificable el
  `<meta name="robots" content="noindex">` del HTML (más badge, banner, 413
  y `/api/v1/entorno`); (b) EN EL DESPLIEGUE REAL es donde se verifica la
  cabecera `X-Robots-Tag: noindex` (la inyecta el enrutado de Vercel desde
  `vercel.json`, no existe en uvicorn). Ambas son obligatorias (RF-6).
- RNF-4: El modo local no cambia en nada: mismas rutas, mismo límite de 10 MB
  y mensaje 413 idéntico, sin badge ni banner (con el entorno respondiendo),
  sin tope de filas, misma base de datos local y mismo comportamiento de las
  descargas y la vista previa (specs 001-003) — SALVO el registro de cargas
  best-effort (RF-4): en local, un fallo de la base de datos tampoco rompe
  ya la validación (es la única ruta que cambia, elegida a propósito para
  dejar UN solo comportamiento en los dos modos).
- RNF-5: Todos los textos visibles (badge, banner, ayuda, 413) van en
  español; los identificadores en inglés.

## Enmienda a la constitución y a AGENTS.md (requiere aprobación del usuario)
Texto propuesto para el artículo 5 de `docs/constitution.md` (sustituye al
actual):

> 5. **Los datos del usuario no salen del equipo (modo local); la demo
> aprobada en la nube es la única excepción.** En modo local (uvicorn) todo se
> procesa en el equipo del usuario: SQLite en disco, sin servicios externos ni
> telemetría. Excepción aprobada con la spec 004: el MODO DEMO (despliegue
> público en Vercel) procesa los archivos en los servidores de Vercel; la
> interfaz lo identifica con el badge «Demo» y un aviso visible, está pensado
> solo para demostraciones (nunca con datos confidenciales) y su base de datos
> es efímera (/tmp), guardando únicamente recuentos. Prohibido subir datos,
> claves o tokens a repos, logs o APIs de terceros.

Textos propuestos para `AGENTS.md`:

- En la sección «## Datos», el bullet de persistencia pasa a ser:
  «Persistencia en SQLite local (SQLAlchemy 2.0 / AsyncSession). En modo local
  nada sale del equipo.» y se añade un bullet nuevo:
  «Modo demo en la nube (spec 004): los despliegues públicos en Vercel
  procesan los archivos en los servidores de Vercel (badge «Demo» y aviso
  visible en la UI); SQLite es efímero (`/tmp`) y solo guarda recuentos.»
- En la sección «## Límites», la línea de prohibición pasa a ser:
  «🚫 Nunca: React, frameworks de frontend, npm ni un paso de build. Nunca
  subir datos de usuario a servicios externos ni persistirlos fuera del
  equipo (la demo de Vercel solo los procesa en memoria y los descarta; ver
  spec 004).»

## Contrato de la API (endpoint nuevo)
- `GET /api/v1/entorno` (sin autenticación) →

```json
{ "modo": "nube", "limite_mb": 4 }
```

  - `modo` (texto): `"nube"` o `"local"`, según la variable `VERCEL`.
  - `limite_mb` (entero ≥ 1): `MAX_UPLOAD_MB` con parseo estricto (strip +
    número entero ≥ 1); si no es válida, el defecto del modo (4 en nube, 10
    en local). EN nube se aplica además clamp: nunca devuelve más de 4 (p. ej.
    `MAX_UPLOAD_MB=8` en nube → `limite_mb: 4`; en local → `8`).
  - El endpoint no falla nunca por configuración inválida (RF-1); los campos
    son opcionales para un cliente que no los conozca (compatible por
    adición).

## Despliegue (prerrequisitos y pasos)
- Prerrequisitos: cuenta de Vercel con **plan Hobby (gratis) — ELEGIDO por el
  usuario para esta demo**, pensado por Vercel solo para proyectos
  personales/no comerciales: la demo es NO comercial. (Si en el futuro la
  demo o el proyecto se usan con fines comerciales o de empresa, Vercel
  exige el **plan Pro**, de pago; cambiar de plan NO modifica el código ni la
  spec, solo la cuenta.) Además: repo en GitHub u otro proveedor soportado
  con remoto configurado (el repo ya es git) o, como alternativa, la CLI de
  Vercel con sesión iniciada.
- Pasos (integración Git, recomendada):
  1. Añadir `.gitignore` y `.vercelignore` (RF-6) y confirmar que
     `data.sqlite3` y `__pycache__/` NO se suben.
  2. Añadir `requirements.txt` en la RAÍZ del repo (RF-6), más `vercel.json`
     y `api/index.py`; sin ese manifiesto Vercel no instala las dependencias
     y la función falla con `ModuleNotFoundError`.
  3. Importar el repo en Vercel (o `vercel link` con la CLI) y desplegar la
     rama principal (`vercel --prod` en CLI).
  4. Variables de entorno: ninguna obligatoria (`VERCEL` la define Vercel;
     `MAX_UPLOAD_MB` y `MAX_FILAS_NUBE` son opcionales). `DATABASE_URL` NO se
     define (RF-7 aplica).
  5. Verificar en SIMULACIÓN local (`VERCEL=1` con uvicorn): meta robots
     noindex, badge «Demo», banner, texto de tamaño bajo el input, 413 de
     bytes y de filas y `/api/v1/entorno`.
  6. Verificar en la URL REAL del despliegue: badge «Demo», banner, límite
     4 MB, cabecera `X-Robots-Tag: noindex` y que una validación completa
     funciona (autocorrección, edición y descargas) sin `ModuleNotFoundError`.

## Casos límite
- `VERCEL=1` sin `MAX_UPLOAD_MB` → `{"modo": "nube", "limite_mb": 4}`; un
  archivo de 4,1 MB → 413 «El archivo supera el límite de 4 MB.».
- Sin `VERCEL` → `{"modo": "local", "limite_mb": 10}`; un archivo de 9 MB
  pasa y uno de 11 MB → 413 «El archivo supera el límite de 10 MB.» (mensaje
  idéntico al actual).
- `MAX_UPLOAD_MB` con parseo estricto: `MAX_UPLOAD_MB=8` → 8 en LOCAL y clamp
  a 4 en NUBE (nube nunca admite más de 4); `" 8 "` (con espacios) → 8
  (strip); `0`, `-3`, `4.5`, `4,5`, `abc` o vacío → se ignora y manda el
  defecto del modo (4 en nube, 10 en local); nunca un 500.
- La base de datos no admite escribir (disco lleno o de solo lectura) → la
  validación responde 200 con el resultado completo y solo se pierde el
  registro (RF-4).
- `FRONTEND_DIR` fijada por variable de entorno a un directorio inexistente
  (RF-5) → la aplicación se importa sin error (subproceso con import limpio),
  la API responde y "/" da 404; en local, con el directorio por defecto
  presente, todo es el de hoy.
- La consulta a `/api/v1/entorno` falla, no responde o no trae JSON válido →
  la interfaz muestra el badge «Demo» y el banner (nunca se oculta el aviso
  en caso de duda, RF-1/RF-2) y el texto de tamaño bajo el input usa el
  defecto de nube («Tamaño máximo del archivo: 4 MB.», solo informativa); la
  validación sigue funcionando porque el límite lo aplica el backend (RF-3).
- `vercel dev` define `VERCEL=1` → en desarrollo local con esa CLI la app
  arranca en MODO NUBE (badge, banner, 4 MB y tope de filas). Para forzar el
  modo local se define `VERCEL=` (valor vacío) en el `.env` del proyecto o se
  arranca con uvicorn directamente (ver «Riesgos»).
- En nube, dos validaciones simultáneas → ambas responden con su resultado;
  sus registros pueden perderse (efímero + mejor esfuerzo), sin mezclarse.
- Archivo que pasa el límite pero trae esquema inválido → manda el orden de
  hoy: el 413 del tamaño se comprueba ANTES de parsear (igual que ahora).
- En nube, archivo con EXACTAMENTE 2.000 filas de datos → pasa (200) y se
  valida completo.
- En nube, archivo con 2.001 filas de datos → 413 «La demo en línea acepta
  hasta 2.000 filas por archivo. Para archivos más grandes, ejecuta la
  aplicación en local.»; no se corrige ni se valida nada (RF-8), con
  autocorrección activada o no.
- En nube, REVALIDACIÓN de una fila con el campo `ediciones` sobre un archivo
  de 2.500 filas → 413 con el mismo mensaje del tope: el tope aplica a toda
  petición `/upload` (RF-8), no solo a la primera carga; en local esa misma
  revalidación se procesa con normalidad.
- Sin `VERCEL` (modo local), archivo con 2.001 filas → 200: el mensaje del
  tope NO se dispara nunca en local aunque exista `MAX_FILAS_NUBE`.
- En nube con `MAX_FILAS_NUBE=500` → el tope pasa a 500 (501 filas → 413 con
  «…hasta 500 filas…»); con `MAX_FILAS_NUBE` en `0`, `-10` o `abc` → se
  ignora y manda el defecto 2000.
- En nube, archivo de 1.500 filas pero de 5 MB → manda el 413 de bytes
  (RF-3, comprobado ANTES de parsear); en nube, archivo de 2.500 filas de 1 MB
  → manda el 413 de filas (RF-8, tras parsear): cada límite se aplica en su
  momento y ninguno anula al otro.
- En nube, archivo dentro del tope (≤2.000 filas) y con esquema de MUCHAS
  columnas o celdas largas → la respuesta de la vista previa puede seguir
  superando el tamaño permitido por Vercel y fallar (riesgo residual, ver
  "Riesgos y limitaciones conocidas").

## Riesgos y limitaciones conocidas (demo)
- Respuesta grande en nube: **MITIGADO con el tope de 2.000 filas solo en
  nube (RF-8, decisión del usuario «tope de 2.000 filas solo en nube»)**:
  archivos demasiado grandes se rechazan con un mensaje claro antes de
  corregir/validar, con lo que desaparece el caso peor (archivos enormes con
  respuestas gigantes). **Riesgo residual**: dentro del tope, un esquema con
  MUCHAS columnas o celdas largas puede hacer que la vista previa o la
  descarga corregida sigan superando el tamaño de respuesta que admite
  Vercel (~4,5 MB) y la petición falle; se vigila durante la demo y solo
  afecta a la nube (en local no hay tope ni límite de respuesta). NO se
  añade ningún tope de columnas ni de ancho de celda (fuera de alcance):
  el tope de filas (RF-8) es la única mitigación que se aplica.
- Sin autenticación ni rate limiting: la URL pública es libre; el usuario
  ACEPTA explícitamente el abuso posible (ver «Dudas cerradas»): consume su
  cuota de Vercel y puede degradar la demo; fuera de alcance de esta spec y
  coherente con que el plan Hobby exige que la demo sea no comercial.
- Archivo hostil («bomba zip» en `.xlsx`): una hoja de cálculo comprimida
  puede expandir en RAM a muchísimo más que su tamaño en disco (pandas/openpyxl
  la expanden al leerla), dentro del presupuesto de 1024 MB y 60 s de la
  función. ACEPTADO para la demo pública sin antiabuso (misma decisión que
  el rate limiting): se mitiga parcialmente con el límite de 4 MB de entrada
  y el tope de filas (RF-8); si abusa, consume cuota del plan.
- Estáticos servidos por la función con catch-all: cada carga de
  `index.html`, `app.js`, `styles.css` o componente consume una INVOCACIÓN
  de la función (aunque FastAPI los sirva desde caché del FS de la función)
  y encarece los cold starts de la demo. ACEPTADO por simplicidad (replica
  el comportamiento local sin duplicar rutas); alternativa descartada:
  declarar los estáticos en `vercel.json` uno a uno (más configuración y
  riesgo de desincronización con el frontend real).
- `vercel dev` define `VERCEL=1`: la CLI de desarrollo local activa el MODO
  NUBE (banner, 4 MB, tope de filas) incluso en el equipo del desarrollador.
  Mitigado documentando el forzado a modo local: `VERCEL=` (vacío) en `.env`
  o arrancar con uvicorn sin `vercel dev` (ver casos límite).
- Runtime de Vercel: su Python no es la 3.14 local; la primera versión que
  compruebe el despliegue debe verificar que backend y dependencias arrancan
  (mismo código, otro runtime).
- Historial de cargas: en la nube es efímero y puede perderse en cualquier
  momento; nadie debe depender de él (solo guarda recuentos).

## Fuera de alcance
- Login, cuentas, autenticación o control de acceso de ningún tipo.
- Postgres u otra base de datos persistente (la nube solo necesita el registro
  efímero de recuentos).
- Rate limiting, captcha, WAF o cualquier protección antiabuso: el usuario
  lo acepta de forma explícita (URL libre; ver «Dudas cerradas»).
- Tope de columnas, de ancho de celda o de tamaño de respuesta en la nube:
  dentro del tope de filas (RF-8), la respuesta se manda tal cual.
- Uso real de la herramienta con datos confidenciales o de producción.
- Migración o conservación del histórico de cargas de la nube.
- Entornos múltiples con configuraciones distintas (preview/producción),
  dominio personalizado y certificados a medida.
- Cambios en la lógica de validación, autocorrección, edición o descargas
  (specs 001-003 intactas).

## Criterios de finalización
- En LOCAL (uvicorn, con el entorno respondiendo): no se ve ni el badge «Demo»
  ni el banner en ningún momento; el límite sigue siendo 10 MB con su mensaje
  413 idéntico al actual; el texto «Tamaño máximo del archivo: 10 MB.» está
  SIEMPRE visible justo debajo del input de archivo; NO hay tope de filas
  (un archivo de 2.001 o más filas se valida completo con 200 y el mensaje de
  la demo no aparece jamás); un fallo de la base de datos NO rompe la
  validación (registro best-effort, RF-4); toda la funcionalidad de las
  specs 001-003 funciona igual y `python -m pytest` pasa completo en verde
  (189 actuales + los nuevos de esta spec).
- En NUBE, comprobable EN SIMULACIÓN local (`VERCEL=1` con uvicorn): el badge
  «Demo» y el banner con su texto exacto se ven junto al formulario; el
  límite es 4 MB y un archivo mayor responde 413 «El archivo supera el límite
  de 4 MB.»; el texto «Tamaño máximo del archivo: 4 MB.» está justo debajo
  del input; `/api/v1/entorno` responde `{"modo": "nube", "limite_mb": 4}`;
  un archivo de 2.000 filas pasa y uno de 2.001 responde 413 «La demo en
  línea acepta hasta 2.000 filas por archivo. Para archivos más grandes,
  ejecuta la aplicación en local.» sin llegar a corregir ni validar; el HTML
  lleva el meta robots noindex.
- En NUBE, comprobable SOLO EN EL DESPLIEGUE REAL: la validación completa de
  archivos dentro de los límites funciona (autocorrección, edición manual,
  vista previa y descargas) SIN `ModuleNotFoundError` (gracias al
  `requirements.txt` de la raíz, RF-6); las respuestas llevan la cabecera
  `X-Robots-Tag: noindex`; un fallo de la base de datos no rompe la
  validación.
- El repo queda con `.gitignore` y `.vercelignore` (sin `data.sqlite3` ni
  `__pycache__/` subidos), con `requirements.txt` en la raíz (RF-6) y con
  `vercel.json` + `api/index.py`; el proyecto sigue sin npm y sin pasos de
  build; el despliegue es en el plan Hobby de Vercel (demo no comercial).

## Pruebas
- Nuevos tests de backend (pytest, services/endpoints, sin HTTP externo):
  - `tests/test_entorno.py`: `VERCEL` presente, ausente y vacío → `modo`;
    `MAX_UPLOAD_MB` con parseo estricto: válida (`8`, `" 8 "` con espacios) →
    `limite_mb` correcto; en nube con `8` → clamp a 4; `0`, `-3`, `4.5`,
    `abc` o vacío → defecto del modo (4/10); el endpoint nunca devuelve 500;
    JSON de respuesta con los dos campos.
  - `tests/test_upload_endpoint.py` ampliado: 413 con mensaje dinámico en
    nube («El archivo supera el límite de 4 MB.») y en local («…de 10 MB.»);
    registro mejor esfuerzo EN AMBOS MODOS (sesión que falla al hacer commit
    → la respuesta sigue siendo 200 completa).
  - Tope de filas en nube (RF-8): en modo nube, un archivo de 2.000 filas →
    200; de 2.001 filas → 413 con el mensaje exacto de la demo y sin haber
    llamado a corregir/validar; una REVALIDACIÓN con `ediciones` sobre un
    archivo de 2.500 filas en nube → 413 con el mismo mensaje; en modo local
    (sin `VERCEL`), 2.001 filas → 200 y el mensaje del tope NO aparece;
    `MAX_FILAS_NUBE` válida cambia el tope y un valor no válido (`0`, `-10`,
    `abc`) cae al defecto 2000.
  - `tests/test_main.py` (o equivalente): importar la aplicación en un
    SUBPROCESO con la variable de entorno `FRONTEND_DIR` fijada a un
    directorio inexistente no lanza, la API responde y "/" da 404 (seam
    RF-5); con el valor por defecto, el montaje es el de hoy.
  - `tests/test_despliegue.py` (coherencia de repositorio, sin HTTP): existe
    `requirements.txt` en la raíz y referencia
    `data-processor-app/backend/requirements.txt` (RF-6); evita regresiones
    que romperían el despliegue con `ModuleNotFoundError`.
  - Los 189 tests actuales siguen pasando sin modificarse (RNF-2; RNF-4 con
    el matiz del registro best-effort).
- Verificación en navegador (sin frameworks de JS, contra la API real):
  - Local: sin badge/banner, texto «Tamaño máximo del archivo: 10 MB.»
    visible justo debajo del input, una validación completa y un archivo de
    más de 2.000 filas validado sin ningún aviso de tope.
  - Nube (simulación `VERCEL=1`): badge «Demo», banner con su texto, texto
    «…4 MB.» bajo el input, 413 al subir un archivo mayor, subir un archivo
    de >2.000 filas muestra «La demo en línea acepta hasta 2.000 filas por
    archivo…», meta robots comprobado; a 1280px y 375px el badge y el banner
    se ven bien (RF-2, RNF-5). En el DESPLIEGUE REAL se comprueba además la
    cabecera `X-Robots-Tag: noindex` (RNF-3).

## Dudas cerradas y decisiones validadas
- Demo pública SIN login en internet abierto (decisión del usuario, textual:
  «adelante: demo pública sin login»): se asume el uso público de la URL; si
  en el futuro hace falta restricción, será otra spec.
- Nube pública en Vercel (decisión del usuario): la herramienta se procesa
  fuera del equipo SOLO en el modo demo; el modo local sigue intacto.
- Enmienda de privacidad (decisión del usuario, textual: «los datos se
  procesan en servidores de Vercel… el objetivo es una demo pública, no uso
  real con datos confidenciales»): el artículo 5 y AGENTS.md se adaptan con el
  texto de esta spec.
- Límite de 4 MB en nube (para no chocar con el tope de 4,5 MB del cuerpo de
  Vercel) y de 10 MB en local: configurables con `MAX_UPLOAD_MB` sin tocar
  código.
- Enrutado catch-all a la función (`/(.*)` → `api/index.py`): replica el
  comportamiento local (FastAPI sirve API y estáticos) sin duplicar
  configuración de rutas.
- Registro de cargas como mejor esfuerzo EN AMBOS MODOS: la validación NUNCA
  depende de la base de datos (RF-4); una sola ruta para local y nube, más
  robusta (corrige la contradicción RF-4/RNF-4 señalada por QA).
- Aceptación explícita de la URL pública SIN ninguna protección antiabuso
  (decisión del usuario, literal: «acepta explícitamente la URL pública sin
  ninguna protección antiabuso: sin login, sin rate limiting, sin captcha;
  asume que el abuso consume su cuota de Vercel y puede afectar a la demo»):
  queda registrado el riesgo y su aceptación en «Riesgos».
- Si `GET /api/v1/entorno` FALLA, la interfaz muestra el banner de privacidad
  y el badge «Demo» IGUALMENTE (decisión del usuario: «nunca ocultar el
  aviso en caso de duda»): RF-1/RF-2 y sus casos límite quedan ajustados; el
  límite real lo fija siempre el backend.
- Manifiesto `requirements.txt` en la RAÍZ del repo (hallazgo bloqueante de
  QA): una línea `-r data-processor-app/backend/requirements.txt`; Vercel
  solo instala dependencias desde la raíz y sin él `api/index.py` falla con
  `ModuleNotFoundError`; se elige la referencia `-r` para no duplicar
  versiones (una sola fuente de verdad).
- MB = 1.048.576 bytes (1024²), la definición que ya usa `upload.py`; todos
  los textos y mensajes de MB (413 y «Tamaño máximo del archivo: {N} MB.»)
  se leen así.
- Compatibilidad con la spec 003: los textos de «10 MB» que aquella fija
  quedan ACOTADOS AL MODO LOCAL (idénticos, sin cambios); en el modo nube
  rige 4 MB, según RF-1/RF-3. Las 189 pruebas de 003 siguen intactas.
- SQLite efímero en `/tmp` solo para el registro de recuentos: el contenido
  de los archivos NUNCA se persiste, ni en local ni en nube.
- Tope de 2.000 filas SOLO en nube (decisión del usuario, textual:
  «Tope de 2.000 filas solo en nube»): en la demo se rechazan los archivos
  de más de 2.000 filas con un mensaje claro en español antes de
  corregir/validar; el modo local NO tiene tope de filas (spec 003 intacta).
  Se implementa como `MAX_FILAS_NUBE` (defecto 2000, ignorada en local) con
  413 por coherencia con el límite de bytes; aplica a toda petición
  `/upload`, incluidas las revalidaciones con `ediciones` (RF-8).
- Detección de entorno por la variable `VERCEL` (no por hostname): es lo que
  Vercel garantiza en sus despliegues y es testeable con `monkeypatch`;
  `vercel dev` TAMBIÉN la define y por eso activa el modo nube en
  desarrollo local (documentado en «Riesgos» con la forma de forzar modo
  local: `VERCEL=` vacío en `.env` o uvicorn directo).
- Plan de Vercel: **Hobby (gratis) — decisión del usuario, textual: «Hobby
  (gratis, demo)»**: la demo pública es NO comercial; Vercel restringe Hobby
  a proyectos personales/no comerciales. Un uso comercial o de empresa
  requeriría el plan Pro (de pago), lo que NO cambia el código ni la spec.

## Decisiones pendientes (dependen del usuario)
Ninguna: las que quedaban están cerradas en «Dudas cerradas y decisiones
validadas» — tope de 2.000 filas solo en nube (RF-8), plan Hobby no
comercial, aceptación explícita de la URL pública sin antiabuso y aviso
visible (badge + banner) aunque falle `/api/v1/entorno`.
