import enum
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import Base
from src.models.base import get_utc_now


class RolUsuario(str, enum.Enum):
    ESTUDIANTE = "estudiante"
    DOCENTE = "docente"
    RESPONSABLE = "responsable"
    COORDINACION = "coordinacion"


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nombre_completo: Mapped[str] = mapped_column(String(255), nullable=False)
    documento: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    rol: Mapped[RolUsuario] = mapped_column(Enum(RolUsuario, name="rol_usuario_enum"), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    # Relaciones
    solicitudes = relationship("Solicitud", back_populates="solicitante", foreign_keys="Solicitud.solicitante_id")
    novedades_asociadas = relationship("Novedad", back_populates="usuario_inhabilitado", foreign_keys="Novedad.usuario_inhabilitado_id")

    def __repr__(self) -> str:
        return f"<Usuario(id={self.id}, email='{self.email}', rol='{self.rol}')>"

