from __future__ import annotations

import asyncio
import sys
import types
from types import SimpleNamespace

redis_module = types.ModuleType("redis")
redis_asyncio_module = types.ModuleType("redis.asyncio")
redis_asyncio_module.Redis = object
redis_module.asyncio = redis_asyncio_module
sys.modules.setdefault("redis", redis_module)
sys.modules.setdefault("redis.asyncio", redis_asyncio_module)

psycopg_pool_module = types.ModuleType("psycopg_pool")
psycopg_pool_module.AsyncConnectionPool = object
sys.modules.setdefault("psycopg_pool", psycopg_pool_module)

psycopg_module = types.ModuleType("psycopg")
psycopg_rows_module = types.ModuleType("psycopg.rows")
psycopg_rows_module.dict_row = object
psycopg_module.rows = psycopg_rows_module
sys.modules.setdefault("psycopg", psycopg_module)
sys.modules.setdefault("psycopg.rows", psycopg_rows_module)

from app.models.schemas import ChatMessage
from app.core.config import Settings
from app.core.defaults import (
    CHAT_FREQUENCY_PENALTY,
    CHAT_MAX_RESPONSE_TOKENS,
    CHAT_PRESENCE_PENALTY,
    OPENAI_REASONING_EFFORT,
    CHAT_TOP_P,
)
from app.services.chat_service import ChatService
from app.providers.gemini_provider import GeminiProvider
from app.providers.nim_provider import NimProvider
from app.providers.ollama_provider import OllamaProvider
from app.providers.openai_provider import OpenAIProvider


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _RetryingOpenAIResponse:
    def __init__(self, payload: dict, *, status_code: int = 200, text: str = "", reason_phrase: str = "OK") -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = text
        self.reason_phrase = reason_phrase

    def raise_for_status(self) -> None:
        if self.status_code < 400:
            return None
        module = __import__("app.providers.openai_provider", fromlist=["httpx"])
        request = module.httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        raise module.httpx.HTTPStatusError(
            "simulated openai thinking rejection",
            request=request,
            response=self,
        )

    def json(self) -> dict:
        return self._payload


def _build_settings() -> SimpleNamespace:
    return SimpleNamespace(
        chat_temperature=0.15,
        chat_thinking_enabled=False,
        chat_show_thinking_block=False,
        openai_api_key="test-openai-key",
        gemini_api_key="test-gemini-key",
        ollama_base_url="http://localhost:11434",
        nim_base_url="http://localhost:8000/v1",
        nim_api_key=None,
    )


def _patch_async_client(monkeypatch, module, response_payload: dict, captured: dict) -> None:
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            captured["init"] = {"args": args, "kwargs": kwargs}

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, headers=None, json=None, params=None):
            captured["post"] = {
                "url": url,
                "headers": headers,
                "json": json,
                "params": params,
            }
            return _FakeResponse(response_payload)

    monkeypatch.setattr(module.httpx, "AsyncClient", FakeAsyncClient)


def test_openai_payload_uses_env_generation_settings(monkeypatch) -> None:
    settings = _build_settings()
    captured: dict = {}
    _patch_async_client(
        monkeypatch,
        __import__("app.providers.openai_provider", fromlist=["httpx"]),
        {"choices": [{"message": {"content": "ok"}}]},
        captured,
    )
    provider = OpenAIProvider(settings)

    result = asyncio.run(provider.complete_chat([ChatMessage(role="user", content="Hi")], "gpt-4o-mini"))

    payload = captured["post"]["json"]
    assert payload["temperature"] == settings.chat_temperature
    assert payload["top_p"] == CHAT_TOP_P
    assert payload["frequency_penalty"] == CHAT_FREQUENCY_PENALTY
    assert payload["presence_penalty"] == CHAT_PRESENCE_PENALTY
    assert payload["max_tokens"] == CHAT_MAX_RESPONSE_TOKENS
    assert "reasoning_effort" not in payload
    assert result.thinking is None


def test_gemini_payload_uses_env_generation_settings(monkeypatch) -> None:
    settings = _build_settings()
    settings.chat_thinking_enabled = True
    captured: dict = {}
    _patch_async_client(
        monkeypatch,
        __import__("app.providers.gemini_provider", fromlist=["httpx"]),
        {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]},
        captured,
    )
    provider = GeminiProvider(settings)

    asyncio.run(provider.complete_chat([ChatMessage(role="user", content="Hi")], "gemini-2.0-flash"))

    payload = captured["post"]["json"]
    generation_config = payload["generationConfig"]
    assert generation_config["temperature"] == settings.chat_temperature
    assert generation_config["topP"] == CHAT_TOP_P
    assert generation_config["maxOutputTokens"] == CHAT_MAX_RESPONSE_TOKENS
    assert generation_config["candidateCount"] == 1
    assert generation_config["thinkingConfig"]["thinkingBudget"] == -1
    assert generation_config["thinkingConfig"]["includeThoughts"] is True


def test_ollama_payload_uses_env_generation_settings(monkeypatch) -> None:
    settings = _build_settings()
    settings.chat_thinking_enabled = True
    captured: dict = {}
    _patch_async_client(
        monkeypatch,
        __import__("app.providers.ollama_provider", fromlist=["httpx"]),
        {"message": {"content": "ok"}},
        captured,
    )
    provider = OllamaProvider(settings)

    asyncio.run(provider.complete_chat([ChatMessage(role="user", content="Hi")], "llama3.2"))

    payload = captured["post"]["json"]
    options = payload["options"]
    assert options["temperature"] == settings.chat_temperature
    assert options["top_p"] == CHAT_TOP_P
    assert options["num_predict"] == CHAT_MAX_RESPONSE_TOKENS
    assert payload["think"] is True


def test_nim_payload_uses_env_generation_settings(monkeypatch) -> None:
    settings = _build_settings()
    settings.chat_thinking_enabled = True
    captured: dict = {}
    _patch_async_client(
        monkeypatch,
        __import__("app.providers.nim_provider", fromlist=["httpx"]),
        {"choices": [{"message": {"content": "ok"}}]},
        captured,
    )
    provider = NimProvider(settings)

    asyncio.run(provider.complete_chat([ChatMessage(role="user", content="Hi")], "meta/llama"))

    payload = captured["post"]["json"]
    assert payload["temperature"] == settings.chat_temperature
    assert payload["top_p"] == CHAT_TOP_P
    assert payload["frequency_penalty"] == CHAT_FREQUENCY_PENALTY
    assert payload["presence_penalty"] == CHAT_PRESENCE_PENALTY
    assert payload["max_tokens"] == CHAT_MAX_RESPONSE_TOKENS
    assert payload["chat_template_kwargs"]["enable_thinking"] is True


def test_openai_payload_uses_reasoning_effort_when_enabled(monkeypatch) -> None:
    settings = _build_settings()
    settings.chat_thinking_enabled = True
    captured: dict = {}
    _patch_async_client(
        monkeypatch,
        __import__("app.providers.openai_provider", fromlist=["httpx"]),
        {"choices": [{"message": {"content": "ok"}}]},
        captured,
    )
    provider = OpenAIProvider(settings)

    asyncio.run(provider.complete_chat([ChatMessage(role="user", content="Hi")], "gpt-4o-mini"))

    payload = captured["post"]["json"]
    assert payload["reasoning_effort"] == OPENAI_REASONING_EFFORT
    assert payload["max_completion_tokens"] == CHAT_MAX_RESPONSE_TOKENS


def test_openai_retries_without_thinking_when_model_rejects_it(monkeypatch) -> None:
    settings = _build_settings()
    settings.chat_thinking_enabled = True
    captured: dict = {"posts": []}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            captured["init"] = {"args": args, "kwargs": kwargs}

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, headers=None, json=None, params=None):
            captured["posts"].append(
                {
                    "url": url,
                    "headers": headers,
                    "json": json,
                    "params": params,
                }
            )
            if "reasoning_effort" in (json or {}):
                return _RetryingOpenAIResponse(
                    {},
                    status_code=404,
                    text="reasoning_effort is not supported",
                    reason_phrase="Not Found",
                )
            return _RetryingOpenAIResponse({"choices": [{"message": {"content": "ok"}}]})

    module = __import__("app.providers.openai_provider", fromlist=["httpx"])
    monkeypatch.setattr(module.httpx, "AsyncClient", FakeAsyncClient)
    provider = OpenAIProvider(settings)

    result = asyncio.run(provider.complete_chat([ChatMessage(role="user", content="Hi")], "gpt-4o-mini"))

    assert result.text == "ok"
    assert len(captured["posts"]) == 2
    assert "reasoning_effort" in captured["posts"][0]["json"]
    assert "reasoning_effort" not in captured["posts"][1]["json"]


def test_chat_service_formats_thinking_block_based_on_setting() -> None:
    service = object.__new__(ChatService)

    service._settings = SimpleNamespace(chat_show_thinking_block=False)  # type: ignore[attr-defined]
    assert service._format_answer("<think>reasoning</think> final", "reasoning") == "final"

    service._settings = SimpleNamespace(chat_show_thinking_block=True)  # type: ignore[attr-defined]
    assert service._format_answer("final", "reasoning") == "<thinking>\nreasoning\n</thinking>\n\nfinal"


def test_default_llm_profile_resolves_generation_default() -> None:
    settings = Settings(
        default_llm_profile="nim_3super120",
        generation_profiles={
            "nim_3super120": {
                "provider": "nim",
                "model": "nvidia/nemotron-3-super-120b-a12b",
            }
        },
        default_embedding_profile="ollama_1536",
        embedding_profiles={
            "ollama_1536": {
                "provider": "ollama",
                "model": "rjmalagon/gte-qwen2-1.5b-instruct-embed-f16",
                "dimension": 1536,
            }
        },
    )

    assumptions = settings.phase_one_assumptions()

    assert settings.default_generation_provider == "nim"
    assert settings.default_generation_model == "nvidia/nemotron-3-super-120b-a12b"
    assert assumptions["default_generation_profile"] == "nim_3super120"
    assert assumptions["default_generation_provider"] == "nim"
    assert assumptions["default_generation_model"] == "nvidia/nemotron-3-super-120b-a12b"


def test_guardrails_truncate_response_ends_cleanly() -> None:
    from app.services.guardrails import GuardrailService

    service = object.__new__(GuardrailService)
    service._settings = SimpleNamespace()  # type: ignore[attr-defined]

    text = (
        "SNAIC helps industry partners build practical AI solutions. "
        "This part should be trimmed mid-sentence. "
        * 80
    )
    truncated = service.truncate_response(text)

    assert truncated.endswith(("...", ".", "!", "?"))
    assert len(truncated) < len(text)
