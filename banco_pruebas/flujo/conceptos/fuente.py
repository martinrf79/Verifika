"""LA VISTA DE LA FUENTE: CADA MODELO DE LA TIENDA CON SUS CAMPOS YA LEIDOS (24-nov-2026, FICHA en curso, paso 1).

Une productos.csv, compatibilidad.csv y specs_por_modelo.csv de la tienda en un diccionario por modelo, con los numeros
ya sacados del texto: capacidad, memoria, potencia, pulgadas y hz. Es lo unico que leen los conceptos y la
compatibilidad: si la fuente cambia de forma, se toca aca y nada mas.

    vista(k) -> dict      k = (rubro, marca, modelo)
"""
import csv, os, re, unicodedata
from collections import OrderedDict

TIENDA = os.environ.get("TIENDA_BANCO", "verifika_prod")
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "data", "clientes", TIENDA)


def nrm(s):
    s = "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()


def _leer(nombre):
    return list(csv.DictReader(open(os.path.join(D, nombre), encoding="utf-8")))


MOD = OrderedDict()
for p in _leer("productos.csv"):
    MOD.setdefault((p["categoria"], p["marca"], p["modelo"]), []).append(p)
COMPAT = {(c["categoria"], c["marca"], c["modelo"]): c for c in _leer("compatibilidad.csv")}
SPECS = {(s["categoria"], s["marca"], s["modelo"]): s for s in _leer("specs_por_modelo.csv")}
RUBROS = sorted({k[0] for k in MOD})


def _gb(texto, cual="ultimo"):
    """La capacidad en GB de un texto: '16GB 512GB SSD' -> 16 el primero, 512 el ultimo; '1TB' -> 1000."""
    m = re.findall(r"(\d+(?:\.\d+)?)\s*(TB|GB)", texto or "", re.I)
    if not m:
        return None
    n, u = m[0] if cual == "primero" else m[-1]
    return int(float(n) * (1000 if u.upper() == "TB" else 1))


def _num(texto, unidad):
    m = re.search(r"(\d+(?:\.\d+)?)\s*" + unidad, texto or "", re.I)
    return float(m.group(1)) if m else None


def _lista(x):
    return [v for v in (x or "").split("|") if v]


def vista(k):
    filas, c, s = MOD[k], COMPAT.get(k, {}), SPECS.get(k, {})
    p, rub, mod = filas[0], k[0], k[2]
    v = {
        "rubro": rub, "marca": k[1], "modelo": mod, "nombre": p["nombre"],
        "precio": min(int(f["precio_ars"]) for f in filas),
        "peso": min(int(f["peso_gramos"] or 999999) for f in filas),
        "color": [f["color"] for f in filas if f["color"]],
        "uso": p["uso_recomendado"], "origen": p["origen"], "material": p["material"], "extra": p["caracteristicas_extra"],
        "conecta_por": _lista(c.get("conecta_por")), "plataformas": _lista(c.get("plataformas")),
        "requiere": _lista(c.get("requiere")), "provee": _lista(c.get("provee")),
        "retroiluminacion": s.get("retroiluminacion") or "", "switch_teclado": s.get("switch_teclado") or "",
        "panel": s.get("panel") or "", "resolucion": s.get("resolucion") or "",
        "resistencia_agua": s.get("resistencia_agua") or "", "bateria": s.get("bateria") or "",
        "hz": _num(s.get("hz"), "hz"), "potencia_w": _num(s.get("potencia"), "w"),
        "memoria_video_gb": _gb(s.get("memoria_video")),
        "microfono": s.get("microfono") or "", "cancelacion_ruido": s.get("cancelacion_ruido") or "",
        "pulgadas": _num(s.get("pulgadas"), "pulgadas"), "nucleos": _num(s.get("nucleos"), "nucleos"),
        "fuente_recomendada_w": _num(s.get("fuente_recomendada"), "w"),
    }
    # La capacidad, segun el rubro: en el nombre del modelo, o la primera de la ficha.
    v["capacidad_gb"] = None
    if rub in ("memoria ram", "ssd", "almacenamiento externo"):
        v["capacidad_gb"] = _gb(mod)
    elif rub == "tablet":
        v["capacidad_gb"] = _gb(p["caracteristicas_extra"].split(",")[0])
    elif rub == "placa de video":
        v["capacidad_gb"] = v["memoria_video_gb"]
    # La notebook dice la ram y el disco en el nombre: "16GB 512GB SSD".
    v["ram_gb"] = _gb(mod, "primero") if rub == "notebook" else None
    v["disco_gb"] = _gb(mod) if rub == "notebook" else None
    if rub == "cargador" and v["potencia_w"] is None:
        v["potencia_w"] = _num(mod, "w")
    # Las pulgadas salen de la ficha, `pulgadas`, nunca del nombre: el monitor que no las tiene queda sin dato.
    return v


VISTA = {k: vista(k) for k in MOD}

if __name__ == "__main__":
    import collections
    llenos = collections.Counter(f for v in VISTA.values() for f, x in v.items() if x not in (None, "", []))
    print("campos con dato, por modelos:", dict(llenos))
    print("monitores sin pulgadas:", [k[2] for k, v in VISTA.items() if k[0] == "monitor" and not v["pulgadas"]])
