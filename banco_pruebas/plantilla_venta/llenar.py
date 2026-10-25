"""EL LLENADO — la plantilla con la fuente de una tienda, y cada caso validado por el ejecutor, 25-oct-2026, FICHA 80.

Sin modelo y sin credenciales: la fuente sale de `data/clientes/<tienda>/` por el doble de Firestore.

  1. Los huecos de cada caso se llenan con la fuente. En las frases, como lo dice un cliente: el rubro con las palabras
     de la base de conocimiento que el codigo lleva a ese rubro, rotando por frase, y el producto con el nombre mas
     corto que la identidad certifica. En la agenda, con el nombre de la tienda.
  2. Los turnos de `antes` se corren por el ejecutor: el estado que dejan es el mostrador, y la libreta es lo que el
     modelo veria en ese turno.
  3. La agenda del caso se corre por el ejecutor con ese estado, y se compara con lo que el caso espera.
  4. La respuesta: el dato de la redaccion viva y el gancho del caso, por `motor.py`.

Un caso no entra si falta su hueco en la fuente, si su clase no aplica a la tienda o si la validacion falla. El
informe dice cuantos y por que.

    python3 -m banco_pruebas.plantilla_venta.llenar                 el informe
    python3 -m banco_pruebas.plantilla_venta.llenar --ver AR05a     un caso entero, con su libreta y su respuesta
    python3 -m banco_pruebas.plantilla_venta.llenar --escribir      deja el llenado en llenado_<tienda>.jsonl
"""
import collections
import copy
import csv
import json
import logging
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

TID = os.environ.get("TIENDA_PLANTILLA", "verifika_prod")

# Lo que no es de la tienda.
LUGARES = ["Rosario", "Mendoza", "Cordoba", "Salta"]
NOMBRES = ["Lucia Gomez", "Martin Ruiz", "Sofia Benitez"]
# Como dice el cliente cada plataforma de la tabla de compatibilidades.
# Como dice el cliente cada equipo de la tabla de compatibilidades, y como lo copia la agenda: sin el articulo, que
# el codigo arma la pregunta con "tu". Los sistemas operativos no son equipos: "¿que modelo es tu Windows?".
EQUIPOS = {"ps5": ("la PS5", "PS5"), "ps4": ("la Play 4", "PS4"), "xbox": ("la Xbox", "Xbox"),
           "nintendo_switch": ("la Switch", "Nintendo Switch"), "android": ("mi celular Android", "celular Android"),
           "ios": ("el iPhone", "iPhone"), "smart_tv": ("la smart TV", "smart TV"), "macos": ("mi Mac", "Mac")}
# Un equipo que para saber que le sirve hace falta su modelo.
EQUIPO_MODELO = ("una notebook", "notebook")
# Los medios, como los nombra una FAQ de formas de pago.
MEDIOS = ["transferencia", "Mercado Pago", "tarjeta de credito", "efectivo", "debito"]
# El tema universal de la plantilla y como puede llamarlo la FAQ de cada tienda.
TEMAS = {
    "como_comprar": ["como_comprar"], "originales": ["marcas_originales", "originales"], "garantia": ["garantia"],
    "reposicion": ["reposicion_stock", "stock_disponibilidad"], "factura": ["factura", "datos_fiscales"],
    "promociones": ["promociones"], "mayoristas": ["mayoristas"], "confianza": ["confianza_seguridad"],
    "descuento_transferencia": ["descuento_transferencia"], "cuotas": ["cuotas"], "plazo_envio": ["plazo_envio"],
    "envios": ["envios"], "retiro": ["retiro_local"], "urgente": ["envio_urgente"], "formas_pago": ["formas_pago"],
    "contra_entrega": ["pago_contra_entrega"], "devoluciones": ["devoluciones", "cambios"],
    "defectuoso": ["defectuoso"], "usados": ["usados"], "envoltorio": ["envoltorio_regalo"],
    "ubicacion": ["ubicacion"], "monedas": ["monedas_aceptadas"], "embalaje": ["embalaje_envio"],
    "reservas": ["reservas"], "verificacion_pagos": ["verificacion_pagos"], "seguimiento": ["seguimiento_pedido"],
    "cancelacion": ["cancelacion_pedido"], "cambio_direccion": ["cambio_direccion"], "reembolso": ["reembolso"],
    "soporte": ["soporte_configuracion"], "redes": ["redes"],
}
# Los campos que describen al producto como lo pide un cliente: "inalambrico", "mecanico", "ips". El origen, la marca y
# los numeros tienen sus propias clases.
DESCRIBEN = ("conexion", "panel", "switch_teclado", "retroiluminacion", "bluetooth")
NO_EMPIEZA = {"no", "solo", "por", "de", "para", "y", "o", "si", "segun"}
# Las clases que la tienda no tiene con que vender: talle o medida en una tienda sin esa variante.
SIN_VARIANTE_TALLE = {"verifika_prod"}


def entorno():
    """El doble de Firestore con la fuente del repo y los logs callados."""
    import structlog
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL))
    logging.disable(logging.CRITICAL)
    from banco_pruebas import sim_firestore
    sim_firestore.install()


def redondeo(v: int) -> int:
    """Un monto como lo dice un cliente: para arriba, a cinco mil, a diez mil o a medio millon."""
    paso = 500_000 if v >= 1_000_000 else 10_000 if v >= 100_000 else 5_000
    return -(-v // paso) * paso


def dicho(v: int) -> str:
    """El monto en palabras de cliente: "250 mil", "un millon y medio", "2 millones"."""
    if v >= 1_000_000:
        m, medio = divmod(v, 1_000_000)
        base = "un millon" if m == 1 else f"{m} millones"
        return base + (" y medio" if medio else "")
    return f"{v // 1000} mil"


def _prefijos(texto: str) -> set:
    return {w[:4] for w in re.findall(r"[a-z]+", str(texto).lower().replace("_", " ")) if len(w) > 2}


class Fuente:
    """Lo que la tienda tiene para cada hueco, elegido de forma estable y rotando entre casos."""

    def __init__(self, tid: str):
        from app.core import agente
        from app.core.flujo import catalogo as K
        self.K, self.tid = K, tid
        self.todos = K.productos(tid)
        self.temas = set(agente.indice(tid)["temas"])
        base = os.path.join(REPO, "data", "clientes", tid)
        self.base = json.load(open(os.path.join(base, "base_conocimiento.json"), encoding="utf-8"))
        self.faq = json.load(open(os.path.join(base, "faq.json"), encoding="utf-8"))
        self.no_vendidas = json.load(open(os.path.join(base, "no_vendidas.json"), encoding="utf-8"))["no_vendidas"]
        self.compat = list(csv.DictReader(open(os.path.join(base, "compatibilidad.csv"), encoding="utf-8")))
        self.hallazgos, self._conds = collections.Counter(), {}
        self.familias = self._familias()
        self.rubros = sorted({f["rubro"] for f in self.familias})
        self.dichos = {r: self._dichos(r) for r in self.rubros}
        self.descriptos = self._descriptos()

    # ── el catalogo ──────────────────────────────────────────────────────────

    def _corto(self, fam: list) -> str:
        """El nombre mas corto que la identidad certifica como ese modelo: "G305", no el nombre del catalogo."""
        p = fam[0]
        palabras = str(p.get("modelo") or "").split()
        for texto in [" ".join(palabras[:i]) for i in range(1, len(palabras) + 1)] + \
                [f"{p['marca']} " + " ".join(palabras[:i]) for i in range(1, len(palabras) + 1)]:
            if len(texto) < 3 or texto.isdigit():
                continue
            idt = self.K.identificar(texto, "", self.tid)
            if idt["veredicto"] == "exists" and idt["producto"].get("modelo") == p.get("modelo"):
                return texto
        return ""

    def _familias(self) -> list:
        grupos = collections.defaultdict(list)
        for p in self.todos:
            if p.get("modelo"):
                grupos[(p["marca"], p["modelo"], p["categoria"])].append(p)
        out = []
        for (marca, modelo, rubro), ps in sorted(grupos.items()):
            con = [p for p in ps if self.K.con_stock(p)]
            if not con:
                continue
            corto = self._corto(ps)
            if corto:
                colores = list(dict.fromkeys(p["color"] for p in con if p.get("color")))
                out.append({"marca": marca, "modelo": modelo, "rubro": rubro, "corto": corto, "productos": ps,
                            "colores": colores, "claros": [c for c in colores if self._claro(corto, c)],
                            "precio": min(int(p.get("precio_ars") or 0) for p in con)})
        # Lo corto primero: el cliente dice "el G305", no el nombre entero del catalogo.
        return sorted(out, key=lambda f: (len(f["corto"].split()), f["rubro"], f["corto"]))

    def _claro(self, corto: str, color: str) -> bool:
        """Un color que, dicho, deja un solo producto: "negro" no lo es si tambien hay "negro y rojo"."""
        idt = self.K.identificar(corto, color, self.tid)
        return idt["veredicto"] == "exists" and not idt.get("falta_color") \
            and self.K.n(idt["producto"].get("color")) == self.K.n(color)

    def _dichos(self, rubro: str) -> list:
        """Como dice un cliente el rubro: las palabras de la base de conocimiento que el codigo lleva a ese rubro."""
        out = []
        for c in self.base["categorias"]:
            if c["grupo"] != "criterio_producto":
                continue
            destinos = [self.K.rubro(d, self.tid) for d in c["disparadores"]]
            suyo = collections.Counter(r for r in destinos if r).most_common(1)
            if not suyo or suyo[0][0] != rubro:
                continue
            if not _prefijos(c["id"]) & _prefijos(rubro):
                continue  # una situacion de criterio, como las marcas, no es el rubro aunque sus palabras caigan ahi
            for d, r in zip(c["disparadores"], destinos):
                if r == rubro and d not in out and self.K.solo_rubro(d, self.tid) == rubro:
                    out.append(d)
                elif r and r != rubro:
                    # Una palabra del rubro que el codigo lleva a otro: es un hallazgo de la fuente, no un hueco.
                    self.hallazgos[f"'{d}', de {c['id']}, va al rubro {r}"] += 1
        return out or [rubro]

    def _descriptos(self) -> list:
        """El rubro dicho por como se usa —"internet en casa", "camara para zoom"—: las frases de la base de
        conocimiento de mas de una palabra que no nombran el rubro y que el codigo lleva a el."""
        out = []
        for c in self.base["categorias"]:
            if c["grupo"] != "criterio_producto":
                continue
            for d in c["disparadores"]:
                r = self.K.rubro(d, self.tid)
                if r and " " in d and not _prefijos(d) & _prefijos(r) and _prefijos(c["id"]) & _prefijos(r):
                    out.append((d, r))
        return out

    def condiciones(self, rubro: str) -> list:
        """Lo que algunos del rubro tienen y otros no, y el catalogo filtra."""
        if rubro not in self._conds:
            self._conds[rubro] = self._condiciones(rubro)
        return self._conds[rubro]

    def _condiciones(self, rubro: str) -> list:
        from app.core.flujo.catalogo import PRIORIDAD, _valores
        del_rubro = [p for p in self.todos if p.get("categoria") == rubro and self.K.con_stock(p)]
        vistos, out = set(), []
        for campo in [c for c in PRIORIDAD if c in DESCRIBEN]:
            for p in del_rubro:
                v = " ".join(self.K.n(_valores(p, campo)).split(",")[0].split()[:2])
                if not v or v in vistos or v.split()[0] in NO_EMPIEZA or re.search(r"\d| y | o ", f" {v} "):
                    continue
                vistos.add(v)
                f = self.K.atar(v, del_rubro, self.tid)
                if "campo" in f and 0 < sum(self.K.cumple(x, f) for x in del_rubro) < len(del_rubro):
                    out.append(v)
        return out

    # ── los huecos de un caso ────────────────────────────────────────────────

    def valores(self, i: int) -> dict:
        """Los huecos para el caso numero i: rota sobre los rubros que tienen todo lo que un caso pide."""
        aptos = [r for r in self.rubros if len({f["marca"] for f in self.familias if f["rubro"] == r}) >= 2
                 and any(len(f["claros"]) >= 2 for f in self.familias if f["rubro"] == r)
                 and self.condiciones(r)]
        rubro = aptos[i % len(aptos)]
        fams = [f for f in self.familias if f["rubro"] == rubro]
        fam = next(f for f in fams if len(f["claros"]) >= 2)
        fam2 = next(f for f in fams if f["modelo"] != fam["modelo"])
        # El de otro rubro, de un solo color: sumarlo no abre otra pregunta.
        otros = [f for f in self.familias if f["rubro"] != rubro and len(f["colores"]) == 1]
        otra = otros[i % len(otros)]
        marcas = list(dict.fromkeys([fam["marca"]] + [f["marca"] for f in fams]))
        conds = self.condiciones(rubro)
        prod = fam["productos"][0]
        del_rubro = [p for p in self.todos if p.get("categoria") == rubro]
        falsas = [c for c in conds if not self.K.cumple(prod, self.K.atar(c, del_rubro, self.tid))]
        compat = self._compat(i)
        total = fam["precio"] + otra["precio"]
        v = {
            "producto": fam["corto"], "producto2": fam2["corto"], "producto_otro": otra["corto"],
            "rubro": rubro, "rubro2": otra["rubro"], "color": fam["claros"][0], "color2": fam["claros"][1],
            "marca": marcas[0], "marca2": marcas[1], "condicion": conds[0],
            "condicion_falsa": falsas[0] if falsas else "",
            "uso": self.K.n(prod.get("uso_recomendado")) or "",
            "descripto": self.descriptos[i % len(self.descriptos)][0] if self.descriptos else "",
            "rubro_descripto": self.descriptos[i % len(self.descriptos)][1] if self.descriptos else "",
            "no_vendido": next((k for k in self.no_vendidas if not self.K.rubro(k, self.tid)), ""),
            "ajeno": self._ajeno(fam["marca"]),
            "producto_parcial": f"{self.dichos[rubro][0]} {fam['marca']}",
            "lugar": LUGARES[i % 2], "lugar2": LUGARES[2 + i % 2], "n": "dos", "nombre": NOMBRES[i % len(NOMBRES)],
            "plata": redondeo(int(fam["precio"] * 1.15)), "plata_total": redondeo(int(total * 1.15)),
            "plata_justa": (total - 1) // 1000 * 1000, "medio": "", "medio2": "",
            **compat,
        }
        medios = [m for m in MEDIOS if any(self.K.n(m) in self.K.n(x["respuesta"]) for x in self.faq
                                           if x["tema"] == "formas_pago")]
        if len(medios) >= 2:
            v["medio"], v["medio2"] = medios[0], medios[1]
        return v

    def _compat(self, i: int) -> dict:
        filas = []
        for r in self.compat:
            plats = [x for x in r["plataformas"].split("|") if x in EQUIPOS]
            fam = next((f for f in self.familias if f["marca"] == r["marca"] and f["modelo"] == r["modelo"]), None)
            if plats and fam:
                filas.append((fam, plats[0]))
        if not filas:
            return {"producto_compat": "", "equipo": "", "rubro_compat": "", "rubro_de_compat": "", "equipo_modelo": ""}
        fam, plat = filas[i % len(filas)]
        return {"producto_compat": fam["corto"], "equipo": EQUIPOS[plat], "rubro_compat": fam["rubro"],
                "rubro_de_compat": fam["rubro"], "equipo_modelo": EQUIPO_MODELO}

    def _ajeno(self, marca: str) -> str:
        for sufijo in ("ZX-9000", "Q777", "Nova 12"):
            if self.K.identificar(f"{marca} {sufijo}", "", self.tid)["veredicto"] == "not_found":
                return f"{marca} {sufijo}"
        return ""

    def tema(self, universal: str) -> str:
        return next((t for t in TEMAS.get(universal, [universal]) if t in self.temas), "")


PLATA = ("plata", "plata_total", "plata_justa")
HUECO = re.compile(r"\{([a-z_0-9]+)(?::([a-z_]+))?\}")


def _en_frase(texto: str, v: dict, dichos: dict, k: int) -> str:
    def cambia(m):
        nombre, sub = m.group(1), m.group(2)
        if nombre in ("rubro", "rubro2", "rubro_compat"):
            ds = dichos.get(v[nombre]) or [v[nombre]]
            return ds[k % len(ds)]
        if nombre in PLATA:
            return dicho(v[nombre])
        if nombre in ("color", "color2"):
            return str(v[nombre]).lower()
        if isinstance(v.get(nombre), tuple):
            return v[nombre][0]
        return str(v.get(nombre, m.group(0)))
    return HUECO.sub(cambia, texto)


def _en_agenda(x, v: dict, fuente: Fuente, faltan: set, campo: str = ""):
    if isinstance(x, dict):
        return {k: _en_agenda(y, v, fuente, faltan, k) for k, y in x.items()}
    if isinstance(x, list):
        return [_en_agenda(y, v, fuente, faltan, campo) for y in x]
    if not isinstance(x, str):
        return x
    m = HUECO.fullmatch(x)
    if m and m.group(1) in PLATA and campo == "tope":
        return v[m.group(1)]

    def cambia(mm):
        nombre, sub = mm.group(1), mm.group(2)
        if nombre in PLATA:
            return dicho(v[nombre])
        if nombre == "tema":
            t = fuente.tema(sub)
            if not t:
                faltan.add(f"tema {sub}")
            return t or sub
        val = v.get(nombre)
        if val in (None, ""):
            faltan.add(nombre)
            return mm.group(0)
        return str(val[1] if isinstance(val, tuple) else val)
    return HUECO.sub(cambia, x)


def _huecos_de(caso: dict) -> set:
    textos = [f[0] for f in caso["frases"]] + [caso["confirma"]]
    return {m.group(1) for t in textos for m in HUECO.finditer(t) if m.group(1) != "tema"}


def _correr(agendas: list, estado: dict, tid: str):
    from app.core.flujo.ejecutor import ejecutar
    t = None
    for ag in agendas:
        ag = copy.deepcopy(ag if isinstance(ag, dict) else {"preguntas": ag})
        for i, p in enumerate(ag["preguntas"], 1):
            p.setdefault("n", i)
            p.setdefault("cita", ag.get("respuesta") or "lo que dijo")
        t = ejecutar(ag, estado, tid, explicar=lambda q: "Explicacion de saber general.")
    return t


def _cumple(espera: dict, t, texto: str) -> str:
    """"" si el ejecutor devolvio lo que el caso espera, o por que no."""
    tipos = [h["tipo"] for h in t.hechos]
    dice = [x for x in espera.get("no_dice") or [] if x in texto]
    if dice:
        return f"la respuesta dice \"{dice[0]}\""
    if not texto.strip():
        return "la respuesta salio vacia"
    falta = [x for x in espera["tipos"] if x not in tipos]
    sobra = [x for x in espera["sin"] if x in tipos]
    perdidas = [n for n, e in t.estados.items() if e == "sin_estado"]
    if falta:
        return f"no volvio {', '.join(falta)}; volvio {', '.join(tipos) or 'nada'}"
    if sobra:
        return f"volvio {', '.join(sobra)}, que no tenia que volver"
    if perdidas:
        return "una pregunta quedo sin estado: el candado repregunto"
    if espera["pregunta"] and not t.preguntas:
        return "tenia que repreguntar y no repregunto"
    if espera.get("alguno") and not any(x in tipos or (x == "pregunta" and t.preguntas) for x in espera["alguno"]):
        return f"no volvio ninguno de {', '.join(espera['alguno'])}; volvio {', '.join(tipos) or 'nada'}"
    return ""


def llenar(tid: str = TID) -> dict:
    """Cada caso llenado y validado. Devuelve {"casos": [...], "hallazgos": {...}}."""
    from app.core.flujo import estado as E
    from app.core.flujo import interprete
    from . import casos as C
    from . import mapa as M
    from . import motor
    fuente = Fuente(tid)
    out = []
    for i, caso in enumerate(C.CASOS):
        clase = M.POR_ID[caso["clase"]]
        r = {"id": caso["id"], "clase": clase["id"], "etapa": clase["etapa"], "nombre": clase["nombre"],
             "herramienta": clase["herramienta"], "situaciones": clase["situaciones"], "origen": clase["origen"]}
        if not clase["universal"] and tid in SIN_VARIANTE_TALLE:
            out.append({**r, "entra": False, "motivo": "la clase no aplica a la tienda"})
            continue
        v = fuente.valores(i)
        faltan = {h for h in _huecos_de(caso) if v.get(h) in (None, "")}
        estado = E.leer({})
        antes = [_en_agenda(a, v, fuente, faltan) for a in caso["antes"]]
        agenda = _en_agenda(caso["agenda"], v, fuente, faltan)
        if faltan:
            out.append({**r, "entra": False, "motivo": "la fuente no tiene: " + ", ".join(sorted(faltan))})
            continue
        if antes:
            _correr(antes, estado, tid)
        libreta = interprete.libreta(estado, [], tid)
        frases = [{"texto": _en_frase(f, v, fuente.dichos, k), "variacion": var, "dificil": dif}
                  for k, (f, var, dif) in enumerate(caso["frases"])]
        if caso["responde"] or caso["cliente"]:
            agenda = {"preguntas": agenda, **({"responde": caso["responde"], "respuesta": frases[0]["texto"]}
                                              if caso["responde"] else {}),
                      **({"cliente": _en_agenda(caso["cliente"], v, fuente, faltan)} if caso["cliente"] else {})}
        t = _correr([agenda], estado, tid)
        resp = motor.responder(caso, clase["herramienta"], t)
        motivo = _cumple(caso["espera"], t, resp["texto"])
        out.append({**r, "entra": not motivo, "motivo": motivo, "frases": frases,
                    "libreta": libreta, "antes": antes, "agenda": agenda,
                    "hechos": [h["tipo"] for h in t.hechos], "estados": {str(k): e for k, e in t.estados.items()},
                    "respuesta": resp, "confirma": _en_frase(caso["confirma"], v, fuente.dichos, 0)})
    return {"casos": out, "hallazgos": dict(fuente.hallazgos)}


def informe(res: dict) -> str:
    from . import mapa as M
    casos = res["casos"]
    entran = [c for c in casos if c["entra"]]
    sin_herr = [c for c in entran if c["herramienta"].startswith("falta:")]
    r = [f"PLANTILLA DE VENTA, tienda {TID}: {len(entran)} de {len(casos)} casos entran; "
         f"{len(sin_herr)} de esos sin herramienta propia, cumplidos con lo que hay."]
    por_etapa = collections.Counter(c["etapa"] for c in entran)
    r.append("Por etapa: " + ", ".join(f"{e} {por_etapa[e]}" for e in M.ETAPAS))
    frases = sum(len(c.get("frases") or []) for c in entran)
    dificiles = sum(f["dificil"] for c in entran for f in c.get("frases") or [])
    r.append(f"Frases: {frases}, {dificiles} dificiles.")
    afuera = [c for c in casos if not c["entra"]]
    if afuera:
        r.append("No entran:")
        r += [f"  {c['id']} {c['nombre']}: {c['motivo']}" for c in afuera]
    if sin_herr:
        r.append("Sin herramienta propia: " + ", ".join(f"{c['id']} {c['herramienta'][6:]}" for c in sin_herr))
    if res["hallazgos"]:
        r.append("Hallazgos de la fuente, palabras que el codigo lleva a otro rubro:")
        r += [f"  {h}" for h in sorted(res["hallazgos"])]
    return "\n".join(r)


def ver(c: dict) -> str:
    r = [f"{c['id']} · {c['etapa']} · {c['nombre']} · {c['herramienta']} · entra: {c['entra']} {c['motivo']}"]
    for f in c.get("frases") or []:
        r.append(f"  [{f['variacion']}{' dificil' if f['dificil'] else ''}] {f['texto']}")
    if c.get("libreta"):
        r += [c["libreta"], "AGENDA: " + json.dumps(c["agenda"], ensure_ascii=False),
              "HECHOS: " + ", ".join(c["hechos"]), "RESPUESTA:", c["respuesta"]["texto"]]
    return "\n".join(r)


def main(args: list) -> None:
    entorno()
    res = llenar(TID)
    if "--ver" in args:
        ids = args[args.index("--ver") + 1:]
        print("\n\n".join(ver(c) for c in res["casos"] if c["id"] in ids or c["clase"] in ids or "todos" in ids))
        return
    print(informe(res))
    if "--escribir" in args:
        ruta = os.path.join(AQUI, f"llenado_{TID}.jsonl")
        with open(ruta, "w", encoding="utf-8") as f:
            for c in res["casos"]:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        print(f"Escrito {ruta}")


if __name__ == "__main__":
    main(sys.argv[1:])
