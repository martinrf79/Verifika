"""EL NEXO DE RUBRO Y PRODUCTO: LA SEGUNDA BUSQUEDA CONTRA LOS PRODUCTOS Y LA FUNCION DE CODIGO QUE ELIGE.

Pasado de `banco_pruebas/flujo/nexo_rubro.py` el 17-nov-2026, orden de Martin, tal cual: el banco importa de aca. Los
embeddings de lo que escribio la llamada 0 contra los rubros de la tienda dan tres rubros candidatos; dentro de esos, contra
cada modelo, cinco candidatos; el codigo elige el primero cuyo texto trae la primera palabra de la busqueda, y lo dudoso
lo confirma Jev. La calibracion, la vara y los numeros quedan en el banco.
"""
import csv
import functools
import json
import os
import re

DATOS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "data", "clientes"))
# Calibrado en el banco, `banco_pruebas/flujo/embeddings.py` NEXOS: cinco productos candidatos.
CANDIDATOS = 5
# FICHA 102: con "?", los productos que traen los embeddings del fragmento. Medido el 16-nov, `embeddings_candidatos.py`:
# con 8, el correcto entra en 25 de las 28 lineas con "?" del 18-nov.
K_DUDA = 8
NO_SABE = "?"
NINGUNO = "ninguno"
DESC_NINGUNO = "la tienda no tiene ese tipo de producto: ninguno de estos es lo que pide"


def n(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", t)).strip()


# ══ LA FUENTE ════════════════════════════════════════════════════════════════
@functools.lru_cache(maxsize=None)
def fuente(tid):
    filas = list(csv.DictReader(open(os.path.join(DATOS, tid, "productos.csv"), encoding="utf-8")))
    alias = json.load(open(os.path.join(DATOS, tid, "alias.json"), encoding="utf-8"))["rubros"]
    rubros = sorted({f["categoria"] for f in filas})
    modelos = {}
    for f in filas:
        modelos.setdefault((f["categoria"], f["marca"], f["modelo"]), []).append(f)
    return filas, alias, rubros, modelos


def doc_rubro(r, alias):
    return f"{r}: {', '.join(alias.get(r, []))}"


# Lo que la tienda declara que no vende, `no_vendidas.json`, entra al indice de rubros como rubro sin productos: si queda
# primero y la busqueda lo dice, no hay. Calibrado el 16-nov, `--calibrar`: lo que no se vende de nuevas70b pasa de 8 a
# 11 de 14.
NO_SE_VENDE = "no se vende: "


def indice_rubros(rubros, alias, tid):
    """[(rubro, documento)]: los rubros de la tienda con sus alias, y lo que declara que no vende."""
    d = json.load(open(os.path.join(DATOS, tid, "no_vendidas.json"), encoding="utf-8"))["no_vendidas"]
    return [(r, doc_rubro(r, alias)) for r in rubros] + [(NO_SE_VENDE + x, NO_SE_VENDE + x) for x in sorted(d)]


def etiquetas(filas):
    return sorted({t.strip() for f in filas for t in str(f.get("tags") or "").split(",") if t.strip()})


def doc_producto(k, filas, alias):
    """El modelo con los alias de su rubro adelante: calibrado el 16-nov, `--calibrar`, elige bien uno mas en cada
    corrida de nuevas70 y el rubro equivocado baja de 5 a 1. "pantalla tactil" ya no cae en monitor."""
    return f"{k[0]}: {', '.join(alias.get(k[0], []))}. {k[1]} {k[2]}. {', '.join(etiquetas(filas))}"




class Nexo:
    def __init__(self, tid, puntajes):
        """`puntajes`: {"rubros", "modelos", "consultas": {busqueda: {"r": [...], "m": [...]}}}, de `vectores`."""
        self.tid = tid
        self.filas, self.alias, _, self.modelos = fuente(tid)
        p = puntajes
        self.rubros, self.ms, self.q = p["rubros"], [tuple(m) for m in p["modelos"]], p["consultas"]
    def _rank_rubros(self, q):
        return [r for _, r in sorted(zip(self.q[q]["r"], self.rubros), reverse=True)] if q else []

    def _fila(self, k):
        con = [f for f in self.modelos[k] if int(f["stock"] or 0) > 0]
        if not con:
            return None
        f = min(con, key=lambda f: float(f["precio_ars"]))
        return {"id": f["id"], "nombre": f["nombre"], "rubro": k[0], "precio": int(float(f["precio_ars"])),
                "stock": int(f["stock"]), "modelo": list(k)}

    def busqueda2(self, linea, rubros):
        """PIEZA 2: los cinco candidatos, el mejor de cada rubro y los dos que siguen, en el orden de los embeddings."""
        orden = [k for _, k in sorted(zip(self.q[str(linea["busqueda"])]["m"], self.ms), reverse=True) if k[0] in rubros]
        filas = [f for f in map(self._fila, orden) if f]
        primeros = [next(f for f in filas if f["rubro"] == r) for r in rubros if any(f["rubro"] == r for f in filas)]
        resto = [f for f in filas if f not in primeros][:CANDIDATOS - len(primeros)]
        return sorted(primeros + resto, key=filas.index)

    def producto(self, linea):
        """La regla de la FICHA 102, 18-nov, orden de Martin. Cuando la llamada 0 tradujo, su producto es la verdad: los
        embeddings del producto solo lo ubican en el rubro mas parecido, y si lo mas parecido es algo que la tienda
        declara que no vende, no hay. Cuando escribio "?", los embeddings del fragmento traen 8 productos; sus rubros, con
        esos productos de ejemplo, quedan dudosos para Jev, y ninguno es repregunta. Dentro del rubro, la busqueda entera,
        producto y condiciones, ordena los candidatos. Medido en el banco, `embeddings_candidatos.py --definida v7`:
        traducidas 608 de 620; con "?", Jev 22 bien, 6 ninguno y 0 mal de 28. Sin campo producto, el de la v2, la
        busqueda entera hace de producto."""
        b = str(linea["busqueda"])
        pr = str(linea.get("producto") or b).strip()
        base = {"busqueda": b, "fragmento": linea.get("fragmento"), "pedido": pr, "duda": pr == NO_SABE}
        if pr == NO_SABE:
            cerca = [k for _, k in sorted(zip(self.q[str(linea.get("fragmento") or b)]["m"], self.ms), reverse=True)][:K_DUDA]
            rubros = list(dict.fromkeys(k[0] for k in cerca))
            ejemplos = {r: [f"{k[1]} {k[2]}" for k in cerca if k[0] == r] for r in rubros}
            cands = [f for f in (self.busqueda2(linea, [r]) for r in rubros) for f in f[:1]]
            return {**base, "rubros": [f["rubro"] for f in cands], "ejemplos": ejemplos, "candidatos": cands,
                    "elegido": None, "no_hay": False, "dudoso": bool(cands), "cercano": None}
        primero = (self._rank_rubros(pr) or [""])[0]
        if not primero or primero.startswith(NO_SE_VENDE):
            # Lo mas parecido es algo que la tienda declara que no vende: no hay, y no se ofrece nada a ciegas.
            return {**base, "rubros": [], "candidatos": [], "elegido": None, "no_hay": True, "dudoso": False,
                    "cercano": None}
        cands = self.busqueda2(linea, [primero])
        return {**base, "rubros": [primero], "candidatos": cands, "elegido": cands[0] if cands else None,
                "no_hay": not cands, "dudoso": False, "cercano": cands[0] if cands else None}
