"""
EL CENSO DEL PUNTO DE OFERTA — en cuantos turnos el bot tenia algo que
proponer, y en cuantos lo propuso.

POR QUE EXISTE. La FICHA 15 abrio el punto sintetico `oferta` y midio su censo
a mano, pegando numeros en el mensaje del commit. Un numero que vive en un
commit no se puede volver a correr: cuando se regraban los casetes hay que
compararlo contra algo, y ese algo tiene que ser un instrumento, no un texto.

DE DONDE SALE. Del mismo evento `indice_turno` que el bot ya loguea en cada
turno, leido con `banco_pruebas/observador.py` —la misma ventana que en
produccion es Cloud Logging—. `cobertura()` corre varias veces por turno
(las dos llamadas de `hub_venta` mas la puerta de salida); vale la ULTIMA,
que es la que mira el texto final, igual que hace la vara con `hub_venta_ok`.

LAS TRES CASILLAS, y son las unicas en que la oferta puede terminar:

  OFRECIDO        el turno propuso el paso siguiente sobre ese producto.
  NO_CORRESPONDE  habia motivo tipado para no proponerlo: el cliente ya lo
                  rechazo, el pedido ya lo tiene, o el turno esta cerrando.
  SIN_ESTADO      el punto se abrio y el turno se fue sin ofrecer nada. Es
                  la casilla vacia, y es la que la sonda viene a mirar.

Los turnos donde el punto NI SE ABRE no entran en el censo: no hubo producto
certificado, o la herramienta salio ambigua y la oferta cede a proposito.

LA SONDA DEL 25-AGO SE MIDE CON `--sonda`, y es la otra grabacion de los MISMOS
quince guiones: `banco_pruebas/casetes_sonda_25ago/`. La bateria no la lee a
proposito —el corpus es `casetes/` y no se toca— pero es prosa viva del modelo,
distinta de la del corpus, y sirve para verificar GRATIS un arreglo del detector
contra texto que ninguna sesion escribio para que pasara. De ahi salieron los
defectos de la FICHA 16.

USO
    python3 banco_pruebas/censo_oferta.py             # el censo entero
    python3 banco_pruebas/censo_oferta.py --sonda     # sobre la sonda del 25-ago
    python3 banco_pruebas/censo_oferta.py --detalle   # turno por turno
    python3 banco_pruebas/censo_oferta.py 62 77       # solo esas charlas
    python3 banco_pruebas/censo_oferta.py --ofertas   # el texto ENTERO de cada
                                                      # turno que ofrecio algo
"""
import asyncio
import json
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas import vara_de_venta as vara  # noqa: E402
from banco_pruebas import clon_produccion as clon, observador  # noqa: E402
from banco_pruebas.casete import Casete, reproducir  # noqa: E402
from banco_pruebas.puntaje import leer_guion  # noqa: E402

CASILLAS = ("OFRECIDO", "NO_CORRESPONDE", "SIN_ESTADO")

SONDA = Path(__file__).resolve().parent / "casetes_sonda_25ago"


def casetes_de_la_sonda() -> list:
    """Los quince casetes de la sonda del 25-ago, en orden."""
    return sorted(p for p in SONDA.glob("*.json") if not p.name.startswith("_"))


def _estado_de_la_oferta(eventos: list) -> str | None:
    """Como termino la oferta en este turno, o None si el punto no se abrio.

    Se mira el ULTIMO `indice_turno` del turno porque `cobertura()` corre mas
    de una vez y solo la ultima vio el texto que el cliente lee."""
    indices = [e for e in eventos if e.get("event") == "indice_turno"]
    if not indices:
        return None
    for marca in (indices[-1].get("estados") or []):
        if str(marca).startswith("oferta:"):
            return str(marca).split("=", 1)[1]
    return None


def _producto_ofrecido(eventos: list) -> str:
    """QUE producto tenia el bot para proponer en este turno.

    Sale del PRIMER `indice_turno`, no del ultimo: ahi la oferta todavia no se
    escribio, asi que el punto figura en `faltan` con su texto entero
    —"proponerle el paso siguiente sobre X"—. En el ultimo, si el turno ofrecio,
    el punto ya esta atendido y no figura."""
    for e in eventos:
        if e.get("event") != "indice_turno":
            continue
        for f in (e.get("faltan") or []):
            if str(f).startswith("proponerle el paso siguiente sobre "):
                return str(f).replace("proponerle el paso siguiente sobre ", "")
    return ""


def correr_charla(path: Path) -> dict:
    datos = json.loads(Path(path).read_text(encoding="utf-8"))
    casete = Casete(Path(path).stem, datos.get("turnos") or [])
    guion = Path(path).resolve().parent.parent / "guiones" / f"{Path(path).stem}.txt"
    turnos = (leer_guion(guion.read_text(encoding="utf-8")) if guion.exists()
              else [{"mensaje": t.get("mensaje", "")} for t in casete.turnos])

    user = f"censo_oferta_{Path(path).stem}"
    clon.reiniciar_cliente(user)
    filas: list = []

    async def _charla():
        for t in turnos:
            casete.abrir_turno(t["mensaje"])
            with observador.turno() as obs:
                partes = await clon.turno(user, t["mensaje"])
            filas.append({"mensaje": (t["mensaje"] or "")[:60],
                          "estado": _estado_de_la_oferta(obs.eventos),
                          "producto": _producto_ofrecido(obs.eventos),
                          "texto": "\n".join(partes)})

    with reproducir(casete):
        asyncio.run(_charla())
    return {"nombre": Path(path).stem, "turnos": filas}


def medir(paths: list | None = None) -> dict:
    with vara._escuchando():
        charlas = [correr_charla(p) for p in (paths or vara._casetes())]
    filas = [f for c in charlas for f in c["turnos"]]
    abren = [f for f in filas if f["estado"] is not None]
    censo = {k: sum(1 for f in abren if (f["estado"] or "SIN_ESTADO") == k)
             for k in CASILLAS}
    return {"charlas": len(charlas), "turnos": len(filas),
            "abren": len(abren), **censo, "_charlas": charlas}


def _main() -> int:
    pedidos = [a for a in sys.argv[1:] if not a.startswith("--")]
    fuente = casetes_de_la_sonda() if "--sonda" in sys.argv else vara._casetes()
    paths = ([p for p in fuente
              if any(p.stem.startswith(x) for x in pedidos)]
             if pedidos else fuente)
    res = medir(paths)
    if "--detalle" in sys.argv:
        for c in res["_charlas"]:
            print(f"\n{c['nombre']}")
            for i, f in enumerate(c["turnos"], 1):
                estado = f["estado"]
                marca = "no abre" if estado is None else (estado or "SIN_ESTADO")
                print(f"  t{i:<2} {marca:<16s} {f['mensaje']}")
    if "--ofertas" in sys.argv:
        # EL TEXTO ENTERO Y SIN TOCAR. Lo unico de toda esta maquinaria que no
        # lo puede juzgar ningun test: si una oferta suena a insistir, a vender
        # lo que no se pidio o a cambiar de tema, lo dice una persona leyendo.
        # Por eso sale COMPLETO y no la oracion que a este script le parezca la
        # oferta: recortar seria decidir por el que lee.
        for c in res["_charlas"]:
            for i, f in enumerate(c["turnos"], 1):
                if f["estado"] != "OFRECIDO":
                    continue
                print(f"\n{'─' * 70}\n{c['nombre']}  turno {i}")
                print(f"CLIENTE: {f['mensaje']}")
                print(f"tenia para ofrecer: {f['producto'] or '(no figura)'}")
                print(f"BOT:\n{f['texto']}")
        print(f"\n{'─' * 70}")
    print(f"\nCENSO DEL PUNTO DE OFERTA — {res['charlas']} charlas, "
          f"{res['turnos']} turnos, el punto abre en {res['abren']}")
    for k in CASILLAS:
        print(f"  {k:16s} {res[k]:4d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
