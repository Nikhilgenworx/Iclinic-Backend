from control.config.openrouter_config import OpenRouterConfig
from langchain_openai import ChatOpenAI


class LLMFactory:
    @staticmethod
    def get_llm(temperature: float = 0.3):
        config = OpenRouterConfig()

        return ChatOpenAI(
            model=config.default_model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=temperature,
            max_tokens=512,
            timeout=30,
            max_retries=1,
        )

    @staticmethod
    def get_router_llm():
        """Lightweight, fast LLM for intent classification only.
        Uses low max_tokens since it only needs to output a single word."""
        config = OpenRouterConfig()

        return ChatOpenAI(
            model=config.router_model,
            api_key=config.router_api_key,
            base_url=config.router_base_url,
            temperature=0.0,
            max_tokens=20,
            timeout=10,
            max_retries=1,
        )
