
import time
import ollama

MODELS = [
    "deepseek-r1:1.5b-qwen-distill-q4_K_M",
    "qwen2.5-coder:7b"
]

prompt = """
You are assisting a logistics operations team.

Shipment reference: CP-SHP-2026-005
Route: Rotterdam to Colombo, Sri Lanka
Container: TEMU5678901
Status: CUSTOMS HOLD

Evidence:
1. The expected customs clearance date was 5 November 2026.
2. Customs clearance has not been recorded.
3. The shipment has an active high-severity delay exception.

Tasks:
1. Summarise the situation.
2. Identify what is confirmed by the evidence.
3. Suggest two reasonable next steps.
4. Do not invent missing information.

Keep your answer concise.
"""

for model in MODELS:
    print("\n" + "=" * 60)
    print("TESTING MODEL:", model)
    print("=" * 60)

    start = time.time()

    try:
        response = ollama.chat(
            model=model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            options={"temperature": 0}
        )

        elapsed = time.time() - start

        print("\nMODEL RESPONSE:")
        print(response["message"]["content"])

        print(f"\nRESPONSE TIME: {elapsed:.2f} seconds")

    except Exception as error:
        print("ERROR:", error)
