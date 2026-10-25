"""LA PRIMERA LLAMADA CON LOS DOS EJES Y LAS CASILLAS — el cambio de como el modelo le pide al codigo, medido (25-oct).

Plan con Martin del 25-oct. El modelo no elige la respuesta de la tienda: por cada parte del mensaje dice que hace el
cliente y sobre que, y llena las casillas de los datos. El codigo cruza los dos ejes con el indice de la tienda,
`vara_dato.cruce`, y arma la agenda que cumple el ejecutor de siempre. Es banco: no toca el camino vivo.

  la parte    las palabras del cliente primero; hace, sobre, que; y las casillas: cantidad, variante, destino,
              condiciones, lo que no quiere, lo que prefiere, orden, de que parte depende y con que resultado vale, lo
              que tiene que cumplir para llevarlo, con que tiene que andar, lo que quiere saber, por que lo cambia.
  lo de todo  el orden para todo, el tope del total, el pago, cuantos son, si rehace el pedido, lo que contesta y lo que
              dice de si.

LOS EJEMPLOS salen solo de la plantilla de venta, `plantilla_venta/llenar.py`, llenada con la fuente: ninguna frase de
las 48, las 58, los siete de produccion ni las 16 nuevas. Se arman una vez, `--ejemplos`, y quedan en
`primera_ejes_ejemplos.json`: la consigna queda fija y la corrida se puede repetir.

EL EXAMEN, que no se mira al calibrar:
  sueltos   cada turno con el estado de la vara: las 48 con su memoria escrita, las 58 con el estado del cableado a mano,
            y las 16 frases nuevas de `entrevista_datos.py` con su vara escrita antes de esta consigna.
  cadena    las 58 enteras y los siete de produccion, cada turno sobre el estado que dejo el anterior, por el webhook.

LAS VARAS, en tres niveles y contra la ficha nativa en las mismas condiciones:
  datos      `vara_dato.py`: los turnos con todos sus datos, cada dato, de que depende y lo que entra de mas.
  pedido     las 48 por `medir_pedido`: lo que queda en el bot, BIEN, DUDO o MAL SIN AVISAR.
  respuesta  las casillas de `vara_58.json` sobre lo que lee el cliente, sueltos y en cadena; y los siete de produccion.

EL CRITERIO, escrito antes de correr:
  1. Datos: las 58 con todos sus datos en 70 de 105 o mas, contra 65 de la ficha; las 48 en 24 o mas; de que depende
     en 10 de 16 o mas, contra 3; lo que entra de mas en 4 o menos, contra 14.
  2. Respuesta: las 58 sueltas y en cadena no peor que la ficha; las 48 con BIEN no menos que la ficha; los siete de
     produccion no menos que la ficha.
  3. Ninguna clase de falla empeora en mas de dos turnos.
  Si no se cumple, no entra, y se vuelve al objetivo: mejorar como el modelo le pasa al codigo la pregunta del cliente.

    python3 banco_pruebas/primera_ejes.py --ejemplos                     los ejemplos desde la plantilla, sin modelo
    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/primera_ejes.py --sueltos [--rep N]
    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/primera_ejes.py --cadena [--rep N] [--base]
    python3 banco_pruebas/primera_ejes.py --medir [--ver]                las varas sobre lo grabado, sin modelo
"""
import asyncio
import collections
import copy
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
sys.path.insert(0, REPO)
sys.path.insert(0, AQUI)
os.chdir(REPO)
ARGS = sys.argv[1:]
if os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
    os.environ["BANCO_CLAVE_PAGA"] = "true"  # la paga, solo con la marca de Martin
import vara_dato as V  # noqa: E402  — prepara el clon de produccion, la vara y el cliente del modelo
from app.core.flujo import catalogo as K  # noqa: E402
from app.core.flujo import interprete  # noqa: E402

TID = V.TID
REP = int(ARGS[ARGS.index("--rep") + 1]) if "--rep" in ARGS else 0
EJEMPLOS = os.path.join(AQUI, "primera_ejes_ejemplos.json")
SALIDAS = os.path.join(AQUI, "primera_ejes")
os.makedirs(SALIDAS, exist_ok=True)
NADA = "nada"
_TXT, _LISTA = {"type": "string"}, {"type": "array", "items": {"type": "string"}}
_ENTERO = {"type": ["integer", "null"]}

# ══ LA CONSIGNA ══════════════════════════════════════════════════════════════












# ══ LA LECTURA ES LA DEL APP: el banco la mide, no la copia ══════════════════
from app.core.flujo import lectura as L  # noqa: E402

CONSIGNA, FALTO = L.CONSIGNA, L.FALTO
_conds_de, _vacio = L._conds_de, L._vacio


def esquema() -> dict:
    return L.esquema(TID)


def formato() -> dict:
    return L.formato(TID)


def consigna() -> str:
    return L.consigna(TID)


def normalizar(salida: dict) -> tuple:
    return (dict(salida or {}), []) if "--crudo" in ARGS else L.normalizar(salida, TID)


def a_agenda(salida: dict, estado: dict, mensaje: str = "") -> dict:
    return L.a_agenda(salida, estado, TID, mensaje)


def frases(mensaje: str) -> list:
    return L.frases(mensaje)


def anclas(frase: str) -> list:
    return L.anclas(frase, TID)


def sin_cubrir(mensaje: str, salida: dict) -> list:
    return L.sin_cubrir(mensaje, salida, TID)


async def releer(mensaje: str, historial: list, estado: dict, salida: dict) -> tuple:
    return await L.releer(mensaje, historial, estado, salida, TID, interprete._pedir, "primera_ejes_releer")


def mensajes(mensaje: str, historial: list, estado: dict) -> list:
    """La consigna, con unos espacios por repeticion: la misma pregunta al modelo, sin la respuesta guardada."""
    return [{"role": "system", "content": consigna() + " " * REP},
            {"role": "user", "content": interprete.libreta(estado, historial, TID) + f"\nULTIMO MENSAJE: {mensaje}"}]


# ══ LOS EJEMPLOS, desde la plantilla de venta ════════════════════════════════

# Una o dos por clase de falla medida y las clases que mas aparecen; ninguna frase del examen.
CLASES_EJEMPLO = ["MO01a", "MO04a", "MO03a", "DE03a", "DU01a", "DU06a", "DU09a", "DU14a", "DU29a", "DE09a", "AP04a",
                  "DU21a", "DC02a", "DC05a", "DC13a", "AR05a", "AR06a", "AR09a", "AR10a", "AR15a", "AR17a", "CE02a",
                  "UN02a", "UN03a", "UN05a", "FU01a", "AR04a", "DC06a"]


def _vacio(v) -> bool:
    return v in (None, "", [], False, NADA, "ninguno")


def _conds_a_casillas(cs) -> dict:
    out = {"condiciones": [], "no_quiere": [], "prefiere": []}
    for c in [str(x) for x in V._lista(cs)]:
        m = re.match(r"^(?:que )?no (?:sea|sean)(?: de)? (.+)$", K.n(c))
        if m:
            out["no_quiere"].append(c[len(c) - len(m.group(1)):])
        elif K.n(c).startswith(("preferentemente", "preferiblemente", "ideal")):
            out["prefiere"].append(re.sub(r"^\w+\s+", "", c))
        else:
            out["condiciones"].append(c)
    return out


def partes_de_agenda(agenda) -> dict:
    """La salida que tiene que dar el modelo para una agenda a mano: la vara de los ejemplos."""
    ag = agenda if isinstance(agenda, dict) else {"preguntas": agenda}
    partes, todo, n_de = [], {}, {}

    def parte(p, hace, sobre, que="", **k):
        x = {"hace": hace, "sobre": sobre, "que": que, **{a: b for a, b in k.items() if not _vacio(b)}}
        if p.get("si"):
            x["depende_de"] = n_de.get(K.entero(p["si"].get("de")))
            x["vale_si"] = p["si"].get("da") or "si"
        partes.append(x)
        n_de.setdefault(K.entero(p.get("n"), len(partes)), len(partes))

    # Lo que busca y elige del mismo rubro es una sola parte: la que elige, con el criterio de la busqueda.
    elegidos = {K.solo_rubro(str(a.get("producto")), TID) for q in ag.get("preguntas") or [] if q.get("accion") ==
                "comprar" for a in V._lista(q.get("agrega")) if isinstance(a.get("producto"), str)} - {""}
    criterio = {q["rubro"]: q for q in ag.get("preguntas") or [] if q.get("accion") == "buscar"
                and q.get("rubro") in elegidos}
    for i, p in enumerate(ag.get("preguntas") or [], 1):
        p = {"n": i, **p}
        acc = p.get("accion")
        if acc == "buscar" and p.get("rubro") in criterio:
            # Si lo que pidio del rubro no es lo que reparte, la lista queda dicha: "dos mouse... y los otros".
            repartidos = sum(K.entero(a.get("cantidad"), 1) for q in ag.get("preguntas") or []
                             if q.get("accion") == "comprar" for a in V._lista(q.get("agrega"))
                             if K.solo_rubro(str(a.get("producto")), TID) == p["rubro"])
            if K.entero(p.get("cantidad"), 1) <= repartidos:
                continue
            parte(p, "pide_ver", "rubro", p["rubro"], rubro=p["rubro"], cantidad=K.entero(p.get("cantidad")))
            continue
        if acc == "buscar":
            parte(p, "pide_ver", "mostrado" if p.get("entre_lo_mostrado") else "rubro", p.get("rubro"),
                  rubro=p.get("rubro"), cantidad=K.entero(p.get("cantidad")) if K.entero(p.get("cantidad"), 1) > 1
                  else None, orden=p.get("orden"), **_conds_a_casillas(p.get("condiciones")))
        elif acc == "producto":
            parte(p, "pregunta", "producto", " y ".join(map(str, V._lista(p.get("producto")))),
                  quiere_saber=p.get("quiere_saber") if K.n(p.get("quiere_saber")) not in ("", "precio") else "",
                  variante=p.get("color"), afirma=p.get("afirma"))
        elif acc == "compatibilidad":
            parte(p, "pregunta", "producto", p.get("producto"), con=p.get("con"))
        elif acc == "envio":
            parte(p, "pregunta", "lugar", p.get("destino"))
        elif acc == "politica":
            parte(p, "pregunta", "tema", p.get("tema"), tema=p.get("tema"), afirma=p.get("afirma"))
        elif acc == "explicar":
            parte(p, "pregunta", "tecnologia", p.get("pregunta"))
        elif acc == "cuenta":
            if p.get("tope"):
                todo["tope_total"] = K.entero(p["tope"])
            if p.get("reparto"):
                todo["pago"] = [{"medio": r["medio"], "porcentaje": r["porcentaje"]} for r in p["reparto"]]
            if not p.get("tope") and not p.get("reparto"):
                parte(p, "pregunta", "pedido", "el total")
        elif acc == "otro":
            hace, sobre = V._OTRO.get(p.get("que"), ("nada", "nada"))
            if p.get("que") != "corrige":
                parte(p, hace, sobre, "")
        elif acc == "comprar":
            if p.get("reemplaza"):
                todo["rehace"] = True
            for a in V._lista(p.get("agrega")):
                v = a.get("producto")
                que = " y ".join(map(str, v)) if isinstance(v, list) else str(v)
                rub = K.solo_rubro(que, TID)
                crit = criterio.get(rub) or {}
                parte(p, "elige", "mostrado" if re.search(r"\bM-\d", que) else "rubro" if rub else "producto", que,
                      rubro=rub, cantidad=K.entero(a.get("cantidad")) if K.entero(a.get("cantidad"), 1) > 1 else None,
                      variante=a.get("color"), destino=a.get("destino"), si_cumple=a.get("si_cumple"),
                      orden=crit.get("orden"), **_conds_a_casillas(crit.get("condiciones")))
            for c in V._lista(p.get("cambia")):
                parte(p, "cambia", "pedido", c.get("es"), por=c.get("producto"), cantidad=c.get("cantidad"),
                      variante=c.get("color"), destino=c.get("destino"))
            for r in V._lista(p.get("saca")):
                parte(p, "saca", "pedido", r)
            for r in V._lista(p.get("confirma")) + V._lista(p.get("acepta")):
                parte(p, "elige", "pedido", r)
            if p.get("total"):
                todo["son"] = K.entero(p["total"])
            if p.get("reparto"):
                todo["pago"] = [{"medio": r["medio"], "porcentaje": r["porcentaje"]} for r in p["reparto"]]
    if ag.get("responde"):
        todo["responde"] = ag["responde"]
    if ag.get("cliente"):
        todo["cliente"] = {k: v for k, v in ag["cliente"].items() if v}
    return {"partes": partes, "todo": todo}


def armar_ejemplos() -> None:
    """Los ejemplos desde la plantilla. Despues se corrigen a mano en el archivo —las palabras del cliente de cada parte,
    lo que la agenda no dice, como "es estudiante"—, asi que no se pisa un archivo que ya existe."""
    if os.path.exists(EJEMPLOS) and "--pisar" not in ARGS:
        raise SystemExit(f"{EJEMPLOS} ya existe y esta corregido a mano: --pisar para rehacerlo")
    from banco_pruebas.plantilla_venta import llenar as LL
    LL.entorno()
    res = {c["id"]: c for c in LL.llenar()["casos"]}
    out = []
    for cid in CLASES_EJEMPLO:
        c = res.get(cid)
        if not c or not c.get("entra"):
            print(f"  {cid}: no entra, {c and c.get('motivo')}")
            continue
        frase = c["frases"][0]["texto"]
        salida = partes_de_agenda(c["agenda"])
        for p, cli in zip(salida["partes"], [frase] * len(salida["partes"])):
            p.setdefault("cliente", cli if len(salida["partes"]) == 1 else "")
        out.append({"clase": cid, "frase": frase, "libreta": c["libreta"], "salida": salida})
    json.dump(out, open(EJEMPLOS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(out)} ejemplos en {EJEMPLOS}")


# ══ DE LAS PARTES A LA AGENDA, sin modelo ════════════════════════════════════





# ══ LA FORMA NORMAL DE LAS PARTES: lo que quiere decir cada forma de la salida, sin leer el mensaje ════════════════
# Cada regla define una forma, no corrige un caso; se mide sobre lo grabado en las 48, las 58 y las 16 nuevas.



























async def interpretar(mensaje: str, historial: list, estado: dict, tienda_id: str = TID, trace_id: str = ""):
    """El reemplazo de `interprete.interpretar` para la cadena: la misma puerta, la consigna nueva."""
    try:
        crudo = await interprete._pedir(mensajes(mensaje, historial, estado), "primera_ejes", formato())
    except Exception as e:  # noqa: BLE001
        print("  sin respuesta del modelo:", type(e).__name__, str(e)[:120])
        return None
    salida = interprete._json(crudo)
    # LA SEGUNDA VUELTA: lo que la cobertura marca vuelve al modelo con su lectura.
    salida, releyo = await releer(mensaje, historial, estado, salida)
    GRABADO.append({"mensaje": mensaje, "salida": salida, "releyo": releyo})
    return a_agenda(salida, estado, mensaje)


GRABADO = []


# ══ LA SALIDA COMO COSAS, para la vara por dato ══════════════════════════════

_ACTO = {"buscar": "opciones", "producto": "dato", "compatibilidad": "compat", "envio": "envio", "politica": "regla",
         "explicar": "saber", "cuenta": "cuenta"}


def como_cosas(salida: dict, nums: dict) -> dict:
    salida, _ = normalizar(salida)
    cosas = []
    todo = (salida or {}).get("todo") or {}
    for p in V._lista((salida or {}).get("partes")):
        if not isinstance(p, dict):
            continue
        hace, sobre = p.get("hace") or NADA, p.get("sobre") or NADA
        acc = V.cruce(hace, sobre, con=bool(p.get("con")))
        acto = {"elige": "lleva", "cambia": "cambia", "saca": "saca", "de_si": "de_si"}.get(hace) \
            if acc in ("comprar", "otro") else _ACTO.get(acc, "nada")
        if acc == "producto" and len(re.split(r"\by\b|,", str(p.get("que") or ""))) > 1:
            acto = "comparar"
        if hace == "elige" and sobre == "pedido":
            acto = "lleva"
        texto = V._con_nombres(" ".join(str(p.get(k) or "") for k in ("que", "rubro", "tema", "cliente", "por")), nums)
        ref = next((f"L{m}" for m in re.findall(r"\bL-?(\d+)\b", str(p.get("que") or "")) if f"L-{m}" in nums), "")
        conds = _conds_de(p) + ([str(p["si_cumple"])] if p.get("si_cumple") else [])
        cosas.append({"acto": acto, "texto": V.n(texto), "ref": ref, "datos": {
            "cantidad": K.entero(p.get("cantidad"), 1), "color": V.n(p.get("variante")),
            "destino": V.n(p.get("destino") or (p.get("por") if hace == "cambia" else "")),
            "orden": V._orden(p.get("orden")), "condiciones": V.n(" ; ".join(conds + [str(p.get("quiere_saber") or ""),
                                                                                 str(p.get("con") or "")])),
            "depende": bool(K.entero(p.get("depende_de")) or p.get("si_cumple")), "pide": V.n(texto)}})
    cli = todo.get("cliente") if isinstance(todo.get("cliente"), dict) else {}
    if any(not _vacio(v) for v in cli.values()) and not any(c["acto"] == "de_si" for c in cosas):
        cosas.append({"acto": "de_si", "texto": V.n(" ".join(map(str, cli.values()))), "ref": "", "datos": {}})
    reparto = [[K.entero(m.get("porcentaje")), V.n(m.get("medio"))] for m in V._lista(todo.get("pago"))
               if isinstance(m, dict) and K.entero(m.get("porcentaje"))]
    return {"cosas": cosas, "todo": {"orden": V._orden(todo.get("orden")), "tope": K.entero(todo.get("tope_total")) or None,
                                     "reparto": [] if reparto == [[100, "sin decir"]] else reparto, "condiciones": ""},
            "crudo": salida}


# ══ LAS 16 NUEVAS, con su vara escrita antes de la consigna ══════════════════

def _estado_mem(mem: dict) -> tuple:
    from medir_pedido import estado_de
    return estado_de(mem)


def _id(nombre: str, color: str = "") -> str:
    return str(K.identificar(nombre, color, TID)["producto"]["id"])


def nuevas() -> list:
    """(id, mensaje, estado, historial, vara) de las 16 frases de la entrevista de los datos."""
    from entrevista_datos import FRASES, MEMORIA_A, MEMORIA_B
    c = V.cosa
    MOU, TEC = ["mouse", "raton"], ["teclado"]
    mem_a = {"M": [_id("G305", "negro"), _id("G203", "negro"), _id("Cobra M711", "negro")]}
    mem_b = {"M": [_id("K120", "negro"), _id("G305", "negro")],
             "L": [(2, "teclado", _id("K120", "negro"), "Rosario"), (1, "mouse", _id("G305", "negro"), "Rosario")],
             "R": ["¿Con qué medio pagás?"]}
    varas = [
        {"cosas": [c("lleva", TEC, excluye=[["redragon"]]), c("lleva", TEC, cantidad=2, orden="barato")], "todo": {}},
        {"cosas": [c("opciones", ["auricular"], condicion=[["bluetooth"], ["80"]]), c("opciones", MOU,
                   condicion=[["oficina"]])], "todo": {}},
        {"cosas": [c("lleva", ["parlante"], cantidad=2, destino="Mendoza"), c("lleva", ["parlante"], destino="San Luis")],
         "todo": {"reparto": [[50, "transferencia"], [50, "mercado"]]}},
        {"cosas": [c("dato", ["c920"]), c("lleva", ["c920"], depende=True), c("opciones", ["webcam"], depende=True,
                   condicion=[["1080"]])], "todo": {}},
        {"cosas": [c("lleva", ["monitor"]), c("lleva", TEC)], "todo": {"tope": 400000}},
        {"cosas": [c("opciones", MOU, excluye=[["logitech"]], condicion=[["inalambr"], ["livian", "peso"]])], "todo": {}},
        {"cosas": [c("lleva", ["memoria", "ram"], cantidad=2), c("lleva", ["ssd"]), c("lleva", ["cargador", "demas",
                   "otros"], cantidad=2)], "todo": {}},
        {"cosas": [c("dato", ["g502"], que_pide=["4", "cuatro", "stock"]), c("lleva", ["g502"], cantidad=4,
                   color="negro", depende=True)], "todo": {}},
        {"cosas": [c("compat", ["memoria", "ram"], que_pide=["notebook", "lenovo"])], "todo": {}},
        {"cosas": [c("lleva", ["g203"], color="blanco"), c("lleva", ["cobra"], cantidad=2)], "todo": {}},
        {"cosas": [c("opciones", MOU, condicion=[["inalambr"]], orden="barato")], "todo": {}},
        {"cosas": [c("cambia", ["g305"], "L2", destino="Cordoba"), c("cambia", ["k120"], "L1", cantidad=1)],
         "todo": {"reparto": [[100, "transferencia"]]}},
        {"cosas": [c("cuenta", ["*"]), c("saca", ["g305"], "L2", depende=True)], "todo": {}},
        {"cosas": [c("dato", ["k120"], que_pide=["negro"])], "todo": {}},
        {"cosas": [c("lleva", ["k120"], cantidad=2, destino="Salta"), c("lleva", ["g305"], destino="Salta")], "todo": {}},
        {"cosas": [c("lleva", ["parlante"], orden="caro"), c("lleva", MOU, orden="barato")], "todo": {}},
    ]
    out = []
    for i, ((mem, frase, _), vara) in enumerate(zip(FRASES, varas), 1):
        estado, historial = _estado_mem(mem_a if mem == MEMORIA_A else mem_b if mem == MEMORIA_B else {})
        out.append((f"N{i:02d}", frase, estado, historial, vara))
    return out


# ══ LAS CORRIDAS ═════════════════════════════════════════════════════════════

def _archivo(nombre: str) -> str:
    return os.path.join(SALIDAS, f"{nombre}_rep{REP}.jsonl")


def _turnos_sueltos() -> list:
    """(fuente, id, mensaje, estado, historial)."""
    from fichas import CHARLAS
    from experimento import limpio
    out = []
    for ch in CHARLAS:
        for i, tu in enumerate(ch["turnos"]):
            estado, historial = _estado_mem(tu["mem"])
            out.append(("48", f"{ch['id']} t{i}", limpio(tu["msg"]), estado, historial))
    for r in map(json.loads, open(V.TURNOS58, encoding="utf-8")):
        out.append(("58", f"{r['charla']} t{r['turno']}", r["msg"], r["estado"], r["historial"]))
    for cid, msg, estado, historial, _ in nuevas():
        out.append(("nuevas", cid, msg, estado, historial))
    return out


async def sueltos() -> None:
    hechos = {}
    if os.path.exists(_archivo("sueltos")):
        hechos = {(r["fuente"], r["id"]): r for r in map(json.loads, open(_archivo("sueltos"), encoding="utf-8"))
                  if r.get("salida")}
    sem = asyncio.Semaphore(int(os.environ.get("A_LA_VEZ", "4")))

    async def uno(fuente, cid, msg, estado, historial):
        if (fuente, cid) in hechos:
            return hechos[(fuente, cid)]
        async with sem:
            try:
                crudo = await interprete._pedir(mensajes(msg, historial, estado), "primera_ejes", formato())
                return {"fuente": fuente, "id": cid, "mensaje": msg, "salida": interprete._json(crudo)}
            except Exception as e:  # noqa: BLE001 — un turno sin respuesta queda anotado
                return {"fuente": fuente, "id": cid, "mensaje": msg, "error": f"{type(e).__name__}: {str(e)[:160]}"}
    rs = await asyncio.gather(*[uno(*t) for t in _turnos_sueltos()])
    with open(_archivo("sueltos"), "w", encoding="utf-8") as fh:
        for r in rs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"sueltos: {sum(bool(r.get('salida')) for r in rs)} de {len(rs)} en {_archivo('sueltos')}")


def cadena(base: bool) -> None:
    """Las 58 enteras y los siete de produccion por el webhook, con el modelo real en cada turno."""
    from banco_pruebas import clon_produccion as C
    from banco_pruebas.cableado58 import charlas
    from banco_pruebas.sonda_charlas import nota_casilla
    if not base:
        interprete.interpretar = interpretar
    prod7 = json.load(open(os.path.join(AQUI, "jev", "casos_produccion.json"), encoding="utf-8"))["charlas"]
    nombre = "cadena_base" if base else "cadena"
    with open(_archivo(nombre), "w", encoding="utf-8") as fh:
        for fuente, lista in (("58", charlas()), ("prod7", prod7)):
            for ch in lista:
                uid = f"ejes_{nombre}_{ch['id']}_{REP}"
                C.reiniciar_cliente(uid)
                resps, turnos = [], []
                for t in ch["turnos"]:
                    del GRABADO[:]
                    txt = "\n".join(asyncio.run(C.turno(uid, t["texto"])))
                    resps.append(txt)
                    turnos.append({"texto": t["texto"], "respuesta": txt, "salida": list(GRABADO),
                                   "casillas": [(k["n"], nota_casilla(k, [], txt, resps)) for k in t["casillas"]]})
                malas = [n for t in turnos for n, ok in t["casillas"] if ok is not True]
                print(f"  {fuente} {ch['id']}: {'bien' if not malas else 'MAL ' + '; '.join(malas)}", flush=True)
                fh.write(json.dumps({"fuente": fuente, "id": ch["id"], "turnos": turnos}, ensure_ascii=False) + "\n")


# ══ LAS VARAS sobre lo grabado ═══════════════════════════════════════════════

def _sueltos_58_respuesta(agenda_de) -> tuple:
    """Las 58 sueltas por lo que lee el cliente: la charla con las agendas a mano, y el turno medido con la agenda que
    sale de la lectura. Sin modelo: lo grabado."""
    from banco_pruebas import cableado58 as C58
    from banco_pruebas.agendas58 import AGENDAS, EXPLICAR
    interp = C58.instalar()
    bien, total, malos = 0, 0, []
    for ch in C58.charlas():
        ags = list(AGENDAS.get(ch["id"]) or [])
        if len(ags) != len(ch["turnos"]):
            continue
        for i in range(len(ags)):
            if not ch["turnos"][i]["casillas"]:
                continue
            ag = agenda_de(f"{ch['id']} t{i}")
            if ag is None:
                continue
            prueba = ags[:i] + [ag]
            turnos = C58.correr({**ch, "turnos": ch["turnos"][:i + 1]}, prueba, interp, EXPLICAR)
            ok = all(v is True for _, v in turnos[-1]["casillas"])
            total += 1
            bien += ok
            if not ok:
                malos.append(f"{ch['id']} t{i}")
    return bien, total, malos


def medir() -> None:
    import medir_pedido as MP
    import medir_ficha as MF
    from fichas import CHARLAS
    from app.core.flujo import ficha as F
    grabado = _archivo("sueltos_cob" if "--cob" in ARGS else "sueltos")
    sal = {(r["fuente"], r["id"]): r.get("salida") for r in map(json.loads, open(grabado, encoding="utf-8"))}
    ver = "--ver" in ARGS
    # 1. LOS DATOS: la vara por dato, la lectura nueva y la ficha nativa.
    for nombre in ("ficha nativa", "los dos ejes"):
        V.NOTA.clear()
        V.FALLAS.clear()
        for fuente, cid, msg, estado, historial in _turnos_sueltos():
            nums = interprete.numeros(estado)
            renglones = [r["L"] for r in (estado.get("borrador") or {}).get("renglones") or []]
            if fuente == "48":
                ch, t = cid.split(" t")
                tu = next(c for c in CHARLAS if c["id"] == ch)["turnos"][int(t)]
                vara = V.vara_48(tu)
            elif fuente == "58":
                r = next(x for x in map(json.loads, open(V.TURNOS58, encoding="utf-8"))
                         if f"{x['charla']} t{x['turno']}" == cid)
                vara = V.vara_58(r["agenda"], nums)
            else:
                vara = next(v for i, m, e, h, v in nuevas() if i == cid)
            if nombre == "ficha nativa":
                if fuente == "nuevas":
                    continue
                fichas = _fichas()
                leido = V.de_ficha(fichas.get((fuente, cid)), nums, renglones)
            else:
                if sal.get((fuente, cid)) is None:
                    continue
                leido = como_cosas(sal[(fuente, cid)], nums)
            V.calificar(fuente, cid, vara, leido)
        _informe_datos(nombre, ver)
    # 2. EL PEDIDO de las 48, lo que queda en el bot.
    # La ficha nativa salio del codigo el 25-oct, FICHA 81: su medida queda la de ese dia, 36 BIEN, 3 DUDO y 9 MAL en las
    # 48, y 62 de 74 en las 58 sueltas.
    for nombre, agenda_de in (("los dos ejes", lambda cid, msg, estado: a_agenda(sal.get(("48", cid)) or {}, estado,
                                                                                  msg)),):
        cuenta = collections.Counter()
        for ch in CHARLAS:
            for i, tu in enumerate(ch["turnos"]):
                cid = f"{ch['id']} t{i}"

                async def ag(msg, historial, estado, _cid=cid, _f=agenda_de):
                    return _f(_cid, msg, estado)
                try:
                    r = asyncio.run(MP.turno(tu, ag))
                    c = MF.calificar(tu, json.dumps(r["ficha"], ensure_ascii=False))
                except Exception as e:  # noqa: BLE001
                    c = {"veredicto": "MAL SIN AVISAR", "fallas": [str(e)[:80]]}
                cuenta[c["veredicto"]] += 1
                if ver and c["veredicto"] != "BIEN":
                    print(f"    {nombre} {cid} {c['veredicto']}: {c['fallas']}")
        print(f"\nEL PEDIDO EN LAS 48 · {nombre}: BIEN {cuenta['BIEN']} · DUDO {cuenta['DUDO']} · "
              f"MAL SIN AVISAR {cuenta['MAL SIN AVISAR']}")
    # 3. LA RESPUESTA de las 58 sueltas.
    turnos58 = {f"{r['charla']} t{r['turno']}": r for r in map(json.loads, open(V.TURNOS58, encoding="utf-8"))}
    for nombre, agenda_de in (
            ("los dos ejes", lambda cid: a_agenda(sal.get(("58", cid)) or {}, turnos58[cid]["estado"],
                                                  turnos58[cid]["msg"]) if sal.get(("58", cid)) else None),):
        bien, total, malos = _sueltos_58_respuesta(agenda_de)
        print(f"\nLA RESPUESTA EN LAS 58 SUELTAS · {nombre}: {bien} de {total} turnos con sus casillas"
              + (f"\n    mal: {' '.join(malos)}" if ver else ""))
    # 4. LA CADENA, si se corrio.
    for nombre in ("cadena_base", "cadena"):
        if not os.path.exists(_archivo(nombre)):
            continue
        cuenta = collections.Counter()
        for r in map(json.loads, open(_archivo(nombre), encoding="utf-8")):
            ok = all(v is True for t in r["turnos"] for _, v in t["casillas"])
            cuenta[(r["fuente"], ok)] += 1
        print(f"\nLA CADENA · {'ficha nativa' if nombre == 'cadena_base' else 'los dos ejes'}: " + " · ".join(
            f"{f} {cuenta[(f, True)]} de {cuenta[(f, True)] + cuenta[(f, False)]} charlas" for f in ("58", "prod7")))


_FICHAS = {}


def _fichas() -> dict:
    if not _FICHAS:
        _FICHAS.update({("48", f"{r['charla']} t{r['turno']}"): r["salida"]
                        for r in map(json.loads, open(V.FICHA48, encoding="utf-8"))})
        _FICHAS.update({("58", f"{r['charla']} t{r['turno']}"): r.get("salida")
                        for r in map(json.loads, open(V.FICHA58, encoding="utf-8"))})
    return _FICHAS


def _informe_datos(nombre: str, ver: bool) -> None:
    print(f"\nLOS DATOS · {nombre}")
    for fuente in ("48", "58", "nuevas"):
        c = V.NOTA[fuente]
        if not c["turnos"]:
            continue
        datos = " · ".join(f"{d} {c[f'{d} bien']}/{c[f'{d} casos']}" for d in
                           ("la cosa", "acto") + V.DATOS[1:] + ("orden para todo", "tope", "si pasa, saca", "reparto")
                           if c[f"{d} casos"])
        print(f"  las {fuente}: {c['turnos enteros']} de {c['turnos']} turnos enteros · lleva de mas {c['lleva de mas']}"
              f"\n    {datos}")
        if ver:
            for cid, dato, que in V.FALLAS[fuente]:
                print(f"      {cid:8} {dato:14} {que[:100]}")


# ══ LA COBERTURA, 25-oct: ninguna frase del mensaje se pierde ═══════════════════════════════════════════════════════
# El modelo no sabe que se olvido algo. El codigo si: cada frase del mensaje tiene que estar en las palabras literales que
# el modelo copio en "cliente" de alguna parte. No interpreta: compara palabras.

_SALUDO = set("hola buenas buen dia tardes noches gracias saludos che bueno dale ok genial perfecto".split())


















async def sueltos_releidos() -> None:
    """Los sueltos grabados con la segunda vuelta donde la cobertura marca algo: solo esos llaman al modelo."""
    estados = {(f, c): (e, h) for f, c, m, e, h in _turnos_sueltos()}
    out, releidos = [], 0
    for r in map(json.loads, open(_archivo("sueltos"), encoding="utf-8")):
        if r.get("salida"):
            e, h = estados[(r["fuente"], r["id"])]
            r["salida"], hizo = await releer(r["mensaje"], h, e, r["salida"])
            releidos += hizo
        out.append(r)
    with open(_archivo("sueltos_cob"), "w", encoding="utf-8") as fh:
        for r in out:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"releidos {releidos} de {len(out)}; queda sin cubrir en "
          f"{sum(bool(sin_cubrir(r['mensaje'], r.get('salida') or {})) for r in out)}")


def cobertura() -> None:
    """Lo que el control marca en todo lo grabado: los sueltos y cada turno de la cadena."""
    marcados, total = [], 0
    for r in map(json.loads, open(_archivo("sueltos"), encoding="utf-8")):
        total += 1
        for f in sin_cubrir(r["mensaje"], r.get("salida") or {}):
            marcados.append((r["fuente"], r["id"], f))
    if os.path.exists(_archivo("cadena")):
        for r in map(json.loads, open(_archivo("cadena"), encoding="utf-8")):
            for i, t in enumerate(r["turnos"]):
                for s in t["salida"]:
                    total += 1
                    for f in sin_cubrir(s["mensaje"], s["salida"]):
                        marcados.append(("cadena " + r["fuente"], f"{r['id']} t{i}", f))
    print(f"\nLA COBERTURA: {len(marcados)} frases sin cubrir en {total} lecturas")
    for m in marcados:
        print(f"  {m[0]:12} {m[1]:8} {m[2][:110]}")


def main() -> None:
    if "--cobertura" in ARGS:
        return cobertura()
    if "--releer" in ARGS:
        return asyncio.run(sueltos_releidos())
    if "--ejemplos" in ARGS:
        return armar_ejemplos()
    if "--sueltos" in ARGS:
        return asyncio.run(sueltos())
    if "--cadena" in ARGS:
        return cadena("--base" in ARGS)
    if "--medir" in ARGS:
        return medir()
    print(__doc__)


if __name__ == "__main__":
    main()
