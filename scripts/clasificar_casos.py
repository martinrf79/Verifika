"""
CLASIFICADOR DE CASOS REALES (carril modelo, usa DeepSeek por costo).

Toma conversaciones reales exportadas a un JSONL local y, con DeepSeek (barato),
clasifica cada una por tipo y dificultad y marca si es buen candidato a test de
regresion. La salida alimenta el banco: los casos de calculo se vuelven filas en
data/casos_reales.json.

Pipeline completo:
  1. Exportar conversaciones reales de Firestore a data/conversaciones_raw.jsonl
     (una conversacion por linea). Ese export es un paso aparte, no lo hace este
     script, para no acoplar credenciales de Firestore.
  2. Correr este script: clasifica con DeepSeek y escribe reports/casos_clasificados.json.
  3. Revisar y pasar los candidatos de calculo a data/casos_reales.json (con
     items, items_extra, destino y total_esperado), que el banco ya carga solo.

Costo: una llamada chica por conversacion, max_tokens bajo, temperatura 0. Con
--dry-run no llama al modelo, solo cuenta cuantas conversaciones hay.

Uso:
  winvenv\\Scripts\\python.exe scripts\\clasificar_casos.py --dry-run
  winvenv\\Scripts\\python.exe scripts\\clasificar_casos.py --limit 20
"""
import os
import sys
import json
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "conversaciones_raw.jsonl")
OUT = os.path.join(ROOT, "reports", "casos_clasificados.json")


def cargar_secrets():
    """Carga la clave de DeepSeek desde .secrets.env, sin imprimirla."""
    path = os.path.join(ROOT, ".secrets.env")
    if not os.path.exists(path):
        raise SystemExit("Falta .secrets.env en la raiz del proyecto")
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()
            elif line.startswith("sk-"):
                os.environ["DEEPSEEK_API_KEY"] = line


def leer_conversaciones():
    if not os.path.exists(RAW):
        raise SystemExit(
            f"No existe {RAW}. Exporta primero las conversaciones reales, una "
            f"por linea, con un campo 'mensajes' o 'transcript'.")
    convs = []
    with open(RAW, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    convs.append(json.loads(line))
                except Exception:
                    pass
    return convs


def texto_conversacion(c):
    """Arma el texto plano de la conversacion para pasarselo al clasificador."""
    if isinstance(c.get("transcript"), str):
        return c["transcript"][:3000]
    msgs = c.get("mensajes") or c.get("history") or []
    partes = []
    for m in msgs:
        rol = m.get("role", "?")
        cont = str(m.get("content", ""))[:400]
        partes.append(f"{rol}: {cont}")
    return "\n".join(partes)[:3000]


SYSTEM = (
    "Sos un clasificador de conversaciones de un bot de ventas. Para la "
    "conversacion dada, devolve SOLO JSON estricto con estos campos:\n"
    '{"tipo": "cotizacion|faq|cierre|saludo|reclamo|otro", '
    '"dificultad": "facil|media|dificil", '
    '"candidato_regresion": true|false, '
    '"motivo": "una frase corta"}\n'
    "candidato_regresion es true si la conversacion tiene un calculo de precio, "
    "envio o descuento que conviene fijar como test, o un caso borde que el bot "
    "podria errar. Nada de texto fuera del JSON."
)


def clasificar_una(texto):
    from app.verifika.llm_adapter import llm_complete
    res = llm_complete(
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "CONVERSACION:\n" + texto + "\n\nJSON:"},
        ],
        role="proposer",
        temperature=0.0,
        max_tokens=120,
    )
    content = (res.get("content") or "").strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()
    try:
        return json.loads(content)
    except Exception:
        return {"tipo": "otro", "dificultad": "media",
                "candidato_regresion": False, "motivo": "no parseable"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="Maximo de conversaciones a clasificar. 0 = todas.")
    ap.add_argument("--dry-run", action="store_true",
                    help="No llama al modelo, solo cuenta.")
    args = ap.parse_args()

    convs = leer_conversaciones()
    if args.limit:
        convs = convs[:args.limit]

    print(f"\nConversaciones a procesar: {len(convs)}")
    if args.dry_run:
        print("Dry-run: no se llama al modelo. Quita --dry-run para clasificar.\n")
        return 0

    cargar_secrets()
    if not os.environ.get("DEEPSEEK_API_KEY", "").startswith("sk-"):
        raise SystemExit("No se encontro DEEPSEEK_API_KEY valida en .secrets.env")
    sys.path.insert(0, ROOT)

    resultados = []
    candidatos = 0
    for i, c in enumerate(convs, 1):
        clasif = clasificar_una(texto_conversacion(c))
        if clasif.get("candidato_regresion"):
            candidatos += 1
        resultados.append({"id": c.get("id", f"conv-{i}"), **clasif})
        print(f"  [{i}/{len(convs)}] {clasif.get('tipo'):<10} "
              f"{clasif.get('dificultad'):<7} "
              f"candidato={clasif.get('candidato_regresion')}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    print(f"\n{len(resultados)} clasificadas, {candidatos} candidatas a "
          f"regresion. Escrito en reports/casos_clasificados.json\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
