"""LAS DOS LLAMADAS CON CASOS — el flujo de Martin del 24-oct, FICHA 78 paso 3. Es banco.

  llamada 1   separa el mensaje en partes y traduce cada una: las palabras del cliente tal cual, la parte completa que
              se entiende sin la charla, lo que senala de la libreta y la traduccion calibrada de `traduccion_sola.py`,
              variante orden: la lista cerrada de la tienda, "otro" con la palabra del cliente y "duda".
  el codigo   busca por cada parte completa los CINCO casos mas parecidos del motor de `motor_casos.py`, del mismo
              estado de la charla, sin los casos de la charla que se mide.
  llamada 2   con la libreta, el mensaje ORIGINAL —la segunda que lee solo lo de la primera pierde, FICHA 78—, las partes
              y sus casos, etiqueta cada parte con la respuesta de la tienda que pide, de la lista media de
              `respuestas.py`, y repite en pocas palabras que entendio.
  coincide    el codigo compara las dos: el mismo numero de partes, el mismo renglon del pedido y lo entendido parecido a
              la parte completa por significado. Si no coincide, o la llamada 1 dijo duda, el bot confirmaria o
              repreguntaria en vez de seguir.

Dos formas de la llamada 2: "llamada", una llamada aparte; "vuelta", la misma charla con el modelo, un segundo turno
despues de la traduccion. La vara es la de `respuestas.py`: las 48 por `actos.py` y las 58 con las K por su agenda,
contra la lista media en una llamada, 35 de 48 y 74 de 105. Ademas cuenta lo que importa para vender sin alucinar:
lo mal etiquetado que SIGUE sin confirmar, y cuantas confirmaciones dispara.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> TOPE_CORRIDA=0.30 python3 banco_pruebas/dos_llamadas.py llamada|vuelta [--ver]
"""
import asyncio
import collections
import json
import os
import sys

ARGS = sys.argv[1:]
VER = "--ver" in ARGS
FORMA = "vuelta" if "vuelta" in ARGS else "llamada"
sys.argv = [sys.argv[0]]
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import motor_casos as M  # noqa: E402  — el motor, las varas y el entorno
import traduccion_sola as TS  # noqa: E402
from banco_pruebas import libro_paga  # noqa: E402
from app.core.flujo import interprete  # noqa: E402

R, A, CA = M.R, M.A, M.CA
TOPE = float(os.environ.get("TOPE_CORRIDA", "0.30"))
PARECIDO = 0.80   # lo entendido en la llamada 2 contra la parte completa de la llamada 1, por coseno
SALIDA = os.path.join(M.CACHE, f"dos_llamadas_{FORMA}.jsonl")


# ══ LLAMADA 1: separar y traducir ════════════════════════════════════════════

SEPARAR = """Sos el traductor de una tienda online de tecnologia de Argentina que vende por WhatsApp. No le contestas al
cliente. Con la LIBRETA de la charla y el ULTIMO MENSAJE, separa el mensaje en partes, una por cada cosa que pide,
pregunta o dice, en su orden. Por cada parte:
- "cliente": las palabras del cliente de esa parte, tal cual.
- "completa": la parte completa, que se entienda sin leer la charla. Si no repite de que habla —"¿y en blanco?", "lo de
  Rosario", "el de mi hija"—, lo tomas de la libreta. Una pregunta sigue siendo pregunta y un pedido, pedido.
- "senala": los numeros de la libreta que nombra o senala —M-2 lo mostrado, L-1 un renglon del pedido, R-1 lo que
  pregunto el vendedor—; [] si ninguno.
- "pide": lo que pide en los nombres de la tienda, como se explica abajo.
El destino, el color, la cantidad y las condiciones van dentro de su parte: nunca son una parte aparte.

LA TRADUCCION de cada parte: por cada cosa que pide, su "tipo" —clase de producto, regla de la tienda, caracteristica u
orden— y su "nombre".
"""


def consigna_1() -> str:
    cuerpo = TS.consigna("orden").split("\n", 3)[3]
    return SEPARAR + cuerpo.rsplit("\nDevolve SOLO", 1)[0]


def formato_1() -> dict:
    pide = TS.formato("orden")["json_schema"]["schema"]["properties"]["pide"]
    return {"type": "json_schema", "json_schema": {"name": "separar", "schema": {
        "type": "object", "required": ["partes"], "properties": {"partes": {"type": "array", "items": {
            "type": "object", "required": ["cliente", "completa", "senala", "pide"], "properties": {
                "cliente": {"type": "string"}, "completa": {"type": "string"},
                "senala": {"type": "array", "items": {"type": "string"}}, "pide": pide}}}}}}}


# ══ LLAMADA 2: etiquetar con los casos a la vista ════════════════════════════

ETIQUETAR = """Sos parte del sistema de una tienda online de tecnologia de Argentina. No le contestas al cliente. El
mensaje ya esta separado en partes y traducido. Por cada parte, en el mismo orden, devolve:
- "entendi": que pide o pregunta esa parte, en pocas palabras tuyas.
- "respuesta": que respuesta de la tienda necesita, una de la lista.
- "renglon": si habla de algo que ya esta en el pedido de la libreta, su numero L-n; si no, "".
Lee el ULTIMO MENSAJE tal cual lo escribio el cliente: la separacion puede estar mal, y manda lo que dijo el cliente.
Pedir algo que todavia no eligio —"necesito algo para..."— es opciones: la tienda primero le muestra.
Cada parte trae CASOS RESUELTOS parecidos de esta tienda: como se etiqueto lo que dijo otro cliente en la misma situacion.
Son una guia, no una regla: si la parte dice otra cosa, manda la parte.
RESPUESTAS:
{lista}"""


def consigna_2() -> str:
    return ETIQUETAR.format(lista=R.media())


def formato_2() -> dict:
    return {"type": "json_schema", "json_schema": {"name": "etiquetar", "schema": {
        "type": "object", "required": ["partes"], "properties": {"partes": {"type": "array", "items": {
            "type": "object", "required": ["entendi", "respuesta", "renglon"], "properties": {
                "entendi": {"type": "string"}, "respuesta": {"type": "string", "enum": list(R.CORTA)},
                "renglon": {"type": "string"}}}}}}}}


def pool(casos: list, charla: str) -> list:
    """Los casos que se pueden traer para una parte: los de la plantilla, y los turnos de una sola respuesta de las 48
    y las 58, sin los de la charla que se mide."""
    return [c for c in casos if c["origen"] == "plantilla"
            or (c["charla"] != charla and len(c["respuestas"]) == 1)]


CORTA_PALABRAS = 4   # una respuesta corta, "a Salta", solo se entiende con lo que pregunto el vendedor
MISMO_ESTADO = 0.05  # lo que suma al parecido un caso del mismo estado de la charla: pesa, pero no excluye


def cinco_de(p: dict, turno: dict, casos: list) -> list:
    """Los cinco casos mas parecidos a una parte. La pregunta del vendedor entra solo si lo que dijo el cliente es corto:
    con el pedido armado, "lo de Concordia mandalo a Parana" es un cambio aunque el vendedor haya preguntado el pago."""
    corta = len(str(p.get("cliente") or "").split()) <= CORTA_PALABRAS
    q = M.vectores([M._clave({"frase": str(p.get("completa") or p.get("cliente") or ""),
                               "abierta": turno["abierta"] if corta else ""})])[0]
    cs = pool(casos, turno["charla"])
    vs = M.vectores([M._clave(c) for c in cs])
    nota = [M._coseno(q, v) + MISMO_ESTADO * (c["estado"] == turno["estado"]) for c, v in zip(cs, vs)]
    return [c for _, c in sorted(zip(nota, cs), key=lambda x: -x[0])[:M.CINCO]]


def con_casos(partes: list, turno: dict, casos: list) -> str:
    out = []
    for n, p in enumerate(partes, 1):
        cinco = cinco_de(p, turno, casos)
        pide = "; ".join(f"{x.get('tipo')}: {x.get('nombre')}" + (f" ({x.get('palabra')})" if x.get("palabra") else "")
                         for x in p.get("pide") or [] if isinstance(x, dict))
        out.append(f"PARTE {n}\n  dijo: {p.get('cliente')}\n  completa: {p.get('completa')}\n"
                   f"  senala: {', '.join(p.get('senala') or []) or 'nada'}\n  traduccion: {pide or 'nada'}\n"
                   "  CASOS RESUELTOS:\n" + "\n".join("    " + M.como_ejemplo(c) for c in cinco))
    return "\n".join(out)


async def leer(turno: dict, casos: list) -> tuple:
    usuario_1 = turno["libreta"] + f"\nULTIMO MENSAJE: {A.limpio(turno['frase'])}"
    m1 = [{"role": "system", "content": consigna_1()}, {"role": "user", "content": usuario_1}]
    crudo_1 = await interprete._pedir(m1, "dos_llamadas_1", formato_1())
    partes = [p for p in interprete._json(crudo_1).get("partes") or [] if isinstance(p, dict)]
    if not partes:
        return [], []
    texto_2 = f"ULTIMO MENSAJE: {A.limpio(turno['frase'])}\n\n{con_casos(partes, turno, casos)}"
    if FORMA == "vuelta":
        m2 = m1 + [{"role": "assistant", "content": crudo_1},
                   {"role": "user", "content": consigna_2() + "\n\n" + texto_2}]
    else:
        m2 = [{"role": "system", "content": consigna_2()},
              {"role": "user", "content": turno["libreta"] + "\n" + texto_2}]
    et = [p for p in interprete._json(await interprete._pedir(m2, "dos_llamadas_2", formato_2())).get("partes") or []
          if isinstance(p, dict)]
    return partes, et


# ══ LA COINCIDENCIA ══════════════════════════════════════════════════════════

def coincide(partes: list, et: list) -> str:
    """"" si las dos llamadas dicen lo mismo; si no, por que no: el bot confirmaria o repreguntaria."""
    if any(x.get("nombre") == TS.DUDA for p in partes for x in p.get("pide") or [] if isinstance(x, dict)):
        return "duda"
    if len(partes) != len(et):
        return "partes"
    for p, e in zip(partes, et):
        l1 = sorted(CA._ref(s) for s in p.get("senala") or [] if CA._ref(s).startswith("L-"))
        l2 = CA._ref(e.get("renglon"))
        if l2 and l2 not in l1 or (l1 and not l2 and e.get("respuesta") in ("cambiar", "sacar")):
            return "renglon"
    va, vb = M.vectores([str(p.get("completa") or "") for p in partes]), M.vectores([str(e.get("entendi") or "")
                                                                                    for e in et])
    if any(M._coseno(a, b) < PARECIDO for a, b in zip(va, vb)):
        return "entendido"
    return ""


# ══ LA CORRIDA ═══════════════════════════════════════════════════════════════

def bien(turno: dict, et: list) -> bool:
    puestas = {e.get("respuesta") for e in et}
    if turno["origen"] == "58":
        return R._58(puestas) in [set(v) for v in turno["valen"]]
    ch = next(c for c in A.CHARLAS if c["id"] == turno["charla"])
    tu = ch["turnos"][turno["turno"]]
    actos = A.definir([{"texto": e.get("entendi"), "acto": R.AL_ACTO.get(e.get("respuesta"), "nada")} for e in et],
                      tu["mem"])
    return {a["acto"] for a in actos} in R.valen_48(ch, turno["turno"], tu)


def main() -> None:
    casos = M.cargar()
    turnos = [c for c in casos if c["origen"] in ("48", "58")]
    desde = libro_paga.gastado(libro_paga._hoy())
    nota = collections.Counter()
    faltas = []
    with open(SALIDA, "w", encoding="utf-8") as fh:
        for t in turnos:
            if libro_paga.gastado(libro_paga._hoy()) - desde >= TOPE:
                print(f"TOPE de la corrida: {TOPE} dolares")
                break
            with CA.Puerta():
                partes, et = asyncio.run(leer(t, casos))
                por = coincide(partes, et) if et else "sin salida"
            ok = bool(et) and bien(t, et)
            o = t["origen"]
            nota[(o, "casos")] += 1
            nota[(o, "bien")] += ok
            nota[(o, "sigue bien")] += ok and not por
            nota[(o, "sigue mal")] += (not ok) and not por
            nota[(o, "confirma")] += bool(por)
            nota[(o, "confirma y estaba mal")] += bool(por) and not ok
            nota[("por", por)] += bool(por)
            fh.write(json.dumps({"origen": o, "charla": t["charla"], "turno": t["turno"], "frase": t["frase"],
                                 "partes": partes, "etiqueta": et, "coincide": por, "bien": ok},
                                ensure_ascii=False) + "\n")
            if not ok or por:
                faltas.append((o, t, partes, et, por, ok))
    if VER:
        for o, t, partes, et, por, ok in faltas:
            print(f"--- {o} {t['charla']} t{t['turno']} {'BIEN' if ok else 'MAL'}"
                  + (f" · confirma por {por}" if por else " · sigue") + f"\n    {A.limpio(t['frase'])[:160]}"
                  f"\n    vale {t['valen'][0]}")
            for e in et:
                print(f"      {str(e.get('respuesta')):15} {str(e.get('renglon')):5} {str(e.get('entendi'))[:100]}")
    print(f"\nLAS DOS LLAMADAS CON CASOS, forma {FORMA}")
    for o in ("48", "58"):
        n = nota[(o, "casos")]
        print(f"  las {o}: BIEN {nota[(o, 'bien')]} de {n} · sigue bien {nota[(o, 'sigue bien')]} · "
              f"SIGUE MAL {nota[(o, 'sigue mal')]} · confirma {nota[(o, 'confirma')]}, de esas estaba mal "
              f"{nota[(o, 'confirma y estaba mal')]}")
    print("  confirma por: " + ", ".join(f"{k[1]} {v}" for k, v in nota.items() if k[0] == "por"))
    print(f"  cada turno en {SALIDA}")
    print(f"Gasto: {libro_paga.gastado(libro_paga._hoy()) - desde:.3f} dolares")


if __name__ == "__main__":
    main()
