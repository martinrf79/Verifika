"""SONDA DE CHARLAS — el loop de herramientas en charlas de varios turnos (26-sep-2026).

La sonda del modelo mide un turno por vez. Esta corre las charlas de las
varas del repo —`vara_charlas*.json`, cada turno con sus casillas— turno por
turno, con la charla entera en el historial y las herramientas del banco del
asistente, que leen la fuente real. La memoria es la del propio historial: no
hay libreta. Es la pregunta de la memoria activa: ¿resuelve lo lejano solo?

Las casillas se traducen a lo que se ve en un loop de herramientas:
  referencia / responde_sobre  el modelo del producto aparece en lo que llamo o en lo que dijo
  consulta     busco ese rubro, o pidio un producto de ese rubro
  condicion    el valor viaja en una busqueda; excluir va en sin_marca
  envio        cotizo ese destino
  cuenta       llamo a calcular
  pregunta     repregunto
  nombra       la palabra viaja en alguna llamada
  tema         consulto esa politica
  sin_rubro    no volvio a buscar ese rubro
  barato/orden busco ordenado; si contesto sin buscar se anota aparte
  cantidad     esa cantidad en calcular o comprar
  sin_condicion / sin_umbral_inventado  no excluyo ni invento un tope
Y dos invariantes por turno: toda cifra de plata vino de una herramienta, y la
respuesta no esta vacia. Tambien se anota el caché que informa la API.

  python3 -m banco_pruebas.sonda_charlas                 todas
  python3 -m banco_pruebas.sonda_charlas CH1 CH9         solo esas
  opciones: --hilos 1  --temp 0.2  --etiqueta base  --regla-dura
"""
import glob
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from banco_pruebas import banco_asistente as BA
from banco_pruebas.sonda_modelo import REGLA_DURA, S_VENDEDOR, SinCuota, _cliente, _llamar, _n, _plata

SALIDA = "banco_pruebas/sonda_charlas_corridas.jsonl"
MODELOS = sorted({(_n(p["modelo"]), p["categoria"]) for p in BA.PRODUCTOS if len(p["modelo"]) > 2},
                 key=lambda m: -len(m[0]))


def charlas():
    out = []
    for f in sorted(glob.glob("banco_pruebas/vara_charlas*.json")):
        sufijo = re.sub(r".*vara_charlas_?|\.json", "", f)
        for c in json.load(open(f, encoding="utf-8"))["charlas"]:
            out.append({**c, "id": c["id"] + (f"_{sufijo}" if sufijo else "")})
    return out


COLORES = sorted({_n(p["color"]) for p in BA.PRODUCTOS if p["color"]}, key=len, reverse=True)


def _mostrados(texto):
    """Los productos del catalogo en el orden en que aparecen en la respuesta:
    modelo y color, porque "el segundo" puede ser la otra variante del mismo."""
    t, vistos = _n(texto), []
    for m, _ in MODELOS:
        for hit in re.finditer(re.escape(m), t):
            if any(hit.start() >= a and hit.end() <= b for a, b, _ in vistos):
                continue  # un modelo mas corto adentro de uno ya visto
            cola = t[hit.end():hit.end() + 30]
            color = next((c for c in COLORES if c in cola), "")
            vistos.append((hit.start(), hit.end(), (m + " " + color).strip()))
    lista = []
    for _, _, e in sorted(vistos):
        if e not in lista:
            lista.append(e)
    return lista


def _modelo_de(casilla, respuestas):
    if casilla.get("modelo"):
        return _n(casilla["modelo"])
    lista = _mostrados(respuestas[casilla["de_turno"] - 1]) if casilla.get("de_turno", 0) <= len(respuestas) else []
    pos = casilla.get("posicion", 0)
    return lista[pos - 1] if 0 < pos <= len(lista) else None


def nota_casilla(k, llamadas, texto, respuestas):
    tipo, args = k["tipo"], _n(json.dumps([a for _, a in llamadas], ensure_ascii=False))
    busq = [a for n, a in llamadas if n == "buscar"]
    if tipo in ("referencia", "responde_sobre"):
        m = _modelo_de(k, respuestas)
        if m is None:
            return None
        return all(w in _n(texto) for w in m.split()) or (tipo == "referencia" and all(w in args for w in m.split()))
    if tipo == "consulta":
        cat = _n(k["categoria"])[:5]
        if any(cat in _n(a.get("rubro", "")) for a in busq):
            return True
        return any(cat in _n(c) for m, c in MODELOS if m in args)
    if tipo == "condicion":
        v = _n(k["valor"])
        if set(k.get("acepta", [])) & {"no_contiene", "evita", "distinto"}:
            return any(v in _n(a.get("sin_marca", "")) for a in busq)
        return v in _n(json.dumps(busq, ensure_ascii=False))
    if tipo == "envio":
        return any(n == "envio" and _n(k["destino"])[:5] in _n(a.get("lugar", "")) for n, a in llamadas)
    if tipo == "cuenta":
        return any(n == "calcular" for n, _ in llamadas)
    if tipo == "pregunta":
        return "?" in texto and not any(n == "comprar" for n, _ in llamadas)
    if tipo == "nombra":
        return _n(k["palabra"]) in args
    if tipo == "tema":
        return any(n == "tienda" and any(_n(x)[:6] in _n(a.get("tema", "")) for x in k["acepta"])
                   for n, a in llamadas)
    if tipo == "sin_rubro":
        return not any(_n(k["categoria"])[:5] in _n(a.get("rubro", "")) for a in busq)
    if tipo in ("barato", "orden"):
        quiero = "mas_caro" if "max" in k.get("direccion", []) else "mas_barato"
        if any(a.get("orden") == quiero for a in busq):
            return True
        return "sin_herramienta" if not llamadas else False
    if tipo == "cantidad":
        cant = [int(it.get("cantidad", 0) or 0) for n, a in llamadas if n == "calcular" for it in a.get("items", [])]
        cant += [int(a.get("cantidad", 0) or 0) for n, a in llamadas if n == "comprar"]
        return k["valor"] in cant
    if tipo == "sin_condicion":
        v = _n(k["valor"])
        return not any(v in _n(a.get("sin_marca", "")) for a in busq) and not any(
            str(a.get("precio_max", "")) and int(a.get("precio_max") or 0) < int(k["valor"])
            for a in busq if k["valor"].isdigit())
    if tipo == "sin_umbral_inventado":
        return not any(a.get("precio_max") for a in busq)
    if tipo == "afirma":
        return any(_n(x) in _n(texto) for x in k["nombra"]) or "cable" in _n(texto)
    return None


def correr(charla, cli, modelo, temp, sistema):
    msgs = [{"role": "system", "content": sistema}]
    respuestas, vistos, turnos = [], "", []
    for i, t in enumerate(charla["turnos"], 1):
        msgs.append({"role": "user", "content": t["texto"]})
        llamadas, texto, uso = [], "", []
        for _ in range(5):
            r = _llamar(cli, modelo, msgs, temp, tools=BA.TOOLS, pausa=0)
            u = r.usage
            det = getattr(u, "prompt_tokens_details", None) if u else None
            uso.append({"entrada": u.prompt_tokens if u else 0,
                        "cache": (getattr(det, "cached_tokens", 0) or 0) if det else 0})
            m = r.choices[0].message
            texto = m.content or ""
            if not m.tool_calls:
                break
            msgs.append({"role": "assistant", "content": texto,
                         "tool_calls": [c.model_dump() for c in m.tool_calls]})
            for c in m.tool_calls:
                try:
                    args = json.loads(c.function.arguments or "{}")
                except ValueError:
                    args = {}
                try:
                    out = BA.CUERPOS[c.function.name](**args)
                except Exception as e:  # noqa: BLE001 — un argumento raro no tira la charla
                    out = {"error": str(e)[:100]}
                llamadas.append((c.function.name, args))
                vistos += json.dumps(out, ensure_ascii=False)
                msgs.append({"role": "tool", "tool_call_id": c.id, "content": json.dumps(out, ensure_ascii=False)})
        msgs.append({"role": "assistant", "content": texto})
        respuestas.append(texto)
        casillas = [(k["n"], nota_casilla(k, llamadas, texto, respuestas)) for k in t["casillas"]]
        visto = set(re.sub(r"\D+", " ", vistos).split())
        plata_mala = [c for c in re.findall(r"\$\s?(\d{4,})", _plata(texto)) if c not in visto]
        turnos.append({"turno": i, "texto": t["texto"], "casillas": casillas, "plata_no_vista": plata_mala,
                       "vacia": not texto.strip(), "llamadas": [f"{n}{json.dumps(a, ensure_ascii=False)}"
                                                                for n, a in llamadas],
                       "respuesta": texto, "uso": uso})
    return turnos


def informe(etiqueta):
    filas = [json.loads(x) for x in open(SALIDA, encoding="utf-8")]
    filas = [f for f in filas if f["etiqueta"] == etiqueta]
    cas = [(c, t) for f in filas for t in f["turnos"] for c in t["casillas"]]
    ok = sum(c[1] is True for c, _ in cas)
    mal = [(c, t) for c, t in cas if c[1] is False]
    sinh = sum(c[1] == "sin_herramienta" for c, _ in cas)
    na = sum(c[1] is None for c, _ in cas)
    turnos = [t for f in filas for t in f["turnos"]]
    plata = [t for t in turnos if t["plata_no_vista"]]
    charlas_ok = sum(all(c[1] in (True, None, "sin_herramienta") for t in f["turnos"] for c in t["casillas"])
                     and not any(t["plata_no_vista"] or t["vacia"] for t in f["turnos"]) for f in filas)
    print(f"\nCHARLAS · {etiqueta} · {len(filas)} charlas, {len(turnos)} turnos")
    print(f"casillas: {ok} bien, {len(mal)} mal, {sinh} contestadas sin herramienta, {na} no aplican")
    print(f"charlas enteras bien: {charlas_ok} de {len(filas)}")
    print(f"turnos con plata no vista: {len(plata)}; vacios: {sum(t['vacia'] for t in turnos)}")
    por_tipo = {}
    for c, t in mal:
        por_tipo.setdefault(c[0], []).append(t["texto"][:60])
    print("\ncasillas que fallan, por nombre:")
    for n, v in sorted(por_tipo.items(), key=lambda x: -len(x[1])):
        print(f"  {len(v):3}  {n[:50]:50}  ej: {v[0]}")
    usos = [u for t in turnos for u in t["uso"]]
    ent, cache = sum(u["entrada"] for u in usos), sum(u["cache"] for u in usos)
    print(f"\ncache: {cache} de {ent} tokens de entrada ({100 * cache // max(1, ent)}%), {len(usos)} llamadas")
    for t in plata[:5]:
        print(f"  plata no vista {t['plata_no_vista']} en: {t['texto'][:60]}")


def main():
    a = sys.argv[1:]

    def opt(nombre, defecto, tipo):
        if nombre in a:
            i = a.index(nombre)
            v = tipo(a[i + 1])
            del a[i:i + 2]
            return v
        return defecto
    hilos, temp, etiqueta = opt("--hilos", 1, int), opt("--temp", 0.2, float), opt("--etiqueta", "base", str)
    sistema = S_VENDEDOR
    if "--regla-dura" in a:
        a.remove("--regla-dura")
        sistema += REGLA_DURA
    if "--informe" in a:
        informe(etiqueta)
        return
    pedidas = set(a)
    cli, modelo = _cliente()
    nombre = modelo.replace(" (paga)", "")
    hechas = set()
    try:
        hechas = {json.loads(x)["id"] for x in open(SALIDA, encoding="utf-8") if json.loads(x)["etiqueta"] == etiqueta}
    except FileNotFoundError:
        pass
    cola = [c for c in charlas() if (not pedidas or c["id"] in pedidas) and c["id"] not in hechas]
    print(f"{modelo} · {len(cola)} charlas · temp {temp} · hilos {hilos} · etiqueta {etiqueta}")
    candado = threading.Lock()

    def una(c):
        t0 = time.time()
        turnos = correr(c, cli, nombre, temp, sistema)
        with candado:
            with open(SALIDA, "a", encoding="utf-8") as f:
                f.write(json.dumps({"etiqueta": etiqueta, "modelo": modelo, "id": c["id"], "clase": c.get("clase"),
                                    "seg": round(time.time() - t0, 1), "turnos": turnos}, ensure_ascii=False) + "\n")
            mal = [k for t in turnos for k in t["casillas"] if k[1] is False]
            print(f"{'OK ' if not mal else 'MAL'} {c['id']:10} {'; '.join(k[0] for k in mal)[:90]}", flush=True)
    try:
        with ThreadPoolExecutor(hilos) as ex:
            for fut in [ex.submit(una, c) for c in cola]:
                fut.result()
    except SinCuota as e:
        print(f"CUOTA: {e}")
    informe(etiqueta)


if __name__ == "__main__":
    main()
