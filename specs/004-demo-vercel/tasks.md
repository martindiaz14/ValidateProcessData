# Tareas — Spec 004: Demo pública en la nube (Vercel)

Protocolo del usuario: **UNA tarea por vez** — se ejecuta UNA sola tarea, se
verifica (`pytest` y/o navegador según la tarea), se resume lo cambiado y se
**PARA** a esperar la confirmación del usuario antes de pasar a la siguiente.
La validación RF por RF completa se hace solo al FINAL (T7).

Verificación de backend tras cada tarea: `python -m pytest` desde
`data-processor-app/backend/`. **Red de seguridad: los 189 tests actuales
deben seguir en verde desde T0** (cifra medida por QA; la T0 la reconcilia en
las specs 001-003 documentales). Sin frameworks de testing en JavaScript: el
frontend se verifica en el navegador contra la API real (constitución, regla
4).

Estado: **T0-T6 COMPLETADAS** (spec 004 aprobada, incluida la enmienda de
privacidad; `plan.md` aprobado; 225 tests en verde). **T7 PENDIENTE**.

- [x] **T0. Reconciliar la cifra de 189 tests en las specs de la 003
  (documental, sin código).** RF: RNF-2 (nota de alcance T0)
  - Alcance (SOLO `specs/`): `specs/003-auto-correccion/spec.md` — la línea
    de Estado y cualquier mención desactualizada quedan con **189 tests**;
    `specs/003-auto-correccion/tasks.md` — las menciones a 191 y 193 (T11,
    T13, T15, T16) se dejan como histórico de ESAS tareas pero se aclara en
    el encabezado/Estado que la cifra FINAL y vigente es **189** (la medición
    de QA). No se toca NINGÚN archivo de código.
  - Hecho cuando: el diff de T0 toca SOLO esos dos archivos; comprobar con
    `git diff --name-only` (no debe aparecer ningún archivo fuera de
    `specs/003-auto-correccion/spec.md` y `specs/003-auto-correccion/tasks.md`
    además de los cambios NO commiteados que el repo ya tuviera de la propia
    spec 004, que no cuentan) o bien inspeccionando el diff de esos dos
    archivos; ambos dicen 189 como cifra vigente y 191/193 quedan marcados
    como históricos; `python -m pytest` sigue en verde sin haberse tocado
    código (red de seguridad confirmada).
  - RF cubiertos: RNF-2. Tests: los 189 existentes, sin cambios.
  - **Nota de parada**: resumir el diff y PARAR.

- [x] **T1. Backend: configuración en tiempo de llamada + `GET /api/v1/entorno`
  + tests (upload.py INTACTO).** RF-1, RF-7
  - Alcance: `app/core/config.py` (constantes `MB`, `LIMITE_MB_LOCAL`,
    `LIMITE_MB_NUBE_TOPE`, `LIMITE_FILAS_NUBE_DEFECTO`; funciones puras
    `_entero_estricto`, `es_modo_nube`, `limite_mb` con clamp a 4 en nube,
    `limite_filas_nube`, `_url_base_datos` —VERCEL → `sqlite:////tmp/
    data.sqlite3`, con `DATABASE_URL` explícita se respeta—; `DATABASE_URL`
    y `FRONTEND_DIR` pasan a resolverse con esos helpers, `FRONTEND_DIR`
    sobrescribible por env); **nuevo** `app/api/v1/endpoints/entorno.py`
    (router propio, sin BD); `app/api/v1/api.py` (incluye el router);
    `app/schemas/quality.py` (modelo `EntornoRespuesta` con
    `modo: Literal["nube","local"]` y `limite_mb: int`); **nuevo**
    `tests/test_entorno.py`. NO se toca `upload.py` ni `main.py` (T2/T3).
  - Hecho cuando: `python -m pytest` pasa (189 + los nuevos) cubriendo:
    `VERCEL=1`/ausente/vacío → `modo` correcto; `MAX_UPLOAD_MB` estricta
    (`8`→8 local y clamp 4 nube, `" 8 "`→8, `0`/`-3`/`4.5`/`4,5`/`abc`/
    vacío → defecto 10/4); `MAX_FILAS_NUBE` `500`→500 y `0`/`-10`/`abc`→2000;
    `GET /api/v1/entorno` devuelve el JSON del contrato
    (`{"modo","limite_mb"}`) y nunca 500; `_url_base_datos` con los tres
    casos (VERCEL → `/tmp`, sin VERCEL → `backend/data.sqlite3`, explícita →
    respetada); con `upload.py` intacto, los 189 previos siguen en verde.
  - RF cubiertos: RF-1 (endpoint y helpers), RF-7 (sucursal `/tmp`).
    Tests: `tests/test_entorno.py` (nuevo).
  - **Nota de parada**: resumir y PARAR.

- [x] **T2. Backend: `upload.py` con límite dinámico, tope de filas en nube y
  registro best-effort + tests.** RF-3, RF-4, RF-8
  - Alcance: `app/api/v1/endpoints/upload.py` — (a) se elimina la constante
    `MAX_BYTES` y el límite de bytes pasa a leerse con `limite_mb()` en cada
    petición (`limite * MB`), con 413 dinámico «El archivo supera el límite
    de {N} MB.» (idéntico al actual en local: «…10 MB.»); (b) auxiliar pura
    `_formatear_miles` (2000 → «2.000») y comprobación del tope de filas
    DESPUÉS de `parse_file` y ANTES de `_parsear_ediciones`/`corregir_filas`:
    solo si `es_modo_nube()` y `len(rows) > limite_filas_nube()` → 413 con
    el mensaje EXACTO de la spec; (c) el registro de la carga (add/commit)
    queda en `try/except Exception` con `rollback()` y `logging.warning`,
    fuera del cual está el `return result` (un fallo de BD nunca da 500);
    `validator.py`, `parser.py` y `normalizer.py` INTACTOS.
    `tests/test_upload_endpoint.py` ampliado.
  - Hecho cuando: `python -m pytest` pasa (189 + los nuevos) cubriendo:
    local sin `VERCEL`, archivo > 10 MB → 413 «El archivo supera el límite de
    10 MB.» (texto idéntico al actual); con `VERCEL=1`, archivo > 4 MB →
    413 «…de 4 MB.»; en nube, CSV de 2.000 filas → 200 y de 2.001 → 413 con
    «La demo en línea acepta hasta 2.000 filas por archivo. Para archivos
    más grandes, ejecuta la aplicación en local.» (y la respuesta nunca
    llegó a corregir/validar); revalidación con `ediciones` sobre 2.500
    filas en nube → mismo 413; en local, 2.001 filas → 200 sin ese mensaje
    jamás; `MAX_FILAS_NUBE=500` → 501 filas → 413 con «…hasta 500 filas…»;
    registro best-effort: con `app.dependency_overrides[get_session]` y una
    sesión cuyo `commit()` lanza, la respuesta sigue siendo 200 completa (se
    limpia el override al terminar) y el registro normal sigue
    persistiéndose.
  - RF cubiertos: RF-3 (413 dinámico), RF-4 (best-effort ambos modos),
    RF-8 (tope solo nube, toda petición `/upload`). Tests:
    `tests/test_upload_endpoint.py` ampliado.
  - **Nota de parada**: resumir y PARAR.

- [x] **T3. Backend: `FRONTEND_DIR` por variable de entorno + montaje
  condicional + test por subproceso.** RF-5
  - Alcance: `app/core/config.py` (la resolución de `FRONTEND_DIR` ya quedó
    en T1; aquí solo se confirma el uso); `app/main.py` — el montaje de
    `StaticFiles` pasa a ir dentro de `if FRONTEND_DIR.is_dir():` (comprobación
    en el momento del montaje); **nuevo** `tests/test_main.py` (subproceso con
    `FRONTEND_DIR` fijada a un directorio inexistente: importa
    `app.main` sin lanzar, `GET /api/v1/entorno` → 200 y `GET /` → 404; con
    el valor por defecto, `GET /` sigue sirviendo `index.html`).
  - Hecho cuando: `python -m pytest` pasa (189 + los nuevos) y el test de
    subproceso cubre los dos escenarios (directorio inexistente → API viva y
    raíz 404; defecto → frontend servido como hoy).
  - RF cubiertos: RF-5. Tests: `tests/test_main.py` (nuevo).
  - **Nota de parada**: resumir y PARAR.

- [x] **T4. Artefactos de despliegue en la raíz + test de coherencia.**
  RF-6, RNF-1, RNF-3
  - Alcance (archivos NUEVOS en la RAÍZ del repo, pre-aprobados):
    `requirements.txt` (`-r data-processor-app/backend/requirements.txt`);
    `vercel.json` (functions `api/index.py` con `maxDuration` 60, `memory`
    1024 e `includeFiles` con globs positivos —`.py` del backend, su
    requirements y el frontend—; `rewrites` catch-all
    `{source: "/(.*)", destination: "/api/index"}` (NO `routes`: es legacy
    y no puede combinarse con `headers`); `headers` con `X-Robots-Tag:
    noindex` en todas las rutas);
    `api/index.py` (monta `data-processor-app/backend` en `sys.path` y
    exporta `app` de `app.main`); `.gitignore` (`.venv/`, `__pycache__/`,
    `*.pyc`, `data.sqlite3`, `.pytest_cache/`, `*.log` y `.vercel/`);
    `.vercelignore` (los mismos patrones + `specs/`, `docs/`, `.agents/`,
    `.opencode/`, `skills-lock.json`, `opencode.json`, `MEMORY.md`);
    **nuevo** `tests/test_despliegue.py` (raíz del repo resuelta desde el
    test: `requirements.txt` contiene la referencia `-r …`; `vercel.json`
    parsea y tiene `rewrites` catch-all (no `routes`) + `includeFiles` en
    `functions` + 60 + 1024 + noindex; subproceso que importa
    `api/index.py` desde la raíz con `VERCEL=1` y `FRONTEND_DIR` al frontend
    real y expone `app`).
  - Hecho cuando: `python -m pytest` pasa (189 + los nuevos); con
    `git check-ignore data-processor-app/backend/data.sqlite3` (y un
    `__pycache__`) el patrón calza; el subproceso de `api/index.py` importa
    limpio; el contenido de `vercel.json` coincide con el del plan.
  - RF cubiertos: RF-6, RNF-1, RNF-3 (parte cabecera, verificable aquí solo
    como configuración). Tests: `tests/test_despliegue.py` (nuevo).
  - **Nota de parada**: resumir y PARAR.

- [x] **T5. Frontend: noindex, badge «Demo», banner, `/entorno` con fallback
  y texto de tamaño + verificación en navegador.** RF-2, RF-3 (UI), RNF-3a,
  RNF-5
  - Alcance: `frontend/index.html` (`<meta name="robots" content="noindex">`,
    `<span id="badge-demo" class="hidden">Demo</span>` dentro del `<h1>`,
    `<section id="banner-demo" class="hidden">` justo encima de
    `#uploader`); `frontend/app.js` (función `consultarEntorno()` al cargar:
    éxito `local` → nada visible y límite del backend; éxito `nube` → badge
    (tooltip exacto) + banner con el texto EXACTO de la spec; fallo → badge y
    banner IGUALMENTE y límite conservador 4; en los tres casos llama a
    `actualizarLimiteSubida(n)`); `frontend/components/FileUploader.js`
    (`<p id="limite-tamano">` justo debajo del input con texto inicial
    conservador «Tamaño máximo del archivo: 4 MB.» y export
    `actualizarLimiteSubida(n)`). `HelpModal.js` SIN CAMBIOS (no menciona
    tamaños). Sin archivos nuevos; los CSV de prueba se generan temporales
    fuera del repo.
  - Hecho cuando: en navegador contra la API real a 1280px y 375px: (1)
    uvicorn SIN `VERCEL` → sin badge ni banner en ningún momento, texto
    «Tamaño máximo del archivo: 10 MB.» visible bajo el input, validación
    completa y un CSV temporal de > 2.000 filas validado sin aviso de tope;
    (2) uvicorn CON `VERCEL=1` → badge «Demo» con tooltip y banner con el
    texto exacto, texto «…4 MB.» bajo el input, subir ~4,1 MB muestra
    «El archivo supera el límite de 4 MB.», subir 2.001 filas muestra «La
    demo en línea acepta hasta 2.000 filas por archivo…», el HTML servido
    incluye el meta robots noindex, y a 375px todo se ve bien; (3) bloqueando
    `/api/v1/entorno` y recargando → badge y banner visibles con «4 MB»;
    `python -m pytest` sigue en verde.
  - RF cubiertos: RF-1 (consumo del endpoint), RF-2, RF-3 (texto de tamaño),
    RNF-3 (meta), RNF-5 (textos en español). Tests: verificación en
    navegador (sin frameworks JS); los de backend no cambian.
  - **Nota de parada**: resumir y PARAR.

- [x] **T6. Enmienda a la constitución y a `AGENTS.md` + `MEMORY.md`.**
  RF: enmienda aprobada de la spec 004
  - Alcance: `docs/constitution.md` — el artículo 5 se SUSTITUYE por el texto
    literal aprobado en la spec («Los datos del usuario no salen del equipo
    (modo local); la demo aprobada en la nube es la única excepción…»);
    `AGENTS.md` — sección «Datos»: el bullet de persistencia pasa a «…En
    modo local nada sale del equipo.» y se añade el bullet del modo demo en
    la nube; sección «Límites»: la línea de prohibición pasa al texto
    literal aprobado («…Nunca subir datos de usuario a servicios externos ni
    persistirlos fuera del equipo (la demo de Vercel solo los procesa en
    memoria y los descarta; ver spec 004).»); `MEMORY.md` (estado: spec 004
    en marcha T0-T6, decisiones de esta spec y error a evitar: `vercel dev`
    define `VERCEL=1`). No se toca código.
  - Hecho cuando: los tres archivos muestran los textos EXACTOS de la spec
    004 (sección «Enmienda»); `python -m pytest` sigue en verde (no se tocó
    código).
  - RF cubiertos: enmienda (art. 5 + AGENTS.md). Tests: los 189 + los
    añadidos, sin cambios.
  - **Nota de parada**: resumir y PARAR.

- [ ] **T7. Verificación integral + checklist de despliegue real.**
  RF: criterios de finalización de la spec
  - Alcance: sin cambios de código salvo los arreglos que descubra la
    verificación; actualización final de `MEMORY.md`; entrega al usuario del
    checklist de despliegue real (el agente NO despliega: requiere la cuenta
    y el token del usuario).
  - Hecho cuando: (1) `python -m pytest` completo en verde (189 actuales +
    todos los nuevos de T1-T4); (2) recorrido en navegador contra la API
    real conforme a TODOS los criterios de la spec (local: sin badge/banner,
    10 MB y sin tope de filas; simulación `VERCEL=1`: badge/banner con textos
    exactos, 4 MB, 413 de bytes y de filas, meta noindex, y fallback de
    `/entorno`); (3) `MEMORY.md` refleja el estado final; (4) el usuario
    tiene el checklist del plan (cuenta Hobby no comercial, remoto Git,
    import en Vercel, verificación en la URL real de `X-Robots-Tag`, badge,
    banner, 4 MB, y una validación completa SIN `ModuleNotFoundError`) y
    confirma el despliegue él mismo (o pide hacerlo con su token).
  - RF cubiertos: todos los RF/RNF de la spec, validados RF por RF.
    Tests: los de backend + la verificación en navegador.
  - **Nota de parada**: cierre de la spec con el usuario (incluido el
    resultado del despliegue real).
  - **Nota (T7, 20-oct-2026): verificación técnica COMPLETADA** — `pytest`
    225 en verde; navegador local/nube/fallback a 1280 y 375 conforme a los
    criterios; coherencia de despliegue verificada (requirements raíz,
    `vercel.json`, `api/index.py` con `VERCEL=1`, ignores). El checkbox queda
    **sin marcar a propósito**: el despliegue real es del usuario.
