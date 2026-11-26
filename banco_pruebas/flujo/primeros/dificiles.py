"""LA RUEDA SOBRE LAS 300 DIFICILES DE LA FICHA 104 (26-nov-2026, pedido de Martin). Sin gasto: lo que Luna separo con el
v14f1b ya esta grabado en `grabado/llamada0_modelos.jsonl`, y la vara es la de `embeddings_antes.mensajes()`: los rubros
esperados de las 200 dificiles y de los 100 negativos, mas lo que la tienda no vende de `bancos/negativos100.py`.

Por mensaje, lo que la rueda ofreceria: el rubro de cada fila con corchete de producto que `existe` no descarta. Se cuenta:
  todos los rubros esperados ofrecidos, rubros esperados que faltan, rubros ofrecidos que no se pidieron, y en los
  negativos, lo que la tienda no vende que termina ofrecido como un rubro de la tienda.

    python3 primeros/dificiles.py [--ver]
"""
import collections, json, os, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
FL = os.path.join(AQUI, "..")
sys.path[:0] = [AQUI, FL, os.path.join(FL, "bancos")]
sys.dont_write_bytecode = True
_argv, sys.argv = sys.argv, ["x"]
import cadena as C  # noqa: E402
import embeddings_antes as EA  # noqa: E402
from entorno import GRABADO  # noqa: E402
from negativos100 import CASOS  # noqa: E402
sys.argv = _argv
nrm = C.nrm


def main(ver):
    # La clave es (banco, id): los ids se repiten entre bancos, R04 de las reales y R04 de las 525.
    g = {(r["banco"], r["id"]): r for r in map(json.loads, open(os.path.join(GRABADO, "llamada0_modelos.jsonl")))
         if r["corrida"] == "luna" and r["prompt"] == "v14f1b"}
    no_vende = {cid: [nrm(x) for x in e["no_vende"]] for cid, _, e in CASOS}
    n, fallas = collections.Counter(), []
    for conj, banco, cid, texto, esperados, _ in EA.mensajes():
        r = g.get((banco, cid))
        if r is None:
            n["sin grabar"] += 1
            continue
        ofrece, sin_rubro = set(), []
        for t in (r["salida"] or {}).get("textos") or []:
            for f in C.leer(str(t)):
                if not f["nombra"]:
                    continue
                if not f["rubro"]:
                    sin_rubro.append(f["consulta"][:40])
                    continue
                v, _ = C.EX.existe(f["nombre"] or f["consulta"], aislado=True)
                if v != "no_hay":
                    ofrece.add(f["rubro"])
        esp = {nrm(x) for x in esperados}
        n[conj + " mensajes"] += 1
        if esp:
            n[conj + " con rubro esperado"] += 1
            n[conj + " todos los rubros ofrecidos"] += esp <= ofrece
            n[conj + " rubros esperados"] += len(esp)
            n[conj + " rubros que faltan"] += len(esp - ofrece)
        de_mas = ofrece - esp
        n[conj + " mensajes con rubro de mas"] += bool(de_mas)
        nv = no_vende.get(cid) if conj == "neg100" else None
        if nv:
            n["neg100 con algo que no se vende"] += 1
            n["neg100 lo no vendido ofrecido como otro rubro"] += bool(de_mas)
        if (esp - ofrece) or de_mas:
            fallas.append(f"{cid:6} falta {sorted(esp - ofrece)} de mas {sorted(de_mas)} sin rubro {sin_rubro}"
                          f" | {texto[:70]!r}")
    for k in sorted(n):
        print(f"  {k:48} {n[k]}")
    if ver:
        for f in fallas:
            print("   ", f)


if __name__ == "__main__":
    main("--ver" in sys.argv)
