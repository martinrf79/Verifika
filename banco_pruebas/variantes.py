"""LAS VARIANTES — cada compleja dicha de muchas formas, con el modelo real (20-oct-2026, pieza 3 del plan de Martin).

POR QUE EXISTE. Una regla que arregla la forma en que el cliente lo dijo hoy puede romper otra forma: "lo pedido" arreglo
"toma lo mas caro" y rompio el primer mensaje de los siete articulos. Esto es la vara para que entre un cambio en la
consigna o en el codigo: cada familia es una compleja dicha de diez formas, y el cambio entra si el puntaje no baja en
ninguna familia, no si arregla la forma que lo motivo.

  la familia   una compleja con sus formas de decirla, la charla previa si la necesita, y como se califica.
  el modelo    el de produccion, con la clave GRATIS, por el webhook entero del clon. La charla previa va con la agenda
               grabada, asi lo que se mide es solo la forma nueva.
  la nota      por respuesta: bien, pregunta —no la resolvio pero no rompio la venta: repregunta o deja propuesto— o
               mal. Por familia, cuantas bien de cuantas.

Es REANUDABLE: cada respuesta se anota en variantes_corridas.jsonl con la huella de la consigna, y lo ya corrido con la
misma consigna se saltea. Si la cuota se agota, se corta limpio y se sigue otro dia con el mismo comando.

  python3 -m banco_pruebas.variantes                 todas las familias
  python3 -m banco_pruebas.variantes mejor vendido   solo esas
  python3 -m banco_pruebas.variantes --informe       solo el informe de lo ya corrido
"""
import asyncio
import hashlib
import json
import os
import re
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
CORRIDAS = os.path.join(AQUI, "variantes_corridas.jsonl")
PREVIA = "19d2fdb852"  # la charla de las 19:29: siete articulos a Rosario y Neuquen, tope y pago partido
LECTURA = {"texto": "a Rosario, 2 mouse, 1 teclado y 1 webcam; a Neuquén, 1 mouse, 1 teclado y 1 auriculares; "
                    "7 en total", "cita": "el resto a Neuquén"}


def _total_final(r: str) -> int:
    m = re.search(r"Total final: \$([\d.]+)", r) or re.search(r"Total general: \$([\d.]+)", r)
    return int(m.group(1).replace(".", "")) if m else 0


def _plano(r: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", r.lower()) if unicodedata.category(c) != "Mn")


def _destinos(r: str) -> bool:
    return "envio a rosario" in _plano(r) and "envio a neuquen" in _plano(r)


def _siete(r: str) -> str:
    if "No llegué a resolver" in r:
        return "mal"
    destinos = _destinos(r)
    if destinos and "Pago dividido" in r and "Webcam" in r and (_total_final(r) <= 600000 or "pasa tu tope" in r):
        return "bien"
    return "pregunta" if "?" in r and "Presupuesto:" not in r else "mal"


def _mejor(r: str) -> str:
    rubros = all(f"el de gama más alta de {x}" in r for x in ("mouse", "teclado", "auriculares", "webcam"))
    if rubros and _destinos(r):
        return "bien"
    return "pregunta" if "Con ese cambio saco del pedido" in r else "mal"


def _vendido(r: str) -> str:
    if "Con ese cambio saco del pedido" in r or "Dejé el pedido" in r:
        return "mal"
    return "bien" if "No tengo el dato" in r else "mal"


FAMILIAS = {
    "siete": {"que": "siete articulos a dos destinos, tope de 600 mil y pago mitad y mitad, en el primer mensaje",
              "previa": False, "nota": _siete, "formas": [
        "Necesito tres mouse, dos teclados y un par de auriculares, no más de 600 mil. Dos mouse y un teclado a Rosario, "
        "el resto a Neuquén, sumame una webcam para Rosario. Pago mitad transferencia y mitad Mastercard",
        "Quiero 3 mouse, 2 teclados y 1 auricular. Tengo 600 mil como máximo. A Rosario mandá 2 mouse y un teclado, lo "
        "que queda a Neuquén, y agregá una webcam a Rosario. Mitad transferencia, mitad Mastercard.",
        "hola! presupuesto x favor: tres mouses, dos teclados, unos auriculares. presupuesto max 600k. rosario: 2 mouse "
        "+ 1 teclado + webcam. neuquen el resto. pago 50/50 transferencia y master",
        "Necesito armar un pedido de 3 mouse, 2 teclados y auriculares sin pasarme de 600.000 pesos. Dos mouse y un "
        "teclado van para Rosario junto con una webcam; lo demás para Neuquén. Pago la mitad por transferencia y la "
        "otra mitad con Mastercard.",
        "Me pasás precio de tres mouse dos teclados y un auricular? no quiero gastar mas de 600 lucas. en rosario 2 "
        "mouse 1 teclado y sumá webcam, el resto a neuquen. la mitad transfiero y la otra mitad mastercard",
        "Busco 3 mouse, 2 teclados, 1 auricular y 1 webcam. Total tope 600 mil. Rosario: 2 mouse, 1 teclado, la "
        "webcam. Neuquén: 1 mouse, 1 teclado, el auricular. Pago 50% transferencia 50% Mastercard.",
        "Para la oficina: 3 mouse, 2 teclados, auriculares. Presupuesto de 600 mil en total. Un envío a Rosario con dos "
        "mouse, un teclado y una webcam, y otro a Neuquén con lo restante. Abono mitad transferencia mitad Mastercard.",
        "Che, necesito 3 mouse y 2 teclados y unos auris, hasta 600 mil todo. 2 mouse y 1 teclado a Rosario, lo otro a "
        "Neuquén. Ah y una webcam para Rosario. Pago mitad y mitad, transferencia y Mastercard.",
        "Cotizame 3 mouse, 2 teclados y 1 par de auriculares con un máximo de 600 mil. Entrega en Rosario de 2 mouse y "
        "1 teclado más una webcam; en Neuquén el resto. Forma de pago: 50 transferencia, 50 Mastercard.",
        "tres mouse dos teclados auriculares, que no pase 600 mil. rosario dos mouse un teclado y webcam. neuquen lo "
        "demas. transferencia la mitad, mastercard la otra"]},
    "mejor": {"que": "con el pedido armado, otro orden para todo: lo mejor, lo mas caro", "previa": True,
              "nota": _mejor, "formas": [
        "Arma todo con lo mejor que tengas", "No tomes lo mas barato toma lo mas caro",
        "y si en vez de lo mas barato me presupuestas lo mejor que tengas", "quiero todo de gama alta",
        "cambiá todo por lo más top que tengas", "no me importa el precio, poné lo mejor en todo",
        "mejor dame los mejores modelos de cada cosa", "subí todo a la mejor calidad", "lo más caro de cada uno",
        "ponele lo mejor a todo el pedido"]},
    "vendido": {"que": "un orden sin dato en las fichas: el mas vendido", "previa": True, "nota": _vendido, "formas": [
        "cual es el mouse mas vendido", "qué teclado es el que más sale", "el más popular de los auriculares?",
        "cuál es la webcam más vendida", "el mouse que mas se vende", "lo más pedido en teclados"]},
}


def _huella() -> str:
    """La consigna y el esquema de la ficha, desde el 22-oct: un cambio en cualquiera de los dos se mide de nuevo."""
    from app.core.flujo import ficha
    return hashlib.sha1((ficha.consigna("verifika_prod") + json.dumps(ficha.formato("verifika_prod"), sort_keys=True))
                        .encode()).hexdigest()[:10]


def _leidas() -> dict:
    out = {}
    if os.path.exists(CORRIDAS):
        for linea in open(CORRIDAS, encoding="utf-8"):
            x = json.loads(linea)
            out[(x["huella"], x["familia"], x["forma"])] = x
    return out


def correr(familias: list) -> None:
    from banco_pruebas import cableado58 as R
    from banco_pruebas import clon_produccion as C
    from app.core import llm_reintento
    puerta = llm_reintento._cliente
    it = R.instalar()
    real = it.interpretar
    llm_reintento._cliente = puerta  # el modelo real: lo que se mide es su traduccion
    previa = json.load(open(os.path.join(AQUI, "reales", PREVIA + ".json"), encoding="utf-8"))["turnos"][0]
    R.ELEGIR[previa["mensaje"]] = LECTURA
    huella, hechas = _huella(), _leidas()
    for nombre in familias:
        f = FAMILIAS[nombre]
        for k, forma in enumerate(f["formas"]):
            if (huella, nombre, forma) in hechas:
                continue
            uid = f"variantes_{nombre}_{k}"
            C.reiniciar_cliente(uid)
            if f["previa"]:
                cola = [previa["agenda"]]

                async def _grabada(*a, **kw):
                    return cola.pop(0)
                it.interpretar = _grabada
                asyncio.run(C.turno(uid, previa["mensaje"]))
            vistas = []

            async def _modelo(*a, **kw):
                for intento in range(5):
                    r = await real(*a, **kw)
                    if r is not None:
                        vistas.append(r)
                        return r
                    time.sleep(10 * (intento + 1))
                return None
            it.interpretar = _modelo
            respuesta = "\n".join(asyncio.run(C.turno(uid, forma)))
            if not vistas:
                print(f"[{nombre} {k}] el modelo no contesto: se corta, se sigue otro dia con el mismo comando")
                return
            x = {"huella": huella, "familia": nombre, "forma": forma, "nota": f["nota"](respuesta),
                 "agenda": vistas[-1], "respuesta": respuesta}
            with open(CORRIDAS, "a", encoding="utf-8") as out:
                out.write(json.dumps(x, ensure_ascii=False) + "\n")
            print(f"[{nombre} {k}] {x['nota']}")
            time.sleep(2)


def informe(familias: list) -> None:
    from banco_pruebas import clon_produccion as C
    C.preparar_entorno()
    C.instalar()
    huella, hechas = _huella(), _leidas()
    print(f"\nVARIANTES, con la consigna {huella}:")
    for nombre in familias:
        # La nota se recalcula con lo guardado: corregir como se califica no pide volver a llamar al modelo.
        notas = [FAMILIAS[nombre]["nota"](hechas[(huella, nombre, f)]["respuesta"]) for f in FAMILIAS[nombre]["formas"]
                 if (huella, nombre, f) in hechas]
        n = len(FAMILIAS[nombre]["formas"])
        print(f"  {nombre:8} bien {notas.count('bien')}, pregunta {notas.count('pregunta')}, mal {notas.count('mal')}"
              f" — de {len(notas)} corridas de {n} formas · {FAMILIAS[nombre]['que']}")


def main(argv: list) -> int:
    sys.path.insert(0, os.path.dirname(AQUI))
    pedidas = [a for a in argv if a in FAMILIAS] or list(FAMILIAS)
    if "--informe" not in argv:
        correr(pedidas)
    informe(pedidas)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
