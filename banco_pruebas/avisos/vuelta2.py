"""SEGUNDA VUELTA SOBRE LOS 11 — la informacion justa de cada clase, dada solo donde aparece el error.

Sobre la base V4 con los avisos de O1, se suma:
  A1  confirmar lo que no tiene nada pendiente: un si que no cambia nada es CUENTA.
  A2  una cuenta con lo buscado y el pedido vacio: lo buscado no se anota solo, va AGREGAR por rubro con su destino.
  A3  la compatibilidad, en seco: que parte de "con" uso el codigo y que parte no.
  A4  elegir entre lo mostrado cuando por eso una condicion no se puede aplicar, y en la tienda si.
  T   la tercera vuelta corrige solo lo avisado y devuelve lo demas identico.
  P   una pista de producto que es solo un rubro, "2 mouse", se contesta como rubro, no con nombres de modelos.
Cada uno salta solo donde el modelo escribe ese error, o donde la pista es esa: lo demas no cambia de entrada.
"""
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import pistas as P  # noqa: E402

TIENDA = "verifika_prod"
_VACIAS = set("a al con de del el en la las lo los mi mis me para por que un una y o es tengo tiene".split())

TERCERA_EXTRA = ("- Corregi SOLO los renglones que nombra un aviso, y pone el pedazo sin citar en el renglon que ya lo "
                 "pide. Los demas renglones devolvelos identicos, palabra por palabra.\n")


def _palabras(t):
    from banco_pruebas.traduccion58 import plano
    return [w for w in plano(str(t or "")).split() if len(w) > 2 and w not in _VACIAS]


def avisos_nuevos(base):
    from app.core import agente
    from app.core.flujo import agenda as A
    from app.core.flujo import borrador as B
    from app.core.flujo import catalogo as K
    from app.core.flujo import interprete as I

    def avisos(agenda, estado, mensaje):
        problemas, datos, hay_si = base(agenda, estado, mensaje)
        qs = A.preguntas(agenda)
        b = B.leer(estado.get("borrador"))
        res = B.resolver(b, TIENDA) if b["renglones"] else []
        pendientes = {x["L"] for x in B.faltantes(b, res) if x.get("L")} if b["renglones"] else set()
        mostrados = [v for k, v in I.numeros(estado).items() if k.startswith("M-")]
        acciones = [q.get("accion") for q in qs]
        hay_agrega = any(q.get("agrega") for q in qs)
        for q in qs:
            n = q.get("n")
            # A1
            for clave in ("confirma", "acepta"):
                for r in q.get(clave) or []:
                    for L in re.findall(r"L-\d+", str(r)):
                        if b["renglones"] and L not in pendientes:
                            problemas.append(f"renglon {n}: {L} no tiene nada que confirmar ni aceptar, ya esta completo. "
                                             "Un si que no cambia nada del pedido es CUENTA: muestra el total.")
            # A2
            if q.get("accion") == "cuenta" and not b["renglones"] and "buscar" in acciones and not hay_agrega:
                problemas.append(f"renglon {n}: el pedido esta vacio y lo buscado no se anota solo: para que la cuenta "
                                 "lo sume va un AGREGAR por cada rubro, con su cantidad y su destino si dice adonde.")
            # A3
            if q.get("accion") == "compatibilidad" and q.get("con"):
                idt = K.identificar(str(q.get("producto") or ""), "", TIENDA)
                if idt["veredicto"] == "exists":
                    r = agente.ejecutar("compatibilidad", {"producto": str(idt["producto"]["id"]), "con": str(q["con"])},
                                        TIENDA)
                    vs = [v for v in r.get("compatibilidad") or [] if isinstance(v, dict)]
                    usado = " ".join(str(v.get("con_equipo") or "") for v in vs)
                    sobran = [w for w in _palabras(q["con"]) if w not in " ".join(_palabras(usado))]
                    if sobran and any(v.get("veredicto") in ("compatible", "incompatible") for v in vs):
                        problemas.append(f"renglon {n}: el codigo juzgo la compatibilidad con '{usado}' y no uso "
                                         f"'{' '.join(sobran)}'. con lleva el dato del equipo que decide.")
                        datos += [f"  lo que dice la ficha del producto: {v.get('motivo')}" for v in vs if v.get("motivo")]
            # A4
            if q.get("accion") == "buscar" and q.get("entre_lo_mostrado") and mostrados:
                rub = K.rubro(str(q.get("rubro") or ""), TIENDA)
                conds = q.get("condiciones") or []
                con_m = K.buscar(rub, conds, "nada", 50, TIENDA, entre=mostrados)
                sin_m = K.buscar(rub, conds, "nada", 50, TIENDA)
                trabadas = [c for c in con_m["sin_campo"] + con_m["vacio_por"]
                            if c not in sin_m["sin_campo"] + sin_m["vacio_por"]]
                if trabadas:
                    problemas.append(f"renglon {n}: con entre_lo_mostrado el codigo no puede aplicar "
                                     f"{', '.join(repr(c) for c in trabadas)}: entre lo mostrado no hay de eso, y en "
                                     "toda la tienda si. Si pide ver si hay, es BUSCAR sin entre_lo_mostrado.")
        return problemas, datos, hay_si
    return avisos


def pista_producto_rubro(original):
    from app.core.flujo import catalogo as K

    def _producto(t):
        if K.solo_rubro(t, TIENDA):
            return P._rubro(t)
        return original(t)
    return _producto


REGISTRO = []


def instalar():
    import opciones
    import variante3 as V3
    opciones.instalar("O1")
    V3.avisos = avisos_nuevos(V3.avisos)
    V3.TERCERA = V3.TERCERA.replace("- No escribas precios", TERCERA_EXTRA + "- No escribas precios", 1)
    assert TERCERA_EXTRA in V3.TERCERA
    P._producto = pista_producto_rubro(P._producto)
    paso1 = P.paso1

    def paso1_anotado(mensaje, hay):
        r = paso1(mensaje, hay)
        REGISTRO.append({"mensaje": mensaje, "pistas": r})
        return r
    P.paso1 = paso1_anotado


def correr(nombre: str, casos: set):
    from banco_pruebas import traduccion58 as T
    T.CORRIDAS = os.path.join(AQUI, f"corridas_{nombre}.jsonl")
    T.REPS = 1
    original = T.formas_de
    T.formas_de = lambda ch, k, *a: {f: v for f, v in original(ch, k, *a).items() if (ch, k, f) in casos}
    instalar()
    turnos = {(c, k) for c, k, _f in casos}
    ok = T.correr(1, 1, sorted({c for c, _ in turnos}), turnos)
    with open(os.path.join(AQUI, f"pistas_{nombre}.jsonl"), "a", encoding="utf-8") as f:
        for r in REGISTRO:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(AQUI, f"uso_{nombre}.jsonl"), "a", encoding="utf-8") as f:
        for u in P.USO:
            f.write(json.dumps(u) + "\n")
    return ok


if __name__ == "__main__":
    import vuelta2
    nombre = sys.argv[1]
    casos = {tuple(json.loads(x)) for x in open(os.path.join(AQUI, sys.argv[2]), encoding="utf-8")}
    casos = {(c, int(k), f) for c, k, f in casos}
    print("terminó" if vuelta2.correr(nombre, casos) else "cortado")
