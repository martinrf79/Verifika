"""Lista modelos disponibles en OpenRouter filtrados por palabra clave."""
import os
import sys
from openai import OpenAI

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_sec = os.path.join(root, ".secrets10.env")
if os.path.exists(_sec):
    for _l in open(_sec, encoding="utf-8"):
        _l = _l.strip()
        if _l and not _l.startswith("#") and "=" in _l:
            k, v = _l.split("=", 1)
            os.environ[k.strip()] = v.strip()

if not os.environ.get("OPENROUTER_API_KEY"):
    print("❌ Falta OPENROUTER_API_KEY en .secrets10.env")
    sys.exit(1)

client = OpenAI(
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url="https://openrouter.ai/api/v1",
    timeout=10
)

filtro = sys.argv[1].lower() if len(sys.argv) > 1 else "gemini"

try:
    models = client.models.list()
    matches = [m for m in models.data if filtro in m.id.lower()]

    if matches:
        print(f"\n✓ Modelos con '{filtro}' en OpenRouter:\n")
        for m in sorted(matches, key=lambda x: x.id):
            print(f"  {m.id}")
    else:
        print(f"❌ No hay modelos con '{filtro}'")
        print("\nProbá con: gemma, llama, deepseek, qwen, mistral")
except Exception as e:
    print(f"❌ Error: {e}")
