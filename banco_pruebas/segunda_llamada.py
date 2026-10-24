"""LA SEGUNDA LLAMADA CON EL INFORME — paso B del plan de Martin del 24-oct. Es banco.

  llamada 1   la primera llamada entera de `primera_llamada.py`, grabada: separar, completar, modo, para quien y
              traducir. Vuelve de `respuestas_modelo.jsonl` sin gasto.
  informe     el laboratorio de `lab_informe.py`, codigo sin modelo: la tienda, a que renglon o mostrado apunta con
              sus razones, los cinco casos resueltos y las premisas.
  llamada 2   con la libreta, el mensaje ORIGINAL y el informe de cada parte, etiqueta cada parte con la respuesta de la
              tienda que pide, de la lista media de `respuestas.py`, dice a que renglon va y repite lo que entendio.
  coincide    el codigo compara las dos llamadas y el informe: la duda de la llamada 1, el numero de partes, el renglon
              contra lo que senalo la llamada 1 y lo que encontro el laboratorio, y el modo de la llamada 1 contra la
              etiqueta. Si no coincide, el bot confirmaria en vez de seguir.

La vara es la de `respuestas.py`, contra la lista media en una llamada: 35 de 48 y 74 de 105. Cuenta tambien lo que
importa para vender sin alucinar: lo mal etiquetado que SIGUE sin confirmar, y cuantas confirmaciones dispara.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> TOPE_CORRIDA=0.25 python3 banco_pruebas/segunda_llamada.py [--ver]
"""
import asyncio
import collections
import json
import os
import sys

ARGS = sys.argv[1:]
VER = "--ver" in ARGS
sys.argv = [sys.argv[0]]
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import dos_llamadas as DL  # noqa: E402  — la consigna de la etiqueta, el formato y la vara
import lab_informe as LI  # noqa: E402
import primera_llamada as PL  # noqa: E402
import traduccion_sola as TS  # noqa: E402
from banco_pruebas import libro_paga  # noqa: E402
from app.core.flujo import interprete  # noqa: E402

CA, A, MC, R = LI.CA, LI.A, LI.MC, DL.R
TOPE = float(os.environ.get("TOPE_CORRIDA", "0.25"))
# Lo que puede pedir cada modo de la llamada 1. Decidir puede ser opciones: elegir algo que todavia no eligio.
FAMILIA = {"pregunta": {"dato", "comparar", "compatibilidad", "envio", "regla", "cuenta", "saber_general"},
           "pide ver": {"opciones"}, "decide": {"anotar", "cambiar", "sacar", "cuenta", "opciones"},
           "cuenta de si": {"dato_cliente"}, "nada": {"nada"}}
SALIDA = os.path.join(MC.CACHE, "segunda_llamada.jsonl")

ETIQUETAR = """Sos parte del sistema de una tienda online de tecnologia de Argentina. No le contestas al cliente. Otro paso
ya separo el mensaje en partes, y el programa de la tienda reviso cada parte. Por cada parte, en el mismo orden, devolve:
- "entendi": que pide o pregunta esa parte, en pocas palabras tuyas.
- "respuesta": que respuesta de la tienda necesita, una de la lista.
- "renglon": si habla de algo que ya esta en el pedido de la libreta, su numero L-n; si no, "".
Lee el ULTIMO MENSAJE tal cual lo escribio el cliente: si la separacion esta mal, manda lo que dijo el cliente.
Pedir algo que todavia no eligio —"necesito algo para..."— es opciones: la tienda primero le muestra.
Cada parte trae lo que reviso el programa:
- "modo": si pregunta, pide ver, decide, cuenta algo de si o nada. Lo dijo el paso anterior; puede equivocarse.
- "apunta a": el renglon del pedido o lo mostrado al que se refiere, con las razones que encontro el programa. Si apunta
  a un renglon y el cliente decide algo de el, es cambiar o sacar, no anotar ni opciones, aunque pida otro con
  condiciones: "cambialo por uno gamer", "que sean de 27" cambian ese renglon, y la tienda busca el reemplazo.
A donde va lo que lleva o ya pidio es un detalle de anotar o cambiar, no envio: envio es solo cuando pregunta cuanto
sale o cuanto tarda mandar.
- "casos": como se etiqueto lo que dijo otro cliente parecido en esta tienda. Son una guia, no una regla.
RESPUESTAS:
{lista}"""


def consigna() -> str:
    return ETIQUETAR.format(lista=R.media())


def informe_en_palabras(partes: list, inf: list) -> str:
    r = []
    for i, (p, x) in enumerate(zip(partes, inf), 1):
        r.append(f"PARTE {i}\n  dijo: {p.get('cliente')}\n  completa: {p.get('completa')}\n  modo: {p.get('modo')}"
                 + (f"\n  destino: {p['destino']}" if p.get("destino") else "")
                 + (f"\n  para quien: {p['para_quien']}" if p.get("para_quien") else ""))
        pide = "; ".join(f"{y.get('tipo')}: {y.get('nombre')}" for y in p.get("pide") or [] if isinstance(y, dict))
        if pide:
            r.append(f"  en la tienda: {pide}")
        tops = LI.primeros(x["pedido"])
        razones = {k: z for k, _, z in x["pedido"]}
        r.append("  apunta a: " + ("; ".join(f"{k} ({', '.join(razones[k])})" for k in tops) if tops
                                    else "nada del pedido ni de lo mostrado"))
        if x["premisas"]:
            r.append("  premisas: " + "; ".join(x["premisas"]))
        r += ["  casos:"] + [f"    {c}" for c in x["casos"]]
    return "\n".join(r)


async def etiquetar(msg: str, lib: str, partes: list, inf: list) -> list:
    m = [{"role": "system", "content": consigna()},
         {"role": "user", "content": f"{lib}\nULTIMO MENSAJE: {A.limpio(msg)}\n\n{informe_en_palabras(partes, inf)}"}]
    return [e for e in interprete._json(await interprete._pedir(m, "segunda_llamada", DL.formato_2())).get("partes")
            or [] if isinstance(e, dict)]


def coincide(partes: list, inf: list, et: list) -> str:
    """"" si la llamada 1, el informe y la llamada 2 dicen lo mismo; si no, por que no."""
    if any(TS.DUDA == x.get("nombre") for p in partes for x in p.get("pide") or [] if isinstance(x, dict)):
        return "duda"
    if len(partes) != len(et):
        return "partes"
    for p, x, e in zip(partes, inf, et):
        vistos = {CA._ref(s, False) for s in p.get("senala") or []} | set(LI.primeros(x["pedido"]))
        l2 = CA._ref(e.get("renglon"), False)
        if l2 and l2 not in vistos:
            return "renglon"
        if not l2 and e.get("respuesta") in ("cambiar", "sacar") and not any(k.startswith("L-") for k in vistos):
            return "renglon"
    # El modo de la llamada 1 contra la etiqueta de la llamada 2: dos lecturas del mismo lenguaje. Medido el 24-oct sobre
    # la primera corrida, avisa mejor que comparar lo entendido por significado: 26 mal de 37 que confirma, contra 11
    # de 28.
    if any(e.get("respuesta") not in FAMILIA.get(p.get("modo"), set()) for p, e in zip(partes, et)):
        return "modo"
    return ""


def main() -> None:
    todos = MC.cargar()
    desde = libro_paga.gastado(libro_paga._hoy())
    nota = collections.Counter()
    faltas = []
    with open(SALIDA, "w", encoding="utf-8") as fh:
        for fuente, cid, msg, estado, lib, turno, _ in LI.turnos():
            if libro_paga.gastado(libro_paga._hoy()) - desde >= TOPE:
                print(f"TOPE de la corrida: {TOPE} dolares")
                break
            with CA.Puerta():
                partes = asyncio.run(PL.separar(msg, lib))
                inf = LI.informe(partes, estado, lib, turno, todos)
                et = asyncio.run(etiquetar(msg, lib, partes, inf)) if partes else []
                por = coincide(partes, inf, et) if et else "sin salida"
            ok = bool(et) and DL.bien(turno, et)
            nota[(fuente, "casos")] += 1
            nota[(fuente, "bien")] += ok
            nota[(fuente, "sigue bien")] += ok and not por
            nota[(fuente, "sigue mal")] += (not ok) and not por
            nota[(fuente, "confirma")] += bool(por)
            nota[(fuente, "confirma y estaba mal")] += bool(por) and not ok
            nota[("por", por)] += bool(por)
            fh.write(json.dumps({"fuente": fuente, "id": cid, "mensaje": A.limpio(msg), "partes": partes,
                                 "etiqueta": et, "coincide": por, "bien": ok}, ensure_ascii=False) + "\n")
            if not ok or por:
                faltas.append((fuente, cid, msg, turno, et, por, ok))
    if VER:
        for fuente, cid, msg, turno, et, por, ok in faltas:
            print(f"--- {fuente} {cid} {'BIEN' if ok else 'MAL'}" + (f" · confirma por {por}" if por else " · SIGUE")
                  + f"\n    {A.limpio(msg)[:160]}\n    vale {turno['valen'][0]}")
            for e in et:
                print(f"      {str(e.get('respuesta')):15} {str(e.get('renglon')):5} {str(e.get('entendi'))[:100]}")
    print("\nLA SEGUNDA LLAMADA CON EL INFORME, sobre la primera llamada entera grabada")
    for f in ("48", "58"):
        n = nota[(f, "casos")]
        print(f"  las {f}: BIEN {nota[(f, 'bien')]} de {n} · sigue bien {nota[(f, 'sigue bien')]} · "
              f"SIGUE MAL {nota[(f, 'sigue mal')]} · confirma {nota[(f, 'confirma')]}, de esas estaba mal "
              f"{nota[(f, 'confirma y estaba mal')]}")
    print("  confirma por: " + (", ".join(f"{k[1]} {v}" for k, v in nota.items() if k[0] == "por" and v) or "nada"))
    print(f"  cada turno en {SALIDA}")
    print(f"Gasto: {libro_paga.gastado(libro_paga._hoy()) - desde:.3f} dolares")


if __name__ == "__main__":
    main()
