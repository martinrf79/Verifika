"""LA BASE DE JERGA EN DOS TABLAS, ARMADA Y CONTROLADA POR CODIGO (27-nov-2026, FICHA 111 seccion 6).

Dos tablas:
  tienda.jsonl   la palabra literal del cliente -> un concepto cerrado de la tienda: rubro, atributo, preferencia,
                 plataforma, color, origen, orden, campo de la ficha, tema de la FAQ o algo que no se vende.
  general.jsonl  lo que sirve para cualquier tienda: intencion, relleno, negacion, cantidad, plata, precio, calidad,
                 urgencia, pago, envio y referencia. Puede enlazar a un concepto de la tienda.
Y dos listas de marca: trampas.jsonl, lo que puede ser mas de una cosa, y vagas.jsonl, lo que el cliente pide y la
ficha no responde.

De donde sale: las semillas que ya habia, `alias.json` y la base de reglas de la FICHA 106, y lo que escribieron los
agentes en `crudo/`, mirando en la web el estilo de compradores argentinos sin ver el examen ni las reales. El codigo
descarta toda fila con un concepto fuera de la lista cerrada de `encargo.json`. Una expresion que dos conceptos de la
misma clase reclaman se marca como trampa: no la resuelve la tabla.

    python3 tabla.py            # arma las tablas y dice cuantas filas, por clase y por fuente
"""
import json, os, re, sys, unicodedata
from collections import Counter, defaultdict

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(AQUI, "..", "..", ".."))
B = os.path.join(REPO, "data", "clientes", "verifika_prod")


def nrm(s):
    s = "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()


ENCARGO = json.load(open(os.path.join(AQUI, "encargo.json")))
IDS_TIENDA = set(ENCARGO["conceptos"]) | set(ENCARGO["campos"]) | set(ENCARGO["temas"])
CLASES_GENERAL = {"intencion", "relleno", "negacion", "cantidad", "plata", "precio", "calidad", "urgencia", "pago",
                  "envio", "referencia"}


def clase_de(cid):
    if cid in ENCARGO["conceptos"]:
        return ENCARGO["conceptos"][cid]["clase"]
    return cid.split(":")[0]


def valido_tienda(cid):
    return cid in IDS_TIENDA or (cid or "").startswith("no_vende:")


def valido_puede_ser(x):
    return valido_tienda(x) or x in ("fuera", "sin_dato") or (x or "").split(":")[0] in CLASES_GENERAL


# La base de reglas de la FICHA 106 nombra sus conceptos corto; aca su id cerrado.
DE_REGLAS = {
    "inalambrico": "atributo:inalambrico", "con_cable": "atributo:con_cable", "gamer": "preferencia:uso_gamer",
    "oficina": "preferencia:uso_oficina", "streaming": "preferencia:uso_streaming", "ps5": "plataforma:ps5",
    "ps4": "plataforma:ps4", "xbox": "plataforma:xbox", "switch": "plataforma:nintendo_switch",
    "mac": "plataforma:macos", "iphone": "plataforma:ios", "android": "plataforma:android",
    "pc": "plataforma:pc_escritorio", "tv": "plataforma:smart_tv", "mecanico": "atributo:mecanico",
    "membrana": "atributo:membrana", "luces": "atributo:con_luces", "sin_luces": "atributo:sin_luces",
    "ips": "atributo:panel_ips", "oled": "atributo:panel_oled", "full_hd": "atributo:full_hd", "qhd": "atributo:qhd",
    "agua": "atributo:resistente_agua", "negro": "color:negro", "blanco": "color:blanco", "rojo": "color:rojo",
    "azul": "color:azul", "gris": "color:gris", "chino": "origen:fabricado_china", "barato": "orden:mas_barato",
    "caro": "orden:mas_caro", "liviano": "orden:mas_liviano",
}


def semillas():
    a = json.load(open(os.path.join(B, "alias.json")))
    for r, xs in a["rubros"].items():
        for x in xs + [r]:
            yield {"expresion": x, "concepto": "rubro:" + r.replace(" ", "_"), "fuente": "alias"}
    for t, xs in a["temas"].items():
        for x in xs:
            yield {"expresion": x, "concepto": "tema:" + t, "fuente": "alias"}
    for c, xs in a["campos"].items():
        for x in xs:
            yield {"expresion": x, "concepto": "campo:" + c, "fuente": "alias"}
    sys.path.insert(0, os.path.join(AQUI, "..", "reglas"))
    try:
        import base as R  # noqa: E402
        for nombre, _cond, xs in R.BASE:
            if nombre in DE_REGLAS:
                for x in xs:
                    yield {"expresion": x, "concepto": DE_REGLAS[nombre], "fuente": "reglas"}
    except Exception as e:  # la base de reglas lee el catalogo; si falla, se sigue sin ella y se dice
        print("sin la base de reglas:", e, file=sys.stderr)
    for k in ENCARGO["no_vende"]:
        yield {"expresion": k.split(":", 1)[1], "concepto": k, "fuente": "no_vendidas"}


def crudo():
    d = os.path.join(AQUI, "crudo")
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if not f.endswith(".jsonl"):
            continue
        for n, linea in enumerate(open(os.path.join(d, f)), 1):
            linea = linea.strip()
            if not linea:
                continue
            try:
                x = json.loads(linea)
            except Exception:
                yield None, f"{f}:{n} no es JSON"
                continue
            x["fuente"] = "agente:" + f[:-6]
            yield x, None


def armar(solo_semillas=False):
    tienda, general, trampas, vagas, malas = [], [], [], [], Counter()
    for x in semillas():
        tienda.append(x)
    for x, err in ([] if solo_semillas else crudo()):
        if err:
            malas["no es JSON"] += 1
            continue
        if not nrm(x.get("expresion")):
            malas["sin expresion"] += 1
        elif x.get("trampa"):
            ps = [p for p in x.get("puede_ser", []) if valido_puede_ser(p)]
            if len(ps) < 2:
                malas["trampa con menos de dos ids validos"] += 1
            else:
                trampas.append({"expresion": x["expresion"], "puede_ser": ps, "nota": x.get("nota", ""),
                                "fuente": x["fuente"]})
        elif x.get("vaga"):
            cc = x.get("concepto_cercano")
            vagas.append({"expresion": x["expresion"], "concepto_cercano": cc if valido_tienda(cc) else None,
                          "nota": x.get("nota", ""), "fuente": x["fuente"]})
        elif x.get("clase") in CLASES_GENERAL:
            v = x.get("valor") or ""
            if v.split(":")[0] != x["clase"]:
                malas["general con valor de otra clase"] += 1
                continue
            en = x.get("enlace")
            general.append({"expresion": x["expresion"], "clase": x["clase"], "valor": v,
                            "enlace": en if valido_tienda(en) else None, "fuente": x["fuente"]})
        elif valido_tienda(x.get("concepto")):
            tienda.append({"expresion": x["expresion"], "concepto": x["concepto"], "modo": x.get("modo", ""),
                           "fuente": x["fuente"]})
        else:
            malas["concepto fuera de la lista"] += 1

    # sin repetidos: la misma expresion al mismo concepto queda una vez, con todas sus fuentes
    def juntar(filas, clave):
        m = {}
        for x in filas:
            k = (nrm(x["expresion"]), clave(x))
            if k in m:
                m[k]["fuente"] = "|".join(sorted(set(m[k]["fuente"].split("|")) | {x["fuente"]}))
            else:
                m[k] = dict(x, nrm=k[0])
        return list(m.values())

    tienda = juntar(tienda, lambda x: (x["concepto"], x.get("modo", "")))
    general = juntar(general, lambda x: x["valor"])
    # la misma expresion reclamada por dos conceptos de la misma clase: es trampa, la tabla no la resuelve
    por = defaultdict(set)
    for x in tienda:
        por[(x["nrm"], clase_de(x["concepto"]))].add(x["concepto"])
    choques = {k: v for k, v in por.items() if len(v) > 1}
    for (e, _c), v in choques.items():
        trampas.append({"expresion": e, "puede_ser": sorted(v), "nota": "choque en la tabla", "fuente": "codigo"})
    tienda = [x for x in tienda if (x["nrm"], clase_de(x["concepto"])) not in choques]
    trampas = juntar(trampas, lambda x: tuple(sorted(x["puede_ser"])))
    vagas = juntar(vagas, lambda x: x["concepto_cercano"])
    return tienda, general, trampas, vagas, malas


def escribir(nombre, filas):
    with open(os.path.join(AQUI, nombre), "w") as f:
        for x in sorted(filas, key=lambda x: (x.get("concepto") or x.get("valor") or "", x["nrm"])):
            f.write(json.dumps(x, ensure_ascii=False) + "\n")


def cargar():
    def lee(n):
        p = os.path.join(AQUI, n)
        return [json.loads(l) for l in open(p)] if os.path.exists(p) else []
    return lee("tienda.jsonl"), lee("general.jsonl"), lee("trampas.jsonl"), lee("vagas.jsonl")


if __name__ == "__main__":
    t, g, tr, v, malas = armar()
    for n, f in (("tienda.jsonl", t), ("general.jsonl", g), ("trampas.jsonl", tr), ("vagas.jsonl", v)):
        escribir(n, f)
    print(f"tienda {len(t)}, general {len(g)}, trampas {len(tr)}, vagas {len(v)}")
    print("tienda por clase:", dict(Counter(clase_de(x["concepto"]) if not x["concepto"].startswith("no_vende")
                                            else "no_vende" for x in t)))
    print("tienda por fuente:", dict(Counter(f for x in t for f in x["fuente"].split("|"))))
    print("general por clase:", dict(Counter(x["clase"] for x in g)))
    sin = sorted(i for i in IDS_TIENDA if i not in {x["concepto"] for x in t})
    print(f"conceptos de la tienda sin ninguna expresion: {len(sin)}", sin[:20])
    print("descartadas:", dict(malas))
