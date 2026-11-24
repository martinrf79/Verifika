"""LA COMPATIBILIDAD CON EL EQUIPO DEL CLIENTE, POR CODIGO (24-nov-2026, paso 1).

El cliente dice que tiene: "mi placa es ddr5", "tengo un ryzen 5 5600", "pc con socket am4", "mother micro atx". Eso se
lee como familias de la columna requiere y provee de compatibilidad.csv. Un producto es compatible si, en esa familia,
lo que requiere o provee comparte algun valor con lo que tiene el cliente. Las plataformas, "para la play 5", son
conceptos de conceptos.py, no van aca.

    equipo(frase) -> [{"familia", "valores", "texto"}]
    cumple(v, familia, valores) -> True / False / None si el producto no tiene nada en esa familia
"""
import re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fuente as F  # noqa: E402

FAMILIAS = {
    "memoria": {"ddr4": "ranura_ddr4", "ddr5": "ranura_ddr5"},
    "socket": {"am4": "socket_am4", "am5": "socket_am5", "lga1700": "socket_lga1700", "1700": "socket_lga1700"},
    "disco": {"m2": "ranura_m2_nvme", "m 2": "ranura_m2_nvme", "nvme": "ranura_m2_nvme", "sata": "conector_sata"},
    "formato": {"micro atx": "formato_micro_atx", "matx": "formato_micro_atx", "atx": "formato_atx"},
}
TODOS = {v for f in FAMILIAS.values() for v in f.values()}
FAM_DE = {v: f for f, d in FAMILIAS.items() for v in d.values()}
DUENO = r"\b(mi|tengo|tiene|con|placa|mother|motherboard|madre|pc|compu|gabinete|equipo)\b"


def equipo(frase):
    s = F.nrm(frase)
    out = []
    # 1. lo que el cliente dice de su equipo: la palabra de la familia cerca de "mi", "tengo", "placa"...
    for fam, d in FAMILIAS.items():
        tomados = []
        for pal in sorted(d, key=len, reverse=True):
            for m in re.finditer(r"\b" + pal + r"\b", s):
                if any(m.start() < y and x < m.end() for x, y in tomados):
                    continue
                tomados.append(m.span())
                antes = s[max(0, m.start() - 30):m.start()]
                if re.search(DUENO, antes) and not re.search(r"\b(la|el|una|un)\s+\w+\s+\w+\s+\w+\s*$", antes[-20:]) or re.search(r"\b(placa|mother|motherboard|socket|pc)\s+(de\s+)?$", antes):
                    out.append({"familia": fam, "valores": {d[pal]}, "texto": m.group(0)})
                    break
    # 2. un producto de la tienda que el cliente dice que tiene: "tengo un ryzen 5 5600" -> lo que ese producto requiere
    for k, v in F.VISTA.items():
        if k[0] not in ("procesador", "motherboard", "memoria ram"):
            continue
        n = F.nrm(k[2])
        m = re.search(r"\b(tengo|mi|tiene)\b[a-z0-9 ]{0,12}\b" + re.escape(n) + r"\b", s)
        if m:
            for x in v["requiere"] + v["provee"]:
                if x in FAM_DE and not any(o["familia"] == FAM_DE[x] for o in out):
                    out.append({"familia": FAM_DE[x], "valores": {x}, "texto": n})
    # una familia, un valor: si salio dos veces, se juntan
    junto = {}
    for o in out:
        junto.setdefault(o["familia"], {"familia": o["familia"], "valores": set(), "texto": o["texto"]})["valores"] |= o["valores"]
    return list(junto.values())


def cumple(v, familia, valores):
    suyos = {x for x in v["requiere"] + v["provee"] if FAM_DE.get(x) == familia}
    if not suyos:
        return None
    return bool(suyos & set(valores))


CASOS = [
    ("tengo pc de escritorio con placa ddr5, si la kingston fury beast ddr4 16gb no va que otra memoria hay", {"memoria": {"ranura_ddr5"}}),
    ("tengo un ryzen 5 5600, que cooler me sirve", {"socket": {"socket_am4"}}),
    ("mi mother es am5", {"socket": {"socket_am5"}}),
    ("tenes un ssd m.2 para mi pc", {}),
    ("mi placa tiene m.2", {"disco": {"ranura_m2_nvme"}}),
    ("la kingston fury beast ddr4 cuanto sale", {}),
    ("gabinete para placa micro atx", {"formato": {"formato_micro_atx"}}),
]

if __name__ == "__main__":
    mal = 0
    for fr, esp in CASOS:
        got = {o["familia"]: o["valores"] for o in equipo(fr)}
        ok = got == esp
        mal += not ok
        print("ok " if ok else "MAL", fr[:70], "->", got)
    print(f"{len(CASOS) - mal} de {len(CASOS)} casos")
    ram = [k[2] for k, v in F.VISTA.items() if k[0] == "memoria ram" and cumple(v, "memoria", {"ranura_ddr5"})]
    print("memorias ddr5 compatibles:", len(ram), ram[:3])
