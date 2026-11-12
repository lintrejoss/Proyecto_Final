import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import Base
from src.models.base import get_utc_now


class TipoNovedad(str, enum.Enum):
    DANO = "dano"
    FALTANTE = "faltante"
    RETRASO = "retraso"
    OBSERVACION = "observacion"


class Novedad(Base):
    __tablename__ = "novedades"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    prestamo_id: Mapped[int] = mapped_column(ForeignKey("prestamos.id"), nullable=False, index=True)
    recurso_id: Mapped[int] = mapped_column(ForeignKey("recursos.id"), nullable=False, index=True)
    usuario_inhabilitado_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)

    tipo: Mapped[TipoNovedad] = mapped_column(
        Enum(TipoNovedad, name="tipo_novedad_enum"),
        nullable=False,
        index=True
    )
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)

    # Estado de la novedad y rehabilitación
    resuelta: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    fecha_resolucion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    responsable_resolucion_id: Mapped[Optional[int]] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    observaciones_resolucion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    # Relaciones
    prestamo = relationship("Prestamo", back_populates="novedades")
    recurso = relationship("Recurso", back_populates="novedades")
    usuario_inhabilitado = relationship("Usuario", foreign_keys=[usuario_inhabilitado_id], back_populates="novedades_asociadas")
    responsable_resolucion = relationship("Usuario", foreign_keys=[responsable_resolucion_id])

    def __repr__(self) -> str:
        return f"<Novedad(id={self.id}, tipo='{self.tipo}', resuelta={self.resuelta})>"

