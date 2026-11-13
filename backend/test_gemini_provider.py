
from dotenv import load_dotenv

from app.llm.gemini_client import GeminiProvider


def test_gemini_provider():

    load_dotenv()

    provider = GeminiProvider(
        model="gemini-3.5-flash-lite"
    )

    prompt = """
    You are CargoPilot 360, a logistics operations assistant.

    Shipment: CP-SHP-2026-005
    Route: Rotterdam to Colombo, Sri Lanka.
    Status: CUSTOMS HOLD.

    Evidence:
    - Expected customs clearance: 5 November 2026.
    - Customs clearance has not been recorded.
    - An active high-severity delay exception exists.

    Tasks:
    1. Summarise the situation.
    2. Identify confirmed facts.
    3. Suggest two reasonable next steps.

    Do not invent missing information.
    """

    print("\nTesting CargoPilot Gemini integration...")

    response = provider.generate(prompt)

    print("\nGEMINI RESPONSE:")
    print(response)

    print("\nGemini integration test completed successfully!")


if __name__ == "__main__":
    test_gemini_provider()
