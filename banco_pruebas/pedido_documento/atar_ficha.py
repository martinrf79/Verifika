"""DE LA FICHA A LA FUENTE — cuanto de lo que escribe el modelo ata el codigo de hoy, sin modelo (23-oct-2026).

La ficha nativa conserva lo que pide el cliente: 128 de 132 pares contra 89 del lenguaje natural libre. El cuello paso
al paso siguiente: las palabras de la ficha —"no fabricado en China", "el Deco", "cuanto tarda"— tienen que atarse a la
fuente con las herramientas que ya existen, sin modelo:
  producto     un renglon o un numero de la memoria; si no, `catalogo.identificar`; si no, el rubro
  destino      el padron de localidades, `normal.lugares`
  condicion    `catalogo.atar` sobre el rubro del articulo: un campo, un tope, o nada
  orden        las claves de `catalogo.ORDEN`
  pago         los medios que nombra la FAQ de formas de pago
  consulta     su herramienta: la regla por los temas de la FAQ, el envio por el padron, el producto por el marcador
Cada cosa se cuenta como atada o no, y si lo atado es lo correcto segun la ficha de la charla. Al final, lo que no se
ata, por clase y con sus palabras: la lista de lo que hay que resolver en el codigo.

    python3 banco_pruebas/pedido_documento/atar_ficha.py [--archivo ficha_v2.jsonl]
"""
import collections
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, AQUI)
from medir_ficha import pedido_correcto, articulos, tiene  # noqa: E402
from calificar import n, RUBRO_PAL, BARATO, producto_de, _lista, PS, TID  # noqa: E402
from fichas import CHARLAS  # noqa: E402
from app.core import fuente  # noqa: E402
from app.core.flujo import catalogo as K, marcador  # noqa: E402
from app.core.flujo.normal import lugares  # noqa: E402

VACIO = ("", "sin decir", "ninguna", "ninguno", "null", "none", "no especificado", "no especificada", "n/a")
MEDIOS = n(" ".join(str(x.get("texto")) for x in fuente.politicas_de(["formas_pago"], TID).get("politicas") or []))
HERRAMIENTA = {"buscar": "buscar", "producto": "producto", "comparar": None, "compatibilidad": "compatibilidad",
               "envio": "envio", "cuenta": "cuenta", "regla de la tienda": "politica", "saber general": "explicar"}


def rubro_de_palabras(ws: list) -> str:
    for w in ws:
        for r, ps in RUBRO_PAL.items():
            if w in ps:
                return r
    for w in ws:
        p = next((p for p in PS if n(p.get("modelo")).split()[:1] == [w]), None)
        if p:
            return p["categoria"]
    return ""


def atar_producto(it: dict, mem: dict) -> tuple:
    """(rubro, como lo ato)."""
    texto = f"{it.get('renglon') or ''} {it.get('producto') or ''}"
    ref = re.search(r"\b([LM])-?(\d+)\b", texto)
    if ref:
        p = producto_de(f"{ref.group(1)}{ref.group(2)}", mem)
        if p.get("categoria"):
            return p["categoria"], "memoria"
    idt = K.identificar(str(it.get("producto") or ""), str(it.get("color") or ""), TID)
    if idt["veredicto"] == "exists":
        return idt["producto"]["categoria"], "producto"
    cats = {p.get("categoria") for p in idt.get("opciones") or []}
    if len(cats) == 1:
        return cats.pop(), "producto ambiguo"
    r = K.solo_rubro(str(it.get("producto") or ""), TID) or K.rubro(str(it.get("producto") or ""), TID)
    return (r, "rubro") if r else ("", "no ata")


def frases(t) -> list:
    out = []
    for x in _lista(t):
        for f in re.split(r"[;,]|\by\b", str(x)):
            f = f.strip()
            if n(f) not in VACIO and len(n(f)) > 2:
                out.append(f)
    return out


def main(archivo: str = "ficha_v2.jsonl") -> None:
    filas = {(r["charla"], r["turno"]): r for r in map(json.loads, open(os.path.join(AQUI, archivo), encoding="utf-8"))
             if not r.get("error") and r.get("rep", 0) == 0}
    c = collections.defaultdict(collections.Counter)
    sueltas = collections.defaultdict(collections.Counter)
    for ch in CHARLAS:
        for t, tu in enumerate(ch["turnos"]):
            r = filas.get((ch["id"], t))
            if not r:
                continue
            try:
                ficha = json.loads(r["salida"])
            except ValueError:
                continue
            mem = tu["mem"]
            arts, _, _ = pedido_correcto(tu)
            its = articulos(ficha)
            pr = ficha.get("preferencias")
            prefs = frases(pr.get("condiciones") if isinstance(pr, dict) else pr)
            ordenes = [n(pr.get("orden"))] if isinstance(pr, dict) and pr.get("orden") else []
            for it in its:
                # El articulo de la ficha de la charla que le corresponde, para saber que era lo correcto.
                oro = next((a for a in arts if tiene(it["texto"], a["que"]) and (not a["dest"] or n(a["dest"]).split()[0]
                                                                                in n(it["destino"]))), None)
                rub, como = atar_producto(it, mem)
                c["producto"]["atado" if rub else "no atado"] += 1
                c["producto"][como] += 1
                if oro:
                    esperado = rubro_de_palabras(oro["que"])
                    c["producto"]["correcto" if esperado and rub == esperado else "otro rubro"] += bool(esperado)
                if not rub:
                    sueltas["producto"][str(it.get("producto"))] += 1
                d = str(it.get("destino") or "")
                if n(d) not in VACIO:
                    ls = lugares(d)
                    c["destino"]["atado" if ls else "no atado"] += 1
                    if oro and oro["dest"] and ls:
                        c["destino"]["correcto" if n(ls[0][0]).split()[0] == n(oro["dest"]).replace(" capital", "").split()[0]
                                      else "otro lugar"] += 1
                    if not ls:
                        sueltas["destino"][d] += 1
                univ = [p for p in PS if p.get("categoria") == rub]
                for o in ordenes + ([n(it["orden"])] if it.get("orden") else []):
                    if o not in VACIO and o != "nada":
                        c["orden"]["atado" if o in K.ORDEN else "no atado"] += 1
                        if o not in K.ORDEN:
                            sueltas["orden"][o] += 1
                for f in frases(it.get("condiciones")) + prefs:
                    if any(w in n(f) for w in BARATO + ["caro", "mejor", "liviano"]):
                        c["orden"]["atado" if n(f) in K.ORDEN else "no atado"] += 1
                        if n(f) not in K.ORDEN:
                            sueltas["orden"][n(f)] += 1
                        continue
                    a = K.atar(f, univ, TID)
                    ok = "campo" in a or "tope" in a or "todas" in a or "ninguno_de" in a
                    c["condicion"]["atado" if ok else "no atado"] += 1
                    gold = [g for g in (oro or {}).get("conds", []) if g.get("campos") and tiene(n(f), g["pal"])]
                    if gold and ok:
                        campos = {a.get("campo")} | {x.get("campo") for x in a.get("todas", []) + a.get("ninguno_de", [])}
                        c["condicion"]["al campo correcto" if campos & set(gold[0]["campos"]) else "a otro campo"] += 1
                    if not ok:
                        sueltas["condicion"][f"{rub or '?'}: {n(f)}"] += 1
            for m in _lista((ficha.get("pago") or {}).get("medios")):
                medio = n((m or {}).get("medio")) if isinstance(m, dict) else ""
                if medio in VACIO:
                    continue
                ok = any(w in MEDIOS for w in medio.split() if len(w) > 3)
                c["pago"]["atado" if ok else "no atado"] += 1
                if not ok:
                    sueltas["pago"][medio] += 1
            for q in _lista(ficha.get("consultas")):
                if not isinstance(q, dict):
                    continue
                tipo, sobre = n(q.get("tipo")), str(q.get("sobre") or "")
                h = HERRAMIENTA.get(tipo, "sin tipo")
                if h is None or h == "sin tipo":
                    c["consulta"][f"{tipo or 'sin tipo'}: sin herramienta"] += 1
                    sueltas["consulta"][f"{tipo}: {sobre[:60]}"] += 1
                    continue
                if h == "politica":
                    temas = {x for ts in marcador._temas(sobre, TID).values() for x in ts}
                    ok = bool(temas)
                elif h == "envio":
                    ok = bool(lugares(sobre)) or bool(re.search(r"\b[LM]-?\d", sobre))
                elif h in ("producto", "compatibilidad", "buscar"):
                    marcas = marcador.marcar(sobre, TID)
                    ok = bool(re.search(r"\b[LM]-?\d", sobre)) or any("producto" in e or "rubro" in e or "puede ser" in e
                                                                       for _, e in marcas)
                else:
                    ok = True
                c["consulta"][f"{h}: {'atada' if ok else 'no atada'}"] += 1
                if not ok:
                    sueltas["consulta"][f"{tipo}: {sobre[:70]}"] += 1
    print(f"DE LA FICHA A LA FUENTE · {archivo}, {len(filas)} turnos\n")
    for clase in ("producto", "destino", "condicion", "orden", "pago", "consulta"):
        print(f"{clase.upper()}: " + " · ".join(f"{k} {v}" for k, v in sorted(c[clase].items())))
    print("\nLO QUE EL CODIGO NO ATA:")
    for clase, cs in sueltas.items():
        print(f"  {clase}: " + "; ".join(f"{k} ({v})" if v > 1 else k for k, v in cs.most_common(25)))


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[a.index("--archivo") + 1] if "--archivo" in a else "ficha_v2.jsonl")
