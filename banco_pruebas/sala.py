"""LA SALA — la vara de las 58, solo la traduccion, barata (30-sep-2026).

POR QUE EXISTE. El 28 y 29-sep el banco se llevo unos diez dolares de la clave
paga en un dia: cinco vueltas enteras de la vara por el clon, tres corridas
cada una, mas los mensajes nuevos. Cada charla corria todos sus turnos, con el
webhook entero, y cada turno reenviaba prompt, herramientas y charla dos o tres
veces. Para explorar eso sobra.

NO ES OTRO BANCO. Son las mismas charlas de `vara_58.json`, las mismas piezas
de `desmenuzar.CASOS` y el mismo calificador, `sonda_charlas.interpretacion_de`.
Lo que cambia es cuanto se corre:

  - SOLO EL ULTIMO TURNO va al modelo. Los anteriores de cada charla —lo que
    dijo el cliente, lo que contesto el bot y lo que pidio— se toman de una
    corrida ya guardada, `--historia`. La memoria sale de esa charla de texto:
    la libreta de productos vistos que arma `respuesta` no entra, asi que las
    charlas de memoria se miden un poco mas dificiles que en produccion.
  - SIN EL WEBHOOK: `agente.turno` directo, con el motor de verdad sobre el
    doble de Firestore.
  - CON LA CLAVE GRATIS, siempre. Si el entorno no tiene una gratis distinta de
    la paga, no corre.
  - UNA REPETICION y un TOPE de tokens de entrada que corta solo.

Mide la INTERPRETACION —lo que el modelo le pide al codigo—, no la respuesta.
Para decidir si una mejora entra sigue mandando la vara por el clon y
`puerta.py`, con tres corridas.

  python3 -m banco_pruebas.sala --etiqueta prueba
  python3 -m banco_pruebas.sala C27 C46 --etiqueta prueba
  python3 -m banco_pruebas.sala --etiqueta prueba --frases otras.json   el ultimo turno dicho de otra forma
  python3 -m banco_pruebas.sala --informe --etiqueta prueba --contra otra
  opciones: --historia v58_p_1  --tope 600000
"""
import json
import os
import sys

SALIDA = "banco_pruebas/sala_corridas.jsonl"
TOPE = 600_000


def _opt(a, nombre, defecto, tipo=str):
    if nombre in a:
        i = a.index(nombre)
        v = tipo(a[i + 1])
        del a[i:i + 2]
        return v
    return defecto


def _historias(etiqueta: str) -> dict:
    """Las charlas guardadas de esa corrida del clon, por id."""
    from banco_pruebas.sonda_charlas import SALIDA as CORRIDAS
    out = {}
    for x in open(CORRIDAS, encoding="utf-8"):
        f = json.loads(x)
        if f["etiqueta"] == etiqueta:
            out[f["id"]] = f
    return out


def correr(ids: list, etiqueta: str, historia: str, frases: str, tope: int) -> None:
    from banco_pruebas import clon_produccion as C
    detalle = C.preparar_entorno()
    if "gratis" not in detalle["clave"] or "NO disponible" in detalle["clave"]:
        sys.exit(f"LA SALA CORRE SOLO CON LA CLAVE GRATIS y no hay una distinta de la paga: {detalle['clave']}")
    C.instalar()
    import asyncio
    from app.core import agente
    from banco_pruebas.sonda_charlas import _guardadas, charlas
    previas = _historias(historia)
    if not previas:
        sys.exit(f"no hay corrida guardada con la etiqueta {historia}")
    otras = json.load(open(frases, encoding="utf-8")) if frases else {}
    gastado = 0
    for c in charlas():
        if ids and c["id"] not in ids:
            continue
        ref = previas.get(c["id"])
        if ref is None or len(ref["turnos"]) != len(c["turnos"]):
            continue
        if gastado >= tope:
            print(f"TOPE: {gastado} tokens de entrada, se corta antes de {c['id']}")
            break
        historial = []
        for t in ref["turnos"][:-1]:
            historial += [{"role": "user", "content": t["texto"]}, {"role": "assistant", "content": t["respuesta"]}]
        mensaje = (otras.get(c["id"]) or [c["turnos"][-1]["texto"]])[-1]
        r = asyncio.run(agente.turno(historial, mensaje, C.TIENDA, trace_id=f"sala_{c['id']}"))
        crudas, vueltas = _guardadas(r["llamadas"])
        uso = r.get("uso") or []
        gastado += sum(u.get("entrada", 0) for u in uso)
        ultimo = {"turno": len(c["turnos"]), "texto": mensaje, "casillas": [], "plata_no_vista": [],
                  "vacia": not (r.get("texto") or "").strip(), "llamadas": crudas, "vueltas": vueltas,
                  "respuesta": r.get("texto") or "", "uso": uso}
        fila = {"etiqueta": etiqueta, "historia": historia, "id": c["id"],
                "turnos": ref["turnos"][:-1] + [ultimo]}
        with open(SALIDA, "a", encoding="utf-8") as f:
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
        print(f"{c['id']:5} {len(crudas)} llamadas  {gastado} tokens", flush=True)
    print(f"listo: {gastado} tokens de entrada")


def notas(etiqueta: str) -> dict:
    """{id: (bien, piezas)} de la interpretacion del ultimo turno."""
    from banco_pruebas.desmenuzar import CASOS
    from banco_pruebas.pedido_agente import preparar_sin_modelo
    from banco_pruebas.sonda_charlas import interpretacion_de
    preparar_sin_modelo()
    casos = {c[0]: c for c in CASOS}
    out = {}
    for x in open(SALIDA, encoding="utf-8"):
        f = json.loads(x)
        if f["etiqueta"] == etiqueta and f["id"] in casos:
            n = interpretacion_de(f, casos[f["id"]])
            out[f["id"]] = (n["bien"] == n["piezas"], n["detalle"])
    return out


def informe(etiqueta: str, contra: str = "") -> None:
    a = notas(etiqueta)
    tok = sum(u.get("entrada", 0) for x in open(SALIDA, encoding="utf-8")
              for f in [json.loads(x)] if f["etiqueta"] == etiqueta for u in f["turnos"][-1].get("uso") or [])
    print(f"SALA · {etiqueta} · interpretacion entera bien: {sum(v[0] for v in a.values())} de {len(a)} · "
          f"{tok} tokens de entrada")
    if contra:
        b = notas(contra)
        print(f"     contra {contra}: {sum(v[0] for v in b.values())} de {len(b)}")
        for k in sorted(set(a) & set(b)):
            if a[k][0] != b[k][0]:
                print(f"    {k}  {'ARREGLA' if a[k][0] else 'ROMPE  '}  {(b[k][1] if a[k][0] else a[k][1])[:90]}")
    else:
        for k, v in sorted(a.items()):
            if not v[0]:
                print(f"    {k}  {v[1][:100]}")


def main():
    a = sys.argv[1:]
    etiqueta = _opt(a, "--etiqueta", "")
    if not etiqueta:
        sys.exit("falta --etiqueta")
    contra = _opt(a, "--contra", "")
    if "--informe" in a:
        informe(etiqueta, contra)
        return
    historia = _opt(a, "--historia", "v58_p_1")
    frases = _opt(a, "--frases", "")
    tope = _opt(a, "--tope", TOPE, int)
    if os.environ.get("BANCO_CLAVE_PAGA", "").lower() in ("true", "1", "yes"):
        sys.exit("LA SALA NO USA LA CLAVE PAGA: saca BANCO_CLAVE_PAGA")
    correr([x for x in a if not x.startswith("--")], etiqueta, historia, frases, tope)
    informe(etiqueta)


if __name__ == "__main__":
    main()
