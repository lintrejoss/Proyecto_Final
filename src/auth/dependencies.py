from typing import List, Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from src.database import get_db
from src.models.usuario import Usuario, RolUsuario
from src.auth.security import decode_access_token

security_scheme = HTTPBearer(auto_error=False)


def get_token_from_request(
    request: Request,
    auth_credentials: Optional[HTTPAuthorizationCredentials] = None
) -> Optional[str]:
    """
    Extrae el token JWT del header 'Authorization: Bearer <token>'
    o alternativamente de una cookie 'access_token' para navegación web.
    """
    if auth_credentials and hasattr(auth_credentials, "credentials"):
        return auth_credentials.credentials

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1]

    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        # Si la cookie contiene el prefijo "Bearer ", se remueve
        if cookie_token.startswith("Bearer "):
            return cookie_token.split(" ", 1)[1]
        return cookie_token
    return None


def get_current_user(
    request: Request,
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> Usuario:
    """
    Valida el token JWT y retorna el usuario autenticado desde la base de datos.
    Lanza HTTP 401 si el token no existe, expiró o es inválido.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo autenticar las credenciales o la sesión ha expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = get_token_from_request(request, auth_credentials)
    if not token:
        raise credentials_exception

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        raise credentials_exception

    user = db.query(Usuario).filter(Usuario.id == user_id_int).first()
    if user is None:
        raise credentials_exception

    if not user.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta de usuario está desactivada"
        )

    return user


def require_roles(*allowed_roles: RolUsuario):
    """
    Decorador / Dependencia para autorizar únicamente los roles especificados.
    Lanza HTTP 403 Forbidden si el rol del usuario autenticado no está en la lista.
    """
    def role_checker(current_user: Usuario = Depends(get_current_user)) -> Usuario:
        if current_user.rol not in allowed_roles:
            roles_str = ", ".join([r.value for r in allowed_roles])
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Se requiere uno de los siguientes roles: [{roles_str}]"
            )
        return current_user

    return role_checker
