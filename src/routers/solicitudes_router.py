from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from src.database import get_db
from src.models.usuario import Usuario, RolUsuario
from src.models.solicitud import Solicitud, EstadoSolicitud
from src.schemas.solicitud import (
    SolicitudCreate, SolicitudCancelar, SolicitudOut,
    EvaluacionDocenteRequest, EvaluacionResponsableRequest,
    SolicitudBandejaResponsableOut
)
from src.auth.dependencies import get_current_user, require_roles
from src.services.solicitud_service import (
    crear_solicitud, cancelar_solicitud, listar_solicitudes, formatear_solicitud_out
)
from src.services.evaluacion_service import (
    evaluar_docente, evaluar_responsable,
    listar_bandeja_docente, listar_bandeja_responsable
)

router = APIRouter(prefix="/api/v1/solicitudes", tags=["Solicitudes"])


@router.get("/bandeja/docente", response_model=List[SolicitudOut])
def get_bandeja_docente(
    db: Session = Depends(get_db),
    docente: Usuario = Depends(require_roles(RolUsuario.DOCENTE))
):
    """
    Retorna la bandeja de solicitudes de estudiantes en espera de visto bueno docente.
    Restringido al rol Docente.
    """
    return listar_bandeja_docente(db, docente)


@router.get("/bandeja/responsable", response_model=List[SolicitudBandejaResponsableOut])
def get_bandeja_responsable(
    db: Session = Depends(get_db),
    responsable: Usuario = Depends(require_roles(RolUsuario.RESPONSABLE))
):
    """
    Retorna la bandeja de solicitudes en espera de aprobación del responsable,
    con diagnósticos en tiempo real de colisión y prioridad de orden FIFO.
    Restringido al rol Responsable.
    """
    return listar_bandeja_responsable(db, responsable)


@router.post("", response_model=SolicitudOut, status_code=status.HTTP_201_CREATED)
def post_solicitud(
    datos: SolicitudCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Crea una nueva solicitud de préstamo.
    - Rol Estudiante -> Inicia en estado 'pendiente_docente' (RN-02).
    - Rol Docente -> Inicia en estado 'pendiente_responsable' (RN-03).
    Valida ausencia de inhabilitación y fechas estrictamente válidas.
    """
    return crear_solicitud(db, current_user, datos)


@router.get("", response_model=List[SolicitudOut])
def get_solicitudes(
    estado: Optional[EstadoSolicitud] = None,
    solo_propias: bool = Query(False, description="Filtrar únicamente solicitudes propias del usuario"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Lista las solicitudes según el rol del usuario conectado:
    - Estudiante: Solo sus solicitudes.
    - Docente: Sus solicitudes y las pendientes de su aval.
    - Responsable / Coordinación: Todas las solicitudes del sistema.
    """
    return listar_solicitudes(db, current_user, estado=estado, solo_propias=solo_propias)


@router.get("/{solicitud_id}", response_model=SolicitudOut)
def get_solicitud_por_id(
    solicitud_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Obtiene el detalle completo de una solicitud."""
    solicitud = db.query(Solicitud).filter(Solicitud.id == solicitud_id).first()
    if not solicitud:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud no encontrada")

    # Validación de acceso por propiedad
    if current_user.rol == RolUsuario.ESTUDIANTE and solicitud.solicitante_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permiso para consultar solicitudes de otros estudiantes."
        )

    return formatear_solicitud_out(solicitud)


@router.post("/{solicitud_id}/cancelar", response_model=SolicitudOut)
def post_cancelar_solicitud(
    solicitud_id: int,
    datos: SolicitudCancelar,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Cancela una solicitud antes de que ocurra la entrega física.
    Si la solicitud estaba aprobada, libera automáticamente la reserva.
    """
    return cancelar_solicitud(db, solicitud_id, current_user, datos.motivo_cancelacion)


@router.post("/{solicitud_id}/evaluar-docente", response_model=SolicitudOut)
def post_evaluar_docente(
    solicitud_id: int,
    datos: EvaluacionDocenteRequest,
    db: Session = Depends(get_db),
    docente: Usuario = Depends(require_roles(RolUsuario.DOCENTE))
):
    """
    Emite el visto bueno académico (o rechazo) de un docente sobre una solicitud de estudiante.
    """
    return evaluar_docente(
        db=db,
        solicitud_id=solicitud_id,
        docente=docente,
        aprobado=datos.aprobado,
        motivo_rechazo=datos.motivo_rechazo
    )


@router.post("/{solicitud_id}/evaluar-responsable", response_model=SolicitudOut)
def post_evaluar_responsable(
    solicitud_id: int,
    datos: EvaluacionResponsableRequest,
    db: Session = Depends(get_db),
    responsable: Usuario = Depends(require_roles(RolUsuario.RESPONSABLE))
):
    """
    Aprueba definitivamente (creando reserva firme) o rechaza una solicitud.
    Aplica bloqueo pesimista ordenado de filas (SELECT ... FOR UPDATE) y valida regla FIFO.
    """
    return evaluar_responsable(
        db=db,
        solicitud_id=solicitud_id,
        responsable=responsable,
        aprobado=datos.aprobado,
        motivo_rechazo=datos.motivo_rechazo
    )


