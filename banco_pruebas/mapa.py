"""
EL MAPA DE CONEXIONES — que parte del codigo trabaja para que pregunta.

QUE PROBLEMA RESUELVE, dicho por Martin el 5-ago: "cada vez que empezas un
arreglo te encontras con cosas que no funcionan, desconectadas o conectadas a
medias, y los arreglos se pisan entre si". Eso no se arregla leyendo mejor: se
arregla midiendo. La pregunta exacta era: son X conexiones, cuales funcionan
para todas las preguntas, cuales para algunas, y cuales no se usan nunca.

COMO SE CONTESTA, y son dos medidas que se cruzan:

  1. ALCANCE, estatico. Desde el webhook de WhatsApp y el de Telegram, a que
     funciones se puede llegar. Lo que no se alcanza no corre en produccion,
     por mas que este escrito y tenga tests.
  2. EJERCICIO, dinamico, y son TRES familias. LAS 40 -la parte de codigo de
     cada pregunta de Martin- y LAS CHARLAS GRABADAS -el turno completo por el
     camino del webhook, con el modelo reemplazado por su casete- corren cada
     una con su propio contexto: de ahi sale la matriz funcion x prueba, que es
     la que contesta "¿a quien rompo si toco esto?". Y LA BATERIA OFFLINE
     entera corre aparte, como un solo contexto, porque para la zona ciega la
     pregunta no es cual test la toca sino si la toca ALGUNO: sin esta tercera
     pasada, 35 funciones figuraban ciegas teniendo prueba escrita, nueve de
     ellas en `pago.py`, o sea la plata.

Del cruce salen las cuatro cubetas:

  TRONCAL             la usan muchas pruebas. Tocarla es caro: si se rompe, se
                      cae medio sistema y hay que mirarla con cuidado.
  DE ALGUNAS          la usan una o dos. Se puede tocar, con la lista de
                      dependientes delante.
  VIVA Y SIN EJERCITAR  corre en produccion y NINGUNA prueba la toca. Es LA
                      ZONA CIEGA: de aca salieron todas las sorpresas de cada
                      sesion. Medida el 5-ago daba 143 de 304, el 47%, con el
                      hub entero adentro; con las charlas grabadas al dia bajo
                      a 37 de 315, el 12%. El 13-ago ese 12% resulto ser
                      MENTIRA DEL INSTRUMENTO -ver abajo-. El numero del dia lo
                      imprime el propio mapa; no se copia a ningun documento.
  SIN ALCANCE         no se llega desde ningun webhook. Candidata a borrar, con
                      el ojo puesto: puede ser de un endpoint de admin o de un
                      banco.

EL 13-AGO EL INSTRUMENTO MEDIA MAL, y conviene saber como para no repetirlo. La
linea del `def` se EJECUTA al importar el modulo. El mapa contaba cada funcion
desde esa linea, asi que un modulo que entraba por primera vez con un contexto
de cobertura prendido quedaba entero marcado como ejercitado sin que nadie lo
llamara. Quedaban tapados `main.py`, los dos conectores y `pago.py` enteros:
modulos que las 40 y los casetes IMPORTAN y no ejecutan. Ademas el numero
dependia del orden de los imports: el dia que `las_40` empezo a importar
`app.verifika` un poco antes, ocho funciones de `llm_adapter` cayeron fuera de
todo contexto, aparecieron ciegas de golpe y el nocturno quedo tres noches en
rojo sin que cambiara una linea de esas funciones. Hoy se mide desde el CUERPO
de la funcion, los corredores se arman ANTES de prender la cobertura, y
`tests/test_mapa.py::test_importar_un_modulo_no_lo_da_por_ejercitado` lo
defiende en cada push.

LA REGLA QUE LO VUELVE UTIL, y sale del paper de evaluacion por capas: una capa
que no se ejercita NO PUNTUA. Por eso el marcador de 40 de 40 no significaba lo
que parecia: media una capa sola. El piso de este mapa -`mapa_piso.json`- guarda
la zona ciega de hoy, y `tests/test_mapa.py` falla si CRECE. No exige que sea
cero, que seria mentir sobre el estado: exige que no empeore.

LIMITE, dicho sin maquillar. El alcance se calcula por NOMBRE de funcion, no
resolviendo el import: si dos modulos tienen una funcion que se llama igual,
las dos cuentan como alcanzadas. Sobre-estima el alcance a proposito, para no
declarar muerto algo que esta vivo. Y la cobertura dice QUE SE EJECUTA, nunca
si esta bien: el mapa localiza la zona ciega, no la arregla.

    python3 banco_pruebas/mapa.py            # el mapa
    python3 banco_pruebas/mapa.py --fijar    # ademas graba el piso
"""
import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

APP = _RAIZ / "app"
PISO = Path(__file__).resolve().parent / "mapa_piso.json"

# Las raices del camino VIVO del cliente: por aca entra un mensaje real.
RAICES = ("whatsapp_webhook", "_process_and_reply_whatsapp",
          "telegram_webhook", "_process_and_reply_telegram", "process_message")

# Las raices de ADMIN. No son el camino del cliente, pero tampoco son codigo
# muerto: se separan para que no ensucien la cuenta.
RAICES_ADMIN = ("upload_catalog", "upload_faq", "health_tienda", "health",
                "root", "diag_latencia")

# Cuantas preguntas hacen falta para llamarla troncal. No es magia: es el corte
# donde una funcion deja de servir a un caso y pasa a sostener el sistema.
TRONCAL = 8


# ── 1. EL INVENTARIO Y EL ALCANCE, por AST ──────────────────────────────────
def inventario() -> dict:
    """{clave: {modulo, nombre, ini, cuerpo, fin, llama}} para toda funcion.

    `ini` es la linea del `def`; `cuerpo`, la primera linea de ADENTRO. La
    diferencia no es cosmetica y costo tres rojos del nocturno: la linea del
    `def` se EJECUTA al importar el modulo, asi que si el modulo entra por
    primera vez mientras hay un contexto de cobertura prendido, TODAS sus
    funciones quedan marcadas como ejercitadas sin que nadie las llame. La
    medicion pasa a mirar solo el cuerpo."""
    fuera = {}
    for py in sorted(APP.rglob("*.py")):
        if "__pycache__" in str(py):
            continue
        try:
            arbol = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        mod = str(py.relative_to(_RAIZ))
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            llama = set()
            for hijo in ast.walk(nodo):
                if isinstance(hijo, ast.Call):
                    f = hijo.func
                    if isinstance(f, ast.Name):
                        llama.add(f.id)
                    elif isinstance(f, ast.Attribute):
                        llama.add(f.attr)
            fuera[f"{mod}:{nodo.name}"] = {
                "modulo": mod, "nombre": nodo.name, "ini": nodo.lineno,
                "cuerpo": nodo.body[0].lineno if nodo.body else nodo.lineno,
                "fin": getattr(nodo, "end_lineno", nodo.lineno),
                "llama": llama}
    return fuera


def alcanzables(inv: dict, raices: tuple) -> set:
    """Las claves a las que se llega desde las raices, siguiendo por NOMBRE.

    Se sigue por nombre y no resolviendo el import a proposito: este repo hace
    imports adentro de las funciones en casi todos los modulos, asi que un
    grafo 'exacto' seria mas falso que este. Sobre-estimar el alcance es el
    error seguro: como mucho deja una funcion muerta adentro del mapa, nunca al
    reves."""
    por_nombre: dict = {}
    for clave, f in inv.items():
        por_nombre.setdefault(f["nombre"], []).append(clave)
    vistos, cola = set(), []
    for r in raices:
        cola.extend(por_nombre.get(r, []))
    while cola:
        clave = cola.pop()
        if clave in vistos:
            continue
        vistos.add(clave)
        for nom in inv[clave]["llama"]:
            for otra in por_nombre.get(nom, []):
                if otra not in vistos:
                    cola.append(otra)
    return vistos


# ── 2. EL EJERCICIO: LAS 40, una por una, con su propio contexto ────────────
def _corredores() -> list:
    """(id de la prueba, funcion que la ejercita). Dos familias, y hacen falta
    las dos:

      LAS 40   la parte de codigo de cada pregunta de Martin, con la llamada
               ideal escrita a mano. Miden la HERRAMIENTA.
      CASETES  las charlas grabadas, corridas enteras por el camino del webhook
               con el modelo reemplazado por su grabacion. Miden EL TURNO: el
               bucle, el reconciliador, las guardas de salida y el corte en
               partes, que es todo lo que las 40 no tocan.

    Sin los casetes, el mapa marcaba el hub entero como zona ciega y tenia
    razon. Con ellos, lo que quede ciego es lo que de verdad no prueba nadie."""
    from banco_pruebas.las_40 import LAS_40
    from banco_pruebas import banco_candidatos as BC
    from banco_pruebas import banco_memoria as BM
    from banco_pruebas.casete import CASETES as DIR_CASETES, reproducir_charla

    series = {"Serie 1": BM.serie_1, "Serie 3": BM.serie_3,
              "Serie 15": BM.serie_15, "Contexto": BM.medidas_de_contexto}
    fuera = []
    for id_, _nombre, _fuente, mide in LAS_40:
        if callable(mide):
            fuera.append((id_, mide))
        elif mide[0] == "candidatos":
            fuera.append((id_, BC.CASOS[mide[1] - 1]))
        else:
            fuera.append((id_, series.get(mide[1], lambda: None)))
    for casete in sorted(DIR_CASETES.glob("*.json")):
        if casete.name.startswith("_"):
            continue
        fuera.append((f"casete:{casete.stem}",
                      lambda p=casete: reproducir_charla(p)))
    return fuera


def _la_bateria(tmp: Path) -> dict:
    """{archivo: {linea: ["bateria"]}} — lo que toca la bateria offline entera.

    LA SEGUNDA PASADA, y es la que faltaba. El mapa preguntaba "¿que funcion
    usa cada una de las 40?", que es la pregunta fina y sirve para saber a
    quien rompes si tocas algo. Pero para la ZONA CIEGA la pregunta es otra y
    mas simple: **¿la toca alguien?**. Con solo las 40 y los casetes, 35
    funciones figuraban ciegas teniendo prueba escrita — nueve de ellas en
    `pago.py`, o sea la plata. El mapa decia "nadie la prueba" de codigo que
    `tests/test_pago.py` prueba desde hace semanas.

    CORRE EN UN SUBPROCESO, con su propio archivo de datos, por la misma razon
    por la que `tests/test_mapa.py` corre el mapa afuera: medio sistema cachea,
    y una bateria arrancada despues de las 40 mediria de menos. Aparte, pytest
    adentro del mismo proceso se pisa con los imports ya hechos.

    SIN LOS `pesado`. Los cinco barridos que recorren la fuente entera -880
    productos por 7 formas, 16.164 localidades, 41 campos por 5 operadores- bajo
    el tracing de cobertura pasan de segundos a horas: medido, la corrida quedo
    en el 17% despues de veinte minutos. No se pierde nada: barren certificador,
    geo, FAQ, compatibilidad y filtros, que ya son troncales por las 40."""
    datos_bateria = tmp / "cobertura_bateria"
    r = subprocess.run(
        [sys.executable, "-m", "coverage", "run",
         f"--data-file={datos_bateria}", f"--source={APP}",
         "-m", "pytest", "-q", "-p", "no:randomly",
         "-m", "not vivo and not lento and not pesado",
         # LO QUE LA PASADA 1 YA CORRE NO SE CORRE DOS VECES. `test_las_40` y
         # `test_charlas_grabadas` son exactamente los corredores de arriba, y
         # arriba entran con contexto propio, que es mejor: dicen CUAL prueba.
         # Repetirlos aca no suma un dato y se lleva la mitad del reloj -son
         # los cuatro tests mas lentos de la bateria y replayan turnos enteros-.
         "--ignore=tests/test_las_40.py",
         "--ignore=tests/test_charlas_grabadas.py"],
        capture_output=True, text=True, timeout=2700, cwd=str(_RAIZ))
    if not datos_bateria.exists():
        print(f"AVISO: la bateria no dejo cobertura ({r.returncode}). "
              f"El mapa mide solo las 40 y los casetes.\n{r.stdout[-800:]}")
        return {}
    import coverage
    d = coverage.CoverageData(str(datos_bateria))
    d.read()
    return {arch: {ln: ["bateria"] for ln in (d.lines(arch) or [])}
            for arch in d.measured_files()}


def ejercicio(tmp: Path | None = None) -> dict:
    """{archivo: {linea: [preguntas que la ejecutaron]}}."""
    import coverage
    # LOS CORREDORES SE ARMAN ANTES DE PRENDER LA COBERTURA. Armarlos adentro
    # metia los imports de `banco_pruebas` -que arrastran medio `app/`- en la
    # ventana de medicion, y de que modulo entrara primero dependia el numero.
    # Afuera, el punto de partida es el mismo siempre.
    corredores = _corredores()
    # `check_preimported` apagado a proposito: los modulos ya estan importados
    # cuando esto arranca, asi que las lineas de nivel de modulo no se miden. No
    # importa: lo que se mide aca son los CUERPOS de las funciones, que se
    # ejecutan despues. Prendido, el aviso sale 18 veces y tapa el resultado.
    cov = coverage.Coverage(data_file=None, source=[str(APP)],
                            check_preimported=False)
    cov.start()
    try:
        for id_, fn in corredores:
            cov.switch_context(id_)
            try:
                fn()
            except Exception:
                # Una pregunta que revienta igual dejo su rastro hasta donde
                # llego, y el rojo ya lo reporta el marcador. Aca no se juzga.
                pass
    finally:
        cov.stop()
    datos = cov.get_data()
    fuera = {}
    for archivo in datos.measured_files():
        try:
            fuera[archivo] = datos.contexts_by_lineno(archivo)
        except Exception:
            continue
    # LA SEGUNDA PASADA SE FUSIONA ACA. La bateria entra como UN contexto,
    # `bateria`: para la lista de dependientes no aporta -no dice cual test es-
    # pero para la zona ciega es lo unico que importa, que alguien la toque.
    with tempfile.TemporaryDirectory() as td:
        for archivo, lineas in _la_bateria(tmp or Path(td)).items():
            destino = fuera.setdefault(archivo, {})
            for ln, ctxs in lineas.items():
                destino.setdefault(ln, []).extend(ctxs)
    return fuera


def preguntas_por_funcion(inv: dict, cob: dict) -> dict:
    """{clave de funcion: set de preguntas que la ejecutaron}."""
    por_archivo: dict = {}
    for clave, f in inv.items():
        por_archivo.setdefault(str(_RAIZ / f["modulo"]), []).append(clave)
    fuera = {clave: set() for clave in inv}
    for archivo, lineas in cob.items():
        for clave in por_archivo.get(str(Path(archivo).resolve()), []):
            f = inv[clave]
            for ln, ctxs in lineas.items():
                # Desde el CUERPO, no desde el `def`: ver `inventario`.
                if f["cuerpo"] <= ln <= f["fin"]:
                    fuera[clave] |= {c for c in ctxs if c}
    return fuera


# ── 3. LAS CUATRO CUBETAS ───────────────────────────────────────────────────
def mapa() -> dict:
    inv = inventario()
    vivas = alcanzables(inv, RAICES)
    admin = alcanzables(inv, RAICES_ADMIN) - vivas
    usan = preguntas_por_funcion(inv, ejercicio())

    cubetas = {"troncal": [], "de_algunas": [], "zona_ciega": [],
               "sin_alcance": [], "admin": []}
    for clave in sorted(inv):
        n = len(usan.get(clave, ()))
        if clave in vivas:
            if n >= TRONCAL:
                cubetas["troncal"].append((clave, n))
            elif n > 0:
                cubetas["de_algunas"].append((clave, n))
            else:
                cubetas["zona_ciega"].append((clave, 0))
        elif clave in admin:
            cubetas["admin"].append((clave, n))
        elif n == 0:
            cubetas["sin_alcance"].append((clave, 0))
        else:
            # No se alcanza por nombre pero una pregunta la corrio: el grafo se
            # quedo corto, no la funcion. Cuenta como viva.
            cubetas["de_algunas" if n < TRONCAL else "troncal"].append(
                (clave, n))
    return {"cubetas": cubetas, "usan": usan, "inv": inv}


def dependientes(clave: str, usan: dict) -> list:
    """Las preguntas que dependen de esta funcion. Es lo que hay que mirar
    ANTES de tocarla, que es la mitad de lo que pidio Martin."""
    return sorted(usan.get(clave, ()))


def main() -> int:
    m = mapa()
    c = m["cubetas"]
    # EL MAPA SE MIDE EN UN PROCESO LIMPIO, SIEMPRE. Medio sistema cachea -el
    # catalogo, la FAQ, el registro de campos, el geo de CP-, asi que si algo ya
    # corrio antes, la funcion cacheada NO se vuelve a ejecutar y el mapa la
    # cuenta como ciega. Corriendo el mapa adentro de la bateria salian tres
    # funciones ciegas de mas, y cambiaban segun el orden de los tests. Por eso
    # `tests/test_mapa.py` invoca ESTE archivo en un subproceso: mismo punto de
    # partida, mismo resultado.
    if "--json" in sys.argv:
        destino = Path(sys.argv[sys.argv.index("--json") + 1])
        destino.write_text(json.dumps({
            k: [[clave, n] for clave, n in v] for k, v in c.items()},
            ensure_ascii=False), encoding="utf-8")
    total = sum(len(v) for v in c.values())
    print("=" * 78)
    print(f"MAPA DE CONEXIONES — {total} funciones en app/")
    print("=" * 78)
    for nombre, titulo in (
            ("troncal", f"TRONCAL — la usan {TRONCAL} pruebas o mas"),
            ("de_algunas", "DE ALGUNAS — la usan entre 1 y "
                           f"{TRONCAL - 1} pruebas"),
            ("zona_ciega", "ZONA CIEGA — corre en produccion y NINGUNA prueba "
                           "la toca, ni las 40 ni las charlas grabadas"),
            ("sin_alcance", "SIN ALCANCE — no se llega desde ningun webhook"),
            ("admin", "ADMIN — endpoints de carga y salud, fuera del camino "
                      "del cliente")):
        filas = sorted(c[nombre], key=lambda t: (-t[1], t[0]))
        print(f"\n{titulo}: {len(filas)}")
        for clave, n in filas[:25]:
            print(f"   {n:>3} pruebas  {clave}")
        if len(filas) > 25:
            print(f"   ... y {len(filas) - 25} mas")

    print("\n" + "=" * 78)
    vivas = len(c["troncal"]) + len(c["de_algunas"]) + len(c["zona_ciega"])
    ciega = len(c["zona_ciega"])
    print(f"EL NUMERO DEL MAPA: {ciega} de {vivas} funciones del camino vivo "
          f"NO las toca ninguna prueba "
          f"({100 * ciega / max(1, vivas):.0f}% a ciegas)")
    print("=" * 78)

    if "--fijar" in sys.argv:
        PISO.write_text(json.dumps({
            "_doc": "Piso del mapa. La zona ciega puede ACHICARSE, nunca "
                    "crecer: tests/test_mapa.py lo defiende. Se refija a mano "
                    "con `python3 banco_pruebas/mapa.py --fijar` cuando baja.",
            "zona_ciega": sorted(k for k, _ in c["zona_ciega"]),
            "vivas": vivas}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"piso grabado en {PISO.name}: zona ciega de {ciega}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
