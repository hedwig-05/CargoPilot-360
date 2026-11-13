
import os
from dotenv import load_dotenv
from google import genai

load_dotenv(override=True)

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

print("\nAvailable Gemini models:\n")

for model in client.models.list():
    actions = model.supported_actions or []

    if "generateContent" in actions:
        print(model.name)
