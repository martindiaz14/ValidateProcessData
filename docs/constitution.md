# Constitución — Plataforma de Procesamiento y Validación de Reportes

1. **Stack fijo.** Backend Python 3.11+ (FastAPI, Pydantic v2, Pandas, SQLAlchemy 2.0 + SQLite, Uvicorn). Frontend JavaScript vanilla con Tailwind y Chart.js por CDN: sin React, sin npm, sin build. FastAPI sirve los archivos estáticos del frontend.
2. **Spec antes que código.** Toda funcionalidad se describe primero en `specs/NNN-*/` aprobada; el código solo implementa lo que la spec dice. Si cambia el código, la spec se actualiza en la misma tarea.
3. **Lógica separada de la interfaz.** Validación, parsing y cálculos viven en `backend/app/services/` y se prueban sin HTTP; los endpoints solo enrutan. El frontend solo llama a la API y pinta, nunca valida datos.
4. **Tests obligatorios.** `pytest` para backend (services y endpoints). El frontend se verifica en el navegador contra la API real. Sin frameworks de testing en JavaScript.
5. **Los datos del usuario no salen del equipo.** Todo se procesa en local: SQLite en disco, sin servicios externos ni telemetría. Prohibido subir datos, claves o tokens a repos, logs o APIs de terceros.
6. **Español en todo.** Textos de interfaz, comentarios y documentación (spec, memoria, constitución) en español. Identificadores en inglés claro y descriptivo.
