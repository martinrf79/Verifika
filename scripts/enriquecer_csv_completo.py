"""
ENRIQUECIMIENTO COMPLETO DEL CATALOGO CSV — sin LLM, sin costo, sin Firestore.

Agrega a cada producto de data/clientes/verifika_prod/productos.csv los campos:
  - tags             (sinonimos de busqueda para el buscador)
  - descripcion_rica (descripcion tecnica completa, reemplaza la linea generica)
  - origen           (pais de la marca + pais de fabricacion)
  - contenido_caja   (que trae el paquete segun categoria)
  - garantia_detalle (texto completo de garantia)

Solo completa campos vacios o el campo descripcion si es la frase generica.
Nunca pisa datos ya cargados manualmente.

Uso:
    python scripts/enriquecer_csv_completo.py            # dry-run, no escribe
    python scripts/enriquecer_csv_completo.py --aplicar  # escribe el CSV

El CSV resultante reemplaza data/clientes/verifika_prod/productos.csv y queda
listo para cargar a Firestore con el script de carga normal.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
CSV_IN = ROOT / "data/clientes/verifika_prod/productos.csv"
CSV_OUT = ROOT / "data/clientes/verifika_prod/productos.csv"
APLICAR = "--aplicar" in sys.argv


# ─────────────────────────────────────────────────────────────
# TABLAS DETERMINISTAS
# ─────────────────────────────────────────────────────────────

PAIS_MARCA = {
    "logitech": "Suiza", "razer": "Estados Unidos", "hyperx": "Estados Unidos",
    "redragon": "China", "genius": "Taiwan", "corsair": "Estados Unidos",
    "asus": "Taiwan", "keychron": "China", "lg": "Corea del Sur",
    "samsung": "Corea del Sur", "aoc": "Taiwan", "gigabyte": "Taiwan",
    "philips": "Paises Bajos", "msi": "Taiwan", "viewsonic": "Estados Unidos",
    "dell": "Estados Unidos", "sony": "Japon", "jbl": "Estados Unidos",
    "sennheiser": "Alemania", "lenovo": "China", "hp": "Estados Unidos",
    "acer": "Taiwan", "zotac": "Hong Kong", "sapphire": "Hong Kong",
    "xfx": "Estados Unidos", "powercolor": "Taiwan", "asrock": "Taiwan",
    "intel": "Estados Unidos", "amd": "Estados Unidos",
    "kingston": "Estados Unidos", "g.skill": "Taiwan",
    "crucial": "Estados Unidos", "teamgroup": "Taiwan", "adata": "Taiwan",
    "patriot": "Estados Unidos", "western digital": "Estados Unidos",
    "seagate": "Estados Unidos", "lexar": "Estados Unidos",
    "evga": "Estados Unidos", "cooler master": "Taiwan",
    "thermaltake": "Taiwan", "seasonic": "Taiwan", "nzxt": "Estados Unidos",
    "lian li": "Taiwan", "gamemax": "China", "montech": "Taiwan",
    "antec": "Estados Unidos", "deepcool": "China", "noctua": "Austria",
    "arctic": "Suiza", "thermalright": "Taiwan", "blue": "Estados Unidos",
    "fifine": "China", "rode": "Australia", "shure": "Estados Unidos",
    "avermedia": "Taiwan", "edifier": "China", "cougar": "Taiwan",
    "dt3": "Brasil", "noblechairs": "Alemania", "toshiba": "Japon",
    "sandisk": "Estados Unidos", "tp-link": "China", "mercusys": "China",
    "tenda": "China", "epson": "Japon", "brother": "Japon", "canon": "Japon",
    "anker": "China", "baseus": "China", "xiaomi": "China", "ugreen": "China",
    "nvidia": "Estados Unidos", "microsoft": "Estados Unidos",
    "glorious": "Estados Unidos", "corsair": "Estados Unidos",
    "steelseries": "Dinamarca", "roccat": "Alemania", "natec": "Polonia",
    "trust": "Paises Bajos", "benq": "Taiwan", "iiyama": "Japon",
    "eaton": "Irlanda", "apc": "Estados Unidos", "cyberpower": "Estados Unidos",
}

FABRICACION_DEFAULT = {
    "procesador": "Malasia o Vietnam segun linea",
    "ssd": "China, Taiwan o Corea segun linea",
    "almacenamiento externo": "Tailandia o Malasia segun linea",
    "memoria ram": "Taiwan o China segun linea",
}
FAB_DEFAULT = "China"

CONTENIDO_CAJA = {
    "mouse": "Mouse, cable o receptor USB segun version, manual de garantia",
    "teclado": "Teclado, cable o receptor segun version, extractor de teclas segun modelo, manual de garantia",
    "monitor": "Monitor, base ajustable, fuente o cable de poder, cable de video, manual",
    "auriculares": "Auriculares, cable o receptor segun version, microfono desmontable segun modelo, manual de garantia",
    "notebook": "Notebook, cargador, manual de garantia. Sin mouse ni mochila salvo promo especial",
    "placa de video": "Placa de video, adaptadores de corriente segun modelo, manual",
    "procesador": "Procesador en caja sellada, cooler incluido en versiones BOX, manual",
    "motherboard": "Motherboard, chapa I/O, cables SATA x2, tornillos M.2, manual",
    "memoria ram": "Modulo o kit de memoria en blister sellado",
    "ssd": "Unidad SSD en blister o caja sellada, tornillo de montaje segun modelo",
    "fuente": "Fuente, cable de poder, cables modulares segun modelo, manual",
    "gabinete": "Gabinete, kit de tornillos, manual de armado. Gabinete vacio sin componentes",
    "cooler": "Cooler, kit de montaje compatible Intel y AMD, pasta termica, manual",
    "microfono": "Microfono, cable USB, soporte o tripode segun modelo, manual",
    "webcam": "Webcam con cable USB fijo, clip de montaje universal, manual",
    "parlante": "Parlantes, cables de conexion, fuente segun modelo, manual",
    "silla gamer": "Silla desarmada en caja, kit de tornillos, herramientas, manual de armado",
    "almacenamiento externo": "Unidad externa, cable USB, manual de garantia",
    "router": "Router, fuente, cable de red, guia rapida de configuracion",
    "impresora": "Impresora, cartuchos o botellas iniciales, cable USB, manual",
    "cargador": "Cargador en caja sellada, cable segun modelo",
    "tablet": "Tablet, cargador, cable, manual de garantia. Sin funda ni stylus salvo modelo especifico",
}
CONTENIDO_DEFAULT = "Producto en caja sellada con accesorios segun modelo y manual de garantia"

# Tags base por categoria: terminos que un cliente usaria al buscar
TAGS_CATEGORIA = {
    "mouse": ["mouse", "raton", "puntero", "mause"],
    "teclado": ["teclado", "keyboard", "teclas"],
    "monitor": ["monitor", "pantalla", "display", "screen"],
    "auriculares": ["auriculares", "headset", "audifonos", "headphones", "cascos"],
    "notebook": ["notebook", "laptop", "portatil", "computadora portatil", "computador"],
    "placa de video": ["placa de video", "gpu", "tarjeta de video", "grafica", "graficos"],
    "procesador": ["procesador", "cpu", "nucleo", "chip"],
    "motherboard": ["motherboard", "placa madre", "mainboard", "placa base"],
    "memoria ram": ["ram", "memoria", "memoria ram", "modulo de memoria"],
    "ssd": ["ssd", "disco solido", "almacenamiento solido", "nvme", "m.2"],
    "fuente": ["fuente", "fuente de poder", "psu", "fuente atx"],
    "gabinete": ["gabinete", "case", "caja pc", "torre"],
    "cooler": ["cooler", "disipador", "refrigeracion", "ventilador cpu"],
    "microfono": ["microfono", "mic", "micro"],
    "webcam": ["webcam", "camara web", "camara pc"],
    "parlante": ["parlante", "speaker", "bocina", "altavoz", "audio pc"],
    "silla gamer": ["silla gamer", "silla gaming", "silla ergonomica", "silla escritorio"],
    "almacenamiento externo": ["disco externo", "hdd externo", "pendrive", "almacenamiento portatil"],
    "router": ["router", "wifi", "enrutador", "punto de acceso", "internet"],
    "impresora": ["impresora", "printer", "imprimir"],
    "cargador": ["cargador", "charger", "adaptador de corriente", "fuente notebook"],
    "tablet": ["tablet", "tableta", "ipad", "tab"],
    "auriculares": ["auriculares", "headset", "headphones", "cascos", "audifonos"],
    "microfono": ["microfono", "mic", "micro", "grabacion voz"],
    "cooler": ["cooler", "disipador", "refrigeracion cpu", "ventilador"],
    "fuente": ["fuente", "psu", "fuente de poder", "fuente atx", "alimentacion"],
}

# Tags extra segun caracteristicas_extra comunes
TAGS_CARACTERISTICAS = {
    "inalambrico": ["inalambrico", "wireless", "sin cable", "bluetooth"],
    "bluetooth": ["bluetooth", "inalambrico", "wireless"],
    "rgb": ["rgb", "iluminado", "led rgb", "luces"],
    "mecanico": ["mecanico", "mechanical", "switch mecanico"],
    "switch red": ["switch red", "mecanico lineal", "red switch"],
    "switch blue": ["switch blue", "mecanico tactil", "blue switch", "click"],
    "switch brown": ["switch brown", "mecanico tactil silencioso", "brown switch"],
    "sensor optico": ["optico", "sensor optico"],
    "sensor laser": ["laser", "sensor laser"],
    "con cable": ["con cable", "cableado", "usb"],
    "4k": ["4k", "uhd", "ultra hd", "2160p"],
    "full hd": ["full hd", "1080p", "fhd", "1920x1080"],
    "2k": ["2k", "1440p", "qhd", "wqhd"],
    "144hz": ["144hz", "144 hz", "alta frecuencia", "gaming monitor"],
    "240hz": ["240hz", "240 hz", "ultra fast", "gaming competitivo"],
    "75hz": ["75hz", "75 hz"],
    "ips": ["ips", "panel ips", "colores precisos"],
    "va": ["va", "panel va", "alto contraste"],
    "tn": ["tn", "panel tn", "rapido"],
    "surround": ["surround", "7.1", "sonido envolvente"],
    "noise cancelling": ["noise cancelling", "cancelacion de ruido", "anc"],
    "7.1": ["7.1", "surround", "sonido envolvente"],
    "nvme": ["nvme", "m.2", "pcie", "ultra rapido"],
    "sata": ["sata", "2.5", "disco sata"],
    "ddr4": ["ddr4", "ram ddr4"],
    "ddr5": ["ddr5", "ram ddr5", "nueva generacion"],
    "core i5": ["core i5", "i5", "intel i5"],
    "core i7": ["core i7", "i7", "intel i7"],
    "core i9": ["core i9", "i9", "intel i9"],
    "ryzen 5": ["ryzen 5", "r5", "amd ryzen 5"],
    "ryzen 7": ["ryzen 7", "r7", "amd ryzen 7"],
    "ryzen 9": ["ryzen 9", "r9", "amd ryzen 9"],
    "rtx 4060": ["rtx 4060", "4060", "nvidia 4060"],
    "rtx 4070": ["rtx 4070", "4070", "nvidia 4070"],
    "rtx 4080": ["rtx 4080", "4080", "nvidia 4080"],
    "rtx 4090": ["rtx 4090", "4090", "nvidia 4090"],
    "rtx 3060": ["rtx 3060", "3060"],
    "rtx 3070": ["rtx 3070", "3070"],
    "rx 7600": ["rx 7600", "radeon 7600", "amd 7600"],
    "rx 7700": ["rx 7700", "radeon 7700"],
    "tenkeyless": ["tenkeyless", "tkl", "sin numpad", "compacto"],
    "tkl": ["tkl", "tenkeyless", "sin numpad"],
    "ergonomico": ["ergonomico", "ergonomica", "lumbar", "ajustable"],
    "ink tank": ["ink tank", "sistema de tinta continua", "ecotank"],
    "laser": ["laser", "impresora laser"],
}

# Plantillas de descripcion tecnica por categoria
def _descripcion_rica(p: dict) -> str:
    cat = p.get("categoria", "").lower()
    marca = p.get("marca", "")
    modelo = p.get("modelo", "")
    color = p.get("color", "")
    mat = p.get("material", "")
    peso = p.get("peso_gramos", "")
    dims = p.get("dimensiones", "")
    gar = p.get("garantia_meses", "")
    uso = p.get("uso_recomendado", "")
    extra = p.get("caracteristicas_extra", "")

    color_str = f", color {color}" if color else ""
    peso_str = f"{peso}g" if peso else ""
    dims_str = f"{dims}" if dims else ""
    gar_str = f"{gar} meses" if gar else ""

    specs = []
    if extra:
        specs.append(extra)
    if peso_str:
        specs.append(f"peso {peso_str}")
    if dims_str:
        specs.append(f"dimensiones {dims_str}")

    specs_str = ". ".join(specs) if specs else ""

    templates = {
        "mouse": (
            f"{marca} {modelo}{color_str}. {specs_str}. "
            f"Material {mat}. Garantia oficial {gar_str}. Ideal para {uso}."
        ),
        "teclado": (
            f"{marca} {modelo}{color_str}. {specs_str}. "
            f"Material {mat}. Garantia oficial {gar_str}. Ideal para {uso}."
        ),
        "monitor": (
            f"Monitor {marca} {modelo}{color_str}. {specs_str}. "
            f"Estructura en {mat}. Garantia oficial {gar_str}. Recomendado para {uso}."
        ),
        "auriculares": (
            f"Auriculares {marca} {modelo}{color_str}. {specs_str}. "
            f"Construccion en {mat}. Garantia oficial {gar_str}. Ideal para {uso}."
        ),
        "notebook": (
            f"Notebook {marca} {modelo}{color_str}. {specs_str}. "
            f"Carcasa de {mat}. Garantia oficial {gar_str}. Uso recomendado: {uso}."
        ),
        "placa de video": (
            f"Placa de video {marca} {modelo}. {specs_str}. "
            f"Garantia oficial {gar_str}. Ideal para {uso}."
        ),
        "procesador": (
            f"Procesador {marca} {modelo}. {specs_str}. "
            f"Garantia oficial {gar_str}."
        ),
        "motherboard": (
            f"Motherboard {marca} {modelo}. {specs_str}. "
            f"Garantia oficial {gar_str}."
        ),
        "memoria ram": (
            f"Memoria RAM {marca} {modelo}. {specs_str}. "
            f"Garantia oficial {gar_str}."
        ),
        "ssd": (
            f"SSD {marca} {modelo}. {specs_str}. "
            f"Garantia oficial {gar_str}."
        ),
        "fuente": (
            f"Fuente de poder {marca} {modelo}. {specs_str}. "
            f"Garantia oficial {gar_str}."
        ),
        "gabinete": (
            f"Gabinete {marca} {modelo}{color_str}. {specs_str}. "
            f"Material {mat}. Garantia oficial {gar_str}."
        ),
        "cooler": (
            f"Cooler {marca} {modelo}. {specs_str}. "
            f"Garantia oficial {gar_str}. Compatible Intel y AMD."
        ),
        "microfono": (
            f"Microfono {marca} {modelo}{color_str}. {specs_str}. "
            f"Garantia oficial {gar_str}. Ideal para {uso}."
        ),
        "webcam": (
            f"Webcam {marca} {modelo}. {specs_str}. "
            f"Garantia oficial {gar_str}. Ideal para {uso}."
        ),
        "parlante": (
            f"Parlante {marca} {modelo}{color_str}. {specs_str}. "
            f"Garantia oficial {gar_str}. Ideal para {uso}."
        ),
        "silla gamer": (
            f"Silla gamer {marca} {modelo}{color_str}. {specs_str}. "
            f"Material {mat}. Garantia oficial {gar_str}. Disenada para {uso}."
        ),
        "almacenamiento externo": (
            f"Almacenamiento externo {marca} {modelo}. {specs_str}. "
            f"Garantia oficial {gar_str}."
        ),
        "router": (
            f"Router {marca} {modelo}. {specs_str}. "
            f"Garantia oficial {gar_str}."
        ),
        "impresora": (
            f"Impresora {marca} {modelo}. {specs_str}. "
            f"Garantia oficial {gar_str}. Ideal para {uso}."
        ),
        "cargador": (
            f"Cargador {marca} {modelo}. {specs_str}. "
            f"Garantia oficial {gar_str}."
        ),
        "tablet": (
            f"Tablet {marca} {modelo}{color_str}. {specs_str}. "
            f"Garantia oficial {gar_str}. Ideal para {uso}."
        ),
    }

    desc = templates.get(cat)
    if not desc:
        desc = (f"{marca} {modelo}{color_str}. {specs_str}. "
                f"Garantia oficial {gar_str}." if specs_str else
                f"{marca} {modelo}{color_str}. Garantia oficial {gar_str}.")

    # Limpiar dobles espacios y puntos duplicados
    desc = " ".join(desc.split())
    desc = desc.replace(". .", ".").replace("..",".")
    return desc.strip()


def _generar_tags(p: dict) -> str:
    """Genera lista de tags como string separado por comas.
    Busca en nombre, modelo y caracteristicas_extra para cubrir sinonimos."""
    cat = p.get("categoria", "").lower()
    marca = p.get("marca", "").lower()
    modelo = p.get("modelo", "").lower()
    nombre = p.get("nombre", "").lower()
    extra = p.get("caracteristicas_extra", "").lower()
    uso = p.get("uso_recomendado", "").lower()
    color = p.get("color", "").lower()

    # Texto combinado para detectar atributos en nombre o extra
    texto_completo = f"{nombre} {modelo} {extra}".lower()

    tags = set()

    # Tags de categoria
    for t in TAGS_CATEGORIA.get(cat, [cat]):
        tags.add(t)

    # Marca y modelo
    if marca:
        tags.add(marca)
    if modelo:
        tags.add(modelo)
        for parte in modelo.split():
            if len(parte) > 2:
                tags.add(parte.lower())

    # Tags de caracteristicas: buscar en nombre + modelo + extra
    for key, vals in TAGS_CARACTERISTICAS.items():
        if key in texto_completo:
            tags.update(vals)

    # Detectar inalambrico/wireless en nombre o modelo
    if "wireless" in texto_completo or "inalambrico" in texto_completo or "inalámbrico" in texto_completo:
        tags.update(["inalambrico", "wireless", "sin cable"])
    if "bluetooth" in texto_completo:
        tags.update(["bluetooth", "inalambrico", "wireless"])
    if "usb" in texto_completo and "inalambrico" not in tags:
        tags.add("con cable")
        tags.add("cableado")

    # Detectar tamaño monitor por nombre
    for tam in ["24", "27", "32", "34"]:
        if f'{tam}"' in nombre or f'{tam}\"' in nombre or f' {tam} ' in nombre or nombre.startswith(f'{tam}'):
            tags.add(f"{tam} pulgadas")
            tags.add(f'{tam}"')

    # Uso recomendado
    if "gaming" in uso:
        tags.update(["gaming", "gamer"])
    if "trabajo" in uso or "estudio" in uso:
        tags.update(["trabajo", "estudio", "oficina"])
    if "home office" in uso:
        tags.update(["home office", "teletrabajo"])
    if uso and uso not in ["gaming", "trabajo y estudio"]:
        tags.add(uso)

    # Color solo si no es el default
    if color and color.lower() not in ["negro", "black"]:
        tags.add(color.lower())

    tags = {t.strip() for t in tags if t.strip() and len(t.strip()) > 1}
    return ", ".join(sorted(tags))


def _origen(p: dict) -> str:
    marca = p.get("marca", "").strip()
    mkey = marca.lower()
    cat = p.get("categoria", "").lower()
    pais_marca = PAIS_MARCA.get(mkey)
    fab = FABRICACION_DEFAULT.get(cat, FAB_DEFAULT)
    if pais_marca:
        return f"Marca {marca} de {pais_marca}. Fabricado en {fab}."
    elif marca:
        return f"Marca {marca}. Fabricado en {fab}."
    return f"Fabricado en {fab}."


def _contenido_caja(p: dict) -> str:
    cat = p.get("categoria", "").lower()
    return CONTENIDO_CAJA.get(cat, CONTENIDO_DEFAULT)


def _garantia_detalle(p: dict) -> str:
    meses = p.get("garantia_meses", "")
    marca = p.get("marca", "")
    if not meses:
        return ""
    return (
        f"Garantia oficial {marca or 'del fabricante'} de {meses} meses por "
        f"defectos de fabricacion, gestionada con el servicio tecnico autorizado "
        f"en Argentina. No cubre danos por mal uso, golpes ni humedad."
    )


DESC_GENERICA = "Nuevo y original con garantia oficial del fabricante."


def _vacio(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def enriquecer_producto(p: dict) -> dict:
    nuevos = {}

    # tags: siempre regenerar (campo nuevo)
    if _vacio(p.get("tags")):
        nuevos["tags"] = _generar_tags(p)

    # descripcion_rica: siempre agregar (nuevo campo, no pisa descripcion)
    if _vacio(p.get("descripcion_rica")):
        nuevos["descripcion_rica"] = _descripcion_rica(p)

    # descripcion: mejorar si es la frase generica
    desc_actual = p.get("descripcion", "")
    if DESC_GENERICA in desc_actual or _vacio(desc_actual):
        nuevos["descripcion"] = _descripcion_rica(p)

    # origen
    if _vacio(p.get("origen")):
        nuevos["origen"] = _origen(p)

    # contenido_caja
    if _vacio(p.get("contenido_caja")):
        nuevos["contenido_caja"] = _contenido_caja(p)

    # garantia_detalle
    if _vacio(p.get("garantia_detalle")):
        gd = _garantia_detalle(p)
        if gd:
            nuevos["garantia_detalle"] = gd

    return nuevos


def main():
    with open(CSV_IN, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        original_fields = reader.fieldnames or []
        productos = list(reader)

    print(f"Productos leidos: {len(productos)}")

    nuevos_campos = ["tags", "descripcion_rica", "origen", "contenido_caja", "garantia_detalle"]
    todos_campos = list(original_fields)
    for nc in nuevos_campos:
        if nc not in todos_campos:
            todos_campos.append(nc)

    productos_enriquecidos = []
    cambios_por_campo = {c: 0 for c in nuevos_campos + ["descripcion"]}

    for p in productos:
        nuevos = enriquecer_producto(p)
        prod_final = dict(p)
        for campo, valor in nuevos.items():
            prod_final[campo] = valor
            if campo in cambios_por_campo:
                cambios_por_campo[campo] += 1
        productos_enriquecidos.append(prod_final)

    print("\nCambios por campo:")
    for campo, count in cambios_por_campo.items():
        if count > 0:
            print(f"  {campo}: {count}/{len(productos)} productos")

    print("\nEjemplo (primer producto):")
    ej = productos_enriquecidos[0]
    for campo in nuevos_campos + ["descripcion"]:
        val = ej.get(campo, "")
        if val:
            print(f"  {campo}: {val[:120]}")

    if not APLICAR:
        print("\nDRY-RUN: no se escribio nada.")
        print("Para aplicar: python scripts/enriquecer_csv_completo.py --aplicar")
        return

    with open(CSV_OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=todos_campos, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(productos_enriquecidos)

    print(f"\nLISTO: CSV enriquecido guardado en {CSV_OUT}")
    print(f"Total campos por producto: {len(todos_campos)}")
    print(f"Campos: {', '.join(todos_campos)}")


if __name__ == "__main__":
    main()
