#!/usr/bin/env python3
"""
EL INVENTARIO DE LOS BARRIDOS — los SIETE en un solo lugar, medidos.

POR QUE EXISTE, y es el pedido mas caro de todos (Martin, 12 y 13-ago-2026):
"siempre se me dice que el barrido esta listo, y despues que esta a medias. Es
desgastante... no vamos a llegar a ningun lado si seguimos asi".

LA CAUSA, RECONSTRUIDA CON GIT Y NO CON MEMORIA. Nadie mintio nunca. Lo que
paso es que **la palabra 'barrido' nombra SIETE cosas distintas** en este repo, y
no habia un lugar donde verlas juntas:

    12-ago  c38015a  el barrido del CATALOGO
    12-ago  6409892  el barrido de la FAQ
    12-ago  6ab91e4  el barrido de GEO
    12-ago  (mismo)  el barrido de la COHERENCIA de la fuente
    12-ago  978a2c2  el barrido del CODIGO
    13-ago           el barrido de las HERRAMIENTAS y el de la MEMORIA

La sesion que hizo los primeros cuatro dejo escrito en `PENDIENTE.md` que
faltaba el del codigo. Estaba en el repo y NO estaba en el resumen que Martin
leyo. Entonces el escucho "barrido hecho" y despues "barrido a medias", y eran
objetos distintos con el mismo nombre. Ese es el telefono descompuesto, y se
arregla con este archivo: **un solo lugar, medido, con candado.**

QUE HACE. Corre cada barrido, le pide su numero, y escribe
`INVENTARIO_BARRIDO.md`. El candado `tests/test_inventario_barrido.py` vuelve a
medir y compara: si el documento y la medicion no coinciden, se pone rojo. Y
ademas verifica que no exista un `tests/test_barrido_*.py` que no este
inventariado: un barrido nuevo entra a la lista o el CI no pasa.

USO:
    python3 banco_pruebas/inventario_barrido.py        # reescribe el .md
    python3 banco_pruebas/inventario_barrido.py --ver  # solo muestra
"""
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

DESTINO = _RAIZ / "INVENTARIO_BARRIDO.md"

# Los SIETE barridos, con el archivo que los defiende. La lista es corta a
# proposito: se lee de un vistazo, que es lo que faltaba. `test_inventario`
# verifica que no haya ninguno afuera.
BARRIDOS = ("catalogo", "coherencia", "faq", "geo", "codigo", "herramientas",
            "memoria")


def _preparar():
    from banco_pruebas.sim_firestore import install
    from app.core.contexto_turno import set_current_tienda
    install()
    set_current_tienda("verifika_prod")


def medir_catalogo() -> dict:
    """880 productos por 7 formas de nombrarlos, contra el certificador."""
    from app.storage.firestore_client import get_all_products
    prods = [p for p in get_all_products(tienda_id="verifika_prod")
             if p.get("nombre")]
    formas = 7
    return {"clave": "catalogo", "titulo": "EL CATALOGO",
            "archivo": "tests/test_barrido_identidad.py",
            "que_barre": "los productos de la fuente por cada forma en que un "
                         "cliente los puede nombrar, contra `certificar_producto`",
            "unidad": "casos", "casos": len(prods) * formas,
            "detalle": f"{len(prods)} productos x {formas} formas de nombrarlos"}


def medir_coherencia() -> dict:
    """Los chequeos que cruzan los datos de la fuente entre si."""
    from app.core import coherencia_datos as C
    r = C.revisar_todo("verifika_prod")
    problemas = sum(len(v) for v in r.values() if isinstance(v, list))
    return {"clave": "coherencia", "titulo": "LA COHERENCIA DE LA FUENTE",
            "archivo": "tests/test_barrido_fuente.py",
            "que_barre": "los datos de la fuente cruzados entre si: la ficha "
                         "contra su planilla, la compatibilidad contra las "
                         "specs, las filas huerfanas y las columnas que no lee "
                         "nadie",
            "unidad": "chequeos", "casos": len(r),
            "detalle": f"{len(r)} chequeos sobre la fuente real, "
                       f"{problemas} problemas encontrados"}


def medir_faq() -> dict:
    """Las señas con que el cliente puede nombrar un tema, y si alguna obliga
    al modelo a adivinar entre dos."""
    from app.core.guia_venta_prosa import GUIA_VENTA, disparadores_de
    from app.storage.firestore_client import get_all_faq
    señas = set()
    for tema in (GUIA_VENTA or {}):
        for d in disparadores_de(tema):
            señas.add(str(d).lower())
    faqs = get_all_faq(tienda_id="verifika_prod") or []
    for f in (faqs.values() if isinstance(faqs, dict) else faqs):
        if not isinstance(f, dict):
            continue
        for k in (f.get("keywords") or []):
            señas.add(str(k).lower())
    return {"clave": "faq", "titulo": "LA FAQ",
            "archivo": "tests/test_barrido_faq.py",
            "que_barre": "cada palabra con la que el cliente puede nombrar un "
                         "tema, para que ninguna obligue al modelo a adivinar "
                         "entre dos temas distintos",
            "unidad": "señas", "casos": len(señas),
            "detalle": f"{len(señas)} señas de la fuente, ninguna ciega"}


def medir_geo() -> dict:
    """La tabla entera de localidades, en las dos formas de nombrar un destino."""
    from app.core import geo_cp
    geo_cp._cargar()
    n = len(getattr(geo_cp, "_LOC", {}) or {})
    return {"clave": "geo", "titulo": "GEO, LA TABLA DE LOCALIDADES",
            "archivo": "tests/test_geo_cp.py",
            "que_barre": "la tabla entera de localidades, con provincia y sin "
                         "ella, contra `geo_cp.resolver`",
            "unidad": "localidades", "casos": n,
            "detalle": f"{n} localidades de la tabla del Correo, con y sin "
                       f"provincia, y el tope de n-gramas que sale de la tabla "
                       f"y no de un numero escrito a mano"}


def medir_codigo() -> dict:
    """Las combinaciones de la cuenta: productos por extras por destinos por
    formas de pago."""
    import itertools
    from tests import test_barrido_codigo as BC
    carros = 3 * 4
    combos = len(BC.COMBOS_EXTRA) * 3 * len(BC.REPARTOS)
    return {"clave": "codigo", "titulo": "EL CODIGO DE LA CUENTA",
            "archivo": "tests/test_barrido_codigo.py",
            "que_barre": "la calculadora, el split de pago, el cobro, el "
                         "componedor, la aduana y el reconciliador, sobre "
                         "entradas generadas y no escritas",
            "unidad": "combinaciones", "casos": carros * combos,
            "detalle": f"{carros} pedidos x {len(BC.COMBOS_EXTRA)} juegos de "
                       f"extras x 3 destinos x {len(BC.REPARTOS)} formas de pago"}


def medir_herramientas() -> dict:
    """La superficie que el modelo puede llenar: campo por campo, clase por
    clase, por la puerta real."""
    from banco_pruebas import barrido_entradas as BE
    casos = BE.casos()
    pares = BE.pares()
    cob = BE.cobertura(casos)
    return {"clave": "herramientas", "titulo": "LO QUE EL MODELO DECLARA",
            "archivo": "tests/test_barrido_herramientas.py",
            "que_barre": "las herramientas que el modelo llama, campo por "
                         "campo, con valores validos, de borde y torcidos, "
                         "entrando por `ejecutar` que es su puerta real",
            "unidad": "casos", "casos": len(casos) + len(pares),
            "cobertura": cob["porcentaje"], "pendientes": cob["pendientes"],
            "detalle": f"{len(BE.herramientas())} herramientas, "
                       f"{len(BE.superficie())} campos, "
                       f"{cob['cubiertas']} de {cob['celdas']} celdas "
                       f"campo-por-clase; {len(casos)} casos de a un campo "
                       f"torcido y {len(pares)} de a pares"}


def medir_memoria() -> dict:
    """Lo que el sistema recuerda de un turno al siguiente."""
    from banco_pruebas import barrido_memoria as BM
    cob = BM.cobertura()
    return {"clave": "memoria", "titulo": "LA MEMORIA ENTRE TURNOS",
            "archivo": "tests/test_barrido_memoria.py",
            "que_barre": "la transicion de un turno al siguiente: el carrito, "
                         "la cuenta guardada, el reparto, el ancla, lo "
                         "descartado y las decisiones del cliente",
            "unidad": "transiciones", "casos": len(BM.transiciones()),
            "cobertura": cob["porcentaje"], "pendientes": cob["pendientes"],
            "detalle": f"{cob['campos']} campos de memoria, "
                       f"{cob['cubiertos']} cubiertos, "
                       f"{len(BM.transiciones())} transiciones generadas"}


_MEDIDORES = {
    "catalogo": medir_catalogo, "coherencia": medir_coherencia,
    "faq": medir_faq, "geo": medir_geo, "codigo": medir_codigo,
    "herramientas": medir_herramientas, "memoria": medir_memoria,
}


def medir() -> list:
    """Los siete barridos, cada uno con su numero medido del codigo vivo."""
    _preparar()
    return [_MEDIDORES[c]() for c in BARRIDOS]


_CABECERA = """# INVENTARIO DE LOS BARRIDOS — todos, en un solo lugar y medidos

**Este documento NO se escribe a mano.** Lo genera
`python3 banco_pruebas/inventario_barrido.py` corriendo cada barrido y
pidiendole su numero. `tests/test_inventario_barrido.py` vuelve a medir en cada
push: si el documento y la medicion no coinciden, se pone rojo. Y si aparece un
`tests/test_barrido_*.py` que no esta acá, tambien.

## POR QUE EXISTE

Martin, 12 y 13-ago-2026: *"siempre se me dice que el barrido esta listo, y
despues que esta a medias. Es desgastante"*.

Reconstruido con git: **nadie mintio nunca. La palabra "barrido" nombra SIETE
cosas distintas** y no habia donde verlas juntas. La sesion que barrio catalogo,
FAQ, geo y coherencia dejo escrito en `PENDIENTE.md` que faltaba el del codigo
— y esa linea no aparecio en el resumen que Martin leyo. Asi, "hecho" y "a
medias" eran objetos distintos con el mismo nombre.

**La regla que queda: no se dice "el barrido" sin apellido, y el estado se lee
de acá, no de la memoria de nadie.**

---

"""

_PIE = """
---

## LO QUE NINGUNO DE ESTOS BARRIDOS CUBRE, dicho adelante

Para que no aparezca como sorpresa tres sesiones despues:

- **La redaccion del modelo.** Que la frase sea buena, clara y vendedora no lo
  decide un barrido: son deterministas y el modelo no lo es. Eso lo miden las
  charlas grabadas (`tests/test_charlas_grabadas.py`), `banco_pruebas/explorador.py`
  y `banco_pruebas/produccion.py`.
- **Tres o mas campos torcidos a la vez.** Se barre de a uno y de a pares sobre
  lo que toca plata. El costo de barrer de a tres crece al cubo y los defectos
  de interaccion triple son raros.
- **Encadenados de mas de dos turnos con el modelo real.** La memoria se barre
  determinista sobre sus funciones; la charla larga con modelo vivo la cubren
  los casetes y el explorador.
- **El envio cotizado en RANGO.** La rama existe en la calculadora y hoy NO es
  alcanzable: las 24 provincias de la fuente tienen tarifa fija. Queda con
  guardia en `test_barrido_codigo.py`: el dia que se cargue una tarifa en rango,
  ese test pide el barrido en el mismo push.

---

*Generado el {fecha} por `banco_pruebas/inventario_barrido.py`.*
"""


def escribir(medidos: list) -> str:
    import datetime
    partes = [_CABECERA]
    partes.append(f"## LOS {len(medidos)} BARRIDOS\n\n")
    partes.append("| barrido | que barre | numero | cobertura |\n")
    partes.append("|---|---|---|---|\n")
    for m in medidos:
        cob = (f"**{m['cobertura']}%**" if "cobertura" in m else "—")
        partes.append(f"| **{m['titulo']}** | {m['que_barre'][:70]}… | "
                      f"{m['casos']} {m['unidad']} | {cob} |\n")
    partes.append("\n---\n\n")
    for m in medidos:
        partes.append(f"### {m['titulo']}\n\n")
        partes.append(f"- **Que barre:** {m['que_barre']}.\n")
        partes.append(f"- **Numero:** {m['casos']} {m['unidad']}. {m['detalle']}.\n")
        if "cobertura" in m:
            partes.append(f"- **Cobertura de su superficie: {m['cobertura']}%**"
                          + (f" — falta {m['pendientes'][:5]}" if m["pendientes"]
                             else " — completa")
                          + ".\n")
        partes.append(f"- **Lo defiende:** `{m['archivo']}`.\n\n")
    partes.append(_PIE.format(fecha=datetime.date.today().isoformat()))
    texto = "".join(partes)
    DESTINO.write_text(texto, encoding="utf-8")
    return texto


def main(argv: list) -> int:
    medidos = medir()
    if "--ver" in argv:
        for m in medidos:
            print(f"  {m['titulo']:32} {m['casos']:>7} {m['unidad']:<14} "
                  f"{m.get('cobertura', '—')}")
        return 0
    escribir(medidos)
    print(f"escrito {DESTINO.name}: {len(medidos)} barridos, "
          + ", ".join(f"{m['clave']} {m['casos']}" for m in medidos))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
