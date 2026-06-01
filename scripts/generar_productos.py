"""Genera 100 productos realistas de tecnología/gaming en pesos argentinos."""
import json
import random

random.seed(42)

CATALOGO = [
    # MONITORES (10)
    ("MON-001", "Monitor Samsung 24'' Full HD", "monitores", 280000, 5, "Monitor LED 24'' resolución 1920x1080, HDMI y VGA, ideal oficina y uso diario"),
    ("MON-002", "Monitor LG 27'' 144Hz", "monitores", 450000, 2, "Monitor gamer 27'' 144Hz, 1ms, ideal gaming competitivo"),
    ("MON-003", "Monitor AOC 22'' Full HD", "monitores", 215000, 8, "Monitor LED 22'' 1920x1080, panel VA, conexión HDMI y VGA"),
    ("MON-004", "Monitor Samsung 32'' 4K", "monitores", 720000, 3, "Monitor 32'' resolución 4K UHD, ideal diseño y video"),
    ("MON-005", "Monitor Philips 24'' IPS", "monitores", 320000, 6, "Monitor 24'' panel IPS, colores precisos, ideal diseño"),
    ("MON-006", "Monitor Gigabyte 27'' QHD 165Hz", "monitores", 580000, 2, "Monitor gamer 27'' 2560x1440 165Hz, panel IPS, FreeSync"),
    ("MON-007", "Monitor LG UltraWide 29''", "monitores", 540000, 1, "Monitor ultrawide 29'' 2560x1080, ideal multitasking"),
    ("MON-008", "Monitor BenQ 24'' Eye-Care", "monitores", 295000, 4, "Monitor 24'' Full HD, tecnología Eye-Care, sin parpadeo"),
    ("MON-009", "Monitor Asus TUF Gaming 27''", "monitores", 620000, 2, "Monitor gamer 27'' 1ms 165Hz, panel IPS, ELMB"),
    ("MON-010", "Monitor MSI Optix 24''", "monitores", 380000, 5, "Monitor curvo 24'' 144Hz, panel VA, FreeSync"),

    # TECLADOS (12)
    ("TEC-001", "Teclado mecánico Redragon Kumara", "teclados", 85000, 12, "Teclado mecánico RGB switches red, retroiluminado, layout español"),
    ("TEC-002", "Teclado Logitech K120", "teclados", 22000, 30, "Teclado de membrana USB, layout español latinoamericano"),
    ("TEC-003", "Teclado mecánico HyperX Alloy Origins", "teclados", 195000, 4, "Teclado mecánico TKL, switches HyperX Aqua, RGB"),
    ("TEC-004", "Teclado Razer BlackWidow V3", "teclados", 245000, 3, "Teclado mecánico full size, switches Razer Green, RGB"),
    ("TEC-005", "Teclado Genius KB-110", "teclados", 14000, 50, "Teclado básico USB membrana, layout español, ideal oficina"),
    ("TEC-006", "Teclado Corsair K70 RGB MK.2", "teclados", 320000, 2, "Teclado mecánico Cherry MX Red, RGB por tecla, USB passthrough"),
    ("TEC-007", "Teclado Redragon Devarajas", "teclados", 95000, 8, "Teclado mecánico full RGB, switches outemu blue, antighosting"),
    ("TEC-008", "Teclado inalámbrico Logitech K380", "teclados", 75000, 15, "Teclado bluetooth multi-dispositivo, layout español, ultradelgado"),
    ("TEC-009", "Teclado SteelSeries Apex 3", "teclados", 145000, 6, "Teclado gaming RGB resistente al agua IP32, anti-ghosting"),
    ("TEC-010", "Teclado Microsoft Wired 600", "teclados", 28000, 25, "Teclado USB básico, layout español, ergonómico"),
    ("TEC-011", "Teclado Asus ROG Strix Scope", "teclados", 215000, 3, "Teclado mecánico Cherry MX, RGB Aura Sync, gamer"),
    ("TEC-012", "Teclado Logitech MX Keys", "teclados", 235000, 5, "Teclado inalámbrico premium, retroiluminación inteligente, USB-C"),

    # MOUSE (12)
    ("MOU-001", "Mouse Logitech G203", "mouse", 35000, 20, "Mouse gamer 8000 DPI, RGB, 6 botones programables"),
    ("MOU-002", "Mouse Razer DeathAdder V2", "mouse", 95000, 8, "Mouse gamer 20000 DPI, sensor Focus+, 8 botones, RGB"),
    ("MOU-003", "Mouse Logitech M90", "mouse", 12000, 40, "Mouse óptico USB básico, 1000 DPI, ambidiestro"),
    ("MOU-004", "Mouse HyperX Pulsefire Surge", "mouse", 75000, 10, "Mouse gamer 16000 DPI, RGB 360°, 6 botones"),
    ("MOU-005", "Mouse Redragon Cobra M711", "mouse", 32000, 18, "Mouse gamer 10000 DPI, 7 botones programables, RGB"),
    ("MOU-006", "Mouse Logitech MX Master 3", "mouse", 215000, 4, "Mouse productividad inalámbrico, scroll magnético, USB-C"),
    ("MOU-007", "Mouse Razer Basilisk V3", "mouse", 145000, 6, "Mouse gamer 26000 DPI, 11 botones, scroll wheel inteligente"),
    ("MOU-008", "Mouse SteelSeries Aerox 3", "mouse", 110000, 5, "Mouse gamer ultraliviano 59g, 18000 DPI, IP54"),
    ("MOU-009", "Mouse Microsoft Comfort 4500", "mouse", 22000, 22, "Mouse ergonómico USB, 1000 DPI, ideal oficina"),
    ("MOU-010", "Mouse Genius DX-110", "mouse", 8500, 60, "Mouse óptico USB, 1000 DPI, plug & play"),
    ("MOU-011", "Mouse inalámbrico Logitech M170", "mouse", 18000, 35, "Mouse inalámbrico USB nano, 1000 DPI, hasta 12 meses batería"),
    ("MOU-012", "Mouse Corsair Harpoon RGB", "mouse", 65000, 12, "Mouse gamer 6000 DPI, 6 botones, RGB, ergonómico"),

    # AUDIO (10)
    ("AUR-001", "Auriculares HyperX Cloud II", "audio", 145000, 7, "Auriculares gamer 7.1 surround virtual, micrófono desmontable"),
    ("AUR-002", "Auriculares Logitech G733", "audio", 245000, 4, "Auriculares gamer inalámbricos, RGB, micrófono LIGHTSPEED"),
    ("AUR-003", "Auriculares Razer Kraken X", "audio", 85000, 12, "Auriculares gamer 7.1 surround, micrófono cardioide flexible"),
    ("AUR-004", "Auriculares Sony WH-CH520", "audio", 95000, 10, "Auriculares bluetooth, 50hs autonomía, ideal música"),
    ("AUR-005", "Auriculares JBL Tune 510BT", "audio", 75000, 15, "Auriculares bluetooth on-ear, 40hs autonomía, JBL Pure Bass"),
    ("AUR-006", "Auriculares Genius HS-300A", "audio", 18000, 25, "Auriculares con micrófono, jack 3.5mm, ideal oficina/zoom"),
    ("AUR-007", "Auriculares Redragon Zeus H510", "audio", 65000, 10, "Auriculares gamer 7.1, drivers 53mm, micrófono retráctil"),
    ("AUR-008", "Auriculares SteelSeries Arctis 5", "audio", 195000, 5, "Auriculares gamer 7.1, micrófono ClearCast, RGB"),
    ("AUR-009", "Auriculares in-ear Sony MDR-EX15LP", "audio", 22000, 30, "Auriculares in-ear con cable, drivers 9mm, ideal celular"),
    ("AUR-010", "Auriculares Razer BlackShark V2 X", "audio", 115000, 6, "Auriculares gamer 7.1, drivers TriForce 50mm, ultraliviano"),

    # SILLAS GAMER (6)
    ("SIL-001", "Silla gamer Redragon Coeus", "sillas", 385000, 3, "Silla gamer reclinable, ergonómica, hasta 130kg, almohadas lumbares"),
    ("SIL-002", "Silla gamer Cougar Armor S", "sillas", 520000, 2, "Silla gamer profesional, cuero PVC, brazos 4D, hasta 120kg"),
    ("SIL-003", "Silla gamer Razer Iskur", "sillas", 850000, 1, "Silla gamer premium, soporte lumbar incorporado, cuero PVC"),
    ("SIL-004", "Silla oficina ergonómica básica", "sillas", 145000, 8, "Silla oficina giratoria, regulable en altura, malla transpirable"),
    ("SIL-005", "Silla gamer Sentey GS-1500", "sillas", 285000, 5, "Silla gamer reclinable 180°, brazos 2D, hasta 110kg"),
    ("SIL-006", "Silla gamer Noblechairs Hero", "sillas", 1100000, 1, "Silla gamer ultra premium, eco-cuero, soporte lumbar 4D"),

    # ALMACENAMIENTO (10)
    ("ALM-001", "SSD Kingston A400 480GB", "almacenamiento", 65000, 20, "SSD SATA 2.5'' 480GB, lectura 500MB/s, escritura 450MB/s"),
    ("ALM-002", "SSD Samsung 970 EVO 1TB", "almacenamiento", 185000, 6, "SSD NVMe M.2 1TB, lectura 3500MB/s, ideal gaming"),
    ("ALM-003", "Disco rígido Seagate 1TB", "almacenamiento", 75000, 15, "HDD 3.5'' 1TB 7200RPM, ideal almacenamiento masivo"),
    ("ALM-004", "SSD Western Digital Blue 500GB", "almacenamiento", 78000, 10, "SSD SATA 2.5'' 500GB, lectura 560MB/s"),
    ("ALM-005", "Disco rígido externo Toshiba 2TB", "almacenamiento", 125000, 8, "HDD externo USB 3.0 2TB, portátil, 2.5''"),
    ("ALM-006", "Pendrive Kingston DataTraveler 64GB", "almacenamiento", 18000, 30, "Pendrive USB 3.2 64GB, hasta 100MB/s"),
    ("ALM-007", "Pendrive SanDisk Cruzer 32GB", "almacenamiento", 12000, 40, "Pendrive USB 2.0 32GB, plug & play"),
    ("ALM-008", "SSD Crucial MX500 1TB", "almacenamiento", 165000, 5, "SSD SATA 2.5'' 1TB, lectura 560MB/s, AES 256-bit"),
    ("ALM-009", "Tarjeta SD Lexar 128GB", "almacenamiento", 28000, 18, "Tarjeta microSD 128GB clase 10, U3, ideal celular/cámara"),
    ("ALM-010", "SSD NVMe Western Digital SN770 500GB", "almacenamiento", 110000, 7, "SSD NVMe Gen4 500GB, lectura 5000MB/s"),

    # MEMORIA RAM (6)
    ("RAM-001", "Memoria RAM Kingston Fury 8GB DDR4", "memorias", 55000, 12, "Memoria DDR4 8GB 2666MHz, disipador, gaming"),
    ("RAM-002", "Memoria RAM Corsair Vengeance 16GB DDR4", "memorias", 115000, 8, "Kit DDR4 2x8GB 3200MHz, disipador aluminio"),
    ("RAM-003", "Memoria RAM G.Skill Ripjaws 32GB DDR4", "memorias", 235000, 4, "Kit DDR4 2x16GB 3600MHz, alto rendimiento"),
    ("RAM-004", "Memoria RAM Crucial 8GB DDR4", "memorias", 48000, 15, "Memoria DDR4 8GB 2666MHz, sin disipador"),
    ("RAM-005", "Memoria RAM Kingston Fury 16GB DDR5", "memorias", 195000, 5, "Memoria DDR5 16GB 5200MHz, RGB"),
    ("RAM-006", "Memoria RAM Corsair Dominator 32GB DDR5", "memorias", 425000, 2, "Kit DDR5 2x16GB 6000MHz, premium gaming"),

    # WEBCAMS (5)
    ("WEB-001", "Webcam Logitech C920", "webcams", 145000, 8, "Webcam Full HD 1080p, autoenfoque, micrófono dual"),
    ("WEB-002", "Webcam Genius FaceCam 1000X", "webcams", 35000, 18, "Webcam HD 720p, micrófono integrado, USB"),
    ("WEB-003", "Webcam Logitech Brio 4K", "webcams", 385000, 3, "Webcam 4K UHD, HDR, autenticación facial Windows Hello"),
    ("WEB-004", "Webcam Razer Kiyo", "webcams", 195000, 4, "Webcam 1080p 30fps, anillo de luz incorporado, streaming"),
    ("WEB-005", "Webcam HP w200", "webcams", 45000, 12, "Webcam HD 720p, plug & play, ideal videoconferencia"),

    # MICRÓFONOS (5)
    ("MIC-001", "Micrófono Blue Yeti USB", "microfonos", 215000, 5, "Micrófono condensador USB, 4 patrones polares, ideal streaming"),
    ("MIC-002", "Micrófono HyperX QuadCast", "microfonos", 245000, 3, "Micrófono condensador RGB, anti-vibración, monitoreo"),
    ("MIC-003", "Micrófono Razer Seiren X", "microfonos", 165000, 4, "Micrófono condensador supercardioide, ideal streaming"),
    ("MIC-004", "Micrófono FIFINE K669B USB", "microfonos", 65000, 12, "Micrófono USB cardioide, ideal podcast/zoom"),
    ("MIC-005", "Micrófono Audio-Technica ATR2100x", "microfonos", 195000, 4, "Micrófono dinámico USB/XLR, ideal podcast profesional"),

    # PADS Y ALFOMBRILLAS (4)
    ("PAD-001", "Pad mouse Redragon Flick L", "pads", 18000, 25, "Pad mouse 450x400mm, base antideslizante, superficie speed"),
    ("PAD-002", "Pad mouse Logitech G240", "pads", 25000, 18, "Pad mouse de tela 340x280mm, ideal sensores ópticos"),
    ("PAD-003", "Pad mouse Razer Goliathus Extended", "pads", 55000, 8, "Pad mouse XL 920x294mm, RGB, base de goma"),
    ("PAD-004", "Pad mouse SteelSeries QcK", "pads", 32000, 15, "Pad mouse mediano 320x270mm, tela alta densidad"),

    # CABLES (8)
    ("CAB-001", "Cable HDMI 2m 4K", "cables", 8500, 50, "Cable HDMI 2.0 de 2 metros, soporta 4K 60Hz"),
    ("CAB-002", "Cable HDMI 5m 4K", "cables", 14000, 30, "Cable HDMI 2.0 de 5 metros, soporta 4K 60Hz"),
    ("CAB-003", "Cable USB-C a USB-C 1m", "cables", 12000, 35, "Cable USB-C 1m, 60W carga rápida, datos hasta 10Gbps"),
    ("CAB-004", "Cable DisplayPort 1.8m", "cables", 11000, 22, "Cable DisplayPort 1.4 de 1.8m, soporta 4K 144Hz"),
    ("CAB-005", "Cable USB-A a Lightning 1m", "cables", 9500, 40, "Cable certificado MFi para iPhone, 1 metro"),
    ("CAB-006", "Adaptador USB-C a HDMI", "cables", 18000, 18, "Adaptador USB-C a HDMI 4K, plug & play"),
    ("CAB-007", "Cable de red Cat 6 5m", "cables", 6500, 60, "Cable ethernet Cat 6 UTP de 5 metros, hasta 10Gbps"),

    # HUBS USB (4)
    ("HUB-001", "Hub USB 3.0 4 puertos Genius", "hubs", 12000, 25, "Hub USB 3.0 con 4 puertos, plug & play"),
    ("HUB-002", "Hub USB-C 7 en 1 Anker", "hubs", 95000, 8, "Hub USB-C: HDMI 4K + 2x USB 3.0 + SD + microSD + USB-C PD"),
    ("HUB-003", "Hub USB 2.0 7 puertos con fuente", "hubs", 28000, 12, "Hub 7 puertos USB 2.0 con alimentación externa"),
    ("HUB-004", "Hub USB-C 5 en 1 portátil", "hubs", 55000, 10, "Hub USB-C: HDMI + 2 USB 3.0 + USB-C PD + Ethernet"),

    # COOLERS Y VENTILACIÓN (5)
    ("COO-001", "Cooler CPU DeepCool Gammaxx 400", "coolers", 65000, 10, "Cooler CPU 4 heatpipes, ventilador 120mm RGB, hasta 130W TDP"),
    ("COO-002", "Cooler Noctua NH-U12S", "coolers", 195000, 4, "Cooler CPU premium, ventilador 120mm, máximo silencio"),
    ("COO-003", "Watercooling Cooler Master ML240L", "coolers", 235000, 3, "Refrigeración líquida 240mm, RGB, compatible AMD/Intel"),
    ("COO-004", "Ventilador 120mm Corsair LL120", "coolers", 38000, 18, "Ventilador 120mm RGB, doble anillo de luz, PWM"),

    # GAMEPADS Y JOYSTICKS (5)
    ("JOY-001", "Joystick Xbox Wireless Controller", "gamepads", 185000, 6, "Control inalámbrico Xbox, compatible PC, Series X/S, bluetooth"),
    ("JOY-002", "Joystick PS5 DualSense", "gamepads", 215000, 4, "Control PS5, retroalimentación háptica, gatillos adaptativos"),
    ("JOY-003", "Joystick Logitech F310", "gamepads", 55000, 12, "Control USB para PC, 2 modos D-input/X-input, layout PlayStation"),
    ("JOY-004", "Joystick 8BitDo Pro 2", "gamepads", 145000, 5, "Control bluetooth multiplataforma, retroiluminación, customizable"),
    ("JOY-005", "Volante Logitech G29", "gamepads", 685000, 2, "Volante racing 900° con pedales, force feedback, PS4/PS5/PC"),
]

# Verificar que sean exactamente 100
print(f"Total productos: {len(CATALOGO)}")
assert len(CATALOGO) == 100, f"Se esperaban 100, hay {len(CATALOGO)}"

# Verificar IDs únicos
ids = [p[0] for p in CATALOGO]
assert len(set(ids)) == 100, "IDs duplicados"

# Generar JSON
productos = []
for pid, nombre, cat, precio, stock, desc in CATALOGO:
    productos.append({
        "id": pid,
        "nombre": nombre,
        "categoria": cat,
        "precio_ars": precio,
        "stock": stock,
        "descripcion": desc,
    })

with open("/home/claude/agente-v3/agente-firestore/data/productos.json", "w", encoding="utf-8") as f:
    json.dump(productos, f, ensure_ascii=False, indent=2)

# Stats
categorias = {}
for p in productos:
    categorias[p["categoria"]] = categorias.get(p["categoria"], 0) + 1
print("\nProductos por categoría:")
for cat, n in sorted(categorias.items()):
    print(f"  {cat}: {n}")

precios = [p["precio_ars"] for p in productos]
print(f"\nRango de precios: ${min(precios):,} - ${max(precios):,}")
print(f"Productos sin stock: {len([p for p in productos if p['stock'] == 0])}")
print(f"Stock total: {sum(p['stock'] for p in productos)} unidades")
