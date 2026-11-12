import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import Base
from src.models.base import get_utc_now


class CategoriaRecurso(str, enum.Enum):
    HERRAMIENTA = "herramienta"
    EQUIPO = "equipo"


class CondicionRecurso(str, enum.Enum):
    HABILITADO = "habilitado"
    NO_DISPONIBLE = "no_disponible"
    DADO_DE_BAJA = "dado_de_baja"


class Recurso(Base):
    __tablename__ = "recursos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    codigo: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    categoria: Mapped[CategoriaRecurso] = mapped_column(Enum(CategoriaRecurso, name="categoria_recurso_enum"), nullable=False)
    marca: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    modelo: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    serie: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    condicion: Mapped[CondicionRecurso] = mapped_column(
        Enum(CondicionRecurso, name="condicion_recurso_enum"),
        default=CondicionRecurso.HABILITADO,
        nullable=False
    )
    ubicacion: Mapped[str] = mapped_column(String(150), default="Almacén Principal", nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    # Relaciones
    solicitud_recursos = relationship("SolicitudRecurso", back_populates="recurso")
    novedades = relationship("Novedad", back_populates="recurso")

    def __repr__(self) -> str:
        return f"<Recurso(id={self.id}, codigo='{self.codigo}', nombre='{self.nombre}', condicion='{self.condicion}')>"

