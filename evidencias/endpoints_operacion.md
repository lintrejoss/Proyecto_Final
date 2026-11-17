# Evidencias de Operación y Consumo de la API REST

Evidencias de solicitudes y respuestas reales sobre la API REST expuesta en `/api/v1`, conforme a la **Actividad 6** y los parámetros del informe (**Sección 8, Numeral 6 y 7**) de la Guía **PF-03**.

---

## 1. Autenticación y Emisión de JWT (RF-01)

### Solicitud de Login (Paulina Trejos - Estudiante)
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=estudiante@universidad.edu.co&password=Estudiante123!"
```

**Respuesta Exitosa (HTTP 200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "usuario": {
    "id": 1,
    "email": "estudiante@universidad.edu.co",
    "nombre_completo": "Paulina Trejos",
    "documento": "EST-2026-001",
    "rol": "estudiante"
  }
}
```

---

## 2. Consulta de Disponibilidad Temporal [inicio, fin) (CA-01)

### Consulta de Disponibilidad de Herramienta para Fechas Futuras
```bash
curl -X GET "http://localhost:8000/api/v1/recursos/1/disponibilidad?fecha_inicio=2026-11-20T08:00:00Z&fecha_fin=2026-11-20T12:00:00Z" \
  -H "Authorization: Bearer <TOKEN_ESTUDIANTE>"
```

**Respuesta Exitosa (HTTP 200 OK):**
```json
{
  "recurso_id": 1,
  "codigo": "HER-001",
  "nombre": "Multímetro Digital Industrial",
  "condicion": "habilitado",
  "disponible": true,
  "motivo": null
}
```

---

## 3. Registro de Solicitud de Préstamo (CA-02 / RF-03)

### Solicitud de Estudiante (Requiere Aval Docente - RN-02)
```bash
curl -X POST "http://localhost:8000/api/v1/solicitudes" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN_ESTUDIANTE>" \
  -d '{
    "fecha_inicio": "2026-11-20T08:00:00Z",
    "fecha_fin": "2026-11-20T12:00:00Z",
    "motivo": "Práctica de circuitos y medición de señales",
    "recurso_ids": [1]
  }'
```

**Respuesta Exitosa (HTTP 201 Created):**
```json
{
  "id": 14,
  "solicitante_id": 1,
  "fecha_inicio": "2026-11-20T08:00:00Z",
  "fecha_fin": "2026-11-20T12:00:00Z",
  "motivo": "Práctica de circuitos y medición de señales",
  "estado": "pendiente_docente",
  "recursos": [
    {
      "id": 1,
      "codigo": "HER-001",
      "nombre": "Multímetro Digital Industrial",
      "categoria": "herramienta"
    }
  ]
}
```

---

## 4. Evaluación Docente y Aprobación Responsable con Regla FIFO (CA-03 / RN-05)

### Visto Bueno Docente (Prof. Carlos Ruiz)
```bash
curl -X POST "http://localhost:8000/api/v1/solicitudes/14/evaluar-docente" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN_DOCENTE>" \
  -d '{"aprobado": true}'
```

**Respuesta (HTTP 200 OK):**
Pasa el estado a `pendiente_responsable`.

### Aprobación Final de Responsable (Marta Gómez - Consolida Reserva Firme)
```bash
curl -X POST "http://localhost:8000/api/v1/solicitudes/14/evaluar-responsable" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN_RESPONSABLE>" \
  -d '{"aprobado": true}'
```

**Respuesta (HTTP 200 OK):**
Estado pasa a `aprobada` tras validar que no existan colisiones ni violaciones a la cola de llegada FIFO (`SELECT ... FOR UPDATE`).

---

## 5. Entrega Física y Validación de Mora (CA-04 / RN-06 / RF-07)

### Intento de Entrega Física con Préstamo Vencido Activo (Bloqueo Institucional)
```bash
curl -X POST "http://localhost:8000/api/v1/prestamos/entregar" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN_RESPONSABLE>" \
  -d '{"solicitud_id": 14, "observaciones": "Entrega con funda"}'
```

**Respuesta de Bloqueo por Regla Institucional (HTTP 422 Unprocessable Content):**
```json
{
  "detail": "El solicitante tiene el préstamo #2 vencido (fecha límite: 2026-11-15 10:00). Según la regla institucional del profesor [RN-06], debe devolver todo recurso adeudado antes de recibir otro."
}
```

---

## 6. Devolución con Daño e Inhabilitación (CA-05 / RN-07 / RF-08)

### Registro de Devolución con Pantalla Rota
```bash
curl -X POST "http://localhost:8000/api/v1/prestamos/5/devolver" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN_RESPONSABLE>" \
  -d '{
    "observaciones": "Devolución con daño",
    "items": [
      {
        "recurso_id": 1,
        "estado_fisico": "dano",
        "descripcion_novedad": "Pantalla LCD estrellada por caída accidental"
      }
    ]
  }'
```

**Resultado:**
- El préstamo pasa a `devuelto`.
- El recurso `HER-001` pasa a condición `no_disponible`.
- Se crea la `Novedad #3` no resuelta.
- El estudiante queda inhabilitado para crear nuevas solicitudes (recibe `HTTP 403 Forbidden`).

---

## 7. Consulta Consolidada de Coordinación (CA-06 / RF-12)

### Obtención de Métricas y KPIs Institucionales
```bash
curl -X GET "http://localhost:8000/api/v1/reportes/metricas" \
  -H "Authorization: Bearer <TOKEN_COORDINACION>"
```

**Respuesta Exitosa (HTTP 200 OK):**
```json
{
  "total_prestamos": 12,
  "prestamos_activos": 3,
  "prestamos_vencidos": 1,
  "prestamos_devueltos": 9,
  "tasa_cumplimiento": 88.89,
  "total_recursos": 8,
  "recursos_no_disponibles": 1,
  "total_novedades_abiertas": 1,
  "recursos_mas_prestados": [
    {"codigo": "HER-001", "nombre": "Multímetro Digital Industrial", "total_prestamos": 5},
    {"codigo": "EQP-002", "nombre": "Laptop de Desarrollo Móvil", "total_prestamos": 4}
  ]
}
```
