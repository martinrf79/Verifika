"""
BANCO DE MEMORIA — los turnos largos, offline y sin un solo token.

QUE MIDE. El banco de candidatos mide UN turno: que le trae el codigo al modelo
cuando el modelo pide perfecto. Este mide lo otro: que SOBREVIVE de un turno al
siguiente. Se simula el modelo perfecto igual que alla -las llamadas ideales de
cada turno estan escritas a mano- y se corre el pipeline de memoria REAL del
hub, funcion por funcion, el mismo que corre en produccion:

    construir_estado -> _memoria_texto -> _mensajes -> [llamadas] ->
    _productos_del_turno -> merge_productos -> _carrito_del_turno /
    _carrito_podado -> memoria_larga -> save_conversation

Lo unico que se reemplaza es el LLM. Si una serie falla aca, no la arregla
ningun prompt: es el estado que no se guarda o el contexto que no llega.

LAS SERIES SALEN DE LAS PRUEBAS DE MARTIN, verbatim. Son las que estresan lo
que el sistema comprime: retractaciones, referencias ordinales, destino por
item y cambios de cantidad a lo largo de doce turnos.

    python3 banco_pruebas/banco_memoria.py
"""
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas import sim_firestore  # noqa: E402

sim_firestore.install()

from app.config import get_settings  # noqa: E402
from app.core import herramientas as H  # noqa: E402
from app.core import hub_venta as HV  # noqa: E402
from app.core import reposicion as R  # noqa: E402
from app.core.estado_venta import (construir_estado, merge_productos,  # noqa: E402
                                   get_envio_localidades)
from app.core.memoria_larga import _compactar_determinista  # noqa: E402
from app.storage.firestore_client import (get_conversation,  # noqa: E402
                                          save_conversation,
                                          reset_conversation, get_all_products)

TIENDA = "verifika_prod"
S = get_settings()
CAT = [p for p in (get_all_products(tienda_id=TIENDA) or [])
       if (p.get("stock") or 0) > 0]


def uno(categoria: str, n: int = 0) -> dict:
    return [p for p in CAT if p.get("categoria") == categoria][n]


RESULTADOS = []


def caso(serie, turno, que, esperado, obtenido, ok, causa=""):
    RESULTADOS.append({"serie": serie, "turno": turno, "que": que,
                       "esperado": esperado, "obtenido": obtenido, "ok": ok,
                       "causa": causa})


# ── EL TURNO, tal cual lo corre el hub, con el LLM reemplazado ──────────────
def correr_turno(user_id: str, mensaje: str, pedidos: list,
                 respuesta: str = "ok") -> dict:
    """Un turno completo de memoria. `pedidos` son las llamadas que haria un
    modelo perfecto: [{"nombre": ..., "args": {...}}].

    Devuelve lo que el modelo VIO antes de contestar y el estado que quedo
    guardado despues.
    """
    conv = get_conversation(user_id, tienda_id=TIENDA)
    history = conv.get("history", []) or []
    estado = construir_estado(conv, None)
    memoria = HV._memoria_texto(estado, history, TIENDA)
    msgs = HV._mensajes("Verifika", memoria, history, mensaje, "instr")

    llamadas = []
    declarado = {}
    for p in pedidos:
        r = H.ejecutar(p["nombre"], p.get("args") or {}, TIENDA)
        llamadas.append({"herramienta": p["nombre"],
                         "pedido": p.get("args") or {}, "resultado": r})
        if p["nombre"] == "registrar_pedido":
            declarado = (r or {}).get("pedido") or p.get("args") or {}

    # ── la seccion 7 de procesar_venta, identica ────────────────────────
    history = history + [{"role": "user", "content": mensaje},
                         {"role": "assistant", "content": respuesta}]
    resumen = conv.get("summary", "") or ""
    descartados = history[:-(S.HISTORY_LIMIT * 2)]
    if descartados:
        # En produccion esto lo redacta el modelo; su red determinista es la
        # que corre aca, que es la que manda cuando el LLM falla.
        resumen = _compactar_determinista(resumen, descartados)
    history = history[-(S.HISTORY_LIMIT * 2):]

    vistos = merge_productos(conv.get("productos_vistos") or [],
                             HV._productos_del_turno(llamadas,
                                                     turno=len(history) // 2))
    carrito = HV._carrito_del_turno(llamadas)
    bajas = []
    if not carrito:
        carrito, bajas = HV._carrito_podado(
            conv.get("carrito_vigente") or [], declarado)
    declarado_ahora = HV._declarados(declarado)
    descartados = HV._descartados_nuevos(
        conv.get("descartados") or [], bajas, carrito,
        declarado_antes=conv.get("ultimo_declarado") or [],
        declarado_ahora=declarado_ahora)
    locs = get_envio_localidades() or (conv.get("ultimas_localidades") or [])
    bloque = R._bloque_presupuesto(llamadas)
    save_conversation(user_id, history, resumen, tienda_id=TIENDA,
                      estado_conversacion="en_curso",
                      productos_vistos=vistos, carrito_vigente=carrito,
                      descartados=descartados,
                      ultimo_declarado=(declarado_ahora or
                                        conv.get("ultimo_declarado") or []),
                      ultima_localidad=(locs[-1] if locs else ""),
                      ultimas_localidades=locs,
                      ultimo_presupuesto=(bloque or
                                          conv.get("ultimo_presupuesto") or None))
    return {"vio": "\n".join(str(m.get("content")) for m in msgs),
            "memoria": memoria, "carrito": carrito, "vistos": vistos,
            "descartados": descartados, "llamadas": llamadas}


def buscar(categoria=None, descripcion=None, **kw):
    return {"nombre": "buscar_productos",
            "args": {"categoria": categoria, "descripcion": descripcion, **kw}}


def declarar(items, **kw):
    return {"nombre": "registrar_pedido",
            "args": {"items": items, **kw}}


def presupuesto(items, destinos=None, pago=None):
    args = {"items": items}
    if destinos:
        args["destinos"] = destinos
    if pago:
        args["pago"] = pago
    return {"nombre": "armar_presupuesto", "args": args}


# ── SERIE 1 — carrito, cambio de producto y presupuesto ────────────────────
def serie_1():
    u = "serie1"
    reset_conversation(u, tienda_id=TIENDA)
    mouse = uno("mouse")
    tec_inal = next(p for p in CAT if p.get("categoria") == "teclado"
                    and "inalambr" in str((p.get("specs") or {})
                                          .get("conexion", "")).lower())
    correr_turno(u, "Quiero un mouse gamer barato y un teclado inalambrico",
                 [declarar([{"que": "mouse", "cantidad": 1},
                            {"que": "teclado", "cantidad": 1}]),
                  buscar("mouse", "mouse gamer barato"),
                  buscar("teclado", "teclado inalambrico")])
    correr_turno(u, "Mostrame opciones de los dos, pero no me armes presupuesto",
                 [buscar("mouse"), buscar("teclado")])
    r3 = correr_turno(u, "El mouse que me mostraste primero me sirve. Guardalo",
                      [declarar([{"que": "mouse", "cantidad": 1}]),
                       presupuesto([{"product_id": mouse["id"],
                                     "cantidad": 1}])])
    ok3 = len(r3["carrito"]) == 1
    caso("Serie 1", 3, "guardar el mouse en el pedido",
         "carrito con 1 item", f"{[c['nombre'] for c in r3['carrito']]}", ok3)

    # turno 5: saca el mouse y deja el teclado, SIN pedir precio
    r5 = correr_turno(u, "No, para: deja el teclado inalambrico y saca el mouse",
                      [declarar([{"que": "teclado inalambrico",
                                  "cantidad": 1}])])
    nombres = [c["nombre"] for c in r5["carrito"]]
    ok5 = not any("Mouse" in n for n in nombres)
    caso("Serie 1", 5, "sacar el mouse sin recotizar",
         "el mouse ya no esta en el carrito", f"{nombres}", ok5,
         "" if ok5 else "el producto dado de baja sigue en el pedido")

    r6 = correr_turno(u, "Mejor agrega dos mouse iguales y manten el teclado",
                      [declarar([{"que": "mouse", "cantidad": 2},
                                 {"que": "teclado", "cantidad": 1}]),
                       presupuesto([{"product_id": mouse["id"], "cantidad": 2},
                                    {"product_id": tec_inal["id"],
                                     "cantidad": 1}])])
    cant = {c["nombre"]: c["cantidad"] for c in r6["carrito"]}
    ok6 = len(r6["carrito"]) == 2 and 2 in cant.values()
    caso("Serie 1", 6, "dos mouse mas el teclado",
         "2 items, uno con cantidad 2", f"{cant}", ok6)

    r8 = correr_turno(u, "Pago 20% Mercado Pago y el resto transferencia",
                      [presupuesto([{"product_id": mouse["id"], "cantidad": 2},
                                    {"product_id": tec_inal["id"],
                                     "cantidad": 1}],
                                   destinos=["Cordoba capital"],
                                   pago=[{"medio": "mercado pago",
                                          "porcentaje": 20},
                                         {"medio": "transferencia",
                                          "porcentaje": 80}])])
    # el destino se dio en el turno 7 y la cuenta es del 8
    bloque = R._bloque_presupuesto(r8["llamadas"])
    ok8 = "ordoba" in bloque and "%" in bloque
    caso("Serie 1", 8, "la cuenta con el destino dado un turno antes",
         "el destino y el reparto de pago en el bloque",
         f"destino en el bloque: {'ordoba' in bloque}, reparto: {'%' in bloque}",
         ok8)


# ── SERIE 3 — pedido largo, destinos y cambio de cantidades ────────────────
def serie_3():
    u = "serie3"
    reset_conversation(u, tienda_id=TIENDA)
    aur, mou, tec = uno("auriculares"), uno("mouse"), uno("teclado")
    correr_turno(u, "Necesito dos auriculares, tres mouse y un teclado",
                 [declarar([{"que": "auriculares", "cantidad": 2},
                            {"que": "mouse", "cantidad": 3},
                            {"que": "teclado", "cantidad": 1}]),
                  buscar("auriculares"), buscar("mouse"), buscar("teclado")])
    # turno 2: el reparto por destino
    r2 = correr_turno(
        u, "Un auricular y un mouse van a Cordoba capital; el resto a Posadas",
        [declarar([{"que": "auriculares", "cantidad": 1,
                    "destino": "Cordoba capital"},
                   {"que": "auriculares", "cantidad": 1,
                    "destino": "Posadas"},
                   {"que": "mouse", "cantidad": 1,
                    "destino": "Cordoba capital"},
                   {"que": "mouse", "cantidad": 2, "destino": "Posadas"},
                   {"que": "teclado", "cantidad": 1, "destino": "Posadas"}]),
         presupuesto([{"product_id": aur["id"], "cantidad": 1,
                       "destino": "Cordoba capital"},
                      {"product_id": aur["id"], "cantidad": 1,
                       "destino": "Posadas"},
                      {"product_id": mou["id"], "cantidad": 1,
                       "destino": "Cordoba capital"},
                      {"product_id": mou["id"], "cantidad": 2,
                       "destino": "Posadas"},
                      {"product_id": tec["id"], "cantidad": 1,
                       "destino": "Posadas"}])])
    con_destino = [c for c in r2["carrito"] if c.get("destino")]
    ok2 = len(con_destino) == len(r2["carrito"]) and r2["carrito"]
    caso("Serie 3", 2, "el destino de cada item se guarda",
         "todos los items del carrito con su destino",
         f"{len(con_destino)} de {len(r2['carrito'])} con destino", ok2,
         "" if ok2 else "el reparto no sobrevive al turno")

    # turno 5: uno de los auriculares era solo consulta, no se compra
    r5 = correr_turno(u, "Para, uno de los auriculares era solo una consulta",
                      [declarar([{"que": "auriculares", "cantidad": 1},
                                 {"que": "mouse", "cantidad": 3},
                                 {"que": "teclado", "cantidad": 1}])])
    aur_en_carrito = sum(c["cantidad"] for c in r5["carrito"]
                         if "uricular" in c["nombre"])
    ok5 = aur_en_carrito == 1
    caso("Serie 3", 5, "bajar de 2 auriculares a 1 sin recotizar",
         "1 auricular en el pedido", f"{aur_en_carrito} auriculares", ok5,
         "" if ok5 else "LA CANTIDAD NO SE PUEDE CORREGIR SIN RECOTIZAR: la "
                        "poda quita items enteros, no baja unidades")

    # turno 6: el cliente pide confirmacion de lo que quedo
    r6 = correr_turno(u, "Confirmame que entendiste eso", [])
    ve_el_pedido = "Pedido vigente" in r6["memoria"]
    caso("Serie 3", 6, "el bot puede confirmar el pedido vigente",
         "el pedido vigente viaja en el contexto",
         f"lo ve: {ve_el_pedido} -> {r6['memoria'][:90]!r}", ve_el_pedido)

    # turno 8: cotizar los tres destinos por separado
    r8 = correr_turno(u, "Cotiza Cordoba, Concordia y Posadas por separado",
                      [presupuesto([{"product_id": mou["id"], "cantidad": 1,
                                     "destino": "Cordoba capital"},
                                    {"product_id": mou["id"], "cantidad": 1,
                                     "destino": "Concordia"},
                                    {"product_id": tec["id"], "cantidad": 1,
                                     "destino": "Posadas"}],
                                   destinos=["Cordoba capital", "Concordia",
                                             "Posadas"])])
    bloque = R._bloque_presupuesto(r8["llamadas"])
    tres = sum(1 for d in ("ordoba", "oncordia", "osadas") if d in bloque)
    caso("Serie 3", 8, "los tres destinos cotizados por separado",
         "los 3 en el bloque", f"{tres} de 3", tres == 3)


# ── SERIE 15 — la integral, doce turnos ────────────────────────────────────
def serie_15():
    u = "serie15"
    reset_conversation(u, tienda_id=TIENDA)
    mou, tec = uno("mouse"), uno("teclado")
    guiones = [
        "Quiero dos mouse, un teclado y unos auriculares",
        "Mostrame opciones, pero no armes la cuenta todavia",
        "El primer mouse y el segundo teclado me interesan. Los auriculares "
        "solo los nombre como posibilidad, no los sumes",
        "Mejor cambia el teclado por uno inalambrico",
        "Los dos mouse van a Cordoba capital y el teclado a Rosario",
        "Para: uno de los mouse va a Concordia y el otro a Cordoba",
        "Quiero la alternativa mas barata, pero no si tiene peor garantia",
        "Confirmame que productos quedaron, con cantidades y destinos",
        "Arma el presupuesto y divide 30% Mercado Pago y 70% transferencia",
        "El total es mas alto de lo que esperaba",
        "Deja el teclado original, pasame los datos de Mercado Pago",
        "Antes de cerrar, repetime el resumen y verifica que no hayas "
        "agregado los auriculares",
    ]
    # El turno 3 es el que importa: los auriculares se nombran y se RETRACTAN.
    for i, g in enumerate(guiones, 1):
        pedidos = []
        if i == 1:
            pedidos = [declarar([{"que": "mouse", "cantidad": 2},
                                 {"que": "teclado", "cantidad": 1},
                                 {"que": "auriculares", "cantidad": 1}]),
                       buscar("mouse"), buscar("teclado"),
                       buscar("auriculares")]
        elif i == 3:
            pedidos = [declarar([{"que": "mouse", "cantidad": 2},
                                 {"que": "teclado", "cantidad": 1}])]
        elif i == 9:
            pedidos = [presupuesto(
                [{"product_id": mou["id"], "cantidad": 1,
                  "destino": "Concordia"},
                 {"product_id": mou["id"], "cantidad": 1,
                  "destino": "Cordoba capital"},
                 {"product_id": tec["id"], "cantidad": 1,
                  "destino": "Rosario"}],
                destinos=["Concordia", "Cordoba capital", "Rosario"],
                pago=[{"medio": "mercado pago", "porcentaje": 30},
                      {"medio": "transferencia", "porcentaje": 70}])]
        r = correr_turno(u, g, pedidos)
        if i == 3:
            hay_aur = any("uricular" in c["nombre"] for c in r["carrito"])
            caso("Serie 15", 3, "los auriculares se nombraron y se retractaron",
                 "no entran al pedido",
                 f"auriculares en el carrito: {hay_aur}", not hay_aur)
        if i == 12:
            ultimo = r
    # LA PRUEBA DE FUEGO: en el turno 12, ¿el sistema todavia sabe que los
    # auriculares fueron descartados en el turno 3?
    vio = ultimo["vio"]
    turnos_visibles = sum(1 for g in guiones if g[:35] in vio)
    hay_aur = any("uricular" in c["nombre"] for c in ultimo["carrito"])
    caso("Serie 15", 12, "los auriculares no reaparecen doce turnos despues",
         "el carrito final sin auriculares",
         f"auriculares en el carrito: {hay_aur}", not hay_aur)
    # La prosa de la retractacion sale de la ventana; lo que tiene que
    # sobrevivir es el HECHO, anotado en el estado.
    anotado = any("uricular" in str(d) for d in (ultimo["descartados"] or []))
    caso("Serie 15", 12, "la RETRACTACION del turno 3 sigue viva",
         "los auriculares anotados como descartados en el estado",
         f"turnos del guion visibles en el prompt: {turnos_visibles} de 12; "
         f"descartados guardados: {ultimo['descartados']}", anotado,
         "" if anotado else "MEMORIA NEGATIVA: lo que el cliente descarto no "
                            "se guarda en ningun campo y sale de la ventana")


# ── LAS TRES MEDIDAS DIRECTAS DEL CONTEXTO ─────────────────────────────────
def medidas_de_contexto():
    u = "ventana"
    reset_conversation(u, tienda_id=TIENDA)
    for i in range(1, 13):
        r = correr_turno(u, f"MENSAJE NUMERO {i} del cliente", [],
                         respuesta=f"respuesta {i}")
    vio = r["vio"]
    visibles = [i for i in range(1, 13) if f"MENSAJE NUMERO {i} " in vio]
    caso("Contexto", 12, "cuantos turnos ve el modelo en el turno 12",
         "los 12, o al menos los que el sistema guarda",
         f"ve los turnos {visibles}", len(visibles) >= 10,
         "" if len(visibles) >= 10 else
         f"VENTANA CORTA: el prompt usa history[-10:] -mensajes, no turnos- "
         f"asi que ve {len(visibles)} de 12 turnos, y el sistema GUARDA "
         f"{S.HISTORY_LIMIT}")

    conv = get_conversation(u, tienda_id=TIENDA)
    guardados = sum(1 for m in (conv.get("history") or [])
                    if m.get("role") == "user")
    caso("Contexto", 12, "el prompt no tira memoria ya guardada",
         "el modelo ve al menos todo lo que el sistema persiste",
         f"guarda {guardados} turnos de cliente, muestra {len(visibles)} "
         f"-los guardados mas el turno en curso, que todavia no se salvo-",
         len(visibles) >= guardados,
         "" if len(visibles) >= guardados else
         "SE GUARDA MAS DE LO QUE SE MUESTRA: la memoria ya esta paga en "
         "Firestore y el prompt la tira")

    # memoria negativa: donde se anota lo que el cliente descarto
    campos = set(construir_estado(get_conversation(u, tienda_id=TIENDA),
                                  None))
    tiene = any("descart" in c or "excluid" in c or "no_quiere" in c
                for c in campos)
    caso("Contexto", 0, "existe un campo para lo que el cliente DESCARTO",
         "un campo de memoria negativa en el estado",
         f"campos del estado: {sorted(campos)}", tiene,
         "" if tiene else "MEMORIA NEGATIVA: no existe. Solo se guarda lo que "
                          "entra al pedido, nunca lo que el cliente saco o "
                          "dijo que no queria, asi que al salir de la ventana "
                          "el producto retractado puede volver")

    # ordinales: lo mostrado, ¿con posicion y turno?
    u2 = "ordinal"
    reset_conversation(u2, tienda_id=TIENDA)
    r = correr_turno(u2, "mostrame teclados", [buscar("teclado", cuantos=3)])
    correr_turno(u2, "y mouse tambien", [buscar("mouse", cuantos=3)])
    conv = get_conversation(u2, tienda_id=TIENDA)
    vistos = conv.get("productos_vistos") or []
    tiene_pos = all(("posicion" in v and "turno" in v) for v in vistos) \
        if vistos else False
    caso("Contexto", 0, "'el segundo teclado que me mostraste' se puede resolver",
         "cada producto visto con su turno y su posicion",
         f"{len(vistos)} vistos, campos: "
         f"{sorted(vistos[0]) if vistos else []}", tiene_pos,
         "" if tiene_pos else "ORDINALES: productos_vistos guarda id, nombre y "
                              "precio, sin turno ni posicion ni de que "
                              "busqueda salio. 'El segundo teclado' no tiene "
                              "contra que resolverse")


def correr() -> list:
    """Corre las series y devuelve los resultados, sin imprimir nada. Lo usa el
    marcador de `las_40.py`, que necesita los mismos casos sin el volcado."""
    RESULTADOS.clear()
    for f in (serie_1, serie_3, serie_15, medidas_de_contexto):
        try:
            f()
        except Exception as e:
            import traceback
            caso(f.__name__, 0, f.__name__, "-",
                 f"EXCEPCION {type(e).__name__}: {str(e)[:200]}", False,
                 traceback.format_exc().splitlines()[-3][:120])
    return RESULTADOS


def main():
    correr()
    verdes = [r for r in RESULTADOS if r["ok"]]
    print("=" * 78)
    print(f"BANCO DE MEMORIA — {len(verdes)} de {len(RESULTADOS)} en verde")
    print("=" * 78)
    for r in RESULTADOS:
        print(f"\n[{'OK ' if r['ok'] else 'MAL'}] {r['serie']} turno {r['turno']}"
              f" — {r['que']}")
        print(f"   esperado : {r['esperado']}")
        print(f"   obtenido : {r['obtenido']}")
        if r["causa"]:
            print(f"   CAUSA    : {r['causa']}")
    print("\n" + "=" * 78)
    print("CAUSAS, agrupadas")
    print("=" * 78)
    causas: dict = {}
    for r in RESULTADOS:
        if r["causa"]:
            causas.setdefault(r["causa"].split(":")[0], []).append(
                f"{r['serie']}.{r['turno']}")
    for c, ns in sorted(causas.items(), key=lambda t: -len(t[1])):
        print(f"  {len(ns)} caso(s) {ns}: {c}")
    return 0 if len(verdes) == len(RESULTADOS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
