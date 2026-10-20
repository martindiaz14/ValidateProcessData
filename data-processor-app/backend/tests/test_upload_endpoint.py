"""Tests del endpoint de carga (POST /api/v1/upload)."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.v1.endpoints.upload import _formatear_miles
from app.core.database import SessionLocal, get_session
from app.main import app
from app.models.upload import Upload

client = TestClient(app)

ESQUEMA = (
    '{"campos":['
    '{"nombre":"nombre","tipo":"texto","requerido":true},'
    '{"nombre":"monto","tipo":"numero","requerido":true}'
    "]}"
)


def test_upload_valido():
    contenido = b"nombre,monto\nEmpresa A,100\nEmpresa B,200\n"
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", contenido, "text/csv")},
        data={"quality_schema": ESQUEMA},
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["total_filas"] == 2
    assert cuerpo["validas"] == 2
    assert cuerpo["invalidas"] == 0


def test_upload_con_filas_invalidas():
    contenido = b"nombre,monto\nEmpresa A,\n,abc\n"
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", contenido, "text/csv")},
        data={"quality_schema": ESQUEMA},
    )
    assert r.status_code == 200
    assert r.json()["invalidas"] == 2
    assert len(r.json()["errores"]) == 3  # fila 2 sin monto, fila 4 sin nombre y tipo


def test_esquema_invalido_devuelve_400():
    contenido = b"nombre,monto\nEmpresa A,100\n"
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", contenido, "text/csv")},
        data={"quality_schema": "esto-no-es-json"},
    )
    assert r.status_code == 400
    assert "JSON" in r.json()["detail"]


def test_extension_no_soportada_devuelve_400():
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.pdf", b"abc", "application/octet-stream")},
        data={"quality_schema": ESQUEMA},
    )
    assert r.status_code == 400
    assert "soportada" in r.json()["detail"]


def test_archivo_vacio_devuelve_400():
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", b"", "text/csv")},
        data={"quality_schema": ESQUEMA},
    )
    assert r.status_code == 400


# --- Autocorrección y ediciones en el endpoint (spec 003, T5) -----------------

# Un valor con espacios sobrantes: la autocorrección lo puede limpiar
CSV_ESPACIOS = b'nombre,monto\n"  Empresa A  ",100\n'


def test_sin_campos_nuevos_es_compatibilidad():
    contenido = b"nombre,monto\nEmpresa A,100\nEmpresa B,200\n"
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", contenido, "text/csv")},
        data={"quality_schema": ESQUEMA},
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["total_filas"] == 2
    assert cuerpo["validas"] == 2
    assert cuerpo["invalidas"] == 0
    # campos nuevos con valores por defecto (RNF-5) y sin corrección fantasma
    assert cuerpo["correcciones"] == []
    assert cuerpo["filas_corregidas"] == []
    assert cuerpo["descarga_corregida_disponible"] is True


def test_campo_autocorreccion_ausente_no_autocorrige():
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", CSV_ESPACIOS, "text/csv")},
        data={"quality_schema": ESQUEMA},
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["correcciones"] == []
    assert cuerpo["filas_corregidas"] == []
    assert cuerpo["muestra"][0]["nombre"] == "  Empresa A  "  # intacto


def test_autocorreccion_true_corrige():
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", CSV_ESPACIOS, "text/csv")},
        data={"quality_schema": ESQUEMA, "autocorreccion": "true"},
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert len(cuerpo["correcciones"]) == 1
    c = cuerpo["correcciones"][0]
    assert c["tipo"] == "espacios"
    assert c["antes"] == "  Empresa A  "
    assert c["despues"] == "Empresa A"
    assert cuerpo["filas_corregidas"][0]["nombre"] == "Empresa A"
    assert cuerpo["descarga_corregida_disponible"] is True


def test_autocorreccion_false_igual_que_hoy():
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", CSV_ESPACIOS, "text/csv")},
        data={"quality_schema": ESQUEMA, "autocorreccion": "false"},
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["validas"] == 1  # mismo cómputo que sin corregir
    assert cuerpo["correcciones"] == []
    assert cuerpo["filas_corregidas"] == []


def test_ediciones_multipart_aplicadas():
    contenido = b"nombre,monto\nEmpresa A,100\n"
    lote = '[{"fila": 1, "columna": "nombre", "valor": "Editada"}]'
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", contenido, "text/csv")},
        data={"quality_schema": ESQUEMA, "ediciones": lote},
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert len(cuerpo["correcciones"]) == 1
    assert cuerpo["correcciones"][0]["tipo"] == "manual"
    assert cuerpo["correcciones"][0]["despues"] == "Editada"
    assert cuerpo["filas_corregidas"][0]["nombre"] == "Editada"


def test_edicion_numerica_devuelve_numero_en_filas_corregidas():
    contenido = b"nombre,monto\nEmpresa A,100\n"
    lote = '[{"fila": 1, "columna": "monto", "valor": "99"}]'
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", contenido, "text/csv")},
        data={"quality_schema": ESQUEMA, "ediciones": lote},
    )
    assert r.status_code == 200
    cuerpo = r.json()
    monto = cuerpo["filas_corregidas"][0]["monto"]
    assert isinstance(monto, (int, float)) and not isinstance(monto, bool)
    assert monto == 99  # columna numérica convertible → número, no texto
    assert isinstance(cuerpo["muestra"][0]["monto"], (int, float))
    assert cuerpo["correcciones"][0]["despues"] == "99"  # el rastro, en texto


def test_ediciones_json_malformado_devuelve_400():
    contenido = b"nombre,monto\nEmpresa A,100\n"
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", contenido, "text/csv")},
        data={"quality_schema": ESQUEMA, "ediciones": "no-es-json"},
    )
    assert r.status_code == 400
    assert "ediciones" in r.json()["detail"].lower()
    assert "total_filas" not in r.json()  # sin validar


def test_ediciones_no_lista_devuelve_400():
    contenido = b"nombre,monto\nEmpresa A,100\n"
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", contenido, "text/csv")},
        data={"quality_schema": ESQUEMA, "ediciones": '{"fila": 1}'},
    )
    assert r.status_code == 400
    assert "lista" in r.json()["detail"]


def test_ediciones_fila_invalida_devuelve_400_sin_validar():
    contenido = b"nombre,monto\nEmpresa A,100\n"
    lote = '[{"fila": 99, "columna": "nombre", "valor": "X"}]'
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", contenido, "text/csv")},
        data={"quality_schema": ESQUEMA, "ediciones": lote},
    )
    assert r.status_code == 400
    assert "fila" in r.json()["detail"].lower()
    assert "total_filas" not in r.json()  # sin validar (RF-18)


def test_ediciones_columna_invalida_devuelve_400():
    contenido = b"nombre,monto\nEmpresa A,100\n"
    lote = '[{"fila": 1, "columna": "inexistente", "valor": "X"}]'
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", contenido, "text/csv")},
        data={"quality_schema": ESQUEMA, "ediciones": lote},
    )
    assert r.status_code == 400
    assert "esquema" in r.json()["detail"]


def test_filas_corregidas_vacio_csv_sin_correcciones():
    contenido = b"nombre,monto\nEmpresa A,100\n"
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", contenido, "text/csv")},
        data={"quality_schema": ESQUEMA, "autocorreccion": "true"},
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["correcciones"] == []
    assert cuerpo["filas_corregidas"] == []  # sin correcciones y no es .xlsx
    assert cuerpo["descarga_corregida_disponible"] is True


def test_xlsx_sin_correcciones_envia_filas_corregidas():
    backend = Path(__file__).resolve().parents[1]
    contenido = (backend / "ejemplo_datos.xlsx").read_bytes()
    esquema = (backend / "ejemplo_esquema.json").read_text(encoding="utf-8")
    r = client.post(
        "/api/v1/upload",
        files={
            "file": (
                "ejemplo_datos.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={"quality_schema": esquema, "autocorreccion": "true"},
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["correcciones"] == []  # el ejemplo actual no se autocorrige
    assert len(cuerpo["filas_corregidas"]) == cuerpo["total_filas"]
    assert cuerpo["descarga_corregida_disponible"] is True


def test_tope_de_filas_vacia_corregidas_y_apaga_flag(monkeypatch):
    monkeypatch.setattr("app.services.normalizer.LIMITE_FILAS_CORREGIDAS", 1)
    contenido = b'nombre,monto\n"  Empresa A  ",100\nEmpresa B,200\n'
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", contenido, "text/csv")},
        data={"quality_schema": ESQUEMA, "autocorreccion": "true"},
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert len(cuerpo["correcciones"]) == 1  # el rastro sigue completo
    assert cuerpo["filas_corregidas"] == []  # tope: nunca se envían
    assert cuerpo["descarga_corregida_disponible"] is False  # único motivo


def test_registro_de_carga_sigue_persistiendose():
    from app.core.database import SessionLocal
    from app.models.upload import Upload

    contenido = b"nombre,monto\nEmpresa A,100\n"
    with SessionLocal() as s:
        antes = s.query(Upload).count()
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", contenido, "text/csv")},
        data={"quality_schema": ESQUEMA, "autocorreccion": "true"},
    )
    assert r.status_code == 200
    with SessionLocal() as s:
        assert s.query(Upload).count() == antes + 1


# --- Archivo de ejemplo de autocorrección (spec 003, T6) ---------------------


def _subir_ejemplo_autocorreccion(autocorreccion: str):
    backend = Path(__file__).resolve().parents[1]
    contenido = (backend / "ejemplo_autocorreccion.csv").read_bytes()
    esquema = (backend / "ejemplo_autocorreccion_esquema.json").read_text(
        encoding="utf-8"
    )
    return client.post(
        "/api/v1/upload",
        files={"file": ("ejemplo_autocorreccion.csv", contenido, "text/csv")},
        data={"quality_schema": esquema, "autocorreccion": autocorreccion},
    )


def test_ejemplo_autocorreccion_corrige_todos_los_tipos_corregibles():
    r = _subir_ejemplo_autocorreccion("true")
    assert r.status_code == 200
    cuerpo = r.json()
    tipos = {c["tipo"] for c in cuerpo["correcciones"]}
    # espacios sobrantes/internos, espacio duro, número, fecha y enum
    assert {"espacios", "numero", "fecha", "enum", "vacio"} <= tipos
    # los no corregibles siguen sin corregir, visibles en los errores
    motivos = {(e["fila"], e["columna"]) for e in cuerpo["errores"]}
    assert (4, "cliente_email") in motivos  # correo mal formado de verdad
    assert (4, "monto") in motivos  # 1,234 ambiguo
    assert (4, "estado") in motivos  # DESCONOCIDO, distancia > 1
    assert (5, "monto") in motivos  # "mil": texto donde debería haber número
    assert cuerpo["invalidas"] == 2


def test_ejemplo_autocorreccion_con_interruptor_apagado_no_corrige():
    r = _subir_ejemplo_autocorreccion("false")
    assert r.status_code == 200
    assert r.json()["correcciones"] == []


# --- Vista previa de errores: muestra/muestra_filas (RF-11, T11) ---------------

def _csv_errores_en_80_y_900() -> bytes:
    """900 filas válidas salvo las filas 80 y 900, sin monto (campo requerido)."""
    lineas = ["nombre,monto"]
    for i in range(1, 901):
        monto = "" if i in (80, 900) else str(i)
        lineas.append(f"Empresa {i},{monto}")
    return ("\n".join(lineas) + "\n").encode("utf-8")


def test_muestra_trae_solo_las_filas_80_y_900():
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", _csv_errores_en_80_y_900(), "text/csv")},
        data={"quality_schema": ESQUEMA},
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["muestra_filas"] == [80, 900]
    assert len(cuerpo["muestra"]) == 2
    assert cuerpo["muestra"][0]["nombre"] == "Empresa 80"
    assert cuerpo["muestra"][1]["nombre"] == "Empresa 900"
    assert {e["fila"] for e in cuerpo["errores"]} == {80, 900}


def test_edicion_de_la_fila_900_se_aplica_sin_error():
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", _csv_errores_en_80_y_900(), "text/csv")},
        data={
            "quality_schema": ESQUEMA,
            "ediciones": '[{"fila": 900, "columna": "monto", "valor": "250"}]',
        },
    )
    # RF-18: la fila 900 existe y la edición viaja con su número real
    assert r.status_code == 200
    cuerpo = r.json()
    manuales = [c for c in cuerpo["correcciones"] if c["tipo"] == "manual"]
    assert len(manuales) == 1
    assert manuales[0]["fila"] == 900
    assert cuerpo["filas_corregidas"][899]["monto"] == 250
    # La fila 900 sigue siendo de interés: ahora por su corrección manual
    assert 900 in cuerpo["muestra_filas"]


def test_muestra_filas_en_fallback_es_1_a_n():
    contenido = b"nombre,monto\nEmpresa A,100\nEmpresa B,200\n"
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", contenido, "text/csv")},
        data={"quality_schema": ESQUEMA},
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["muestra_filas"] == [1, 2]  # fallback: filas de interés ninguna
    assert len(cuerpo["muestra"]) == 2


# --- `limite_muestra` eliminado: se ignora sin error (RF-11, RNF-5, T16) --------
# La vista previa ya no tiene límite editable: trae TODAS las filas de
# interés. Si un cliente antiguo envía `limite_muestra`, el campo se IGNORA
# (nunca un 400) y la respuesta no cambia.

def _csv_un_error_por_fila(n_filas: int) -> bytes:
    """`n_filas` filas con 1 incidencia cada una (monto vacío = requerido)."""
    lineas = ["nombre,monto"] + [f"Empresa {i}," for i in range(1, n_filas + 1)]
    return ("\n".join(lineas) + "\n").encode("utf-8")


def test_sin_campo_limite_muestra_las_70_filas_de_interes():
    # Sin el campo (la interfaz ya no lo envía): 70 filas con un error cada
    # una → salen las 70 de interés (sin tope)
    contenido = _csv_un_error_por_fila(70)
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", contenido, "text/csv")},
        data={"quality_schema": ESQUEMA},
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["muestra_filas"] == list(range(1, 71))
    assert len(cuerpo["muestra"]) == 70
    assert len(cuerpo["errores"]) == 70  # la respuesta sigue trayendo TODO


def test_limite_muestra_valores_varios_se_ignoran_sin_400():
    # (g) cualquier valor que envíe un cliente antiguo (vacío, 0, negativo,
    # entero, letras) se IGNORA: siempre todas las filas de interés, sin 400
    contenido = _csv_un_error_por_fila(70)
    for valor in ("", "0", "-5", "2", "5", "5000", "abc"):
        r = client.post(
            "/api/v1/upload",
            files={"file": ("datos.csv", contenido, "text/csv")},
            data={"quality_schema": ESQUEMA, "limite_muestra": valor},
        )
        assert r.status_code == 200
        assert r.json()["muestra_filas"] == list(range(1, 71))


def test_limite_muestra_en_fallback_sigue_dando_las_primeras_50():
    # Archivo limpio (sin filas de interés): fallback intacto, con o sin el
    # campo antiguo (su valor se ignora)
    lineas = ["nombre,monto"] + [f"Empresa {i},{i}" for i in range(1, 61)]
    contenido = ("\n".join(lineas) + "\n").encode("utf-8")
    for extra in ({}, {"limite_muestra": "2"}):
        r = client.post(
            "/api/v1/upload",
            files={"file": ("datos.csv", contenido, "text/csv")},
            data={"quality_schema": ESQUEMA, **extra},
        )
        assert r.status_code == 200
        cuerpo = r.json()
        assert cuerpo["muestra_filas"] == list(range(1, 51))
        assert len(cuerpo["muestra"]) == 50


# --- Spec 004: límite dinámico, tope de filas en nube y registro best-effort ----
# El límite de bytes (RF-3) y el tope de filas (RF-8) se leen del entorno en
# CADA petición; el registro de la carga es mejor esfuerzo (RF-4).

SUCIOS_ENTORNO_T2 = ("VERCEL", "MAX_UPLOAD_MB", "MAX_FILAS_NUBE")


def _limpiar_entorno_t2(monkeypatch) -> None:
    """Quita las variables de la spec 004 para no contaminar otros tests."""
    for nombre in SUCIOS_ENTORNO_T2:
        monkeypatch.delenv(nombre, raising=False)


def _csv_limpio_n_filas(n: int) -> bytes:
    """CSV válido de `n` filas (enteros: sin correcciones del paso número)."""
    lineas = ["nombre,monto"] + [f"Empresa {i},{i}" for i in range(1, n + 1)]
    return ("\n".join(lineas) + "\n").encode("utf-8")


def test_formatear_miles():
    assert _formatear_miles(2000) == "2.000"
    assert _formatear_miles(500) == "500"
    assert _formatear_miles(1234567) == "1.234.567"


def test_limbite_bytes_local_10_mb(monkeypatch):
    _limpiar_entorno_t2(monkeypatch)
    contenido = b"x" * (11 * 1024 * 1024)  # 11 MB
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", contenido, "text/csv")},
        data={"quality_schema": ESQUEMA},
    )
    assert r.status_code == 413
    assert r.json()["detail"] == "El archivo supera el límite de 10 MB."


def test_limbite_bytes_nube_4_mb(monkeypatch):
    _limpiar_entorno_t2(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")
    contenido = b"x" * (5 * 1024 * 1024)  # 5 MB
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", contenido, "text/csv")},
        data={"quality_schema": ESQUEMA},
    )
    assert r.status_code == 413
    assert r.json()["detail"] == "El archivo supera el límite de 4 MB."


def test_tope_filas_nube_2000_pasa(monkeypatch):
    # En nube, EXACTAMENTE el tope → se valida completo (200)
    _limpiar_entorno_t2(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", _csv_limpio_n_filas(2000), "text/csv")},
        data={"quality_schema": ESQUEMA},
    )
    assert r.status_code == 200
    assert r.json()["total_filas"] == 2000


def test_tope_filas_nube_2001_rechaza_sin_validar(monkeypatch):
    # En nube, una fila de más → 413 con el mensaje exacto; la respuesta NO
    # trae nada de validación (el archivo no se corrige ni se valida, RF-8)
    _limpiar_entorno_t2(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", _csv_limpio_n_filas(2001), "text/csv")},
        data={"quality_schema": ESQUEMA, "autocorreccion": "true"},
    )
    assert r.status_code == 413
    assert r.json() == {
        "detail": (
            "La demo en línea acepta hasta 2.000 filas por archivo. "
            "Para archivos más grandes, ejecuta la aplicación en local."
        )
    }
    assert "total_filas" not in r.json()


def test_tope_filas_nube_tambien_en_revalidacion_con_ediciones(monkeypatch):
    # El tope aplica a TODA petición /upload en nube, incluida la
    # revalidación con el campo `ediciones`
    _limpiar_entorno_t2(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")
    lote = '[{"fila": 1, "columna": "nombre", "valor": "Editada"}]'
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", _csv_limpio_n_filas(2500), "text/csv")},
        data={"quality_schema": ESQUEMA, "ediciones": lote},
    )
    assert r.status_code == 413
    assert r.json() == {
        "detail": (
            "La demo en línea acepta hasta 2.000 filas por archivo. "
            "Para archivos más grandes, ejecuta la aplicación en local."
        )
    }


def test_tope_filas_no_existe_en_local(monkeypatch):
    # En local NO hay tope de filas, aunque exista MAX_FILAS_NUBE
    _limpiar_entorno_t2(monkeypatch)
    monkeypatch.setenv("MAX_FILAS_NUBE", "500")
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", _csv_limpio_n_filas(2001), "text/csv")},
        data={"quality_schema": ESQUEMA},
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["total_filas"] == 2001
    assert "demo" not in str(cuerpo).lower()  # el mensaje del tope, nunca


def test_tope_filas_nube_con_max_filas_500(monkeypatch):
    _limpiar_entorno_t2(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("MAX_FILAS_NUBE", "500")
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos.csv", _csv_limpio_n_filas(501), "text/csv")},
        data={"quality_schema": ESQUEMA},
    )
    assert r.status_code == 413
    assert r.json() == {
        "detail": (
            "La demo en línea acepta hasta 500 filas por archivo. "
            "Para archivos más grandes, ejecuta la aplicación en local."
        )
    }


def test_registro_best_effort_un_fallo_de_bd_no_da_500(monkeypatch):
    # RF-4: el commit de la BD falla (disco lleno, solo lectura…) → la
    # respuesta sigue siendo 200 COMPLETA, con rollback y sin 500
    _limpiar_entorno_t2(monkeypatch)

    class _SesionRota:
        """Sesión de mentira: el commit falla como un disco no escribible."""

        def __init__(self):
            self.add_llamado = False
            self.rollback_llamado = False

        def add(self, registro):
            self.add_llamado = True

        def commit(self):
            raise RuntimeError("disco lleno")

        def rollback(self):
            self.rollback_llamado = True

    rota = _SesionRota()
    app.dependency_overrides[get_session] = lambda: rota
    try:
        contenido = b"nombre,monto\nEmpresa A,100\n"
        r = client.post(
            "/api/v1/upload",
            files={"file": ("datos.csv", contenido, "text/csv")},
            data={"quality_schema": ESQUEMA},
        )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["total_filas"] == 1
    assert cuerpo["validas"] == 1
    assert cuerpo["invalidas"] == 0
    assert cuerpo["errores"] == []
    assert cuerpo["columnas"] == ["nombre", "monto"]
    assert cuerpo["muestra"][0]["nombre"] == "Empresa A"
    assert rota.add_llamado is True  # el registro se intentó…
    assert rota.rollback_llamado is True  # …y se hizo rollback


def test_registro_normal_sigue_persistiendose():
    # Caso feliz (BD escribible): el registro se sigue guardando igual
    with SessionLocal() as sesion:
        antes = sesion.query(Upload).count()

    contenido = b"nombre,monto\nEmpresa A,100\n"
    r = client.post(
        "/api/v1/upload",
        files={"file": ("datos_t2.csv", contenido, "text/csv")},
        data={"quality_schema": ESQUEMA},
    )
    assert r.status_code == 200

    with SessionLocal() as sesion:
        despues = sesion.query(Upload).count()
        ultimo = sesion.query(Upload).order_by(Upload.id.desc()).first()
    assert despues == antes + 1
    assert ultimo.filename == "datos_t2.csv"
