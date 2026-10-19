// Componente de resumen: tarjetas con total, válidas e inválidas.

export function renderValidationSummary(contenedor, resultado) {
  const tarjetas = [
    { titulo: "Total de filas", valor: resultado.total_filas, color: "text-slate-800" },
    { titulo: "Filas válidas", valor: resultado.validas, color: "text-emerald-600" },
    { titulo: "Filas inválidas", valor: resultado.invalidas, color: "text-red-600" },
  ];

  contenedor.innerHTML = `
    <div class="grid gap-4 sm:grid-cols-3">
      ${tarjetas
        .map(
          (t) => `
        <div class="bg-white rounded-xl border border-slate-200 p-4">
          <p class="text-sm text-slate-500">${t.titulo}</p>
          <p class="text-3xl font-semibold ${t.color}">${t.valor}</p>
        </div>`
        )
        .join("")}
    </div>
    ${renderContadoresCorrecciones(resultado)}
    ${renderMetricas(resultado.metricas)}
  `;
}

// Contadores del RF-13, con el cómputo exacto del "Contrato de la API":
// N = entradas con tipo distinto de "manual"; M = entradas con tipo "manual".
// Si hay correcciones (≥1 en total) se muestra SIEMPRE el de automáticas,
// aunque N sea 0 (p. ej. «0 celdas autocorregidas · 2 ediciones manuales»);
// el de manuales solo si M > 0. Sin correcciones no se muestra ninguno.
function renderContadoresCorrecciones(resultado) {
  const correcciones = resultado.correcciones || [];
  if (!correcciones.length) return "";
  const automaticas = correcciones.filter((c) => c.tipo !== "manual").length;
  const manuales = correcciones.length - automaticas;

  const partes = [];
  partes.push(`
      <span class="inline-flex items-center gap-2">
        <span class="w-2.5 h-2.5 rounded-full bg-amber-400"></span>
        <strong>${automaticas}</strong> ${automaticas === 1 ? "celda autocorregida" : "celdas autocorregidas"}
      </span>`);
  if (manuales > 0) {
    partes.push(`
      <span class="inline-flex items-center gap-2">
        <span class="w-2.5 h-2.5 rounded-full bg-blue-500"></span>
        <strong>${manuales}</strong> ${manuales === 1 ? "edición manual" : "ediciones manuales"}
      </span>`);
  }

  return `
    <div class="mt-4 bg-white rounded-xl border border-slate-200 px-4 py-3 flex flex-wrap items-center gap-x-8 gap-y-2 text-sm text-slate-700">
      ${partes.join("")}
    </div>
  `;
}

function renderMetricas(metricas) {
  if (!metricas || !metricas.columna) return "";
  const fmt = (n) =>
    n === null || n === undefined ? "—" : Number(n).toLocaleString("es-ES");
  return `
    <div class="mt-4 bg-white rounded-xl border border-slate-200 p-4">
      <p class="text-sm text-slate-500 mb-1">Métricas numéricas de "<span class="font-medium">${metricas.columna}</span>"</p>
      <div class="flex gap-8">
        <div><span class="text-slate-500 text-sm">Suma:</span> <span class="font-semibold">${fmt(metricas.suma)}</span></div>
        <div><span class="text-slate-500 text-sm">Media:</span> <span class="font-semibold">${fmt(metricas.media)}</span></div>
      </div>
    </div>
  `;
}
