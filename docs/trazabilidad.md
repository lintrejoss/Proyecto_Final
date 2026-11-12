# Matriz de Trazabilidad de Requisitos

Esta matriz vincula cada requisito funcional (RF), requisito no funcional (RNF) y regla de negocio (RN) con su fuente, su componente de código en la arquitectura y sus pruebas de verificación.

| Código Requisito | Descripción | Fuente | Componente / Archivo | Casos de Prueba | Estado |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CA-01** | Disponibilidad coherente por fechas | [A] Guía | `src/models/recurso.py`, `src/services/recurso_service.py` | TC-09 | Diseñado |
| **CA-02** | Solicitud persistente y recuperable | [A] Guía | `src/models/solicitud.py`, `src/routers/solicitudes_router.py` | TC-10 | Diseñado |
| **CA-03** | Evaluación y gestión docente/responsable | [A] Guía | `src/routers/solicitudes_router.py`, `src/auth/dependencies.py` | TC-12, TC-14 | Diseñado |
| **CA-04** | Asignación y entrega sin conflictos | [A] Guía | `src/models/prestamo.py`, `src/services/prestamo_service.py` | TC-15, TC-16 | Diseñado |
| **CA-05** | Devolución, historial y novedades | [A] Guía | `src/models/novedad.py`, `src/routers/prestamos_router.py` | TC-17, TC-18 | Diseñado |
| **CA-06** | Consulta consolidada de coordinación | [A] Guía | `src/routers/reportes_router.py`, `src/templates/reportes.html` | TC-19 | Diseñado |
| **RF-01** | Autenticación con JWT Bearer y Argon2 | [A] Guía + [C] Equipo | `src/auth/security.py`, `src/routers/auth_router.py` | TC-02, TC-03, TC-04, TC-05 | **Implementado** |
| **RNF-01** | Control de acceso basado en roles (RBAC) | [A] Guía | `src/auth/dependencies.py` (`require_roles`) | TC-06, TC-08 | **Implementado** |
| **RNF-02** | No almacenar contraseñas en texto plano ni exponer hashes | [A] Guía | `src/auth/security.py`, `src/schemas/auth.py` | TC-02, TC-05 | **Implementado** |
| **RNF-04** | Base de datos relacional y migraciones | [A] Guía + [C] Equipo | `src/database.py`, `alembic/`, `src/models/` | TC-01 | **Implementado** |
| **RNF-05** | Zona horaria America/Bogota | [A] Guía + [C] Equipo | `src/config.py`, `src/models/base.py`, `src/static/js/api.js` | TC-01 | **Implementado** |
| **RNF-06** | Interfaz responsive sin compiladores | [C] Equipo | `src/templates/`, `src/static/css/style.css` | TC-07, TC-08 | **Implementado** |

