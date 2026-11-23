"""EL MODELO CHICO: un reordenador multilingue que puntua cada par (frase, fila). Corre en su propio entorno, fuera de
requirements.txt: torch y sentence-transformers.

    venv/bin/python entrenar.py cero      # sin ajustar: el modelo tal como viene
    venv/bin/python entrenar.py ajustar   # ajustado con datos.json, guarda el modelo en modelo/
    venv/bin/python entrenar.py probar    # el ajustado sobre las 48

Los umbrales se fijan en la validacion, con el objetivo escrito en plan.md, y despues se aplican a las 48 sin tocarlos.
"""
import json, os, random, statistics, sys, time
import numpy as np, torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

AQUI = os.path.dirname(os.path.abspath(__file__))
# cross-encoder/mmarco-mMiniLMv2-L12-H384-v1, bajado a mano a la carpeta que diga CHICO_BASE.
BASE = os.environ.get("CHICO_BASE", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
GUARDA = os.path.join(AQUI, "modelo")
D = json.load(open(os.path.join(AQUI, "datos.json")))
F = D["filas"]
torch.set_num_threads(4)


def cargar(ruta):
    tok = AutoTokenizer.from_pretrained(ruta)
    mod = AutoModelForSequenceClassification.from_pretrained(ruta, num_labels=1).eval()
    return tok, mod


@torch.no_grad()
def puntuar(tok, mod, frase, claves):
    x = tok([frase] * len(claves), [F[k] for k in claves], truncation=True, max_length=160, padding=True, return_tensors="pt")
    return torch.sigmoid(mod(**x).logits.squeeze(-1)).tolist()


def decidir(sc, claves, alto, bajo, topes=(), precio=None):
    ok = [(s, k) for s, k in zip(sc, claves)
          if all((precio[k] <= n if d == "max" else precio[k] >= n) for d, n in topes)] if precio else list(zip(sc, claves))
    sirven = sorted([x for x in ok if x[0] >= alto], reverse=True)[:5]
    if sirven:
        return "ofrece", [k for _, k in sirven]
    if any(s >= bajo for s, _ in ok):
        return "repregunta", []
    return "no_hay", []


def corregir(dec, of, acept, top):
    ac = set(acept)
    if ac and not ac & set(top):
        return "falla_busqueda"
    if dec == "repregunta":
        return "repregunta"
    if dec == "no_hay":
        return "acierta" if not ac else "erra"
    return "acierta" if of and all(k in ac for k in of) else "erra"


def val_por_frase():
    """La validacion agrupada por frase: (frase, claves, aceptables)."""
    g = {}
    for fr, k, y in D["val"]:
        g.setdefault(fr, ([], []))
        g[fr][0].append(k)
        if y:
            g[fr][1].append(k)
    return [(fr, ks, ac) for fr, (ks, ac) in g.items()]


def umbrales(tok, mod):
    """Fija alto y bajo en la validacion: maximiza acierta - 3 * erra, porque errar pesa mas que repreguntar."""
    vs = [(puntuar(tok, mod, fr, ks), ks, ac) for fr, ks, ac in val_por_frase()]
    mejor = None
    for alto in np.arange(0.3, 0.96, 0.05):
        for bajo in np.arange(0.05, alto, 0.05):
            c = [corregir(*decidir(sc, ks, alto, bajo), ac, ks) for sc, ks, ac in vs]
            v = c.count("acierta") - 3 * c.count("erra")
            if mejor is None or v > mejor[0]:
                mejor = (v, round(float(alto), 2), round(float(bajo), 2), c.count("acierta"), c.count("repregunta"), c.count("erra"), len(c))
    print("validacion: alto", mejor[1], "bajo", mejor[2], "acierta", mejor[3], "repregunta", mejor[4], "erra", mejor[5], "de", mejor[6])
    return mejor[1], mejor[2]


def probar(tok, mod, etiqueta):
    alto, bajo = umbrales(tok, mod)
    seg, out = [], []
    for p in D["prueba"]:
        t = time.time()
        sc = puntuar(tok, mod, p["frase"], p["top"])
        seg.append(time.time() - t)
        dec, of = decidir(sc, p["top"], alto, bajo, [tuple(x) for x in p["topes"]], D["precio"])
        out.append({"id": p["id"], "dudosa": p["dudosa"], "dec": dec, "of": of, "c": corregir(dec, of, p["acept"], p["top"]),
                    "sc": [round(s, 3) for s in sc]})
    with open(os.path.join(AQUI, f"prueba_{etiqueta}.jsonl"), "w") as f:
        for o in out:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    for nom, sel in (("todas", out), ("sin dudosas", [o for o in out if not o["dudosa"]])):
        c = [o["c"] for o in sel]
        print(f"{etiqueta} {nom}: N {len(c)} acierta {c.count('acierta')} repregunta {c.count('repregunta')} erra {c.count('erra')} falla_busqueda {c.count('falla_busqueda')}")
    seg.sort()
    print(f"tiempo por frase, 15 filas, 4 hilos: mediana {statistics.median(seg):.3f} s, p90 {seg[int(len(seg) * .9) - 1]:.3f} s")


def ajustar():
    tok = AutoTokenizer.from_pretrained(BASE)
    mod = AutoModelForSequenceClassification.from_pretrained(BASE, num_labels=1)
    tr = D["train"][:]
    random.Random(105).shuffle(tr)
    opt = torch.optim.AdamW(mod.parameters(), lr=2e-5)
    lossf = torch.nn.BCEWithLogitsLoss()
    mod.train()
    B, t0 = 32, time.time()
    for i in range(0, len(tr), B):
        b = tr[i:i + B]
        x = tok([p[0] for p in b], [F[p[1]] for p in b], truncation=True, max_length=160, padding=True, return_tensors="pt")
        loss = lossf(mod(**x).logits.squeeze(-1), torch.tensor([float(p[2]) for p in b]))
        loss.backward(); opt.step(); opt.zero_grad()
        if (i // B) % 50 == 0:
            print(f"  {i}/{len(tr)} perdida {loss.item():.3f} {time.time() - t0:.0f} s", flush=True)
    mod.eval()
    mod.save_pretrained(GUARDA); tok.save_pretrained(GUARDA)
    print(f"ajustado en {time.time() - t0:.0f} s")


if __name__ == "__main__":
    q = sys.argv[1]
    if q == "cero":
        probar(*cargar(BASE), "cero")
    elif q == "ajustar":
        ajustar()
    elif q == "probar":
        probar(*cargar(GUARDA), "ajustado")
