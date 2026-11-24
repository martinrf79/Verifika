"""LA LISTA CERRADA DE CONCEPTOS DE LA TIENDA Y EL PAR B: CONCEPTO -> CONDICION SOBRE LA FUENTE (24-nov-2026, paso 1).

Un concepto es lo que el cliente quiere, dicho del lado del usuario, con un id fijo: "rubro:auriculares",
"atributo:inalambrico", "plataforma:ps5", "color:negro", "orden:mas_barato". Cada uno lleva su condicion, que el codigo
ejecuta sobre `fuente.VISTA`. La jerga, en el paso 4, apunta a estos ids; nunca a filas.

Condicion: lista de (campo, operador, valor), todas juntas. Operadores en `cumple`.
Tipos:
  rubro       lo que es el producto
  atributo    una caracteristica que filtra
  preferencia una caracteristica que ordena pero no vacia: el uso
  plataforma  con que equipo anda
  color       la variante
  origen      donde se fabrica
  orden       no filtra: ordena por un campo
Los numeros y la compatibilidad con el equipo del cliente no son conceptos fijos: los leen `numeros.py` y `compat.py`.

    python3 conceptos.py     # arma conceptos.json y controla cada condicion contra la fuente
"""
import json, os, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.dont_write_bytecode = True
import fuente as F  # noqa: E402

nrm = F.nrm


def cumple(v, cond):
    campo, op, val = cond
    x = v.get(campo)
    if op == "igual":
        return x == val
    if op == "alguno":
        return bool(set(x or []) & set(val))
    if op == "ninguno":
        return not set(x or []) & set(val)
    if op == "tiene":
        t = nrm(" ".join(x) if isinstance(x, list) else (x or ""))
        return any(nrm(a) in t for a in val)
    if op == "empieza":
        return any(nrm(x or "").startswith(nrm(a)) for a in val)
    if op == "min":
        return x is not None and x >= val
    if op == "max":
        return x is not None and x <= val
    if op == "orden":
        return True
    raise ValueError(op)


PLATAFORMAS = {"ps5": "PlayStation 5", "ps4": "PlayStation 4", "xbox": "Xbox", "nintendo_switch": "Nintendo Switch",
               "macos": "Mac", "ios": "iPhone o iPad", "android": "Android", "smart_tv": "Smart TV",
               "pc_escritorio": "PC de escritorio", "notebook": "notebook", "windows": "Windows", "linux": "Linux"}

# Los atributos: una caracteristica, su campo y valor en la fuente. Lo que el cliente dice y la fuente no trae no esta:
# va al verificador, que dice que no tiene el dato.
ATRIBUTOS = {
    "inalambrico": ("atributo", [("conecta_por", "alguno", ["bluetooth", "receptor_usb"])]),
    "con_cable": ("atributo", [("conecta_por", "ninguno", ["bluetooth", "receptor_usb"])]),
    "bluetooth": ("atributo", [("conecta_por", "alguno", ["bluetooth"])]),
    "wifi": ("atributo", [("conecta_por", "alguno", ["wifi"])]),
    "usb_c": ("atributo", [("conecta_por", "alguno", ["puerto_usb_c"])]),
    "mecanico": ("atributo", [("switch_teclado", "tiene", ["mecanico"])]),
    "membrana": ("atributo", [("switch_teclado", "tiene", ["membrana"])]),
    "silencioso": ("atributo", [("switch_teclado", "tiene", ["membrana", "tijera"])]),
    "con_microfono": ("atributo", [("microfono", "empieza", ["si"])]),
    "cancelacion_ruido": ("atributo", [("cancelacion_ruido", "empieza", ["si"])]),
    "con_luces": ("atributo", [("retroiluminacion", "empieza", ["si"])]),
    "sin_luces": ("atributo", [("retroiluminacion", "empieza", ["no"])]),
    "resistente_agua": ("atributo", [("resistencia_agua", "empieza", ["si"])]),
    "panel_ips": ("atributo", [("panel", "tiene", ["ips"])]),
    "panel_oled": ("atributo", [("panel", "tiene", ["oled"])]),
    "panel_va": ("atributo", [("panel", "tiene", ["va"])]),
    "full_hd": ("atributo", [("resolucion", "tiene", ["full hd"])]),
    "qhd": ("atributo", [("resolucion", "tiene", ["qhd"])]),
    "ultrawide": ("atributo", [("resolucion", "tiene", ["ultrawide", "uwqhd"])]),
    "con_bateria": ("atributo", [("bateria", "empieza", ["si", "funciona con"])]),
    "uso_gamer": ("preferencia", [("uso", "empieza", ["gaming"])]),
    "uso_oficina": ("preferencia", [("uso", "tiene", ["trabajo", "oficina", "productividad"])]),
    "uso_streaming": ("preferencia", [("uso", "tiene", ["streaming", "videoconferencias"])]),
    "fabricado_china": ("origen", [("origen", "tiene", ["fabricado en china."])]),
}
ORDENES = {"mas_barato": ("precio", "asc"), "mas_caro": ("precio", "desc"), "mas_liviano": ("peso", "asc"),
           "mas_pesado": ("peso", "desc"), "mas_capacidad": ("capacidad_gb", "desc"), "mas_potente_w": ("potencia_w", "desc"),
           "mas_hz": ("hz", "desc"), "mas_ram": ("ram_gb", "desc"), "mas_pulgadas": ("pulgadas", "desc"),
           "mas_nucleos": ("nucleos", "desc")}


def armar():
    C = {}
    for r in F.RUBROS:
        C[f"rubro:{nrm(r).replace(' ', '_')}"] = {"tipo": "rubro", "nombre": r, "cond": [("rubro", "igual", r)]}
    for p, nom in PLATAFORMAS.items():
        C[f"plataforma:{p}"] = {"tipo": "plataforma", "nombre": nom, "cond": [("plataformas", "alguno", [p])]}
    colores = sorted({nrm(c) for v in F.VISTA.values() for c in v["color"]})
    for c in colores:
        C[f"color:{c.replace(' ', '_')}"] = {"tipo": "color", "nombre": c, "cond": [("color", "tiene", [c])]}
    for a, (tipo, cond) in ATRIBUTOS.items():
        C[f"{tipo}:{a}"] = {"tipo": tipo, "nombre": a.replace("_", " "), "cond": cond}
    for o, (campo, sentido) in ORDENES.items():
        C[f"orden:{o}"] = {"tipo": "orden", "nombre": o.replace("_", " "), "cond": [(campo, "orden", sentido)]}
    return C


def filas(cond):
    return [k for k, v in F.VISTA.items() if all(cumple(v, c) for c in cond)]


def control(C):
    """Cada concepto que filtra apunta a alguna fila; el orden, a un campo con dato. Devuelve los que no."""
    malos = []
    for cid, c in C.items():
        if c["tipo"] == "orden":
            campo = c["cond"][0][0]
            n = sum(1 for v in F.VISTA.values() if v.get(campo) not in (None, "", []))
        else:
            n = len(filas(c["cond"]))
        c["filas"] = n
        if not n:
            malos.append(cid)
    return malos


if __name__ == "__main__":
    C = armar()
    malos = control(C)
    json.dump(C, open(os.path.join(AQUI, "conceptos.json"), "w"), ensure_ascii=False, indent=1)
    import collections
    print("conceptos por tipo:", dict(collections.Counter(c["tipo"] for c in C.values())))
    print("sin filas en la fuente:", malos)
