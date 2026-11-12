from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from src.database import get_db
from src.models.usuario import Usuario
from src.schemas.auth import LoginRequest, TokenResponse, UsuarioSummary
from src.auth.security import verify_password, create_access_token
from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticación"])


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: LoginRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Autentica un usuario mediante email y contraseña (Argon2).
    Genera un token JWT Bearer y opcionalmente establece una cookie HttpOnly.
    """
    user = db.query(Usuario).filter(Usuario.email == credentials.email.lower()).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo electrónico o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta de usuario se encuentra inactiva"
        )

    access_token = create_access_token(
        data={"sub": str(user.id), "rol": user.rol.value, "email": user.email}
    )

    # Establecer cookie para navegación web sin fisuras
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        samesite="lax",
        max_age=8 * 3600
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UsuarioSummary.model_validate(user)
    )


@router.get("/me", response_model=UsuarioSummary)
def get_me(current_user: Usuario = Depends(get_current_user)):
    """Retorna los datos del usuario actualmente autenticado (sin contraseñas)."""
    return UsuarioSummary.model_validate(current_user)


@router.post("/logout")
def logout(response: Response):
    """Cierra la sesión limpiando la cookie de autenticación."""
    response.delete_cookie(key="access_token")
    return {"message": "Sesión cerrada exitosamente"}

