"""JEV EN LA INTERPRETACION — ¿el clasificador de TypeSafe pone cada renglon en su casilla? (15-oct-2026).

Jev no escribe texto: de un estado y una lista cerrada devuelve la opcion con su probabilidad. No parte el mensaje.
La prueba usa los renglones que ya corto la ficha 9 —las palabras literales del cliente— y le pide a Jev la casilla
de cada uno, sin volver a llamar al modelo que los corto.

La vara es la CAPA DE CASILLAS, no la del contenido. El corrector del desmenuzado mira el contenido —el rubro, el
destino, el porcentaje—, y eso Jev no lo escribe. Aca se mira si cada parte esperada del caso tiene su casilla en
algun renglon. Con la misma vara se mide la casilla que puso el modelo que corto: la comparacion es pareja.

Las 58 son clases de CHARLA, no de renglon, y no tienen lo correcto por renglon: no se pueden medir asi. Las
casillas de la ficha 9 si, y son la lista cerrada que usa el turno.

Dos formas de preguntar:
  choice  una pregunta por renglon, las casillas como opciones. Casilla es la elegida, y las de probabilidad alta.
  noul    una pregunta si o no por renglon y casilla. Un renglon puede ir a dos casillas.

  python3 banco_pruebas/nexos/jev.py --ronda j1 --de cc_h9,c5_h9 --forma noul
  python3 banco_pruebas/nexos/jev.py --informe j1
"""
import argparse, json, os, re, sys, threading, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.dirname(os.path.dirname(AQUI)))
import desmenuzado as D  # noqa: E402
import ficha_casillas as F  # noqa: E402

SALIDA = os.path.join(AQUI, "jev_corridas.jsonl")
URL = "https://api.typesafe.ai/v1/systemone"
MODELO = "jev-latest"
PRECIO_ENTRADA = 0.042 / 1e6  # dolares por token de entrada; la salida no se cobra, ficha 67
_lock = threading.Lock()


def _definiciones() -> dict:
    """Cada casilla de la ficha 9 con su definicion, sacada de CASILLAS_9 y no copiada aca. El pedido se parte en
    sus dos subcampos, porque el corrector los mide por separado: articulos y reparto del pago."""
    defs, actual = {}, None
    for linea in F.CASILLAS_9.splitlines()[1:]:
        m = re.match(r"- (\w+): (.*)", linea)
        if m:
            actual = m.group(1)
            defs[actual] = m.group(2)
        elif actual:
            defs[actual] += " " + linea.strip()
    # La forma JSON del final no le dice nada a Jev y lo distrae.
    defs = {k: re.sub(r'\s*(\[\{.*\}\]|\{".*\}|\[[^\]"]*\])\s*$', "", v).strip() for k, v in defs.items()}
    ped = defs.pop("pedido")
    # DEFS 2, 15-oct: con la 1 Jev marcaba pedido en "precio de un mouse" —Q063 Q077 Q082, con "no" agregar—. Lee
    # literal, y su documentacion pide poner el borde en la definicion: pedir precio o buscar no es comprar.
    defs["pedido.articulos"] = ("lo que el cliente compra, anota, saca o mueve, con cantidad, color o destino de cada "
                                "producto. Pedir precio, buscar, preguntar o comparar NO es comprar: va solo si dice "
                                "que lo compra, lo lleva, lo anota, lo saca, lo cambia o lo manda a un destino. " + ped.split('"reparto_pago"')[0].split('"articulos" es')[-1].strip(' ;'))
    defs["pedido.reparto_pago"] = "con que medio paga, o como reparte el pago entre medios o porcentajes."
    defs["nada"] = "no pide ni dice nada que haya que buscar o anotar: un saludo, un agradecimiento, un relleno."
    return defs


DEFS = _definiciones()
VERSION_DEFS = 2

# La casilla de cada parte que espera el corrector. Una parte se cumple si ALGUN renglon va a alguna de sus casillas:
# las mismas equivalencias que hace `ficha_casillas.atomos` —la condicion viaja con la compatibilidad o el tope, el
# producto vale en cualquier casilla que lo lleve—.
CASILLAS_DE_PARTE = {
    "prod": {"productos", "referencias", "compatibilidad", "afirma", "pedido.articulos"},
    "ficha": {"productos", "referencias", "afirma"},
    "buscar": {"busquedas"},
    "compat": {"compatibilidad"},
    "politica": {"politicas", "afirma"},
    "envio": {"envios"},
    "pago": {"pedido.reparto_pago"},
    "cuenta": {"total", "pedido.reparto_pago", "pedido.articulos"},
    "condicion": {"condiciones", "compatibilidad", "total"},
    "preguntar": {"preguntar", "compatibilidad"},
    "humano": {"humano"},
    "novende": {"no_vende"},
    "destino": {"pedido.articulos", "envios"},
    "agregar": {"pedido.articulos"},
}


def casillas_de(e) -> set:
    if e["t"] == "alt":
        return set().union(*(casillas_de(x) for x in e["de"]))
    return CASILLAS_DE_PARTE[e["t"]]


def normalizar(c: str) -> str:
    """Como nombra la casilla el modelo que corta: "politicas.factura" es politicas; "pedido" a secas o
    "pedido.cambia" es articulos."""
    c = str(c).strip()
    if c == "pedido.reparto_pago":
        return c
    if c.startswith("pedido"):
        return "pedido.articulos"
    return c.split(".")[0]


def nota(esp, puestas: set) -> dict:
    """La capa de casillas de un caso: que partes no tienen su casilla en ningun renglon."""
    partes = list(esp["partes"]) + ([{"t": "agregar"}] if esp.get("carrito") else [])
    faltan = [p for p in partes if not (casillas_de(p) & puestas)]
    prohibidos = [t for t in esp.get("no", []) if t == "agregar" and "pedido.articulos" in puestas]
    return {"partes": len(partes), "bien": len(partes) - len(faltan), "ok": not faltan and not prohibidos,
            "faltan": [D.en_palabras(f) if f["t"] != "agregar" else "el pedido" for f in faltan]}


# Las casillas que disparan una accion del codigo: buscar, cotizar, anotar, preguntar. Una de mas es un turno que
# hace algo que no le pidieron. Las otras —jerga, cliente, afirma— solo informan, y no cuentan como de mas.
DE_ACCION = {"busquedas", "productos", "compatibilidad", "politicas", "envios", "pedido.articulos",
             "pedido.reparto_pago", "condiciones", "preguntar", "total", "no_vende", "humano"}


def de_mas(esp, puestas: set) -> set:
    """Las casillas de accion que ninguna parte esperada del caso pide. Es la otra mitad de la vara: sin ella, marcar
    todas las casillas en todos los renglones daria todo bien."""
    partes = list(esp["partes"]) + ([{"t": "agregar"}] if esp.get("carrito") else [])
    pedidas = set().union(set(), *(casillas_de(p) for p in partes))
    return (puestas & DE_ACCION) - pedidas


def renglones_de(etiquetas: str) -> dict:
    """Los renglones de la ultima corrida de cada caso, en las etiquetas de la ficha 9 que se nombran."""
    from app.core.tablero import _json
    out = {}
    for et in etiquetas.split(","):
        for cid, f in F.filas(et).items():
            if f["crudo"].startswith("ERROR"):
                continue
            rs = [r for r in (_json(f["crudo"]).get("renglones") or []) if isinstance(r, dict) and r.get("cita")]
            if rs:
                out[cid] = {"de": et, "modelo": f["modelo"], "renglones": rs, "ok_modelo": f["ok"]}
    return out


def estado(ctx, msg) -> str:
    """Lo que Jev necesita para leer un renglon, y nada mas: la charla de antes, el mensaje entero, los rubros y los
    temas. Su documentacion avisa que el estado lleno de detalle que no hace falta lo distrae: no van los datos de
    cada producto."""
    from app.core import tablero as T
    rubros, temas, _ = T._vocabulario(D.TIENDA)
    previo = "nada, es el primer mensaje"
    if ctx:
        previo = "\n".join(f"CLIENTE: {c}\nVENDEDOR: {v}" for c, v in ctx.get("antes") or [])
        if ctx.get("carrito"):
            previo += "\nPEDIDO ANOTADO: " + "; ".join(f"{q} {D.POR_ID[p]['nombre']} a {d or 'sin destino'}"
                                                       for p, q, d in ctx["carrito"])
    return (f"Una tienda online de tecnologia de Argentina. RUBROS QUE VENDE: {', '.join(rubros)}.\n"
            f"TEMAS DE POLITICA DE LA TIENDA: {', '.join(temas)}.\n\nLA CHARLA ANTES:\n{previo}\n\n"
            f"ULTIMO MENSAJE DEL CLIENTE, ENTERO: {msg}")


def preguntas(renglones, forma) -> dict:
    qs = {}
    for i, r in enumerate(renglones):
        cita = r["cita"]
        if forma == "choice":
            qs[f"r{i}"] = {"type": "choice", "criteria": DEFS,
                           "instructions": f"A que casilla de la ficha va este pedazo del ultimo mensaje del cliente: "
                                           f"«{cita}». Leelo dentro del mensaje entero y de la charla."}
        else:
            for k, (c, d) in enumerate(DEFS.items()):
                if c == "nada":
                    continue
                qs[f"r{i}_{k}"] = {"type": "noul",
                                   "instructions": f"Este pedazo del ultimo mensaje del cliente, «{cita}», leido "
                                                   f"dentro del mensaje entero y de la charla, va en la casilla "
                                                   f"\"{c}\": {d}"}
    return qs


def llamar(body) -> dict:
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={
        "Authorization": "Bearer " + os.environ["TYPESAFE_API_KEY"].strip(), "Content-Type": "application/json"})
    espera = 5
    for i in range(5):
        try:
            return json.load(urllib.request.urlopen(req, timeout=120))
        except urllib.error.HTTPError as e:
            if i < 4 and e.code in (429, 500, 502, 503, 504):
                time.sleep(espera)
                espera *= 2
                continue
            raise RuntimeError(f"{e.code} {e.read()[:300]!r}")


def uno(caso, origen, forma, etiqueta):
    cid, ctx, msg, esp = caso
    rs = origen["renglones"]
    t0 = time.time()
    try:
        r = llamar({"state": estado(ctx, msg), "model": MODELO, "questions": preguntas(rs, forma)})
        ans, uso, error = r["answers"], r.get("usage", {}), None
    except Exception as e:  # noqa: BLE001
        ans, uso, error = {}, {}, f"{type(e).__name__}: {str(e)[:300]}"
    salida = []
    for i, x in enumerate(rs):
        if forma == "choice":
            a = ans.get(f"r{i}", {})
            salida.append({"cita": x["cita"], "modelo": x.get("casillas"), "choice": a.get("choice"),
                           "confianza": a.get("confidence"), "prob": a.get("probabilities", {})})
        else:
            prob = {c: (ans.get(f"r{i}_{k}") or {}).get("noul") for k, c in enumerate(DEFS) if c != "nada"}
            salida.append({"cita": x["cita"], "modelo": x.get("casillas"), "prob": prob})
    fila = {"etiqueta": etiqueta, "forma": forma, "defs": VERSION_DEFS, "jev": r.get("model") if not error else None, "id": cid,
            "reserva": cid in D.RESERVA, "de": origen["de"], "corto": origen["modelo"], "ok_modelo": origen["ok_modelo"],
            "ms": int((time.time() - t0) * 1000), "tokens": [uso.get("input_tokens", 0), uso.get("output_tokens", 0)],
            "error": error, "renglones": salida}
    with _lock:
        with open(SALIDA, "a", encoding="utf-8") as f:
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
    return fila


def puestas_jev(fila, umbral) -> list:
    """La casilla de cada renglon segun Jev. En choice, la elegida y toda la que pase el umbral; en noul, toda la que
    pase el umbral, y si ninguna pasa, la mas alta: cada renglon cae en algun lado."""
    out = []
    for r in fila["renglones"]:
        prob = {k: v for k, v in (r.get("prob") or {}).items() if v is not None}
        s = {c for c, p in prob.items() if p >= umbral}
        if fila["forma"] == "choice" and r.get("choice"):
            s.add(r["choice"])
        if not s and prob:
            s.add(max(prob, key=prob.get))
        out.append(s - {"nada"})
    return out


def filas(etiqueta) -> dict:
    ult = {}
    if os.path.exists(SALIDA):
        for x in open(SALIDA, encoding="utf-8"):
            f = json.loads(x)
            if f["etiqueta"] == etiqueta:
                ult[f["id"]] = f
    return ult


def ronda(etiqueta, de, forma, casos=""):
    origen = renglones_de(de)
    lista = [c for c in D.CASOS if c[0] in origen and (not casos or c[0] in casos.split(","))]
    print(f"{len(lista)} casos con renglones de {de}; forma {forma}", flush=True)
    with ThreadPoolExecutor(4) as ex:
        for f in ex.map(lambda c: uno(c, origen[c[0]], forma, etiqueta), lista):
            print(f"{f['id']}: {f['ms']} ms {f['tokens'][0]} tokens{' ' + f['error'] if f['error'] else ''}", flush=True)
    informe(etiqueta)


def informe(etiqueta, umbrales=(0.9, 0.7, 0.5, 0.3)):
    fs = filas(etiqueta)
    casos = {c[0]: c for c in D.CASOS}
    buenas = [f for f in fs.values() if not f["error"]]
    if not buenas:
        print("sin filas")
        return
    forma = buenas[0]["forma"]
    tok = sum(f["tokens"][0] for f in buenas)
    print(f"\nJEV {etiqueta}, forma {forma}, {len(buenas)} casos ({len(fs) - len(buenas)} con error), renglones de "
          f"{sorted({f['de'] for f in buenas})}. Entrada {tok} tokens, unos {tok * PRECIO_ENTRADA * 100:.2f} centavos de "
          f"dolar; {sum(f['ms'] for f in buenas) / len(buenas) / 1000:.1f} s por caso.")

    def grupo(nombre, sel):
        sel = list(sel)
        if not sel:
            return
        linea = [f"{nombre} {len(sel)}:"]
        def par(esp, puestas):
            return f"{int(nota(esp, puestas)['ok'])}{int(not de_mas(esp, puestas))}"

        def cuenta(pares):
            pares = list(pares)
            return (f"{sum(p[0] == '1' for p in pares)}, limpios {sum(p[1] == '1' for p in pares)}, "
                    f"las dos {sum(p == '11' for p in pares)}")
        linea.append("el que corto " + cuenta(par(casos[f["id"]][3], set().union(
            set(), *[{normalizar(c) for c in r["modelo"] or []} for r in f["renglones"]])) for f in sel))
        for u in umbrales:
            linea.append(f"Jev {u} " + cuenta(par(casos[f["id"]][3], set().union(set(), *puestas_jev(f, u)))
                                             for f in sel))
        linea.append(f"| contenido del que corto {sum(f['ok_modelo'] for f in sel)}")
        print("  " + " · ".join(linea))
    print("Casos con todas sus partes en una casilla; limpios, sin casilla de accion de mas; y las dos cosas:")
    grupo("todos", buenas)
    grupo("ajuste", (f for f in buenas if not f["reserva"]))
    grupo("reserva", (f for f in buenas if f["reserva"]))
    for de in sorted({f["de"] for f in buenas}):
        grupo(de, (f for f in buenas if f["de"] == de))
    u = umbrales[2]
    print(f"\nLos que Jev pierde con umbral {u}, y lo que falta:")
    for f in sorted(buenas, key=lambda f: f["id"]):
        n = nota(casos[f["id"]][3], set().union(set(), *puestas_jev(f, u)))
        if not n["ok"]:
            print(f"  {f['id']}{'r' if f['reserva'] else ' '} {n['bien']}/{n['partes']}: " + "; ".join(n["faltan"])[:160])
    # Renglon a renglon: donde Jev y el que corto no coinciden en la casilla principal.
    total = distintos = 0
    for f in buenas:
        for r, s in zip(f["renglones"], puestas_jev(f, 1.01)):
            m = {normalizar(c) for c in r["modelo"] or []} - {"nada"}
            total += 1
            distintos += bool(m) and not (m & s)
    print(f"\nRenglones: {total}; en {distintos} la casilla que mas le da Jev no esta entre las del que corto.")
    # JEV COMO SEGUNDA OPINION: la alarma es un renglon donde Jev pone, con 0.7 o mas, una casilla de accion que el
    # que corto no puso. ¿Las alarmas caen en los casos donde el que corto se equivoco en el contenido?
    def alarma(f):
        for r in f["renglones"]:
            m = {normalizar(c) for c in r["modelo"] or []}
            prob = {k: v for k, v in (r.get("prob") or {}).items() if v is not None}
            if any(p >= 0.7 and c in DE_ACCION and c not in m for c, p in prob.items()):
                return True
        return False
    mal = [f for f in buenas if not f["ok_modelo"]]
    bien = [f for f in buenas if f["ok_modelo"]]
    print(f"Segunda opinion: el que corto erro el contenido en {len(mal)}; Jev alarma en {sum(map(alarma, mal))} de "
          f"esos y en {sum(map(alarma, bien))} de los {len(bien)} bien: "
          + ", ".join(f["id"] + ("!" if alarma(f) else "") for f in mal))
    cort = sum(len({normalizar(c) for c in r["modelo"] or []} - {"nada"}) for f in buenas for r in f["renglones"])
    print(f"Casillas por renglon: el que corto {cort / total:.1f}; Jev " + ", ".join(
        f"{x} {sum(len(s) for f in buenas for s in puestas_jev(f, x)) / total:.1f}" for x in umbrales) + ".")


def main():
    global MODELO
    ap = argparse.ArgumentParser()
    ap.add_argument("--ronda")
    ap.add_argument("--de", default="cc_h9,c5_h9", help="etiquetas de la ficha 9 de las que salen los renglones")
    ap.add_argument("--forma", default="noul", choices=("choice", "noul"))
    ap.add_argument("--casos", default="")
    ap.add_argument("--modelo", default=MODELO)
    ap.add_argument("--informe")
    a = ap.parse_args()
    MODELO = a.modelo
    D.preparar()
    if a.ronda:
        ronda(a.ronda, a.de, a.forma, a.casos)
    elif a.informe:
        informe(a.informe)


if __name__ == "__main__":
    main()
