"""SI LA CONDICION LLEGA DESDE LUNA AL CODIGO (26-nov-2026, pedido de Martin). FICHA 108, capa 3, la entrada.

Antes de construir la capa de condicion, se mide si lo que ella necesita sale de la rueda: por cada condicion etiquetada
con sus palabras literales, en el examen y en las reales del pozo, si esas palabras estan en la consulta de la fila de
Luna de ese pedido, y si Luna las marco con un nombre del vocabulario, condicion lista para atar, o las dejo sueltas.
La negacion, "que no sea Genius", cuenta si el "no" llega con ella.

    python3 primeros/condicion_llega.py [--ver]
"""
import collections, json, os, re, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
FL = os.path.join(AQUI, "..")
sys.path[:0] = [AQUI, os.path.join(FL, "examen")]
sys.dont_write_bytecode = True
_argv, sys.argv = sys.argv, ["x"]
import cadena as C  # noqa: E402
sys.argv = _argv
X, nrm = C.X, C.nrm
TIPOS = ("atributo", "color", "numero", "orden", "marca", "plataforma", "modelo", "compat")
CONJS = {"examen": (os.path.join(FL, "examen", "examen.json"), os.path.join(FL, "examen", "luna_b.jsonl")),
         "reales": (os.path.join(AQUI, "reales.json"), os.path.join(AQUI, "luna_reales.jsonl"))}


def _esta(ws, texto):
    """Cada palabra esta en el texto, con la ortografia que corrigio Luna: "inalanbrico" por "inalambrico", "1tb" por
    "1 tb", "tplink" por "tp link". Parecido de 0,75 por palabra, o la palabra entera sin espacios."""
    import difflib
    pegado = texto.replace(" ", "")
    return all(w in texto.split() or w in pegado or difflib.get_close_matches(w, texto.split(), 1, 0.75) for w in ws)


def main(ver):
    n, fallas = collections.Counter(), []
    for conj, (et, lu) in CONJS.items():
        ex = json.load(open(et, encoding="utf-8"))
        luna = {json.loads(l)["id"]: json.loads(l) for l in open(lu)}
        for e in ex:
            ts = (luna[e["id"]]["salida"] or {}).get("textos") or []
            filas = [(f, C.partes(t)) for t in ts for f in C.leer(t)[:1]]
            for p in e["pedidos"]:
                rs = {nrm(X.CONC[i]["nombre"]) for c in p["cas"] if c["tipo"] == "rubro" for i in X._ids(c)}
                mias = [x for x in filas if x[0]["rubro"] in rs] or filas
                texto = " ".join(nrm(x[0]["consulta"]) for x in mias)
                marcadas = " ".join(nrm(pa) for _, ps in mias for pa, nm in ps if nm)
                for c in p["cas"]:
                    if c["tipo"] not in TIPOS or c["modo"] not in ("", "no") or not c["palabras"]:
                        continue
                    ws = [w for w in nrm(c["palabras"]).split() if len(w) > 1 or w.isdigit()]
                    llega = _esta(ws, texto)
                    if not llega and _esta(ws, " ".join(nrm(x[0]["consulta"]) for x in filas)):
                        # Llega al codigo, pero en otra fila: "el mas barato" suelto, sin el rubro.
                        n[(conj, c["tipo"], "llega en otra fila")] += 1
                        n[(conj, "TOTAL", "llega en otra fila")] += 1
                        fallas.append(f"{conj} {e['id']} {c['tipo']} {c['palabras']!r} en otra fila")
                        continue
                    if c["modo"] == "no":
                        llega = llega and bool(re.search(r"\b(no|sin|ni)\b", texto))
                    marca = llega and all(w in marcadas for w in ws)
                    k = "llega marcada" if marca else ("llega suelta" if llega else "se pierde")
                    n[(conj, c["tipo"], k)] += 1
                    n[(conj, "TOTAL", k)] += 1
                    if k == "se pierde":
                        fallas.append(f"{conj} {e['id']} {c['tipo']} {c['palabras']!r} | {[x[0]['consulta'][:50] for x in mias]}")
    for (a, t, k), v in sorted(n.items()):
        print(f"  {a:7} {t:11} {k:14} {v}")
    if ver:
        for f in fallas:
            print("   ", f)


if __name__ == "__main__":
    main("--ver" in sys.argv)
