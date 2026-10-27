"""LA VERIFICACION POR PARAFRASIS — si una segunda llamada corta ve los errores de la traduccion (27-oct-2026, FICHA 82).

Idea de la sesion con Martin del 27-oct. El modelo traduce, el codigo arma la agenda y la cuenta en castellano llano, sin
modelo, y una segunda llamada solo dice si eso es lo que pidio el cliente. Verificar es otra tarea que traducir: comparar
dos frases en castellano, no llenar casillas. Si ve el error que la traduccion repite, el bot puede repreguntar con la
misma frase en vez de equivocarse sin avisar.

  la entrada  los 169 turnos sueltos con la lectura grabada de Gemini, `primera_ejes/sueltos_rep0.jsonl`: el estado de
              la vara, la libreta que vio el modelo y su salida.
  la vara     la de `vara_dato.py` por turno, la misma de `primera_ejes.py --medir`: entero o no.
  lo medido   de los turnos mal, cuantos marca el verificador; de los bien, cuantos deja pasar. Sirve si marca la
              mayoria de los mal y casi ningun bien.

    python3 banco_pruebas/verificar.py              con la clave gratis; lo pedido queda en respuestas_modelo.jsonl
    python3 banco_pruebas/verificar.py --ver        ademas, cada turno donde el verificador y la vara no coinciden
"""
import asyncio
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
ARGS = sys.argv[1:]
sys.argv = [sys.argv[0]]
import primera_ejes as P  # noqa: E402  — prepara el clon, la vara y el cliente del modelo
from fichas import CHARLAS  # noqa: E402
from app.core.flujo import interprete  # noqa: E402

V = P.V
CONSIGNA = """Sos el control de calidad de una tienda online que vende por WhatsApp. Un cliente escribio un mensaje y el
sistema anoto lo que entendio. Tu unico trabajo es decir si lo entendido es exactamente lo que pidio el cliente en su
ULTIMO MENSAJE, leido con la LIBRETA, que es lo que ya paso en la charla.

LAS DEFINICIONES DE LA TIENDA, que valen aunque vos lo dirias distinto:
- Preguntar es querer saber algo: precio, stock, un dato, si anda con algo, el envio, una regla, el total.
- Pedir ver opciones es "mostrame", "busco", "tenes", "quiero un mouse inalambrico", "necesito algo para": todavia no
  eligio. Un pedido sin cantidad ni destino es pedir ver opciones, aunque diga "quiero".
- Llevar es "me llevo", "anotame", "sumame", "dame", "quiero dos de esos", o armar el pedido con cantidades y destinos.
  Pedir precio de varias cosas con cantidades y destinos es llevar: el programa arma el presupuesto.
- Cuando el cliente deja elegir al programa —"el mas barato", "uno inalambrico", "el que sea"—, el programa elige: no es
  un error que lo entendido no nombre el modelo.
- Lo que el sistema completa sin cambiar nada no es un error: la cantidad uno cuando no dijo cantidad, el unico color o
  la unica opcion, el pedido que ya estaba en la LIBRETA y sigue igual, un saludo o un dato de si.

ES UN ERROR solo lo que haria que la tienda haga otra cosa que lo que pidio:
1. Falta algo que pidio o pregunto, o hay algo que no pidio.
2. Se busca o se lleva otra clase de producto que la que dijo.
3. Una pregunta o pedir ver se tomo como llevar, o al reves; o un cambio de lo que ya esta en el pedido se tomo como
   algo nuevo.
4. La cantidad, el color, el destino, una condicion, el orden o el tope son otros que los que dijo, o van con otra cosa.
5. La regla de la tienda que pregunta es otra.

No juzgues si la tienda tiene el producto, ni los precios, ni como se va a responder. Lo que el sistema dice con otras
palabras pero hace lo mismo, coincide. Ante la duda entre dos lecturas razonables, coincide."""
FORMATO = {"type": "json_schema", "json_schema": {"name": "verificacion", "schema": {
    "type": "object", "properties": {"coincide": {"type": "boolean"}, "diferencia": {"type": "string"}},
    "required": ["coincide", "diferencia"]}}}


def _l(x) -> list:
    return x if isinstance(x, list) else ([] if x in (None, "", {}) else [x])


def _art(a: dict, criterio: dict = None) -> str:
    b = (criterio or {}).get(str(a.get("producto"))) or {}
    c = [f"que cumpla: {', '.join(map(str, _l(b.get('condiciones'))))}"] if b.get("condiciones") else []
    c += [f"el {b['orden']}"] if b.get("orden") not in (None, "", "nada") else []
    return " ".join(str(x) for x in (a.get("cantidad") or 1, a.get("producto"), a.get("color")) if x) + \
        (f" ({', '.join(c)})" if c else "") + (f" a {a['destino']}" if a.get("destino") else "")


def _criterio(p: dict) -> list:
    d = [f"que cumplan: {', '.join(map(str, _l(p.get('condiciones'))))}"] if p.get("condiciones") else []
    d += [f"ordenadas por {p['orden']}"] if p.get("orden") not in (None, "", "nada") else []
    return d + (["entre lo que ya le mostraron"] if p.get("entre_lo_mostrado") else [])


def parafrasis(agenda: dict) -> str:
    """Lo que el codigo va a hacer, en castellano llano: una linea por pregunta de la agenda. Sin modelo. La busqueda de
    un rubro que el mismo mensaje lleva es el criterio de esa compra, y va con ella: asi la cumple el codigo."""
    ps = agenda.get("preguntas") or []
    llevados = {str(a.get("producto")) for p in ps if p.get("accion") == "comprar" for a in _l(p.get("agrega"))}
    criterio = {p.get("rubro"): p for p in ps if p.get("accion") == "buscar" and p.get("rubro") in llevados}
    out = []
    for p in ps:
        acc, d = p.get("accion"), []
        if acc == "buscar" and p.get("rubro") in criterio:
            continue
        if acc == "buscar":
            n = p.get("cantidad") or 1
            d = [f"Quiere ver opciones de {p.get('rubro')}" + (f", {n} de ellas" if n > 1 else "")] + _criterio(p)
        elif acc == "producto":
            d = [f"Pregunta {p.get('quiere_saber') or 'el precio'} de {' o '.join(map(str, _l(p.get('producto'))))}"]
            d += [f"en {p['color']}"] if p.get("color") else []
            d += [f"y da por cierto que {p['afirma']}"] if p.get("afirma") else []
        elif acc == "envio":
            d = [f"Pregunta cuanto sale el envio a {p.get('destino')}"]
        elif acc == "cuenta":
            d = ["Pide el total"]
            d += [f"sin pasar de {p['tope']}"] if p.get("tope") else []
            d += [f"y si pasa, saca {p['si_pasa']}"] if p.get("si_pasa") else []
            d += ["pagando " + " y ".join(f"{r.get('porcentaje')}% con {r.get('medio')}" for r in _l(p.get("reparto")))] \
                if p.get("reparto") else []
        elif acc == "politica":
            d = [f"Pregunta la regla de la tienda sobre {str(p.get('tema') or '').replace('_', ' ')}"]
            d += [f"y da por cierto que {p['afirma']}"] if p.get("afirma") else []
        elif acc == "compatibilidad":
            d = [f"Pregunta si {p.get('producto')} anda con {p.get('con')}"]
        elif acc == "explicar":
            d = [f"Pregunta algo general de tecnologia: {p.get('pregunta')}"]
        elif acc == "comprar":
            d += [f"Quiere llevar {', '.join(_art(a, criterio) for a in _l(p.get('agrega')))}"] if p.get("agrega") else []
            d += [f"Saca del pedido {', '.join(map(str, _l(p.get('saca'))))}"] if p.get("saca") else []
            d += [f"Cambia en el pedido {c.get('es')}: " + ", ".join(f"{k} {v}" for k, v in c.items() if k != "es" and v)
                  for c in _l(p.get("cambia"))]
            d += [f"Confirma {', '.join(map(str, _l(p.get('confirma'))))}"] if p.get("confirma") else []
            d += [f"Acepta como quedo {', '.join(map(str, _l(p.get('acepta'))))}"] if p.get("acepta") else []
            d += [f"Dice que en total son {p['total']}"] if p.get("total") else []
            d += ["Rehace el pedido entero asi"] if p.get("reemplaza") else []
            d += ["Paga " + " y ".join(f"{r.get('porcentaje')}% con {r.get('medio')}" for r in _l(p.get("reparto")))] \
                if p.get("reparto") else []
        elif acc == "otro":
            d = [{"saludo": "Saluda o agradece", "dato": "Cuenta algo de si", "corrige": "Corrige lo que dijo",
                  "humano": "Pide hablar con una persona", "fuera_de_tema": "Habla de algo ajeno a la tienda",
                  "catalogo": "Pregunta que vende la tienda"}.get(p.get("que"), f"Otra cosa: {p.get('que')}")]
        if p.get("si"):
            d.append(f"solo si lo de la linea {p['si'].get('de')} da {p['si'].get('da')}")
        if d:
            out.append(f"{len(out) + 1}. " + ", ".join(d) + ".")
    cli = {k: v for k, v in (agenda.get("cliente") or {}).items() if v}
    if cli:
        out.append(f"{len(out) + 1}. Dice de si: " + ", ".join(f"{k} {v}" for k, v in cli.items()) + ".")
    return "\n".join(out) or "Nada: no pidio ni pregunto nada."


def _vara(fuente, cid, estado, salida) -> bool:
    nums = interprete.numeros(estado)
    if fuente == "48":
        ch, t = cid.split(" t")
        vara = V.vara_48(next(c for c in CHARLAS if c["id"] == ch)["turnos"][int(t)])
    elif fuente == "58":
        r = next(x for x in map(json.loads, open(V.TURNOS58, encoding="utf-8")) if f"{x['charla']} t{x['turno']}" == cid)
        vara = V.vara_58(r["agenda"], nums)
    else:
        vara = next(v for i, m, e, h, v in P.nuevas() if i == cid)
    return V.calificar(fuente, cid, vara, P.como_cosas(salida, nums))


async def main() -> None:
    grabado = {(r["fuente"], r["id"]): r.get("salida") for r in
               map(json.loads, open(os.path.join(AQUI, "primera_ejes", "sueltos_rep0.jsonl"), encoding="utf-8"))}
    sem = asyncio.Semaphore(int(os.environ.get("A_LA_VEZ", "3")))

    async def uno(fuente, cid, msg, estado, historial):
        salida = grabado.get((fuente, cid))
        if salida is None:
            return None
        bien = _vara(fuente, cid, estado, salida)
        texto = parafrasis(P.a_agenda(salida, estado, msg))
        msgs = [{"role": "system", "content": CONSIGNA},
                {"role": "user", "content": f"{interprete.libreta(estado, historial, P.TID)}\nULTIMO MENSAJE: {msg}\n\n"
                                            f"LO QUE ENTENDIO EL SISTEMA:\n{texto}"}]
        async with sem:
            try:
                v = interprete._json(await interprete._pedir(msgs, "verificar", FORMATO))
            except Exception as e:  # noqa: BLE001 — un turno sin respuesta queda anotado y no cuenta
                return {"id": cid, "error": f"{type(e).__name__}: {str(e)[:120]}"}
        return {"fuente": fuente, "id": cid, "bien": bien, "coincide": bool(v.get("coincide")),
                "diferencia": v.get("diferencia") or "", "mensaje": msg, "parafrasis": texto}

    rs = [r for r in await asyncio.gather(*[uno(*t) for t in P._turnos_sueltos()]) if r]
    malos = [r for r in rs if "error" in r]
    rs = [r for r in rs if "error" not in r]
    # Cada consigna graba aparte, por su huella: la medida de una no pisa la de otra.
    import hashlib
    nombre = "verificar_" + hashlib.sha1(CONSIGNA.encode()).hexdigest()[:8] + ".jsonl"
    print(f"grabado en {nombre}")
    with open(os.path.join(AQUI, nombre), "w", encoding="utf-8") as fh:
        for r in rs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    bien = [r for r in rs if r["bien"]]
    mal = [r for r in rs if not r["bien"]]
    print(f"\nVERIFICACION sobre {len(rs)} turnos, {len(malos)} sin respuesta del modelo")
    print(f"  de {len(mal)} turnos MAL, el verificador marca {sum(not r['coincide'] for r in mal)}")
    print(f"  de {len(bien)} turnos BIEN, deja pasar {sum(r['coincide'] for r in bien)} y marca {sum(not r['coincide'] for r in bien)}")
    for f in ("48", "58", "nuevas"):
        m, b = [r for r in mal if r["fuente"] == f], [r for r in bien if r["fuente"] == f]
        print(f"    {f:7} mal marcados {sum(not r['coincide'] for r in m)}/{len(m)} · bien marcados "
              f"{sum(not r['coincide'] for r in b)}/{len(b)}")
    if "--ver" in ARGS:
        for r in rs:
            if r["coincide"] == r["bien"]:
                continue
            print(f"\n  {r['id']} · vara {'BIEN' if r['bien'] else 'MAL'} · verificador "
                  f"{'pasa' if r['coincide'] else 'marca: ' + r['diferencia'][:160]}\n    {r['mensaje'][:120]}")


if __name__ == "__main__":
    asyncio.run(main())
