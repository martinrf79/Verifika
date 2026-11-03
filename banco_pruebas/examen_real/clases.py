"""LAS CUATRO CLASES DEL PEDIDO EN EL EXAMEN REAL — destino, medio, omision y duplicado (2-nov-2026, FICHA 86 paso 6).

Una sola corrida del examen no se califica a mano entera: se cuentan solo las cuatro clases que el pedido por comandos
tiene que bajar, sobre lo que leyo el cliente, con la misma regla de los dos lados. Decision de Martin, 2-nov.

  destino     un "Envio a X" de la cuenta, con X que el cliente no dijo en la charla hasta ese turno.
  medio       un renglon del reparto o del cobro con un medio que el cliente no dijo; "a definir" no cuenta.
  omision     un rubro que el cliente nombro en ese mensaje y que la cuenta de ese turno no trae, o trae menos de los
              que dijo con un numero delante: "dos memorias" y la cuenta con una.
  duplicado   el mismo producto dos veces al mismo destino en la cuenta de un turno.

No llama al modelo. Lo que marca es candidato: se lee el caso antes de creerlo.

    python3 banco_pruebas/examen_real/clases.py corrida_1nov.jsonl corrida_<nueva>.jsonl [--ver]
"""
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(AQUI)))
# "verificador": lo que marco el verificador en la respuesta, que vuelve al modelo; con el codigo de hoy sobre una
# corrida grabada, `examen.py --codigo`, es lo que el verificador caza de lo que escribio el modelo ese dia.
CLASES = ("destino", "medio", "omision", "duplicado", "verificador")
RESPUESTA_CORTA = 4  # la misma de agente.py: la respuesta corta elige lo que le ofrecio el bot
CUANTOS = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
           "nueve": 9, "diez": 10}


def _bloques(texto: str) -> list:
    """[(destino, [nombre por renglon])] de cada cuenta del texto."""
    out = []
    for parte in re.split(r"(?m)^Presupuesto:\s*$", texto)[1:]:
        nombres = [(int(c), n) for c, n in re.findall(r"(?m)^- (\d+)x (.+?): \$", parte)]
        d = re.search(r"(?m)^Envio a (.+?):", parte)
        out.append((d.group(1).strip() if d else "", nombres))
    return out


def marcas(charla: dict, tienda_id: str) -> list:
    """[(turno, clase, detalle)] de una charla."""
    from app.core.flujo import catalogo as K
    from app.core.flujo import marcador as MK
    def ws(x) -> list:
        return re.findall(r"[a-z0-9]+", K.n(x))
    out, dicho, antes = [], set(), ""
    for i, t in enumerate(charla["turnos"], 1):
        msg = ws(t["cliente"])
        dicho |= set(msg) | (set(ws(antes)) if len(t["cliente"].split()) <= RESPUESTA_CORTA else set())
        bot, bloques = t["bot"], _bloques(t["bot"])
        for d, _ in bloques:
            if d and not set(ws(d)) <= dicho:
                out.append((i, "destino", d))
        for m in re.findall(r"(?m)^- ([a-zA-Z ]+?) \(\d+%\)", bot) + re.findall(r"Para pagar (?:por|con) ([a-zA-Z ]+?):", bot):
            if K.n(m) != "a definir" and not any(w[:4] == ws(m)[0][:4] for w in dicho):
                out.append((i, "medio", m))
        if bloques:
            pide = {}
            for w, r in MK._rubros(msg, tienda_id):
                j = msg.index(w.split()[0])
                c = msg[j - 1] if j else ""
                # La mayor cantidad dicha: "dos auriculares" y despues "un auricular a Cordoba" son dos.
                pide[r] = max(pide.get(r, 0), int(c) if c.isdigit() else CUANTOS.get(c, 0))
            hay = {}
            for _, nombres in bloques:
                for c, n in nombres:
                    idt = K.identificar(n, "", tienda_id)
                    if idt["veredicto"] == "exists":
                        r = idt["producto"].get("categoria")
                        hay[r] = hay.get(r, 0) + c
            out += [(i, "omision", f"{r}: pidio {c or 'alguno'}, van {hay.get(r, 0)}") for r, c in sorted(pide.items())
                    if not hay.get(r) or hay[r] < c]
            vistos = set()
            for d, nombres in bloques:
                for _, n in nombres:
                    if (K.n(n), K.n(d)) in vistos:
                        out.append((i, "duplicado", f"{n} a {d or 'sin destino'}"))
                    vistos.add((K.n(n), K.n(d)))
        antes = bot
    return out


def contar(archivo: str, tienda_id: str) -> dict:
    ruta = archivo if os.path.isabs(archivo) else os.path.join(AQUI, archivo)
    charlas = [json.loads(x) for x in open(ruta, encoding="utf-8")]
    return {"charlas": len(charlas), "turnos": sum(len(c["turnos"]) for c in charlas),
            "marcas": {c["id"]: marcas(c, tienda_id) + [(i, "verificador", str(h)[:160]) for i, t in
                                                         enumerate(c["turnos"], 1) for h in t.get("hallazgos") or []]
                       for c in charlas}}


if __name__ == "__main__":
    from banco_pruebas import clon_produccion as C
    C.instalar()
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    res = {f: contar(f, C.TIENDA) for f in a}
    comunes = set.intersection(*(set(r["marcas"]) for r in res.values()))
    for f, r in res.items():
        cuenta = {k: sum(1 for cid in comunes for m in r["marcas"][cid] if m[1] == k) for k in CLASES}
        print(f"{f}: {len(comunes)} charlas en comun, {r['turnos']} turnos · " +
              " · ".join(f"{k} {v}" for k, v in cuenta.items()))
        if "--ver" in sys.argv:
            for cid in sorted(comunes):
                for m in r["marcas"][cid]:
                    print(f"   {cid} t{m[0]} {m[1]}: {m[2]}")
