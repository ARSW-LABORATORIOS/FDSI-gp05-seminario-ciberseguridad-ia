# Checklist de seguridad del Pull Request
- [x] El cambio tiene una descripción funcional y un alcance definido.
- [x] Revisé que no se subieran credenciales, tokens ni archivos .env.
- [x] El SAST fue ejecutado; interpreté hallazgos verdaderos y falsos positivos.
- [x] Revisé dependencias y actualizaciones relevantes.
- [ ] Revisé autenticación y autorización si el cambio afecta APIs.
- [x] Se ejecutaron pruebas funcionales y de regresión.
- [x] Si hay DAST, fue sobre mi staging autorizado.
- [x] Vinculé hallazgos, decisiones de mitigación y evidencias.
