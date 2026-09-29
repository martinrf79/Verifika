"""Capacidad base: el modelo LEYENDO los datos, sin herramientas, en una charla.
Tres formatos del mismo dato: prosa, tabla, json. Un rubro chico y uno grande. Scratch."""
import json, re, sys
sys.path.insert(0, "/home/user/Verifika")
from banco_pruebas import clon_produccion
clon_produccion.preparar_entorno(); clon_produccion.instalar()
import logging; logging.disable(logging.CRITICAL)
from app.storage.firestore_client import get_all_products, get_all_faq
from app.core.llm_reintento import _cliente, _modelo
from concurrent.futures import ThreadPoolExecutor

T = "verifika_prod"
cli, mod = _cliente(), _modelo()
P = get_all_products(tienda_id=T)
FAQ = get_all_faq(tienda_id=T)
REPS = 3

def n(t):
    import unicodedata
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")

def filas(rubro):
    return [p for p in P if p["categoria"] == rubro]

def fmt(prods, forma):
    if forma == "prosa":
        return "\n".join(f"- {p['nombre']}: {p.get('descripcion_rica') or p.get('descripcion')} Precio ${p['precio_ars']}. "
                         f"Stock {p['stock']}. {p.get('origen','')}" for p in prods)
    keys = sorted({k for p in prods for k in (p.get("specs") or {})})
    if forma == "tabla":
        cab = ["nombre", "precio", "stock", "peso_g"] + keys + ["origen"]
        out = [" | ".join(cab)]
        for p in prods:
            s = p.get("specs") or {}
            out.append(" | ".join([p["nombre"], str(p["precio_ars"]), str(p["stock"]), str(p.get("peso_gramos"))]
                                  + [str(s.get(k, "")) for k in keys] + [p.get("origen", "")]))
        return "\n".join(out)
    return json.dumps([{"nombre": p["nombre"], "precio": p["precio_ars"], "stock": p["stock"],
                        "peso_g": p.get("peso_gramos"), **(p.get("specs") or {}), "origen": p.get("origen")}
                       for p in prods], ensure_ascii=False)

faq_txt = "\n".join(f"- {t}: {d.get('respuesta')}" for t, d in FAQ.items())

# ── verdad, calculada del catalogo ──
par = filas("parlante")
agua = sorted({p["modelo"] for p in par if n((p.get("specs") or {}).get("resistencia_agua", "")).startswith("si")})
agua_barato = min((p for p in par if p["modelo"] in agua), key=lambda p: p["precio_ars"])
def horas(p):
    m = re.search(r"(\d+)\s*horas", n((p.get("specs") or {}).get("bateria", "")))
    return int(m.group(1)) if m else -1
agua_bat = max((p for p in par if p["modelo"] in agua), key=horas)
jbl = sorted({p["modelo"] for p in par if p["marca"] == "JBL"})
aur = filas("auriculares")
bt80 = sorted({p["modelo"] for p in aur if n((p.get("specs") or {}).get("bluetooth", "")).startswith("si") and p["precio_ars"] < 80000})
nb = filas("notebook")
liv = min(nb, key=lambda p: p["peso_gramos"])
nb16 = [p for p in nb if n((p.get("specs") or {}).get("ram", "")).startswith("16") and p["peso_gramos"] < 2000]
nb16b = min(nb16, key=lambda p: p["precio_ars"]) if nb16 else None
lenovo = len({p["modelo"] for p in nb if p["marca"] == "Lenovo"})
print("verdad:", agua, agua_barato["modelo"], agua_bat["modelo"], jbl, bt80, liv["nombre"], nb16b and nb16b["nombre"], lenovo)

def tiene(t, *ws):
    return all(n(w) in n(t) for w in ws)

CHAT_CHICO = [
 ("que parlantes tenes que se puedan mojar?", lambda t: all(tiene(t, m) for m in agua) and not any(
     tiene(t, p["modelo"]) for p in par if p["modelo"] not in agua and len(p["modelo"]) > 3)),
 ("de esos, cual es el mas barato?", lambda t: tiene(t, agua_barato["modelo"]) and str(agua_barato["precio_ars"])[:2] in re.sub(r"\D", "", t)),
 ("y cual de esos tiene mas bateria?", lambda t: tiene(t, agua_bat["modelo"])),
 ("cuantos modelos de parlante JBL tienen?", lambda t: str(len(jbl)) in t or any(w in n(t) for w in ["tres", "cuatro", "cinco", "seis"][len(jbl)-3:len(jbl)-2])),
 ("tenes auriculares bluetooth de menos de 80 mil?", lambda t: (all(tiene(t, m) for m in bt80) if bt80 else ("no" in n(t)))),
 ("si me llega roto que hago?", lambda t: "7" in t and ("sin costo" in n(t) or "gratis" in n(t))),
 ("el primero que me dijiste que se moja, donde se fabrica?", lambda t: "china" in n(t)),
]
CHAT_GRANDE = [
 ("cual es la notebook mas liviana que tienen?", lambda t: tiene(t, liv["modelo"].split()[0]) and str(liv["peso_gramos"])[:2] in re.sub(r"\D", "", t)),
 ("y con 16 de ram y menos de 2 kilos, la mas barata?", lambda t: nb16b is not None and str(nb16b["precio_ars"])[:3] in re.sub(r"\D", "", t)),
 ("cuantos modelos Lenovo tienen?", lambda t: str(lenovo) in t),
]

def charla(rubros, preguntas, forma):
    datos = "\n\n".join(f"RUBRO {r}:\n{fmt(filas(r), forma)}" for r in rubros)
    sis = ("Sos el vendedor de una tienda online de tecnologia de Argentina. Contesta corto, con voseo, SOLO con "
           "estos datos; si no estan, deci que no figura.\n\nPOLITICAS:\n" + faq_txt + "\n\nPRODUCTOS:\n" + datos)
    msgs = [{"role": "system", "content": sis}]
    notas, textos, tok = [], [], 0
    for q, chk in preguntas:
        msgs.append({"role": "user", "content": q})
        r = cli.chat.completions.create(model=mod, messages=msgs, temperature=0.2)
        t = r.choices[0].message.content or ""
        tok = r.usage.prompt_tokens
        msgs.append({"role": "assistant", "content": t})
        try:
            ok = bool(chk(t))
        except Exception:
            ok = False
        notas.append(ok); textos.append(t[:160].replace("\n", " "))
    return notas, textos, tok

trab = [(chat, forma, rep) for chat in ("chico", "grande") for forma in ("prosa", "tabla", "json") for rep in range(REPS)]
def una(x):
    chat, forma, rep = x
    if chat == "chico":
        return x, charla(["parlante", "auriculares"], CHAT_CHICO, forma)
    return x, charla(["notebook"], CHAT_GRANDE, forma)

with ThreadPoolExecutor(9) as ex:
    res = list(ex.map(una, trab))
from collections import defaultdict
agg = defaultdict(list); tok = {}
for (chat, forma, rep), (notas, textos, tk) in res:
    agg[(chat, forma)].append(notas); tok[(chat, forma)] = tk
for k, v in sorted(agg.items()):
    por_preg = [sum(x[i] for x in v) for i in range(len(v[0]))]
    print(k, "tokens", tok[k], "por pregunta (de 3):", por_preg, "total", sum(por_preg), "/", 3 * len(por_preg))
json.dump([[list(x), r] for x, r in res], open("/tmp/claude-0/-home-user-Verifika/9485093e-efa9-58bd-a799-27a093938332/scratchpad/capacidad.json", "w"), ensure_ascii=False)
