from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from src.config import settings
from src.database import engine, Base
import src.models  # Registra todos los modelos ORM en Base.metadata
from src.routers import auth_router, views_router

app = FastAPI(
    title=settings.APP_NAME,
    description="API REST y Vistas Web para la Gestión del Ciclo de Vida de Préstamos Universitarios",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Archivos estáticos
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# Registro de routers de API REST y vistas web
app.include_router(views_router.router)
app.include_router(auth_router.router)


@app.get("/api/v1/health", tags=["Sistema"])
def health_check():
    """Endpoint de verificación de estado y conectividad del servicio."""
    return {
        "status": "online",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "timezone": settings.TIMEZONE
    }


@app.on_event("startup")
def on_startup():
    """
    Inicialización de tablas de base de datos en caso de no existir.
    Garantiza que la base de datos quede lista para uso inmediato.
    """
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        # Si la base de datos externa aún no está levantada o configurada,
        # la aplicación iniciará informando el estado.
        print(f"[ALERTA DE INICIO] Error al conectar/crear tablas en base de datos: {e}")

