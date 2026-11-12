import os
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from starlette.testclient import TestClient
from src.main import app
from src.database import SessionLocal
from src.models import (
    Usuario, RolUsuario, Recurso, CondicionRecurso,
    Solicitud, SolicitudRecurso, EstadoSolicitud,
    Prestamo, Novedad
)


def get_token(email: str, password: str) -> str:
    client = TestClient(app)
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Fallo login {email}"
    return res.json()["access_token"]


def limpiar_base_datos():
    db = SessionLocal()
    try:
        db.query(Novedad).delete()
        db.query(Prestamo).delete()
        db.query(SolicitudRecurso).delete()
        db.query(Solicitud).delete()
        # Restablecer recursos a habilitado
        db.query(Recurso).update({Recurso.condicion: CondicionRecurso.HABILITADO})
        db.commit()
    finally:
        db.close()


def test_visto_bueno_docente():
    limpiar_base_datos()
    token_est = get_token("estudiante@universidad.edu.co", "Estudiante123!")
    token_doc = get_token("docente@universidad.edu.co", "Docente123!")
    client = TestClient(app)

    # 1. Estudiante crea solicitud
    ahora = datetime.now(timezone.utc)
    res_crear = client.post("/api/v1/solicitudes", json={
        "recurso_ids": [1],
        "fecha_inicio": (ahora + timedelta(days=2)).isoformat(),
        "fecha_fin": (ahora + timedelta(days=2, hours=3)).isoformat(),
        "motivo": "Práctica de física electromagnética"
    }, headers={"Authorization": f"Bearer {token_est}"})
    assert res_crear.status_code == 201
    sol_id = res_crear.json()["id"]
    assert res_crear.json()["estado"] == "pendiente_docente"

    # 2. Docente consulta bandeja
    res_bandeja = client.get("/api/v1/solicitudes/bandeja/docente", headers={"Authorization": f"Bearer {token_doc}"})
    assert res_bandeja.status_code == 200
    ids_en_bandeja = [s["id"] for s in res_bandeja.json()]
    assert sol_id in ids_en_bandeja
    print("✓ Solicitud estudiantil visible en bandeja docente.")

    # 3. Docente otorga visto bueno
    res_vb = client.post(
        f"/api/v1/solicitudes/{sol_id}/evaluar-docente",
        json={"aprobado": True},
        headers={"Authorization": f"Bearer {token_doc}"}
    )
    assert res_vb.status_code == 200
    data = res_vb.json()
    assert data["estado"] == "pendiente_responsable"
    assert data["docente_evaluo"]["rol"] == "docente"
    print(f"✓ Visto bueno docente otorgado a Solicitud #{sol_id} -> pasa a 'pendiente_responsable'.")


def test_rechazo_docente_con_motivo():
    limpiar_base_datos()
    token_est = get_token("estudiante@universidad.edu.co", "Estudiante123!")
    token_doc = get_token("docente@universidad.edu.co", "Docente123!")
    client = TestClient(app)

    ahora = datetime.now(timezone.utc)
    res_crear = client.post("/api/v1/solicitudes", json={
        "recurso_ids": [1],
        "fecha_inicio": (ahora + timedelta(days=3)).isoformat(),
        "fecha_fin": (ahora + timedelta(days=3, hours=2)).isoformat(),
        "motivo": "Uso para proyecto extracurricular no sustentado"
    }, headers={"Authorization": f"Bearer {token_est}"})
    sol_id = res_crear.json()["id"]

    # Rechazo sin motivo debe fallar (HTTP 422)
    res_sin_mot = client.post(
        f"/api/v1/solicitudes/{sol_id}/evaluar-docente",
        json={"aprobado": False, "motivo_rechazo": ""},
        headers={"Authorization": f"Bearer {token_doc}"}
    )
    assert res_sin_mot.status_code == 422

    # Rechazo con motivo válido
    res_rechazo = client.post(
        f"/api/v1/solicitudes/{sol_id}/evaluar-docente",
        json={"aprobado": False, "motivo_rechazo": "La práctica requiere aval previo del director de departamento"},
        headers={"Authorization": f"Bearer {token_doc}"}
    )
    assert res_rechazo.status_code == 200
    assert res_rechazo.json()["estado"] == "rechazada"
    assert "director de departamento" in res_rechazo.json()["motivo_rechazo"]
    print(f"✓ Rechazo docente de Solicitud #{sol_id} con motivo registrado con éxito.")


def test_aprobacion_responsable_crea_reserva():
    limpiar_base_datos()
    token_doc = get_token("docente@universidad.edu.co", "Docente123!")
    token_resp = get_token("responsable@universidad.edu.co", "Responsable123!")
    client = TestClient(app)

    # 1. Solicitud directa de docente (inicia en pendiente_responsable)
    ahora = datetime.now(timezone.utc)
    inicio = ahora + timedelta(days=4)
    fin = ahora + timedelta(days=4, hours=4)

    res_crear = client.post("/api/v1/solicitudes", json={
        "recurso_ids": [1, 2],
        "fecha_inicio": inicio.isoformat(),
        "fecha_fin": fin.isoformat(),
        "motivo": "Laboratorio avanzado de instrumentación"
    }, headers={"Authorization": f"Bearer {token_doc}"})
    sol_id = res_crear.json()["id"]
    assert res_crear.json()["estado"] == "pendiente_responsable"

    # 2. Responsable aprueba la solicitud
    res_aprob = client.post(
        f"/api/v1/solicitudes/{sol_id}/evaluar-responsable",
        json={"aprobado": True},
        headers={"Authorization": f"Bearer {token_resp}"}
    )
    assert res_aprob.status_code == 200
    data = res_aprob.json()
    assert data["estado"] == "aprobada"
    assert data["responsable_evaluo"]["rol"] == "responsable"
    print(f"✓ Solicitud #{sol_id} aprobada por Responsable. Reserva firme consolidada.")

    # 3. Comprobar que los recursos 1 y 2 ya NO están disponibles en esas fechas
    res_disp = client.get(
        "/api/v1/recursos",
        params={"fecha_inicio": inicio.isoformat(), "fecha_fin": fin.isoformat()},
        headers={"Authorization": f"Bearer {token_resp}"}
    )
    assert res_disp.status_code == 200
    recursos = res_disp.json()
    r1 = next(r for r in recursos if r["id"] == 1)
    r2 = next(r for r in recursos if r["id"] == 2)
    assert r1["disponible"] is False
    assert r2["disponible"] is False
    assert f"Solicitud #{sol_id}" in r1["motivo_no_disponible"]
    print("✓ Disponibilidad en catálogo refleja correctamente la reserva firme aprobada.")


def test_regla_fifo_estricta():
    limpiar_base_datos()
    token_est = get_token("estudiante@universidad.edu.co", "Estudiante123!")
    token_doc = get_token("docente@universidad.edu.co", "Docente123!")
    token_resp = get_token("responsable@universidad.edu.co", "Responsable123!")
    client = TestClient(app)

    ahora = datetime.now(timezone.utc)
    inicio = ahora + timedelta(days=6)
    fin = ahora + timedelta(days=6, hours=3)

    # 1. Solicitud 1 (anterior, por Estudiante)
    res_sol1 = client.post("/api/v1/solicitudes", json={
        "recurso_ids": [3],
        "fecha_inicio": inicio.isoformat(),
        "fecha_fin": fin.isoformat(),
        "motivo": "Solicitud previa número 1 (Estudiante)"
    }, headers={"Authorization": f"Bearer {token_est}"})
    sol1_id = res_sol1.json()["id"]

    # Dar un pequeño retraso de timestamp
    time.sleep(0.05)

    # 2. Solicitud 2 (posterior, por Docente - va directo a pendiente_responsable)
    res_sol2 = client.post("/api/v1/solicitudes", json={
        "recurso_ids": [3],
        "fecha_inicio": inicio.isoformat(),
        "fecha_fin": fin.isoformat(),
        "motivo": "Solicitud posterior número 2 (Docente que compite por mismo recurso y fecha)"
    }, headers={"Authorization": f"Bearer {token_doc}"})
    sol2_id = res_sol2.json()["id"]

    # 3. Intentar aprobar la Solicitud 2 (posterior) mientras la Solicitud 1 está pendiente
    res_aprob_indebida = client.post(
        f"/api/v1/solicitudes/{sol2_id}/evaluar-responsable",
        json={"aprobado": True},
        headers={"Authorization": f"Bearer {token_resp}"}
    )
    # Debe ser bloqueada por FIFO (HTTP 422)
    assert res_aprob_indebida.status_code == 422
    assert "Bloqueo por orden de llegada (FIFO)" in res_aprob_indebida.json()["detail"]
    assert f"#{sol1_id}" in res_aprob_indebida.json()["detail"]
    print(f"✓ Bloqueo FIFO verificado: Solicitud posterior #{sol2_id} bloqueada por solicitud anterior #{sol1_id}.")

    # 4. Docente rechaza la Solicitud 1
    client.post(
        f"/api/v1/solicitudes/{sol1_id}/evaluar-docente",
        json={"aprobado": False, "motivo_rechazo": "Estudiante no asistirá"},
        headers={"Authorization": f"Bearer {token_doc}"}
    )

    # 5. Ahora la Solicitud 2 ya NO está bloqueada y puede aprobarse
    res_aprob_desbloqueada = client.post(
        f"/api/v1/solicitudes/{sol2_id}/evaluar-responsable",
        json={"aprobado": True},
        headers={"Authorization": f"Bearer {token_resp}"}
    )
    assert res_aprob_desbloqueada.status_code == 200
    assert res_aprob_desbloqueada.json()["estado"] == "aprobada"
    print(f"✓ Tras rechazo de solicitud previa bloqueante, Solicitud #{sol2_id} aprobada con éxito.")


def test_bloqueo_por_condicion_no_disponible():
    limpiar_base_datos()
    token_doc = get_token("docente@universidad.edu.co", "Docente123!")
    token_resp = get_token("responsable@universidad.edu.co", "Responsable123!")
    client = TestClient(app)

    ahora = datetime.now(timezone.utc)
    res_sol = client.post("/api/v1/solicitudes", json={
        "recurso_ids": [4],
        "fecha_inicio": (ahora + timedelta(days=8)).isoformat(),
        "fecha_fin": (ahora + timedelta(days=8, hours=2)).isoformat(),
        "motivo": "Práctica con estación de soldadura"
    }, headers={"Authorization": f"Bearer {token_doc}"})
    sol_id = res_sol.json()["id"]

    # Simular que el recurso 4 se daña antes de aprobar
    db = SessionLocal()
    try:
        r4 = db.query(Recurso).filter(Recurso.id == 4).first()
        r4.condicion = CondicionRecurso.NO_DISPONIBLE
        db.commit()
    finally:
        db.close()

    # Intentar aprobar solicitud con recurso en condición no disponible
    res_aprob_dano = client.post(
        f"/api/v1/solicitudes/{sol_id}/evaluar-responsable",
        json={"aprobado": True},
        headers={"Authorization": f"Bearer {token_resp}"}
    )
    assert res_aprob_dano.status_code == 409
    assert "no_disponible" in res_aprob_dano.json()["detail"]
    print("✓ Bloqueo por condición física no disponible (HTTP 409) OK.")

    # Restaurar
    limpiar_base_datos()


if __name__ == "__main__":
    print("\n--- INICIANDO SUITE DE PRUEBAS PARA LA ETAPA 3 ---")
    test_visto_bueno_docente()
    test_rechazo_docente_con_motivo()
    test_aprobacion_responsable_crea_reserva()
    test_regla_fifo_estricta()
    test_bloqueo_por_condicion_no_disponible()
    print("\n🎉>>> TODOS LOS 5 TESTS DE LA ETAPA 3 PASARON EXITOSAMENTE AL 100% <<<")

