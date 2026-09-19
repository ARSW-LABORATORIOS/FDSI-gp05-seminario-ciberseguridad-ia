"""
Esta parte es la que de verdad le habla al LLM. La dejamos separada del resto para
que tanto unsecure como secure llamen exactamente la misma función -- así cuando
comparemos las dos, la única diferencia real son los controles, no cómo se llama al modelo.
"""

import tiktoken

# TODO: elegir proveedor real (OpenAI, Claude, o algo local con Ollama) y poner la API key
# en un .env (nunca subir la key directo al código)


def count_tokens(text: str) -> int:
    """Cuenta cuántos tokens tiene un texto -- esto es lo que usamos en vez de
    contar 'peticiones', porque una pregunta corta y una larga no cuestan lo mismo."""
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def ask_llm(question: str, context_chunks: list[str]) -> dict:
    """
    Arma el prompt final (pregunta + contexto encontrado por RAG) y llama al modelo.
    Devuelve la respuesta y cuántos tokens costó, para poder medirlo en las pruebas.
    """
    context = "\n\n".join(context_chunks)
    prompt = f"Contexto del curso:\n{context}\n\nPregunta del estudiante: {question}"

    tokens_entrada = count_tokens(prompt)

    # TODO: acá va la llamada real a la API del LLM, por ejemplo con el cliente de OpenAI:
    # respuesta = client.chat.completions.create(model="...", messages=[...])
    respuesta_texto = "TODO: respuesta real del modelo"
    tokens_salida = count_tokens(respuesta_texto)

    return {
        "respuesta": respuesta_texto,
        "tokens_entrada": tokens_entrada,
        "tokens_salida": tokens_salida,
        "tokens_total": tokens_entrada + tokens_salida,
    }
