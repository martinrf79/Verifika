"""EL EXAMEN CON LAS CHARLAS REALES DE WHATSAPP — 31-oct-2026, con Martin.

La vara del banco daba 74 de 75 y en WhatsApp el bot fallaba. Aca estan las 42 charlas reales distintas de los ultimos
60 dias, `charlas.json`, bajadas con `produccion.py` y con el usuario cambiado por un hash. Cada una pasa entera por el
clon del bot con el modelo de produccion y la clave gratis, y cada turno se califica a mano contra lo que recibio el
cliente y lo que devolvieron las herramientas.

  charlas.json            los mensajes del cliente, en orden; en_banco dice si el mensaje ya estaba en el banco
  corrida_<dia>.jsonl     lo que contesto el bot y lo que pidio y devolvio cada herramienta
  notas_<dia>.json        cada turno bien o mal, con su causa y por que

El 31-oct, con el codigo de produccion, las 42: 72 de 113 turnos bien, el 64%; 52 de 80 de lo que ya estaba en el banco
y 20 de 33 de lo que no. 28 charlas con la gratis y 14 con la paga, el mismo modelo, 11 centavos.

    python3 banco_pruebas/examen_real/examen.py corrida_<dia>.jsonl [id ...]
    python3 banco_pruebas/examen_real/examen.py --ver corrida_<dia>.jsonl [id ...]
    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/examen_real/examen.py --paga corrida_<dia>.jsonl

Una charla con un turno sin respuesta del modelo no se guarda: se corre de nuevo. Lo ya guardado no se repite.
"""
import asyncio
import json
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, REPO)
PAUSA_S = 12  # la gratis corta por minuto


def ver(salida: str, ids: list) -> None:
    for c in map(json.loads, open(salida, encoding="utf-8")):
        if ids and c["id"] not in ids:
            continue
        print("########", c["id"])
        for i, t in enumerate(c["turnos"], 1):
            print(f"--- t{i} {'B' if t['en_banco'] else '-'} CLIENTE: {t['cliente']}")
            for p in t["pasos"]:
                print("   >", p["h"], json.dumps(p["pide"], ensure_ascii=False)[:200])
            if t["hallazgos"]:
                print("   ! VERIFICADOR:", t["hallazgos"])
            print("   BOT:", t["bot"].replace("\n", " / "))


def correr(salida: str, ids: list, paga: bool = False) -> None:
    from banco_pruebas import agente_replay as R
    from banco_pruebas import clon_produccion as C
    falso, vistos = R.instalar(vivo=True, gratis=not paga)
    hechos = {json.loads(x)["id"] for x in open(salida, encoding="utf-8")} if os.path.exists(salida) else set()
    for e in json.load(open(os.path.join(AQUI, "charlas.json"), encoding="utf-8")):
        if (ids and e["id"] not in ids) or e["id"] in hechos:
            continue
        uid = f"examen_{e['id']}"
        C.reiniciar_cliente(uid)
        turnos = []
        for m, en_banco in zip(e["mensajes"], e["en_banco"]):
            time.sleep(PAUSA_S)
            vistos.clear()
            texto = "\n".join(asyncio.run(C.turno(uid, m)))
            v = vistos[-1] if vistos else {}
            turnos.append({"cliente": m, "bot": texto, "en_banco": en_banco, "error": v.get("error"),
                           "pasos": [{"h": p["herramienta"], "pide": p["pide"], "devuelve": p["devuelve"][:1500]}
                                     for p in v.get("pasos") or []], "hallazgos": v.get("hallazgos")})
        if any(t["error"] for t in turnos):
            print(e["id"], "sin respuesta del modelo en algun turno: no se guarda", flush=True)
            continue
        with open(salida, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"id": e["id"], "turnos": turnos}, ensure_ascii=False) + "\n")
        print(e["id"], len(turnos), "turnos", flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    modo = a.pop(0) if a[:1] in (["--ver"], ["--paga"]) else ""
    archivo = a[0] if os.path.isabs(a[0]) else os.path.join(AQUI, a[0])
    ver(archivo, a[1:]) if modo == "--ver" else correr(archivo, a[1:], modo == "--paga")
