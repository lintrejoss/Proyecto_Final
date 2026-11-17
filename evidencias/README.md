# Registro de Evidencias Funcionales y Operativas

Este directorio almacena las evidencias reproducibles de funcionamiento de la aplicación, ejecución de pruebas automatizadas y consumo de la API REST del **Sistema de Préstamos de Herramientas y Equipos (MK.books)**, dando cumplimiento a la **Actividad 6** y los parámetros del informe (**Sección 8**) de la Guía **PF-03**.

---

## Contenido de Evidencias

1. [`pruebas_pytest.txt`](./pruebas_pytest.txt): Registro completo de ejecución de las **30 pruebas automatizadas** con `pytest -v`, cubriendo las 5 etapas del ciclo de vida del préstamo, seguridad, RBAC y casos límite.
2. [`endpoints_operacion.md`](./endpoints_operacion.md): Catálogo de solicitudes HTTP reales (cURL y respuestas JSON) que demuestran el ciclo completo:
   - Login y obtención de tokens JWT por rol.
   - Consulta de catálogo y cálculo temporal `[inicio, fin)`.
   - Creación de solicitudes (estudiante y docente).
   - Aval docente obligatorio y aprobación responsable con regla FIFO.
   - Entrega física con bloqueo estricto por préstamos vencidos [RN-06].
   - Devolución física, generación de novedades por daño [RN-07] e inhabilitación.
   - Resolución de casos y rehabilitación [RN-08].
   - Métricas y consulta consolidada de Coordinación [CA-06 / RF-12].
