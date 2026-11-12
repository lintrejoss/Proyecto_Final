# Sistema de Préstamos de Herramientas y Equipos

Aplicación web funcional monolítica modular para la gestión integral del ciclo de vida de préstamos de herramientas y equipos universitarios: consulta de disponibilidad en tiempo real, solicitudes persistentes, evaluación docente y de responsable con atención en orden estricto (FIFO), reservas atómicas con control de concurrencia, entregas controladas con bloqueo por préstamos vencidos, devoluciones con reporte de novedades físicas (daños/faltantes), inhabilitación temporal y panel consolidado para coordinación.

Desarrollado con **Python 3**, **FastAPI**, **PostgreSQL**, **SQLAlchemy 2.0**, **Alembic**, **Pydantic v2**, **Argon2** y frontend nativo con **HTML5, CSS y JavaScript** servido mediante **Jinja2**.

---

## 1. Pila Tecnológica

- **Backend**: Python 3.9+ con FastAPI.
- **ORM y Persistencia**: SQLAlchemy 2.0 (sesiones síncronas) y PostgreSQL (driver `psycopg2-binary`).
- **Migraciones de Base de Datos**: Alembic.
- **Validación de Datos**: Pydantic v2 y Pydantic Settings.
- **Seguridad**: JWT Bearer (`pyjwt[crypto]`) y hash de contraseñas con Argon2id (`argon2-cffi`).
- **Frontend**: HTML5 semántico, CSS moderno y Vanilla JavaScript con `fetch` API. Sin frameworks JS ni herramientas de compilación externas.
- **Zona Horaria**: UTC en almacenamiento / `America/Bogota` (Colombia) para entrada y visualización.

---

## 2. Instalación y Puesta en Marcha

### Prerrequisitos
- Python 3.9 o superior instalado.
- PostgreSQL (opcional para desarrollo local inmediato; incluye fallback a SQLite para pruebas rápidas).

### Paso 1: Clonar o ingresar al repositorio
```bash
cd "proyecto final"
```

### Paso 2: Crear y activar entorno virtual
En macOS / Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```
En Windows (PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### Paso 3: Instalar dependencias reproducibles
```bash
pip install -r requirements.txt
```

### Paso 4: Configurar variables de entorno
Copiar la plantilla `.env.example` como `.env`:
```bash
cp .env.example .env
```
Por defecto, `.env` está configurado para desarrollo inmediato. Si deseas conectar a PostgreSQL, ajusta `DATABASE_URL`:
```ini
DATABASE_URL="postgresql+psycopg2://postgres:tu_password@localhost:5432/prestamos_db"
```

### Paso 5: Ejecutar migraciones de base de datos
```bash
alembic upgrade head
```

### Paso 6: Cargar datos iniciales de prueba (Seed Data)
Crea las tablas y carga los usuarios institucionales y recursos iniciales con contraseñas hasheadas en Argon2:
```bash
python3 scripts/seed_data.py
```

### Paso 7: Iniciar el servidor web
```bash
uvicorn src.main:app --reload --port 8000
```
La aplicación estará disponible en:
- **Interfaz Web**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Documentación Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 3. Cuentas de Acceso para Demostración

| Rol | Correo Electrónico | Contraseña | Nombre | Documento |
| :--- | :--- | :--- | :--- | :--- |
| **Estudiante** | `estudiante@universidad.edu.co` | `Estudiante123!` | Laura Méndez | `EST-2026-001` |
| **Docente** | `docente@universidad.edu.co` | `Docente123!` | Prof. Carlos Ruiz | `DOC-1082-993` |
| **Responsable** | `responsable@universidad.edu.co` | `Responsable123!` | Marta Gómez (Lab) | `LAB-0045-812` |
| **Coordinación** | `coordinacion@universidad.edu.co` | `Coordinacion123!` | Dr. Fernando Ospina | `CRD-0012-745` |

*(La pantalla de inicio de sesión incluye botones de acceso rápido que precargan automáticamente estas credenciales)*.

---

## 4. Ejecución de Pruebas Unitarias y Funcionales

Ejecutar la suite de pruebas automatizadas:
```bash
python3 tests/test_etapa1_auth.py
```

---

## 5. Estructura de Documentación

- [`docs/requisitos.md`](docs/requisitos.md): Requisitos funcionales, no funcionales y reglas de negocio explícitas con fuente.
- [`docs/diseno.md`](docs/diseno.md): Diagramas de componentes, modelo relacional, máquinas de estado y concurrencia.
- [`docs/decisiones.md`](docs/decisiones.md): Registro formal de decisiones de arquitectura (ADR) clasificadas por fuente (Guía, Profesor, Equipo).
- [`docs/pruebas.md`](docs/pruebas.md): Matriz de pruebas funcionales y casos límite.
- [`docs/trazabilidad.md`](docs/trazabilidad.md): Matriz de trazabilidad Requisitos vs. Código vs. Pruebas.

