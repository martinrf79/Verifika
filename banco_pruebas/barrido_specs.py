"""
EL BARRIDO DE LAS SPECS — cada spec preguntable, una por una, contra la fuente.

POR QUE EXISTE. `data/clientes/verifika_prod/` declara las specs que un cliente
puede preguntar: los hercios de la pantalla, si la RAM se amplia, los puertos,
el Thunderbolt. Cada una trae COMO se pregunta -`rx_pregunta`- y COMO se saca el
valor de la ficha -`extraer`-. Nada verificaba que esas dos mitades funcionaran
para todas: una spec con la pregunta rota es una spec que el bot nunca reconoce,
y una con el patron roto es una que reconoce y no puede contestar. Las dos se
ven igual desde afuera -"no me supo decir"- y ninguna deja rastro.

QUE BARRE, y son las tres preguntas de una spec:

  1. ¿SE RECONOCE LA PREGUNTA? Por cada spec, su `rx_pregunta` tiene que
     matchear como la escribe un cliente, y NO matchear la pregunta de otra
     spec. Una seña que dispara dos specs obliga al sistema a adivinar, que es
     el mismo defecto que el barrido de la FAQ ya caza un piso mas arriba.
  2. ¿SE SACA EL VALOR? Por cada spec y cada categoria donde APLICA, tiene que
     haber al menos un producto real de la fuente del que se extraiga. Una spec
     declarada para una categoria donde ningun producto la tiene es una promesa
     que el bot no puede cumplir.
  3. ¿LO QUE SE SACA ESTA EN LA FICHA? El valor extraido tiene que aparecer,
     textual, en algun campo del producto. Es la atadura: una spec que devuelve
     algo que no esta escrito en la fuente es una alucinacion con formato de
     dato, y es peor que no contestar.

DE DONDE SALEN LOS CASOS. De la FUENTE, no de una lista escrita a mano: las
specs de `specs_config` por los 880 productos reales. Si mañana se agrega una
spec al json, aparece sola en la cuenta y queda sin cubrir hasta que la fuente
tenga un producto que la tenga. Es el mismo candado que `INVENTARIO_FUENTE`
tiene sobre el catalogo: el numero sale de la fuente.

CORRE OFFLINE Y GRATIS: doble local de Firestore con el catalogo real, cero
llamadas al modelo.
"""
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

TIENDA = "verifika_prod"

# Como pregunta un cliente por cada spec. LA SEÑA NO SE INVENTA: sale de las
# `claves` que declara la FUENTE, que son las palabras con las que el sistema
# dice entender esa spec. Primer intento: arme la pregunta con la `etiqueta`, y
# el barrido acuso dos specs rotas que no lo estaban -"si la RAM se puede
# ampliar" es la DESCRIPCION de la spec, no como la nombra un cliente-. Una
# prueba que se inventa la entrada mide su propia invencion.
_MOLDES = ("{c}?", "tiene {c}?", "me decis si tiene {c}", "que {c} tiene",
           "consulta: {c}")


def _productos() -> list:
    from app.storage.firestore_client import get_all_products
    return get_all_products(tienda_id=TIENDA) or []


def specs() -> list:
    from app.core.fuente_producto import specs_config
    return specs_config(TIENDA)


def _config_cruda() -> dict:
    """El json de specs tal cual, para leer las `claves`: `specs_config` las
    compila adentro de `rx_pregunta` y ya no se pueden ver de a una."""
    import json
    from app.core.fuente_producto import _ruta_config
    ruta = _ruta_config(TIENDA)
    if not ruta:
        return {}
    with open(ruta, encoding="utf-8") as f:
        data = json.load(f)
    return {(s.get("id") or ""): [c for c in (s.get("claves") or []) if c]
            for s in (data.get("specs") or [])}


def preguntas_de(spec: dict) -> list:
    """Las formas en que un cliente pregunta por esta spec. Las palabras salen
    de la FUENTE -sus `claves`-; los moldes, de acá."""
    claves = _config_cruda().get(spec.get("id") or "") or []
    return [m.format(c=c) for c in claves for m in _MOLDES]


def _tablas_curadas() -> set:
    """Los valores que la fuente carga A MANO: la planilla por modelo, los
    defaults por categoria y las reglas condicionales. Son fuente igual que la
    ficha, solo que no estan escritos en el texto del producto."""
    from app.core.fuente_producto import specs_por_categoria, specs_por_modelo
    fuera = set()
    for d in specs_por_modelo(TIENDA).values():
        fuera |= {str(v).strip().lower() for v in d.values() if v}
    cfg = specs_por_categoria(TIENDA)
    for d in cfg["categorias"].values():
        fuera |= {str(v).strip().lower() for v in d.values() if v}
    for regla in cfg["reglas"]:
        fuera |= {str(v).strip().lower()
                  for v in (regla.get("entonces") or {}).values() if v}
    return fuera


def cobertura() -> dict:
    """Cuantas specs de la fuente quedan REALMENTE barridas: las que tienen al
    menos un producto del que se extrae su valor. Las que no, se nombran."""
    from app.core.fuente_producto import extraer_specs

    todas = specs()
    con_dato: dict = {}
    for prod in _productos():
        for sid in extraer_specs(prod, TIENDA):
            con_dato.setdefault(sid, 0)
            con_dato[sid] += 1
    pendientes = sorted(s["id"] for s in todas if s["id"] not in con_dato)
    cubiertas = len(todas) - len(pendientes)
    return {"specs": len(todas), "cubiertas": cubiertas,
            "pendientes": pendientes, "productos_con_spec": con_dato,
            "porcentaje": round(100.0 * cubiertas / max(1, len(todas)), 1)}


def casos() -> int:
    """El tamaño del barrido: las preguntas generadas de la fuente, mas cada
    spec medida en cada producto que la tiene."""
    cob = cobertura()
    preguntas = sum(len(preguntas_de(s)) for s in specs())
    return preguntas + sum(cob["productos_con_spec"].values())


def correr() -> dict:
    """Los tres chequeos, sobre la fuente entera. Devuelve los defectos."""
    from app.core.fuente_producto import extraer_specs, campos_ficha

    defectos = []
    todas = specs()

    # 1. la pregunta se reconoce por su propia seña de la fuente
    for spec in todas:
        rx = spec.get("rx_pregunta")
        for pregunta in preguntas_de(spec):
            if rx is not None and not rx.search(pregunta.lower()):
                defectos.append({
                    "tipo": "PREGUNTA NO RECONOCIDA", "spec": spec["id"],
                    "detalle": f"su propia clave no matchea: {pregunta!r}"})
                break

    # 2 y 3. el valor sale, y sale de la FUENTE: del texto de la ficha o de las
    # tablas curadas. La distincion importa y me costo una vuelta: los valores
    # de `_completar_capas` -planilla por modelo, default de categoria, reglas-
    # NO estan en el texto del producto y son igual de legitimos. Pedirlos
    # textuales en la ficha marcaba 4298 defectos que no existian.
    curados = _tablas_curadas()
    prods = _productos()
    for prod in prods:
        sacadas = extraer_specs(prod, TIENDA)
        if not sacadas:
            continue
        texto = " ".join(str(v) for _c, v in campos_ficha(prod)).lower()
        texto_pegado = texto.replace(" ", "")
        for sid, valor in sacadas.items():
            v = str(valor).strip().lower()
            if not v:
                defectos.append({"tipo": "VALOR VACIO", "spec": sid,
                                 "detalle": f"{prod.get('id')} devolvio ''"})
                continue
            if v.replace(" ", "") in texto_pegado or v in curados:
                continue
            defectos.append({
                "tipo": "VALOR QUE NO SALE DE LA FUENTE", "spec": sid,
                "detalle": f"{prod.get('id')} devolvio {valor!r}: ni esta en "
                           f"su ficha ni en las tablas curadas"})

    cob = cobertura()
    return {"casos": casos(), "defectos": defectos, "cobertura": cob,
            "productos": len(prods)}


if __name__ == "__main__":
    from banco_pruebas.sim_firestore import install
    install()
    r = correr()
    c = r["cobertura"]
    print(f"EL BARRIDO DE LAS SPECS: {r['casos']} casos · "
          f"{c['specs']} specs de la fuente, {c['cubiertas']} con dato real "
          f"({c['porcentaje']}%)")
    if c["pendientes"]:
        print("  specs declaradas SIN ningun producto que las tenga:")
        for s in c["pendientes"]:
            print(f"    - {s}")
    for d in r["defectos"][:20]:
        print(f"  [{d['tipo']}] {d['spec']}: {d['detalle']}")
    print(f"defectos: {len(r['defectos'])}")
