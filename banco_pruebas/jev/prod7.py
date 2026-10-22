"""Los 7 casos de produccion, charla entera, con el modelo real en CADA turno: la memoria tambien se mide.
  base  produccion tal cual: interpretar, elegir, explicar y vender reales
  jev   lo mismo, y antes de interpretar: vuelta 1 de Gemini, Jev, y el recorte en la vuelta 2, con el ejecutor de prueba
Tres repeticiones; tope de la paga por corrida: TOPE_USD."""
import asyncio, copy, json, os, sys
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D)
import ronda2 as R2                       # entorno, puerta real, copia limpia del interprete y ejecutor de prueba
from ronda2 import C, V, I, K, FRESH, it, libro_paga, nota_casilla, EXTRA
OUT = os.path.join(D, "prod7.jsonl"); TOPE_USD = float(os.environ.get("TOPE_USD", "0.20"))
CASOS = json.load(open(os.path.join(D, "casos_produccion.json")))["charlas"]
real_interp, real_mensajes = FRESH.interpretar, FRESH.mensajes

async def recorte(mensaje, libreta):
    msgs = [{"role": "system", "content": V.VARIANTES["v4"]}, {"role": "user", "content": f"{libreta}\nULTIMO MENSAJE: {mensaje}"}]
    sal = FRESH._json(await FRESH._pedir(msgs, "", {"type": "json_object"}))
    rs = [r for r in sal.get("renglones") or [] if isinstance(r, dict)]
    lineas, temas, vistos = [], [], set()
    nom = {str(p["id"]): p for p in K.productos("verifika_prod")}
    for r in rs:
        s = V.jev1(r.get("limpio", ""), libreta); temas += [t for t in s["temas"] if t not in temas]
        for rub in s["rubros"]:
            if rub in vistos: continue
            vistos.add(rub); x = V.jev2(r.get("limpio", ""), rub, libreta); vs = I.valores(rub)
            lineas.append(f"- rubro {rub}; campos: " + "; ".join(f"{c}: {' | '.join(vs[c][:14])}" for c in x["campos"])
                          + "; productos: " + "; ".join(nom[i]["nombre"] for i in x["prods"] if i in nom))
    return ("MENSAJE LIMPIO, renglon por renglon:\n" + "\n".join(f"- {r.get('limpio','')}" for r in rs)
            + "\nLO QUE LA FUENTE DE LA TIENDA TIENE PARA ESTE MENSAJE:\n" + "\n".join(lineas)
            + (f"\n- temas de la tienda que puede preguntar: {', '.join(temas[:3])}" if temas else ""))

def charla(c, con_jev, rep):
    uid = f"p7_{c['id']}_{int(con_jev)}_{rep}"; C.reiniciar_cliente(uid); resps, turnos = [], []
    for t in c["turnos"]:
        extra = {"txt": ""}
        def _mensajes(mensaje, historial, estado, tienda_id):
            m = real_mensajes(mensaje, historial, estado, tienda_id)
            if con_jev and extra["txt"]:
                m = copy.deepcopy(m); m[0]["content"] += EXTRA
                u = m[1]["content"]; i = u.rfind("\nULTIMO MENSAJE:"); m[1]["content"] = u[:i] + "\n" + extra["txt"] + u[i:]
            return m
        vistas = []
        async def _interp(mensaje, historial, estado, tienda_id, trace_id=""):
            if con_jev: extra["txt"] = await recorte(mensaje, FRESH.libreta(estado, historial, tienda_id))
            FRESH.mensajes = _mensajes
            try:
                for _ in range(3):
                    r = await real_interp(mensaje, historial, estado, tienda_id, trace_id)
                    if r is not None: vistas.append(r); return r
                    await asyncio.sleep(15)
            finally:
                FRESH.mensajes = real_mensajes
            return None
        it.interpretar, it.explicar, it.elegir, it.vender = _interp, FRESH.explicar, FRESH.elegir, FRESH.vender
        txt = "\n".join(asyncio.run(C.turno(uid, t["texto"]))); resps.append(txt)
        malas = [k["n"] for k in t["casillas"] if nota_casilla(k, [], txt, resps) is not True]
        turnos.append({"texto": t["texto"], "respuesta": txt, "malas": malas, "agenda": vistas[-1] if vistas else None, "recorte": extra["txt"]})
        if not vistas: return turnos, False
    return turnos, True

if __name__ == "__main__":
    hechos = {(x["id"], x["config"], x["rep"]) for x in map(json.loads, open(OUT))} if os.path.exists(OUT) else set()
    g0 = libro_paga.hoy()
    for rep in range(3):
        for c in CASOS:
            for cfg in ("base", "jev"):
                if (c["id"], cfg, rep) in hechos: continue
                if libro_paga.hoy() - g0 > TOPE_USD: print("TOPE", flush=True); sys.exit()
                turnos, ok = charla(c, cfg == "jev", rep)
                if not ok: print(c["id"], cfg, "el modelo no contesto, se corta", flush=True); sys.exit()
                malas = [m for t in turnos for m in t["malas"]]
                with open(OUT, "a") as o: o.write(json.dumps({"id": c["id"], "config": cfg, "rep": rep, "bien": not malas, "turnos": turnos}, ensure_ascii=False) + "\n")
                print(f"r{rep} {c['id']} {cfg}: {'bien' if not malas else 'MAL ' + '; '.join(malas)}", flush=True)
    print(f"paga en esta corrida: {libro_paga.hoy() - g0:.4f} USD", flush=True)
