import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from src.main import app
from src.database import SessionLocal
from src.models import (
    Usuario, RolUsuario,
    Recurso, CategoriaRecurso, CondicionRecurso,
    Solicitud, EstadoSolicitud, SolicitudRecurso,
    Prestamo, EstadoPrestamo,
    Novedad, TipoNovedad
)
from src.auth.security import hash_password, create_access_token


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def setup_etapa4_data():
    db = SessionLocal()

    # 1. Crear usuarios de prueba específicos
    estudiante = db.query(Usuario).filter(Usuario.email == "estudiante_test4@universidad.edu.co").first()
    if not estudiante:
        estudiante = Usuario(
            email="estudiante_test4@universidad.edu.co",
            password_hash=hash_password("Estudiante123!"),
            nombre_completo="Estudiante Test 4",
            documento="EST-T4-001",
            rol=RolUsuario.ESTUDIANTE,
            activo=True
        )
        db.add(estudiante)

    responsable = db.query(Usuario).filter(Usuario.email == "responsable_test4@universidad.edu.co").first()
    if not responsable:
        responsable = Usuario(
            email="responsable_test4@universidad.edu.co",
            password_hash=hash_password("Responsable123!"),
            nombre_completo="Responsable Test 4",
            documento="RES-T4-001",
            rol=RolUsuario.RESPONSABLE,
            activo=True
        )
        db.add(responsable)

    # 2. Crear recursos de prueba específicos
    rec_a = db.query(Recurso).filter(Recurso.codigo == "TEST-E4-A").first()
    if not rec_a:
        rec_a = Recurso(
            codigo="TEST-E4-A",
            nombre="Multímetro Test Etapa 4",
            categoria=CategoriaRecurso.HERRAMIENTA,
            marca="TestMarca",
            modelo="TM-1",
            condicion=CondicionRecurso.HABILITADO,
            ubicacion="Lab 4"
        )
        db.add(rec_a)

    rec_b = db.query(Recurso).filter(Recurso.codigo == "TEST-E4-B").first()
    if not rec_b:
        rec_b = Recurso(
            codigo="TEST-E4-B",
            nombre="Osciloscopio Test Etapa 4",
            categoria=CategoriaRecurso.EQUIPO,
            marca="TestMarca",
            modelo="TM-2",
            condicion=CondicionRecurso.HABILITADO,
            ubicacion="Lab 4"
        )
        db.add(rec_b)

    db.commit()
    db.refresh(estudiante)
    db.refresh(responsable)
    db.refresh(rec_a)
    db.refresh(rec_b)

    token_estudiante = create_access_token({"sub": str(estudiante.id), "rol": estudiante.rol.value})
    token_responsable = create_access_token({"sub": str(responsable.id), "rol": responsable.rol.value})

    ids = {
        "estudiante_id": estudiante.id,
        "responsable_id": responsable.id,
        "rec_a_id": rec_a.id,
        "rec_b_id": rec_b.id,
        "token_estudiante": token_estudiante,
        "token_responsable": token_responsable
    }

    db.close()
    return ids


def test_entrega_fisica_exitosa(client, setup_etapa4_data):
    """
    CA-04 / RF-07: Registra entrega física de una solicitud en estado APROBADA.
    Debe crear el registro de préstamo en_curso.
    """
    data = setup_etapa4_data
    db = SessionLocal()
    ahora = datetime.now(timezone.utc)

    # Crear solicitud aprobada
    sol = Solicitud(
        solicitante_id=data["estudiante_id"],
        fecha_inicio=ahora - timedelta(hours=1),
        fecha_fin=ahora + timedelta(hours=5),
        motivo="Práctica de circuitos",
        estado=EstadoSolicitud.APROBADA,
        responsable_evaluo_id=data["responsable_id"],
        fecha_evaluacion_responsable=ahora
    )
    db.add(sol)
    db.flush()

    item = SolicitudRecurso(solicitud_id=sol.id, recurso_id=data["rec_a_id"])
    db.add(item)
    db.commit()
    sol_id = sol.id
    db.close()

    # Intentar entrega física como Responsable
    headers = {"Authorization": f"Bearer {data['token_responsable']}"}
    res = client.post(
        "/api/v1/prestamos/entregar",
        json={"solicitud_id": sol_id, "observaciones": "Entrega con cables y funda"},
        headers=headers
    )

    assert res.status_code == 201, res.text
    p_data = res.json()
    assert p_data["solicitud_id"] == sol_id
    assert p_data["estado"] == "en_curso"
    assert p_data["es_vencido"] is False
    assert len(p_data["recursos"]) == 1
    assert p_data["recursos"][0]["id"] == data["rec_a_id"]


def test_bloqueo_entrega_por_prestamo_vencido_rn06(client, setup_etapa4_data):
    """
    RN-06 [B]: Si una persona tiene un préstamo vencido (fecha_fin < ahora y no devuelto),
    debe devolverlo antes de recibir otro préstamo.
    """
    data = setup_etapa4_data
    db = SessionLocal()
    ahora = datetime.now(timezone.utc)

    # 1. Crear un préstamo anterior YA VENCIDO para el estudiante
    sol_vencida = Solicitud(
        solicitante_id=data["estudiante_id"],
        fecha_inicio=ahora - timedelta(days=3),
        fecha_fin=ahora - timedelta(days=1),  # Venció ayer
        motivo="Préstamo anterior no devuelto",
        estado=EstadoSolicitud.APROBADA
    )
    db.add(sol_vencida)
    db.flush()

    item_vencido = SolicitudRecurso(solicitud_id=sol_vencida.id, recurso_id=data["rec_a_id"])
    db.add(item_vencido)

    prestamo_mora = Prestamo(
        solicitud_id=sol_vencida.id,
        responsable_entrega_id=data["responsable_id"],
        fecha_entrega_real=ahora - timedelta(days=3),
        estado=EstadoPrestamo.EN_CURSO,
        fecha_devolucion_real=None  # Sin devolver
    )
    db.add(prestamo_mora)

    # 2. Crear una nueva solicitud APROBADA para hoy
    sol_nueva = Solicitud(
        solicitante_id=data["estudiante_id"],
        fecha_inicio=ahora,
        fecha_fin=ahora + timedelta(hours=3),
        motivo="Nuevo préstamo que debe bloquearse",
        estado=EstadoSolicitud.APROBADA
    )
    db.add(sol_nueva)
    db.flush()

    item_nuevo = SolicitudRecurso(solicitud_id=sol_nueva.id, recurso_id=data["rec_b_id"])
    db.add(item_nuevo)
    db.commit()

    sol_nueva_id = sol_nueva.id
    prestamo_mora_id = prestamo_mora.id
    db.close()

    # 3. Intentar entregar la nueva solicitud -> Debe fallar con 422 por RN-06
    headers = {"Authorization": f"Bearer {data['token_responsable']}"}
    res = client.post(
        "/api/v1/prestamos/entregar",
        json={"solicitud_id": sol_nueva_id},
        headers=headers
    )

    assert res.status_code == 422, res.text
    assert "vencido" in res.json()["detail"].lower()
    assert "RN-06" in res.json()["detail"] or "regla institucional" in res.json()["detail"].lower()

    # 4. Devolver el préstamo en mora para levantar el bloqueo
    res_dev = client.post(
        f"/api/v1/prestamos/{prestamo_mora_id}/devolver",
        json={"observaciones": "Devuelto con retraso justificado"},
        headers=headers
    )
    assert res_dev.status_code == 200

    # 5. Ahora sí debe permitir entregar la nueva solicitud
    res_reintento = client.post(
        "/api/v1/prestamos/entregar",
        json={"solicitud_id": sol_nueva_id},
        headers=headers
    )
    assert res_reintento.status_code == 201


def test_devolucion_exitosa_sin_novedades(client, setup_etapa4_data):
    """
    CA-05 / RF-08: Devolución formal con todos los ítems en buen estado.
    El préstamo pasa a DEVUELTO y el recurso sigue HABILITADO.
    """
    data = setup_etapa4_data
    db = SessionLocal()
    ahora = datetime.now(timezone.utc)

    sol = Solicitud(
        solicitante_id=data["estudiante_id"],
        fecha_inicio=ahora - timedelta(hours=2),
        fecha_fin=ahora + timedelta(hours=2),
        motivo="Uso en taller",
        estado=EstadoSolicitud.APROBADA
    )
    db.add(sol)
    db.flush()

    item = SolicitudRecurso(solicitud_id=sol.id, recurso_id=data["rec_a_id"])
    db.add(item)

    prestamo = Prestamo(
        solicitud_id=sol.id,
        responsable_entrega_id=data["responsable_id"],
        fecha_entrega_real=ahora - timedelta(hours=2),
        estado=EstadoPrestamo.EN_CURSO
    )
    db.add(prestamo)
    db.commit()

    p_id = prestamo.id
    db.close()

    headers = {"Authorization": f"Bearer {data['token_responsable']}"}
    res = client.post(
        f"/api/v1/prestamos/{p_id}/devolver",
        json={
            "observaciones": "Todo en orden",
            "items": [
                {"recurso_id": data["rec_a_id"], "estado_fisico": "bueno"}
            ]
        },
        headers=headers
    )

    assert res.status_code == 200, res.text
    p_out = res.json()
    assert p_out["estado"] == "devuelto"
    assert p_out["fecha_devolucion_real"] is not None

    # Verificar condición del recurso
    db = SessionLocal()
    r = db.query(Recurso).filter(Recurso.id == data["rec_a_id"]).first()
    assert r.condicion == CondicionRecurso.HABILITADO
    db.close()


def test_devolucion_con_dano_e_inhabilitacion_rn07(client, setup_etapa4_data):
    """
    RN-07 [B]: Si devuelve un recurso dañado o incompleto, se crea la Novedad,
    el recurso queda NO_DISPONIBLE y la persona queda inhabilitada para préstamos.
    """
    data = setup_etapa4_data
    db = SessionLocal()
    ahora = datetime.now(timezone.utc)

    # Asegurar que rec_a esté HABILITADO antes del test
    r_prep = db.query(Recurso).filter(Recurso.id == data["rec_a_id"]).first()
    r_prep.condicion = CondicionRecurso.HABILITADO
    db.commit()

    sol = Solicitud(
        solicitante_id=data["estudiante_id"],
        fecha_inicio=ahora - timedelta(hours=1),
        fecha_fin=ahora + timedelta(hours=1),
        motivo="Medición de voltaje",
        estado=EstadoSolicitud.APROBADA
    )
    db.add(sol)
    db.flush()

    item = SolicitudRecurso(solicitud_id=sol.id, recurso_id=data["rec_a_id"])
    db.add(item)

    prestamo = Prestamo(
        solicitud_id=sol.id,
        responsable_entrega_id=data["responsable_id"],
        fecha_entrega_real=ahora - timedelta(hours=1),
        estado=EstadoPrestamo.EN_CURSO
    )
    db.add(prestamo)
    db.commit()

    p_id = prestamo.id
    db.close()

    # Registrar devolución con DAÑO en el recurso rec_a
    headers_resp = {"Authorization": f"Bearer {data['token_responsable']}"}
    res = client.post(
        f"/api/v1/prestamos/{p_id}/devolver",
        json={
            "observaciones": "Equipo devuelto con pantalla quebrada",
            "items": [
                {
                    "recurso_id": data["rec_a_id"],
                    "estado_fisico": "dano",
                    "descripcion_novedad": "Pantalla LCD rota por caída accidental"
                }
            ]
        },
        headers=headers_resp
    )

    assert res.status_code == 200, res.text

    # Verificar que el recurso quedó NO_DISPONIBLE y se creó la Novedad
    db = SessionLocal()
    r = db.query(Recurso).filter(Recurso.id == data["rec_a_id"]).first()
    assert r.condicion == CondicionRecurso.NO_DISPONIBLE

    nov = db.query(Novedad).filter(Novedad.prestamo_id == p_id).first()
    assert nov is not None
    assert nov.tipo == TipoNovedad.DANO
    assert nov.resuelta is False
    assert nov.usuario_inhabilitado_id == data["estudiante_id"]
    db.close()

    # Verificar que el usuario queda inhabilitado para crear solicitudes (RN-07)
    headers_est = {"Authorization": f"Bearer {data['token_estudiante']}"}
    res_sol = client.post(
        "/api/v1/solicitudes",
        json={
            "fecha_inicio": (ahora + timedelta(days=1)).isoformat(),
            "fecha_fin": (ahora + timedelta(days=1, hours=2)).isoformat(),
            "motivo": "Intento de solicitud estando inhabilitado",
            "recurso_ids": [data["rec_b_id"]]
        },
        headers=headers_est
    )
    assert res_sol.status_code == 403
    assert "inhabilitado" in res_sol.json()["detail"].lower()


def test_resolucion_novedad_y_rehabilitacion_rn08(client, setup_etapa4_data):
    """
    RN-08 [C]: Al resolver la novedad con acuerdo/reparación, el recurso puede rehabilitarse
    y el usuario recupera su capacidad de solicitar y recibir préstamos.
    """
    data = setup_etapa4_data
    db = SessionLocal()
    ahora = datetime.now(timezone.utc)

    # Buscar la novedad abierta creada en el test anterior
    nov = (
        db.query(Novedad)
        .filter(
            Novedad.usuario_inhabilitado_id == data["estudiante_id"],
            Novedad.resuelta == False
        )
        .first()
    )
    assert nov is not None
    novedad_id = nov.id
    recurso_id = nov.recurso_id
    db.close()

    headers_resp = {"Authorization": f"Bearer {data['token_responsable']}"}
    res = client.post(
        f"/api/v1/novedades/{novedad_id}/resolver",
        json={
            "observaciones_resolucion": "Estudiante abonó el repuesto y servicio técnico reemplazó la pantalla LCD.",
            "rehabilitar_recurso": True
        },
        headers=headers_resp
    )

    assert res.status_code == 200, res.text
    nov_out = res.json()
    assert nov_out["resuelta"] is True
    assert nov_out["fecha_resolucion"] is not None

    # Verificar que el recurso volvió a HABILITADO
    db = SessionLocal()
    r = db.query(Recurso).filter(Recurso.id == recurso_id).first()
    assert r.condicion == CondicionRecurso.HABILITADO
    db.close()

    # Verificar que el estudiante ahora PUEDE crear una solicitud exitosamente
    headers_est = {"Authorization": f"Bearer {data['token_estudiante']}"}
    res_sol = client.post(
        "/api/v1/solicitudes",
        json={
            "fecha_inicio": (ahora + timedelta(days=2)).isoformat(),
            "fecha_fin": (ahora + timedelta(days=2, hours=3)).isoformat(),
            "motivo": "Solicitud posterior a ser rehabilitado",
            "recurso_ids": [data["rec_b_id"]]
        },
        headers=headers_est
    )
    assert res_sol.status_code == 201, res_sol.text
