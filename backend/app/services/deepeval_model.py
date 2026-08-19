"""Обёртка DeepSeek под интерфейс DeepEval (``DeepEvalBaseLLM``).

DeepEval из коробки рассчитан на модели OpenAI как LLM-судью для метрик
(``GEval``, ``AnswerRelevancy`` и т.д.). У нас нет ключа OpenAI (§1, §4.1
SPEC — провайдер LLM в проекте — DeepSeek), поэтому судьёй для эвалов тоже
выступает DeepSeek через тот же OpenAI-совместимый клиент (`llm_client.py`).
Используется только в `tests/evals` — на прод-код влияния не оказывает.
"""

from deepeval.models.base_model import DeepEvalBaseLLM

from app.services.llm_client import DeepSeekLLMClient


class DeepSeekEvalModel(DeepEvalBaseLLM):
    """Судья для метрик DeepEval поверх `DeepSeekLLMClient`."""

    def __init__(self, llm: DeepSeekLLMClient, model_name: str | None = None):
        self._llm = llm
        self._model_name = model_name or llm.model
        super().__init__(model=self._model_name)

    def load_model(self) -> "DeepSeekEvalModel":
        return self

    async def a_generate(self, prompt: str, *args, **kwargs) -> str:
        return await self._llm.chat_text(
            system_prompt="Ты — точный и беспристрастный ассистент-оценщик. Отвечай строго по инструкции в запросе.",
            user_prompt=prompt,
            model=self._model_name,
        )

    def generate(self, prompt: str, *args, **kwargs) -> str:
        import asyncio

        return asyncio.run(self.a_generate(prompt))

    def get_model_name(self) -> str:
        return self._model_name
