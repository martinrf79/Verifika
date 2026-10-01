"""EL BANCO DE LA INTERPRETACION Y LA RESPUESTA — el unico (28-sep-2026).

Corre las charlas de la vara de las 58 (`vara_58.json`) turno por turno por el
clon de produccion: el webhook entero, el mismo codigo que el bot vivo, sobre
el doble local de Firestore con los datos del repo. De cada charla guarda la
respuesta, las llamadas a herramientas y los tokens, en
`sonda_charlas_corridas.jsonl`, con una etiqueta por corrida.

Dos notas por charla, separadas para saber donde arreglar:
  RESPUESTA        lo que recibio el cliente, con las casillas de `vara_58.json`.
  INTERPRETACION   lo que el modelo le pidio a las herramientas en el ultimo
                   turno, contra las piezas correctas de `desmenuzar.CASOS`,
                   con `pedido_agente.nota_piezas`.

Una mejora se juzga con `puerta.py`, charla por charla contra tres corridas de
base. El README de esta carpeta dice el procedimiento entero.

  python3 -m banco_pruebas.sonda_charlas --etiqueta v58_algo_1       las 68 por el clon
  python3 -m banco_pruebas.sonda_charlas C27 C46 --etiqueta prueba   solo esas
  python3 -m banco_pruebas.sonda_charlas --informe --etiqueta v58_algo_1
  opciones: --vara compleja (la de todos los dias)  --vara todas (todo, antes de un deploy)  --camino agente (el turno viejo, sin el webhook)

Hasta el 28-sep corria tambien las varas viejas, un camino simulado y uno
sobre `motor.esquema`. Salieron con los bancos viejos de interpretacion, que
estan en `archivo/banco_interpretacion_28sep/`.
"""
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from banco_pruebas import banco_asistente as BA
from banco_pruebas.sonda_modelo import SinCuota, _cliente, _n, _plata

SALIDA = "banco_pruebas/sonda_charlas_corridas.jsonl"
MODELOS = sorted({(_n(p["modelo"]), p["categoria"]) for p in BA.PRODUCTOS if len(p["modelo"]) > 2},
                 key=lambda m: -len(m[0]))


def charlas(vara="58"):
    """Que charlas corre el banco. Una sola fuente: `vara_58.json` y la memoria
    de `lista_finita.json`.

      58         las 58 y la jerga, como hasta el 1-oct
      memoria    las charlas largas de memoria
      compleja   LA DE TODOS LOS DIAS: las complejas del grupo K, la memoria y
                 diez centinelas de las 58. Lo simple se da por cubierto si sale
                 lo complejo; las centinelas avisan si no.
      todas      todo junto, antes de un deploy
    """
    if vara == "memoria":
        return json.load(open("banco_pruebas/lista_finita.json", encoding="utf-8"))["memoria"]["charlas"]
    doc = json.load(open("banco_pruebas/vara_58.json", encoding="utf-8"))
    if vara == "todas":
        return doc["charlas"] + charlas("memoria")
    if vara == "compleja":
        return ([c for c in doc["charlas"] if c["grupo"] == "K"] + charlas("memoria")
                + [c for c in doc["charlas"] if c["id"] in doc["centinelas"]])
    return [c for c in doc["charlas"] if c["grupo"] != "K"]


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


def _dice(palabra, texto):
    return any(_n(o) in _n(texto) for o in palabra.split("|"))


_MONTO = re.compile(r"\$\s?(\d{4,})")


def _total_general(texto):
    """El monto que es la suma de los totales de dos o mas bloques. Los
    totales de bloque son los renglones que empiezan con "Total"; el "Total
    final" de un reparto repite el de su bloque y no cuenta."""
    t = _plata(texto)
    bloques = [int(m) for r in t.splitlines()
               if re.match(r"\W*total\b(?!\s*final)", _n(r)) for m in _MONTO.findall(r)[-1:]]
    for x in sorted({int(m) for m in _MONTO.findall(t)}, reverse=True):
        resto = list(bloques)
        if x in resto:
            resto.remove(x)
        if len(resto) >= 2 and sum(resto) == x:
            return x
    return None


def nota_casilla(k, llamadas, texto, respuestas):
    """Una casilla de la vara de las 58: solo mira lo que recibe el cliente."""
    tipo = k["tipo"]
    if tipo == "dice":
        return all(_dice(p, texto) for p in k["palabras"])
    if tipo == "no_dice":
        return not any(_dice(p, texto) for p in k["palabras"])
    if tipo == "plata":
        return str(k["monto"]) in re.sub(r"\D+", " ", _plata(texto)).split()
    if tipo == "no_patron":
        return not re.search(k["patron"], _n(texto))
    if tipo == "todas":
        return all(nota_casilla(o, llamadas, texto, respuestas) is True for o in k["opciones"])
    if tipo == "alguna":
        return any(nota_casilla(o, llamadas, texto, respuestas) is True for o in k["opciones"])
    if tipo == "mas_barato_de":
        mostrados = _mostrados(respuestas[k["de_turno"] - 1])
        precios = {}
        for p in BA.PRODUCTOS:
            e = (_n(p["modelo"]) + " " + _n(p["color"])).strip()
            if e in mostrados:
                precios[e] = int(p["precio_ars"])
        if not precios:
            return None
        barato = min(precios, key=precios.get)
        return all(w in _n(texto) for w in barato.split()[:-1]) if " " in barato else barato in _n(texto)
    if tipo == "n_de":  # "la segunda", "el primero": el de esa posicion de lo mostrado
        mostrados = _mostrados(respuestas[k["de_turno"] - 1])
        if len(mostrados) < k["pos"]:
            return None
        return all(w in _n(texto) for w in mostrados[k["pos"] - 1].split()[:2])
    if tipo == "articulos":  # "1x Auriculares ...": ningun articulo pedido sin destino
        renglones = re.findall(r"(\d+)\s?x\s+([^\n:]+)", _n(texto))
        return all(sum(int(c) for c, nom in renglones if p in nom) >= m for p, m in k["minimos"].items())
    if tipo == "total_general":
        return _total_general(texto) is not None
    if tipo == "reparto_total":
        tot = _total_general(texto)
        return bool(tot) and str(round(tot * k["pct"] / 100)) in re.sub(r"\D+", " ", _plata(texto)).split()
    if tipo == "tope_plata":  # ningun monto de la respuesta pasa el tope
        montos = [int(x) for x in re.findall(r"\$\s?(\d{4,})", _plata(texto))]
        return bool(montos) and max(montos) <= k["monto"]
    if tipo == "pregunta":  # repregunta: con signo, o pidiendo el dato sin signo
        pide = "?" in texto or re.search(r"necesito que|decime|pasame|indicame|contame|me confirmas", _n(texto))
        return bool(pide) and not any(n == "comprar" for n, _ in llamadas)
    return None


def _casillas(charla, t, llamadas, texto, respuestas, historia):
    return [(k["n"], nota_casilla(k, [], texto, respuestas)) for k in t["casillas"]]


def _guardadas(llamadas):
    return ([f"{x['herramienta']}{json.dumps(x['args'], ensure_ascii=False)}" for x in llamadas],
            [x.get("vuelta") for x in llamadas])


def correr_clon(charla, n_corrida=0):
    """Produccion tal cual: el webhook entero por el clon, turno por turno.
    Desde el 27-sep se espian las llamadas del agente adentro del webhook."""
    import asyncio
    from banco_pruebas import clon_produccion as C
    from banco_pruebas.pedido_agente import espiar
    uid = f"sonda_{charla['id']}_{n_corrida}"
    C.reiniciar_cliente(uid)
    respuestas, turnos, historia = [], [], []
    for i, t in enumerate(charla["turnos"], 1):
        with espiar() as llamadas:
            partes = asyncio.run(C.turno(uid, t["texto"]))
        texto = "\n".join(partes)
        respuestas.append(texto)
        casillas = _casillas(charla, t, llamadas, texto, respuestas, historia)
        crudas, vueltas = _guardadas(llamadas)
        turnos.append({"turno": i, "texto": t["texto"], "casillas": casillas, "plata_no_vista": [],
                       "vacia": not texto.strip(), "llamadas": crudas, "vueltas": vueltas,
                       "respuesta": texto, "uso": list(llamadas.uso)})
    return turnos


def correr_agente(charla):
    """El camino nuevo, llamando al codigo de app/ tal cual."""
    import asyncio
    from app.core import agente
    from banco_pruebas import clon_produccion as C
    historial, respuestas, turnos, historia = [], [], [], []
    for i, t in enumerate(charla["turnos"], 1):
        r = asyncio.run(agente.turno(historial, t["texto"], C.TIENDA, trace_id=f"sonda_{charla['id']}"))
        texto = r["texto"]
        historial += [{"role": "user", "content": t["texto"]}, {"role": "assistant", "content": texto}]
        respuestas.append(texto)
        vistos = json.dumps([x["vuelve"] for x in r["llamadas"]], ensure_ascii=False, default=str)
        casillas = _casillas(charla, t, r["llamadas"], texto, respuestas, historia)
        visto = set(re.sub(r"\D+", " ", _plata(vistos)).split())
        plata_mala = [c for c in re.findall(r"\$\s?(\d{4,})", _plata(texto)) if c not in visto]
        crudas, vueltas = _guardadas(r["llamadas"])
        turnos.append({"turno": i, "texto": t["texto"], "casillas": casillas, "plata_no_vista": plata_mala,
                       "vacia": not texto.strip(), "llamadas": crudas, "vueltas": vueltas,
                       "respuesta": texto, "uso": r["uso"]})
    return turnos


def _recalificar(f):
    """La vara de las 58 mira solo la respuesta: se recalifica desde lo guardado."""
    vara = {c["id"]: c for c in charlas("todas")}
    if f["id"] not in vara or not f["etiqueta"].startswith(("v58", "tab")):
        return f
    respuestas = [t["respuesta"] for t in f["turnos"]]
    for t, tv in zip(f["turnos"], vara[f["id"]]["turnos"]):
        t["casillas"] = [(k["n"], nota_casilla(k, [], t["respuesta"], respuestas[:t["turno"]]))
                         for k in tv["casillas"]]
    return f


def informe(etiqueta):
    filas = cargar(etiqueta)
    cas = [(c, t) for f in filas for t in f["turnos"] for c in t["casillas"]]
    ok = sum(c[1] is True for c, _ in cas)
    mal = [(c, t) for c, t in cas if c[1] is False]
    sinh = sum(c[1] == "sin_herramienta" for c, _ in cas)
    na = sum(c[1] is None for c, _ in cas)
    turnos = [t for f in filas for t in f["turnos"]]
    plata = [t for t in turnos if t["plata_no_vista"]]
    charlas_ok = sum(respuesta_ok(f) for f in filas)
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
    if etiqueta.startswith("v58"):
        informe_interpretacion(filas)


def respuesta_ok(f) -> bool:
    """La charla entera bien por lo que recibio el cliente. `f` ya recalificada."""
    return (all(c[1] in (True, None, "sin_herramienta") for t in f["turnos"] for c in t["casillas"])
            and not any(t["plata_no_vista"] or t["vacia"] for t in f["turnos"]))


def interpretacion_de(f, caso) -> dict:
    """Las llamadas del ultimo turno contra las piezas del caso; las de los
    turnos anteriores cubren solo consultas."""
    from banco_pruebas.pedido_agente import llamadas_de, nota_piezas
    t = f["turnos"][-1]
    ll = t.get("llamadas") or []
    if t.get("vueltas"):
        ll = [{**x, "vuelta": v} for x, v in zip(llamadas_de(ll), t["vueltas"])]
    previas = [x for tt in f["turnos"][:-1] for x in (tt.get("llamadas") or [])]
    return nota_piezas(caso, ll, t["respuesta"], previas)


def cargar(etiqueta) -> list:
    """Las charlas guardadas de una etiqueta, recalificadas con la vara de hoy."""
    filas = [json.loads(x) for x in open(SALIDA, encoding="utf-8")]
    return [_recalificar(f) for f in filas if f["etiqueta"] == etiqueta]


def informe_interpretacion(filas):
    """LO QUE EL MODELO LE PIDIO AL CODIGO en el ultimo turno de cada charla,
    contra las piezas de `desmenuzar.CASOS`. Sin llamar al modelo."""
    from banco_pruebas.desmenuzar import CASOS
    from banco_pruebas.pedido_agente import nota_piezas, preparar_sin_modelo
    casos = {c[0]: c for c in CASOS}
    # Una charla sin llamadas puede estar bien —"la capital de Francia"—: lo
    # que se mira es si la CORRIDA guardo llamadas, no cada charla.
    guardo = any(t.get("llamadas") for f in filas for t in f["turnos"])
    con = [f for f in filas if f["id"] in casos] if guardo else []
    print(f"\nINTERPRETACION · las llamadas del ultimo turno contra las piezas de desmenuzar")
    if not con:
        print("  estas corridas no guardaron llamadas: el clon las guarda desde el 27-sep")
        return
    preparar_sin_modelo()
    piezas = bien = enteras = 0
    malos = []
    for f in con:
        t = f["turnos"][-1]
        n = interpretacion_de(f, casos[f["id"]])
        piezas += n["piezas"]
        bien += n["bien"]
        enteras += n["bien"] == n["piezas"]
        if n["bien"] < n["piezas"]:
            malos.append((f["id"], n["detalle"], t["texto"]))
    print(f"  piezas bien: {bien} de {piezas} · mensajes enteros: {enteras} de {len(con)}")
    for cid, det, txt in sorted(malos):
        print(f"    {cid}  {det[:80]}   ({txt[:40]})")


def main():
    a = sys.argv[1:]

    def opt(nombre, defecto, tipo):
        if nombre in a:
            i = a.index(nombre)
            v = tipo(a[i + 1])
            del a[i:i + 2]
            return v
        return defecto
    hilos, etiqueta = opt("--hilos", 1, int), opt("--etiqueta", "base", str)
    vara = opt("--vara", "58", str)
    camino = opt("--camino", "clon", str)
    if camino not in ("clon", "agente", "tablero"):
        sys.exit(f"camino {camino}: solo hay clon, agente y tablero")
    if etiqueta == "base":
        etiqueta = f"v58_{camino}"
    if "--informe" in a:
        informe(etiqueta)
        return
    pedidas = set(a)
    from banco_pruebas import clon_produccion as C
    C.preparar_entorno()  # ANTES de importar app.config: si no, la clave y la tienda quedan mal
    C.instalar()
    _, modelo = _cliente()
    if camino == "tablero":  # desde el 30-sep el clon YA corre el tablero: es el turno vivo
        camino = "clon"
    hechas = set()
    try:
        hechas = {json.loads(x)["id"] for x in open(SALIDA, encoding="utf-8") if json.loads(x)["etiqueta"] == etiqueta}
    except FileNotFoundError:
        pass
    if camino in ("clon", "tablero"):
        hilos = 1  # el conector del clon es uno solo: los turnos van de a uno
    cola = [c for c in charlas(vara) if (not pedidas or c["id"] in pedidas) and c["id"] not in hechas]
    print(f"{modelo} · {len(cola)} charlas · hilos {hilos} · etiqueta {etiqueta}")
    candado = threading.Lock()

    def una(c):
        t0 = time.time()
        turnos = correr_agente(c) if camino == "agente" else correr_clon(c)
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
