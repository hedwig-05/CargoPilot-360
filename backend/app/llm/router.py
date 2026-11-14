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
    Routes LLM requests to a primary provider and optionally falls back
    to a secondary provider.
    """

    def __init__(self, primary, fallback=None):
        self.primary = primary
        self.fallback = fallback

    @staticmethod
    def _provider_metadata(provider):
        return {
            "provider_name": provider.__class__.__name__.replace(
                "Provider", ""
            ).upper(),
            "model_name": provider.model,
        }

    def generate_with_metadata(self, prompt: str) -> dict:
        """
        Generate text and return provider execution metadata.

        The fallback is optional. A missing fallback credential must not
        prevent the configured primary provider from being used.
        """
        start_time = time.perf_counter()

        try:
            content = self.primary.generate(prompt)
            metadata = self._provider_metadata(self.primary)

            return {
                "content": content,
                **metadata,
                "latency_ms": int(
                    (time.perf_counter() - start_time) * 1000
                ),
                "fallback_used": False,
            }

        except Exception as primary_error:
            logger.warning("Primary LLM failed: %s", primary_error)

            if self.fallback is None:
                raise RuntimeError(
                    "Primary LLM failed and no usable fallback provider "
                    "is configured."
                ) from primary_error

            try:
                logger.info("Trying fallback LLM provider.")
                content = self.fallback.generate(prompt)
                metadata = self._provider_metadata(self.fallback)

                return {
                    "content": content,
                    **metadata,
                    "latency_ms": int(
                        (time.perf_counter() - start_time) * 1000
                    ),
                    "fallback_used": True,
                }

            except Exception as fallback_error:
                logger.exception("Both configured LLM providers failed.")
                raise RuntimeError(
                    "Both primary and fallback providers failed. "
                    f"Primary: {primary_error}. "
                    f"Fallback: {fallback_error}"
                ) from fallback_error

    def generate(self, prompt: str) -> str:
        """Backward-compatible text-only generation method."""
        return self.generate_with_metadata(prompt)["content"]


def create_llm_router() -> LLMRouter:
    """Create an LLM router from backend/.env or process environment."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(dotenv_path=env_path)

    primary_name = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    fallback_name = os.getenv(
        "LLM_FALLBACK_PROVIDER", "ollama"
    ).strip().lower()

    def create_provider(name):
        if name == "ollama":
            return OllamaProvider(
                model=os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
            )

        if name == "gemini":
            return GeminiProvider(
                model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
            )

        raise ValueError(f"Unsupported LLM provider: {name}")

    if primary_name == fallback_name:
        raise ValueError(
            "LLM_PROVIDER and LLM_FALLBACK_PROVIDER must be different."
        )

    # The primary provider is required: fail early if it is misconfigured.
    primary_provider = create_provider(primary_name)

    # A fallback is optional. In particular, a missing Gemini API key
    # should not stop an Ollama primary configuration from starting.
    fallback_provider = None
    try:
        fallback_provider = create_provider(fallback_name)
    except (ValueError, ImportError) as error:
        logger.warning(
            "Fallback LLM provider '%s' is unavailable: %s",
            fallback_name,
            error,
        )

    return LLMRouter(
        primary=primary_provider,
        fallback=fallback_provider,
    )
