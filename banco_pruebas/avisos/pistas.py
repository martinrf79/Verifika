"""LA PRUEBA DE LAS PISTAS — el modelo, sin datos, pide al codigo lo que necesita de cada pista del mensaje; el codigo
contesta desde la fuente; recien ahi traduce. Corre por el flujo entero y se califica con las casillas de la vara.

  V1  paso 1 pistas + paso 2 con la consigna de hoy: las respuestas del codigo reemplazan a la tabla del marcador.
  V2  paso 1 pistas + paso 2 en un idioma de comandos, que el codigo pasa a la agenda.

  python3 pistas.py V1 [--formas original] [--reps 1]
"""
import asyncio
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import contexto  # noqa: E402,F401  — prepara el entorno y la puerta real

from app.core.flujo import interprete as I  # noqa: E402
from app.core.flujo import agenda as A  # noqa: E402
from app.core.flujo import catalogo as K  # noqa: E402
from app.core.flujo import marcador as M  # noqa: E402
from app.core.flujo import borrador as B  # noqa: E402

TIENDA = "verifika_prod"
TURNOS = {("C25", 0), ("C26", 0), ("C30", 0), ("C32", 0), ("C34", 1), ("C35", 1), ("C46", 1), ("C47", 1), ("C52", 1),
          ("C54", 0), ("C56", 0), ("K03", 0), ("K07", 0), ("K20", 0), ("K21", 2), ("K21", 3), ("K21", 5), ("K21", 6),
          ("K21", 0), ("K11", 5)}
USO = []  # tokens y segundos de cada llamada de esta prueba

# ══ PASO 1: las pistas ══════════════════════════════════════════════════════

PASO1 = """Sos el interprete de una tienda online de tecnologia de Argentina. Todavia no tenes ningun dato de la tienda. Antes de
traducir el mensaje del cliente, le pedis al codigo lo que necesitas saber de cada pista que trae el mensaje. El codigo
contesta desde la fuente de la tienda.

Manda TODAS las pistas, aunque creas que no hace falta, siempre de la misma forma:
- producto: cada modelo o producto que nombra —"G203", "el K120 negro", "la Kingston Fury"—.
- rubro: cada tipo de producto —"mouse", "auriculares", "una placa de video"—.
- lugar: cada ciudad, provincia o lugar.
- numero: cada monto, porcentaje o cantidad —"10 mil", "70 por ciento", "dos"—.
- referencia: cada cosa que senala de la charla —"ese", "el segundo", "lo de antes", "los mismos", "el de Rosario"—.
- condicion: cada condicion sobre lo que quiere —una marca, un color, "inalambrico", "menos de 10 mil", "que no sea X",
  "el mas potente", "que aguante tal cosa"—.
- tema: cada cosa que pregunta de las reglas de la tienda —garantia, factura, cuotas, descuentos, devoluciones—.
- pedido: si el mensaje decide, cambia, confirma, corrige o suma algo de una compra, pedi el estado del pedido.
"texto" son las palabras literales del cliente.

Devolve SOLO el JSON: {"pistas": [{"texto": "...", "tipo": "..."}]}"""


def paso1(mensaje: str, hay_charla: bool) -> list:
    msgs = [{"role": "system", "content": PASO1},
            {"role": "user", "content": f"HAY CHARLA PREVIA: {'si' if hay_charla else 'no'}\nMENSAJE: {mensaje}"}]
    crudo, uso = contexto.llamar(msgs, json_=True)
    USO.append({"paso": 1, **uso})
    return [p for p in (I._json(crudo).get("pistas") or []) if isinstance(p, dict) and p.get("texto")]


# ══ LO QUE CONTESTA EL CODIGO, desde la fuente ══════════════════════════════

def _nombre(p: dict) -> str:
    colores = [v["color"] for v in K._colores_de(p, K.productos(TIENDA)) if v.get("color") and K.con_stock(v)]
    return f"{p['nombre']}" + (f", colores con stock: {', '.join(colores)}" if colores else "")


def _producto(t: str) -> str:
    idt = K.identificar(t, "", TIENDA)
    if idt["veredicto"] == "exists":
        return f"es el producto {_nombre(idt['producto'])}. Lo toma la accion producto, o comprar si decide llevarlo."
    if idt["veredicto"] == "ambiguous":
        ops = [o.get("nombre") for o in (idt.get("opciones") or [])]
        return (f"no nombra un modelo solo: lo comparten {len(ops)} productos, como {' o '.join(ops[:4])}. "
                "Si pide uno de ellos sin decir cual, es una busqueda con esa condicion.")
    return _rubro(t)


def _rubro(t: str) -> str:
    from app.core.guia_compra import _no_vendidas
    for cosa, alt in _no_vendidas(TIENDA).items():
        if re.search(rf"\b{re.escape(K.n(cosa))}", K.n(t)):
            return "es algo que la tienda no vende" + (f"; lo mas parecido: {alt}" if alt else "") + "."
    r = K.rubro(t, TIENDA)
    return f"es el rubro {r}: lo toma buscar." if r else "no es un producto ni un rubro de la tienda."


def _lugar(t: str) -> str:
    from app.core.envio import clasificar_provincia
    ws = re.findall(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]+", t)
    hallados, usadas = [], set()
    for n in (1, 2, 3):
        for i in range(len(ws) - n + 1):
            if usadas & set(range(i, i + n)):
                continue
            f = " ".join(ws[i:i + n])
            prov = len(f) > 3 and clasificar_provincia(f)
            if prov:
                usadas |= set(range(i, i + n))
                hallados.append((f, prov))
    # Una ciudad y su provincia dichas juntas son un solo lugar: "Posadas, Misiones".
    hallados = [f"{f}, de {p}" for f, p in hallados
                if not (K.n(f) == K.n(p) and any(q == p and K.n(g) != K.n(p) for g, q in hallados))]
    if not hallados:
        return "no es una localidad a la que se envie."
    if len(hallados) == 1:
        return f"es una localidad, {hallados[0]}: un destino de envio. Lo cotiza la accion envio, un destino por pregunta."
    return ("son " + str(len(hallados)) + " localidades: " + "; ".join(hallados)
            + ". Cada una es un destino distinto: un envio por cada una.")


def _numero(t: str) -> str:
    n = K.n(t)
    for m in M._PAR.finditer(n):
        a, b = M._numero(m.group(1)), M._numero(m.group(2))
        if a + b == 100:
            return f"es un reparto del pago, {a} y {b} por ciento: va en cuenta o en comprar como reparto."
    for m in M._MONTO.finditer(n):
        if m.group(2) or m.group(3):
            monto = K._monto(m.group(1) or m.group(3), m.group(2) or "")
            return ("es un monto, " + f"{monto:,}".replace(",", ".") + " pesos"
                    + ": un tope del total en cuenta, o una condicion de precio en buscar o producto.")
    pct = re.search(r"(\d{1,3})\s*(%|por ciento|off)", n)
    if pct:
        return f"es un porcentaje, {pct.group(1)} por ciento."
    if re.search(r"\d", n) or set(n.split()) & set("un uno una dos tres cuatro cinco seis siete ocho nueve diez".split()):
        return "es una cantidad."
    return "no es un numero."


def _referencia(t: str, estado: dict) -> str:
    nums = I.numeros(estado)
    ms = [k for k in nums if k.startswith("M-")]
    ls = [k for k in nums if k.startswith("L-")]
    rs = [k for k in nums if k.startswith("R-")]
    if not (ms or ls or rs):
        return "no hay nada en la charla a lo que pueda apuntar."
    partes = []
    if ms:
        partes.append(f"hay {len(ms)} productos mostrados, {ms[0]} a {ms[-1]}" if len(ms) > 1
                      else "hay un solo producto mostrado, M-1")
    if ls:
        partes.append(f"el pedido tiene {len(ls)} renglones, {ls[0]} a {ls[-1]}" if len(ls) > 1 else "el pedido tiene un renglon, L-1")
    if rs:
        partes.append(f"hay {len(rs)} pregunta del vendedor abierta, " + ", ".join(rs))
    return "; ".join(partes) + ". El codigo no sabe a cual apunta: si el mensaje no lo dice, van todos los que puede ser."


def _condicion(t: str) -> str:
    c = K.atar(t, K.productos(TIENDA), TIENDA)
    if "tope" in c:
        lado, monto = c["tope"]
        return (f"es una condicion de precio por unidad: {'como minimo' if lado == 'min' else 'como maximo'} "
                + f"{monto:,}".replace(",", ".") + " pesos. Va en condiciones; el codigo compara.")
    if "campo" in c or "todas" in c:
        campos = [x["campo"] for x in c.get("todas") or [c]]
        return (f"el codigo la filtra por el dato {', '.join(dict.fromkeys(campos))}"
                + (", como exclusion" if c.get("niega") else "") + ". Va en condiciones, en palabras del cliente.")
    return "el codigo no tiene un dato para filtrarla: va en condiciones, en palabras del cliente, o es otra cosa."


def _tema(t: str) -> str:
    temas = sorted({x for ts in M._temas(t, TIENDA).values() for x in ts})
    if not temas:
        return "no es un tema de las reglas de la tienda."
    return ("es el tema " + " o ".join(temas) + " de las reglas de la tienda: va en politica SOLO si pregunta la regla; "
            "pedir un envio, una cuenta o un dato de un producto no es politica.")


def _pedido(estado: dict) -> str:
    b = B.leer(estado.get("borrador"))
    if not b["renglones"]:
        return "el pedido esta vacio: no hay ningun renglon anotado."
    return f"el pedido tiene {len(b['renglones'])} renglones, en la LIBRETA, BORRADOR."


def contestar(pistas: list, estado: dict) -> str:
    out = []
    for p in pistas:
        t, tipo = str(p.get("texto")), str(p.get("tipo") or "").lower()
        r = {"producto": lambda: _producto(t), "rubro": lambda: _rubro(t), "lugar": lambda: _lugar(t),
             "numero": lambda: _numero(t), "referencia": lambda: _referencia(t, estado),
             "condicion": lambda: _condicion(t), "tema": lambda: _tema(t), "pedido": lambda: _pedido(estado)}.get(tipo)
        out.append(f'- "{t}" ({tipo}): ' + (r() if r else "el codigo no sabe contestar ese tipo."))
    return "LO QUE EL CODIGO CONTESTO A TUS PISTAS:\n" + ("\n".join(out) if out else "nada.")


# ══ V1: la consigna de hoy, con las respuestas en lugar de la tabla ═════════

def instalar_v1():
    def mensajes(mensaje, historial, estado, tienda_id):
        hay = bool([m for m in historial if m.get("role") == "user"])
        respuestas = contestar(paso1(mensaje, hay), estado)
        return [{"role": "system", "content": I.consigna(tienda_id)},
                {"role": "user", "content": I.libreta(estado, historial, tienda_id) + "\n" + respuestas
                 + f"\nULTIMO MENSAJE: {mensaje}"}]
    I.mensajes = mensajes


def correr(variante: str, formas: tuple, reps: int):
    from banco_pruebas import traduccion58 as T
    T.CORRIDAS = os.path.join(AQUI, f"corridas_{variante}.jsonl")
    T.REPS = reps
    original = T.formas_de
    T.formas_de = lambda *a: {f: v for f, v in original(*a).items() if f in formas}
    {"V1": instalar_v1}.get(variante, lambda: None)()
    if variante == "V2":
        import comandos
        comandos.instalar()
    if variante == "V3":
        import variante3
        variante3.instalar()
    if variante in ("V3L", "V4", "V5", "V6"):
        import limpio
        limpio.instalar()
        if variante == "V3L":
            import variante3
            variante3.instalar()
        else:
            import fichas
            fichas.instalar(variante)
            if variante == "V6":
                import banco
                banco.instalar()
    ok = T.correr(1, 1, sorted({c for c, _ in TURNOS}), TURNOS)
    with open(os.path.join(AQUI, f"uso_{variante}.jsonl"), "a", encoding="utf-8") as f:
        for u in USO:
            f.write(json.dumps(u) + "\n")
    return ok


if __name__ == "__main__":
    v = sys.argv[1]
    formas = tuple(sys.argv[sys.argv.index("--formas") + 1].split(",")) if "--formas" in sys.argv else ("original",)
    reps = int(sys.argv[sys.argv.index("--reps") + 1]) if "--reps" in sys.argv else 1
    import pistas  # el mismo modulo que usan comandos y variante3, asi el uso se anota en un solo lugar
    print("terminó" if pistas.correr(v, formas, reps) else "cortado")
