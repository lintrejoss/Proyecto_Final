import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from starlette.testclient import TestClient
from src.main import app
from src.database import SessionLocal
from src.models import (
    Usuario, RolUsuario, Recurso, CondicionRecurso,
    Solicitud, EstadoSolicitud, Novedad, TipoNovedad, Prestamo, EstadoPrestamo
)

BOGOTA_TZ = ZoneInfo("America/Bogota")


def get_auth_token(email: str, password: str) -> str:
    client = TestClient(app)
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Fallo login para {email}: {res.text}"
    return res.json()["access_token"]


def test_catalogo_recursos():
    token = get_auth_token("estudiante@universidad.edu.co", "Estudiante123!")
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Listar todos los recursos activos
    res = client.get("/api/v1/recursos", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 8
    print(f"✓ Catálogo general cargado: {len(data)} recursos.")

    # 2. Filtrar por categoría herramienta
    res_her = client.get("/api/v1/recursos?categoria=herramienta", headers=headers)
    assert res_her.status_code == 200
    for r in res_her.json():
        assert r["categoria"] == "herramienta"
    print("✓ Filtro por categoría 'herramienta' OK.")

    # 3. Filtrar por texto de búsqueda
    res_fluke = client.get("/api/v1/recursos?busqueda=Fluke", headers=headers)
    assert res_fluke.status_code == 200
    assert len(res_fluke.json()) >= 1
    assert "Fluke" in res_fluke.json()[0]["marca"]
    print("✓ Filtro de búsqueda textual 'Fluke' OK.")

    # 4. Disponibilidad por fechas válidas
    ahora = datetime.now(timezone.utc)
    inicio = (ahora + timedelta(days=2)).isoformat()
    fin = (ahora + timedelta(days=3)).isoformat()
    res_disp = client.get(
        "/api/v1/recursos",
        params={"fecha_inicio": inicio, "fecha_fin": fin},
        headers=headers
    )
    assert res_disp.status_code == 200
    for r in res_disp.json():
        assert "disponible" in r
    print("✓ Cálculo de disponibilidad por rango de fechas OK.")


def test_creacion_solicitud_estudiante():
    token = get_auth_token("estudiante@universidad.edu.co", "Estudiante123!")
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    # Obtener el primer recurso disponible
    res_rec = client.get("/api/v1/recursos", headers=headers)
    recurso_id = res_rec.json()[0]["id"]

    ahora = datetime.now(timezone.utc)
    inicio = (ahora + timedelta(days=1)).isoformat()
    fin = (ahora + timedelta(days=1, hours=4)).isoformat()

    payload = {
        "recurso_ids": [recurso_id],
        "fecha_inicio": inicio,
        "fecha_fin": fin,
        "motivo": "Práctica de laboratorio de circuitos digitales"
    }

    res = client.post("/api/v1/solicitudes", json=payload, headers=headers)
    assert res.status_code == 201, f"Error al crear solicitud: {res.text}"
    data = res.json()
    assert data["estado"] == "pendiente_docente"
    assert data["solicitante"]["rol"] == "estudiante"
    assert len(data["recursos"]) == 1
    assert data["recursos"][0]["id"] == recurso_id
    print(f"✓ Solicitud de estudiante creada en estado 'pendiente_docente' (Solicitud #{data['id']}).")


def test_creacion_solicitud_docente_directa():
    token = get_auth_token("docente@universidad.edu.co", "Docente123!")
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    res_rec = client.get("/api/v1/recursos", headers=headers)
    recurso_id = res_rec.json()[1]["id"]

    ahora = datetime.now(timezone.utc)
    inicio = (ahora + timedelta(days=2)).isoformat()
    fin = (ahora + timedelta(days=2, hours=3)).isoformat()

    payload = {
        "recurso_ids": [recurso_id],
        "fecha_inicio": inicio,
        "fecha_fin": fin,
        "motivo": "Preparación de clase magistral con osciloscopio"
    }

    res = client.post("/api/v1/solicitudes", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    # Solicitud docente va directo a pendiente_responsable (RN-03)
    assert data["estado"] == "pendiente_responsable"
    assert data["solicitante"]["rol"] == "docente"
    print(f"✓ Solicitud de docente creada directo en estado 'pendiente_responsable' (Solicitud #{data['id']}).")


def test_validaciones_de_fecha():
    token = get_auth_token("estudiante@universidad.edu.co", "Estudiante123!")
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    ahora = datetime.now(timezone.utc)

    # 1. Error: Inicio posterior a Fin
    payload_invertido = {
        "recurso_ids": [1],
        "fecha_inicio": (ahora + timedelta(days=2)).isoformat(),
        "fecha_fin": (ahora + timedelta(days=1)).isoformat(),
        "motivo": "Intento de solicitud con fechas invertidas"
    }
    res_inv = client.post("/api/v1/solicitudes", json=payload_invertido, headers=headers)
    assert res_inv.status_code == 422
    assert "anterior a la fecha de finalización" in res_inv.json()["detail"]
    print("✓ Rechazo de fecha inicio >= fecha fin (HTTP 422) OK.")

    # 2. Error: Fecha de inicio en el pasado
    payload_pasado = {
        "recurso_ids": [1],
        "fecha_inicio": (ahora - timedelta(days=1)).isoformat(),
        "fecha_fin": (ahora + timedelta(days=1)).isoformat(),
        "motivo": "Intento de solicitud en fecha pasada"
    }
    res_pas = client.post("/api/v1/solicitudes", json=payload_pasado, headers=headers)
    assert res_pas.status_code == 422
    assert "en el pasado" in res_pas.json()["detail"]
    print("✓ Rechazo de fecha de inicio en el pasado (HTTP 422) OK.")


def test_cancelacion_solicitud():
    token = get_auth_token("estudiante@universidad.edu.co", "Estudiante123!")
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    # Crear solicitud para luego cancelarla
    ahora = datetime.now(timezone.utc)
    res_crear = client.post("/api/v1/solicitudes", json={
        "recurso_ids": [1],
        "fecha_inicio": (ahora + timedelta(days=5)).isoformat(),
        "fecha_fin": (ahora + timedelta(days=5, hours=2)).isoformat(),
        "motivo": "Solicitud para probar cancelación"
    }, headers=headers)
    sol_id = res_crear.json()["id"]

    # Cancelar la solicitud
    res_canc = client.post(
        f"/api/v1/solicitudes/{sol_id}/cancelar",
        json={"motivo_cancelacion": "La práctica de laboratorio fue reprogramada"},
        headers=headers
    )
    assert res_canc.status_code == 200
    assert res_canc.json()["estado"] == "cancelada"
    assert res_canc.json()["motivo_cancelacion"] == "La práctica de laboratorio fue reprogramada"
    print(f"✓ Solicitud #{sol_id} cancelada oportunamente con motivo.")


def test_bloqueo_por_inhabilitacion():
    # Insertar temporalmente una novedad de daño abierta para el estudiante
    db = SessionLocal()
    try:
        estudiante = db.query(Usuario).filter(Usuario.email == "estudiante@universidad.edu.co").first()
        recurso = db.query(Recurso).first()

        # Crear o buscar un préstamo para asociar la novedad
        solicitud_dummy = Solicitud(
            solicitante_id=estudiante.id,
            fecha_inicio=datetime.now(timezone.utc) - timedelta(days=2),
            fecha_fin=datetime.now(timezone.utc) - timedelta(days=1),
            motivo="Préstamo previo para prueba de daño",
            estado=EstadoSolicitud.APROBADA
        )
        db.add(solicitud_dummy)
        db.flush()

        prestamo_dummy = Prestamo(
            solicitud_id=solicitud_dummy.id,
            responsable_entrega_id=estudiante.id,
            fecha_entrega_real=datetime.now(timezone.utc) - timedelta(days=2),
            estado=EstadoPrestamo.DEVUELTO
        )
        db.add(prestamo_dummy)
        db.flush()

        novedad_dano = Novedad(
            prestamo_id=prestamo_dummy.id,
            recurso_id=recurso.id,
            usuario_inhabilitado_id=estudiante.id,
            tipo=TipoNovedad.DANO,
            descripcion="Pantalla de osciloscopio estrellada durante el uso",
            resuelta=False
        )
        db.add(novedad_dano)
        db.commit()
        novedad_id = novedad_dano.id
        prestamo_id = prestamo_dummy.id
        solicitud_id = solicitud_dummy.id
    finally:
        db.close()

    try:
        # Intentar radicar una solicitud mientras está inhabilitado
        token = get_auth_token("estudiante@universidad.edu.co", "Estudiante123!")
        client = TestClient(app)
        headers = {"Authorization": f"Bearer {token}"}

        ahora = datetime.now(timezone.utc)
        res_bloqueo = client.post("/api/v1/solicitudes", json={
            "recurso_ids": [1],
            "fecha_inicio": (ahora + timedelta(days=10)).isoformat(),
            "fecha_fin": (ahora + timedelta(days=10, hours=2)).isoformat(),
            "motivo": "Intento de solicitud estando inhabilitado"
        }, headers=headers)

        assert res_bloqueo.status_code == 403
        assert "Inhabilitado por novedad" in res_bloqueo.json()["detail"]
        print("✓ Bloqueo por inhabilitación por daño/faltante activo (HTTP 403) OK.")
    finally:
        # Limpiar la sanción de prueba para no contaminar tests futuros
        db_clean = SessionLocal()
        try:
            db_clean.query(Novedad).filter(Novedad.id == novedad_id).delete()
            db_clean.query(Prestamo).filter(Prestamo.id == prestamo_id).delete()
            db_clean.query(Solicitud).filter(Solicitud.id == solicitud_id).delete()
            db_clean.commit()
            print("✓ Novedad de prueba removida tras verificar el bloqueo.")
        finally:
            db_clean.close()


if __name__ == "__main__":
    print("\n--- INICIANDO SUITE DE PRUEBAS PARA LA ETAPA 2 ---")
    test_catalogo_recursos()
    test_creacion_solicitud_estudiante()
    test_creacion_solicitud_docente_directa()
    test_validaciones_de_fecha()
    test_cancelacion_solicitud()
    test_bloqueo_por_inhabilitacion()
    print("\n🎉>>> TODOS LOS 6 TESTS DE LA ETAPA 2 PASARON EXITOSAMENTE AL 100% <<<")
