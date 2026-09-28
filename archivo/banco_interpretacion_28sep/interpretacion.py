"""
¿ENTENDIO EL MENSAJE? — la interpretacion, medida sola (Martin, 7-ago-2026).

LA PREGUNTA DE MARTIN, textual: "me interesa el resultado de lo que se decia que
funcionaba bien, que era la interpretacion, porque a lo mejor no estamos lejos
de algo que se diferencie".

Es la pregunta correcta y nunca se habia medido. Todo lo que se mide en este
repo juzga la RESPUESTA: el bloque, la cuenta, las frases. Si el bot contesta
mal, no hay forma de saber si fue porque **no entendio** el mensaje o porque
entendio bien y despues se perdio. Son dos problemas distintos con dos
soluciones distintas, y sin separarlos se arregla a ciegas.

QUE MIDE. Solo lo que el modelo PIDIO: sus llamadas a herramientas en el turno.
Hasta el 26-sep era la declaracion de `registrar_pedido`; desde que el agente
reemplazo al interprete, lo que entendio son las herramientas que llamo y con
que. Se espia `agente.turno`, las llamadas pasan a la forma del pedido con
`pedido_agente.pedido`, y se compara contra la verdad de la pregunta, campo
por campo, sin mirar la respuesta. La unica excepcion es la contradiccion del
teclado: el agente no tiene donde declararla, asi que cuenta si la respuesta
la nombra.

Y EN LA MISMA CORRIDA SE CRUZA CON LA RESPUESTA. Es lo que convierte esto en una
decision y no en un dato suelto:

  entiende bien + contesta bien  ->  el camino esta sano, es cuestion de pulir.
  entiende bien + contesta mal   ->  el problema esta DESPUES de entender: el
                                     bucle, las herramientas, la redaccion.
  entiende mal  + contesta mal   ->  el problema es la INTERPRETACION, y ahi si
                                     tiene sentido volver al interprete tipado.

Si sale la tercera, la vuelta al interprete deja de ser una intuicion y pasa a
ser lo que dice el numero. Si sale la segunda, volver al interprete no arregla
nada y hay que mirar a otro lado.

USO:
    python3 banco_pruebas/interpretacion.py --repeticiones 3
"""
import json
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas.objetivo import (VARIANTES, _cuenta_del_texto,  # noqa: E402
                                    _n, medir_comunicacion, medir_estado, nota)

TIENDA = "verifika_prod"


# ── LA VERDAD DE LA PREGUNTA, campo por campo ───────────────────────────────
# Los diez hechos que un vendedor humano sacaria del mensaje. No es opinion:
# cada uno esta escrito literalmente en la pregunta de Martin.
def medir_declaracion(d: dict, texto: str = "") -> list:
    """(nombre, ok, detalle) por cada cosa que el modelo tenia que entender.
    `d` es el pedido de `pedido_agente.pedido`."""
    from banco_pruebas.pedido_agente import categoria_de
    d = d or {}
    cats = [_n(q.get("categoria")) for q in (d.get("consultas") or [])]
    items = list((d.get("cuenta") or {}).get("items") or [])
    cats += [_n(categoria_de(i.get("id"))) for i in items]
    txt = " ".join(cats)
    restr = _n(json.dumps([q.get("condiciones") for q in (d.get("consultas") or [])],
                          ensure_ascii=False))
    contra = _n(texto)
    dest_txt = " ".join(_n(e.get("destino")) for e in (d.get("envios") or []))
    cants = {}
    for i in items:
        for rubro in ("auricular", "mouse", "memoria"):
            if rubro in _n(categoria_de(i.get("id"))):
                cants[rubro] = cants.get(rubro, 0) + int(i.get("cantidad") or 1)
    return [
        ("rubro_auriculares", "auricular" in txt, "declaro auriculares"),
        ("rubro_mouse", "mouse" in txt, "declaro mouse"),
        ("rubro_memorias", "memoria" in txt, "declaro memorias"),
        ("cantidades_de_a_dos",
         all(cants.get(r) == 2 for r in ("auricular", "mouse", "memoria")),
         f"dos de cada uno; declaro {cants or 'nada'}"),
        ("pide_precio", bool(d.get("pedir_total")), "el cliente pidio precio: llamo a cuenta"),
        ("destino_cordoba", "cordoba" in dest_txt, "Cordoba capital"),
        ("destino_concordia", "concordia" in dest_txt, "Concordia"),
        ("destino_posadas", "posadas" in dest_txt, "Posadas"),
        ("criterio_de_origen", any(x in restr for x in ("chin", "origen", "pais")),
         "las menos partes chinas posibles"),
        # Se acepta por el campo TIPADO -el camino bueno- o por la frase en
        # restricciones, que es la red. Lo que se mide es si ENTENDIO el
        # reparto, no por que puerta lo declaro.
        ("reparto_de_pago", bool(d.get("reparto_pago")), "el reparto 70/30, en la cuenta"),
        ("contradiccion_del_teclado", "teclado" in contra,
         "el teclado nombrado en el envio y no en el pedido: la respuesta lo nombra"),
    ]


def correr(repeticiones: int = 3) -> dict:
    import asyncio
    import os
    # LA CLAVE LA ELIGE UN SOLO LUGAR: `clon_produccion.preparar_entorno`,
    # que desde el 4-ago tiene el default en la GRATIS y pide
    # BANCO_CLAVE_PAGA=true para gastar. Aca habia dos lineas que la
    # pisaban con la paga ANTES de que esa guarda corriera, asi que la
    # guarda veia la paga puesta, decidia que "no hay clave gratis
    # distinta" y la dejaba. La regla existia y cuatro scripts la
    # esquivaban: la misma falla que este repo ya pago dos veces, una
    # regla escrita en dos lados que quedaron distintas.
    from banco_pruebas import clon_produccion as clon
    from banco_pruebas.pedido_agente import espiar, pedido
    clon.instalar()

    filas = []
    for nombre, msg in VARIANTES.items():
        corridas = []
        for i in range(max(1, repeticiones)):
            usuario = f"interp_{nombre}_{i}"
            clon.reiniciar_cliente(usuario)
            with espiar() as llamadas:
                partes = asyncio.run(clon.turno(usuario, msg))
            texto = "\n".join(partes)
            declarado = [pedido(llamadas)]
            dec = medir_declaracion(declarado[0], texto)
            n_dec = round(100 * sum(1 for _, ok, _ in dec if ok)
                          / max(1, len(dec)))
            n_res = nota(medir_estado(texto, _cuenta_del_texto(texto)),
                         medir_comunicacion(texto, msg))["nota"]
            corridas.append({"entiende": n_dec, "contesta": n_res,
                             "fallas": [k for k, ok, _ in dec if not ok],
                             "declaro": declarado[0]})
        filas.append({"variante": nombre, "corridas": corridas})
    return {"filas": filas, "repeticiones": repeticiones}


def main(argv: list) -> int:
    reps = 3
    if "--repeticiones" in argv:
        reps = int(argv[argv.index("--repeticiones") + 1])
    res = correr(reps)
    todas = [c for f in res["filas"] for c in f["corridas"]]
    print("=" * 78)
    print(f"LA INTERPRETACION, SOLA — {len(res['filas'])} redacciones x {reps}")
    print("=" * 78)
    print("| redacción | ENTIENDE | CONTESTA |")
    print("|---|---|---|")
    for f in res["filas"]:
        e = round(sum(c["entiende"] for c in f["corridas"]) / len(f["corridas"]))
        r = round(sum(c["contesta"] for c in f["corridas"]) / len(f["corridas"]))
        print(f"| {f['variante']} | **{e}** | {r} |")
    e_prom = round(sum(c["entiende"] for c in todas) / max(1, len(todas)))
    r_prom = round(sum(c["contesta"] for c in todas) / max(1, len(todas)))
    print(f"\nENTIENDE {e_prom}/100   CONTESTA {r_prom}/100")

    # EL CRUCE, que es lo que decide adonde trabajar.
    bien_e = [c for c in todas if c["entiende"] >= 90]
    print(f"\nEL CRUCE, sobre {len(todas)} corridas:")
    print(f"  entendio bien (>=90): {len(bien_e)}")
    if bien_e:
        print(f"     y de esas, contesto bien (>=80): "
              f"{sum(1 for c in bien_e if c['contesta'] >= 80)}")
        print(f"     nota media de respuesta cuando entendio bien: "
              f"{round(sum(c['contesta'] for c in bien_e) / len(bien_e))}")
    mal_e = [c for c in todas if c["entiende"] < 90]
    if mal_e:
        print(f"  entendio mal  (<90): {len(mal_e)}, "
              f"nota media de respuesta {round(sum(c['contesta'] for c in mal_e) / len(mal_e))}")

    from collections import Counter
    cuenta = Counter(x for c in todas for x in c["fallas"])
    print("\nQUE ES LO QUE NO ENTIENDE, por frecuencia:")
    for k, v in cuenta.most_common():
        print(f"  {v:3d}/{len(todas)}  {k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
