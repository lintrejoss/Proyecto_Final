import os
import sys

# Agregar el directorio raíz al path para importar módulos de src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.database import SessionLocal, engine, Base
from src.models import (
    Usuario, RolUsuario,
    Recurso, CategoriaRecurso, CondicionRecurso
)
from src.auth.security import hash_password


def seed_database():
    print("--- INICIANDO CARGA DE DATOS SEMILLA ---")
    
    # 1. Crear tablas si no existen
    Base.metadata.create_all(bind=engine)
    print("✓ Tablas de base de datos verificadas/creadas.")

    db = SessionLocal()
    try:
        # 2. Usuarios semilla para los 4 perfiles requeridos
        usuarios_data = [
            {
                "email": "estudiante@universidad.edu.co",
                "password": "Estudiante123!",
                "nombre_completo": "Laura Méndez",
                "documento": "EST-2026-001",
                "rol": RolUsuario.ESTUDIANTE
            },
            {
                "email": "docente@universidad.edu.co",
                "password": "Docente123!",
                "nombre_completo": "Prof. Carlos Ruiz",
                "documento": "DOC-1082-993",
                "rol": RolUsuario.DOCENTE
            },
            {
                "email": "responsable@universidad.edu.co",
                "password": "Responsable123!",
                "nombre_completo": "Marta Gómez (Laboratorio)",
                "documento": "LAB-0045-812",
                "rol": RolUsuario.RESPONSABLE
            },
            {
                "email": "coordinacion@universidad.edu.co",
                "password": "Coordinacion123!",
                "nombre_completo": "Dr. Fernando Ospina",
                "documento": "CRD-0012-745",
                "rol": RolUsuario.COORDINACION
            }
        ]

        for u in usuarios_data:
            existente = db.query(Usuario).filter(Usuario.email == u["email"]).first()
            if not existente:
                nuevo_usuario = Usuario(
                    email=u["email"],
                    password_hash=hash_password(u["password"]),
                    nombre_completo=u["nombre_completo"],
                    documento=u["documento"],
                    rol=u["rol"],
                    activo=True
                )
                db.add(nuevo_usuario)
                print(f"✓ Usuario creado: {u['nombre_completo']} ({u['rol'].value}) -> {u['email']}")
            else:
                print(f"• Usuario ya existente: {u['email']}")

        # 3. Recursos semilla iniciales (Herramientas y Equipos)
        recursos_data = [
            {
                "codigo": "HER-001",
                "nombre": "Multímetro Digital Industrial",
                "categoria": CategoriaRecurso.HERRAMIENTA,
                "marca": "Fluke",
                "modelo": "87V",
                "serie": "FLK-87V-9421",
                "condicion": CondicionRecurso.HABILITADO,
                "ubicacion": "Mesa de Electrónica - Lab 1"
            },
            {
                "codigo": "HER-002",
                "nombre": "Osciloscopio Digital 4 Canales",
                "categoria": CategoriaRecurso.HERRAMIENTA,
                "marca": "Rigol",
                "modelo": "DS1054Z",
                "serie": "RGL-DS-7712",
                "condicion": CondicionRecurso.HABILITADO,
                "ubicacion": "Mesa de Medición - Lab 1"
            },
            {
                "codigo": "HER-003",
                "nombre": "Kit de Destornilladores de Precisión",
                "categoria": CategoriaRecurso.HERRAMIENTA,
                "marca": "iFixit",
                "modelo": "Pro Tech Toolkit",
                "serie": "IFX-PT-3301",
                "condicion": CondicionRecurso.HABILITADO,
                "ubicacion": "Armario A - Cajón 2"
            },
            {
                "codigo": "HER-004",
                "nombre": "Estación de Soldadura Digital",
                "categoria": CategoriaRecurso.HERRAMIENTA,
                "marca": "Weller",
                "modelo": "WE1010",
                "serie": "WLL-WE-4409",
                "condicion": CondicionRecurso.HABILITADO,
                "ubicacion": "Mesa de Soldadura - Lab 1"
            },
            {
                "codigo": "EQP-001",
                "nombre": "Proyector Multimedia Full HD",
                "categoria": CategoriaRecurso.EQUIPO,
                "marca": "Epson",
                "modelo": "PowerLite 2247U",
                "serie": "EPS-PL-8812",
                "condicion": CondicionRecurso.HABILITADO,
                "ubicacion": "Almacén Central Audiovisuales"
            },
            {
                "codigo": "EQP-002",
                "nombre": "Laptop de Desarrollo Móvil",
                "categoria": CategoriaRecurso.EQUIPO,
                "marca": "Dell",
                "modelo": "Latitude 5420",
                "serie": "DLL-LT-6523",
                "condicion": CondicionRecurso.HABILITADO,
                "ubicacion": "Gabinete de Cómputo"
            },
            {
                "codigo": "EQP-003",
                "nombre": "Generador de Funciones Arbitrarias",
                "categoria": CategoriaRecurso.EQUIPO,
                "marca": "Siglent",
                "modelo": "SDG1032X",
                "serie": "SGL-SD-5019",
                "condicion": CondicionRecurso.HABILITADO,
                "ubicacion": "Mesa de Medición - Lab 1"
            },
            {
                "codigo": "EQP-004",
                "nombre": "Cámara Termográfica de Diagnóstico",
                "categoria": CategoriaRecurso.EQUIPO,
                "marca": "FLIR",
                "modelo": "E4 WiFi",
                "serie": "FLR-E4-1184",
                "condicion": CondicionRecurso.HABILITADO,
                "ubicacion": "Caja Fuerte de Equipos Especiales"
            }
        ]

        for r in recursos_data:
            existente = db.query(Recurso).filter(Recurso.codigo == r["codigo"]).first()
            if not existente:
                nuevo_recurso = Recurso(
                    codigo=r["codigo"],
                    nombre=r["nombre"],
                    categoria=r["categoria"],
                    marca=r["marca"],
                    modelo=r["modelo"],
                    serie=r["serie"],
                    condicion=r["condicion"],
                    ubicacion=r["ubicacion"]
                )
                db.add(nuevo_recurso)
                print(f"✓ Recurso creado: [{r['codigo']}] {r['nombre']} ({r['categoria'].value})")
            else:
                print(f"• Recurso ya existente: {r['codigo']}")

        db.commit()
        print("--- CARGA DE DATOS SEMILLA FINALIZADA CON ÉXITO ---")
    except Exception as e:
        db.rollback()
        print(f"❌ Error durante la carga de datos semilla: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()

