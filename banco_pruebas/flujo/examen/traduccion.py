"""LA TRADUCCION DE LUNA SOLA, CONTRA LO ETIQUETADO (25-nov-2026). Ver el ultimo plan de plan.md.

Mide solo el primer proceso: que entendio Luna de lo que quiere el cliente. No toca la tienda. Sin gasto: lee lo que
Luna ya devolvio en `luna_conceptos.jsonl`.

    python3 examen/traduccion.py [--ver]
"""
import collections, json, os, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [AQUI, os.path.join(AQUI, "..", "conceptos")]
sys.dont_write_bytecode = True
import fuente as F  # noqa: E402

nrm = lambda t: F.nrm(str(t or "")).replace(" ", "").replace("-", "")
NO_CUENTA = {"cantidad", "compat"}


def esperado(p, e):
    """Lo etiquetado del pedido como un juego de (casillero, valor) que se puede comparar con lo de Luna."""
    out = []
    for c in p["cas"] + e.get("global", []):
        t, v, m = c["tipo"], c["valor"], c["modo"]
        if t in NO_CUENTA or m == "anulado" or (t == "fuera" and v == "ignorar"):
            continue
        if t == "rubro":
            out.append(("rubro", frozenset(v if isinstance(v, list) else [v])))
        elif t in ("atributo", "color", "plataforma", "preferencia", "origen"):
            out.append(({"no": "negado", "pregunta": "pregunta"}.get(m, "concepto"), v))
        elif t == "marca":
            out.append(("marca_negada" if m == "no" else "marca", (c["palabras"], v)))
        elif t == "modelo":
            out.append(("modelo", (c["palabras"], tuple(v))))
        elif t == "numero":
            out.append(("numero", tuple(v)))
        elif t == "orden":
            out.append(("orden", v.split(":")[1]))
        elif t == "fuera" and v == "no_vende":
            out.append(("no_vende", True))
        elif t == "fuera" and v == "sin_dato":
            out.append(("abierta", c["palabras"]))
        elif t == "dato":
            out.append(("abierta", c["palabras"]))
    return out


def bien(k, v, f):
    """Si la fila de Luna trae el casillero etiquetado."""
    if k == "rubro":
        return bool(v & set(i for i in f["conceptos"] if i.startswith("rubro:")))
    if k == "concepto":
        return v in f["conceptos"]
    if k == "negado":
        return v in f["negados"]
    if k == "pregunta":
        return v in f["preguntas"] or v in f["conceptos"]
    if k in ("marca", "marca_negada"):
        l = nrm(f[k])
        return bool(l) and l in (nrm(v[0]), nrm(v[1]))
    if k == "modelo":
        l = nrm(f["modelo"])
        return bool(l) and (l == nrm(v[0]) or any(l == nrm(m) for m in v[1]))
    if k == "numero":
        return any(n["campo"] == v[0] and n["op"] == v[1] and float(n["valor"]) == float(v[2]) for n in f["numeros"])
    if k == "orden":
        return f["orden"] == v
    if k == "no_vende":
        return f["no_vende"]
    if k == "abierta":
        return any(nrm(v) in nrm(a) or nrm(a) in nrm(v) for a in f["abiertas"])
    raise ValueError(k)


def agregados(esp, f):
    """Lo que Luna puso que filtra y no esta etiquetado."""
    tiene = collections.defaultdict(set)
    for k, v in esp:
        tiene[k].add(v)
    out = []
    if f["no_vende"] and "no_vende" not in tiene:
        out.append("no_vende")
    rub = set().union(*tiene["rubro"]) if tiene["rubro"] else set()
    for i in f["conceptos"]:
        if i.startswith("rubro:"):
            if rub and i not in rub:
                out.append(i)
            elif not rub:
                out.append(i)
        elif i not in tiene["concepto"] and i not in tiene["pregunta"] and not i.startswith("preferencia:"):
            out.append(i)
    for i in f["negados"]:
        if i not in tiene["negado"]:
            out.append("no " + i)
    if f["marca"] and not tiene["marca"]:
        out.append("marca " + f["marca"])
    if f["modelo"] and not tiene["modelo"]:
        out.append("modelo " + f["modelo"])
    for n in f["numeros"]:
        if not any(n["campo"] == v[0] and n["op"] == v[1] and float(n["valor"]) == float(v[2]) for v in tiene["numero"]):
            out.append(f"numero {n['campo']} {n['op']} {n['valor']}")
    if f["orden"] != "ninguno" and f["orden"] not in tiene["orden"]:
        out.append("orden " + f["orden"])
    return out


def main(ver):
    ex = {e["id"]: e for e in json.load(open(os.path.join(AQUI, "examen.json"), encoding="utf-8"))}
    por = collections.defaultdict(collections.Counter)
    frases = collections.Counter()
    for x in open(os.path.join(AQUI, "luna_conceptos.jsonl")):
        r = json.loads(x)
        e = ex[r["id"]]
        if len(e["pedidos"]) > 1 or e["dudosa"]:
            continue
        filas = [f for f in ((r["salida"] or {}).get("filas") or []) if f.get("producto")]
        f = filas[0] if filas else None
        esp = esperado(e["pedidos"][0], e)
        if f is None:
            for k, _ in esp:
                por[k]["falta"] += 1
            frases["sin fila de producto"] += 1
            if ver:
                print(f"  SIN FILA   {r['id']:11} {e['texto'][:100]}")
            continue
        faltan = [(k, v) for k, v in esp if not bien(k, v, f)]
        for k, v in esp:
            por[k]["bien" if (k, v) not in faltan else "falta o mal"] += 1
        de_mas = agregados(esp, f)
        for a in de_mas:
            por["agregado"][a.split(":")[0].split(" ")[0]] += 1
        frases["entera bien" if not faltan and not de_mas else "con fallas"] += 1
        if ver and (faltan or de_mas):
            print(f"  {r['id']:11} {e['texto'][:100]}")
            print(f"              falta o mal: {[(k, v if not isinstance(v, frozenset) else sorted(v)) for k, v in faltan]}")
            print(f"              agrega: {de_mas}")
    print(f"frases de un pedido sin dudosas: {sum(frases.values())}")
    print(f"  traduccion entera bien {frases['entera bien']}, con fallas {frases['con fallas']},"
          f" sin fila de producto {frases['sin fila de producto']}")
    print("  por casillero etiquetado:")
    for k, n in sorted(por.items()):
        if k != "agregado":
            print(f"    {k:13} bien {n['bien']:3}, falta o mal {n['falta o mal'] + n['falta']:3}")
    print(f"  lo que agrega sin estar etiquetado: {dict(por['agregado'])}")


if __name__ == "__main__":
    main("--ver" in sys.argv)
