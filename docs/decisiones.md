# Registro de Decisiones de Arquitectura y Negocio (ADR)

Este documento registra formalmente las decisiones tomadas para el desarrollo del **Sistema de Préstamos de Herramientas y Equipos**, clasificadas según la jerarquía de fuentes:
- **[A] Obligación de la Guía**
- **[B] Respuesta Confirmada del Profesor**
- **[C] Propuesta / Decisión del Equipo** *(No atribuir al profesor ni a la guía)*

---

### DEC-001: Eliminación del límite de 24 horas y cálculo de duraciones
- **Fuente**: [B] Respuesta Confirmada del Profesor.
- **Contexto**: El borrador inicial mencionaba una restricción máxima de 24 horas para préstamos.
- **Decisión**: Se elimina completamente la restricción de 24 horas. Los préstamos se definen con intervalos donde `fecha_inicio < fecha_fin`. Se permite solicitar para fechas futuras.
- **Consecuencia**: Las reservas pueden durar días o semanas según el requerimiento académico.

---

### DEC-002: Identificación unitaria de recursos y solicitudes conjuntas
- **Fuente**: [C] Propuesta del Equipo.
- **Contexto**: Se requiere saber si los recursos se prestan por tipo, cantidad genérica o unidad física.
- **Decisión**:
  1. Cada herramienta o equipo se identifica individualmente con un `código interno único` y número de serie.
  2. Categorías base: `herramienta` y `equipo`.
  3. Una solicitud puede agrupar una o varias unidades específicas.
  4. La aprobación, entrega y devolución en este MVP se gestiona de forma conjunta para todos los ítems de la solicitud (no hay préstamos ni devoluciones parciales).
- **Consecuencia**: Se simplifica la integridad transaccional del MVP y se evita la complejidad de trazabilidad de ítems individuales desmembrados.

---

### DEC-003: Flujo de Aprobación Diferenciado (Estudiante vs. Docente)
- **Fuente**: [B] Respuesta Confirmada del Profesor + [C] Propuesta del Equipo.
- **Contexto**: El profesor confirmó que los préstamos a estudiantes deben contar con aprobación docente.
- **Decisión**:
  - **Solicitud de Estudiante**: Estado inicial `pendiente_docente`. Al recibir visto bueno de un docente, pasa a `pendiente_responsable`. Tras revisión del responsable pasa a `aprobada` (o `rechazada`).
  - **Solicitud de Docente**: Pasa directamente a `pendiente_responsable`.
  - Solo la aprobación final del **Responsable** crea reservas firmes sobre los recursos. El visto bueno docente es un aval académico preliminar que no reserva ni bloquea recursos.
- **Consecuencia**: Evita acaparamientos prematuros y cumple con la supervisión académica obligatoria.

---

### DEC-004: Orden Estricto de Atención (FIFO) y Bloqueo de Conflictos
- **Fuente**: [B] Respuesta Confirmada del Profesor + [C] Propuesta del Equipo.
- **Contexto**: El profesor confirmó que las solicitudes se atienden en orden de llegada.
- **Decisión**:
  - Las solicitudes se ordenan cronológicamente por `(creado_en ASC, id ASC)`.
  - Al evaluar una solicitud para aprobación, el sistema valida que **no existan solicitudes anteriores que sigan en estado pendiente (`pendiente_docente` o `pendiente_responsable`) con recursos y rangos de fechas superpuestos**.
  - Si una solicitud anterior bloqueante es rechazada o cancelada, deja de bloquear a las posteriores.
  - La interfaz muestra explícitamente el motivo: *"En espera por solicitud previa #X pendiente"*.
- **Consecuencia**: Se garantiza equidad algorítmica sin depender del criterio subjetivo del evaluador.

---

### DEC-005: Modelo de Intervalos de Reserva $[t_{\text{inicio}}, t_{\text{fin}})$
- **Fuente**: [C] Propuesta del Equipo.
- **Contexto**: Determinación matemática de colisión de fechas entre préstamos/reservas.
- **Decisión**:
  - Intervalos semiabiertos $[inicio, fin)$: Dos intervalos $A$ y $B$ colisionan si y solo si:
    $$inicio_A < fin_B \quad \land \quad inicio_B < fin_A$$
  - Esto permite que un recurso sea devuelto a las 14:00 y entregado inmediatamente a otro usuario a las 14:00 sin generar falso conflicto.
  - No se contempla tiempo muerto de mantenimiento en el MVP.
- **Consecuencia**: Precisión matemática en la disponibilidad y reservas.

---

### DEC-006: Separación de Condición Operativa, Disponibilidad Temporal y Sanciones
- **Fuente**: [C] Propuesta del Equipo.
- **Contexto**: Evitar el antipatrón de un único booleano `esta_disponible`.
- **Decisión**:
  1. **Condición Operativa del Recurso** (`condicion`): `habilitado`, `no_disponible`, `dado_de_baja`.
  2. **Disponibilidad Temporal**: Calculada dinámicamente evaluando si en el rango $[inicio, fin)$ no existen reservas aprobadas ni préstamos activos superpuestos, y si la condición operativa es `habilitado`.
  3. **Inhabilitación del Usuario**: Calculada a partir de la presencia de novedades abiertas (`resuelta = False`) de tipo `dano` o `faltante`.
- **Consecuencia**: Un equipo prestado hoy puede reservarse para el próximo lunes sin inconsistencias; un usuario sancionado no puede solicitar ni recibir entregas.

---

### DEC-007: Bloqueo de Nuevos Préstamos por Vencimiento
- **Fuente**: [B] Respuesta Confirmada del Profesor.
- **Contexto**: Control de usuarios morosos.
- **Decisión**:
  - Un préstamo está `vencido` si `fecha_devolucion_real IS NULL` y `hora_actual > fecha_fin`.
  - Se calcula al vuelo en base a fechas (sin necesidad de cron jobs o tareas en background).
  - Si un usuario tiene al menos un préstamo vencido, el sistema **bloquea la entrega de nuevos préstamos**, exigiendo la devolución previa del recurso en mora.
  - Como decisión del equipo, se le permite registrar solicitudes futuras para planificación, pero no podrá materializar entregas hasta ponerse al día.
- **Consecuencia**: Cumplimiento estricto de la regla del profesor sin sobreingeniería de procesos asíncronos.

---

### DEC-008: Concurrencia y Transacciones con Bloqueo Pesimista
- **Fuente**: [A] Integridad y Concurrencia + [C] Propuesta del Equipo.
- **Contexto**: Evitar condiciones de carrera (doble reserva simultánea del mismo equipo por dos evaluadores).
- **Decisión**:
  - Toda operación de aprobación, entrega y devolución se ejecuta dentro de una transacción `with db.begin():`.
  - Para aprobación: se ordenan los IDs de los recursos `ORDER BY id ASC` y se ejecuta `SELECT ... FOR UPDATE` sobre la tabla de recursos antes de recalcular solapamientos.
- **Consecuencia**: Evita interbloqueos (deadlocks) por orden estable y previene el sobreagendamiento concurrente.

---

### DEC-009: Arquitectura Monolítica Modular y Autenticación
- **Fuente**: [A] Guía / Decisión de Pila.
- **Contexto**: Simplicidad de despliegue y desarrollo reproducible para entorno académico.
- **Decisión**:
  - Monolito FastAPI sirviendo API REST en `/api/v1` y vistas HTML con Jinja2 en `/`.
  - Autenticación con JWT Bearer almacenado en el frontend (localStorage / header Authorization), con decodificación y validación de rol estrictamente en el backend.
  - Contraseñas procesadas mediante Argon2 (`argon2-cffi`).
  - Base de datos relacional PostgreSQL con SQLAlchemy síncrono y soporte de configuración por variables de entorno (`.env`).
- **Consecuencia**: Fácil de ejecutar, depurar y sustentar sin requerir frameworks JS pesados ni microservicios innecesarios.

