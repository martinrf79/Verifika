"""Controla las etiquetas de los primeros mensajes con `examen.controlar` y congela con hash.

    python3 primeros/control.py [S001 ...]     # problemas por frase; sin problemas escribe examen.json y hash.txt
"""
import hashlib, json, os, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [AQUI, os.path.join(AQUI, "..", "examen"), os.path.join(AQUI, "..", "conceptos")]
sys.dont_write_bytecode = True
import examen as X  # noqa: E402
from primeras import L  # noqa: E402

frases = {json.loads(l)["id"]: json.loads(l)["texto"] for l in open(os.path.join(AQUI, "sinteticas.jsonl"))}
pedir = set(sys.argv[1:])
malos, out = 0, []
for i, t in frases.items():
    if pedir and i not in pedir:
        continue
    if i not in L:
        print(i, "sin etiqueta"); malos += 1; continue
    p = X.controlar(t, L[i])
    for m in p:
        print(i, m)
    malos += bool(p)
    out.append({"id": i, "texto": t, **L[i]})
print(f"{len(out)} etiquetadas, {malos} con problemas")
if not malos and not pedir and len(out) == len(frases):
    s = json.dumps(out, ensure_ascii=False, sort_keys=True)
    open(os.path.join(AQUI, "examen.json"), "w").write(json.dumps(out, ensure_ascii=False, indent=0))
    open(os.path.join(AQUI, "hash.txt"), "w").write(hashlib.sha256(s.encode()).hexdigest() + "\n")
    print("congelado:", hashlib.sha256(s.encode()).hexdigest()[:12])
