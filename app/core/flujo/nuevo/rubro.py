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
# Calibrados en el banco, `banco_pruebas/flujo/embeddings.py` NEXOS: tres rubros y cinco productos candidatos.
RUBROS_CANDIDATOS, CANDIDATOS = 3, 5
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


def _doc_etiquetas(k, filas, alias=None):
    """El documento de antes del 16-nov, para la V0 de la calibracion."""
    return f"{k[0]} {k[1]} {k[2]}. {', '.join(etiquetas(filas))}"




class Nexo:
    def __init__(self, tid, puntajes):
        """`puntajes`: {"rubros", "modelos", "consultas": {busqueda: {"r": [...], "m": [...]}}}, de `vectores`."""
        self.tid = tid
        self.filas, self.alias, _, self.modelos = fuente(tid)
        p = puntajes
        self.rubros, self.ms, self.q = p["rubros"], [tuple(m) for m in p["modelos"]], p["consultas"]
        # El texto de la tienda de cada modelo, para la funcion que elige.
        self.texto = {}
        for k, fs in self.modelos.items():
            formas = [k[0], k[1], k[2]] + [f["nombre"] for f in fs] + etiquetas(fs) + self.alias.get(k[0], [])
            self.texto[k] = set(" ".join(n(x) for x in formas).split())
        # Lo firme de cada modelo: su nombre y su rubro. Lo que solo esta en etiquetas o alias es dudoso.
        self.firme = {k: set(" ".join(n(x) for x in [k[0]] + [f["nombre"] for f in fs]).split())
                      for k, fs in self.modelos.items()}

    def _rank_rubros(self, q):
        return [r for _, r in sorted(zip(self.q[q]["r"], self.rubros), reverse=True)] if q else []

    n_rubros = RUBROS_CANDIDATOS

    def llamada0(self, linea):
        """PIEZA 1: los tres rubros candidatos de lo que tradujo el modelo, entre los que la tienda vende."""
        return [r for r in self._rank_rubros(str(linea["busqueda"])) if not r.startswith(NO_SE_VENDE)][:self.n_rubros]

    def _fila(self, k):
        con = [f for f in self.modelos[k] if int(f["stock"] or 0) > 0]
        if not con:
            return None
        f = min(con, key=lambda f: float(f["precio_ars"]))
        return {"id": f["id"], "nombre": f["nombre"], "rubro": k[0], "precio": int(float(f["precio_ars"])),
                "stock": int(f["stock"]), "modelo": list(k)}

    @staticmethod
    def _lo_dice(busqueda, negativo):
        """Lo que no se vende gana solo si es lo que pide la busqueda, su primera palabra, como en la funcion que elige:
        los embeddings proponen y el codigo confirma. "sony xm5" queda cerca de "play 5" por Sony, y en "auriculares
        ps5" lo pedido son auriculares: la PS5 es con que se usan. Medido el 16-nov en los mensajes reales."""
        ws = [w for w in n(busqueda).split() if not w.isdigit()]
        ps = n(negativo[len(NO_SE_VENDE):]).split()
        return bool(ws) and all(any(w == p or (min(len(w), len(p)) >= 4 and (w.startswith(p) or p.startswith(w)))
                                    for w in ws[:len(ps)]) for p in ps)

    def busqueda2(self, linea, rubros):
        """PIEZA 2: los cinco candidatos, el mejor de cada rubro y los dos que siguen, en el orden de los embeddings."""
        orden = [k for _, k in sorted(zip(self.q[str(linea["busqueda"])]["m"], self.ms), reverse=True) if k[0] in rubros]
        filas = [f for f in map(self._fila, orden) if f]
        primeros = [next(f for f in filas if f["rubro"] == r) for r in rubros if any(f["rubro"] == r for f in filas)]
        resto = [f for f in filas if f not in primeros][:CANDIDATOS - len(primeros)]
        return sorted(primeros + resto, key=filas.index)

    def elegir(self, linea, candidatos):
        """PIEZA 3: el primer candidato cuyo texto de la tienda trae la primera palabra de lo que tradujo el modelo."""
        palabras = [w for w in n(linea["busqueda"]).split() if not w.isdigit()]
        pedido = palabras[0] if palabras else ""

        def trae(k, donde):
            return any(w == pedido or (min(len(w), len(pedido)) >= 4 and (w.startswith(pedido) or pedido.startswith(w)))
                       for w in donde[k])
        elegido = next((f for f in candidatos if trae(tuple(f["modelo"]), self.texto)), None)
        # Dudoso: no hay, o se eligio por una palabra que solo esta en etiquetas o alias. Eso lo confirma Jev.
        dudoso = bool(candidatos) and (elegido is None or not trae(tuple(elegido["modelo"]), self.firme))
        return {"pedido": pedido, "elegido": elegido, "no_hay": elegido is None, "dudoso": dudoso,
                "cercano": candidatos[0] if candidatos else None}

    def producto(self, linea):
        primero = (self._rank_rubros(str(linea["busqueda"])) or [""])[0]
        rubros = self.llamada0(linea)
        if primero.startswith(NO_SE_VENDE) and self._lo_dice(linea["busqueda"], primero):
            # Lo mas parecido es algo que la tienda declara que no vende: no hay, y no se ofrece nada a ciegas.
            return {"busqueda": linea["busqueda"], "fragmento": linea.get("fragmento"), "rubros": rubros,
                    "candidatos": [], "pedido": "", "elegido": None, "no_hay": True, "dudoso": False, "cercano": None}
        cands = self.busqueda2(linea, rubros)
        return {"busqueda": linea["busqueda"], "fragmento": linea.get("fragmento"), "rubros": rubros,
                "candidatos": cands, **self.elegir(linea, cands)}

