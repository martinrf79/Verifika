"""LA SUFICIENCIA — si lo que recibe el modelo alcanza para escribir la agenda correcta, sin llamar al modelo (20-oct-2026).

Antes de gastar una corrida con el modelo se prueba gratis que la informacion esta: cada dato de la agenda escrita a
mano en `agendas58.py` tiene que poder salir de lo que el modelo ve en ese turno —la libreta, la tabla del marcador o
las palabras del cliente—. Si un dato no esta, el modelo lo tendria que adivinar: la falla es del codigo, y se arregla
en el marcador o en la libreta, no en la consigna.

Las libretas salen del estado real de cada turno: las charlas corren por el clon de produccion con las agendas a mano,
y antes de cada turno se toma el estado tal como lo veria el interprete.

  python3 -m banco_pruebas.suficiencia            lo que falta, turno por turno
  python3 -m banco_pruebas.suficiencia --ver C49  con la libreta y la tabla de cada turno
"""
import asyncio
import copy
import sys

from banco_pruebas import cableado58 as CB
from banco_pruebas import clon_produccion as C


def vistas() -> list:
    """[(charla, turno, mensaje, estado, historial)] de las 58 y las K, antes de cada turno."""
    interprete = CB.instalar()
    from banco_pruebas.agendas58 import AGENDAS as T, EXPLICAR
    out = []
    for charla in CB.charlas():
        uid = f"suficiencia_{charla['id']}"
        C.reiniciar_cliente(uid)
        cola = list(T[charla["id"]])

        async def _interpretar(mensaje, historial, estado, *a, _c=charla["id"], _cola=cola, **k):
            out.append((_c, len([x for x in out if x[0] == _c]), mensaje, copy.deepcopy(estado), list(historial)))
            return _cola.pop(0) if _cola else {}

        async def _explicar(pregunta, *a, **k):
            return EXPLICAR.get(pregunta, "")
        interprete.interpretar, interprete.explicar = _interpretar, _explicar
        for t in charla["turnos"]:
            asyncio.run(C.turno(uid, t["texto"]))
    return out


def faltas(agenda: dict, mensaje: str, estado: dict, historial: list, tienda_id: str) -> list:
    """Cada dato de la agenda que no sale de lo que ve el modelo, con su motivo."""
    from app.core.flujo import agenda as A, catalogo as K, interprete as I, marcador
    libreta = K.n(I.libreta(estado, historial, tienda_id))
    tabla = K.n(marcador.tabla(mensaje, tienda_id))
    dicho = K.n(mensaje)
    nums = I.numeros(estado)
    out = []

    def producto(nombre, n):
        if isinstance(nombre, list):
            return [producto(x, n) for x in nombre]
        nombre = str(nombre)
        if nombre in nums or K.n(nombre) in ("los otros",):
            return
        if K.solo_rubro(nombre, tienda_id):
            return rubro(K.solo_rubro(nombre, tienda_id), n)
        idt = K.identificar(nombre, "", tienda_id)
        if idt["veredicto"] != "exists":
            return out.append((n, "producto", f"{nombre}: no es un producto del catalogo"))
        if K.n(marcador._modelo(idt["producto"])) not in tabla:
            out.append((n, "producto", f"{nombre}: el marcador no lo reconocio"))

    def rubro(r, n):
        r = K.rubro(str(r), tienda_id) or str(r)
        if f"el rubro {K.n(r)}" not in tabla and K.n(r) not in libreta:
            out.append((n, "rubro", f"{r}: ni en la tabla ni en la libreta"))

    for p in A.preguntas(agenda):
        n, acc = p["n"], p["accion"]
        out += [(n, "referencia", f"{r} no esta en la libreta") for r in A.referencias(p) if r not in nums]
        if acc in ("producto", "compatibilidad"):
            producto(p.get("producto"), n)
        if acc == "buscar":
            rubro(p["rubro"], n)
        for x in p.get("agrega") or []:
            producto(x["producto"], n)
            d = K.n(x.get("destino"))
            if d and not all(w in dicho or w in libreta for w in d.split()):
                out.append((n, "destino", f"{x['destino']}: ni en el mensaje ni en la libreta"))
        if acc == "envio" and not all(w in dicho or w in libreta for w in K.n(p["destino"]).split()):
            out.append((n, "destino", f"{p['destino']}: ni en el mensaje ni en la libreta"))
        if acc == "politica" and f" {K.n(p['tema'])}" not in tabla:
            out.append((n, "tema", f"{p['tema']}: el marcador no lo reconocio"))
        if p.get("si_pasa"):
            producto(p["si_pasa"], n)
        reparto = p.get("reparto") or []
        if len(reparto) == 2 and f"{reparto[0]['porcentaje']} y {reparto[1]['porcentaje']} por ciento" not in tabla \
                and f"paga: {K.n(reparto[0]['medio'])} {reparto[0]['porcentaje']}%" not in libreta:
            out.append((n, "reparto", "los porcentajes no estan en la tabla"))
        if p.get("tope") and f"{int(p['tope']):,} pesos".replace(",", ".") not in tabla:
            out.append((n, "tope", f"{p['tope']}: no esta en la tabla"))
    return out


def medir(ids=None) -> list:
    """[(charla, turno, n, clase, detalle)] de todo lo que falta."""
    from banco_pruebas.agendas58 import AGENDAS
    out = []
    for cid, t, mensaje, estado, historial in vistas():
        if ids and cid not in ids:
            continue
        out += [(cid, t + 1, *f) for f in faltas(AGENDAS[cid][t], mensaje, estado, historial, C.TIENDA)]
    return out


def main():
    ids = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--ver" in sys.argv:
        from app.core.flujo import interprete as I, marcador
        for cid, t, mensaje, estado, historial in vistas():
            if not ids or cid in ids:
                print(f"== {cid} T{t + 1}\n{I.libreta(estado, historial, C.TIENDA)}\n"
                      f"{marcador.tabla(mensaje, C.TIENDA)}\nULTIMO MENSAJE: {mensaje}\n")
        return
    fs = medir(ids)
    for f in fs:
        print(f"{f[0]} T{f[1]} pregunta {f[2]}: {f[3]}, {f[4]}")
    clases = {}
    for f in fs:
        clases[f[3]] = clases.get(f[3], 0) + 1
    print(f"\nSUFICIENCIA: {len(fs)} datos que el modelo tendria que adivinar"
          + (": " + ", ".join(f"{k} {v}" for k, v in clases.items()) if clases else ""))


if __name__ == "__main__":
    main()
