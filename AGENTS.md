# AGENTS.md — Plataforma de Procesamiento y Validación de Reportes

Aplicación web B2B: las empresas suben archivos de datos (CSV/JSON), el backend los
valida bajo esquemas estrictos de calidad y el frontend muestra un reporte visual
interactivo. Los datos se procesan en local y no salen del equipo del usuario.

## Stack y estructura
- Backend Python 3.11+ (FastAPI, Pydantic v2, Pandas, SQLAlchemy 2.0 + SQLite, Uvicorn).
- Frontend JavaScript vanilla + Tailwind CSS y Chart.js por CDN: sin React, sin npm, sin build.
- Estructura:
  - `data-processor-app/backend/app/` → `api/v1/` (endpoints), `core/` (config, database),
    `models/` (SQLAlchemy), `schemas/` (Pydantic), `services/` (lógica), `main.py`.
  - `data-processor-app/frontend/` → `index.html`, `styles.css`, `app.js`, `components/`.
- FastAPI sirve el frontend estático y la API bajo `/api/v1/`.

## Convenciones
- Textos de la interfaz, comentarios y documentación en español.
- Identificadores de código en inglés claro y descriptivo.
- Diseño limpio y responsive; cualquier pantalla nueva debe verse bien en el móvil.
- La lógica de validación/parsing vive en `services/` y se prueba sin HTTP.

## Datos
- Persistencia en SQLite local (SQLAlchemy 2.0 / AsyncSession). Nada sale del equipo.
- Si cambias la forma de los datos guardados, mantén compatibilidad con lo ya guardado.

## Forma de trabajar
- Lee `docs/constitution.md` y la spec activa (`specs/NNN-*/`) antes de tocar código.
- Haz solo lo que se pide: no añadas funcionalidades por tu cuenta.
- Cambios pequeños y enfocados; no reescribas lo que ya funciona.
- Al terminar, resume qué has cambiado y cualquier decisión que deba revisar.

## Verificación
- Tests de backend con `pytest`. Sin frameworks de testing en JavaScript.
- Lo visual se verifica en el navegador contra la API real (incluida vista móvil).

## Límites
- ✅ Siempre: mantener textos en español y los datos del usuario en local.
- ✅ Siempre: actualizar `MEMORY.md` al terminar cada tarea.
- ⚠️ Pregunta antes: crear archivos nuevos, cambiar el formato de los datos guardados,
  o añadir una librería (Python o JS) a las ya fijadas en la constitución.
- 🚫 Nunca: React, frameworks de frontend, npm ni un paso de build. Nunca subir datos a
  servicios externos.

## Memoria
- Al empezar, lee `MEMORY.md` para conocer el estado y las decisiones tomadas.
- Al terminar una tarea, actualízalo: estado actual, decisiones (con su porqué) y errores
  a evitar. Mantenlo breve (máximo ~50 líneas).
- No guardes nunca datos sensibles (claves, tokens, datos personales).
