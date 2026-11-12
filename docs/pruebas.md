# Matriz de Pruebas Funcionales y Casos de Prueba

Este documento registra los casos de prueba del **Sistema de Préstamos de Herramientas y Equipos**, organizados por etapas funcionales.

---

## Convenciones de Estado de Pruebas
- **[PASÓ]**: Caso ejecutado y validado en el entorno de desarrollo con evidencia.
- **[PENDIENTE]**: Caso diseñado pendiente de implementación de la etapa correspondiente.
- **[FALLÓ]**: Error detectado en ejecución.

---

## 1. Pruebas de la Etapa 1: Autenticación, Roles y Acceso

| ID Prueba | Requisito | Descripción | Precondiciones | Datos de Entrada | Resultado Esperado | Estado | Código HTTP |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-01** | RNF-07 | Health check del sistema | Servicio activo | GET `/api/v1/health` | HTTP 200 con JSON `{"status": "online"}` | **PASÓ** | 200 OK |
| **TC-02** | RNF-02 | Verificación de hash Argon2id | Módulo `security` | Hash y verificación con string plano | Hash inicia con `$argon2id$`, coincide con password original y rechaza incorrecto | **PASÓ** | N/A |
| **TC-03** | RF-01 | Login exitoso para los 4 roles | Usuarios semilla cargados | Correo y pass de Estudiante, Docente, Responsable, Coordinación | HTTP 200, JWT emitido con claims de usuario y rol | **PASÓ** | 200 OK |
| **TC-04** | RF-01 | Bloqueo por credenciales inválidas | Usuario existe en DB | Password incorrecto | HTTP 401 Unauthorized con mensaje de error | **PASÓ** | 401 Unauthorized |
| **TC-05** | RF-01 | Consulta de `/auth/me` con token válido | Token JWT activo | Header `Authorization: Bearer <token>` | HTTP 200 con datos del usuario sin exponer `password_hash` | **PASÓ** | 200 OK |
| **TC-06** | RNF-01 | Rechazo de `/auth/me` sin token | Sin sesión | GET `/api/v1/auth/me` sin headers | HTTP 401 Unauthorized | **PASÓ** | 401 Unauthorized |
| **TC-07** | RNF-06 | Redirección de `/` a `/login` sin sesión | Sin cookie ni token | GET `/` | HTTP 302 Redirect hacia `/login` | **PASÓ** | 302 Found |
| **TC-08** | RNF-06 | Acceso al panel `/` con sesión iniciada | Cookie `access_token` presente | GET `/` | HTTP 200 renderizando plantilla con nombre y rol | **PASÓ** | 200 OK |

---

## 2. Pruebas de la Etapa 2: Recursos, Catálogo y Solicitudes Persistidas

| ID Prueba | Requisito | Descripción | Precondiciones | Datos de Entrada | Resultado Esperado | Estado | Código HTTP |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-09** | CA-01, RF-02 | Consulta de catálogo y filtros | Token activo | GET `/api/v1/recursos?categoria=herramienta&busqueda=Fluke` | HTTP 200 con lista filtrada y cálculo de disponibilidad | **PASÓ** | 200 OK |
| **TC-10** | CA-02, RF-03 | Solicitud persistente estudiante | Rol `estudiante`, no sancionado | POST `/api/v1/solicitudes` con recurso ID 1, fechas futuras | HTTP 201 en estado `pendiente_docente` (RN-02) | **PASÓ** | 201 Created |
| **TC-11** | RN-03, RF-03 | Solicitud persistente docente | Rol `docente` | POST `/api/v1/solicitudes` con recurso ID 2, fechas futuras | HTTP 201 en estado `pendiente_responsable` directo (RN-03) | **PASÓ** | 201 Created |
| **TC-12** | RN-01, RNF-07 | Validación de fechas inconsistentes | Token activo | `fecha_inicio >= fecha_fin` | HTTP 422 Unprocessable Entity con detalle del error | **PASÓ** | 422 Unprocessable |
| **TC-13** | RN-01, RNF-07 | Rechazo de fechas en el pasado | Token activo | `fecha_inicio < ahora` | HTTP 422 Unprocessable Entity | **PASÓ** | 422 Unprocessable |
| **TC-14** | RN-09, RF-04 | Cancelación oportuna por solicitante | Solicitud en estado pendiente | POST `/api/v1/solicitudes/{id}/cancelar` con motivo | HTTP 200 con estado `cancelada` y motivo registrado | **PASÓ** | 200 OK |
| **TC-15** | RN-07, RF-03 | Bloqueo de solicitud por inhabilitación | Novedad de daño abierta en DB | Intento de POST `/api/v1/solicitudes` | HTTP 403 Forbidden indicando inhabilitación activa | **PASÓ** | 403 Forbidden |

---

## 3. Pruebas Planificadas para Etapas Posteriores

- **TC-16 (Etapa 3)**: Visto bueno de docente a solicitud de estudiante (`pendiente_docente` -> `pendiente_responsable`).
- **TC-17 (Etapa 3)**: Bloqueo de aprobación por solicitud previa pendiente (FIFO estricto).
- **TC-18 (Etapa 3)**: Bloqueo pesimista `FOR UPDATE` en orden estable para reservas concurrentes.
- **TC-19 (Etapa 4)**: Entrega física bloqueada por usuario con préstamo vencido.
- **TC-20 (Etapa 4)**: Devolución con daño/faltante genera novedad e inhabilitación.
- **TC-21 (Etapa 4)**: Devolución exitosa libera disponibilidad inmediata y preserva reservas futuras.
- **TC-22 (Etapa 5)**: Consulta consolidada de coordinación con auditoría completa.

