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
