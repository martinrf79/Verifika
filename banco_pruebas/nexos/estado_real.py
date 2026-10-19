"""EL ESTADO REAL — la ficha 10 con lo que arma produccion, no con lo escrito a mano (19-oct-2026).

La FICHA 69 midio que la traduccion cae cuando el estado de la charla lo arma produccion. Este banco cierra ese hueco
para las charlas de memoria de las 58:
  1. reproduce SIN MODELO los turnos anteriores de una charla grabada —`sonda_charlas`, lo crudo del modelo de
     produccion— por el clon, el codigo de hoy entero;
  2. lee el documento de la charla que quedo en el doble de Firestore y lo pasa por `ficha_charla.estado`, que es lo
     que el tablero usa;
  3. lo traduce a lo que lee la ficha 10, `ctx_de_estado`. Es la pieza que necesita el tablero para recibir la ficha.

  python3 banco_pruebas/nexos/estado_real.py --comparar gp_basemontos_1     el estado real contra el escrito a mano
  python3 banco_pruebas/nexos/estado_real.py --ronda f10_real_g1 --de gp_basemontos_1    la ficha 10 con el real
"""
import contextlib
import io
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, AQUI)
sys.path.insert(0, RAIZ)
import desmenuzado as D  # noqa: E402
import casos58  # noqa: E402

GRABADAS = os.path.join(RAIZ, "banco_pruebas", "sonda_charlas_corridas.jsonl")


def grabada(etiqueta: str, cid: str) -> dict:
    for x in open(GRABADAS, encoding="utf-8"):
        f = json.loads(x)
        if f["etiqueta"] == etiqueta and f["id"] == cid:
            return f
    return {}


def conv_antes_del_ultimo(etiqueta: str, cid: str) -> dict:
    """El documento de la charla como lo dejo produccion antes del ultimo mensaje, reproducido sin modelo."""
    from banco_pruebas import sonda_charlas as S
    from app.storage.firestore_client import get_conversation
    g = grabada(etiqueta, cid)
    vara = {c["id"]: c for c in S.charlas("todas")}
    charla = dict(vara[cid], turnos=vara[cid]["turnos"][:-1])
    if not charla["turnos"] or not g:
        return {}
    with contextlib.redirect_stdout(io.StringIO()):
        S.correr_clon(charla, n_corrida=0, grabado=g["turnos"][:-1])
    return get_conversation(f"sonda_{cid}_0", tienda_id=D.TIENDA)


def ctx_de_estado(conv: dict) -> dict:
    """LO QUE LEE LA FICHA 10, desde el estado de produccion: lo mostrado en el ultimo mensaje, el pedido con su
    destino, lo que busco el cliente, las exclusiones que siguen valiendo y los dos ultimos intercambios."""
    from app.core import ficha_charla as FC
    from app.core import tablero as T
    e = FC.estado(conv)
    vistos = [str(p["id"]) for g in e["mostrado"] for p in g[:1] if str(p.get("id")) in D.POR_ID]
    carrito = []
    for g in e["pedido"]:
        for it in g["items"]:
            if it["producto"] in D.POR_ID:
                carrito.append((it["producto"], it["cantidad"], g.get("destino") or ""))
    excl = [str(c["valor"]) for c in T.exclusiones_vigentes(e["busquedas"]) if c.get("campo") == "marca"]
    hist = [h for h in conv.get("history") or [] if isinstance(h, dict)]
    antes, cli = [], None
    for h in hist:
        rol, txt = h.get("role"), str(h.get("content") or h.get("text") or "")
        if rol == "user":
            cli = txt
        elif rol in ("assistant", "model") and cli is not None:
            antes.append((cli, txt))
            cli = None
    ctx = {"antes": antes[-2:], "vistos": vistos}
    if carrito:
        ctx["carrito"] = carrito
    if e.get("criterio"):
        ctx["criterio"] = e["criterio"]
    if excl:
        ctx["excluye"] = excl
    return ctx


def casos_reales(etiqueta: str) -> list:
    """Las charlas de memoria de las 58 con el estado que armo produccion en lugar del escrito a mano."""
    out = []
    for cid, ctx, msg, esp in casos58.CASOS_58:
        if not ctx or not grabada(etiqueta, cid):
            continue
        out.append((cid, ctx_de_estado(conv_antes_del_ultimo(etiqueta, cid)), msg, esp))
    return out


def comparar(etiqueta: str):
    a_mano = {c[0]: c[1] for c in casos58.CASOS_58}
    for cid, real, msg, _ in casos_reales(etiqueta):
        m = a_mano[cid]
        print(f"\n== {cid}: {msg}")
        for k in ("vistos", "carrito", "criterio", "excluye"):
            if m.get(k) != real.get(k):
                print(f"   {k:9s} a mano {m.get(k)}  ·  real {real.get(k)}")
        print(f"   antes    real {len(real.get('antes', []))} intercambios, a mano {len(m.get('antes', []))}")


if __name__ == "__main__":
    with contextlib.redirect_stdout(io.StringIO()):
        D.preparar()
    a = sys.argv
    de = a[a.index("--de") + 1] if "--de" in a else "gp_basemontos_1"
    if "--comparar" in a:
        comparar(a[a.index("--comparar") + 1])
    if "--ronda" in a:
        import ficha_casillas as F
        import ficha10 as X
        reales = casos_reales(de)
        D.CASOS, D.RESERVA = reales, casos58.RESERVA_58
        F.FICHA["version"], F.INFO["version"] = 9, 2
        X.con_info_10()
        F.ronda(a[a.index("--ronda") + 1], 0)
