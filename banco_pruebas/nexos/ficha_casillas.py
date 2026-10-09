"""LA FICHA DE CASILLAS — ¿que casillas llena cada mensaje, y como lo descifra el modelo? (9-oct-2026, ficha 68).

Experimento de Martin. El modelo recibe una ficha con TODAS las casillas que puede tener una charla, simple o
compleja, con lo que ya se sabe de la charla escrito adentro. No le contesta al cliente: lee su ultimo mensaje,
traduce la jerga, razona solo si hace falta, y dice que casillas llena ese mensaje y con que, cuales quedan vacias,
y los pasos que siguio.

Y el ciclo para que el modelo diga una y otra vez como descifrar una pregunta compleja:
  1. ronda: llena la ficha; el corrector del desmenuzado la mide, por contenido.
  2. procedimiento: en cada falla de AJUSTE se le muestra lo que lleno y lo que falto, en palabras del cliente, y
     escribe los pasos generales que lo hubieran evitado; despues se le pide unificarlos en un solo procedimiento.
  3. otra ronda con ese procedimiento en la consigna. La RESERVA no se mira para escribirlo: es la medida limpia.

  python3 banco_pruebas/nexos/ficha_casillas.py --ronda fc0
  python3 banco_pruebas/nexos/ficha_casillas.py --procedimiento fc0 --version 1
  python3 banco_pruebas/nexos/ficha_casillas.py --ronda fc1 --con 1
"""
import argparse, json, os, sys, threading
from concurrent.futures import ThreadPoolExecutor

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.dirname(os.path.dirname(AQUI)))
import desmenuzado as D  # noqa: E402

SALIDA = os.path.join(AQUI, "ficha_casillas_corridas.jsonl")
PROCS = os.path.join(AQUI, "ficha_casillas_procedimientos.json")
MODELO = "gemini-3.1-flash-lite"
_lock = threading.Lock()

CASILLAS = """LA FICHA DE LA CHARLA. Estas son TODAS las casillas que puede llenar un mensaje del cliente:
- jerga: lo que el cliente nombra con sus palabras y lo que es en la tienda. [{"dijo", "es"}]
- referencias: lo que el cliente senala de la charla —"ese", "el segundo", "de esos", "lo de Rosario", "uno igual"— y a
  que producto o parte del pedido apunta, con el nombre concreto. [{"dijo", "es"}]
- productos: productos concretos de los que quiere saber algo —precio, stock, color, garantia, peso, un dato tecnico—.
  [{"producto", "quiere_saber"}]
- busquedas: lo que hay que buscar en el catalogo. rubro de la lista o "toda la tienda"; cantidad de articulos
  distintos; orden "mas barato", "mas caro" o "nada"; condiciones en palabras —marca, color, conexion, tope de precio,
  que no sea tal marca—. [{"rubro", "cantidad", "orden", "condiciones": [..]}]
- no_vende: lo que pide y la tienda no vende. [texto]
- compatibilidad: si un producto anda con un equipo u otro producto. [{"producto", "con"}]
- politicas: reglas de la tienda que pregunta, por tema de la lista. [tema]
- envios: destinos cuyo envio hay que cotizar. [destino]
- pedido: lo que compra o arma. "cambia" es true si este mensaje agrega, saca, mueve o confirma algo; "articulos" es el
  pedido ENTERO como queda despues de este mensaje, lo de antes que sigue y lo nuevo, cada uno con su destino;
  "reparto_pago" si reparte el pago; "pide_total" si pide sumar.
  {"cambia", "articulos": [{"producto", "cantidad", "destino"}], "reparto_pago": [{"medio", "porcentaje"}], "pide_total"}
- condiciones: lo que el cliente hace segun un resultado. [{"si", "entonces"}]
- preguntar: el dato del cliente que falta y no se puede deducir. [dato]
- humano: true si pide hablar con una persona."""

CONSIGNA = """Sos el interprete de una tienda online de tecnologia de Argentina. NO le contestas al cliente.
Tu unico trabajo: leer su ULTIMO mensaje y decir que casillas de la ficha llena, con que, y cuales quedan vacias.
Traduci la jerga a lo que vende la tienda. Razona solo cuando haga falta para saber que pide. Usa lo que la ficha ya
sabe de la charla para resolver referencias. No escribas precios.
{casillas}

RUBROS DE LA TIENDA: {rubros}
TEMAS DE POLITICA: {temas}
{procedimiento}
Devolve SOLO un JSON:
{{"pasos": ["los pasos que seguiste para descifrar el mensaje, uno por renglon"],
  "llena": {{solo las casillas que este mensaje llena, con la forma de arriba}},
  "vacias": ["las casillas que este mensaje no llena"]}}"""


def lo_que_ya_sabe(ctx) -> str:
    """Lo que la ficha ya trae de la charla, escrito por el codigo."""
    if not ctx:
        return "LO QUE YA SABE LA FICHA: nada, es el primer mensaje."
    r = ["LO QUE YA SABE LA FICHA:"]
    if ctx.get("vistos"):
        r.append("- lo mostrado en el ultimo mensaje, en orden: " + "; ".join(
            f"{i}. {D.POR_ID[p]['nombre']} ${D.POR_ID[p]['precio']:,}".replace(",", ".")
            for i, p in enumerate(ctx["vistos"], 1)))
    if ctx.get("carrito"):
        r.append("- pedido: " + "; ".join(f"{q} {D.POR_ID[p]['nombre']} a {d or 'sin destino'}"
                                          for p, q, d in ctx["carrito"]))
    if ctx.get("presupuesto"):
        r.append("- ultimo presupuesto: " + ctx["presupuesto"])
    if ctx.get("criterio"):
        r.append("- lo que busco el cliente: " + ctx["criterio"])
    for c, v in ctx.get("antes") or []:
        r.append(f"- CLIENTE dijo: {c}\n  VENDEDOR contesto: {v}")
    return "\n".join(r)


def consigna(procedimiento: str = "") -> str:
    from app.core import tablero as T
    rubros, temas, _ = T._vocabulario(D.TIENDA)
    proc = ("\nPROCEDIMIENTO para descifrar el mensaje, seguilo paso por paso:\n" + procedimiento + "\n") if procedimiento else ""
    return CONSIGNA.format(casillas=CASILLAS, rubros=", ".join(rubros), temas=", ".join(temas), procedimiento=proc)


def _lista(x):
    return x if isinstance(x, list) else ([x] if x else [])


def atomos(llena: dict) -> list:
    """La ficha llena como los atomos que mide el corrector del desmenuzado."""
    out = []
    for b in _lista(llena.get("busquedas")):
        if not isinstance(b, dict):
            continue
        rub = str(b.get("rubro") or "")
        o = D.n(str(b.get("orden") or ""))
        out.append({"t": "buscar", "rubro": "" if "toda" in D.n(rub) else rub,
                    "cant": b.get("cantidad") if isinstance(b.get("cantidad"), int) else None,
                    "orden": "min" if "barat" in o else "max" if "car" in o else None,
                    "cond": " ".join(str(c) for c in _lista(b.get("condiciones"))) + " " + rub})
    for p in _lista(llena.get("productos")):
        if isinstance(p, dict):
            out.append({"t": "prod", "prod": f"{p.get('producto') or ''} {p.get('quiere_saber') or ''}"})
    for r in _lista(llena.get("referencias")):
        if isinstance(r, dict):
            out.append({"t": "prod", "prod": str(r.get("es") or "")})
    for c in _lista(llena.get("compatibilidad")):
        if isinstance(c, dict):
            out.append({"t": "compat", "prod": str(c.get("producto") or ""), "con": str(c.get("con") or "")})
    for t in _lista(llena.get("politicas")):
        tema = D.n(str(t)).replace(" ", "_")
        out.append({"t": "politica", "tema": [tema] if tema in D.TEMAS else D.tema_de(str(t))})
    for d in _lista(llena.get("envios")):
        out.append({"t": "envio", "destino": str(d)})
    if llena.get("no_vende"):
        out.append({"t": "novende"})
    for _ in _lista(llena.get("condiciones")):
        out.append({"t": "condicion"})
    if llena.get("preguntar"):
        out.append({"t": "preguntar"})
    if llena.get("humano") is True:
        out.append({"t": "humano"})
    ped = llena.get("pedido") if isinstance(llena.get("pedido"), dict) else {}
    if ped.get("reparto_pago"):
        out.append({"t": "pago", "medios": {D.n(str(x.get("medio"))): x.get("porcentaje")
                                            for x in _lista(ped["reparto_pago"]) if isinstance(x, dict)}})
    # Un cambio del pedido lo recalcula el codigo (ficha 68): el total esta implicito.
    if ped.get("pide_total") or ped.get("reparto_pago") or ped.get("cambia"):
        out.append({"t": "cuenta"})
    if ped.get("cambia"):
        for a in _lista(ped.get("articulos")):
            if isinstance(a, dict):
                out.append({"t": "agregar", "prod": str(a.get("producto") or "")})
                out.append({"t": "destino", "destino": str(a.get("destino") or "")})
    return out


_SIN_DESTINO = ("", "nada", "sin destino", "sin definir", "ninguno", "no definido", "a definir", "null", "none")


def carrito(llena: dict, ctx) -> list:
    ped = llena.get("pedido") if isinstance(llena.get("pedido"), dict) else {}
    if ped.get("cambia") and ped.get("articulos"):
        return [(str(a.get("producto") or ""), int(a.get("cantidad") or 1),
                 "" if D.n(str(a.get("destino") or "")) in _SIN_DESTINO else str(a["destino"]))
                for a in _lista(ped["articulos"]) if isinstance(a, dict)]
    return [(D.POR_ID[p]["nombre"], q, d) for p, q, d in (ctx or {}).get("carrito", [])]


def corregir(caso, llena: dict) -> dict:
    cid, ctx, msg, esp = caso
    at = atomos(llena)
    faltan = [e for e in esp["partes"] if not any(D.cumple(e, a) for a in at)]
    prohibidos = [t for t in esp.get("no", []) if any(a["t"] == t for a in at)]
    carr = carrito(llena, ctx) if esp.get("carrito") else None
    carrito_ok = D.igual_carrito(esp["carrito"], carr) if esp.get("carrito") else True
    total = len(esp["partes"]) + (1 if esp.get("carrito") else 0)
    return {"partes": total, "bien": total - len(faltan) - (0 if carrito_ok else 1),
            "faltan": [json.dumps(f, ensure_ascii=False) for f in faltan], "prohibidos": prohibidos,
            "carrito_ok": carrito_ok, "carrito": carr, "ok": not faltan and not prohibidos and carrito_ok}


def uno(caso, etiqueta, procedimiento):
    cid, ctx, msg, esp = caso
    from app.core.contexto_turno import set_current_tienda
    set_current_tienda(D.TIENDA)
    msgs = [{"role": "system", "content": consigna(procedimiento)},
            {"role": "user", "content": lo_que_ya_sabe(ctx) + f"\n\nULTIMO MENSAJE DEL CLIENTE: {msg}"}]
    try:
        crudo, uso = D._crear(MODELO, msgs, {"type": "json_object"})
        from app.core.tablero import _json
        salida = _json(crudo)
        nota = corregir(caso, salida.get("llena") or {})
    except Exception as e:  # noqa: BLE001
        crudo, uso, salida = f"ERROR {type(e).__name__}: {str(e)[:200]}", (0, 0), {}
        nota = {"partes": 0, "bien": 0, "ok": False, "faltan": ["ERROR"], "carrito_ok": False, "prohibidos": []}
    fila = {"etiqueta": etiqueta, "modelo": MODELO, "id": cid, "reserva": cid in D.RESERVA,
            "partes_esperadas": len(esp["partes"]) + (1 if esp.get("carrito") else 0),
            "tokens": list(uso), "crudo": crudo[:6000], "pasos": salida.get("pasos"), **nota}
    with _lock:
        with open(SALIDA, "a", encoding="utf-8") as f:
            f.write(json.dumps(fila, ensure_ascii=False, default=str) + "\n")
    return fila


def filas(etiqueta):
    ult = {}
    for x in open(SALIDA, encoding="utf-8"):
        f = json.loads(x)
        if f["etiqueta"] == etiqueta:
            ult[f["id"]] = f
    return ult


def recalificar(etiqueta):
    """Las filas guardadas, corregidas de nuevo con el corrector de hoy y sin llamar al modelo."""
    from app.core.tablero import _json
    casos = {c[0]: c for c in D.CASOS}
    out = []
    for f in filas(etiqueta).values():
        if f["crudo"].startswith("ERROR"):
            out.append(f)
            continue
        out.append({**f, **corregir(casos[f["id"]], _json(f["crudo"]).get("llena") or {})})
    return {f["id"]: f for f in out}


def informe(etiqueta):
    fs = list(recalificar(etiqueta).values())

    def cuenta(sel):
        sel = list(sel)
        return f"{sum(f['ok'] for f in sel)} de {len(sel)}"
    print(f"\nFICHA DE CASILLAS {etiqueta}: casos enteros bien {cuenta(fs)} · ajuste {cuenta(f for f in fs if not f['reserva'])}"
          f" · reserva {cuenta(f for f in fs if f['reserva'])} · con 4 casillas o mas {cuenta(f for f in fs if f['partes_esperadas'] >= 4)}"
          f" · partes {sum(f['bien'] for f in fs)} de {sum(f['partes'] for f in fs)}")
    for f in sorted(fs, key=lambda f: f["id"]):
        if not f["ok"]:
            print(f"  {f['id']}{'r' if f['reserva'] else ' '} {f['bien']}/{f['partes']} "
                  + "; ".join(D.en_palabras(json.loads(x)) if x.startswith("{") else x for x in f["faltan"])[:200]
                  + ("" if f.get("carrito_ok", True) else " | pedido mal: " + str(f.get("carrito"))[:120]))


def ronda(etiqueta, version):
    procedimiento = ""
    if version:
        procedimiento = json.load(open(PROCS, encoding="utf-8"))[str(version)]
    with ThreadPoolExecutor(3) as ex:
        for f in ex.map(lambda c: uno(c, etiqueta, procedimiento), D.CASOS):
            print(f"{f['id']}: {'BIEN' if f['ok'] else 'MAL '} {f['bien']}/{f['partes']}", flush=True)
    informe(etiqueta)


PIDE_PASOS = """Esto es una revision, no un turno con el cliente. Arriba esta la ficha que llenaste.
Para que el codigo pueda trabajar, faltaba esto o quedo mal:
{faltan}
No me digas que te equivocaste. Escribi los PASOS GENERALES, numerados, maximo 8, que tendrias que seguir para
descifrar un mensaje asi y llenar bien la ficha: en este caso y en todos los parecidos. Pasos que sirvan para cualquier
producto y cualquier tienda: sin nombrar los productos de este caso."""

UNIFICA = """Te paso procedimientos que escribiste, cada uno despues de un error distinto llenando la ficha de casillas de una
tienda. Unificalos en UN SOLO procedimiento general para descifrar cualquier mensaje del cliente, simple o complejo, y
llenar la ficha: maximo 12 pasos numerados, en orden, concretos, sin repetir, sin nombrar productos ni casos. Si dos
pasos dicen lo mismo, dejalo una vez. Solo los pasos.

{procs}"""


def procedimiento(etiqueta, version):
    """Las fallas de AJUSTE de una ronda: cada una pide sus pasos; despues se unifican en uno solo."""
    casos = {c[0]: c for c in D.CASOS}
    malas = [f for f in filas(etiqueta).values() if not f["ok"] and not f["reserva"] and not f["crudo"].startswith("ERROR")]
    previos = json.load(open(PROCS, encoding="utf-8")) if os.path.exists(PROCS) else {}
    base_proc = previos.get(str(version - 1), "")
    pasos = []
    for f in malas:
        cid, ctx, msg, esp = casos[f["id"]]
        faltan = [D.en_palabras(json.loads(x)) if x.startswith("{") else x for x in f["faltan"]]
        if not f.get("carrito_ok", True):
            faltan.append("el pedido tenia que quedar asi: " + "; ".join(
                f"{q} de {D._legible(rx)} a {d or 'sin destino'}" for rx, q, d in esp["carrito"])
                + "; quedo: " + "; ".join(f"{q} de {p} a {d or 'sin destino'}" for p, q, d in f.get("carrito") or []))
        msgs = [{"role": "system", "content": consigna(base_proc)},
                {"role": "user", "content": lo_que_ya_sabe(ctx) + f"\n\nULTIMO MENSAJE DEL CLIENTE: {msg}"},
                {"role": "assistant", "content": f["crudo"][:4000]},
                {"role": "user", "content": PIDE_PASOS.format(faltan="\n".join("- " + x for x in faltan))}]
        r, _ = D._crear(MODELO, msgs)
        pasos.append(r)
        print(f"\n== {cid}\n{r}", flush=True)
    if base_proc:
        pasos.insert(0, "PROCEDIMIENTO ANTERIOR:\n" + base_proc)
    unico, _ = D._crear(MODELO, [{"role": "user", "content": UNIFICA.format(procs="\n\n---\n\n".join(pasos))}])
    previos[str(version)] = unico.strip()
    json.dump(previos, open(PROCS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n== PROCEDIMIENTO {version}\n{unico}")


CASILLA_DE = {"condicion": "condiciones", "cuenta": "pedido.pide_total", "pago": "pedido.reparto_pago",
              "buscar": "busquedas", "prod": "productos y referencias", "ficha": "productos y referencias",
              "compat": "compatibilidad", "politica": "politicas", "envio": "envios", "destino": "pedido.articulos",
              "novende": "no_vende", "preguntar": "preguntar", "humano": "humano", "agregar": "pedido.articulos"}

PIDE_REGLA = """Sos el interprete de una tienda que llena una ficha de casillas con el ultimo mensaje del cliente.
La casilla "{casilla}" quedo mal o vacia en estos mensajes:
{casos}
Escribi UNA regla concreta para esa casilla: cuando se llena, con que, y que senal del mensaje o de lo que ya sabe la
ficha la dispara. Agrega un ejemplo inventado por vos —otro producto, otra frase— con como queda la casilla.
Maximo cuatro renglones. Que sirva para cualquier mensaje parecido, sin nombrar los productos de estos casos.
NUNCA escribas datos de la tienda —precios, descuentos, plazos, condiciones—: la casilla lleva lo que el cliente pide
o el tema de la lista, nunca la respuesta. La respuesta la trae el codigo."""


def reglas(etiqueta, version):
    """Una regla por casilla, sacada de las fallas de AJUSTE de esa casilla (9-oct): el procedimiento unificado
    salia tan general que perdia lo concreto y la ronda 2 no subio."""
    casos = {c[0]: c for c in D.CASOS}
    por_casilla: dict = {}
    for f in filas(etiqueta).values():
        if f["ok"] or f["reserva"] or f["crudo"].startswith("ERROR"):
            continue
        cid, ctx, msg, esp = casos[f["id"]]
        for x in f["faltan"]:
            e = json.loads(x) if x.startswith("{") else {"t": x}
            ts = [y["t"] for y in e["de"]] if e["t"] == "alt" else [e["t"]]
            cas = CASILLA_DE.get(ts[0], ts[0])
            por_casilla.setdefault(cas, []).append(f"- CLIENTE: {msg}\n  FALTO: {D.en_palabras(e)}")
        if not f.get("carrito_ok", True):
            por_casilla.setdefault("pedido.articulos", []).append(
                f"- CLIENTE: {msg}\n  FALTO: el pedido tenia que quedar " + "; ".join(
                    f"{q} de {D._legible(rx)} a {d or 'sin destino'}" for rx, q, d in esp["carrito"]))
    previos = json.load(open(PROCS, encoding="utf-8")) if os.path.exists(PROCS) else {}
    salida = []
    for cas, lineas in sorted(por_casilla.items()):
        r, _ = D._crear(MODELO, [{"role": "user", "content": PIDE_REGLA.format(casilla=cas, casos="\n".join(lineas))}])
        salida.append(f"[{cas}] {r.strip()}")
        print(f"\n== {cas}\n{r}", flush=True)
    previos[str(version)] = "REGLAS POR CASILLA:\n" + "\n".join(salida)
    json.dump(previos, open(PROCS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ronda")
    ap.add_argument("--con", type=int, default=0, help="version del procedimiento a usar en la ronda")
    ap.add_argument("--procedimiento", help="etiqueta de la ronda de la que salen las fallas")
    ap.add_argument("--version", type=int, default=1)
    ap.add_argument("--informe")
    ap.add_argument("--reglas", help="etiqueta de la ronda de la que salen las reglas por casilla")
    a = ap.parse_args()
    D.preparar()
    if a.ronda:
        ronda(a.ronda, a.con)
    elif a.procedimiento:
        procedimiento(a.procedimiento, a.version)
    elif a.reglas:
        reglas(a.reglas, a.version)
    elif a.informe:
        informe(a.informe)


if __name__ == "__main__":
    main()
