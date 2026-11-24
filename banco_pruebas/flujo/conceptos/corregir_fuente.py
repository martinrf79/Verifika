"""CORRIGE LA FUENTE DE LA TIENDA: LAS CARACTERISTICAS DE PLANTILLA Y LOS DATOS QUE FALTABAN (24-nov-2026).

Orden de Martin del 24-nov. Lo encontrado al armar el paso 1:
- `caracteristicas_extra` repetia el mismo texto en todos los modelos de 15 rubros: todos los monitores "IPS Full HD 75Hz",
  todas las placas "8GB GDDR6", todas las fuentes "550W", todos los procesadores "6 nucleos", todos los routers
  "WiFi 5", todas las motherboards "DDR4". Ese texto se repite en `descripcion`, `descripcion_rica` y en las etiquetas.
- Faltaban: las pulgadas de los monitores, el microfono y la cancelacion de ruido de los auriculares, el consumo y la
  fuente recomendada de las placas, los nucleos de los procesadores y el estandar WiFi de los routers.

De donde sale cada dato:
- de la ficha, `specs_por_modelo.csv`, cuando ya lo traia: monitores, placas, fuentes, coolers, parlantes;
- de la compatibilidad, `compatibilidad.csv`: memoria y socket de las motherboards, formato de los gabinetes;
- del dato publico del fabricante, en las tablas de abajo, modelo por modelo. Lo que no se sabe con certeza queda vacio:
  el Samsung ViewFinity S6 sin pulgadas; tablets, cargadores y sillas no se tocan.

    python3 corregir_fuente.py          # muestra lo que cambiaria
    python3 corregir_fuente.py --grabar # reescribe los CSV y specs_preguntables.json
"""
import csv, io, json, os, re, sys

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "data", "clientes", "verifika_prod")

PULGADAS = {  # clase comercial, como se vende
    ("AOC", "24B2XH"): 24, ("AOC", "24G2"): 24, ("AOC", "27G2"): 27, ("Asus", "ProArt PA248QV"): 24,
    ("Asus", "TUF VG249Q1A"): 24, ("Asus", "TUF VG279Q1A"): 27, ("Dell", "S2421HN"): 24, ("Gigabyte", "G24F 2"): 24,
    ("Gigabyte", "M27Q"): 27, ("LG", "24MK430H"): 24, ("LG", "27GP850 UltraGear"): 27, ("LG", "29WP60G UltraWide"): 29,
    ("LG", "32GN600"): 32, ("LG", "34WP65C Curvo"): 34, ("MSI", "G274F"): 27, ("Philips", "242V8A"): 24,
    ("Philips", "271E1"): 27, ("Samsung", "Odyssey G3 24"): 24, ("Samsung", "Odyssey G5 32"): 32,
    ("Samsung", "Odyssey G9 49"): 49, ("Samsung", "T35F 24"): 24, ("ViewSonic", "VA2406"): 24, ("ViewSonic", "VX2718"): 27,
}
NUCLEOS = {
    "Core i5-12400F": (6, 12), "Core i5-13400F": (10, 16), "Core i5-14600KF": (14, 20), "Core i7-13700KF": (16, 24),
    "Ryzen 5 5600": (6, 12), "Ryzen 5 7600": (6, 12), "Ryzen 7 5800X3D": (8, 16), "Ryzen 7 7800X3D": (8, 16),
    "Ryzen 5 5500": (6, 12), "Core i3-12100F": (4, 8), "Core i3-14100F": (4, 8), "Core i5-13600KF": (14, 20),
    "Core i7-14700KF": (20, 28), "Core i9-14900K": (24, 32), "Ryzen 5 5600X": (6, 12), "Ryzen 5 7500F": (6, 12),
    "Ryzen 7 7700X": (8, 16), "Ryzen 9 7900X": (12, 24), "Ryzen 5 8400F": (6, 12),
}
WIFI = {
    "Archer C6": "WiFi 5 AC1200", "Archer AX23": "WiFi 6 AX1800", "Halo H30G": "WiFi 5 AC1300", "AC10": "WiFi 5 AC1200",
    "Deco M4 Mesh": "WiFi 5 AC1200", "Archer AX55": "WiFi 6 AX3000", "Archer AX73": "WiFi 6 AX5400",
    "Deco X50 Mesh": "WiFi 6 AX3000", "MR70X": "WiFi 6 AX1800", "AC8": "WiFi 5 AC1200", "Nova MW6 Mesh": "WiFi 5 AC1200",
}
MICROFONO = {
    "Cloud II": "si, microfono desmontable", "Cloud III": "si, microfono desmontable", "Cloud Alpha": "si, microfono desmontable",
    "G Pro X": "si, microfono desmontable", "BlackShark V2": "si, microfono desmontable", "G733 Lightspeed": "si, microfono desmontable",
    "Cloud Stinger 2": "si, microfono abatible", "Quantum 200": "si, microfono abatible", "G535": "si, microfono abatible",
    "Kraken V3": "si, microfono retractil", "Kraken Kitty V2": "si, microfono retractil",
    "Zeus X": "si, microfono incluido", "Pandora": "si, microfono incluido", "G435": "si, microfono integrado",
    "WH-1000XM5": "si, microfono integrado para llamadas", "WH-CH520": "si, microfono integrado para llamadas",
    "Tune 510BT": "si, microfono integrado para llamadas", "Tune 770NC": "si, microfono integrado para llamadas",
    "WH-CH720N": "si, microfono integrado para llamadas", "ULT Wear": "si, microfono integrado para llamadas",
    "Tune 520BT": "si, microfono integrado para llamadas", "HD 560S": "no, sin microfono", "HD 599": "no, sin microfono",
}
CON_ANC = {"WH-1000XM5", "Tune 770NC", "WH-CH720N", "ULT Wear"}
PLACAS = {  # chip: (consumo en W, fuente recomendada en W, quien la recomienda)
    "RTX 4060 Ti": (160, 550, "NVIDIA"), "RTX 4060": (115, 550, "NVIDIA"), "RTX 4070 Ti Super": (285, 700, "NVIDIA"),
    "RTX 4070 Super": (220, 650, "NVIDIA"), "RTX 4070": (200, 650, "NVIDIA"), "RTX 4080 Super": (320, 750, "NVIDIA"),
    "RX 7600 XT": (190, 600, "AMD"), "RX 7600": (165, 550, "AMD"), "RX 7700 XT": (245, 700, "AMD"),
    "RX 7800 XT": (263, 700, "AMD"), "RX 7900 XT": (315, 750, "AMD"),
}
CANALES = {"Z313": "2.1", "Z207 Bluetooth": "2.0", "R1280T": "2.0", "Go 3": "portatil", "Flip 6": "portatil",
           "SP-HF180": "2.0", "Z625 THX": "2.1", "Z906 5.1": "5.1", "R1700BT": "2.0", "Charge 5": "portatil",
           "Clip 4": "portatil", "SW-2.1 375": "2.1"}
SOLO_CAMBIA = {("webcam", "C270 HD"): "HD 720p", ("microfono", "MV7"): "USB y XLR",
               ("impresora", "HL-1212W"): "solo impresora, laser monocromatica"}
RESOL_TAGS = {"Full HD": ["full hd", "fhd", "1080p"], "QHD": ["qhd", "2k", "1440p"], "WUXGA": ["wuxga"],
              "UltraWide": ["ultrawide"], "UWQHD": ["ultrawide", "uwqhd"], "DQHD": ["dqhd", "super ultrawide"]}


def leer(nombre):
    raw = open(os.path.join(D, nombre), encoding="utf-8", newline="").read()
    filas = list(csv.reader(io.StringIO(raw)))
    return filas[0], [dict(zip(filas[0], f)) for f in filas[1:]]


def escribir(nombre, cab, filas):
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\r\n")
    w.writerow(cab)
    w.writerows([[f.get(c, "") for c in cab] for f in filas])
    open(os.path.join(D, nombre), "w", encoding="utf-8", newline="").write(out.getvalue())


def chip(modelo):
    return next((c for c in sorted(PLACAS, key=len, reverse=True) if c in modelo), None)


def specs_nuevas(cab, specs):
    """Columnas nuevas y datos que faltaban en specs_por_modelo.csv."""
    for c in ("pulgadas", "microfono", "cancelacion_ruido", "fuente_recomendada", "nucleos"):
        if c not in cab:
            cab.append(c)
    for s in specs:
        cat, mar, mod = s["categoria"], s["marca"], s["modelo"]
        if cat == "monitor" and (mar, mod) in PULGADAS:
            s["pulgadas"] = f"{PULGADAS[(mar, mod)]} pulgadas"
        if cat == "auriculares" and mod in MICROFONO:
            s["microfono"] = MICROFONO[mod]
            s["cancelacion_ruido"] = "si, cancelacion activa de ruido" if mod in CON_ANC else "no, sin cancelacion activa de ruido"
        if cat == "placa de video" and chip(mod):
            w, f, quien = PLACAS[chip(mod)]
            s["potencia"] = f"consume hasta {w}W"
            s["fuente_recomendada"] = f"fuente de {f}W o mas, recomendada por {quien}"
        if cat == "procesador" and mod in NUCLEOS:
            s["nucleos"] = "{} nucleos, {} hilos".format(*NUCLEOS[mod])
        if cat == "router" and mod in WIFI:
            s["wifi"] = WIFI[mod]
    return {(s["categoria"], s["marca"], s["modelo"]): s for s in specs}


def extra_nueva(p, s, comp):
    """La caracteristica de cada producto, sacada de su ficha y su compatibilidad; None si no se cambia."""
    cat, mar, mod = p["categoria"], p["marca"], p["modelo"]
    if (cat, mod) in SOLO_CAMBIA:
        return SOLO_CAMBIA[(cat, mod)]
    if cat == "monitor":
        partes = [s.get("pulgadas", ""), f"panel {s['panel']}" if s.get("panel") else "", s.get("resolucion", ""), s.get("hz", "")]
        return ", ".join(x for x in partes if x)
    if cat == "placa de video":
        return s.get("memoria_video") or None
    if cat == "fuente":
        m = re.match(r"(\d+W)", s.get("potencia", ""))
        return m.group(1) if m else None
    if cat == "cooler":
        return s.get("potencia") or None
    if cat == "procesador":
        return s.get("nucleos") or None
    if cat == "router":
        return s.get("wifi") or None
    if cat == "parlante" and mod in CANALES:
        return f"{CANALES[mod]}, {s.get('potencia', '')}".strip(", ")
    if cat == "motherboard":
        pv = comp.get("provee", "").split("|")
        ddr = [x.replace("ranura_", "").upper() for x in pv if x.startswith("ranura_ddr")]
        so = [x.replace("socket_", "").upper() for x in pv if x.startswith("socket_")]
        return ", ".join(ddr + [f"socket {x}" for x in so]) or None
    if cat == "gabinete":
        pv = comp.get("provee", "").split("|")
        return "ATX" if "formato_atx" in pv else ("micro ATX" if "formato_micro_atx" in pv else None)
    return None


def tags_nuevas(p, vieja, nueva, s):
    tags = [t.strip() for t in p["tags"].split(",") if t.strip()]
    sacar = {vieja.lower()} | {w for w in re.split(r"[ ,]+", vieja.lower()) if w}
    if p["categoria"] == "monitor":
        sacar |= {"1080p", "1920x1080", "75 hz", "75hz", "fhd", "full hd", "ips", "panel ips", "colores precisos"}
    tags = [t for t in tags if t not in sacar]
    poner = {nueva.lower()}
    if p["categoria"] == "monitor":
        if s.get("panel"):
            poner |= {s["panel"].lower(), f"panel {s['panel'].lower()}"}
        for k, ts in RESOL_TAGS.items():
            if s.get("resolucion", "").startswith(k + " "):
                poner |= set(ts)
        m = re.search(r"(\d+x\d+)", s.get("resolucion", ""))
        if m:
            poner.add(m.group(1))
        if s.get("hz"):
            n = s["hz"].lower().replace("hz", "")
            poner |= {f"{n}hz", f"{n} hz"}
        if s.get("pulgadas"):
            n = s["pulgadas"].split()[0]
            poner |= {f"{n} pulgadas", f'{n}"'}
    return ", ".join(sorted(set(tags) | poner))


def main(grabar):
    cab_s, specs = leer("specs_por_modelo.csv")
    S = specs_nuevas(cab_s, specs)
    _, comps = leer("compatibilidad.csv")
    C = {(c["categoria"], c["marca"], c["modelo"]): c for c in comps}
    cab_p, prods = leer("productos.csv")
    cambios = 0
    for p in prods:
        k = (p["categoria"], p["marca"], p["modelo"])
        nueva = extra_nueva(p, S.get(k, {}), C.get(k, {}))
        vieja = p["caracteristicas_extra"]
        if not nueva or nueva == vieja:
            continue
        for campo in ("descripcion", "descripcion_rica"):
            if f". {vieja}." in p[campo]:
                p[campo] = p[campo].replace(f". {vieja}.", f". {nueva}.", 1)
            else:
                print("  AVISO sin el texto viejo en", campo, p["id"])
        p["tags"] = tags_nuevas(p, vieja, nueva, S.get(k, {}))
        p["caracteristicas_extra"] = nueva
        cambios += 1
        if not grabar and cambios % 40 == 1:
            print(p["id"], repr(vieja), "->", repr(nueva))
    print("productos corregidos:", cambios)
    texto = open(os.path.join(D, "specs_preguntables.json"), encoding="utf-8").read()
    pr = json.loads(texto)
    ids = {x["id"] for x in pr["specs"]}
    nuevas = [
        {"id": "pulgadas", "claves": ["pulgadas", "pulgada", "tamano de pantalla", "de cuantas pulgadas", "cuanto mide la pantalla"],
         "etiqueta": "el tamano de la pantalla", "aplica_a": ["monitor"], "extraer": ["(\\d+(?:[.,]\\d+)?\\s*pulgadas)"], "claves_ficha": ["pulgadas"]},
        {"id": "microfono", "claves": ["microfono", "micro", "mic", "para hablar", "tiene micro"], "etiqueta": "el microfono",
         "aplica_a": ["auriculares"], "extraer": ["((?:si|no),? [^.]*microfono[^.]*)"], "claves_ficha": ["microfono"]},
        {"id": "cancelacion_ruido", "claves": ["cancelacion de ruido", "anc", "noise cancelling", "que no se escuche el ruido", "aislar el ruido"],
         "etiqueta": "la cancelacion activa de ruido", "aplica_a": ["auriculares"], "extraer": ["((?:si|no),? [^.]*cancelacion[^.]*)"],
         "claves_ficha": ["cancelacion"]},
        {"id": "fuente_recomendada", "claves": ["que fuente necesita", "fuente recomendada", "cuantos watts de fuente", "me alcanza la fuente"],
         "etiqueta": "la fuente recomendada", "aplica_a": ["placa de video"], "extraer": ["(fuente de \\d+\\s*w[^.]*)"], "claves_ficha": ["fuente de"]},
        {"id": "nucleos", "claves": ["nucleos", "nucleo", "cores", "hilos", "threads"], "etiqueta": "los nucleos y los hilos",
         "aplica_a": ["procesador"], "extraer": ["(\\d+\\s*nucleos(?:,\\s*\\d+\\s*hilos)?)"], "claves_ficha": ["nucleos"]},
    ]
    agregar = [x for x in nuevas if x["id"] not in ids]


    def bloque(x):
        return "    {\n" + ",\n".join(f'      "{k}": {json.dumps(v, ensure_ascii=False)}' for k, v in x.items()) + "\n    }"
    t = texto.replace('"aplica_a": ["fuente", "parlante", "cargador", "cooler"]',
                      '"aplica_a": ["fuente", "parlante", "cargador", "cooler", "placa de video"]', 1)
    if agregar:
        i = t.rindex("    }\n  ]\n}")
        t = t[:i] + "    },\n" + ",\n".join(bloque(x) for x in agregar) + "\n" + t[i + len("    },\n") - 1:]
    json.loads(t)
    if grabar:
        escribir("specs_por_modelo.csv", cab_s, specs)
        escribir("productos.csv", cab_p, prods)
        open(os.path.join(D, "specs_preguntables.json"), "w", encoding="utf-8").write(t)
        print("grabado")


if __name__ == "__main__":
    main("--grabar" in sys.argv)
