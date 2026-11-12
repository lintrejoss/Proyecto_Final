import enum
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import Base
from src.models.base import get_utc_now


class EstadoSolicitud(str, enum.Enum):
    PENDIENTE_DOCENTE = "pendiente_docente"
    PENDIENTE_RESPONSABLE = "pendiente_responsable"
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"
    CANCELADA = "cancelada"


class SolicitudRecurso(Base):
    __tablename__ = "solicitud_recursos"

    solicitud_id: Mapped[int] = mapped_column(ForeignKey("solicitudes.id", ondelete="CASCADE"), primary_key=True)
    recurso_id: Mapped[int] = mapped_column(ForeignKey("recursos.id", ondelete="RESTRICT"), primary_key=True)

    # Relaciones
    solicitud = relationship("Solicitud", back_populates="recursos_asociados")
    recurso = relationship("Recurso", back_populates="solicitud_recursos")


class Solicitud(Base):
    __tablename__ = "solicitudes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    solicitante_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    
    fecha_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    fecha_fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    motivo: Mapped[str] = mapped_column(Text, nullable=False)

    estado: Mapped[EstadoSolicitud] = mapped_column(
        Enum(EstadoSolicitud, name="estado_solicitud_enum"),
        default=EstadoSolicitud.PENDIENTE_DOCENTE,
        nullable=False,
        index=True
    )

    motivo_rechazo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    motivo_cancelacion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Trazabilidad de evaluación docente
    docente_evaluo_id: Mapped[Optional[int]] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    fecha_evaluacion_docente: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Trazabilidad de evaluación del responsable
    responsable_evaluo_id: Mapped[Optional[int]] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    fecha_evaluacion_responsable: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now, nullable=False, index=True)

    # Relaciones
    solicitante = relationship("Usuario", foreign_keys=[solicitante_id], back_populates="solicitudes")
    docente_evaluo = relationship("Usuario", foreign_keys=[docente_evaluo_id])
    responsable_evaluo = relationship("Usuario", foreign_keys=[responsable_evaluo_id])

    recursos_asociados: Mapped[List[SolicitudRecurso]] = relationship(
        "SolicitudRecurso",
        back_populates="solicitud",
        cascade="all, delete-orphan"
    )
    prestamo = relationship("Prestamo", back_populates="solicitud", uselist=False)

    def __repr__(self) -> str:
        return f"<Solicitud(id={self.id}, solicitante_id={self.solicitante_id}, estado='{self.estado}')>"

