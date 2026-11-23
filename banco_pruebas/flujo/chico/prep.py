"""Deja en datos.json lo que el modelo chico necesita, para que entrenar y probar corran sin el resto del banco:
las filas recortadas de cada modelo, iguales a las del podado; los pares de entrenamiento y validacion; y las 48 de prueba
con sus 15 candidatos, aceptables y topes de precio por la frase. Controla el hash de la muestra."""
import hashlib, json, os, random, re, sys
AQUI = os.path.dirname(os.path.abspath(__file__)); TR = os.path.join(AQUI, "..", "traductor")
sys.path[:0] = [TR]; sys.dont_write_bytecode = True
import catalogo as K, podado, decidir_verif as DV  # noqa: E402
from muestra import M  # noqa: E402

h = hashlib.sha256(open(os.path.join(TR, "muestra.py"), "rb").read()).hexdigest()
assert h in open(os.path.join(TR, "hash.txt")).read(), "la muestra cambio: la prueba no vale"
clave = lambda k: "|".join(k)
FILAS = {clave(k): podado.fila(0, k)[3:] for k in K.MOD}

def topes(frase):
    out = []
    for m in re.finditer(r"\d[\d.,]*\s*[a-z]*", DV.norm(frase)):
        t = DV.tope(m.group(0), frase)
        if t: out.append(t)
    return out

# Entrenamiento: cada frase contra todo su rubro y 6 modelos de otros rubros; las reglas se parten 85 / 15.
rnd = random.Random(105)
reglas = [json.loads(x) for x in open(os.path.join(AQUI, "frases.jsonl"))]
rnd.shuffle(reglas)
corte = int(len(reglas) * 0.85)
todos = list(K.MOD)
def pares(rs):
    out = []
    for r in rs:
        ac = {clave(a) for a in r["acept"]}
        rubros = set(r["regla"].get("rubro") or [])
        cand = [k for k in todos if k[0] in rubros]
        for fr in r["frases"]:
            otros = rnd.sample([k for k in todos if k[0] not in rubros], 6)
            out += [[fr, clave(k), int(clave(k) in ac)] for k in cand + otros]
    return out
prueba = [{"id": m[1], "frase": m[2], "dudosa": m[4], "top": [clave(k) for k in c["top"]],
           "acept": [clave(a) for a in ac], "topes": topes(m[2])}
          for m, c, ac in zip(M, json.load(open(os.path.join(TR, "cand.json"))), json.load(open(os.path.join(TR, "aceptables.json"))))]
d = {"filas": FILAS, "train": pares(reglas[:corte]), "val": pares(reglas[corte:]), "prueba": prueba,
     "precio": {clave(k): min(int(x["precio_ars"]) for x in K.MOD[k]) for k in K.MOD}}
json.dump(d, open(os.path.join(AQUI, "datos.json"), "w"), ensure_ascii=False)
print("reglas", len(reglas), "pares train", len(d["train"]), "val", len(d["val"]), "positivos train",
      sum(p[2] for p in d["train"]), "prueba", len(prueba), "con tope", sum(bool(p["topes"]) for p in prueba))
