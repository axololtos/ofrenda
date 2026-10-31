"""Local Gemma via Ollama, with Sentry gen_ai spans around every call."""
import json
import os

import httpx
import sentry_sdk

HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
CHAT_MODEL = os.getenv("OFRENDA_MODEL", "gemma3:4b")  # Featured category: Gemma
EMBED_MODEL = os.getenv("OFRENDA_EMBED_MODEL", "nomic-embed-text")
# Stories are private. Prompts/outputs only reach Sentry if you opt in.
TRACE_CONTENT = os.getenv("OFRENDA_TRACE_CONTENT") == "1"


async def chat(messages: list[dict], agent: str, json_mode: bool = False) -> str:
    with sentry_sdk.start_span(op="gen_ai.chat", name=f"chat {CHAT_MODEL}") as span:
        span.set_data("gen_ai.request.model", CHAT_MODEL)
        span.set_data("gen_ai.agent.name", agent)
        if TRACE_CONTENT:
            span.set_data("gen_ai.request.messages", json.dumps(messages))
        body = {"model": CHAT_MODEL, "messages": messages, "stream": False}
        if json_mode:
            body["format"] = "json"
        async with httpx.AsyncClient(timeout=300) as c:
            r = await c.post(f"{HOST}/api/chat", json=body)
            r.raise_for_status()
        d = r.json()
        out = d["message"]["content"]
        span.set_data("gen_ai.usage.input_tokens", d.get("prompt_eval_count", 0))
        span.set_data("gen_ai.usage.output_tokens", d.get("eval_count", 0))
        if TRACE_CONTENT:
            span.set_data("gen_ai.response.text", out)
        return out


async def embed(texts: list[str]) -> list[list[float]]:
    with sentry_sdk.start_span(op="gen_ai.embeddings", name=f"embed {EMBED_MODEL}") as span:
        span.set_data("gen_ai.request.model", EMBED_MODEL)
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(f"{HOST}/api/embed", json={"model": EMBED_MODEL, "input": texts})
            r.raise_for_status()
        return r.json()["embeddings"]
