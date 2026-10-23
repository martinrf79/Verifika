"""LA LISTA DE RESPUESTAS — que respuesta de la tienda pide cada parte del mensaje, idea de Martin del 23-oct.

Hasta aca el modelo etiquetaba que quiere el cliente: mirar, llevar, cambiar. Aca etiqueta que RESPUESTA de la tienda
necesita cada parte, de una lista que sale de lo que el ejecutor ya sabe contestar. La lista va en tres versiones:

  corta   las trece respuestas, una linea cada una. Va en la consigna, con los nombres de la tienda como hoy.
  media   cada respuesta con lo que necesita para cumplirse y lo que puede volver, con los rubros, los temas y los
          campos de la tienda adentro de la respuesta que los usa. Va en la consigna en lugar de la corta.
  larga   cada respuesta abierta por cada cosa de la fuente, y las 58 y las 48 escritas como la secuencia de respuestas
          que piden. No va a la consigna: es el indice para los embeddings y el banco de ejemplos. Se arma con --larga y
          queda fuera del repo, porque copia la fuente.

Lo que el modelo elige es la clase de la pregunta. Lo que vuelve —"no lo vendemos", "ese producto no existe", "pasa el
tope"— lo decide el codigo, y la media se lo cuenta al modelo para que no lo confunda con otra clase.

Lo correcto sale de lo escrito a mano antes de correr: el oro de las 48 llevado a respuestas, y las agendas de las 58
con las K, por su accion. En las 58 no cuentan "nada" ni la diferencia entre dato y comparar, que el menu de las
agendas no separa. En las 48 se usa la vara de `actos.py`, con su regla del codigo y `actos.TAMBIEN`.

La base es la consigna unida de hoy, con su acto llevado a respuesta: sus respuestas ya estan guardadas.

    python3 banco_pruebas/respuestas.py --tokens                     cuanto ocupa cada version, sin modelo
    python3 banco_pruebas/respuestas.py --larga                       arma la larga en ~/.cache/verifika
    MARTIN_AUTORIZO_LA_PAGA=<fecha> TOPE_CORRIDA=0.20 python3 banco_pruebas/respuestas.py --lista base|corta|media [--ver]
"""
import asyncio
import collections
import json
import os
import sys

ARGS = sys.argv[1:]
VER = "--ver" in ARGS
LISTA = ARGS[ARGS.index("--lista") + 1] if "--lista" in ARGS else ""
sys.argv = [sys.argv[0]]
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import candidatos as CA  # noqa: E402  — el entorno, la puerta al modelo y el flujo de las 58
from banco_pruebas import libro_paga  # noqa: E402
from app.core.flujo import interprete  # noqa: E402

A = CA.A
TID = CA.TID
TOPE = float(os.environ.get("TOPE_CORRIDA", "0.20"))
LARGA = os.path.expanduser("~/.cache/verifika/respuestas_larga.txt")

# ══ LAS TRES LISTAS ══════════════════════════════════════════════════════════

# Lo que el ejecutor sabe contestar, como clase de pregunta.
CORTA = {
    "opciones": "mostrar opciones de una clase de producto, con lo que pide que tengan o un orden",
    "dato": "un dato de un producto nombrado o mostrado: precio, stock, si hay tantos, una caracteristica",
    "comparar": "comparar dos o mas productos por un dato",
    "compatibilidad": "si un producto anda con algo que tiene el cliente",
    "envio": "cuanto sale o cuanto tarda mandar a un lugar",
    "cuenta": "el total del pedido, un tope de plata o como paga",
    "regla": "como trabaja la tienda: cuotas, garantia, factura, retiro, devoluciones, descuentos",
    "anotar": "sumar algo nuevo al pedido",
    "cambiar": "cambiar algo de lo que ya esta en el pedido: producto, cantidad, color, destino o el criterio de todo",
    "sacar": "sacar algo del pedido",
    "dato_cliente": "anotar algo del cliente: su nombre, su localidad, su equipo",
    "saber_general": "explicar algo de tecnologia en general, que no depende de la tienda",
    "nada": "no hace falta respuesta de la tienda: saluda, agradece, confirma sin cambiar nada",
}


def _indice() -> dict:
    import json as _j
    from app.core.filtros_catalogo import campos_filtrables
    i = A.agente.indice(TID)
    specs = {s["id"]: s.get("etiqueta") or "" for s in _j.load(open(os.path.join(
        os.path.dirname(AQUI), "data", "clientes", TID, "specs_preguntables.json"), encoding="utf-8"))["specs"]}
    campos = [c for c in campos_filtrables(TID) if c not in ("descripcion", "nombre", "modelo", "precio_ars")]
    return {"rubros": sorted(i["rubros"]), "temas": [t.replace("_", " ") for t in i["temas"]],
            "campos": [f"{c.replace('_', ' ')}" + (f" ({specs[c]})" if specs.get(c) else "") for c in campos]}


def media() -> str:
    """Cada respuesta con lo que necesita y lo que puede volver, con los nombres de la tienda adentro."""
    i = _indice()
    filas = {
        "opciones": f"{CORTA['opciones']}. Necesita el rubro, uno de: {', '.join(i['rubros'])}; y si las dice, las "
                    "condiciones y el orden. Puede volver la lista, o que la tienda no vende ese rubro.",
        "dato": f"{CORTA['dato']}. Necesita el producto —el modelo tal cual o su M-n— y el dato: precio, stock o uno de "
                f"estos campos: {', '.join(i['campos'])}. Puede volver el dato, que ese producto no existe, o que la "
                "ficha no lo dice.",
        "comparar": f"{CORTA['comparar']}. Necesita los productos y el dato.",
        "compatibilidad": f"{CORTA['compatibilidad']}. Necesita el producto y con que tiene que andar. Puede volver si, "
                          "no, sin dato, o preguntar el modelo del equipo.",
        "envio": f"{CORTA['envio']}. Necesita el lugar. Vuelve el costo y el plazo.",
        "cuenta": f"{CORTA['cuenta']}. Necesita lo que dijo: el tope, o el medio y el porcentaje de cada parte. Vuelve el "
                  "total, o que pasa el tope.",
        "regla": f"{CORTA['regla']}. Necesita el tema, uno de: {', '.join(i['temas'])}. Vuelve la regla de la tienda.",
        "anotar": f"{CORTA['anotar']}. Necesita el producto o el rubro, la cantidad, el color y el destino si los dice.",
        "cambiar": f"{CORTA['cambiar']}. Necesita el renglon del pedido, L-n, y que cambia.",
        "sacar": f"{CORTA['sacar']}. Necesita el renglon del pedido, L-n.",
        "dato_cliente": f"{CORTA['dato_cliente']}.",
        "saber_general": f"{CORTA['saber_general']}.",
        "nada": f"{CORTA['nada']}.",
    }
    return "\n".join(f"- {k}: {v}" for k, v in filas.items())


def corta() -> str:
    return "\n".join(f"- {k}: {v}" for k, v in CORTA.items())


# ══ LO CORRECTO, EN RESPUESTAS ═══════════════════════════════════════════════

# El acto de `actos.py` es casi la misma lista con otro nombre: asi se compara la base y se usa la vara de las 48.
DEL_ACTO = {"lleva": "anotar", "mira": "opciones", "pregunta_dato": "dato", "compara": "comparar",
            "compatibilidad": "compatibilidad", "cambia": "cambiar", "saca": "sacar", "envio": "envio", "paga": "cuenta",
            "regla_tienda": "regla", "saber_general": "saber_general", "dato_cliente": "dato_cliente", "nada": "nada"}
AL_ACTO = {v: k for k, v in DEL_ACTO.items()}


def oro_58(agenda: dict) -> set:
    out = set()
    for p in agenda.get("preguntas") or []:
        acc = p.get("accion")
        if acc == "buscar":
            out.add("opciones")
        elif acc == "producto":
            out.add("dato")
        elif acc in ("compatibilidad", "envio", "cuenta"):
            out.add(acc)
        elif acc == "politica":
            out.add("regla")
        elif acc == "explicar":
            out.add("saber_general")
        elif acc == "comprar":
            if p.get("reemplaza") or p.get("cambia"):
                out.add("cambiar")
            elif p.get("agrega"):
                out.add("anotar")
            if p.get("saca"):
                out.add("sacar")
        elif acc == "otro" and p.get("que") == "dato":
            out.add("dato_cliente")
    return out


def _58(s: set) -> set:
    """En las 58 no cuentan "nada" ni la diferencia entre dato y comparar."""
    return {"dato" if x == "comparar" else x for x in s} - {"nada"}


# ══ LA LLAMADA ═══════════════════════════════════════════════════════════════

CONSIGNA = """Sos parte del sistema de una tienda online de tecnologia de Argentina. No le contestas al cliente. Con la
LIBRETA de la charla y el ULTIMO MENSAJE, llena esta ficha en JSON:
{{
  "numero": cuantas cosas pide o pregunta el cliente en este mensaje,
  "partes": una por cada cosa, en su orden: [{{"texto": la parte dicha simple, con los modelos y marcas tal cual,
     "respuesta": que respuesta de la tienda necesita esta parte, una de la lista, "depende_de": el numero de la parte
     de la que depende, 0 si no depende de nada, "cantidad": la cantidad con las palabras del cliente, "" si no dice,
     "destino": a donde va, "" si no dice}}]
}}
Los destinos, el color y las condiciones son detalles de su parte, no partes aparte: un destino nunca es una parte.
Un modelo, una marca o un producto concreto que nombra el cliente se copia TAL CUAL lo escribio, con sus errores.
RESPUESTAS QUE DA LA TIENDA, una por parte:
{lista}{nombres}{ejemplos}"""

NOMBRES = """
Cada parte nombra lo que pide o pregunta con el nombre que usa la tienda, si es uno de estos:
- productos: {rubros}
- temas de la tienda: {temas}"""


def consigna(version: str) -> str:
    i = _indice()
    ej = "\nEJEMPLOS, de a pares que se parecen y piden otra respuesta:\n" + "\n".join(
        f'- "{t}" -> {DEL_ACTO[a]}' + (f" ({c})" if c else "") for t, a, c in A.EJEMPLOS)
    nombres = "" if version == "media" else NOMBRES.format(rubros=", ".join(i["rubros"]), temas=", ".join(i["temas"]))
    return CONSIGNA.format(lista=media() if version == "media" else corta(), nombres=nombres, ejemplos=ej)


def formato() -> dict:
    return {"type": "json_schema", "json_schema": {"name": "respuestas", "schema": {
        "type": "object", "required": ["numero", "partes"], "properties": {
            "numero": {"type": "integer"},
            "partes": {"type": "array", "items": {"type": "object",
                       "required": ["texto", "respuesta", "depende_de", "cantidad", "destino"], "properties": {
                           "texto": {"type": "string"}, "respuesta": {"type": "string", "enum": list(CORTA)},
                           "depende_de": {"type": "integer"}, "cantidad": {"type": "string"},
                           "destino": {"type": "string"}}}}}}}}


async def leer(mensaje: str, libreta: str) -> list:
    """Las respuestas de cada parte. La base es la consigna unida de hoy, con su acto llevado a respuesta."""
    if LISTA == "base":
        partes = await CA.traducir(mensaje, libreta)
        return [{**p, "respuesta": DEL_ACTO.get(p.get("acto"), "nada")} for p in partes]
    msgs = [{"role": "system", "content": consigna(LISTA)},
            {"role": "user", "content": libreta + f"\nULTIMO MENSAJE: {A.limpio(mensaje)}"}]
    r = interprete._json(await interprete._pedir(msgs, "respuestas", formato()))
    return [p for p in r.get("partes") or [] if isinstance(p, dict)]


# ══ LA CORRIDA ═══════════════════════════════════════════════════════════════

def tokens() -> None:
    """Cuatro letras por token: la cuenta del proveedor, sin llamarlo."""
    print("Lo que ocupa cada version, a cuatro letras por token:")
    print(f"  corta, la lista sola            {len(corta()) // 4:6}")
    print(f"  media, la lista sola            {len(media()) // 4:6}")
    print(f"  la consigna entera con la corta {len(consigna('corta')) // 4:6}")
    print(f"  la consigna entera con la media {len(consigna('media')) // 4:6}")
    print(f"  la consigna unida de hoy        {len(A.consigna_unida()) // 4:6}")
    if os.path.exists(LARGA):
        print(f"  larga, el indice                {len(open(LARGA, encoding='utf-8').read()) // 4:6}")


def larga() -> None:
    """Cada respuesta abierta por cada cosa de la fuente, y cada turno de la vara como su secuencia de respuestas."""
    from app.storage import firestore_client as fc
    from banco_pruebas.agendas58 import AGENDAS
    i, al = _indice(), A.agente._alias(TID)
    faq = fc.get_all_faq(tienda_id=TID) or {}
    r = ["# LA LISTA LARGA DE RESPUESTAS", "", "## opciones, por rubro"]
    r += [f"- opciones de {x}: {', '.join((al.get('rubros') or {}).get(x, [])[:8])}" for x in i["rubros"]]
    r += ["", "## dato, por campo"] + [f"- dato: {c}" for c in i["campos"]]
    r += ["", "## regla, por tema"] + [
        f"- regla {t}: {str((faq.get(t) or {}).get('respuesta') or '')[:160]}" for t in A.agente.indice(TID)["temas"]]
    r += ["", "## las 58 y las K, cada turno como su secuencia de respuestas"]
    for cid, ags in AGENDAS.items():
        r.append(f"- {cid}: " + " | ".join(" + ".join(sorted(oro_58(ag))) or "nada" for ag in ags))
    r += ["", "## las 48, cada turno como su secuencia de respuestas"]
    for ch in A.CHARLAS:
        r.append(f"- {ch['id']}: " + " | ".join(
            " + ".join(sorted({DEL_ACTO[A.DEL_ORO[x['tipo']]] for x in tu["oro"] if not x.get("opt")}))
            for tu in ch["turnos"]))
    os.makedirs(os.path.dirname(LARGA), exist_ok=True)
    open(LARGA, "w", encoding="utf-8").write("\n".join(r) + "\n")
    print(f"La larga quedo en {LARGA}: {len(r)} lineas, unos {len(chr(10).join(r)) // 4} tokens")


def corrida() -> None:
    desde = libro_paga.gastado(libro_paga._hoy())
    nota = collections.Counter()
    faltas = []
    for ch in A.CHARLAS:
        for i, tu in enumerate(ch["turnos"]):
            if libro_paga.gastado(libro_paga._hoy()) - desde >= TOPE:
                break
            estado, historial = A.P.estado_de(tu["mem"])
            lib = interprete.libreta(estado, historial, TID)
            with CA.Puerta():
                partes = asyncio.run(leer(tu["msg"], lib))
            actos = A.definir([{**p, "acto": AL_ACTO.get(p.get("respuesta"), "nada")} for p in partes], tu["mem"])
            puso = {p["acto"] for p in actos}
            quiere = {A.DEL_ORO[x["tipo"]] for x in tu["oro"] if not x.get("opt")}
            bien = puso == quiere or puso in A.TAMBIEN.get((ch["id"], i), [])
            nota[("48", bien)] += 1
            if not bien:
                faltas.append(("48", f"{ch['id']} t{i}", A.limpio(tu["msg"]), sorted(DEL_ACTO[a] for a in quiere),
                               [(DEL_ACTO.get(p["acto"]), p.get("texto")) for p in actos]))
    from banco_pruebas import cableado58 as C58
    from banco_pruebas.agendas58 import AGENDAS
    from app.core.flujo import estado as E
    from app.storage import firestore_client as fc
    interp = C58.instalar()
    for charla in C58.charlas():
        agendas = list(AGENDAS.get(charla["id"]) or [])
        if len(agendas) != len(charla["turnos"]):
            continue
        uid = f"candidatos_{charla['id']}"
        C58.C.reiniciar_cliente(uid)
        for i, (t, ag) in enumerate(zip(charla["turnos"], agendas)):
            if libro_paga.gastado(libro_paga._hoy()) - desde >= TOPE:
                break
            conv = fc.get_conversation(uid, tienda_id=TID) or {}
            lib = interprete.libreta(E.leer(conv), conv.get("history") or [], TID)
            with CA.Puerta():
                partes = asyncio.run(leer(t["texto"], lib))
            puso, quiere = _58({p.get("respuesta") for p in partes}), _58(oro_58(ag))
            nota[("58", puso == quiere)] += 1
            if puso != quiere:
                faltas.append(("58", f"{charla['id']} t{i}", t["texto"], sorted(quiere),
                               [(p.get("respuesta"), p.get("texto")) for p in partes]))

            async def _interpretar(*a, _ag=ag, **k):
                return _ag

            interp.interpretar = _interpretar
            asyncio.run(C58.C.turno(uid, t["texto"]))
    if VER:
        for fuente, cid, msg, quiere, puso in faltas:
            print(f"--- {fuente} {cid}: {msg[:150]}\n    quiere {quiere}")
            for r, txt in puso:
                print(f"      {str(r):15} {str(txt)[:110]}")
    print(f"\nLA LISTA DE RESPUESTAS, version {LISTA}")
    for f in ("48", "58"):
        print(f"  las {f}: BIEN {nota[(f, True)]} de {nota[(f, True)] + nota[(f, False)]}")
    print(f"Gasto: {libro_paga.gastado(libro_paga._hoy()) - desde:.3f} dolares")


if __name__ == "__main__":
    if "--larga" in ARGS:
        larga()
    if "--tokens" in ARGS:
        tokens()
    if LISTA:
        corrida()
