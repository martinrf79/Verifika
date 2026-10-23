"""LA IDA Y VUELTA — el codigo dice en castellano lo que entendio, y el modelo lo compara con el mensaje (23-oct-2026).

Pregunta de Martin: el modelo entiende bien y etiqueta mal en los bordes, y el codigo no puede ver una etiqueta mal
puesta porque no entiende razonamiento. ¿Lo ve el modelo si se le muestra lo entendido en castellano simple? Es la
verificacion de ida y vuelta de la formalizacion: traducir, volver a decir, comparar.

Sobre las 48 fichas que ya devolvio el modelo de produccion, `ficha_vivo.jsonl`, sin volver a pedirlas:
  1. el codigo, sin modelo, dice la ficha en castellano: el pedido entero, lo que consulta, el pago;
  2. el modelo recibe la libreta, el mensaje y eso, y contesta si coincide y que difiere;
  3. se cruza con la vara de `medir_ficha.calificar`: de las fichas mal, cuantas marca; de las bien, cuantas de mas.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> TOPE_CORRIDA=0.10 python3 banco_pruebas/pedido_documento/ida_y_vuelta.py [--ver]
"""
import asyncio
import collections
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, REPO)
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(REPO, "banco_pruebas", "pregunta_razonada"))
os.chdir(REPO)
if os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
    os.environ["BANCO_CLAVE_PAGA"] = "true"

import medir_pedido as P  # noqa: E402  — arma el entorno, el estado de cada turno y la vara
from banco_pruebas import libro_paga  # noqa: E402
from app.core.flujo import catalogo as K  # noqa: E402
from app.core.flujo import interprete  # noqa: E402
from experimento import limpio  # noqa: E402
from fichas import CHARLAS  # noqa: E402

TOPE = float(os.environ.get("TOPE_CORRIDA", "0.10"))
VACIO = ("", "sin decir", "ninguno", "ninguna", "nada", "nuevo", "null", "none")

COMPARAR = """Sos el control de calidad de una tienda online de tecnologia de Argentina. Otro programa leyo el ULTIMO
MENSAJE del cliente, con la LIBRETA de la charla, y escribio LO QUE ENTENDIO: como queda el pedido despues del mensaje,
lo que consulta y el pago. Busca solo errores de lectura de ESTE mensaje:
- algo que el cliente pidio o pregunto en este mensaje y no esta;
- algo que esta y el cliente no dijo;
- una pregunta anotada como compra, o una compra anotada como pregunta;
- una cantidad, un color, un destino o una condicion distinta de la que dijo;
- algo que el cliente dijo que depende de otra cosa, anotado sin esa condicion.

NO es error: que modelo o marca concreta se eligio, cual es mas barato, precios o datos de productos, que falte el nombre
o la localidad: todo eso lo resuelve la tienda despues. Tampoco la redaccion ni el orden.

Cada diferencia lleva entre comillas las palabras EXACTAS del ULTIMO MENSAJE que la prueban. Si no podes citar palabras
exactas del mensaje, no es una diferencia.

Contesta en JSON: {"diferencias": [{"cita": "palabras exactas del mensaje", "error": "una oracion"}]}"""


def _citada(d, msg: str) -> bool:
    """La diferencia vale si su cita esta, palabra por palabra, en el mensaje."""
    from app.core.flujo.agenda import palabras
    cita = " ".join(palabras((d or {}).get("cita") if isinstance(d, dict) else ""))
    return len(cita.split()) >= 1 and f" {cita} " in f" {' '.join(palabras(msg))} "


def _d(v) -> str:
    return "" if K.n(v) in VACIO else str(v).strip()


def _nombre(v, nums: dict) -> str:
    """Un numero de la libreta con lo que senala: "M-2" es el producto mostrado, "L-1" el renglon."""
    from app.core.flujo.ficha import _refs
    t = _d(v)
    for r in _refs(t, nums):
        x = nums[r]
        nom = K.por_id(x, P.TID).get("nombre") if isinstance(x, str) else (x.get("que") if isinstance(x, dict) else "")
        t = t.replace(r, f"{r} ({nom})" if nom else r)
    return t


def en_castellano(f: dict, nums: dict) -> str:
    """La ficha dicha simple, sin modelo: lo que el codigo va a cumplir."""
    out = []
    items = [(g, it) for g in f.get("pedido") or [] if isinstance(g, dict)
             for it in g.get("items") or [] if isinstance(it, dict)]
    if items:
        out.append("PEDIDO, como queda:")
        for g, it in items:
            que = _nombre(it.get("producto"), nums) or _d(it.get("rubro"))
            partes = [f"{it.get('cantidad') or 1} {que}"]
            if _d(it.get("color")):
                partes.append(f"en {it['color']}")
            conds = [c for c in it.get("condiciones") or [] if _d(c)]
            if conds:
                partes.append("que sea " + ", ".join(conds))
            orden = _d(it.get("orden_otro")) if K.n(it.get("orden")) == "otro" else _d(it.get("orden"))
            if orden:
                partes.append(f"el {orden}")
            partes.append(f"a {_d(g.get('destino')) or 'destino sin decir'}")
            renglon = _d(it.get("renglon"))
            out.append("- " + ", ".join(partes))
    else:
        out.append("PEDIDO: ninguno, no decidio llevar nada.")
    pref = f.get("preferencias") or {}
    pc = [c for c in pref.get("condiciones") or [] if _d(c)]
    if pc or _d(pref.get("orden")):
        out.append("Para todo el pedido: " + ", ".join(pc + ([f"el {pref['orden']}"] if _d(pref.get("orden")) else [])))
    dice = {"buscar": "quiere ver opciones de", "producto": "pregunta sobre", "comparar": "compara",
            "compatibilidad": "pregunta si anda", "envio": "pregunta el envio", "cuenta": "pide el total",
            "regla de la tienda": "pregunta la regla de la tienda sobre", "saber general": "pregunta en general"}
    cons = [c for c in f.get("consultas") or [] if isinstance(c, dict)]
    out.append("CONSULTAS:" if cons else "CONSULTAS: ninguna.")
    for c in cons:
        tipo = K.n(c.get("tipo"))
        partes = [dice.get(tipo, tipo)]
        for k in ("producto", "sobre", "rubro", "tema"):
            if _d(c.get(k)) and _nombre(c.get(k), nums) not in " ".join(partes):
                partes.append(_nombre(c.get(k), nums))
        if _d(c.get("con")):
            partes.append(f"con {c['con']}")
        if _d(c.get("lugar")):
            partes.append(f"a {c['lugar']}")
        conds = [x for x in c.get("condiciones") or [] if _d(x)]
        if conds:
            partes.append("que sea " + ", ".join(conds))
        if _d(c.get("orden")):
            partes.append(f"el {c['orden']}")
        if _d(c.get("si")):
            partes.append(f"solo si {c['si']}")
        out.append("- " + " ".join(partes))
    pago = f.get("pago") or {}
    medios = [m for m in pago.get("medios") or [] if isinstance(m, dict) and K.entero(m.get("porcentaje"))]
    if medios and not (len(medios) == 1 and not _d(medios[0].get("medio"))):
        out.append("PAGO: " + ", ".join(f"{m.get('porcentaje')}% {_d(m.get('medio')) or 'medio sin decir'}"
                                        for m in medios))
    if pago.get("tope_total"):
        out.append(f"TOPE DEL TOTAL: {pago['tope_total']} pesos")
    if f.get("son"):
        out.append(f"DICE QUE SON {f['son']} en total")
    if _d(f.get("responde")):
        out.append(f"CONTESTA la pregunta del vendedor {f['responde']}")
    return "\n".join(out)


async def comparar(msg: str, libreta: str, entendio: str) -> dict:
    crudo = await interprete._pedir([{"role": "system", "content": COMPARAR}, {"role": "user", "content":
                                     f"{libreta}\n\nULTIMO MENSAJE: {msg}\n\nLO QUE ENTENDIO:\n{entendio}"}],
                                    "ida_y_vuelta", {"type": "json_object"})
    return interprete._json(crudo)


def main() -> None:
    ver = "--ver" in sys.argv
    grabadas = {(r["charla"], r["turno"]): r["salida"] for r in
                map(json.loads, open(os.path.join(AQUI, "ficha_vivo.jsonl"), encoding="utf-8"))
                if not r.get("error") and r.get("rep", 0) == 0}
    desde = libro_paga.gastado(libro_paga._hoy())
    cruce = collections.Counter()
    for ch in CHARLAS:
        for i, tu in enumerate(ch["turnos"]):
            crudo = grabadas.get((ch["id"], i))
            if crudo is None:
                continue
            if libro_paga.gastado(libro_paga._hoy()) - desde >= TOPE:
                print(f"TOPE de la corrida: {TOPE} dolares")
                break
            vara = P.M.calificar(tu, crudo)["veredicto"]
            estado, historial = P.estado_de(tu["mem"])
            nums = interprete.numeros(estado)
            msg = limpio(tu["msg"])
            entendio = en_castellano(interprete._json(crudo), nums)
            r = asyncio.run(comparar(msg, interprete.libreta(estado, historial, P.TID), entendio))
            difs = [d for d in r.get("diferencias") or [] if _citada(d, msg)]
            r["diferencias"] = [f'"{d.get("cita")}" {d.get("error")}' for d in difs]
            marca = bool(difs)
            bien = vara == "BIEN"
            cruce[("bien" if bien else "mal", "marca" if marca else "pasa")] += 1
            if ver and (marca or not bien):
                print(f"--- {ch['id']} t{i} vara {vara} · {'MARCA' if marca else 'pasa'}: {msg[:160]}")
                print("    " + entendio.replace("\n", "\n    "))
                for d in r.get("diferencias") or []:
                    print(f"    >> {d}")
    mal = cruce[("mal", "marca")] + cruce[("mal", "pasa")]
    bien = cruce[("bien", "marca")] + cruce[("bien", "pasa")]
    print(f"\nIDA Y VUELTA sobre {mal + bien} fichas grabadas")
    print(f"  fichas mal o con duda segun la vara: {mal}, marcadas {cruce[('mal', 'marca')]}")
    print(f"  fichas bien segun la vara: {bien}, marcadas de mas {cruce[('bien', 'marca')]}")
    print(f"  gasto: {libro_paga.gastado(libro_paga._hoy()) - desde:.3f} dolares")


if __name__ == "__main__":
    main()
