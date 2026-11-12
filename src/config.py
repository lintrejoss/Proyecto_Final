import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Sistema de Préstamos de Herramientas y Equipos"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000

    # Base de datos
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/prestamos_db"

    # Seguridad JWT
    JWT_SECRET_KEY: str = "clave-secreta-de-desarrollo-cambiar-en-produccion-123456789"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 horas para uso universitario continuo

    # Zona horaria oficial del proyecto
    TIMEZONE: str = "America/Bogota"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

