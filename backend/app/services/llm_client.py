import json
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any, Protocol

from loguru import logger
from openai import AsyncOpenAI

from app.core.config import get_settings


class LLMClient(Protocol):
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        json_schema: dict[str, Any] | None = None,
        stream: bool = False,
        model: str | None = None,
    ) -> Any: ...


class DeepSeekLLMClient:
    def __init__(self, base_url: str, api_key: str, model: str, reasoner_model: str):
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key or "sk-placeholder")
        self.model = model
        self.reasoner_model = reasoner_model
        # api_key.isascii() отсекает незаполненный плейсхолдер из .env.example
        # ("sk-...твой_токен_deepseek..."), чтобы не пытаться слать реальные запросы.
        self.enabled = bool(api_key) and api_key.isascii()

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        json_schema: dict[str, Any] | None = None,
        stream: bool = False,
        model: str | None = None,
    ):
        kwargs: dict[str, Any] = {"model": model or self.model, "messages": messages, "stream": stream}
        if tools:
            kwargs["tools"] = tools
        if json_schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": json_schema["name"],
                    "schema": json_schema["schema"],
                    "strict": True,
                },
            }
        return await self.client.chat.completions.create(**kwargs)

    async def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
        model: str | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            return {}
        try:
            response = await self.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                json_schema=json_schema,
                model=model,
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"LLM chat_json ошибка: {exc}")
            return {}

    async def chat_text(self, system_prompt: str, user_prompt: str, model: str | None = None) -> str:
        if not self.enabled:
            return ""
        try:
            response = await self.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=model,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"LLM chat_text ошибка: {exc}")
            return ""

    async def chat_stream(
        self, messages: list[dict[str, Any]], model: str | None = None
    ) -> AsyncIterator[str]:
        if not self.enabled:
            yield ""
            return
        try:
            stream = await self.chat(messages=messages, stream=True, model=model)
            async for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield delta
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"LLM chat_stream ошибка: {exc}")
            yield ""


@lru_cache
def get_llm_client() -> DeepSeekLLMClient:
    settings = get_settings()
    return DeepSeekLLMClient(
        base_url=settings.llm_api_base,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        reasoner_model=settings.llm_reasoner_model,
    )
