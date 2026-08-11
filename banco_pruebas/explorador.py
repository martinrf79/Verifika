"""
EL EXPLORADOR — la charla que NADIE escribio, corrida por el camino vivo.

POR QUE EXISTE (Martin, 11-ago-2026): "los errores se contabilizan y se miden,
pero luego de que pasan; hay que diagnosticarlos de antemano". Este archivo es
la mitad que faltaba para eso, y ataca la CEGUERA DE ESCENARIOS, que esta
medida y con nombre desde el 10-ago:

    Las dos reglas nuevas del componedor se dispararon CERO veces en los 176
    turnos de las 13 charlas grabadas, y en la charla REAL de Martin cortaron
    500 caracteres por turno. ¿Por que? Porque **ninguna charla grabada tenia a
    un cliente confirmando un pedido en varios turnos sin cambiar nada**, que es
    justo lo que hace un cliente de verdad. El banco medía preguntas; el defecto
    vivia en las confirmaciones.

Un guion escrito a mano solo prueba el escenario que alguien penso. Aca los
escenarios se ARMAN: se sortean productos REALES del catalogo de 880 y se
encadenan CONDUCTAS de cliente -agregar, sacar, repartir a dos destinos,
dividir el pago, confirmar dos veces sin cambiar nada, pedir descuento, dar el
nombre-. La charla que sale no la escribio nadie y por eso puede pegarle a un
hueco que nadie anticipo.

COMO SE JUZGA SIN RESPUESTA ESPERADA. Con los invariantes de
`app/verifika/invariantes.py`: propiedades que ninguna respuesta correcta viola
-que la cuenta cierre, que lo cobrado sea lo facturado, que el reparto cubra el
pedido, que nada se diga dos veces, que no se fugue una etiqueta interna-. No
hay que saber cual era la respuesta buena para saber que esa esta mal. Es lo
que permite juzgar una charla inventada al vuelo.

LA DIFERENCIA CON `produccion.py`, que es su hermano: aquel toma las charlas
REALES de Martin y las audita DESPUES; este las inventa ANTES. Los dos usan los
mismos invariantes. Uno mide lo que ya paso, el otro busca lo que va a pasar.

LA CLAVE: la GRATIS, siempre, que es la regla de la casa. `clon_produccion`
la elige solo. Su cuota es de 250.000 tokens de entrada por minuto -medido el
11-ago- y un turno consume entre 18.000 y 35.000, asi que el explorador corre
de a un turno y respeta el `retryDelay` que manda el proveedor. Si aparece un
429 se espera, no se gasta.

USO:
    python3 banco_pruebas/explorador.py                    # 4 charlas
    python3 banco_pruebas/explorador.py --charlas 8 --semilla 7
    python3 banco_pruebas/explorador.py --guion confirmacion_multiturno

EL NUMERO QUE DEJA: **defectos por charla inventada**. Es el mismo numero que
deja `produccion.py` sobre las charlas reales, a proposito: si el explorador da
cero y la charla real de Martin da defectos, el explorador no esta explorando
donde duele, y eso tambien es un dato.
"""
import argparse
import asyncio
import random
import sys
import time
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas import clon_produccion  # noqa: E402


# ── LAS CONDUCTAS. Lo que hace un cliente, no lo que pregunta ───────────────
#
# Cada una es (nombre, como se escribe el turno). Reciben el estado de la
# charla -que productos ya pidio, a donde va- y devuelven el texto del cliente.
# Escritas como escribe la gente: minuscula, sin tildes, con la pregunta
# pegada.
def _pedido_inicial(e):
    p = e["productos"][0]
    return f"hola, necesito {p['cantidad']} {p['que']}, cuanto me sale?"


def _sumar_producto(e):
    p = e["productos"][1] if len(e["productos"]) > 1 else e["productos"][0]
    return f"agregame tambien {p['cantidad']} {p['que']}"


def _sacar_producto(e):
    p = e["productos"][0]
    return f"pensandolo bien saca {p['que']} del pedido"


def _dos_destinos(e):
    return (f"lo de {e['destino_a']} mandalo ahi y el resto a "
            f"{e['destino_b']}, se puede?")


def _dividir_pago(e):
    return "podes dividir el pago 65 por transferencia y 35 con mercado pago?"


def _confirmar(e):
    return "me parece bien asi"


def _confirmar_otra_vez(e):
    return "okay te confirmo entonces"


def _pedir_descuento(e):
    return "y si pago todo por transferencia me haces algo de descuento?"


def _dar_nombre(e):
    return e["nombre"]


def _codigo_pelado(e):
    return f"tenes el {e['codigo']}?"


def _pregunta_de_rubro(e):
    return random.choice([
        "cuanto tarda el envio?",
        "aceptan cuotas sin interes?",
        "tienen garantia?",
        "hacen factura a?",
    ])


def _cambio_de_idea(e):
    p = e["productos"][-1]
    return f"me equivoque, en vez de eso poneme 2 {p['que']}"


CONDUCTAS = {
    "pedido_inicial": _pedido_inicial,
    "sumar_producto": _sumar_producto,
    "sacar_producto": _sacar_producto,
    "dos_destinos": _dos_destinos,
    "dividir_pago": _dividir_pago,
    "confirmar": _confirmar,
    "confirmar_otra_vez": _confirmar_otra_vez,
    "pedir_descuento": _pedir_descuento,
    "dar_nombre": _dar_nombre,
    "codigo_pelado": _codigo_pelado,
    "pregunta_de_rubro": _pregunta_de_rubro,
    "cambio_de_idea": _cambio_de_idea,
}

# ── LOS GUIONES DE CONDUCTA. El orden es lo que hace al escenario ───────────
#
# CONFIRMACION_MULTITURNO es el que reproduce el hueco del 10-ago y por eso va
# primero: es la charla que Martin tuvo de verdad y que ninguna grabada tenia.
GUIONES = {
    "confirmacion_multiturno": [
        "pedido_inicial", "sumar_producto", "dividir_pago",
        "confirmar", "confirmar_otra_vez", "dar_nombre"],
    "reparto_y_pago": [
        "pedido_inicial", "sumar_producto", "dos_destinos",
        "dividir_pago", "confirmar", "dar_nombre"],
    "cliente_que_cambia": [
        "pedido_inicial", "sumar_producto", "cambio_de_idea",
        "sacar_producto", "confirmar"],
    "regateo": [
        "pedido_inicial", "pregunta_de_rubro", "pedir_descuento",
        "confirmar", "dar_nombre"],
    "codigo_y_pedido": [
        "codigo_pelado", "pedido_inicial", "pregunta_de_rubro",
        "confirmar_otra_vez"],
}

_DESTINOS = ["Cordoba", "Rosario", "Mendoza", "La Plata", "Mar del Plata",
             "Salta", "Neuquen", "Tucuman"]
_NOMBRES = ["Jorge Campos", "Silvia Roldan", "Martin Perez", "Ana Diaz",
            "Luis Ferreyra"]


def _catalogo() -> list:
    from app.storage.firestore_client import get_all_products
    return get_all_products(tienda_id=clon_produccion.TIENDA)


def _escenario(rnd: random.Random, catalogo: list) -> dict:
    """El material de una charla: productos REALES del catalogo, cantidades,
    destinos y un nombre. Se sortea, no se escribe."""
    elegidos = rnd.sample(catalogo, k=min(3, len(catalogo)))
    productos = []
    for p in elegidos:
        nombre = str(p.get("nombre") or "").strip()
        # Como lo escribe un cliente: la categoria y dos palabras del nombre,
        # no el nombre completo con el codigo.
        corto = " ".join(nombre.split()[:3]) or str(p.get("categoria") or "")
        productos.append({"que": corto, "cantidad": rnd.choice([1, 1, 2, 3]),
                          "id": p.get("id"), "nombre": nombre})
    con_codigo = next((p for p in elegidos
                       if any(c.isdigit() for c in str(p.get("nombre") or ""))),
                      elegidos[0])
    codigo = next((w for w in str(con_codigo.get("nombre") or "").split()
                   if any(c.isdigit() for c in w)), "g203")
    a, b = rnd.sample(_DESTINOS, k=2)
    return {"productos": productos, "destino_a": a, "destino_b": b,
            "nombre": rnd.choice(_NOMBRES), "codigo": codigo}


def armar_charla(rnd: random.Random, catalogo: list, guion: str) -> dict:
    """Una charla completa: el escenario sorteado y los turnos del cliente."""
    e = _escenario(rnd, catalogo)
    pasos = GUIONES[guion]
    return {"guion": guion, "escenario": e,
            "turnos": [CONDUCTAS[p](e) for p in pasos], "pasos": list(pasos)}


# ── CORRER Y JUZGAR ─────────────────────────────────────────────────────────
async def correr(charla: dict, uid: str) -> dict:
    """La charla entera por el camino VIVO del webhook. Devuelve lo que el
    cliente recibio, turno por turno, y el reloj de cada uno."""
    clon_produccion.reiniciar_cliente(uid)
    respuestas, tiempos = [], []
    for texto in charla["turnos"]:
        t0 = time.time()
        try:
            partes = await clon_produccion.turno(uid, texto)
        except Exception as e:  # noqa: BLE001 — una charla rota no corta la corrida
            partes = [f"[EXPLOTO] {type(e).__name__}: {e}"]
        tiempos.append(int((time.time() - t0) * 1000))
        respuestas.append("\n".join(partes))
    return {**charla, "respuestas": respuestas, "ms": tiempos}


def juzgar(corrida: dict, vocabulario: set) -> list:
    """Los invariantes sobre la charla corrida. Sin respuesta esperada."""
    from app.verifika.invariantes import revisar_charla
    fallas = revisar_charla(corrida["respuestas"], vocabulario=vocabulario)
    for f in fallas:
        i = f["turno"] - 1
        f["dijo"] = corrida["turnos"][i] if i < len(corrida["turnos"]) else ""
        f["paso"] = corrida["pasos"][i] if i < len(corrida["pasos"]) else ""
    return fallas


def informe(corridas: list) -> str:
    lineas = ["", "=" * 78,
              "EL EXPLORADOR — charlas que nadie escribio, por el camino vivo",
              "=" * 78, ""]
    todas = [f for c in corridas for f in c["fallas"]]
    turnos = sum(len(c["respuestas"]) for c in corridas)
    fallback = sum(1 for c in corridas for r in c["respuestas"]
                   if clon_produccion.es_fallback(r) or "[EXPLOTO]" in r)

    for c in corridas:
        estado = f"{len(c['fallas'])} violaciones" if c["fallas"] else "limpia"
        lineas.append(f"── {c['guion']:<26} {len(c['respuestas'])} turnos, "
                      f"{estado}")
        for f in c["fallas"]:
            lineas.append(f"   turno {f['turno']:>2} [{f['paso']}] "
                          f"'{f['dijo'][:38]}'")
            lineas.append(f"      {f['regla']:<34} {f['detalle'][:90]}")
    lineas.append("")

    largos = [len(r) for c in corridas for r in c["respuestas"]]
    todos_ms = [m for c in corridas for m in c["ms"]]
    lineas += [
        "=" * 78,
        f"CHARLAS: {len(corridas)}   TURNOS: {turnos}   "
        f"VIOLACIONES: {len(todas)}",
        f"EL NUMERO — DEFECTOS POR CHARLA INVENTADA: "
        f"{(len(todas) / len(corridas)) if corridas else 0:.2f}",
        f"LARGO: promedio {sum(largos) // len(largos) if largos else 0}, "
        f"maximo {max(largos) if largos else 0} caracteres",
        f"RELOJ: mediana {sorted(todos_ms)[len(todos_ms) // 2] if todos_ms else 0} ms "
        f"por turno",
        f"TURNOS QUE NO CONTESTARON (enlatado o excepcion): {fallback}",
        "=" * 78]
    if todas:
        cuenta = {}
        for f in todas:
            cuenta[f["regla"]] = cuenta.get(f["regla"], 0) + 1
        lineas += ["", "POR REGLA, de la que mas duele para abajo:"]
        for regla, n in sorted(cuenta.items(), key=lambda x: -x[1]):
            lineas.append(f"  {n:>3}  {regla}")
    return "\n".join(lineas)


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description="Charlas inventadas por el camino vivo")
    ap.add_argument("--charlas", type=int, default=4)
    ap.add_argument("--semilla", type=int, default=11)
    ap.add_argument("--guion", default="", choices=[""] + list(GUIONES))
    args = ap.parse_args(argv)

    detalle = clon_produccion.preparar_entorno()
    info = clon_produccion.instalar()
    print(f"CLAVE: {detalle['clave']}   MODELO: {info.get('solver_model')}   "
          f"TIENDA: {info.get('tienda')}")

    catalogo = _catalogo()
    if not catalogo:
        print("Sin catalogo cargado: no hay con que armar una charla.")
        return 1
    rnd = random.Random(args.semilla)
    random.seed(args.semilla)
    guiones = ([args.guion] * args.charlas if args.guion
               else [list(GUIONES)[i % len(GUIONES)] for i in range(args.charlas)])

    from app.verifika.invariantes import _n  # noqa: F401 — misma normalizacion
    vocabulario = {str(p.get("nombre") or "") for p in catalogo if p.get("nombre")}

    corridas = []
    for i, g in enumerate(guiones, 1):
        charla = armar_charla(rnd, catalogo, g)
        print(f"\n[{i}/{len(guiones)}] {g}: "
              + " | ".join(t[:34] for t in charla["turnos"]), flush=True)
        corrida = asyncio.run(correr(charla, f"explorador_{args.semilla}_{i}"))
        corrida["fallas"] = juzgar(corrida, vocabulario)
        corridas.append(corrida)
        print(f"      {len(corrida['fallas'])} violaciones, "
              f"{sum(corrida['ms']) // 1000}s", flush=True)

    print(informe(corridas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
