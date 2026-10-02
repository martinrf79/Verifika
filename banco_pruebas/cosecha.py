"""LA COSECHA — las charlas reales de produccion, turno por turno, con lo que pidio el modelo (2-oct-2026).

POR QUE EXISTE. Las charlas del banco las escribimos nosotros; las de
produccion las escribio el cliente, y desde el 27-sep el reset ya no las
borra: las archiva. Esto las junta todas, vivas y archivadas, y cruza cada
turno con los logs de Cloud Run por su trace_id:

  cliente     lo que escribio, `message_received`
  pedidos     lo que el modelo le pidio a cada herramienta, `agente_turno`
  piezas      el tipo de cada pieza que armo el interprete
  banderas    las preguntas de si o no que dieron si
  bot         lo que contesto, de la charla guardada en Firestore

ES DE SOLO LECTURA y no gasta modelo: Firestore y Logging con la cuenta
`claude-lector`, la de `GCP_SA_KEY_B64`. Los logs de Cloud Run guardan treinta
dias; las charlas, desde que existen.

LO QUE NO TRAE, dicho adelante: la salida CRUDA del interprete —el JSON de las
piezas con sus campos— no se loguea; los pedidos son lo que el codigo hizo con
ella. Para reproducir el codigo sin modelo hace falta grabar, y eso lo hace
`sonda_charlas` desde el 2-oct.

  python3 -m banco_pruebas.cosecha                    todo lo que hay
  python3 -m banco_pruebas.cosecha --desde 7d
  python3 -m banco_pruebas.cosecha --informe          cuantas, de que tipo
"""
import json
import sys
import time
import urllib.parse
from datetime import datetime

from banco_pruebas import produccion as P

SALIDA = "banco_pruebas/cosecha_produccion.jsonl"
EVENTOS = ("message_received", "agente_turno", "turno_ok")


def logs(tok: str, desde_s: int) -> dict:
    """{trace_id: {evento: payload}} de los eventos del turno en la ventana."""
    desde = datetime.utcfromtimestamp(time.time() - desde_s).strftime("%Y-%m-%dT%H:%M:%SZ")
    filtro = (f'resource.type="cloud_run_revision" AND resource.labels.service_name="{P.SERVICIO}" '
              f'AND jsonPayload.event=({" OR ".join(chr(34) + e + chr(34) for e in EVENTOS)}) '
              f'AND timestamp>="{desde}"')
    out, token = {}, ""
    for _ in range(200):
        cuerpo = {"resourceNames": [f"projects/{P.PROYECTO}"], "filter": filtro,
                  "orderBy": "timestamp asc", "pageSize": 1000}
        if token:
            cuerpo["pageToken"] = token
        r = P._post("https://logging.googleapis.com/v2/entries:list", tok, cuerpo)
        for e in r.get("entries") or []:
            p = e.get("jsonPayload") or {}
            t = p.get("trace_id")
            if t:
                out.setdefault(t, {})[p.get("event")] = {**p, "_t": e.get("timestamp")}
        token = r.get("nextPageToken") or ""
        if not token:
            break
    return out


def _docs(tok: str, coleccion: str) -> list:
    out, token = [], ""
    while True:
        url = f"{P._BASE}/tiendas/{P.TIENDA}/{coleccion}?pageSize=300"
        if token:
            url += f"&pageToken={urllib.parse.quote(token)}"
        try:
            d = P._get(url, tok)
        except Exception:  # noqa: BLE001 — una coleccion que no esta no corta la cosecha
            return out
        out += d.get("documents") or []
        token = d.get("nextPageToken") or ""
        if not token:
            return out


def cosechar(desde_s: int) -> list:
    tok = P._token()
    if not tok:
        sys.exit("sin credencial: hace falta GCP_SA_KEY_B64")
    por_traza = logs(tok, desde_s)
    # Los turnos del log, por usuario y en orden: el usuario del archivo es
    # `<usuario>_<fecha>`, asi que se aparea por el texto del cliente.
    por_usuario: dict = {}
    for t, ev in por_traza.items():
        m = ev.get("message_received")
        if m:
            por_usuario.setdefault(str(m.get("user_id")), []).append((m.get("_t"), t, ev))
    charlas = []
    for coleccion in ("conversaciones", "conversaciones_archivo"):
        for doc in _docs(tok, coleccion):
            cid = str(doc.get("name", "")).rsplit("/", 1)[-1]
            usuario = cid.split("_")[0]
            dialogo = P._dialogo(doc)
            turnos_log = sorted(por_usuario.get(usuario, []))
            turnos, i = [], 0
            while i < len(dialogo):
                rol, txt = dialogo[i]
                if rol != "user":
                    i += 1
                    continue
                bot = dialogo[i + 1][1] if i + 1 < len(dialogo) and dialogo[i + 1][0] == "assistant" else ""
                ev = next((e for _, _, e in turnos_log
                           if (e["message_received"].get("msg_preview") or "")[:200] == txt[:200]), {})
                ag = ev.get("agente_turno") or {}
                turnos.append({"cliente": txt, "bot": bot, "pedidos": ag.get("pedidos"),
                               "piezas": ag.get("piezas"), "banderas": ag.get("banderas"),
                               "revision": ag.get("revision"), "ms": (ev.get("turno_ok") or {}).get("latency_ms"),
                               "trace_id": (ev.get("message_received") or {}).get("trace_id")})
                i += 2 if bot else 1
            if turnos:
                charlas.append({"id": cid, "coleccion": coleccion, "actualizada": doc.get("updateTime"),
                                "turnos": turnos})
    return charlas


def informe(charlas: list) -> None:
    turnos = [t for c in charlas for t in c["turnos"]]
    con_log = [t for t in turnos if t["pedidos"] is not None]
    largos = [t for t in turnos if len(t["cliente"]) > 150]
    print(f"{len(charlas)} charlas, {len(turnos)} turnos del cliente; {len(con_log)} con lo que pidio el modelo "
          f"(los logs guardan 30 dias); {len(largos)} mensajes de mas de 150 caracteres")
    for c in sorted(charlas, key=lambda c: -len(c["turnos"]))[:10]:
        print(f"  {c['id'][:40]:40} {len(c['turnos']):3} turnos  {c['coleccion']}")


def main(a: list) -> int:
    desde = P.ventana_a_segundos(a[a.index("--desde") + 1]) if "--desde" in a else 30 * 86400
    if "--informe" in a:
        informe([json.loads(x) for x in open(SALIDA, encoding="utf-8")])
        return 0
    charlas = cosechar(desde)
    with open(SALIDA, "w", encoding="utf-8") as f:
        for c in charlas:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    informe(charlas)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
