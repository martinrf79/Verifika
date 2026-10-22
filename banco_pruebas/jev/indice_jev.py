"""El indice en niveles para Jev, armado SOLO con lo que ya existe en el repo: alias.json, faq.json, filtros_catalogo.vocabulario,
specs_preguntables.json y compatibilidad.csv. Jev nunca lee el catalogo entero."""
import json, os, sys, csv, collections
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D)
from fuente import PS, FAQ, K, n, REPO
TID = "verifika_prod"
AL = json.load(open(os.path.join(REPO, f"data/clientes/{TID}/alias.json")))
SPECS = {s["id"]: s for s in json.load(open(os.path.join(REPO, f"data/clientes/{TID}/specs_preguntables.json")))["specs"]}
COMPAT = {(r["marca"], r["modelo"]): r for r in csv.DictReader(open(os.path.join(REPO, f"data/clientes/{TID}/compatibilidad.csv")))}
RUBROS = sorted({p["categoria"] for p in PS})
NOMBRE = {"fuente": "fuente de alimentacion para PC", "parlante": "parlante o altavoz", "silla gamer": "silla gamer o de escritorio"}

def desc_rubro(r):
    return f"{NOMBRE.get(r, r)}; tambien le dicen: {', '.join((AL.get('rubros') or {}).get(r, [])[:8])}"
def desc_tema(f):
    return f"{f['tema'].replace('_', ' ')}: {', '.join(f.get('keywords', [])[:6])}"

def nivel1():
    """Rubros y temas, un renglon cada uno."""
    return ("RUBROS DE LA TIENDA:\n" + "\n".join(f"- {desc_rubro(r)}" for r in RUBROS)
            + "\n\nTEMAS DE LAS REGLAS DE LA TIENDA:\n" + "\n".join(f"- {desc_tema(f)}" for f in FAQ))

CORTOS = 40  # un valor mas largo es prosa: no sirve como opcion
NO = {"descripcion", "dimensiones", "modelo", "nombre", "garantia_detalle", "contenido_caja", "caracteristicas_extra", "origen", "uso_recomendado", "descripcion_rica", "tags", "material"}
from app.core.filtros_catalogo import campos_filtrables
TIPOS = campos_filtrables(TID)
def valor_indice(campo, v):
    """Un campo de si o no se indexa por su veredicto: "si, retroiluminacion rgb" y "si, teclado retroiluminado" son "si"."""
    v = n(v)
    if TIPOS.get(campo) == "si_no" and v[:2] in ("si", "no"): return v[:2]
    return v
import re as _re
_ORIGEN = _re.compile(r"marca .*? de ([a-z ]+)\. fabricad[oa] en ([a-z ,]+?)(?: segun linea)?\.")
def derivados(p):
    """Lo que la fuente dice en prosa y se puede partir sin inventar: el origen en pais de la marca y pais de fabricacion."""
    m = _ORIGEN.match(n(p.get("origen") or ""))
    return {"pais_marca": m.group(1), "pais_fabricacion": m.group(2)} if m else {}
def valores(r):
    """Por rubro, cada campo con sus valores distintos, cortos: lo que Jev elige en el nivel 2. Mas 'anda con'."""
    out = collections.defaultdict(collections.Counter)
    for p in PS:
        if p["categoria"] != r: continue
        campos = {k: v for k, v in p.items() if k not in NO and k not in ("id", "categoria", "precio_ars", "stock", "peso_gramos", "specs", "compat", "garantia_meses") and isinstance(v, (str, int, float)) and v != ""}
        campos.update({k: v for k, v in (p.get("specs") or {}).items() if v})
        campos.update(derivados(p))
        for k, v in campos.items():
            v = valor_indice(k, v)
            if 0 < len(v) <= CORTOS: out[k][v] += 1
        c = COMPAT.get((p.get("marca"), p.get("modelo")))
        if c:
            for t in c["plataformas"].split("|"):
                if t: out["anda_con"][t] += 1
    return {k: sorted(v) for k, v in out.items() if len(v) >= 2}
def nivel2(r):
    vs = valores(r)
    precios = sorted(K.entero(p.get("precio_ars")) for p in PS if p["categoria"] == r)
    return (f"RUBRO {NOMBRE.get(r, r)}. Precios de ${precios[0]} a ${precios[-1]}.\nDATOS QUE TIENEN SUS PRODUCTOS, campo: valores posibles:\n"
            + "\n".join(f"- {(SPECS.get(k) or {}).get('etiqueta', k.replace('_', ' '))} [{k}]: {' | '.join(v)}" for k, v in vs.items()))
def opciones2(r):
    return {f"{k}={v}": f"{(SPECS.get(k) or {}).get('etiqueta', k.replace('_', ' '))}: {v}" for k, vs in valores(r).items() for v in vs}

def productos_con(r, campo, valor):
    """Lo que el codigo devuelve para un campo=valor elegido por Jev: deterministico."""
    out = set()
    for p in PS:
        if p["categoria"] != r or not K.con_stock(p): continue
        if campo == "anda_con":
            c = COMPAT.get((p.get("marca"), p.get("modelo")))
            if c and valor in c["plataformas"].split("|"): out.add(str(p["id"]))
        else:
            v = derivados(p).get(campo) or (p.get(campo) if p.get(campo) not in (None, "") else (p.get("specs") or {}).get(campo))
            if v and valor_indice(campo, v) == valor: out.add(str(p["id"]))
    return out

if __name__ == "__main__":
    import math
    print("nivel 1:", len(nivel1()), "caracteres")
    tams = {r: len(nivel2(r)) for r in RUBROS}; print("nivel 2 por rubro, caracteres:", sorted(tams.values()))
    print("opciones nivel 2 max:", max(len(opciones2(r)) for r in RUBROS))
    print(nivel2("mouse")[:1500])
SPECS.setdefault("pais_marca", {"etiqueta": "el pais de origen de la marca"})
SPECS.setdefault("pais_fabricacion", {"etiqueta": "el pais donde se fabrica"})
SPECS.setdefault("anda_con", {"etiqueta": "con que equipos, consolas o sistemas anda"})
