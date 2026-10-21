"""CINCO OPCIONES PARA LOS CASOS QUE FALLAN — cada una sola, sobre la mejor base del 21-oct: limpio, fichas, pistas,
avisos y tercera vuelta (V4). Se corren solo los casos de traduccion que V4 falla.

  O1  avisos nuevos del codigo, de clase: una compra con un renglon del pedido como producto, un REEMPLAZAR sin como
      queda el pedido, y elegir entre lo mostrado cuando la tienda tiene mas. Solo cambian el mensaje donde saltan.
  O2  O1 y, en la tercera vuelta, un caso curado de la clase del aviso.
  O3  O1 y, en la tercera vuelta, el resultado en seco: como quedaria el pedido con esos comandos.
  O4  lineas de frontera en las fichas, compartidas: cambian la entrada de todos los mensajes.
  O5  antes de los comandos, una linea ENTENDI con lo que pide el cliente, compartida.

  python3 opciones.py O1
"""
import copy
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import pistas as P  # noqa: E402

CASOS = {("K11", 5, "original"), ("K11", 5, "whatsapp"), ("K11", 5, "coloquial"), ("K21", 2, "original"),
         ("K07", 0, "coloquial"), ("C46", 1, "original"), ("C46", 1, "whatsapp"), ("C46", 1, "coloquial")}

CAMBIAR_RENGLON = ("cambiar_renglon", "LIBRETA:\n- BORRADOR:\n  L-1 1 parlante a Salta: 1 Parlante JBL Go 3 Negro\n"
                   "  L-2 1 webcam a Salta: 1 Webcam Logitech C270 HD Negro",
                   "pensandolo bien que sean tres parlantes, y enviamelos a Neuquen. cuanto da todo, envio incluido?",
                   '1. CAMBIAR renglon="L-1" cantidad="3" destino="Neuquen" | "pensandolo bien que sean tres parlantes, '
                   'y enviamelos a Neuquen."\n'
                   '2. ENVIO destino="Neuquen" | "cuanto da todo, envio incluido?"\n'
                   '3. CUENTA | "cuanto da todo, envio incluido?"')
REHACER_BARATO = ("rehacer_mas_barato", "LIBRETA:\n- BORRADOR:\n  L-1 1 parlante a Salta: 1 Parlante JBL Flip 6 Negro\n"
                  "  L-2 1 webcam a Neuquen: 1 Webcam Logitech C920 HD Pro Negro\n- PIDIO POR RUBRO: 1 parlante, 1 webcam",
                  "si total la marca me da lo mismo, cambiame todo por lo mas economico de cada cosa",
                  '1. OTRO que="dato" | "si total la marca me da lo mismo,"\n'
                  '2. BUSCAR rubro="parlante" cantidad="1" orden="mas barato" | "cambiame todo por lo mas economico de cada cosa"\n'
                  '3. BUSCAR rubro="webcam" cantidad="1" orden="mas barato" | "cambiame todo por lo mas economico de cada cosa"\n'
                  '4. REEMPLAZAR | "cambiame todo por lo mas economico de cada cosa"\n'
                  '4. AGREGAR producto="parlante" cantidad="1" destino="Salta" | "cambiame todo por lo mas economico de cada cosa"\n'
                  '4. AGREGAR producto="webcam" cantidad="1" destino="Neuquen" | "cambiame todo por lo mas economico de cada cosa"')

FRONTERAS = [
    ('   SACAR, CAMBIAR, CONFIRMAR, ACEPTAR, TOTAL y REEMPLAZAR son cambios',
     '   Lo que YA esta en el BORRADOR no se vuelve a AGREGAR: mandarlo a otro lugar o cambiar cuantos son es CAMBIAR\n'
     '   su renglon, con la cantidad y el destino nuevos. REEMPLAZAR va siempre con los AGREGAR de como queda todo.\n'
     '   SACAR, CAMBIAR, CONFIRMAR, ACEPTAR, TOTAL y REEMPLAZAR son cambios'),
    ('   entre_lo_mostrado: SOLO si elige dentro de lo ya mostrado,',
     '   Rehacer la eleccion del pedido, lo mas barato de cada cosa, busca en toda la tienda, no entre lo mostrado.\n'
     '   entre_lo_mostrado: SOLO si elige dentro de lo ya mostrado,'),
    ('PARA TODOS: lo que depende de otro renglon',
     'PARA TODOS: cada cosa que pide el cliente, tambien "pasame precios" o "decime cuanto", va citada en el renglon al que\n'
     'corresponde. Lo que depende de otro renglon'),
]

ENTENDI = ("\n7. Antes de los renglones, escribi UNA linea que empiece con ENTENDI: y diga en tus palabras todo lo que pide\n"
           "   el cliente. Despues, los renglones.")


def _avisos_nuevos(avisos_base):
    """O1: los avisos de V3 mas tres de clase, que solo saltan donde el modelo escribe ese error."""
    from app.core.flujo import agenda as A
    from app.core.flujo import catalogo as K
    from app.core.flujo import interprete as I

    def avisos(agenda, estado, mensaje):
        problemas, datos, hay_si = avisos_base(agenda, estado, mensaje)
        nums = I.numeros(estado)
        mostrados = [v for k, v in nums.items() if k.startswith("M-")]
        qs = A.preguntas(agenda)
        for q in qs:
            n = q.get("n")
            for a in q.get("agrega") or []:
                if re.match(r"^L-\d+$", str(a.get("producto") or "").strip()):
                    problemas.append(f'renglon {n}: {a["producto"]} ya esta en el pedido: no se vuelve a agregar. Para '
                                     f'mandarlo a otro lugar o cambiar cuantos son, es CAMBIAR renglon="{a["producto"]}".')
            if q.get("reemplaza") and not [a for a in q.get("agrega") or [] if a.get("producto")]:
                problemas.append(f"renglon {n}: REEMPLAZAR sin AGREGAR deja el pedido vacio: los AGREGAR son como queda.")
            if q.get("accion") == "buscar" and q.get("entre_lo_mostrado"):
                rub = K.rubro(str(q.get("rubro") or ""), "verifika_prod")
                conds = q.get("condiciones") or []
                en_m = len(K.buscar(rub, conds, "nada", 50, "verifika_prod", entre=mostrados)["filas"])
                en_t = len(K.buscar(rub, conds, "nada", 50, "verifika_prod")["filas"])
                if en_t > en_m:
                    problemas.append(f"renglon {n}: entre lo mostrado hay {en_m} de {rub or 'ese rubro'} que cumplen; en "
                                     f"toda la tienda hay {en_t}. entre_lo_mostrado va solo si elige dentro de lo ya mostrado.")
        return problemas, datos, hay_si
    return avisos


def _caso_de(problemas):
    t = " ".join(problemas)
    if "ya esta en el pedido" in t:
        return CAMBIAR_RENGLON
    if "REEMPLAZAR" in t or "entre lo mostrado" in t:
        return REHACER_BARATO
    return None


def _en_seco(agenda, estado):
    """O3: como quedaria el pedido con estos comandos, sin contestarle al cliente."""
    from app.core.flujo import agenda as A
    from app.core.flujo import borrador as B
    b = copy.deepcopy(B.leer(estado.get("borrador")))
    for q in A.preguntas(agenda):
        if q.get("accion") != "comprar":
            continue
        try:
            B.aplicar(b, {k: q.get(k) for k in ("saca", "cambia", "confirma", "total", "reemplaza", "responde")}
                      | {"agrega": [dict(a, cita=q.get("cita") or "") for a in q.get("agrega") or [] if a.get("producto")]})
        except Exception as e:  # noqa: BLE001
            return f"ASI QUEDARIA EL PEDIDO: el codigo no pudo aplicar el renglon {q.get('n')} ({type(e).__name__})."
    if not b["renglones"]:
        return "ASI QUEDARIA EL PEDIDO: vacio."
    res = B.resolver(b, "verifika_prod")
    return "ASI QUEDARIA EL PEDIDO:\n" + "\n".join(B.libreta(b, res, B.faltantes(b, res)))


def instalar(opcion: str):
    import limpio
    import fichas
    import variante3 as V3
    limpio.instalar()
    if opcion == "O4":
        for a, b in FRONTERAS:
            assert a in fichas.FICHAS, a
            fichas.FICHAS = fichas.FICHAS.replace(a, b)
    fichas.instalar("V4")
    if opcion == "O5":
        base = V3.consigna
        V3.consigna = lambda t: base(t).replace("\nLOS NUEVE TIPOS", ENTENDI + "\n\nLOS NUEVE TIPOS", 1)
    if opcion in ("O1", "O2", "O3"):
        V3.avisos = _avisos_nuevos(V3.avisos)
    if opcion in ("O2", "O3"):
        avisos_o1 = V3.avisos

        def avisos(agenda, estado, mensaje):
            problemas, datos, hay_si = avisos_o1(agenda, estado, mensaje)
            if opcion == "O2":
                c = _caso_de(problemas)
                if c:
                    datos.append(f"UN CASO RESUELTO DE ESTA CLASE, con su propia libreta:\n{c[1]}\nULTIMO MENSAJE: {c[2]}"
                                 f"\nCOMANDOS:\n{c[3]}")
            if opcion == "O3" and problemas:
                datos.append(_en_seco(agenda, estado))
            return problemas, datos, hay_si
        V3.avisos = avisos


def correr(opcion: str):
    from banco_pruebas import traduccion58 as T
    T.CORRIDAS = os.path.join(AQUI, f"corridas_{opcion}.jsonl")
    T.REPS = 1
    original = T.formas_de
    T.formas_de = lambda ch, k, *a: {f: v for f, v in original(ch, k, *a).items() if (ch, k, f) in CASOS}
    instalar(opcion)
    turnos = {(c, k) for c, k, _f in CASOS}
    ok = T.correr(1, 1, sorted({c for c, _ in turnos}), turnos)
    with open(os.path.join(AQUI, f"uso_{opcion}.jsonl"), "a", encoding="utf-8") as f:
        for u in P.USO:
            f.write(json.dumps(u) + "\n")
    return ok


if __name__ == "__main__":
    import opciones
    print("terminó" if opciones.correr(sys.argv[1]) else "cortado")
