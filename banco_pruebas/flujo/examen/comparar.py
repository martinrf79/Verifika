"""UN CAMBIO AL RESOLVEDOR, MEDIDO EN LAS CUATRO MUESTRAS (24-nov-2026). El examen fijo y las tres muestras de antes: las
48 de la FICHA 105, muestra2 y muestra3, cada una contra sus hashes. Un cambio entra solo si no empeora en ninguna: el
examen ya se miro para encontrar la clase, las otras tres no se miraron para esto. No escribe nada en reglas/.

    E5=<carpeta de e5> <venv>/bin/python examen/comparar.py <etiqueta>     # graba examen/comparar_<etiqueta>.json
"""
import collections, hashlib, importlib, json, os, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
RG, TR = os.path.join(AQUI, "..", "reglas"), os.path.join(AQUI, "..", "traductor")
sys.path[:0] = [AQUI, RG, TR]
sys.dont_write_bytecode = True
import examen as X  # noqa: E402
import resolver as RV  # noqa: E402
import acept as A  # noqa: E402

C = json.load(open(RV.CORTES))


def correr(fr):
    return RV.resolver(fr, C["alto"], C["bajo"], RV.topes(fr))


def cuenta(xs):
    c = collections.Counter(xs)
    return [c["acierta"], c["repregunta"], c["erra"]]


def examen():
    ex, _, h = X.congelar()
    assert h == open(os.path.join(AQUI, "hash.txt")).read().strip(), "el examen cambio"
    out = {}
    for e in ex:
        dec, of, _ = correr(e["texto"])
        out[e["id"]] = (X.corregir(e, dec, of), e["dudosa"] or len(e["pedidos"]) > 1)
    return out


def m48():
    from muestra import M
    assert hashlib.sha256(open(os.path.join(TR, "muestra.py"), "rb").read()).hexdigest() in open(os.path.join(TR, "hash.txt")).read()
    AC = json.load(open(os.path.join(TR, "aceptables.json")))
    out = {}
    for m, ac in zip(M, AC):
        dec, of, _ = correr(m[2])
        out[m[1]] = (RV.corregir(dec, of, ac), m[4])
    return out


def mn(n):
    Mn = getattr(importlib.import_module("muestra" + n), "M" + n)
    assert hashlib.sha256(open(os.path.join(RG, f"muestra{n}.py"), "rb").read()).hexdigest() in open(os.path.join(RG, f"hash{n}.txt")).read()
    out = {}
    for f, fr, r, dud, _ in Mn:
        r2 = dict(r); caro = r2.pop("caro", False); ac = A.acept(r2)
        if caro:
            mx = max(RV.VISTA[k]["precio"] for k in ac); ac = {k for k in ac if RV.VISTA[k]["precio"] == mx}
        dec, of, _ = correr(fr)
        out[f] = (RV.corregir(dec, of, sorted(ac)), dud)
    return out


if __name__ == "__main__":
    et = sys.argv[1]
    res = {"examen": examen(), "m48": m48(), "muestra2": mn("2"), "muestra3": mn("3")}
    json.dump(res, open(os.path.join(AQUI, f"comparar_{et}.json"), "w"), ensure_ascii=False, indent=0)
    print(et, "· acierta, repregunta, erra · limpias es sin dudosas, y en el examen ademas de un pedido")
    for k, r in res.items():
        print(f"  {k:9} todas {cuenta([c for c, _ in r.values()])}   limpias {cuenta([c for c, d in r.values() if not d])}")
