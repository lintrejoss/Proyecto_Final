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

## 3. Pruebas de la Etapa 3: Evaluación Docente, Aprobación de Responsable y Orden FIFO

| ID Prueba | Requisito | Descripción | Precondiciones | Datos de Entrada | Resultado Esperado | Estado | Código HTTP |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-16** | RN-02, RF-05 | Visto bueno docente a solicitud | Solicitud en `pendiente_docente` | POST `/evaluar-docente` con `aprobado: true` | Pasa a `pendiente_responsable` y registra docente evaluador | **PASÓ** | 200 OK |
| **TC-17** | RN-02, RF-05 | Rechazo docente con motivo | Solicitud en `pendiente_docente` | POST `/evaluar-docente` con `aprobado: false` y motivo | Pasa a `rechazada` con motivo registrado | **PASÓ** | 200 OK |
| **TC-18** | RN-04, RF-06 | Aprobación de responsable y reserva | Solicitud en `pendiente_responsable` | POST `/evaluar-responsable` con `aprobado: true` | Pasa a `aprobada`, crea reserva firme y actualiza disponibilidad | **PASÓ** | 200 OK |
| **TC-19** | RN-05, RNF-03 | Bloqueo por orden de llegada (FIFO) | Solicitud 1 y 2 compiten por recursos | Intento de aprobar Solicitud 2 (posterior) | HTTP 422 Unprocessable Entity indicando prioridad de Solicitud 1 | **PASÓ** | 422 Unprocessable |
| **TC-20** | RN-05, RF-06 | Desbloqueo FIFO tras rechazo previo | Solicitud 1 rechazada por docente | Aprobación de Solicitud 2 (posterior) | Aprobación exitosa (HTTP 200) tras desaparecer el bloqueo | **PASÓ** | 200 OK |
| **TC-21** | DEC-006, RNF-03 | Bloqueo por condición no disponible | Recurso marcado `no_disponible` | Intento de aprobación por responsable | HTTP 409 Conflict impidiendo reservar equipo dañado | **PASÓ** | 409 Conflict |

---

## 4. Pruebas Planificadas para Etapas Posteriores

- **TC-22 (Etapa 4)**: Entrega física bloqueada si el solicitante tiene un préstamo vencido (RN-06).
- **TC-23 (Etapa 4)**: Devolución con daño/faltante genera novedad automática e inhabilita a la persona (RN-07).
- **TC-24 (Etapa 4)**: Devolución a tiempo libera recursos para uso inmediato y conserva reservas futuras.
- **TC-25 (Etapa 4)**: Resolución de novedad y rehabilitación condicionada (RN-08).
- **TC-26 (Etapa 5)**: Consulta consolidada de coordinación con auditoría completa (CA-06, RF-12).

