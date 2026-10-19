// Vista previa de filas: error residual en rojo, celdas corregidas en ámbar
// (con el valor "antes" en el tooltip de escritorio) y edición manual de las
// celdas con error o corregidas (RF-11, RF-16 y RF-17 de la spec 003).
// «Vista previa de errores» (RF-11): cuando hay filas de interés (error
// residual o alguna corrección) solo se muestran ESAS, con su número de fila
// REAL desde `muestra_filas` (T11); sin ninguna de interés se comporta como
// el fallback de siempre (primeras filas, nada editable, RF-16). La vista
// previa es SIN LÍMITE (decisión «sin límite»): se muestran TODAS las filas
// de interés y encima de la tabla va el contador «X filas con errores o
// correcciones · Y incidencias» (X e Y del cruce errores ∪ correcciones,
// derivados en el navegador); desde 2.000 filas de interés se añade un aviso
// de volumen no bloqueante.

export function renderRowPreview(contenedor, resultado, opciones = {}) {
  const pendientes = opciones.pendientes || new Map();
  const onEditarCelda = opciones.onEditarCelda || (() => {});
  const onAplicarCambios = opciones.onAplicarCambios || (() => {});

  const columnas = resultado.columnas || [];
  const muestra = resultado.muestra || [];

  if (!muestra.length) {
    contenedor.innerHTML = "";
    return;
  }

  // Números de fila REALES de cada entrada de `muestra` (T11); el `i + 1` es
  // solo un fallback defensivo por compatibilidad si el campo viniera vacío
  const numerosFila = resultado.muestra_filas || [];
  const numFilaDe = (i) =>
    Number.isInteger(numerosFila[i]) ? numerosFila[i] : i + 1;

  // Contador del RF-11: filas de interés (unión de números de fila de
  // errores ∪ correcciones) e INCIDENCIAS totales (celda fila + columna de
  // esa unión; una celda con error Y corrección cuenta 1 sola). El backend
  // ya no trae tope: se muestran TODAS las filas de interés y este contador
  // va SIEMPRE encima de la tabla (en fallback no hay: no hay nada que
  // contar); el aviso de volumen aparece desde 2.000 filas de interés
  const celdasIncidencia = new Set();
  const filasInteres = new Set();
  const registrarIncidencia = (clave, fila) => {
    celdasIncidencia.add(clave);
    filasInteres.add(fila);
  };

  // "fila:columna" con error residual: números de fila reales de la respuesta
  const conError = new Set();
  for (const e of resultado.errores || []) {
    const clave = `${e.fila}:${e.columna}`;
    if (!celdasIncidencia.has(clave)) registrarIncidencia(clave, e.fila);
    conError.add(clave);
  }

  // "fila:columna" corregida: ámbar con el `antes` de la PRIMERA entrada (RF-11)
  const conCorreccion = new Map();
  for (const c of resultado.correcciones || []) {
    const clave = `${c.fila}:${c.columna}`;
    if (!celdasIncidencia.has(clave)) registrarIncidencia(clave, c.fila);
    if (!conCorreccion.has(clave)) conCorreccion.set(clave, c.antes);
  }
  const hayInteres = filasInteres.size > 0;

  const filasHtml = muestra
    .map((fila, i) => {
      const numFila = numFilaDe(i);
      const celdas = columnas
        .map((col) => celdaHtml(numFila, col, fila[col], conError, conCorreccion, pendientes, hayInteres))
        .join("");
      return `<tr><td class="py-1.5 px-2 text-slate-400 border-t border-slate-100">${numFila}</td>${celdas}</tr>`;
    })
    .join("");

  // Contador SIEMPRE visible encima de la tabla cuando hay filas de interés
  // (RF-11): «X filas con errores o correcciones · Y incidencias», con
  // singular correcto; desde 2.000 filas, aviso de volumen no bloqueante.
  // En fallback, la nota clásica de las primeras 50 (sin contador)
  let contador = "";
  let nota = "";
  if (hayInteres) {
    const x = filasInteres.size;
    const y = celdasIncidencia.size;
    contador =
      `<p class="text-sm text-slate-600 mb-2">` +
      `${x} ${x === 1 ? "fila con errores o correcciones" : "filas con errores o correcciones"}` +
      ` · ${y} ${y === 1 ? "incidencia" : "incidencias"}</p>`;
    if (x >= 2000) {
      contador +=
        `<p class="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-3 py-2 mb-2">` +
        `Esta vista previa tiene ${x} filas con errores o correcciones; puede tardar en mostrarse.</p>`;
    }
  } else if (resultado.total_filas > muestra.length) {
    nota = `<p class="text-xs text-slate-400 mt-2">Mostrando las primeras ${muestra.length} de ${resultado.total_filas} filas.</p>`;
  }

  const titulo = hayInteres ? "Vista Previa de Errores" : "Vista previa de filas";

  contenedor.innerHTML = `
    <div class="bg-white rounded-xl border border-slate-200 p-4">
      <h3 class="font-semibold mb-3 flex items-center gap-2">
        <i data-lucide="table" class="w-5 h-5 text-blue-600"></i>
        ${titulo}
      </h3>
      ${contador}
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="text-left text-slate-500">
            <tr>
              <th class="py-2 px-2">#</th>
              ${columnas.map((col) => `<th class="py-2 px-2 whitespace-nowrap">${esc(col)}</th>`).join("")}
            </tr>
          </thead>
          <tbody>${filasHtml}</tbody>
        </table>
      </div>
      <div class="mt-3 flex flex-col sm:flex-row sm:items-center gap-3">
        <button id="btn-aplicar" type="button" ${pendientes.size ? "" : "disabled"}
          class="w-full sm:w-auto inline-flex items-center justify-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed">
          <i data-lucide="check-check" class="w-4 h-4"></i>
          Aplicar cambios y revalidar
        </button>
        <p id="preview-ayuda" class="text-xs text-slate-500">${ayudaEdicion(pendientes)}</p>
      </div>
      ${nota}
      <p class="text-xs text-slate-400 mt-2">Rojo: error. Ámbar: corregido (pasa el cursor para ver el valor antes).</p>
    </div>
  `;

  contenedor.querySelector("#btn-aplicar").addEventListener("click", () => {
    if (pendientes.size === 0) return;
    onAplicarCambios();
  });

  // Edición in-situ: al pulsar una celda editable se abre un campo (RF-16)
  contenedor.querySelector("tbody").addEventListener("click", (ev) => {
    const td = ev.target.closest("td[data-editable]");
    if (!td || td.querySelector("input")) return;
    abrirEditor(td, pendientes, onEditarCelda, () => {
      contenedor.querySelector("#btn-aplicar").disabled = pendientes.size === 0;
      contenedor.querySelector("#preview-ayuda").textContent = ayudaEdicion(pendientes);
    });
  });

  if (window.lucide) window.lucide.createIcons();
}

function celdaHtml(numFila, col, valor, conError, conCorreccion, pendientes, hayInteres) {
  const clave = `${numFila}:${col}`;
  const mostrar = valor === null || valor === undefined ? "" : esc(valor);
  const falla = conError.has(clave);
  const corregida = conCorreccion.has(clave);
  const pendiente = pendientes.has(clave);
  // Editables solo con error o corregidas (RF-16); en fallback (sin filas de
  // interés) NINGUNA celda es editable
  const editable = hayInteres && (falla || corregida);

  let clase = "py-1.5 px-2 border-t border-slate-100";
  if (editable) clase += " cursor-pointer hover:ring-1 hover:ring-blue-300";
  // Gana el error sobre el ámbar (RF-11); el anillo azul marca lo pendiente
  if (falla) clase += " bg-red-100 text-red-700 font-semibold";
  else if (corregida) clase += " bg-amber-100 text-amber-800";
  if (pendiente) clase += " ring-2 ring-blue-400";

  const titulo = corregida && !falla ? ` title="Antes: ${escAtributo(conCorreccion.get(clave))}"` : "";
  const attrs = editable
    ? ` data-editable data-fila="${numFila}" data-col="${escAtributo(col)}"` +
      ` data-valor="${escAtributo(valor === null || valor === undefined ? "" : valor)}"` +
      ` data-falla="${falla ? 1 : 0}" data-corregida="${corregida ? 1 : 0}"`
    : "";
  return `<td class="${clase}"${attrs}${titulo}>${mostrar}</td>`;
}

function abrirEditor(td, pendientes, onEditarCelda, alCambiarPendientes) {
  const clave = `${td.dataset.fila}:${td.dataset.col}`;
  const pendiente = pendientes.get(clave);
  const inicial = pendiente ? pendiente.valor : td.dataset.valor;

  const input = document.createElement("input");
  input.type = "text";
  input.id = "edicion-celda";
  input.name = "edicion-celda";
  input.value = inicial; // vaciarlo y confirmar deja la celda vacía
  input.className = "w-full min-w-24 px-1 py-0.5 text-sm border border-blue-400 rounded";
  td.innerHTML = "";
  td.appendChild(input);
  input.focus();
  input.select();

  let cerrado = false;
  const cerrar = (confirmar) => {
    if (cerrado) return;
    cerrado = true;
    if (confirmar) {
      const fila = Number(td.dataset.fila);
      const col = td.dataset.col;
      // Dejarlo como estaba = quitar la edición pendiente de esa celda
      const sinCambios = input.value === td.dataset.valor;
      onEditarCelda(fila, col, sinCambios ? null : input.value);
      alCambiarPendientes();
    }
    repintarCelda(td, pendientes);
  };

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") cerrar(true);
    else if (e.key === "Escape") cerrar(false);
  });
  input.addEventListener("blur", () => cerrar(true));
}

function repintarCelda(td, pendientes) {
  const clave = `${td.dataset.fila}:${td.dataset.col}`;
  const falla = td.dataset.falla === "1";
  const corregida = td.dataset.corregida === "1";
  const pendiente = pendientes.has(clave);

  let clase = "py-1.5 px-2 border-t border-slate-100";
  if (falla) clase += " bg-red-100 text-red-700 font-semibold";
  else if (corregida) clase += " bg-amber-100 text-amber-800";
  if (pendiente) clase += " ring-2 ring-blue-400";
  td.className = clase;
  td.textContent = pendiente ? pendientes.get(clave).valor : td.dataset.valor;
}

function ayudaEdicion(pendientes) {
  if (pendientes.size === 0) {
    return "Pulsa una celda en rojo o ámbar para editarla.";
  }
  const n = pendientes.size;
  return `${n} ${n === 1 ? "edición pendiente" : "ediciones pendientes"}: pulsa «Aplicar cambios y revalidar» para validarlas.`;
}

function esc(valor) {
  return String(valor ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function escAtributo(valor) {
  return esc(valor).replace(/"/g, "&quot;");
}
