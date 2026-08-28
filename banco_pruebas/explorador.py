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
    cliente recibio, turno por turno, el reloj de cada uno, y si la corrida
    quedo SIN MEDIR por cuota.

    LO DE "SIN MEDIR" NO ES UN DETALLE, y es la leccion del 9-ago: si una
    corrida donde el modelo nunca contesto se promedia con las demas, el numero
    manda a arreglar codigo que ni siquiera corrio. Con la clave gratis y su
    cuota de 250.000 tokens por minuto eso pasa seguido, asi que se separa.

    FICHA 35: la ficha de aduana del explorador deja de existir. Sin mutador
    vivo no hay atajos que contar."""
    from app.core.llm_reintento import reiniciar_cupo, sin_cupo

    clon_produccion.reiniciar_cliente(uid)
    reiniciar_cupo()
    respuestas, tiempos = [], []
    for texto in charla["turnos"]:
        t0 = time.time()
        try:
            partes = await clon_produccion.turno(uid, texto)
        except Exception as e:  # noqa: BLE001 — una charla rota no corta la corrida
            partes = [f"[EXPLOTO] {type(e).__name__}: {e}"]
        tiempos.append(int((time.time() - t0) * 1000))
        respuestas.append("\n".join(partes))
    negadas = sin_cupo()
    return {**charla, "respuestas": respuestas, "ms": tiempos,
            "sin_medir": int(negadas["veces"]),
            "motivo": negadas["ultimo"][:80]}


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

    medidas = [c for c in corridas if not c.get("sin_medir")]
    for c in corridas:
        estado = f"{len(c['fallas'])} violaciones" if c["fallas"] else "limpia"
        if c.get("sin_medir"):
            estado += f"  ⚠ SIN MEDIR ({c['sin_medir']} llamadas negadas)"
        ad = c.get("aduana") or {}
        if ad.get("reparadas"):
            estado += f"  [aduana atajo {ad['reparadas']}]"
        lineas.append(f"── {c['guion']:<26} {len(c['respuestas'])} turnos, "
                      f"{estado}")
        for f in c["fallas"]:
            lineas.append(f"   turno {f['turno']:>2} [{f['paso']}] "
                          f"'{f['dijo'][:38]}'")
            lineas.append(f"      {f['regla']:<34} {f['detalle'][:90]}")
            # EL TEXTO QUE FALLO, o el hallazgo no se puede arreglar. Un numero
            # dice que algo esta mal; el mensaje dice QUE. Va sangrado y entero
            # hasta 600 caracteres, que alcanza para ver la cuenta duplicada.
            culpable = c["respuestas"][f["turno"] - 1]
            lineas += ["      ── lo que le llego al cliente:"] + [
                f"      | {l}" for l in culpable[:600].splitlines()]
    lineas.append("")

    largos = [len(r) for c in corridas for r in c["respuestas"]]
    todos_ms = [m for c in corridas for m in c["ms"]]
    atajadas = sum((c.get("aduana") or {}).get("reparadas", 0) for c in corridas)
    rojas = sum((c.get("aduana") or {}).get("rojas", 0) for c in corridas)
    medidas_f = [f for c in medidas for f in c["fallas"]]
    lineas += [
        "=" * 78,
        f"CHARLAS: {len(corridas)}   TURNOS: {turnos}   "
        f"VIOLACIONES: {len(todas)}",
        f"CHARLAS MEDIDAS: {len(medidas)} de {len(corridas)} "
        f"(las otras quedaron SIN MEDIR: al modelo no se le pudo hablar)",
        f"EL NUMERO — DEFECTOS POR CHARLA INVENTADA: "
        f"{(len(medidas_f) / len(medidas)) if medidas else 0:.2f}"
        f"   (solo sobre las medidas)",
        f"LA ADUANA ATAJO {atajadas} defectos antes de mandar, y marco "
        f"{rojas} en ROJO",
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
    ap.add_argument("--pausa", type=int, default=70,
                    help="segundos a esperar y repetir cuando la cuota gratis "
                         "corta una charla. 0 para no repetir.")
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
        # LA CUOTA DE LA GRATIS SE ESPERA, NO SE PAGA. Son 250.000 tokens de
        # entrada por minuto y un turno consume entre 18.000 y 35.000: correr
        # charlas pegadas la agota siempre. Si al modelo no se le pudo hablar,
        # se espera a que la ventana se renueve y se corre la charla de nuevo,
        # UNA vez. Es la diferencia entre una corrida que mide y una que no.
        if corrida["sin_medir"] and args.pausa:
            print(f"      cuota agotada ({corrida['sin_medir']} llamadas "
                  f"negadas). Espero {args.pausa}s y la repito.", flush=True)
            time.sleep(args.pausa)
            corrida = asyncio.run(correr(charla,
                                         f"explorador_{args.semilla}_{i}b"))
        corrida["fallas"] = juzgar(corrida, vocabulario)
        corridas.append(corrida)
        print(f"      {len(corrida['fallas'])} violaciones, "
              f"{sum(corrida['ms']) // 1000}s"
              + ("  SIN MEDIR" if corrida["sin_medir"] else ""), flush=True)

    salida = informe(corridas)
    print(salida)

    # EL REPORTE QUEDA EN DISCO, como el de la compuerta. El explorador corre
    # en el nocturno y su hallazgo tiene que sobrevivir al log del runner: sin
    # el archivo, el defecto se ve una vez y se pierde.
    corridas_dir = _RAIZ / "banco_pruebas" / "corridas"
    corridas_dir.mkdir(exist_ok=True)
    marca = time.strftime("%Y%m%d_%H%M")
    destino = corridas_dir / f"{marca}_explorador.md"
    detalle = ["", "## LAS CHARLAS, COMPLETAS", ""]
    for i, c in enumerate(corridas, 1):
        detalle.append(f"### {i}. {c['guion']}")
        for j, (dijo, dice) in enumerate(zip(c["turnos"], c["respuestas"]), 1):
            detalle += [f"**T{j} cliente:** {dijo}", "", f"```\n{dice}\n```", ""]
    destino.write_text("```\n" + salida + "\n```\n" + "\n".join(detalle),
                       encoding="utf-8")
    print(f"\nReporte: {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
