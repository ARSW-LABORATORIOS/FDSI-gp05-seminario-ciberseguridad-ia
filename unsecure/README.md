# Arquitectura Unsecure

`main.py` tiene el esqueleto del backend sin controles. Le falta completar los TODO (conectar los documentos reales del curso y la API del LLM), pero la lógica y los comentarios de qué hace cada parte ya están.

Es la línea base del riesgo OWASP LLM10:2025 *Unbounded Consumption* que describe el [ADR-001](../docs/ADR-001-arquitectura-segura.md): sin login ni identidad, sin cuota, sin caché, sin perímetro y trayendo hasta 50 fragmentos del RAG por consulta. Existe a propósito para atacarla con las pruebas T01–T05 y comparar contra secure.

Ver diagrama en `/diagrams/unsecure.png`: usa las mismas zonas que el diagrama secure, y las capas que faltan aparecen vacías en rojo.
