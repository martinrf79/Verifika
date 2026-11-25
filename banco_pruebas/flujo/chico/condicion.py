"""EL MODELO CHICO COMO VERIFICADOR DE CONDICION (25-nov-2026). Ver el segundo plan de plan.md.

multilingual-e5-small tal como viene, en ONNX cuantizado, dice si una condicion corta esta en la ficha de un producto:
cumple, no cumple o sin dato. La verdad la da el codigo, con conceptos.json. No gasta nada.

    E5=<carpeta con model_quantized.onnx y tokenizer.json> PYTHONPATH=<donde esta tokenizers> python3 chico/condicion.py
"""
import collections, json, os, statistics, sys, time
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(AQUI, "..", "examen"), os.path.join(AQUI, "..", "conceptos")]
sys.dont_write_bytecode = True
import examen as X  # noqa: E402

F, CO, CONC = X.F, X.CO, X.CONC
E5 = os.environ["E5"]
TOK = Tokenizer.from_file(os.path.join(E5, "tokenizer.json"))
TOK.enable_truncation(64)
TOK.enable_padding()
SES = ort.InferenceSession(os.path.join(E5, "model_quantized.onnx"), providers=["CPUExecutionProvider"])
NOMBRES = {i.name for i in SES.get_inputs()}
CACHE = {}
TEXTO = ("extra", "material", "uso", "origen", "retroiluminacion", "switch_teclado", "panel", "resolucion",
         "resistencia_agua", "bateria", "microfono", "cancelacion_ruido")


def vec(textos):
    nuevos = [t for t in dict.fromkeys(textos) if t not in CACHE]
    for i in range(0, len(nuevos), 64):
        lote = nuevos[i:i + 64]
        enc = TOK.encode_batch(["query: " + t for t in lote])
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        m = np.array([e.attention_mask for e in enc], dtype=np.int64)
        ent = {"input_ids": ids, "attention_mask": m}
        if "token_type_ids" in NOMBRES:
            ent["token_type_ids"] = np.zeros_like(ids)
        h = SES.run(None, ent)[0]
        v = (h * m[..., None]).sum(1) / m.sum(1, keepdims=True)
        v /= np.linalg.norm(v, axis=1, keepdims=True)
        for t, x in zip(lote, v):
            CACHE[t] = x
    return np.array([CACHE[t] for t in textos])


def frases(v):
    """La ficha de un producto en frases cortas."""
    out = [f"{c.replace('_', ' ')}: {v[c]}" for c in TEXTO if v.get(c)]
    out += [x.strip() for x in (v.get("extra") or "").split(",") if x.strip()]
    out += [f"color {c}" for c in v["color"]]
    out += [f"conecta por {c.replace('_', ' ')}" for c in v["conecta_por"]]
    out += [f"compatible con {p.replace('_', ' ')}" for p in v["plataformas"]]
    return out


FR = {k: frases(v) for k, v in F.VISTA.items()}
FV = {k: vec(f) for k, f in FR.items()}


def puntajes(cond, rubro):
    q = vec([cond])[0]
    return {k: float((FV[k] @ q).max()) for k, v in F.VISTA.items() if v["rubro"] == rubro}


def veredictos(cond, rubro, umbral):
    p = puntajes(cond, rubro)
    alguno = any(s >= umbral for s in p.values())
    return {k: "cumple" if s >= umbral else ("no" if alguno else "sin_dato") for k, s in p.items()}


def verdad(cid, rubro):
    cond = [tuple(c) for c in CONC[cid]["cond"]]
    campo = cond[0][0]
    out = {}
    for k, v in F.VISTA.items():
        if v["rubro"] != rubro:
            continue
        if all(CO.cumple(v, c) for c in cond):
            out[k] = "cumple"
        elif v.get(campo) in (None, "", []):
            out[k] = "sin_dato"
        else:
            out[k] = "no"
    return out


def rubros_de(p):
    r = {CONC[i]["nombre"] for c in p["cas"] if c["tipo"] == "rubro" for i in X._ids(c) if i in CONC}
    if not r:
        r = {v["rubro"] for c in p["cas"] if c["tipo"] == "modelo" for v in F.VISTA.values() if v["modelo"] in c["valor"]}
    return r


def casos_examen():
    """(texto que entra, rubro, verdad por producto, de donde sale)."""
    out = []
    for e in json.load(open(os.path.join(AQUI, "..", "examen", "examen.json"), encoding="utf-8")):
        for p in e["pedidos"]:
            for c in p["cas"]:
                t, val = c["tipo"], c["valor"]
                for r in rubros_de(p):
                    if t in ("atributo", "color", "plataforma") and isinstance(val, str) and val in CONC:
                        ver = verdad(val, r)
                        if any(x == "cumple" for x in ver.values()) or t == "atributo":
                            out.append((c["palabras"], CONC[val]["nombre"], r, ver, e["id"]))
                    elif t == "fuera" and val == "sin_dato":
                        ver = {k: "sin_dato" for k, v in F.VISTA.items() if v["rubro"] == r}
                        out.append((c["palabras"], c["palabras"], r, ver, e["id"]))
    return out


def casos_calibracion(usados):
    out = []
    for cid, c in CONC.items():
        if c["tipo"] not in ("atributo", "color", "plataforma") or cid in usados:
            continue
        for r in sorted({v["rubro"] for k, v in F.VISTA.items() if all(CO.cumple(v, tuple(x)) for x in c["cond"])}):
            out.append((c["nombre"], c["nombre"], r, verdad(cid, r), cid))
    return out


def contar(casos, umbral, cual):
    n = collections.Counter()
    for cl, co, r, ver, _ in casos:
        pred = veredictos(cl if cual == "cliente" else co, r, umbral)
        for k, v in ver.items():
            n[(v, pred[k])] += 1
    return n


def nota(n):
    ok = sum(x for (a, b), x in n.items() if a == b)
    falso = sum(x for (a, b), x in n.items() if b == "cumple" and a != "cumple")
    return ok - 3 * falso


def informe(n, titulo):
    tot = sum(n.values())
    print(f"  {titulo}: {tot} pares")
    for v in ("cumple", "no", "sin_dato"):
        fila = {b: n[(v, b)] for b in ("cumple", "no", "sin_dato")}
        s = sum(fila.values())
        if s:
            print(f"    verdad {v:8}: {s:5} -> cumple {fila['cumple']}, no {fila['no']}, sin dato {fila['sin_dato']}")
    falso = sum(x for (a, b), x in n.items() if b == "cumple" and a != "cumple")
    print(f"    cumple falsos: {falso} de {tot - sum(n[('cumple', b)] for b in ('cumple', 'no', 'sin_dato'))}"
          f" pares que no cumplen, {100 * falso / max(1, tot):.1f} por ciento del total")


if __name__ == "__main__":
    ex = casos_examen()
    usados = {e for e in CONC if any(co == CONC[e]["nombre"] for _, co, _, _, _ in ex)}
    cal = casos_calibracion(usados)
    print(f"calibracion: {len(cal)} conceptos por rubro que el examen no usa; prueba: {len(ex)} condiciones del examen")
    mejor = max((nota(contar(cal, u / 100, "concepto")), u / 100) for u in range(70, 96))
    U = mejor[1]
    print(f"umbral fijado en la calibracion: {U}")
    informe(contar(cal, U, "concepto"), "calibracion")
    for cual in ("concepto", "cliente"):
        informe(contar(ex, U, cual), f"examen, entrando {'el nombre del concepto' if cual == 'concepto' else 'las palabras del cliente'}")
    t = []
    for cl, co, r, ver, _ in ex[:20]:
        CACHE.pop(cl, None)
        t0 = time.time()
        veredictos(cl, r, U)
        t.append((time.time() - t0) / len(ver))
    print(f"  segundos por par, con las fichas ya calculadas: mediana {statistics.median(t):.4f}")
    print("\n  detalle del examen, nombre del concepto:")
    for cl, co, r, ver, i in ex:
        pred = veredictos(co, r, U)
        mal = collections.Counter((ver[k], pred[k]) for k in ver if ver[k] != pred[k])
        print(f"    {i:9} {co[:30]:30} {r[:14]:14} bien {sum(ver[k] == pred[k] for k in ver):3} de {len(ver):3}"
              + (f"  mal: {dict(mal)}" if mal else ""))
