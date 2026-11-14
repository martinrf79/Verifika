"""EL MODELO MAS LOS EMBEDDINGS EN EL MOMENTO CERO: ¿CUANTO SUMAN LOS EMBEDDINGS A LA TRADUCCION DEL MODELO? (14-nov-2026)

Orden de Martin del 14-nov. Sin modelo y sin gasto: usa lo ya grabado.
  - La separacion y la traduccion del engranaje 0 v2, `engranaje0_corridas.jsonl`, con su vara de `nuevas70.py`.
  - Los embeddings de cada producto contra los rubros de la tienda con sus alias, `engranaje0_embeddings.json`: el rubro
    primero con la busqueda del modelo y con el fragmento del cliente.

LA REGLA, escrita antes de correr:
  Un producto que el modelo tradujo mal queda rescatado si la busqueda del modelo y el fragmento del cliente dan, los dos,
  el mismo rubro primero, y ese rubro es el esperado. Lo que el modelo perdio o reescribio no se rescata: no hay fragmento
  que buscar, o el fragmento no es del cliente.

Informa por modelo:
  1. el modelo solo, con su vara de siempre;
  2. el modelo mas los embeddings: los mensajes que pasan a estar bien;
  3. el riesgo de la regla: productos que la tienda vende donde las dos coinciden en un rubro equivocado, y productos que
     la tienda no vende donde las dos coinciden en un rubro, que se colarian sin el paso que confirma.

    python3 banco_pruebas/momento0_suma.py
"""
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(AQUI), AQUI]

import engranaje0 as E  # noqa: E402
from nuevas70 import CASOS  # noqa: E402


def main():
    casos = {c[0]: c for c in CASOS}
    esperado = E._esperado()
    emb = {(r["modelo"], r["id"], r["i"]): r
           for r in json.load(open(os.path.join(AQUI, "engranaje0_embeddings.json"), encoding="utf-8"))}
    filas = {(r["modelo"], r["id"]): r for r in map(json.loads, open(E.SALIDA)) if r["v"] == "v2"}

    def coincide(r):
        return bool(r and r["busqueda"] and r["fragmento"] and r["busqueda"][0][0] == r["fragmento"][0][0])

    print("\nEL MODELO MAS LOS EMBEDDINGS EN EL MOMENTO CERO · 70 mensajes nuevos, v2 grabada, sin gasto")
    for m in ("gemini", "haiku", "deepseek"):
        solo = suma = 0
        rescatados, quedan = [], []
        for cid, (_, texto, cosas) in casos.items():
            r = filas.get((m, cid))
            if not r or r.get("salida") is None:
                quedan.append((cid, ["sin salida valida"]))
                continue
            malas, _ = E.calificar_uno(texto, cosas, r["salida"], "v2")
            if not malas:
                solo += 1
                suma += 1
                continue
            # Cada "traduce mal" se cruza con su producto: el indice i de la cosa cuyo nombre es el de la falla.
            resto = []
            for x in malas:
                if not x.startswith("traduce mal"):
                    resto.append(x)
                    continue
                nombre = x.split(":")[1].split("->")[0].strip()
                i = next(k for k, c in enumerate(cosas) if c["en"][0] == nombre)
                e = emb.get((m, cid, i))
                if not (coincide(e) and e["busqueda"][0][0] == esperado.get((cid, i))):
                    resto.append(x)
            if resto:
                quedan.append((cid, resto))
            else:
                suma += 1
                rescatados.append(cid)
        mal_vendido = [(r["id"], r["texto_busqueda"], r["busqueda"][0][0], r["esperado"]) for k, r in emb.items()
                       if k[0] == m and r["esperado"] != "ninguno" and coincide(r)
                       and r["busqueda"][0][0] != r["esperado"]]
        colado = [(r["id"], r["texto_busqueda"], r["busqueda"][0][0]) for k, r in emb.items()
                  if k[0] == m and r["esperado"] == "ninguno" and coincide(r)]
        print(f"\n  {m}: el modelo solo {solo} de {len(casos)}; con los embeddings {suma} de {len(casos)}")
        print(f"    rescata: {', '.join(rescatados) or 'nada'}")
        for cid, ms in quedan:
            print(f"    queda: {cid} {ms}")
        print(f"    riesgo, vende y las dos coinciden en otro rubro: {mal_vendido or 'ninguno'}")
        print(f"    riesgo, no vende y las dos coinciden en un rubro: {colado}")


if __name__ == "__main__":
    main()
