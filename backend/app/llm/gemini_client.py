
import os

from google import genai

from app.llm.base import BaseLLMProvider


class GeminiProvider(BaseLLMProvider):
    """
    Cloud LLM provider using Google's Gemini API.
    """

    def __init__(self, model: str = "gemini-3.5-flash-lite"):
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured."
            )

        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate(self, prompt: str) -> str:
        """
        Send a prompt to Gemini and return its response.
        """

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )

            if not response.text:
                raise RuntimeError(
                    "Gemini returned an empty response."
                )

            return response.text.strip()

        except Exception as error:
            raise RuntimeError(
                f"Gemini generation failed: {error}"
            ) from error
