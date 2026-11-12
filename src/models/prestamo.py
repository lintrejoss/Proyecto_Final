import enum
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import Base


class EstadoPrestamo(str, enum.Enum):
    EN_CURSO = "en_curso"
    DEVUELTO = "devuelto"


class Prestamo(Base):
    __tablename__ = "prestamos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    solicitud_id: Mapped[int] = mapped_column(ForeignKey("solicitudes.id"), unique=True, nullable=False)

    # Entrega
    responsable_entrega_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    fecha_entrega_real: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observaciones_entrega: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Devolución
    responsable_recepcion_id: Mapped[Optional[int]] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    fecha_devolucion_real: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    observaciones_devolucion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    estado: Mapped[EstadoPrestamo] = mapped_column(
        Enum(EstadoPrestamo, name="estado_prestamo_enum"),
        default=EstadoPrestamo.EN_CURSO,
        nullable=False,
        index=True
    )

    # Relaciones
    solicitud = relationship("Solicitud", back_populates="prestamo")
    responsable_entrega = relationship("Usuario", foreign_keys=[responsable_entrega_id])
    responsable_recepcion = relationship("Usuario", foreign_keys=[responsable_recepcion_id])
    novedades: Mapped[List["Novedad"]] = relationship("Novedad", back_populates="prestamo")

    def __repr__(self) -> str:
        return f"<Prestamo(id={self.id}, solicitud_id={self.solicitud_id}, estado='{self.estado}')>"

