"""
Comprueba el aislamiento desde DENTRO del orquestador, como si un atacante ya lo hubiera
comprometido: no debe poder salir a internet, ni llegar a otros servicios, ni usar
herramientas no aprobadas. Se ejecuta en el contenedor del orquestador:

    docker compose exec -T orquestador python - < pruebas/aislamiento.py
"""

import asyncio
import socket
import sys

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

fallos = 0


def comprobar(nombre, condicion, detalle=""):
    global fallos
    fallos += 0 if condicion else 1
    print(f"[{'OK' if condicion else 'FALLA'}] {nombre}" + (f"  ({detalle})" if detalle else ""), flush=True)


def alcanza(host: str, puerto: int) -> bool:
    try:
        socket.create_connection((host, puerto), timeout=3).close()
        return True
    except OSError:
        return False


print("--- Red privada ---")
comprobar("El orquestador no sale a internet", not alcanza("1.1.1.1", 443))
comprobar("El orquestador no resuelve dominios externos", not alcanza("google.com", 443))
comprobar("El orquestador no llega a Valkey", not alcanza("valkey", 6379))
comprobar("El orquestador no llega al proveedor directamente", not alcanza("mock-llm", 9000))
comprobar("El orquestador sí llega a LiteLLM", alcanza("litellm", 4000))
comprobar("El orquestador sí llega a agentgateway", alcanza("agentgateway", 3000))


async def herramientas():
    print("--- Herramientas MCP ---")
    async with streamablehttp_client("http://agentgateway:3000/mcp") as (leer, escribir, _):
        async with ClientSession(leer, escribir) as s:
            await s.initialize()
            nombres = sorted(t.name for t in (await s.list_tools()).tools)
            comprobar("El gateway solo muestra herramientas aprobadas", "borrar_indice" not in nombres and "buscar_documentos" in nombres, str(nombres))
            aprobada = await s.call_tool("listar_documentos", {})
            comprobar("Una herramienta aprobada funciona", not aprobada.isError)


def llamar_directo():
    """HTTP crudo: el cliente MCP revienta con el 400 del gateway, y aquí interesa ver la respuesta."""
    url = "http://agentgateway:3000/mcp"
    cabeceras = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    r = httpx.post(url, headers=cabeceras, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "prueba", "version": "1"}}})
    sesion = r.headers.get("mcp-session-id")
    if sesion:
        cabeceras["Mcp-Session-Id"] = sesion
    httpx.post(url, headers=cabeceras, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    r = httpx.post(url, headers=cabeceras, json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "borrar_indice", "arguments": {}}})
    ejecutada = "ALERTA" in r.text
    comprobar("Llamar una herramienta no aprobada se rechaza y no se ejecuta", not ejecutada and (r.status_code >= 400 or "error" in r.text),
              f"estado {r.status_code}: {r.text[:90]}")


asyncio.run(herramientas())
llamar_directo()
print(f"\n{'Todo bien' if not fallos else f'{fallos} comprobaciones fallaron'}")
sys.exit(1 if fallos else 0)
