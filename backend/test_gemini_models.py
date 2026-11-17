"""Manual Gemini model-list API check; makes a network request only when run."""
import os
from dotenv import load_dotenv
from google import genai


def main():
    load_dotenv(override=True)
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    client = genai.Client(api_key=api_key)
    print("\nAvailable Gemini models:\n")
    for model in client.models.list():
        if "generateContent" in (model.supported_actions or []):
            print(model.name)


if __name__ == "__main__":
    main()
