"""
EL PESO DEL TURNO — cuanto le cargamos al modelo en cada llamada, medido.

POR QUE EXISTE (Martin, 13-ago-2026): *"optimizar para dejarle menos carga al
LLM en la respuesta, hacer un sistema mas agil, tal vez con menos llamadas,
latencia"*. Eso no se puede hacer a ojo. Hasta hoy el repo medIa si el bot
contesta BIEN -las charlas, el piso, los once barridos- y no medIa **cuanto
cuesta cada respuesta**. Sin ese numero, aliviar el sistema es una opinion, y
la sesion siguiente no puede saber si aliviano o empeoro.

QUE MIDE, y son las tres cosas que viajan en cada llamada al modelo:

  EL ESQUEMA DE HERRAMIENTAS. Lo mas pesado con diferencia, y lo que menos se
      mira porque no lo escribe nadie a mano: sale de los moldes Pydantic.
  LOS PROMPTS. Las instrucciones del decisor y del redactor.
  LOS ENUM. Las listas cerradas que viajan adentro del esquema -los temas de la
      FAQ, los campos filtrables, las categorias-.

Y lo cruza con EL USO REAL: cuantas veces llama el modelo a cada herramienta en
las charlas grabadas. Una herramienta que pesa mucho y no se usa nunca es carga
pura; una que se usa siempre y pesa poco esta bien donde esta.

EL TECHO, y es lo que lo vuelve un candado y no un informe. `peso_techo.json`
guarda el peso de hoy. `tests/test_peso_del_turno.py` se pone rojo si CRECE.
Es el espejo del piso del mapa: alla la cobertura no puede bajar, aca el peso no
puede subir. Se baja con `python3 banco_pruebas/peso_del_turno.py --fijar`.

LO QUE NO MIDE, dicho adelante. Los tokens de VERDAD: los cuenta el tokenizador
del proveedor y varia entre modelos. Aca se miden BYTES, que es lo que no
depende de nadie, y se muestra una estimacion dividiendo por cuatro. Para
comparar dos versiones del mismo sistema los bytes alcanzan y sobran; para
predecir la factura, no.
"""
import json
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

TIENDA = "verifika_prod"
TECHO = Path(__file__).resolve().parent / "peso_techo.json"
CASETES = Path(__file__).resolve().parent / "casetes"


def _preparar() -> None:
    from banco_pruebas.sim_firestore import install
    from app.core.contexto_turno import set_current_tienda
    install()
    set_current_tienda(TIENDA)


def esquema() -> dict:
    """{herramienta: {bytes, campos, enum_valores}} tal como viaja al modelo."""
    from app.core import herramientas as H
    fuera = {}
    for t in H.esquemas(TIENDA):
        f = t.get("function", t)
        props = (f.get("parameters") or {}).get("properties") or {}
        enums = 0
        for v in props.values():
            enums += len(v.get("enum")
                         or (v.get("items") or {}).get("enum") or [])
        fuera[f["name"]] = {"bytes": len(json.dumps(t, ensure_ascii=False)),
                            "campos": len(props), "enum_valores": enums}
    return fuera


def prompts() -> dict:
    """{constante: bytes} de las instrucciones que viajan en cada llamada."""
    from app.core import hub_venta as HV
    fuera = {}
    for n in dir(HV):
        if not n.startswith(("_INSTRUCCION", "_SISTEMA", "_NOTA", "_PROMPT")):
            continue
        v = getattr(HV, n)
        if isinstance(v, str) and len(v) > 100:
            fuera[n] = len(v)
    return fuera


def uso_real() -> dict:
    """{herramienta: veces que el modelo la llamo} en las charlas grabadas.

    Es la unica evidencia honesta de uso que hay offline: son turnos reales con
    lo que el modelo contesto de verdad. NO es prueba de que lo que no aparece
    sea inutil -son 15 charlas, no el universo-, pero si es prueba de lo que SI
    se usa, y de que algo nunca hizo falta en ninguna de las grabadas."""
    fuera: dict = {n: 0 for n in esquema()}
    turnos = 0
    for c in sorted(CASETES.glob("*.json")):
        if c.name.startswith("_"):
            continue
        d = json.loads(c.read_text(encoding="utf-8"))
        for t in d.get("turnos", []):
            turnos += 1
            for ll in t.get("llamadas", []):
                try:
                    s = json.loads(ll.get("salida") or "{}")
                except Exception:
                    continue
                for tc in (s.get("tool_calls") or []):
                    n = tc.get("name")
                    if n in fuera:
                        fuera[n] += 1
    return {"llamadas": fuera, "turnos": turnos}


def medir() -> dict:
    _preparar()
    esq = esquema()
    pr = prompts()
    uso = uso_real()
    bytes_esquema = sum(v["bytes"] for v in esq.values())
    bytes_prompts = sum(pr.values())
    total = bytes_esquema + bytes_prompts
    nunca = sorted(n for n, v in uso["llamadas"].items() if v == 0)
    return {
        "herramientas": len(esq),
        "bytes_esquema": bytes_esquema,
        "bytes_prompts": bytes_prompts,
        "bytes_por_llamada": total,
        "pct_esquema": round(100.0 * bytes_esquema / max(1, total), 1),
        "detalle": esq, "prompts": pr, "uso": uso, "nunca_usadas": nunca,
    }


def comparar_con_el_techo(m: dict) -> list:
    """Los excesos contra el techo guardado. Lista vacia = no engordo."""
    if not TECHO.exists():
        return []
    techo = json.loads(TECHO.read_text(encoding="utf-8"))
    excesos = []
    if m["bytes_por_llamada"] > techo["bytes_por_llamada"]:
        excesos.append(
            f"el turno engordo: {techo['bytes_por_llamada']} -> "
            f"{m['bytes_por_llamada']} bytes por llamada al modelo")
    for nombre, v in m["detalle"].items():
        antes = (techo.get("detalle") or {}).get(nombre)
        if antes and v["bytes"] > antes["bytes"]:
            excesos.append(f"  {nombre}: {antes['bytes']} -> {v['bytes']} bytes")
    return excesos


def _fijar(m: dict) -> None:
    TECHO.write_text(json.dumps({
        "_doc": "Techo del peso del turno. Puede BAJAR, nunca subir: "
                "tests/test_peso_del_turno.py lo defiende. Se refija a mano "
                "con `python3 banco_pruebas/peso_del_turno.py --fijar` cuando "
                "baja. Es el espejo del piso del mapa.",
        "bytes_por_llamada": m["bytes_por_llamada"],
        "bytes_esquema": m["bytes_esquema"],
        "bytes_prompts": m["bytes_prompts"],
        "detalle": {k: {"bytes": v["bytes"]} for k, v in m["detalle"].items()},
    }, ensure_ascii=False, indent=1), encoding="utf-8")


def main(argv: list) -> int:
    m = medir()
    print("=" * 72)
    print(f"EL PESO DEL TURNO — {m['bytes_por_llamada']} bytes viajan al modelo "
          f"en CADA llamada (~{m['bytes_por_llamada'] // 4} tokens)")
    print("=" * 72)
    print(f"  esquema de las {m['herramientas']} herramientas: "
          f"{m['bytes_esquema']} bytes ({m['pct_esquema']}% del total)")
    print(f"  instrucciones al modelo:            {m['bytes_prompts']} bytes")
    print()
    u = m["uso"]["llamadas"]
    print(f"  {'herramienta':<22} {'bytes':>7} {'campos':>7} {'enum':>6} "
          f"{'usos':>6}")
    for n, v in sorted(m["detalle"].items(), key=lambda x: -x[1]["bytes"]):
        marca = "   <-- NUNCA en las grabadas" if u.get(n, 0) == 0 else ""
        print(f"  {n:<22} {v['bytes']:>7} {v['campos']:>7} "
              f"{v['enum_valores']:>6} {u.get(n, 0):>6}{marca}")
    print(f"\n  medido sobre {m['uso']['turnos']} turnos grabados")

    excesos = comparar_con_el_techo(m)
    if excesos:
        print("\n  EL TURNO ENGORDO contra el techo:")
        for e in excesos:
            print(f"    {e}")

    if "--fijar" in argv:
        _fijar(m)
        print(f"\ntecho grabado en {TECHO.name}: "
              f"{m['bytes_por_llamada']} bytes por llamada")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
