#!/usr/bin/env python3
"""EL TRADUCTOR, MEDIDO SOLO — la primera etapa, antes de construir encima.

QUE ES. Un experimento de banco, no el camino vivo. Le da al modelo el mensaje
del cliente y un TABLERO chico —intenciones, rubros y conceptos, sin un solo
valor del catalogo— y le pide una FICHA: el mensaje partido en partes, cada una
con su intencion, su ORIGEN y su rubro. No contesta, no busca, no deploya.

EL ORIGEN ES LA IDEA NUEVA, y sale de la charla con Martin del 23-sep. Cada
parte de una respuesta sale de uno de cuatro lugares:

    tienda    datos de ESTA tienda: productos, precio, stock, envio, pago
    general   saber general de tecnologia o de uso, que no afirma nada de un
              producto puntual
    cliente   depende del aparato o la situacion del cliente, que no tenemos
    ninguno   charla, o no hay como contestarlo

LA REGLA QUE CORTA LA ALUCINACION: un dato de un producto con nombre es SIEMPRE
tienda. `prohibido_general` en la vara lo mide.

SE MIDE SIN JUEZ. Todo lo que se puntua lo comprueba el codigo: que la parte
exista, que su origen, intencion y rubro sean los esperados, que la copia este
en el mensaje, que lo afirmado quede anotado, y la latencia.

Uso, desde la raiz:
    python3 banco_pruebas/traductor.py --modelo gemini
    python3 banco_pruebas/traductor.py --modelo deepseek --solo T07,T25
"""
import argparse
import concurrent.futures as cf
import json
import os
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from banco_pruebas import clon_produccion  # noqa: E402
from banco_pruebas.leer_interpretacion import _norm  # noqa: E402

VARA = os.path.join(RAIZ, "banco_pruebas", "vara_traductor.json")
TIENDA = "verifika_prod"

INTENCIONES = ("buscar", "precio", "stock", "caracteristica", "comparar",
               "compatibilidad", "envio", "pago", "politica", "comprar",
               "postventa", "charla")
ORIGENES = ("tienda", "general", "cliente", "ninguno")
FUERZAS = ("debe", "prefiere", "evita")

# LOS CAMPOS QUE NO SON CONCEPTOS: prosa o identidad. El producto puntual va en
# su propia casilla, no como criterio.
_NO_CONCEPTO = {"nombre", "descripcion", "caracteristicas_extra",
                "contenido_caja", "garantia_detalle", "modelo", "dimensiones"}
_ETIQUETA_BASE = {"precio_ars": "el precio", "marca": "la marca",
                  "color": "el color", "material": "el material",
                  "peso_gramos": "el peso", "garantia_meses": "la garantia",
                  "pais_fabricacion": "donde se fabrica",
                  "pais_marca": "de que pais es la marca"}


def tablero() -> dict:
    """Rubros y conceptos, SALIDOS DEL DATO. Ningun valor del catalogo."""
    from app.core.filtros_catalogo import campos_filtrables, recorrida
    rubros = [c for c, _ in recorrida(TIENDA).get("categorias") or []]
    with open(os.path.join(RAIZ, "data", "clientes", TIENDA,
                           "specs_preguntables.json"), encoding="utf-8") as f:
        etiquetas = {s["id"]: s["etiqueta"] for s in json.load(f)["specs"]}
    etiquetas.update(_ETIQUETA_BASE)
    conceptos = {c: etiquetas.get(c, c.replace("_", " "))
                 for c in sorted(campos_filtrables(TIENDA))
                 if c not in _NO_CONCEPTO}
    return {"rubros": rubros, "conceptos": conceptos}


def prompt(tab: dict, version: str = "v2") -> str:
    conceptos = "; ".join(f"{c} ({e})" for c, e in tab["conceptos"].items())
    v2 = ("" if version == "v1" else
          "- destino: el lugar adonde lo quiere mandar, con sus palabras, o vacio.\n")
    v3 = ("" if version in ("v1", "v2") else """
UNA PARTE POR RUBRO Y POR DESTINO: "2 notebooks y 1 microfono" son dos partes, y "2 a Villa Maria y 3 a Toledo" son dos partes, aunque el pedazo copiado sea el mismo.
criterios_generales: lo que vale para TODO el pedido y no para un rubro solo —"lo menos chino posible", "acorde a la crisis", "el precio no importa"—, con la misma forma que criterios.
reparto: si reparte el pago —"70 transferencia 30 mercado pago", "mitad y mitad"—, cada medio con su porcentaje; si no, vacio.
""")
    regla_afirma = ("" if version == "v1" else
                    " Si le atribuye una caracteristica a un producto con "
                    "NOMBRE —'el K120 inalambrico'— eso va aca y NO en "
                    "criterios: puede ser falso.")
    return f"""Sos el TRADUCTOR de una tienda online de tecnologia. NO le contestas al cliente: llenas una ficha que despues usa el sistema.

Parti el mensaje en PARTES: una por cada cosa que pregunta, pide o cuenta. Si una pregunta mezcla saber general con un producto puntual, parti en dos partes.

Por cada parte:
- dice: el pedazo del mensaje, COPIADO tal cual.
- quiere: {", ".join(INTENCIONES)}.
- origen:
  tienda: se contesta con datos de ESTA tienda: sus productos, precios, stock, datos de un producto puntual, envios, pagos, politicas, pedidos.
  general: saber general de tecnologia o de uso, que vale para cualquier tienda y NO afirma nada de un producto puntual.
  cliente: depende del aparato o la situacion del cliente, que la tienda no conoce.
  ninguno: saludo, charla, o no se puede contestar.
  REGLA: un dato de un producto con nombre o modelo es SIEMPRE tienda, nunca general.
- rubro: uno de la lista; 'otro' si es un rubro que no esta; 'ninguno' si no habla de un producto.
- producto: el nombre o modelo tal como lo dijo, o vacio.
- criterios: lo que tiene que cumplir. concepto de la lista u 'otro'; valor con sus palabras; fuerza: debe, prefiere o evita.
- cantidad: unidades que quiere comprar, o 0.
{v2}
afirma: lo que el cliente da por cierto, sobre la tienda, un producto o sus propios aparatos. No lo corrijas: anotalo.{regla_afirma}
reescrita: el mensaje entero bien escrito, en una linea.
{v3}
RUBROS: {", ".join(tab["rubros"])}.
CONCEPTOS: {conceptos}."""


def esquema(tab: dict, version: str = "v2") -> dict:
    rubros = tab["rubros"] + ["otro", "ninguno"]
    conceptos = list(tab["conceptos"]) + ["otro"]
    parte = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "dice": {"type": "string"},
            "quiere": {"type": "string", "enum": list(INTENCIONES)},
            "origen": {"type": "string", "enum": list(ORIGENES)},
            "rubro": {"type": "string", "enum": rubros},
            "producto": {"type": "string"},
            "criterios": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "concepto": {"type": "string", "enum": conceptos},
                    "valor": {"type": "string"},
                    "fuerza": {"type": "string", "enum": list(FUERZAS)}},
                "required": ["concepto", "valor", "fuerza"]}},
            "cantidad": {"type": "integer"}},
        "required": ["dice", "quiere", "origen", "rubro", "producto",
                     "criterios", "cantidad"]}
    if version != "v1":
        parte["properties"]["destino"] = {"type": "string"}
        parte["required"].append("destino")
    criterio = parte["properties"]["criterios"]
    extra_props, extra_req = {}, []
    if version not in ("v1", "v2"):
        extra_props = {
            "criterios_generales": criterio,
            "reparto": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "properties": {"medio": {"type": "string"},
                               "porcentaje": {"type": "number"}},
                "required": ["medio", "porcentaje"]}}}
        extra_req = ["criterios_generales", "reparto"]
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            **extra_props,
            "reescrita": {"type": "string"},
            "partes": {"type": "array", "items": parte},
            "afirma": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "properties": {"sobre": {"type": "string"},
                               "dice": {"type": "string"}},
                "required": ["sobre", "dice"]}}},
        "required": ["reescrita", "partes", "afirma"] + extra_req}


def _cliente(modelo: str):
    from openai import OpenAI
    if modelo == "deepseek":
        return (OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"],
                       base_url="https://api.deepseek.com"), "deepseek-chat")
    from app.core.llm_reintento import _cliente as c, _modelo as m
    return c(), m()


def traducir(texto: str, modelo: str, sistema: str, esq: dict) -> tuple:
    cli, nombre = _cliente(modelo)
    if modelo == "deepseek":
        # DeepSeek no obliga el esquema: se lo pide en el texto y se valida
        # despues. Las casillas fuera de lista se cuentan aparte.
        extra = {"response_format": {"type": "json_object"}}
        sis = sistema + "\n\nDevolve SOLO un JSON con este esquema:\n" + \
            json.dumps(esq, ensure_ascii=False)
    else:
        extra = {"response_format": {"type": "json_schema", "json_schema": {
            "name": "ficha", "strict": True, "schema": esq}}}
        sis = sistema
    t0 = time.time()
    r = cli.chat.completions.create(
        model=nombre, temperature=0.2, max_tokens=1500,
        messages=[{"role": "system", "content": sis},
                  {"role": "user", "content": texto}], **extra)
    ms = int((time.time() - t0) * 1000)
    crudo = r.choices[0].message.content or "{}"
    try:
        return json.loads(crudo), ms
    except json.JSONDecodeError:
        return {"_roto": crudo[:300]}, ms


# ── LA VARA ─────────────────────────────────────────────────────────────────

def _acepta(v, esperado) -> bool:
    if esperado is None:
        return True
    lista = esperado if isinstance(esperado, list) else [esperado]
    return _norm(v) in [_norm(x) for x in lista]


def puntuar(m: dict, ficha: dict, tab: dict) -> dict:
    from app.core.cotejo import renglon_es_copia
    partes = [p for p in (ficha.get("partes") or []) if isinstance(p, dict)]
    fallas, ok, de = [], 0, 0
    for e in m["partes"]:
        clave = _norm(e["clave"])
        # LA CLAVE SE BUSCA EN TODO LO QUE LA PARTE ANOTO: el pedazo, el
        # producto y el destino. Con una parte por destino, "La Plata" vive en
        # `destino` y no en el pedazo copiado.
        cand = [p for p in partes
                if clave in _norm(" ".join(str(p.get(k) or "") for k in
                                           ("dice", "producto", "destino")))]
        # EL REPARTO TIENE SU CASILLA DESDE v3: "setenta treinta" ya no es una
        # parte, es `reparto`. Se da por encontrada si el reparto se lleno.
        if not cand and "pago" in (e.get("quiere") or []) and \
                ficha.get("reparto"):
            cand = [{"origen": "tienda", "quiere": "pago",
                     "rubro": e.get("rubro")}]
        # UN TOPE O UN PLAZO PUEDE SER CRITERIO Y NO PARTE (forma v3): "tengo
        # 200 mil" es un tope de precio del pedido entero, y asi lo anota. Si
        # la vara lo marca como `puede_ser_criterio`, encontrarlo en un valor
        # de criterio cuenta como la parte, con sus controles.
        if not cand and e.get("puede_ser_criterio"):
            todos = [c for p in partes for c in (p.get("criterios") or [])] \
                + list(ficha.get("criterios_generales") or [])
            if any(clave in _norm(str((c or {}).get("valor")))
                   for c in todos if isinstance(c, dict)):
                cand = [{"origen": "tienda", "quiere": (e.get("quiere")
                                                        or ["buscar"])[0],
                         "rubro": e.get("rubro") or "ninguno"}]
        de += 1
        if not cand:
            # UNA PARTE QUE FALTA FALLA TAMBIEN SUS CONTROLES. Si no, faltar
            # sale mas barato que equivocarse y el denominador cambia entre
            # corridas: medido el 23-sep, v3 dio 342/358 contra 359/372.
            de += sum(1 for campo in ("origen", "quiere", "rubro")
                      if campo in e)
            fallas.append(f"falta la parte '{e['clave']}'")
            continue
        ok += 1
        # UN DESTINO ATADO A SU PRODUCTO NO TIENE QUE SER UNA PARTE DE ENVIO:
        # "2 notebooks a La Plata" es una parte de notebook con destino.
        por_destino = [p for p in cand
                       if clave in _norm(str(p.get("destino") or ""))]
        for campo in ("origen", "quiere", "rubro"):
            if campo not in e:
                continue
            if por_destino and campo in ("quiere", "rubro"):
                de += 1
                ok += 1
                continue
            de += 1
            if any(_acepta(p.get(campo), e[campo]) for p in cand):
                ok += 1
            else:
                fallas.append(f"{e['clave']}: {campo} "
                              f"{[p.get(campo) for p in cand]} "
                              f"y se esperaba {e[campo]}")
    for mod in m.get("prohibido_general") or []:
        de += 1
        malas = [p for p in partes if _norm(p.get("origen")) == "general"
                 and _norm(mod) in _norm(str(p.get("dice")) + " "
                                         + str(p.get("producto")))]
        if malas:
            fallas.append(f"'{mod}' quedo como saber general")
        else:
            ok += 1
    for a in m.get("afirma") or []:
        de += 1
        # POR RAIZ: "inalambrico" tiene que ver "inalambrica". Medido: la
        # primera corrida conto como fallado un afirma que estaba bien.
        raiz = _norm(a)[:6]
        if any(raiz in _norm(json.dumps(x, ensure_ascii=False))
               for x in ficha.get("afirma") or []):
            ok += 1
        else:
            fallas.append(f"no anoto lo que afirma: '{a}'")
    for d in m.get("destinos") or []:
        de += 1
        if any(_norm(d) in _norm(p.get("destino")) for p in partes):
            ok += 1
        else:
            fallas.append(f"el destino '{d}' no quedo en su casilla")
    for concepto, fuerza in m.get("criterios") or []:
        de += 1
        if any(_norm(c.get("concepto")) == _norm(concepto)
               and _norm(c.get("fuerza")) == _norm(fuerza)
               for c in [c for p in partes for c in (p.get("criterios") or [])]
               + list(ficha.get("criterios_generales") or [])
               if isinstance(c, dict)):
            ok += 1
        else:
            fallas.append(f"falta el criterio {concepto} {fuerza}")
    if m.get("reparto"):
        de += 1
        hubo = sorted(int(x.get("porcentaje") or 0)
                      for x in ficha.get("reparto") or [] if isinstance(x, dict))
        if hubo == sorted(m["reparto"]):
            ok += 1
        else:
            fallas.append(f"reparto {hubo} y se esperaba {m['reparto']}")
    if m.get("cantidad"):
        de += 1
        if any(p.get("cantidad") == m["cantidad"] for p in partes):
            ok += 1
        else:
            fallas.append(f"la cantidad {m['cantidad']} no quedo")
    copias = sum(1 for p in partes if renglon_es_copia(str(p.get("dice")),
                                                       m["texto"]))
    fuera_de_lista = sum(
        1 for p in partes
        if p.get("quiere") not in INTENCIONES
        or p.get("origen") not in ORIGENES
        or p.get("rubro") not in tab["rubros"] + ["otro", "ninguno"])
    return {"ok": ok, "de": de, "fallas": fallas, "partes": len(partes),
            "copias": copias, "fuera_de_lista": fuera_de_lista}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default="gemini", choices=("gemini", "deepseek"))
    ap.add_argument("--solo", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--hilos", type=int, default=6)
    ap.add_argument("--tablero", default="v2", choices=("v1", "v2", "v3"))
    args = ap.parse_args()
    clon_produccion.preparar_entorno()
    from banco_pruebas import sim_firestore
    sim_firestore.install()
    tab = tablero()
    sistema, esq = prompt(tab, args.tablero), esquema(tab, args.tablero)
    with open(VARA, encoding="utf-8") as f:
        vara = json.load(f)
    quiero = {x.strip().upper() for x in args.solo.split(",") if x.strip()}
    mensajes = [m for m in vara["mensajes"]
                if not quiero or m["id"] in quiero]
    print(f"TABLERO: {len(tab['rubros'])} rubros, "
          f"{len(tab['conceptos'])} conceptos, "
          f"~{len(sistema) // 4} tokens de sistema")

    def uno(m):
        try:
            ficha, ms = traducir(m["texto"], args.modelo, sistema, esq)
        except Exception as e:  # noqa: BLE001 — un mensaje caido no tumba
            ficha, ms = {"_error": f"{type(e).__name__}: {str(e)[:120]}"}, 0
        return m, ficha, ms

    with cf.ThreadPoolExecutor(args.hilos) as ex:
        filas = list(ex.map(uno, mensajes))

    total_ok = total_de = 0
    por_grupo: dict = {}
    crudo, lat = [], []
    for m, ficha, ms in filas:
        r = puntuar(m, ficha, tab)
        total_ok += r["ok"]
        total_de += r["de"]
        g = por_grupo.setdefault(m["grupo"], [0, 0])
        g[0] += r["ok"]
        g[1] += r["de"]
        lat.append(ms)
        marca = "OK" if r["ok"] == r["de"] else "XX"
        print(f"{marca} {m['id']} {r['ok']}/{r['de']} partes={r['partes']} "
              f"copias={r['copias']} fuera={r['fuera_de_lista']} {ms}ms  "
              f"{m['texto'][:60]}")
        for f in r["fallas"]:
            print(f"      - {f}")
        if ficha.get("_error") or ficha.get("_roto"):
            print(f"      ! {ficha}")
        crudo.append({"id": m["id"], "texto": m["texto"], "ficha": ficha,
                      "ms": ms, **r})
    lat.sort()
    print(f"\n{args.modelo.upper()} tablero {args.tablero}: {total_ok} de {total_de} "
          f"({100 * total_ok // max(total_de, 1)}%)   latencia p50 "
          f"{lat[len(lat) // 2]}ms p90 {lat[int(len(lat) * .9) - 1]}ms")
    for g, (o, d) in por_grupo.items():
        print(f"   {g:<8} {o}/{d}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(crudo, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
