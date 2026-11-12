from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from src.models.novedad import TipoNovedad


class ResolverNovedadRequest(BaseModel):
    observaciones_resolucion: str = Field(..., min_length=5, max_length=1000, description="Detalle del acuerdo, pago o reparación efectuada")
    rehabilitar_recurso: bool = Field(True, description="Si es True, el recurso vuelve a condición HABILITADO. Si es False, se mantiene NO_DISPONIBLE.")


class NovedadOut(BaseModel):
    id: int
    prestamo_id: int
    recurso_id: int
    recurso_codigo: str
    recurso_nombre: str
    usuario_inhabilitado_id: int
    usuario_nombre: str
    usuario_email: str
    usuario_documento: str
    tipo: TipoNovedad
    descripcion: str
    resuelta: bool
    fecha_resolucion: Optional[datetime] = None
    responsable_resolucion_nombre: Optional[str] = None
    observaciones_resolucion: Optional[str] = None
    creado_en: datetime

    model_config = {"from_attributes": True}
