import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import or_
from src.main import app
from src.database import SessionLocal
from src.models import (
    Usuario, RolUsuario,
    Recurso, CategoriaRecurso, CondicionRecurso,
    Solicitud, SolicitudRecurso, EstadoSolicitud,
    Prestamo, EstadoPrestamo,
    Novedad, TipoNovedad,
    AuditoriaEvento
)
from src.auth.security import hash_password, create_access_token
from src.services.prestamo_service import calcular_si_prestamo_vencido
from src.services.recurso_service import BOGOTA_TZ

URL_METRICAS = "/api/v1/reportes/metricas"
URL_CONSOLIDADO = "/api/v1/reportes/consolidado"
URL_AUDITORIA = "/api/v1/reportes/auditoria"

# Un solo hash reutilizado (Argon2 es lento a propósito)
PASSWORD_HASH = hash_password("Test5Reportes123!")

# Datos propios de esta etapa: no se tocan usuarios ni recursos de otras pruebas
USUARIOS_T5 = {
    "estudiante": ("est.reportes.t5@universidad.edu.co", "Estudiante Reportes T5", "EST-T5-001", RolUsuario.ESTUDIANTE),
    "docente": ("doc.reportes.t5@universidad.edu.co", "Docente Reportes T5", "DOC-T5-001", RolUsuario.DOCENTE),
    "responsable": ("resp.reportes.t5@universidad.edu.co", "Responsable Reportes T5", "RES-T5-001", RolUsuario.RESPONSABLE),
    "coordinacion": ("coord.reportes.t5@universidad.edu.co", "Coordinación Reportes T5", "CRD-T5-001", RolUsuario.COORDINACION),
}
RECURSOS_T5 = {
    "h1": ("TEST-E5-H1", "Multímetro Reportes T5", CategoriaRecurso.HERRAMIENTA),
    "h2": ("TEST-E5-H2", "Soldador Reportes T5", CategoriaRecurso.HERRAMIENTA),
    "e1": ("TEST-E5-E1", "Osciloscopio Reportes T5", CategoriaRecurso.EQUIPO),
    "e2": ("TEST-E5-E2", "Proyector Reportes T5", CategoriaRecurso.EQUIPO),
}



# Utilidades de prueba


def _utc(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _limpiar_datos_t5(db):
    """Elimina únicamente los datos creados por esta suite."""
    uids = [r[0] for r in db.query(Usuario.id).filter(Usuario.email.in_([v[0] for v in USUARIOS_T5.values()])).all()]
    rids = [r[0] for r in db.query(Recurso.id).filter(Recurso.codigo.in_([v[0] for v in RECURSOS_T5.values()])).all()]
    sids = [r[0] for r in db.query(Solicitud.id).filter(Solicitud.solicitante_id.in_(uids)).all()] if uids else []

    if uids or rids:
        db.query(Novedad).filter(
            or_(Novedad.usuario_inhabilitado_id.in_(uids), Novedad.recurso_id.in_(rids))
        ).delete(synchronize_session=False)
    if sids:
        db.query(Prestamo).filter(Prestamo.solicitud_id.in_(sids)).delete(synchronize_session=False)
    if sids or rids:
        db.query(SolicitudRecurso).filter(
            or_(SolicitudRecurso.solicitud_id.in_(sids), SolicitudRecurso.recurso_id.in_(rids))
        ).delete(synchronize_session=False)
    if sids:
        db.query(Solicitud).filter(Solicitud.id.in_(sids)).delete(synchronize_session=False)
    if uids:
        db.query(AuditoriaEvento).filter(AuditoriaEvento.usuario_id.in_(uids)).delete(synchronize_session=False)
    if rids:
        db.query(Recurso).filter(Recurso.id.in_(rids)).delete(synchronize_session=False)
    if uids:
        db.query(Usuario).filter(Usuario.id.in_(uids)).delete(synchronize_session=False)
    db.commit()


def _oraculo_metricas(db):
    """Calcula las métricas directamente desde la BD, de forma independiente al servicio de reportes."""
    ahora = datetime.now(timezone.utc)
    prestamos = db.query(Prestamo).all()
    activos = [p for p in prestamos if p.estado == EstadoPrestamo.EN_CURSO]
    vencidos = [p for p in activos if calcular_si_prestamo_vencido(p, ahora)]
    devueltos = [p for p in prestamos if p.estado == EstadoPrestamo.DEVUELTO]
    a_tiempo = [p for p in devueltos if _utc(p.fecha_devolucion_real) <= _utc(p.solicitud.fecha_fin)]
    abiertas = db.query(Novedad).filter(Novedad.resuelta == False).all()  # noqa: E712
    return {
        "total_prestamos": len(prestamos),
        "prestamos_activos": len(activos),
        "prestamos_vencidos": len(vencidos),
        "prestamos_devueltos": len(devueltos),
        "devueltos_a_tiempo": len(a_tiempo),
        "recursos_totales": db.query(Recurso).count(),
        "recursos_no_disponibles": db.query(Recurso).filter(
            Recurso.condicion == CondicionRecurso.NO_DISPONIBLE
        ).count(),
        "novedades_abiertas": len(abiertas),
        "recursos_con_novedad_abierta": len({n.recurso_id for n in abiertas}),
    }


def _crear_prestamo(db, *, solicitante, recursos, inicio, fin, entrega, devolucion, docente, responsable):
    sol = Solicitud(
        solicitante_id=solicitante.id,
        fecha_inicio=inicio,
        fecha_fin=fin,
        motivo="Práctica de laboratorio (reportes T5)",
        estado=EstadoSolicitud.APROBADA,
        docente_evaluo_id=docente.id if docente else None,
        fecha_evaluacion_docente=(inicio - timedelta(hours=2)) if docente else None,
        responsable_evaluo_id=responsable.id,
        fecha_evaluacion_responsable=inicio - timedelta(hours=1)
    )
    db.add(sol)
    db.flush()
    for r in recursos:
        db.add(SolicitudRecurso(solicitud_id=sol.id, recurso_id=r.id))

    prestamo = Prestamo(
        solicitud_id=sol.id,
        responsable_entrega_id=responsable.id,
        fecha_entrega_real=entrega,
        estado=EstadoPrestamo.DEVUELTO if devolucion else EstadoPrestamo.EN_CURSO,
        responsable_recepcion_id=responsable.id if devolucion else None,
        fecha_devolucion_real=devolucion
    )
    db.add(prestamo)
    db.flush()
    return prestamo


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def escenario():
    """
    Escenario controlado (4 préstamos):
      P1  docente     [H1]      devuelto a tiempo
      P2  estudiante  [E1]      devuelto 3 h tarde, con novedad de daño abierta (E1 -> no_disponible)
      P3  estudiante  [H2, E2]  en curso y VENCIDO (fecha fin hace 3 h)
      P4  docente     [H1]      en curso dentro del plazo
    """
    db = SessionLocal()
    try:
        _limpiar_datos_t5(db)
        base = _oraculo_metricas(db)
        ahora = datetime.now(timezone.utc)

        usuarios = {}
        for clave, (email, nombre, documento, rol) in USUARIOS_T5.items():
            u = Usuario(email=email, password_hash=PASSWORD_HASH, nombre_completo=nombre,
                        documento=documento, rol=rol, activo=True)
            db.add(u)
            usuarios[clave] = u

        recursos = {}
        for clave, (codigo, nombre, categoria) in RECURSOS_T5.items():
            r = Recurso(codigo=codigo, nombre=nombre, categoria=categoria,
                        condicion=CondicionRecurso.HABILITADO, ubicacion="Lab Reportes T5")
            db.add(r)
            recursos[clave] = r
        db.flush()

        est, doc, resp = usuarios["estudiante"], usuarios["docente"], usuarios["responsable"]

        p1 = _crear_prestamo(
            db, solicitante=doc, recursos=[recursos["h1"]], docente=None, responsable=resp,
            inicio=ahora - timedelta(days=10), fin=ahora - timedelta(days=10) + timedelta(hours=4),
            entrega=ahora - timedelta(days=10) + timedelta(minutes=10),
            devolucion=ahora - timedelta(days=10) + timedelta(hours=3)
        )
        p2 = _crear_prestamo(
            db, solicitante=est, recursos=[recursos["e1"]], docente=doc, responsable=resp,
            inicio=ahora - timedelta(days=5), fin=ahora - timedelta(days=5) + timedelta(hours=4),
            entrega=ahora - timedelta(days=5) + timedelta(minutes=10),
            devolucion=ahora - timedelta(days=5) + timedelta(hours=7)
        )
        db.add(Novedad(
            prestamo_id=p2.id, recurso_id=recursos["e1"].id, usuario_inhabilitado_id=est.id,
            tipo=TipoNovedad.DANO, descripcion="Pantalla averiada al devolver (T5)", resuelta=False
        ))
        recursos["e1"].condicion = CondicionRecurso.NO_DISPONIBLE

        p3 = _crear_prestamo(
            db, solicitante=est, recursos=[recursos["h2"], recursos["e2"]], docente=doc, responsable=resp,
            inicio=ahora - timedelta(hours=8), fin=ahora - timedelta(hours=3),
            entrega=ahora - timedelta(hours=7, minutes=50), devolucion=None
        )
        p4 = _crear_prestamo(
            db, solicitante=doc, recursos=[recursos["h1"]], docente=None, responsable=resp,
            inicio=ahora - timedelta(hours=1), fin=ahora + timedelta(hours=5),
            entrega=ahora - timedelta(minutes=50), devolucion=None
        )

        db.add(AuditoriaEvento(usuario_id=resp.id, accion="ENTREGA_PRESTAMO", entidad="prestamos",
                               entidad_id=p3.id, detalles="Entrega registrada (T5)"))
        db.add(AuditoriaEvento(usuario_id=resp.id, accion="DEVOLUCION_PRESTAMO", entidad="prestamos",
                               entidad_id=p2.id, detalles="Devolución con daño registrada (T5)"))
        db.commit()

        yield {
            "base": base,
            "ids": {"p1": p1.id, "p2": p2.id, "p3": p3.id, "p4": p4.id},
            "nombres": {k: v[1] for k, v in USUARIOS_T5.items()},
            "tokens": {
                clave: create_access_token({"sub": str(u.id), "rol": u.rol.value})
                for clave, u in usuarios.items()
            },
        }
    finally:
        db.rollback()
        _limpiar_datos_t5(db)
        db.close()


def _consolidado(client, escenario, rol="coordinacion", **params):
    res = client.get(URL_CONSOLIDADO, params=params, headers=_auth(escenario["tokens"][rol]))
    assert res.status_code == 200, res.text
    return res.json()


def _ids(data):
    return [item["prestamo_id"] for item in data["items"]]



# Test 1: control de acceso (RBAC)


def test_rbac_reportes_solo_coordinacion_y_responsable(client, escenario):
    for url in (URL_METRICAS, URL_CONSOLIDADO, URL_AUDITORIA):
        # Sin sesión
        assert client.get(url).status_code == 401, f"{url} debe exigir autenticación"

        # Estudiante y Docente: acceso denegado
        for rol in ("estudiante", "docente"):
            res = client.get(url, headers=_auth(escenario["tokens"][rol]))
            assert res.status_code == 403, f"{rol} no debe acceder a {url}"

        # Coordinación y Responsable: acceso permitido
        for rol in ("coordinacion", "responsable"):
            res = client.get(url, headers=_auth(escenario["tokens"][rol]))
            assert res.status_code == 200, f"{rol} debe acceder a {url}: {res.text}"


def test_vista_web_reportes_restringida_por_rol(client, escenario):
    for rol in ("coordinacion", "responsable"):
        res = client.get("/reportes/consolidado", headers=_auth(escenario["tokens"][rol]), follow_redirects=False)
        assert res.status_code == 200
        assert "Consulta Consolidada" in res.text

    for rol in ("estudiante", "docente"):
        res = client.get("/reportes/consolidado", headers=_auth(escenario["tokens"][rol]), follow_redirects=False)
        assert res.status_code == 302
        assert res.headers["location"] == "/"

    res = client.get("/reportes/consolidado", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "/login"



# Test 2: precisión de las métricas


def test_metricas_coinciden_con_base_de_datos(client, escenario):
    res = client.get(URL_METRICAS, params={"top": 20}, headers=_auth(escenario["tokens"]["coordinacion"]))
    assert res.status_code == 200
    m = res.json()

    # 1) Coincide con el cálculo independiente directo sobre la BD
    db = SessionLocal()
    try:
        esperado = _oraculo_metricas(db)
    finally:
        db.close()
    for campo, valor in esperado.items():
        assert m[campo] == valor, f"{campo}: API={m[campo]} BD={valor}"

    # 2) Aporte exacto del escenario controlado sobre la línea base
    base = escenario["base"]
    assert m["total_prestamos"] - base["total_prestamos"] == 4
    assert m["prestamos_activos"] - base["prestamos_activos"] == 2      # P3 y P4
    assert m["prestamos_vencidos"] - base["prestamos_vencidos"] == 1    # solo P3
    assert m["prestamos_devueltos"] - base["prestamos_devueltos"] == 2  # P1 y P2
    assert m["devueltos_a_tiempo"] - base["devueltos_a_tiempo"] == 1    # solo P1
    assert m["devueltos_con_retraso"] == m["prestamos_devueltos"] - m["devueltos_a_tiempo"]
    assert m["recursos_totales"] - base["recursos_totales"] == 4
    assert m["recursos_no_disponibles"] - base["recursos_no_disponibles"] == 1  # E1 dañado
    assert m["recursos_con_novedad_abierta"] - base["recursos_con_novedad_abierta"] == 1
    assert m["novedades_abiertas"] - base["novedades_abiertas"] == 1

    # 3) Tasa de cumplimiento = devueltos a tiempo / devueltos
    assert m["tasa_cumplimiento"] == pytest.approx(
        m["devueltos_a_tiempo"] * 100.0 / m["prestamos_devueltos"], abs=0.1
    )

    # 4) Rankings
    ranking = {r["codigo"]: r["total_prestamos"] for r in m["recursos_mas_prestados"]}
    assert ranking["TEST-E5-H1"] == 2   # P1 y P4
    assert ranking["TEST-E5-H2"] == 1

    con_novedad = {r["codigo"]: r for r in m["recursos_con_novedades_abiertas"]}
    assert con_novedad["TEST-E5-E1"]["novedades_abiertas"] == 1
    assert con_novedad["TEST-E5-E1"]["tipos"] == ["dano"]
    assert con_novedad["TEST-E5-E1"]["condicion"] == "no_disponible"



# Test 3: filtros de la consulta consolidada


def test_consolidado_filtros_por_estado_solicitante_y_categoria(client, escenario):
    ids = escenario["ids"]
    est = "est.reportes.t5"   # texto único que identifica al estudiante de la suite
    doc = "doc.reportes.t5"

    # Sin filtros de estado: el estudiante tiene P2 y P3 (más reciente primero)
    data = _consolidado(client, escenario, solicitante=est)
    assert data["total_registros"] == 2
    assert _ids(data) == [ids["p3"], ids["p2"]]

    # Estado: vencido / en_curso / devuelto
    assert _ids(_consolidado(client, escenario, solicitante=est, estado="vencido")) == [ids["p3"]]
    assert _ids(_consolidado(client, escenario, solicitante=doc, estado="en_curso")) == [ids["p4"]]
    assert _ids(_consolidado(client, escenario, solicitante=doc, estado="devuelto")) == [ids["p1"]]
    assert _ids(_consolidado(client, escenario, solicitante=est, estado="devuelto")) == [ids["p2"]]

    # Un préstamo vencido sigue contando como "en_curso", pero uno al día no es vencido
    en_curso_doc = _consolidado(client, escenario, solicitante=doc, estado="vencido")
    assert en_curso_doc["total_registros"] == 0

    # Categoría de recurso
    assert set(_ids(_consolidado(client, escenario, solicitante=est, categoria="equipo"))) == {ids["p2"], ids["p3"]}
    assert _ids(_consolidado(client, escenario, solicitante=est, categoria="herramienta")) == [ids["p3"]]
    assert set(_ids(_consolidado(client, escenario, solicitante=doc, categoria="equipo"))) == set()

    # Paginación: total_registros no depende del limit
    pag = _consolidado(client, escenario, solicitante=est, limit=1)
    assert pag["total_registros"] == 2 and len(pag["items"]) == 1


def test_consolidado_filtros_por_rango_de_fechas(client, escenario):
    ids = escenario["ids"]
    est = "est.reportes.t5"
    hoy = datetime.now(timezone.utc).astimezone(BOGOTA_TZ).date()

    # P2 se entregó hace ~5 días y P3 hace ~8 horas
    desde_reciente = (hoy - timedelta(days=2)).isoformat()
    assert _ids(_consolidado(client, escenario, solicitante=est, fecha_desde=desde_reciente)) == [ids["p3"]]

    hasta_antiguo = (hoy - timedelta(days=4)).isoformat()
    assert _ids(_consolidado(client, escenario, solicitante=est, fecha_hasta=hasta_antiguo)) == [ids["p2"]]

    rango_amplio = _consolidado(
        client, escenario, solicitante=est,
        fecha_desde=(hoy - timedelta(days=7)).isoformat(), fecha_hasta=(hoy + timedelta(days=1)).isoformat()
    )
    assert set(_ids(rango_amplio)) == {ids["p2"], ids["p3"]}

    futuro = (hoy + timedelta(days=30)).isoformat()
    assert _consolidado(client, escenario, solicitante=est, fecha_desde=futuro)["total_registros"] == 0

    # Validaciones: rango invertido y estado inexistente -> 422
    headers = _auth(escenario["tokens"]["coordinacion"])
    res = client.get(URL_CONSOLIDADO, params={"fecha_desde": "2026-12-31", "fecha_hasta": "2026-01-01"}, headers=headers)
    assert res.status_code == 422
    res = client.get(URL_CONSOLIDADO, params={"estado": "inexistente"}, headers=headers)
    assert res.status_code == 422



# Test 4: contenido del consolidado (trazabilidad y morosidad)


def test_consolidado_trazabilidad_morosidad_y_novedades(client, escenario):
    ids = escenario["ids"]
    nombres = escenario["nombres"]
    data = _consolidado(client, escenario, solicitante="reportes.t5")
    por_id = {item["prestamo_id"]: item for item in data["items"]}
    assert set(por_id) == set(ids.values())

    # P3: vencido, con mora de ~3 h y dos recursos
    p3 = por_id[ids["p3"]]
    assert p3["estado"] == "en_curso" and p3["es_vencido"] is True
    assert 2.9 <= p3["horas_retraso"] <= 3.5
    assert p3["devuelto_a_tiempo"] is None
    assert [r["codigo"] for r in p3["recursos"]] == ["TEST-E5-E2", "TEST-E5-H2"]
    assert p3["trazabilidad"]["responsable_recepcion"] is None

    # P2: devuelto tarde, con novedad abierta y trazabilidad completa de estudiante
    p2 = por_id[ids["p2"]]
    assert p2["estado"] == "devuelto" and p2["es_vencido"] is False
    assert p2["devuelto_a_tiempo"] is False
    assert p2["horas_retraso"] == pytest.approx(3.0, abs=0.05)
    assert p2["solicitante"]["nombre_completo"] == nombres["estudiante"]
    assert p2["trazabilidad"]["docente_aprobo"]["nombre_completo"] == nombres["docente"]
    assert p2["trazabilidad"]["responsable_aprobo"]["nombre_completo"] == nombres["responsable"]
    assert p2["trazabilidad"]["responsable_entrega"]["nombre_completo"] == nombres["responsable"]
    assert p2["trazabilidad"]["responsable_recepcion"]["nombre_completo"] == nombres["responsable"]
    assert len(p2["novedades"]) == 1
    assert p2["novedades"][0]["tipo"] == "dano" and p2["novedades"][0]["resuelta"] is False
    assert p2["recursos"][0]["condicion"] == "no_disponible"

    # P1: devuelto a tiempo (sin retraso) y solicitud directa de docente (sin aval previo)
    p1 = por_id[ids["p1"]]
    assert p1["devuelto_a_tiempo"] is True and p1["horas_retraso"] is None
    assert p1["trazabilidad"]["docente_aprobo"] is None

    # P4: en curso dentro del plazo
    p4 = por_id[ids["p4"]]
    assert p4["estado"] == "en_curso" and p4["es_vencido"] is False and p4["horas_retraso"] is None



# Test 5: resumen de trazabilidad y auditoría


def test_resumen_auditoria(client, escenario):
    res = client.get(URL_AUDITORIA, params={"limite": 10}, headers=_auth(escenario["tokens"]["coordinacion"]))
    assert res.status_code == 200
    data = res.json()

    acciones = {a["accion"]: a["total"] for a in data["eventos_por_accion"]}
    assert acciones.get("ENTREGA_PRESTAMO", 0) >= 1
    assert acciones.get("DEVOLUCION_PRESTAMO", 0) >= 1
    assert data["total_eventos"] >= 2
    assert data["total_eventos"] == sum(acciones.values())

    recientes = [e for e in data["ultimos_eventos"] if e["usuario_nombre"] == escenario["nombres"]["responsable"]]
    assert len(recientes) == 2