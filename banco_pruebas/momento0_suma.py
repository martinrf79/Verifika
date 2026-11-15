"""EL MOMENTO CERO EN EQUIPO, RECALIBRADO: LOS EMBEDDINGS LEEN AL CLIENTE POR SU CUENTA (15-nov-2026).

Orden de Martin del 15-nov. Reemplaza a la medicion del 14-nov, que esta en git, 6b05fef, y tenia dos baches: decidia el
rescate mirando la respuesta esperada, y solo contaba las lineas cuyo fragmento nombraba el producto. Y corrige el error
de la sesion: si los embeddings buscan solo con lo que tradujo el modelo, no pueden sumar lo que el modelo no vio.

LO QUE HACE CADA PARTE, sobre la v2 grabada del engranaje 0 y los 70 mensajes de `nuevas70.py`:
  el modelo     por cada linea con busqueda, su rubro por embeddings con lo que tradujo, contra los rubros de la tienda
                con sus alias. Es lo que el modelo entendio.
  el cliente    el mensaje se corta en partes por la puntuacion y por "y", "e", "o", "pero", "ni", "+". Cada parte se
                busca por embeddings contra los mismos rubros, sin mirar al modelo. Es lo que dijo el cliente.
  lo no visto   una parte del cliente que el modelo no uso: menos de la mitad de sus palabras de tres letras o mas estan
                en algun campo de la salida del modelo. Es el mismo criterio de `engranaje0.fiel`. Esa parte es lo que el
                modelo no vio, y su rubro se suma como dudoso.
  la linea      el rubro de lo que tradujo el modelo y el de su fragmento: si coinciden, firme; si no, los dos van como
                dudosos. Ninguno vota sobre el otro.
  de producto   una parte del cliente que el modelo uso para una linea con busqueda: la mitad o mas de sus palabras estan
                en el fragmento o la busqueda de esa linea. Es la palabra del cliente sobre un producto que el modelo vio,
                cortada fina: "cada uno lleva un mouse" y "unos auris" por separado, aunque el modelo los junto en un
                combo. Esta variante se sumo despues de ver las cuatro primeras.

LA VARA, escrita antes de correr, por mensaje y por rubro, sin mirar el texto del fragmento:
  cada producto que la tienda vende tiene su rubro esperado, `engranaje0._esperado`.
  traido     el rubro esperado esta entre los que propone el momento cero para ese mensaje.
  sobrante   un rubro propuesto que el mensaje no pide: es ruido que le llega al nexo.
  Se cuenta para el modelo solo, para el modelo mas el cliente entero, y para el modelo mas lo no visto.
  Lo que la tienda no vende: cuantos rubros le proponen, que el nexo despues tiene que poder descartar.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/momento0_suma.py --embeddings   # las partes, centavos
    python3 banco_pruebas/momento0_suma.py [--ver]                                         # sin gasto
"""
import collections
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(AQUI), AQUI]

import engranaje0 as E  # noqa: E402
import nexo_rubro as NR  # noqa: E402
from nuevas70 import CASOS  # noqa: E402

PARTES = os.path.join(AQUI, "momento0_suma_partes.json")
CORTES = r"[,.;:!?¿¡\n+/]| y | e | o | pero | ni "
CAMPOS = ("fragmento", "busqueda", "destino", "plata", "orden", "condiciones")


def partes(texto):
    return [p.strip() for p in re.split(CORTES, f" {texto} ", flags=re.I) if len(E._palabras(p)) >= 1]


def no_visto(parte, salida):
    """La parte que el modelo no uso: menos de la mitad de sus palabras estan en algun campo de su salida."""
    usado = " ".join(E.n(" ".join(l.get(k)) if isinstance(l.get(k), list) else l.get(k))
                     for l in salida.get("lineas") or [] for k in CAMPOS)
    ps = E._palabras(parte)
    return sum(p in usado.split() for p in ps) / len(ps) < 0.5


def de_producto(parte, ls):
    """La parte que el modelo uso para una linea de producto: la mitad o mas de sus palabras estan en el fragmento o la
    busqueda de alguna linea con busqueda. Es la palabra del cliente sobre un producto que el modelo si vio."""
    ps = E._palabras(parte)
    for l in ls:
        usado = (E.n(l.get("fragmento")) + " " + E.n(l.get("busqueda"))).split()
        if sum(p in usado for p in ps) / len(ps) >= 0.5:
            return True
    return False


def embeddings():
    if not os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
        raise SystemExit("los embeddings van con la paga: falta MARTIN_AUTORIZO_LA_PAGA=<fecha>")
    import llamada1_modelos as L
    _, alias, rubros, _ = NR.fuente()
    cache = json.load(open(NR.CACHE)) if os.path.exists(NR.CACHE) else {}
    qs = sorted({p for _, texto, _ in CASOS for p in partes(texto)})
    clave = os.environ["GEMINI_API_KEY_PROD"].strip()
    dr = L._emb([NR.doc_rubro(r, alias) for r in rubros], "RETRIEVAL_DOCUMENT", clave, cache)
    vq = L._emb(qs, "RETRIEVAL_QUERY", clave, cache)
    json.dump(cache, open(NR.CACHE, "w"))
    out = {q: [round(sum(a * b for a, b in zip(x, d)), 4) for d in dr] for q, x in zip(qs, vq)}
    json.dump({"rubros": rubros, "partes": out}, open(PARTES, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{len(qs)} partes de los mensajes, {sum(len(q) for q in qs)} caracteres")


def main(ver=False):
    p = json.load(open(PARTES, encoding="utf-8"))
    nx = NR.Nexo()
    rubros = p["rubros"]

    def primero_parte(q):
        return max(zip(p["partes"][q], rubros))[1]

    def primero(q):
        return nx._rank_rubros(q)[0] if q else None

    esperado = E._esperado()
    salidas = {(r["modelo"], r["id"]): r["salida"] for r in map(json.loads, open(E.SALIDA))
               if r["v"] == "v2" and r.get("salida")}
    print("\nEL MOMENTO CERO EN EQUIPO, RECALIBRADO · por mensaje y por rubro, 70 mensajes, v2 grabada")
    for m in NR.MODELOS:
        c = collections.Counter()
        detalle = []
        for cid, texto, cosas in CASOS:
            sal = salidas.get((m, cid)) or {"lineas": []}
            ls = [l for l in sal["lineas"] if str(l.get("busqueda") or "").strip()]
            firmes, dudosos = set(), set()
            for l in ls:
                rb, rf = primero(l["busqueda"]), primero(l.get("fragmento"))
                (firmes if rb == rf else dudosos).update({rb} if rb == rf else {rb, rf} - {None})
            modelo = {primero(l["busqueda"]) for l in ls}
            ps = partes(texto)
            cliente = {primero_parte(q) for q in ps}
            nv = [q for q in ps if no_visto(q, sal)]
            no_vistos = {primero_parte(q) for q in nv}
            de_prod = {primero_parte(q) for q in ps if de_producto(q, ls)}
            pide = {esperado[(cid, i)] for i in range(len(cosas)) if (cid, i) in esperado} - {"ninguno"}
            no_vende = [cosas[i]["en"][0] for i in range(len(cosas)) if esperado.get((cid, i)) == "ninguno"]
            for nombre, propone in (("modelo", modelo), ("modelo y linea", modelo | firmes | dudosos),
                                    ("modelo y no visto", modelo | no_vistos), ("modelo y cliente", modelo | cliente),
                                    ("modelo y producto", modelo | de_prod)):
                c[f"{nombre} traido"] += len(pide & propone)
                c[f"{nombre} sobrante"] += len(propone - pide)
            c["pide"] += len(pide)
            c["no visto partes"] += len(nv)
            falta = pide - modelo
            if falta or (ver and nv):
                detalle.append((cid, sorted(falta), [(q, primero_parte(q)) for q in nv]))
            c["no vende"] += len(no_vende)
        print(f"\n  {m}: de {c['pide']} rubros pedidos en los 70 mensajes")
        for nombre in ("modelo", "modelo y linea", "modelo y no visto", "modelo y cliente", "modelo y producto"):
            print(f"    {nombre:18} trae {c[nombre + ' traido']:>3} · sobrantes {c[nombre + ' sobrante']:>3}")
        print(f"    partes que el modelo no uso: {c['no visto partes']}")
        for cid, falta, nv in detalle:
            print(f"    {cid} falta al modelo {falta} · no visto {nv}")


if __name__ == "__main__":
    if "--embeddings" in sys.argv:
        embeddings()
    else:
        main("--ver" in sys.argv)
