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

## 2. Pruebas Planificadas para Etapas Posteriores

- **TC-09 (Etapa 2)**: Catálogo y disponibilidad por fechas sin cruce de intervalos.
- **TC-10 (Etapa 2)**: Creación de solicitud con datos válidos (`inicio < fin`).
- **TC-11 (Etapa 2)**: Rechazo de solicitud con fechas inválidas o en el pasado.
- **TC-12 (Etapa 3)**: Visto bueno de docente obligatorio para estudiantes.
- **TC-13 (Etapa 3)**: Solicitud de docente sin aval previo pasa a responsable.
- **TC-14 (Etapa 3)**: Bloqueo de aprobación por solicitud previa pendiente (FIFO estricto).
- **TC-15 (Etapa 3)**: Dos aprobaciones concurrentes del mismo recurso (Bloqueo pesimista `FOR UPDATE`).
- **TC-16 (Etapa 4)**: Entrega física bloqueada por usuario con préstamo vencido.
- **TC-17 (Etapa 4)**: Devolución con daño/faltante genera novedad e inhabilitación.
- **TC-18 (Etapa 4)**: Devolución exitosa libera disponibilidad inmediata y preserva reservas futuras.
- **TC-19 (Etapa 5)**: Consulta consolidada de coordinación con auditoría completa.

