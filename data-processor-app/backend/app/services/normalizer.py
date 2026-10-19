"""Normalización automática de filas (autocorrección de la spec 003).

Funciones puras (RNF-1): reciben las filas ya parseadas y devuelven SIEMPRE
una copia corregida junto con el rastro de correcciones; nunca mutan la
entrada (RF-1, RNF-2). Por celda, y SOLO para columnas del esquema (RF-2),
el valor pasa por un pipeline en orden fijo:

    limpieza (espacios/invisibles, RF-3) → vacío (marcadores, RF-8)
    → minúsculas (solo email, RF-4) → enum (RF-7) → número/fecha (RF-5/RF-6)

Todos los pasos actúan solo sobre columnas de su tipo y solo con lecturas
inequívocas (los ambiguos quedan como están para que el validador emita su
error). `corregir_filas` orquesta la copia, la autocorrección, las ediciones
manuales (`aplicar_ediciones`, RF-17/RF-18) y devuelve la lista de
correcciones ya ordenada (RF-9).
"""
import re
from datetime import date
from typing import Any, Optional, Union

from app.schemas.quality import Correccion, FieldCheck, RowError

# Límite del fallback de la vista previa (50 filas): se importa de validator.py
# como constante de solo lectura (validate_rows y LIMITE_MUESTRA quedan intactos)
from app.services.validator import LIMITE_MUESTRA

# Lista cerrada de marcadores de vacío (RF-8), comparados sin mayúsculas
MARCADORES_VACIO = frozenset({
    "n/a", "#n/a", "n.a.", "na", "null", "none", "-", "--", "sin dato", "sin datos",
})

# Espacio duro U+00A0: se trata como un espacio normal
_ESPACIO_DURO = "\u00a0"

# Caracteres invisibles de ancho cero, que se eliminan por completo (RF-3)
ANCHO_CERO = "\u200b\u200c\u200d\u2060\ufeff"

# Tope de filas de `filas_corregidas` (RNF-7): es el ÚNICO motivo por el que
# `descarga_corregida_disponible` pasa a false
LIMITE_FILAS_CORREGIDAS = 100_000

# Convención de fechas de una columna (RF-6)
CONVENCION_DIA_MES = "dia/mes"
CONVENCION_MES_DIA = "mes/dia"

# Dígitos ASCII (evita que «isdigit()» acepte superíndices u otros símbolos)
_DIGITOS = "0123456789"

# Tres grupos con año de 4 dígitos al final (RF-6): DD/MM/AAAA, DD-MM-AAAA, ...
_FECHA_RE = re.compile(r"^([0-9]{1,2})[/-]([0-9]{1,2})[/-]([0-9]{4})$")

# Mismos sinónimos de tipos que el validador (validator.py no se toca)
_TIPOS_NUMERO = {"float", "int", "integer", "number", "double", "numero"}
_TIPOS_FECHA = {"date", "fecha"}


def normalizar_filas(
    rows: list[dict], checks: list[FieldCheck]
) -> tuple[list[dict], list[Correccion]]:
    """Copia de las filas con las normalizaciones automáticas (RF-1..RF-8) y su
    rastro. No modifica `rows`."""
    por_columna = {c.nombre: c for c in checks}
    # Pre-paso lineal por columna de fecha: convención deducida una sola vez
    convenciones = _deducir_convenciones(rows, checks)
    copia: list[dict] = []
    correcciones: list[Correccion] = []

    for num_fila, fila in enumerate(rows, start=1):
        if not isinstance(fila, dict):
            copia.append(fila)
            continue
        nueva = dict(fila)
        for columna, check in por_columna.items():
            if columna not in nueva:
                continue
            valor_original = nueva[columna]
            valor_final, tipo = _normalizar_valor(
                valor_original, check, convenciones.get(columna)
            )
            if valor_final != valor_original:
                nueva[columna] = valor_final
            if tipo is not None:
                correcciones.append(
                    Correccion(
                        fila=num_fila,
                        columna=columna,
                        antes=valor_original
                        if isinstance(valor_original, str)
                        else str(valor_original),
                        despues=valor_final,
                        tipo=tipo,
                    )
                )
        copia.append(nueva)
    return copia, correcciones


def corregir_filas(
    rows: list[dict],
    checks: list[FieldCheck],
    autocorreccion: bool = True,
    ediciones: Optional[list[dict]] = None,
) -> tuple[list[dict], list[Correccion]]:
    """Orquesta la corrección completa (RF-1, RF-9): copia → normalización
    automática (solo si `autocorreccion`) → ediciones manuales → lista de
    correcciones ordenada según el contrato (fila ascendente, orden de las
    columnas EN EL ARCHIVO, automática antes que manual)."""
    if autocorreccion:
        filas, correcciones = normalizar_filas(rows, checks)
    else:
        filas = [dict(fila) if isinstance(fila, dict) else fila for fila in rows]
        correcciones = []

    if ediciones:
        # Ediciones manuales (RF-17): se aplican DESPUÉS de la normalización
        filas, manuales = aplicar_ediciones(filas, ediciones, checks)
        correcciones = correcciones + manuales

    return filas, _ordenar_correcciones(filas, correcciones)


def aplicar_ediciones(
    rows: list[dict], ediciones: list[dict], checks: list[FieldCheck]
) -> tuple[list[dict], list[Correccion]]:
    """Aplica el lote de ediciones manuales sobre una copia de las filas, en
    orden del lote (RF-17). Cada aplicación deja una entrada `tipo="manual"`
    con `antes` = valor previo de la celda (ya corregido si hubo
    autocorrección) y `despues` como TEXTO (|RF-9|); el VALOR DE LA FILA se
    guarda como número si la columna es numérica y el texto es convertible de
    forma inequívoca (misma representación que `muestra`/`filas_corregidas`,
    contrato de la API), y como texto en cualquier otro caso. Lanza ValueError
    con mensaje en español si la fila no existe, la columna no está en el
    esquema o el lote está mal formado (RF-18); la validación del lote es
    PREVIA: si algo falla, no se modifica nada."""
    # 1) Validación de TODO el lote antes de tocar nada (RF-18)
    total_filas = len(rows)
    columnas = {c.nombre for c in checks}
    for indice, edicion in enumerate(ediciones, start=1):
        if not isinstance(edicion, dict):
            raise ValueError(f"La edición {indice} del lote no es un objeto válido.")
        fila = edicion.get("fila")
        columna = edicion.get("columna")
        valor = edicion.get("valor")
        if not isinstance(fila, int) or isinstance(fila, bool):
            raise ValueError(f"La edición {indice}: «fila» debe ser un número entero.")
        if not 1 <= fila <= total_filas:
            raise ValueError(
                f"La edición {indice}: la fila {fila} no existe; "
                f"el archivo tiene {total_filas} filas."
            )
        if not isinstance(rows[fila - 1], dict):
            raise ValueError(f"La edición {indice}: la fila {fila} no es una fila válida.")
        if not isinstance(columna, str) or not columna.strip():
            raise ValueError(
                f"La edición {indice}: «columna» debe ser un nombre de columna no vacío."
            )
        if columna not in columnas:
            raise ValueError(
                f"La edición {indice}: la columna «{columna}» no está definida en el esquema."
            )
        if not isinstance(valor, str):
            raise ValueError(
                f"La edición {indice}: «valor» debe ser un texto (puede estar vacío)."
            )

    # 2) Aplicación en orden del lote sobre una copia
    por_columna = {c.nombre: c for c in checks}
    filas = [dict(f) if isinstance(f, dict) else f for f in rows]
    correcciones: list[Correccion] = []
    for edicion in ediciones:
        num_fila = edicion["fila"]
        columna = edicion["columna"]
        valor = edicion["valor"]
        fila_dict = filas[num_fila - 1]
        anterior = fila_dict.get(columna)
        # El VALOR DE LA FILA va como número si la columna es numérica y el
        # texto es convertible de forma inequívoca (contrato de la API); el
        # rastro `manual` se serializa SIEMPRE como texto (|RF-9|)
        valor_fila: Any = valor
        if (por_columna[columna].tipo or "").lower() in _TIPOS_NUMERO:
            numero = _a_numero_manual(valor)
            if numero is not None:
                valor_fila = numero
        fila_dict[columna] = valor_fila
        correcciones.append(
            Correccion(
                fila=num_fila,
                columna=columna,
                antes=""
                if anterior is None
                else (anterior if isinstance(anterior, str) else str(anterior)),
                despues=valor,
                tipo="manual",
            )
        )
    return filas, correcciones


def preparar_descarga_corregida(
    rows: list[dict],
    correcciones: list[Correccion],
    es_xlsx: bool = False,
    limite: Optional[int] = None,
) -> tuple[list[dict], bool]:
    """(filas_corregidas, descarga_corregida_disponible) del contrato (RF-14,
    RNF-7): envía las filas (TODAS, con la representación de `muestra`) si hay
    correcciones O si el archivo es `.xlsx` aunque no las haya (el navegador
    no puede regenerar un .xlsx sin librerías nuevas); si no, vienen vacías y
    el navegador genera la corregida del original. El tope de filas las vacía
    SIEMPRE, sea cual sea el formato, y es el ÚNICO motivo del flag en
    `false`. `limite` por defecto None: se lee la constante en cada llamada
    para que los tests puedan ajustarla con monkeypatch."""
    if limite is None:
        limite = LIMITE_FILAS_CORREGIDAS
    if len(rows) > limite:
        return [], False
    if correcciones or es_xlsx:
        return [dict(f) if isinstance(f, dict) else f for f in rows], True
    return [], True


def preparar_muestra(
    rows: list[dict],
    errores: list[RowError],
    correcciones: list[Correccion],
) -> tuple[list[dict], list[int]]:
    """(muestra, muestra_filas) de la vista previa de errores (RF-11, T16).

    Sin tope de filas (decisión «sin límite»): `muestra` trae TODAS las
    filas de interés —las que tienen error residual O alguna corrección
    (unión de números de fila)— en orden de fila ascendente, con la MISMA
    representación de siempre; `muestra_filas` sus números 1-based reales,
    siempre paralelos en longitud y orden. Sin ninguna fila de interés →
    fallback: las primeras `LIMITE_MUESTRA` filas (una subida limpia siempre
    muestra algo; único uso de esa constante) con `muestra_filas = [1..N]`.
    El contador ("X filas con errores o correcciones · Y incidencias") y el
    aviso por volumen NO los calcula el backend: el navegador los deriva de
    las listas completas `errores` ∪ `correcciones`. `LIMITE_MUESTRA` se
    importa de `validator.py` sin modificarlo (regla del proyecto)."""
    # Filas de interés: números de la unión errores ∪ correcciones
    filas_de_interes: set[int] = set()
    for e in errores:
        if 1 <= e.fila <= len(rows):
            filas_de_interes.add(e.fila)
    for c in correcciones:
        if 1 <= c.fila <= len(rows):
            filas_de_interes.add(c.fila)

    muestra: list[dict] = []
    muestra_filas: list[int] = []
    for num in sorted(filas_de_interes):
        fila = rows[num - 1]
        if isinstance(fila, dict):
            muestra.append(dict(fila))
            muestra_filas.append(num)

    if not muestra_filas:  # sin filas de interés → el fallback de siempre
        muestra = [dict(f) for f in rows[:LIMITE_MUESTRA] if isinstance(f, dict)]
        muestra_filas = list(range(1, len(muestra) + 1))
    return muestra, muestra_filas


def _ordenar_correcciones(
    rows: list[dict], correcciones: list[Correccion]
) -> list[Correccion]:
    """Orden de la lista `correcciones` (RF-9, decisión técnica 9 del plan):
    fila ascendente → orden de aparición de la columna EN EL ARCHIVO →
    automática antes que manual → orden de recolección (sorted es estable,
    así que actúa como desempate del lote)."""
    indice_columna: dict[str, int] = {}
    for fila in rows:
        if isinstance(fila, dict):
            for nombre in fila.keys():
                if nombre not in indice_columna:
                    indice_columna[nombre] = len(indice_columna)

    def clave(c: Correccion) -> tuple:
        return (
            c.fila,
            indice_columna.get(c.columna, len(indice_columna)),
            1 if c.tipo == "manual" else 0,
        )

    return sorted(correcciones, key=clave)


def _normalizar_valor(
    valor: Any, check: FieldCheck, convencion: Optional[str] = None
) -> tuple[Any, Optional[str]]:
    """Pipeline de una celda. Devuelve (valor_final, tipo): `tipo` es None si
    ningún paso modificó el valor; si varios lo hicieron, es el del último."""
    if not isinstance(valor, str):
        # Los valores no textuales no se tocan en este pipeline
        # (los pasos de enum/número/fecha no reinterpretan números ni fechas
        # nativos: ya son del tipo correcto).
        return valor, None

    limpio, habia_invisibles = _limpiar_texto(valor)
    if not limpio:
        # Solo espacios/invisibles: ya contaba como vacía para el validador,
        # por lo que NO se genera registro de corrección (RF-3).
        return "", None

    actual = limpio
    tipo: Optional[str] = None
    if actual != valor:
        # Un solo paso de limpieza; si hubo invisibles, ese es el tipo (RF-3)
        tipo = "invisibles" if habia_invisibles else "espacios"

    # Paso vacío (RF-8): marcadores SOLO en columnas no requeridas
    if not check.requerido and actual.lower() in MARCADORES_VACIO:
        return "", "vacio"

    tipo_check = (check.tipo or "").lower()

    # Paso minúsculas (RF-4): SOLO columnas de tipo email
    if tipo_check == "email" and actual.lower() != actual:
        return actual.lower(), "minusculas"

    # Paso enum (RF-7): única coincidencia insensible a mayúsculas/espacios
    # (su forma exacta) o, si no, único candidato a distancia de edición ≤ 1
    if tipo_check == "enum" and check.allowed_values is not None:
        corregido = _corregir_enum(actual, check.allowed_values)
        if corregido is not None and corregido != actual:
            return corregido, "enum"

    # Paso número (RF-5): SOLO columnas numéricas y patrón inequívoco
    if tipo_check in _TIPOS_NUMERO:
        numero = _a_numero_corregido(actual)
        if numero is not None:
            return numero, "numero"

    # Paso fecha (RF-6): SOLO columnas de fecha y lectura según convención
    if tipo_check in _TIPOS_FECHA:
        fecha = _convertir_fecha(actual, check, convencion)
        if fecha is not None and fecha != actual:
            return fecha, "fecha"

    if tipo is None:
        return valor, None
    return actual, tipo


def _limpiar_texto(valor: str) -> tuple[str, bool]:
    """Elimina caracteres invisibles y espacios sobrantes (iniciales, finales
    y dobles internos). Devuelve (texto limpio, había invisibles)."""
    habia_invisibles = any(ch == _ESPACIO_DURO or ch in ANCHO_CERO for ch in valor)
    sin_ancho_cero = "".join(ch for ch in valor if ch not in ANCHO_CERO)
    sin_duros = sin_ancho_cero.replace(_ESPACIO_DURO, " ")
    return " ".join(sin_duros.split()), habia_invisibles


# --- Enums (RF-7) -------------------------------------------------------------

def _corregir_enum(valor: str, permitidos: list) -> Optional[str]:
    """RF-7: (a) si al ignorar mayúsculas/minúsculas y espacios coincide con
    EXACTAMENTE un valor permitido, devuelve ese valor en su forma exacta;
    (b) si no, y hay EXACTAMENTE UN valor permitido a distancia de edición ≤ 1
    del valor tal cual, devuelve ese valor. Con varios candidatos no se
    corrige (se conserva el error original)."""
    candidatos_exactos = [
        v for v in permitidos
        if isinstance(v, str) and v.strip().lower() == valor.strip().lower()
    ]
    if len(candidatos_exactos) == 1:
        return candidatos_exactos[0]
    if len(candidatos_exactos) > 1:
        return None  # dos permitidos con la misma forma normalizada: ambiguo

    cercanos = [
        v for v in permitidos
        if isinstance(v, str) and _distancia_edicion(valor, v) <= 1
    ]
    if len(cercanos) == 1:
        return cercanos[0]
    return None


def _distancia_edicion(a: str, b: str) -> int:
    """Distancia de edición (Levenshtein) entre dos textos, con programación
    dinámica de dos filas: coste O(len(a) * len(b)) y memoria O(len(b))."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    fila = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        diagonal = fila[0]
        fila[0] = i
        for j, cb in enumerate(b, start=1):
            anterior = fila[j]
            fila[j] = min(
                fila[j] + 1,            # eliminación
                fila[j - 1] + 1,        # inserción
                diagonal + (ca != cb),  # sustitución
            )
            diagonal = anterior
    return fila[-1]


# --- Números (RF-5) -----------------------------------------------------------

def _a_numero_corregido(valor: str) -> Optional[Union[int, float]]:
    """Convierte un texto con separadores a NÚMERO solo si el patrón de
    separadores es inequívoco (RF-5). Devuelve None si no se corrige
    (ambiguo o sin sentido numérico) y entero si no hay parte decimal."""
    texto = valor.strip()
    if not texto or not _todos_digitos(texto.replace(",", "").replace(".", "")):
        return None
    if texto[0] in ",." or texto[-1] in ",.":
        return None

    coma, punto = texto.count(","), texto.count(".")

    if coma and punto:
        # (a) ambos separadores: el último es el decimal; a la izquierda,
        # todos los grupos deben formar grupos de 3 dígitos
        if texto.rfind(",") > texto.rfind("."):
            decimal, miles = ",", "."
        else:
            decimal, miles = ".", ","
        parte_entera, parte_decimal = texto.rsplit(decimal, 1)
        if not _todos_digitos(parte_decimal) or not _grupos_de_tres(parte_entera, miles):
            return None  # no inequívoco: se conserva el error original
        return float(parte_entera.replace(miles, "") + "." + parte_decimal)

    if coma or punto:
        sep = "," if coma else "."
        partes = texto.split(sep)
        if len(partes) == 2:
            izq, der = partes
            if not _todos_digitos(izq) or not _todos_digitos(der):
                return None
            # (c) un único separador: decimal, salvo ambigüedad (exactamente
            # 3 dígitos a la derecha y 1-3 a la izquierda también leerían miles)
            if len(der) == 3 and 1 <= len(izq) <= 3:
                return None
            return float(izq + "." + der)
        # (b) un separador repetido: todos los grupos deben ser de 3 dígitos
        if not _grupos_de_tres(texto, sep):
            return None  # no inequívoco
        return int("".join(partes))

    return None  # sin separadores: el entero ya es válido, sin corrección


def _a_numero_manual(valor: str) -> Optional[Union[int, float]]:
    """Número para el VALOR DE LA FILA de una edición manual sobre columna
    numérica: las lecturas inequívocas de RF-5 (punto y coma decimal, miles
    en grupos de tres) más el caso simple sin separadores (con signo
    opcional). Devuelve None si no es convertible de forma inequívoca (p. ej.
    «mil» o «1,234»): el texto se conserva y el validador emitirá su error."""
    texto = valor.strip()
    signo = ""
    if texto[:1] in ("-", "+"):
        signo = "-" if texto[0] == "-" else ""
        texto = texto[1:].strip()
    if not texto:
        return None
    numero = _a_numero_corregido(texto)
    if numero is not None:
        return -numero if signo == "-" else numero
    if _todos_digitos(texto):
        return int(signo + texto)
    return None


def _grupos_de_tres(texto: str, separador: str) -> bool:
    """Comprueba que el texto es dígitos agrupados por `separador` en grupos
    de 3 desde la derecha (el grupo de la izquierda, de 1 a 3 dígitos)."""
    partes = texto.split(separador)
    if not partes[0] or not 1 <= len(partes[0]) <= 3 or not _todos_digitos(partes[0]):
        return False
    return all(len(p) == 3 and _todos_digitos(p) for p in partes[1:])


def _todos_digitos(texto: str) -> bool:
    """True si el texto no está vacío y contiene solo dígitos ASCII."""
    return bool(texto) and all(ch in _DIGITOS for ch in texto)


# --- Fechas (RF-6) ------------------------------------------------------------

def _deducir_convenciones(rows: list, checks: list[FieldCheck]) -> dict[str, str]:
    """Convención de cada columna de fecha, deducida una sola vez (pre-paso,
    RF-6). Solo incluye las columnas que aportan convención inequívoca."""
    convenciones: dict[str, str] = {}
    for check in checks:
        if (check.tipo or "").lower() not in _TIPOS_FECHA:
            continue
        valores = []
        for fila in rows:
            if isinstance(fila, dict):
                valor = fila.get(check.nombre)
                if isinstance(valor, str):
                    valores.append(_limpiar_texto(valor)[0])
        convencion = _deducir_convencion_fechas(valores)
        if convencion is not None:
            convenciones[check.nombre] = convencion
    return convenciones


def _deducir_convencion_fechas(valores: list) -> Optional[str]:
    """Deduce la convención de la columna a partir de sus valores de lectura
    única (RF-6): CONVENCION_DIA_MES o CONVENCION_MES_DIA. Cuenta las lecturas
    únicas de cada orden y gana la MAYORÍA estricta; si hay empate (conflicto,
    p. ej. 25/12/2026 y 05/13/2026) o no hay inequívocos, la columna se
    considera sin convención y se devuelve None."""
    cuenta_dia_mes = 0
    cuenta_mes_dia = 0
    for valor in valores:
        if not isinstance(valor, str):
            continue
        lecturas = _lecturas_fecha(valor)
        if lecturas is None:
            continue
        dia_mes, mes_dia = lecturas
        if dia_mes is not None and mes_dia is None:
            cuenta_dia_mes += 1  # solo se lee como día/mes (p. ej. 25/12/2026)
        elif mes_dia is not None and dia_mes is None:
            cuenta_mes_dia += 1  # solo se lee como mes/día (p. ej. 05/13/2026)
        # ambigua o imposible: no aporta convención
    if cuenta_dia_mes > cuenta_mes_dia:
        return CONVENCION_DIA_MES
    if cuenta_mes_dia > cuenta_dia_mes:
        return CONVENCION_MES_DIA
    return None


def _lecturas_fecha(
    valor: str,
) -> Optional[tuple[Optional[tuple], Optional[tuple]]]:
    """Analiza un valor de 3 grupos con año de 4 dígitos al final (RF-6).
    Devuelve (lectura día/mes, lectura mes/día); cada lectura es
    (anio, mes, dia) o None si no es una fecha válida. Devuelve None si el
    valor no encaja en el patrón (p. ej. año de 2 dígitos o al principio)."""
    m = _FECHA_RE.match(valor.strip())
    if not m:
        return None
    g1, g2, anio = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return _fecha_valida(anio, g2, g1), _fecha_valida(anio, g1, g2)


def _fecha_valida(anio: int, mes: int, dia: int) -> Optional[tuple]:
    """(anio, mes, dia) si es una fecha real; None si es imposible (p. ej.
    31/02/2026)."""
    try:
        date(anio, mes, dia)
    except ValueError:
        return None
    return (anio, mes, dia)


def _convertir_fecha(
    valor: str, check: FieldCheck, convencion: Optional[str]
) -> Optional[str]:
    """Aplica el RF-6 a un valor limpio y devuelve el texto en el formato de
    la regla (por defecto AAAA-MM-DD), o None si no se corrige."""
    lecturas = _lecturas_fecha(valor)
    if lecturas is None:
        return None
    dia_mes, mes_dia = lecturas

    if dia_mes is not None and mes_dia is not None:
        # Ambiguo: aplica la convención de la columna; sin convención no se
        # corrige y el valor sigue siendo error (RF-6b)
        if convencion == CONVENCION_DIA_MES:
            elegida = dia_mes
        elif convencion == CONVENCION_MES_DIA:
            elegida = mes_dia
        else:
            return None
    elif dia_mes is not None:
        # Lectura única: se aplica si aporta convención o no la hay; si la
        # convención de la columna es contraria, no se corrige (RF-6c)
        if convencion == CONVENCION_MES_DIA:
            return None
        elegida = dia_mes
    elif mes_dia is not None:
        if convencion == CONVENCION_DIA_MES:
            return None
        elegida = mes_dia
    else:
        return None  # ninguna lectura válida (fecha imposible)

    anio, mes, dia = elegida
    formato = check.date_format or "YYYY-MM-DD"
    return (
        formato.replace("YYYY", f"{anio:04d}")
        .replace("MM", f"{mes:02d}")
        .replace("DD", f"{dia:02d}")
    )
