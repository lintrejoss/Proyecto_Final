from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from src.database import get_db
from src.models.usuario import Usuario, RolUsuario
from src.models.recurso import CategoriaRecurso
from src.schemas.reporte import (
    EstadoFiltroPrestamo,
    ConsolidadoFiltros,
    MetricasOut,
    ConsolidadoOut,
    TrazabilidadResumenOut
)
from src.auth.dependencies import require_roles
from src.services.reporte_service import (
    obtener_metricas,
    listar_consolidado,
    obtener_resumen_auditoria
)

router = APIRouter(prefix="/api/v1/reportes", tags=["Reportes de Coordinación"])

# Para dejar los reportes exclusivos de Coordinación basta con quitar RolUsuario.RESPONSABLE.
ROLES_REPORTES = (RolUsuario.COORDINACION, RolUsuario.RESPONSABLE)


@router.get("/metricas", response_model=MetricasOut)
def get_metricas(
    top: int = Query(5, ge=1, le=20, description="Cantidad de recursos en el ranking de más prestados"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_roles(*ROLES_REPORTES))
):
    """
    CA-06 / RF-12: KPIs consolidados en tiempo real (préstamos activos y vencidos, tasa de
    cumplimiento, recursos no disponibles, ranking de recursos y novedades abiertas).
    """
    return obtener_metricas(db, top=top)


@router.get("/consolidado", response_model=ConsolidadoOut)
def get_consolidado(
    fecha_desde: Optional[date] = Query(None, description="Entrega real desde (YYYY-MM-DD)"),
    fecha_hasta: Optional[date] = Query(None, description="Entrega real hasta (YYYY-MM-DD)"),
    estado: Optional[EstadoFiltroPrestamo] = Query(None, description="en_curso, devuelto o vencido"),
    solicitante: Optional[str] = Query(None, max_length=100, description="Nombre, correo o documento"),
    solicitante_id: Optional[int] = Query(None, ge=1),
    categoria: Optional[CategoriaRecurso] = Query(None, description="herramienta o equipo"),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_roles(*ROLES_REPORTES))
):
    """
    Historial consolidado de préstamos con solicitante, responsables de entrega y recepción,
    fechas pactadas vs. reales, recursos asociados y novedades.
    """
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La fecha 'desde' no puede ser posterior a la fecha 'hasta'."
        )

    filtros = ConsolidadoFiltros(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        estado=estado,
        solicitante=solicitante,
        solicitante_id=solicitante_id,
        categoria=categoria
    )
    return listar_consolidado(db, filtros, limit=limit, offset=offset)


@router.get("/auditoria", response_model=TrazabilidadResumenOut)
def get_resumen_auditoria(
    limite: int = Query(10, ge=1, le=50, description="Cantidad de eventos recientes a retornar"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_roles(*ROLES_REPORTES))
):
    """Resumen de trazabilidad: total de eventos de auditoría, conteo por acción y últimos eventos."""
    return obtener_resumen_auditoria(db, limite=limite)