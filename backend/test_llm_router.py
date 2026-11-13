
from dotenv import load_dotenv

from app.llm.router import create_llm_router


load_dotenv()

print("Testing CargoPilot LLM Router Metadata...\n")

router = create_llm_router()

prompt = """
Shipment CP-SHP-2026-005 is travelling from Rotterdam to Colombo.
Its customs clearance milestone is overdue.
Provide a short operational summary using only these facts.
"""

result = router.generate_with_metadata(prompt)

print("LLM RESPONSE:")
print(result["content"])

print("\nEXECUTION METADATA:")
print("Provider:", result["provider_name"])
print("Model:", result["model_name"])
print("Latency:", result["latency_ms"], "ms")
print("Fallback used:", result["fallback_used"])

print("\nLLM metadata test completed!")
