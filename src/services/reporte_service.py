from datetime import datetime, time, timedelta, timezone
from typing import Dict, List, Optional
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from src.models import (
    Usuario,
    Recurso, CondicionRecurso,
    Solicitud, SolicitudRecurso,
    Prestamo, EstadoPrestamo,
    Novedad,
    AuditoriaEvento
)
from src.models.base import get_utc_now
from src.schemas.reporte import (
    EstadoFiltroPrestamo,
    ConsolidadoFiltros,
    RecursoRankingOut,
    RecursoNovedadAbiertaOut,
    MetricasOut,
    UsuarioRefOut,
    RecursoConsolidadoOut,
    NovedadConsolidadoOut,
    TrazabilidadPrestamoOut,
    PrestamoConsolidadoOut,
    ConsolidadoOut,
    AccionConteoOut,
    AuditoriaEventoOut,
    TrazabilidadResumenOut
)
# Se reutilizan (sin modificar) la regla de mora de la Etapa 4 y la zona horaria del proyecto
from src.services.prestamo_service import calcular_si_prestamo_vencido
from src.services.recurso_service import BOGOTA_TZ



# Utilidades internas


def _a_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normaliza a UTC. Un datetime naive (SQLite) se interpreta como UTC, igual que en la Etapa 4."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _horas(delta: timedelta) -> float:
    return round(delta.total_seconds() / 3600, 2)


def _patron_like(texto: str) -> str:
    """Escapa comodines de LIKE para que el texto buscado se trate literalmente."""
    limpio = texto.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{limpio}%"


def _usuario_ref(u: Optional[Usuario]) -> Optional[UsuarioRefOut]:
    if u is None:
        return None
    return UsuarioRefOut(
        id=u.id,
        nombre_completo=u.nombre_completo,
        email=u.email,
        documento=u.documento,
        rol=u.rol.value
    )


def _condiciones_vencido(ahora: datetime) -> list:
    """
    RN-06: préstamo vencido = en_curso, sin devolución real y ahora > fecha_fin pactada.
    Misma regla que calcular_si_prestamo_vencido, expresada en SQL para poder contar y filtrar.
    """
    return [
        Prestamo.estado == EstadoPrestamo.EN_CURSO,
        Prestamo.fecha_devolucion_real.is_(None),
        Prestamo.solicitud.has(Solicitud.fecha_fin < ahora)
    ]



# Métricas / KPIs


def obtener_metricas(db: Session, top: int = 5) -> MetricasOut:
    """Calcula en tiempo real los KPIs institucionales para Coordinación (CA-06 / RF-12)."""
    ahora = get_utc_now()

    # --- Préstamos ---
    total_prestamos = db.query(func.count(Prestamo.id)).scalar() or 0
    prestamos_activos = (
        db.query(func.count(Prestamo.id))
        .filter(Prestamo.estado == EstadoPrestamo.EN_CURSO)
        .scalar() or 0
    )
    prestamos_devueltos = (
        db.query(func.count(Prestamo.id))
        .filter(Prestamo.estado == EstadoPrestamo.DEVUELTO)
        .scalar() or 0
    )
    prestamos_vencidos = (
        db.query(func.count(Prestamo.id))
        .filter(*_condiciones_vencido(ahora))
        .scalar() or 0
    )
    devueltos_a_tiempo = (
        db.query(func.count(Prestamo.id))
        .select_from(Prestamo)
        .join(Solicitud, Prestamo.solicitud_id == Solicitud.id)
        .filter(
            Prestamo.estado == EstadoPrestamo.DEVUELTO,
            Prestamo.fecha_devolucion_real.isnot(None),
            Prestamo.fecha_devolucion_real <= Solicitud.fecha_fin
        )
        .scalar() or 0
    )
    tasa_cumplimiento = (
        round(devueltos_a_tiempo * 100.0 / prestamos_devueltos, 1)
        if prestamos_devueltos > 0 else None
    )

    # --- Recursos y novedades ---
    recursos_totales = db.query(func.count(Recurso.id)).scalar() or 0
    recursos_no_disponibles = (
        db.query(func.count(Recurso.id))
        .filter(Recurso.condicion == CondicionRecurso.NO_DISPONIBLE)
        .scalar() or 0
    )
    novedades_abiertas = (
        db.query(func.count(Novedad.id))
        .filter(Novedad.resuelta.is_(False))
        .scalar() or 0
    )
    recursos_con_novedad_abierta = (
        db.query(func.count(func.distinct(Novedad.recurso_id)))
        .filter(Novedad.resuelta.is_(False))
        .scalar() or 0
    )

    return MetricasOut(
        total_prestamos=total_prestamos,
        prestamos_activos=prestamos_activos,
        prestamos_vencidos=prestamos_vencidos,
        prestamos_devueltos=prestamos_devueltos,
        devueltos_a_tiempo=devueltos_a_tiempo,
        devueltos_con_retraso=prestamos_devueltos - devueltos_a_tiempo,
        tasa_cumplimiento=tasa_cumplimiento,
        recursos_totales=recursos_totales,
        recursos_no_disponibles=recursos_no_disponibles,
        recursos_con_novedad_abierta=recursos_con_novedad_abierta,
        novedades_abiertas=novedades_abiertas,
        recursos_mas_prestados=_ranking_recursos_mas_prestados(db, top),
        recursos_con_novedades_abiertas=_recursos_con_novedades_abiertas(db),
        generado_en=ahora
    )


def _ranking_recursos_mas_prestados(db: Session, top: int) -> List[RecursoRankingOut]:
    total = func.count(Prestamo.id)
    filas = (
        db.query(Recurso.id, Recurso.codigo, Recurso.nombre, Recurso.categoria, total.label("total"))
        .select_from(Recurso)
        .join(SolicitudRecurso, SolicitudRecurso.recurso_id == Recurso.id)
        .join(Solicitud, Solicitud.id == SolicitudRecurso.solicitud_id)
        .join(Prestamo, Prestamo.solicitud_id == Solicitud.id)
        .group_by(Recurso.id, Recurso.codigo, Recurso.nombre, Recurso.categoria)
        .order_by(total.desc(), Recurso.codigo.asc())
        .limit(top)
        .all()
    )
    return [
        RecursoRankingOut(
            recurso_id=f[0], codigo=f[1], nombre=f[2], categoria=f[3], total_prestamos=f[4]
        )
        for f in filas
    ]


def _recursos_con_novedades_abiertas(db: Session) -> List[RecursoNovedadAbiertaOut]:
    abiertas = (
        db.query(Novedad)
        .options(joinedload(Novedad.recurso))
        .filter(Novedad.resuelta.is_(False))
        .order_by(Novedad.creado_en.desc())
        .all()
    )
    agrupadas: Dict[int, RecursoNovedadAbiertaOut] = {}
    for n in abiertas:
        r = n.recurso
        if r.id not in agrupadas:
            agrupadas[r.id] = RecursoNovedadAbiertaOut(
                recurso_id=r.id,
                codigo=r.codigo,
                nombre=r.nombre,
                condicion=r.condicion,
                novedades_abiertas=0,
                tipos=[]
            )
        item = agrupadas[r.id]
        item.novedades_abiertas += 1
        if n.tipo not in item.tipos:
            item.tipos.append(n.tipo)

    return sorted(agrupadas.values(), key=lambda x: (-x.novedades_abiertas, x.codigo))



# Consulta consolidada


def _construir_condiciones(filtros: ConsolidadoFiltros, ahora: datetime) -> list:
    conds: list = []

    # Rango de fechas sobre la entrega real. Los días se interpretan en hora de Bogotá
    # y se convierten a UTC (así se almacenan las fechas).
    if filtros.fecha_desde:
        inicio = datetime.combine(filtros.fecha_desde, time.min, tzinfo=BOGOTA_TZ).astimezone(timezone.utc)
        conds.append(Prestamo.fecha_entrega_real >= inicio)
    if filtros.fecha_hasta:
        limite = datetime.combine(
            filtros.fecha_hasta + timedelta(days=1), time.min, tzinfo=BOGOTA_TZ
        ).astimezone(timezone.utc)
        conds.append(Prestamo.fecha_entrega_real < limite)

    if filtros.estado == EstadoFiltroPrestamo.EN_CURSO:
        conds.append(Prestamo.estado == EstadoPrestamo.EN_CURSO)
    elif filtros.estado == EstadoFiltroPrestamo.DEVUELTO:
        conds.append(Prestamo.estado == EstadoPrestamo.DEVUELTO)
    elif filtros.estado == EstadoFiltroPrestamo.VENCIDO:
        conds.extend(_condiciones_vencido(ahora))

    if filtros.solicitante_id is not None:
        conds.append(Prestamo.solicitud.has(Solicitud.solicitante_id == filtros.solicitante_id))

    if filtros.solicitante and filtros.solicitante.strip():
        patron = _patron_like(filtros.solicitante)
        conds.append(
            Prestamo.solicitud.has(
                Solicitud.solicitante.has(
                    or_(
                        Usuario.nombre_completo.ilike(patron, escape="\\"),
                        Usuario.email.ilike(patron, escape="\\"),
                        Usuario.documento.ilike(patron, escape="\\")
                    )
                )
            )
        )

    if filtros.categoria is not None:
        conds.append(
            Prestamo.solicitud.has(
                Solicitud.recursos_asociados.any(
                    SolicitudRecurso.recurso.has(Recurso.categoria == filtros.categoria)
                )
            )
        )

    return conds


def _formatear_item(p: Prestamo, ahora: datetime) -> PrestamoConsolidadoOut:
    sol = p.solicitud
    fecha_fin = _a_utc(sol.fecha_fin)
    fecha_dev = _a_utc(p.fecha_devolucion_real)
    es_vencido = calcular_si_prestamo_vencido(p, ahora)

    devuelto_a_tiempo: Optional[bool] = None
    horas_retraso: Optional[float] = None
    if p.estado == EstadoPrestamo.DEVUELTO and fecha_dev is not None:
        devuelto_a_tiempo = fecha_dev <= fecha_fin
        if not devuelto_a_tiempo:
            horas_retraso = _horas(fecha_dev - fecha_fin)
    elif es_vencido:
        horas_retraso = _horas(ahora - fecha_fin)

    recursos = sorted(
        (asoc.recurso for asoc in sol.recursos_asociados),
        key=lambda r: r.codigo
    )

    return PrestamoConsolidadoOut(
        prestamo_id=p.id,
        solicitud_id=sol.id,
        estado=p.estado,
        es_vencido=es_vencido,
        motivo=sol.motivo,
        solicitante=_usuario_ref(sol.solicitante),
        fecha_inicio_prevista=_a_utc(sol.fecha_inicio),
        fecha_fin_prevista=fecha_fin,
        fecha_entrega_real=_a_utc(p.fecha_entrega_real),
        fecha_devolucion_real=fecha_dev,
        devuelto_a_tiempo=devuelto_a_tiempo,
        horas_retraso=horas_retraso,
        trazabilidad=TrazabilidadPrestamoOut(
            docente_aprobo=_usuario_ref(sol.docente_evaluo),
            fecha_aval_docente=_a_utc(sol.fecha_evaluacion_docente),
            responsable_aprobo=_usuario_ref(sol.responsable_evaluo),
            fecha_aprobacion_responsable=_a_utc(sol.fecha_evaluacion_responsable),
            responsable_entrega=_usuario_ref(p.responsable_entrega),
            responsable_recepcion=_usuario_ref(p.responsable_recepcion)
        ),
        recursos=[
            RecursoConsolidadoOut(
                id=r.id, codigo=r.codigo, nombre=r.nombre,
                categoria=r.categoria, condicion=r.condicion
            )
            for r in recursos
        ],
        novedades=[
            NovedadConsolidadoOut(
                id=n.id, recurso_codigo=n.recurso.codigo, tipo=n.tipo,
                descripcion=n.descripcion, resuelta=n.resuelta
            )
            for n in sorted(p.novedades, key=lambda n: n.id)
        ]
    )


def listar_consolidado(
    db: Session,
    filtros: ConsolidadoFiltros,
    limit: int = 200,
    offset: int = 0
) -> ConsolidadoOut:
    """
    Historial consolidado de préstamos con solicitante, responsables, fechas pactadas vs. reales,
    recursos asociados y novedades. Soporta filtros por fechas, estado, solicitante y categoría.
    """
    ahora = get_utc_now()
    conds = _construir_condiciones(filtros, ahora)

    total = db.query(func.count(Prestamo.id)).filter(*conds).scalar() or 0

    prestamos = (
        db.query(Prestamo)
        .options(
            selectinload(Prestamo.solicitud).options(
                joinedload(Solicitud.solicitante),
                joinedload(Solicitud.docente_evaluo),
                joinedload(Solicitud.responsable_evaluo),
                selectinload(Solicitud.recursos_asociados).joinedload(SolicitudRecurso.recurso)
            ),
            joinedload(Prestamo.responsable_entrega),
            joinedload(Prestamo.responsable_recepcion),
            selectinload(Prestamo.novedades).joinedload(Novedad.recurso)
        )
        .filter(*conds)
        .order_by(Prestamo.fecha_entrega_real.desc(), Prestamo.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return ConsolidadoOut(
        total_registros=total,
        limit=limit,
        offset=offset,
        filtros_aplicados=filtros,
        items=[_formatear_item(p, ahora) for p in prestamos]
    )



# Trazabilidad y auditoría


def obtener_resumen_auditoria(db: Session, limite: int = 10) -> TrazabilidadResumenOut:
    """Resumen de eventos de auditoría: total, conteo por acción y últimos eventos."""
    total = db.query(func.count(AuditoriaEvento.id)).scalar() or 0

    conteo = func.count(AuditoriaEvento.id)
    por_accion = (
        db.query(AuditoriaEvento.accion, conteo)
        .group_by(AuditoriaEvento.accion)
        .order_by(conteo.desc(), AuditoriaEvento.accion.asc())
        .all()
    )

    ultimos = (
        db.query(AuditoriaEvento)
        .options(joinedload(AuditoriaEvento.usuario))
        .order_by(AuditoriaEvento.creado_en.desc(), AuditoriaEvento.id.desc())
        .limit(limite)
        .all()
    )

    return TrazabilidadResumenOut(
        total_eventos=total,
        eventos_por_accion=[AccionConteoOut(accion=a, total=c) for a, c in por_accion],
        ultimos_eventos=[
            AuditoriaEventoOut(
                id=e.id,
                accion=e.accion,
                entidad=e.entidad,
                entidad_id=e.entidad_id,
                usuario_id=e.usuario_id,
                usuario_nombre=e.usuario.nombre_completo if e.usuario else None,
                detalles=e.detalles,
                creado_en=_a_utc(e.creado_en)
            )
            for e in ultimos
        ]
    )