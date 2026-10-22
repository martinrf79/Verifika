"""LOS SIETE CASOS DE PRODUCCION, charla entera por el camino vivo (22-oct-2026).

Sin parches de prueba: el clon de produccion, el modelo real en cada turno y las casillas que aprobo Martin en
`jev/casos_produccion.json`. Una repeticion: con temperatura 0 el modelo contesta igual, y lo ya preguntado sale de
`libro_paga.recordar` sin gasto. Medido el 22-oct: el interprete de la agenda daba 5 de 7; la ficha nativa, 6 de 7.
    python3 banco_pruebas/pedido_documento/prod7_ficha.py [--ver]      con la gratis; la paga, con la marca de Martin
"""
import asyncio
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, REPO)
os.chdir(REPO)
if os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
    os.environ["BANCO_CLAVE_PAGA"] = "true"

from banco_pruebas import clon_produccion as C  # noqa: E402
C.preparar_entorno()
C.instalar()
from banco_pruebas.sonda_charlas import nota_casilla  # noqa: E402
from app.core.flujo import ficha  # noqa: E402

CASOS = json.load(open(os.path.join(REPO, "banco_pruebas", "jev", "casos_produccion.json"), encoding="utf-8"))["charlas"]


def main() -> None:
    a = sys.argv[1:]
    config = "vivo"
    if "--ver" in a:
        a_agenda = ficha.a_agenda

        def _ver(f, estado, tid, mensaje=""):
            ag = a_agenda(f, estado, tid, mensaje)
            print("    FICHA:", json.dumps({k: f.get(k) for k in ("pedido", "pago", "consultas", "dudas")},
                                           ensure_ascii=False)[:1500])
            print("    AGENDA:", json.dumps(ag["preguntas"], ensure_ascii=False)[:1200])
            return ag
        ficha.a_agenda = _ver
    bien, salida = 0, []
    for c in CASOS:
        uid = f"p7f_{c['id']}_{config}"
        C.reiniciar_cliente(uid)
        resps, malas = [], []
        for t in c["turnos"]:
            txt = "\n".join(asyncio.run(C.turno(uid, t["texto"])))
            resps.append(txt)
            m = [k["n"] for k in t["casillas"] if nota_casilla(k, [], txt, resps) is not True]
            malas += m
            if "--ver" in a:
                print(f"--- {c['id']} CLIENTE: {t['texto'][:160]}\n{txt}\n    MAL: {m}")
        bien += not malas
        salida.append({"id": c["id"], "config": config, "bien": not malas, "malas": malas, "respuestas": resps})
        print(f"{c['id']} {config}: {'bien' if not malas else 'MAL ' + '; '.join(malas)}", flush=True)
    print(f"\n{config}: {bien} de {len(CASOS)} charlas bien")
    with open(os.path.join(AQUI, f"prod7_{config}.jsonl"), "w", encoding="utf-8") as f:
        f.writelines(json.dumps(s, ensure_ascii=False) + "\n" for s in salida)


if __name__ == "__main__":
    main()
