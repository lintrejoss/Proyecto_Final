# Especificación de Requisitos y Reglas de Negocio

Este documento define los Requisitos Funcionales (RF), Requisitos No Funcionales (RNF), Reglas de Negocio (RN) y Criterios de Aceptación (CA) del **Sistema de Préstamos de Herramientas y Equipos**.

---

## 1. Criterios de Aceptación Obligatorios (Guía)

- **CA-01 (Consulta y Disponibilidad Coherente)**: Los usuarios autorizados pueden consultar recursos y su disponibilidad coherente en el tiempo con las asignaciones y reservas registradas.
- **CA-02 (Registro y Persistencia de Solicitudes)**: El solicitante puede registrar solicitudes que se almacenan de forma persistente y recuperarlas desde la aplicación en su sección personal.
- **CA-03 (Evaluación y Gestión)**: El personal docente y los responsables pueden evaluar, aprobar o rechazar solicitudes según los permisos de su rol.
- **CA-04 (Asignación y Entrega sin Conflictos)**: Se puede registrar la asignación y entrega física de los recursos solicitados, identificando solicitante y equipo, impidiendo entregas incompatibles o concurrentes.
- **CA-05 (Devolución e Historial)**: Se puede registrar la devolución formal con el estado físico de los recursos, conservando el historial y actualizando inmediatamente la disponibilidad.
- **CA-06 (Consolidación y Auditoría)**: Coordinación puede consultar información consolidada de recursos, préstamos, estados y responsables.

---

## 2. Reglas de Negocio Explícitas (RN)

| Código | Regla | Fuente | Detalle Operativo |
| :--- | :--- | :--- | :--- |
| **RN-01** | Fechas de Préstamo | [B] Profesor + [C] Equipo | La fecha de inicio debe ser estrictamente menor a la fecha fin (`inicio < fin`). No se permiten fechas de inicio en el pasado (con tolerancia de 5 min por envío). Se permiten solicitudes para fechas futuras sin límite de 24 horas. |
| **RN-02** | Aprobación Docente Obligatoria | [B] Profesor | Toda solicitud originada por un usuario con rol `estudiante` requiere el visto bueno de un usuario con rol `docente` antes de ser evaluada por el responsable. |
| **RN-03** | Solicitud Docente Directa | [C] Equipo | Una solicitud de un `docente` pasa directamente a estado `pendiente_responsable`, sin requerir visto bueno de otro docente. |
| **RN-04** | Reserva Firme | [C] Equipo | Ni la creación de la solicitud ni el visto bueno docente reservan recursos. La reserva solo se consolida cuando el `responsable` emite la aprobación final. |
| **RN-05** | Atención en Orden de Llegada (FIFO) | [B] Profesor + [C] Equipo | Las solicitudes se procesan por orden de creación (`creado_en`, `id`). El sistema impide aprobar una solicitud si existe una anterior en estado pendiente con solapamiento en al menos uno de sus recursos. |
| **RN-06** | Bloqueo por Préstamo Vencido | [B] Profesor | Un préstamo no devuelto cuya `fecha_fin` sea menor al instante actual se considera vencido. El sistema bloquea automáticamente la entrega de cualquier nuevo préstamo al solicitante infractor hasta la devolución del recurso pendiente. |
| **RN-07** | Inhabilitación por Daño o Faltante | [B] Profesor + [C] Equipo | Si en la devolución se registra una novedad de tipo `dano` o `faltante`, el recurso pasa a condición `no_disponible` y el usuario queda inhabilitado para crear nuevas solicitudes y recibir entregas. |
| **RN-08** | Rehabilitación Condicionada | [C] Equipo | La rehabilitación del usuario ocurre únicamente cuando el responsable resuelve todas las novedades abiertas que pesen sobre él. La habilitación del recurso físico es una decisión independiente. |
| **RN-09** | Cancelación Oportuna | [C] Equipo | El solicitante puede cancelar su solicitud en cualquier momento antes de la entrega física. Si estaba aprobada, se liberan las reservas asociadas. Un préstamo ya entregado no puede ser cancelado (debe devolverse). |
| **RN-10** | Unicidad e Integridad de Entrega | [A] Guía + [C] Equipo | La entrega se registra en bloque para todos los recursos de la solicitud, dentro del rango horario previsto, validando condición operativa y ausencia de sanciones. |

---

## 3. Requisitos Funcionales (RF)

- **RF-01 (Autenticación y Sesión)**: El sistema debe autenticar usuarios mediante correo y contraseña utilizando JWT Bearer, identificando su rol (`estudiante`, `docente`, `responsable`, `coordinacion`).
- **RF-02 (Catálogo con Disponibilidad por Fechas)**: Permite listar recursos filtrando por categoría, texto y rango de fechas $[inicio, fin)$, calculando si cada unidad está disponible, reservada o no operativa.
- **RF-03 (Registro de Solicitudes)**: Permite a estudiantes y docentes seleccionar unidades de herramientas y equipos, definir fechas de uso y motivo.
- **RF-04 (Mis Solicitudes y Cancelación)**: El solicitante puede visualizar el estado de sus solicitudes y cancelar solicitudes pendientes o aprobadas previas a la entrega.
- **RF-05 (Bandeja y Visto Bueno Docente)**: Los docentes pueden listar solicitudes de estudiantes pendientes de su aval, emitiendo visto bueno o rechazo fundamentado.
- **RF-06 (Bandeja y Aprobación de Responsable)**: El responsable puede revisar solicitudes pendientes, visualizar alertas de colisión y orden de llegada, y aprobar o rechazar con motivo.
- **RF-07 (Gestión de Entrega)**: El responsable registra la entrega física verificando que no existan préstamos vencidos ni inhabilitación, capturando observaciones del estado de salida.
- **RF-08 (Gestión de Devolución)**: El responsable registra la recepción física, estado de los ítems y genera novedades automáticas en caso de daño o faltante.
- **RF-09 (Gestión de Novedades y Sanciones)**: El responsable lista novedades abiertas, registra acuerdos/reparaciones y resuelve casos para rehabilitar usuarios.
- **RF-10 (Administración de Recursos)**: El responsable puede dar de alta, editar metadatos y cambiar la condición operativa de herramientas y equipos.
- **RF-11 (Panel de Préstamos Activos y Vencidos)**: Vista especializada para monitorear préstamos en curso y alertas rojas de vencimiento.
- **RF-12 (Consulta Consolidada de Coordinación)**: Vista gerencial para consultar historial, estadísticas y trazabilidad completa de eventos por usuario y recurso.

---

## 4. Requisitos No Funcionales (RNF)

- **RNF-01 (Seguridad y Roles)**: Validación obligatoria de JWT y verificación de permisos RBAC en cada endpoint del backend.
- **RNF-02 (Protección de Credenciales)**: Contraseñas hasheadas exclusivamente con Argon2. No se devuelven hashes en ninguna respuesta de la API.
- **RNF-03 (Concurrencia e Integridad Transaccional)**: Uso de transacciones atómicas con bloqueo pesimista (`FOR UPDATE`) en orden determinista de IDs para evitar reservas duplicadas en aprobaciones simultáneas.
- **RNF-04 (Persistencia)**: Base de datos relacional PostgreSQL gestionada con migraciones versionadas en Alembic.
- **RNF-05 (Manejo de Zona Horaria)**: Almacenamiento en instantes con zona horaria (UTC en base de datos) y serialización adecuada hacia la zona local `America/Bogota`.
- **RNF-06 (Frontend Ligero y Responsive)**: HTML5 semántico, CSS moderno y Vanilla JavaScript con `fetch`, adaptable a dispositivos móviles y escritorio sin bundlers.
- **RNF-07 (Manejo de Errores)**: Respuestas HTTP consistentes con códigos estándar (400, 401, 403, 404, 409, 422, 500) y mensajes legibles para el usuario.
- **RNF-08 (Auditoría)**: Registro de eventos clave (aprobación, rechazo, entrega, devolución, novedades) vinculando usuario actuante, fecha y hora.

