"""COMO RESPONDE EL CODIGO CON CADA LINEA — de las lineas grabadas a la respuesta, sin modelo de texto (28-oct-2026, FICHA 83).

Paso 2 de "Lo que sigue" de la FICHA 83. Toma las lineas que el modelo separo con cosa y tema, `momento0_cosa_tema.jsonl`,
en los primeros mensajes de las 58 y las complejas, y las lleva hasta lo que recibe el cliente:

  candidatos  cada linea busca en un solo indice de la tienda —rubros con sus alias, temas y productos— con las palabras
              del cliente y con la cosa, embeddings con tipo de tarea, las dos sumadas. Lo mejor medido en la FICHA 83.
  la duda     la linea se marca si la busqueda con las palabras y la de la cosa no eligen lo mismo: la regla medida el
              28-oct sobre las 238 frases, que caza 30 de los 37 errores.
  la salida   el codigo arma con cada linea una parte de la lectura viva, `lectura.py`: que hace y sobre que salen del
              candidato y de las casillas de la linea, sin modelo. Despues `lectura.a_agenda`, el ejecutor y la redaccion
              de siempre, por el webhook entero de `cableado58.py`.
  la vara     las casillas del primer turno de `vara_58.json`, que no se tocan. Se compara con la agenda a mano, que es el
              techo del codigo, y con la lectura grabada de hoy, `primera_ejes/sueltos_rep0.jsonl`.

    python3 banco_pruebas/responder_lineas.py [--ver] [C27 K20 ...]      embeddings con la clave gratis
    python3 banco_pruebas/responder_lineas.py --grabar                    fuera de muestra: separa y lee, con la gratis
    python3 banco_pruebas/responder_lineas.py --nuevas [--ver]            fuera de muestra, sin modelo de texto
"""
import collections
import json
import os
import re
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
ARGS, sys.argv = sys.argv[1:], [sys.argv[0]]
sys.path.insert(0, AQUI)
sys.path.insert(0, REPO)
import embeddings_primera as EP  # noqa: E402  — prepara el clon y la vara
import buscar_mejoras as BM  # noqa: E402
from banco_pruebas import cableado58 as C58  # noqa: E402
from app.core.flujo import catalogo as K  # noqa: E402
from app.core.flujo import estado as E  # noqa: E402
from app.core.flujo import ficha as F  # noqa: E402
from app.core.flujo import interprete  # noqa: E402
from app.core.flujo import lectura as L  # noqa: E402

P = EP.P
TID = P.TID
VER = "--ver" in ARGS
SOLO = [a for a in ARGS if not a.startswith("--")]

# Los embeddings con la clave gratis, guardados aparte: lo de `buscar_mejoras.py` se lee, no se reescribe.
# Con la gratis agotada, la paga por orden de Martin: MARTIN_AUTORIZO_LA_PAGA=<fecha>, y la tanda va al libro.
PAGA = bool(os.environ.get("MARTIN_AUTORIZO_LA_PAGA") and os.environ.get("GEMINI_API_KEY_PROD"))
BM.PAGA = (os.environ.get("GEMINI_API_KEY_PROD") if PAGA else os.environ.get("GEMINI_API_KEY")) or ""
BM.CACHE, _VIEJO = os.path.join(AQUI, "responder_lineas_emb.npz"), BM.CACHE
for _c in (_VIEJO, BM.CACHE):
    if os.path.exists(_c):
        z = np.load(_c, allow_pickle=False)
        BM._VEC.update(zip(z["claves"].tolist(), z["vectores"].astype(np.float32)))
_nativo = BM.nativo


def _con_espera(textos, tarea):
    """La gratis corta con 429 por minuto: se espera y se reintenta. Con la paga, cada tanda nueva va al libro."""
    import time
    faltan = [t for t in dict.fromkeys(textos) if f"{tarea}|{t}" not in BM._VEC]
    if PAGA and faltan:
        import datetime
        ahora = datetime.datetime.now()
        with open(os.path.join(AQUI, "libro_paga.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"dia": ahora.strftime("%Y-%m-%d"), "hora": ahora.strftime("%H:%M:%S"),
                                 "modelo": "gemini-embedding-001", "entrada": sum(len(t) for t in faltan) // 4,
                                 "salida": 0, "dolares": 0.0, "proceso": os.getpid()}) + "\n")
    for intento in range(6):
        try:
            return _nativo(textos, tarea)
        except Exception as e:  # noqa: BLE001
            if "429" not in str(e) or intento == 5:
                raise
            time.sleep(30 * (intento + 1))


BM.nativo = _con_espera

_PREGUNTA = re.compile(r"\?|^(cuanto|cual|cuales|que|tenes|tienen|hay|queda|anda|sirve|es |son |viene|trae|como|donde|"
                       r"hacen|aceptan|puedo|se puede)")
_STOCK = re.compile(r"\b(tenes|tienen|hay|stock|queda|quedan|disponible)\b")
_ENVIO = {"envio", "envios", "el envio", "costo de envio", "flete"}
_TOTAL = re.compile(r"\b(todo|total|en total|presupuesto|cuanto (me )?(sale|queda|seria))\b")
_NO_SEA = re.compile(r"\bque no (?:sea|sean)\s+(?:de\s+)?(?:marca\s+)?([a-z0-9]+(?:\s+[a-z0-9]+)?)")
_MEDIOS = ("transferencia", "efectivo", "mercado pago", "mercadopago", "visa", "mastercard", "tarjeta", "debito",
           "credito", "cripto", "cuotas")
_PRECIO = re.compile(r"\b(cuanto|precio|sale|cuesta|vale)\b")
_COMPRA = re.compile(r"\b(llevo|me llevo|anotame|anota|compro|comprar|pedido|mandame|mandar|reservame|separame)\b")
# Lo que no dice nada del producto: pedir, preguntar, cantidades. El resto de la linea es la condicion o lo que quiere
# saber, en palabras del cliente, y el ejecutor lo ata a los campos del catalogo.
_NO_DICE = set("quiero necesito busco tenes tienen hay me le se mi su es son sirve sirven cual cuales cuanto sale "
               "cuesta vale conviene mostrame pasame decime algun alguna no si tiene trae viene esta estan "
               "llevo anotame compro".split())


def _resto(t: str, quitar: str) -> str:
    fuera = set(K.n(quitar).split()) | K._RELLENO | _NO_DICE
    ws = [w for w in re.findall(r"[a-z0-9]+", t) if w not in fuera and not w.isdigit()]
    return " ".join(ws)


_DECENAS = {"diez": 10, "veinte": 20, "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70,
            "ochenta": 80, "noventa": 90}
_DEL_TOTAL = re.compile(r"\b(total|todo|pasa|pasar|supera|superar)\b")
_TOPE = re.compile(r"\b(no (me )?quiero pasar|pasar de|pasa de|tope|hasta|maximo|como mucho|no mas de|presupuesto de)\b")


# ══ LOS CANDIDATOS DE CADA LINEA ═════════════════════════════════════════════

class Indice:
    def __init__(self):
        self.base = BM.indice(False)
        self.vb = BM.nativo([b for b, _ in self.base], "RETRIEVAL_DOCUMENT")
        self.claves = sorted(set(k for _, k in self.base))
        self.idx = collections.defaultdict(list)
        for i, (_, k) in enumerate(self.base):
            self.idx[k].append(i)

    def preparar(self, textos: list) -> None:
        textos = [t for t in dict.fromkeys(textos) if t]
        self.vq = dict(zip(textos, BM.nativo(textos, "RETRIEVAL_QUERY"))) if textos else {}

    def candidatos(self, frase: str, cosa: str, tipos=("rubro", "producto")) -> tuple:
        """([(clave, puntaje)] los tres primeros, duda): la frase del cliente y la cosa, sumadas."""
        def por(t):
            if not t or t not in self.vq:
                return {k: 0.0 for k in self.claves}
            s = self.vb @ self.vq[t]
            return {k: float(max(s[i] for i in ii)) for k, ii in self.idx.items()}
        a, b = por(frase), por(cosa)
        ks = [k for k in self.claves if k[0] in tipos]
        suma = {k: a[k] + b[k] for k in ks}
        orden = sorted(ks, key=lambda k: -suma[k])[:3]
        duda = bool(cosa) and max(ks, key=a.get) != max(ks, key=b.get)
        return [(k, round(suma[k], 3)) for k in orden], duda


# ══ DE LAS LINEAS A LA LECTURA VIVA ══════════════════════════════════════════

def _es_pregunta(t: str) -> bool:
    return bool(_PREGUNTA.search(t))


def _color(t: str) -> str:
    L._definir({"variante": "x"}, TID)  # llena los colores de la tienda
    return next((c for c in L._COLORES[TID] if c and re.search(rf"\b{re.escape(c)}s?\b", t)), "")


def _cosa_del_catalogo(x: dict, ind: Indice) -> tuple:
    """(sobre, que, rubro, candidatos, duda): un modelo que la tienda certifica por lo que dijo el cliente, o el rubro del
    primer candidato. El modelo de lenguaje no elige productos: un producto de los candidatos que el cliente no nombro
    vale por su rubro."""
    cosa, texto = str(x.get("cosa") or ""), str(x.get("texto") or "")
    for t in (cosa, texto):
        if t and (F._es_modelo(t, "", TID) or F._nombra_varios(t, TID)):
            return "producto", t, "", [], False
    cands, duda = ind.candidatos(texto, cosa)
    if not cands:
        return "rubro", cosa, "", cands, duda
    (tipo, nombre), _ = cands[0]
    if tipo == "producto":
        idt = K.identificar(nombre, "", TID)
        rub = (idt.get("producto") or {}).get("categoria") or ""
        return "rubro", rub, rub if rub in F._rubros_de(TID) else "", cands, duda
    return "rubro", nombre, nombre, cands, duda


CLASES = {"dato": "pregunta precio, stock o un dato de un producto",
          "ver": "quiere ver opciones de una clase de producto, o de toda la tienda",
          "compra": "lo compra o lo agrega al pedido",
          "cambia": "cambia algo de lo que ya esta en el pedido",
          "saca": "saca algo del pedido",
          "confirma": "dice que si a lo que tiene el pedido",
          "total": "pregunta el total o el presupuesto",
          "envio": "pregunta lo que sale o tarda el envio a un lugar",
          "regla": "pregunta una regla de la tienda: pago, garantia, factura, horarios",
          "no_vende": "pide una clase de producto que la tienda no vende",
          "general": "pregunta de tecnologia en general, no de la tienda",
          "contesta": "contesta lo que le pregunto el vendedor",
          "charla": "saludo, agradecimiento o un dato suyo"}


def _clase(p: dict, k: str, ref: str, x: dict, ind, temas: set) -> tuple:
    """LO QUE HACE LA LINEA LO DICE EL MODELO, de una lista corta; los datos los pone el codigo: la cantidad, el destino,
    el color, el orden y la condicion de la linea, la identidad por el catalogo y el rubro por los embeddings. Devuelve
    (candidatos, duda) de la busqueda, si busco."""
    texto, cosa, tema = str(x.get("texto") or ""), str(x.get("cosa") or ""), str(x.get("tema") or "")
    t = K.n(texto)
    refs = re.findall(r"\b[ML]-\d+\b", f"{ref} {cosa}")
    cands, duda, sobre, que, rub = [], False, "rubro", cosa, ""
    if cosa and not refs and k in ("dato", "ver", "compra"):
        sobre, que, rub, cands, duda = _cosa_del_catalogo(x, ind)
    resto = _resto(t, f"{que} {p.get('destino') or ''}")
    conds = [c] if (c := _atable(resto, rub)) else []
    if k == "dato":
        if refs:
            p.update(hace="pregunta", sobre="mostrado" if refs[0][0] == "M" else "producto", que=refs[0])
        elif sobre == "producto":
            p.update(hace="pregunta", sobre="producto", que=que)
        else:
            p.update(hace="pide_ver", sobre="rubro", que=que, rubro=rub, condiciones=conds)
            return cands, duda
        p["quiere_saber"] = "precio" if _PRECIO.search(t) else "stock" if _STOCK.search(t) else resto
    elif k == "ver":
        p.update(hace="pide_ver", sobre="mostrado" if refs else "rubro", que=refs[0] if refs else
                 (que or f"toda la tienda {p['orden']}"), rubro=rub, condiciones=conds)
    elif k == "compra":
        p.update(hace="elige", sobre="mostrado" if refs and refs[0][0] == "M" else sobre,
                 que=refs[0] if refs else que, rubro=rub, condiciones=conds, cantidad=p.get("cantidad") or 1)
    elif k in ("cambia", "saca"):
        p.update(hace=k, sobre="pedido", que=refs[0] if refs else cosa)
    elif k == "confirma":
        p.update(hace="elige", sobre="pedido", que=" ".join(refs))
    elif k == "total":
        p.update(hace="pregunta", sobre="pedido", que="total")
    elif k == "envio":
        p.update(hace="pregunta", sobre="lugar", que=p.get("destino") or texto, tema="costo_envio")
    elif k == "regla":
        if tema not in temas:
            (tipo, tema), _ = (ind.candidatos(texto, cosa or texto, tipos=("tema",))[0] or [(("tema", ""), 0)])[0]
        p.update(hace="pregunta", sobre="tema", que=tema, tema=tema)
    elif k == "no_vende":
        # LO QUE NO VENDE se busca por la clase sola, sin la marca: "celulares samsung" ataria la marca a un monitor.
        p.update(hace="pide_ver", sobre="rubro", que=(cosa or texto).split()[0], rubro="")
    elif k == "general":
        p.update(hace="pregunta", sobre="tecnologia", que=texto)
    else:
        p.update(hace="nada", sobre="nada", que=texto)
    return cands, duda


def a_salida(lineas: list, todo: str, ind: Indice, clases: list = None) -> tuple:
    """La salida de la lectura viva, armada por el codigo con cada linea, y lo que vio de cada una. Con `clases`, lo que
    hace cada linea lo dijo el modelo: [(clase, a que senala)]."""
    partes, vistas, con_si, tope_de_si, responde = [], [], set(), None, ""
    temas = set(F._temas_de(TID))
    tn = K.n(todo)
    for i, x in enumerate(lineas, 1):
        texto, cosa, tema = str(x.get("texto") or ""), str(x.get("cosa") or ""), str(x.get("tema") or "")
        t = K.n(texto)
        cant, dest, si = K.entero(x.get("cantidad")) or None, str(x.get("destino") or ""), str(x.get("si") or "")
        p = {"cliente": texto, "cantidad": cant, "destino": dest, "variante": _color(t),
             "orden": L._orden_de(t, TID) or L._orden_de(tn, TID) or "nada",
             "no_quiere": [m.group(1) for m in _NO_SEA.finditer(t)], "condiciones": [], "prefiere": []}
        cands, duda = [], False
        k, ref = clases[i - 1] if clases and i <= len(clases) else ("", "")
        if k == "contesta" and re.match(r"^R-\d+$", ref or ""):
            responde = ref
        if k and k in CLASES and k != "contesta":
            cands, duda = _clase(p, k, ref, x, ind, temas)
        elif K.n(cosa) in _ENVIO or (tema in ("costo_envio", "envios") and not (cosa and cant and dest)):
            # Con la cosa, la cantidad y el destino, "envio de 2 notebooks a La Plata" es el reparto del pedido.
            p.update(hace="pregunta", sobre="lugar" if dest or L._lugares(texto) else "tema", que=dest or texto,
                     tema=tema if tema in temas else "costo_envio")
        elif not cosa and tema in temas and not _es_pregunta(t) and any(y.get("cosa") for y in lineas):
            # LO QUE PIDE QUE TENGAN LOS PRODUCTOS —"que lleven las menos partes chinas"— no es una regla de la tienda:
            # es una condicion de todo lo que pide, si el catalogo la ata a un campo.
            p.update(hace="nada", sobre="nada", que="", para_todo=texto)
        elif not cosa and tema in temas and not L._orden_de(t, TID):
            p.update(hace="pregunta", sobre="tema", que=tema, tema=tema)
        elif not cosa and L._orden_de(t, TID):
            # "EL ARTICULO MAS CARO QUE VENDES": sin cosa y con un orden, es una busqueda en toda la tienda.
            p.update(hace="pide_ver", sobre="rubro", que=f"toda la tienda {p['orden']}", rubro="")
        elif not cosa and _TOTAL.search(t):
            p.update(hace="pregunta", sobre="pedido", que="total")
        elif not cosa:
            p.update(hace="nada", sobre="nada", que=texto)
        else:
            # LA LINEA QUE NOMBRA UN PRODUCTO O UN RUBRO es sobre eso: el tema que puso el modelo —stock,
            # especificaciones, asesoramiento— dice que quiere saber de el, no es una regla de la tienda.
            sobre, que, rub, cands, duda = _cosa_del_catalogo(x, ind)
            resto = _resto(t, f"{que} {dest}")
            conds = _atable(resto, rub)
            compra = bool(dest) or bool(cant) or bool(_COMPRA.search(t)) or (si and not _es_pregunta(t))
            if tema == "compatibilidad":
                m = re.search(r"\b(?:con|a|para|en)\s+(?:un|una|mi|el|la)?\s*([a-z0-9][a-z0-9 ]{1,40})", t)
                p.update(hace="pregunta", sobre="producto", que=que, rubro=rub, con=m.group(1).strip() if m else "")
            elif compra:
                p.update(hace="elige", sobre=sobre, que=que, rubro=rub, condiciones=[conds] if conds else [])
            elif sobre == "producto":
                p.update(hace="pregunta", sobre="producto", que=que,
                         quiere_saber="precio" if _PRECIO.search(t) else "stock" if _STOCK.search(t) else resto)
            else:
                p.update(hace="pide_ver", sobre="rubro", que=que, rubro=rub, condiciones=[conds] if conds else [])
        if si and L._monto_de(si) and _DEL_TOTAL.search(K.n(si)):
            # UN "SI" CON UN MONTO DEL TOTAL no es una condicion del producto: es el tope del pedido, que cuenta el codigo.
            tope_de_si, si = L._monto_de(si), ""
        if si:
            # LA CONDICION es la parte de antes que pregunta por lo que nombra el "si"; "no hay" o "si no" es su
            # contrario. Si ninguna lo pregunta —"si el K120 sale menos de 10 mil, llevo dos"—, la condicion es una
            # pregunta por la misma cosa, y el codigo la agrega.
            sn = set(K.n(si).split()) - K._RELLENO - _NO_DICE
            antes = [j for j in range(len(partes), 0, -1) if j not in con_si]
            dep = next((j for j in antes if partes[j - 1]["hace"] == "pregunta"
                        and set(K.n(partes[j - 1].get("que")).split()) & sn), 0)
            if not dep and p.get("sobre") in ("producto", "rubro"):
                partes.append({"cliente": si, "hace": "pregunta" if p["sobre"] == "producto" else "pide_ver",
                               "sobre": p["sobre"], "que": p.get("que"), "rubro": p.get("rubro"),
                               "variante": p.get("variante"), "quiere_saber": _resto(K.n(si), str(p.get("que") or "")),
                               "condiciones": [] if p["sobre"] == "producto" else [si]})
                dep = len(partes)
            dep = dep or (antes[0] if antes else 0)
            if dep:
                p.update(depende_de=dep, vale_si="no" if re.match(r"(si )?no\b", K.n(si)) else "si")
                con_si.add(len(partes) + 1)
        partes.append(p)
        vistas.append({"texto": texto, "cosa": cosa, "tema": tema, "hace": p["hace"], "sobre": p["sobre"],
                       "que": p.get("que"), "candidatos": cands, "duda": duda})
    partes = _sin_totales(partes)
    para_todo = [p.pop("para_todo") for p in partes if p.get("para_todo")]
    partes = [p for p in partes if p["hace"] != "nada" or not p.get("cliente") in para_todo]
    for p in partes:
        if p["hace"] in ("elige", "pide_ver") and p["sobre"] in ("producto", "rubro"):
            p["condiciones"] = list(p.get("condiciones") or []) + para_todo
    for palabra, num in _DECENAS.items():
        tn = re.sub(rf"\b{palabra}\b", str(num), tn)
    pago = []
    for m in re.finditer(r"(\d{1,3})\s*%?\s*(?:por ciento\s*)?(?:en|por|con)?\s*(" + "|".join(_MEDIOS) + ")", tn):
        pago.append({"medio": m.group(2), "porcentaje": int(m.group(1))})
    if not pago and re.search(r"\bmitad\b", tn):
        ms = [md for md in _MEDIOS if md in tn]
        pago = [{"medio": md, "porcentaje": 50} for md in ms[:2]] or [{"medio": "sin decir", "porcentaje": 50}] * 2
    if not pago and len(ms := [md for md in _MEDIOS if re.search(rf"\b{md}\b", tn)]) == 1:
        pago = [{"medio": ms[0], "porcentaje": 100}]
    if not pago and (m := re.search(r"\b(\d{1,3})\s*(?:y|/|-)?\s*(\d{1,3})\b", tn)) and int(m.group(1)) + int(m.group(2)) == 100:
        pago = [{"medio": "sin decir", "porcentaje": int(m.group(1))}, {"medio": "sin decir", "porcentaje": int(m.group(2))}]
    # "SI PASA DE 300 MIL SACA EL MX": lo que sale si el total pasa el tope, como lo lee la lectura viva.
    if (m := re.search(r"\bsac(?:a|as|ame|alo)\s+(?:el|la|los|las)?\s*([a-z0-9][a-z0-9 ]*)", tn)) and L._monto_de(todo):
        partes.append({"cliente": todo, "hace": "saca", "sobre": "producto", "que": m.group(1).strip(),
                       "si_cumple": todo})
    todo_ = {"orden": L._orden_de(tn, TID) or "nada",
             "tope_total": L._monto_de(todo) if _TOPE.search(tn) else tope_de_si,
             "pago": pago, "son": None, "rehace": False, "responde": responde, "cliente": {}}
    return {"partes": partes, "todo": todo_}, vistas


# ══ FUERA DE MUESTRA ══════════════════════════════════════════════════════════
# El puente se escribio mirando las 65 de arriba. El control: los primeros mensajes de las K y las J de la vara que no
# estan en la bateria, que el puente nunca vio. Se separan con la consigna de cosa y tema, y se leen con la lectura viva
# de hoy, las dos con la clave gratis; despues corren sin modelo como las 65.

NUEVAS = os.path.join(AQUI, "responder_lineas_nuevas.jsonl")


def _fuera_de_muestra(vara: dict) -> list:
    return [c for c in vara.values() if c["id"][0] in "JK" and c["id"] not in C58.COMPLEJAS]


async def grabar() -> None:
    import asyncio
    import momento0 as M0
    vara = {c["id"]: c for c in json.load(open(os.path.join(AQUI, "vara_58.json"), encoding="utf-8"))["charlas"]}
    consigna = M0.consigna_tema(", ".join(F._temas_de(TID)))
    sem = asyncio.Semaphore(2)
    vacio = E.leer({})

    async def pedir(msgs, formato):
        async with sem:
            for intento in range(6):
                try:
                    return interprete._json(await interprete._pedir(msgs, "responder_lineas", formato))
                except Exception as e:  # noqa: BLE001 — la gratis se traba: se espera y se reintenta
                    if intento == 5:
                        return {"error": f"{type(e).__name__}: {str(e)[:100]}"}
                    await asyncio.sleep(20 * (intento + 1))

    async def uno(c):
        msg = c["turnos"][0]["texto"]
        lineas = await pedir([{"role": "system", "content": consigna},
                              {"role": "user", "content": f"MENSAJE DEL CLIENTE: {msg}"}], M0.formato_tema())
        hoy = await pedir(L.mensajes(msg, [], vacio, TID), L.formato(TID))
        if "error" not in hoy:
            hoy, _ = await L.releer(msg, [], vacio, hoy, TID, interprete._pedir, "responder_lineas")
        return {"id": c["id"], "mensaje": msg, "lineas": lineas, "hoy": hoy}

    filas = await asyncio.gather(*[uno(c) for c in _fuera_de_muestra(vara)])
    with open(NUEVAS, "w", encoding="utf-8") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    print(f"grabadas {len(filas)}, con error {sum('error' in f['lineas'] or 'error' in f['hoy'] for f in filas)}")


def _atable(cond: str, rubro: str) -> str:
    """El resto de la linea es condicion solo si el catalogo lo ata a un campo o a un tope del rubro: "inalambrico",
    "jbl", "64 gb". Lo que no ata —"dame precio", "envio"— no es algo que el producto tenga."""
    if not cond:
        return ""
    universo = [p for p in K.productos(TID) if not rubro or p.get("categoria") == rubro]
    f = K.atar(cond, universo, TID)
    return cond if "campo" in f or "tope" in f else ""


def _sin_totales(partes: list) -> list:
    """EL TOTAL Y SU REPARTO: "dame precio de 2 auriculares" y despues "1 auricular a Cordoba", "1 a Posadas" son la
    misma compra dicha dos veces. Una linea sin destino cuya cantidad es la suma de las de la misma cosa con destino
    sale, y sus condiciones pasan al reparto. Lo que depende de otra parte se renumera."""
    fuera = set()
    for i, p in enumerate(partes):
        if p["hace"] != "elige" or p.get("destino") or not p.get("cantidad"):
            continue
        reparto = [q for q in partes if q is not p and q["hace"] == "elige" and q.get("destino")
                   and K.n(q.get("que")) == K.n(p.get("que"))]
        if reparto and sum(K.entero(q.get("cantidad")) for q in reparto) == K.entero(p["cantidad"]):
            fuera.add(i + 1)
            for q in reparto:
                q["condiciones"] = list(dict.fromkeys(list(q.get("condiciones") or []) + list(p.get("condiciones") or [])))
    if not fuera:
        return partes
    nuevo = {j: j - sum(1 for f in fuera if f < j) for j in range(1, len(partes) + 1) if j not in fuera}
    out = []
    for j, p in enumerate(partes, 1):
        if j in fuera:
            continue
        if p.get("depende_de"):
            p["depende_de"] = nuevo.get(p["depende_de"])
        out.append(p)
    return out


# ══ LA CORRIDA ═══════════════════════════════════════════════════════════════

def main() -> None:
    from banco_pruebas.agendas58 import AGENDAS, EXPLICAR
    interp = C58.instalar()
    todos = list(P._turnos_sueltos())
    primeros = [t for t in todos if "vacia" in interprete.libreta(t[3], t[4], TID)]
    grab = [json.loads(x) for x in open(os.path.join(AQUI, "momento0_cosa_tema.jsonl"), encoding="utf-8")]
    s91 = [g["salida"] for g in grab if g["examen"] == "91"]
    hoy = {(r["fuente"], r["id"]): r.get("salida") for r in
           map(json.loads, open(os.path.join(AQUI, "primera_ejes", "sueltos_rep0.jsonl"), encoding="utf-8"))}
    vara = {c["id"]: c for c in json.load(open(os.path.join(AQUI, "vara_58.json"), encoding="utf-8"))["charlas"]}
    nuevas = "--nuevas" in ARGS
    if nuevas:
        gr = [json.loads(x) for x in open(NUEVAS, encoding="utf-8")]
        casos = [(g["id"], g["mensaje"], g["lineas"]) for g in gr if "error" not in g["lineas"] and "error" not in g["hoy"]
                 and (not SOLO or g["id"] in SOLO)]
        hoy = {("58", f"{g['id']} t0"): g["hoy"] for g in gr}
    else:
        casos = [(cid.split(" ")[0], msg, s) for (f, cid, msg, _, _), s in zip(primeros, s91)
                 if f == "58" and (not SOLO or cid.split(" ")[0] in SOLO)]
    ind = Indice()
    ind.preparar([str(x.get(k) or "") for _, _, s in casos for x in s.get("lineas") or [] for k in ("texto", "cosa")])
    nota = collections.Counter()
    filas = []
    for ch, msg, s in casos:
        charla = {"id": ch, "turnos": vara[ch]["turnos"][:1]}
        vacio = E.leer({})
        salida, vistas = a_salida(s.get("lineas") or [], str(s.get("todo") or ""), ind)
        agendas = {"a mano": AGENDAS[ch][0] if ch in AGENDAS else {"preguntas": []},
                   "lectura de hoy": L.a_agenda(hoy[("58", f"{ch} t0")], vacio, TID, msg),
                   "lineas": L.a_agenda(salida, E.leer({}), TID, msg)}
        fila = {"id": ch, "msg": msg, "vistas": vistas, "todo": s.get("todo")}
        for nombre, ag in agendas.items():
            t = C58.correr(charla, [ag], interp, EXPLICAR)[0]
            malas = [n for n, ok in t["casillas"] if ok is not True]
            nota[nombre] += not malas
            fila[nombre] = {"malas": malas, "respuesta": t["respuesta"], "agenda": ag}
        filas.append(fila)
    with open(os.path.join(AQUI, "responder_lineas_nuevas_corrida.jsonl" if nuevas else "responder_lineas_corrida.jsonl"), "w", encoding="utf-8") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False, default=str) + "\n")
    n = len(filas)
    print(f"\nCOMO RESPONDE EL CODIGO CON CADA LINEA · {n} primeros mensajes "
          f"{'fuera de muestra, las K y J que no estan en la bateria' if nuevas else 'de las 58 y las complejas'} · casillas del T1")
    for nombre in ("a mano", "lectura de hoy", "lineas"):
        print(f"  {nombre:15} {nota[nombre]} de {n}")
    ls = [v for f in filas for v in f["vistas"] if v["candidatos"]]
    dudosas = [f for f in filas if any(v["duda"] for v in f["vistas"])]
    print(f"  lineas con candidatos {len(ls)}, marcadas por la duda {sum(v['duda'] for v in ls)}")
    print(f"  charlas con alguna linea en duda {len(dudosas)}: las lineas mal en {sum(bool(f['lineas']['malas']) for f in dudosas)}"
          f" · sin duda, mal en {sum(bool(f['lineas']['malas']) for f in filas if f not in dudosas)} de {n - len(dudosas)}")
    for f in filas:
        if f["lineas"]["malas"] and (VER or SOLO):
            print(f"\n{f['id']} {f['msg'][:160]}")
            print(f"  a mano {'bien' if not f['a mano']['malas'] else 'MAL'} · hoy {'bien' if not f['lectura de hoy']['malas'] else 'MAL'}"
                  f" · lineas MAL: {'; '.join(f['lineas']['malas'])}")
            for v in f["vistas"]:
                print(f"   - {v['texto'][:70]} | cosa {v['cosa']} tema {v['tema']} -> {v['hace']}/{v['sobre']} {v['que']}"
                      f"{' DUDA' if v['duda'] else ''} {[(k[1], s) for k, s in v['candidatos']]}")
            print(f"   todo: {f['todo']}")
            print(f"   agenda: {json.dumps(f['lineas']['agenda']['preguntas'], ensure_ascii=False)[:500]}")
            print("   " + f["lineas"]["respuesta"][:500].replace("\n", "\n   "))
    if C58.LLAMADAS_AL_MODELO:
        print(f"ERROR: {len(C58.LLAMADAS_AL_MODELO)} intentos de llamar al modelo")


if __name__ == "__main__":
    if "--grabar" in ARGS:
        import asyncio
        asyncio.run(grabar())
    else:
        main()
