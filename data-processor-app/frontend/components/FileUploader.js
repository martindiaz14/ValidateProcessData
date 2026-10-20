// Componente de carga: archivo de datos + editor de esquema en línea.
// El esquema se define con un formulario sencillo (nombre, tipo, requerido y
// parámetros) que genera el JSON que el backend ya entiende.

const TIPOS = {
  texto: { backend: "string", etiqueta: "Texto" },
  numero: { backend: "float", etiqueta: "Número" },
  fecha: { backend: "date", etiqueta: "Fecha" },
  email: { backend: "email", etiqueta: "Email" },
  enum: { backend: "enum", etiqueta: "Selección (enum)" },
  booleano: { backend: "boolean", etiqueta: "Sí / No" },
};

// Estado del formulario (una lista de campos)
let campos = [];
let contenedorCampos = null;
let inputTabla = null;
let previoJson = null;
// Aviso de app.js cuando cambia el archivo o el esquema (RF-16: invalida las
// ediciones pendientes). El interruptor de autocorrección NO lo dispara.
let notificarCambio = null;

function ejemploCampos() {
  return [
    { nombre: "id_transaccion", tipo: "texto", requerido: true, ejemplo: "TX-123" },
    { nombre: "cliente_email", tipo: "email", requerido: true },
    { nombre: "monto", tipo: "numero", requerido: true, min: "0.01", max: "" },
    { nombre: "fecha_pago", tipo: "fecha", requerido: true, formato: "YYYY-MM-DD" },
    { nombre: "estado", tipo: "enum", requerido: true, valores: "APROBADO, PENDIENTE, RECHAZADO" },
  ];
}

export function renderFileUploader(contenedor, onValidar, alCambiarEntrada) {
  notificarCambio = alCambiarEntrada || null;
  contenedor.innerHTML = `
    <div class="bg-white rounded-xl border border-slate-200 p-5 space-y-4">
      <h2 class="font-semibold flex items-center gap-2">
        <i data-lucide="upload" class="w-5 h-5 text-blue-600"></i>
        Cargar datos
      </h2>

      <label class="block">
        <span class="text-sm font-medium text-slate-600">Archivo de datos (CSV, JSON o Excel)</span>
        <input id="file-datos" name="file-datos" type="file" accept=".csv,.json,.xlsx"
          class="mt-1 block w-full text-sm text-slate-600 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100" />
        <!-- Tamaño máximo del archivo (RF-3): SIEMPRE visible y junto al
             campo; el texto inicial es el conservador de nube (4 MB) y
             app.js lo ajusta con el límite real del backend -->
        <p id="limite-tamano" class="text-xs text-slate-500 mt-1">Tamaño máximo del archivo: 4 MB.</p>
      </label>

      <div class="border-t border-slate-200 pt-4 space-y-3">
        <div class="flex items-center justify-between">
          <h3 class="font-semibold flex items-center gap-2">
            <i data-lucide="list-checks" class="w-5 h-5 text-blue-600"></i>
            Esquema de calidad
          </h3>
          <button id="btn-ejemplo" type="button" class="text-xs text-blue-600 hover:underline">Cargar ejemplo</button>
        </div>

        <label class="block sm:w-80">
          <span class="text-xs text-slate-500">Nombre de la tabla (opcional)</span>
          <input id="tabla-nombre" name="tabla-nombre" type="text" value="transacciones_pagos" placeholder="p. ej. transacciones"
            class="mt-1 block w-full text-sm border border-slate-300 rounded-md px-2 py-1.5" />
        </label>

        <div id="campos" class="space-y-3"></div>

        <button id="btn-add" type="button"
          class="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline">
          <i data-lucide="plus" class="w-4 h-4"></i> Añadir campo
        </button>

        <details class="text-sm">
          <summary class="cursor-pointer text-blue-600">Ver JSON generado</summary>
          <pre id="json-previo" class="mt-2 bg-slate-100 rounded-lg p-3 overflow-x-auto text-xs"></pre>
        </details>

        <label class="flex items-start gap-3 border border-slate-200 rounded-lg p-3 bg-slate-50 cursor-pointer sm:w-96"
          title="Normaliza espacios, formatos de número/fecha y enums antes de validar; nunca toca tu archivo original">
          <input id="autocorreccion" name="autocorreccion" type="checkbox" checked class="mt-0.5 w-5 h-5 shrink-0 text-blue-600" />
          <span>
            <span class="text-sm font-medium text-slate-700">Autocorrección</span>
            <span class="block text-xs text-slate-500">Normaliza espacios, formatos de número/fecha y enums antes de validar; nunca toca tu archivo original.</span>
          </span>
        </label>
      </div>

      <button id="btn-validar"
        class="w-full sm:w-auto inline-flex items-center gap-2 bg-blue-600 text-white px-5 py-2.5 rounded-lg hover:bg-blue-700 disabled:opacity-50">
        <i data-lucide="check-circle" class="w-5 h-5"></i>
        Validar
      </button>
    </div>
  `;

  contenedorCampos = contenedor.querySelector("#campos");
  inputTabla = contenedor.querySelector("#tabla-nombre");
  previoJson = contenedor.querySelector("#json-previo");

  campos = ejemploCampos();
  renderCampos();
  actualizarJson();

  contenedor.querySelector("#btn-add").addEventListener("click", () => {
    campos.push({ nombre: "", tipo: "texto", requerido: true });
    renderCampos();
    actualizarJson();
  });

  // El nombre de la tabla forma parte del esquema: refresca el JSON y avisa
  // de posibles ediciones pendientes igual que el resto de cambios (RF-16)
  inputTabla.addEventListener("input", actualizarJson);

  contenedor.querySelector("#btn-ejemplo").addEventListener("click", () => {
    campos = ejemploCampos();
    inputTabla.value = "transacciones_pagos";
    renderCampos();
    actualizarJson();
  });

  contenedor.querySelector("#btn-validar").addEventListener("click", () => {
    const datos = contenedor.querySelector("#file-datos").files[0];
    const autocorreccion = contenedor.querySelector("#autocorreccion").checked;
    onValidar(datos, generarJson(), autocorreccion);
  });

  // Cambiar el archivo seleccionado invalida las ediciones pendientes (RF-16)
  contenedor.querySelector("#file-datos").addEventListener("change", () => {
    if (notificarCambio) notificarCambio("archivo");
  });

  if (window.lucide) window.lucide.createIcons();
}

function renderCampos() {
  contenedorCampos.innerHTML = "";
  if (!campos.length) {
    contenedorCampos.innerHTML =
      `<p class="text-sm text-slate-400">Sin campos todavía. Pulsa "Añadir campo".</p>`;
    return;
  }
  // El índice solo sirve para id/name únicos de cada tarjeta (re-render al añadir/borrar)
  campos.forEach((campo, indice) => contenedorCampos.appendChild(filaCampo(campo, indice)));
}

function filaCampo(campo, indice) {
  const div = document.createElement("div");
  div.className = "border border-slate-200 rounded-lg p-3 space-y-2 bg-slate-50";
  div.innerHTML = `
    <div class="grid gap-2 sm:grid-cols-[1fr_auto_auto_auto] items-end">
      <label class="block">
        <span class="text-xs text-slate-500">Nombre del campo</span>
        <input type="text" id="campo-${indice}-nombre" name="campo-${indice}-nombre" data-rol="nombre" value="${esc(campo.nombre)}" placeholder="p. ej. monto"
          class="mt-1 block w-full text-sm border border-slate-300 rounded-md px-2 py-1.5" />
      </label>
      <label class="block">
        <span class="text-xs text-slate-500">Tipo</span>
        <select id="campo-${indice}-tipo" name="campo-${indice}-tipo" data-rol="tipo" class="mt-1 block text-sm border border-slate-300 rounded-md px-2 py-1.5">
          ${Object.entries(TIPOS)
            .map(([k, t]) => `<option value="${k}" ${campo.tipo === k ? "selected" : ""}>${t.etiqueta}</option>`)
            .join("")}
        </select>
      </label>
      <label class="flex items-center gap-2 pb-2">
        <input type="checkbox" id="campo-${indice}-requerido" name="campo-${indice}-requerido" data-rol="requerido" ${campo.requerido ? "checked" : ""} class="w-4 h-4" />
        <span class="text-sm text-slate-600">Requerido</span>
      </label>
      <button type="button" data-rol="eliminar" class="text-red-500 hover:text-red-700 text-sm pb-2">Eliminar</button>
    </div>
    <div data-rol="params"></div>
  `;

  const params = div.querySelector('[data-rol="params"]');

  function pintarParams() {
    params.innerHTML = paramsHtml(campo, indice);
    params.querySelectorAll("input[data-rol]").forEach((inp) => {
      inp.addEventListener("input", () => {
        campo[inp.dataset.rol] = inp.value;
        actualizarJson();
      });
    });
  }
  pintarParams();

  div.querySelector('[data-rol="nombre"]').addEventListener("input", (e) => {
    campo.nombre = e.target.value;
    actualizarJson();
  });
  div.querySelector('[data-rol="tipo"]').addEventListener("change", (e) => {
    campo.tipo = e.target.value;
    // Limpia los parámetros que no aplican al nuevo tipo
    campo.ejemplo = campo.min = campo.max = campo.formato = campo.valores = "";
    pintarParams();
    actualizarJson();
  });
  div.querySelector('[data-rol="requerido"]').addEventListener("change", (e) => {
    campo.requerido = e.target.checked;
    actualizarJson();
  });
  div.querySelector('[data-rol="eliminar"]').addEventListener("click", () => {
    const i = campos.indexOf(campo);
    if (i >= 0) campos.splice(i, 1);
    renderCampos();
    actualizarJson();
  });

  return div;
}

function paramsHtml(c, indice) {
  const prefijo = `campo-${indice}`;
  if (c.tipo === "texto") {
    return campoTexto("ejemplo", "Texto de ejemplo (opcional)", c.ejemplo, "p. ej. TX-123", "text", prefijo);
  }
  if (c.tipo === "numero") {
    return `<div class="grid grid-cols-2 gap-2">
      ${campoTexto("min", "Mínimo (opcional)", c.min, "p. ej. 0.01", "number", prefijo)}
      ${campoTexto("max", "Máximo (opcional)", c.max, "p. ej. 1000", "number", prefijo)}
    </div>`;
  }
  if (c.tipo === "fecha") {
    return campoTexto("formato", "Formato (opcional)", c.formato, "YYYY-MM-DD", "text", prefijo);
  }
  if (c.tipo === "enum") {
    return campoTexto("valores", "Valores permitidos (separados por coma)", c.valores, "APROBADO, PENDIENTE, RECHAZADO", "text", prefijo);
  }
  return `<p class="text-xs text-slate-400">Sin parámetros adicionales.</p>`;
}

function campoTexto(rol, etiqueta, valor, placeholder, tipo = "text", prefijo = "") {
  const id = prefijo ? `${prefijo}-${rol}` : "";
  return `<label class="block">
    <span class="text-xs text-slate-500">${etiqueta}</span>
    <input type="${tipo}"${id ? ` id="${id}" name="${id}"` : ""} data-rol="${rol}" value="${esc(valor)}" placeholder="${esc(placeholder)}"
      class="mt-1 block w-full text-sm border border-slate-300 rounded-md px-2 py-1.5" />
  </label>`;
}

function generarJson() {
  const rules = {};
  for (const c of campos) {
    const nombre = (c.nombre || "").trim();
    if (!nombre) continue;

    const regla = { type: TIPOS[c.tipo].backend, required: !!c.requerido };
    if (c.tipo === "texto" && (c.ejemplo || "").trim()) regla.pattern = ejemploAPatron(c.ejemplo);
    if (c.tipo === "numero") {
      if ((c.min || "").trim() !== "" && !isNaN(Number(c.min))) regla.min_value = Number(c.min);
      if ((c.max || "").trim() !== "" && !isNaN(Number(c.max))) regla.max_value = Number(c.max);
    }
    if (c.tipo === "fecha" && (c.formato || "").trim()) regla.format = c.formato.trim();
    if (c.tipo === "enum" && (c.valores || "").trim()) {
      regla.allowed_values = c.valores.split(",").map((s) => s.trim()).filter((s) => s !== "");
    }
    rules[nombre] = regla;
  }

  const esquema = {};
  const tabla = (inputTabla && inputTabla.value || "").trim();
  if (tabla) esquema.table_name = tabla;
  esquema.rules = rules;
  return JSON.stringify(esquema, null, 2);
}

function actualizarJson() {
  if (previoJson) previoJson.textContent = generarJson();
  // Cualquier cambio en el esquema invalida las ediciones pendientes (RF-16);
  // app.js decide avisar (no hace nada si no hay pendientes)
  if (notificarCambio) notificarCambio("esquema");
}

// Convierte un texto de ejemplo en una regla que comprueba que los valores
// "se parezcan": las tiras de dígitos → \d+, las de letras → [A-Za-z]…,
// los espacios → \s+ y el resto se toma literal (se escapando).
function ejemploAPatron(ejemplo) {
  const e = (ejemplo || "").trim();
  if (!e) return "";
  const clase = claseLetras(e);
  const reLetra = /[A-Za-zÁÉÍÓÚÜÑáéíóúüñÀÈÌÒÙàèìòùçÇ]/;
  let salida = "";
  let i = 0;
  while (i < e.length) {
    const c = e[i];
    if (/[0-9]/.test(c)) {
      while (i < e.length && /[0-9]/.test(e[i])) i++;
      salida += "\\d+";
    } else if (reLetra.test(c)) {
      while (i < e.length && reLetra.test(e[i])) i++;
      salida += clase + "+";
    } else if (/\s/.test(c)) {
      while (i < e.length && /\s/.test(e[i])) i++;
      salida += "\\s+";
    } else {
      salida += escaparRegex(c);
      i++;
    }
  }
  return "^" + salida + "$";
}

function escaparRegex(c) {
  return c.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function claseLetras(ejemplo) {
  return /[ÁÉÍÓÚÜÑáéíóúüñÀÈÌÒÙàèìòùçÇ]/.test(ejemplo)
    ? "[A-Za-zÁÉÍÓÚÜÑáéíóúüñÀÈÌÒÙàèìòùçÇ]"
    : "[A-Za-z]";
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// Tamaño máximo del archivo (RF-3, spec 004): actualiza el texto de
// `#limite-tamano` con el límite que devuelve /api/v1/entorno; tolera que el
// formulario aún no esté montado (no hay nada que actualizar)
export function actualizarLimiteSubida(limiteMb) {
  const texto = document.getElementById("limite-tamano");
  if (!texto) return;
  texto.textContent = `Tamaño máximo del archivo: ${limiteMb} MB.`;
}
