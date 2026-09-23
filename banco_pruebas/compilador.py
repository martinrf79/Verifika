#!/usr/bin/env python3
"""EL COMPILADOR — de la ficha del traductor al pedido que ejecuta el motor.

QUE ES. El prototipo, en el banco, de los pasos 1 a 3 del plan del 23-sep:
VALIDAR la ficha, ATERRIZAR las palabras del cliente en valores del catalogo
y COMPILAR la ficha al pedido. El pedido sale con la MISMA forma que hoy
escribe el modelo en el camino vivo —consultas, temas, envios, reparto,
afirma—, y eso es lo que permite medirlo con la vara de 19 y el mismo lector
que dio el piso de 56 de 57, sin tocar produccion.

EL REPARTO DE TRABAJO, que es toda la idea:

    el modelo      traduce: partes, intencion, origen, rubro, criterios con
                   las PALABRAS del cliente
    este codigo    decide: que campo, que valor del catalogo, que operador,
                   que tema de la casa. Determinista, sin llamar a nadie.

LO QUE NO HACE, a proposito:
  - No inventa una cifra: un umbral sale solo de un numero escrito en el
    valor que el cliente dijo.
  - No adivina un rubro: si la parte se refiere a algo anterior, el rubro
    queda vacio y lo resuelve la memoria —paso 6—.
  - No elige entre dos temas que empatan: los pasa, y el motor ya sabe
    servir candidatos.

Uso, desde la raiz:
    python3 banco_pruebas/compilador.py --modelo deepseek
    python3 banco_pruebas/compilador.py --modelo gemini --solo M1,M6
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from banco_pruebas import clon_produccion  # noqa: E402
from banco_pruebas import traductor as T  # noqa: E402
from banco_pruebas.leer_interpretacion import (  # noqa: E402
    CASILLA, DEUDA, _norm)

TIENDA = T.TIENDA
VARA_19 = os.path.join(RAIZ, "banco_pruebas", "vara_interpretacion.json")


# ── 1 · VALIDAR ─────────────────────────────────────────────────────────────

def validar(ficha: dict, mensaje: str, tab: dict) -> tuple:
    """La ficha que el codigo acepta, y lo que se saco. Con DeepSeek el
    proveedor no obliga las listas, asi que esto es la atadura; con Gemini es
    una segunda llave."""
    from app.core.cotejo import renglon_es_copia
    rubros = set(tab["rubros"]) | {"otro", "ninguno", "toda_la_tienda"}
    conceptos = set(tab["conceptos"]) | {"otro", "compatible_con"}
    msg = _norm(mensaje)
    avisos, partes = [], []
    for p in ficha.get("partes") or []:
        if not isinstance(p, dict):
            continue
        if not renglon_es_copia(str(p.get("dice")), mensaje):
            avisos.append(f"parte que no esta en el mensaje: {p.get('dice')!r}")
            continue
        p = dict(p)
        if p.get("quiere") not in T.INTENCIONES:
            avisos.append(f"intencion fuera de lista: {p.get('quiere')}")
            p["quiere"] = "charla"
        if p.get("origen") not in T.ORIGENES:
            avisos.append(f"origen fuera de lista: {p.get('origen')}")
            p["origen"] = "ninguno"
        if p.get("rubro") not in rubros:
            avisos.append(f"rubro fuera de lista: {p.get('rubro')}")
            p["rubro"] = "ninguno"
        # EL PRODUCTO TIENE QUE ESTAR ESCRITO: un nombre que el cliente no
        # dijo es identidad inventada, la regla 10.0.
        if p.get("producto") and _norm(p["producto"]) not in msg:
            toks = [w for w in _norm(p["producto"]).split() if len(w) > 2]
            if not toks or not all(w in msg for w in toks):
                avisos.append(f"producto que no dijo: {p['producto']!r}")
                p["producto"] = ""
        # LO ANTERIOR NO SE ADIVINA: el rubro lo pone la memoria.
        if p.get("anterior") and not p.get("producto"):
            p["rubro"] = "ninguno"
        p["criterios"] = [c for c in (p.get("criterios") or [])
                          if isinstance(c, dict)
                          and c.get("concepto") in conceptos
                          and c.get("fuerza") in T.FUERZAS]
        partes.append(p)
    limpia = dict(ficha, partes=partes)
    limpia["criterios_generales"] = [
        c for c in (ficha.get("criterios_generales") or [])
        if isinstance(c, dict) and c.get("concepto") in conceptos
        and c.get("fuerza") in T.FUERZAS]
    return limpia, avisos


# ── 2 · ATERRIZAR ───────────────────────────────────────────────────────────

_BARATO = ("barat", "econom", "crisis", "no sea car", "no salga mucho",
           "no me fundan", "no sea muy car", "accesible", "menor precio",
           "lo mas bajo", "no tan car", "presupuesto acorde")
_CARO = ("lo mas car", "el mas car", "el mejor", "tope de gama",
         "sin importar el precio")
_LIVIANO = ("livian", "menos pes", "que pese poco")
_GRADO = ("posible", "lo menos", "en lo posible", "ojala no",
          "preferentemente no")


def _cifras(valor: str) -> list:
    """Los numeros ESCRITOS en el valor, con mil, lucas y k."""
    t = _norm(valor).replace(".", "")
    fuera = []
    for m in re.finditer(r"(\d+(?:,\d+)?)\s*(mil|lucas|luca|k)?\b", t):
        n = float(m.group(1).replace(",", "."))
        if m.group(2):
            n *= 1000
        fuera.append(int(n))
    return fuera


_NIEGA = re.compile(r"\b(no|nada|sin|menos|excepto|salvo|ni)\b")


def aterrizar(concepto: str, valor: str, fuerza: str, rubro: str,
              dice: str = "") -> dict:
    """{condiciones, orden} para UN criterio. Nunca inventa una cifra.

    LA NEGACION SE LEE EN LAS PALABRAS DEL CLIENTE, no en la fuerza que puso
    el modelo. Medido el 23-sep: Gemini marco "cualquiera menos redragon" y
    "lo menos chino posible" como `debe`, y compilado literal eso es
    "contiene redragon" —el sentido al reves—. Si el pedazo niega, un `debe`
    no puede quedar como filtro positivo."""
    from app.core.filtros_catalogo import vocabulario
    v = _norm(valor)
    if fuerza == "debe" and concepto not in ("precio_ars", "peso_gramos") \
            and (_NIEGA.search(v) or _NIEGA.search(_norm(dice))):
        fuerza = "evita"
    fuera = {"condiciones": [], "orden": ""}
    if concepto == "precio_ars":
        cifras = _cifras(valor)
        if cifras:
            if len(cifras) >= 2 and re.search(r"\b(de|entre)\b", v):
                fuera["condiciones"] += [
                    {"campo": "precio_ars", "operador": "mayor",
                     "valor": str(min(cifras))},
                    {"campo": "precio_ars", "operador": "menor",
                     "valor": str(max(cifras))}]
            elif re.search(r"\b(desde|mas de|minimo|arriba)\b", v):
                fuera["condiciones"].append(
                    {"campo": "precio_ars", "operador": "mayor",
                     "valor": str(cifras[0])})
            else:
                fuera["condiciones"].append(
                    {"campo": "precio_ars", "operador": "menor",
                     "valor": str(cifras[0])})
        # SIN CIFRA, EL PRECIO ES UN ORDEN Y NUNCA UN TECHO. Lo barato se
        # reconoce por la regla y no por una lista de frases: evitar lo caro,
        # o negar lo caro —"no muy cara", "que no me fundan"—, es lo barato
        # primero. La lista queda para lo que se dice sin negar —"acorde a la
        # crisis"—.
        elif fuerza == "evita" or (_NIEGA.search(v) and "car" in v) or \
                any(k in v for k in _BARATO):
            fuera["orden"] = "precio_ars_min"
        elif any(k in v for k in _CARO):
            fuera["orden"] = "precio_ars_max"
        return fuera
    if concepto == "peso_gramos" and any(k in v for k in _LIVIANO):
        fuera["orden"] = "peso_gramos_min"
        return fuera
    if concepto in ("otro", "compatible_con"):
        return fuera
    # EL VALOR DEL CATALOGO, POR RAIZ. Si el campo se enumera y alguna raiz
    # de un valor real aparece en lo que dijo el cliente, se usa ESE valor:
    # "las menos partes chinas" aterriza en "China".
    reales = ((vocabulario(TIENDA) or {}).get(concepto) or {}).get(
        "valores") or []
    elegido = ""
    for r in reales:
        raiz = _norm(r)[:5]
        if len(raiz) >= 3 and re.search(r"\b" + re.escape(raiz), v):
            elegido = str(r)
            break
    valor_final = elegido or valor
    if fuerza == "debe":
        op = "contiene"
    elif fuerza == "prefiere":
        op = "prefiere"
    else:
        # EVITA TIENE DOS LECTURAS y el cliente las distingue con palabras:
        # "lo menos chino posible" gradua; "cualquiera menos redragon"
        # excluye. El v4 las junto en una fuerza; aca se separan.
        op = "evita" if any(k in v or k in _norm(dice) for k in _GRADO) \
            else "no_contiene"
    fuera["condiciones"].append({"campo": concepto, "operador": op,
                                 "valor": valor_final})
    return fuera


# ── 3 · COMPILAR ────────────────────────────────────────────────────────────

_MEDIOS = (("transfer", "transferencia"), ("mercado", "mercado_pago"),
           ("mp", "mercado_pago"), ("tarjeta", "tarjeta"),
           ("credito", "tarjeta"), ("debito", "tarjeta"))
_TOTAL = re.compile(r"\b(total|presupuesto|cuanto (es|sale|me sale) todo|"
                    r"armame|arma me)\b")
_CONSEJO = re.compile(r"\b(conviene|recomend|cual me|que me sirve|mejor)\b")
_NO_BUSCAN = {"envio", "pago", "politica", "postventa", "charla"}


def compilar(ficha: dict, mensaje: str, tab: dict) -> dict:
    from app.core.fuente import certificar_tema, temas_del_tablero
    partes = ficha.get("partes") or []
    catalogo = set(tab["rubros"])
    generales = ficha.get("criterios_generales") or []
    pedido = {"renglones": [p.get("dice") for p in partes],
              "pedir_total": bool(ficha.get("reparto"))
              or bool(_TOTAL.search(_norm(mensaje))),
              "consultas": [], "temas": [], "compatibilidad": [],
              "afirma": [a for a in ficha.get("afirma") or []
                         if isinstance(a, dict)],
              "envios": [], "reparto_pago": []}

    # EL ALCANCE DENTRO DEL MENSAJE. Una parte sin rubro propio que solo
    # agrega criterios —"cualquiera menos redragon", "y si no hay negro
    # mandame blanco"— modifica a la parte con rubro que tiene ANTES en el
    # mismo mensaje. Medido: Gemini las marco como `anterior` y la exclusion
    # se perdia entera. Solo si no hay ninguna antes queda para la memoria.
    partes = [dict(p) for p in partes]
    ultima = None
    for p in partes:
        if p.get("rubro") in catalogo or p.get("producto"):
            ultima = p
            continue
        if ultima is not None and p.get("criterios") and \
                p.get("quiere") not in _NO_BUSCAN:
            ultima["criterios"] = list(ultima.get("criterios") or []) + \
                [dict(c, _dice=p.get("dice")) for c in p["criterios"]]
            p["criterios"] = []
            p["_absorbida"] = True
    # LAS CONSULTAS: una por rubro y producto. Las partes de envio del mismo
    # rubro suman su cantidad; la parte que pide el producto manda si dijo
    # una cantidad mayor —"dos auriculares" y "un auricular a Cordoba"—.
    grupos: dict = {}
    for p in partes:
        rubro = p.get("rubro")
        if p.get("origen") not in ("tienda", "general"):
            continue
        if p.get("_absorbida"):
            continue
        if rubro not in catalogo and not p.get("producto") and not (
                rubro in ("otro", "toda_la_tienda")
                and p.get("quiere") in ("buscar", "precio", "stock")):
            continue
        if p.get("quiere") in _NO_BUSCAN and not p.get("destino") \
                and not p.get("producto"):
            continue
        clave = (rubro, _norm(p.get("producto")))
        g = grupos.setdefault(clave, {"pide": 0, "envia": 0, "partes": []})
        g["partes"].append(p)
        n = int(p.get("cantidad") or 0)
        if p.get("destino"):
            g["envia"] += n
        else:
            g["pide"] = max(g["pide"], n)
    for (rubro, _prod), g in grupos.items():
        ps = g["partes"]
        producto = next((p.get("producto") for p in ps if p.get("producto")),
                        "")
        c = {"busco": "uno" if producto else "varios", "orden": "ninguno",
             "condiciones": []}
        if rubro in catalogo:
            c["categoria"] = rubro
        if producto:
            c["texto"] = producto
        elif rubro not in catalogo:
            # SIN RUBRO DEL CATALOGO: se busca por lo que dijo, y el motor
            # ya pesa por rareza. "Un aparato para la compu" es vago y la
            # respuesta tiene que preguntar; la busqueda le da de que.
            c["texto"] = ps[0].get("dice")
        cant = max(g["pide"], g["envia"])
        if cant:
            c["cantidad"] = cant
        for crit in [x for p in ps for x in (p.get("criterios") or [])] + \
                list(generales):
            if crit.get("concepto") == "compatible_con":
                pedido["compatibilidad"].append(
                    {"producto": producto or rubro, "con": crit.get("valor")})
                continue
            a = aterrizar(crit.get("concepto"), str(crit.get("valor")),
                          crit.get("fuerza"), rubro,
                          crit.get("_dice") or next(
                              (p.get("dice") for p in ps
                               if crit in (p.get("criterios") or [])),
                              # UN CRITERIO GENERAL NO TIENE PEDAZO PROPIO:
                              # la negacion y el grado se leen en el mensaje.
                              mensaje))
            c["condiciones"] += a["condiciones"]
            if a["orden"] and c["orden"] == "ninguno":
                c["orden"] = a["orden"]
        if any(p.get("quiere") == "compatibilidad" for p in ps) and \
                not pedido["compatibilidad"]:
            pedido["compatibilidad"].append(
                {"producto": producto or rubro,
                 "con": next(p.get("dice") for p in ps
                             if p.get("quiere") == "compatibilidad")})
        pedido["consultas"].append(c)

    # LOS DESTINOS, cada uno con QUE va, que es el vinculo que el cliente dijo.
    destinos: dict = {}
    for p in partes:
        d = str(p.get("destino") or "").strip()
        if d:
            destinos.setdefault(d, []).append(p.get("dice"))
    pedido["envios"] = [{"destino": d, "va": ", ".join(dict.fromkeys(v))}
                        for d, v in destinos.items()]

    for r in ficha.get("reparto") or []:
        medio = next((m for k, m in _MEDIOS if k in _norm(r.get("medio"))), "")
        pedido["reparto_pago"].append({"medio": medio,
                                       "porcentaje": r.get("porcentaje")})

    # LOS TEMAS DE LA CASA LOS ELIGE EL CODIGO, leyendo el pedazo que el
    # cliente dijo. El modelo ya no elige entre 104 nombres.
    from app.storage.firestore_client import get_all_faq
    temas_ok = set(temas_del_tablero(TIENDA))
    # LA POLITICA SALE DE LA FAQ Y EL CONSEJO SALE DE LA BASE. certificar_tema
    # devuelve empatados de las dos —"garantia" y "teclado_mecanico_membrana"
    # para "¿tienen garantia en los teclados mecanicos?"—; la intencion de
    # la parte dice de cual de los dos cajones corresponde.
    de_la_faq = set((get_all_faq(tienda_id=TIENDA) or {}).keys())
    for p in partes:
        if p.get("origen") not in ("tienda", "general"):
            continue
        if p.get("quiere") in ("politica", "postventa") or (
                p.get("quiere") in ("pago", "envio")
                and not p.get("destino") and not ficha.get("reparto")):
            cert = certificar_tema(str(p.get("dice")), TIENDA)
            for t in cert.get("temas") or []:
                if t in temas_ok and t in de_la_faq and \
                        t not in pedido["temas"]:
                    pedido["temas"].append(t)
        elif (p.get("quiere") == "comparar"
              or _CONSEJO.search(_norm(p.get("dice")))) and \
                p.get("rubro") in temas_ok:
            # UNA FAMILIA, UN TEMA: si ya entro "teclado_mecanico_membrana"
            # no se suma "teclado" encima.
            if not any(p["rubro"].split()[0] in t for t in pedido["temas"]):
                pedido["temas"].append(p["rubro"])
    return pedido


# ── LA MEDICION: la vara de 19, con el lector del piso ─────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default="deepseek",
                    choices=("gemini", "deepseek"))
    ap.add_argument("--tablero", default="v5")
    ap.add_argument("--solo", default="")
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    clon_produccion.preparar_entorno()
    from banco_pruebas import sim_firestore
    sim_firestore.install()
    tab = T.tablero()
    sistema, esq = T.prompt(tab, args.tablero), T.esquema(tab, args.tablero)
    with open(VARA_19, encoding="utf-8") as f:
        vara = json.load(f)
    quiero = {x.strip().upper() for x in args.solo.split(",") if x.strip()}
    mensajes = [m for m in vara["mensajes"] if not quiero or m["id"] in quiero]

    def uno(m):
        ficha, ms = T.traducir(m["texto"], args.modelo, sistema, esq)
        limpia, avisos = validar(ficha, m["texto"], tab)
        return m, ficha, limpia, avisos, compilar(limpia, m["texto"], tab), ms

    with cf.ThreadPoolExecutor(4) as ex:
        filas = list(ex.map(uno, mensajes))
    ok = de = 0
    crudo = []
    for m, ficha, limpia, avisos, pedido, ms in filas:
        res = [(c["n"], CASILLA[c["tipo"]](c, pedido))
               for c in m["casillas"] if c["tipo"] != DEUDA]
        o = sum(1 for _n, v in res if v)
        ok += o
        de += len(res)
        print(f"{'OK' if o == len(res) else 'XX'} {m['id']:<4} {o}/{len(res)} "
              f"{ms}ms  {m['texto'][:60]}")
        for n, v in res:
            if not v:
                print(f"      - {n}")
        for a in avisos:
            print(f"      ! {a}")
        crudo.append({"id": m["id"], "ficha": ficha, "pedido": pedido,
                      "avisos": avisos, "casillas": res, "ms": ms})
    print(f"\n{args.modelo.upper()} {args.tablero} + compilador: {ok} de {de} "
          f"en la vara de 19 (piso del camino vivo: 56 de 57)")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(crudo, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
