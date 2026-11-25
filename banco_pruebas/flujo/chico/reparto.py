"""EL REPARTO, TECHO CON TRADUCCION PERFECTA (25-nov-2026). Ver el tercer plan de plan.md.

La traduccion sale de las etiquetas del examen. El codigo verifica exacto lo que esta en la lista cerrada; el modelo
chico solo dice si lo que no esta en la lista falta en todo el rubro. Candidatos: los grabados por la llamada unica.

    E5=<carpeta del modelo> PYTHONPATH=<donde esta tokenizers> python3 chico/reparto.py [--ver]
"""
import collections, json, os, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import condicion as C  # noqa: E402

X, F, CONC = C.X, C.F, C.CONC
U = 0.87
GRAB = os.path.join(AQUI, "..", "examen", "llamada_unica.jsonl")


def resolver(p, cand):
    """(decision, ofrecidos, nota) para un pedido etiquetado."""
    cas = [c for c in p["cas"] if c["modo"] not in ("pregunta", "anulado")]
    if any(c["tipo"] == "fuera" and c["valor"] == "no_vende" for c in cas):
        return "no_hay", [], "no vende"
    filtran = [c for c in cas if c["tipo"] in X.FILTRAN]

    def pasa(k):
        v = F.VISTA[k]
        return all((X._cumple(v, c) is False) if c["modo"] == "no" else X._cumple(v, c) for c in filtran)

    quedan = [k for k in map(tuple, cand) if k in F.VISTA and pasa(k)]
    orden = [c for c in cas if c["tipo"] == "orden"]
    if orden and quedan:
        rub = {F.VISTA[k]["rubro"] for k in quedan}
        quedan += [k for k, v in F.VISTA.items() if v["rubro"] in rub and k not in quedan and pasa(k)]
        campo, _, sentido = CONC[orden[0]["valor"]]["cond"][0]
        con = [k for k in quedan if F.VISTA[k][campo] is not None]
        quedan = sorted(con, key=lambda k: F.VISTA[k][campo], reverse=sentido == "desc") or quedan
    nota = ""
    abiertas = [c for c in cas if (c["tipo"] == "fuera" and c["valor"] == "sin_dato") or c["tipo"] == "dato"]
    for c in abiertas:
        rub = {F.VISTA[k]["rubro"] for k in quedan} or {F.VISTA[tuple(k)]["rubro"] for k in cand[:1]}
        if any(s >= U for r in rub for s in C.puntajes(c["palabras"], r).values()):
            return "repregunta", [], f"el chico ve parecido: {c['palabras']}"
        nota += f" sin dato: {c['palabras']};"
    if quedan:
        return "ofrece", quedan[:3], nota
    return "no_hay", [], nota


def main():
    ver = "--ver" in sys.argv
    ex = {e["id"]: e for e in json.load(open(os.path.join(AQUI, "..", "examen", "examen.json"), encoding="utf-8"))}
    g = [json.loads(x) for x in open(GRAB)]
    cuenta = collections.defaultdict(list)
    for r in g:
        e = ex[r["id"]]
        if len(e["pedidos"]) > 1:
            for p in e["pedidos"]:
                dec, of, nota = resolver(p, r["cand"])
                cuenta["varios pedidos, por linea"].append(X.corregir(e, dec, of))
            continue
        dec, of, nota = resolver(e["pedidos"][0], r["cand"])
        n = X.corregir(e, dec, of)
        cuenta["un pedido, dudosas" if e["dudosa"] else "un pedido, sin dudosas"].append(n)
        if ver and n != "acierta":
            print(f"  {n:10} {e['id']:11} {dec:10} {[k[2] for k in of]} {nota} | {e['texto'][:90]}")
    print(f"frases {len(g)}, traduccion perfecta de las etiquetas")
    for k in ("un pedido, sin dudosas", "un pedido, dudosas", "varios pedidos, por linea"):
        n = collections.Counter(cuenta[k])
        print(f"  {k}: {len(cuenta[k])} · acierta {n['acierta']}, repregunta {n['repregunta']}, erra {n['erra']}")


if __name__ == "__main__":
    main()
