from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from src.database import get_db
from src.models.usuario import Usuario, RolUsuario
from src.models.recurso import Recurso, CategoriaRecurso, CondicionRecurso
from src.schemas.recurso import (
    RecursoCreate, RecursoUpdate, RecursoOut, RecursoConDisponibilidad
)
from src.auth.dependencies import get_current_user, require_roles
from src.services.recurso_service import (
    listar_recursos, recurso_esta_disponible_en_rango
)

router = APIRouter(prefix="/api/v1/recursos", tags=["Recursos"])


@router.get("", response_model=List[RecursoConDisponibilidad])
def get_recursos(
    categoria: Optional[CategoriaRecurso] = None,
    condicion: Optional[CondicionRecurso] = None,
    busqueda: Optional[str] = None,
    fecha_inicio: Optional[datetime] = Query(None, description="Inicio del intervalo para calcular disponibilidad [inicio, fin)"),
    fecha_fin: Optional[datetime] = Query(None, description="Fin del intervalo para calcular disponibilidad [inicio, fin)"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Lista el catálogo de recursos con filtros opcionales y cálculo de disponibilidad por fechas.
    Accesible para todos los usuarios autenticados.
    """
    if (fecha_inicio and not fecha_fin) or (fecha_fin and not fecha_inicio):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Para consultar disponibilidad debe proveer tanto fecha_inicio como fecha_fin."
        )

    if fecha_inicio and fecha_fin and fecha_inicio >= fecha_fin:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La fecha de inicio debe ser anterior a la fecha de fin."
        )

    # Si es responsable o coordinación, permitir ver recursos dados de baja si lo solicitan
    incluir_baja = current_user.rol in [RolUsuario.RESPONSABLE, RolUsuario.COORDINACION]
    return listar_recursos(
        db=db,
        categoria=categoria,
        condicion=condicion,
        busqueda=busqueda,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        incluir_dados_de_baja=incluir_baja
    )


@router.get("/{recurso_id}", response_model=RecursoConDisponibilidad)
def get_recurso_por_id(
    recurso_id: int,
    fecha_inicio: Optional[datetime] = None,
    fecha_fin: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Obtiene el detalle individual de un recurso y su disponibilidad."""
    recurso = db.query(Recurso).filter(Recurso.id == recurso_id).first()
    if not recurso:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso no encontrado")

    if fecha_inicio and fecha_fin:
        disponible, motivo, prestado = recurso_esta_disponible_en_rango(db, recurso.id, fecha_inicio, fecha_fin)
    else:
        disponible, motivo, prestado = recurso_esta_disponible_en_rango(db, recurso.id, recurso.creado_en, recurso.creado_en)

    return RecursoConDisponibilidad(
        id=recurso.id,
        codigo=recurso.codigo,
        nombre=recurso.nombre,
        categoria=recurso.categoria,
        marca=recurso.marca,
        modelo=recurso.modelo,
        serie=recurso.serie,
        condicion=recurso.condicion,
        ubicacion=recurso.ubicacion,
        creado_en=recurso.creado_en,
        disponible=disponible,
        motivo_no_disponible=motivo,
        prestado_actualmente=prestado
    )


@router.post("", response_model=RecursoOut, status_code=status.HTTP_201_CREATED)
def crear_recurso(
    datos: RecursoCreate,
    db: Session = Depends(get_db),
    admin_user: Usuario = Depends(require_roles(RolUsuario.RESPONSABLE))
):
    """
    Crea un nuevo recurso en el inventario.
    Restringido exclusivamente al rol Responsable.
    """
    existente = db.query(Recurso).filter(Recurso.codigo == datos.codigo.upper()).first()
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un recurso registrado con el código '{datos.codigo.upper()}'."
        )

    nuevo = Recurso(
        codigo=datos.codigo.upper().strip(),
        nombre=datos.nombre.strip(),
        categoria=datos.categoria,
        marca=datos.marca.strip() if datos.marca else None,
        modelo=datos.modelo.strip() if datos.modelo else None,
        serie=datos.serie.strip() if datos.serie else None,
        condicion=datos.condicion,
        ubicacion=datos.ubicacion.strip()
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


@router.put("/{recurso_id}", response_model=RecursoOut)
def actualizar_recurso(
    recurso_id: int,
    datos: RecursoUpdate,
    db: Session = Depends(get_db),
    admin_user: Usuario = Depends(require_roles(RolUsuario.RESPONSABLE))
):
    """
    Actualiza metadatos o la condición física de un recurso.
    Restringido al rol Responsable.
    """
    recurso = db.query(Recurso).filter(Recurso.id == recurso_id).first()
    if not recurso:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso no encontrado")

    update_dict = datos.model_dump(exclude_unset=True)
    for field, val in update_dict.items():
        if val is not None:
            setattr(recurso, field, val)

    db.commit()
    db.refresh(recurso)
    return recurso

