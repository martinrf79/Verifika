"""EL NEXO DE PRODUCTO NOMBRADO: EL RUBRO POR EMBEDDINGS Y LA IDENTIDAD POR PALABRA EXACTA (15-nov-2026).

Orden de Martin del 15-nov, FICHA 97 punto 6. La busqueda hibrida: los embeddings no distinguen G203 de G305, la palabra
exacta si. Cada parte hace lo suyo:

  PIEZA 1, EL RUBRO. Lo pone el nexo de producto, `nexo_rubro`, con los embeddings de la busqueda que tradujo el modelo:
  tres rubros, cinco candidatos y la funcion que elige. El nombrado no suma vectores: usa el rubro elegido.

  PIEZA 2, LAS PALABRAS DE IDENTIDAD. De la busqueda, las que la tienda usa como marca, o como nombre de modelo en ese
  rubro: las palabras del campo `modelo` que el rubro no usa en ningun otro campo, porque "ddr4" o "750w" son atributos.
  Las que tienen un numero, "g305", "5600x", "13400", si estan dentro de un modelo del rubro. Un numero suelto o una
  palabra corta, solo pegada a otra de identidad: "ryzen 5", "4060 ti". Una marca de la tienda que no es del rubro
  tambien es de identidad: "motherboard compatible procesador intel" no nombra ninguna motherboard.
  Sin palabras de identidad el nexo no corre: "airpods" no es de la tienda y lo contesta el de producto.

  PIEZA 3, LA IDENTIDAD. La funcion de produccion, `catalogo._identificar`, sobre los productos del rubro elegido, con
  sus tres veredictos: exists, ambiguous y not_found. El color, si la busqueda dice uno que el rubro tiene.

LA VARA, escrita antes de correr:
  `nombrados38.py`  38 mensajes con modelos gemelos. Veredicto y modelos exactos en al menos 90 por ciento de las cosas;
                    ningun exists con otro modelo; los dos que la tienda no tiene, not_found; la marca que no vende, no
                    aplica.
  las 140           lo nombrado de `nuevas70` y `nuevas70b`, abajo en `ESPERADO_140`. Mismo corte. Las lineas donde el
                    nexo corre por un atributo del modelo, "memoria ddr4", "monitor curvo", se cuentan aparte: no estan
                    en la vara.

    python3 banco_pruebas/flujo/nexo_nombrado.py --llamada0     # la llamada 0 sobre nombrados38, con la gratis
    python3 banco_pruebas/flujo/nexo_nombrado.py --embeddings   # los vectores de sus busquedas, con la gratis
    python3 banco_pruebas/flujo/nexo_nombrado.py [--ver]        # califica, sin gasto
"""
import collections
import csv
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from entorno import GRABADO, REPO  # noqa: E402

import nexo_rubro as NR  # noqa: E402

TID = NR.TID
LLAMADA0 = os.path.join(GRABADO, "nexo_nombrado_llamada0.jsonl")
PUNTAJES = os.path.join(GRABADO, "nexo_nombrado_puntajes.json")
import embeddings as EMB  # noqa: E402

# Lo nombrado de las 140: (banco, id, raiz de la busqueda, veredicto, modelos que valen).
_SONY = {"ULT Wear", "WH-1000XM5", "WH-CH520", "WH-CH720N"}
_JBL_P = {"Charge 5", "Clip 4", "Flip 6", "Go 3"}
_R5 = {"Ryzen 5 5500", "Ryzen 5 5600", "Ryzen 5 5600X", "Ryzen 5 7500F", "Ryzen 5 7600", "Ryzen 5 8400F"}
_INTEL = {"Core i3-12100F", "Core i3-14100F", "Core i5-12400F", "Core i5-13400F", "Core i5-13600KF", "Core i5-14600KF",
          "Core i7-13700KF", "Core i7-14700KF", "Core i9-14900K"}
_LOGI_M = {"G Pro Wireless", "G Pro X Superlight", "G203 Lightsync", "G305 Lightspeed", "G502 Hero", "G502 X", "G600 MMO",
           "M170", "M220 Silent", "MX Master 3S"}
_LOGI_T = {"G213 Prodigy", "G413 TKL SE", "G915 TKL", "K120", "K380", "MX Keys S"}
_LOGI_A = {"G Pro X", "G435", "G535", "G733 Lightspeed"}
_RTX = {"Dual RTX 4060", "Dual RTX 4070 Super", "ROG Strix RTX 4080 Super", "TUF RTX 4080 Super", "Eagle RTX 4060",
        "Gaming OC RTX 4060 Ti", "Gaming OC RTX 4070 Ti Super", "Gaming X RTX 4070 Ti Super", "Ventus 2X RTX 4070 Super",
        "Trinity RTX 4070", "Twin Edge RTX 4060 Ti"}
_EPSON = {"EcoTank L3250", "EcoTank L3560", "EcoTank L4260", "EcoTank L5590"}
ESPERADO_140 = [
    ("nuevas70", "M08", "procesador ryzen 5", "ambiguous", _R5),
    ("nuevas70", "M08", "motherboard compatible ryzen 5", "not_found", set()),
    ("nuevas70", "M15", "auriculares inalambricos sony", "ambiguous", _SONY),
    ("nuevas70", "M15", "parlante jbl grande", "ambiguous", _JBL_P),
    ("nuevas70", "A08", "parlante jbl flip", "exists", {"Flip 6"}),
    ("nuevas70", "A08", "parlante jbl flip azul", "exists", {"Flip 6"}),
    ("nuevas70b", "B04", "procesador ryzen 5", "ambiguous", _R5),
    ("nuevas70b", "B20", "procesador intel", "ambiguous", _INTEL),
    ("nuevas70b", "B20", "motherboard compatible procesador intel", "not_found", set()),
    ("nuevas70b", "B51", "mouse logitech", "ambiguous", _LOGI_M),
    ("nuevas70b", "B51", "teclado logitech", "ambiguous", _LOGI_T),
    ("nuevas70b", "B51", "auriculares logitech", "ambiguous", _LOGI_A),
    ("nuevas70b", "B67", "parlante jbl", "ambiguous", _JBL_P),
    ("nuevas70b", "B67", "airpods", "no aplica", set()),
    ("nuevas70b", "B68", "rtx", "ambiguous", _RTX),
    ("nuevas70b", "B68", "ryzen 7", "ambiguous", {"Ryzen 7 5800X3D", "Ryzen 7 7700X", "Ryzen 7 7800X3D"}),
    ("nuevas70b", "B69", "epson tinta continua", "ambiguous", _EPSON),
    ("nuevas70", "F01", "iphone 15 pro max", "no aplica", set()),
    ("nuevas70", "F02", "zapatillas nike talle 42", "no aplica", set()),
    ("nuevas70", "F11", "play 5", "no aplica", set()),
]


# LA SONDA: variantes de escritura que un cliente usa, escritas como las dejaria la llamada 0. No es vara: muestra que
# hace el nexo fuera de lo medido. (busqueda, lo que deberia dar)
SONDA = [
    ("logitech g 305", "exists G305 Lightspeed"), ("g-305", "exists G305 Lightspeed"),
    ("logi g305", "exists G305 Lightspeed"), ("logitec g305", "exists G305 Lightspeed"),
    ("G305 LIGHTSPEED", "exists G305 Lightspeed"), ("rtx4060", "ambiguous las dos 4060"),
    ("rtx 4060ti", "ambiguous las dos 4060 Ti"), ("i5-13400f", "exists Core i5-13400F"),
    ("i5 13400f", "exists Core i5-13400F"), ("ryzen5 5600", "exists Ryzen 5 5600"),
    ("ryzen 5 5600 x", "exists Ryzen 5 5600X"), ("sony wh1000xm5", "exists WH-1000XM5"),
    ("sony xm 5", "exists WH-1000XM5"), ("jbl flip6", "exists Flip 6"), ("jbl flip 5", "not_found"),
    ("g502x", "exists G502 X"), ("razer deathadder v3", "exists DeathAdder V3"), ("razer kraken v3", "exists Kraken V3"),
    ("hyperx cloud iii", "exists Cloud III"), ("hyperx cloud 3", "exists Cloud III"),
    ("samsung odyssey g5 32", "exists Odyssey G5 32"), ("epson l 3250", "exists EcoTank L3250"),
    ("logitech c 920", "exists C920 HD Pro"), ("logitech mx master", "exists MX Master 3S"),
    ("rtx 4070", "exists Trinity RTX 4070"), ("rx 7800 xt", "ambiguous las dos 7800 XT"),
    ("mouse logitech inalambrico", "ambiguous los Logitech inalambricos, o los Logitech: condicion"),
]


# ══ LA LLAMADA 0 Y LOS EMBEDDINGS DEL BANCO NUEVO ════════════════════════════
def correr_llamada0():
    """La misma llamada 0 de tres campos del flujo nuevo, Gemini de produccion por la gratis."""
    import flujo_nuevo as F
    from openai import OpenAI
    from app.config import get_settings
    from nombrados38 import CASOS
    s = get_settings()
    cli = OpenAI(api_key=os.environ["GEMINI_API_KEY"].split()[0], base_url=s.GEMINI_BASE_URL)
    hechas = {r["id"] for r in map(json.loads, open(LLAMADA0))} if os.path.exists(LLAMADA0) else set()
    for cid, texto, _ in CASOS:
        if cid in hechas:
            continue
        fila = {"banco": "nombrados38", "id": cid, "clave": "gratis"}
        for intento in range(5):
            try:
                t0 = time.time()
                r = cli.chat.completions.create(
                    model=s.GEMINI_MODEL, reasoning_effort="low",
                    messages=[{"role": "system", "content": F.PROMPT},
                              {"role": "user", "content": f"MENSAJE DEL CLIENTE: {texto}"}],
                    response_format={"type": "json_schema",
                                     "json_schema": {"name": "lineas", "strict": True, "schema": F.ESQUEMA}})
                t = re.sub(r"^```(?:json)?|```$", "", (r.choices[0].message.content or "").strip(), flags=re.M).strip()
                fila["salida"] = json.loads(t[t.find("{"):t.rfind("}") + 1])
                fila["segundos"] = round(time.time() - t0, 2)
                break
            except Exception as ex:  # noqa: BLE001
                print(f"  {cid} intento {intento}: {type(ex).__name__}: {str(ex)[:160]}", flush=True)
                time.sleep(20 * (intento + 1))
        if fila.get("salida"):
            with open(LLAMADA0, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
            print(f"  {cid} {[l['busqueda'] for l in fila['salida']['lineas']]}", flush=True)
        time.sleep(4)


def llamada0():
    """{("nombrados38", id): [Linea]} de lo grabado."""
    import flujo_nuevo as F
    out = {}
    if os.path.exists(LLAMADA0):
        for r in map(json.loads, open(LLAMADA0)):
            out[(r["banco"], r["id"])] = [F.Linea(str(l.get("fragmento") or ""), str(l.get("busqueda") or "").strip(),
                                                  str(l.get("destino") or "").strip()) for l in r["salida"]["lineas"]]
    return out


def embeddings():
    """Las busquedas del banco nuevo contra el mismo indice de rubros y productos del nexo de rubro. Los documentos se
    recalculan, porque el cache de la sesion que los calculo ya no esta; como control, tres busquedas de las 140 tienen
    que dar los mismos puntajes que quedaron en el repo."""
    _, alias, rubros, modelos = NR.fuente()
    ms = list(modelos)
    ir = NR.indice_rubros(rubros, alias)
    rubros, dr_t = [r for r, _ in ir], [d for _, d in ir]
    dp_t = [NR.doc_producto(k, modelos[k], alias) for k in ms]
    viejos = json.load(open(os.path.join(GRABADO, "flujo_nuevo_puntajes.json"), encoding="utf-8"))
    control = sorted(viejos["consultas"])[:3]
    qs = sorted({l.busqueda for ls in llamada0().values() for l in ls} - {""} | {q for q, _ in SONDA}) + control
    cache = EMB.cargar()
    # La gratis se traba con la cuota de embeddings; con la marca de Martin va la paga, menos de dos centavos.
    for textos, tarea in ((dr_t + dp_t, EMB.DOCUMENTO), (qs, EMB.CONSULTA)):
        EMB.pedir(textos, tarea, cache)
    dr = [cache[f"RETRIEVAL_DOCUMENT|{t}"] for t in dr_t]
    dp = [cache[f"RETRIEVAL_DOCUMENT|{t}"] for t in dp_t]

    def dot(a, b):
        return round(sum(x * y for x, y in zip(a, b)), 4)
    out = {"rubros": rubros, "modelos": [list(k) for k in ms], "consultas": {}}
    for q in qs:
        x = cache[f"RETRIEVAL_QUERY|{q}"]
        out["consultas"][q] = {"r": [dot(x, d) for d in dr], "m": [dot(x, d) for d in dp]}
    for q in control:
        dif = max(abs(a - b) for a, b in zip(out["consultas"][q]["r"] + out["consultas"][q]["m"],
                                             viejos["consultas"][q]["r"] + viejos["consultas"][q]["m"]))
        print(f"  control '{q}': diferencia maxima con el repo {dif}")
        del out["consultas"][q]
    json.dump(out, open(PUNTAJES, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"{len(qs) - len(control)} busquedas del banco nuevo")


# ══ EL NEXO ══════════════════════════════════════════════════════════════════
def _codigo(w):
    return any(c.isdigit() for c in w) and any(c.isalpha() for c in w)


class Nexo:
    def __init__(self, indice):
        from app.core.flujo.agenda import _VACIAS
        self.idx, self.vacias = indice, _VACIAS
        fs = indice.filas
        sp = {(r["marca"], r["modelo"]): r for r in csv.DictReader(
            open(os.path.join(REPO, f"data/clientes/{TID}/specs_por_modelo.csv"), encoding="utf-8"))}
        propios = {"id", "nombre", "marca", "modelo", "tags", "descripcion", "descripcion_rica", "categoria",
                   "precio_ars", "stock"}
        self.marcas = {NR.n(f["marca"]) for f in fs}
        self.por_rubro, self.rub = collections.defaultdict(list), {}
        for f in fs:
            self.por_rubro[f["categoria"]].append(f)
        for r, ps in self.por_rubro.items():
            atributos = {w for f in ps for k, v in f.items() if k not in propios for w in NR.n(v).split()}
            atributos |= {w for f in ps for k, v in (sp.get((f["marca"], f["modelo"])) or {}).items()
                          if k not in ("marca", "modelo", "categoria") for w in NR.n(v).split()}
            vocab = set(NR.n(r).split()) | {w for x in indice.alias.get(r, []) for w in NR.n(x).split()}
            tokens = {w for f in ps for w in NR.n(f["modelo"]).split()}
            # Un nombre nombra solo a sus modelos: si la palabra esta en las etiquetas o la descripcion de un modelo que
            # no la lleva en el nombre, es un atributo. "hd" esta en las etiquetas de webcams que no se llaman HD.
            describe = {w for f in ps for w in NR.n(f"{f.get('tags')} {f.get('descripcion')}").split()
                        if w not in NR.n(f["modelo"]).split()}
            self.rub[r] = {"marcas": {NR.n(f["marca"]) for f in ps}, "vocab": vocab, "tokens": tokens,
                           "nombres": {w for w in tokens - atributos - vocab - describe if not w.isdigit()},
                           "no_nombre": atributos | vocab | describe,
                           "modelos": {f["modelo"]: NR.n(f["modelo"]).split() for f in ps},
                           "colores": {NR.n(f["color"]) for f in ps if f.get("color")},
                           "por_marca": {m: {w for f in ps if NR.n(f["marca"]) == m for w in NR.n(f["modelo"]).split()}
                                         for m in {NR.n(f["marca"]) for f in ps}}}

    def palabras(self, busqueda, rubro):
        """PIEZA 2: las palabras de identidad de la busqueda en ese rubro, en orden.

        Fuertes: marca de la tienda, nombre de modelo del rubro, o codigo con letras y numeros que esta dentro de un
        modelo del rubro. Pegadas a una de identidad, encadenadas, "ryzen 5 5600": un numero o una palabra corta que
        esta en un modelo, o un codigo con letras y numeros aunque la tienda no lo tenga, "sony xm4", para que la
        identidad diga que no esta en vez de traer todos los Sony."""
        R = self.rub[rubro]
        ws = self._acomodar([w for w in NR.n(busqueda).split() if w not in self.vacias], R)

        def codigo(w):
            return any(c.isdigit() for c in w) and any(c.isalpha() for c in w)
        dentro = [any(w in t for t in R["tokens"]) for w in ws]
        # Un codigo es de identidad si lo usa una sola marca del rubro: "g305" es de Logitech; "16gb" o "750w" los
        # usan todas, son medidas metidas en el campo modelo y las resuelve el nexo de condicion.
        propio = [len({m for m, toks in R["por_marca"].items() if any(w in t for t in toks)}) == 1 for w in ws]
        # Los nombres de modelo de otro rubro no: medido el 15-nov, "parlante para smart tv" tomaba "smart" de las
        # impresoras Smart Tank y "keyboard switches red" el "red" de la Red Devil, y daban un falso "no lo tengo".
        si = [w in self.marcas or w in R["nombres"] or (codigo(w) and p) for w, p in zip(ws, propio)]
        cambio = True
        while cambio:
            cambio = False
            for i, w in enumerate(ws):
                pegada = (i > 0 and si[i - 1]) or (i + 1 < len(ws) and si[i + 1])
                if not si[i] and pegada and w not in R["vocab"] and (
                        codigo(w) or ((w.isdigit() or len(w) <= 3) and dentro[i])):
                    si[i] = cambio = True
        # La identidad de produccion exige palabra entera a lo corto: "xm5" se lleva al codigo del catalogo que lo
        # contiene, "1000xm5", si es uno solo.
        out = []
        for w, s in zip(ws, si):
            if s:
                con = {t for t in R["tokens"] if w in t}
                lleva = len(con) == 1 and (_codigo(w) or next(iter(con)).startswith(w))
                out.append(con.pop() if w not in R["tokens"] and lleva else w)
        return out

    @staticmethod
    def _acomodar(ws, R):
        """La busqueda escrita como el catalogo escribe sus codigos. Se juntan dos palabras seguidas si juntas estan en
        un codigo del rubro y alguna de las dos sola no esta: "5600 x" es "5600x", "g 305" es "g305". Se parte un codigo
        pegado que no esta en el rubro, entre letras y numeros, si sus partes son codigos exactos del rubro: "rtx4060",
        "flip6", "4060ti"; "xm4" no, porque "xm" solo esta dentro de "1000xm5"."""
        def esta(w):
            return any(w in t for t in R["tokens"])
        out, i = [], 0
        while i < len(ws):
            w = ws[i]
            if i + 1 < len(ws) and (not esta(w) or not esta(ws[i + 1]) or len(w) == 1 or len(ws[i + 1]) == 1) \
                    and _codigo(w + ws[i + 1]) and esta(w + ws[i + 1]):
                out.append(w + ws[i + 1])
                i += 2
                continue
            if _codigo(w) and not esta(w):
                cortes = [k for k in range(1, len(w)) if w[k - 1].isdigit() != w[k].isdigit()]
                partes = next(([w[:k], w[k:]] for k in cortes if w[:k] in R["tokens"] and w[k:] in R["tokens"]), None)
                if partes:
                    out.extend(partes)
                    i += 1
                    continue
            out.append(w)
            i += 1
        return out

    @staticmethod
    def _solo(prods, modelos):
        return [p for p in prods if p["modelo"] in modelos]

    def _sufijo(self, v, ids, color, prods, R):
        """Un numero dicho elige el modelo donde ese numero termina: el sufijo que el cliente no dijo, "Ti" o "Super", es
        otro modelo, si hay alguno sin sufijo. "rtx 4060" no trae las 4060 Ti; "rtx 4070" no trae las 4070 Super."""
        if v["veredicto"] != "ambiguous":
            return v
        # Solo numeros puros, los de generacion: "ddr5" o "32gb" son medidas y el sufijo de un DDR5 es su velocidad.
        numeros = {w for w in ids if w.isdigit()}

        def con_sufijo(m):
            t = R["modelos"][m]
            return any(x in numeros and k + 1 < len(t) and t[k + 1] not in ids for k, x in enumerate(t))
        ms = [o["modelo"] for o in v["opciones"]]
        sin = [m for m in ms if not con_sufijo(m)]
        if not sin or len(sin) == len(ms) or not any(x in numeros for m in sin for x in R["modelos"][m]):
            return v
        from app.core.flujo.catalogo import _identificar
        return _identificar(" ".join(ids), color, self._solo(prods, sin))

    def _numero_suelto(self, v, ids, color, prods, R):
        """Un numero suelto que calza de casualidad no elige: si el modelo hallado lleva un nombre que el cliente no dijo
        y sin ese numero calzan otros, es ambiguo y se pregunta. "hyperx cloud 2" no es el Cloud Stinger 2: el Cloud II
        se escribe con romanos."""
        if v["veredicto"] != "exists":
            return v
        # Suelto es el numero que coincide entero con una palabra del modelo, el "2" de Stinger 2; el que esta dentro de
        # un codigo, "13400" en "13400f", no.
        sueltos = [w for w in ids if w.isdigit() and w in R["modelos"][v["producto"]["modelo"]]]
        no_dicho = [x for x in R["modelos"][v["producto"]["modelo"]]
                    if x in R["nombres"] and x not in ids and not any(w in x for w in sueltos)]
        if not sueltos or not no_dicho:
            return v
        from app.core.flujo.catalogo import _identificar
        sin = _identificar(" ".join(w for w in ids if w not in sueltos), color, prods)
        if sin["veredicto"] != "ambiguous":
            return v
        # Si los otros modelos de la familia llevan otro numero, el del cliente elige de verdad: "rtx 4070" es la 4070,
        # no cualquier RTX. En la familia Cloud los otros no llevan numero, y ahi el 2 calzo de casualidad.
        otros = [o["modelo"] for o in sin["opciones"] if o["modelo"] != v["producto"]["modelo"]]
        return v if any(x.isdigit() for m in otros for x in R["modelos"][m]) else sin

    def _nombra(self, busqueda, rubro):
        """Cuantas palabras de la busqueda nombran algo de ese rubro: marca, nombre de modelo o codigo de su catalogo."""
        R = self.rub[rubro]
        ws = self._acomodar([w for w in NR.n(busqueda).split() if w not in self.vacias], R)
        return sum(w in R["marcas"] or w in R["nombres"] or (_codigo(w) and any(w in t for t in R["tokens"])) for w in ws)

    def rubro(self, busqueda, elegido):
        """PIEZA 1, la mitad exacta: el rubro lo eligen los embeddings. Solo si no eligieron ninguno, lo propone la
        palabra exacta: el rubro donde la busqueda nombra un modelo y donde mas palabras suyas estan en los modelos.
        "lenovo legion 5 i7" no trae notebook entre los tres rubros de los embeddings; "legion" solo nombra notebooks."""
        if elegido:
            return elegido
        crudas = [w for w in NR.n(busqueda).split() if w not in self.vacias]
        cuenta = {}
        for r, R in self.rub.items():
            ws = self._acomodar(crudas, R)
            # Tiene que nombrar una marca del rubro, o traer un codigo exacto del rubro, ademas de un nombre o un codigo
            # del rubro: "repetidor wifi" no es una motherboard WiFi y "resma a4" no es un SSD A400; "g-305" y
            # "rtx4060" si dicen que son.
            exacto = any(_codigo(w) and w in R["tokens"] for w in ws) or any(_codigo(w) for w in crudas if w not in ws)
            nombra = any(w in R["nombres"] or (_codigo(w) and w in R["tokens"]) for w in ws)
            if nombra and (exacto or any(w in R["marcas"] for w in ws)):
                cuenta[r] = sum(any(w in t for t in R["tokens"]) for w in ws)
        mejor = [r for r, k in cuenta.items() if k == max(cuenta.values())] if cuenta else []
        return mejor[0] if len(mejor) == 1 else None

    def nombrado(self, linea):
        """PIEZAS 1 A 3. None si el nexo no corre."""
        p = self.idx.producto({"busqueda": linea.busqueda, "fragmento": linea.fragmento})
        elegido = self.rubro(linea.busqueda, p["elegido"]["rubro"] if p["elegido"] else None)
        exacto = self.rubro(linea.busqueda, None)
        # La identidad la decide la palabra exacta, regla 7.0: si otro rubro nombra mas palabras de la busqueda, con
        # marca o codigo exacto, gana ese. Los embeddings desempatan. Medido el 16-nov: con el indice calibrado,
        # "jbl tune 520" caia en parlantes y "hyperx cloud 2" en microfonos.
        rubro = exacto if exacto and (not elegido or self._nombra(linea.busqueda, exacto)
                                      > self._nombra(linea.busqueda, elegido)) else elegido
        ids = self.palabras(linea.busqueda, rubro) if rubro else []
        if not ids:
            return None
        from app.core.flujo.catalogo import _identificar
        R = self.rub[rubro]
        color = next((c for c in R["colores"] if c and c in NR.n(linea.busqueda).split()), "")
        prods = [dict(f, stock=int(f["stock"] or 0)) for f in self.por_rubro[rubro]]
        v = _identificar(" ".join(ids), color, prods)
        v = self._sufijo(v, ids, color, prods, R)
        v = self._numero_suelto(v, ids, color, prods, R)
        if v["veredicto"] == "exists":
            modelos, prod = [v["producto"]["modelo"]], v["producto"]
        elif v["veredicto"] == "ambiguous":
            modelos, prod = [o["modelo"] for o in v["opciones"]], None
        else:
            modelos, prod = [], None
        # Si ninguna palabra es marca, nombre o codigo de este rubro, nombra otra cosa: "motherboard compatible procesador
        # intel" no pide una motherboard Intel. El not_found vale, pero no es un "no lo tengo": lo contestan el de
        # producto y el de condicion.
        de_otro = not any(w in R["marcas"] or w in R["nombres"] or (_codigo(w) and any(w in t for t in R["tokens"]))
                          for w in ids)
        return {"busqueda": linea.busqueda, "rubro": rubro, "palabras": ids, "color": color, "de_otro_rubro": de_otro,
                "veredicto": v["veredicto"], "modelos": modelos, "producto": prod and {
                    "id": prod["id"], "nombre": prod["nombre"], "precio": int(float(prod["precio_ars"])),
                    "stock": int(prod["stock"])}}


def indice():
    """El indice del flujo nuevo con los puntajes de las 140 y los del banco nuevo."""
    import flujo_nuevo as F
    idx = F.Indice()
    if os.path.exists(PUNTAJES):
        idx.q = dict(idx.q, **json.load(open(PUNTAJES, encoding="utf-8"))["consultas"])
    return idx


# ══ LA VARA ══════════════════════════════════════════════════════════════════
def calificar(ver=False):
    import flujo_nuevo as F
    from nombrados38 import CASOS
    NR.instalar()
    idx = indice()
    nx = Nexo(idx)
    print("\nEL NEXO DE PRODUCTO NOMBRADO · el rubro por embeddings, la identidad por palabra exacta")
    l38 = llamada0()
    cosas38 = []
    for cid, texto, cs in CASOS:
        ls = l38.get(("nombrados38", cid), [])
        usadas = set()
        for raiz, rubro, ver_, mods in cs:
            k = next((j for j, l in enumerate(ls) if j not in usadas and NR.n(raiz) in NR.n(l.busqueda + " " + l.fragmento)),
                     None)
            if k is not None:
                usadas.add(k)
            cosas38.append((cid, texto, ls[k] if k is not None else None, rubro, ver_, mods))
    l140 = F.llamada0()
    cosas140 = []
    for banco, cid, q, ver_, mods in ESPERADO_140:
        l = next((x for x in l140.get((banco, cid), []) if x.busqueda == q), None)
        cosas140.append((cid, q, l, None, ver_, mods))
    for nombre, cosas in (("nombrados38", cosas38), ("las 140", cosas140)):
        c, fallas = collections.Counter(), []
        for cid, texto, l, rubro, ver_, mods in cosas:
            c["cosas"] += 1
            if l is None:
                c["sin linea"] += 1
                fallas.append((cid, texto, ver_, mods, "sin linea de la llamada 0"))
                continue
            r = nx.nombrado(l)
            dio = ("no aplica", set()) if r is None else (r["veredicto"], set(r["modelos"]))
            bien = dio[0] == ver_ and dio[1] == mods
            c["bien"] += bien
            c["exists con otro modelo"] += dio[0] == "exists" and not dio[1] <= mods
            if ver_ == "not_found":
                c["not_found pedidos"] += 1
                c["not_found bien"] += dio[0] == "not_found"
            if ver_ == "no aplica":
                c["no aplica pedidos"] += 1
                c["no aplica bien"] += dio[0] == "no aplica"
            if not bien or ver:
                fallas.append((cid, l.busqueda, ver_, mods, f"{'bien' if bien else 'MAL'}: " + (
                    "no corre" if r is None else
                    f"{r['rubro']} {r['palabras']} {r['color'] or ''} -> {r['veredicto']} {sorted(r['modelos'])[:6]}"
                    + (f" ... {len(r['modelos'])}" if len(r["modelos"]) > 6 else "")
                    + (f" · {r['producto']['nombre']}" if r["producto"] else ""))))
        print(f"\n  {nombre}: {c['cosas']} cosas · bien {c['bien']} · exists con otro modelo {c['exists con otro modelo']} · "
              f"not_found {c['not_found bien']} de {c['not_found pedidos']} · no aplica {c['no aplica bien']} de "
              f"{c['no aplica pedidos']} · sin linea {c['sin linea']}")
        for cid, q, ver_, mods, dio in fallas:
            print(f"    {cid} '{q}': espera {ver_} {sorted(mods)[:3]}{' ...' if len(mods) > 3 else ''} · {dio}")
    # Las lineas de las 140 donde el nexo corre fuera de la vara.
    en_vara = {(b, cid, q) for b, cid, q, _, _ in ESPERADO_140}
    otras = collections.Counter()
    for (banco, cid), ls in l140.items():
        for l in ls:
            if l.busqueda and (banco, cid, l.busqueda) not in en_vara:
                r = nx.nombrado(l)
                if r:
                    otras[f"{l.busqueda} -> {r['palabras']} {r['veredicto']} {len(r['modelos'])}"] += 1
    print(f"\n  en las 140, fuera de la vara, el nexo corre en {sum(otras.values())} lineas:")
    for k, v in sorted(otras.items()):
        print(f"    {k}" + (f" · {v} veces" if v > 1 else ""))


def sonda():
    import flujo_nuevo as F
    NR.instalar()
    nx = Nexo(indice())
    print("\nLA SONDA DEL NEXO NOMBRADO · variantes de escritura, no es vara")
    for q, deberia in SONDA:
        r = nx.nombrado(F.Linea("", q, ""))
        dio = "no corre" if r is None else f"{r['veredicto']} {sorted(r['modelos'])[:4]}" + (
            f" ... {len(r['modelos'])}" if len(r["modelos"]) > 4 else "")
        print(f"  '{q}': deberia {deberia} · da {dio}" + (f" · {r['rubro']} {r['palabras']}" if r else ""))


if __name__ == "__main__":
    if "--sonda" in sys.argv:
        sonda()
    elif "--llamada0" in sys.argv:
        correr_llamada0()
    elif "--embeddings" in sys.argv:
        embeddings()
    else:
        calificar("--ver" in sys.argv)
