from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr
from src.models.usuario import RolUsuario


class UsuarioBase(BaseModel):
    email: EmailStr
    nombre_completo: str
    documento: str
    rol: RolUsuario
    activo: bool = True


class UsuarioCreate(UsuarioBase):
    password: str


class UsuarioOut(UsuarioBase):
    id: int
    creado_en: datetime

    class Config:
        from_attributes = True

