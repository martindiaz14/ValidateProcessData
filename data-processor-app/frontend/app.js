// Lógica de la interfaz: recoge la entrada del usuario, llama a la API y pinta.
// No valida datos aquí: la validación vive en el backend (services/).

import { renderFileUploader, actualizarLimiteSubida } from "/components/FileUploader.js";
import { renderValidationSummary } from "/components/ValidationSummary.js";
import { renderExportButtons } from "/components/ExportButtons.js";
import {
  renderMetricsChart,
  renderErrorsByColumnChart,
  renderHistogramChart,
} from "/components/MetricsChart.js";
import { renderRowPreview } from "/components/RowPreview.js";
import { renderHelpModal } from "/components/HelpModal.js";

const uploader = document.getElementById("uploader");
const seccionResultados = document.getElementById("resultados");
const seccionError = document.getElementById("error");

// Estado de la edición manual (RF-16/RF-17): edicionesPendientes es un Map
// "fila:columna" -> {fila, columna, valor}; solo el botón "Aplicar cambios y
// revalidar" las envía, en la MISMA petición que archivo + esquema + interruptor
const edicionesPendientes = new Map();
let ultimoResultado = null; // última respuesta válida, para repintar
let archivoValidado = null; // archivo de la última validación
let esquemaValidado = null; // esquema de la última validación
let autocorreccionValidada = false; // interruptor de la última validación

renderHelpModal();
renderFileUploader(uploader, manejarValidacion, manejarCambioEntrada);

// RF-1/RF-2/RF-3 (spec 004): al cargar, el navegador pregunta el entorno al
// backend. Local → sin badge ni banner y el límite del backend; nube → badge
// y banner visibles; SI LA CONSULTA FALLA (o el JSON no es válido) → badge y
// banner IGUALMENTE con el límite conservador de nube: ante la duda se avisa
// y NUNCA se oculta el aviso de privacidad (decisión del usuario). El límite
// REAL de subida lo sigue fijando el backend con su 413; esto es informativo
async function consultarEntorno() {
  let modo = "nube"; // por defecto, lo conservador: fallo = se avisa
  let limite = 4;
  try {
    const respuesta = await fetch("/api/v1/entorno");
    if (!respuesta.ok) throw new Error("respuesta sin 200");
    const datos = await respuesta.json();
    if (datos && (datos.modo === "local" || datos.modo === "nube")) {
      modo = datos.modo;
      limite = Number(datos.limite_mb) > 0 ? Number(datos.limite_mb) : 4;
    } else {
      throw new Error("JSON sin modo reconocido");
    }
  } catch {
    modo = "nube";
    limite = 4;
  }
  const esDemo = modo === "nube";
  document.getElementById("badge-demo").classList.toggle("hidden", !esDemo);
  document.getElementById("banner-demo").classList.toggle("hidden", !esDemo);
  actualizarLimiteSubida(limite);
}

consultarEntorno();

async function manejarValidacion(archivoDatos, esquemaTexto, autocorreccion) {
  ocultarError();

  if (!archivoDatos) {
    mostrarError("Selecciona el archivo de datos.");
    return;
  }
  if (!esquemaTexto || !esquemaTexto.trim()) {
    mostrarError("Escribe o pega el esquema de calidad en JSON.");
    return;
  }

  // RF-16: "Validar" envía una validación NUEVA sin ediciones; si hay
  // pendientes se descartan y se avisa en español
  if (edicionesPendientes.size > 0) {
    descartarPendientes(
      "Se descartaron las ediciones pendientes: el botón «Validar» valida el archivo sin ellas."
    );
  } else {
    limpiarAviso();
  }

  archivoValidado = archivoDatos;
  esquemaValidado = esquemaTexto;
  autocorreccionValidada = !!autocorreccion;

  const formData = new FormData();
  formData.append("file", archivoDatos);
  formData.append("quality_schema", esquemaTexto);
  // El backend solo autocorrige si el campo viene explícito (por defecto no)
  formData.append("autocorreccion", autocorreccion ? "true" : "false");

  await enviarValidacion(formData);
}

// ÚNICA acción que envía ediciones (RF-17): el lote va junto al archivo, el
// esquema y el interruptor en la misma petición
async function manejarAplicarCambios() {
  if (edicionesPendientes.size === 0) return;
  ocultarError();

  const formData = new FormData();
  formData.append("file", archivoValidado);
  formData.append("quality_schema", esquemaValidado);
  formData.append("autocorreccion", autocorreccionValidada ? "true" : "false");
  formData.append("ediciones", JSON.stringify([...edicionesPendientes.values()]));

  await enviarValidacion(formData, { limpiarPendientes: true });
}

async function enviarValidacion(formData, { limpiarPendientes = false } = {}) {
  try {
    const respuesta = await fetch("/api/v1/upload", {
      method: "POST",
      body: formData,
    });

    const datos = await respuesta.json();

    if (!respuesta.ok) {
      // El lote sigue pendiente (no se limpia): el usuario puede reintentar
      mostrarError(datos.detail || "No se pudo validar el archivo.");
      return;
    }

    if (limpiarPendientes) {
      edicionesPendientes.clear();
      limpiarAviso();
    }
    ultimoResultado = datos;
    pintarResultado(datos);
  } catch (err) {
    mostrarError("Error de conexión con el servidor. ¿Está arrancado el backend?");
  }
}

// El componente de vista previa comunica cada celda confirmada (RF-16):
// valor null = quitar la pendiente de esa celda (dejarlo como estaba)
function manejarEdicionCelda(fila, columna, valor) {
  const clave = `${fila}:${columna}`;
  if (valor === null || valor === undefined) {
    edicionesPendientes.delete(clave);
  } else {
    edicionesPendientes.set(clave, { fila, columna, valor });
  }
}

// Cambiar el archivo o el esquema invalida las ediciones pendientes (RF-16);
// el interruptor de autocorrección no entra aquí
function manejarCambioEntrada(tipo) {
  if (edicionesPendientes.size === 0) return;
  const motivo =
    tipo === "archivo" ? "el archivo seleccionado" : "el esquema de calidad";
  descartarPendientes(
    `Se descartaron las ediciones pendientes al cambiar ${motivo}.`
  );
}

function descartarPendientes(mensaje) {
  edicionesPendientes.clear();
  if (ultimoResultado) pintarResultado(ultimoResultado);
  mostrarAviso(mensaje);
}

function pintarResultado(datos) {
  seccionError.classList.add("hidden");
  seccionResultados.classList.remove("hidden");

  renderValidationSummary(document.getElementById("summary"), datos);
  renderExportButtons(document.getElementById("exportar"), datos, archivoValidado);
  renderCorrecciones(datos);
  renderMetricsChart(document.getElementById("chart"), datos);
  renderErrorsByColumnChart(document.getElementById("chart-columnas"), datos);
  renderHistogramChart(document.getElementById("chart-histograma"), datos);
  renderRowPreview(document.getElementById("preview"), datos, {
    pendientes: edicionesPendientes,
    onEditarCelda: manejarEdicionCelda,
    onAplicarCambios: manejarAplicarCambios,
  });
  renderErrores(datos.errores);

  if (window.lucide) window.lucide.createIcons();
}

function renderErrores(errores) {
  const contenedor = document.getElementById("errores");
  if (!errores || errores.length === 0) {
    contenedor.innerHTML = "";
    return;
  }

  const filas = errores
    .slice(0, 50)
    .map(
      (e) => `
      <tr class="border-t border-slate-100">
        <td class="py-2 px-3">${e.fila}</td>
        <td class="py-2 px-3">${e.columna}</td>
        <td class="py-2 px-3 text-red-600">${e.motivo}</td>
      </tr>`
    )
    .join("");

  contenedor.innerHTML = `
    <div class="bg-white rounded-xl border border-slate-200 p-4">
      <h3 class="font-semibold mb-3 flex items-center gap-2">
        <i data-lucide="alert-triangle" class="w-5 h-5 text-amber-500"></i>
        Errores por fila (${errores.length})
      </h3>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="text-left text-slate-500">
            <tr>
              <th class="py-2 px-3">Fila</th>
              <th class="py-2 px-3">Columna</th>
              <th class="py-2 px-3">Motivo</th>
            </tr>
          </thead>
          <tbody>${filas}</tbody>
        </table>
      </div>
      ${errores.length > 50 ? `<p class="text-xs text-slate-400 mt-2">Mostrando las primeras 50 de ${errores.length}.</p>` : ""}
    </div>
  `;
}

function mostrarError(mensaje) {
  seccionResultados.classList.add("hidden");
  seccionError.classList.remove("hidden");
  seccionError.innerHTML = `
    <div class="bg-red-50 border border-red-200 text-red-700 rounded-xl p-4 flex items-start gap-2">
      <i data-lucide="x-circle" class="w-5 h-5 mt-0.5"></i>
      <span>${mensaje}</span>
    </div>
  `;
  if (window.lucide) window.lucide.createIcons();
}

// Etiqueta legible para cada tipo del vocabulario cerrado del contrato (RF-9)
const TIPOS_CORRECCION = {
  espacios: "Espacios",
  invisibles: "Caracteres invisibles",
  minusculas: "Minúsculas",
  enum: "Selección (enum)",
  numero: "Número",
  fecha: "Fecha",
  vacio: "Vacío",
  manual: "Manual",
};

// Sección "Correcciones aplicadas" (RF-13): las PRIMERAS 50 entradas de
// `correcciones`, con fila, columna, antes → después y tipo; las automáticas
// en ámbar y las manuales en azul. Sin correcciones no se pinta nada.
function renderCorrecciones(datos) {
  const contenedor = document.getElementById("correcciones");
  const correcciones = datos.correcciones || [];
  if (!correcciones.length) {
    contenedor.innerHTML = "";
    return;
  }

  const total = correcciones.length;
  const visibles = correcciones.slice(0, 50);
  const mostrarValor = (v) =>
    v === null || v === undefined || v === "" ? "—" : escHtml(String(v));

  const filas = visibles
    .map((c) => {
      const esManual = c.tipo === "manual";
      const etiqueta = TIPOS_CORRECCION[c.tipo] || escHtml(String(c.tipo));
      const badge = esManual
        ? `<span class="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">Manual</span>`
        : `<span class="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">Autocorrección · ${etiqueta}</span>`;
      return `
      <tr class="border-t border-slate-100">
        <td class="py-2 px-3">${c.fila}</td>
        <td class="py-2 px-3 whitespace-nowrap">${escHtml(String(c.columna))}</td>
        <td class="py-2 px-3 text-slate-500 whitespace-pre">${mostrarValor(c.antes)}</td>
        <td class="py-2 px-3 whitespace-pre">${mostrarValor(c.despues)}</td>
        <td class="py-2 px-3 whitespace-nowrap">${badge}</td>
      </tr>`;
    })
    .join("");

  contenedor.innerHTML = `
    <div class="bg-white rounded-xl border border-slate-200 p-4">
      <h3 class="font-semibold mb-3 flex items-center gap-2">
        <i data-lucide="wand-2" class="w-5 h-5 text-amber-500"></i>
        Correcciones aplicadas (${total})
      </h3>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="text-left text-slate-500">
            <tr>
              <th class="py-2 px-3">Fila</th>
              <th class="py-2 px-3">Columna</th>
              <th class="py-2 px-3">Antes</th>
              <th class="py-2 px-3">Después</th>
              <th class="py-2 px-3">Tipo</th>
            </tr>
          </thead>
          <tbody>${filas}</tbody>
        </table>
      </div>
      ${total > visibles.length ? `<p class="text-xs text-slate-400 mt-2">Mostrando ${visibles.length} de ${total} correcciones.</p>` : ""}
    </div>
  `;
  if (window.lucide) window.lucide.createIcons();
}

function escHtml(valor) {
  return String(valor ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// Aviso no bloqueante (p. ej. ediciones pendientes descartadas): vive en su
// propio contenedor #aviso, fuera de #resultados, para no ocultar resultados
function mostrarAviso(mensaje) {
  const seccionAviso = document.getElementById("aviso");
  seccionAviso.classList.remove("hidden");
  seccionAviso.innerHTML = `
    <div class="bg-amber-50 border border-amber-200 text-amber-800 rounded-xl p-4 flex items-start gap-2">
      <i data-lucide="alert-triangle" class="w-5 h-5 mt-0.5"></i>
      <span>${mensaje}</span>
    </div>
  `;
  if (window.lucide) window.lucide.createIcons();
}

function limpiarAviso() {
  const seccionAviso = document.getElementById("aviso");
  seccionAviso.classList.add("hidden");
  seccionAviso.innerHTML = "";
}

function ocultarError() {
  seccionError.classList.add("hidden");
  seccionError.innerHTML = "";
}
