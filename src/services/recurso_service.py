from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from zoneinfo import ZoneInfo
from src.config import settings
from src.models import (
    Recurso, CondicionRecurso, CategoriaRecurso,
    Solicitud, SolicitudRecurso, EstadoSolicitud,
    Prestamo, EstadoPrestamo
)
from src.schemas.recurso import RecursoConDisponibilidad

BOGOTA_TZ = ZoneInfo(settings.TIMEZONE)


def asegurar_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Asegura que un datetime tenga zona horaria y se convierta a UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Si es naive, se asume la zona horaria del proyecto (America/Bogota)
        dt = dt.replace(tzinfo=BOGOTA_TZ)
    return dt.astimezone(timezone.utc)


def hay_colision_fechas(inicio_a: datetime, fin_a: datetime, inicio_b: datetime, fin_b: datetime) -> bool:
    """
    Evalúa colisión de intervalos semiabiertos [inicio, fin):
    Dos períodos A y B se superponen si y solo si:
    inicio_a < fin_b AND inicio_b < fin_a
    """
    return inicio_a < fin_b and inicio_b < fin_a


def recurso_esta_disponible_en_rango(
    db: Session,
    recurso_id: int,
    fecha_inicio: datetime,
    fecha_fin: datetime
) -> Tuple[bool, Optional[str], bool]:
    """
    Evalúa si un recurso individual está disponible en el intervalo [fecha_inicio, fecha_fin).
    Retorna: (disponible: bool, motivo_no_disponible: Optional[str], prestado_actualmente: bool)
    """
    inicio_utc = asegurar_utc(fecha_inicio)
    fin_utc = asegurar_utc(fecha_fin)
    ahora_utc = datetime.now(timezone.utc)

    recurso = db.query(Recurso).filter(Recurso.id == recurso_id).first()
    if not recurso:
        return False, "Recurso no encontrado", False

    # 1. Validación de Condición Física/Operativa
    if recurso.condicion != CondicionRecurso.HABILITADO:
        return False, f"Recurso no apto (Condición: {recurso.condicion.value})", False

    # 2. Verificar si está prestado físicamente en este instante
    prestamo_activo = (
        db.query(Prestamo)
        .join(Solicitud, Prestamo.solicitud_id == Solicitud.id)
        .join(SolicitudRecurso, SolicitudRecurso.solicitud_id == Solicitud.id)
        .filter(
            SolicitudRecurso.recurso_id == recurso_id,
            Prestamo.estado == EstadoPrestamo.EN_CURSO,
            Prestamo.fecha_devolucion_real.is_(None)
        )
        .first()
    )
    prestado_actualmente = prestamo_activo is not None

    # Si está prestado y la fecha de inicio solicitada es ahora o está dentro del período del préstamo activo no devuelto
    if prestado_actualmente:
        solicitud_prestamo = prestamo_activo.solicitud
        # Si la fecha de fin prevista del préstamo activo aún no pasa o si ya venció y sigue en poder del usuario
        fin_prestamo_activo = asegurar_utc(solicitud_prestamo.fecha_fin)
        if inicio_utc < fin_prestamo_activo or inicio_utc <= ahora_utc:
            return False, "El recurso está actualmente en préstamo físico y no ha sido devuelto", True

    # 3. Verificar colisiones con reservas formalmente aprobadas
    reservas_solapadas = (
        db.query(Solicitud)
        .join(SolicitudRecurso, SolicitudRecurso.solicitud_id == Solicitud.id)
        .filter(
            SolicitudRecurso.recurso_id == recurso_id,
            Solicitud.estado == EstadoSolicitud.APROBADA,
            Solicitud.fecha_inicio < fin_utc,
            Solicitud.fecha_fin > inicio_utc
        )
        .first()
    )

    if reservas_solapadas:
        return False, f"Ya existe una reserva aprobada para este recurso en esas fechas (Solicitud #{reservas_solapadas.id})", prestado_actualmente

    return True, None, prestado_actualmente


def listar_recursos(
    db: Session,
    categoria: Optional[CategoriaRecurso] = None,
    condicion: Optional[CondicionRecurso] = None,
    busqueda: Optional[str] = None,
    fecha_inicio: Optional[datetime] = None,
    fecha_fin: Optional[datetime] = None,
    incluir_dados_de_baja: bool = False
) -> List[RecursoConDisponibilidad]:
    """
    Consulta el catálogo de recursos con filtros opcionales y cálculo dinámico de disponibilidad temporal.
    """
    query = db.query(Recurso)

    if not incluir_dados_de_baja and condicion is None:
        query = query.filter(Recurso.condicion != CondicionRecurso.DADO_DE_BAJA)

    if categoria:
        query = query.filter(Recurso.categoria == categoria)

    if condicion:
        query = query.filter(Recurso.condicion == condicion)

    if busqueda:
        termino = f"%{busqueda.strip().lower()}%"
        query = query.filter(
            or_(
                Recurso.codigo.ilike(termino),
                Recurso.nombre.ilike(termino),
                Recurso.marca.ilike(termino),
                Recurso.modelo.ilike(termino),
                Recurso.serie.ilike(termino),
                Recurso.ubicacion.ilike(termino)
            )
        )

    recursos = query.order_by(Recurso.categoria.asc(), Recurso.codigo.asc()).all()
    resultado: List[RecursoConDisponibilidad] = []

    for r in recursos:
        if fecha_inicio and fecha_fin:
            disponible, motivo, prestado = recurso_esta_disponible_en_rango(db, r.id, fecha_inicio, fecha_fin)
        else:
            # Disponibilidad inmediata genérica
            ahora = datetime.now(timezone.utc)
            disponible, motivo, prestado = recurso_esta_disponible_en_rango(db, r.id, ahora, ahora)

        item = RecursoConDisponibilidad(
            id=r.id,
            codigo=r.codigo,
            nombre=r.nombre,
            categoria=r.categoria,
            marca=r.marca,
            modelo=r.modelo,
            serie=r.serie,
            condicion=r.condicion,
            ubicacion=r.ubicacion,
            creado_en=r.creado_en,
            disponible=disponible,
            motivo_no_disponible=motivo,
            prestado_actualmente=prestado
        )
        resultado.append(item)

    return resultado

