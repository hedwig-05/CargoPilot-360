
from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """
    Common interface for all LLM providers.
    """

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """
        Generate a response from the language model.
        """
        pass
