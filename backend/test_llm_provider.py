
from app.llm.ollama_client import OllamaProvider


def test_ollama_provider():

    provider = OllamaProvider(
        model="qwen2.5-coder:7b"
    )

    prompt = """
    You are CargoPilot 360, a logistics operations assistant.

    A shipment from Rotterdam to Colombo has an
    overdue customs clearance milestone.

    Explain the situation in two sentences.
    Do not invent information.
    """

    print("\nTesting CargoPilot Ollama integration...")
    
    response = provider.generate(prompt)

    print("\nMODEL RESPONSE:")
    print(response)

    print("\nOllama integration test completed successfully!")


if __name__ == "__main__":
    test_ollama_provider()
