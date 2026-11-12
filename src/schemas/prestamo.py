from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from src.models.prestamo import EstadoPrestamo
from src.models.novedad import TipoNovedad


class PrestamoEntregaRequest(BaseModel):
    solicitud_id: int = Field(..., description="ID de la solicitud aprobada que se va a entregar")
    observaciones: Optional[str] = Field(None, max_length=500, description="Observaciones del estado de los equipos al salir")


class ItemDevolucionEstado(BaseModel):
    recurso_id: int
    estado_fisico: str = Field(..., description="'bueno', 'dano' o 'faltante'")
    descripcion_novedad: Optional[str] = Field(None, max_length=500, description="Detalle del daño o faltante si aplica")


class PrestamoDevolucionRequest(BaseModel):
    observaciones: Optional[str] = Field(None, max_length=500, description="Observaciones generales de la recepción")
    items: Optional[List[ItemDevolucionEstado]] = Field(None, description="Reporte individual por recurso devuelto")


class RecursoPrestamoSimple(BaseModel):
    id: int
    codigo: str
    nombre: str
    categoria: str
    condicion: str

    model_config = {"from_attributes": True}


class PrestamoOut(BaseModel):
    id: int
    solicitud_id: int
    solicitante_id: int
    solicitante_nombre: str
    solicitante_email: str
    solicitante_documento: str
    responsable_entrega_nombre: str
    fecha_entrega_real: datetime
    observaciones_entrega: Optional[str] = None
    responsable_recepcion_nombre: Optional[str] = None
    fecha_devolucion_real: Optional[datetime] = None
    observaciones_devolucion: Optional[str] = None
    estado: EstadoPrestamo
    fecha_inicio_prevista: datetime
    fecha_fin_prevista: datetime
    es_vencido: bool
    recursos: List[RecursoPrestamoSimple]

    model_config = {"from_attributes": True}
