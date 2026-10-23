"""EL ACTO QUE ARMA EL CODIGO — primer paso de la propuesta del 23-oct, sin gasto.

La hipotesis: el acto de trece mezcla lo que dice el lenguaje —si pregunta, decide, saca o informa— con lo que solo sabe
el codigo —si eso es un rubro, un producto, un tema o un renglon del pedido—. Si el modelo da solo el modo y el codigo
pone el resto, el acto sale de una tabla que cubre la clase, no el caso.

Esta prueba no llama al modelo: toma las respuestas GUARDADAS de `actos.py --unida` sobre las 48, lleva cada acto a su
modo y vuelve a derivar el acto con la tabla, con lo que la parte toca de la tienda y la memoria del turno. Lo que toca se
busca por palabras, `agente`, el padron del catalogo y los numeros de la libreta: es la cota de abajo de la busqueda por
significado, que no quedo guardada. Lo correcto es la misma vara de `actos.py`.

Lo que esta prueba no puede mostrar: un acto mal entre modos —mirar contra llevar— sigue mal, porque el modo sale del
acto que puso el modelo. Eso lo mide la corrida con el modelo pidiendo el modo, si esta da 34 o mas.

    python3 banco_pruebas/modos.py [--ver]
"""
import collections
import os
import re
import sys

sys.argv = [sys.argv[0]] + [a for a in sys.argv[1:] if a == "--ver"]
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import actos as A  # noqa: E402  — la consigna unida, la vara y el entorno
from banco_pruebas import libro_paga  # noqa: E402
from app.core import agente  # noqa: E402
from app.core.flujo import catalogo as K  # noqa: E402
from app.core.flujo import interprete  # noqa: E402
from app.core.flujo.ficha import VACIO  # noqa: E402
from app.core.flujo.marcador import _productos  # noqa: E402
from app.core.llm_reintento import _modelo  # noqa: E402

TID = A.P.TID

# EL MODO: lo que dice el lenguaje, sin saber nada de la tienda ni del pedido.
# Decidir algo nuevo y decidir sobre lo que ya esta en el pedido son dos modos: lo primero de esta prueba mostro que
# no sale del objeto ni del estado —"mejor la Gamemax en negro" cambia, "otra igual pero roja" suma—, es lenguaje.
MODO = {"lleva": "decide", "cambia": "modifica", "saca": "saca", "nada": "nada", "dato_cliente": "informa",
        "paga": "informa", "mira": "pregunta", "pregunta_dato": "pregunta", "compara": "pregunta",
        "regla_tienda": "pregunta", "envio": "pregunta", "saber_general": "pregunta",
        # "¿anda con mi iPad?" es una relacion que dice el lenguaje: queda su modo, no sale del objeto.
        "compatibilidad": "anda_con"}

PAGO = {"formas_pago", "cuotas", "descuento_transferencia", "pago_contra_entrega", "monedas_aceptadas",
        "verificacion_pagos"}
ENVIO = {"envios", "costo_envio", "plazo_envio", "envio_urgente", "envio_exterior"}
_TOTAL = re.compile(r"\b(total|presupuesto|cuanto (me )?da|suma|cuanto seria)\b")
_PLATA = re.compile(r"\$|\d+ ?%|\bpor ?ciento\b|\bmil\b|\d{4,}|\b(transferencia|efectivo|tarjeta|mercado ?pago|"
                    r"cripto|debito|credito|pago|pagar|pagamos|pagaria)\b")


def _puntos(texto: str, grupo: str) -> list:
    """Cada candidato con su puntaje por palabras, como `agente.ubicar`, del mejor al peor."""
    q = agente._tokens(texto)
    out = [(2 * len(q & b["nombre"]) + len(q & b["alias"]), k) for k, b in agente.indice(TID)[grupo].items()]
    return sorted([x for x in out if x[0]], key=lambda x: (-x[0], x[1]))


def _productos_de(texto: str) -> list:
    out = []
    for tramo, _ in _productos([w for w in re.findall(r"[a-z0-9]+", K.n(texto)) if w not in K._RELLENO], TID):
        idt = K.identificar(tramo, "", TID)
        for p in [idt["producto"]] if idt["veredicto"] == "exists" else idt.get("opciones") or []:
            out.append(p)
    return out


def _raices(texto: str) -> set:
    return {w[:5] if len(w) > 4 else w.rstrip("s") for w in re.findall(r"[a-z0-9]+", K.n(texto)) if len(w) > 2}


def _nombrados(texto: str, grupo: str) -> list:
    """Lo que la parte nombra con el nombre de la tienda, que la consigna unida le pide al modelo: todas las palabras
    del nombre estan en la parte."""
    q = _raices(texto)
    return [k for k in agente.indice(TID)[grupo] if _raices(k.replace("_", " ")) <= q]


def objeto(parte: dict, mem: dict) -> dict:
    """Lo que la parte toca de la tienda y de la charla, sin el acto. Primero lo nombrado con los nombres de la tienda;
    las palabras sueltas, solo si no nombra nada: ahi iria la busqueda por significado."""
    t = str(parte.get("texto") or "")
    por_id = {str(p["id"]): p for p in K.productos(TID)}
    sin_elegir = {rub for _, rub, pid, _ in mem.get("L") or [] if not pid}
    refs = re.findall(r"\b([MLml])-?(\d+)\b", t)
    m_refs = [(mem.get("M") or [])[int(n) - 1] for l, n in refs if l.upper() == "M" and int(n) <= len(mem.get("M") or [])]
    l_refs = [n for l, n in refs if l.upper() == "L"]
    prods = [por_id[i] for i in m_refs if i in por_id] + _productos_de(t)
    rubros, temas = _nombrados(t, "rubros"), _nombrados(t, "temas")
    if not (prods or rubros or temas):
        pr, pt = _puntos(t, "rubros"), _puntos(t, "temas")
        if pr and (not pt or pr[0][0] >= pt[0][0]):
            rubros = [pr[0][1]]
        elif pt:
            temas = [pt[0][1]]
    rubro = rubros[0] if rubros else ""
    tema = temas[0] if temas else ""
    del_prod = {p.get("categoria") for p in prods}
    total = bool(_TOTAL.search(K.n(t)))
    return {"renglon": bool(l_refs) or bool((del_prod | {rubro}) & sin_elegir),
            "productos": len({p.get("nombre") for p in prods}), "rubro": rubro, "tema": tema,
            "plata": total or bool(_PLATA.search(K.n(t))), "total": total,
            "lugar": K.n(parte.get("destino") or "").strip() not in VACIO}


def derivar(modo: str, o: dict, con_pedido: bool) -> str:
    """LA TABLA: el acto desde el modo, lo que toca y si hay pedido. Se prueba sin modelo."""
    if modo in ("nada", "saca"):
        return modo
    if modo == "anda_con":
        return "compatibilidad"
    if modo == "informa":
        return "paga" if o["plata"] or o["tema"] in PAGO else "dato_cliente"
    if modo == "modifica":
        return "cambia"
    if modo == "decide":
        if o["plata"] and not (o["productos"] or o["rubro"]):
            return "paga"
        # Decidir sobre algo que ya tiene renglon, o sin producto ni rubro con un pedido —"mandá todo a Mendoza"—,
        # es cambiar el pedido.
        if o["renglon"] or (con_pedido and not (o["productos"] or o["rubro"])):
            return "cambia"
        return "lleva"
    # pregunta
    if o["total"]:
        return "paga"
    # Una regla de la tienda nombrada por su nombre gana: "¿los auriculares tienen garantia?" es la garantia.
    if o["tema"] and not o["productos"] or o["tema"] in PAGO | ENVIO | {"garantia", "cuotas"}:
        return "envio" if o["tema"] in ENVIO else "regla_tienda"
    if o["productos"] >= 2:
        return "compara"
    if o["productos"] == 1:
        return "pregunta_dato"
    if o["rubro"]:
        return "mira"
    if o["lugar"]:
        return "envio"
    return "saber_general"


def modo(p: dict) -> str:
    """El modo desde el acto guardado. "paga" junta decir como paga y pedir el total: con signo de pregunta, pregunta."""
    if p.get("acto") == "paga" and "?" in str(p.get("texto") or ""):
        return "pregunta"
    return MODO.get(p.get("acto"), "pregunta")


def guardada(tu: dict) -> dict:
    estado, historial = A.P.estado_de(tu["mem"])
    msgs = [{"role": "system", "content": A.consigna_unida()},
            {"role": "user", "content": interprete.libreta(estado, historial, TID)
             + f"\nULTIMO MENSAJE: {A.limpio(tu['msg'])}"}]
    clave = libro_paga._clave({"model": _modelo(), "messages": msgs, "response_format": A.formato_unido(),
                               "temperature": 0})
    texto = libro_paga._guardadas().get(clave)
    return interprete._json(texto) if texto else None


def main() -> None:
    ver = "--ver" in sys.argv
    cuenta = collections.Counter()
    por_acto = collections.Counter()
    for ch in A.CHARLAS:
        for i, tu in enumerate(ch["turnos"]):
            r = guardada(tu)
            if r is None:
                cuenta["SIN GUARDAR"] += 1
                continue
            oro = [x for x in tu["oro"] if not x.get("opt")]
            quiere = {A.DEL_ORO[x["tipo"]] for x in oro}
            tambien = A.TAMBIEN.get((ch["id"], i), [])
            partes = [p for p in r.get("partes") or [] if isinstance(p, dict)]
            antes = {p.get("acto") for p in A.definir([dict(p) for p in partes], tu["mem"])}
            con_pedido = bool(tu["mem"].get("L"))
            despues = [derivar(modo(p), objeto(p, tu["mem"]), con_pedido) for p in partes]
            puso = set(despues)
            b_antes = antes == quiere or antes in tambien
            b_desp = puso == quiere or puso in tambien
            cuenta["antes"] += b_antes
            cuenta["tabla"] += b_desp
            cuenta[("arregla" if b_desp else "rompe") if b_antes != b_desp else ""] += 1
            for p, d in zip(partes, despues):
                por_acto[(p.get("acto"), d)] += p.get("acto") != d
            if ver and (b_antes != b_desp or not b_desp):
                marca = "ARREGLA" if b_desp and not b_antes else ("ROMPE" if b_antes else "sigue mal")
                print(f"--- {ch['id']} t{i} {marca}: {A.limpio(tu['msg'])[:150]}")
                print(f"    quiere {sorted(quiere)} · modelo {sorted(antes)} · tabla {sorted(puso)}")
                for p, d in zip(partes, despues):
                    print(f"      {p.get('acto'):14} -> {d:14} {p.get('texto')}")
    print(f"\nLAS 48, con las respuestas guardadas de la consigna unida, sin gasto"
          + (f", sin guardar {cuenta['SIN GUARDAR']}" if cuenta["SIN GUARDAR"] else ""))
    print(f"  el acto del modelo con la regla del codigo: BIEN {cuenta['antes']}")
    print(f"  el modo del modelo y la tabla del codigo:   BIEN {cuenta['tabla']}"
          f" · arregla {cuenta['arregla']} · rompe {cuenta['rompe']}")
    cambios = [(k, v) for k, v in por_acto.items() if v]
    if cambios:
        print("  partes que la tabla cambia, del modelo a la tabla:")
        for (a, d), v in sorted(cambios, key=lambda x: -x[1]):
            print(f"    {a:14} -> {d:14} {v}")


if __name__ == "__main__":
    main()
