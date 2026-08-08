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

QUE MIDE. Solo la DECLARACION: lo que el modelo dice que entendio cuando llama a
`registrar_pedido`. Eso es, literalmente, el interprete de hoy -el viejo tenia
mas campos y tipados, pero cumple el mismo rol-. Se compara contra la verdad de
la pregunta, campo por campo, sin mirar una sola letra de la respuesta.

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
def medir_declaracion(d: dict) -> list:
    """(nombre, ok, detalle) por cada cosa que el modelo tenia que entender."""
    d = d or {}
    items = list(d.get("items") or [])
    txt = " ".join(_n(i.get("que")) for i in items)
    restr = " ".join(_n(r) for r in (d.get("restricciones") or []))
    contra = " ".join(_n(c) for c in (d.get("contradicciones") or []))
    dest = [_n(x) for x in (d.get("destinos") or [])]
    dest_txt = " ".join(dest + [_n(i.get("destino")) for i in items])
    cants = {}
    for i in items:
        for rubro in ("auricular", "mouse", "memoria"):
            if rubro in _n(i.get("que")):
                cants[rubro] = cants.get(rubro, 0) + int(i.get("cantidad") or 1)
    return [
        ("rubro_auriculares", "auricular" in txt, "declaro auriculares"),
        ("rubro_mouse", "mouse" in txt, "declaro mouse"),
        ("rubro_memorias", "memoria" in txt, "declaro memorias"),
        ("cantidades_de_a_dos",
         all(cants.get(r) == 2 for r in ("auricular", "mouse", "memoria")),
         f"dos de cada uno; declaro {cants or 'nada'}"),
        ("pide_precio", bool(d.get("pide_precio")), "el cliente pidio precio"),
        ("destino_cordoba", "cordoba" in dest_txt, "Cordoba capital"),
        ("destino_concordia", "concordia" in dest_txt, "Concordia"),
        ("destino_posadas", "posadas" in dest_txt, "Posadas"),
        ("criterio_de_origen", "chin" in restr or "chin" in _n(str(d)),
         "las menos partes chinas posibles"),
        # Se acepta por el campo TIPADO -el camino bueno- o por la frase en
        # restricciones, que es la red. Lo que se mide es si ENTENDIO el
        # reparto, no por que puerta lo declaro.
        ("reparto_de_pago",
         bool(d.get("reparto_pago"))
         or any(x in restr for x in ("70", "setenta", "30", "treinta")),
         "el reparto 70/30"),
        ("contradiccion_del_teclado", "teclado" in contra,
         "el teclado nombrado en el envio y no en el pedido"),
    ]


def correr(repeticiones: int = 3) -> dict:
    import asyncio
    import os
    if os.environ.get("GEMINI_API_KEY_PROD"):
        os.environ["GEMINI_API_KEY"] = os.environ["GEMINI_API_KEY_PROD"]
    from banco_pruebas import clon_produccion as clon
    from app.core import hub_venta as HV
    clon.instalar()

    # Se captura la PRIMERA declaracion del turno, que es la interpretacion del
    # mensaje del cliente. Las de rondas siguientes son repeticiones suyas.
    declarado: list = []
    orig = HV._ejecutar_en_paralelo

    async def espia(pedidos, tienda_id, trace_id):
        for p_ in (pedidos or []):
            if isinstance(p_, dict) and p_.get("nombre") == "registrar_pedido":
                if not declarado:
                    declarado.append(dict(p_.get("args") or {}))
        return await orig(pedidos, tienda_id, trace_id)
    HV._ejecutar_en_paralelo = espia

    filas = []
    try:
        for nombre, msg in VARIANTES.items():
            corridas = []
            for i in range(max(1, repeticiones)):
                declarado.clear()
                usuario = f"interp_{nombre}_{i}"
                clon.reiniciar_cliente(usuario)
                partes = asyncio.get_event_loop().run_until_complete(
                    clon.turno(usuario, msg))
                texto = "\n".join(partes)
                dec = medir_declaracion(declarado[0] if declarado else {})
                n_dec = round(100 * sum(1 for _, ok, _ in dec if ok)
                              / max(1, len(dec)))
                n_res = nota(medir_estado(texto, _cuenta_del_texto(texto)),
                             medir_comunicacion(texto))["nota"]
                corridas.append({"entiende": n_dec, "contesta": n_res,
                                 "fallas": [k for k, ok, _ in dec if not ok],
                                 "declaro": declarado[0] if declarado else {}})
            filas.append({"variante": nombre, "corridas": corridas})
    finally:
        HV._ejecutar_en_paralelo = orig
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
