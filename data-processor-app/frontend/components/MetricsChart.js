// Gráficas (Chart.js por CDN). Cada render destruye la anterior del mismo contenedor.

const graficas = new Map();

function pintar(canvas, clave, config) {
  if (graficas.has(clave)) graficas.get(clave).destroy();
  graficas.set(clave, new Chart(canvas.getContext("2d"), config));
}

const OPCIONES_BASE = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
};

export function renderMetricsChart(contenedor, resultado) {
  contenedor.innerHTML = `
    <div class="bg-white rounded-xl border border-slate-200 p-4">
      <h3 class="font-semibold mb-3 flex items-center gap-2">
        <i data-lucide="bar-chart-3" class="w-5 h-5 text-blue-600"></i>
        Distribución de validación
      </h3>
      <div class="chart-wrap"><canvas id="grafica-dist"></canvas></div>
    </div>
  `;

  pintar(contenedor.querySelector("#grafica-dist"), "dist", {
    type: "bar",
    data: {
      labels: ["Válidas", "Inválidas"],
      datasets: [
        {
          label: "Filas",
          data: [resultado.validas, resultado.invalidas],
          backgroundColor: ["#10b981", "#ef4444"],
          borderRadius: 6,
        },
      ],
    },
    options: { ...OPCIONES_BASE, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
  });

  if (window.lucide) window.lucide.createIcons();
}

export function renderErrorsByColumnChart(contenedor, resultado) {
  const conteo = {};
  for (const e of resultado.errores || []) {
    conteo[e.columna] = (conteo[e.columna] || 0) + 1;
  }
  const etiquetas = Object.keys(conteo);
  const valores = Object.values(conteo);

  if (!etiquetas.length) {
    contenedor.innerHTML = `
      <div class="bg-white rounded-xl border border-slate-200 p-4">
        <h3 class="font-semibold mb-3 flex items-center gap-2">
          <i data-lucide="alert-triangle" class="w-5 h-5 text-emerald-500"></i>
          Errores por columna
        </h3>
        <p class="text-sm text-slate-500">Sin errores: todas las filas son válidas.</p>
      </div>
    `;
    if (window.lucide) window.lucide.createIcons();
    return;
  }

  contenedor.innerHTML = `
    <div class="bg-white rounded-xl border border-slate-200 p-4">
      <h3 class="font-semibold mb-3 flex items-center gap-2">
        <i data-lucide="alert-triangle" class="w-5 h-5 text-amber-500"></i>
        Errores por columna
      </h3>
      <div class="chart-wrap"><canvas id="grafica-col"></canvas></div>
    </div>
  `;

  pintar(contenedor.querySelector("#grafica-col"), "col", {
    type: "bar",
    data: {
      labels: etiquetas,
      datasets: [
        {
          label: "Errores",
          data: valores,
          backgroundColor: "#f59e0b",
          borderRadius: 6,
        },
      ],
    },
    options: {
      ...OPCIONES_BASE,
      indexAxis: "y",
      scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
    },
  });

  if (window.lucide) window.lucide.createIcons();
}

export function renderHistogramChart(contenedor, resultado) {
  const metricas = resultado.metricas || {};
  const hist = metricas.histograma;
  const columna = metricas.columna;

  if (!hist || !hist.length) {
    contenedor.innerHTML = ""; // sin columna numérica: no se muestra
    return;
  }

  const etiquetas = hist.map((b) => `${redondear(b.min)} – ${redondear(b.max)}`);
  const valores = hist.map((b) => b.cantidad);

  contenedor.innerHTML = `
    <div class="bg-white rounded-xl border border-slate-200 p-4">
      <h3 class="font-semibold mb-3 flex items-center gap-2">
        <i data-lucide="activity" class="w-5 h-5 text-blue-600"></i>
        Distribución de "${columna}"
      </h3>
      <div class="chart-wrap"><canvas id="grafica-hist"></canvas></div>
    </div>
  `;

  pintar(contenedor.querySelector("#grafica-hist"), "hist", {
    type: "bar",
    data: {
      labels: etiquetas,
      datasets: [
        {
          label: "Frecuencia",
          data: valores,
          backgroundColor: "#3b82f6",
          borderRadius: 4,
        },
      ],
    },
    options: { ...OPCIONES_BASE, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
  });

  if (window.lucide) window.lucide.createIcons();
}

function redondear(n) {
  return Number(n).toLocaleString("es-ES", { maximumFractionDigits: 2 });
}
