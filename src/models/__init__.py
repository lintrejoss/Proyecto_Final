from src.database import Base
from src.models.usuario import Usuario, RolUsuario
from src.models.recurso import Recurso, CategoriaRecurso, CondicionRecurso
from src.models.solicitud import Solicitud, SolicitudRecurso, EstadoSolicitud
from src.models.prestamo import Prestamo, EstadoPrestamo
from src.models.novedad import Novedad, TipoNovedad
from src.models.auditoria import AuditoriaEvento

__all__ = [
    "Base",
    "Usuario",
    "RolUsuario",
    "Recurso",
    "CategoriaRecurso",
    "CondicionRecurso",
    "Solicitud",
    "SolicitudRecurso",
    "EstadoSolicitud",
    "Prestamo",
    "EstadoPrestamo",
    "Novedad",
    "TipoNovedad",
    "AuditoriaEvento"
]

