# Pruebas

- `locustfile.py` — T01 (flooding), T04 (ráfaga multiusuario) y T05 (usuario legítimo bajo ataque). Se corre con Locust.
- `test_context_and_cache.py` — T02 (contexto masivo) y T03 (repetición para probar caché). Se corre directo con `python`.

Cada una se corre dos veces: una vez contra `unsecure` y otra contra `secure`, para poder comparar los números.
