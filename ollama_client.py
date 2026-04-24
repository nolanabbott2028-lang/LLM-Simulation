"""Singleton Ollama client: quick connect failure, long read for slow local inference."""
import os
from typing import Any, List, Optional

import httpx
from ollama import Client

from config import OLLAMA_HOST, OLLAMA_CONNECT_TIMEOUT, OLLAMA_READ_TIMEOUT

_client: Optional[Client] = None


def get_ollama_client() -> Client:
    global _client
    if _client is None:
        host = os.environ.get("OLLAMA_HOST", OLLAMA_HOST)
        timeout = httpx.Timeout(
            connect=OLLAMA_CONNECT_TIMEOUT,
            read=OLLAMA_READ_TIMEOUT,
            write=30.0,
            pool=5.0,
        )
        _client = Client(host=host, timeout=timeout)
    return _client


def ollama_chat(
    model: str,
    messages: List[dict],
) -> Any:
    return get_ollama_client().chat(model=model, messages=messages)
