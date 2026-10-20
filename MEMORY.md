# MEMORY.md — Plataforma de Procesamiento y Validación de Reportes
Memoria del proyecto entre sesiones. Máximo ~50 líneas: resume o elimina lo que no aporte.

## Estado actual
- App B2B full-stack: `data-processor-app/backend/` (FastAPI + SQLAlchemy 2.0 + SQLite,
  servicios con `Session` síncrona) y `frontend/` vanilla (Tailwind + Chart.js por CDN).
- Spec 001 COMPLETADA: carga CSV/JSON/Excel + esquema configurable + validación + reporte.
- Spec 002 COMPLETADA: celdas en rojo, editor de esquema en línea, exportación CSV/JSON y Excel.
- Spec 003 COMPLETADA (T1-T17): autocorrección (`normalizer.py`), edición manual, descargas
  normal/corregida y vista previa SIN límite (decisión 24: `preparar_muestra` trae todas las
  filas de interés; `limite_muestra` eliminado, si llega se ignora sin 400). Contador «X filas
  con errores o correcciones · Y incidencias» derivado en navegador; aviso ámbar ≥2.000 filas.
- Spec 004 «demo-vercel»: **T0-T7 TÉCNICO completado** (verificación integral en navegador
  OK: local/nube/fallback a 1280 y 375, límites y textos exactos; coherencia de despliegue
  verificada). **225 tests en verde**. Constitución art. 5 y AGENTS.md enmendados.
  Cambios de la spec publicados en `main`. **Despliegue real PENDIENTE del usuario**
  (checklist entregado en T7).
- Repo Git publicado en `main`; fuera: `data.sqlite3`, `.pyc`, cachés y `.env`.

## Decisiones de la spec 004 (y por qué)
- Demo en Vercel SIN login y NO comercial (plan Hobby del usuario); privacidad: badge «Demo»
  + banner ámbar; si `/api/v1/entorno` FALLA se avisa igual (nunca se oculta el aviso) y el
  texto de tamaño usa el conservador 4 MB. `/entorno` devuelve `{"modo","limite_mb"}`.
- Límites por entorno leídos en cada petición: nube 4 MB + tope 2.000 filas (413 con textos
  exactos); local 10 MB y SIN tope de filas. Registro de carga best-effort (un fallo de BD
  jamás da 500). `vercel.json` con `rewrites` catch-all (NO `routes`, legacy) + noindex.
- Constante canónica `LIMITE_MB_NUBE_TOPE`; `FRONTEND_DIR` por env y montaje condicional
  (app funciona sin frontend, RF-5). Frontend: `consultarEntorno()` en `app.js`.

## Aprendizajes y errores a evitar
- `vercel dev` define `VERCEL=1` y activa el modo nube sin querer: para simular nube a mano
  usar uvicorn con `VERCEL=1`; para local, sin ella.
- En Windows `VERCEL=1` necesita `DATABASE_URL` explícita: el defecto nube es
  `sqlite:////tmp/data.sqlite3` y `/tmp` NO existe en Windows (en Vercel Linux sí).
- pandas convierte `n/a`/`NA` a NaN en read_csv: usar otro marcador de la lista cerrada.
- El paso `numero` del normalizer corrige números CON separador (`10.5` → TODAS las filas);
  en CSVs de prueba "limpios" usar enteros para no disparar el interés.
- MCP navegador: 375 solo con `emulate({viewport:"375x812x2,mobile,touch"})` (RECARGA; los
  pageIds pueden cambiar → relistar); volver a escritorio `emulate({pageId})` + `resize_page`;
  NUNCA anidar backticks en `evaluate_script`; clics por uid poco fiables con táctil → eventos
  DOM; `args` del evaluate SOLO admite uids (para pegar datos, incrustarlos en el script).
- Overflow a 375 de `#chart`/`#chart-columnas` DECIDIDO no tocar (la tabla sí recorta).
- Entre sesiones puede haber ediciones manuales: ejecutar `pytest` AL EMPEZAR.

## Próximos pasos
- Spec 004: **despliegue real en Vercel por el usuario** (checklist en el informe de T7:
  cuenta Hobby, import con root en la raíz, verificación en la URL real); después, marcar
  T7 en `tasks.md` y cerrar la spec (incluido el commit de lo pendiente).
