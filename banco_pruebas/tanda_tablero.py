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
MENSAJES = [
    ("1  lo tenes*", "hola, tenes la notebook G15?"),
    ("2  stock", "cuantos teclados mecanicos te quedan?"),
    ("3  que trae*", "el mouse G502 que trae en la caja?"),
    ("4  cual cumple", "busco una notebook con 16gb de ram y que no sea fabricada en china"),
    ("4b valor que no existe", "tenes algo fabricado en japon?"),
    ("4c marca", "trabajan con la marca Redragon?"),
    ("7  cuanto sale", "cuanto sale el monitor mas barato que tengas?"),
    ("8  todo junto", "quiero dos auriculares y dos memorias ram, cuanto me sale todo?"),
    ("9  envio", "hacen envios a Posadas? cuanto sale?"),
    ("10 politica", "que garantia tienen las notebooks? hacen factura A?"),
    ("11 precio", "me haces precio si pago por transferencia?"),
    ("1b generico", "tenes algo para jugar que no sea muy caro?"),
    ("no vendemos", "venden bicicletas?"),
    ("13 posventa", "donde esta mi pedido? lo compre la semana pasada"),
]


async def _un_turno(texto: str) -> dict:
    from app.core import fuente as F
    from app.core import guardas_salida as gs
    from app.core import respuesta as R
    from app.core.contexto_turno import set_current_tienda

    set_current_tienda(TIENDA)
    inventario = F.texto_inventario(TIENDA)
    envio = F.texto_envio(texto, "", TIENDA)
    apagados = R.TEMAS_DEL_ENVIO if envio.get("texto") else ()
    bloque = R._bloque_fuente([], inventario, envio.get("texto") or "")

    # SE ENVUELVE `buscar` PARA VER LO QUE EL MODELO ESCRIBIO, no solo lo que
    # volvio. El informe cuenta los campos que no se aplicaron; el motivo
    # -si fue un hueco de valor o una condicion imposible- solo esta aca.
    from app.core import motor as MT
    crudo = {"consultas": [], "motivos": []}
    original = MT.buscar

    def espia(consultas, tienda_id, trace_id="", **kw):
        crudo["consultas"].extend(consultas or [])
        r = original(consultas, tienda_id, trace_id, **kw)
        for res in (r or {}).get("resultados") or []:
            for na in res.get("no_aplicado") or []:
                crudo["motivos"].append(str(na.get("motivo") or ""))
        return r

    MT.buscar = espia
    R.MT = MT
    t0 = time.time()
    try:
        salida, fichas, informe = await R._preguntar(
            R._voz(gs.business_name(TIENDA)), "", [], texto, bloque,
            "tanda", TIENDA, temas_apagados=apagados)
    finally:
        MT.buscar = original
    ms = int((time.time() - t0) * 1000)
    huecos = [m for m in crudo["motivos"] if "la fuente no escribe" in m]
    return {"texto": texto, "ms": ms, "salida": salida, "informe": informe,
            "consultas": crudo["consultas"], "huecos": huecos,
            "motivos": crudo["motivos"]}


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    sim_firestore.install()

    filas = []
    for etiqueta, texto in MENSAJES:
        try:
            r = await _un_turno(texto)
        except Exception as e:  # noqa: BLE001 — un turno caido no tumba la tanda
            print(f"{etiqueta:<24} ERROR {type(e).__name__}: {str(e)[:120]}")
            continue
        r["pedido"] = etiqueta
        filas.append(r)
        inf = r["informe"]
        tipo = (r["salida"] or {}).get("tipo") or "SIN RESPUESTA"
        print(f"{etiqueta:<24} vueltas={inf['vueltas']} "
              f"llamadas={inf['llamadas']} consultas={inf['consultas']} "
              f"puntuales={inf['puntuales']} repetidas={inf['repetidas']} "
              f"vacios={inf['vacios']} huecos={len(r['huecos'])} "
              f"{r['ms']}ms  {tipo}")

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
    print(f"SIN RESPUESTA           {sum(1 for f in filas if not f['salida'])}")
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
