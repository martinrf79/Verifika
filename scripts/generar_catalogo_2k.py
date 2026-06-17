"""
GENERADOR DE CATALOGO DE 2000 PRODUCTOS (cliente simulado verifika_2k).

Arma un catalogo grande, realista y SIN gastar tokens: combina marcas reales,
lineas de modelo, atributos y rangos de precio actuales del mercado argentino de
tecnologia. Las descripciones son ricas en palabras para que la busqueda por
keywords tenga senal.

Incluye ADENTRO los 50 productos reales de verifika_demo, asi las preguntas
etiquetadas siguen resolviendo y probamos el anclaje a escala (2000 compitiendo).

Salida:
  data/clientes/verifika_2k/productos.csv   (2000 productos)
  data/clientes/verifika_2k/faq.json        (copia de la FAQ de verifika_demo)

Uso:
  winvenv\\Scripts\\python.exe scripts\\generar_catalogo_2k.py
"""
import os
import csv
import random
import shutil

random.seed(42)  # reproducible
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "data", "clientes", "verifika_demo")
OUT = os.path.join(ROOT, "data", "clientes", "verifika_2k")

CAMPOS = ["id", "nombre", "categoria", "precio_ars", "stock", "descripcion",
          "marca", "modelo", "color", "material", "peso_gramos", "dimensiones",
          "garantia_meses", "uso_recomendado", "caracteristicas_extra"]

# categoria -> (marcas, prefijo_id, (precio_min, precio_max), [features], material)
CATS = {
    "mouse": (["Logitech", "Razer", "Genius", "Redragon", "HyperX", "Microsoft"],
              "MOU", (8000, 220000),
              ["sensor optico", "RGB", "inalambrico", "con cable", "ergonomico",
               "liviano", "6 botones programables", "8000 DPI", "16000 DPI"],
              "Plastico ABS"),
    "teclado": (["Logitech", "Razer", "HyperX", "Redragon", "Genius", "Corsair"],
                "TEC", (12000, 490000),
                ["mecanico", "membrana", "RGB", "inalambrico", "switches red",
                 "switches blue", "layout español", "compacto", "full size"],
                "Aluminio"),
    "monitor": (["Samsung", "LG", "AOC", "Philips", "Gigabyte", "ViewSonic"],
                "MON", (150000, 950000),
                ["IPS", "VA", "Full HD", "2K QHD", "4K", "75Hz", "144Hz", "165Hz",
                 "curvo", "HDMI", "DisplayPort", "FreeSync"],
                "Plastico y metal"),
    "auriculares": (["Logitech", "Razer", "HyperX", "Sony", "JBL", "Redragon"],
                    "AUR", (25000, 400000),
                    ["inalambrico", "con cable", "cancelacion de ruido", "gamer",
                     "microfono", "bluetooth", "surround 7.1", "almohadillas"],
                    "Plastico y cuero sintetico"),
    "silla": (["Redragon", "Cougar", "ProSeat", "Gamemax", "Noblechairs"],
              "SIL", (170000, 700000),
              ["gamer", "ergonomica", "reclinable", "apoyabrazos 4D", "malla",
               "ecocuero", "soporte lumbar"],
              "Ecocuero y metal"),
    "webcam": (["Logitech", "Razer", "Microsoft", "Genius"], "WEB", (35000, 230000),
               ["Full HD 1080p", "2K", "autofoco", "microfono integrado", "USB",
                "para streaming"], "Plastico"),
    "microfono": (["HyperX", "Blue", "Razer", "FIFINE"], "MIC", (35000, 320000),
                  ["condensador", "USB", "cardioide", "para streaming", "brazo",
                   "filtro pop"], "Metal"),
    "parlante": (["Logitech", "JBL", "Edifier", "Genius"], "PAR", (20000, 350000),
                 ["bluetooth", "2.0", "2.1", "RGB", "estereo", "subwoofer"],
                 "Madera y plastico"),
    "ssd": (["Samsung", "Kingston", "Western Digital", "Crucial", "ADATA"],
            "SSD", (25000, 420000),
            ["NVMe", "SATA", "M.2", "500GB", "1TB", "2TB", "lectura 3500MB/s",
             "7000MB/s"], "Metal"),
    "ram": (["Kingston", "Corsair", "ADATA", "G.Skill"], "RAM", (20000, 260000),
            ["DDR4", "DDR5", "8GB", "16GB", "32GB", "3200MHz", "6000MHz", "RGB"],
            "PCB"),
    "placa de video": (["ASUS", "Gigabyte", "MSI", "Zotac"], "GPU", (350000, 3500000),
                       ["RTX 4060", "RTX 4070", "RTX 4080", "RX 7600", "8GB GDDR6",
                        "12GB", "ray tracing"], "Metal y plastico"),
    "fuente": (["Corsair", "EVGA", "Cooler Master", "Thermaltake"], "FUE",
               (45000, 350000),
               ["650W", "750W", "850W", "80 Plus Bronze", "80 Plus Gold",
                "modular"], "Metal"),
    "gabinete": (["Cooler Master", "NZXT", "Thermaltake", "Gamemax"], "GAB",
                 (60000, 420000),
                 ["ATX", "Micro ATX", "vidrio templado", "RGB", "3 coolers",
                  "buena ventilacion"], "Acero y vidrio"),
    "procesador": (["Intel", "AMD"], "CPU", (150000, 1200000),
                   ["Core i5", "Core i7", "Ryzen 5", "Ryzen 7", "6 nucleos",
                    "8 nucleos", "AM5", "LGA1700"], "Silicio"),
    "motherboard": (["ASUS", "Gigabyte", "MSI", "ASRock"], "MBO", (120000, 800000),
                    ["B650", "B760", "X670", "DDR5", "WiFi", "ATX", "Micro ATX"],
                    "PCB"),
    "cooler": (["Cooler Master", "Noctua", "DeepCool"], "COO", (25000, 260000),
               ["aire", "liquida 240mm", "liquida 360mm", "RGB", "silencioso"],
               "Aluminio y cobre"),
    "notebook": (["Lenovo", "HP", "Dell", "Asus", "Acer"], "NOT", (700000, 3500000),
                 ["Core i5", "Ryzen 7", "16GB RAM", "512GB SSD", "1TB SSD",
                  "pantalla 15.6", "14 pulgadas", "Windows 11"], "Aluminio"),
    "tablet": (["Samsung", "Lenovo"], "TAB", (200000, 900000),
               ["10 pulgadas", "11 pulgadas", "128GB", "WiFi", "con lapiz"],
               "Aluminio"),
    "pendrive": (["Kingston", "SanDisk"], "PEN", (8000, 60000),
                 ["32GB", "64GB", "128GB", "USB 3.2", "metalico"], "Metal"),
    "router": (["TP-Link", "Mercusys", "Tenda"], "ROU", (30000, 200000),
               ["WiFi 6", "doble banda", "AX1800", "mesh", "4 antenas"],
               "Plastico"),
    "impresora": (["Epson", "HP", "Brother"], "IMP", (150000, 700000),
                  ["multifuncion", "wifi", "sistema continuo", "laser", "color"],
                  "Plastico"),
    "cargador": (["Anker", "Baseus", "Genius"], "CAR", (8000, 70000),
                 ["USB-C", "carga rapida", "65W", "GaN", "2 puertos"], "Plastico"),
}

COLORES = ["Negro", "Blanco", "Gris", "Rosa", "Azul", "Rojo", "Grafito", "Plata"]
USOS = ["Gaming", "Oficina", "Profesional", "Hogar", "Estudio", "Streaming"]


def precio_realista(lo, hi):
    p = random.randint(lo, hi)
    return int(round(p / 500.0)) * 500  # redondeo a 500


def leer_demo():
    rows = []
    with open(os.path.join(DEMO, "productos.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def main():
    os.makedirs(OUT, exist_ok=True)
    demo_rows = leer_demo()
    ids_usados = {r["id"].strip().upper() for r in demo_rows}

    generados = []
    n_objetivo = 2000 - len(demo_rows)
    cats = list(CATS.keys())
    contador = {c: 0 for c in cats}
    i = 0
    while len(generados) < n_objetivo:
        cat = cats[i % len(cats)]
        i += 1
        marcas, pref, (lo, hi), feats, material = CATS[cat]
        contador[cat] += 1
        n = contador[cat]
        marca = random.choice(marcas)
        # modelo: linea + numero
        linea = random.choice(["Pro", "Ultra", "Max", "Lite", "Plus", "X", "S",
                               "Gamer", "Series", "One", "Air", "Go"])
        modelo = f"{linea} {random.randint(100, 9999)}"
        color = random.choice(COLORES)
        f1, f2 = random.sample(feats, 2)
        precio = precio_realista(lo, hi)
        stock = random.choices([0, random.randint(1, 40)], weights=[1, 9])[0]
        pid = f"{pref}{n:04d}"
        while pid in ids_usados:
            n += 1
            pid = f"{pref}{n:04d}"
        ids_usados.add(pid)
        nombre = f"{cat.capitalize()} {marca} {modelo}"
        desc = (f"{cat} {marca} {f1} {f2}, color {color.lower()}. "
                f"Ideal para {random.choice(USOS).lower()}.")
        generados.append({
            "id": pid,
            "nombre": nombre,
            "categoria": cat,
            "precio_ars": precio,
            "stock": stock,
            "descripcion": desc,
            "marca": marca,
            "modelo": modelo,
            "color": color,
            "material": material,
            "peso_gramos": random.randint(50, 8000),
            "dimensiones": f"{random.randint(5,60)}x{random.randint(5,40)}x{random.randint(2,30)} cm",
            "garantia_meses": random.choice([6, 12, 24, 36]),
            "uso_recomendado": random.choice(USOS),
            "caracteristicas_extra": f"{f1}, {f2}",
        })

    # Escribir: primero los 50 reales (preservando sus columnas), luego generados.
    out_path = os.path.join(OUT, "productos.csv")
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS, extrasaction="ignore")
        w.writeheader()
        for r in demo_rows:
            fila = {c: r.get(c, "") for c in CAMPOS}
            w.writerow(fila)
        for r in generados:
            w.writerow(r)

    # Copiar la FAQ de verifika_demo (reglas de negocio, no dependen del producto).
    shutil.copy(os.path.join(DEMO, "faq.json"), os.path.join(OUT, "faq.json"))

    total = len(demo_rows) + len(generados)
    print(f"OK catalogo verifika_2k: {total} productos "
          f"({len(demo_rows)} reales de verifika_demo + {len(generados)} generados)")
    print(f"  productos: {out_path}")
    print(f"  faq:       {os.path.join(OUT, 'faq.json')}")
    print(f"  categorias: {len(CATS)}")


if __name__ == "__main__":
    main()
