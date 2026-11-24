"""LA BASE DE CONOCIMIENTO DE CARACTERISTICAS, TRES GRUPOS POR ENTRADA (24-nov-2026). Ver plan.md.

Cada entrada: el concepto, las expresiones con que lo dice el cliente, y la condicion que el codigo ejecuta sobre la
fuente. Las expresiones salen del conocimiento general del habla argentina, no de las frases de prueba.

Condicion: (campo, operador, valor). Campos de `vista(k)`: los de productos.csv, compatibilidad.csv y
specs_por_modelo.csv de cada modelo. Operadores:
  alguno   el campo, una lista, tiene alguno de los valores
  ninguno  el campo, una lista, no tiene ninguno: "con cable" es no inalambrico
  tiene    el texto del campo contiene alguno de los valores, sin acentos ni mayusculas
  empieza  el texto del campo empieza con alguno de los valores
  min      el numero del campo es mayor o igual al valor
  orden    no filtra: ordena por el campo, "asc" o "desc"
"""
import os, re, sys, unicodedata
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(AQUI, "..", "traductor")]
sys.dont_write_bytecode = True
import catalogo as K  # noqa: E402
from columnas import S  # noqa: E402


def nrm(s):
    s = "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()


def vista(k):
    p, c, s = K.MOD[k][0], K.C[k], S.get(k, {})
    hz = re.match(r"(\d+)", s.get("hz") or "")
    return {
        "rubro": k[0], "marca": k[1], "modelo": k[2],
        "uso": p["uso_recomendado"], "origen": p["origen"], "material": p["material"], "extra": p["caracteristicas_extra"],
        "color": [r["color"] for r in K.MOD[k] if r["color"]],
        "peso": min(int(r["peso_gramos"] or 999999) for r in K.MOD[k]),
        "precio": min(int(r["precio_ars"]) for r in K.MOD[k]),
        "conecta_por": [x for x in c["conecta_por"].split("|") if x],
        "plataformas": [x for x in c["plataformas"].split("|") if x],
        "retroiluminacion": s.get("retroiluminacion") or "", "switch_teclado": s.get("switch_teclado") or "",
        "hz": int(hz.group(1)) if hz else None, "panel": s.get("panel") or "", "resolucion": s.get("resolucion") or "",
        "resistencia_agua": s.get("resistencia_agua") or "", "bateria": s.get("bateria") or "",
    }


def cumple(v, cond):
    campo, op, val = cond
    x = v.get(campo)
    if op == "alguno":
        return bool(set(x or []) & set(val))
    if op == "ninguno":
        return not set(x or []) & set(val)
    if op == "tiene":
        t = nrm(" ".join(x) if isinstance(x, list) else x)
        return any(nrm(a) in t for a in val)
    if op == "empieza":
        return any(nrm(x).startswith(nrm(a)) for a in val)
    if op == "min":
        return x is not None and x >= val
    return True  # orden: no filtra


# (concepto, [condiciones, todas], [expresiones])
BASE = [
    ("inalambrico", [("conecta_por", "alguno", ["bluetooth", "receptor_usb"])],
     ["inalambrico", "inalambricos", "sin cable", "sin cables", "wireless", "sin hilos", "que no tenga cable",
      "con bluetooth", "bluetooth", "blutu", "con receptor", "a pila", "inalambrica"]),
    ("con_cable", [("conecta_por", "ninguno", ["bluetooth", "receptor_usb"])],
     ["con cable", "cableado", "de cable", "alambrico", "que se enchufe", "por usb", "con cablecito"]),
    ("gamer", [("uso", "empieza", ["gaming"])],
     ["gamer", "para jugar", "pa jugar", "para juegos", "gaming", "para gamear", "para viciar", "para el lol",
      "para el fortnite", "para competitivo", "gamer pro"]),
    ("oficina", [("uso", "tiene", ["trabajo", "oficina", "productividad"])],
     ["para la oficina", "para trabajar", "para el laburo", "para estudiar", "para la facu", "para home office",
      "para el trabajo", "para la escuela", "para excel"]),
    ("streaming", [("uso", "tiene", ["streaming"])],
     ["para streamear", "para stream", "para hacer streaming", "para twitch", "para videollamadas", "para zoom"]),
    ("ps5", [("plataformas", "alguno", ["ps5"])],
     ["para la play 5", "play 5", "ps5", "para la ps5", "playstation 5", "la cinco", "la play nueva"]),
    ("ps4", [("plataformas", "alguno", ["ps4"])],
     ["para la play 4", "play 4", "ps4", "playstation 4", "la play vieja"]),
    ("play", [("plataformas", "alguno", ["ps4", "ps5"])],
     ["para la play", "la play", "playstation", "para la pley"]),
    ("xbox", [("plataformas", "alguno", ["xbox"])], ["para la xbox", "xbox", "para la equis box", "la x box"]),
    ("switch", [("plataformas", "alguno", ["nintendo_switch"])],
     ["para la switch", "nintendo switch", "la nintendo", "switch"]),
    ("mac", [("plataformas", "alguno", ["macos"])], ["para mac", "para la mac", "macbook", "para apple", "mac"]),
    ("iphone", [("plataformas", "alguno", ["ios"])], ["para iphone", "para el iphone", "para ipad", "para ios"]),
    ("android", [("plataformas", "alguno", ["android"])], ["para android", "para el celu", "para el celular", "para el telefono"]),
    ("pc", [("plataformas", "alguno", ["pc_escritorio", "windows", "notebook"])],
     ["para la pc", "para la compu", "para la computadora", "para windows", "para el escritorio", "para la notebook"]),
    ("tv", [("plataformas", "alguno", ["smart_tv"])], ["para la tele", "para el smart tv", "para la tv", "para el televisor"]),
    ("mecanico", [("switch_teclado", "tiene", ["mecanico"])],
     ["mecanico", "mecanica", "mecanicos", "de switches", "con switches", "clicky", "que suene clac", "switches rojos",
      "switches azules"]),
    ("membrana", [("switch_teclado", "tiene", ["membrana"])], ["de membrana", "membrana", "silencioso de goma"]),
    ("luces", [("retroiluminacion", "empieza", ["si"])],
     ["con luces", "con luz", "rgb", "retroiluminado", "que prenda", "con lucecitas", "iluminado", "con colores",
      "que brille"]),
    ("sin_luces", [("retroiluminacion", "empieza", ["no"])], ["sin luces", "sin rgb", "sin luz", "sin iluminacion"]),
    ("alta_frecuencia", [("hz", "min", 144)],
     ["144hz", "144 hz", "165hz", "de muchos hz", "alta tasa de refresco", "para competitivo de muchos hz", "144"]),
    ("ips", [("panel", "tiene", ["ips"])], ["ips", "panel ips", "pantalla ips"]),
    ("oled", [("panel", "tiene", ["oled"])], ["oled", "pantalla oled"]),
    ("full_hd", [("resolucion", "tiene", ["full hd"])], ["full hd", "1080p", "1080", "fullhd", "fhd"]),
    ("qhd", [("resolucion", "tiene", ["qhd", "2560x1440"])], ["2k", "qhd", "1440p", "2560"]),
    ("agua", [("resistencia_agua", "empieza", ["si"])],
     ["resistente al agua", "que no se moje", "contra salpicaduras", "sumergible", "a prueba de agua", "ip67"]),
    ("negro", [("color", "tiene", ["negro"])], ["negro", "negra", "negros", "black", "en negro", "oscuro"]),
    ("blanco", [("color", "tiene", ["blanco"])], ["blanco", "blanca", "blancos", "white", "en blanco"]),
    ("rojo", [("color", "tiene", ["rojo"])], ["rojo", "roja", "red", "colorado"]),
    ("azul", [("color", "tiene", ["azul"])], ["azul", "azulado"]),
    ("gris", [("color", "tiene", ["gris", "plata"])], ["gris", "plateado", "plata", "silver"]),
    ("rosa", [("color", "tiene", ["rosa"])], ["rosa", "rosado", "pink"]),
    ("chino", [("origen", "tiene", ["fabricado en china."])],
     ["chino", "china", "de china", "made in china", "chinos", "chinada", "chingado"]),
    ("barato", [("precio", "orden", "asc")],
     ["barato", "baratito", "economico", "el mas barato", "lo mas barato", "mas eco", "accesible", "que no sea caro",
      "barata", "lo mas economico", "bajo precio", "precio bajo"]),
    ("caro", [("precio", "orden", "desc")], ["el mas caro", "lo mejor", "tope de gama", "premium", "el mas top"]),
    ("liviano", [("peso", "orden", "asc")], ["liviano", "el mas liviano", "que pese poco", "livianito", "ligero", "poco peso"]),
]

# Las condiciones de negacion: "que no sea chino" niega la de chino. Las palabras que niegan, antes del concepto.
NIEGA = ("no", "sin", "nada de", "que no sea", "que no sean", "evitar", "menos")


def control():
    """Cada condicion de la base apunta a alguna fila del catalogo; devuelve las que no."""
    vs = [vista(k) for k in K.MOD]
    return [c for c, conds, _ in BASE if not any(all(cumple(v, x) for x in conds) for v in vs)]


if __name__ == "__main__":
    print("entradas", len(BASE), "expresiones", sum(len(e) for _, _, e in BASE), "sin filas:", control())
