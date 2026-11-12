from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from src.database import get_db
from src.models.usuario import Usuario, RolUsuario
from src.schemas.prestamo import (
    PrestamoEntregaRequest,
    PrestamoDevolucionRequest,
    PrestamoOut
)
from src.schemas.solicitud import SolicitudOut
from src.auth.dependencies import get_current_user, require_roles
from src.services.prestamo_service import (
    registrar_entrega_prestamo,
    registrar_devolucion_prestamo,
    listar_prestamos_servicio,
    listar_solicitudes_listas_para_entrega,
    verificar_inhabilitacion_o_vencimiento_usuario
)
from src.services.solicitud_service import formatear_solicitud_out

router = APIRouter(prefix="/api/v1/prestamos", tags=["Préstamos"])


@router.get("/listas-para-entrega", response_model=List[SolicitudOut])
def get_solicitudes_listas_para_entrega(
    db: Session = Depends(get_db),
    responsable: Usuario = Depends(require_roles(RolUsuario.RESPONSABLE))
):
    """
    Retorna las solicitudes en estado APROBADA que están pendientes de entrega física.
    Exclusivo para el Responsable de Laboratorio.
    """
    solicitudes = listar_solicitudes_listas_para_entrega(db)
    return [formatear_solicitud_out(s) for s in solicitudes]


@router.get("/verificar-usuario/{usuario_id}")
def verificar_estado_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    responsable: Usuario = Depends(require_roles(RolUsuario.RESPONSABLE))
):
    """
    Verifica de manera preventiva si un usuario puede recibir préstamos
    o si tiene préstamos vencidos / novedades abiertas (RN-06, RN-07).
    """
    puede_recibir, motivo = verificar_inhabilitacion_o_vencimiento_usuario(db, usuario_id)
    return {
        "usuario_id": usuario_id,
        "puede_recibir": puede_recibir,
        "motivo_bloqueo": motivo
    }


@router.post("/entregar", response_model=PrestamoOut, status_code=status.HTTP_201_CREATED)
def post_entregar_prestamo(
    datos: PrestamoEntregaRequest,
    db: Session = Depends(get_db),
    responsable: Usuario = Depends(require_roles(RolUsuario.RESPONSABLE))
):
    """
    CA-04 / RF-07: Registra la entrega física de una solicitud aprobada.
    Crea el préstamo en estado 'en_curso' y actualiza la solicitud a 'en_curso'.
    Aplica RN-06 (bloqueo por vencidos) y RN-07 (bloqueo por sanciones).
    """
    return registrar_entrega_prestamo(db, responsable, datos)


@router.post("/{prestamo_id}/devolver", response_model=PrestamoOut)
def post_devolver_prestamo(
    prestamo_id: int,
    datos: PrestamoDevolucionRequest,
    db: Session = Depends(get_db),
    responsable: Usuario = Depends(require_roles(RolUsuario.RESPONSABLE))
):
    """
    CA-05 / RF-08: Registra la recepción física y devolución de los equipos.
    Si se reporta daño o faltante, genera la Novedad e inhabilita al solicitante (RN-07).
    """
    return registrar_devolucion_prestamo(db, responsable, prestamo_id, datos)


@router.get("", response_model=List[PrestamoOut])
def get_prestamos(
    solo_activos: bool = Query(False, description="Filtrar solo préstamos en curso"),
    solo_vencidos: bool = Query(False, description="Filtrar solo préstamos vencidos en curso"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_roles(RolUsuario.RESPONSABLE, RolUsuario.COORDINACION))
):
    """
    RF-11: Lista préstamos registrados con estado, fechas y cálculo dinámico de vencidos.
    Disponible para Responsable y Coordinación.
    """
    return listar_prestamos_servicio(db, solo_activos=solo_activos, solo_vencidos=solo_vencidos)


@router.get("/mis-prestamos", response_model=List[PrestamoOut])
def get_mis_prestamos(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Retorna el historial personal de préstamos del solicitante autenticado.
    """
    return listar_prestamos_servicio(db, usuario_id=current_user.id)
