"""EL EXAMEN FIJO DEL TRADUCTOR, FICHA 106 paso 2 (24-nov-2026).

Frases reales de `pozo.json`, que ninguna prueba ni ajuste uso, etiquetadas por casillero en `etiquetas.py` con los ids de
`conceptos/conceptos.json`. Nunca se usa para entrenar ni para fijar umbrales: solo para medir. Congelado con hash en
`hash.txt`; si el hash cambia, el examen ya no es el mismo y las medidas no se comparan.

La respuesta correcta es una regla sobre el catalogo: `aceptables(pedido)` filtra la vista de la fuente con los
casilleros exigidos; la preferencia, el orden, la cantidad y el dato no filtran. Al congelar se controla:
  - cada pedazo de `palabras` esta literal en la frase normalizada;
  - cada concepto existe en conceptos.json y cada modelo nombrado esta en el catalogo;
  - lo esperado cuadra con el catalogo: si solo vale no_hay, no queda nada; si vale ofrecer y no no_hay, queda algo.

    python3 examen/examen.py            # controla, escribe examen.json y hash.txt
    python3 examen/examen.py --verificar   # solo compara contra hash.txt, sin escribir nada
"""
import collections, hashlib, json, os, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [AQUI, os.path.join(AQUI, "..", "conceptos")]
sys.dont_write_bytecode = True
import fuente as F  # noqa: E402
import conceptos as CO  # noqa: E402
import compat as CP  # noqa: E402
from etiquetas import L  # noqa: E402

CONC = json.load(open(os.path.join(AQUI, "..", "conceptos", "conceptos.json"), encoding="utf-8"))
nrm = F.nrm
FILTRAN = {"rubro", "atributo", "plataforma", "color", "origen", "marca", "modelo", "numero", "compat"}


def _ids(c):
    v = c["valor"]
    return v if isinstance(v, list) else [v]


def _cumple(v, c):
    t, val = c["tipo"], c["valor"]
    if t == "rubro":
        return any(CONC[i]["nombre"] == v["rubro"] for i in _ids(c))
    if t in ("atributo", "plataforma", "color", "origen"):
        return all(CO.cumple(v, tuple(x)) for x in CONC[val]["cond"])
    if t == "marca":
        return nrm(v["marca"]) == nrm(val)
    if t == "modelo":
        return v["modelo"] in val
    if t == "numero":
        campo, op, x = val
        return campo == "precio_total" or CO.cumple(v, (campo, op, x))
    if t == "compat":
        fam, vals = val
        return CP.cumple(v, fam, set(vals)) is True
    return True


def aceptables(pedido):
    """Los modelos de la tienda que valen para el pedido: (rubro, marca, modelo)."""
    if any(c["tipo"] == "fuera" and c["valor"] == "no_vende" and c["modo"] == "" for c in pedido["cas"]):
        return []
    out = []
    for k, v in F.VISTA.items():
        ok = True
        for c in pedido["cas"]:
            if c["tipo"] not in FILTRAN or c["modo"] in ("pregunta", "anulado"):
                continue
            r = _cumple(v, c)
            if (c["modo"] == "no" and r) or (c["modo"] == "" and not r):
                ok = False
                break
        if ok:
            out.append(k)
    return out


def controlar(texto, e):
    """Lista de problemas de una etiqueta; vacia si esta bien."""
    malos = []
    t = nrm(texto)
    modelos = {k[2] for k in F.VISTA}
    for i, p in enumerate(e["pedidos"]):
        for c in p["cas"] + (e["global"] if i == 0 else []):
            if nrm(c["palabras"]) not in t:
                malos.append(f"'{c['palabras']}' no esta en la frase")
            if c["tipo"] in ("rubro", "atributo", "preferencia", "plataforma", "color", "origen", "orden"):
                for x in _ids(c):
                    if x not in CONC:
                        malos.append(f"concepto {x} no existe")
            if c["tipo"] == "modelo":
                for m in c["valor"]:
                    if m not in modelos:
                        malos.append(f"modelo {m} no esta en el catalogo")
        n = len(aceptables(p))
        esp = set(p["esperados"])
        if esp == {"no_hay"} and n:
            malos.append(f"pedido {i}: solo vale no_hay y quedan {n}")
        if "ofrecer" in esp and "no_hay" not in esp and not n:
            malos.append(f"pedido {i}: vale ofrecer y no queda nada")
    return malos


def congelar():
    pozo = json.load(open(os.path.join(AQUI, "pozo.json"), encoding="utf-8"))
    ex, problemas = [], {}
    for i, e in sorted(L.items()):
        texto = pozo[i]["texto"]
        m = controlar(texto, e)
        if m:
            problemas[i] = m
        ex.append({"id": f"{pozo[i]['fuente']}:{i}", "texto": texto, **e})
    crudo = json.dumps(ex, ensure_ascii=False, sort_keys=True)
    h = hashlib.sha256(crudo.encode()).hexdigest()
    return ex, problemas, h


if __name__ == "__main__":
    ex, problemas, h = congelar()
    if "--verificar" in sys.argv:
        fijo = open(os.path.join(AQUI, "hash.txt")).read().strip()
        sys.exit(0 if h == fijo and not problemas else f"el examen cambio: {h} contra {fijo}")
    for i, m in problemas.items():
        print(i, m)
    if problemas:
        sys.exit(f"{len(problemas)} etiquetas con problemas: no se congela")
    json.dump(ex, open(os.path.join(AQUI, "examen.json"), "w"), ensure_ascii=False, indent=1)
    open(os.path.join(AQUI, "hash.txt"), "w").write(h + "\n")
    ped = sum(len(e["pedidos"]) for e in ex)
    cas = collections.Counter(c["tipo"] for e in ex for p in e["pedidos"] for c in p["cas"] + e["global"])
    esp = collections.Counter(x for e in ex for p in e["pedidos"] for x in p["esperados"])
    print(f"frases {len(ex)}, dudosas {sum(e['dudosa'] for e in ex)}, pedidos {ped}")
    print("casilleros:", dict(cas.most_common()))
    print("esperados:", dict(esp.most_common()))
    print("hash", h)
