"""Los NEXOS sobre las varas del banco, charla por charla, con las casillas de siempre.

  python3 banco_pruebas/nexos/correr_nexos.py <etiqueta> <modelo[,modelo]> [ids separados por coma]

Gemini va con la gratis salvo BANCO_CLAVE_PAGA=true con la marca de Martin; DeepSeek se anota en el libro.
La salida queda en banco_pruebas/nexos/nexos_<etiqueta>.jsonl. No toca app/ ni produccion.
"""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))


def main(argv):
    sys.path.insert(0, AQUI)
    sys.path.insert(0, RAIZ)
    from banco_pruebas import clon_produccion as CP
    CP.preparar_entorno(); CP.instalar()
    from app.core.contexto_turno import set_current_tienda
    set_current_tienda(CP.TIENDA)
    from banco_pruebas import sonda_charlas as S
    import nexos as NX
    etq, modelos = argv[0], argv[1].split(",")
    ids = argv[2].split(",") if len(argv) > 2 else None
    charlas = [c for c in S.charlas("compleja") + S.charlas("guiones") + S.charlas("58") if c["id"][0] in "KGCJ"]
    vistos, cola = set(), []
    for c in charlas:
        if c["id"] in vistos or (ids and c["id"] not in ids):
            continue
        vistos.add(c["id"]); cola.append(c)
    salida = f"{AQUI}/nexos_{etq}.jsonl"
    hechas = set()
    if os.path.exists(salida):
        hechas = {(json.loads(x)["id"], json.loads(x)["modelo"]) for x in open(salida)}

    def una(t):
        c, m = t
        if (c["id"], m) in hechas:
            return
        s = NX.Sesion(); turnos, resp = [], []
        t0 = time.time()
        for tu in c["turnos"]:
            try:
                r = s.turno_de(m, tu["texto"])
            except Exception as e:  # noqa: BLE001 — una falla no tira la tanda
                r = {"lineas": "", "datos": f"ERROR {type(e).__name__}: {e}", "respuesta": "", "rondas": 0}
            resp.append(r["respuesta"])
            cas = [(k["n"], S.nota_casilla(k, [], r["respuesta"], resp)) for k in tu["casillas"]]
            turnos.append(dict(r, texto=tu["texto"], casillas=cas))
        fila = {"id": c["id"], "modelo": m, "seg": round(time.time() - t0, 1), "turnos": turnos}
        with open(salida, "a") as f:
            f.write(json.dumps(fila, ensure_ascii=False, default=str) + "\n")
        mal = [f"t{i+1}:{n}" for i, tu in enumerate(turnos) for n, ok in tu["casillas"] if ok is False]
        print(f"{'OK ' if not mal else 'MAL'} {c['id']} {m[:6]} {'; '.join(mal)[:150]}", flush=True)

    with ThreadPoolExecutor(6) as ex:
        list(ex.map(una, [(c, m) for c in cola for m in modelos]))


if __name__ == "__main__":
    main(sys.argv[1:])
