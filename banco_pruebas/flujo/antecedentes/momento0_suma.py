"""EMBEDDINGS EN LA LLAMADA 0, SOBRE LO QUE REPARTIO EL MODELO (15-nov-2026).

Orden de Martin del 15-nov. La forma de medir: el modelo reparte el mensaje en una linea por cosa que pide el cliente, y
cada linea trae el fragmento, las palabras del cliente para esa cosa. Los embeddings se miden sobre esos fragmentos: cada
uno se busca contra los rubros de la tienda con sus alias, y su rubro primero se compara con el de lo que tradujo el
modelo. Sin gasto: los puntajes ya estan en `nexo_rubro_puntajes.json`.

LA VARA, por mensaje y por rubro, para no depender de como el modelo escribio el fragmento:
  cada producto que la tienda vende tiene su rubro esperado, `engranaje0._esperado`.
  trae      el rubro esperado esta entre los que da la busqueda para ese mensaje.
  sobra     un rubro que da la busqueda y el mensaje no pide.
Se cuenta para lo que tradujo el modelo, para los fragmentos, y para los dos juntos. Y se listan las lineas donde los dos
no coinciden, con el rubro esperado.

    python3 banco_pruebas/flujo/antecedentes/momento0_suma.py
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import entorno  # noqa: E402,F401

import engranaje0 as E  # noqa: E402
import nexo_rubro as NR  # noqa: E402
from nuevas70 import CASOS  # noqa: E402


def main():
    nx = NR.Nexo()
    esperado = E._esperado()
    lineas = NR.lineas_v2()

    def rubro(q):
        return nx._rank_rubros(q)[0] if q else None

    print("\nEMBEDDINGS EN LA LLAMADA 0, SOBRE LO QUE REPARTIO EL MODELO · 70 mensajes, v2 grabada, sin gasto")
    for m in NR.MODELOS:
        c = collections.Counter()
        distintas = []
        for cid, _, cosas in CASOS:
            pide = {esperado[(cid, i)] for i in range(len(cosas)) if (cid, i) in esperado} - {"ninguno"}
            c["pide"] += len(pide)
            tradujo, fragmento = set(), set()
            for l in lineas.get((m, cid), []):
                rb, rf = rubro(l["busqueda"]), rubro(l.get("fragmento"))
                tradujo.add(rb)
                fragmento.add(rf)
                if rb != rf:
                    distintas.append((cid, l["busqueda"], rb, l.get("fragmento"), rf, sorted(pide)))
            for nombre, da in (("lo que tradujo", tradujo), ("los fragmentos", fragmento),
                               ("los dos juntos", tradujo | fragmento)):
                c[nombre + " trae"] += len(pide & da)
                c[nombre + " sobra"] += len(da - pide)
        print(f"\n  {m}: de {c['pide']} rubros pedidos")
        for nombre in ("lo que tradujo", "los fragmentos", "los dos juntos"):
            print(f"    {nombre:15} trae {c[nombre + ' trae']:>3} · sobran {c[nombre + ' sobra']:>3}")
        print(f"    lineas donde no coinciden: {len(distintas)}")
        for cid, b, rb, f, rf, pide in distintas:
            print(f"    {cid} '{b}' -> {rb} | '{f}' -> {rf} | pide {pide}")


if __name__ == "__main__":
    main()
