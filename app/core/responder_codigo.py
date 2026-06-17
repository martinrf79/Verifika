"""
RESPONDER POR CODIGO — arma la respuesta SIN el Solver, desde el contrato.

Es la mitad "sin LLM" del sistema: dado lo que ya calculo el Provider (foco, ab,
multi, carrito, envio, catalogo, ficha) y la planilla (estado_pedido), redacta un
mensaje deterministico, reproducible y gratis. No inventa: todo numero y producto
sale del contrato. Sirve para (1) probar el espinazo offline a escala con
aserciones exactas, y (2) fallback en prod cuando el LLM se cae o improvisa.

Funcion PURA (lee dicts, no toca red ni LLM). Detras del flag SOLVER_CODIGO.
Devuelve el texto, o None si no hay material suficiente (ahi cae al Solver/puente).
"""
from typing import Optional


def _m(v) -> str:
    if not isinstance(v, (int, float)):
        return ""
    return f"${v:,.0f}".replace(",", ".")


def _lista_productos(prods: list, cap: int = 8) -> str:
    out = []
    for p in prods[:cap]:
        nom = p.get("nombre") or p.get("id")
        precio = p.get("precio_ars", p.get("precio"))
        m = _m(precio)
        out.append(f"- {nom}" + (f" — {m}" if m else ""))
    return "\n".join(out)


def _cola_etapa(etapa: str, faltantes: list) -> str:
    if etapa == "capturado":
        return "Listo, ya tengo todos tus datos. En breve coordinamos el pago y el envio."
    if etapa == "cierre":
        pide = {"nombre": "nombre y apellido", "telefono": "un telefono",
                "direccion": "la direccion de envio", "forma_pago": "la forma de pago"}
        falta = ", ".join(pide.get(f, f) for f in (faltantes or []))
        return (f"Para cerrar el pedido me falta {falta}. Me lo pasas?"
                if falta else "Confirmame y cerramos el pedido.")
    if etapa == "pedido":
        return "Te sirve asi? Si queres sumar o sacar algo, decime."
    return ""


def responder(prov: dict, estado: dict, mensaje: str = "", *,
              catalogo_texto: Optional[str] = None) -> Optional[str]:
    """Arma la respuesta por codigo. None si no hay material (cae al Solver).

    Args:
        prov: dict de provider.proveer().
        estado: dict de estado_pedido.construir_estado().
        catalogo_texto: respuesta de catalogo ya armada (categorias), si aplica.
    """
    prov = prov or {}
    estado = estado or {}

    # 1) Pedido GENERICO de catalogo: lista de categorias (ya armada afuera).
    if catalogo_texto:
        return catalogo_texto

    # 2) Confirmacion abierta (A/B, te_referis_a): la pregunta por codigo.
    conf = estado.get("confirmacion") or {}
    if conf.get("necesita") and conf.get("texto"):
        return conf["texto"]

    # 3) Stock insuficiente: no se vende, se avisa.
    if prov.get("stock_falta"):
        faltan = prov["stock_falta"]
        lineas = "\n".join(
            f"- {f.get('nombre')}: hay {f.get('stock')}, pediste {f.get('pedido')}"
            for f in faltan)
        return ("Uh, no me alcanza el stock para lo que pediste:\n" + lineas +
                "\nTe ofrezco una alternativa del catalogo o te aviso cuando "
                "vuelva a haber. Que preferis?")

    # 4) Pedido con presupuesto cerrado (planilla con items y presentacion).
    items = estado.get("items") or []
    pres = (estado.get("presentacion") or "").strip()
    if items and pres:
        cola = _cola_etapa(estado.get("etapa"), estado.get("faltantes"))
        return pres + (("\n\n" + cola) if cola else "")

    # 5) Exploracion: productos que trajo la busqueda del catalogo.
    cat = prov.get("catalogo") or {}
    comp = cat.get("compacto") if isinstance(cat, dict) else None
    prods = (comp or cat or {}).get("productos") or []
    if prods:
        return ("Tenemos estas opciones:\n" + _lista_productos(prods) +
                "\nCual te interesa? Te paso mas detalle o te armo el presupuesto.")

    # 6) Ficha del foco (un producto en foco, sin pedido cerrado).
    foco = prov.get("foco")
    if foco and (foco.get("calc") or {}).get("presentacion"):
        return foco["calc"]["presentacion"].strip()

    # 7) Sin material: que decida el puente / Solver.
    return None
