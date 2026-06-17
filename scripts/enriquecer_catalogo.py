"""
ENRIQUECER CATALOGO — completa procedencia, fabricacion, contenido de caja y
garantia detallada de cada producto, POR CODIGO, sin LLM y sin costo.

Por que sin LLM: los campos faltantes salen de dos tablas chicas (marca -> pais
de la marca, categoria -> contenido de caja) mas los campos que el producto ya
tiene (garantia_meses, marca). Es mas barato, instantaneo y 100% consistente:
880 productos en segundos y dos productos de la misma marca nunca se contradicen.

Solo COMPLETA campos vacios o ausentes; nunca pisa un dato cargado.

Uso (Martin, PowerShell, con el venv y las env de .secrets6.env cargadas):
    .\\correr_local.ps1 server   # no: este script va directo con python
    python scripts/enriquecer_catalogo.py                  # dry-run, no escribe
    python scripts/enriquecer_catalogo.py --aplicar        # escribe en Firestore
    python scripts/enriquecer_catalogo.py otra_tienda --aplicar
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.storage.firestore_client import get_all_products, upsert_product

TIENDA = next((a for a in sys.argv[1:] if not a.startswith("-")), "verifika_prod")
APLICAR = "--aplicar" in sys.argv

# Pais de origen de cada marca (sede de la marca, dato publico y estable).
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
    "nvidia": "Estados Unidos", "blue yeti": "Estados Unidos",
}

# Pais de fabricacion tipico. Default China (electronica de consumo); las
# excepciones reflejan donde fabrica realmente cada rubro o marca.
FABRICACION_MARCA = {
    "noctua": "Taiwan", "seasonic": "Taiwan", "lian li": "Taiwan",
}
FABRICACION_CATEGORIA = {
    "procesador": "Malasia o Vietnam segun linea",
    "ssd": "China, Taiwan o Corea segun linea",
    "almacenamiento externo": "Tailandia o Malasia segun linea",
    "memoria ram": "Taiwan o China segun linea",
}
FABRICACION_DEFAULT = "China"

# Contenido de caja por categoria. Generico y honesto: no promete extras.
CONTENIDO_CAJA = {
    "mouse": "Mouse, cable o receptor USB segun version, manual de garantia",
    "teclado": "Teclado, cable o receptor segun version, manual de garantia",
    "monitor": "Monitor, base, fuente o cable de poder, cable de video, manual",
    "auriculares": "Auriculares, cable o receptor segun version, manual de garantia",
    "notebook": "Notebook, cargador, manual de garantia",
    "placa de video": "Placa de video, adaptadores de corriente segun modelo, manual",
    "procesador": "Procesador en caja sellada, cooler incluido segun linea, manual",
    "motherboard": "Motherboard, chapa I/O, cables SATA, tornillos M.2, manual",
    "memoria ram": "Modulo o kit de memoria en blister sellado",
    "ssd": "Unidad SSD en blister o caja sellada, tornillo segun modelo",
    "fuente": "Fuente, cable de poder, cables modulares segun modelo, manual",
    "gabinete": "Gabinete, kit de tornillos, manual de armado",
    "cooler": "Cooler, kit de montaje para Intel y AMD, pasta termica, manual",
    "microfono": "Microfono, cable USB, soporte o tripode segun modelo, manual",
    "webcam": "Webcam con cable USB, clip de montaje, manual",
    "parlante": "Parlantes, cables de conexion, fuente segun modelo, manual",
    "silla gamer": "Silla desarmada, kit de tornillos, herramientas, manual de armado",
    "almacenamiento externo": "Unidad externa, cable USB, manual de garantia",
    "router": "Router, fuente, cable de red, guia rapida",
    "impresora": "Impresora, cartuchos o botellas iniciales, cable USB, manual",
    "cargador": "Cargador en caja sellada, cable segun modelo",
    "tablet": "Tablet, cargador, cable, manual de garantia",
}
CONTENIDO_DEFAULT = "Producto en caja sellada con manual de garantia"


def _vacio(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def enriquecer(p: dict) -> dict:
    """Devuelve SOLO los campos nuevos a completar para este producto."""
    nuevos = {}
    marca = str(p.get("marca", "")).strip()
    mkey = marca.lower()
    cat = str(p.get("categoria", "")).strip().lower()

    if _vacio(p.get("origen")):
        pais = PAIS_MARCA.get(mkey)
        fab = (FABRICACION_MARCA.get(mkey)
               or FABRICACION_CATEGORIA.get(cat) or FABRICACION_DEFAULT)
        if pais:
            nuevos["origen"] = (f"Marca {marca} de {pais}. "
                                f"Fabricado en {fab}.")
        elif marca:
            nuevos["origen"] = f"Marca {marca}. Fabricado en {fab}."

    if _vacio(p.get("contenido_caja")):
        nuevos["contenido_caja"] = CONTENIDO_CAJA.get(cat, CONTENIDO_DEFAULT)

    if _vacio(p.get("garantia_detalle")):
        meses = p.get("garantia_meses")
        if meses:
            nuevos["garantia_detalle"] = (
                f"Garantia oficial {marca or 'del fabricante'} de {meses} "
                "meses por defectos de fabricacion, gestionada con el "
                "servicio tecnico autorizado en Argentina. No cubre danos "
                "por mal uso, golpes ni humedad.")

    return nuevos


def main():
    productos = get_all_products(force_refresh=True, tienda_id=TIENDA)
    print(f"Tienda {TIENDA}: {len(productos)} productos leidos.")
    if not productos:
        sys.exit(1)

    cambios = []
    marcas_sin_pais = set()
    for p in productos:
        nuevos = enriquecer(p)
        if nuevos:
            cambios.append((p.get("id") or p.get("_id"), p.get("nombre", ""), nuevos))
        mk = str(p.get("marca", "")).strip().lower()
        if mk and mk not in PAIS_MARCA:
            marcas_sin_pais.add(p.get("marca"))

    print(f"Productos a completar: {len(cambios)} de {len(productos)}")
    campos = {}
    for _, _, n in cambios:
        for k in n:
            campos[k] = campos.get(k, 0) + 1
    for k, v in sorted(campos.items()):
        print(f"  {k}: {v}")
    if marcas_sin_pais:
        print(f"Marcas sin pais en la tabla (queda solo fabricacion): "
              f"{sorted(marcas_sin_pais)}")

    print("\nEjemplos:")
    for pid, nombre, nuevos in cambios[:4]:
        print(f"- {nombre} ({pid})")
        for k, v in nuevos.items():
            print(f"    {k}: {v}")

    if not APLICAR:
        print("\nDRY-RUN: no se escribio nada. Para aplicar: --aplicar")
        return

    ok = 0
    for pid, _, nuevos in cambios:
        if not pid:
            continue
        upsert_product(pid, nuevos, tienda_id=TIENDA)
        ok += 1
        if ok % 100 == 0:
            print(f"  ... {ok}/{len(cambios)}")
    print(f"\nLISTO: {ok} productos actualizados en {TIENDA}.")


if __name__ == "__main__":
    main()
