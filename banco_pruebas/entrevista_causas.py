"""LA ENTREVISTA DE LAS CAUSAS — el modelo frente a su propia falla (30-oct-2026, FICHA 83).

Pedido de Martin del 30-oct: con el catalogo entero en contexto el modelo no mejora, y algo del cableado falla. Las
entrevistas de antes eran de diseño, antes de armar cada herramienta; esta es despues de la prueba: por cada caso que
fallo, el modelo ve exactamente lo que recibio —la consigna, el mensaje con su contexto, cada herramienta que llamo con
lo que devolvio— y lo que contesto, y se le pregunta puntual la causa.

Los casos salen de lo grabado por `catalogo_entero.py` y `buscador_agente.py`. Con la gratis.

    python3 banco_pruebas/entrevista_causas.py [C41 K20 ...]
"""
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import catalogo_entero as CE  # noqa: E402

B = CE.B
SALIDA = os.path.join(AQUI, "entrevista_causas.json")
# Las fallas que se repiten, de cada clase: reglas contestadas sin buscar, el pedido reescrito al cambiarlo, lo mas caro de
# toda la tienda, el orden por un campo, y lo que vende la tienda.
CASOS = [("catalogo", "primeros", "C41", 0), ("catalogo", "primeros", "C11", 0), ("catalogo", "primeros", "C13", 0),
         ("catalogo", "fuera de muestra", "K18", 0), ("catalogo", "con charla", "K20", 1),
         ("catalogo", "con charla", "K21", 1), ("catalogo", "con charla", "K21", 2),
         ("buscador", "fuera de muestra", "K04", 0), ("buscador", "fuera de muestra", "K19", 0),
         ("buscador", "primeros", "C41", 0)]

PREGUNTA = """Esto es una revision de una falla, no un turno con el cliente. Arriba esta exactamente lo que recibiste y
lo que hiciste. La revision de la tienda marco que tu respuesta no cumple esto: {malas}.

Contesta con sinceridad, como experto en tu propio funcionamiento, y corto:
1. La causa puntual. Elegi una letra y deci por que:
   A) el dato que hacia falta no estaba en lo que recibiste;
   B) estaba y no lo usaste o no lo viste;
   C) la consigna te llevo a hacerlo asi;
   D) una herramienta devolvio algo confuso o incompleto;
   E) no entendiste lo que pedia el cliente;
   F) la revision esta mal: tu respuesta era correcta.
2. Copia textual la frase de lo que recibiste que te llevo al error, o deci que dato faltaba.
3. El cambio puntual en lo que te damos —un dato, la consigna o una herramienta— que lo hubiera evitado."""


def _transcripcion(consigna: str, entrada: str, g: dict) -> str:
    pasos = "\n".join(f"LLAMASTE {p['herramienta']} {json.dumps(p['pide'], ensure_ascii=False)}\nDEVOLVIO:\n"
                      f"{p['devuelve']}" for p in g.get("pasos") or [])
    return (f"=== LA CONSIGNA QUE RECIBISTE ===\n{consigna}\n\n=== EL MENSAJE QUE RECIBISTE ===\n{entrada}\n\n"
            f"=== LO QUE HICISTE CON LAS HERRAMIENTAS ===\n{pasos or 'ninguna herramienta'}\n\n"
            f"=== TU RESPUESTA AL CLIENTE ===\n{g.get('respuesta') or '(no llegaste a contestar)'}\n\n")


def main() -> None:
    from banco_pruebas.agendas58 import AGENDAS, EXPLICAR
    from banco_pruebas.sonda_charlas import nota_casilla
    from app.core.flujo import estado as E
    from app.storage import firestore_client as fc
    solo = [a for a in B.ARGS if a[:1] in "CKJ" and a[1:].isdigit()]
    interp = B.HM.C58.instalar()
    cat = CE.catalogo()
    consigna_buscador = B.CONSIGNA.split("\n\nTenes el catalogo entero")[0]
    vara = {c["id"]: c for c in json.load(open(os.path.join(AQUI, "vara_58.json"), encoding="utf-8"))["charlas"]}
    grab = {}
    for fuente, archivo in (("catalogo", CE.B.GRABADO), ("buscador", os.path.join(AQUI, "buscador_agente.jsonl"))):
        for r in map(json.loads, open(archivo, encoding="utf-8")):
            grab[(fuente, r["conjunto"], r["id"], r["turno"])] = r
    cli, _, modelo = B._cliente()
    out = []
    for clave in CASOS:
        fuente, conj, ch, t = clave
        if solo and ch not in solo or clave not in grab:
            continue
        g = grab[clave]
        turnos = vara[ch]["turnos"]
        previos = B.HM.C58.correr({"id": ch, "turnos": turnos[:t]}, list(AGENDAS[ch])[:t], interp, EXPLICAR) if t else []
        estado = E.leer(fc.get_conversation(f"cableado_{ch}", tienda_id=B.TID) or {}) if t else E.leer({})
        h = [x for p in previos for x in (("user", p["texto"]), ("assistant", p["respuesta"]))]
        contexto = (f"ESTADO DEL PEDIDO:\n{B.CM.carrito(estado)}\n\nEL PEDIDO ACTUAL, en el formato del presupuesto: "
                    f"{json.dumps(B.pedido_actual(estado), ensure_ascii=False)}")
        if fuente == "catalogo":
            contexto = f"{cat}\n\n{contexto}"
        entrada = f"{B.charla(h)}\n\n{contexto}\n\nULTIMO MENSAJE DEL CLIENTE: {g['mensaje']}"
        respuestas = [x["respuesta"] for x in previos] + [g.get("respuesta") or ""]
        malas = [k["n"] for k in turnos[t]["casillas"]
                 if nota_casilla(k, [], g.get("respuesta") or "", respuestas) is not True] or ["no llego a contestar"]
        texto = _transcripcion(B.CONSIGNA if fuente == "catalogo" else consigna_buscador, entrada, g) + \
            PREGUNTA.format(malas="; ".join(malas))
        r = None
        for intento in range(5):
            try:
                r = cli.chat.completions.create(model=modelo, temperature=0,
                                                messages=[{"role": "user", "content": texto}])
                break
            except Exception as e:  # noqa: BLE001
                print(f"  reintento {intento + 1}: {type(e).__name__}", flush=True)
                import time
                time.sleep(15 * (intento + 1))
        dice = (r.choices[0].message.content or "") if r else "SIN RESPUESTA"
        out.append({"fuente": fuente, "conjunto": conj, "id": ch, "turno": t, "mensaje": g["mensaje"],
                    "malas": malas, "causa": dice})
        print(f"\n== {fuente} · {ch} t{t}: {g['mensaje'][:140]}\n   MAL: {'; '.join(malas)}\n{dice}", flush=True)
        json.dump(out, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\ngratis · {modelo} · {len(out)} respuestas en {SALIDA}")


if __name__ == "__main__":
    main()
