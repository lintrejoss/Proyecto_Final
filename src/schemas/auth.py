from pydantic import BaseModel, EmailStr
from typing import Optional


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UsuarioSummary"


class UsuarioSummary(BaseModel):
    id: int
    email: str
    nombre_completo: str
    rol: str
    documento: str

    class Config:
        from_attributes = True


TokenResponse.model_rebuild()

