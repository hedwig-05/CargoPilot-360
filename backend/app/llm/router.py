
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from app.llm.ollama_client import OllamaProvider
from app.llm.gemini_client import GeminiProvider


logger = logging.getLogger(__name__)


class LLMRouter:
    """
    Routes LLM requests to a primary provider.
    Uses a fallback provider if the primary provider fails.
    """

    def __init__(self, primary, fallback=None):
        self.primary = primary
        self.fallback = fallback

    def generate_with_metadata(self, prompt: str) -> dict:
        """
        Generate a response and return provider execution metadata.

        Returns:
            content: Generated response
            provider_name: GEMINI or OLLAMA
            model_name: Actual model used
            latency_ms: Total generation time in milliseconds
            fallback_used: Whether fallback was used
        """

        start_time = time.perf_counter()

        try:
            # Try the primary provider first.
            content = self.primary.generate(prompt)

            return {
                "content": content,
                "provider_name": self.primary.__class__.__name__.replace(
                    "Provider", ""
                ).upper(),
                "model_name": self.primary.model,
                "latency_ms": int(
                    (time.perf_counter() - start_time) * 1000
                ),
                "fallback_used": False
            }

        except Exception as primary_error:
            logger.warning(
                "Primary LLM failed: %s",
                primary_error
            )

            if self.fallback is None:
                raise RuntimeError(
                    "Primary LLM failed and no fallback is configured."
                ) from primary_error

            try:
                # Try the fallback provider.
                logger.info("Trying fallback LLM provider.")

                content = self.fallback.generate(prompt)

                return {
                    "content": content,
                    "provider_name": self.fallback.__class__.__name__.replace(
                        "Provider", ""
                    ).upper(),
                    "model_name": self.fallback.model,
                    "latency_ms": int(
                        (time.perf_counter() - start_time) * 1000
                    ),
                    "fallback_used": True
                }

            except Exception as fallback_error:
                logger.error(
                    "Both LLM providers failed. Primary: %s. Fallback: %s",
                    primary_error,
                    fallback_error
                )

                raise RuntimeError(
                    "Both primary and fallback providers failed. "
                    f"Primary: {primary_error}. "
                    f"Fallback: {fallback_error}"
                ) from fallback_error

    def generate(self, prompt: str) -> str:
        """
        Backward-compatible method.
        Returns only the generated text.
        """

        result = self.generate_with_metadata(prompt)
        return result["content"]


def create_llm_router() -> LLMRouter:
    """
    Creates the LLM router using environment configuration.
    """

    env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(dotenv_path=env_path)

    primary_name = os.getenv(
        "LLM_PROVIDER", "gemini"
    ).lower()

    fallback_name = os.getenv(
        "LLM_FALLBACK_PROVIDER", "ollama"
    ).lower()

    def create_provider(name):

        if name == "ollama":
            return OllamaProvider(
                model=os.getenv(
                    "OLLAMA_MODEL",
                    "qwen2.5-coder:7b"
                )
            )

        if name == "gemini":
            return GeminiProvider(
                model=os.getenv(
                    "GEMINI_MODEL",
                    "gemini-3.5-flash-lite"
                )
            )

        raise ValueError(
            f"Unsupported LLM provider: {name}"
        )

    if primary_name == fallback_name:
        raise ValueError(
            "Primary and fallback providers must be different."
        )

    primary_provider = create_provider(primary_name)
    fallback_provider = create_provider(fallback_name)

    return LLMRouter(
        primary=primary_provider,
        fallback=fallback_provider
    )
