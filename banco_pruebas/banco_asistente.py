"""BANCO DEL ASISTENTE — prueba aparte de produccion (26-sep-2026).

La pregunta que contesta: si el ASISTENTE DETERMINISTA existiera —herramientas
que contestan verdad y una libreta con la memoria—, ¿el modelo parte bien el
mensaje, consulta lo que hace falta y contesta cada parte sin inventar?

Las herramientas son SIMULADAS pero leen la fuente real del repo: catalogo,
compatibilidad y FAQ. El envio es una tarifa fija inventada: aca no se mide
la plata del envio, se mide que el modelo lo pregunte.

La nota la pone el codigo, no un juez:
  llamo    cada llamada esperada aparecio, con su dato clave
  numeros  todo numero de plata de la respuesta vino de una herramienta
  dice     la respuesta nombra lo que tiene que nombrar

Corre con la clave GRATIS. Uso:
  python3 -m banco_pruebas.banco_asistente            todos los casos
  python3 -m banco_pruebas.banco_asistente 28 43      solo esos
"""
import csv
import json
import os
import re
import sys
import time
import unicodedata

from openai import OpenAI

D = "data/clientes/verifika_prod/"
PRODUCTOS = list(csv.DictReader(open(D + "productos.csv", encoding="utf-8")))
POR_ID = {p["id"]: p for p in PRODUCTOS}
COMPAT = list(csv.DictReader(open(D + "compatibilidad.csv", encoding="utf-8")))
FAQ = json.load(open(D + "faq.json", encoding="utf-8"))


def _n(t):
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _corto(p):
    return {"id": p["id"], "nombre": p["nombre"], "precio": int(p["precio_ars"]),
            "stock": int(p["stock"] or 0)}


# ══ LAS HERRAMIENTAS, SIMULADAS SOBRE LA FUENTE REAL ═══════════════════════

def buscar(rubro="", texto="", orden="ninguno", marca="", sin_marca="",
           precio_max=0, **_):
    rub = _n(rubro)
    c = [p for p in PRODUCTOS if rub and (rub in _n(p["categoria"])
                                          or _n(p["categoria"]) in rub)]
    if marca:
        c = [p for p in c if _n(p["marca"]) == _n(marca)]
    if sin_marca:
        fuera = {_n(m) for m in re.split(r"[,y ]+", sin_marca) if m}
        c = [p for p in c if _n(p["marca"]) not in fuera]
    if precio_max:
        c = [p for p in c if int(p["precio_ars"]) <= int(precio_max)]
    pal = [w for w in _n(texto).split() if len(w) > 2]

    def puntos(p):
        h = _n(" ".join([p["nombre"], p["tags"], p["caracteristicas_extra"],
                         p["descripcion"]]))
        return sum(w in h for w in pal)
    if pal:
        c = [p for p in c if puntos(p) > 0] or c
    if orden == "mas_barato":
        c.sort(key=lambda p: int(p["precio_ars"]))
    elif orden == "mas_caro":
        c.sort(key=lambda p: -int(p["precio_ars"]))
    else:
        c.sort(key=lambda p: -puntos(p))
    if not c:
        return {"veredicto": "no_hay", "rubro": rubro}
    return {"veredicto": "hay", "total": len(c), "primeros": [_corto(p) for p in c[:3]]}


def producto(nombre="", **_):
    pal = [w for w in _n(nombre).split() if len(w) > 1]
    m = [p for p in PRODUCTOS if pal and all(w in _n(p["nombre"] + " " + p["modelo"])
                                             for w in pal)]
    if not m:
        return {"veredicto": "not_found", "buscado": nombre}
    modelos = {p["marca"] + " " + p["modelo"] for p in m}
    if len(modelos) > 1:
        return {"veredicto": "ambiguous", "opciones": sorted(modelos)[:6]}
    p0 = m[0]
    return {"veredicto": "exists", "modelo": p0["marca"] + " " + p0["modelo"],
            "variantes": [_corto(p) for p in m],
            "ficha": {"descripcion": p0["descripcion"][:300],
                      "caracteristicas": p0["caracteristicas_extra"],
                      "garantia_meses": p0["garantia_meses"],
                      "origen": p0["origen"]}}


def compatibilidad(producto_nombre="", con="", **_):
    r = producto(producto_nombre)
    if r["veredicto"] != "exists":
        return r
    mod = r["modelo"]
    fila = next((f for f in COMPAT if _n(f["marca"] + " " + f["modelo"]) == _n(mod)), None)
    if not fila:
        return {"veredicto": "sin_dato", "producto": mod}
    return {"producto": mod, "conecta_por": fila["conecta_por"],
            "anda_con": fila["plataformas"].split("|"),
            "no_compatible": fila["no_compatible"], "nota": fila["nota"],
            "pedido": con}


def envio(lugar="", **_):
    caba = any(w in _n(lugar) for w in ("caba", "capital", "buenos aires", "gba"))
    return {"lugar": lugar, "costo": 6500 if caba else 9800,
            "plazo": "2 a 3 dias habiles" if caba else "3 a 6 dias habiles"}


def tienda(tema="", **_):
    q = _n(tema)
    mejor = max(FAQ, key=lambda f: sum(_n(k) in q or q in _n(k)
                                       for k in f["keywords"] + [f["tema"]]))
    if not any(_n(k) in q or q in _n(k) for k in mejor["keywords"] + [mejor["tema"]]):
        return {"veredicto": "no_esta_escrito", "tema": tema}
    return {"tema": mejor["tema"], "respuesta": mejor.get("respuesta_curada")
            or mejor["respuesta"]}


def calcular(items=None, reparto=None, **_):
    filas, total = [], 0
    for it in items or []:
        p = POR_ID.get(it.get("id", ""))
        if not p:
            filas.append({"id": it.get("id"), "error": "id desconocido"})
            continue
        sub = int(p["precio_ars"]) * int(it.get("cantidad", 1) or 1)
        total += sub
        filas.append({"id": p["id"], "nombre": p["nombre"],
                      "cantidad": it.get("cantidad", 1), "subtotal": sub})
    out = {"items": filas, "total": total}
    if reparto:
        out["reparto"] = [{"medio": r["medio"],
                           "monto": round(total * float(r["porcentaje"]) / 100)}
                          for r in reparto]
    return out


def comprar(id="", cantidad=1, **_):
    p = POR_ID.get(id)
    if not p:
        return {"veredicto": "id desconocido"}
    if int(p["stock"] or 0) < int(cantidad):
        return {"veredicto": "sin_stock_suficiente", "stock": int(p["stock"] or 0)}
    return {"veredicto": "reservado", "id": id, "cantidad": cantidad,
            "falta": "el nombre del cliente para cerrar"}


CUERPOS = {"buscar": buscar, "producto": producto, "compatibilidad": compatibilidad,
           "envio": envio, "tienda": tienda, "calcular": calcular, "comprar": comprar}


def _f(nombre, desc, props, req):
    return {"type": "function", "function": {
        "name": nombre, "description": desc,
        "parameters": {"type": "object", "properties": props, "required": req}}}


S = {"type": "string"}
TOOLS = [
    _f("buscar", "Busca productos de la tienda. Devuelve los primeros tres con id, precio y stock.",
       {"rubro": {"type": "string", "description": "notebook, mouse, teclado, monitor, auriculares, parlante, etc."},
        "texto": {"type": "string", "description": "condiciones con palabras simples: inalambrico, 16gb, rgb"},
        "orden": {"type": "string", "enum": ["mas_barato", "mas_caro", "ninguno"]},
        "marca": S, "sin_marca": {"type": "string", "description": "marcas a excluir"},
        "precio_max": {"type": "integer"}}, ["rubro"]),
    _f("producto", "La ficha de UN producto por su nombre o modelo: exists, ambiguous o not_found.",
       {"nombre": S}, ["nombre"]),
    _f("compatibilidad", "Con que equipos anda un producto.",
       {"producto_nombre": S, "con": {"type": "string", "description": "el equipo del cliente"}},
       ["producto_nombre"]),
    _f("envio", "Costo y plazo del envio a una localidad.", {"lugar": S}, ["lugar"]),
    _f("tienda", "Politicas de la tienda: pagos, cuotas, garantia, factura, devoluciones, descuentos, mayoristas.",
       {"tema": S}, ["tema"]),
    _f("calcular", "Suma productos por id y cantidad, y reparte el pago por porcentaje.",
       {"items": {"type": "array", "items": {"type": "object", "properties": {
           "id": S, "cantidad": {"type": "integer"}}, "required": ["id", "cantidad"]}},
        "reparto": {"type": "array", "items": {"type": "object", "properties": {
            "medio": S, "porcentaje": {"type": "number", "description": "de 0 a 100: 70 es setenta por ciento"}}, "required": ["medio", "porcentaje"]}}},
       ["items"]),
    _f("comprar", "Reserva un producto por id. Solo cuando el cliente dice que lo compra.",
       {"id": S, "cantidad": {"type": "integer"}}, ["id", "cantidad"]),
]

SISTEMA = """Sos el vendedor de una tienda online de tecnologia de Argentina. Hablas en espanol argentino, con voseo, corto y claro.

COMO TRABAJAS:
1. Parti el mensaje en partes: una por cada cosa que pregunta, pide o cuenta.
2. Cada dato de la tienda —productos, precios, stock, envios, politicas, cuentas— lo sacas SOLO de las herramientas. Nunca lo escribas de memoria. Podes llamar varias herramientas a la vez.
3. Lo que el cliente da por cierto sobre la tienda o un producto, verificalo con una herramienta antes de aceptarlo. Si es falso, decilo con amabilidad.
4. Si una parte depende de otra ("si no hay", "si anda", "si pasa de"), consulta la primera, mira el resultado y segui.
5. "Ese", "el otro", "el segundo", "lo mismo" y los datos que el cliente dijo antes estan en la LIBRETA. Usala antes de preguntar.
6. Si algo es ambiguo y la libreta no lo resuelve, hace UNA sola pregunta corta.
7. El saber general de tecnologia lo explicas vos, sin herramienta.
8. Contesta TODAS las partes, en el orden del mensaje. Sin repetir."""


# ══ LOS CASOS ═══════════════════════════════════════════════════════════════
# llamo: [herramienta, argumento, texto que tiene que contener]; una lista
#        adentro es "alguna de estas". dice: textos que la respuesta nombra.
#        nada: no deberia llamar herramientas.

L_G305 = ("productos vistos: 1) MOU0029 Mouse Logitech G305 Lightspeed Negro, 80500. "
          "2) MOU0001 Mouse Logitech G203 Lightsync Negro, 37500. Ultima lista: esos dos.")
L_MUCHO = ("productos vistos: 1) TEC0029 Teclado Logitech K120 Negro, 14500, turno 1. "
           "2) AUR0013 Auriculares JBL Tune 510BT Negro, 78000, turno 4. "
           "3) MOU0029 Mouse Logitech G305 Lightspeed Negro, 80500, turno 8. Ultima lista: el 3.")

CASOS = [
    (1, "tenes el G305?", "", [["producto", "nombre", "g305"]], ["G305"]),
    (2, "que parlantes tenes?", "", [["buscar", "rubro", "parlante"]], []),
    (3, "cuantos dpi tiene el g502 hero?", "", [["producto", "nombre", "g502"]], []),
    (4, "el K120, que es inalambrico, cuanto sale?", "", [["producto", "nombre", "k120"]], ["14.500|14500"]),
    (7, "un mouse que no sea genius", "", [["buscar", "sin_marca", "genius"]], []),
    (9, "el monitor mas barato", "", [["buscar", "orden", "mas_barato"]], []),
    (10, "cuanto sale el envio a posadas?", "", [["envio", "lugar", "posadas"]], ["9.800|9800"]),
    (11, "hacen factura A?", "", [["tienda", "tema", "factura"]], []),
    (12, "tienen 50 por ciento off en todo, no?", "", [["tienda", "tema", ["descuento", "promo", "off"]]], []),
    (14, "que conviene, ddr4 o ddr5?", "", [], [], ),
    (16, "me llevo el K120 negro, pago 70 transferencia y 30 mercado pago", "",
     [["calcular", "reparto", "70"]], []),
    (17, "cuanto sale el G305 y que teclados mecanicos tenes?", "",
     [["producto", "nombre", "g305"], ["buscar", "rubro", "teclado"]], ["G305"]),
    (18, "tenes auriculares jbl y cuanto sale mandarlos a cordoba?", "",
     [["buscar", "rubro", "auricular"], ["envio", "lugar", "cordoba"]], []),
    (20, "sumame dos K120 y un G203", "", [["calcular", "items", "TEC0029|TEC0030"]], []),
    (23, "necesito un aparato rectangular con teclas y dada la crisis dame uno acorde", "",
     [["buscar", "rubro", "teclado"]], []),
    (24, "teclado y mouse, lo mas barato posible los dos", "",
     [["buscar", "rubro", "teclado"], ["buscar", "rubro", "mouse"]], []),
    (26, "mandame un G203 a rosario y otro a mendoza, cuanto sale cada envio?", "",
     [["envio", "lugar", "rosario"], ["envio", "lugar", "mendoza"]], []),
    (28, "si no hay G502 hero en negro, pasame el G305", "",
     [["producto", "nombre", "g502"]], ["G305"]),
    (29, "si el G305 anda con mac, me lo llevo", "",
     [["compatibilidad", "producto_nombre", "g305"]], []),
    (31, "sumame un MX Master 3S negro y dos G305 negro, si pasa de 300 mil saca el MX", "",
     [["calcular", "items", "MOU0007|MOU0029"]], []),
    (32, "entre el G305 y el G203, cual tiene mas bateria? dame ese", "",
     [["producto", "nombre", "g305"], ["producto", "nombre", "g203"]], []),
    (33, "quiero un teclado redragon, ah no mejor logitech", "",
     [["buscar", "marca", "logitech"]], []),
    (34, "me equivoque, era para cordoba no rosario, cuanto sale?",
     "destino vigente: Rosario. " + L_G305, [["envio", "lugar", "cordoba"]], []),
    (35, "ya no importa la marca, pasame mas opciones",
     "condiciones vigentes: rubro mouse, marca logitech, inalambrico.",
     [["buscar", "rubro", "mouse"]], []),
    (36, "el G305 anda con mi ps5?", "", [["compatibilidad", "producto_nombre", "g305"]], []),
    (38, "le sirve a mi pc?", L_G305, [], []),
    (39, "el G203 es inalambrico, no? lo quiero para viajar", "",
     [["producto", "nombre", "g203"]], []),
    (41, "soy revendedor, tienen precio mayorista?", "",
     [["tienda", "tema", ["mayorista", "revend"]]], []),
    (43, "cuanto sale el segundo?", L_G305, [], ["37.500|37500"]),
    (44, "y el otro?", "productos vistos: 1) MOU0029 G305 Negro, 80500. 2) MOU0001 G203 Negro, 37500. "
     "Ultimo del que se hablo: el 1.", [["producto", "nombre", "g203"]], ["G203"]),
    (45, "y en blanco?", "condiciones vigentes: rubro mouse, marca logitech. " + L_G305,
     [["*", "*", "blanco"]], []),
    (47, "mandamelo a casa", "cliente: dijo que vive en Posadas, Misiones. " + L_G305
     + " Ultimo del que se hablo: el 1.", [["envio", "lugar", "posadas"]], []),
    (49, "el teclado ese que vimos al principio, cuanto era?", L_MUCHO, [], ["14.500|14500"]),
    (50, "el primero", "pendiente: le preguntaste al cliente cual de los dos queria, el G305 o el G203, "
     "porque dijo 'me llevo uno'. " + L_G305, [["comprar", "id", "MOU0029"]], []),
    (52, "y ese cuanto?", "productos vistos: 1) MOU0029 G305 Negro. 2) TEC0029 K120 Negro. "
     "3) AUR0013 JBL Tune 510BT Negro. Los tres en el mismo turno, ninguno elegido.", [], []),
    (53, "del que me dijiste antes, si no hay en negro dame el blanco", "productos vistos: "
     "1) MOU0003 Mouse Logitech G502 Hero Negro, 70000. Ultimo del que se hablo: el 1.",
     [["producto", "nombre", "g502"]], ["blanco"]),
    (55, "ah no, el otro, y ese me lo llevo", "productos vistos: 1) MOU0029 G305 Negro, 80500. "
     "2) MOU0001 G203 Negro, 37500. Ultimo del que se hablo: el 1.",
     [["comprar", "id", "MOU0001"]], []),
    (56, "tienen 50 off no? entonces si el K120 sale menos de 20 mil llevo dos", "",
     [["tienda", "tema", ["descuento", "promo", "off"]], ["producto", "nombre", "k120"]], []),
    (57, "cual es la capital de francia?", "", [], []),
    (58, "jaja buenisimo gracias crack, che y el G305 tiene garantia?", "",
     [["producto", "nombre", "g305"]], []),
]


# ══ LA CORRIDA ══════════════════════════════════════════════════════════════

def _cliente():
    from app.config import get_settings
    return OpenAI(api_key=os.environ["GEMINI_API_KEY"],
                  base_url=get_settings().GEMINI_BASE_URL), get_settings().GEMINI_MODEL


def _llamar(cli, modelo, msgs):
    for intento in range(5):
        try:
            return cli.chat.completions.create(model=modelo, messages=msgs, tools=TOOLS,
                                               tool_choice="auto", temperature=0.2)
        except Exception as e:  # noqa: BLE001 — la gratis devuelve 429: se aguanta
            if "429" in str(e) or "503" in str(e):
                time.sleep(8 * (intento + 1))
                continue
            raise
    raise RuntimeError("cuota agotada")


def correr(caso, cli, modelo):
    num, msg, libreta, esperadas, dice = caso
    sistema = SISTEMA + ("\n\nLIBRETA:\n" + libreta if libreta else "\n\nLIBRETA: vacia.")
    msgs = [{"role": "system", "content": sistema}, {"role": "user", "content": msg}]
    llamadas, vistos, t0, tok = [], libreta, time.time(), 0
    for vuelta in range(4):
        r = _llamar(cli, modelo, msgs)
        tok += r.usage.total_tokens if r.usage else 0
        m = r.choices[0].message
        if not m.tool_calls:
            break
        msgs.append({"role": "assistant", "content": m.content or "",
                     "tool_calls": [c.model_dump() for c in m.tool_calls]})
        for c in m.tool_calls:
            args = json.loads(c.function.arguments or "{}")
            out = CUERPOS[c.function.name](**args)
            llamadas.append((vuelta + 1, c.function.name, args))
            vistos += json.dumps(out, ensure_ascii=False)
            msgs.append({"role": "tool", "tool_call_id": c.id,
                         "content": json.dumps(out, ensure_ascii=False)})
    texto = m.content or ""
    return nota(caso, llamadas, vistos, texto) + (llamadas, texto, time.time() - t0, tok)


def _contiene(valor, quiero):
    v = _n(json.dumps(valor, ensure_ascii=False))
    opciones = quiero if isinstance(quiero, list) else [quiero]
    return any(_n(o) in v for q in opciones for o in q.split("|"))


def nota(caso, llamadas, vistos, texto):
    num, msg, libreta, esperadas, dice = caso
    fallas = []
    for herr, arg, quiero in esperadas:
        if not any(herr in ("*", n) and _contiene(a if arg == "*" else a.get(arg, ""), quiero)
                   for _, n, a in llamadas):
            fallas.append(f"falto {herr}({arg}~{quiero})")
    if not esperadas and num in (14, 57, 52) and llamadas:
        fallas.append("llamo sin necesidad")
    sinpunto = re.sub(r"(\d)\.(\d{3})", r"\1\2", texto)
    visto = re.sub(r"\D+", " ", vistos).split()
    for cifra in re.findall(r"\$\s?(\d{4,})", sinpunto):
        if cifra not in visto:
            fallas.append(f"numero no visto ${cifra}")
    for d in dice:
        if not any(_n(o) in _n(texto) for o in d.split("|")):
            fallas.append(f"no dice {d}")
    if not texto.strip():
        fallas.append("respuesta vacia")
    return (not fallas, fallas)


def main():
    pedidos = {int(a) for a in sys.argv[1:]}
    cli, modelo = _cliente()
    casos = [c for c in CASOS if not pedidos or c[0] in pedidos]
    ok, filas = 0, []
    for caso in casos:
        bien, fallas, llamadas, texto, seg, tok = correr(caso, cli, modelo)
        ok += bien
        filas.append({"caso": caso[0], "ok": bien, "fallas": fallas, "seg": round(seg, 1),
                      "tokens": tok, "vueltas": max([v for v, _, _ in llamadas] or [0]),
                      "llamadas": [f"{n}{json.dumps(a, ensure_ascii=False)}" for _, n, a in llamadas],
                      "mensaje": caso[1], "respuesta": texto})
        print(f"{'OK ' if bien else 'MAL'} {caso[0]:>2} {seg:4.1f}s {tok:5}t  "
              + ("; ".join(fallas) if fallas else ""), flush=True)
    print(f"\n{modelo}: {ok} de {len(casos)} casos")
    with open("banco_pruebas/banco_asistente_ultima.json", "w", encoding="utf-8") as f:
        json.dump(filas, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
