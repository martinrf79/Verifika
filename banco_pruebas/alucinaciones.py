"""EL BANCO DE ALUCINACIONES — cuantas caza el verificador y cuantas falsas alarmas da (29-oct-2026, FICHA 83).

Toma las respuestas ya grabadas del buscador, `buscador_agente.jsonl` y `buscador_charlas.jsonl`, cada una con su fuente:
lo que devolvieron las herramientas, la charla de antes y el mensaje del cliente. Sin modelo.

  falsas alarmas  el verificador sobre cada respuesta tal cual. Lo que marca se audita: puede ser una alucinacion real.
  inyectadas      a cada respuesta que nombra un producto se le mete una alucinacion de cada clase: un precio cambiado,
                  un producto que no salio de la fuente, un atributo que el producto no tiene, un superlativo falso, el
                  stock al reves, una medida inventada y un CBU inventado. Se cuenta si el verificador la caza.
La vara, fijada antes de medir: caza 95% o mas de las inyectadas; falsa alarma en 5% o menos de las respuestas.

    python3 banco_pruebas/alucinaciones.py [--ver]
"""
import collections
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import buscador_agente as B  # noqa: E402
import verificador as V  # noqa: E402
from app.core.flujo import catalogo as K  # noqa: E402

VER = "--ver" in B.ARGS
CLASES = ["dato", "producto", "atributo", "superlativo", "stock", "medida", "pago"]


def respuestas() -> list:
    """(id, respuesta, fuente, pegados) de cada turno grabado del buscador. De los turnos sueltos van solo los primeros:
    los de charla no tienen grabada la charla de antes, que es parte de su fuente; esos van de las charlas enteras."""
    out = []
    for r in map(json.loads, open(os.path.join(AQUI, "buscador_agente.jsonl"), encoding="utf-8")):
        if r.get("respuesta") and r["turno"] == 0:
            salidas = [p["devuelve"] for p in r.get("pasos") or []]
            out.append((f"{r['id']} t{r['turno']} {r['conjunto']}", r["respuesta"], " ".join(salidas + [r["mensaje"]]),
                        salidas))
    previas = collections.defaultdict(list)
    for r in sorted(map(json.loads, open(os.path.join(AQUI, "buscador_charlas.jsonl"), encoding="utf-8")),
                    key=lambda r: (r["id"], r["turno"])):
        if r.get("respuesta"):
            fuente = " ".join([p["devuelve"] for p in r.get("pasos") or []] + previas[r["id"]] + [r["mensaje"],
                              json.dumps(r.get("memoria") or {}, ensure_ascii=False)])
            out.append((f"{r['id']} t{r['turno']} charla", r["respuesta"], fuente,
                        [p["devuelve"] for p in r.get("pasos") or []]))
            previas[r["id"]] += [r["mensaje"], r["respuesta"]]
    return out


def inyectar(resp: str, fuente: str) -> dict:
    """{clase: respuesta con una alucinacion de esa clase}, para las que se pueden armar con esta respuesta."""
    todos = K.productos(B.TID)
    f = K.n(fuente)
    nombrados = [p for _, p in V._productos(resp) if V._en_fuente(p, f)]
    out = {}
    m = re.search(r"\$\s?(\d[\d.]*)", resp)
    if m:
        v = int(re.sub(r"\D", "", m.group(1)))
        nuevo = f"${(v * 11 // 10 // 500 * 500 + 500):,}".replace(",", ".")
        out["dato"] = resp[:m.start()] + nuevo + resp[m.end():]
    out["pago"] = resp + "\nTransferi al CBU 1234567890123456789012."
    if not nombrados:
        return out
    p = nombrados[0]
    corto = f"{p.get('marca')} {p.get('modelo')}"
    rubro = [x for x in todos if x.get("categoria") == p.get("categoria")]
    otro = next((x for x in rubro if not V._en_fuente(x, f) and x.get("modelo") != p.get("modelo")), None)
    if otro:
        out["producto"] = resp + f"\nTambien te recomiendo el {otro['nombre']}."
    for w in ("inalambrico", "con cable", "rgb", "bluetooth", "mecanico", "usb"):
        filtro = K.atar(w, rubro, B.TID)
        if "campo" in filtro and not K.cumple(p, filtro):
            out["atributo"] = resp + f"\nEl {corto} es {w}."
            break
    vistos = [x for x in rubro if V._en_fuente(x, f)]
    if not V._primero(p, "precio_ars", 1, rubro) and not V._primero(p, "precio_ars", 1, vistos):
        out["superlativo"] = resp + f"\nEl {corto} es el mas barato que tenemos."
    if K.con_stock(p):
        out["stock"] = resp + f"\nEl {corto} no tiene stock."
    out["medida"] = resp + f"\nEl {corto} pesa 999 g."
    return out


def main() -> None:
    rs = respuestas()
    alarmas, cazadas, total, perdidas = [], collections.Counter(), collections.Counter(), []
    for rid, resp, fuente, pegados in rs:
        base = V.verificar(resp, fuente, pegados)
        if base:
            alarmas.append((rid, base, resp))
        for clase, mala in inyectar(resp, fuente).items():
            total[clase] += 1
            nuevos = [h for h in V.verificar(mala, fuente, pegados) if h not in base]
            if nuevos:
                cazadas[clase] += 1
            else:
                perdidas.append((rid, clase, mala[-160:]))
    n, t, c = len(rs), sum(total.values()), sum(cazadas.values())
    print(f"EL BANCO DE ALUCINACIONES · {n} respuestas grabadas del buscador")
    print("  vara: caza 95% o mas de las inyectadas; falsa alarma en 5% o menos de las respuestas")
    print(f"  inyectadas cazadas: {c} de {t} ({100 * c / max(t, 1):.1f}%)")
    for k in CLASES:
        if total[k]:
            print(f"    {k:12} {cazadas[k]} de {total[k]}")
    print(f"  respuestas tal cual con alguna marca: {len(alarmas)} de {n} ({100 * len(alarmas) / max(n, 1):.1f}%)"
          " · se auditan: pueden ser alucinaciones reales")
    print(f"  {'PASA' if c >= 0.95 * t and len(alarmas) <= 0.05 * n else 'no pasa'}")
    if VER:
        for rid, base, resp in alarmas:
            print(f"\n  MARCA {rid}: {base}\n    " + resp[:400].replace("\n", " | "))
        for rid, clase, mala in perdidas[:30]:
            print(f"\n  SE ESCAPA {rid} {clase}: ...{mala}".replace("\n", " | "))


if __name__ == "__main__":
    main()
