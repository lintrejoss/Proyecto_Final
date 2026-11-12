from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from src.database import get_db
from src.models.usuario import Usuario, RolUsuario
from src.schemas.novedad import NovedadOut, ResolverNovedadRequest
from src.auth.dependencies import require_roles
from src.services.prestamo_service import (
    listar_novedades_servicio,
    resolver_novedad_servicio
)

router = APIRouter(prefix="/api/v1/novedades", tags=["Novedades"])


@router.get("", response_model=List[NovedadOut])
def get_novedades(
    solo_abiertas: bool = Query(False, description="Filtrar solo novedades no resueltas"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_roles(RolUsuario.RESPONSABLE, RolUsuario.COORDINACION))
):
    """
    RF-09: Lista novedades de equipos y usuarios inhabilitados.
    Permite filtrar por novedades abiertas/pendientes de resolución.
    """
    return listar_novedades_servicio(db, solo_abiertas=solo_abiertas)


@router.post("/{novedad_id}/resolver", response_model=NovedadOut)
def post_resolver_novedad(
    novedad_id: int,
    datos: ResolverNovedadRequest,
    db: Session = Depends(get_db),
    responsable: Usuario = Depends(require_roles(RolUsuario.RESPONSABLE, RolUsuario.COORDINACION))
):
    """
    RN-08 [C]: Resuelve una novedad pendiente, registrando observaciones y acuerdos.
    Opcionalmente rehabilita la condición operativa del recurso.
    Si el usuario no tiene más sanciones, queda habilitado para futuros préstamos.
    """
    return resolver_novedad_servicio(db, responsable, novedad_id, datos)
