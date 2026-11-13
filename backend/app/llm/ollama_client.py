
import ollama

from app.llm.base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    """
    Local LLM provider using Ollama.
    """

    def __init__(self, model: str = "qwen2.5-coder:7b"):
        self.model = model

    def generate(self, prompt: str) -> str:
        """
        Send a prompt to the selected Ollama model
        and return its response.
        """

        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                options={
                    "temperature": 0
                }
            )

            return response["message"]["content"].strip()

        except Exception as error:
            raise RuntimeError(
                f"Ollama generation failed: {error}"
            ) from error
