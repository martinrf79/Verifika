"""
EL CANDADO QUE VALE MAS QUE UNA FICHA — una excepcion atrapada y seguida de
largo (FICHA 19, 25-ago-2026).

LOS DOS PEORES DEFECTOS QUE ENCONTRAMOS ENTRARON POR LA MISMA PUERTA:

  EL CRASHER DE COMPATIBILIDAD. La pieza explotaba, la puerta devolvia el texto
  tal como habia entrado, y al cliente le llegaba el enlatado. La bateria
  entera en verde: nadie estaba mirando.

  EL `(?i)` DEL COMPONEDOR. Los mensajes se alargaban turno a turno y ningun
  test se puso rojo. Lo encontro una persona leyendo una charla.

LOS DOS COMPARTEN LA FORMA, y no el modulo: algo salio mal, alguien lo atrapo,
y el turno siguio como si nada. El control que esa pieza ERA no corrio, y el
cliente leyo lo que la guardia tenia que haber arreglado. Esa es la unica falla
del repo que se puede reintroducir sin escribir una linea de logica nueva:
alcanza con un `except` de mas.

LA REGLA, y es de las duras: **una guardia de salida o registra la excepcion
con nombre y sale ROJA en la bateria, o no la atrapa.** No hay tercera opcion,
y no la hay porque la tercera opcion es exactamente lo que ya paso dos veces.

ESTE ARCHIVO LA CIERRA POR LOS DOS LADOS, porque uno solo no alcanza:

  LA MITAD VIVA mira lo que PASO. Corre el corpus por el camino vivo y exige
  que el censo del grafo no tenga NI UN `levanto:`. La marca existia desde
  siempre —`G.paso` la deja— pero vivia en una lista de detalles de la que
  ningun test afirmaba nada, o sea que estaba escrita y nadie la leia. Ahora es
  un numero, y el numero tiene que ser cero.

  LA MITAD ESTATICA mira lo que PODRIA pasar. La viva solo ve las excepciones
  que el corpus provoca, y el corpus no provoca las que importan: si lo
  hiciera, ya las habriamos visto. Asi que se lee el CODIGO de las guardias de
  salida y se cuenta cuantos `except` no dejan rastro. Hoy son CERO y el techo
  dice cero: el proximo que se escriba pone el push en rojo antes de correr.
"""
import ast
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))


# ── LA MITAD ESTATICA ───────────────────────────────────────────────────────

# LAS GUARDIAS DE SALIDA: los modulos que tocan el texto que el cliente lee.
# Es una lista escrita a mano a proposito y el test afirma su largo: deducirla
# —"todo lo que importe salida"— la dejaria envejecer sin que nadie lo note,
# que es la misma ceguera que este archivo viene a cerrar.
_GUARDIAS = (
    "app/core/salida.py",          # las cuatro puertas y sus piezas
    "app/core/atadura_prosa.py",   # cada afirmacion atada a su producto
    "app/core/guardas_salida.py",  # identidad, saludo, honestidad de bot
    "app/core/guia_venta_prosa.py",  # el texto fijo que sale tal cual
    "app/core/mensaje.py",         # el componedor: el del `(?i)`
    "app/core/camino_cobro.py",    # como se paga, y ninguna cuenta inventada
    "app/core/cierre.py",          # los datos del cliente y el cobro
)

# QUE CUENTA COMO DEJAR RASTRO. Un log de `warning` o peor, o una marca en el
# grafo. `info` NO alcanza y no es un capricho: un `info` no se mira, y el
# punto entero de este candado es que la marca se vea. Re-levantar tambien
# vale: la excepcion sigue viaje y el turno la ve.
_DEJA_RASTRO = frozenset({"warning", "error", "exception", "critical",
                          "registrar", "veredicto", "anotar"})

# EL TECHO, Y SOLO BAJA. Cero es cero: no hay ningun `except` mudo en las siete
# guardias, asi que el primero que aparezca es un rojo. Si alguna vez hay que
# subirlo, se sube A MANO, en su propio commit, con el motivo escrito.
# FICHA 35: salio app/core/aduana.py. Eran 8, ahora 7.
_TECHO_MUDOS = 0


def _deja_rastro(cuerpo) -> bool:
    for n in ast.walk(cuerpo):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        nombre = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
        if nombre in _DEJA_RASTRO:
            return True
    return False


def _funcion_de(nodo, padres) -> str:
    q = nodo
    while q in padres:
        q = padres[q]
        if isinstance(q, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return q.name
    return "(nivel de modulo)"


def _censo_de_except() -> tuple:
    """(todos, mudos). Un `except` es MUDO si no re-levanta y no deja rastro."""
    todos, mudos = [], []
    for ruta in _GUARDIAS:
        p = _RAIZ / ruta
        assert p.exists(), f"{ruta} no existe: la lista de guardias envejecio"
        arbol = ast.parse(p.read_text(encoding="utf-8"))
        padres = {h: n for n in ast.walk(arbol) for h in ast.iter_child_nodes(n)}
        for n in ast.walk(arbol):
            if not isinstance(n, ast.ExceptHandler):
                continue
            ficha = (ruta, n.lineno, _funcion_de(n, padres),
                     ast.unparse(n.type) if n.type else "bare")
            todos.append(ficha)
            cuerpo = ast.Module(body=n.body, type_ignores=[])
            if any(isinstance(x, ast.Raise) for x in ast.walk(cuerpo)):
                continue
            if _deja_rastro(cuerpo):
                continue
            mudos.append(ficha)
    return todos, mudos


def test_ninguna_guardia_de_salida_se_traga_una_excepcion_en_silencio():
    """EL CANDADO ESTATICO. Se lee el codigo, no se espera a que reviente."""
    todos, mudos = _censo_de_except()
    print(f"\n  se leyeron {len(_GUARDIAS)} guardias y {len(todos)} except")
    assert not mudos or len(mudos) <= _TECHO_MUDOS, (
        f"hay {len(mudos)} `except` que atrapan y siguen de largo, y el techo "
        f"es {_TECHO_MUDOS}:\n  "
        + "\n  ".join(f"{r}:{l} en {f}()  except {t}" for r, l, f, t in mudos)
        + "\n\nO registra con nombre —log.warning/error, o una marca en el "
          "grafo— o no la atrapa. Las dos veces que este repo se comio un "
          "defecto grande fue por esta puerta.")


def test_el_censo_de_except_no_puede_pasar_por_vacio():
    """SOBRE CUANTOS CORRIO. Sin esto el candado se pone verde el dia que la
    lista de guardias quede vacia o el parser deje de encontrar handlers, que
    es la forma en que los candados de este repo ya se murieron dos veces."""
    todos, _ = _censo_de_except()
    assert len(_GUARDIAS) == 7, (
        f"la lista de guardias tiene {len(_GUARDIAS)} modulos y estaban "
        "escritos 7. FICHA 35: salio aduana.py. Si una guardia se suma o se "
        "muda, el numero se cambia a mano y el commit dice cual")
    assert len(todos) >= 14, (
        f"solo se encontraron {len(todos)} except en las siete guardias: el "
        "censo esta mirando mal y todo lo de arriba pasa por vacio. FICHA 35: "
        "el piso era 15 con aduana (3 except ahi + 1 en higiene); ahora 14")


def test_el_techo_de_mudos_es_cero_y_esta_escrito():
    """EL TECHO ES UN NUMERO ESCRITO, no una lista de excepciones toleradas.
    Con cero no hay nada que perdonar, y esa es la unica forma en que la regla
    no se erosiona de a una."""
    assert _TECHO_MUDOS == 0


# ── LA MITAD VIVA ───────────────────────────────────────────────────────────

def test_ningun_engranaje_levanta_corriendo_el_corpus(firestore_doble):
    """EL CANDADO VIVO. Las quince charlas por el camino vivo, y el censo del
    grafo tiene que cerrar con `levantes` VACIO.

    `G.paso` marca `levanto:X` cuando una pieza explota, devuelve el texto tal
    como entro y sigue. Eso es lo correcto en vivo —una guardia rota no puede
    dejar mudo al bot— pero en la BATERIA tiene que ser rojo: significa que el
    control no corrio y que el cliente leyo lo que esa pieza iba a arreglar."""
    from banco_pruebas import clon_produccion as clon
    clon.preparar_entorno()
    from banco_pruebas import vara_de_venta as vara
    from app.verifika import grafo as G

    G.censo_reiniciar()
    with vara._escuchando():
        res = vara.medir()
    censo = G.censo()

    print(f"\n  se corrieron {res['charlas']} charlas y {res['turnos']} turnos, "
          f"{censo['nodos_medidos']} engranajes")
    # CUANTO SE MIDIO, primero y como asercion: sin esto `levantes` vacio es
    # indistinguible de no haber corrido nada.
    assert res["charlas"] >= 15 and res["turnos"] >= 55, (
        f"se midieron {res['charlas']} charlas y {res['turnos']} turnos: el "
        "corpus no entro entero y el candado estaria pasando por vacio")
    # 54 Y NO 55, Y ESTA MEDIDO: de los 55 turnos del corpus hay UNO que no
    # llega a `abrir_turno` porque se corta antes del hub. Es el numero con el
    # que el censo del grafo viene contando desde la FICHA 12 y el que dice
    # PENDIENTE; escribir 55 aca pondria rojo un candado por un turno que
    # ninguna guardia toca.
    assert censo["turnos"] >= 54, (
        f"el grafo conto {censo['turnos']} turnos: no esta midiendo")
    assert censo["nodos_medidos"] > 30, (
        f"el grafo midio {censo['nodos_medidos']} engranajes: son demasiado "
        "pocos, el censo no esta viendo la cadena entera")

    assert not censo["levantes"], (
        "estos engranajes LEVANTARON y el turno siguio de largo:\n  "
        + "\n  ".join(f"{k}: {', '.join(v[:4])}"
                      for k, v in censo["levantes"].items())
        + "\n\nCada uno es un control que NO corrio sobre el mensaje que leyo "
          "el cliente. Es la forma exacta del crasher de compatibilidad.")


def test_el_censo_de_levantes_ve_de_verdad():
    """QUE EL CANDADO VIVO NO SEA UN ADORNO. Si `levantes` no se llenara nunca,
    el test de arriba estaria verde para siempre sin mirar nada. Aca se rompe
    una pieza a proposito y se comprueba que el censo la ve, con su nombre y
    con el tipo de la excepcion."""
    from app.verifika import grafo as G

    G.censo_reiniciar()
    G.abrir_turno()

    def _explota(texto):
        raise ValueError("a proposito")

    salida = G.paso("probeta_del_candado", _explota, "el texto que entro")
    censo = G.censo()

    assert salida == "el texto que entro", (
        "en vivo una guardia rota NO puede dejar mudo al bot: devuelve el "
        "texto como entro. Eso no cambia, lo que cambia es que ahora se cuenta")
    assert censo["levantes"] == {"probeta_del_candado": ["ValueError"]}, (
        f"el censo no vio el levante: {censo['levantes']}")
    G.censo_reiniciar()
