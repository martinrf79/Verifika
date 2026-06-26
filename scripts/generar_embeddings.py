"""
GENERA LOS EMBEDDINGS DE UN CATALOGO, una sola vez (usa OpenAI).

Lee el catalogo CSV de una tienda, genera el vector de cada producto con OpenAI
(text-embedding-3-small, barato) y lo guarda en data/clientes/{tienda}/embeddings.json
como mapa id -> vector. El harness y la busqueda los levantan de ahi.

Costo: ~2000 productos x ~50 tokens = centavos, una sola vez. La clave de OpenAI
sale de .secrets4.env, nunca se imprime.

Uso:
  winvenv\\Scripts\\python.exe scripts\\generar_embeddings.py --tienda verifika_prod
"""
import os
import sys
import csv
import json
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cargar_secrets():
    """Carga SOLO la clave de OpenAI desde .secrets4.env, sin imprimirla."""
    path = os.path.join(ROOT, ".secrets4.env")
    if not os.path.exists(path):
        raise SystemExit("Falta .secrets4.env con OPENAI_API_KEY")
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tienda", default="verifika_prod")
    ap.add_argument("--limit", type=int, default=0, help="0 = todos")
    args = ap.parse_args()

    cargar_secrets()
    if not os.environ.get("OPENAI_API_KEY", "").startswith(("sk-", "sk_")):
        raise SystemExit("No se encontro OPENAI_API_KEY valida en .secrets4.env")
    # Provider openai para el cliente de embeddings.
    os.environ["EMBEDDINGS_PROVIDER"] = "openai"

    sys.path.insert(0, ROOT)
    from app.storage.embeddings import generate_embedding

    cat_dir = os.path.join(ROOT, "data", "clientes", args.tienda)
    prods = []
    with open(os.path.join(cat_dir, "productos.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            prods.append(row)
    if args.limit:
        prods = prods[:args.limit]

    print(f"Generando embeddings de {len(prods)} productos de {args.tienda}...")
    vectores = {}
    fallos = 0
    for i, p in enumerate(prods, 1):
        texto = (f"{p.get('nombre','')}. Categoria: {p.get('categoria','')}. "
                 f"{p.get('descripcion','')}")
        emb = generate_embedding(texto)
        if emb:
            vectores[p["id"].strip()] = emb
        else:
            fallos += 1
        if i % 200 == 0:
            print(f"  {i}/{len(prods)}...")

    out = os.path.join(cat_dir, "embeddings.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(vectores, f)
    dim = len(next(iter(vectores.values()))) if vectores else 0
    print(f"\nOK {len(vectores)} vectores (dim {dim}), {fallos} fallos.")
    print(f"  {out}")


if __name__ == "__main__":
    main()
