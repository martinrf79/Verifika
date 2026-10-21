"""AVISOS CANDIDATOS, uno por clase. Cada uno se mide sin modelo sobre la base de 475: entra solo si salta unicamente en
casos que fallan. Todo sale de la fuente o del estado, sin listas de palabras."""
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import contexto  # noqa: E402

from app.core import agente  # noqa: E402
from app.core.flujo import agenda as A  # noqa: E402
from app.core.flujo import borrador as B  # noqa: E402
from app.core.flujo import catalogo as K  # noqa: E402
from app.core.flujo import interprete as I  # noqa: E402
from app.core.flujo import marcador as M  # noqa: E402

TIENDA = "verifika_prod"


def _lugares(t):
    import pistas as P
    r = P._lugar(str(t or ""))
    m = re.match(r"son (\d+) localidades", r)
    return int(m.group(1)) if m else (0 if r.startswith("no es") else 1)


def _plano(t):
    from banco_pruebas.traduccion58 import plano
    return plano(str(t or ""))


def dos_lugares(ag, estado, mensaje):
    return [f'La pregunta {q.get("n")} cotiza un envio a "{q["destino"]}", que son {_lugares(q["destino"])} lugares: va '
            "una pregunta envio por cada lugar." for q in A.preguntas(ag)
            if q.get("accion") == "envio" and _lugares(q.get("destino")) > 1]


def confirma_completo(ag, estado, mensaje):
    """Confirma renglones que no tienen nada pendiente, y el mensaje no cambia nada del pedido."""
    b = B.leer(estado.get("borrador"))
    if not b["renglones"]:
        return []
    res = B.resolver(b, TIENDA)
    pend = {x["L"] for x in B.faltantes(b, res) if x.get("L")}
    qs = A.preguntas(ag)
    if any(q.get(k) for q in qs for k in ("agrega", "saca", "cambia", "total", "reemplaza")):
        return []
    # Solo si el mensaje entero es confirmar: si ademas pide otra cosa -una cuenta, un pago-, no salta.
    if any(not (q.get("accion") == "comprar" and (q.get("confirma") or q.get("acepta"))) for q in qs):
        return []
    conf = [L for q in qs for k in ("confirma", "acepta") for r in q.get(k) or [] for L in re.findall(r"L-\d+", str(r))]
    if conf and not set(conf) & pend:
        return [f"Las preguntas confirman {', '.join(conf)}, que no tienen nada pendiente: el pedido ya esta completo. Un si "
                "que no cambia nada del pedido es una pregunta cuenta, que le muestra el total."]
    return []


def compat_contradice(ag, estado, mensaje):
    out = []
    for q in A.preguntas(ag):
        if q.get("accion") != "compatibilidad" or not q.get("con"):
            continue
        idt = K.identificar(str(q.get("producto") or ""), "", TIENDA)
        if idt["veredicto"] != "exists":
            continue
        r = agente.ejecutar("compatibilidad", {"producto": str(idt["producto"]["id"]), "con": str(q["con"])}, TIENDA)
        for v in [v for v in r.get("compatibilidad") or [] if isinstance(v, dict)]:
            usado = _plano(v.get("con_equipo"))
            sobran = [w for w in _plano(q["con"]).split() if len(w) > 2 and w not in usado.split()
                      and w not in ("con", "una", "uno", "que", "para", "tengo", "mi", "mis")]
            # La ficha del producto nombra justo lo que el codigo no uso: el veredicto no lo tuvo en cuenta.
            if v.get("veredicto") == "compatible" and sobran and any(w in _plano(v.get("motivo")) for w in sobran):
                out.append(f"La pregunta {q.get('n')}: el codigo juzgo la compatibilidad con '{v.get('con_equipo')}' sin "
                           f"usar '{' '.join(sobran)}'. La ficha del producto dice: {v.get('motivo')} con lleva el dato del "
                           "equipo que decide.")
    return out


def color_invalido(ag, estado, mensaje):
    nums = I.numeros(estado)
    out = []
    for q in A.preguntas(ag):
        for c in q.get("cambia") or []:
            col = c.get("color") if isinstance(c, dict) else None
            r = nums.get(str(c.get("es") or "")) if isinstance(c, dict) else None
            if not col or not isinstance(r, dict):
                continue
            colores = {_plano(p.get("color")) for p in K.productos(TIENDA) if p.get("color")}
            if _plano(col) not in colores:
                out.append(f'La pregunta {q.get("n")} cambia el color de {c.get("es")} a "{col}", que no es un color de la '
                           "tienda: si le da igual el color, no se cambia nada.")
    return out


def lista_nombrada(ag, estado, mensaje):
    out = []
    for q in A.preguntas(ag):
        p = q.get("producto")
        if q.get("accion") == "producto" and isinstance(p, list) and len(p) > 1 and not any(str(x).startswith("M-") for x in p):
            ok = [x for x in p if K.identificar(str(x), "", TIENDA)["veredicto"] == "exists"]
            if len(ok) == len(p):
                out.append(f"La pregunta {q.get('n')} lista {', '.join(p)}, que son productos distintos nombrados por el "
                           "cliente: va una pregunta producto por cada uno. La lista es solo para lo que senala sin decir cual.")
    return out


def ultimo_de_muchos(ag, estado, mensaje):
    nums = I.numeros(estado)
    ms = [k for k in nums if k.startswith("M-")]
    if len(ms) < 3 or any(e.startswith(("el producto", "puede ser")) for _d, e in M.marcar(mensaje, TIENDA)):
        return []
    return [f"La pregunta {q.get('n')} senala {q['producto']}, el ultimo de {len(ms)} productos mostrados, y el mensaje no "
            "nombra cual: si no dice cual, van todos los que puede ser, como lista, y el codigo pregunta."
            for q in A.preguntas(ag) if q.get("accion") == "producto" and q.get("producto") == ms[-1]]


def monto_suelto(ag, estado, mensaje):
    montos = [(d, re.sub(r"\D", "", e)) for d, e in M.marcar(mensaje, TIENDA) if "pesos" in e]
    if not montos:
        return []
    campos = json.dumps({k: v for k, v in ag.items() if k != "_crudo"}, ensure_ascii=False)
    sin_cita = re.sub(r'"cita": "[^"]*"', "", campos)
    out = []
    for d, v in montos:
        if v not in re.sub(r"\D", "", sin_cita.replace(" mil", "000")) and _plano(d) not in _plano(sin_cita):
            out.append(f'El monto "{d}", {v} pesos, no esta en ninguna pregunta: si es una condicion de precio de un '
                       "producto, va como lo que quiere saber del producto y la compra depende de esa pregunta.")
    return out


def envio_sin_cuenta_libreta(ag, estado, mensaje):
    """Precio y envio a la localidad que esta en la libreta, no en el mensaje, sin cuenta: pide el total puesto."""
    qs = A.preguntas(ag)
    acc = [q.get("accion") for q in qs]
    if "cuenta" in acc or "producto" not in acc:
        return []
    out = []
    for q in qs:
        if q.get("accion") == "envio" and q.get("destino"):
            dest = _plano(q["destino"]).split()
            if dest and dest[0] not in _plano(mensaje).split():
                out.append(f"La pregunta {q.get('n')} cotiza el envio a {q['destino']}, que el cliente no nombro en este "
                           "mensaje, junto con el precio: si pide lo que le sale con el envio, va tambien una pregunta "
                           "cuenta que lo suma.")
    return out


CANDIDATOS = {"dos_lugares": dos_lugares, "confirma_completo": confirma_completo, "compat_contradice": compat_contradice,
              "color_invalido": color_invalido, "lista_nombrada": lista_nombrada, "ultimo_de_muchos": ultimo_de_muchos,
              "monto_suelto": monto_suelto, "envio_sin_cuenta_libreta": envio_sin_cuenta_libreta}


def medir(solo=None):
    base = {tuple(json.loads(k)): v for k, v in json.load(open(os.path.join(AQUI, "base475.json"))).items()}
    cache, res = {}, {c: [] for c in CANDIDATOS}
    for k, r in sorted(base.items()):
        if (k[0], k[1]) not in cache:
            cache[(k[0], k[1])] = contexto.contexto(k[0], k[1], uid="cand")
        ag = {kk: vv for kk, vv in r["agenda"].items() if kk != "_crudo"}
        for c, f in CANDIDATOS.items():
            if solo and c not in solo:
                continue
            try:
                av = f(ag, cache[(k[0], k[1])]["estado"], r["texto"])
            except Exception as e:  # noqa: BLE001
                av = [f"ERROR {type(e).__name__}: {e}"]
            if av:
                res[c].append((k, r["bien"], av[0]))
    for c, xs in res.items():
        if solo and c not in solo:
            continue
        andan = [x for x in xs if x[1]]
        fallan = [x for x in xs if not x[1]]
        print(f"{c:26} salta en {len(fallan):3} que fallan y {len(andan):3} que andan")
        for k, b, a in andan[:4]:
            print(f"     ANDA {k} {a[:110]}")
        for k, b, a in fallan[:2]:
            print(f"     FALLA {k} {a[:110]}")
    if not solo:
        json.dump({c: [[list(k), b, a] for k, b, a in xs] for c, xs in res.items()},
                  open(os.path.join(AQUI, "candidatos_salta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return res


if __name__ == "__main__":
    medir(sys.argv[1:] or None)


# ══ TANDA 3 ══════════════════════════════════════════════════════════════════

_ENVIOS = {"costo_envio", "envios", "plazo_envio"}


def politica_envio_con_destinos(ag, estado, mensaje):
    qs = A.preguntas(ag)
    destinos = [a.get("destino") for q in qs for a in q.get("agrega") or [] if a.get("destino")]
    return [f"La pregunta {q.get('n')} pregunta la regla de envios, pero el pedido de este mensaje va a "
            f"{', '.join(dict.fromkeys(destinos))}: el costo de mandar a esos lugares es una pregunta envio por cada destino."
            for q in qs if q.get("accion") == "politica" and q.get("tema") in _ENVIOS and destinos]


def uno_de_muchos(ag, estado, mensaje):
    nums = I.numeros(estado)
    ms = [k for k in nums if k.startswith("M-")]
    if len(ms) < 3 or any(e.startswith(("el producto", "puede ser")) for _d, e in M.marcar(mensaje, TIENDA)):
        return []
    return [f"La pregunta {q.get('n')} senala {q['producto']}, uno de {len(ms)} productos mostrados, y el mensaje no nombra "
            "cual: si no dice cual, van todos los que puede ser, como lista, y el codigo pregunta."
            for q in A.preguntas(ag) if q.get("accion") == "producto" and isinstance(q.get("producto"), str)
            and q["producto"] in ms]


_CAMPOS = {"buscar": {"rubro", "cantidad", "orden", "condiciones", "entre_lo_mostrado"},
           "producto": {"producto", "quiere_saber", "color", "afirma"}, "envio": {"destino"},
           "cuenta": {"tope", "si_pasa", "reparto"}, "politica": {"tema", "afirma"},
           "compatibilidad": {"producto", "con", "falta_modelo"},
           "comprar": {"agrega", "saca", "cambia", "confirma", "acepta", "total", "reemplaza", "reparto"},
           "explicar": {"pregunta"}, "otro": {"que"}}
_COMUNES = {"n", "cita", "accion", "si", "responde"}


def campo_inventado(ag, estado, mensaje):
    out = []
    for q in A.preguntas(ag):
        extra = set(q) - _COMUNES - _CAMPOS.get(q.get("accion"), set())
        # Solo en una compra: un campo de mas en una compra cambia lo que se anota.
        if extra and q.get("accion") == "comprar":
            out.append(f"La pregunta {q.get('n')} es {q.get('accion')} y trae {', '.join(sorted(extra))}, que {q.get('accion')} "
                       "no tiene: el codigo no lo lee. Si la compra depende de un dato del producto, va una pregunta "
                       "producto con lo que quiere saber, y la compra con si.")
    return out


def elegir_por_dato(ag, estado, mensaje):
    out = []
    for q in A.preguntas(ag):
        p = q.get("producto")
        qs_ = str(q.get("quiere_saber") or "")
        if (q.get("accion") == "producto" and isinstance(p, list) and len(p) > 1
                and not any(str(x).startswith("M-") for x in p) and _plano(qs_) not in ("precio", "stock", "")
                and "campo" in K.atar(qs_, K.productos(TIENDA), TIENDA)
                and all(K.identificar(str(x), "", TIENDA)["veredicto"] == "exists" for x in p)):
            out.append(f"La pregunta {q.get('n')} lista {', '.join(p)} y quiere saber {qs_}: son productos nombrados, va "
                       "una pregunta producto por cada uno. Si elige el que cumpla, va ademas una compra de cada uno con si "
                       "de su pregunta.")
    return out


def cuenta_sin_pedido_consultas(ag, estado, mensaje):
    """La cuenta con el pedido vacio y productos consultados con cantidad, sin anotar nada."""
    qs = A.preguntas(ag)
    if B.leer(estado.get("borrador"))["renglones"] or any(q.get("agrega") for q in qs):
        return []
    if "cuenta" not in [q.get("accion") for q in qs]:
        return []
    con_cant = [q for q in qs if q.get("accion") == "producto" and re.search(r"\d", str(q.get("afirma") or ""))]
    return ["La cuenta va con el pedido vacio y las cantidades estan como afirma de productos consultados: para que la "
            "cuenta las sume, va una compra con agrega, con cada producto y su cantidad."] if con_cant else []


CANDIDATOS.update({"politica_envio_con_destinos": politica_envio_con_destinos, "uno_de_muchos": uno_de_muchos,
                   "campo_inventado": campo_inventado, "elegir_por_dato": elegir_por_dato,
                   "cuenta_sin_pedido_consultas": cuenta_sin_pedido_consultas})


def medir_primera(nombres, actual="base521.json"):
    """El aviso se evalua sobre la PRIMERA traduccion, como en produccion. Cuenta donde salta: en los que fallan hoy, en
    los que andan sin devuelta —ahi no puede saltar— y en los que ya arreglo una devuelta —esos se vuelven a correr—."""
    import seguros as S
    primera = S.base()
    hoy = {tuple(json.loads(k)): v for k, v in json.load(open(os.path.join(AQUI, actual))).items()}
    cache, out = {}, {}
    for c in nombres:
        out[c] = {"fallan": [], "andan": [], "devuelta": []}
    for k, r in sorted(primera.items()):
        if (k[0], k[1]) not in cache:
            cache[(k[0], k[1])] = contexto.contexto(k[0], k[1], uid="mp")
        ag = {kk: vv for kk, vv in r["agenda"].items() if kk != "_crudo"}
        for c in nombres:
            if CANDIDATOS[c](ag, cache[(k[0], k[1])]["estado"], r["texto"]):
                grupo = "fallan" if not hoy[k]["bien"] else ("devuelta" if hoy[k]["base"] not in ("produccion", "tabla")
                                                            else "andan")
                out[c][grupo].append(k)
    for c, g in out.items():
        print(f"{c:30} fallan {len(g['fallan']):3} | andan {len(g['andan']):3} | ya con devuelta {len(g['devuelta']):3}"
              + (f"  ANDAN: {g['andan'][:4]}" if g["andan"] else ""))
    return out


# ══ TANDA 4 ══════════════════════════════════════════════════════════════════

def repite_lo_mostrado(ag, estado, mensaje):
    mostrados = {str(v) for k, v in I.numeros(estado).items() if k.startswith("M-")}
    if len(mostrados) < 2:
        return []
    previa = estado.get("busqueda") or {}
    out = []
    for q in A.preguntas(ag):
        if q.get("accion") != "buscar" or q.get("entre_lo_mostrado"):
            continue
        # Solo si solto todas las condiciones de la busqueda anterior del mismo rubro.
        if not previa.get("condiciones") or q.get("condiciones") or previa.get("rubro") != K.rubro(str(q.get("rubro") or ""), TIENDA):
            continue
        rub = K.rubro(str(q.get("rubro") or ""), TIENDA)
        r = K.buscar(rub, q.get("condiciones") or [], q.get("orden") or "nada", 5, TIENDA)
        ids = {str(p["id"]) for p in r["filas"]}
        if ids and ids <= mostrados:
            antes = ", ".join(str(c) for c in previa.get("condiciones") or [])
            out.append(f"La pregunta {q.get('n')} busca {rub} y trae solo lo que el cliente ya vio: los {len(ids)} ya estan "
                       "mostrados. Si pide otras opciones, va lo que las excluye, por ejemplo 'que no sea' la marca de lo "
                       "mostrado" + (f", y las condiciones de la busqueda anterior que no solto siguen: {antes}." if antes else "."))
    return out


def agrega_con_campo(ag, estado, mensaje):
    out = []
    for q in A.preguntas(ag):
        for a in q.get("agrega") or []:
            extra = set(a) - {"producto", "cantidad", "color", "destino", "cita", "condicion"} if isinstance(a, dict) else set()
            if extra:
                out.append(f"La pregunta {q.get('n')} agrega {a.get('producto')} con {', '.join(sorted(extra))}, que una "
                           "compra no tiene. Elegir lo mas barato o lo mejor de un rubro es una pregunta buscar por rubro, "
                           "con su orden; la compra lleva el rubro, su cantidad y su destino.")
    return out


def pedido_sin_cuenta(ag, estado, mensaje):
    qs = A.preguntas(ag)
    acc = [q.get("accion") for q in qs]
    destinos = {a.get("destino") for q in qs for a in q.get("agrega") or [] if a.get("destino")}
    if len(destinos) > 1 and "cuenta" not in acc and "envio" not in acc and "buscar" in acc:
        return ["El pedido de este mensaje va a varios destinos y pide precios, pero no hay cuenta: sin cuenta el codigo no "
                "suma ni cotiza los envios de cada destino."]
    return []


def compat_rubro_con_dato(ag, estado, mensaje):
    return [f"La pregunta {q.get('n')} pregunta la compatibilidad de un rubro, {q['producto']}, con '{q['con']}', que trae "
            "un dato del equipo: si busca el mejor que cumpla, es una pregunta buscar de ese rubro, con el orden y con lo "
            "que tiene que aguantar como condicion."
            for q in A.preguntas(ag) if q.get("accion") == "compatibilidad" and K.solo_rubro(str(q.get("producto") or ""), TIENDA)
            and re.search(r"\d+\s*(w|watts|gb|tb|hz|mah|mm)\b", _plano(q.get("con")))]


def uno_de_muchos_sin_rubro(ag, estado, mensaje):
    if any(e.startswith("el rubro") for _d, e in M.marcar(mensaje, TIENDA)):
        return []
    return uno_de_muchos(ag, estado, mensaje)


CANDIDATOS.update({"repite_lo_mostrado": repite_lo_mostrado, "agrega_con_campo": agrega_con_campo,
                   "pedido_sin_cuenta": pedido_sin_cuenta, "compat_rubro_con_dato": compat_rubro_con_dato,
                   "uno_de_muchos_sin_rubro": uno_de_muchos_sin_rubro})


# ══ TANDA 5 ══════════════════════════════════════════════════════════════════

def cantidad_cero(ag, estado, mensaje):
    return [f"La pregunta {q.get('n')} agrega {a.get('producto')} con cantidad 0, y eso no se anota: lo que queda de la "
            "lista es \"los otros\", sin cantidad." for q in A.preguntas(ag) for a in q.get("agrega") or []
            if isinstance(a, dict) and str(a.get("cantidad")).strip() in ("0", "0.0")]


def porcentaje_como_politica(ag, estado, mensaje):
    """Un porcentaje dicho junto a un medio de pago, con el pedido armado, va como politica y no como reparto."""
    if not B.leer(estado.get("borrador"))["renglones"]:
        return []
    qs = A.preguntas(ag)
    if any(q.get("reparto") for q in qs):
        return []
    pcts = re.findall(r"\b(\d{1,2})\s*(?:%|por ciento)", _plano(mensaje))
    if not pcts:
        return []
    return [f"La pregunta {q.get('n')} pregunta la regla de {q.get('tema')}, pero el cliente dice {pcts[0]} por ciento con "
            "un medio, con el pedido armado: es como reparte el pago, una pregunta cuenta con reparto."
            for q in qs if q.get("accion") == "politica"]


CANDIDATOS.update({"cantidad_cero": cantidad_cero, "porcentaje_como_politica": porcentaje_como_politica})


# ══ LOS QUE ENTRARON ═════════════════════════════════════════════════════════
# Medidos sobre la primera traduccion de las 525: cada uno salta solo en casos que fallaban, y donde salto se corrio la
# devuelta y salio bien. Los tres de `seguros.py` —vacio, suma, traba— son la primera tanda. Los demas de este archivo
# quedaron afuera porque saltan tambien en casos que andan: confirma_completo sin acotar, compat_contradice,
# lista_nombrada, monto_suelto, uno_de_muchos, uno_de_muchos_sin_rubro y pedido_sin_cuenta.
SEGUROS = ["dos_lugares", "color_invalido", "ultimo_de_muchos", "envio_sin_cuenta_libreta", "confirma_completo",
           "politica_envio_con_destinos", "campo_inventado", "elegir_por_dato", "cuenta_sin_pedido_consultas",
           "repite_lo_mostrado", "compat_rubro_con_dato", "agrega_con_campo", "cantidad_cero", "porcentaje_como_politica"]


def solapados():
    """Casos donde saltan dos avisos de tandas distintas: ahi la devuelta junta no se midio."""
    import seguros as S
    primera = S.base()
    cache, out = {}, {}
    for k, r in sorted(primera.items()):
        if (k[0], k[1]) not in cache:
            cache[(k[0], k[1])] = contexto.contexto(k[0], k[1], uid="sol")
        e = cache[(k[0], k[1])]["estado"]
        ag = {kk: vv for kk, vv in r["agenda"].items() if kk != "_crudo"}
        cuales = [c for c in SEGUROS if CANDIDATOS[c](ag, e, r["texto"])] + [c for c, _t in S.avisos(ag, e)]
        if len(cuales) > 1:
            out[k] = cuales
    for k, v in out.items():
        print(k, v)
    print(f"casos con mas de un aviso: {len(out)}")
    return out
