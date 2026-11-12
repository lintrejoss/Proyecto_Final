from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import Base
from src.models.base import get_utc_now


class AuditoriaEvento(Base):
    __tablename__ = "auditoria_eventos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    usuario_id: Mapped[Optional[int]] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    accion: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entidad: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entidad_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    detalles: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now, nullable=False, index=True)

    usuario = relationship("Usuario", foreign_keys=[usuario_id])

    def __repr__(self) -> str:
        return f"<AuditoriaEvento(id={self.id}, accion='{self.accion}', entidad='{self.entidad}', id={self.entidad_id})>"

