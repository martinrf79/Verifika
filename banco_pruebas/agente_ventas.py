"""EL AGENTE DE VENTAS CON HUECOS — el modelo responde como vendedor y el codigo llena los datos deterministas
(28-oct-2026, FICHA 83).

Idea de Martin del 28-oct: "Eres un agente de ventas de ecommerce y necesito tu capacidad para responder; tendras la
multipregunta separada, la pregunta original y el estado de la charla. De acuerdo a la respuesta, hay que limarla para
ingresar en ella los datos deterministas." El modelo hace lo que mejor sabe por entrenamiento: contestar como vendedor.
Donde va un dato que no sabe —un precio, el stock, opciones, un envio, el total, una regla—, deja un hueco con lo que
necesita. El codigo llena cada hueco con el ejecutor de siempre, en orden y sobre el estado de la charla, y la respuesta
que recibe el cliente es el borrador con los huecos llenos. Se califica con las mismas casillas.

Los casos son los de `herramientas_modelo.py`: el mensaje, las lineas que separo la primera llamada, el carrito en
palabras de `carrito_modelo.py`. Los turnos de antes corren con la agenda a mano.

    python3 banco_pruebas/agente_ventas.py --llamar [--hasta 10]      con la gratis
    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/agente_ventas.py --llamar
    python3 banco_pruebas/agente_ventas.py [--ver]                     sin modelo
"""
import collections
import copy
import json
import os
import re
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
_PAGA = os.environ.get("GEMINI_API_KEY_PROD") if os.environ.get("MARTIN_AUTORIZO_LA_PAGA") else None
import carrito_modelo as CM  # noqa: E402
import herramientas_modelo as HM  # noqa: E402
from app.core.flujo import catalogo as K  # noqa: E402
from app.core.flujo import ficha as F  # noqa: E402

TID = HM.TID
GRABADO = os.path.join(AQUI, "agente_ventas.jsonl")

CONSIGNA = """Eres un agente de ventas de una tienda online de tecnologia de Argentina que vende por WhatsApp. Necesito tu
capacidad para responder el ultimo mensaje del cliente: tenes su mensaje original, el mismo mensaje separado en lineas y
el estado de la charla. Responde como un buen vendedor: corto, claro, en español rioplatense con voseo, contestando todo
lo que pregunto y llevando a la venta.

Vos no sabes precios, stock, envios, totales ni las reglas de la tienda. Donde va uno de esos datos, deja un hueco y el
sistema lo llena con el dato real. Los huecos, tal cual:
  [[PRECIO producto]]                      precio y stock de un modelo que nombro el cliente o del carrito
  [[DATO producto | lo que pregunta]]      un dato de la ficha: "inalambrico", "peso", "dpi"
  [[OPCIONES clase | orden | cantidad | condicion]]   productos para elegir; orden: mas barato, mas caro, mas liviano o nada
  [[AGREGAR cantidad | producto o clase | destino]]   anota en el pedido; con una clase, la tienda elige
  [[QUITAR item n]]   [[CAMBIAR item n | lo nuevo]]   [[CONFIRMAR item n]]
  [[ENVIO lugar]]                          lo que sale y tarda el envio
  [[TOTAL | tope | pagos]]                 el presupuesto del pedido; tope y pagos solo si los dijo: "70 transferencia, 30 tarjeta"
  [[REGLA tema]]                           una regla de la tienda, de estos temas: {temas}
  [[COMPATIBLE producto | equipo]]         si un producto anda con su equipo
  [[NO_VENDEMOS clase]]                    algo que la tienda no vende
Las clases de producto de la tienda son: {rubros}.
No escribas ningun numero de precio ni de plata: van en los huecos. No inventes productos."""

# LAS DOS VERSIONES COMPLETAS, 28-oct, orden de Martin: las cinco mejoras de la primera corrida en la consigna —el
# producto como lo nombro el cliente o por su numero, los huecos con campos por nombre, no afirmar lo que dice un hueco,
# solo lo que pregunto y lo senalado por su numero—, una con la salida libre y otra atada a un esquema.
LIBRE, ATADO = "--libre" in HM.ARGS, "--atado" in HM.ARGS
if LIBRE or ATADO:
    GRABADO = os.path.join(AQUI, "agente_ventas_atado.jsonl" if ATADO else "agente_ventas_libre.jsonl")

_REGLAS = """Eres un agente de ventas de una tienda online de tecnologia de Argentina que vende por WhatsApp. Necesito tu
capacidad para responder el ultimo mensaje del cliente: tenes su mensaje original, el mismo mensaje separado en lineas y
el estado de la charla. Responde como un buen vendedor: corto, claro, en español rioplatense con voseo, llevando a la
venta.

- Contesta solo lo que pregunto o pidio. No agregues datos ni opciones que no pidio.
- Vos no sabes precios, stock, envios, totales ni las reglas de la tienda: van en huecos que el sistema llena con el
  dato real. No afirmes nada de lo que dice un hueco —que hay stock, cuanto sale, que es gratis—: lo dice el hueco.
- En un hueco, un producto va como lo nombro el cliente —"G305", "K120 negro"— o por su numero del estado: "mostrado 2",
  "item 1". La clase de producto, solo si no nombro un modelo.
- Lo que senala de la charla —"ese", "el otro", "lo de Rosario"— va por su numero del estado.
- No escribas ningun numero de plata. No inventes productos.
Las clases de producto de la tienda son: {rubros}.
Los temas de las reglas de la tienda son: {temas}."""

CONSIGNA_LIBRE = _REGLAS + """

LOS HUECOS, con sus campos por nombre; los que el cliente no dijo, no van:
  [[PRECIO producto=...]]                          precio y stock
  [[DATO producto=... que=...]]                    un dato de la ficha: inalambrico, peso, dpi
  [[OPCIONES clase=... orden=... cantidad=... condicion=...]]   orden: mas barato, mas caro o mas liviano
  [[AGREGAR producto=... cantidad=... destino=...]]   anota en el pedido; destino: una ciudad
  [[QUITAR item=n]]   [[CAMBIAR item=n cantidad=... destino=... producto=...]]   [[CONFIRMAR item=n]]
  [[ENVIO destino=...]]
  [[TOTAL tope=... pagos=...]]                     pagos como "70 transferencia, 30 mercado pago"
  [[REGLA tema=...]]
  [[COMPATIBLE producto=... equipo=...]]
  [[NO_VENDEMOS clase=...]]"""

CONSIGNA_ATADA = _REGLAS + """

Devolves la respuesta con una marca [[1]], [[2]]... donde va cada dato, y la lista de huecos en ese orden, cada uno con
su tipo y sus campos; los campos que el cliente no dijo, vacios:
  PRECIO producto · DATO producto, que · OPCIONES clase, orden, cantidad, condicion · AGREGAR producto, cantidad,
  destino · QUITAR item · CAMBIAR item y lo que cambia · CONFIRMAR item · ENVIO destino · TOTAL tope, pagos ·
  REGLA tema · COMPATIBLE producto, equipo · NO_VENDEMOS clase."""

TIPOS = ["PRECIO", "DATO", "OPCIONES", "AGREGAR", "QUITAR", "CAMBIAR", "CONFIRMAR", "ENVIO", "TOTAL", "REGLA",
         "COMPATIBLE", "NO_VENDEMOS"]


def formato_atado() -> dict:
    s, n = {"type": "string"}, {"type": "integer"}
    hueco = {"type": "object", "properties": {
        "tipo": {"type": "string", "enum": TIPOS}, "producto": s, "que": s,
        "clase": {"type": "string", "enum": F._rubros(TID) + ["toda la tienda", ""]},
        "orden": {"type": "string", "enum": ["mas barato", "mas caro", "mas liviano", ""]}, "cantidad": n,
        "condicion": s, "destino": s, "item": n, "tope": n, "pagos": {"type": "array", "items": {
            "type": "object", "properties": {"medio": s, "porcentaje": n}, "required": ["medio", "porcentaje"]}},
        "tema": {"type": "string", "enum": F._temas_de(TID) + [""]}, "equipo": s}, "required": ["tipo"]}
    return {"type": "json_schema", "json_schema": {"name": "respuesta", "schema": {"type": "object", "properties": {
        "respuesta": s, "huecos": {"type": "array", "items": hueco}}, "required": ["respuesta", "huecos"]}}}


def _de_atado(s: dict) -> str:
    """La salida atada, al borrador con huecos de campos por nombre: lo mismo que lima el codigo en las dos."""
    def hueco(h):
        campos = []
        for k, v in h.items():
            if k == "tipo" or v in (None, "", [], 0):
                continue
            if k == "pagos":
                v = ", ".join(f"{p.get('porcentaje')} {p.get('medio')}" for p in v)
            if k == "item":
                v = str(v)
            campos.append(f"{k}={v}")
        return f"[[{h.get('tipo')} {' '.join(campos)}]]"
    hs = [h for h in s.get("huecos") or [] if isinstance(h, dict)]
    texto, usados = str(s.get("respuesta") or ""), set()

    def poner(m):
        i = int(m.group(1))
        usados.add(i)
        return hueco(hs[i - 1]) if 0 < i <= len(hs) else ""
    texto = re.sub(r"\[\[\s*(\d+)\s*\]\]", poner, texto)
    return (texto + "".join(f"\n{hueco(h)}" for i, h in enumerate(hs, 1) if i not in usados)).strip()


def _cliente():
    from openai import OpenAI
    from app.config import get_settings
    clave = (_PAGA or os.environ["GEMINI_API_KEY"]).split()[0]
    return OpenAI(api_key=clave, base_url=get_settings().GEMINI_BASE_URL), bool(_PAGA), get_settings().GEMINI_MODEL


def llamar() -> None:
    from banco_pruebas import libro_paga
    cli, paga, modelo = _cliente()
    hechos = {(r["conjunto"], r["id"], r["turno"]) for r in map(json.loads, open(GRABADO, encoding="utf-8"))
              if "error" not in r} if os.path.exists(GRABADO) else set()
    pend = [c for c in HM.casos() if c[:3] not in hechos]
    pend = pend[:HM.HASTA] if HM.HASTA else pend
    sistema = (CONSIGNA_ATADA if ATADO else CONSIGNA_LIBRE if LIBRE else CONSIGNA).format(
        temas=", ".join(F._temas_de(TID)), rubros=", ".join(F._rubros(TID)))
    kw = {"response_format": formato_atado()} if ATADO else {}
    print(f"a pedir {len(pend)} · {'PAGA' if paga else 'gratis'} · {'atado' if ATADO else 'libre' if LIBRE else 'primera'}",
          flush=True)
    for conj, ch, t, msg, est, h, lineas, todo in pend:
        user = (f"ESTADO DE LA CHARLA:\n{CM.carrito(est)}\n\nMENSAJE ORIGINAL: {msg}\n\nSEPARADO:\n"
                + "\n".join(f"{i}. {x.get('texto')}" for i, x in enumerate(lineas, 1)) + (f"\nPARA TODO: {todo}" if todo else ""))
        fila = {"conjunto": conj, "id": ch, "turno": t, "mensaje": msg}
        for intento in range(4):
            try:
                if paga:
                    libro_paga.puede()
                t0 = time.time()
                r = cli.chat.completions.create(model=modelo, temperature=0, **kw, messages=[
                    {"role": "system", "content": sistema}, {"role": "user", "content": user}])
                u = r.usage
                if paga:
                    libro_paga.anotar(modelo, u.prompt_tokens, u.completion_tokens)
                fila.update(seg=round(time.time() - t0, 2), entrada=u.prompt_tokens, salida=u.completion_tokens,
                            crudo=r.choices[0].message.content or "")
                fila["borrador"] = _de_atado(json.loads(fila["crudo"])) if ATADO else fila["crudo"]
                fila.pop("error", None)
                break
            except libro_paga.TopeDiario:
                raise
            except Exception as e:  # noqa: BLE001
                fila["error"] = f"{type(e).__name__}: {str(e)[:160]}"
                if "429" in str(e) and intento >= 1:
                    break
                time.sleep(20 * (intento + 1))
        with open(GRABADO, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
        print(f"  {conj} {ch} t{t}: {len(re.findall(r'\[\[', fila.get('borrador') or ''))} huecos {fila.get('seg')}s "
              f"{fila.get('entrada')}+{fila.get('salida')} {fila.get('error') or ''}", flush=True)
        if "429" in str(fila.get("error")):
            print("SIN CUOTA: se corta", flush=True)
            return


# ══ LIMAR: cada hueco, a una pregunta de la agenda, cumplida sobre el estado ══

_HUECO = re.compile(r"\[\[\s*([A-Z_]+)\s*([^\]]*)\]\]")
_ORDEN = {"mas barato": "mas barato", "mas caro": "mas caro", "mas liviano": "mas liviano", "nada": "nada"}


# Los campos de cada hueco, en orden, para los huecos sin nombre de campo de la primera corrida.
_POSICION = {"PRECIO": ["producto"], "DATO": ["producto", "que"], "OPCIONES": ["clase", "orden", "cantidad", "condicion"],
             "AGREGAR": ["cantidad", "producto", "destino"], "QUITAR": ["item"], "CAMBIAR": ["item", "nuevo"],
             "CONFIRMAR": ["item"], "ENVIO": ["destino"], "TOTAL": ["tope", "pagos"], "REGLA": ["tema"],
             "COMPATIBLE": ["producto", "equipo"], "NO_VENDEMOS": ["clase"]}


def _campos(tipo: str, args: str) -> dict:
    """"producto=G305 que=peso" o "G305 | peso": los campos del hueco por nombre."""
    if re.search(r"\b\w+=", args):
        return {m.group(1): m.group(2).strip().strip("\"'") for m in re.finditer(r"(\w+)=(.*?)(?=\s+\w+=|$)", args)}
    partes = [x.strip() for x in args.strip().strip("|").split("|")]
    return dict(zip(_POSICION.get(tipo, []), partes))


def _item(x: str) -> str:
    m = re.search(r"(\d+)", str(x or ""))
    return f"L-{m.group(1)}" if m else str(x or "")


def _producto(x: str) -> str:
    return CM._ref(K.n(x)) if re.match(r"^\s*(mostrado|item)\s+\d+\s*$", K.n(x)) else str(x or "")


def accion(tipo: str, args: str) -> dict:
    """Un hueco a una pregunta de la agenda. Lo nuestro lo pone el codigo."""
    c = _campos(tipo, args)
    g = lambda k: str(c.get(k) or "").strip()  # noqa: E731
    if tipo == "PRECIO":
        return {"accion": "producto", "producto": _producto(g("producto")), "quiere_saber": "precio"}
    if tipo == "DATO":
        return {"accion": "producto", "producto": _producto(g("producto")), "quiere_saber": g("que") or "precio"}
    if tipo == "OPCIONES":
        cl = g("clase")
        rub = F._rubro(cl, TID, cl if cl in F._rubros(TID) else "") or ("toda la tienda" if not cl or
                                                                        "tienda" in K.n(cl) else cl)
        return {"accion": "buscar", "rubro": rub, "orden": _ORDEN.get(K.n(g("orden")), "nada"),
                "cantidad": K.entero(g("cantidad")) or None, "condiciones": [g("condicion")] if g("condicion") else []}
    if tipo == "AGREGAR":
        return {"accion": "comprar", "agrega": [{k: v for k, v in {"cantidad": K.entero(g("cantidad")) or 1,
                                                                   "producto": _producto(g("producto")),
                                                                   "destino": g("destino")}.items() if v}]}
    if tipo == "QUITAR":
        return {"accion": "comprar", "saca": [_item(g("item"))]}
    if tipo == "CAMBIAR":
        n = g("nuevo")
        lugar = g("destino") or (n if HM.L._lugares(n) else "")
        cant = K.entero(g("cantidad")) or (K.entero(n) if re.fullmatch(r"\s*\d+\s*", n) else None)
        prod = g("producto") or ("" if lugar or cant else n)
        return {"accion": "comprar", "cambia": [{k: v for k, v in {"es": _item(g("item")), "destino": lugar,
                                                                    "cantidad": cant, "producto": _producto(prod),
                                                                    "color": g("color")}.items() if v}]}
    if tipo == "CONFIRMAR":
        return {"accion": "comprar", "confirma": [_item(x) for x in re.split(r",|\by\b", g("item")) if x.strip()]}
    if tipo == "ENVIO":
        return {"accion": "envio", "destino": g("destino")}
    if tipo == "TOTAL":
        pagos = [{"medio": m.group(2).strip(), "porcentaje": int(m.group(1))}
                 for m in re.finditer(r"(\d{1,3})\s*%?\s*([a-z ]+)", K.n(g("pagos")))]
        return {"accion": "cuenta", "tope": K.entero(g("tope")) or HM.L._monto_de(g("tope")) or None, "reparto": pagos}
    if tipo == "REGLA":
        return {"accion": "politica", "tema": g("tema").replace(" ", "_")}
    if tipo == "COMPATIBLE":
        return {"accion": "compatibilidad", "producto": _producto(g("producto")), "con": g("equipo"),
                "falta_modelo": K.identificar(g("equipo"), "", TID)["veredicto"] != "exists"}
    if tipo == "NO_VENDEMOS":
        return {"accion": "buscar", "rubro": (g("clase") or "eso").split()[0], "orden": "nada"}
    return {}


_VACIO = {"", "nada", "ninguno", "ninguna", "-", "carrito", "domicilio", "sin decir"}


def _limpio(q: dict) -> dict:
    """Lo que el modelo dejo de relleno no es un dato: "nada", "carrito". Un destino es un lugar que el padron ubica."""
    def art(a):
        a = {k: v for k, v in a.items() if K.n(v) not in _VACIO}
        if a.get("destino") and not HM.L._lugares(a["destino"]):
            a.pop("destino")
        return a
    q = {k: v for k, v in q.items() if v not in (None, [], "") and (not isinstance(v, str) or K.n(v) not in _VACIO)}
    if "condiciones" in q:
        q["condiciones"] = [c for c in q["condiciones"] if K.n(c) not in _VACIO]
    for k in ("agrega", "cambia"):
        if k in q:
            q[k] = [art(a) for a in q[k]]
    if q.get("accion") == "buscar" and not q.get("rubro"):
        q["rubro"] = "toda la tienda"
    return q


def limar(borrador: str, estado: dict) -> tuple:
    """El borrador con cada hueco lleno. Todos los huecos van en UNA agenda, como un turno: la cuenta ve lo que se
    agrego antes. Cada hecho trae el numero de su pregunta y va a su hueco; lo que no es de ninguno, al final."""
    from app.core.flujo import redaccion
    from app.core.flujo.ejecutor import ejecutar
    huecos = list(_HUECO.finditer(borrador))
    acciones = [_limpio({"n": i, **accion(m.group(1), m.group(2))}) for i, m in enumerate(huecos, 1)]
    ps = [q for q in acciones if q.get("accion")]
    try:
        t = ejecutar({"preguntas": ps, "cliente": {}, "responde": "", "respuesta": "", "dudas": []}, estado, TID)
        por_n = collections.defaultdict(list)
        for h in t.hechos:
            por_n[h.get("n")].append(h)
        textos = {q["n"]: redaccion.texto(por_n.pop(q["n"], []), [], False) for q in ps}
        resto = redaccion.texto([h for hs in por_n.values() for h in hs], t.preguntas, False)
    except Exception as e:  # noqa: BLE001 — un turno que el codigo no puede llenar queda sin datos, no rompe
        textos, resto = {}, f"(sin dato: {type(e).__name__})"
    i = iter(range(1, len(huecos) + 1))
    final = _HUECO.sub(lambda m: textos.get(next(i), ""), borrador)
    return f"{final}\n{resto}".strip(), acciones


def main() -> None:
    from banco_pruebas.agendas58 import AGENDAS, EXPLICAR
    from banco_pruebas.sonda_charlas import nota_casilla
    from app.core.flujo import estado as E
    from app.storage import firestore_client as fc
    interp = HM.C58.instalar()
    grab = {(r["conjunto"], r["id"], r["turno"]): r for r in map(json.loads, open(GRABADO, encoding="utf-8"))
            if "borrador" in r}
    vara = {c["id"]: c for c in json.load(open(os.path.join(AQUI, "vara_58.json"), encoding="utf-8"))["charlas"]}
    nota, tot, toks, filas = collections.Counter(), collections.Counter(), [], []
    for conj, ch, t, msg, est, h, lineas, todo in HM.casos():
        g = grab.get((conj, ch, t))
        previas = list(AGENDAS.get(ch) or [])[:t]
        if not g or len(previas) < t:
            continue
        turnos = vara[ch]["turnos"]
        previos = HM.C58.correr({"id": ch, "turnos": turnos[:t]}, previas, interp, EXPLICAR) if t else []
        estado = E.leer(fc.get_conversation(f"cableado_{ch}", tienda_id=TID) or {}) if t else E.leer({})
        final, acciones = limar(g["borrador"], copy.deepcopy(estado))
        respuestas = [x["respuesta"] for x in previos] + [final]
        malas = [k["n"] for k in turnos[t]["casillas"] if nota_casilla(k, [], final, respuestas) is not True]
        tot[conj] += 1
        nota[conj] += not malas
        toks.append((g["entrada"], g["salida"], g["seg"]))
        filas.append({"conjunto": conj, "id": ch, "turno": t, "msg": msg, "borrador": g["borrador"], "final": final,
                      "acciones": acciones, "malas": malas})
    with open(GRABADO.replace(".jsonl", "_corrida.jsonl"), "w", encoding="utf-8") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    print("\nEL AGENTE DE VENTAS CON HUECOS · casillas del turno")
    for conj in tot:
        print(f"  {conj:16} {nota[conj]} de {tot[conj]}")
    if toks:
        n = len(toks)
        print(f"  tokens por llamada: entrada {sum(x[0] for x in toks) / n:.0f}, salida {sum(x[1] for x in toks) / n:.0f}"
              f" · demora mediana {sorted(x[2] for x in toks)[n // 2]}s")
    for f in filas:
        if f["malas"] and (HM.VER or HM.SOLO):
            print(f"\n{f['id']} t{f['turno']} {f['conjunto']}: {f['msg'][:150]}\n  MAL: {'; '.join(f['malas'])}")
            print("  BORRADOR: " + f["borrador"][:600].replace("\n", "\n  "))
            print("  FINAL: " + f["final"][:600].replace("\n", "\n  "))
    if HM.C58.LLAMADAS_AL_MODELO:
        print(f"ERROR: {len(HM.C58.LLAMADAS_AL_MODELO)} intentos de llamar al modelo")


if __name__ == "__main__":
    llamar() if "--llamar" in HM.ARGS else main()
