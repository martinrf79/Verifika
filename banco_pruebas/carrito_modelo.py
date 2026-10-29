"""EL CARRITO — la segunda llamada con herramientas de asistente de compras, y el codigo que las lleva a la agenda
(28-oct-2026, FICHA 83).

Pedido de Martin del 28-oct. En `herramientas_modelo.py` el modelo usa su entrenamiento solo en la forma: llama
funciones, pero cada herramienta y cada argumento son nuestro menu, con nuestros significados —lo supuesto, el orden
para todo, los numeros L y M, depende_de contado por llamada—, y falla justo ahi. Aca se le dan herramientas cuyo
significado ya conoce, las de cualquier asistente de compras, y el estado como un carrito:

  las herramientas  buscar_productos, ver_producto, agregar_al_carrito, quitar_del_carrito, cambiar_item,
                    confirmar_carrito, vaciar_carrito, reelegir_carrito, cotizar_envio, presupuesto, politica,
                    compatibilidad, saber_general, no_vendemos, preguntar_al_cliente, responder_pregunta, conversacion.
  el estado         el carrito con sus items, lo ultimo que se mostro numerado y lo que pregunto el vendedor, en
                    palabras; reemplaza a la libreta con sus M, L, R y ABIERTO.
  el adaptador      `a_agenda`: cada llamada estandar a la agenda que cumple el ejecutor. Lo nuestro lo resuelve el
                    codigo: item 2 es L-2, mostrado 1 es M-1, confirmar es confirma o acepta segun el renglon.

La entrada de lineas y candidatos, los casos y la vara son los de `herramientas_modelo.py`.

    python3 banco_pruebas/carrito_modelo.py --llamar [--hasta 10]      con la gratis
    python3 banco_pruebas/carrito_modelo.py [--ver]                     sin modelo
"""
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
# LA ORDEN DE LA PAGA SE LEE ANTES DEL CLON, que la saca del entorno: si no, la corrida sale con la gratis sin decirlo.
_PAGA = os.environ.get("GEMINI_API_KEY_PROD") if os.environ.get("MARTIN_AUTORIZO_LA_PAGA") else None
import herramientas_modelo as HM  # noqa: E402


def _cliente():
    from openai import OpenAI
    from app.config import get_settings
    clave = (_PAGA or os.environ["GEMINI_API_KEY"]).split()[0]
    return OpenAI(api_key=clave, base_url=get_settings().GEMINI_BASE_URL), bool(_PAGA), get_settings().GEMINI_MODEL


HM._cliente = _cliente
from app.core.flujo import borrador as B  # noqa: E402
from app.core.flujo import catalogo as K  # noqa: E402
from app.core.flujo import ficha as F  # noqa: E402
from app.core.flujo import interprete  # noqa: E402

TID = HM.TID
HM.GRABADO = os.path.join(AQUI, "carrito_modelo.jsonl")

HM.CONSIGNA = """Sos el asistente de compras de una tienda online de tecnologia de Argentina que vende por WhatsApp. En
este paso no le escribis al cliente: llamas a las herramientas de la tienda que hacen falta para poder contestarle su
ultimo mensaje. La tienda pone todos los precios, el stock, los envios y los totales.

- Llama todas las herramientas que hagan falta en una sola respuesta, en el orden del mensaje.
- Solo lo que pide el ultimo mensaje: lo que ya esta en el carrito o ya se mostro, se nombra por su numero.
- Si pide "el mas barato", "el mejor" o una clase de producto sin modelo, busca la clase: el producto lo elige la
  tienda.
- Lo que depende de otra cosa —"si hay", "si no", "si sale menos de"— lleva solo_si con el numero de la llamada de la
  que depende, contando desde 1.
- En cada llamada, "cita": las palabras literales del cliente.

LA TIENDA. Categorias: {rubros}. Temas de politica: {temas}.{reglas}"""

_T, _N, _B = {"type": "string"}, {"type": "integer"}, {"type": "boolean"}
_SI = {"type": "object", "properties": {"llamada": _N, "resultado": {"type": "string", "enum": ["si", "no"]}},
       "required": ["llamada", "resultado"]}
_ITEM = {"type": "object", "properties": {"producto": _T, "cantidad": _N, "color": _T, "envio_a": _T}}
_PAGOS = {"type": "array", "items": {"type": "object", "properties": {"medio": _T, "porcentaje": _N},
                                     "required": ["medio", "porcentaje"]}}
ORDENES = {"precio_menor": "mas barato", "precio_mayor": "mas caro", "peso_menor": "mas liviano",
           "peso_mayor": "mas pesado", "ninguno": "nada"}


def herramientas(productos: list, refs: list) -> list:
    cats = F._rubros(TID) + ["toda la tienda"]
    mostrados = [f"mostrado {r[2:]}" for r in refs if r.startswith("M-")]
    items = [f"item {r[2:]}" for r in refs if r.startswith("L-")] or ["ninguno"]
    lista = list(dict.fromkeys(productos + mostrados)) or ["ninguno"]

    def h(nombre, desc, props, req=()):
        return {"type": "function", "function": {"name": nombre, "description": desc, "parameters": {
            "type": "object", "properties": {**props, "cita": _T, "solo_si": _SI}, "required": ["cita", *req]}}}
    lista_items = {"type": "array", "items": {"type": "string", "enum": items}}
    return [
        h("buscar_productos", "busca productos de una categoria, con orden y filtros",
          {"categoria": {"type": "string", "enum": cats}, "cantidad": _N,
           "orden": {"type": "string", "enum": list(ORDENES)}, "filtros": {"type": "array", "items": _T},
           "excluir": {"type": "array", "items": _T}, "solo_entre_lo_mostrado": _B}, ["categoria"]),
        h("ver_producto", "precio, stock o un dato de un producto", {
            "producto": {"type": "string", "enum": lista}, "pregunta": _T, "color": _T}, ["producto"]),
        h("agregar_al_carrito", "agrega productos al carrito: un modelo, un mostrado o una categoria",
          {"items": {"type": "array", "items": _ITEM}}, ["items"]),
        h("quitar_del_carrito", "saca items del carrito", {"items": lista_items}, ["items"]),
        h("cambiar_item", "cambia un item del carrito", {"item": {"type": "string", "enum": items}, **_ITEM["properties"]},
          ["item"]),
        h("confirmar_carrito", "el cliente dice que si a items del carrito", {"items": lista_items}, ["items"]),
        h("vaciar_carrito", "el cliente rehace el pedido: lo que agregue despues es como queda", {}),
        h("reelegir_carrito", "cambia todos los productos del carrito por otro orden", {
            "orden": {"type": "string", "enum": list(ORDENES)}}, ["orden"]),
        h("cotizar_envio", "lo que sale mandar a un lugar", {"destino": _T}, ["destino"]),
        h("presupuesto", "el total del carrito, con el tope y como paga", {
            "tope": _N, "quitar_si_pasa": _T, "pagos": _PAGOS, "total_de_articulos": _N}),
        h("politica", "una regla de la tienda", {"tema": {"type": "string", "enum": F._temas_de(TID)}, "afirma": _T},
          ["tema"]),
        h("compatibilidad", "si un producto anda con un equipo", {"producto": _T, "equipo": _T}, ["producto"]),
        h("saber_general", "una pregunta de tecnologia que no es de la tienda", {"pregunta": _T}, ["pregunta"]),
        h("no_vendemos", "la categoria que pide no esta en la tienda", {"categoria": _T}, ["categoria"]),
        h("preguntar_al_cliente", "lo que hay que preguntarle para poder seguir", {"pregunta": _T}, ["pregunta"]),
        h("responder_pregunta", "el cliente contesta una pregunta del vendedor", {
            "pregunta": {"type": "string", "enum": [f"pregunta {r[2:]}" for r in refs if r.startswith("R-")] or
                         ["ninguna"]}}, ["pregunta"]),
        h("conversacion", "saludo, un dato suyo, pedir una persona, algo fuera de tema o ver las categorias", {
            "que": {"type": "string", "enum": ["saludo", "dato", "humano", "fuera_de_tema", "categorias"]},
            "nombre": _T, "localidad": _T}, ["que"]),
    ]


# ══ EL ESTADO COMO CARRITO ═══════════════════════════════════════════════════

def carrito(est: dict) -> str:
    todos = K.productos(TID)
    nums = interprete.numeros(est)
    r = []
    b = B.leer(est.get("borrador"))
    res = B.resolver(b, TID) if b["renglones"] else []
    faltas = {x["L"]: x["falta"] for x in B.faltantes(b, res) if x.get("L")}
    if res:
        r.append("CARRITO:")
        for x in res:
            g = x["renglon"]
            pedido = f"{g['cantidad'] or ''} {g['que']}".strip() + (f" {g['color']}" if g["color"] else "") \
                + f", envio a {g['destino'] or 'sin decir'}"
            if x.get("no_aplica"):
                hoy = "no va, no se cumplio la condicion"
            elif x.get("supuesto"):
                hoy = f"sin confirmar: {x['supuesto']['texto']}"
            elif x["L"] in faltas:
                hoy = f"falta {faltas[x['L']]}"
            else:
                hoy = ", ".join(f"{a['cantidad']} {a['nombre']}" for a in x.get("articulos") or [])
            r.append(f"  item {x['L'][2:]}: {pedido} -> {hoy}")
    for k, v in (("dijo que son", b["total"]), ("tope del total", b["tope"])):
        if v:
            r.append(f"{k}: {v}")
    if b["pago"]:
        r.append("paga: " + ", ".join(f"{p['medio']} {p['porcentaje']}%" for p in b["pago"]))
    vistos = [(k, K.por_id(v, TID)) for k, v in nums.items() if k.startswith("M-") and isinstance(v, str)]
    if vistos:
        r.append("LO QUE LE MOSTRASTE:")
        r += [f"  mostrado {k[2:]}: {interprete.datos(p, todos)[:200]}" for k, p in vistos if p]
    abiertas = [(k, v) for k, v in nums.items() if k.startswith("R-")]
    if abiertas:
        r.append("LO QUE LE PREGUNTO EL VENDEDOR:")
        r += [f'  pregunta {k[2:]}: "{v["texto"]}"' for k, v in abiertas]
    return "\n".join(r) or "Charla nueva: carrito vacio, nada mostrado."


def entrada(msg: str, est: dict, h: list, lineas: list, todo: str, ind) -> tuple:
    texto, nombres = HM.candidatos(lineas, ind)
    refs = list(interprete.numeros(est))
    user = (f"{carrito(est)}\n\nULTIMO MENSAJE DEL CLIENTE: {msg}\n\nEL MENSAJE SEPARADO, CON LO QUE TRAJO LA BUSQUEDA:\n"
            f"{texto}" + (f"\nPARA TODO: {todo}" if todo else ""))
    return user, herramientas(nombres, refs)


# ══ EL ADAPTADOR: de las llamadas estandar a la agenda ═══════════════════════

def _ref(x) -> str:
    """"mostrado 2" es M-2, "item 1" es L-1, "pregunta 1" es R-1; lo demas queda como lo dijo."""
    m = re.match(r"^\s*(mostrado|item|pregunta)\s+(\d+)\s*$", str(x or ""))
    return f"{'MLR'['mostrado item pregunta'.split().index(m.group(1))]}-{m.group(2)}" if m else str(x or "")


def _art(it: dict) -> dict:
    return {k: v for k, v in {"producto": _ref(it.get("producto")), "cantidad": it.get("cantidad"),
                              "color": it.get("color"), "destino": it.get("envio_a")}.items() if v not in (None, "")}


def a_agenda(llamadas: list, est: dict = None) -> dict:
    ps, dudas, cliente, responde = [], [], {}, ""
    supuestos = set()
    if est is not None:
        b = B.leer(est.get("borrador"))
        supuestos = {x["L"] for x in (B.resolver(b, TID) if b["renglones"] else []) if x.get("supuesto")}
    vacia = any(c["nombre"] == "vaciar_carrito" for c in llamadas)
    de = {}
    for i, c in enumerate(llamadas, 1):
        a, n = dict(c["args"]), c["nombre"]
        si = a.pop("solo_si", None)
        q = {"cita": a.get("cita")}
        if n == "buscar_productos":
            q.update(accion="buscar", rubro=a.get("categoria"), cantidad=a.get("cantidad"),
                     orden=ORDENES.get(a.get("orden"), "nada"),
                     condiciones=list(a.get("filtros") or []) + [f"que no sea {x}" for x in a.get("excluir") or []],
                     entre_lo_mostrado=bool(a.get("solo_entre_lo_mostrado")))
        elif n == "ver_producto":
            q.update(accion="producto", producto=_ref(a.get("producto")), quiere_saber=a.get("pregunta") or "precio",
                     color=a.get("color"))
        elif n == "agregar_al_carrito":
            q.update(accion="comprar", agrega=[_art(x) for x in a.get("items") or []], reemplaza=vacia)
        elif n == "quitar_del_carrito":
            q.update(accion="comprar", saca=[_ref(x) for x in a.get("items") or []])
        elif n == "cambiar_item":
            q.update(accion="comprar", cambia=[{"es": _ref(a.get("item")), **_art(a)}])
        elif n == "confirmar_carrito":
            ls = [_ref(x) for x in a.get("items") or []]
            q.update(accion="comprar", confirma=[x for x in ls if x not in supuestos],
                     acepta=[x for x in ls if x in supuestos])
        elif n == "vaciar_carrito":
            continue
        elif n == "reelegir_carrito":
            q.update(accion="buscar", rubro="el pedido", orden=ORDENES.get(a.get("orden"), "nada"))
        elif n == "cotizar_envio":
            q.update(accion="envio", destino=a.get("destino"))
        elif n == "presupuesto":
            q.update(accion="cuenta", tope=a.get("tope"), si_pasa=_ref(a.get("quitar_si_pasa")), reparto=a.get("pagos"))
            if a.get("total_de_articulos"):
                ps.append({"n": len(ps) + 1, "cita": a.get("cita"), "accion": "comprar", "total": a["total_de_articulos"]})
        elif n == "politica":
            q.update(accion="politica", tema=a.get("tema"), afirma=a.get("afirma"))
        elif n == "compatibilidad":
            con = str(a.get("equipo") or "")
            q.update(accion="compatibilidad", producto=_ref(a.get("producto")), con=con,
                     falta_modelo=K.identificar(con, "", TID)["veredicto"] != "exists")
        elif n == "saber_general":
            q.update(accion="explicar", pregunta=a.get("pregunta"))
        elif n == "no_vendemos":
            q.update(accion="buscar", rubro=a.get("categoria"), orden="nada")
        elif n == "preguntar_al_cliente":
            dudas.append(a.get("pregunta") or "")
            continue
        elif n == "responder_pregunta":
            responde = _ref(a.get("pregunta"))
            continue
        elif n == "conversacion":
            que = {"categorias": "catalogo"}.get(a.get("que"), a.get("que"))
            cliente.update({k: a[k] for k in ("nombre", "localidad") if a.get(k)})
            q.update(accion="otro", que=que)
        else:
            continue
        q = {"n": len(ps) + 1, **{k: v for k, v in q.items() if v not in (None, "", [])}}
        de[i] = q["n"]
        if si and de.get(K.entero(si.get("llamada"))):
            q["si"] = {"de": de[K.entero(si["llamada"])], "da": si.get("resultado") or "si"}
        ps.append(q)
    return {"preguntas": ps, "cliente": cliente, "responde": responde, "respuesta": "", "dudas": dudas}


HM.entrada = entrada
HM.a_agenda = a_agenda

if __name__ == "__main__":
    HM.llamar() if "--llamar" in HM.ARGS else HM.main()
