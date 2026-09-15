#!/usr/bin/env python3
"""
TANDA DEL TABLERO — el numero que dice si el tablero de la FICHA 53 sirvio.

QUE MIDE, y es lo unico que no se puede saber sin el modelo vivo:

  1. VUELTAS POR TURNO. Es LA metrica. El 12-sep fueron tres en 6 de 6 turnos,
     y cada vuelta vuelve a pagar el prompt entero. Si no baja, el tablero
     costo 1.538 tokens por turno para nada.
  2. HUECOS DE VALOR. Uno es el tablero funcionando: el modelo escribio una
     palabra que la fuente no usa y el motor le devolvio las reales. MUCHOS del
     mismo campo son un renglon de la leyenda que quedo afuera del presupuesto.
  3. SI LOS PARRAFOS MUDADOS AL ESQUEMA SE RESPETAN. `busco` ya se sabe que en
     el esquema no se respetaba -0 de 9 el 12-sep-; los otros tres se mudaron
     sin medicion y este banco es la medicion.
  4. CONSULTAS REPETIDAS y busquedas vacias.

CON LA CLAVE GRATIS, y no se cambia a la paga: el banco mide comportamiento,
no cuota. Si se agota a mitad de tanda se para y se sigue al dia siguiente.

NO DEPLOYA: `banco_pruebas/` esta en el paths-ignore de deploy.yml y en
.gcloudignore. Usa el doble local de Firestore, asi que no toca produccion ni
necesita credenciales de Google.

Uso, desde la raiz:
    python3 banco_pruebas/tanda_tablero.py
    python3 banco_pruebas/tanda_tablero.py --json salida.json
"""
import argparse
import asyncio
import json
import os
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from banco_pruebas import sim_firestore  # noqa: E402

TIENDA = "verifika_prod"

# LOS MENSAJES CUBREN LOS CATORCE PEDIDOS DE LA FICHA 52, no una lista de
# ocurrencias. Cada uno dice cual es, para que se pueda leer el resultado por
# pedido y no en promedio.
# LOS MENSAJES CUBREN LOS CATORCE PEDIDOS DE LA FICHA 52, no una lista de
# ocurrencias. Cada uno dice cual es, para que se pueda leer el resultado por
# pedido y no en promedio.
#
# EL TERCER ELEMENTO ES LA VARA, y es lo que este banco agrega el 14-sep: que
# CAMPOS de la puerta tendria que haber declarado el modelo para ese mensaje.
# Sin eso, "el modelo no usa la herramienta" era una impresion leyendo una
# charla; con eso es un numero que se compara entre corridas.
#
# POR QUE HACIA FALTA. El 14-sep 22:57, en produccion, a un pedido con reparto
# 70/30 el bot contesto "eso no lo puedo hacer" TENIENDO el campo `cuenta`
# enchufado hacia una hora. El campo existia, el modelo no lo uso, y no habia
# forma de verlo sin leer la charla a mano.
#
# VACIO quiere decir que ningun campo es obligatorio para ese mensaje: la
# posventa se deriva y no tiene boca.
MENSAJES = [
    ("1  lo tenes*", "hola, tenes la notebook G15?", {"consultas"}),
    ("2  stock", "cuantos teclados mecanicos te quedan?", {"consultas"}),
    ("3  que trae*", "el mouse G502 que trae en la caja?", {"consultas"}),
    ("4  cual cumple", "busco una notebook con 16gb de ram y que no sea fabricada en china", {"consultas"}),
    ("4b valor que no existe", "tenes algo fabricado en japon?", {"consultas"}),
    ("4c marca", "trabajan con la marca Redragon?", {"consultas"}),
    # PEDIDO 5 Y 6, QUE NO ESTABAN. Criterio y compatibilidad son dos de las
    # cinco bocas y este banco no las tocaba: una boca que el banco no ejercita
    # es una boca que puede estar muerta sin que nadie lo note.
    ("5  me sirve", "me sirve un mouse de esos para diseño grafico?", {"criterio"}),
    ("6  anda con", "el teclado K380 anda con mi PS5?", {"compatibilidad"}),
    ("7  cuanto sale", "cuanto sale el monitor mas barato que tengas?", {"consultas"}),
    ("8  todo junto", "quiero dos auriculares y dos memorias ram, cuanto me sale todo?", {"cuenta"}),
    # EL CASO QUE FALLO VIVO, palabra por palabra de la charla real del
    # 14-sep 22:57. Un banco que no contiene la pregunta que rompio el bot no
    # puede decir que el bot se arreglo.
    ("8b reparto 70/30", "quiero dos auriculares y dos mouse, con envio a Cordoba, "
     "y divido el pago setenta por transferencia y treinta por mercado pago", {"cuenta", "envios"}),
    ("9  envio", "hacen envios a Posadas? cuanto sale?", {"envios"}),
    ("10 politica", "que garantia tienen las notebooks? hacen factura A?", {"temas"}),
    ("11 precio", "me haces precio si pago por transferencia?", {"temas"}),
    ("1b generico", "tenes algo para jugar que no sea muy caro?", {"consultas"}),
    ("no vendemos", "venden bicicletas?", {"consultas"}),
    ("13 posventa", "donde esta mi pedido? lo compre la semana pasada", set()),
]

# LOS SEIS CAMPOS DE LA PUERTA, en el orden en que los nombra el tablero.
CAMPOS = ("consultas", "temas", "compatibilidad", "envios", "criterio", "cuenta")


async def _un_turno(texto: str) -> dict:
    from app.core import fuente as F
    from app.core import guardas_salida as gs
    from app.core import respuesta as R
    from app.core.contexto_turno import set_current_tienda

    set_current_tienda(TIENDA)
    inventario = F.texto_inventario(TIENDA)
    # EL ENVIO YA NO SE EMPUJA: lo pide el modelo por el motor, como el resto.
    # El banco arma el mismo bloque que el turno vivo, ni mas ni menos.
    bloque = R._bloque_fuente([], inventario)

    # SE ENVUELVE `buscar` PARA VER LO QUE EL MODELO ESCRIBIO, no solo lo que
    # volvio. El informe cuenta los campos que no se aplicaron; el motivo
    # -si fue un hueco de valor o una condicion imposible- solo esta aca.
    from app.core import motor as MT
    # EL ESPIA MIRA LOS SEIS CAMPOS, no solo `consultas` (14-sep-2026). Los
    # otros cinco entraban por `**kw` y se tiraban, asi que el banco no podia
    # decir si el modelo pidio una politica, una compatibilidad o una cuenta.
    # Es justo lo que hacia falta saber.
    crudo = {"consultas": [], "motivos": [], "declarados": set()}
    original = MT.buscar

    def espia(consultas, tienda_id, trace_id="", **kw):
        crudo["consultas"].extend(consultas or [])
        if consultas:
            crudo["declarados"].add("consultas")
        for campo in CAMPOS[1:]:
            if kw.get(campo):
                crudo["declarados"].add(campo)
        r = original(consultas, tienda_id, trace_id, **kw)
        for res in (r or {}).get("resultados") or []:
            for na in res.get("no_aplicado") or []:
                crudo["motivos"].append(str(na.get("motivo") or ""))
        return r

    MT.buscar = espia
    R.MT = MT
    t0 = time.time()
    try:
        salida, fichas, envios, cuenta, informe = await R._preguntar(
            R._voz(gs.business_name(TIENDA)), "", [], texto, bloque,
            "tanda", TIENDA)
    finally:
        MT.buscar = original
    ms = int((time.time() - t0) * 1000)
    huecos = [m for m in crudo["motivos"] if "la fuente no escribe" in m]
    return {"texto": texto, "ms": ms, "salida": salida, "informe": informe,
            "consultas": crudo["consultas"], "huecos": huecos,
            "motivos": crudo["motivos"],
            "declarados": sorted(crudo["declarados"]), "cuenta": cuenta}


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    # LA PAUSA NO ES COMODIDAD: SIN ELLA EL BANCO MIDE LA CUOTA, NO EL BOT.
    #
    # MEDIDO el 14-sep: 17 mensajes disparados uno atras de otro dieron NUEVE
    # turnos sin respuesta, con vueltas=1 y 2,1 segundos. No era el modelo
    # esquivando la puerta: era el 429 de la clave gratis, que no es una rafaga
    # sino la cuota de TOKENS POR MINUTO -250.000 de entrada- y trae
    # `retryDelay: 18s` adentro del error. Con tres reintentos acotados no
    # alcanza cuando la tanda entera empuja.
    #
    # Y LO PEOR NO ERA PERDER LOS TURNOS: era que un turno caido por cuota se
    # lee EXACTAMENTE IGUAL que un turno donde el modelo no pidio el campo
    # -campos vacios, FALTO todo-. O sea que sin pausa este banco acusa al
    # modelo de algo que no hizo, que es peor que no medir.
    #
    # NO SE CAMBIA A LA PAGA: el banco mide comportamiento, no cuota.
    ap.add_argument("--pausa", type=float, default=20.0,
                    help="segundos entre mensajes. 0 para no esperar.")
    args = ap.parse_args()
    sim_firestore.install()

    filas = []
    for i, (etiqueta, texto, esperados) in enumerate(MENSAJES):
        if i and args.pausa:
            await asyncio.sleep(args.pausa)
        try:
            r = await _un_turno(texto)
        except Exception as e:  # noqa: BLE001 — un turno caido no tumba la tanda
            print(f"{etiqueta:<24} ERROR {type(e).__name__}: {str(e)[:120]}")
            continue
        r["pedido"] = etiqueta
        r["esperados"] = sorted(esperados)
        # UN TURNO CAIDO NO ACUSA AL MODELO. Sin respuesta y sin una sola
        # llamada al motor no hubo decision que medir: el turno se cuenta
        # aparte, igual que `tablero_piso.json` ya separa los caidos por cuota
        # en vez de ensuciar el promedio.
        r["caido"] = not r["salida"] and not r["informe"]["llamadas"]
        r["faltaron"] = ([] if r["caido"]
                         else sorted(esperados - set(r["declarados"])))
        filas.append(r)
        inf = r["informe"]
        tipo = (r["salida"] or {}).get("tipo") or "SIN RESPUESTA"
        print(f"{etiqueta:<24} vueltas={inf['vueltas']} "
              f"llamadas={inf['llamadas']} consultas={inf['consultas']} "
              f"puntuales={inf['puntuales']} repetidas={inf['repetidas']} "
              f"vacios={inf['vacios']} huecos={len(r['huecos'])} "
              f"{r['ms']}ms  {tipo}")
        # EL RENGLON QUE DICE SI USO LA HERRAMIENTA. Va pegado al turno y no
        # solo en el resumen: un campo que falto hay que poder verlo al lado
        # del mensaje que lo necesitaba.
        print(f"{'':<24} campos={','.join(r['declarados']) or '-'}"
              + (f"   FALTO: {','.join(r['faltaron'])}" if r["faltaron"] else ""))

    if not filas:
        print("\nNI UN TURNO CORRIO. Sin numero no hay medicion.")
        return 1

    n = len(filas)
    vueltas = sum(f["informe"]["vueltas"] for f in filas) / n
    consultas = sum(f["informe"]["consultas"] for f in filas)
    con_motor = sum(1 for f in filas if f["informe"]["llamadas"])
    puntuales = sum(f["informe"]["puntuales"] for f in filas)
    print("\n" + "=" * 64)
    print(f"TURNOS                  {n}")
    print(f"VUELTAS POR TURNO       {vueltas:.2f}   (12-sep: 3.00; meta: 2.00)")
    print(f"BUSCARON                {con_motor} de {n}")
    print(f"CONSULTAS               {consultas}")
    # EL DENOMINADOR DE `busco` NO SON LAS CONSULTAS, y la primera lectura de
    # este banco se asusto de gusto: "2 de 18" parecia que el modelo no lo
    # declaraba, cuando `uno` SOLO corresponde si el cliente nombro un producto
    # puntual. En esta lista hay dos mensajes asi -la G15 y el G502- y los dos
    # lo declararon, las dos tandas. Un numero con el denominador equivocado es
    # peor que ninguno: manda a arreglar lo que no esta roto.
    # EL ASTERISCO marca los mensajes donde el cliente nombra UN producto
    # puntual, que son los unicos donde `uno` corresponde. Se marca a mano en
    # la lista porque es una propiedad del mensaje, no algo que se pueda
    # derivar: la primera version lo adivinaba por el numero de pedido y
    # contaba seis donde hay dos.
    puntuales_posibles = sum(1 for f in filas if "*" in f["pedido"]
                             and f["informe"]["llamadas"])
    print(f"CON `busco: uno`        {puntuales} declaradas sobre "
          f"{puntuales_posibles} mensajes de producto puntual   "
          f"(12-sep: 0 de 9 consultas)")
    print(f"REPETIDAS               {sum(f['informe']['repetidas'] for f in filas)}")
    print(f"BUSQUEDAS VACIAS        {sum(f['informe']['vacios'] for f in filas)}")
    print(f"HUECOS DE VALOR         {sum(len(f['huecos']) for f in filas)}")
    print(f"SIN RESPUESTA           {sum(1 for f in filas if not f['salida'])}"
          f"   (caidos sin llegar al motor: {sum(1 for f in filas if f['caido'])})")

    # ── LA ATADURA DE LA PUERTA — el numero nuevo del 14-sep ────────────
    #
    # QUE CONTESTA: de los mensajes que NECESITABAN un campo, en cuantos el
    # modelo lo declaro. Es lo unico que distingue "la boca esta rota" de "la
    # boca anda y el modelo no la llama", y hasta hoy las dos se veian igual
    # desde afuera: sin campo declarado no hay dato, y sin dato el bot dice
    # que no lo tiene.
    con_vara = [f for f in filas if f["esperados"] and not f["caido"]]
    caidos = [f for f in filas if f["caido"]]
    ok = [f for f in con_vara if not f["faltaron"]]
    print("\n" + "=" * 64)
    print("LA ATADURA DE LA PUERTA — ¿pide el campo que le corresponde?")
    print(f"MENSAJES CON VARA       {len(con_vara)}"
          + (f"   ({len(caidos)} turnos caidos, no se cuentan)" if caidos else ""))
    print(f"PIDIO LO QUE HACIA FALTA {len(ok)} de {len(con_vara)}"
          f"   ({100 * len(ok) // max(1, len(con_vara))}%)")
    # POR CAMPO, que es donde se ve cual boca no la llama nadie. Un promedio
    # alto puede tapar una boca muerta: cinco campos al 100% y uno al 0% dan
    # 83%, y ese 0% es el bot diciendo que no puede hacer algo que si puede.
    print("\n  campo            pedido por la vara   declarado")
    for campo in CAMPOS:
        debia = [f for f in con_vara if campo in f["esperados"]]
        hizo = [f for f in debia if campo in f["declarados"]]
        extra = sum(1 for f in filas if campo in f["declarados"]
                    and campo not in f["esperados"] and not f["caido"])
        if not debia and not extra:
            continue
        print(f"  {campo:<16} {len(debia):>10}          {len(hizo):>10}"
              + (f"   (+{extra} sin vara)" if extra else ""))
    faltaron = [(f["pedido"], ",".join(f["faltaron"])) for f in con_vara
                if f["faltaron"]]
    if faltaron:
        print("\n  LO QUE NO PIDIO, uno por linea:")
        for pedido, campos in faltaron:
            print(f"    {pedido:<24} falto {campos}")
    huecos = [h for f in filas for h in f["huecos"]]
    if huecos:
        print("\nLOS HUECOS, uno por linea:")
        for h in huecos:
            print("  " + h[:150])
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(filas, fh, ensure_ascii=False, indent=1, default=str)
        print(f"\ncrudo en {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
