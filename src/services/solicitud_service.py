from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from src.models import (
    Usuario, RolUsuario,
    Recurso, CondicionRecurso,
    Solicitud, SolicitudRecurso, EstadoSolicitud,
    Novedad, TipoNovedad,
    AuditoriaEvento
)
from src.schemas.solicitud import SolicitudCreate, SolicitudOut
from src.schemas.recurso import RecursoOut
from src.schemas.auth import UsuarioSummary
from src.services.recurso_service import asegurar_utc


def usuario_esta_inhabilitado(db: Session, usuario_id: int) -> Tuple[bool, Optional[str]]:
    """
    Verifica si el usuario tiene novedades abiertas por daño o faltante que lo inhabiliten.
    """
    novedad = (
        db.query(Novedad)
        .filter(
            Novedad.usuario_inhabilitado_id == usuario_id,
            Novedad.resuelta == False,
            Novedad.tipo.in_([TipoNovedad.DANO, TipoNovedad.FALTANTE])
        )
        .first()
    )
    if novedad:
        return True, f"Inhabilitado por novedad #{novedad.id} abierta ({novedad.tipo.value}): {novedad.descripcion}"
    return False, None


def formatear_solicitud_out(solicitud: Solicitud) -> SolicitudOut:
    """Convierte un modelo Solicitud ORM en SolicitudOut con sus relaciones completas."""
    recursos_out = [
        RecursoOut.model_validate(asoc.recurso)
        for asoc in solicitud.recursos_asociados
    ]
    
    docente_summary = (
        UsuarioSummary.model_validate(solicitud.docente_evaluo)
        if solicitud.docente_evaluo else None
    )
    responsable_summary = (
        UsuarioSummary.model_validate(solicitud.responsable_evaluo)
        if solicitud.responsable_evaluo else None
    )

    return SolicitudOut(
        id=solicitud.id,
        solicitante_id=solicitud.solicitante_id,
        solicitante=UsuarioSummary.model_validate(solicitud.solicitante),
        fecha_inicio=solicitud.fecha_inicio,
        fecha_fin=solicitud.fecha_fin,
        motivo=solicitud.motivo,
        estado=solicitud.estado,
        motivo_rechazo=solicitud.motivo_rechazo,
        motivo_cancelacion=solicitud.motivo_cancelacion,
        docente_evaluo_id=solicitud.docente_evaluo_id,
        docente_evaluo=docente_summary,
        fecha_evaluacion_docente=solicitud.fecha_evaluacion_docente,
        responsable_evaluo_id=solicitud.responsable_evaluo_id,
        responsable_evaluo=responsable_summary,
        fecha_evaluacion_responsable=solicitud.fecha_evaluacion_responsable,
        creado_en=solicitud.creado_en,
        recursos=recursos_out
    )


def crear_solicitud(
    db: Session,
    solicitante: Usuario,
    datos: SolicitudCreate
) -> SolicitudOut:
    """
    Registra una solicitud de préstamo en la base de datos aplicando todas las validaciones de negocio.
    """
    # 1. Permisos de rol: Estudiantes y docentes pueden radicar solicitudes
    if solicitante.rol not in [RolUsuario.ESTUDIANTE, RolUsuario.DOCENTE]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los estudiantes y docentes están autorizados para radicar solicitudes de recursos."
        )

    # 2. Verificación de inhabilitación por daño o faltante
    inhabilitado, motivo_inh = usuario_esta_inhabilitado(db, solicitante.id)
    if inhabilitado:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No puede radicar solicitudes: {motivo_inh}"
        )

    # 3. Normalización y validación estricta de fechas
    inicio_utc = asegurar_utc(datos.fecha_inicio)
    fin_utc = asegurar_utc(datos.fecha_fin)
    ahora_utc = datetime.now(timezone.utc)

    if inicio_utc >= fin_utc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La fecha de inicio debe ser estrictamente anterior a la fecha de finalización."
        )

    # Tolerancia de 5 minutos al enviar el formulario para evitar falsos rechazos
    if inicio_utc < (ahora_utc - timedelta(minutes=5)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La fecha y hora de inicio no puede ser en el pasado."
        )

    # 4. Validación de recursos seleccionados
    ids_unicos = list(set(datos.recurso_ids))
    if not ids_unicos:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Debe seleccionar al menos un recurso para la solicitud."
        )

    recursos = db.query(Recurso).filter(Recurso.id.in_(ids_unicos)).all()
    if len(recursos) != len(ids_unicos):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uno o varios recursos seleccionados no existen en el sistema."
        )

    for r in recursos:
        if r.condicion == CondicionRecurso.DADO_DE_BAJA:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"El recurso '{r.nombre}' ({r.codigo}) está dado de baja y no puede solicitarse."
            )

    # 5. Determinación del estado inicial según rol (RN-02 y RN-03)
    if solicitante.rol == RolUsuario.ESTUDIANTE:
        estado_inicial = EstadoSolicitud.PENDIENTE_DOCENTE
    else:
        # Rol docente pasa directo a evaluación del responsable
        estado_inicial = EstadoSolicitud.PENDIENTE_RESPONSABLE

    # 6. Persistencia transaccional de la solicitud
    with db.begin_nested():
        nueva_solicitud = Solicitud(
            solicitante_id=solicitante.id,
            fecha_inicio=inicio_utc,
            fecha_fin=fin_utc,
            motivo=datos.motivo.strip(),
            estado=estado_inicial
        )
        db.add(nueva_solicitud)
        db.flush()

        # Asociar recursos
        for r_id in ids_unicos:
            asoc = SolicitudRecurso(
                solicitud_id=nueva_solicitud.id,
                recurso_id=r_id
            )
            db.add(asoc)

        # Auditoría
        auditoria = AuditoriaEvento(
            usuario_id=solicitante.id,
            accion="CREACION_SOLICITUD",
            entidad="solicitud",
            entidad_id=nueva_solicitud.id,
            detalles=f"Solicitud creada en estado {estado_inicial.value} con {len(ids_unicos)} recursos."
        )
        db.add(auditoria)

    db.commit()
    db.refresh(nueva_solicitud)
    return formatear_solicitud_out(nueva_solicitud)


def cancelar_solicitud(
    db: Session,
    solicitud_id: int,
    usuario_actual: Usuario,
    motivo_cancelacion: str
) -> SolicitudOut:
    """
    Cancela una solicitud antes de su entrega física y libera reservas asociadas.
    """
    solicitud = db.query(Solicitud).filter(Solicitud.id == solicitud_id).first()
    if not solicitud:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Solicitud #{solicitud_id} no encontrada."
        )

    # Solo el solicitante o un responsable/coordinador pueden cancelar
    es_propietario = solicitud.solicitante_id == usuario_actual.id
    es_admin = usuario_actual.rol in [RolUsuario.RESPONSABLE, RolUsuario.COORDINACION]
    if not (es_propietario or es_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene autorización para cancelar esta solicitud."
        )

    # No se puede cancelar si ya fue entregada
    if solicitud.prestamo is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede cancelar una solicitud con entrega física registrada. Debe tramitarse la devolución."
        )

    # Estados cancelables
    if solicitud.estado in [EstadoSolicitud.RECHAZADA, EstadoSolicitud.CANCELADA]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La solicitud ya se encuentra en estado '{solicitud.estado.value}'."
        )

    with db.begin_nested():
        estado_previo = solicitud.estado.value
        solicitud.estado = EstadoSolicitud.CANCELADA
        solicitud.motivo_cancelacion = motivo_cancelacion.strip()

        auditoria = AuditoriaEvento(
            usuario_id=usuario_actual.id,
            accion="CANCELACION_SOLICITUD",
            entidad="solicitud",
            entidad_id=solicitud.id,
            detalles=f"Solicitud #{solicitud.id} cancelada desde estado '{estado_previo}'. Motivo: {motivo_cancelacion.strip()}"
        )
        db.add(auditoria)

    db.commit()
    db.refresh(solicitud)
    return formatear_solicitud_out(solicitud)


def listar_solicitudes(
    db: Session,
    usuario_actual: Usuario,
    estado: Optional[EstadoSolicitud] = None,
    solo_propias: bool = False
) -> List[SolicitudOut]:
    """
    Lista solicitudes respetando las reglas de visibilidad según rol:
    - Estudiantes solo ven sus propias solicitudes.
    - Docentes pueden ver sus solicitudes o las pendientes de su aval.
    - Responsables y Coordinación pueden consultar todas las solicitudes.
    """
    query = db.query(Solicitud)

    if usuario_actual.rol == RolUsuario.ESTUDIANTE or solo_propias:
        query = query.filter(Solicitud.solicitante_id == usuario_actual.id)
    elif usuario_actual.rol == RolUsuario.DOCENTE and not solo_propias:
        # Docentes ven sus solicitudes propias y aquellas pendientes de visto bueno docente
        query = query.filter(
            (Solicitud.solicitante_id == usuario_actual.id) |
            (Solicitud.estado == EstadoSolicitud.PENDIENTE_DOCENTE)
        )

    if estado:
        query = query.filter(Solicitud.estado == estado)

    solicitudes = query.order_by(Solicitud.creado_en.desc()).all()
    return [formatear_solicitud_out(s) for s in solicitudes]
