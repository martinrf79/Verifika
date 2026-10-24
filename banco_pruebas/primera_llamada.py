"""LA PRIMERA LLAMADA ENTERA — separar, completar y traducir en una sola, punto G del plan de Martin del 24-oct. Banco.

Junta en una llamada lo que se midio por separado: la separacion con la pregunta completa de `candidatos.py --pulida` y
la traduccion calibrada de `traduccion_sola.py`, variante orden. Por cada parte devuelve:
  cliente     las palabras del cliente tal cual: la segunda llamada lee lo que dijo, no solo lo reescrito.
  completa    la parte entera, que se entiende sin la charla.
  modo        pregunta, pide ver, decide, cuenta de si o nada: lo que es lenguaje y el codigo no puede poner. Al
              reescribir, el modelo volvia pedido lo que era pregunta, FICHA 78; el modo lo deja dicho aparte.
  senala      los numeros de la libreta.
  destino y para_quien   lo que distingue dos renglones del mismo rubro: "el de mi hija".
  pide        la traduccion a los nombres de la tienda, con "otro" y "duda".

Se mide contra la separacion grabada, la base, con cuatro varas escritas a mano en las 48 y las 58:
  modo        en las 48, el modo de cada cosa del oro: P, CMP, CO, E, PO y EX preguntan; B pide ver; AG, CA, ORD, SA y
              CU deciden; CL cuenta de si; NADA nada. Cuenta el turno si los modos de las partes son los del oro.
  tienda      el rubro, el tema y el producto por significado sobre la parte completa, la vara de `candidatos.py`.
  renglon     a que renglon o mostrado apunta, con el laboratorio de `lab_informe.py`.
  nombre      el rubro o el tema que el modelo pone en "pide", directo, sin busqueda.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> TOPE_CORRIDA=0.15 python3 banco_pruebas/primera_llamada.py [--ver] [--base]

--base corre lo mismo con la separacion grabada, gratis, para tener la base con la misma cuenta.
"""
import asyncio
import collections
import json
import os
import sys

ARGS = sys.argv[1:]
VER = "--ver" in ARGS
BASE = "--base" in ARGS
sys.argv = [sys.argv[0]]
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import lab_informe as LI  # noqa: E402  — el laboratorio, la vara y la separacion grabada
import traduccion_sola as TS  # noqa: E402
from banco_pruebas import libro_paga  # noqa: E402
from app.core.flujo import catalogo as K  # noqa: E402
from app.core.flujo import interprete  # noqa: E402

CA, A, MC = LI.CA, LI.A, LI.MC
TOPE = float(os.environ.get("TOPE_CORRIDA", "0.15"))
MODOS = ["pregunta", "pide ver", "decide", "cuenta de si", "nada"]
DEL_ORO = {"P": "pregunta", "CMP": "pregunta", "CO": "pregunta", "E": "pregunta", "PO": "pregunta", "EX": "pregunta",
           "B": "pide ver", "AG": "decide", "CA": "decide", "ORD": "decide", "SA": "decide", "CU": "decide",
           "CL": "cuenta de si", "NADA": "nada"}
# El acto de la separacion grabada, en modo: asi la base se mide con la misma vara.
DEL_ACTO = {"lleva": "decide", "cambia": "decide", "saca": "decide", "paga": "decide", "mira": "pide ver",
            "pregunta_dato": "pregunta", "compara": "pregunta", "compatibilidad": "pregunta", "envio": "pregunta",
            "regla_tienda": "pregunta", "saber_general": "pregunta", "dato_cliente": "cuenta de si", "nada": "nada"}
SALIDA = os.path.join(MC.CACHE, "primera_llamada" + ("_base" if BASE else "") + ".jsonl")

CONSIGNA = """Sos el traductor de una tienda online de tecnologia de Argentina que vende por WhatsApp. No le contestas al
cliente. Con la LIBRETA de la charla y el ULTIMO MENSAJE, separa el mensaje en partes, una por cada cosa que pide,
pregunta o dice, en su orden. El destino, el color, la cantidad, para quien es y las condiciones van dentro de su parte:
nunca son una parte aparte. Una parte habla de una sola clase de producto: "dos teclados y dos mouse" son dos partes.
No juntes en una parte lo que pregunta con lo que decide: "¿hay tres? si hay, llevo tres" son dos partes. Por cada parte:
- "cliente": las palabras del cliente de esa parte, tal cual, sin cambiar nada.
- "completa": la parte entera, que se entienda sin leer la charla. Si no repite de que habla —"¿y en blanco?", "lo de
  Rosario", "el de mi hija"—, lo tomas de la libreta. Completar no es cambiar lo que dijo: una pregunta sigue siendo
  pregunta, con su signo, y un pedido sigue siendo pedido.
- "modo": que hace el cliente con esa parte, uno de estos:
    pregunta       quiere saber algo: un dato, un precio, si anda con algo, cuanto sale el envio, una regla de la tienda
    pide ver       quiere ver opciones de algo que todavia no eligio: "mostrame", "que tenes", "necesito algo para...",
                   "¿que me recomendas?"
    decide         decide algo del pedido: llevar, cambiar, sacar, a donde va, como paga, cuanto quiere gastar o su
                   presupuesto, y lo que pide que tenga lo que lleva: "que sean de marca conocida", "que no sea chino"
    cuenta de si   dice algo de si mismo que no es del pedido: su nombre, su localidad, el equipo que tiene
    nada           saluda, agradece o confirma sin pedir nada
  Lo que pide que tenga un producto es una condicion de lo que decide, no una pregunta, aunque no lleve verbo.
- "senala": los numeros de la libreta que nombra o senala —M-2 lo mostrado, L-1 un renglon del pedido, R-1 lo que
  pregunto el vendedor—; [] si ninguno.
- "destino": a donde va, si lo dice o lo senala; "" si no.
- "para_quien": para quien es, si lo dice —"mi hija", "el puesto de Juan"—; "" si no.
- "pide": lo que pide en los nombres de la tienda, como se explica abajo.

LA TRADUCCION de cada parte: por cada cosa que pide, su "tipo" —clase de producto, regla de la tienda, caracteristica u
orden— y su "nombre".
"""


def consigna() -> str:
    cuerpo = TS.consigna("orden").split("\n", 3)[3]
    return CONSIGNA + cuerpo.rsplit("\nDevolve SOLO", 1)[0]


def formato() -> dict:
    pide = TS.formato("orden")["json_schema"]["schema"]["properties"]["pide"]
    campos = {"cliente": {"type": "string"}, "completa": {"type": "string"},
              "modo": {"type": "string", "enum": MODOS}, "senala": {"type": "array", "items": {"type": "string"}},
              "destino": {"type": "string"}, "para_quien": {"type": "string"}, "pide": pide}
    return {"type": "json_schema", "json_schema": {"name": "primera_llamada", "schema": {
        "type": "object", "required": ["partes"], "properties": {"partes": {"type": "array", "items": {
            "type": "object", "required": list(campos), "properties": campos}}}}}}


async def separar(mensaje: str, libreta: str) -> list:
    """Las partes con la forma que lee el laboratorio: "texto" es la parte completa."""
    if BASE:
        return await CA.traducir(mensaje, libreta)
    msgs = [{"role": "system", "content": consigna()},
            {"role": "user", "content": libreta + f"\nULTIMO MENSAJE: {A.limpio(mensaje)}"}]
    r = interprete._json(await interprete._pedir(msgs, "primera_llamada", formato()))
    return [{**p, "texto": p.get("completa") or p.get("cliente") or ""} for p in r.get("partes") or []
            if isinstance(p, dict)]


# ══ LAS VARAS ════════════════════════════════════════════════════════════════

NOTA = collections.defaultdict(collections.Counter)
FALTAS = []


def modos_oro(oro: list) -> set:
    return {DEL_ORO[x["tipo"]] for x in oro if not x.get("opt")}


def nombres(partes: list) -> set:
    return {K.n(x.get("nombre")) for p in partes for x in p.get("pide") or [] if isinstance(x, dict)}


def notar(fuente: str, cid: str, msg: str, partes: list, inf: list, esperado: list, mapas: dict, oro: list) -> None:
    LI.notar(fuente, cid, msg, inf, esperado, mapas)
    if fuente == "48":
        quiere, puso = modos_oro(oro), {p.get("modo") or DEL_ACTO.get(p.get("acto")) for p in partes}
        # Como en la vara de las 58, "nada" no cuenta junto a otra cosa: "Bien, ..." no es una parte que falte.
        if len(puso) > 1:
            puso -= {"nada"}
        valen = [quiere]
        # La decision de Martin del 23-oct, la de respuestas.valen_48: pedir algo que todavia no eligio es pide ver.
        if any(x["tipo"] == "AG" and not x.get("cual") for x in oro if not x.get("opt")):
            valen += [(quiere - {"decide"}) | {"pide ver"}, quiere | {"pide ver"}]
        NOTA[fuente]["modo casos"] += 1
        NOTA[fuente]["modo bien"] += puso in valen
        if puso not in valen:
            FALTAS.append((cid, msg, sorted(quiere), [(p.get("modo") or DEL_ACTO.get(p.get("acto")),
                                                       p.get("cliente") or p.get("texto")) for p in partes]))
    if not BASE:
        dichos = nombres(partes)
        for capa, vale, _ in esperado:
            if capa in ("rubro", "tema"):
                NOTA[fuente][f"nombre {capa} casos"] += 1
                NOTA[fuente][f"nombre {capa} bien"] += bool({K.n(v.replace("_", " ")) for v in vale} & dichos)
        NOTA[fuente]["para quien"] += sum(bool(p.get("para_quien")) for p in partes)
        NOTA[fuente]["duda"] += sum(K.n(x.get("nombre")) == TS.DUDA for p in partes for x in p.get("pide") or []
                                    if isinstance(x, dict))
        NOTA[fuente]["partes"] += len(partes)


def main() -> None:
    todos = MC.cargar()
    oros = {f"{ch['id']} t{i}": tu["oro"] for ch in A.CHARLAS for i, tu in enumerate(ch["turnos"])}
    desde = libro_paga.gastado(libro_paga._hoy())
    with open(SALIDA, "w", encoding="utf-8") as fh:
        for fuente, cid, msg, estado, lib, turno, esperado in LI.turnos():
            if libro_paga.gastado(libro_paga._hoy()) - desde >= TOPE:
                print(f"TOPE de la corrida: {TOPE} dolares")
                break
            with CA.Puerta():
                partes = asyncio.run(separar(msg, lib))
                inf = LI.informe(partes, estado, lib, turno, todos)
            notar(fuente, cid, A.limpio(msg), partes, inf, esperado, CA.a_renglon(estado),
                  oros.get(cid) if fuente == "48" else [])
            fh.write(json.dumps({"fuente": fuente, "id": cid, "mensaje": A.limpio(msg), "partes": partes},
                                ensure_ascii=False) + "\n")
    if VER:
        print("\n=== EL MODO QUE NO SALIO, en las 48")
        for cid, msg, quiere, puso in FALTAS:
            print(f"--- {cid}: quiere {quiere}\n    {msg[:150]}")
            for m, c in puso:
                print(f"      {str(m):13} {str(c)[:100]}")
    print("\nLA PRIMERA LLAMADA" + (", LA BASE: la separacion grabada de candidatos.py --pulida" if BASE
                                    else " ENTERA: separar, completar, modo y traducir en una"))
    for fuente in ("48", "58"):
        for capa in ("rubro", "tema", "producto", "charla"):
            n = LI.NOTA[(fuente, capa)]
            if n["casos"]:
                print(f"  las {fuente} · {capa:9} {n['casos']:3} casos · primero {n['primero']:3}"
                      f" · entre los tres {n['entre los tres']:3}"
                      + (f" · igual el mostrado y su renglon {n['mismo producto']:3}" if capa == "charla" else ""))
        n = NOTA[fuente]
        if n["modo casos"]:
            print(f"  las {fuente} · el modo de cada turno: {n['modo bien']} de {n['modo casos']}")
        for capa in ("rubro", "tema"):
            if n[f"nombre {capa} casos"]:
                print(f"  las {fuente} · el {capa} que nombra el modelo, sin busqueda: {n[f'nombre {capa} bien']} de "
                      f"{n[f'nombre {capa} casos']}")
        if n["partes"]:
            print(f"  las {fuente} · {n['partes']} partes, con para quien {n['para quien']}, con duda {n['duda']}")
    print(f"  cada turno en {SALIDA}")
    print(f"Gasto: {libro_paga.gastado(libro_paga._hoy()) - desde:.3f} dolares")


if __name__ == "__main__":
    main()
