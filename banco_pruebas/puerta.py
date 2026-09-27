"""LA PUERTA — un cambio pasa si arregla lo que buscaba y no rompe nada (27-sep-2026).

POR QUE EXISTE. Un total no dice que paso adentro: 79 de 86 puede ser lo mismo
de antes, o una charla arreglada y otra rota. Asi se armaron las cascadas: se
arreglaba una cosa, el numero parecia igual o mejor, y lo roto aparecia dias
despues en WhatsApp. La puerta compara CHARLA POR CHARLA contra la base.

COMO. Cada charla de la vara de las 58 tiene dos notas por corrida: la
RESPUESTA, lo que recibio el cliente, y la INTERPRETACION, lo que el modelo le
pidio a las herramientas. Con tres corridas de base y tres del cambio:

  firme en la base   bien en las tres corridas de base
  rompe              firme en la base y mal en dos o mas corridas del cambio
  tiembla            firme en la base y mal en una sola corrida del cambio
  arregla            mal en dos o mas de la base y bien en dos o mas del cambio

PASA si no rompe nada y, si se le dicen las charlas que buscaba arreglar con
`--busca`, las arregla todas. Tiembla se informa pero no frena: con charlas de
varios turnos hay algo de azar aun a temperatura baja, y una sola corrida no
alcanza para acusar.

LA VARA ES LA MISMA DE LOS DOS LADOS. Base y cambio se recalifican desde lo
guardado con el medidor de hoy, asi que un arreglo del medidor no se confunde
con un arreglo del bot. Y por eso el medidor no se toca mientras se trabaja una
mejora: si hace falta, se corrige aparte y la base se vuelve a calificar.

No llama al modelo.

  python3 -m banco_pruebas.puerta --base v58_clon_p --cambio v58_compra_ --busca C29,C32,C50,C55
  (las etiquetas son prefijos: v58_clon_p toma v58_clon_p1, p2 y p3)
"""
import json
import sys

from banco_pruebas import sonda_charlas as S

MAYORIA = 2


def notas(prefijo: str) -> dict:
    """{id: [(respuesta_ok, interpretacion_ok), ...]} de todas las corridas
    cuya etiqueta empieza con el prefijo."""
    from banco_pruebas.desmenuzar import CASOS
    casos = {c[0]: c for c in CASOS}
    etiquetas = sorted({json.loads(x)["etiqueta"] for x in open(S.SALIDA, encoding="utf-8")
                        if json.loads(x)["etiqueta"].startswith(prefijo)})
    out: dict = {}
    for e in etiquetas:
        for f in S.cargar(e):
            if f["id"] not in casos:
                continue
            n = S.interpretacion_de(f, casos[f["id"]])
            out.setdefault(f["id"], []).append((S.respuesta_ok(f), n["bien"] == n["piezas"]))
    return {"etiquetas": etiquetas, "notas": out}


def comparar(base: dict, cambio: dict, busca=()) -> dict:
    rompe, tiembla, arregla, sigue_mal = [], [], [], []
    for cid, nb in sorted(base["notas"].items()):
        nc = cambio["notas"].get(cid) or []
        if not nc:
            continue
        for k, eje in ((0, "respuesta"), (1, "interpretacion")):
            b_mal = sum(not x[k] for x in nb)
            c_mal = sum(not x[k] for x in nc)
            if b_mal == 0 and c_mal >= MAYORIA:
                rompe.append(f"{cid} {eje}")
            elif b_mal == 0 and c_mal:
                tiembla.append(f"{cid} {eje}")
            elif b_mal >= MAYORIA and len(nc) - c_mal >= MAYORIA:
                arregla.append(f"{cid} {eje}")
    for cid in busca:
        nc = cambio["notas"].get(cid) or []
        if not nc or sum(x[0] and x[1] for x in nc) < MAYORIA:
            sigue_mal.append(cid)
    return {"rompe": rompe, "tiembla": tiembla, "arregla": arregla, "sigue_mal": sigue_mal,
            "pasa": not rompe and not sigue_mal}


def main():
    a = sys.argv[1:]

    def opt(n, d=""):
        return a[a.index(n) + 1] if n in a else d
    base, cambio = opt("--base"), opt("--cambio")
    busca = [x for x in opt("--busca").split(",") if x]
    if not base or not cambio:
        print(__doc__)
        return 2
    from banco_pruebas.pedido_agente import preparar_sin_modelo
    preparar_sin_modelo()
    B, C = notas(base), notas(cambio)
    r = comparar(B, C, busca)
    print(f"\nPUERTA · base {', '.join(B['etiquetas'])} · cambio {', '.join(C['etiquetas'])}")
    for k in ("arregla", "rompe", "tiembla", "sigue_mal"):
        print(f"  {k:10} {len(r[k]):3}  {' '.join(r[k])}")
    print(f"\n  {'PASA' if r['pasa'] else 'NO PASA'}")
    return 0 if r["pasa"] else 1


if __name__ == "__main__":
    sys.exit(main())
