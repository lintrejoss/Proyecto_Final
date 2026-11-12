from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from src.database import get_db
from src.auth.dependencies import get_token_from_request
from src.auth.security import decode_access_token
from src.models.usuario import Usuario

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory="src/templates")


def get_optional_user(request: Request, db: Session) -> Usuario:
    token = get_token_from_request(request)
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    try:
        user_id = int(payload["sub"])
        return db.query(Usuario).filter(Usuario.id == user_id, Usuario.activo == True).first()
    except (ValueError, TypeError):
        return None


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "user": None})


@router.get("/", response_class=HTMLResponse)
def index_dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})


@router.get("/catalogo", response_class=HTMLResponse)
def catalogo_page(request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("catalogo.html", {"request": request, "user": user})


@router.get("/solicitudes", response_class=HTMLResponse)
def solicitudes_page(request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("solicitudes.html", {"request": request, "user": user})


@router.get("/docente/bandeja", response_class=HTMLResponse)
def docente_bandeja_page(request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if user.rol.value != "docente":
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("docente_bandeja.html", {"request": request, "user": user})


@router.get("/responsable/bandeja", response_class=HTMLResponse)
def responsable_bandeja_page(request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if user.rol.value != "responsable":
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("responsable_bandeja.html", {"request": request, "user": user})


@router.get("/responsable/prestamos", response_class=HTMLResponse)
def responsable_prestamos_page(request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if user.rol.value not in ["responsable", "coordinacion"]:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("prestamos_gestion.html", {"request": request, "user": user})


@router.get("/responsable/novedades", response_class=HTMLResponse)
def responsable_novedades_page(request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if user.rol.value not in ["responsable", "coordinacion"]:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("novedades_gestion.html", {"request": request, "user": user})


@router.get("/mis-prestamos", response_class=HTMLResponse)
def mis_prestamos_page(request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("mis_prestamos.html", {"request": request, "user": user})


@router.get("/logout", response_class=HTMLResponse)
def logout_view(request: Request):
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key="access_token")
    return response

