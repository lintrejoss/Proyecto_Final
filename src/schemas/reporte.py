from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from src.models.prestamo import EstadoPrestamo
from src.models.recurso import CategoriaRecurso, CondicionRecurso
from src.models.novedad import TipoNovedad


# Filtros


class EstadoFiltroPrestamo(str, Enum):
    """
    Estados filtrables en la consulta consolidada.
    'vencido' no es un estado almacenado: se calcula dinámicamente (RN-06):
    en_curso + sin devolución real + ahora > fecha_fin pactada.
    """
    EN_CURSO = "en_curso"
    DEVUELTO = "devuelto"
    VENCIDO = "vencido"


class ConsolidadoFiltros(BaseModel):
    fecha_desde: Optional[date] = Field(None, description="Entrega real desde esta fecha (inclusive, hora de Bogotá)")
    fecha_hasta: Optional[date] = Field(None, description="Entrega real hasta esta fecha (inclusive, hora de Bogotá)")
    estado: Optional[EstadoFiltroPrestamo] = None
    solicitante: Optional[str] = Field(None, description="Texto a buscar en nombre, correo o documento del solicitante")
    solicitante_id: Optional[int] = None
    categoria: Optional[CategoriaRecurso] = Field(None, description="Préstamos que incluyan al menos un recurso de esta categoría")



# Métricas / KPIs


class RecursoRankingOut(BaseModel):
    recurso_id: int
    codigo: str
    nombre: str
    categoria: CategoriaRecurso
    total_prestamos: int


class RecursoNovedadAbiertaOut(BaseModel):
    recurso_id: int
    codigo: str
    nombre: str
    condicion: CondicionRecurso
    novedades_abiertas: int
    tipos: List[TipoNovedad]


class MetricasOut(BaseModel):
    # Préstamos
    total_prestamos: int
    prestamos_activos: int = Field(..., description="Préstamos en curso (incluye los vencidos)")
    prestamos_vencidos: int = Field(..., description="Subconjunto de activos que superó su fecha fin pactada")
    prestamos_devueltos: int
    devueltos_a_tiempo: int
    devueltos_con_retraso: int
    tasa_cumplimiento: Optional[float] = Field(
        None, description="% de préstamos devueltos a tiempo sobre el total de devueltos (None si aún no hay devoluciones)"
    )
    # Recursos
    recursos_totales: int
    recursos_no_disponibles: int = Field(..., description="Recursos con condición 'no_disponible'")
    recursos_con_novedad_abierta: int
    novedades_abiertas: int
    # Rankings
    recursos_mas_prestados: List[RecursoRankingOut]
    recursos_con_novedades_abiertas: List[RecursoNovedadAbiertaOut]
    generado_en: datetime



# Consulta consolidada


class UsuarioRefOut(BaseModel):
    id: int
    nombre_completo: str
    email: str
    documento: str
    rol: str


class RecursoConsolidadoOut(BaseModel):
    id: int
    codigo: str
    nombre: str
    categoria: CategoriaRecurso
    condicion: CondicionRecurso


class NovedadConsolidadoOut(BaseModel):
    id: int
    recurso_codigo: str
    tipo: TipoNovedad
    descripcion: str
    resuelta: bool


class TrazabilidadPrestamoOut(BaseModel):
    """Quién aprobó, quién entregó y quién recibió cada préstamo."""
    docente_aprobo: Optional[UsuarioRefOut] = None
    fecha_aval_docente: Optional[datetime] = None
    responsable_aprobo: Optional[UsuarioRefOut] = None
    fecha_aprobacion_responsable: Optional[datetime] = None
    responsable_entrega: Optional[UsuarioRefOut] = None
    responsable_recepcion: Optional[UsuarioRefOut] = None


class PrestamoConsolidadoOut(BaseModel):
    prestamo_id: int
    solicitud_id: int
    estado: EstadoPrestamo
    es_vencido: bool
    motivo: str
    solicitante: UsuarioRefOut
    fecha_inicio_prevista: datetime
    fecha_fin_prevista: datetime
    fecha_entrega_real: datetime
    fecha_devolucion_real: Optional[datetime] = None
    devuelto_a_tiempo: Optional[bool] = Field(None, description="None mientras el préstamo siga en curso")
    horas_retraso: Optional[float] = Field(
        None, description="Mora actual (vencidos) o retraso con el que se devolvió; None si no hubo retraso"
    )
    trazabilidad: TrazabilidadPrestamoOut
    recursos: List[RecursoConsolidadoOut]
    novedades: List[NovedadConsolidadoOut]


class ConsolidadoOut(BaseModel):
    total_registros: int = Field(..., description="Total de préstamos que cumplen los filtros (sin paginar)")
    limit: int
    offset: int
    filtros_aplicados: ConsolidadoFiltros
    items: List[PrestamoConsolidadoOut]



# Trazabilidad y auditoría


class AccionConteoOut(BaseModel):
    accion: str
    total: int


class AuditoriaEventoOut(BaseModel):
    id: int
    accion: str
    entidad: str
    entidad_id: Optional[int] = None
    usuario_id: Optional[int] = None
    usuario_nombre: Optional[str] = None
    detalles: Optional[str] = None
    creado_en: datetime


class TrazabilidadResumenOut(BaseModel):
    total_eventos: int
    eventos_por_accion: List[AccionConteoOut]
    ultimos_eventos: List[AuditoriaEventoOut]