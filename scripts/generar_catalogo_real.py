"""
GENERADOR DE CATALOGO DE PRODUCCION (tienda verifika_prod).

Objetivo (consigna de Martin): un catalogo VENDIBLE de calidad produccion, NO el
fixture procedural verifika_2k. Marcas y modelos que EXISTEN de verdad en el
mercado argentino de tecnologia, precios en ARS plausibles y coherentes,
descripciones buenas, repartido en categorias reales. Se arma por
marca x linea-de-modelo real x variante real (capacidad, tamaño, color), asi cada
SKU es una combinacion creible, no un nombre inventado tipo "Mouse Ultra 509".

Salida:
  data/clientes/verifika_prod/productos.csv
  data/clientes/verifika_prod/faq.json   (FAQ rica con capa de conversion)

Uso:
  winvenv\\Scripts\\python.exe scripts\\generar_catalogo_real.py
"""
import os
import csv
import random
import shutil

random.seed(7)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "data", "clientes", "verifika_demo")
OUT = os.path.join(ROOT, "data", "clientes", "verifika_prod")

CAMPOS = ["id", "nombre", "categoria", "precio_ars", "stock", "descripcion",
          "marca", "modelo", "color", "material", "peso_gramos", "dimensiones",
          "garantia_meses", "uso_recomendado", "caracteristicas_extra"]

# Cada entrada: (marca, modelo_real, precio_base_ars). Las variantes (capacidad,
# tamaño, color) ajustan precio y nombre. Todo modelo aca EXISTE en el mercado.
CATS = {}

CATS["mouse"] = {"pref": "MOU", "material": "Plastico ABS", "gar": 24,
    "uso": "Gaming", "items": [
    ("Logitech", "G203 Lightsync", 38000), ("Logitech", "G502 Hero", 72000),
    ("Logitech", "G Pro X Superlight", 165000), ("Logitech", "MX Master 3S", 210000),
    ("Logitech", "M170", 12000), ("Razer", "DeathAdder V3", 125000),
    ("Razer", "Viper V3 Pro", 230000), ("Razer", "Basilisk V3", 98000),
    ("Redragon", "Cobra M711", 22000), ("Redragon", "King Cobra", 28000),
    ("HyperX", "Pulsefire Haste 2", 75000), ("Genius", "DX-110", 8500),
    ("Microsoft", "Classic IntelliMouse", 45000), ("Glorious", "Model O", 89000)],
    "colores": ["Negro", "Blanco"], "feats": ["sensor optico", "RGB", "ligero"]}

CATS["teclado"] = {"pref": "TEC", "material": "Aluminio", "gar": 24,
    "uso": "Gaming", "items": [
    ("Logitech", "G915 TKL", 485000), ("Logitech", "K380", 55000),
    ("Logitech", "G413 TKL SE", 95000), ("Razer", "BlackWidow V4", 295000),
    ("Razer", "Huntsman Mini", 175000), ("HyperX", "Alloy Origins Core", 165000),
    ("HyperX", "Alloy Origins 60", 145000), ("Redragon", "Kumara K552", 35000),
    ("Redragon", "Vata K580", 62000), ("Genius", "KB-110X", 12000),
    ("Corsair", "K70 RGB Pro", 320000), ("Keychron", "K2", 175000)],
    "colores": ["Negro", "Blanco"],
    "feats": ["switch red", "switch blue", "switch brown", "membrana"]}

CATS["monitor"] = {"pref": "MON", "material": "Plastico y metal", "gar": 36,
    "uso": "Gaming", "items": [
    ("LG", "24MK430H", 165000), ("LG", "27GP850 UltraGear", 580000),
    ("LG", "32GN600", 420000), ("Samsung", "Odyssey G5 32", 485000),
    ("Samsung", "Odyssey G3 24", 215000), ("Samsung", "T35F 24", 155000),
    ("AOC", "27G2", 295000), ("AOC", "24G2", 235000),
    ("Gigabyte", "M27Q", 510000), ("Philips", "242V8A", 175000),
    ("ViewSonic", "VX2718", 245000), ("Asus", "TUF VG249Q1A", 290000)],
    "colores": ["Negro"],
    "feats": ["IPS Full HD 75Hz", "IPS 144Hz", "VA curvo 144Hz", "QHD 165Hz"]}

CATS["auriculares"] = {"pref": "AUR", "material": "Plastico y cuero sintetico",
    "gar": 12, "uso": "Gaming", "items": [
    ("HyperX", "Cloud II", 125000), ("HyperX", "Cloud Stinger 2", 68000),
    ("Logitech", "G Pro X", 285000), ("Logitech", "G435", 95000),
    ("Sony", "WH-1000XM5", 685000), ("Sony", "WH-CH520", 95000),
    ("JBL", "Tune 510BT", 75000), ("JBL", "Tune 770NC", 165000),
    ("Razer", "Kraken V3", 145000), ("Redragon", "Zeus X", 55000),
    ("Sennheiser", "HD 560S", 320000)],
    "colores": ["Negro", "Blanco"],
    "feats": ["con cable", "inalambrico", "cancelacion de ruido", "microfono"]}

CATS["notebook"] = {"pref": "NOT", "material": "Aluminio", "gar": 12,
    "uso": "Trabajo y estudio", "items": [
    ("Lenovo", "IdeaPad 3", 720000), ("Lenovo", "LOQ 15", 1450000),
    ("HP", "245 G9", 680000), ("HP", "Victus 15", 1390000),
    ("Dell", "Inspiron 15 3520", 850000), ("Asus", "Vivobook 15", 790000),
    ("Asus", "TUF Gaming F15", 1650000), ("Acer", "Aspire 5", 760000),
    ("Acer", "Nitro 5", 1520000)],
    "colores": ["Gris", "Negro", "Plata"],
    "feats": ["Core i5 16GB 512GB SSD", "Ryzen 5 16GB 512GB SSD",
              "Core i7 16GB 1TB SSD", "Ryzen 7 16GB 1TB SSD"]}

CATS["placa de video"] = {"pref": "GPU", "material": "Metal y plastico", "gar": 36,
    "uso": "Gaming high end", "items": [
    ("Asus", "Dual RTX 4060", 620000), ("Gigabyte", "Gaming OC RTX 4060 Ti", 780000),
    ("MSI", "Ventus 2X RTX 4070 Super", 1250000),
    ("Gigabyte", "Gaming OC RTX 4070 Ti Super", 1750000),
    ("Asus", "TUF RTX 4080 Super", 2650000), ("Zotac", "Trinity RTX 4070", 1100000),
    ("MSI", "Gaming X RX 7600", 560000), ("Sapphire", "Pulse RX 7700 XT", 980000),
    ("PowerColor", "Hellhound RX 7800 XT", 1280000)],
    "colores": ["Negro"], "feats": ["8GB GDDR6", "12GB GDDR6X", "16GB GDDR6"]}

CATS["procesador"] = {"pref": "CPU", "material": "Silicio", "gar": 36,
    "uso": "Gaming y productividad", "items": [
    ("Intel", "Core i5-12400F", 195000), ("Intel", "Core i5-13400F", 260000),
    ("Intel", "Core i5-14600KF", 410000), ("Intel", "Core i7-13700KF", 620000),
    ("AMD", "Ryzen 5 5600", 180000), ("AMD", "Ryzen 5 7600", 320000),
    ("AMD", "Ryzen 7 5800X3D", 520000), ("AMD", "Ryzen 7 7800X3D", 720000),
    ("AMD", "Ryzen 5 5500", 140000)],
    "colores": ["-"], "feats": ["6 nucleos", "8 nucleos", "AM4", "AM5", "LGA1700"]}

CATS["motherboard"] = {"pref": "MBO", "material": "PCB", "gar": 36,
    "uso": "Armado de PC", "items": [
    ("Asus", "Prime B550M-A", 165000), ("Gigabyte", "B650 Gaming X AX", 320000),
    ("MSI", "B550 Tomahawk", 240000), ("MSI", "PRO B760M-A WiFi", 290000),
    ("ASRock", "B450M Steel Legend", 145000), ("Gigabyte", "A520M K", 110000),
    ("Asus", "TUF B650-Plus WiFi", 410000)],
    "colores": ["Negro"], "feats": ["DDR4", "DDR5", "WiFi", "ATX", "Micro ATX"]}

CATS["memoria ram"] = {"pref": "RAM", "material": "PCB y aluminio", "gar": 120,
    "uso": "Gaming y productividad", "items": [
    ("Kingston", "Fury Beast DDR4 3200", 36000), ("Kingston", "Fury Beast DDR5 5600", 62000),
    ("Corsair", "Vengeance LPX DDR4 3600", 48000), ("Corsair", "Vengeance DDR5 6000", 78000),
    ("G.Skill", "Ripjaws V DDR4 3200", 42000), ("G.Skill", "Trident Z5 DDR5 6000", 95000),
    ("ADATA", "XPG Lancer DDR5 5200", 58000), ("Patriot", "Viper DDR4 3200", 38000)],
    "colores": ["Negro", "Blanco"], "feats": ["8GB", "16GB", "32GB", "2x8GB", "2x16GB"]}

CATS["ssd"] = {"pref": "SSD", "material": "Metal", "gar": 60, "uso": "Almacenamiento",
    "items": [
    ("Samsung", "980", 38000), ("Samsung", "980 PRO", 95000), ("Samsung", "990 PRO", 160000),
    ("Kingston", "NV2", 32000), ("Kingston", "KC3000", 110000), ("Kingston", "A400 SATA", 28000),
    ("Western Digital", "Blue SN580", 45000), ("Western Digital", "Black SN770", 78000),
    ("Crucial", "P3 Plus", 42000), ("Crucial", "MX500 SATA", 52000),
    ("ADATA", "Legend 800", 40000)],
    "colores": ["Negro"], "feats": ["500GB", "1TB", "2TB", "NVMe", "SATA"]}

CATS["fuente"] = {"pref": "FUE", "material": "Metal", "gar": 60, "uso": "Armado de PC",
    "items": [
    ("Corsair", "CV550", 75000), ("Corsair", "RM750e", 165000),
    ("EVGA", "600 BR", 85000), ("Cooler Master", "MWE 650 Bronze", 110000),
    ("Thermaltake", "Smart 600W", 70000), ("Gigabyte", "P650B", 98000),
    ("Asus", "TUF Gaming 750W Gold", 195000)],
    "colores": ["Negro"], "feats": ["550W", "650W", "750W", "80 Plus Bronze", "80 Plus Gold"]}

CATS["gabinete"] = {"pref": "GAB", "material": "Acero y vidrio", "gar": 12,
    "uso": "Armado de PC", "items": [
    ("Cooler Master", "MasterBox Q300L", 75000), ("NZXT", "H5 Flow", 185000),
    ("Thermaltake", "Versa H18", 62000), ("Gamemax", "Black Hole", 88000),
    ("Corsair", "4000D Airflow", 175000), ("Asus", "Prime AP201", 165000),
    ("Montech", "Air 903", 130000)],
    "colores": ["Negro", "Blanco"], "feats": ["ATX", "Micro ATX", "vidrio templado", "RGB"]}

CATS["cooler"] = {"pref": "COO", "material": "Aluminio y cobre", "gar": 60,
    "uso": "Refrigeracion", "items": [
    ("DeepCool", "AK620", 135000), ("DeepCool", "AG400", 48000),
    ("Cooler Master", "Hyper 212", 55000), ("Cooler Master", "ML240L V2", 245000),
    ("Noctua", "NH-U12S Redux", 95000), ("Thermalright", "Peerless Assassin 120", 72000),
    ("Lian Li", "Galahad II 360", 320000)],
    "colores": ["Negro"], "feats": ["aire", "liquida 240mm", "liquida 360mm", "RGB"]}

CATS["microfono"] = {"pref": "MIC", "material": "Metal", "gar": 12, "uso": "Streaming",
    "items": [
    ("HyperX", "QuadCast S", 245000), ("Blue", "Yeti", 225000),
    ("FIFINE", "K669B", 68000), ("FIFINE", "AmpliGame A6T", 95000),
    ("Razer", "Seiren Mini", 88000), ("Rode", "NT-USB Mini", 195000)],
    "colores": ["Negro", "Blanco"], "feats": ["USB", "cardioide", "condensador"]}

CATS["webcam"] = {"pref": "WEB", "material": "Plastico", "gar": 12,
    "uso": "Videoconferencias y streaming", "items": [
    ("Logitech", "C920 HD Pro", 135000), ("Logitech", "C922 Pro", 175000),
    ("Logitech", "Brio 100", 92000), ("Genius", "FaceCam 2000X", 45000),
    ("Razer", "Kiyo X", 110000)],
    "colores": ["Negro"], "feats": ["Full HD 1080p", "autofoco", "microfono integrado"]}

CATS["parlante"] = {"pref": "PAR", "material": "Madera y plastico", "gar": 12,
    "uso": "Multimedia", "items": [
    ("Logitech", "Z313", 75000), ("Logitech", "Z207 Bluetooth", 65000),
    ("Edifier", "R1280T", 145000), ("JBL", "Go 3", 55000),
    ("JBL", "Flip 6", 165000), ("Genius", "SP-HF180", 28000)],
    "colores": ["Negro", "Azul", "Rojo"], "feats": ["2.0", "2.1", "bluetooth"]}

CATS["silla gamer"] = {"pref": "SIL", "material": "Ecocuero y metal", "gar": 12,
    "uso": "Gaming y oficina", "items": [
    ("Redragon", "Coeus", 395000), ("Redragon", "Fishbones", 280000),
    ("Cougar", "Armor S", 535000), ("Gamemax", "GCR07", 240000),
    ("Noblechairs", "Hero", 720000), ("ProSeat", "Ergo Mesh", 285000)],
    "colores": ["Negro y rojo", "Negro", "Negro y azul"],
    "feats": ["reclinable", "apoyabrazos 4D", "soporte lumbar", "malla"]}

CATS["almacenamiento externo"] = {"pref": "EXT", "material": "Aluminio", "gar": 24,
    "uso": "Backup y portabilidad", "items": [
    ("Seagate", "Expansion", 95000), ("Western Digital", "Elements", 105000),
    ("Toshiba", "Canvio Basics", 92000), ("Samsung", "T7 SSD", 165000),
    ("Kingston", "DataTraveler Exodia", 14000), ("SanDisk", "Ultra Flair", 16000)],
    "colores": ["Negro", "Plata"], "feats": ["1TB", "2TB", "USB 3.2", "portatil"]}

CATS["router"] = {"pref": "ROU", "material": "Plastico", "gar": 24,
    "uso": "Redes hogar", "items": [
    ("TP-Link", "Archer C6", 48000), ("TP-Link", "Archer AX23", 95000),
    ("Mercusys", "Halo H30G", 62000), ("Tenda", "AC10", 42000),
    ("TP-Link", "Deco M4 Mesh", 145000)],
    "colores": ["Negro", "Blanco"], "feats": ["WiFi 5", "WiFi 6", "doble banda", "mesh"]}

CATS["impresora"] = {"pref": "IMP", "material": "Plastico", "gar": 12,
    "uso": "Hogar y oficina", "items": [
    ("Epson", "EcoTank L3250", 285000), ("Epson", "EcoTank L3560", 360000),
    ("HP", "Smart Tank 580", 295000), ("Brother", "DCP-T520W", 320000),
    ("Canon", "Pixma G3110", 270000)],
    "colores": ["Negro", "Blanco"], "feats": ["multifuncion", "wifi", "sistema continuo"]}

CATS["cargador"] = {"pref": "CAR", "material": "Plastico", "gar": 12,
    "uso": "Carga", "items": [
    ("Anker", "Nano II 65W", 75000), ("Anker", "PowerPort III 20W", 32000),
    ("Baseus", "GaN5 65W", 58000), ("Xiaomi", "Mi 33W", 38000)],
    "colores": ["Negro", "Blanco"], "feats": ["USB-C", "carga rapida", "GaN"]}

CATS["tablet"] = {"pref": "TAB", "material": "Aluminio", "gar": 12,
    "uso": "Multimedia y estudio", "items": [
    ("Samsung", "Galaxy Tab A9", 220000), ("Samsung", "Galaxy Tab S6 Lite", 480000),
    ("Lenovo", "Tab M11", 290000), ("Xiaomi", "Redmi Pad SE", 260000)],
    "colores": ["Gris", "Plata", "Azul"], "feats": ["128GB", "WiFi", "10 pulgadas", "11 pulgadas"]}


# EXPANSION: mas marcas y modelos REALES por categoria. Todo modelo existe en el
# mercado argentino. Se fusiona con los items base de arriba.
EXTRA = {
"mouse": [("Logitech", "G305 Lightspeed", 78000), ("Logitech", "G502 X", 135000),
    ("Logitech", "G Pro Wireless", 185000), ("Logitech", "M220 Silent", 18000),
    ("Razer", "Cobra", 62000), ("Razer", "Naga V2 Pro", 290000),
    ("Razer", "Orochi V2", 95000), ("Redragon", "Storm Elite", 42000),
    ("Redragon", "Predator", 38000), ("HyperX", "Pulsefire Core", 38000),
    ("Genius", "NX-7000", 14000), ("Logitech", "G600 MMO", 105000)],
"teclado": [("Logitech", "G213 Prodigy", 62000), ("Logitech", "MX Keys S", 245000),
    ("Logitech", "K120", 14000), ("Razer", "Ornata V3", 110000),
    ("Razer", "Huntsman V3 Pro", 380000), ("HyperX", "Alloy Core RGB", 58000),
    ("Redragon", "K617 Fizz", 38000), ("Redragon", "Vara K551", 45000),
    ("Corsair", "K55 RGB Pro", 110000), ("Asus", "ROG Strix Scope II", 290000),
    ("Keychron", "V3", 165000), ("Genius", "Slimstar 130", 16000)],
"monitor": [("LG", "29WP60G UltraWide", 420000), ("LG", "34WP65C Curvo", 720000),
    ("Samsung", "Odyssey G9 49", 1850000), ("Samsung", "ViewFinity S6", 540000),
    ("AOC", "24B2XH", 165000), ("Gigabyte", "G24F 2", 320000),
    ("Asus", "TUF VG279Q1A", 360000), ("Asus", "ProArt PA248QV", 410000),
    ("Philips", "271E1", 195000), ("MSI", "G274F", 330000),
    ("ViewSonic", "VA2406", 175000), ("Dell", "S2421HN", 280000)],
"auriculares": [("HyperX", "Cloud III", 175000), ("HyperX", "Cloud Alpha", 155000),
    ("Logitech", "G733 Lightspeed", 245000), ("Logitech", "G535", 165000),
    ("Razer", "BlackShark V2", 180000), ("Razer", "Kraken Kitty V2", 260000),
    ("Sony", "WH-CH720N", 245000), ("Sony", "ULT Wear", 420000),
    ("JBL", "Quantum 200", 95000), ("JBL", "Tune 520BT", 88000),
    ("Sennheiser", "HD 599", 410000), ("Redragon", "Pandora", 62000)],
"notebook": [("Lenovo", "IdeaPad Slim 5", 980000), ("Lenovo", "ThinkPad E14", 1250000),
    ("Lenovo", "Legion 5", 1850000), ("HP", "Pavilion 15", 920000),
    ("HP", "Omen 16", 1950000), ("Dell", "Latitude 3540", 1100000),
    ("Dell", "G15", 1480000), ("Asus", "Zenbook 14 OLED", 1390000),
    ("Asus", "ROG Strix G16", 2300000), ("Acer", "Swift Go 14", 1050000)],
"placa de video": [("Asus", "Dual RTX 4070 Super", 1280000),
    ("Asus", "ROG Strix RTX 4080 Super", 2950000), ("Gigabyte", "Eagle RTX 4060", 600000),
    ("MSI", "Gaming X RTX 4070 Ti Super", 1820000), ("Zotac", "Twin Edge RTX 4060 Ti", 760000),
    ("Sapphire", "Nitro+ RX 7800 XT", 1350000), ("XFX", "Speedster RX 7700 XT", 950000),
    ("PowerColor", "Red Devil RX 7900 XT", 1980000), ("ASRock", "Challenger RX 7600 XT", 720000)],
"procesador": [("Intel", "Core i3-12100F", 95000), ("Intel", "Core i3-14100F", 130000),
    ("Intel", "Core i5-13600KF", 460000), ("Intel", "Core i7-14700KF", 720000),
    ("Intel", "Core i9-14900K", 1150000), ("AMD", "Ryzen 5 5600X", 210000),
    ("AMD", "Ryzen 5 7500F", 280000), ("AMD", "Ryzen 7 7700X", 620000),
    ("AMD", "Ryzen 9 7900X", 850000), ("AMD", "Ryzen 5 8400F", 240000)],
"motherboard": [("Asus", "Prime B650-Plus", 360000), ("Asus", "ROG Strix B550-F", 380000),
    ("Asus", "TUF B760-Plus WiFi", 350000), ("Gigabyte", "B550M DS3H", 130000),
    ("Gigabyte", "B760M DS3H", 175000), ("MSI", "MAG B650 Tomahawk WiFi", 390000),
    ("MSI", "PRO B550M-VC", 150000), ("ASRock", "B650M-HDV/M.2", 175000)],
"memoria ram": [("Kingston", "Fury Renegade DDR5 6400", 110000),
    ("Corsair", "Vengeance RGB DDR5 6000", 105000), ("Corsair", "Dominator DDR5 6200", 145000),
    ("G.Skill", "Flare X5 DDR5 6000", 88000), ("Crucial", "Pro DDR5 5600", 72000),
    ("TeamGroup", "T-Force Delta RGB DDR5", 98000), ("ADATA", "XPG Spectrix DDR4 3600", 52000),
    ("Patriot", "Viper Steel DDR4 3600", 48000)],
"ssd": [("Samsung", "970 EVO Plus", 78000), ("Samsung", "870 EVO SATA", 62000),
    ("Kingston", "Fury Renegade", 130000), ("Western Digital", "Black SN850X", 145000),
    ("Western Digital", "Green SATA", 30000), ("Crucial", "T500", 130000),
    ("Crucial", "P5 Plus", 85000), ("Seagate", "FireCuda 530", 150000),
    ("Lexar", "NM620", 38000)],
"fuente": [("Corsair", "RM850e", 210000), ("Corsair", "CX650F RGB", 130000),
    ("EVGA", "500 W1", 65000), ("Cooler Master", "MWE 750 Gold V2", 175000),
    ("Thermaltake", "Toughpower GF1 750W", 195000), ("Gigabyte", "UD750GM", 150000),
    ("Seasonic", "Focus GX-650", 220000), ("Asus", "ROG Strix 850W Gold", 320000)],
"gabinete": [("Cooler Master", "TD500 Mesh V2", 195000), ("NZXT", "H7 Flow", 290000),
    ("Lian Li", "Lancool 216", 230000), ("Corsair", "5000D Airflow", 320000),
    ("Thermaltake", "S100 TG", 78000), ("Gamemax", "Infinity", 115000),
    ("Montech", "King 95", 245000), ("Antec", "NX410", 95000)],
"cooler": [("DeepCool", "LE500", 62000), ("DeepCool", "AK500", 92000),
    ("Cooler Master", "Hyper 212 Halo", 78000), ("Noctua", "NH-D15", 195000),
    ("Arctic", "Liquid Freezer III 360", 245000), ("Thermalright", "Frozen Notte 360", 165000),
    ("Lian Li", "Galahad II 240", 230000)],
"microfono": [("HyperX", "SoloCast", 95000), ("Blue", "Yeti Nano", 175000),
    ("Razer", "Seiren V3 Mini", 78000), ("FIFINE", "T669", 78000),
    ("Rode", "NT-USB+", 285000), ("Shure", "MV7", 480000)],
"webcam": [("Logitech", "C270 HD", 48000), ("Logitech", "StreamCam", 245000),
    ("Razer", "Kiyo Pro", 245000), ("Genius", "QCam 6000", 52000),
    ("AverMedia", "PW313", 110000)],
"parlante": [("Logitech", "Z625 THX", 245000), ("Logitech", "Z906 5.1", 520000),
    ("Edifier", "R1700BT", 220000), ("JBL", "Charge 5", 215000),
    ("JBL", "Clip 4", 78000), ("Genius", "SW-2.1 375", 42000)],
"silla gamer": [("Redragon", "King of War", 320000), ("Redragon", "Gaia", 360000),
    ("Cougar", "Fusion", 420000), ("Gamemax", "GCR08", 280000),
    ("DT3", "Elise", 460000), ("Corsair", "TC100 Relaxed", 390000),
    ("Noblechairs", "Epic", 690000)],
"almacenamiento externo": [("Seagate", "One Touch", 110000),
    ("Western Digital", "My Passport", 120000), ("Toshiba", "Canvio Advance", 98000),
    ("SanDisk", "Extreme Portable SSD", 175000), ("Kingston", "DataTraveler Max", 38000),
    ("SanDisk", "Ultra Dual Drive", 24000)],
"router": [("TP-Link", "Archer AX55", 130000), ("TP-Link", "Archer AX73", 195000),
    ("TP-Link", "Deco X50 Mesh", 290000), ("Mercusys", "MR70X", 72000),
    ("Tenda", "AC8", 55000), ("Tenda", "Nova MW6 Mesh", 165000)],
"impresora": [("Epson", "EcoTank L4260", 360000), ("Epson", "EcoTank L5590", 520000),
    ("HP", "DeskJet 2775", 175000), ("HP", "Smart Tank 720", 410000),
    ("Brother", "HL-1212W", 195000), ("Canon", "Pixma G2160", 260000)],
"cargador": [("Anker", "511 Nano 3", 28000), ("Anker", "735 GaN 65W", 88000),
    ("Baseus", "GaN5 Pro 100W", 92000), ("Samsung", "25W Super Fast", 35000),
    ("Xiaomi", "67W Turbo", 52000), ("UGREEN", "Nexode 65W", 78000)],
"tablet": [("Samsung", "Galaxy Tab A8", 280000), ("Samsung", "Galaxy Tab S9 FE", 720000),
    ("Lenovo", "Tab M10", 230000), ("Lenovo", "Tab P11", 390000),
    ("Xiaomi", "Pad 6", 540000)],
}
for _cat, _items in EXTRA.items():
    if _cat in CATS:
        CATS[_cat]["items"].extend(_items)

# Config como variante REAL de notebook (mismo modelo, distinto procesador/RAM).

# Dimensiones y peso PLAUSIBLES por categoria: (ancho, prof, alto cm, peso_min,
# peso_max gramos). Evita los absurdos del fixture viejo (mouse de 5 kg).
DIMS = {
    "mouse": (12, 6.5, 4, 70, 150), "teclado": (44, 14, 4, 500, 1500),
    "monitor": (62, 42, 22, 3000, 8000), "auriculares": (20, 18, 9, 150, 400),
    "notebook": (36, 24, 2, 1500, 2600), "placa de video": (30, 13, 5, 700, 1600),
    "procesador": (4, 4, 1, 50, 120), "motherboard": (27, 22, 5, 600, 1200),
    "memoria ram": (13, 3.4, 0.7, 30, 120), "ssd": (8, 2.5, 0.8, 8, 60),
    "fuente": (15, 16, 8.6, 1500, 3000), "gabinete": (45, 22, 45, 4000, 9000),
    "cooler": (13, 12, 16, 400, 1500), "microfono": (22, 10, 10, 300, 1600),
    "webcam": (9, 3, 3, 80, 200), "parlante": (18, 14, 22, 300, 3000),
    "silla gamer": (70, 70, 125, 12000, 22000),
    "almacenamiento externo": (11, 7.5, 1.5, 80, 250),
    "router": (24, 13, 4, 300, 700), "impresora": (40, 33, 18, 4000, 8000),
    "cargador": (6, 3.5, 3, 60, 150), "tablet": (18, 16.5, 0.7, 300, 600),
}

# Capacidades/tamaños REALES por categoria, cuando el mismo modelo viene en
# varias. Multiplica SKUs sin inventar (un SSD real viene en 500GB/1TB/2TB).
CAPS = {
    "ssd": ["500GB", "1TB", "2TB"], "memoria ram": ["8GB", "16GB", "32GB"],
    "almacenamiento externo": ["1TB", "2TB", "4TB"],
    # Config real de notebook: el mismo modelo viene en varios procesadores/RAM.
    "notebook": ["Core i5 16GB 512GB SSD", "Ryzen 7 16GB 512GB SSD",
                 "Core i7 16GB 1TB SSD"],
}


def precio_var(base, i):
    factor = 1.0 + 0.18 * i
    p = base * factor * random.uniform(0.96, 1.06)
    return int(round(p / 500.0)) * 500


def _dim_peso(cat):
    w, d, h, pmin, pmax = DIMS.get(cat, (20, 15, 8, 200, 1500))
    j = lambda x: round(x * random.uniform(0.9, 1.1), 1)
    return f"{j(w)}x{j(d)}x{j(h)} cm", random.randint(pmin, pmax)


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for cat, spec in CATS.items():
        pref = spec["pref"]
        n = 0
        feats = spec["feats"]
        colores = spec["colores"]
        caps = CAPS.get(cat, [""])
        # SKU distinto y REAL = modelo x color x capacidad real. El feat solo
        # describe (no multiplica ni se mete en el nombre, asi no hay casi
        # duplicados ni contradicciones).
        multicolor = len([c for c in colores if c != "-"]) > 1
        for (marca, modelo, base) in spec["items"]:
            feat_desc = feats[0] if feats else ""
            for ci, cap in enumerate(caps):
                # El precio se fija por modelo y configuracion, NO por color (el
                # color es cosmetico). Asi las variantes de color comparten precio
                # y no parece el mismo producto a precios distintos.
                precio = precio_var(base, ci)
                for color in colores:
                    n += 1
                    pid = f"{pref}{n:04d}"
                    stock = random.choices([0, random.randint(1, 25)],
                                           weights=[1, 9])[0]
                    cap_txt = f" {cap}" if cap else ""
                    col_txt = "" if color == "-" else f", color {color.lower()}"
                    # El color va en el NOMBRE cuando hay varios, asi cada SKU es
                    # distinguible y no hay nombres duplicados.
                    col_nom = f" {color}" if (multicolor and color != "-") else ""
                    nombre = f"{cat.capitalize()} {marca} {modelo}{cap_txt}{col_nom}"
                    dim, peso = _dim_peso(cat)
                    desc = (f"{cat.capitalize()} {marca} {modelo}{cap_txt}"
                            f"{col_txt}. Nuevo y original con garantia oficial "
                            f"del fabricante. Ideal para {spec['uso'].lower()}.")
                    extra = ", ".join(x for x in (cap, feat_desc) if x)
                    rows.append({
                        "id": pid, "nombre": nombre, "categoria": cat,
                        "precio_ars": precio, "stock": stock, "descripcion": desc,
                        "marca": marca, "modelo": f"{modelo}{cap_txt}".strip(),
                        "color": "" if color == "-" else color,
                        "material": spec["material"], "peso_gramos": peso,
                        "dimensiones": dim, "garantia_meses": spec["gar"],
                        "uso_recomendado": spec["uso"],
                        "caracteristicas_extra": extra,
                    })

    out_path = os.path.join(OUT, "productos.csv")
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # FAQ rica con capa de conversion: reusamos la de verifika_demo (ya enriquecida
    # con el campo 'venta'), que es politica de negocio, tienda-agnostica.
    shutil.copy(os.path.join(DEMO, "faq.json"), os.path.join(OUT, "faq.json"))

    cats_ct = {}
    for r in rows:
        cats_ct[r["categoria"]] = cats_ct.get(r["categoria"], 0) + 1
    print(f"OK verifika_prod: {len(rows)} productos en {len(CATS)} categorias")
    for c, k in sorted(cats_ct.items()):
        print(f"  {c}: {k}")
    print(f"  productos: {out_path}")


if __name__ == "__main__":
    main()
