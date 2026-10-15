"""POR EL CODIGO — lo que el modelo YA entendio, pasado por el codigo real del turno, sin modelo (15-oct-2026).

Pedido de Martin: las respuestas buenas del modelo ya estan guardadas. Se toman, se pasan por las herramientas de
produccion —buscar, producto, compatibilidad, politica, envio, cuenta, la memoria de la charla— y se mira si lo que
el codigo entrega es lo correcto escrito en el caso. Como el modelo ya habia entendido bien, una falla de aca es del
codigo, o de la traduccion de la ficha a lo que el codigo consume. No gasta cuota, y da lo mismo cada vez que corre.

LA ENTRADA: la ficha 9 llena de una corrida guardada en `ficha_casillas_corridas.jsonl`.
LA TRADUCCION: `ficha_a_piezas`, la ficha llena a las piezas que consume `tablero.correr_piezas`. Las condiciones
de una busqueda vienen en palabras del cliente y el buscador filtra por campo: se pasan a campo con el vocabulario
del catalogo —un valor real de un campo nombrado en la condicion—, nunca con una lista escrita aca.
LA SALIDA: las llamadas a herramientas que hizo el codigo y lo que devolvio cada una. Se mide con el mismo corrector
del desmenuzado, sobre lo que el codigo PIDIO a cada herramienta y lo que la herramienta RESOLVIO.

  python3 banco_pruebas/nexos/por_el_codigo.py --de f9_g174
  python3 banco_pruebas/nexos/por_el_codigo.py --de f9_g174 --casos X01 --ver
"""
import argparse, json, os, re, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.dirname(os.path.dirname(AQUI)))
import desmenuzado as D  # noqa: E402
import ficha_casillas as F  # noqa: E402

SALIDA = os.path.join(AQUI, "por_el_codigo_corridas.jsonl")


def _lista(x):
    return x if isinstance(x, list) else ([x] if x not in (None, "", {}) else [])


def _n(s) -> str:
    return D.n(str(s or ""))


# ══ LA TRADUCCION: la ficha llena a piezas ═════════════════════════════════

_NIEGA = re.compile(r"\b(no|sin|ni|evit\w*|exclu\w*|menos|salvo|excepto|fuera)\b")
_TOPE = re.compile(r"\b(hasta|menos de|maximo|no (?:mas|pase) de|tope|debajo de|por debajo de)\b\D{0,4}([\d.,]+)\s*(k|mil|lucas)?")


def _palabra_en(valor: str, texto: str) -> bool:
    return bool(re.search(r"(?<![a-z0-9])" + re.escape(valor) + r"(?![a-z0-9])", texto))


def condiciones_de(textos: list, tienda_id: str) -> tuple:
    """(condiciones por campo, lo que queda en palabras). Un valor ENUMERADO de un campo del catalogo que aparece
    entero en la condicion es ese campo; si la condicion lo niega, no_contiene. Un tope de plata es precio_ars menor.
    Lo que no nombra ningun valor —"para programar", "que llegue a toda la casa"— queda como texto de la busqueda."""
    from app.core.filtros_catalogo import vocabulario
    # Los campos de si o no no se nombran con su valor —"no, este modelo es con cable"— y un valor de dos letras
    # pega en cualquier frase: no entran.
    voc = {c: [v for v in d["valores"] if v and len(v) > 2] for c, d in vocabulario(tienda_id).items()
           if d.get("valores") and d.get("etiqueta") and d.get("tipo") != "si_no"
           and c not in ("nombre", "modelo", "descripcion")}
    conds, resto = [], []
    for t in textos:
        txt = _n(t)
        m = _TOPE.search(txt)
        if m:
            num = float(m.group(2).replace(".", "").replace(",", "."))
            num *= 1000 if m.group(3) else 1
            conds.append({"campo": "precio_ars", "operador": "menor", "valor": str(int(num))})
            continue
        hallado = []
        for campo, valores in voc.items():
            for v in sorted(valores, key=len, reverse=True):
                if _palabra_en(_n(v), txt):
                    hallado.append((campo, v))
                    break
        # Un valor que es parte de otro hallado —"negro" adentro de "negro y rojo"— no cuenta dos veces.
        hallado = [(c, v) for c, v in hallado if not any(v != w and _n(v) in _n(w) for _, w in hallado)]
        if not hallado:
            resto.append(str(t))
            continue
        op = "no_contiene" if _NIEGA.search(txt) else "contiene"
        conds += [{"campo": c, "operador": op, "valor": v} for c, v in hallado]
    return conds, " ".join(resto)


def _orden(o) -> dict | None:
    o = _n(o)
    if "barat" in o or "economic" in o:
        return {"campo": "precio_ars", "direccion": "min"}
    if "car" in o:
        return {"campo": "precio_ars", "direccion": "max"}
    return None


def ficha_a_piezas(llena: dict, tienda_id: str) -> list:
    """La ficha 9 llena, como las piezas de `tablero`. Cada casilla va a la pieza que corre su herramienta."""
    from app.core import tablero as T
    llena = F.atar_ficha(llena or {})
    pz = []

    def nueva(tipo, texto, **k):
        pz.append({"n": len(pz) + 1, "tipo": tipo, "texto": str(texto or tipo), **{a: b for a, b in k.items()
                                                                                   if b not in (None, "", [])}})
    for b in _lista(llena.get("busquedas")):
        if not isinstance(b, dict):
            continue
        conds, resto = condiciones_de([str(c) for c in _lista(b.get("condiciones"))], tienda_id)
        rub = str(b.get("rubro") or "")
        nueva("buscar", f"{rub} {resto}".strip(), rubro="" if "toda" in _n(rub) else rub, producto=resto,
              cantidad=b.get("cantidad") if isinstance(b.get("cantidad"), int) else None,
              condiciones=conds, orden=_orden(b.get("orden")))
    for p in _lista(llena.get("productos")):
        if isinstance(p, dict) and p.get("producto"):
            nueva("producto", f"{p['producto']} {p.get('quiere_saber') or ''}".strip(), producto=str(p["producto"]))
    for r in _lista(llena.get("referencias")):
        if isinstance(r, dict) and r.get("es"):
            nueva("producto", r.get("dijo") or r["es"], producto=str(r["es"]))
    if llena.get("no_vende"):
        nueva("buscar", " ".join(map(str, _lista(llena["no_vende"]))), rubro=T.NO_LO_VENDE)
    for c in _lista(llena.get("compatibilidad")):
        if isinstance(c, dict):
            nueva("compatibilidad", f"{c.get('producto') or ''} con {c.get('con') or ''}", producto=str(c.get("producto") or ""),
                  con=str(c.get("con") or ""), falta="el modelo de su equipo" if c.get("falta_modelo") is True else None)
    for t in _lista(llena.get("politicas")):
        nueva("politica", str(t), tema=str(t))
    if llena.get("humano") is True:
        nueva("politica", "hablar con una persona", tema="contacto_humano")
    for a in _lista(llena.get("afirma")):
        if isinstance(a, dict):
            nueva("verificar", f"{a.get('sobre') or ''} {a.get('dice') or ''}".strip(), producto=str(a.get("sobre") or ""))
    for e in _lista(llena.get("explicar")):
        nueva("explicar", str(e))
    if llena.get("catalogo") is True:
        nueva("explicar", "que vende la tienda")
    destinos = [str(d) for d in _lista(llena.get("envios"))]
    ped = llena.get("pedido") if isinstance(llena.get("pedido"), dict) else {}
    tot = llena.get("total") if isinstance(llena.get("total"), dict) else {}
    rep = [r for r in _lista(ped.get("reparto_pago")) if isinstance(r, dict)]
    articulos = [a for a in _lista(ped.get("articulos")) if isinstance(a, dict) and a.get("producto")] if ped.get("cambia") else []
    if articulos or rep or tot.get("pide") is True:
        items = [{"producto": F._con_color(a), "cantidad": F.D._entero(a.get("cantidad")) or 1,
                  "destino": "" if _n(a.get("destino")) in F._SIN_DESTINO else str(a["destino"])} for a in articulos]
        nueva("cuenta", "el pedido" if articulos else "el total", items=items, reparto_pago=rep,
              destinos=sorted({i["destino"] for i in items if i["destino"]}) or destinos,
              sobre_el_pedido=True if not articulos and not llena.get("busquedas") and not llena.get("productos") else None)
    if destinos and not articulos:
        nueva("envio", "envio a " + ", ".join(destinos), destinos=destinos)
    # Lo que el cliente hace segun un resultado: la accion depende de la pieza que averigua —la compatibilidad, el
    # producto—. El codigo se lo pasa al redactor como depende_de_la_parte.
    condicionado = _lista(llena.get("condiciones")) or any(
        isinstance(c, dict) and (c.get("si_anda") or c.get("si_no")) for c in _lista(llena.get("compatibilidad")))
    if condicionado:
        averigua = [p["n"] for p in pz if p["tipo"] in ("compatibilidad", "producto", "verificar", "buscar")]
        for p in pz:
            if p["tipo"] in ("cuenta", "comprar") and averigua:
                p["depende_de"] = averigua[:1]
    for d in _lista(llena.get("preguntar")):
        nueva("repreguntar", str(d), falta=str(d))
    if not pz:
        nueva("charla", "charla")
    return pz


# ══ CORRER: las piezas por el codigo de produccion ═════════════════════════

def correr(caso, llena) -> dict:
    from app.core import tablero as T
    from app.core.respuesta import _memoria_texto
    from app.core.agente import CLIENTE_DIJO
    cid, ctx, msg, esp = caso
    memoria = _memoria_texto(D.conv_de(ctx))
    # Como `tablero.turno`: lo que dijo el cliente en la charla, que el codigo usa para no inventarle medios de pago.
    hist = D.historial(ctx)
    CLIENTE_DIJO.set("\n".join([m.get("content") or "" for m in hist if m.get("role") == "user"] + [msg]))
    piezas, errores, _ = T.atar(ficha_a_piezas(llena, D.TIENDA), D.TIENDA)
    c = {"mensaje": msg, "historial": hist, "memoria": memoria, "tienda_id": D.TIENDA,
         "pide_total": any(p.get("tipo") == "cuenta" for p in piezas), "puede_confirmar": True}
    llamadas, error = [], ""
    try:
        hechos = T.correr_piezas(piezas, D.TIENDA, llamadas, 1, c)
    except Exception as e:  # noqa: BLE001 — que el codigo se rompa con lo que entendio el modelo es una falla
        hechos, error = [], f"{type(e).__name__}: {str(e)[:200]}"
    return {"piezas": piezas, "atadura": errores, "llamadas": llamadas, "hechos": hechos, "error": error,
            "confirma": bool(c.get("pedido"))}


# ══ MEDIR: lo que pidio el codigo y lo que resolvieron las herramientas ═════

def _resueltos(vuelve) -> str:
    """Los nombres que resolvio la herramienta: la identidad la dice el catalogo, no el pedido."""
    filas = (vuelve or {}).get("filas") or []
    return " / ".join(str(f.get("nombre") or "") for f in filas[:3] if isinstance(f, dict))


def atomos(r, ctx) -> list:
    out = []
    for x in r["llamadas"]:
        h, a, v = x["herramienta"], x["args"], x.get("vuelve") or {}
        if h in ("producto", "reservar"):
            out.append({"t": "prod", "prod": f"{a.get('nombre') or a.get('producto') or ''} {_resueltos(v)}"})
        elif h == "buscar":
            o = a.get("orden") or {}
            out.append({"t": "buscar", "rubro": a.get("rubro") or "",
                        "orden": o.get("direccion") if str(o.get("campo") or "").startswith("precio") else None,
                        "cond": " ".join(f"{c.get('campo')} {c.get('operador')} {c.get('valor')}"
                                         for c in a.get("condiciones") or []) + " " + str(a.get("que") or "") + " " + str(a.get("rubro") or ""),
                        "vacio": v.get("veredicto") == "no_existe"})
            for f in (v.get("filas") or [])[:3]:
                out.append({"t": "prod", "prod": str(f.get("nombre") or "")})
        elif h == "compatibilidad":
            for c in v.get("compatibilidad") or [{}]:
                out.append({"t": "compat", "prod": f"{a.get('producto') or ''} {c.get('nombre') or ''}",
                            "con": f"{a.get('con') or ''} {c.get('con_equipo') or ''}"})
        elif h == "politica":
            out.append({"t": "politica", "tema": [p.get("tema") for p in v.get("politicas") or []]})
        elif h == "envio":
            for f in v.get("filas") or []:
                out.append({"t": "envio", "destino": str(f.get("destino") or "")})
        elif h == "cuenta":
            cu = v.get("cuenta") or {}
            out.append({"t": "cuenta"} if cu.get("total_ars") is not None else {"t": "cuenta_sin_total"})
            if a.get("reparto_pago"):
                out.append({"t": "pago", "medios": {f"{_n(m.get('medio'))} {k}": m.get("porcentaje")
                                                    for k, m in enumerate(_lista(a["reparto_pago"])) if isinstance(m, dict)}})
            for it in cu.get("items") or []:
                out.append({"t": "agregar", "prod": str(it.get("nombre") or ""), "cant": it.get("cantidad")})
            for d in a.get("destinos") or [a.get("destino")]:
                if d:
                    out.append({"t": "destino", "destino": str(d)})
    for p in r["piezas"]:
        # Lo que el codigo no resuelve con una herramienta, lo entrega como pieza al redactor.
        if p.get("tipo") == "repreguntar" or p.get("falta"):
            out.append({"t": "preguntar"})
        if p.get("tipo") == "buscar" and p.get("rubro") == "no lo vende la tienda":
            out.append({"t": "novende"})
    for h in r["hechos"]:
        if h.get("depende_de_la_parte"):
            out.append({"t": "condicion"})
        if h.get("pregunta_al_cliente") or h.get("tipo") in ("confirmar_pedido", "articulos"):
            out.append({"t": "preguntar"})
    if r["confirma"]:
        out.append({"t": "cuenta"})  # el pedido que no cierra se confirma antes de calcular: es la cuenta de este turno
    return out


def carrito(r, ctx) -> list:
    filas = []
    for x in r["llamadas"]:
        if x["herramienta"] != "cuenta":
            continue
        cu = (x.get("vuelve") or {}).get("cuenta") or {}
        a = x["args"]
        porid = {}
        for it in a.get("items") or []:
            porid.setdefault(str(it.get("producto")), []).append(str(it.get("destino") or a.get("destino") or ""))
        for it in cu.get("items") or []:
            ds = porid.get(str(it.get("id"))) or [a.get("destino") or ""]
            filas.append((str(it.get("nombre") or ""), int(it.get("cantidad") or 1), ds.pop(0) if len(ds) > 1 else ds[0]))
    if filas:
        return filas
    return [(D.POR_ID[p]["nombre"], q, d) for p, q, d in (ctx or {}).get("carrito", [])]


def corregir(caso, r) -> dict:
    cid, ctx, msg, esp = caso
    at = atomos(r, ctx)
    faltan = [e for e in esp["partes"] if not any(D.cumple(e, a) for a in at)]
    prohibidos = [t for t in esp.get("no", []) if any(a["t"] == t for a in at)]
    carr = carrito(r, ctx) if esp.get("carrito") else None
    carrito_ok = D.igual_carrito(esp["carrito"], carr) if esp.get("carrito") else True
    vacios = [a["rubro"] for a in at if a["t"] == "buscar" and a.get("vacio")]
    ok = not faltan and not prohibidos and carrito_ok and not r["error"]
    return {"ok": ok, "faltan": [D.en_palabras(f) for f in faltan], "prohibidos": prohibidos,
            "carrito_ok": carrito_ok, "carrito": carr, "vacios": vacios}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--de", default="f9_g174", help="etiqueta de la ficha 9 cuyas fichas llenas se pasan por el codigo")
    ap.add_argument("--casos", default="")
    ap.add_argument("--ver", action="store_true", help="muestra piezas y llamadas de cada caso")
    ap.add_argument("--solo-bien", action="store_true", help="solo los casos que el modelo entendio bien")
    a = ap.parse_args()
    D.preparar()
    from app.core.tablero import _json
    casos = {c[0]: c for c in D.CASOS}
    filas = F.filas(a.de)
    res = []
    for cid, f in sorted(filas.items()):
        if (a.casos and cid not in a.casos.split(",")) or f["crudo"].startswith("ERROR") or cid not in casos:
            continue
        if a.solo_bien and not f["ok"]:
            continue
        llena = _json(f["crudo"]).get("llena") or {}
        r = correr(casos[cid], llena)
        nota = corregir(casos[cid], r)
        res.append((cid, f["ok"], nota, r))
        if a.ver:
            print(f"\n== {cid} {'BIEN' if nota['ok'] else 'MAL'}  {casos[cid][2][:150]}")
            for p in r["piezas"]:
                print("  pieza", json.dumps(p, ensure_ascii=False)[:220])
            for x in r["llamadas"]:
                print("  llama", x["herramienta"], json.dumps(x["args"], ensure_ascii=False)[:200])
            print("  falta:", nota["faltan"], nota["prohibidos"], "" if nota["carrito_ok"] else f"carrito {nota['carrito']}",
                  r["error"])
    with open(SALIDA, "a", encoding="utf-8") as o:
        for cid, okm, nota, r in res:
            o.write(json.dumps({"de": a.de, "id": cid, "reserva": cid in D.RESERVA, "ok_modelo": okm, **nota,
                                "error": r["error"], "llamadas": [[x["herramienta"], x["args"]] for x in r["llamadas"]]},
                               ensure_ascii=False, default=str) + "\n")
    bien_m = [x for x in res if x[1]]
    print(f"\nPOR EL CODIGO, fichas de {a.de}: {sum(x[2]['ok'] for x in res)} de {len(res)} casos bien."
          f" De los {len(bien_m)} que el modelo entendio bien, el codigo entrega bien {sum(x[2]['ok'] for x in bien_m)}."
          f" Reserva {sum(x[2]['ok'] for x in res if x[0] in D.RESERVA)} de {sum(1 for x in res if x[0] in D.RESERVA)}.")
    for cid, okm, nota, r in res:
        if okm and not nota["ok"]:
            print(f"  {cid}{'r' if cid in D.RESERVA else ' '} " + "; ".join(nota["faltan"] + nota["prohibidos"])[:170]
                  + ("" if nota["carrito_ok"] else f" | pedido: {nota['carrito']}"[:120]) + (f" | ERROR {r['error']}" if r["error"] else ""))
    vac = [(cid, nota["vacios"]) for cid, _, nota, _ in res if nota["vacios"]]
    print(f"Busquedas que volvieron vacias: {len(vac)} casos: " + ", ".join(f"{c} {v}" for c, v in vac)[:400])


if __name__ == "__main__":
    main()
