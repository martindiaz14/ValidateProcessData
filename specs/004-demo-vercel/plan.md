# Plan — Spec 004: Demo pública en la nube (Vercel)

Punto de partida (MEMORY.md + código verificado en esta sesión): **189 tests en
verde**; backend FastAPI + SQLAlchemy 2.0 con `Session` síncrona; frontend
vanilla sin build; repo git publicado en GitHub (`main`); NO existen
`vercel.json`, `api/`, `.gitignore`, `.vercelignore` ni `README.md` en la raíz;
`data.sqlite3` y `__pycache__/` están en el árbol local.

Hechos de código verificados (los que toca este plan):
- `app/core/config.py`: `DATABASE_URL` sobrescribible por env (líneas 10-12);
  `FRONTEND_DIR` es constante (línea 15).
- `app/core/database.py`: `engine` y `create_engine` se ejecutan EN EL IMPORT
  del módulo (línea 8), leyendo `DATABASE_URL` importado de `config`.
- `app/main.py`: `Base.metadata.create_all` en el import (línea 10) y
  `app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True))`
  incondicional (línea 19).
- `app/api/v1/api.py`: solo monta `upload.router` (7 líneas).
- `app/api/v1/endpoints/upload.py`: `MAX_BYTES = 10 * 1024 * 1024` (línea 22),
  lectura `MAX_BYTES + 1` y 413 con texto fijo «El archivo supera el límite de
  10 MB.» (líneas 59-61); registro con `session.add/commit` SIN protección
  (líneas 102-110); ningún test existente depende de `MAX_BYTES` (verificado
  con grep: solo lo usa `upload.py`).
- `frontend/index.html`: sin meta robots; el título vive en el `<h1>` del
  header; el formulario se monta en `<section id="uploader">`.
- `frontend/app.js`: orquesta todo (`renderFileUploader` al cargar, fetch de
  `/api/v1/upload`); pinta avisos/errores en sus propias secciones.
- `frontend/components/FileUploader.js`: input de archivo sin ningún texto de
  tamaño; `HelpModal.js`: el modal de ayuda NO menciona ningún tamaño de
  archivo (verificado: no hay cifras de MB), así que NO se toca.

Notas de plantilla:
- Ninguna función nueva necesita la fecha actual (`hoy`) como parámetro: toda
  la lógica depende de variables de entorno y del archivo subido; es
  determinista y se prueba sin reloj.
- Tests de backend: `python -m pytest` desde `data-processor-app/backend/`.
  No aplica `node --test` ni ningún framework de JavaScript: la constitución
  (regla 4) y RNF-5 piden verificar el frontend en el navegador contra la API
  real, sin frameworks de testing en JS.
- TODAS las lecturas de entorno nuevas (`VERCEL`, `MAX_UPLOAD_MB`,
  `MAX_FILAS_NUBE`) se hacen EN TIEMPO DE LLAMADA (funciones), nunca como
  constantes de importación: eso permite probarlas con `monkeypatch.setenv`
  sin recargar módulos.

## Archivos y responsabilidades (y RF que cubre cada uno)

- `backend/app/core/config.py` → detección de modo nube y límites en tiempo de
  llamada (`es_modo_nube`, `limite_mb`, `limite_filas_nube`), parseo estricto
  de `MAX_UPLOAD_MB`/`MAX_FILAS_NUBE`, `FRONTEND_DIR` sobrescribible por env y
  `DATABASE_URL` con sucursal `/tmp` cuando hay `VERCEL` (RF-1, RF-5, RF-7,
  RF-8 base).
- **Nuevo** `backend/app/api/v1/endpoints/entorno.py` → endpoint
  `GET /api/v1/entorno` con el contrato `{"modo","limite_mb"}`; sin BD y sin
  posibilidad de fallar por configuración inválida (RF-1).
- `backend/app/api/v1/api.py` → incluye el router de `entorno` además de
  `upload` (RF-1).
- `backend/app/schemas/quality.py` → modelo `EntornoRespuesta` (respuesta del
  endpoint nuevo, documentada en OpenAPI) (RF-1).
- `backend/app/api/v1/endpoints/upload.py` → límite de bytes dinámico con
  mensaje 413 «El archivo supera el límite de {N} MB.», tope de 2.000 filas
  en nube tras `parse_file` (413 con el texto exacto de la spec), y registro
  de carga best-effort en ambos modos (try/except + rollback + log; nunca un
  500 por BD) (RF-3, RF-4, RF-8).
- `backend/app/main.py` → montaje de estáticos condicionado a `is_dir()` en el
  momento del montaje (import seguro sin frontend) (RF-5).
- `frontend/index.html` → `<meta name="robots" content="noindex">`, contenedor
  del badge «Demo» junto al `<h1>` y contenedor del banner encima de
  `#uploader` (RF-2, RF-3, RNF-3).
- `frontend/app.js` → consulta `GET /api/v1/entorno` al cargar con fallback
  conservador (si falla: badge + banner + 4 MB), pintado del badge/banner y
  paso del límite vigente al formulario (RF-1, RF-2, RF-3).
- `frontend/components/FileUploader.js` → texto «Tamaño máximo del archivo:
  {N} MB.» SIEMPRE visible justo debajo del input de archivo + función
  exportada para actualizar el {N} cuando responda el entorno (RF-3).
- `frontend/components/HelpModal.js` → **SIN CAMBIOS**: hoy no menciona
  ningún tamaño de archivo; no se inventan cifras (RF-3, coherencia).
- **Nuevos, en la RAÍZ del repo**: `requirements.txt` (referencia
  `-r data-processor-app/backend/requirements.txt`), `vercel.json`
  (tres claves: `functions` para `api/index.py` con `maxDuration` 60,
  memoria 1024 e `includeFiles` backend+frontend; `rewrites` catch-all a la
  función; `headers` con `X-Robots-Tag: noindex`), `api/index.py` (entrada
  ASGI), `.gitignore` y `.vercelignore` (RF-6, RNF-1, RNF-3).
- Tests: **nuevos** `tests/test_entorno.py`, `tests/test_main.py`,
  `tests/test_despliegue.py`; **ampliado** `tests/test_upload_endpoint.py`.
  Los archivos nuevos están pre-aprobados al aprobar este plan (AGENTS.md pide
  preguntar antes de crear archivos).

## Enfoque técnico

### Backend: `config.py` (RF-1, RF-5, RF-7, RF-8)

Convierte las constantes de entorno en funciones puras y pequeñas, con los
valores por defecto de la spec:

```python
# app/core/config.py (pseudocódigo)
MB = 1024 * 1024                      # 1 MB = 1.048.576 bytes (Definiciones)
LIMITE_MB_LOCAL = 10
LIMITE_MB_NUBE_TOPE = 4               # clamp: cuerpo de Vercel = 4,5 MB
LIMITE_FILAS_NUBE_DEFECTO = 2000

def _entero_estricto(valor) -> Optional[int]:
    """strip + número entero ≥ 1; si no → None (nunca lanza)."""

def es_modo_nube(env=None) -> bool:
    """VERCEL existe con valor no vacío (lectura en tiempo de llamada)."""

def limite_mb(env=None) -> int:
    """Parseo estricto de MAX_UPLOAD_MB; defecto 4 (nube) / 10 (local);
    en nube, clamp a LIMITE_MB_NUBE_TOPE."""

def limite_filas_nube(env=None) -> int:
    """Parseo estricto de MAX_FILAS_NUBE; defecto 2000. Solo lo consulta
    upload.py cuando es_modo_nube() es true (en local se ignora)."""

def _url_base_datos(env, base_dir) -> str:
    """DATABASE_URL explícita → se respeta; VERCEL no vacío →
    sqlite:////tmp/data.sqlite3; si no → backend/data.sqlite3 (de hoy)."""

DATABASE_URL = _url_base_datos(os.environ, BASE_DIR)   # import (lo pide database.py)
FRONTEND_DIR = Path(os.environ.get("FRONTEND_DIR") or (BASE_DIR.parent / "frontend"))
```

`DATABASE_URL` se queda en tiempo de import porque `database.py` crea el
`engine` al importar (línea 8) y el motor no se puede mover sin tocar la
inicialización de la BD; su lógica vive en la pura `_url_base_datos`, así que
se prueba sin recargar nada. El resto (`es_modo_nube`, `limite_mb`,
`limite_filas_nube`) se lee en tiempo de llamada desde `upload.py` y desde el
endpoint `entorno`, y por eso es testeable con `monkeypatch.setenv` sobre el
`TestClient` de módulo que ya usan los tests.

### Backend: endpoint `GET /api/v1/entorno` (RF-1)

Archivo nuevo `endpoints/entorno.py` con su propio router (mismo patrón que
`upload.py`), registrado en `api.py`. Respuesta con el modelo
`EntornoRespuesta` de `schemas/quality.py` (`modo: Literal["nube","local"]`,
`limite_mb: int`), que solo llama a `es_modo_nube()` y `limite_mb()`: sin BD,
sin `Depends`, sin parámetros de entrada; una configuración inválida jamás
produce un error (los helpers devuelven el defecto).

### Backend: `upload.py` (RF-3, RF-4, RF-8)

Tres cambios quirúrgicos sobre el flujo actual (los números de paso son los
del docstring vigente):

1. **Límite de bytes dinámico (paso 2)**: se elimina la constante
   `MAX_BYTES`; en su lugar, al principio del handler:
   `limite_actual = limite_mb()` y lectura de `limite_actual * MB + 1`. El
   413 pasa a ser `detail=f"El archivo supera el límite de {limite_actual}
   MB."` — en local por defecto sale «…de 10 MB.», idéntico al actual (RNF-4
   y las 189 pruebas intactas). El límite de bytes se comprueba ANTES de
   parsear (orden actual preservado, caso límite de la spec).
2. **Tope de filas en nube (paso 3.5, nuevo)**: justo DESPUÉS de
   `parse_file` y ANTES de `_parsear_ediciones`/`corregir_filas`:
   `if es_modo_nube() and len(rows) > limite_filas_nube():` → 413 con
   `detail="La demo en línea acepta hasta {N} filas por archivo. Para
   archivos más grandes, ejecuta la aplicación en local."`, donde
   `{N}` se formatea con separador de miles español («2.000», «500») mediante
   una auxiliar pura `_formatear_miles(n)` (`f"{n:,}".replace(",", ".")`).
   Como el rechazo ocurre antes de corregir/validar, la respuesta NUNCA llega
   a `corregir_filas`, `validate_rows` ni al registro (RF-8: aplica a toda
   petición `/upload`, incluidas las revalidaciones con `ediciones`, porque
   todas pasan por `parse_file`).
3. **Registro best-effort (paso 8)**: `session.add/commit` se envuelve en
   `try/except Exception` con `session.rollback()` y un
   `logging.getLogger(__name__).warning(...)`; el `return result` se queda
   fuera del try, así un fallo de BD NUNCA convierte un 200 en un 500 (RF-4,
   ambos modos). El registro normal (BD escribible) sigue funcionando igual.

### Backend: `main.py` (RF-5)

Sustituir el montaje incondicional por:

```python
# html=True sirve index.html al acceder a "/"; solo se monta si existe
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
```

`FRONTEND_DIR` ya es configurable por env (T3): en local con el valor por
defecto el comportamiento es el de hoy; si apunta a un directorio inexistente
(bundle sin frontend), la app se importa y la API responde (la raíz da 404).

### Frontend: `index.html` (RF-2, RF-3, RNF-3)

- `<meta name="robots" content="noindex" />` junto a la meta de viewport.
- Contenedor del badge, dentro del `<h1>` (que ya es `flex items-center
  gap-2`): `<span id="badge-demo" class="hidden ...">Demo</span>` — oculto
  por defecto: en local NUNCA aparece.
- Contenedor del banner, como `<section id="banner-demo" class="hidden">`
  justo ANTES de `<section id="uploader">` (spec: «encima del formulario»).

### Frontend: `app.js` (RF-1, RF-2, RF-3)

Nuevo flujo de arranque (mismo patrón de pintado que `mostrarAviso`):

- Tras montar el formulario, `consultarEntorno()` hace
  `fetch("/api/v1/entorno")` y:
  - **Éxito con `modo === "local"`**: no pinta badge ni banner (se quedan en
    `hidden`) y fija `limiteMbActual = datos.limite_mb` (p. ej. 10).
  - **Éxito con `modo === "nube"`**: pinta badge «Demo» (con `title` = «Modo
    demo: los archivos se procesan en la nube (Vercel), no en tu equipo.») y
    el banner con el texto EXACTO «Modo demo (nube): los archivos que subas
    se procesan fuera de tu equipo, en los servidores de Vercel. No subas
    datos confidenciales.»; fija `limiteMbActual = datos.limite_mb` (4).
  - **Fallo (rechazo, red caída o JSON inválido)**: pinta badge y banner
    IGUALMENTE (fallback conservador: ante la duda se avisa, RF-2) y fija
    `limiteMbActual = 4` (defecto de nube, el más restrictivo).
- En los tres casos llama después a
  `actualizarLimiteSubida(limiteMbActual)` (exportada por `FileUploader.js`).
- Estado inicial de la página: el badge y el banner arrancan ocultos y el
  texto bajo el input arranca con el conservador «4 MB» (se corrige en
  milisegundos cuando el entorno responde; es el mismo criterio que el
  fallback, RF-2/RF-3).

### Frontend: `FileUploader.js` (RF-3)

- Debajo del `<input id="file-datos">`, dentro del mismo `<label>` o justo
  después: `<p id="limite-tamano" class="mt-1 text-xs text-slate-500
 ">Tamaño máximo del archivo: 4 MB.</p>` (texto inicial conservador).
- Nueva función exportada `actualizarLimiteSubida(n)` que localiza
  `#limite-tamano` y pinta `Tamaño máximo del archivo: ${n} MB.` (nunca
  formatos distintos; el número que llega ya es el vigente del backend).
- Sin cambios en el resto del formulario (el campo de límite de la vista
  previa se eliminó en la spec 003 y NO vuelve).

### Frontend: `HelpModal.js` — SIN CAMBIOS

Verificado: el modal no menciona ningún tamaño de archivo; no se añade nada
(RF-3: «nunca cifras contradictorias» — la única cifra vive bajo el input).

### Artefactos de despliegue, en la RAÍZ del repo (RF-6, RNF-1)

- `requirements.txt` (raíz), una sola línea:
  `-r data-processor-app/backend/requirements.txt`. Vercel solo instala
  dependencias desde la raíz; la referencia `-r` evita duplicar versiones
  (una sola fuente de verdad). Sin él: `ModuleNotFoundError` en
  `api/index.py` (hallazgo bloqueante de QA).
- `vercel.json` (contenido objetivo, sujeto a la verificación del T7):

```json
{
  "version": 2,
  "functions": {
    "api/index.py": {
      "maxDuration": 60,
      "memory": 1024,
      "includeFiles": [
        "data-processor-app/backend/app/**/*.py",
        "data-processor-app/backend/requirements.txt",
        "data-processor-app/frontend/**"
      ]
    }
  },
  "rewrites": [{ "source": "/(.*)", "destination": "/api/index" }],
  "headers": [
    { "source": "/(.*)", "headers": [{ "key": "X-Robots-Tag", "value": "noindex" }] }
  ]
}
```

  - **Por qué catch-all**: FastAPI ya enruta API y estáticos localmente con
    el mismo orden (API primero, estático después); replicar eso con UNA
    reescritura que va todo a la función evita duplicar el mapa de rutas y
    desincronizarse del frontend real (la alternativa de declarar estáticos
    uno a uno está descartada en la spec y aquí).
  - **Por qué `rewrites` y no `routes`**: `routes` es LEGACY y no puede
    combinarse con `headers` en el mismo `vercel.json` (la cabecera
    `X-Robots-Tag: noindex` quedaría ignorada/inválida), mientras que
    `rewrites` sí convive con `headers`. Por eso `vercel.json` queda como
    `functions` + `rewrites` + `headers`, con `includeFiles` dentro de
    `functions` para `api/index.py`.
  - **Por qué `includeFiles` con positivos explícitos**: los globs solo
    empaquetan `.py` del backend, su requirements y el frontend; así NO viajan
    `data.sqlite3`, `__pycache__/`, tests ni ejemplos al bundle de la función
    (exclusión por omisión, más segura que negar globs).
  - **Orden de rutas**: `app.include_router(api_router, prefix="/api/v1")`
    sigue ANTES del montaje estático en `main.py`, y la `rewrites` de Vercel
    reenvía `/api/v1/...` a la misma app: el orden local se replica sin
    tocar la lógica.
- `api/index.py` (entrada ASGI para el runtime de Python de Vercel):

```python
"""Entrada ASGI de Vercel: expone la app FastAPI del backend."""
import sys
from pathlib import Path

# Raíz del bundle: <proyecto>/api/index.py → <proyecto>/data-processor-app/backend
BACKEND = Path(__file__).resolve().parent.parent / "data-processor-app" / "backend"
sys.path.insert(0, str(BACKEND))

from app.main import app  # noqa: E402  (el path debe montarse antes del import)
```

- `.gitignore` (raíz): `.venv/`, `__pycache__/`, `*.pyc`, `data.sqlite3`,
  `.pytest_cache/`, `*.log` (los seis de RF-6) y además `.vercel/`
  (directorio de la CLI con el vínculo del proyecto; decisión añadida para no
  subir configuración local de Vercel al repo).
- `.vercelignore` (raíz): los mismos patrones de `.gitignore` más lo que no
  hace falta en el despliegue: `specs/`, `docs/`, `.agents/`, `.opencode/`,
  `skills-lock.json`, `opencode.json`, `MEMORY.md` (el bundle de la función
  ya lo acota `includeFiles`; esto solo reduce el upload).

## Funciones puras (firmas aproximadas)

```python
# app/core/config.py
def _entero_estricto(valor: Optional[str]) -> Optional[int]
def es_modo_nube(env: Optional[Mapping[str, str]] = None) -> bool
def limite_mb(env: Optional[Mapping[str, str]] = None) -> int
def limite_filas_nube(env: Optional[Mapping[str, str]] = None) -> int
def _url_base_datos(env: Mapping[str, str], base_dir: Path) -> str

# app/api/v1/endpoints/upload.py (auxiliar pura nueva)
def _formatear_miles(n: int) -> str   # 2000 → "2.000" (separador español)
```

`env: None` significa `os.environ` (producción); en tests se pasa un dict o se
usa `monkeypatch.setenv`. Ninguna muta estado global.

## Orden de implementación y por qué

De dentro hacia fuera y de lo verificable a lo visual: **config puro →
endpoint `/entorno` → upload (límites y best-effort) → import seguro de
`main.py` → artefactos de despliegue → frontend → enmienda → verificación
integral**.

- Cada paso deja `pytest` en verde sin depender de la capa siguiente; los 189
  tests actuales son la red de seguridad desde T0 (por eso `validator.py`,
  `parser.py` y `normalizer.py` NO se tocan en ninguna tarea).
- El frontend se hace después del backend porque necesita el endpoint real
  (`/entorno`) para probarlo en el navegador, incluido el fallback.
- Los artefactos de despliegue van antes del frontend para poder verificar ya
  en T5 la simulación completa (`VERCEL=1`) con meta robots incluida.
- La enmienda (T6) va al final, junto a MEMORY, para cerrar la spec con todo
  implementado y verificado.

## Decisiones de diseño (con la alternativa descartada)

1. **Configuración en tiempo de llamada (funciones) y no constantes de
   import**: descartado mantener `MAX_BYTES` (constante congelada al importar
   el módulo; no se puede probar en nube/local con `monkeypatch` sin recargar
   todo el módulo) y descartado leer `os.environ` inline en el endpoint (duplicaría
   el parseo estricto entre `upload.py` y `entorno.py`).
2. **`_entero_estricto` compartido para `MAX_UPLOAD_MB` y `MAX_FILAS_NUBE`**:
   descartado dos parseos distintos (mismo contrato: strip + entero ≥ 1;
   inválido → defecto, nunca excepción).
3. **`DATABASE_URL` resuelto en import vía la pura `_url_base_datos`**:
   descartado un motor perezoso o recarga del módulo (rompería
   `database.py`, `Base` y los 189 tests, que asumen el engine actual) y
   descartado leer `VERCEL` inline en `config.py` (no sería testeable sin
   recargar).
4. **Endpoint `entorno` en archivo propio con router propio**: descartado
   meterlo en `upload.py` (mezclaría el endpoint de carga con un GET de
   estado; el proyecto separa por endpoint) y descartado el hostname
   (decisión cerrada: `VERCEL` es lo que garantiza Vercel y se prueba con
   `monkeypatch`).
5. **`EntornoRespuesta` como modelo Pydantic en `schemas/quality.py`**:
   descartado un dict suelto sin `response_model` (no documenta el contrato
   en OpenAPI y el proyecto responde siempre con modelos).
6. **Tope de filas con 413 y mensaje propio**: descartado 422 (el proyecto
   no usa 422 en endpoints y el frontend ya muestra el `detail` de un 413) y
   descartado 400 (chocaría con el 400 de esquema/ediciones inválidas: aquí
   el archivo ES válido, solo es demasiado grande para la demo).
7. **El tope se comprueba tras `parse_file` y antes de corregir/validar**:
   descartado antes de parsear (no se conoce el número de filas) y descartado
   después de validar (desperdiciaría CPU y respondería con resultado para
   luego tirarlo).
8. **Registro best-effort en AMBOS modos (una sola ruta)**: descartado
   acotarlo a nube (duplicaría comportamientos y dejaría el local con un 500
   latente; decisión del plan aprobado por la spec).
9. **`try/except` con `rollback()` + `logging` estándar**: descartado silenciar
   sin registrar (un fallo de BD debe quedar trazado en los logs de la
   función) y descartado librería de logs nueva (stdlib).
10. **Fallback del frontend: badge + banner + 4 MB si `/entorno` falla**:
    descartado asumir local (ocultaría el aviso de privacidad ante la duda,
    contra la decisión del usuario) y descartado dejar el formulario inerte
    (si la API está caída, la subida fallará igual con su propio aviso).
11. **Texto de tamaño bajo el input con valor inicial conservador (4 MB)
    actualizado por `app.js`**: descartado esperar al fetch para pintarlo
    (dejaría el campo sin el texto «SIEMPRE visible» que pide el RF-3) y
    descartado que `FileUploader` consulte `/entorno` por su cuenta
    (duplicaría la lógica de entorno fuera de `app.js`, que es el
    orquestador).
12. **`HelpModal.js` intacto**: descartado añadir el tamaño al modal (hoy no
    lo menciona; sería inventar contenido y crearía dos fuentes de la cifra).
13. **`includeFiles` con globs positivos explícitos**: descartado
    `data-processor-app/**` (empaquetaría `data.sqlite3`, cachés, tests y
    ejemplos en el bundle).
14. **Catch-all con `rewrites` `/(.*)` → `/api/index`** (y no con `routes`:
    es legacy y rompería `headers`): descartado mapear estáticos uno a
    uno en `vercel.json` (duplica el mapa de rutas del frontend y se
    desincroniza con cada componente nuevo).
15. **`.vercel/` añadido al `.gitignore`**: descartado dejarlo fuera (la CLI
    de Vercel escribe ahí el vínculo del proyecto; no es contenido del
    repositorio). Es el único añadido a la lista de RF-6 y no afecta al
    despliegue.
16. **Tarea T0 documental antes de tocar código**: descartado corregir los
    números «de pasada» (la cifra de 189 es la red de seguridad del plan; si
    empieza ambigua, cualquier regresión pasaría desapercibida).

## Riesgos y mitigación (los de la spec, con su verificación)

1. **Runtime de Python de Vercel ≠ 3.14 local** (spec): mitigado con la
   verificación del T7 en el despliegue real (arranque + una validación
   completa); local se prueba todo con el runtime del equipo.
2. **`includeFiles` y la ruta del bundle en `api/index.py`**: la asunción
   `<raíz>/api/index.py` → `<raíz>/data-processor-app/backend` se prueba en
   local con `tests/test_despliegue.py` (subproceso que importa
   `api/index.py` desde la raíz del repo); si Vercel empaqueta distinto, el
   T7 lo detecta en el primer despliegue.
3. **Respuesta grande con esquemas de muchas columnas** (residual de la
   spec): mitigado con el tope de 2.000 filas; SIN tope de columnas (fuera de
   alcance); verificado vigilando la demo.
4. **Estáticos servidos por la función (invocaciones/cold starts)**: aceptado
   por simplicidad (spec); alternativa descartada documentada arriba (14).
5. **Bomba zip en `.xlsx`**: aceptada (spec); mitigación parcial con el
   límite de 4 MB y el tope de filas; sin librerías nuevas de saneamiento
   (fuera de alcance).
6. **`vercel dev` define `VERCEL=1`** (modo nube en desarrollo local):
   documentado en spec y plan: para forzar local, `VERCEL=` (vacío) en `.env`
   o arrancar con uvicorn directo.
7. **Plan Hobby no comercial**: fuera del alcance del código; condición del
   usuario para el despliegue.
8. **La verificación REAL del despliegue requiere la cuenta/token del
   usuario**: el agente NO despliega por su cuenta; el T7 deja un checklist
   cerrado que el usuario ejecuta (o ejecuta con su sesión/token) y confirma.
   Todo lo demás queda verificado por simulación (`VERCEL=1`) antes de esa
   cita.

## Estrategia de verificación

### Con `pytest` (desde `data-processor-app/backend/`; red de seguridad: 189 actuales)

- **Config y entorno** (`tests/test_entorno.py`, nuevo): `VERCEL` presente /
  ausente / vacío → `modo`; `MAX_UPLOAD_MB` estricta (`8` → 8 en local,
  clamp 4 en nube; `" 8 "` → 8; `0`, `-3`, `4.5`, `4,5`, `abc`, vacío →
  defecto 10/4); `MAX_FILAS_NUBE` válida (`500`) e inválida (`0`, `-10`,
  `abc` → 2000); `_url_base_datos` (VERCEL → `/tmp/data.sqlite3`; sin VERCEL
  → `data.sqlite3` local; con `DATABASE_URL` explícita → se respeta); el
  endpoint devuelve el JSON del contrato y NUNCA 500. Cubre RF-1, RF-7.
- **Upload** (`tests/test_upload_endpoint.py` ampliado): 413 local con
  «El archivo supera el límite de 10 MB.» idéntico al actual; con
  `VERCEL=1`, archivo > 4 MB → 413 «…de 4 MB.»; en nube, CSV de 2.000 filas →
  200 y de 2.001 → 413 con el mensaje exacto «La demo en línea acepta hasta
  2.000 filas por archivo…» SIN haber corregido/validado; revalidación con
  `ediciones` sobre 2.500 filas en nube → mismo 413; en local, 2.001 filas →
  200 y el mensaje jamás aparece; `MAX_FILAS_NUBE=500` → 501 filas → 413 con
  «…hasta 500 filas…»; registro best-effort: con
  `app.dependency_overrides[get_session]` apuntando a una sesión cuyo
  `commit()` lanza, la respuesta sigue siendo 200 completa (y se limpia el
  override); el registro normal sigue persistiendo. Cubre RF-3, RF-4, RF-8.
- **Import seguro** (`tests/test_main.py`, nuevo): subproceso con
  `FRONTEND_DIR` fijada a un directorio inexistente → el import de
  `app.main` no lanza, `GET /api/v1/entorno` responde 200 y `GET /` da 404;
  con el valor por defecto, `GET /` sigue sirviendo `index.html`. Cubre
  RF-5.
- **Coherencia de despliegue** (`tests/test_despliegue.py`, nuevo): existe
  `requirements.txt` en la raíz y contiene la referencia
  `-r data-processor-app/backend/requirements.txt`; `vercel.json` parsea como
  JSON y tiene `rewrites` catch-all (con `functions` + `includeFiles` y NO
  `routes`), `maxDuration` 60, `memory` 1024 y la cabecera
  `X-Robots-Tag: noindex`; existe `api/index.py` y un subproceso que lo
  importa desde la raíz del repo (con `VERCEL=1` y `FRONTEND_DIR` al
  frontend real) expone un objeto `app`. Cubre RF-6, RNF-1.
- **Regresión**: los 189 tests actuales sin modificarse (RNF-2; RNF-4 con el
  matiz best-effort, que solo RELAJA un caso: un commit fallido ya no rompe).

### En el navegador (Chrome DevTools, API real; 1280px y 375px)

- **Local** (uvicorn sin `VERCEL`): sin badge «Demo», sin banner, texto
  «Tamaño máximo del archivo: 10 MB.» visible bajo el input, validación
  completa con `ejemplo_autocorreccion.csv`, y un CSV temporal de > 2.000
  filas validado sin ningún aviso de tope (RNF-4).
- **Simulación nube** (uvicorn con `VERCEL=1`): badge «Demo» (con su tooltip)
  y banner con el texto exacto; texto «…4 MB.» bajo el input; subir un
  archivo de ~4,1 MB muestra «El archivo supera el límite de 4 MB.»; subir
  2.001 filas muestra «La demo en línea acepta hasta 2.000 filas por
  archivo…»; el HTML servido incluye `<meta name="robots" content="noindex">`
  (RNF-3a); a 375px el badge y el banner se ven bien (RF-2, RF-3, RNF-5).
- **Fallback**: bloqueando `/api/v1/entorno` (pestaña de red) y recargando,
  aparecen badge y banner con el texto conservador «4 MB» (RF-2).

### Despliegue real (checklist del T7, lo ejecuta el usuario con su cuenta)

1. Cuenta Vercel Hobby (demo no comercial) y repo en GitHub con remoto.
2. Push de `main` con los artefactos (sin `data.sqlite3` ni `__pycache__/`:
   comprobar con `git status`/`git check-ignore`).
3. Importar el proyecto en Vercel; sin variables obligatorias
   (`VERCEL` la define Vercel; `MAX_UPLOAD_MB`/`MAX_FILAS_NUBE` opcionales;
   `DATABASE_URL` NO definida).
4. Verificar en la URL real: badge «Demo», banner, texto «…4 MB.», 413 de
   bytes y de filas, validación completa (autocorrección, edición, descargas)
   SIN `ModuleNotFoundError`, y `X-Robots-Tag: noindex` en las respuestas
   (p. ej. en las cabeceras de `GET /`).
