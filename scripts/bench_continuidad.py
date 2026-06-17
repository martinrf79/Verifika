"""
BANCO DE CONTINUIDAD (LAZO CERRADO) — conversaciones de varios turnos donde el
estado de cada turno SALE del turno anterior del propio modelo, no escrito a mano.

Esto mide el riesgo real de la continuidad y el cambio de decision: el desvio que
se hace bola turno a turno. El banco de un solo tiro no lo ve; este si.

Cada conversacion se corre varias veces (ROT_REPS, default 3) para medir si el
arrastre es ESTABLE de punta a punta.

Correr:
    .\\correr_local.ps1 py scripts\\bench_continuidad.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench_interpretacion as B  # _pedir, _get, _chequear, _norm

REPS = int(os.getenv("ROT_REPS", "3"))


def _estado_str(cart, zona, pregunta):
    partes = []
    if cart:
        items = "; ".join(f"{c}x {t}" for t, c in cart.items())
        partes.append(f"carrito: {items}")
    if zona:
        partes.append(f"envío a: {zona}")
    s = " | ".join(partes) if partes else "carrito vacío"
    return s, (pregunta or "")


def _find(cart, key):
    kn = B._norm(key or "")
    if not kn:
        return None
    for k in list(cart):
        if kn in B._norm(k) or B._norm(k) in kn:
            return k
    return None


def _aplicar(cart, out):
    """Ejecucion determinista ROUGH (prototipo) para arrastrar el estado."""
    op = out.get("operacion") or "ninguna"
    items = [i for i in (out.get("items") or []) if i.get("termino_crudo")]
    obj = out.get("objetivo_operacion")
    if op in ("vaciar_carrito", "nueva_compra"):
        cart.clear()
        if op == "nueva_compra":
            for it in items:
                cart[it["termino_crudo"]] = it.get("cantidad") or 1
        return
    if op == "sacar":
        k = _find(cart, obj or (items[0]["termino_crudo"] if items else ""))
        if k:
            del cart[k]
        return
    if op == "cambiar_cantidad":
        k = _find(cart, obj or (items[0]["termino_crudo"] if items else ""))
        cant = items[0].get("cantidad") if items else None
        if k and cant:
            cart[k] = cant
        return
    if op == "cambiar_producto":
        k = _find(cart, obj or "")
        prev = cart.pop(k) if k else 1
        if items:
            cart[items[0]["termino_crudo"]] = items[0].get("cantidad") or prev
        return
    if op == "agregar":
        for it in items:
            k = _find(cart, it["termino_crudo"])
            if k:
                cart[k] += it.get("cantidad") or 1
            else:
                cart[it["termino_crudo"]] = it.get("cantidad") or 1
        return
    # ninguna: pedido fresco si el carrito esta vacio
    if items and not cart:
        for it in items:
            cart[it["termino_crudo"]] = it.get("cantidad") or 1


# Conversaciones: cada turno = {bot (pregunta previa), msg, afirma (sobre la
# salida del modelo), cart (subcadena->cantidad esperada en el carrito despues)}
CHARLAS = [
    {"id": "decisiones_encadenadas", "turnos": [
        {"bot": "", "msg": "quiero 3 teclados mecánicos",
         "cart": {"tecl": 3}},
        {"bot": "", "msg": "mejor que sean 2",
         "afirma": [("operacion", "eq", "cambiar_cantidad")], "cart": {"tecl": 2}},
        {"bot": "", "msg": "agregá un mouse G203",
         "afirma": [("operacion", "eq", "agregar")], "cart": {"tecl": 2, "g203": 1}},
        {"bot": "", "msg": "no, sacá los teclados",
         "afirma": [("operacion", "eq", "sacar")], "cart_no": ["tecl"]},
        {"bot": "", "msg": "dale, lo llevo",
         "afirma": [("intencion", "in", ["decision_compra", "confirma_eleccion"])]},
    ]},
    {"id": "ambiguo_luego_cantidad", "turnos": [
        {"bot": "", "msg": "necesito un teclado inalámbrico"},
        {"bot": "¿el G915 o el K380?", "msg": "el más barato",
         "afirma": [("items.0.termino_crudo", "truthy", None)]},
        {"bot": "", "msg": "que sean 3",
         "afirma": [("operacion", "eq", "cambiar_cantidad"),
                    ("items.0.cantidad", "eq", 3)]},
    ]},
    {"id": "zona_y_reversa", "turnos": [
        {"bot": "", "msg": "quiero 2 mouse G203", "cart": {"g203": 2}},
        {"bot": "", "msg": "mandámelo a Córdoba Capital",
         "afirma": [("zona_o_cp", "contains", "cordoba")]},
        {"bot": "Bot: te paso el link de pago", "msg": "pará, no, cancelá todo",
         "afirma": [("cambio_de_idea", "truthy", None)]},
    ]},
]


def _corre_charla(charla):
    """Una pasada de la conversacion. Devuelve (paso_todo, log)."""
    cart, zona, log, ok = {}, None, [], True
    pregunta = ""
    for i, turno in enumerate(charla["turnos"], 1):
        if turno.get("bot"):
            pregunta = turno["bot"]
        estado, ctx = _estado_str(cart, zona, pregunta)
        try:
            out = B._pedir(estado, ctx, turno["msg"])
        except Exception as e:
            log.append(f"  t{i} ERROR: {str(e)[:80]}")
            return False, log
        # afirmaciones sobre la salida del modelo
        for path, op, val in turno.get("afirma", []):
            if not B._chequear(B._get(out, path), op, val):
                ok = False
                log.append(f"  t{i} FALLA {path} {op} {val} "
                           f"(obtuvo {B._get(out, path)!r})")
        # arrastrar estado
        _aplicar(cart, out)
        if out.get("zona_o_cp"):
            zona = out["zona_o_cp"]
        if turno.get("bot") and not turno["bot"].startswith("Bot:"):
            pregunta = ""  # la pregunta se consumio
        # chequeo del carrito resultante
        for sub, cant in (turno.get("cart") or {}).items():
            k = _find(cart, sub)
            if not k or cart[k] != cant:
                ok = False
                log.append(f"  t{i} CART '{sub}'={cant} (carrito={cart})")
        for sub in (turno.get("cart_no") or []):
            if _find(cart, sub):
                ok = False
                log.append(f"  t{i} CART deberia NO tener '{sub}' (carrito={cart})")
        log.append(f"  t{i} \"{turno['msg']}\" -> op={out.get('operacion')} "
                   f"carrito={cart}")
    return ok, log


def main():
    print(f"[continuidad] {len(CHARLAS)} charlas, {REPS} pasadas c/u", flush=True)
    print("=" * 70, flush=True)
    estables = 0
    for charla in CHARLAS:
        pasos, ultimo_log = 0, []
        for _ in range(REPS):
            ok, log = _corre_charla(charla)
            if ok:
                pasos += 1
            else:
                ultimo_log = log
        etiqueta = ("ESTABLE OK " if pasos == REPS
                    else "FALLA FIJA " if pasos == 0 else "INESTABLE  ")
        if pasos == REPS:
            estables += 1
        print(f"[{etiqueta}] {charla['id']}: {pasos}/{REPS}", flush=True)
        for ln in ultimo_log:
            print(ln, flush=True)
        print("-" * 70, flush=True)
    print(f"CHARLAS ESTABLES: {estables}/{len(CHARLAS)}", flush=True)


if __name__ == "__main__":
    main()
