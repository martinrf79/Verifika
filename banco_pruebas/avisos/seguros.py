"""LOS TRES AVISOS SEGUROS sobre la base de ayer — produccion con la tabla mejorada, 468 de 525.

El metodo de ayer: solo cambia la entrada donde hace falta. Los avisos se suman a la devuelta que produccion ya tiene,
y solo saltan donde el modelo escribio ese error:
  vacio    cambia, saca o confirma renglones con el pedido vacio.
  traba    busca entre lo mostrado, y por eso una condicion no se puede aplicar, que en la tienda si.
  suma     pide la cuenta con lo buscado y el pedido vacio, sin anotar nada.

Se corre como repeticion: la primera traduccion es la grabada de la base, identica, y solo se agrega la devuelta. Asi
el cambio queda aislado: lo que no recibe aviso no cambia, porque ni se vuelve a llamar al modelo.

  python3 seguros.py --ver          sin modelo: donde saltan, en casos que andan y en casos que fallan
  python3 seguros.py --correr       la devuelta, solo donde saltan
"""
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import contexto  # noqa: E402

from app.core.flujo import agenda as A  # noqa: E402
from app.core.flujo import borrador as B  # noqa: E402
from app.core.flujo import catalogo as K  # noqa: E402
from app.core.flujo import interprete as I  # noqa: E402

TIENDA = "verifika_prod"
CORRIDAS = "/home/user/Verifika/banco_pruebas/traduccion58_corridas.jsonl"


def base() -> dict:
    """(charla, turno, forma) -> la fila de la base: la de la tabla donde la tabla cambio la entrada, si no la de produccion."""
    filas = [json.loads(l) for l in open(CORRIDAS, encoding="utf-8")]
    prod = {(r["charla"], r["turno"], r["forma"]): dict(r, base="produccion") for r in filas
            if r.get("modelo", "gemini") == "gemini" and r["rep"] == 0}
    tabla = {(r["charla"], r["turno"], r["forma"]): dict(r, base="tabla") for r in filas if r.get("modelo") == "gemini_or+tabla"}
    return {k: tabla.get(k, v) for k, v in prod.items()}


def avisos(agenda: dict, estado: dict) -> list:
    qs = A.preguntas(agenda)
    vacio = not B.leer(estado.get("borrador"))["renglones"]
    mostrados = [v for k, v in I.numeros(estado).items() if k.startswith("M-")]
    acciones = [q.get("accion") for q in qs]
    hay_agrega = any(q.get("agrega") for q in qs)
    out = []
    for q in qs:
        n = q.get("n")
        if q.get("accion") == "comprar" and vacio and any(q.get(k) for k in ("saca", "cambia", "confirma", "acepta")):
            out.append(("vacio", f"La pregunta {n} cambia, saca o confirma renglones, pero el pedido esta vacio: no hay "
                                 "ningun renglon. Lo que pide es otra cosa: una consulta, un envio o una compra nueva."))
        if q.get("accion") == "cuenta" and vacio and "buscar" in acciones and not hay_agrega:
            out.append(("suma", f"La pregunta {n} pide la cuenta con el pedido vacio, y lo buscado no se anota solo: para "
                                "que la cuenta lo sume, va una pregunta comprar con agrega por cada rubro, con su cantidad y "
                                "su destino si dice adonde."))
        if q.get("accion") == "buscar" and q.get("entre_lo_mostrado") and mostrados:
            rub = K.rubro(str(q.get("rubro") or ""), TIENDA)
            conds = q.get("condiciones") or []
            con_m = K.buscar(rub, conds, "nada", 50, TIENDA, entre=mostrados)
            sin_m = K.buscar(rub, conds, "nada", 50, TIENDA)
            trabadas = [c for c in con_m["sin_campo"] + con_m["vacio_por"] if c not in sin_m["sin_campo"] + sin_m["vacio_por"]]
            if trabadas:
                out.append(("traba", f"La pregunta {n} busca entre lo mostrado, y ahi no se puede aplicar "
                                     f"{', '.join(repr(c) for c in trabadas)}: entre lo mostrado no hay de eso, y en toda "
                                     "la tienda si. Si pide ver si hay, es buscar sin entre_lo_mostrado."))
    return out


def ver() -> dict:
    b = base()
    cache, salta = {}, {}
    for k, r in sorted(b.items()):
        if (k[0], k[1]) not in cache:
            cache[(k[0], k[1])] = contexto.contexto(k[0], k[1], uid="seg")
        av = avisos(r["agenda"], cache[(k[0], k[1])]["estado"])
        if av:
            salta[k] = av
    andan = [k for k in salta if b[k]["bien"]]
    fallan = [k for k in salta if not b[k]["bien"]]
    print(f"base: {sum(r['bien'] for r in b.values())} de {len(b)}")
    print(f"los avisos saltan en {len(salta)}: {len(fallan)} que fallan, {len(andan)} que andan")
    for k in sorted(salta):
        print(f"  {'ANDA ' if b[k]['bien'] else 'FALLA'} {k[0]} T{k[1]} {k[2]:10} {b[k]['base']:10} "
              f"{', '.join(c for c, _ in salta[k])}")
    json.dump({json.dumps(list(k)): [t for _c, t in v] for k, v in salta.items()},
              open(os.path.join(AQUI, "seguros_salta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return salta


def correr():
    """La devuelta con los avisos, sobre la traduccion grabada, solo donde saltan. Se califica por el flujo entero."""
    from banco_pruebas import traduccion58 as T
    salta = {tuple(json.loads(k)): v for k, v in json.load(open(os.path.join(AQUI, "seguros_salta.json"))).items()}
    b = base()
    por_texto = {b[k]["texto"]: (k, b[k]) for k in salta}

    async def interpretar(mensaje, historial, estado, tienda_id, trace_id=""):
        k, r = por_texto[mensaje]
        if r["base"] == "tabla":
            msgs = [{"role": "system", "content": I.consigna(tienda_id)},
                    {"role": "user", "content": I.libreta(estado, historial, tienda_id) + "\n"
                     + T._tabla_ideal(mensaje, tienda_id) + f"\nULTIMO MENSAJE: {mensaje}"}]
        else:
            msgs = I.mensajes(mensaje, historial, estado, tienda_id)
        faltas = A.faltas(mensaje, r["agenda"], set(I.numeros(estado))) + salta[k]
        crudo, _uso = contexto.llamar(msgs + [{"role": "assistant", "content": json.dumps(r["agenda"], ensure_ascii=False)},
                                              {"role": "user", "content": I.DEVUELTA.format(faltas="\n".join(faltas))}],
                                      json_=True)
        return I._json(crudo) or r["agenda"]
    I.interpretar = interpretar
    T.CORRIDAS = os.path.join(AQUI, "corridas_seguros.jsonl")
    T.REPS = 1
    original = T.formas_de
    T.formas_de = lambda ch, k, *a: {f: v for f, v in original(ch, k, *a).items() if (ch, k, f) in salta}
    turnos = {(c, k) for c, k, _f in salta}
    return T.correr(1, 1, sorted({c for c, _ in turnos}), turnos)


if __name__ == "__main__":
    if "--ver" in sys.argv:
        ver()
    if "--correr" in sys.argv:
        print("terminó" if correr() else "cortado")
