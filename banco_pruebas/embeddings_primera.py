"""LA PRIMERA TRADUCCION MEDIDA CON EMBEDDINGS — que ve el parecido de lo que la vara marca mal (27-oct-2026, FICHA 82).

Pregunta de Martin del 27-oct: la primera traduccion, partir el mensaje y traducir cada parte, ¿se mide con embeddings?
No: la mide `vara_dato.py`, dato por dato. Los embeddings de la FICHA 82 solo traen ejemplos parecidos a la consigna. Esto
mide, sobre los 169 turnos sueltos grabados de Gemini, `primera_ejes/sueltos_rep0.jsonl`, tres senales sin modelo de
texto, solo embeddings:

  el corte      cada frase del mensaje, cortada por el codigo con `lectura.frases`, contra las palabras del cliente de
                cada parte: la frase que no se parece a ninguna parte es algo que el modelo dejo afuera.
  la parafrasis cada frase contra la cuenta en castellano llano de lo que va a hacer el codigo, la de `verificar.py`, y al
                reves: lo que se pidio y no se hace, o lo que se hace y no se pidio.
  el acto       cada parte del modelo contra las frases de una sola parte de la plantilla de venta, con su hace y sobre a
                mano: los k mas parecidos votan el acto. La plantilla no tiene ninguna frase del examen.

La vara es la de siempre, entero o no, y el acto de cada cosa de la vara alineado a su parte como en `calificar`. Se
compara con el verificador por parafrasis con modelo, `verificar_357f8072.jsonl`.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/embeddings_primera.py      con la paga, por orden de Martin
    python3 banco_pruebas/embeddings_primera.py --ver                                ademas, cada turno marcado
"""
import collections
import json
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
ARGS = sys.argv[1:]
sys.path.insert(0, AQUI)
import candidatos82 as C82  # noqa: E402  — primero: lee la orden de la paga antes de que el clon la saque
import verificar as VE  # noqa: E402
from fichas import CHARLAS  # noqa: E402
from app.core.flujo import interprete  # noqa: E402
from app.core.flujo import lectura as L  # noqa: E402

P, V = VE.P, VE.V
K_VOTO = 7


def _vara_de(fuente, cid, estado):
    nums = interprete.numeros(estado)
    if fuente == "48":
        ch, t = cid.split(" t")
        return V.vara_48(next(c for c in CHARLAS if c["id"] == ch)["turnos"][int(t)]), nums
    if fuente == "58":
        r = next(x for x in map(json.loads, open(V.TURNOS58, encoding="utf-8")) if f"{x['charla']} t{x['turno']}" == cid)
        return V.vara_58(r["agenda"], nums), nums
    return next(v for i, m, e, h, v in P.nuevas() if i == cid), nums


def _alinear(vara: dict, leido: dict) -> dict:
    """{indice de la parte: acto de la vara}, eligiendo como `calificar`."""
    out, usados = {}, set()
    for c in vara["cosas"]:
        cand = [(i, x) for i, x in enumerate(leido["cosas"]) if i not in usados and V._encuentra(c, x)]
        if not cand:
            continue
        mismo = [(i, x) for i, x in cand if x["acto"] == c["acto"]]
        i = (mismo or cand)[0][0]
        usados.add(i)
        out[i] = c["acto"]
    return out


def _acto(hace: str, sobre: str) -> str:
    c = P.como_cosas({"partes": [{"hace": hace, "sobre": sobre, "que": "x"}]}, {})["cosas"]
    return c[0]["acto"] if c else "nada"


def _pool() -> list:
    """Las frases de la plantilla cuya agenda es una sola parte: (texto, hace, sobre)."""
    from banco_pruebas.plantilla_venta import llenar as LL
    LL.entorno()
    out = []
    for c in LL.llenar()["casos"]:
        if not c.get("entra"):
            continue
        ps = P.partes_de_agenda(c["agenda"]).get("partes") or []
        if len(ps) == 1:
            out += [(x["texto"], ps[0]["hace"], ps[0]["sobre"], c["id"]) for x in c["frases"]]
    return out


def _auc(pos: list, neg: list) -> float:
    """La probabilidad de que un turno MAL tenga mas alarma que uno BIEN."""
    if not pos or not neg:
        return float("nan")
    return float(np.mean([(p > q) + 0.5 * (p == q) for p in pos for q in neg]))


def main() -> None:
    grabado = {(r["fuente"], r["id"]): r.get("salida") for r in
               map(json.loads, open(os.path.join(AQUI, "primera_ejes", "sueltos_rep0.jsonl"), encoding="utf-8"))}
    llm = {r["id"]: r for r in map(json.loads, open(os.path.join(AQUI, "verificar_357f8072.jsonl"), encoding="utf-8"))}
    turnos = []
    for fuente, cid, msg, estado, historial in P._turnos_sueltos():
        salida = grabado.get((fuente, cid))
        if not salida:
            continue
        vara, nums = _vara_de(fuente, cid, estado)
        leido = P.como_cosas(salida, nums)
        bien = V.calificar(fuente, cid, vara, leido)
        partes = [p for p in salida.get("partes") or [] if isinstance(p, dict)]
        turnos.append({"fuente": fuente, "id": cid, "msg": msg, "bien": bien, "partes": partes,
                       "oro": _alinear(vara, leido), "cosas": leido["cosas"],
                       "frases": L.frases(msg) or [msg],
                       "para": [x.split(". ", 1)[-1] for x in VE.parafrasis(P.a_agenda(salida, estado, msg)).split("\n")],
                       "llm_marca": cid in llm and not llm[cid]["coincide"]})
    pool = _pool()
    textos = [t for t, *_ in pool]
    for t in turnos:
        textos += t["frases"] + t["para"] + [p.get("cliente") or p.get("que") or "" for p in t["partes"]]
    textos = [x if x.strip() else "-" for x in textos] + ["-"]
    E = dict(zip(dict.fromkeys(textos), C82.embeddings(list(dict.fromkeys(textos)))))
    mp = np.stack([E[t] for t, *_ in pool])

    # ── las tres senales por turno ──
    conf = collections.Counter()
    acto_g = acto_k = acto_n = 0
    discrepa = []
    for t in turnos:
        fr = np.stack([E[x if x.strip() else "-"] for x in t["frases"]])
        cl = [p.get("cliente") or p.get("que") or "-" for p in t["partes"]] or ["-"]
        pc = np.stack([E[x if x.strip() else "-"] for x in cl])
        pa = np.stack([E[x if x.strip() else "-"] for x in t["para"]])
        t["corte"] = 1 - float((fr @ pc.T).max(axis=1).min())
        s = fr @ pa.T
        t["parafrasis"] = 1 - float(min(s.max(axis=1).min(), s.max(axis=0).min()))
        t["acto_mal"] = 0
        for i, p in enumerate(t["partes"]):
            sim = mp @ E[cl[i] if cl[i].strip() else "-"]
            votos = collections.Counter()
            for j in np.argsort(-sim)[:K_VOTO]:
                votos[_acto(pool[j][1], pool[j][2])] += sim[j]
            k_acto = votos.most_common(1)[0][0]
            g_acto = t["cosas"][i]["acto"] if i < len(t["cosas"]) else "nada"
            if k_acto != g_acto:
                t["acto_mal"] += 1
            if i in t["oro"]:
                oro = t["oro"][i]
                acto_n += 1
                acto_g += g_acto == oro
                acto_k += k_acto == oro
                conf[(g_acto == oro, k_acto == oro)] += 1
                if k_acto != g_acto:
                    discrepa.append((g_acto == oro, k_acto == oro, t["id"], cl[i], g_acto, k_acto, oro))

    bien = [t for t in turnos if t["bien"]]
    mal = [t for t in turnos if not t["bien"]]
    print(f"\nLA PRIMERA TRADUCCION CON EMBEDDINGS · {len(turnos)} turnos grabados de Gemini: {len(bien)} BIEN, {len(mal)} MAL")
    print(f"  la base del voto: {len(pool)} frases de una sola parte de la plantilla, {len({c for *_, c in pool})} clases")
    print("\n1. LAS SENALES, cuanto separan MAL de BIEN. AUC 0,5 es tirar una moneda; 1 es perfecto.")
    for s in ("corte", "parafrasis", "acto_mal"):
        print(f"  {s:11} AUC {_auc([t[s] for t in mal], [t[s] for t in bien]):.2f}")
        if s == "acto_mal":
            m, b = sum(t[s] > 0 for t in mal), sum(t[s] > 0 for t in bien)
            print(f"              el voto discrepa con Gemini en {m} de {len(mal)} MAL y en {b} de {len(bien)} BIEN")
            continue
        for tope in (0.05, 0.10, 0.25):
            u = sorted(t[s] for t in bien)[int(len(bien) * (1 - tope))]
            print(f"              con falsa alarma en {int(tope * 100):2}% de las BIEN, marca "
                  f"{sum(t[s] > u for t in mal)} de {len(mal)} MAL, umbral {u:.3f}")
    lm, lb = sum(t["llm_marca"] for t in mal), sum(t["llm_marca"] for t in bien)
    print(f"  el verificador con modelo, para comparar: marca {lm} de {len(mal)} MAL y {lb} de {len(bien)} BIEN")

    print(f"\n2. EL ACTO DE CADA PARTE, sobre {acto_n} partes alineadas a una cosa de la vara")
    print(f"  Gemini acierta {acto_g} · el voto de los {K_VOTO} parecidos acierta {acto_k}")
    print(f"  los dos bien {conf[(True, True)]} · solo Gemini {conf[(True, False)]} · solo el voto "
          f"{conf[(False, True)]} · ninguno {conf[(False, False)]}")

    print("\n3. LO QUE FALLA EN LOS MAL, por dato de la vara")
    por = collections.Counter(d for f in ("48", "58", "nuevas") for cid, d, _ in V.FALLAS[f])
    print("  " + " · ".join(f"{d} {n}" for d, n in por.most_common()))
    corte_mal = [t for t in mal if any(d == "la cosa" for f in ("48", "58", "nuevas") for c, d, _ in V.FALLAS[f]
                                       if c == t["id"])]
    print(f"  turnos con una cosa que falta: {len(corte_mal)} de {len(mal)}; la senal del corte separa esos con AUC "
          f"{_auc([t['corte'] for t in corte_mal], [t['corte'] for t in bien]):.2f}")
    print(f"  frases por turno, cortadas por el codigo: {np.mean([len(t['frases']) for t in turnos]):.1f}; partes "
          f"de Gemini: {np.mean([len(t['partes']) for t in turnos]):.1f}")

    if "--ver" in ARGS:
        print("\nDONDE EL VOTO Y GEMINI NO COINCIDEN: gemini bien, voto bien, turno, palabras, gemini, voto, vara")
        for d in discrepa:
            print(f"  {'G' if d[0] else '-'}{'V' if d[1] else '-'} {d[2]:9} {d[3][:60]!r:62} {str(d[4]):9} {str(d[5]):9} {d[6]}")
        print("\nLAS COSAS DE LA VARA QUE NO ENCONTRO NINGUNA PARTE")
        for f in ("48", "58", "nuevas"):
            for cid, d, que in V.FALLAS[f]:
                if d == "la cosa":
                    t = next(x for x in turnos if x["id"] == cid)
                    print(f"  {cid:9} falta {que:28} partes: {[p.get('que') for p in t['partes']]} · {t['msg'][:70]}")
        print("\nLOS MAL CON MAS ALARMA DE CORTE")
        for t in sorted(mal, key=lambda t: -t["corte"])[:15]:
            print(f"  {t['corte']:.3f} {t['id']:9} {t['msg'][:100]}")


if __name__ == "__main__":
    main()
