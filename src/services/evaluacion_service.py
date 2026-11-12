from datetime import datetime, timezone
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from src.models import (
    Usuario, RolUsuario,
    Recurso, CondicionRecurso,
    Solicitud, SolicitudRecurso, EstadoSolicitud,
    Prestamo, EstadoPrestamo,
    AuditoriaEvento
)
from src.schemas.solicitud import SolicitudOut, SolicitudBandejaResponsableOut
from src.services.solicitud_service import formatear_solicitud_out
from src.services.recurso_service import asegurar_utc, hay_colision_fechas


def verificar_bloqueo_fifo(db: Session, solicitud: Solicitud) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Evalúa la regla de atención estricta por orden de llegada (RN-05):
    Verifica si existe alguna solicitud anterior (menor creado_en, o menor id en caso de empate)
    que continúe en estado pendiente ('pendiente_docente' o 'pendiente_responsable')
    y compita por alguno de los mismos recursos en un rango de fechas superpuesto.
    """
    recurso_ids = [asoc.recurso_id for asoc in solicitud.recursos_asociados]
    if not recurso_ids:
        return False, None, None

    inicio_sol = asegurar_utc(solicitud.fecha_inicio)
    fin_sol = asegurar_utc(solicitud.fecha_fin)

    # Buscar solicitudes creadas estrictamente antes que la actual
    solicitudes_anteriores = (
        db.query(Solicitud)
        .filter(
            Solicitud.id != solicitud.id,
            Solicitud.estado.in_([EstadoSolicitud.PENDIENTE_DOCENTE, EstadoSolicitud.PENDIENTE_RESPONSABLE]),
            (Solicitud.creado_en < solicitud.creado_en) | 
            ((Solicitud.creado_en == solicitud.creado_en) & (Solicitud.id < solicitud.id))
        )
        .order_by(Solicitud.creado_en.asc(), Solicitud.id.asc())
        .all()
    )

    for previa in solicitudes_anteriores:
        # Verificar si comparten recursos
        prev_recurso_ids = [asoc.recurso_id for asoc in previa.recursos_asociados]
        recursos_comunes = set(recurso_ids).intersection(set(prev_recurso_ids))
        if recursos_comunes:
            # Verificar colisión de fechas
            inicio_prev = asegurar_utc(previa.fecha_inicio)
            fin_prev = asegurar_utc(previa.fecha_fin)
            if hay_colision_fechas(inicio_sol, fin_sol, inicio_prev, fin_prev):
                motivo = (
                    f"Existe una solicitud anterior (#{previa.id}) en estado '{previa.estado.value}' "
                    f"radicada el {previa.creado_en.strftime('%Y-%m-%d %H:%M')} que compite por los mismos recursos."
                )
                return True, previa.id, motivo

    return False, None, None


def verificar_conflicto_reserva_existente(db: Session, solicitud: Solicitud) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Verifica si existe alguna solicitud ya formalmente APROBADA que comparta recursos
    y fechas con la solicitud evaluada.
    """
    recurso_ids = [asoc.recurso_id for asoc in solicitud.recursos_asociados]
    inicio_sol = asegurar_utc(solicitud.fecha_inicio)
    fin_sol = asegurar_utc(solicitud.fecha_fin)

    reservas_existentes = (
        db.query(Solicitud)
        .join(SolicitudRecurso, SolicitudRecurso.solicitud_id == Solicitud.id)
        .filter(
            Solicitud.id != solicitud.id,
            Solicitud.estado == EstadoSolicitud.APROBADA,
            SolicitudRecurso.recurso_id.in_(recurso_ids),
            Solicitud.fecha_inicio < fin_sol,
            Solicitud.fecha_fin > inicio_sol
        )
        .first()
    )

    if reservas_existentes:
        motivo = f"El recurso ya cuenta con reserva firme aprobada en la Solicitud #{reservas_existentes.id}."
        return True, reservas_existentes.id, motivo

    return False, None, None


def evaluar_docente(
    db: Session,
    solicitud_id: int,
    docente: Usuario,
    aprobado: bool,
    motivo_rechazo: Optional[str] = None
) -> SolicitudOut:
    """
    Emite el Visto Bueno (o rechazo) de un docente a una solicitud de estudiante (RN-02).
    """
    if docente.rol != RolUsuario.DOCENTE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un usuario con rol docente puede emitir vistos buenos a solicitudes estudiantiles."
        )

    solicitud = db.query(Solicitud).filter(Solicitud.id == solicitud_id).first()
    if not solicitud:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud no encontrada.")

    if solicitud.estado != EstadoSolicitud.PENDIENTE_DOCENTE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La solicitud #{solicitud_id} no está en espera de visto bueno docente (Estado actual: '{solicitud.estado.value}')."
        )

    ahora_utc = datetime.now(timezone.utc)

    if not aprobado:
        if not motivo_rechazo or len(motivo_rechazo.strip()) < 5:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El rechazo docente exige un motivo claro y fundamentado (mínimo 5 caracteres)."
            )
        with db.begin_nested():
            solicitud.estado = EstadoSolicitud.RECHAZADA
            solicitud.motivo_rechazo = motivo_rechazo.strip()
            solicitud.docente_evaluo_id = docente.id
            solicitud.fecha_evaluacion_docente = ahora_utc

            auditoria = AuditoriaEvento(
                usuario_id=docente.id,
                accion="RECHAZO_DOCENTE",
                entidad="solicitud",
                entidad_id=solicitud.id,
                detalles=f"Docente {docente.nombre_completo} rechazó la solicitud. Motivo: {motivo_rechazo.strip()}"
            )
            db.add(auditoria)
    else:
        with db.begin_nested():
            solicitud.estado = EstadoSolicitud.PENDIENTE_RESPONSABLE
            solicitud.docente_evaluo_id = docente.id
            solicitud.fecha_evaluacion_docente = ahora_utc

            auditoria = AuditoriaEvento(
                usuario_id=docente.id,
                accion="VISTO_BUENO_DOCENTE",
                entidad="solicitud",
                entidad_id=solicitud.id,
                detalles=f"Docente {docente.nombre_completo} otorgó visto bueno académico. Avanza a revisión de responsable."
            )
            db.add(auditoria)

    db.commit()
    db.refresh(solicitud)
    return formatear_solicitud_out(solicitud)


def evaluar_responsable(
    db: Session,
    solicitud_id: int,
    responsable: Usuario,
    aprobado: bool,
    motivo_rechazo: Optional[str] = None
) -> SolicitudOut:
    """
    Evaluación definitiva por el Responsable de Laboratorio (RN-04 y RN-05).
    Aplica bloqueo pesimista en orden determinista de IDs (SELECT ... FOR UPDATE)
    y verifica orden FIFO antes de consolidar la reserva firme.
    """
    if responsable.rol != RolUsuario.RESPONSABLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el personal responsable de laboratorio puede aprobar o rechazar definitivamente solicitudes."
        )

    solicitud = db.query(Solicitud).filter(Solicitud.id == solicitud_id).first()
    if not solicitud:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud no encontrada.")

    if solicitud.estado != EstadoSolicitud.PENDIENTE_RESPONSABLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La solicitud #{solicitud_id} no está en estado 'pendiente_responsable' (Estado actual: '{solicitud.estado.value}')."
        )

    ahora_utc = datetime.now(timezone.utc)

    # 1. Caso de Rechazo
    if not aprobado:
        if not motivo_rechazo or len(motivo_rechazo.strip()) < 5:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El rechazo del responsable exige un motivo obligatorio y fundamentado (mínimo 5 caracteres)."
            )
        with db.begin_nested():
            solicitud.estado = EstadoSolicitud.RECHAZADA
            solicitud.motivo_rechazo = motivo_rechazo.strip()
            solicitud.responsable_evaluo_id = responsable.id
            solicitud.fecha_evaluacion_responsable = ahora_utc

            auditoria = AuditoriaEvento(
                usuario_id=responsable.id,
                accion="RECHAZO_RESPONSABLE",
                entidad="solicitud",
                entidad_id=solicitud.id,
                detalles=f"Responsable {responsable.nombre_completo} rechazó la solicitud. Motivo: {motivo_rechazo.strip()}"
            )
            db.add(auditoria)

        db.commit()
        db.refresh(solicitud)
        return formatear_solicitud_out(solicitud)

    # 2. Caso de Aprobación (Consolidación de Reserva Firme)
    # Extraer IDs de recursos ordenados de forma ascendente para evitar deadlocks
    recurso_ids = sorted([asoc.recurso_id for asoc in solicitud.recursos_asociados])
    if not recurso_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La solicitud no tiene recursos asociados para aprobar."
        )

    with db.begin_nested():
        # A. Bloqueo pesimista en orden determinista de IDs
        recursos_bloqueados = (
            db.query(Recurso)
            .filter(Recurso.id.in_(recurso_ids))
            .order_by(Recurso.id.asc())
            .with_for_update()
            .all()
        )

        # B. Validar condición física de cada unidad
        for r in recursos_bloqueados:
            if r.condicion != CondicionRecurso.HABILITADO:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"No se puede aprobar: el recurso '{r.nombre}' ({r.codigo}) se encuentra en condición '{r.condicion.value}'."
                )

        # C. Validar orden de atención FIFO estricto (RN-05)
        bloqueada_fifo, sol_previa_id, motivo_fifo = verificar_bloqueo_fifo(db, solicitud)
        if bloqueada_fifo:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Bloqueo por orden de llegada (FIFO): {motivo_fifo}"
            )

        # D. Validar ausencia de colisiones con reservas aprobadas previamente
        conflicto_reserva, sol_aprob_id, motivo_conf = verificar_conflicto_reserva_existente(db, solicitud)
        if conflicto_reserva:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflicto de reserva concurrente: {motivo_conf}"
            )

        # E. Consolidar aprobación y reserva firme
        solicitud.estado = EstadoSolicitud.APROBADA
        solicitud.responsable_evaluo_id = responsable.id
        solicitud.fecha_evaluacion_responsable = ahora_utc

        auditoria = AuditoriaEvento(
            usuario_id=responsable.id,
            accion="APROBACION_RESPONSABLE",
            entidad="solicitud",
            entidad_id=solicitud.id,
            detalles=f"Responsable {responsable.nombre_completo} aprobó la solicitud. Reserva firme creada para {len(recurso_ids)} recursos."
        )
        db.add(auditoria)

    db.commit()
    db.refresh(solicitud)
    return formatear_solicitud_out(solicitud)


def listar_bandeja_docente(db: Session, docente: Usuario) -> List[SolicitudOut]:
    """Lista las solicitudes de estudiantes pendientes de visto bueno docente."""
    solicitudes = (
        db.query(Solicitud)
        .filter(Solicitud.estado == EstadoSolicitud.PENDIENTE_DOCENTE)
        .order_by(Solicitud.creado_en.asc())
        .all()
    )
    return [formatear_solicitud_out(s) for s in solicitudes]


def listar_bandeja_responsable(db: Session, responsable: Usuario) -> List[SolicitudBandejaResponsableOut]:
    """
    Lista las solicitudes pendientes de aprobación del responsable,
    acompañadas del diagnóstico de colisión y prioridad FIFO en tiempo real.
    """
    solicitudes = (
        db.query(Solicitud)
        .filter(Solicitud.estado == EstadoSolicitud.PENDIENTE_RESPONSABLE)
        .order_by(Solicitud.creado_en.asc(), Solicitud.id.asc())
        .all()
    )

    resultado: List[SolicitudBandejaResponsableOut] = []
    for s in solicitudes:
        bloqueada_fifo, previa_id, motivo_fifo = verificar_bloqueo_fifo(db, s)
        conflicto_res, aprob_id, motivo_conf = verificar_conflicto_reserva_existente(db, s)

        s_out = formatear_solicitud_out(s)
        item = SolicitudBandejaResponsableOut(
            **s_out.model_dump(),
            bloqueada_por_fifo=bloqueada_fifo,
            solicitud_bloqueante_id=previa_id,
            motivo_bloqueo_fifo=motivo_fifo,
            conflicto_reserva_existente=conflicto_res,
            motivo_conflicto_reserva=motivo_conf
        )
        resultado.append(item)

    return resultado

