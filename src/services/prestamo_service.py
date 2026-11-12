from datetime import datetime, timezone
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from src.models import (
    Usuario, RolUsuario,
    Recurso, CondicionRecurso,
    Solicitud, EstadoSolicitud, SolicitudRecurso,
    Prestamo, EstadoPrestamo,
    Novedad, TipoNovedad,
    AuditoriaEvento
)
from src.models.base import get_utc_now
from src.schemas.prestamo import (
    PrestamoEntregaRequest,
    PrestamoDevolucionRequest,
    PrestamoOut,
    RecursoPrestamoSimple
)
from src.schemas.novedad import (
    NovedadOut,
    ResolverNovedadRequest
)


def calcular_si_prestamo_vencido(prestamo: Prestamo, ahora: Optional[datetime] = None) -> bool:
    """
    RN-06 [B]: Calcula dinámicamente si un préstamo está vencido.
    Un préstamo está vencido si su estado es 'en_curso', aún no ha sido devuelto
    (fecha_devolucion_real es NULL) y la hora actual supera la fecha fin pactada.
    """
    if prestamo.estado != EstadoPrestamo.EN_CURSO or prestamo.fecha_devolucion_real is not None:
        return False
    
    if ahora is None:
        ahora = get_utc_now()
    
    fecha_fin = prestamo.solicitud.fecha_fin
    if fecha_fin.tzinfo is None:
        fecha_fin = fecha_fin.replace(tzinfo=timezone.utc)
    if ahora.tzinfo is None:
        ahora = ahora.replace(tzinfo=timezone.utc)
        
    return ahora > fecha_fin


def verificar_inhabilitacion_o_vencimiento_usuario(
    db: Session,
    usuario_id: int
) -> Tuple[bool, Optional[str]]:
    """
    Verifica si un usuario puede recibir una entrega de préstamo:
    1. RN-06 [B]: Si tiene algún préstamo actualmente vencido.
    2. RN-07 [B]: Si tiene novedades abiertas por daño o faltante.
    Retorna (puede_recibir, motivo_bloqueo).
    """
    ahora = get_utc_now()

    # 1. Verificar préstamos vencidos
    prestamos_activos = (
        db.query(Prestamo)
        .join(Solicitud, Prestamo.solicitud_id == Solicitud.id)
        .filter(
            Solicitud.solicitante_id == usuario_id,
            Prestamo.estado == EstadoPrestamo.EN_CURSO,
            Prestamo.fecha_devolucion_real.is_(None)
        )
        .all()
    )

    for p in prestamos_activos:
        if calcular_si_prestamo_vencido(p, ahora):
            return False, (
                f"El solicitante tiene el préstamo #{p.id} vencido (fecha límite: {p.solicitud.fecha_fin.strftime('%Y-%m-%d %H:%M')}). "
                "Según la regla institucional del profesor [RN-06], debe devolver todo recurso adeudado antes de recibir otro."
            )

    # 2. Verificar novedades abiertas (sanción por daño/faltante)
    novedad_pendiente = (
        db.query(Novedad)
        .filter(
            Novedad.usuario_inhabilitado_id == usuario_id,
            Novedad.resuelta == False,
            Novedad.tipo.in_([TipoNovedad.DANO, TipoNovedad.FALTANTE])
        )
        .first()
    )

    if novedad_pendiente:
        return False, (
            f"El solicitante está inhabilitado por la novedad pendiente #{novedad_pendiente.id} "
            f"(tipo: {novedad_pendiente.tipo.value}, detalle: '{novedad_pendiente.descripcion}'). "
            "Debe solucionarse la novedad con el responsable antes de recibir nuevos préstamos [RN-07]."
        )

    return True, None


def formatear_prestamo_out(prestamo: Prestamo, ahora: Optional[datetime] = None) -> PrestamoOut:
    """Convierte un modelo Prestamo a su esquema Pydantic de salida enriquecido."""
    es_venc = calcular_si_prestamo_vencido(prestamo, ahora)
    solicitud = prestamo.solicitud
    solicitante = solicitud.solicitante
    
    recursos_out = [
        RecursoPrestamoSimple(
            id=asoc.recurso.id,
            codigo=asoc.recurso.codigo,
            nombre=asoc.recurso.nombre,
            categoria=asoc.recurso.categoria.value,
            condicion=asoc.recurso.condicion.value
        )
        for asoc in solicitud.recursos_asociados
    ]

    return PrestamoOut(
        id=prestamo.id,
        solicitud_id=solicitud.id,
        solicitante_id=solicitante.id,
        solicitante_nombre=solicitante.nombre_completo,
        solicitante_email=solicitante.email,
        solicitante_documento=solicitante.documento,
        responsable_entrega_nombre=prestamo.responsable_entrega.nombre_completo if prestamo.responsable_entrega else "Desconocido",
        fecha_entrega_real=prestamo.fecha_entrega_real,
        observaciones_entrega=prestamo.observaciones_entrega,
        responsable_recepcion_nombre=prestamo.responsable_recepcion.nombre_completo if prestamo.responsable_recepcion else None,
        fecha_devolucion_real=prestamo.fecha_devolucion_real,
        observaciones_devolucion=prestamo.observaciones_devolucion,
        estado=prestamo.estado,
        fecha_inicio_prevista=solicitud.fecha_inicio,
        fecha_fin_prevista=solicitud.fecha_fin,
        es_vencido=es_venc,
        recursos=recursos_out
    )


def registrar_entrega_prestamo(
    db: Session,
    responsable: Usuario,
    datos: PrestamoEntregaRequest
) -> PrestamoOut:
    """
    CA-04 / RF-07: Registra la entrega física de los recursos de una solicitud aprobada.
    Valida:
    - Estado de solicitud = APROBADA
    - No entrega duplicada
    - Verificación estricta de préstamos vencidos e inhabilitaciones del usuario (RN-06, RN-07)
    - Condición de recursos operativos (todos HABILITADOS)
    """
    ahora = get_utc_now()

    solicitud = (
        db.query(Solicitud)
        .options(
            joinedload(Solicitud.solicitante),
            joinedload(Solicitud.recursos_asociados).joinedload(SolicitudRecurso.recurso),
            joinedload(Solicitud.prestamo)
        )
        .filter(Solicitud.id == datos.solicitud_id)
        .first()
    )

    if not solicitud:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró la solicitud con ID {datos.solicitud_id}."
        )

    if solicitud.estado != EstadoSolicitud.APROBADA:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"La solicitud #{solicitud.id} no puede ser entregada porque su estado actual es '{solicitud.estado.value}'. Solo se entregan solicitudes 'aprobada'."
        )

    if solicitud.prestamo is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"La solicitud #{solicitud.id} ya cuenta con un préstamo registrado (#{solicitud.prestamo.id})."
        )

    # Validar que no haya pasado ya la fecha fin del período pactado
    fecha_fin = solicitud.fecha_fin
    if fecha_fin.tzinfo is None:
        fecha_fin = fecha_fin.replace(tzinfo=timezone.utc)
    if ahora > fecha_fin:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"La fecha límite del préstamo pactado ya venció ({fecha_fin.strftime('%Y-%m-%d %H:%M')}). No es posible entregar una solicitud cuyo período ha expirado."
        )

    # Validar que el usuario no tenga vencidos ni novedades abiertas
    puede_recibir, motivo = verificar_inhabilitacion_o_vencimiento_usuario(db, solicitud.solicitante_id)
    if not puede_recibir:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=motivo
        )

    # Validar condición física de los recursos
    for asoc in solicitud.recursos_asociados:
        recurso = asoc.recurso
        if recurso.condicion != CondicionRecurso.HABILITADO:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El recurso [{recurso.codigo}] '{recurso.nombre}' se encuentra en condición '{recurso.condicion.value}' y no puede ser entregado."
            )

    # Crear el préstamo formal
    nuevo_prestamo = Prestamo(
        solicitud_id=solicitud.id,
        responsable_entrega_id=responsable.id,
        fecha_entrega_real=ahora,
        observaciones_entrega=datos.observaciones,
        estado=EstadoPrestamo.EN_CURSO
    )
    db.add(nuevo_prestamo)

    # Registrar auditoría
    auditoria = AuditoriaEvento(
        usuario_id=responsable.id,
        accion="ENTREGA_PRESTAMO",
        entidad="prestamos",
        entidad_id=solicitud.id,
        detalles=(
            f"Entrega física registrada por {responsable.nombre_completo} para el solicitante "
            f"{solicitud.solicitante.nombre_completo}. Recursos: {[i.recurso.codigo for i in solicitud.recursos_asociados]}"
        )
    )
    db.add(auditoria)

    db.commit()
    db.refresh(nuevo_prestamo)

    return formatear_prestamo_out(nuevo_prestamo, ahora)


def registrar_devolucion_prestamo(
    db: Session,
    responsable: Usuario,
    prestamo_id: int,
    datos: PrestamoDevolucionRequest
) -> PrestamoOut:
    """
    CA-05 / RF-08: Registra la recepción física de los equipos.
    - Pasa préstamo a DEVUELTO.
    - Si se reportan daños o faltantes en algún recurso:
      - Crea Novedad vinculada (RN-07).
      - El recurso pasa a condición NO_DISPONIBLE.
      - El usuario queda inhabilitado hasta que se resuelva la novedad.
    """
    ahora = get_utc_now()

    prestamo = (
        db.query(Prestamo)
        .options(
            joinedload(Prestamo.solicitud).joinedload(Solicitud.solicitante),
            joinedload(Prestamo.solicitud).joinedload(Solicitud.recursos_asociados).joinedload(SolicitudRecurso.recurso),
            joinedload(Prestamo.responsable_entrega)
        )
        .filter(Prestamo.id == prestamo_id)
        .first()
    )

    if not prestamo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el préstamo con ID {prestamo_id}."
        )

    if prestamo.estado != EstadoPrestamo.EN_CURSO:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"El préstamo #{prestamo.id} ya se encuentra en estado '{prestamo.estado.value}'."
        )

    prestamo.responsable_recepcion_id = responsable.id
    prestamo.fecha_devolucion_real = ahora
    prestamo.observaciones_devolucion = datos.observaciones
    prestamo.estado = EstadoPrestamo.DEVUELTO

    solicitud = prestamo.solicitud

    # Procesar reporte individual por ítem (si se especificó en el request)
    recursos_con_novedad = []
    if datos.items:
        items_map = {item.recurso_id: item for item in datos.items}
        for asoc in solicitud.recursos_asociados:
            rec = asoc.recurso
            if rec.id in items_map:
                eval_item = items_map[rec.id]
                if eval_item.estado_fisico in ["dano", "faltante"]:
                    tipo_nov = TipoNovedad.DANO if eval_item.estado_fisico == "dano" else TipoNovedad.FALTANTE
                    desc = eval_item.descripcion_novedad or f"Reporte de {tipo_nov.value} al devolver el préstamo #{prestamo.id}."
                    
                    # 1. Crear Novedad
                    nueva_nov = Novedad(
                        prestamo_id=prestamo.id,
                        recurso_id=rec.id,
                        usuario_inhabilitado_id=solicitud.solicitante_id,
                        tipo=tipo_nov,
                        descripcion=desc,
                        resuelta=False
                    )
                    db.add(nueva_nov)
                    
                    # 2. Marcar recurso como NO_DISPONIBLE
                    rec.condicion = CondicionRecurso.NO_DISPONIBLE
                    recursos_con_novedad.append(f"{rec.codigo} ({tipo_nov.value})")

    # Registrar Auditoría
    detalle_auditoria = (
        f"Devolución recibida por {responsable.nombre_completo} para el préstamo #{prestamo.id} "
        f"del usuario {solicitud.solicitante.nombre_completo}."
    )
    if recursos_con_novedad:
        detalle_auditoria += f" Novedades generadas en: {', '.join(recursos_con_novedad)}. Usuario inhabilitado [RN-07]."

    auditoria = AuditoriaEvento(
        usuario_id=responsable.id,
        accion="DEVOLUCION_PRESTAMO",
        entidad="prestamos",
        entidad_id=prestamo.id,
        detalles=detalle_auditoria
    )
    db.add(auditoria)

    db.commit()
    db.refresh(prestamo)

    return formatear_prestamo_out(prestamo, ahora)


def listar_prestamos_servicio(
    db: Session,
    solo_activos: bool = False,
    solo_vencidos: bool = False,
    usuario_id: Optional[int] = None
) -> List[PrestamoOut]:
    """Lista préstamos con filtros operativos para Responsable y Coordinación."""
    query = (
        db.query(Prestamo)
        .options(
            joinedload(Prestamo.solicitud).joinedload(Solicitud.solicitante),
            joinedload(Prestamo.solicitud).joinedload(Solicitud.recursos_asociados).joinedload(SolicitudRecurso.recurso),
            joinedload(Prestamo.responsable_entrega),
            joinedload(Prestamo.responsable_recepcion)
        )
        .order_by(Prestamo.fecha_entrega_real.desc())
    )

    if usuario_id is not None:
        query = query.join(Solicitud, Prestamo.solicitud_id == Solicitud.id).filter(Solicitud.solicitante_id == usuario_id)

    if solo_activos:
        query = query.filter(Prestamo.estado == EstadoPrestamo.EN_CURSO)

    prestamos = query.all()
    ahora = get_utc_now()

    resultados = []
    for p in prestamos:
        es_venc = calcular_si_prestamo_vencido(p, ahora)
        if solo_vencidos and not es_venc:
            continue
        resultados.append(formatear_prestamo_out(p, ahora))

    return resultados


def listar_solicitudes_listas_para_entrega(db: Session) -> List[Solicitud]:
    """Retorna las solicitudes aprobadas pendientes de ser entregadas físicamente (sin préstamo aún)."""
    return (
        db.query(Solicitud)
        .outerjoin(Prestamo, Solicitud.id == Prestamo.solicitud_id)
        .options(
            joinedload(Solicitud.solicitante),
            joinedload(Solicitud.recursos_asociados).joinedload(SolicitudRecurso.recurso)
        )
        .filter(
            Solicitud.estado == EstadoSolicitud.APROBADA,
            Prestamo.id.is_(None)
        )
        .order_by(Solicitud.fecha_inicio.asc())
        .all()
    )


def listar_novedades_servicio(
    db: Session,
    solo_abiertas: bool = False
) -> List[NovedadOut]:
    """Lista novedades registradas con información detallada del solicitante y recurso."""
    query = (
        db.query(Novedad)
        .options(
            joinedload(Novedad.recurso),
            joinedload(Novedad.usuario_inhabilitado),
            joinedload(Novedad.responsable_resolucion)
        )
        .order_by(Novedad.creado_en.desc())
    )

    if solo_abiertas:
        query = query.filter(Novedad.resuelta == False)

    novedades = query.all()
    out = []
    for n in novedades:
        out.append(
            NovedadOut(
                id=n.id,
                prestamo_id=n.prestamo_id,
                recurso_id=n.recurso_id,
                recurso_codigo=n.recurso.codigo,
                recurso_nombre=n.recurso.nombre,
                usuario_inhabilitado_id=n.usuario_inhabilitado_id,
                usuario_nombre=n.usuario_inhabilitado.nombre_completo,
                usuario_email=n.usuario_inhabilitado.email,
                usuario_documento=n.usuario_inhabilitado.documento,
                tipo=n.tipo,
                descripcion=n.descripcion,
                resuelta=n.resuelta,
                fecha_resolucion=n.fecha_resolucion,
                responsable_resolucion_nombre=n.responsable_resolucion.nombre_completo if n.responsable_resolucion else None,
                observaciones_resolucion=n.observaciones_resolucion,
                creado_en=n.creado_en
            )
        )
    return out


def resolver_novedad_servicio(
    db: Session,
    responsable: Usuario,
    novedad_id: int,
    datos: ResolverNovedadRequest
) -> NovedadOut:
    """
    RN-08 [C]: Resuelve una novedad abierta.
    - Registra el responsable que resuelve y el acuerdo/observación.
    - Si 'rehabilitar_recurso' es True, el recurso vuelve a HABILITADO.
    - El usuario se considera rehabilitado si ya no tiene otras novedades abiertas ni vencidos.
    """
    ahora = get_utc_now()

    novedad = (
        db.query(Novedad)
        .options(
            joinedload(Novedad.recurso),
            joinedload(Novedad.usuario_inhabilitado)
        )
        .filter(Novedad.id == novedad_id)
        .first()
    )

    if not novedad:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró la novedad con ID {novedad_id}."
        )

    if novedad.resuelta:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"La novedad #{novedad.id} ya se encuentra resuelta."
        )

    novedad.resuelta = True
    novedad.fecha_resolucion = ahora
    novedad.responsable_resolucion_id = responsable.id
    novedad.observaciones_resolucion = datos.observaciones_resolucion

    if datos.rehabilitar_recurso:
        novedad.recurso.condicion = CondicionRecurso.HABILITADO

    auditoria = AuditoriaEvento(
        usuario_id=responsable.id,
        accion="RESOLUCION_NOVEDAD",
        entidad="novedades",
        entidad_id=novedad.id,
        detalles=(
            f"Novedad #{novedad.id} resuelta por {responsable.nombre_completo}. "
            f"Recurso {novedad.recurso.codigo} rehabilitado: {datos.rehabilitar_recurso}. "
            f"Observaciones: {datos.observaciones_resolucion}"
        )
    )
    db.add(auditoria)

    db.commit()
    db.refresh(novedad)

    return NovedadOut(
        id=novedad.id,
        prestamo_id=novedad.prestamo_id,
        recurso_id=novedad.recurso_id,
        recurso_codigo=novedad.recurso.codigo,
        recurso_nombre=novedad.recurso.nombre,
        usuario_inhabilitado_id=novedad.usuario_inhabilitado_id,
        usuario_nombre=novedad.usuario_inhabilitado.nombre_completo,
        usuario_email=novedad.usuario_inhabilitado.email,
        usuario_documento=novedad.usuario_inhabilitado.documento,
        tipo=novedad.tipo,
        descripcion=novedad.descripcion,
        resuelta=novedad.resuelta,
        fecha_resolucion=novedad.fecha_resolucion,
        responsable_resolucion_nombre=responsable.nombre_completo,
        observaciones_resolucion=novedad.observaciones_resolucion,
        creado_en=novedad.creado_en
    )
