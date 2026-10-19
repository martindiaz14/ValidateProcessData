// Bloque "Descargas" (RF-14): original, corregido (CSV/JSON) e informe de
// errores (CSV/JSON). Todo se genera en el navegador con lo que ya está en
// memoria (RNF-3): sin endpoint nuevo ni servicios externos.

const AVISO_TOPE =
  "Archivo demasiado grande para generar la copia corregida (más de 100.000 filas).";

export function renderExportButtons(contenedor, resultado, archivo) {
  const corregidaDisponible = resultado.descarga_corregida_disponible !== false;

  contenedor.innerHTML = `
    <div class="bg-white rounded-xl border border-slate-200 p-4">
      <h3 class="font-semibold mb-3 flex items-center gap-2">
        <i data-lucide="download" class="w-5 h-5 text-blue-600"></i>
        Descargas
      </h3>
      <div class="flex flex-wrap gap-3">
        ${botonDescarga("btn-original", "Archivo original", false)}
        ${botonDescarga("btn-corregido-csv", "Archivo corregido (CSV)", !corregidaDisponible)}
        ${botonDescarga("btn-corregido-json", "Archivo corregido (JSON)", !corregidaDisponible)}
        ${botonDescarga("btn-errores-csv", "Informe de errores (CSV)", false)}
        ${botonDescarga("btn-errores-json", "Informe de errores (JSON)", false)}
      </div>
      ${corregidaDisponible ? "" : `
      <p class="mt-3 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 flex items-start gap-2">
        <i data-lucide="alert-triangle" class="w-4 h-4 mt-0.5 shrink-0"></i>
        <span>${AVISO_TOPE}</span>
      </p>`}
    </div>
  `;

  const base = nombreBase(archivo);

  // Original: los MISMOS bytes que se subieron, cualquier formato (RNF-3)
  contenedor.querySelector("#btn-original").addEventListener("click", () => {
    if (archivo) descargarBlob(archivo.name, archivo);
  });

  // Corregido: desde `filas_corregidas` de la respuesta; si viene vacío (sin
  // correcciones y no es .xlsx) se regenera aquí desde el archivo original
  contenedor.querySelector("#btn-corregido-csv").addEventListener("click", async () => {
    const filas = await filasCorregidas(resultado, archivo);
    descargar(`${base}_corregido.csv`, aCsvFilas(filas, resultado.columnas), "text/csv;charset=utf-8");
  });
  contenedor.querySelector("#btn-corregido-json").addEventListener("click", async () => {
    const filas = await filasCorregidas(resultado, archivo);
    descargar(`${base}_corregido.json`, JSON.stringify(filas, null, 2), "application/json");
  });

  contenedor.querySelector("#btn-errores-csv").addEventListener("click", () => {
    descargar("errores.csv", aCsvErrores(resultado), "text/csv;charset=utf-8");
  });
  contenedor.querySelector("#btn-errores-json").addEventListener("click", () => {
    descargar("reporte.json", JSON.stringify(resultado, null, 2), "application/json");
  });

  if (window.lucide) window.lucide.createIcons();
}

function botonDescarga(id, etiqueta, deshabilitado) {
  return `
    <button id="${id}" type="button" ${deshabilitado ? "disabled title=\"No disponible: el archivo supera las 100.000 filas.\"" : ""}
      class="inline-flex items-center gap-2 bg-white border border-slate-300 text-slate-700 px-4 py-2 rounded-lg hover:bg-slate-50 text-sm disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-white">
      <i data-lucide="download" class="w-4 h-4"></i>
      ${etiqueta}
    </button>`;
}

function nombreBase(archivo) {
  const nombre = (archivo && archivo.name) || "datos";
  const punto = nombre.lastIndexOf(".");
  return punto > 0 ? nombre.slice(0, punto) : nombre;
}

// Filas a descargar en la versión corregida: las que envió el backend o, si no
// vienen (la descarga sale idéntica a la normal), las del archivo original
function filasCorregidas(resultado, archivo) {
  if ((resultado.filas_corregidas || []).length) return resultado.filas_corregidas;
  return filasDesdeOriginal(archivo);
}

// Regenera las filas del original en el navegador: JSON.parse para .json y un
// parser CSV propio mínimo (RFC 4180: comillas y comillas dobles) para .csv
function filasDesdeOriginal(archivo) {
  if (!archivo) return [];
  return archivo.text().then((texto) => {
    const nombre = (archivo.name || "").toLowerCase();
    if (nombre.endsWith(".json")) {
      const datos = JSON.parse(texto);
      return Array.isArray(datos) ? datos : [];
    }
    return parseCsv(texto);
  });
}

function parseCsv(texto) {
  const t = texto.charCodeAt(0) === 0xfeff ? texto.slice(1) : texto;
  const filas = [];
  let fila = [];
  let celda = "";
  let entreComillas = false;

  for (let i = 0; i < t.length; i++) {
    const c = t[i];
    if (entreComillas) {
      if (c === '"') {
        if (t[i + 1] === '"') {
          celda += '"';
          i++;
        } else {
          entreComillas = false;
        }
      } else {
        celda += c;
      }
    } else if (c === '"') {
      entreComillas = true;
    } else if (c === ",") {
      fila.push(celda);
      celda = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && t[i + 1] === "\n") i++;
      fila.push(celda);
      celda = "";
      filas.push(fila);
      fila = [];
    } else {
      celda += c;
    }
  }
  if (celda !== "" || fila.length) {
    fila.push(celda);
    filas.push(fila);
  }

  if (!filas.length) return [];
  const [cabecera, ...datos] = filas;
  return datos.map((f) =>
    Object.fromEntries(cabecera.map((col, i) => [col, f[i] ?? ""]))
  );
}

// CSV de la versión corregida: cabecera = `columnas`, TODAS las filas, números
// con punto decimal y sin separadores de miles (String), vacíos como celda
// vacía, comillas RFC-4180 y BOM (como el CSV de errores de siempre)
function aCsvFilas(filas, columnas) {
  const cols = columnas || (filas.length ? Object.keys(filas[0]) : []);
  const lineas = [cols.map(celdaCsv).join(",")];
  for (const f of filas) {
    lineas.push(cols.map((col) => celdaCsv(f[col])).join(","));
  }
  return "\uFEFF" + lineas.join("\n");
}

function aCsvErrores(resultado) {
  const lineas = ["fila,columna,motivo"];
  for (const e of resultado.errores || []) {
    lineas.push([e.fila, e.columna, e.motivo].map(celdaCsv).join(","));
  }
  // BOM para que Excel abra bien los acentos
  return "\uFEFF" + lineas.join("\n");
}

function celdaCsv(valor) {
  const s = String(valor ?? "");
  return /[",;\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function descargar(nombre, contenido, mime) {
  descargarBlob(nombre, new Blob([contenido], { type: mime }));
}

function descargarBlob(nombre, blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
