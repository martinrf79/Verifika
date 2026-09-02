#!/usr/bin/env python3
"""
PLANILLA DE COMPATIBILIDAD — genera `compatibilidad.csv`, la tabla de con QUE
anda cada modelo del catalogo.

Por que existe. La compatibilidad era lo unico grande que el sistema contestaba
SIN dato: el criterio jurado dice "se responde con la ficha, no de memoria",
pero la ficha no traia ni el conector, ni el zocalo, ni el sistema, asi que el
modelo terminaba razonando de memoria. De ahi salio la alucinacion que cazo el
juez el 29-jul, "es compatible con cualquier notebook", dicha sobre una memoria
RAM de escritorio que en una notebook NO entra.

Que hace la tabla. Una fila por MODELO -482 en verifika_prod, no 880- con cinco
campos atados al vocabulario CERRADO de `compatibilidad_vocabulario.json`:

  conecta_por    por donde se conecta (USB-A, Bluetooth, jack 3.5, M.2...)
  plataformas    con que equipos del cliente anda (Windows, Mac, PS5, notebook)
  requiere       que tiene que tener el equipo del cliente para que funcione
  provee         que le OFRECE a otro producto (una motherboard provee zocalo
                 AM4 y ranuras DDR4; ahi es donde se cruza con `requiere` y sale
                 el veredicto entre dos productos, sin que opine ningun modelo)
  no_compatible  el NO explicito, que es la mitad que evita la mentira

La celda vacia NO rompe nada: `app/core/compatibilidad.py` la contesta honesta
("no lo tengo confirmado, lo verifico antes de que compres"), igual que hace la
capa de specs con su hueco.

De donde sale el dato. Del MODELO REAL, que es lo que el nombre del catalogo
identifica sin ambiguedad: un Ryzen 5 5600 es AM4 y un 7600 es AM5, una Fury
Beast DDR4 no entra en una placa DDR5, un Samsung T7 es USB-C. Las reglas de
abajo son esa curaduria, escrita por FAMILIA para que no haya 482 decisiones
sueltas, con override por modelo donde la familia no alcanza. Lo que se cruza
con `specs_por_modelo.csv` -los zocalos y el tipo de RAM de las motherboards-
se toma de ahi, para que las dos tablas no puedan contradecirse.

Uso:
    python scripts/planilla_compatibilidad.py            # genera, no pisa lo cargado
    python scripts/planilla_compatibilidad.py --forzar   # regenera de cero
    python scripts/planilla_compatibilidad.py --resumen  # solo cuenta cobertura
"""
import argparse
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLUMNAS = ["marca", "modelo", "categoria", "conecta_por", "plataformas",
            "requiere", "provee", "no_compatible", "nota"]

# Equipos donde entra cualquier periferico USB de escritorio.
PC = "windows|macos|linux"
PC_NB = "windows|macos|linux|notebook|pc_escritorio"


def j(*partes):
    """Une valores del vocabulario sin repetir y sin vacios."""
    vals = []
    for p in partes:
        for v in str(p or "").split("|"):
            v = v.strip()
            if v and v not in vals:
                vals.append(v)
    return "|".join(vals)


# ── MOUSE ────────────────────────────────────────────────────────────────────
# Los inalambricos del catalogo, por como se conectan de verdad. El resto del
# listado es con cable USB-A.
MOUSE_RECEPTOR = {"NX-7000", "G Pro Wireless", "G Pro X Superlight",
                  "G305 Lightspeed", "M170", "M220 Silent", "Viper V3 Pro"}
MOUSE_BT_Y_RECEPTOR = {"MX Master 3S", "Naga V2 Pro", "Orochi V2"}


def _mouse(marca, modelo):
    if modelo in MOUSE_BT_Y_RECEPTOR:
        return dict(conecta_por="bluetooth|receptor_usb", plataformas=PC_NB,
                    requiere="puerto_usb_a|bluetooth",
                    nota="Anda por Bluetooth o con su receptor USB; con el receptor "
                         "no hace falta que el equipo tenga Bluetooth.")
    if modelo in MOUSE_RECEPTOR:
        return dict(conecta_por="receptor_usb", plataformas=PC_NB,
                    requiere="puerto_usb_a",
                    nota="Inalambrico con receptor USB incluido: se enchufa el "
                         "receptor y anda, no necesita Bluetooth.")
    return dict(conecta_por="puerto_usb_a", plataformas=PC_NB,
                requiere="puerto_usb_a",
                nota="Con cable USB: entra en cualquier puerto USB libre.")


# ── TECLADO ──────────────────────────────────────────────────────────────────
TECLADO_BT = {"K380"}                        # solo Bluetooth, multidispositivo
TECLADO_BT_RECEPTOR = {"MX Keys S", "G915 TKL"}
TECLADO_BT_CABLE = {"K2"}                    # Bluetooth o cable USB-C, sin receptor
TECLADO_USB_C = {"V3"}


def _teclado(marca, modelo):
    if modelo in TECLADO_BT_CABLE:
        return dict(conecta_por="bluetooth|puerto_usb_c", plataformas=PC_NB,
                    requiere="bluetooth|puerto_usb_a|puerto_usb_c",
                    nota="Anda por Bluetooth o con su cable USB-C; no trae "
                         "receptor aparte.")
    if modelo in TECLADO_BT:
        return dict(conecta_por="bluetooth",
                    plataformas=j(PC_NB, "android", "ios"),
                    requiere="bluetooth",
                    nota="Bluetooth multidispositivo: se empareja con la compu, "
                         "el celular o la tablet y se cambia con un boton.")
    if modelo in TECLADO_BT_RECEPTOR:
        return dict(conecta_por="bluetooth|receptor_usb", plataformas=PC_NB,
                    requiere="puerto_usb_a|bluetooth",
                    nota="Anda por Bluetooth o con su receptor USB, lo que tengas "
                         "a mano.")
    if modelo in TECLADO_USB_C:
        return dict(conecta_por="puerto_usb_c", plataformas=PC_NB,
                    requiere="puerto_usb_a|puerto_usb_c",
                    nota="Cable desmontable USB-C del lado del teclado; del otro "
                         "lado entra en un USB comun.")
    return dict(conecta_por="puerto_usb_a", plataformas=PC_NB,
                requiere="puerto_usb_a",
                nota="Con cable USB: entra en cualquier puerto USB libre.")


# ── AURICULARES ──────────────────────────────────────────────────────────────
# El conector define TODO lo que se puede prometer: el de jack 3.5 anda con la
# consola y el celular, el USB solo con la compu.
AURI_BLUETOOTH = {"Tune 510BT", "Tune 520BT", "Tune 770NC", "ULT Wear",
                  "WH-1000XM5", "WH-CH520", "WH-CH720N"}
AURI_RECEPTOR = {"G435", "G535", "G733 Lightspeed"}
AURI_USB = {"Kraken Kitty V2", "Kraken V3", "Pandora", "Zeus X"}


def _auriculares(marca, modelo):
    if modelo in AURI_BLUETOOTH:
        con_jack = modelo in {"Tune 770NC", "ULT Wear", "WH-1000XM5", "WH-CH720N"}
        return dict(
            conecta_por=j("bluetooth", "jack_35" if con_jack else ""),
            plataformas=j(PC_NB, "android", "ios",
                          "ps5|ps4|nintendo_switch" if con_jack else ""),
            requiere=j("bluetooth", "jack_35" if con_jack else ""),
            nota=("Bluetooth, y ademas traen cable de 3.5 mm para enchufarlos a "
                  "la consola o al avion." if con_jack else
                  "Solo Bluetooth: se emparejan con la compu, el celular o la "
                  "tablet."))
    if modelo in AURI_RECEPTOR:
        return dict(conecta_por="receptor_usb|bluetooth" if modelo == "G435"
                    else "receptor_usb",
                    plataformas=j(PC_NB, "ps5|ps4",
                                  "android|ios" if modelo == "G435" else ""),
                    requiere="puerto_usb_a",
                    nota="Inalambricos con receptor USB: andan en la compu y "
                         "tambien en la consola enchufando el receptor.")
    if modelo in AURI_USB:
        return dict(conecta_por="puerto_usb_a", plataformas=PC_NB,
                    requiere="puerto_usb_a", no_compatible="ps5|ps4|xbox",
                    nota="Son USB con sonido virtual: andan en la compu, en la "
                         "consola no.")
    return dict(conecta_por="jack_35",
                plataformas=j(PC_NB, "ps5|ps4|xbox|nintendo_switch",
                              "android|ios"),
                requiere="jack_35",
                nota="Conector de 3.5 mm: andan con la compu, la consola y el "
                     "celular que tenga entrada de auriculares.")


# ── PARLANTE ─────────────────────────────────────────────────────────────────
PARLANTE_BT = {"Charge 5", "Clip 4", "Flip 6", "Go 3"}
PARLANTE_BT_CABLE = {"R1700BT", "Z207 Bluetooth"}


def _parlante(marca, modelo):
    if modelo in PARLANTE_BT:
        return dict(conecta_por="bluetooth",
                    plataformas=j(PC_NB, "android", "ios", "smart_tv"),
                    requiere="bluetooth",
                    nota="Portatil por Bluetooth: se empareja con el celular, la "
                         "tablet o la compu.")
    if modelo in PARLANTE_BT_CABLE:
        return dict(conecta_por="bluetooth|jack_35|rca",
                    plataformas=j(PC_NB, "android", "ios", "smart_tv"),
                    requiere="bluetooth|jack_35",
                    nota="Bluetooth o cable: podes usarlo con la compu por cable "
                         "y con el celular por Bluetooth.")
    con_rca = modelo in {"R1280T", "Z625 THX", "Z906 5.1"}
    return dict(conecta_por=j("jack_35", "rca" if con_rca else ""),
                plataformas=j(PC_NB, "smart_tv" if con_rca else ""),
                requiere=j("jack_35", "rca" if con_rca else ""),
                nota="Con cable de 3.5 mm a la salida de audio de la compu."
                     + (" Tambien tiene entradas RCA para el televisor."
                        if con_rca else ""))


# ── MICROFONO / WEBCAM ───────────────────────────────────────────────────────
MICRO_USB_C = {"NT-USB Mini", "NT-USB+", "MV7"}
WEBCAM_USB_C = {"StreamCam"}


def _microfono(marca, modelo):
    tipo_c = modelo in MICRO_USB_C
    return dict(conecta_por="puerto_usb_c" if tipo_c else "puerto_usb_a",
                plataformas=PC_NB, requiere="puerto_usb_a|puerto_usb_c",
                nota="USB plug and play: se enchufa y la compu lo reconoce sin "
                     "instalar nada.")


def _webcam(marca, modelo):
    tipo_c = modelo in WEBCAM_USB_C
    return dict(conecta_por="puerto_usb_c" if tipo_c else "puerto_usb_a",
                plataformas=PC_NB, requiere="puerto_usb_a|puerto_usb_c",
                nota="USB plug and play: anda en Zoom, Meet y cualquier programa "
                     "de video sin instalar nada.")


# ── MONITOR ──────────────────────────────────────────────────────────────────
def _monitor(marca, modelo):
    return dict(conecta_por="hdmi|displayport",
                plataformas=j(PC_NB, "ps5|ps4|xbox|nintendo_switch"),
                requiere="hdmi|displayport",
                nota="Se conecta por HDMI o DisplayPort: sirve con la compu y "
                     "tambien con la consola.")


# ── NOTEBOOK / TABLET: son el EQUIPO del cliente, o sea que PROVEEN ──────────
def _notebook(marca, modelo):
    return dict(conecta_por="wifi|bluetooth",
                plataformas="windows",
                provee="puerto_usb_a|puerto_usb_c|hdmi|bluetooth|wifi|jack_35",
                nota="Viene con Windows. Tiene USB, USB-C, HDMI, Bluetooth y "
                     "WiFi, asi que le entra cualquier periferico del listado.")


def _tablet(marca, modelo):
    return dict(conecta_por="puerto_usb_c|bluetooth|wifi",
                plataformas="android",
                provee="puerto_usb_c|bluetooth|wifi",
                nota="Es Android y carga por USB-C. Le andan los teclados y "
                     "auriculares Bluetooth.")


# ── MEMORIA RAM ──────────────────────────────────────────────────────────────
# La que mas mentira genera: son modulos de ESCRITORIO y en una notebook no
# entran, por mas que la notebook tenga la misma DDR.
def _memoria(marca, modelo):
    ddr = "ranura_ddr5" if "DDR5" in modelo else "ranura_ddr4"
    otra = "DDR4" if ddr.endswith("ddr5") else "DDR5"
    return dict(conecta_por=ddr, plataformas="pc_escritorio", requiere=ddr,
                no_compatible="notebook|macos",
                nota=f"Modulo de escritorio: entra solo en placas con ranura "
                     f"{'DDR5' if ddr.endswith('ddr5') else 'DDR4'}. En una "
                     f"notebook NO entra, y en una placa {otra} tampoco: el "
                     f"zocalo es distinto.")


# ── SSD ──────────────────────────────────────────────────────────────────────
# Los que la PlayStation 5 admite de verdad: M.2 PCIe 4.0 rapidos y con
# disipador. No se pone el resto para no prometer lo que no se cumple.
SSD_PS5 = {"980 PRO", "990 PRO", "KC3000", "Fury Renegade", "T500", "P5 Plus",
           "Black SN770", "Black SN850X", "FireCuda 530"}


def _ssd(marca, modelo):
    if "SATA" in modelo:
        return dict(conecta_por="conector_sata",
                    plataformas="pc_escritorio|notebook", requiere="conector_sata",
                    nota="Formato 2.5 pulgadas SATA: entra en cualquier PC y en "
                         "la notebook que tenga bahia de disco.")
    familia = re.sub(r"\s*\d+(?:GB|TB)$", "", modelo).strip()
    ps5 = familia in SSD_PS5
    return dict(conecta_por="ranura_m2_nvme",
                plataformas=j("pc_escritorio|notebook", "ps5" if ps5 else ""),
                requiere="ranura_m2_nvme",
                nota="Formato M.2 NVMe: necesita una ranura M.2 libre en la "
                     "placa o en la notebook."
                     + (" Sirve para ampliar la PlayStation 5, que pide que le "
                        "pongas un disipador." if ps5 else ""))


# ── ALMACENAMIENTO EXTERNO ───────────────────────────────────────────────────
EXT_USB_C = {"DataTraveler Max", "T7 SSD", "Extreme Portable SSD"}
EXT_DUAL = {"Ultra Dual Drive"}


def _externo(marca, modelo):
    familia = re.sub(r"\s*\d+(?:GB|TB)$", "", modelo).strip()
    if familia in EXT_DUAL:
        conecta = "puerto_usb_a|puerto_usb_c"
        nota = ("Tiene los dos conectores, USB-A y USB-C: sirve para pasar "
                "archivos de la compu al celular sin adaptador.")
    elif familia in EXT_USB_C:
        conecta = "puerto_usb_c"
        nota = ("Se conecta por USB-C. Si tu equipo solo tiene USB comun, "
                "necesitas un adaptador.")
    else:
        conecta = "puerto_usb_a"
        nota = "Se conecta por USB comun, no necesita fuente ni instalar nada."
    return dict(conecta_por=conecta,
                plataformas=j(PC_NB, "ps5|ps4|xbox|smart_tv",
                              "android" if familia in EXT_DUAL else ""),
                requiere=conecta,
                nota=nota + " Viene formateado para Windows; en Mac o en la "
                            "consola hay que reformatearlo, que se hace en un "
                            "minuto.")


# ── IMPRESORA / ROUTER / CARGADOR ────────────────────────────────────────────
IMPRESORA_SOLO_USB = {"Pixma G2160"}


def _impresora(marca, modelo):
    if modelo in IMPRESORA_SOLO_USB:
        return dict(conecta_por="puerto_usb_a", plataformas=PC_NB,
                    requiere="puerto_usb_a",
                    no_compatible="android|ios",
                    nota="Este modelo se conecta solo por cable USB: no tiene "
                         "WiFi, asi que desde el celular no se imprime.")
    return dict(conecta_por="puerto_usb_a|wifi",
                plataformas=j(PC_NB, "android", "ios"),
                requiere="puerto_usb_a|wifi",
                nota="Se conecta por WiFi o por cable USB. Con WiFi imprimis "
                     "tambien desde el celular con la app de la marca.")


def _router(marca, modelo):
    mesh = "Mesh" in modelo or modelo.startswith("Halo") or "Nova" in modelo
    return dict(conecta_por="wifi|rj45",
                plataformas=j(PC_NB, "android", "ios", "smart_tv",
                              "ps5|ps4|xbox|nintendo_switch"),
                requiere="rj45",
                nota=("Sistema mesh: se conecta al modem de tu proveedor por "
                      "cable de red y repite la señal por toda la casa."
                      if mesh else
                      "Se conecta al modem de tu proveedor por cable de red. "
                      "Le anda cualquier equipo con WiFi."))


CARGADOR_USB_A = {"67W Turbo", "Mi 33W"}


def _cargador(marca, modelo):
    tipo_a = modelo in CARGADOR_USB_A
    return dict(conecta_por="puerto_usb_a" if tipo_a else "puerto_usb_c",
                plataformas="android|ios|notebook",
                requiere="toma_220",
                nota="Carga celulares, tablets y notebooks que carguen por USB. "
                     "La velocidad final depende del cable y de lo que admita "
                     "tu equipo.")


# ── ARMADO DE PC: aca es donde el cruce requiere/provee decide solo ──────────
SOCKET_POR_CPU = {
    "AM4": {"Ryzen 5 5500", "Ryzen 5 5600", "Ryzen 5 5600X", "Ryzen 7 5800X3D"},
    "AM5": {"Ryzen 5 7500F", "Ryzen 5 7600", "Ryzen 5 8400F", "Ryzen 7 7700X",
            "Ryzen 7 7800X3D", "Ryzen 9 7900X"},
}
# Sin grafica integrada: NO dan video solos, necesitan placa de video si o si.
# Los Intel con F y los Ryzen 5000 de escritorio no la tienen; los Ryzen 7000
# si traen una basica.
CPU_SIN_VIDEO_INTEGRADO = re.compile(r"F$|F\b|Ryzen [57] 5\d{3}|7500F|8400F")


def _procesador(marca, modelo):
    if modelo in SOCKET_POR_CPU["AM4"]:
        socket = "socket_am4"
    elif modelo in SOCKET_POR_CPU["AM5"]:
        socket = "socket_am5"
    else:
        socket = "socket_lga1700"          # Intel 12a, 13a y 14a del listado
    sin_video = bool(CPU_SIN_VIDEO_INTEGRADO.search(modelo))
    return dict(conecta_por=socket, plataformas="pc_escritorio",
                requiere=socket, no_compatible="notebook|macos",
                nota=("Va en placas con ese zocalo. "
                      + ("No trae video integrado: necesita una placa de video "
                         "para dar imagen." if sin_video else
                         "Trae video integrado, o sea que da imagen sin placa "
                         "de video.")))


def _motherboard(marca, modelo, specs):
    """El zocalo y el tipo de RAM se LEEN de specs_por_modelo.csv, que ya los
    tiene curados: dos tablas que dicen lo mismo terminan contradiciendose."""
    proc = (specs.get("procesador") or "").lower()
    ram = (specs.get("ram") or "").lower()
    if "am5" in proc:
        socket = "socket_am5"
    elif "am4" in proc:
        socket = "socket_am4"
    else:
        socket = "socket_lga1700"
    ranura = "ranura_ddr5" if "ddr5" in ram else "ranura_ddr4"
    micro = bool(re.search(r"\bM\b|M-|M\.|M/|[AB]\d{3}M", modelo))
    formato = "formato_micro_atx" if micro else "formato_atx"
    return dict(conecta_por=socket, plataformas="pc_escritorio",
                requiere=j(formato, "fuente_atx"),
                provee=j(socket, ranura, "ranura_m2_nvme", "conector_sata",
                         "pcie_x16"),
                no_compatible="notebook|macos",
                nota="Acepta procesadores de ese zocalo y memorias de ese tipo. "
                     "Tiene ranura M.2 para SSD y ranura PCIe para la placa de "
                     "video.")


def _placa_video(marca, modelo):
    return dict(conecta_por="pcie_x16", plataformas="pc_escritorio",
                requiere="pcie_x16|fuente_atx", no_compatible="notebook|macos",
                nota="Va en la ranura PCIe de una PC de escritorio y necesita "
                     "una fuente con la potencia y los conectores que pide. En "
                     "una notebook no se puede poner.")


def _fuente(marca, modelo):
    return dict(conecta_por="fuente_atx", plataformas="pc_escritorio",
                requiere="toma_220|formato_atx", provee="fuente_atx",
                no_compatible="notebook",
                nota="Formato ATX estandar: entra en cualquier gabinete de PC de "
                     "escritorio.")


def _gabinete(marca, modelo):
    solo_micro = modelo in {"Prime AP201"}
    return dict(conecta_por="formato_atx", plataformas="pc_escritorio",
                provee=("formato_micro_atx" if solo_micro else
                        "formato_atx|formato_micro_atx") + "|fuente_atx",
                no_compatible="notebook",
                nota=("Es compacto: le entran placas Micro-ATX y Mini-ITX, una "
                      "ATX grande no." if solo_micro else
                      "Le entran placas ATX y Micro-ATX, y fuente de formato "
                      "ATX."))


def _cooler(marca, modelo):
    liquido = bool(re.search(r"Liquid|Galahad|Frozen Notte|ML\d|LE\d", modelo))
    return dict(conecta_por="socket_am4|socket_am5|socket_lga1700",
                plataformas="pc_escritorio",
                requiere="socket_am4|socket_am5|socket_lga1700",
                no_compatible="notebook",
                nota=("Refrigeracion liquida: trae los soportes para Intel y AMD, "
                      "y el gabinete tiene que tener lugar para el radiador."
                      if liquido else
                      "Trae el kit de montaje para Intel y para AMD, asi que "
                      "entra en los dos."))


def _silla(marca, modelo):
    return dict(nota="No se conecta a nada: no tiene requisitos de "
                     "compatibilidad con tu equipo.")


REGLAS = {
    "mouse": _mouse, "teclado": _teclado, "auriculares": _auriculares,
    "parlante": _parlante, "microfono": _microfono, "webcam": _webcam,
    "monitor": _monitor, "notebook": _notebook, "tablet": _tablet,
    "memoria ram": _memoria, "ssd": _ssd, "almacenamiento externo": _externo,
    "impresora": _impresora, "router": _router, "cargador": _cargador,
    "procesador": _procesador, "motherboard": _motherboard,
    "placa de video": _placa_video, "fuente": _fuente, "gabinete": _gabinete,
    "cooler": _cooler, "silla gamer": _silla,
}


def modelos(tienda_id):
    """[(marca, modelo, categoria)] distintos del catalogo, en orden estable."""
    ruta = os.path.join(RAIZ, "data", "clientes", tienda_id, "productos.csv")
    vistos, out = set(), []
    with open(ruta, encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            clave = (fila.get("marca", "").strip(), fila.get("modelo", "").strip(),
                     (fila.get("categoria") or "").strip().lower())
            if clave[1] and clave not in vistos:
                vistos.add(clave)
                out.append(clave)
    return sorted(out, key=lambda c: (c[2], c[0], c[1]))


def specs_curadas(tienda_id):
    """{(marca, modelo, categoria): {spec: valor}} de specs_por_modelo.csv."""
    ruta = os.path.join(RAIZ, "data", "clientes", tienda_id, "specs_por_modelo.csv")
    out = {}
    if not os.path.exists(ruta):
        return out
    with open(ruta, encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            clave = (fila.get("marca", "").strip(), fila.get("modelo", "").strip(),
                     (fila.get("categoria") or "").strip().lower())
            out[clave] = {k: (v or "").strip() for k, v in fila.items()
                          if k not in ("marca", "modelo", "categoria")}
    return out


def fila_de(marca, modelo, categoria, specs):
    regla = REGLAS.get(categoria)
    if not regla:
        return dict(marca=marca, modelo=modelo, categoria=categoria)
    kwargs = {"marca": marca, "modelo": modelo}
    if regla is _motherboard:
        kwargs["specs"] = specs
    datos = regla(**kwargs)
    fila = {"marca": marca, "modelo": modelo, "categoria": categoria}
    for col in COLUMNAS[3:]:
        fila[col] = datos.get(col, "")
    return fila


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tienda", default="verifika_prod")
    ap.add_argument("--forzar", action="store_true",
                    help="regenera de cero, pisando lo que ya esta cargado")
    ap.add_argument("--resumen", action="store_true")
    args = ap.parse_args()

    destino = os.path.join(RAIZ, "data", "clientes", args.tienda,
                           "compatibilidad.csv")
    cargado = {}
    if os.path.exists(destino) and not args.forzar:
        with open(destino, encoding="utf-8") as f:
            for fila in csv.DictReader(f):
                cargado[(fila["marca"], fila["modelo"], fila["categoria"])] = fila

    specs = specs_curadas(args.tienda)
    filas = []
    for marca, modelo, categoria in modelos(args.tienda):
        clave = (marca, modelo, categoria)
        previa = cargado.get(clave)
        nueva = fila_de(marca, modelo, categoria, specs.get(clave, {}))
        # lo cargado a mano manda: la planilla completa huecos, no pisa curaduria
        if previa:
            for col in COLUMNAS[3:]:
                if (previa.get(col) or "").strip():
                    nueva[col] = previa[col]
        filas.append(nueva)

    con_dato = sum(1 for f in filas if any(f.get(c) for c in COLUMNAS[3:8]))
    print(f"modelos: {len(filas)} | con compatibilidad cargada: {con_dato}")
    if args.resumen:
        return
    with open(destino, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader()
        w.writerows(filas)
    print("escrito:", destino)


if __name__ == "__main__":
    main()
