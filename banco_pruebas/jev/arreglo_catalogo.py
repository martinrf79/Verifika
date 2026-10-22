"""Teclados y auriculares: el relleno de caracteristicas_extra ("switch red" en todos los teclados, "con cable" en todos
los auriculares) se reemplaza por lo que es cada modelo. La conexion de los auriculares sale de compatibilidad.csv,
que ya estaba bien; el tipo de teclado, de cada modelo. Solo cambian esas filas; el resto del archivo queda igual."""
import csv, io, re, sys
DIR = "/home/user/Verifika/data/clientes/verifika_prod/"

# El tipo de teclado. El color del switch no se pone: la fuente no lo trae y seria inventarlo.
TECLADO = {
    "G915 TKL": "mecanico", "G413 TKL SE": "mecanico", "BlackWidow V4": "mecanico", "Huntsman Mini": "mecanico optico",
    "Huntsman V3 Pro": "mecanico optico", "Alloy Origins Core": "mecanico", "Alloy Origins 60": "mecanico",
    "Kumara K552": "mecanico", "Vata K580": "mecanico", "Vara K551": "mecanico", "K617 Fizz": "mecanico",
    "K70 RGB Pro": "mecanico", "K2": "mecanico", "V3": "mecanico", "ROG Strix Scope II": "mecanico",
    "KB-110X": "membrana", "Slimstar 130": "membrana", "K120": "membrana", "Alloy Core RGB": "membrana",
    "K55 RGB Pro": "membrana", "Ornata V3": "membrana", "G213 Prodigy": "membrana",
    "K380": "tijera", "MX Keys S": "tijera",
}
DICHO_TECLADO = {"mecanico": "teclado mecanico", "mecanico optico": "teclado mecanico optico",
                 "membrana": "teclado de membrana", "tijera": "teclado de tijera, perfil bajo"}
ETIQUETAS_TECLADO = {"mecanico": ["mecanico"], "mecanico optico": ["mecanico", "optico"], "membrana": ["membrana"],
                     "tijera": ["tijera", "perfil bajo"]}

# La conexion de cada auricular, de compatibilidad.csv: (bluetooth, conexion, dicho, etiquetas).
CABLE = ("no, este modelo es con cable", "con cable", "con cable de 3.5 mm", ["cableado", "con cable", "jack 3.5"])
USB = ("no, este modelo es con cable", "con cable USB", "con cable USB", ["cableado", "con cable", "usb"])
RECEPTOR = ("no, usa receptor USB inalambrico", "inalambrico", "inalambrico con receptor USB", ["inalambrico", "wireless", "receptor usb"])
BT = ("si, bluetooth integrado", "inalambrico", "inalambrico por Bluetooth", ["inalambrico", "wireless", "bluetooth"])
BT_CABLE = ("si, bluetooth integrado, y tambien con cable de 3.5 mm", "inalambrico", "inalambrico por Bluetooth, y tambien con cable de 3.5 mm",
            ["inalambrico", "wireless", "bluetooth", "jack 3.5"])
RECEPTOR_BT = ("si, Bluetooth y receptor Lightspeed", "inalambrico", "inalambrico por Bluetooth o con receptor USB",
               ["inalambrico", "wireless", "bluetooth", "receptor usb"])
POR_CONECTA = {"jack_35": CABLE, "puerto_usb_a": USB, "receptor_usb": RECEPTOR, "bluetooth": BT, "bluetooth|jack_35": BT_CABLE,
               "receptor_usb|bluetooth": RECEPTOR_BT}
COMPAT = {(r["marca"], r["modelo"]): r["conecta_por"] for r in csv.DictReader(open(DIR + "compatibilidad.csv", encoding="utf-8"))
          if r["categoria"] == "auriculares"}
AURI = {k: POR_CONECTA[v] for k, v in COMPAT.items()}

def linea(campos):
    b = io.StringIO(); csv.writer(b, lineterminator="").writerow(campos); return b.getvalue()

def productos():
    ruta = DIR + "productos.csv"; crudo = open(ruta, encoding="utf-8", newline="").read()
    nl = "\r\n" if "\r\n" in crudo else "\n"; lineas = crudo.split(nl)
    h = next(csv.reader([lineas[0]])); ix = {c: i for i, c in enumerate(h)}
    cambiadas = 0
    for i, l in enumerate(lineas[1:], 1):
        if not l: continue
        r = next(csv.reader([l]))
        if linea(r) != l: sys.exit(f"fila {i}: el csv no se reescribe igual, no se toca")
        cat, modelo, marca = r[ix["categoria"]], r[ix["modelo"]], r[ix["marca"]]
        if cat == "teclado":
            t = TECLADO[modelo]; dicho = DICHO_TECLADO[t]
            assert r[ix["caracteristicas_extra"]] == "switch red", (modelo, r[ix["caracteristicas_extra"]])
            r[ix["caracteristicas_extra"]] = dicho
            for c in ("descripcion", "descripcion_rica"):
                assert ". switch red. " in r[ix[c]], (modelo, c); r[ix[c]] = r[ix[c]].replace(". switch red. ", f". {dicho}. ")
            tags = [x.strip() for x in r[ix["tags"]].split(",") if x.strip() not in ("mecanico lineal", "red switch", "switch red")]
            r[ix["tags"]] = ", ".join(sorted(set(tags) | set(ETIQUETAS_TECLADO[t])))
        elif cat == "auriculares":
            bt, cx, dicho, etiq = AURI[(marca, modelo)]
            assert r[ix["caracteristicas_extra"]] == "con cable", (modelo, r[ix["caracteristicas_extra"]])
            r[ix["caracteristicas_extra"]] = dicho
            for c in ("descripcion", "descripcion_rica"):
                assert ". con cable. " in r[ix[c]], (modelo, c); r[ix[c]] = r[ix[c]].replace(". con cable. ", f". {dicho}. ")
            tags = [x.strip() for x in r[ix["tags"]].split(",") if x.strip() not in ("cableado", "con cable", "usb")]
            r[ix["tags"]] = ", ".join(sorted(set(tags) | set(etiq)))
        else:
            continue
        lineas[i] = linea(r); cambiadas += 1
    open(ruta, "w", encoding="utf-8", newline="").write(nl.join(lineas))
    return cambiadas

def specs():
    """specs_por_modelo.csv: la columna switch_teclado al final, y bluetooth y conexion de cada auricular."""
    ruta = DIR + "specs_por_modelo.csv"; crudo = open(ruta, encoding="utf-8", newline="").read()
    nl = "\r\n" if "\r\n" in crudo else "\n"; lineas = crudo.split(nl)
    h = next(csv.reader([lineas[0]])); assert "switch_teclado" not in h
    ix = {c: i for i, c in enumerate(h)}; lineas[0] = linea(h + ["switch_teclado"]); cambiadas = 0
    for i, l in enumerate(lineas[1:], 1):
        if not l: continue
        r = next(csv.reader([l]))
        if linea(r) != l: sys.exit(f"specs fila {i}: el csv no se reescribe igual, no se toca")
        r.append("")
        if r[ix["categoria"]] == "teclado":
            r[-1] = TECLADO[r[ix["modelo"]]]; cambiadas += 1
        elif r[ix["categoria"]] == "auriculares":
            bt, cx, _, _ = AURI[(r[ix["marca"]], r[ix["modelo"]])]
            assert not r[ix["bluetooth"]] and not r[ix["conexion"]]
            r[ix["bluetooth"]], r[ix["conexion"]] = bt, cx; cambiadas += 1
        lineas[i] = linea(r)
    open(ruta, "w", encoding="utf-8", newline="").write(nl.join(lineas))
    return cambiadas

if __name__ == "__main__":
    print("productos.csv, filas cambiadas:", productos())
    print("specs_por_modelo.csv, modelos cargados:", specs())
