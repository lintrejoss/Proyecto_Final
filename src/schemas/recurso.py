from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from src.models.recurso import CategoriaRecurso, CondicionRecurso


class RecursoBase(BaseModel):
    codigo: str = Field(..., max_length=50, example="HER-005")
    nombre: str = Field(..., max_length=200, example="Multímetro Digital")
    categoria: CategoriaRecurso
    marca: Optional[str] = Field(None, max_length=100, example="Fluke")
    modelo: Optional[str] = Field(None, max_length=100, example="87V")
    serie: Optional[str] = Field(None, max_length=100, example="FLK-9901")
    condicion: CondicionRecurso = CondicionRecurso.HABILITADO
    ubicacion: str = Field("Almacén Principal", max_length=150)


class RecursoCreate(RecursoBase):
    pass


class RecursoUpdate(BaseModel):
    nombre: Optional[str] = None
    categoria: Optional[CategoriaRecurso] = None
    marca: Optional[str] = None
    modelo: Optional[str] = None
    serie: Optional[str] = None
    condicion: Optional[CondicionRecurso] = None
    ubicacion: Optional[str] = None


class RecursoOut(RecursoBase):
    id: int
    creado_en: datetime

    class Config:
        from_attributes = True


class RecursoConDisponibilidad(RecursoOut):
    disponible: bool = True
    motivo_no_disponible: Optional[str] = None
    prestado_actualmente: bool = False

