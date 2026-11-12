from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from src.models.solicitud import EstadoSolicitud
from src.schemas.auth import UsuarioSummary
from src.schemas.recurso import RecursoOut


class SolicitudCreate(BaseModel):
    recurso_ids: List[int] = Field(..., min_length=1, description="Lista de IDs de herramientas y equipos a solicitar")
    fecha_inicio: datetime = Field(..., description="Fecha y hora de inicio requerida")
    fecha_fin: datetime = Field(..., description="Fecha y hora de finalización requerida")
    motivo: str = Field(..., min_length=5, description="Justificación o motivo académico de la solicitud")


class SolicitudCancelar(BaseModel):
    motivo_cancelacion: str = Field(..., min_length=5, description="Motivo obligatorio por el cual se cancela la solicitud")


class SolicitudOut(BaseModel):
    id: int
    solicitante_id: int
    solicitante: UsuarioSummary
    fecha_inicio: datetime
    fecha_fin: datetime
    motivo: str
    estado: EstadoSolicitud
    motivo_rechazo: Optional[str] = None
    motivo_cancelacion: Optional[str] = None
    docente_evaluo_id: Optional[int] = None
    docente_evaluo: Optional[UsuarioSummary] = None
    fecha_evaluacion_docente: Optional[datetime] = None
    responsable_evaluo_id: Optional[int] = None
    responsable_evaluo: Optional[UsuarioSummary] = None
    fecha_evaluacion_responsable: Optional[datetime] = None
    creado_en: datetime
    recursos: List[RecursoOut] = []

    class Config:
        from_attributes = True

