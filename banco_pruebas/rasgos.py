"""LOS RASGOS DEL MENSAJE QUE EL CODIGO VE SOLO — el filtro antes del modelo, medido sin modelo (27-oct-2026, FICHA 82).

Idea de la sesion con Martin del 27-oct. Lo que traba la separacion es de superficie: lugares, cantidades, porcentajes,
montos, un "si", nombres de modelo y de rubro. El codigo los lee sin entender el razonamiento, y con eso elige que
bloques de la consigna entran para ese mensaje. Antes de escribir los bloques se mide si el codigo detecta bien cada
rasgo, contra la vara de cada turno: cuantos detecta de los que hay y cuantas falsas alarmas da.

  varios lugares   dos o mas lugares, como destino o en la pregunta del envio: el bloque del reparto
  condicion        una compra o una accion que depende de algo: el bloque de la condicion
  para todo        un tope del total, un reparto del pago o un orden para todo: el bloque de "todo"
  varias cosas     dos o mas cosas en el mensaje: el bloque de separar

    python3 banco_pruebas/rasgos.py [--ver]
"""
import collections
import re
import sys

sys.argv, ARGS = [sys.argv[0]], sys.argv[1:]
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import embeddings_primera as EP  # noqa: E402  — la vara y los turnos

P, V = EP.P, EP.V
FUERA = {"de_si", "nada"}
_SI = re.compile(r"\b(si (no |hay|tenes|tienen|tiene|sale|salen|anda|andan|pasa|pasan|me |le |es |son |el |la |los |las |"
                 r"llega|alcanza|queda|se |da |esta|estan|viene|vienen|funciona|sirve|cuesta)|en caso de|siempre que|"
                 r"salvo que|a menos que)")
_TODO = re.compile(r"\b(todo|en total|total|presupuesto|no (quiero )?pas(ar|e)|mitad|tope|hasta)\b")


def detectar(msg: str) -> dict:
    """Los rasgos, solo con el codigo: el padron de lugares, los montos, los pares que suman cien, los rubros y modelos."""
    from app.core.flujo import marcador as MK
    from app.core.flujo.normal import lugares
    t = V.n(msg)
    ws = t.split()
    lus = {V.n(x[0]) for x in lugares(msg)}
    montos = [m for m in MK._MONTO.finditer(t) if m.group(2) or m.group(3)]
    par = [m for m in MK._PAR.finditer(t) if MK._numero(m.group(1)) + MK._numero(m.group(2)) == 100]
    cosas = {r for _, r in MK._rubros(ws, P.TID)} | {p for p, _ in MK._productos(ws, P.TID)}
    return {"varios lugares": len(lus) > 1,
            "condicion": bool(_SI.search(t)),
            "para todo": bool(par) or "%" in msg or (bool(montos) and bool(_TODO.search(t))),
            "varias cosas": len(cosas) > 1 or len(lus) > 1 or bool(re.search(r"\by\b.*\?|\?.*\?", t))}


def de_la_vara(vara: dict) -> dict:
    cs = [c for c in vara["cosas"] if c["acto"] not in FUERA]
    lus = {V.n(c["datos"].get("destino")) for c in cs if c["datos"].get("destino")}
    lus |= {(c["que"] or [""])[0] for c in cs if c["acto"] == "envio"}
    return {"varios lugares": len(lus) > 1,
            "condicion": any(c["datos"].get("depende") for c in cs) or "si_pasa" in vara["todo"],
            "para todo": bool({"orden", "tope", "reparto"} & set(vara["todo"])),
            "varias cosas": len(cs) > 1}


def main() -> None:
    cuenta = collections.defaultdict(collections.Counter)
    errores = collections.defaultdict(list)
    n = 0
    for f, cid, msg, est, h in P._turnos_sueltos():
        vara, _ = EP._vara_de(f, cid, est)
        oro, dice = de_la_vara(vara), detectar(msg)
        n += 1
        for k in oro:
            cuenta[k][("hay" if oro[k] else "no hay", "detecta" if dice[k] else "no detecta")] += 1
            if oro[k] != dice[k]:
                errores[k].append((cid, "se le escapa" if oro[k] else "falsa alarma", msg))
    print(f"\nLOS RASGOS QUE EL CODIGO VE SOLO · {n} turnos, contra la vara")
    for k, c in cuenta.items():
        hay = c[("hay", "detecta")] + c[("hay", "no detecta")]
        print(f"  {k:15} hay en {hay:3} · detecta {c[('hay', 'detecta')]:3} · se le escapan {c[('hay', 'no detecta')]:2}"
              f" · falsas alarmas {c[('no hay', 'detecta')]:2} de {n - hay} · acierta {c[('hay', 'detecta')] + c[('no hay', 'no detecta')]} de {n}")
    if "--ver" in ARGS:
        for k, es in errores.items():
            print(f"\n{k}")
            for cid, que, msg in es:
                print(f"  {cid:9} {que:13} {msg[:100]}")


if __name__ == "__main__":
    main()
