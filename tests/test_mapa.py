"""
EL CANDADO DEL MAPA — la zona ciega puede achicarse, nunca crecer.

QUE DEFIENDE. `banco_pruebas/mapa.py` cruza dos medidas: a que funciones se
llega desde el webhook, y cuales ejercita cada una de las 40 preguntas. Del
cruce sale LA ZONA CIEGA: codigo que corre en produccion y que ninguna prueba
toca. Medido el 5-ago: 143 de 304 funciones del camino vivo, el 47%.

POR QUE UN PISO Y NO UN CERO. Exigir cero hoy seria mentir sobre el estado y
dejar el CI rojo para siempre, que es la forma mas rapida de que nadie lo mire.
El piso dice otra cosa, que es la que sirve: **lo que se suma al camino vivo
nace con una pregunta que lo ejercite, o no se suma**. Es la regla de honestidad
de cobertura: una capa que no se ejercita no puntua.

COMO SE BAJA EL PISO. Se le escribe la prueba a una funcion ciega, se corre
`python3 banco_pruebas/mapa.py --fijar` y se commitea el piso nuevo. Cada
sesion deberia bajarlo, aunque sea de a poco.

EL PISO SUBIO UNA SOLA VEZ, el 13-ago, y no fue porque bajara la cobertura: el
instrumento medía mal. Contaba la linea del `def` -que corre al importar el
modulo- como si fuera ejercicio, asi que `main.py`, los dos conectores y
`pago.py` figuraban probados cuando las 40 y los casetes solo los IMPORTAN.
Arreglada la cuenta, aparecieron 35 funciones que siempre estuvieron ciegas y
nadie veia. Se refijo el piso con el numero honesto y esas 35 quedaron anotadas
en `PENDIENTE.md`. Que quede dicho para la proxima: subir el piso se justifica
cuando se demuestra que la medida vieja mentia, nunca para pasar un rojo.

POR QUE ESTA MARCADO `lento` Y NO CORRE EN CADA PUSH. Costo real, y se pago
caro: mide las 40 y las 10 charlas BAJO COBERTURA y en un proceso aparte, o sea
casi dos minutos en esta maquina y varias veces mas en un runner. El 6-ago la
corrida de deploy quedo CANCELADA a los 15 minutos con el job de test colgado y
el deploy en skipped: el arreglo de la cuenta nunca llego a produccion, y Martin
probo por WhatsApp contra codigo viejo creyendo que probaba el nuevo. Un candado
que frena el deploy no protege: estorba. Corre en el nocturno y a mano:

    python3 -m pytest tests/test_mapa.py -m lento
"""
import json
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

PISO = _RAIZ / "banco_pruebas" / "mapa_piso.json"


def test_la_lista_de_sin_camino_offline_no_es_un_atajo():
    """EL ANTI-TRUCO DE LA LISTA DE EXCUSAS, y corre en cada push.

    `banco_pruebas/sin_camino_offline.py` declara las funciones a las que la
    prueba no se les puede escribir -el modelo, Firestore, los conectores- para
    que el numero que queda sea trabajo real y no una mezcla. Una lista asi es
    util exactamente hasta el dia que alguien mete adentro algo que si se puede
    probar. Las tres formas de hacer trampa, las tres en rojo:

      1. Una clave que ya no existe en `app/`: quedo podrida y nadie se entera.
      2. Una funcion declarada que en realidad SI la toca una prueba: que este
         probada es la buena noticia; esconderla aca seria la mala.
      3. Un motivo vacio o de menos de veinte caracteres: "no se puede" no es
         un motivo, es una excusa."""
    from banco_pruebas.mapa import inventario
    from banco_pruebas.sin_camino_offline import SIN_CAMINO_OFFLINE

    inv = inventario()
    fantasmas = sorted(k for k in SIN_CAMINO_OFFLINE if k not in inv)
    assert not fantasmas, (
        "declaradas sin camino offline, pero ya no existen en app/. La lista "
        "quedo podrida:\n  " + "\n  ".join(fantasmas))

    ciega = set(json.loads(PISO.read_text(encoding="utf-8"))["zona_ciega"])
    probadas = sorted(k for k in SIN_CAMINO_OFFLINE if k not in ciega)
    assert not probadas, (
        "estas figuran como 'no se les puede escribir la prueba' y SI las "
        "ejercita alguien. Sacalas de la lista: la buena noticia es que estan "
        "probadas.\n  " + "\n  ".join(probadas))

    flojos = sorted(k for k, v in SIN_CAMINO_OFFLINE.items()
                    if len(str(v).strip()) < 20)
    assert not flojos, (
        "sin motivo escrito. 'No se puede' no es un motivo, es una excusa:\n  "
        + "\n  ".join(flojos))


def test_el_doble_de_firestore_no_se_despega_del_real():
    """EL CANDADO DE LA BASE DEL BANCO ENTERO, y es el mas barato de todos.

    Los 875 tests offline corren contra `banco_pruebas/sim_firestore`, que
    parchea `app/storage/firestore_client`. Si el doble se despega del cliente
    real -alguien le agrega un parametro al real y el doble no lo acepta- la
    bateria entera sigue en verde midiendo una ficcion, y el error aparece
    recien en produccion. Es el mismo modo de falla que este repo ya pago con
    los bancos que llamaban por dentro.

    EL CONTRATO: el doble tiene que ACEPTAR todo lo que acepta el real, por
    nombre de parametro, sea explicito o por `**kw`. Al reves no se exige: el
    doble puede ignorar lo que quiera, mientras no explote.

    SE LEE POR AST y no importando los modulos, para no depender de si alguien
    ya corrio `install()` en esta sesion: una vez parcheado, el real ya no esta
    donde mirar."""
    import ast

    def _firmas(ruta: Path, adentro_de: str | None = None) -> dict:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        if adentro_de:
            arbol = next(n for n in ast.walk(arbol)
                         if isinstance(n, ast.FunctionDef)
                         and n.name == adentro_de)
            nodos = [n for n in arbol.body if isinstance(n, ast.FunctionDef)]
        else:
            nodos = [n for n in arbol.body if isinstance(n, ast.FunctionDef)]
        fuera = {}
        for n in nodos:
            a = n.args
            nombres = {p.arg for p in
                       (*a.posonlyargs, *a.args, *a.kwonlyargs)}
            fuera[n.name] = (nombres, a.kwarg is not None)
        return fuera

    doble = _firmas(_RAIZ / "banco_pruebas/sim_firestore.py", adentro_de="install")
    # Los TRES modulos que el doble pisa. Los leads entraron el 13-ago: el mapa
    # los daba por trabajo pendiente y midiendo se vio que tambien los reemplaza,
    # con leads en RAM, asi que corren el mismo riesgo de deriva.
    real = {}
    for mod in ("app/storage/firestore_client.py", "app/core/leads.py",
                "app/core/notificador.py"):
        for nombre, firma in _firmas(_RAIZ / mod).items():
            real.setdefault(nombre, firma)

    comunes = sorted(set(real) & set(doble))
    assert len(comunes) >= 15, (
        f"el doble solo cubre {len(comunes)} funciones de las reales; algo "
        "cambio de forma y este candado dejo de mirar lo que miraba")

    faltantes = []
    for nombre in comunes:
        acepta, tiene_kw = doble[nombre]
        if tiene_kw:
            continue
        for p in sorted(real[nombre][0] - acepta):
            faltantes.append(f"{nombre}: el real acepta `{p}` y el doble no")
    assert not faltantes, (
        "EL DOBLE SE DESPEGO DE LO REAL. Los tests offline estarian midiendo "
        "una ficcion:\n  " + "\n  ".join(faltantes))


def _mapa_en_proceso_limpio(tmp_path) -> dict:
    """EL MAPA SE MIDE EN UN PROCESO NUEVO. Medio sistema cachea -catalogo,
    FAQ, registro de campos, geo de CP-, asi que una funcion que ya corrio en
    otro test no se vuelve a ejecutar y el mapa la contaria como ciega. Medido:
    adentro de la bateria daban tres funciones ciegas de mas, y cambiaban segun
    el orden. En un subproceso el punto de partida es siempre el mismo."""
    import subprocess
    salida = tmp_path / "mapa.json"
    r = subprocess.run(
        [sys.executable, str(_RAIZ / "banco_pruebas" / "mapa.py"),
         "--json", str(salida)],
        capture_output=True, text=True, timeout=600, cwd=str(_RAIZ))
    assert salida.exists(), (
        f"el mapa no corrio: {r.returncode}\n{r.stderr[-2000:]}")
    return json.loads(salida.read_text(encoding="utf-8"))


def test_importar_un_modulo_no_lo_da_por_ejercitado():
    """EL CANDADO DEL 13-AGO, y es rapido a proposito: corre en cada push.

    QUE PASO. La linea del `def` se EJECUTA al importar el modulo. El mapa
    media cada funcion desde esa linea, asi que si un modulo entraba por
    primera vez con un contexto de cobertura prendido, TODAS sus funciones
    quedaban marcadas como ejercitadas sin que nadie las llamara. Ocho
    funciones de `llm_adapter.py` figuraron ejercitadas por eso durante
    semanas: el modelo esta parchado en las charlas grabadas, o sea que no las
    llama nadie. El dia que las_40 empezo a importar `app.verifika` un poquito
    antes, el import cayo fuera de todo contexto, las ocho aparecieron ciegas
    de golpe y el nocturno quedo tres noches en rojo por una diferencia de
    orden de imports, no de codigo.

    LA MEDIDA HONESTA cuenta desde el CUERPO. Esto lo verifica sin correr el
    mapa entero: una funcion cuyo unico rastro es su propia linea de `def` no
    cuenta como ejercitada."""
    from banco_pruebas.mapa import inventario, preguntas_por_funcion

    inv = inventario()
    assert inv, "el inventario del mapa salio vacio"

    multilinea = {k: f for k, f in inv.items() if f["fin"] > f["ini"] + 1}
    assert multilinea, "ninguna funcion de app/ tiene mas de una linea"
    clave, f = next(iter(sorted(multilinea.items())))
    archivo = str(_RAIZ / f["modulo"])

    solo_el_def = {archivo: {f["ini"]: ["import"]}}
    assert not preguntas_por_funcion(inv, solo_el_def)[clave], (
        f"{clave} figura ejercitada por la linea de su `def` ({f['ini']}), "
        "que corre al importar el modulo y no prueba nada. El mapa tiene que "
        "medir desde el CUERPO de la funcion.")

    el_cuerpo = {archivo: {f["fin"]: ["una prueba"]}}
    assert preguntas_por_funcion(inv, el_cuerpo)[clave] == {"una prueba"}, (
        f"{clave} no figura ejercitada con una linea de su cuerpo corrida: el "
        "mapa dejo de ver el cuerpo y ahora subestima al reves")


@pytest.mark.lento
def test_la_zona_ciega_no_crece(tmp_path):
    pytest.importorskip("coverage",
                        reason="el mapa necesita coverage para medir que "
                               "pregunta ejercita cada funcion")
    piso = json.loads(PISO.read_text(encoding="utf-8"))
    viejas = set(piso["zona_ciega"])
    ciega = {k for k, _ in _mapa_en_proceso_limpio(tmp_path)["zona_ciega"]}
    nuevas = sorted(ciega - viejas)
    assert not nuevas, (
        "ENTRO CODIGO CIEGO AL CAMINO VIVO: estas funciones corren en "
        "produccion y ninguna de las 40 preguntas las toca.\n  "
        + "\n  ".join(nuevas)
        + "\n\nO le escribis la prueba, o no va al camino vivo. Si de verdad "
          "bajo la zona ciega, refija el piso con "
          "`python3 banco_pruebas/mapa.py --fijar`.")
    assert len(ciega) <= len(viejas), (
        f"la zona ciega crecio de {len(viejas)} a {len(ciega)}")
