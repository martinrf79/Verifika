"""EL FLUJO NUEVO DE PUNTA A PUNTA, CON EL CONTRATO DE LA FICHA 96 (15-nov-2026).

Orden de Martin del 15-nov: la FICHA 96 pasada a codigo, en el banco. Cada paso es una funcion con su entrada y su salida;
lo que pasa entre ellos es el contrato. Un nexo que todavia no existe devuelve "repreguntar", asi el flujo no se corta.

  paso 1, la llamada 0   el modelo separa, traduce y marca el lugar de envio. Tres campos por linea: fragmento, busqueda
                         y destino. Es la v1 del engranaje 0 mas el lugar, que se midio que el texto suelto no alcanza:
                         el padron inventa "el ojito" como Salta. Gemini, el de produccion, por la clave gratis.
  paso 2, el ruteo       con busqueda, producto; con fragmento, tema de la FAQ; con destino, ademas envio. Con busqueda,
                         ademas el nombrado, que corre si nombra marca o modelo; con palabras despues del producto, ademas
                         condicion. Sin preguntarle nada mas al modelo.
  paso 3, embeddings     un pedido por mensaje: las busquedas y fragmentos. En el banco, del cache de la sesion.
  paso 4, los nexos      destino, por el codigo de produccion; rubro y producto, `nexo_rubro`; tema de la FAQ, `nexo_tema`,
                         sobre todas las lineas; nombrado, `nexo_nombrado`, cuando la busqueda nombra marca o modelo,
                         y su respuesta reemplaza a la del producto; condicion, `nexo_condicion`, desde el 16-nov, sobre
                         el rubro que eligieron los otros dos, salvo que el nombrado diga exists: ata, no hay o
                         repregunta, y su respuesta reemplaza a la del producto y a la del nombrado ambiguo.
  paso 5, Jev            decidido el 15-nov en `nexo_tema`, contra la llamada corta de Gemini: lo dudoso del tema lo
                         confirma Jev, eligiendo entre los tres candidatos o ninguno. Desde el 16-nov tambien lo dudoso
                         del producto, `nexo_rubro`: entre los cinco candidatos o ninguno. En el banco, lo grabado.
  paso 6, el filtro      lo elegido tiene que estar entre los candidatos y en la fuente.
  paso 7, redactar       el codigo, solo con el contrato.
  paso 8, la memoria     los ids mostrados.

LA VARA, escrita antes de correr, sobre `nuevas70` y `nuevas70b`:
  la llamada 0   el rubro pedido con el primer rubro de lo que tradujo, y los destinos: acierta e inventa, con el codigo
                 de lugares sobre el campo destino. En nuevas70 los destinos son los `d` de cada cosa; en nuevas70b,
                 `momento0_b.DESTINOS`.
  el flujo       los 140 mensajes pasan sin cortarse; cuantas lineas va a cada nexo y con que veredicto; ninguna fila
                 citada fuera del catalogo.
  la prevision   cuantas lineas esperan a cada nexo que falta, con ejemplos: es la carga de lo que sigue.

    python3 banco_pruebas/flujo/flujo_nuevo.py --llamada0        # la llamada 0 con la gratis, retoma lo que falta
    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/flujo/flujo_nuevo.py --embeddings
    python3 banco_pruebas/flujo/flujo_nuevo.py [--ver]           # el flujo y la vara, sin gasto
"""
import collections
import dataclasses
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from entorno import GRABADO, L0, filas_llamada0, grabado, sin_llamada0_vieja  # noqa: E402

import engranaje0 as E  # noqa: E402
import nexo_rubro as NR  # noqa: E402

LLAMADA0 = os.path.join(GRABADO, "flujo_nuevo_llamada0.jsonl")
PUNTAJES = grabado("flujo_nuevo_puntajes.json")
PROMPT = E.PROMPT["v1"].replace("No contestes", """- destino: el lugar a donde hay que enviarlo, solo si el cliente lo
  dijo; si no, vacio.
No contestes""")
# El esquema de tres campos de la v1 y la v2, el del bot hasta el 18-nov. Desde el 18-nov el bot usa el de la v7,
# `app/core/flujo/nuevo/llamada0.ESQUEMA`, con el producto y las condiciones en dos campos.
_S = {"type": "string"}
ESQUEMA = {"type": "object", "additionalProperties": False, "required": ["lineas"], "properties": {"lineas": {
    "type": "array", "items": {"type": "object", "additionalProperties": False,
                               "required": ["fragmento", "busqueda", "destino"],
                               "properties": {"fragmento": _S, "busqueda": _S, "destino": _S}}}}}


# ══ EL CONTRATO, EL RUTEO, LOS NEXOS Y REDACTAR, EN app/ DESDE EL 17-NOV ═════
# Viven en `app/core/flujo/nuevo/contrato.py`, una sola copia: aca, los bancos, la llamada 0 grabada y la vara.
from app.core.flujo.nuevo import contrato as _C  # noqa: E402
from app.core.flujo.nuevo.contrato import (  # noqa: E402,F401
    Linea, Resultado, filtro, flujo, memoria, nexo_condicion, nexo_destino, nexo_nombrado, nexo_producto, nexo_tema, nexos,
    pendiente, redactar, ruteo)


# ══ LOS BANCOS ═══════════════════════════════════════════════════════════════
def bancos():
    """[(banco, id, mensaje, [(raices, rubro esperado o 'ninguno')], [destinos esperados])]."""
    import momento0_b as B
    from nuevas70 import CASOS as C1
    from nuevas70b import CASOS as C2
    esp = E._esperado()
    out = [("nuevas70", cid, t, [(c["en"], esp[(cid, i)]) for i, c in enumerate(cs) if (cid, i) in esp],
            [d for c in cs for d in c.get("d") or []]) for cid, t, cs in C1]
    out += [("nuevas70b", cid, t, [(r, x) for r, x in cs if x], B.DESTINOS.get(cid, [])) for cid, t, cs in C2]
    return out


# ══ PASO 1, LA LLAMADA 0 ═════════════════════════════════════════════════════
def correr_llamada0():
    sin_llamada0_vieja()
    from openai import OpenAI
    from app.config import get_settings
    s = get_settings()
    paga = bool(os.environ.get("MARTIN_AUTORIZO_LA_PAGA"))
    cli = OpenAI(api_key=os.environ["GEMINI_API_KEY_PROD" if paga else "GEMINI_API_KEY"].split()[0],
                 base_url=s.GEMINI_BASE_URL)
    hechas = {(r["banco"], r["id"]) for r in map(json.loads, open(LLAMADA0))} if os.path.exists(LLAMADA0) else set()
    falta = [b for b in bancos() if (b[0], b[1]) not in hechas]
    print(f"[llamada 0, {s.GEMINI_MODEL}, clave {'paga' if paga else 'gratis'}: {len(falta)} por correr]", flush=True)
    for banco, cid, texto, _, _ in falta:
        fila = {"banco": banco, "id": cid, "clave": "paga" if paga else "gratis"}
        for intento in range(5):
            try:
                t0 = time.time()
                r = cli.chat.completions.create(
                    model=s.GEMINI_MODEL, reasoning_effort="low",
                    messages=[{"role": "system", "content": PROMPT}, {"role": "user", "content": f"MENSAJE DEL CLIENTE: {texto}"}],
                    response_format={"type": "json_schema", "json_schema": {"name": "lineas", "strict": True, "schema": ESQUEMA}})
                crudo = r.choices[0].message.content or ""
                t = re.sub(r"^```(?:json)?|```$", "", crudo.strip(), flags=re.M).strip()
                salida = json.loads(t[t.find("{"):t.rfind("}") + 1])
                fila["segundos"] = round(time.time() - t0, 2)
                if E.valido(salida):
                    fila["salida"] = salida
                    break
            except Exception as ex:  # noqa: BLE001
                fila["error"] = f"{type(ex).__name__}: {str(ex)[:200]}"
                print(f"  {banco} {cid} intento {intento}: {fila['error']}", flush=True)
                time.sleep(20 * (intento + 1))
        if fila.get("salida"):
            with open(LLAMADA0, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
        time.sleep(4)


def llamada0():
    """{(banco, id): [Linea]} de lo grabado, con la llamada 0 de FLUJO_L0, `entorno.filas_llamada0`."""
    out = {}
    for r in filas_llamada0("flujo_nuevo_llamada0.jsonl", ("nuevas70", "nuevas70b")):
        out[(r["banco"], r["id"])] = [Linea(str(l.get("fragmento") or ""), str(l.get("busqueda") or "").strip(),
                                            str(l.get("destino") or "").strip()) for l in r["salida"]["lineas"]]
    return out


# ══ PASO 3, EMBEDDINGS ═══════════════════════════════════════════════════════
def embeddings():
    """Los puntajes de cada busqueda contra rubros y productos. Los vectores de la tienda ya estan en el cache."""
    _, alias, rubros, modelos = NR.fuente()
    ms = list(modelos)
    qs = sorted({l.busqueda for ls in llamada0().values() for l in ls} - {""})
    import embeddings as EMB
    cache = EMB.cargar()
    faltan = [q for q in qs if f"{EMB.CONSULTA}|{q}" not in cache]
    EMB.pedir(qs, EMB.CONSULTA, cache)
    ir = NR.indice_rubros(rubros, alias)
    rubros = [r for r, _ in ir]
    EMB.pedir([d for _, d in ir] + [NR.doc_producto(k, modelos[k], alias) for k in ms], EMB.DOCUMENTO, cache)
    dr = [cache[f"RETRIEVAL_DOCUMENT|{d}"] for _, d in ir]
    dp = [cache[f"RETRIEVAL_DOCUMENT|{NR.doc_producto(k, modelos[k], alias)}"] for k in ms]

    def dot(a, b):
        return round(sum(x * y for x, y in zip(a, b)), 4)
    out = {"rubros": rubros, "modelos": [list(k) for k in ms], "consultas": {}}
    for q in qs:
        x = cache[f"RETRIEVAL_QUERY|{q}"]
        out["consultas"][q] = {"r": [dot(x, d) for d in dr], "m": [dot(x, d) for d in dp]}
    json.dump(out, open(PUNTAJES, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"{len(qs)} busquedas; vectores pagados ahora {len(faltan)}, {sum(len(q) for q in faltan)} caracteres")


class Indice(_C.Indice):
    """El indice de la tienda con los puntajes grabados de este flujo, de cada nexo y lo que contesto Jev."""

    def __init__(self):
        import nexo_condicion as NC
        import nexo_tema as NT
        NR.instalar()
        cond = json.load(open(NC.PUNTAJES, encoding="utf-8")) if os.path.exists(NC.PUNTAJES) else {}
        super().__init__(NR.TID, json.load(open(PUNTAJES, encoding="utf-8")), json.load(open(NT.PUNTAJES, encoding="utf-8")),
                         cond, NC.jev_grabado())



# ══ LA VARA ══════════════════════════════════════════════════════════════════
def calificar(ver=False):
    NR.instalar()
    idx = Indice()
    por_id = {f["id"]: f for f in idx.filas}
    l0 = llamada0()
    import nexo_tema as NT
    vd = NT.veredictos("jev", "1")
    vp = NR.veredictos_jev()
    c = collections.Counter()
    cortes, ejemplos, dest_mal = [], collections.defaultdict(list), []
    salida = {}
    for banco, cid, texto, cosas, destinos in bancos():
        if (banco, cid) not in l0:
            c["sin llamada 0"] += 1
            continue
        try:
            frags = [l.fragmento for l in l0[(banco, cid)]]

            def jev(fragmento, banco=banco, cid=cid, frags=frags):
                # En el banco, lo que Jev contesto grabado en `nexo_tema_dudoso.jsonl`, corrida 1.
                return vd.get((banco, cid, frags.index(fragmento)))
            def jev_producto(busqueda, banco=banco, cid=cid):
                # En el banco, lo que Jev contesto grabado en `nexo_rubro_jev.jsonl`.
                return vp.get((banco, "flujo", cid, busqueda))
            lineas, resp, mem = flujo([Linea(l.fragmento, l.busqueda, l.destino) for l in l0[(banco, cid)]], idx, por_id,
                                      jev, jev_producto)
        except Exception as ex:  # noqa: BLE001
            cortes.append((banco, cid, f"{type(ex).__name__}: {ex}"))
            continue
        c[f"{banco} mensajes"] += 1
        # La llamada 0: el rubro pedido con el primer rubro de lo que tradujo.
        pide = {r for _, r in cosas if r != "ninguno"}
        da = {idx._rank_rubros(l.busqueda)[0] for l in lineas if l.busqueda}
        c[f"{banco} rubros pedidos"] += len(pide)
        c[f"{banco} rubros traidos"] += len(pide & da)
        # Los destinos.
        hallados = {E.n(r.datos["lugar"]) for l in lineas for r in l.nexos if r.nexo == "destino" and r.candidatos}
        esperados = {E.n(d) for d in destinos}
        bien = {e for e in esperados if any(e in h or h in e for h in hallados)}
        inventa = {h for h in hallados if not any(e in h or h in e for e in esperados)}
        c[f"{banco} destinos"] += len(esperados)
        c[f"{banco} destinos acierta"] += len(bien)
        c[f"{banco} destinos inventa"] += len(inventa)
        if esperados - bien or inventa:
            dest_mal.append((banco, cid, sorted(esperados - bien), sorted(inventa)))
        # El flujo, por nexo y veredicto.
        for l in lineas:
            for r in l.nexos:
                c[f"nexo {r.nexo} {r.veredicto}"] += 1
                if r.datos == "pendiente: el nexo no existe todavia" and len(ejemplos[r.nexo]) < 6:
                    ejemplos[r.nexo].append(l.busqueda or l.fragmento)
            for r in l.nexos:
                filas = r.datos.get("filas") if r.nexo == "condicion" and isinstance(r.datos, dict) else r.datos
                for f in (filas if r.nexo in ("producto", "nombrado", "condicion") and isinstance(filas, list) else []) or []:
                    real = por_id.get(f["id"])
                    if not real or int(float(real["precio_ars"])) != f["precio"]:
                        c["filas fuera del catalogo"] += 1
        salida[f"{banco} {cid}"] = {"mensaje": texto, "lineas": [dataclasses.asdict(l) for l in lineas],
                                    "respuesta": resp, "memoria": mem}
    print("\nEL FLUJO NUEVO DE PUNTA A PUNTA · contrato de la FICHA 96 · " +
          ("llamada 0 con tres campos, gemini" if L0 == "base" else f"llamada 0 {L0}, prompt v2"))
    for b in ("nuevas70", "nuevas70b"):
        print(f"\n  {b}: {c[b + ' mensajes']} mensajes")
        print(f"    llamada 0, rubros con el primero: {c[b + ' rubros traidos']} de {c[b + ' rubros pedidos']}")
        print(f"    destinos: acierta {c[b + ' destinos acierta']} de {c[b + ' destinos']} · inventa {c[b + ' destinos inventa']}")
    for x in dest_mal:
        print(f"    {x[0]} {x[1]} no encuentra {x[2]} · inventa {x[3]}")
    print(f"\n  el flujo: cortes {len(cortes)} · sin llamada 0 {c['sin llamada 0']} · filas fuera del catalogo "
          f"{c['filas fuera del catalogo']}")
    for k in sorted(x for x in c if x.startswith("nexo ")):
        print(f"    {k[5:]:28} {c[k]}")
    print("\n  la prevision, lo que espera a cada nexo que falta:")
    for nexo, xs in ejemplos.items():
        print(f"    {nexo}: {c['nexo ' + nexo + ' repreguntar']} lineas · por ejemplo {xs}")
    for x in cortes:
        print(f"    corte {x}")
    json.dump(salida, open(grabado("flujo_nuevo_respuestas.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    if "--llamada0" in sys.argv:
        correr_llamada0()
    elif "--embeddings" in sys.argv:
        embeddings()
    else:
        calificar("--ver" in sys.argv)
