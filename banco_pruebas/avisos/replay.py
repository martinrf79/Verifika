"""LA DEVUELTA CON AVISOS SEGUROS, como repeticion sobre la base de 475: la primera traduccion es la grabada, y solo
donde salta un aviso se agrega una devuelta. Lo que no recibe aviso no se vuelve a llamar.

  python3 replay.py <nombre> <aviso> [<aviso> ...]
"""
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import candidatos as C  # noqa: E402
import contexto  # noqa: E402

from app.core.flujo import agenda as A  # noqa: E402
from app.core.flujo import interprete as I  # noqa: E402


def correr(nombre: str, avisos: list):
    from banco_pruebas import traduccion58 as T
    base = {tuple(json.loads(k)): v for k, v in json.load(open(os.path.join(AQUI, os.environ.get("BASE_REPLAY", "base521.json")))).items()}
    cache, salta = {}, {}
    for k, r in sorted(base.items()):
        if r["base"] not in ("produccion", "tabla"):
            continue
        if (k[0], k[1]) not in cache:
            cache[(k[0], k[1])] = contexto.contexto(k[0], k[1], uid="rp")
        ag = {kk: vv for kk, vv in r["agenda"].items() if kk != "_crudo"}
        av = [t for a in avisos for t in C.CANDIDATOS[a](ag, cache[(k[0], k[1])]["estado"], r["texto"])]
        if av:
            salta[k] = av
    print(f"saltan en {len(salta)}: {sum(1 for k in salta if not base[k]['bien'])} que fallan, "
          f"{sum(1 for k in salta if base[k]['bien'])} que andan", flush=True)
    por_texto = {base[k]["texto"]: k for k in salta}

    async def interpretar(mensaje, historial, estado, tienda_id, trace_id=""):
        k = por_texto[mensaje]
        r = base[k]
        if r["base"] == "tabla":
            msgs = [{"role": "system", "content": I.consigna(tienda_id)},
                    {"role": "user", "content": I.libreta(estado, historial, tienda_id) + "\n"
                     + T._tabla_ideal(mensaje, tienda_id) + f"\nULTIMO MENSAJE: {mensaje}"}]
        else:
            msgs = I.mensajes(mensaje, historial, estado, tienda_id)
        ag = {kk: vv for kk, vv in r["agenda"].items() if kk != "_crudo"}
        faltas = A.faltas(mensaje, ag, set(I.numeros(estado))) + salta[k]
        crudo, _uso = contexto.llamar(msgs + [{"role": "assistant", "content": json.dumps(ag, ensure_ascii=False)},
                                              {"role": "user", "content": I.DEVUELTA.format(faltas="\n".join(faltas))}],
                                      json_=True)
        return I._json(crudo) or ag
    I.interpretar = interpretar
    T.CORRIDAS = os.path.join(AQUI, f"corridas_{nombre}.jsonl")
    T.REPS = 1
    original = T.formas_de
    T.formas_de = lambda ch, k, *a: {f: v for f, v in original(ch, k, *a).items() if (ch, k, f) in salta}
    turnos = {(c, k) for c, k, _f in salta}
    return T.correr(1, 1, sorted({c for c, _ in turnos}), turnos)


if __name__ == "__main__":
    import replay
    print("terminó" if replay.correr(sys.argv[1], sys.argv[2:]) else "cortado")
