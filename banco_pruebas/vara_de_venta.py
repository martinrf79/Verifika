"""
LA VARA DE VENTA — el primer numero que SUBE.

POR QUE EXISTE. La bateria tiene mas de mil tests y todos miden lo que el bot
EVITA: que no invente plata, que no omita un punto, que no repita, que no se
alargue, que no llame de mas al modelo. Todos los contadores del proyecto BAJAN.
Ninguno mide si la venta AVANZA. Un bot que contesta "no tengo ese dato" a las
quince charlas saca pleno en todos los pisos de hoy y no vende nada.

Esto mide lo otro: sobre los MISMOS quince casetes ya grabados, cinco cosas por
turno. Sin modelo y sin juez —todo sale del estado del turno mas el texto que
lee el cliente—, asi que corre gratis, sin clave y sin red, en cada push.

DE DONDE SALE CADA DATO, y ninguno se le pregunta al modelo:

  el carrito   del documento de conversacion del doble de Firestore, leido
               ANTES y DESPUES de cada turno. Es el estado que el turno guardo,
               no lo que el turno dice que guardo.
  el texto     las partes tal como las manda el conector de WhatsApp.
  los estados  de `hub_venta_ok`, la ficha del turno que el hub ya loguea:
               `estados` trae el censo terminal del indice —RESUELTO, AMBIGUO,
               NO_SE_SABE, CONFLICTO, SIN_ESTADO— sobre el texto FINAL.
               Se lee con `banco_pruebas/observador.py`, que es la misma
               ventana que en produccion es Cloud Logging.

LAS CINCO, y la definicion completa esta en la funcion que la calcula:

  1. AVANCE               el turno termina con carrito vivo, o mas grande.
  2. NO_SE_FRENA          con carrito, el texto propone el paso siguiente.
  3. EL_DETALLE_NO_MATA   con un punto en NO_SE_SABE, igual mantuvo y ofrecio.
  4. UNA_SOLA_REPREGUNTA  nunca dos preguntas al cliente en el mismo turno.
  5. CAMINO_AL_COBRO      la charla dice en algun momento COMO se paga.

ES UN PISO, NO UN TECHO, Y ESA ES LA DIFERENCIA CON TODO LO DEMAS DEL REPO.
`banco_pruebas/venta_piso.json` guarda los cinco crudos —`verdes` y `de`, no el
porcentaje— y `tests/test_vara_de_venta.py` no los deja BAJAR. Se comparan como
fracciones con enteros, sin redondear: un porcentaje redondeado deja pasar la
regresion de un turno, que es exactamente el agujero que el piso de los casetes
ya tuvo que tapar cambiando `piso` por `puntos`.

EL NUMERO DE HOY ES EL NUMERO DE HOY. Si sale feo, sale feo: la definicion no se
afloja para que de mejor. `--piso` se niega a escribir un numero mas bajo que el
guardado, que es el candado mecanico contra maquillarlo.

USO
    python3 banco_pruebas/vara_de_venta.py            # los cinco numeros
    python3 banco_pruebas/vara_de_venta.py --detalle  # turno por turno
    python3 banco_pruebas/vara_de_venta.py --piso     # refija, solo hacia arriba
"""
import asyncio
import contextlib
import json
import re
import sys
import unicodedata
from pathlib import Path

import structlog

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas import clon_produccion as clon  # noqa: E402

clon.preparar_entorno()

from banco_pruebas import observador, sim_firestore  # noqa: E402
from banco_pruebas.casete import CASETES, Casete, reproducir  # noqa: E402
from banco_pruebas.puntaje import leer_guion  # noqa: E402

PISO = Path(__file__).resolve().parent / "venta_piso.json"

# Las cinco, en el orden en que se leen. El nombre es la clave del piso.
LAS_CINCO = ("avance", "no_se_frena", "el_detalle_no_mata",
             "una_sola_repregunta", "camino_al_cobro")


def _n(texto: str) -> str:
    """Minusculas y sin acentos. `debito` y `débito` son la misma palabra, y el
    modelo escribe las dos."""
    crudo = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in crudo if unicodedata.category(c) != "Mn")


# ── LOS TRES MODOS DE OFRECER EL PASO SIGUIENTE ──────────────────────────────
#
# No es "el texto tiene un signo de pregunta". Con esa definicion casi todo
# turno sale verde y el numero no dice nada: el bot cierra casi siempre con una
# cortesia interrogativa. Lo que cuenta es que el turno ponga sobre la mesa algo
# con lo que el cliente pueda AVANZAR, y eso son tres cosas concretas.

# Un importe dicho. `$` pegado a un numero: es como sale del render de precio.
_RE_PRECIO = re.compile(r"\$\s?\d")

# La linea de total que arma la calculadora. Al principio de renglon, que es
# donde la escribe el componedor, para no confundirla con un "en total tenemos".
_RE_TOTAL = re.compile(r"(?im)^\s*\**\s*total\b")

# UNA ORACION. Corta en punto, salto, punto y coma, admiracion Y SIGNO DE
# PREGUNTA. El `¿` no corta: abre.
#
# EL SIGNO DE PREGUNTA TIENE QUE CORTAR, y aca no es un detalle: `indice_turno`
# a proposito NO corta en `?` —alla se busca en que oracion cae una pregunta— y
# copiar ese criterio hizo que "¿Te lo reservo? ¿A que direccion?" contara como
# UNA sola pregunta. O sea que el punto 4, que existe justo para cazar el turno
# que pregunta dos veces, no podia verlo. Se midio 54/55 con el criterio
# prestado y hubo que corregirlo antes de fijar el piso.
_RE_ORACION = re.compile(r"[^.\n;!?]+[.\n;!?]*")

# Que una pregunta sea DE CIERRE y no de cortesia: que hable de dar el paso.
# Raices cortas y literales a proposito —una lista larga de sinonimos convierte
# cualquier "¿te ayudo en algo mas?" en un cierre y tapa los turnos que frenan.
_CIERRE = ("confirm", "reserv", "avanz", "coordin", "abon", "pag", "cerr",
           "sum", "agreg", "llev", "envi", "despach", "te paso", "cotiz",
           "presupuesto", "total", "nombre", "direccion", "domicilio",
           "cuantas unidades", "cuantos queres", "seguimos")

# COMO SE PAGA. Son MEDIOS de pago, no el verbo pagar: "te lo podes llevar
# pagando" no le dice al cliente por donde entra la plata, y este punto es
# justo si el camino al cobro llego a decirse alguna vez en la charla.
#
# POR QUE SON DOS LISTAS Y NO UNA (FICHA 19, 25-ago-2026). Con una sola lista
# de palabras sueltas el detector contaba la palabra y no el hecho, y en una
# tienda de computacion esas palabras viven en el CATALOGO: `transferencia` es
# la velocidad de un disco, `tarjeta` es de video, `credito` es de una promo.
# Asi entro el falso positivo que inflo el piso a 9/15: `45_consigna_capciosas`
# contaba porque el bot habia escrito "velocidades de TRANSFERENCIA" hablando
# de discos rigidos. Un piso contaminado es peor que un piso bajo: dice que el
# bot hace algo que no hace, y nadie va a arreglar lo que el tablero da verde.
#
#   LITERALES   la palabra ya es del cobro y no significa otra cosa. `mercado
#               pago` es una marca, `transferencia bancaria` no es la de un
#               disco, y `medios de pago` nombra el eje entero.
#   AMBIGUOS    la misma palabra vive en el catalogo. Solo cuentan si la ORACION
#               en la que caen habla de plata, y esa es toda la diferencia
#               entre nombrar un medio y decir COMO SE PAGA.
_RE_COBRO_LITERAL = re.compile(
    r"mercado ?pago|link de pago|medios? de pago|formas? de pago|"
    r"contra ?reembolso|deposito bancario|transferencia bancaria")

_RE_COBRO_AMBIGUO = re.compile(
    r"\b(?:transferencias?|efectivo|tarjetas?|debito|credito|cuotas)\b")

# LA ORACION HABLA DE PLATA. Raices del acto de pagar, no del precio: `precio`
# y `descuento` quedan AFUERA a proposito, porque "la tarjeta de video tiene
# 10% de descuento" volveria a contar la tarjeta del catalogo como un medio de
# pago, que es el mismo defecto por otra puerta.
_RE_CTX_COBRO = re.compile(
    r"pago|paga|pagas|pagar|pagan|pagando|pagamos|pague|pagues|abon|cobr|"
    r"sena|deposit|acredit|transferir|transferis")


def _dice_como_se_paga(texto: str) -> bool:
    """Si en el texto se llego a decir POR DONDE ENTRA LA PLATA.

    El texto entra ya normalizado por `_n`. Se parte en oraciones con el mismo
    cortador que usa el punto 4 —que corta tambien en salto de linea, y por eso
    cada renglon del bloque de pago dividido se juzga solo— y una oracion
    cuenta si trae un literal, o si trae un ambiguo Y ademas habla de plata."""
    for oracion in _RE_ORACION.finditer(texto or ""):
        o = oracion.group(0)
        if _RE_COBRO_LITERAL.search(o):
            return True
        if _RE_COBRO_AMBIGUO.search(o) and _RE_CTX_COBRO.search(o):
            return True
    return False


def _preguntas(texto: str) -> list:
    """Las oraciones del mensaje que le preguntan algo al cliente, una por una.

    Se usa para las DOS cosas —contarlas y mirar si alguna es de cierre— porque
    si el detector viera las preguntas pegadas, una palabra de cierre de la
    primera le daria el verde a la segunda."""
    return [m.group(0) for m in _RE_ORACION.finditer(texto or "")
            if "?" in m.group(0)]


def _ofrece_paso(texto: str) -> str:
    """Con que ofrecio el paso siguiente, o cadena vacia si no ofrecio nada.
    Se devuelve CUAL de los tres para que el numero se pueda auditar sin
    volver a correr todo."""
    if _RE_TOTAL.search(texto or ""):
        return "total"
    if _RE_PRECIO.search(texto or ""):
        return "precio"
    for pregunta in _preguntas(texto):
        if any(v in _n(pregunta) for v in _CIERRE):
            return "pregunta_de_cierre"
    return ""


def _medir_turno(mensaje: str, texto: str, antes: int, despues: int,
                 estados: dict) -> dict:
    """Las cuatro varas POR TURNO. La quinta es de la charla entera."""
    ofrece = _ofrece_paso(texto)
    no_se_sabe = int((estados or {}).get("NO_SE_SABE") or 0)

    # 1. AVANCE. Verde si el turno termina con el carrito VIVO, o mas grande
    #    que cuando empezo. Perder el carrito es lo unico irreversible de una
    #    charla: todo lo demas se puede volver a preguntar. Un turno que empieza
    #    y termina sin carrito no avanzo la venta, y sale rojo aunque haya
    #    contestado perfecto: eso es lo que este numero viene a mostrar.
    avance = despues > 0 or despues > antes

    # 2. NO SE FRENA. Solo cuenta donde HAY carrito: sin carrito todavia no hay
    #    que cerrar. Con carrito, un turno que solo informa y no propone nada
    #    es rojo.
    frena_aplica = despues > 0
    no_frena = bool(ofrece) if frena_aplica else None

    # 3. EL DETALLE NO MATA. El requisito de arquitectura que nunca se midio:
    #    un dato que falta no puede tirar la venta. Cuenta solo donde algun
    #    punto quedo en NO_SE_SABE, y pide las dos cosas juntas —que el carrito
    #    no se haya achicado Y que igual se haya ofrecido algo—, porque
    #    cualquiera de las dos sola deja pasar el turno que se disculpa y corta.
    detalle_aplica = no_se_sabe > 0
    detalle_ok = (despues >= antes and bool(ofrece)) if detalle_aplica else None

    # 4. UNA SOLA REPREGUNTA. Dos preguntas en el mismo mensaje es pedirle al
    #    cliente que administre una agenda. Se cuentan oraciones con `?`, no
    #    signos: "¿si?" adentro de una oracion que ya pregunta es una sola.
    preguntas = len(_preguntas(texto))
    una_sola = preguntas <= 1

    return {"mensaje": (mensaje or "")[:60], "antes": antes, "despues": despues,
            "ofrece": ofrece, "no_se_sabe": no_se_sabe, "preguntas": preguntas,
            "avance": avance, "no_se_frena": no_frena,
            "el_detalle_no_mata": detalle_ok, "una_sola_repregunta": una_sola,
            "largo": len(texto or "")}


def _carrito(user: str) -> int:
    """Cuantos items tiene el pedido guardado. Se lee del documento, que es el
    estado que sobrevive al turno; lo que el turno diga de si mismo no cuenta."""
    for clave, doc in sim_firestore._CONV.items():
        if clave[1] == user:
            return len(doc.get("carrito_vigente") or [])
    return 0


def _casetes() -> list:
    return sorted(p for p in CASETES.glob("*.json") if not p.name.startswith("_"))


_instalado = False


@contextlib.contextmanager
def _escuchando():
    """El clon de produccion enganchado, y la ficha del turno capturada.

    EL ORDEN NO ES DECORATIVO: `clon.instalar()` importa `app.main`, que llama a
    `setup_logging()` y reconfigura structlog; si el observador se instala antes,
    esa llamada le pisa el processor de captura y la ficha del turno no se lee
    —la primera corrida de esto midio 55 turnos con el texto vacio por eso—.

    Y AL SALIR SE DEVUELVE LA CONFIGURACION QUE HABIA. Adentro de la bateria el
    `conftest` deja structlog callado a proposito; si esto lo dejara escuchando,
    los mil y pico de tests que corren despues pagarian el JSON de cada evento
    por una medicion que ya termino.
    """
    global _instalado
    if not _instalado:
        clon.instalar()
        _instalado = True
    previo = structlog.get_config()
    observador.instalar(consola=False)
    try:
        yield
    finally:
        structlog.configure(**previo)


def correr_charla(path: Path) -> dict:
    """Una charla grabada, turno por turno, con su estado y su texto.

    Es el mismo camino vivo que `casete.reproducir_charla` —el webhook real con
    el modelo reemplazado por su grabacion—; lo que cambia es que aca hace falta
    cortar POR TURNO para leer el carrito antes y despues y quedarse con la
    ficha de ese turno, y `reproducir_charla` devuelve la charla ya terminada.
    """
    datos = json.loads(Path(path).read_text(encoding="utf-8"))
    casete = Casete(Path(path).stem, datos.get("turnos") or [])
    guion = Path(path).resolve().parent.parent / "guiones" / f"{Path(path).stem}.txt"
    turnos = (leer_guion(guion.read_text(encoding="utf-8")) if guion.exists()
              else [{"mensaje": t.get("mensaje", "")} for t in casete.turnos])

    user = f"vara_venta_{Path(path).stem}"
    clon.reiniciar_cliente(user)
    filas: list = []
    textos: list = []

    async def _charla():
        for t in turnos:
            casete.abrir_turno(t["mensaje"])
            antes = _carrito(user)
            with observador.turno() as obs:
                partes = await clon.turno(user, t["mensaje"])
            texto = "\n".join(partes)
            fichas = [e for e in obs.eventos if e.get("event") == "hub_venta_ok"]
            # Sin ficha el turno exploto antes de cerrar: se mide igual con el
            # censo vacio. Tirarlo seria medir solo los turnos que salieron
            # bien, que es la forma mas facil de que un piso mienta para arriba.
            estados = dict(fichas[-1].get("estados") or {}) if fichas else {}
            textos.append(texto)
            filas.append(_medir_turno(t["mensaje"], texto, antes,
                                      _carrito(user), estados))

    with reproducir(casete):
        asyncio.run(_charla())

    # 5. CAMINO AL COBRO. Es de la CHARLA, no del turno: no se le puede pedir a
    #    cada mensaje que explique como se paga —seria repetirlo, que es lo que
    #    el objetivo 2 prohibe—. Lo que si se le pide a una charla que llego a
    #    tener un pedido es que en algun momento diga por donde entra la plata.
    cobro = _dice_como_se_paga(_n("\n".join(textos)))
    return {"nombre": Path(path).stem, "turnos": filas,
            "camino_al_cobro": cobro, "sin_ficha": sum(1 for f in filas
                                                       if not f["largo"])}


def medir(paths: list | None = None) -> dict:
    """Los cinco numeros crudos sobre el corpus entero."""
    with _escuchando():
        charlas = [correr_charla(p) for p in (paths or _casetes())]
    filas = [f for c in charlas for f in c["turnos"]]

    def _cuenta(clave):
        aplican = [f for f in filas if f[clave] is not None]
        return {"verdes": sum(1 for f in aplican if f[clave]), "de": len(aplican)}

    fuera = {k: _cuenta(k) for k in LAS_CINCO[:4]}
    fuera["camino_al_cobro"] = {
        "verdes": sum(1 for c in charlas if c["camino_al_cobro"]),
        "de": len(charlas)}
    for k in LAS_CINCO:
        d = fuera[k]
        d["pct"] = round(100.0 * d["verdes"] / d["de"], 1) if d["de"] else None
    fuera.update({"charlas": len(charlas), "turnos": len(filas),
                  "_charlas": charlas, "_filas": filas})
    return fuera


def peor(res: dict) -> str:
    """Cual de las cinco esta peor. Con `de` en cero no se compara: un numero
    sin denominador no es peor ni mejor, es que no se midio."""
    con_datos = [(res[k]["verdes"] / res[k]["de"], k) for k in LAS_CINCO
                 if res[k]["de"]]
    return min(con_datos)[1] if con_datos else ""


# ── el piso ──────────────────────────────────────────────────────────────────

def leer_piso() -> dict:
    return json.loads(PISO.read_text(encoding="utf-8")) if PISO.exists() else {}


def _mejor(nuevo: dict, viejo: dict) -> tuple:
    """Compara dos fracciones con ENTEROS, sin redondear: `a/b >= c/d` es
    `a*d >= c*b`. Un porcentaje redondeado deja pasar la regresion de un turno,
    y eso ya se pago una vez en el piso de los casetes."""
    if not viejo or not viejo.get("de"):
        return True, "primera medicion"
    a, b = nuevo["verdes"], nuevo["de"]
    c, d = viejo["verdes"], viejo["de"]
    if a * d >= c * b:
        return True, f"{c}/{d} -> {a}/{b}"
    return False, f"BAJA {c}/{d} -> {a}/{b}"


def escribir_piso(res: dict) -> dict:
    """Refija el piso HACIA ARRIBA. Una medicion mas baja no se escribe: el piso
    es lo unico que impide que la definicion se afloje de a poco."""
    viejo = leer_piso()
    nuevo = {k: {"verdes": res[k]["verdes"], "de": res[k]["de"]}
             for k in LAS_CINCO}
    rechazados = []
    for k in LAS_CINCO:
        ok, motivo = _mejor(nuevo[k], (viejo.get(k) or {}))
        print(f"  {k:22s} {motivo}")
        if not ok:
            nuevo[k] = viejo[k]
            rechazados.append(k)
    nuevo.update({
        "charlas": max(res["charlas"], int(viejo.get("charlas") or 0)),
        "turnos": max(res["turnos"], int(viejo.get("turnos") or 0)),
        "_doc": (
            "EL PISO DE VENTA, Y SOLO SUBE. Al reves de los techos del repo, "
            "que solo bajan. Guarda `verdes` y `de` crudos, no el porcentaje: "
            "el test compara fracciones con enteros y una regresion de un solo "
            "turno no se puede esconder redondeando. `turnos` y `charlas` son "
            "la afirmacion de CUANTO se midio; sin ellas el test podria pasar "
            "por vacio, que es como el CI estuvo verde cinco dias sin correr "
            "un casete. Se refija con `python3 banco_pruebas/vara_de_venta.py "
            "--piso`, que se NIEGA a escribir un numero mas bajo.")})
    if rechazados:
        print(f"  NO SE ESCRIBIERON (bajaban): {', '.join(rechazados)}")
    PISO.write_text(json.dumps(nuevo, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")
    return nuevo


def _main() -> int:
    res = medir()
    if "--detalle" in sys.argv:
        for c in res["_charlas"]:
            print(f"\n{c['nombre']}  cobro:{'SI' if c['camino_al_cobro'] else 'NO'}")
            for i, f in enumerate(c["turnos"], 1):
                marca = "".join(
                    ("." if f[k] is None else ("v" if f[k] else "X"))
                    for k in LAS_CINCO[:4])
                print(f"  t{i:<2} [{marca}] carrito {f['antes']}->{f['despues']} "
                      f"ofrece:{f['ofrece'] or '-':18s} ns:{f['no_se_sabe']} "
                      f"preg:{f['preguntas']}  {f['mensaje']}")
    print(f"\nLA VARA DE VENTA — {res['charlas']} charlas, {res['turnos']} turnos")
    for k in LAS_CINCO:
        d = res[k]
        print(f"  {k:22s} {d['verdes']:4d}/{d['de']:<4d}  "
              f"{'sin denominador' if d['pct'] is None else str(d['pct']) + '%'}")
    print(f"  PEOR: {peor(res)}")
    if "--piso" in sys.argv:
        print("\nrefijando el piso:")
        escribir_piso(res)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
