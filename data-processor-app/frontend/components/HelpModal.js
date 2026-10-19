// Ayuda contextual: botón '?' en la cabecera que abre una ventana con los pasos
// para usar la plataforma (subir archivo, nombre de tabla, columnas y tipos de dato).
// Solo interfaz; no toca el backend.

export function renderHelpModal() {
  const slot = document.getElementById("ayuda");
  if (!slot) return;

  slot.innerHTML = `
    <button id="btn-ayuda" type="button" aria-label="Ayuda de uso" title="¿Cómo se usa?"
      class="shrink-0 w-9 h-9 mt-0.5 rounded-full border border-slate-300 text-slate-500 hover:text-blue-600 hover:border-blue-400 flex items-center justify-center">
      <i data-lucide="help-circle" class="w-5 h-5"></i>
    </button>
  `;

  const modal = document.createElement("div");
  modal.id = "modal-ayuda";
  modal.className = "fixed inset-0 z-50 hidden";
  modal.innerHTML = `
    <div class="absolute inset-0 bg-slate-900/50" data-accion="cerrar"></div>
    <div role="dialog" aria-modal="true" aria-label="Cómo usar la plataforma"
      class="relative mx-auto my-6 sm:my-10 w-[92%] max-w-2xl bg-white rounded-2xl shadow-xl max-h-[85vh] overflow-y-auto">
      <div class="sticky top-0 bg-white border-b border-slate-200 px-5 py-4 flex items-center justify-between">
        <h2 class="font-semibold flex items-center gap-2">
          <i data-lucide="help-circle" class="w-5 h-5 text-blue-600"></i>
          Cómo usar la plataforma
        </h2>
        <button type="button" data-accion="cerrar" aria-label="Cerrar"
          class="w-8 h-8 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 flex items-center justify-center">
          <i data-lucide="x" class="w-5 h-5"></i>
        </button>
      </div>

      <div class="px-5 py-4 space-y-4 text-sm text-slate-700">
        <ol class="space-y-4 list-decimal list-inside marker:text-blue-600 marker:font-semibold">
          <li>
            <span class="font-semibold text-slate-800">Sube el archivo de datos.</span>
            Pulsa <b>Seleccionar archivo</b> y elige un <b>CSV, JSON o Excel (.xlsx)</b>.
            Debe llevar una fila de cabecera con los nombres de las columnas.
          </li>
          <li>
            <span class="font-semibold text-slate-800">Indica el nombre de la tabla (opcional).</span>
            Solo un nombre para identificar el reporte, p. ej. <code>${code("transacciones_pagos")}</code>.
            No cambia la validación.
          </li>
          <li>
            <span class="font-semibold text-slate-800">Añade las columnas que quieras validar.</span>
            Pulsa <b>Añadir campo</b> por cada columna y escribe su nombre
            <b>tal cual aparece en la cabecera</b> del archivo (p. ej. <code>${code("monto")}</code>).
          </li>
          <li>
            <span class="font-semibold text-slate-800">Elige el tipo de dato y sus reglas.</span>
            En el desplegable <b>Tipo</b>:
            <ul class="mt-2 space-y-1 list-disc list-inside text-slate-600">
              <li><b>Texto</b> — Escribe un <i>ejemplo</i> de cómo debe verse (p. ej. <code>${code("TX-123")}</code>); se comprueba que los valores se le parezcan.</li>
              <li><b>Número</b> — Acepta decimales. Puedes fijar <i>mínimo</i> y <i>máximo</i> (p. ej. mínimo <code>${code("0.01")}</code> para rechazar negativos).</li>
              <li><b>Fecha</b> — Comprueba el <i>formato</i> indicado (p. ej. <code>${code("YYYY-MM-DD")}</code> → <code>${code("2026-10-01")}</code>).</li>
              <li><b>Email</b> — Valida que sea un correo (p. ej. <code>${code("juana@mail.com")}</code>).</li>
              <li><b>Selección (enum)</b> — Solo admite los <i>valores permitidos</i> separados por coma (p. ej. <code>${code("APROBADO, PENDIENTE, RECHAZADO")}</code>).</li>
              <li><b>Sí / No</b> — Valor booleano.</li>
            </ul>
            Activa <b>Requerido</b> si el campo no puede venir vacío.
          </li>
          <li>
            <span class="font-semibold text-slate-800">Pulsa Validar.</span>
            Verás el resumen, las gráficas, los errores por fila y una vista previa con las
            celdas incorrectas en rojo. Puedes exportar el resultado a <b>CSV</b> o <b>JSON</b>.
          </li>
        </ol>

        <div class="rounded-lg bg-blue-50 border border-blue-200 text-blue-800 p-3 text-xs">
          <b>Ver JSON generado</b> muestra el esquema técnico que se envía al validador.
          Úsalo solo si quieres revisarlo o copiarlo; no hace falta para usar la plataforma.
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  const abrir = () => {
    modal.classList.remove("hidden");
    document.body.style.overflow = "hidden";
    if (window.lucide) window.lucide.createIcons();
  };
  const cerrar = () => {
    modal.classList.add("hidden");
    document.body.style.overflow = "";
  };

  slot.querySelector("#btn-ayuda").addEventListener("click", abrir);
  modal.querySelectorAll('[data-accion="cerrar"]').forEach((el) =>
    el.addEventListener("click", cerrar)
  );
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !modal.classList.contains("hidden")) cerrar();
  });

  if (window.lucide) window.lucide.createIcons();
}

function code(texto) {
  return `<code class="bg-slate-100 px-1 py-0.5 rounded text-xs">${texto}</code>`;
}
