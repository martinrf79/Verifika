"""EL LABORATORIO — charlar con el modelo directo, con la cuenta a la vista (29-sep-2026).

POR QUE EXISTE. Martin pidio probar lo que el modelo hace siempre, a veces y
nunca, hablandole directo y sin el bot entero alrededor: sin webhook, sin la
charla repetida, sin prompt de produccion si no hace falta. Cada llamada
anota los tokens de entrada y de SALIDA que devolvio el proveedor y lo que
costaria en dolares, con `costo.py`.

DOS PROVEEDORES, y ninguno toca la paga de produccion:

  gemini     SOLO la clave gratis. Si en el entorno la gratis es la misma que
             la paga, no corre.
  deepseek   la clave de DeepSeek, con su saldo. Se cobra: por eso el tope.

EL TOPE corta solo: antes de cada llamada suma lo gastado y, si pasa
`--tope` dolares, para. Default diez centavos.

  python3 -m banco_pruebas.laboratorio decir "que parlantes tenes?" --modelo deepseek-chat
  python3 -m banco_pruebas.laboratorio decir "..." --sistema prompt.txt
  python3 -m banco_pruebas.laboratorio piezas --forma A --reps 3 --modelo deepseek-chat --etiqueta lab_a
  python3 -m banco_pruebas.laboratorio informe --etiqueta lab_a
  python3 -m banco_pruebas.laboratorio saldo                     lo que queda en DeepSeek

  python3 -m banco_pruebas.laboratorio escalera --item rubro --etiqueta esc_rubro   rubro, tema o dato
  python3 -m banco_pruebas.laboratorio escalera --item rubro --etiqueta esc_rubro --informe

`escalera` mide cuanta informacion de la fuente necesita el modelo para cada
item de `lista_finita.json`, y cuantos tokens cuesta cada escalon.

`piezas` corre las charlas de `desmenuzar.CASOS` —la vara de las 58 mas la
jerga— con su prompt y su nota, y dice por caso si salio siempre, a veces o
nunca.
"""
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from banco_pruebas import costo

SALIDA = Path(__file__).resolve().parent / "laboratorio_corridas.jsonl"
TOPE = 0.10
_escribir = threading.Lock()


def cliente(modelo: str):
    from openai import OpenAI
    if "deepseek" in modelo:
        clave = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if not clave:
            sys.exit("no hay DEEPSEEK_API_KEY")
        return OpenAI(api_key=clave, base_url="https://api.deepseek.com"), modelo
    if os.environ.get("BANCO_CLAVE_PAGA", "").lower() == "true":
        # Solo con la marca con fecha de scripts/guard_clave.sh: Martin la pidio en la sesion.
        return OpenAI(api_key=os.environ["GEMINI_API_KEY_PROD"].strip(),
                      base_url="https://generativelanguage.googleapis.com/v1beta/openai/"), modelo
    gratis = (os.environ.get("GEMINI_API_KEY_FREE") or os.environ.get("GEMINI_API_KEY") or "").split()
    gratis = gratis[0] if gratis else ""
    if not gratis or gratis == (os.environ.get("GEMINI_API_KEY_PROD") or "").strip():
        sys.exit("EL LABORATORIO USA SOLO LA GEMINI GRATIS y no hay una distinta de la paga")
    return OpenAI(api_key=gratis, base_url="https://generativelanguage.googleapis.com/v1beta/openai/"), modelo


def llamar(cli, modelo: str, msgs: list, tools=None, max_tokens=None, temp=0.2) -> dict:
    """Una llamada. Aguanta el 429 de la gratis. Vuelve texto, tokens y segundos."""
    kw = {"tools": tools, "tool_choice": "auto"} if tools else {}
    if max_tokens:
        kw["max_tokens"] = max_tokens
    espera, t0 = 15, time.time()
    for intento in range(6):
        try:
            r = cli.chat.completions.create(model=modelo, messages=msgs, temperature=temp, **kw)
            break
        except Exception as e:  # noqa: BLE001 — la gratis devuelve 429/503: se aguanta
            s = str(e)
            if intento < 5 and any(c in s for c in ("429", "503", "500", "RESOURCE_EXHAUSTED", "overloaded")):
                time.sleep(espera)
                espera = min(espera * 2, 120)
                continue
            raise
    u = r.usage
    det = getattr(u, "prompt_tokens_details", None) if u else None
    cache = (getattr(det, "cached_tokens", 0) or 0) if det else 0
    if not cache and u is not None:  # DeepSeek lo informa con su propio nombre
        cache = getattr(u, "prompt_cache_hit_tokens", 0) or 0
    m = r.choices[0].message
    entrada, salida = (u.prompt_tokens, u.completion_tokens) if u else (0, 0)
    return {"texto": m.content or "", "herramientas": [c.model_dump() for c in (m.tool_calls or [])],
            "entrada": entrada, "salida": salida, "cache": cache, "seg": round(time.time() - t0, 1),
            "dolares": costo.dolares(entrada, salida, modelo, cache, pico=costo.es_pico(costo.precios()[costo.modelo_de(modelo)]))}


def anotar(fila: dict) -> None:
    with _escribir, open(SALIDA, "a", encoding="utf-8") as f:
        f.write(json.dumps(fila, ensure_ascii=False) + "\n")


# ══ DECIR: una charla corta, a mano ═════════════════════════════════════════

def decir(texto: str, modelo: str, sistema: str, etiqueta: str) -> None:
    cli, nombre = cliente(modelo)
    msgs = ([{"role": "system", "content": sistema}] if sistema else []) + [{"role": "user", "content": texto}]
    r = llamar(cli, nombre, msgs)
    anotar({"etiqueta": etiqueta, "modelo": nombre, "modo": "decir", "pregunta": texto, "entrada": r["entrada"],
            "salida_tokens": r["salida"], "cache": r["cache"], "dolares": r["dolares"], "respuesta": r["texto"]})
    print(r["texto"])
    print(f"\n[{nombre} · entrada {r['entrada']} · salida {r['salida']} · {r['dolares']:.5f} dolares · {r['seg']} s]")


# ══ PIEZAS: la traduccion del mensaje, repetida ═════════════════════════════

def piezas(forma: str, reps: int, modelo: str, etiqueta: str, tope: float, ids: list, hilos: int) -> None:
    from banco_pruebas import desmenuzar as D
    cli, nombre = cliente(modelo)
    local = threading.local()

    def _pedir(_cli, _modelo, sistema, usuario):  # la de desmenuzar, anotando la salida
        r = llamar(cli, nombre, [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}])
        local.ultimo = local.ultimo + [r] if getattr(local, "ultimo", None) else [r]
        return r["texto"], r["entrada"]
    D._pedir = _pedir
    cola = [(c, rep) for rep in range(1, reps + 1) for c in D.CASOS if not ids or c[0] in ids]
    gastado = [0.0]
    muestra = costo.estimar(len(cola), 1, 1, nombre, "interpretar")
    print(f"{nombre} · forma {forma} · {len(cola)} llamadas · estimado {muestra['dolares']:.3f} dolares · tope {tope}")

    def uno(t):
        caso, rep = t
        if gastado[0] >= tope:
            return
        local.ultimo = []
        try:
            r = D.correr(forma, caso, cli, nombre)
        except Exception as e:  # noqa: BLE001
            print(f"  {caso[0]} error {str(e)[:100]}")
            return
        usos = local.ultimo
        d = sum(u["dolares"] for u in usos)
        with _escribir:
            gastado[0] += d
        anotar({"etiqueta": etiqueta, "modelo": nombre, "modo": "piezas", "forma": forma, "id": caso[0], "rep": rep,
                "partir": r["partir"], "traducir": r["traducir"], "detalle": r["detalle"],
                "entrada": sum(u["entrada"] for u in usos), "salida_tokens": sum(u["salida"] for u in usos),
                "cache": sum(u["cache"] for u in usos), "dolares": d, "seg": sum(u["seg"] for u in usos),
                "piezas": r["piezas"]})
    with ThreadPoolExecutor(hilos) as ex:
        list(ex.map(uno, cola))
    if gastado[0] >= tope:
        print(f"TOPE: se corto en {gastado[0]:.4f} dolares")
    informe(etiqueta)


def informe(etiqueta: str) -> None:
    filas = [json.loads(x) for x in open(SALIDA, encoding="utf-8")] if SALIDA.exists() else []
    filas = [f for f in filas if f["etiqueta"] == etiqueta and f.get("modo") == "piezas"]
    if not filas:
        sys.exit(f"no hay filas con la etiqueta {etiqueta}")
    por = {}
    for f in filas:
        por.setdefault(f["id"], []).append(f["partir"] and f["traducir"] is not False)
    siempre = sorted(k for k, v in por.items() if all(v))
    nunca = sorted(k for k, v in por.items() if not any(v))
    aveces = sorted(k for k in por if k not in siempre and k not in nunca)
    e, s = sum(f["entrada"] for f in filas), sum(f["salida_tokens"] for f in filas)
    d = sum(f["dolares"] for f in filas)
    print(f"\nLABORATORIO · {etiqueta} · {filas[0]['modelo']} · {len(filas)} llamadas · {len(por)} casos")
    print(f"  SIEMPRE {len(siempre)} · A VECES {len(aveces)} · NUNCA {len(nunca)}")
    print(f"  tokens: entrada {e:,} ({e // len(filas)} por llamada) · salida {s:,} ({s // len(filas)} por llamada)")
    print(f"  costo {d:.4f} dolares · {sum(f['seg'] for f in filas) / len(filas):.1f} s por llamada")
    for k in aveces + nunca:
        dets = [f["detalle"] for f in filas if f["id"] == k and f["detalle"]]
        print(f"    {k} {sum(por[k])}/{len(por[k])}  {max(set(dets), key=dets.count)[:90] if dets else ''}")


# ══ ESCALERA: cuanta informacion necesita cada item de la lista finita ══════
#
# Un item por prueba —rubro, tema, dato—, con sus casos de `lista_finita.json`.
# Cada escalon le da al modelo un poco mas de la fuente, generado por el
# codigo: E0 nada, el modelo dice palabras comunes y el codigo las ubica con
# las mismas funciones del bot; E1 los nombres; E2 y E3 los nombres con una
# linea. Pasada 1: cada escalon una vez. Pasada 2: el escalon mas bajo con el
# mejor puntaje, cuatro veces mas, para ver que sale siempre y que a veces.

LISTA = Path(__file__).resolve().parent / "lista_finita.json"
_NO_FILTRA = {"nombre", "modelo", "descripcion", "contenido_caja", "garantia_detalle", "dimensiones",
              "caracteristicas_extra", "precio_ars"}


def _fuente():
    from banco_pruebas.peso_del_turno import TIENDA, _preparar
    import logging
    _preparar()
    logging.disable(logging.CRITICAL)
    from app.core import agente as A
    return A, TIENDA


def escalones(item: str) -> dict:
    """{nombre: texto que se suma al prompt}. Lo genera el codigo de la fuente."""
    import csv
    from collections import Counter
    A, T = _fuente()
    if item == "rubro":
        prods = list(csv.DictReader(open("data/clientes/verifika_prod/productos.csv", encoding="utf-8")))
        rubros = [c for c, _ in A.indice(T)["rubros"].items()]
        tags = {r: Counter(t.strip() for p in prods if p["categoria"] == r for t in (p["tags"] or "").split(",")
                           if t.strip() and A._n(t.strip()) != A._n(r)) for r in rubros}
        return {"E0": "", "E1": "Rubros de la tienda: " + ", ".join(rubros) + ".",
                "E2": "Rubros de la tienda: " + "; ".join(f"{r} ({', '.join(x for x, _ in tags[r].most_common(3))})"
                                                        for r in rubros) + "."}
    if item == "tema":
        from app.storage.firestore_client import get_all_faq
        faq = get_all_faq(tienda_id=T)
        kw = {t: [k for k in (d.get("keywords") or []) if A._n(k) != A._n(t.replace("_", " "))][:3]
              for t, d in faq.items()}
        return {"E0": "", "E1": "Temas de la tienda: " + ", ".join(faq) + ".",
                "E2": "Temas de la tienda: " + "; ".join(f"{t} ({', '.join(kw[t])})" for t in faq) + ".",
                "E3": "Temas de la tienda y que contesta cada uno: " + "; ".join(
                    f"{t}: {' '.join((d.get('respuesta') or '').split()[:10])}" for t, d in faq.items()) + "."}
    if item == "dato":
        from app.core.filtros_catalogo import campos_filtrables, recorrida
        tipos = {c: t for c, t in campos_filtrables(T).items() if c not in _NO_FILTRA}
        vistos = recorrida(T)["valores"]

        def linea(c, t):
            if t == "si_no":
                return f"{c}: si o no"
            if t == "numero":
                return f"{c}: numero"
            v = sorted((vistos.get(c) or {}).get("vistos", {}).items(), key=lambda x: -x[1])[:4]
            return f"{c}: {' | '.join(x for x, _ in v)}" if v else c
        return {"E0": "", "E1": "Datos de los productos: " + ", ".join(tipos) + ".",
                "E2": "Datos de los productos y como los escribe la tienda: " + "; ".join(
                    linea(c, t) for c, t in tipos.items()) + "."}
    if item == "accion":
        # Capa 2: universal, no depende de la tienda. Cada escalon suma al anterior.
        from banco_pruebas import desmenuzar as D
        defin = {"producto": "un producto nombrado: precio, stock o un dato suyo",
                 "buscar": "un rubro con condiciones u orden",
                 "envio": "costo o plazo de envio a un destino", "politica": "una regla de la tienda",
                 "compatibilidad": "si un producto anda con un equipo u otro producto",
                 "cuenta": "el total de varios productos, cantidades, destino o reparto de pago",
                 "comprar": "el cliente decide llevarse algo", "explicar": "saber general, no de la tienda",
                 "verificar": "el cliente da algo por cierto de la tienda o de un producto",
                 "repreguntar": "falta un dato del cliente o no se sabe a que se refiere",
                 "charla": "saludo, gracias o algo que no es un pedido"}
        e1 = "tipo es uno de: " + ", ".join(D.TIPOS) + "."
        e2 = "tipo es uno de estos: " + "; ".join(f"{t}: {defin[t]}" for t in D.TIPOS) + "."
        e3 = e2 + "\n" + "\n".join(D.BASE.split("\n")[1:])
        e4 = e3 + """
Ejemplos de formato, no de contenido:
"tenes la silla Zeta 9 en rojo? y si no, la mas barata" -> producto (silla zeta 9, rojo); buscar (silla, orden precio barato, depende_de 1)
"la que me dijiste primero, mandamela a Tandil" -> envio (tandil, el producto resuelto de la charla)
"me dijeron que dan 3 cuotas sin interes" -> verificar (cuotas sin interes)"""
        return {"E1": e1, "E2": e2, "E3": e3, "E4": e4}
    sys.exit(f"item sin escalones: {item}")


def _prompt(item: str, pregunta: str, extra: str) -> str:
    plural = item == "dato"
    salida = '{"valores": ["..."]}' if plural else '{"valor": "..."}'
    como = ("Usa EXACTAMENTE uno de los nombres de la lista." if extra else "Decilo en palabras comunes.")
    return (f"Sos el interprete de una tienda online de tecnologia de Argentina. No le contestas al cliente. "
            f"Del ultimo mensaje del cliente, deci {pregunta}. {como}\n" + (extra + "\n" if extra else "")
            + f"Devolve SOLO JSON: {salida}")


def _ubicar(item: str, valor: str, mensaje: str) -> str:
    """Lo que el codigo hace con la palabra del modelo: exacto o ubicado."""
    A, T = _fuente()
    if item == "rubro":
        return A._rubro(valor, T)[0] or ""
    grupo = "temas" if item == "tema" else "campos"
    nombres = A.indice(T)[grupo]
    exacto = next((k for k in nombres if A._n(k) == A._n(valor)), None)
    if exacto:
        return exacto
    cand = A.temas_de(valor, T) if item == "tema" else A.ubicar(valor, "campos", T)
    return cand[0] if cand else ""


_ACCION_SALIDA = """Parti el ultimo mensaje del cliente en piezas: una por cada cosa que pide, pregunta o afirma. Resolve "ese", "el otro", "el primero" con la charla. Traduci lo que pide que cumpla: "acorde a la crisis" es barato.
Devolve SOLO JSON: {"piezas": [{"n": 1, "tipo": "...", "texto": "...", "pregunta": "...", "rubro": "...", "tema": "...", "condiciones": ["..."], "depende_de": []}]}"""


def _uno_accion(cli, nombre, esc, extra, caso, rep, etiqueta):
    """Capa 2 con los casos y la nota de desmenuzar: pieza, tipo y dependencia."""
    from banco_pruebas import desmenuzar as D
    from banco_pruebas.sonda_modelo import _json
    sistema = ("Sos el interprete de una tienda online de tecnologia de Argentina. No le contestas al cliente.\n"
               + extra + "\n" + _ACCION_SALIDA)
    r = llamar(cli, nombre, [{"role": "system", "content": sistema}, {"role": "user", "content": D._mensaje(caso)}])
    piezas = [x for x in ((_json(r["texto"]) or {}).get("piezas") or []) if isinstance(x, dict)]
    for x in piezas:  # la capa 3 no se mide aca: rubro y tema se dan por buenos
        x["rubro_final"], x["tema_final"] = x.get("rubro"), x.get("tema")
    if piezas:
        _, _, det = D.nota(caso, piezas, con_tipo=True)
        con_tipo = D.nota(caso, piezas, con_tipo=True)[0]
        cond_mal = "condicion sin" in det
    else:
        con_tipo, cond_mal, det = False, False, "json roto"
    ok = con_tipo and not cond_mal
    fila = {"etiqueta": etiqueta, "modelo": nombre, "modo": "escalera", "item": "accion", "escalon": esc,
            "id": caso[0], "rep": rep, "ok": ok, "detalle": "" if ok else det,
            "esperado": ["|".join(e["tipos"]) for e in caso[3]], "dijo": [x.get("tipo") for x in piezas],
            "codigo": [], "entrada": r["entrada"], "salida_tokens": r["salida"], "cache": r["cache"],
            "dolares": r["dolares"], "seg": r["seg"]}
    anotar(fila)
    return fila


def _uno_escalon(cli, nombre, item, pregunta, esc, extra, caso, rep, etiqueta):
    from banco_pruebas.sonda_modelo import _json
    if item == "accion":
        return _uno_accion(cli, nombre, esc, extra, caso, rep, etiqueta)
    charla = "\n".join(caso["charla"]) if caso["charla"] else ""
    usuario = (f"CHARLA:\n{charla}\n\n" if charla else "") + f"ULTIMO MENSAJE DEL CLIENTE: {caso['mensaje']}"
    r = llamar(cli, nombre, [{"role": "system", "content": _prompt(item, pregunta, extra)},
                             {"role": "user", "content": usuario}])
    obj = _json(r["texto"]) or {}
    crudos = obj.get("valores") if item == "dato" else [obj.get("valor")]
    crudos = [str(v) for v in (crudos or []) if v]
    finales = [_ubicar(item, v, caso["mensaje"]) for v in crudos]
    ok = any(f in caso["acepta"] for f in finales)
    fila = {"etiqueta": etiqueta, "modelo": nombre, "modo": "escalera", "item": item, "escalon": esc,
            "id": caso["id"], "rep": rep, "ok": ok, "dijo": crudos, "codigo": finales,
            "entrada": r["entrada"], "salida_tokens": r["salida"], "cache": r["cache"], "dolares": r["dolares"],
            "seg": r["seg"]}
    anotar(fila)
    return fila


def _id(caso) -> str:
    return caso["id"] if isinstance(caso, dict) else caso[0]


def escalera(item: str, modelo: str, etiqueta: str, tope: float, hilos: int, reps: int, forzar: str = "") -> None:
    if item == "accion":
        from banco_pruebas.desmenuzar import CASOS
        lista = {"pregunta": "", "casos": CASOS}
    else:
        lista = json.load(open(LISTA, encoding="utf-8"))[item]
    esc = escalones(item)
    cli, nombre = cliente(modelo)
    gastado = [0.0]
    # Retoma: lo que ya esta anotado con esta etiqueta no se vuelve a pagar.
    hechos = {(f["escalon"], f["id"], f["rep"]) for x in (open(SALIDA, encoding="utf-8") if SALIDA.exists() else [])
              for f in [json.loads(x)] if f.get("etiqueta") == etiqueta and f.get("item") == item}

    def correr(trabajos):
        trabajos = [t for t in trabajos if (t[0], _id(t[1]), t[2]) not in hechos]

        def uno(t):
            if gastado[0] >= tope:
                return None
            try:
                f = _uno_escalon(cli, nombre, item, lista["pregunta"], t[0], esc[t[0]], t[1], t[2], etiqueta)
            except Exception as e:  # noqa: BLE001
                print(f"  {t[0]} {_id(t[1])} error {str(e)[:100]}")
                return None
            with _escribir:
                gastado[0] += f["dolares"]
            return f
        with ThreadPoolExecutor(hilos) as ex:
            return [f for f in ex.map(uno, trabajos) if f]

    casos = lista["casos"]
    print(f"{nombre} · {item} · {len(casos)} casos · escalones {list(esc)} · tope {tope} dolares")
    correr([(e, c, 1) for e in esc for c in casos])
    nota = _notas(etiqueta, item)
    mejor = max(v["bien"] for v in nota.values())
    cand = forzar or next(e for e in esc if nota.get(e, {}).get("bien") == mejor)
    print(f"pasada 1 lista; candidato {cand}, se repite {reps - 1} veces mas")
    correr([(cand, c, r) for r in range(2, reps + 1) for c in casos])
    informe_escalera(etiqueta, item)
    if gastado[0] >= tope:
        print(f"TOPE: se corto en {gastado[0]:.4f} dolares")


def _notas(etiqueta: str, item: str) -> dict:
    filas = [json.loads(x) for x in open(SALIDA, encoding="utf-8")]
    filas = [f for f in filas if f["etiqueta"] == etiqueta and f.get("modo") == "escalera" and f["item"] == item]
    out = {}
    for f in filas:
        e = out.setdefault(f["escalon"], {"bien": 0, "total": 0, "entrada": 0, "salida": 0, "dolares": 0.0, "casos": {}})
        e["bien"] += f["ok"]
        e["total"] += 1
        e["entrada"] += f["entrada"]
        e["salida"] += f["salida_tokens"]
        e["dolares"] += f["dolares"]
        e["casos"].setdefault(f["id"], []).append(f)
    return out


def informe_escalera(etiqueta: str, item: str) -> None:
    nota = _notas(etiqueta, item)
    if not nota:
        sys.exit(f"no hay filas de {item} con la etiqueta {etiqueta}")
    base = nota.get("E0", next(iter(nota.values())))
    base_e = base["entrada"] / base["total"]
    print(f"\nESCALERA · {item} · {etiqueta}")
    print("  escalon  bien          tokens por llamada   extra sobre E0   dolares")
    for e in sorted(nota):
        v = nota[e]
        pe = v["entrada"] / v["total"]
        print(f"  {e:7}  {v['bien']:>3}/{v['total']:<4} {100 * v['bien'] / v['total']:5.0f} %  "
              f"{pe:6.0f} + {v['salida'] / v['total']:3.0f} salida   {pe - base_e:+6.0f}         {v['dolares']:.4f}")
    rep = max(nota, key=lambda e: nota[e]["total"])
    casos = nota[rep]["casos"]
    if max(len(x) for x in casos.values()) > 1:
        siempre = [k for k, x in casos.items() if all(f["ok"] for f in x)]
        nunca = [k for k, x in casos.items() if not any(f["ok"] for f in x)]
        aveces = [k for k in casos if k not in siempre and k not in nunca]
        print(f"  en {rep}, repetido: SIEMPRE {len(siempre)} · A VECES {len(aveces)} · NUNCA {len(nunca)}")
        for k in aveces + nunca:
            x = casos[k]
            ultimo = x[-1]
            print(f"    {k} {sum(f['ok'] for f in x)}/{len(x)}  dijo {ultimo['dijo']} -> "
                  f"{ultimo.get('detalle') or ultimo['codigo']}"[:150])
    if item == "accion":  # los puntos flacos, por la accion que se esperaba
        from collections import Counter
        tot, mal = Counter(), Counter()
        for k, x in casos.items():
            for tipo in x[0]["esperado"]:
                tot[tipo] += len(x)
                mal[tipo] += sum(not f["ok"] for f in x)
        print("  por accion esperada, fallas: " + " · ".join(f"{t} {mal[t]}/{tot[t]}" for t in sorted(tot, key=lambda t: -mal[t] / tot[t])))


def main():
    a = sys.argv[1:]
    que = a.pop(0) if a else ""
    opt = costo._opt
    modelo = opt(a, "--modelo", "gemini-3.1-flash-lite")
    etiqueta = opt(a, "--etiqueta", "lab")
    if que == "decir":
        sis = opt(a, "--sistema", "")
        decir(" ".join(a), modelo, open(sis, encoding="utf-8").read() if sis else "", etiqueta)
    elif que == "piezas":
        forma, reps, tope, hilos = opt(a, "--forma", "A"), opt(a, "--reps", 3, int), \
            opt(a, "--tope", TOPE, float), opt(a, "--hilos", 4, int)
        piezas(forma, reps, modelo, etiqueta, tope, [x for x in a if not x.startswith("--")], hilos)
    elif que == "escalera":
        item = opt(a, "--item", "rubro")
        if "--informe" in a:
            informe_escalera(etiqueta, item)
        else:
            escalera(item, modelo, etiqueta, opt(a, "--tope", TOPE, float), opt(a, "--hilos", 4, int),
                     opt(a, "--reps", 5, int), opt(a, "--escalon", ""))
    elif que == "informe":
        informe(etiqueta)
    elif que == "saldo":
        import urllib.request
        q = urllib.request.Request("https://api.deepseek.com/user/balance",
                                   headers={"Authorization": "Bearer " + os.environ.get("DEEPSEEK_API_KEY", "")})
        for b in json.load(urllib.request.urlopen(q, timeout=20))["balance_infos"]:
            print(f"DeepSeek: {b['total_balance']} {b['currency']}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
