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
            --interprete <modelo>: el interprete, las preguntas de si o no y la revision con otro modelo; el
            redactor sigue con el de config. Para medir si el techo es el modelo (1-oct). No toca app/.

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
      produccion las charlas reales cosechadas de produccion, sin casillas
    """
    if vara == "produccion":
        # Las charlas reales de Martin, de `cosecha.py`. Sin casillas: se juzgan
        # con los invariantes de produccion y sirven para grabar al modelo con
        # las preguntas como las escribe el cliente de verdad.
        return [{"id": c["id"], "grupo": "P", "clase": f"real, {c['desde']}",
                 "turnos": [{"texto": t["texto"], "casillas": []} for t in c["turnos"]]}
                for c in (json.loads(x) for x in open("banco_pruebas/cosecha_produccion.jsonl", encoding="utf-8"))]
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


# ══ LA GRABACION DEL MODELO (2-oct) ═════════════════════════════════════════
#
# POR QUE. Hasta el 1-oct cada corrida llamaba al modelo y guardaba solo lo que
# el codigo hizo despues. Asi cada prueba del codigo gastaba cuota, y el azar
# del modelo tapaba si el codigo habia mejorado. Ahora cada turno guarda lo
# CRUDO que devolvio el modelo en cada paso —las piezas, las preguntas de si o
# no, la revision, el texto del redactor— y lo que el codigo le entrego al
# redactor, los hechos. Con `--reproducir <etiqueta>` el banco corre el codigo
# de hoy sobre esa traduccion real, sin llamar al modelo y gratis.
#
# Lo que se juzga al reproducir es el CODIGO: las casillas se miran sobre los
# hechos, que es lo que el codigo arma con lo que entrego el modelo. Si el
# codigo de hoy pide un paso que la grabacion no tiene —una revision que antes
# no se pedia—, el turno queda "sin grabacion" y no se juzga.

class SinGrabacion(Exception):
    pass


_TURNO: dict = {"crudas": [], "hechos": None, "reproducir": None}
# La gratis tiene tope de pedidos por minuto: a la velocidad del banco el 2-oct
# devolvio 368 rechazos y 25 de 42 charlas salieron con el aviso de demanda.
# Con --pausa se espera entre turnos; con la paga no hace falta.
PAUSA = {"seg": 0.0}
_SIN_MODELO = "estoy con mucha demanda"


def _instalar_grabador():
    """Envuelve `tablero._pedir` y `tablero.turno` una sola vez: graba cada
    salida cruda y los hechos del turno; si hay grabacion cargada, la devuelve
    en vez de llamar al modelo."""
    from app.core import tablero as T
    if getattr(T._pedir, "_grabador", False):
        return
    pedir, turno = T._pedir, T.turno

    async def _pedir(cli, msgs, temp, formato, trace_id, uso, paso):
        cola = _TURNO["reproducir"]
        if cola is not None:
            i = next((k for k, x in enumerate(cola) if x["paso"] == paso), None)
            if i is None:
                raise SinGrabacion(paso)
            salida = cola.pop(i)["salida"]
            uso.append({"paso": paso, "entrada": 0, "salida": 0, "cache": 0})
        else:
            salida = await pedir(cli, msgs, temp, formato, trace_id, uso, paso)
        _TURNO["crudas"].append({"paso": paso, "salida": salida})
        return salida

    async def _turno(*a, **k):
        r = await turno(*a, **k)
        _TURNO["hechos"] = r.get("hechos")
        return r
    _pedir._grabador = True
    T._pedir, T.turno = _pedir, _turno


def texto_de_hechos(hechos) -> str:
    """Los hechos como texto para las casillas: cada string, renglon por renglon
    —el detalle de una cuenta trae sus "1x ..." y sus "Total:"—, y el JSON."""
    out = []

    def junta(x):
        if isinstance(x, dict):
            for v in x.values():
                junta(v)
        elif isinstance(x, list):
            for v in x:
                junta(v)
        elif isinstance(x, (str, int, float)) and not isinstance(x, bool):
            out.append(str(x))
    junta(hechos or [])
    return "\n".join(out) + "\n" + json.dumps(hechos or [], ensure_ascii=False, default=str)


_PIDE_PREGUNTAR = ("pregunta_al_cliente", "confirmar_pedido", "falta_elegir", "ambiguo")


def nota_codigo(k, texto_codigo, respuestas):
    """Una casilla sobre los hechos. La jerga es de la redaccion y no aplica;
    la repregunta es que el codigo le pidio al redactor preguntar."""
    if k["tipo"] == "no_patron":
        return None
    if k["tipo"] == "pregunta":
        return any(x in texto_codigo for x in _PIDE_PREGUNTAR)
    if k["tipo"] in ("alguna", "todas"):
        notas = [nota_codigo(o, texto_codigo, respuestas) for o in k["opciones"]]
        validas = [n for n in notas if n is not None]
        if not validas:
            return None
        return any(n is True for n in validas) if k["tipo"] == "alguna" else all(n is True for n in validas)
    return nota_casilla(k, [], texto_codigo, respuestas)


def correr_clon(charla, n_corrida=0, grabado=None):
    """Produccion tal cual: el webhook entero por el clon, turno por turno.
    Desde el 27-sep se espian las llamadas del agente adentro del webhook; desde
    el 2-oct se graba lo crudo del modelo. Con `grabado` —los turnos de una
    corrida guardada— se reproduce sin llamar al modelo."""
    import asyncio
    from banco_pruebas import clon_produccion as C
    from banco_pruebas.pedido_agente import espiar
    _instalar_grabador()
    uid = f"sonda_{charla['id']}_{n_corrida}"
    C.reiniciar_cliente(uid)
    respuestas, turnos, historia = [], [], []
    for i, t in enumerate(charla["turnos"], 1):
        if PAUSA["seg"] and grabado is None:
            time.sleep(PAUSA["seg"])
        _TURNO.update(crudas=[], hechos=None,
                      reproducir=None if grabado is None else
                      [dict(x) for x in (grabado[i - 1].get("crudas_modelo") or [])] if i <= len(grabado) else [])
        sin = False
        try:
            with espiar() as llamadas:
                partes = asyncio.run(C.turno(uid, t["texto"]))
        except SinGrabacion:
            partes, sin = [], True
        texto = "\n".join(partes)
        respuestas.append(texto)
        codigo = texto_de_hechos(_TURNO["hechos"])
        casillas = (None if sin else
                    [(k["n"], nota_codigo(k, codigo, respuestas)) for k in t["casillas"]] if grabado is not None
                    else _casillas(charla, t, llamadas, texto, respuestas, historia))
        crudas, vueltas = _guardadas(llamadas)
        turnos.append({"turno": i, "texto": t["texto"], "casillas": casillas or [], "plata_no_vista": [],
                       "vacia": not texto.strip(), "llamadas": crudas, "vueltas": vueltas,
                       "respuesta": texto, "uso": list(llamadas.uso),
                       "crudas_modelo": list(_TURNO["crudas"]), "texto_codigo": codigo,
                       "sin_grabacion": sin})
    _TURNO["reproducir"] = None
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
    if f["id"] not in vara or not f["etiqueta"].startswith(("v58", "tab", "rep")):
        return f
    # Al reproducir se juzga el codigo: las casillas miran los hechos.
    campo = "texto_codigo" if f["etiqueta"].startswith("rep") else "respuesta"
    respuestas = [t["respuesta"] for t in f["turnos"]]
    for t, tv in zip(f["turnos"], vara[f["id"]]["turnos"]):
        if t.get("sin_grabacion"):
            t["casillas"] = []
            continue
        nota = nota_codigo if campo == "texto_codigo" else (lambda k, x, r: nota_casilla(k, [], x, r))
        t["casillas"] = [(k["n"], nota(k, t.get(campo) or "", respuestas[:t["turno"]])) for k in tv["casillas"]]
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


# EL FRENO DE GASTO (1-oct). Esa noche las tandas con la clave paga agotaron
# el credito prepago y produccion, que usa esa clave, quedo sin modelo. La
# calculadora existia y no se miraba antes de cada tanda: ahora la mira el
# banco, y con la paga no corre si la estimacion pasa el tope. Con la gratis
# solo informa. El tope es por proceso: tres corridas en paralelo, tres topes.
TOPE_DOLARES = 0.25


def frenar_por_costo(cola: list, modelo: str, tope: float) -> bool:
    """True si se puede correr."""
    from banco_pruebas import costo
    if not cola:
        return True
    turnos = sum(len(c["turnos"]) for c in cola) / len(cola)
    est = costo.estimar(len(cola), turnos, 1, modelo.split(" + ")[0])
    paga = "(paga)" in modelo
    print(f"costo estimado: {est['dolares']:.3f} dolares{' de la PAGA' if paga else ', gratis'} · tope {tope}")
    if paga and est["dolares"] > tope:
        print(f"FRENADO: la estimacion pasa el tope de {tope} dolares. Achica la tanda o subi --tope "
              "con la orden de Martin.")
        return False
    return True


def interprete_con(modelo: str) -> None:
    """Los pasos de interpretar del tablero con otro modelo. Solo en el banco:
    se envuelve `tablero._pedir`, el redactor queda con el de config."""
    from app.core import llm_reintento as L
    from app.core import tablero as T
    original, modelo_de_config = T._pedir, L._modelo

    async def _pedir(cli, msgs, temp, formato, trace_id, uso, paso):
        if paso == "redactar":
            return await original(cli, msgs, temp, formato, trace_id, uso, paso)
        L._modelo = lambda: modelo
        try:
            out = await original(cli, msgs, temp, formato, trace_id, uso, paso)
        finally:
            L._modelo = modelo_de_config
        uso[-1]["modelo"] = modelo
        return out
    T._pedir = _pedir


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
    interprete = opt("--interprete", "", str)
    tope = opt("--tope", TOPE_DOLARES, float)
    reproducir = opt("--reproducir", "", str)
    PAUSA["seg"] = opt("--pausa", 0.0, float)
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
    if interprete:
        interprete_con(interprete)
        modelo = f"{modelo} + interprete {interprete}"
    if camino == "tablero":  # desde el 30-sep el clon YA corre el tablero: es el turno vivo
        camino = "clon"
    hechas = set()
    try:
        hechas = {json.loads(x)["id"] for x in open(SALIDA, encoding="utf-8") if json.loads(x)["etiqueta"] == etiqueta}
    except FileNotFoundError:
        pass
    if camino in ("clon", "tablero"):
        hilos = 1  # el conector del clon es uno solo: los turnos van de a uno
    grabadas = {}
    if reproducir:
        grabadas = {json.loads(x)["id"]: json.loads(x)["turnos"] for x in open(SALIDA, encoding="utf-8")
                    if json.loads(x)["etiqueta"] == reproducir}
        if not etiqueta.startswith("rep"):
            sys.exit("al reproducir, la etiqueta empieza con rep: se juzga el codigo, no la respuesta")
    cola = [c for c in charlas(vara) if (not pedidas or c["id"] in pedidas) and c["id"] not in hechas
            and (not reproducir or (c["id"] in grabadas and any(t.get("crudas_modelo") for t in grabadas[c["id"]])))]
    print(f"{modelo} · {len(cola)} charlas · hilos {hilos} · etiqueta {etiqueta}")
    if reproducir:
        print(f"REPRODUCE {reproducir}: sin llamar al modelo, {len(cola)} charlas grabadas")
    elif not frenar_por_costo(cola, modelo, tope):
        return
    candado = threading.Lock()

    def una(c):
        t0 = time.time()
        turnos = correr_agente(c) if camino == "agente" else correr_clon(c, grabado=grabadas.get(c["id"]))
        # SIN MODELO NO SE GUARDA (2-oct): un turno que salio con el aviso de
        # demanda es la cuota, no el bot. La charla no se escribe y la tanda
        # para; la proxima corrida con la misma etiqueta sigue desde aca.
        if not grabadas and any(_SIN_MODELO in (t.get("respuesta") or "") for t in turnos):
            raise SinCuota(f"{c['id']}: el modelo no contesto, se para la tanda")
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
