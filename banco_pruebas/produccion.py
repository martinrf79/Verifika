"""
PRODUCCION COMO BANCO — cada charla real de Martin se vuelve un test, sola.

POR QUE EXISTE (Martin, 10-ago-2026): "en cada prueba en real aparecen nuevos
errores". Es cierto y tiene explicacion: los guiones los escribimos nosotros y
el cliente real no saca sus preguntas de esa lista. Las charlas grabadas cubren
lo que alguien penso; la charla de Martin cubre lo que pasa.

LO QUE CAMBIA ESTE ARCHIVO. Hasta hoy, para saber si una charla real salio bien
habia que LEERLA a mano. Asi se encontro el error de plata del 10-ago -cobrarle
$225.000 a un cliente que debia $131.625- y llevo una hora de leer logs. Con
esto, la misma charla se audita sola en dos segundos, y **sin que nadie escriba
la respuesta esperada**: los invariantes de `app/verifika/invariantes.py` no comparan contra
un texto, afirman propiedades que ninguna respuesta correcta viola.

O sea que cada vez que Martin prueba por WhatsApp, el sistema se mide gratis
contra la distribucion VERDADERA de preguntas. Eso es lo que ningun guion
escrito a mano reproduce.

ES DE SOLO LECTURA. Baja conversaciones y las revisa. No escribe en Firestore,
no toca produccion, no gasta una llamada al modelo: los invariantes son
aritmetica y texto. No necesita clave de LLM, ni la gratis ni la paga.

USO:
    python3 banco_pruebas/produccion.py              # las ultimas 20 charlas
    python3 banco_pruebas/produccion.py --limite 50
    python3 banco_pruebas/produccion.py --usuario 5493547504287

CREDENCIAL: la env `GCP_SA_KEY_B64`, que trae la clave de `claude-lector`
(logging.viewer + datastore.viewer). Sin ella el script avisa y sale sin error,
para que corra en cualquier lado sin romper nada.

EL NUMERO QUE DEJA, y es el que contesta "¿cuando es robusto?": **defectos por
charla real**. Hoy es alto. Cuando quince o veinte charlas reales seguidas no
traigan ninguno, es robusto. Hasta entonces hay una curva y no una sensacion.
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from app.verifika.invariantes import revisar_charla  # noqa: E402

TIENDA = "verifika_prod"
_BASE = ("https://firestore.googleapis.com/v1/projects/memory-engine-v1/"
         "databases/(default)/documents")


# ── CREDENCIAL ──────────────────────────────────────────────────────────────
def _token() -> str | None:
    """Access token desde `GCP_SA_KEY_B64`. None si no esta la env o falta la
    libreria de firma: el script avisa y sale limpio, no explota."""
    crudo = (os.environ.get("GCP_SA_KEY_B64") or "").strip()
    if not crudo:
        return None
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
    except ImportError:
        return None
    sa = json.loads(base64.b64decode(crudo))

    def b64(d):
        return base64.urlsafe_b64encode(d).rstrip(b"=")

    ahora = int(time.time())
    hdr = b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    cuerpo = b64(json.dumps({
        "iss": sa["client_email"],
        "scope": "https://www.googleapis.com/auth/cloud-platform",
        "aud": "https://oauth2.googleapis.com/token",
        "exp": ahora + 3600, "iat": ahora}).encode())
    key = serialization.load_pem_private_key(sa["private_key"].encode(),
                                             password=None)
    firma = b64(key.sign(hdr + b"." + cuerpo, padding.PKCS1v15(), hashes.SHA256()))
    jwt = (hdr + b"." + cuerpo + b"." + firma).decode()
    datos = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt}).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=datos)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["access_token"]


def _get(url: str, tok: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


# ── BAJAR LAS CHARLAS ───────────────────────────────────────────────────────
def _respuestas_del_bot(doc: dict) -> list:
    """Las respuestas del bot, en orden, de un documento de conversacion."""
    hist = (doc.get("fields", {}).get("history", {})
            .get("arrayValue", {}).get("values", []) or [])
    salida = []
    for it in hist:
        f = it.get("mapValue", {}).get("fields", {})
        if f.get("role", {}).get("stringValue") == "assistant":
            salida.append(f.get("content", {}).get("stringValue", ""))
    return salida


def charlas(tok: str, limite: int = 20, usuario: str = "") -> list:
    """[(user_id, [respuestas])] de las conversaciones vivas."""
    if usuario:
        doc = _get(f"{_BASE}/tiendas/{TIENDA}/conversaciones/{usuario}", tok)
        return [(usuario, _respuestas_del_bot(doc))]
    url = (f"{_BASE}/tiendas/{TIENDA}/conversaciones"
           f"?pageSize={max(1, min(int(limite), 300))}")
    datos = _get(url, tok)
    out = []
    for doc in datos.get("documents", []) or []:
        uid = str(doc.get("name", "")).rsplit("/", 1)[-1]
        out.append((uid, _respuestas_del_bot(doc)))
    return out


# ── EL INFORME ──────────────────────────────────────────────────────────────
def informe(revisadas: list) -> str:
    lineas = ["", "=" * 78,
              "PRODUCCION COMO BANCO — los invariantes sobre las charlas REALES",
              "=" * 78, ""]
    total_turnos = sum(len(m) for _, m, _ in revisadas)
    con_falla = [r for r in revisadas if r[2]]
    todas = [f for _, _, fs in revisadas for f in fs]

    for uid, mensajes, fallas in revisadas:
        if not fallas:
            continue
        lineas.append(f"── charla {uid} — {len(mensajes)} turnos, "
                      f"{len(fallas)} violaciones")
        for f in fallas:
            lineas.append(f"   turno {f['turno']:>2}  {f['regla']:<38} "
                          f"{f['detalle']}")
        lineas.append("")

    porc = (100 * len(con_falla) / len(revisadas)) if revisadas else 0
    por_charla = (len(todas) / len(revisadas)) if revisadas else 0
    lineas += [
        "=" * 78,
        f"CHARLAS: {len(revisadas)}   TURNOS: {total_turnos}   "
        f"VIOLACIONES: {len(todas)}",
        f"CHARLAS CON AL MENOS UNA FALLA: {len(con_falla)} de {len(revisadas)} "
        f"({porc:.0f}%)",
        f"EL NUMERO QUE MANDA — DEFECTOS POR CHARLA REAL: {por_charla:.2f}",
        "",
        "Robusto es que esto de CERO sobre quince o veinte charlas seguidas.",
        "=" * 78]

    if todas:
        cuenta = {}
        for f in todas:
            cuenta[f["regla"]] = cuenta.get(f["regla"], 0) + 1
        lineas += ["", "POR REGLA, de la que mas duele para abajo:"]
        for regla, n in sorted(cuenta.items(), key=lambda x: -x[1]):
            lineas.append(f"  {n:>3}  {regla}")
    return "\n".join(lineas)


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limite", type=int, default=20)
    ap.add_argument("--usuario", default="")
    args = ap.parse_args(argv)

    tok = _token()
    if not tok:
        print("Sin GCP_SA_KEY_B64 en el entorno (o sin la libreria de firma):\n"
              "no se pueden bajar las charlas reales. No es un error del\n"
              "sistema; es que este entorno no tiene la credencial de lectura.")
        return 0

    try:
        crudas = charlas(tok, args.limite, args.usuario)
    except Exception as e:
        print(f"No se pudieron bajar las charlas: {type(e).__name__}: {e}")
        return 1

    revisadas = []
    for uid, mensajes in crudas:
        if not mensajes:
            continue
        revisadas.append((uid, mensajes, revisar_charla(mensajes)))

    if not revisadas:
        print("No hay charlas con respuestas del bot para revisar.")
        return 0

    print(informe(revisadas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
