# Checklist de seguridad del Pull Request
- [ ] El cambio tiene una descripción funcional y un alcance definido.
- [ ] Revisé que no se subieran credenciales, tokens ni archivos .env.
- [ ] El SAST fue ejecutado; interpreté hallazgos verdaderos y falsos positivos.
- [ ] Revisé dependencias y actualizaciones relevantes.
- [ ] Revisé autenticación y autorización si el cambio afecta APIs.
- [ ] Se ejecutaron pruebas funcionales y de regresión.
- [ ] Si hay DAST, fue sobre mi staging autorizado.
- [ ] Vinculé hallazgos, decisiones de mitigación y evidencias.
