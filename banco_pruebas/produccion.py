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

Y DESDE EL 3-SEP EL INFORME TERMINA CON LA CHARLA LITERAL. El texto que
recibio el cliente NO esta en ningun log: `turno_ok` anota el largo, la
latencia y los puntos, nunca el mensaje. Este script ya bajaba el `history`
entero de la conversacion para correr los invariantes y despues lo tiraba. Ese
descarte costaba una sesion completa: desde afuera se podia decir que fallo por
dentro y no como sono por fuera, que es justo lo unico que Martin ve. Ahora la
transcripcion va al FINAL del informe, que es la punta que el puente conserva
cuando recorta.

ES DE SOLO LECTURA. Baja conversaciones y las revisa. No escribe en Firestore,
no toca produccion, no gasta una llamada al modelo: los invariantes son
aritmetica y texto. No necesita clave de LLM, ni la gratis ni la paga.

USO:
    python3 banco_pruebas/produccion.py --desde 18h   # solo lo NUEVO
    python3 banco_pruebas/produccion.py --limite 50
    python3 banco_pruebas/produccion.py --usuario 5493547504287
    python3 banco_pruebas/produccion.py --desde 4h --sin-transcripcion

LA VENTANA ES LO QUE HACE COMPARABLE EL NUMERO (3-sep-2026). Sin `--desde`
esto pide una pagina de conversaciones y Firestore la devuelve por orden de
NOMBRE, o sea siempre las mismas charlas viejas, y el denominador de "defectos
por charla" termina siendo `--limite`. Medido: el mismo estado del bot dio 0,8
y 0,20 en dos corridas sin que cambiara un solo defecto. Con `--desde` se
recorren todas las paginas y se auditan solo las charlas tocadas dentro de la
ventana: el denominador pasa a ser una cantidad del mundo y dos corridas con la
misma ventana se pueden comparar.

CREDENCIAL: la env `GCP_SA_KEY_B64`, que trae la clave de `claude-lector`
(logging.viewer + datastore.viewer). Sin ella el script avisa y sale sin error,
para que corra en cualquier lado sin romper nada. Tambien acepta un access token
ya hecho en `GCP_ACCESS_TOKEN`, que es por donde entra el puente de Actions con
WIF, sin ninguna llave.

EL NUMERO QUE DEJA, y es el que contesta "¿cuando es robusto?": **defectos por
charla real**. Hoy es alto. Cuando quince o veinte charlas reales seguidas no
traigan ninguno, es robusto. Hasta entonces hay una curva y no una sensacion.
"""
import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas.invariantes import revisar_charla  # noqa: E402

TIENDA = "verifika_prod"
_BASE = ("https://firestore.googleapis.com/v1/projects/memory-engine-v1/"
         "databases/(default)/documents")

# TOPES DE LA TRANSCRIPCION. El puente corta `auditoria.txt` en 20.000
# caracteres y se queda con la COLA, asi que la transcripcion tiene que entrar
# entera abajo sin empujar los numeros afuera del recorte.
TOPE_CHARLAS_TRANSCRIPTAS = 5
TOPE_MENSAJES = 30
TOPE_CARACTERES_MENSAJE = 2000
TOPE_TRANSCRIPCION = 12000


# ── CREDENCIAL ──────────────────────────────────────────────────────────────
def _token() -> str | None:
    """Access token desde `GCP_SA_KEY_B64`. None si no esta la env o falta la
    libreria de firma: el script avisa y sale limpio, no explota.

    ATAJO PARA EL PUENTE (31-ago-2026). Si el entorno ya trae un access token
    hecho en `GCP_ACCESS_TOKEN`, se usa ese y no hace falta ninguna llave. Es lo
    que permite que `.github/workflows/puente_cowork.yml` corra este script con
    WIF -sin secreto que rotar ni que se pueda filtrar en un log-, y no cambia
    nada para quien corre con la clave de `claude-lector`: si esa env no esta,
    el camino de abajo es el de siempre.
    """
    ya_hecho = (os.environ.get("GCP_ACCESS_TOKEN") or "").strip()
    if ya_hecho:
        return ya_hecho
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


def _dialogo(doc: dict) -> list:
    """La charla ENTERA en orden: `[(rol, texto)]`, cliente y bot.

    Es el mismo `history` que lee `_respuestas_del_bot`, sin filtrar por rol.
    Se agrega aparte y no se toca la otra funcion a proposito: los invariantes
    se corren sobre las respuestas del bot y esa entrada no cambia.

    El rol se guarda tal cual viene. Si algun dia aparece uno que no es `user`
    ni `assistant`, la transcripcion lo muestra con su nombre en vez de
    esconderlo: un rol que no se esperaba es informacion, no ruido.
    """
    hist = (doc.get("fields", {}).get("history", {})
            .get("arrayValue", {}).get("values", []) or [])
    salida = []
    for it in hist:
        f = it.get("mapValue", {}).get("fields", {})
        rol = f.get("role", {}).get("stringValue", "") or "?"
        txt = f.get("content", {}).get("stringValue", "")
        if txt:
            salida.append((rol, txt))
    return salida


def ventana_a_segundos(txt: str) -> int:
    """`18h`, `2d`, `30m` a segundos. Cero si no se entiende o viene vacio."""
    m = re.fullmatch(r"(\d+)\s*([smhd])", (txt or "").strip().lower())
    if not m:
        return 0
    return int(m.group(1)) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[m.group(2)]


def _cuando(doc: dict) -> float:
    """El `updateTime` del documento, en epoch. Cero si no vino."""
    t = str(doc.get("updateTime") or "").strip()
    if not t:
        return 0.0
    # Firestore manda NANOsegundos y `fromisoformat` solo aguanta micro. La
    # fraccion se tira entera: la ventana mas corta que se pide son minutos.
    t = re.sub(r"\.\d+", "", t).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(t).timestamp()
    except ValueError:
        return 0.0


def charlas(tok: str, limite: int = 20, usuario: str = "",
            desde_s: int = 0) -> tuple:
    """`([(user_id, [respuestas])], meta)` de las conversaciones vivas.

    LA VENTANA, Y ES LA MITAD DEL INSTRUMENTO (3-sep-2026). Sin ella esta
    funcion pedia UNA pagina de `pageSize=limite` y Firestore la devuelve en
    orden de NOMBRE de documento, o sea siempre las mismas charlas viejas. Dos
    consecuencias, las dos medidas: el puente re-auditaba las mismas cinco
    charlas corrida tras corrida, y como el denominador de "defectos por
    charla" era `limite`, el numero se movia entre 0,8 y 0,20 sin que cambiara
    UN SOLO defecto. Un instrumento cuyo numero depende de cuanto le pedis no
    mide nada.

    Con `desde_s` se recorren TODAS las paginas y se queda solo lo que se toco
    dentro de la ventana. Ahi el denominador pasa a ser "las charlas que hubo
    en la ventana", que es una cantidad del mundo y no del pedido, y dos
    corridas con la misma ventana se pueden comparar.

    `limite` deja de elegir el conjunto y queda como tope de seguridad.

    `meta["dialogos"]` lleva la charla literal de cada una, para la
    transcripcion del final. La forma de `out` NO cambia: quien ya usaba esta
    funcion sigue recibiendo los mismos pares.
    """
    if usuario:
        doc = _get(f"{_BASE}/tiendas/{TIENDA}/conversaciones/{usuario}", tok)
        return ([(usuario, _respuestas_del_bot(doc))],
                {"ventana_s": 0, "vistas": 1, "usuario": usuario,
                 "dialogos": {usuario: _dialogo(doc)}})

    tope = max(1, min(int(limite), 300))
    corte = (time.time() - desde_s) if desde_s else 0
    out, vistas, token = [], 0, ""
    dialogos: dict = {}
    while True:
        url = (f"{_BASE}/tiendas/{TIENDA}/conversaciones"
               f"?pageSize={300 if desde_s else tope}")
        if token:
            url += f"&pageToken={urllib.parse.quote(token)}"
        datos = _get(url, tok)
        for doc in datos.get("documents", []) or []:
            vistas += 1
            if corte and _cuando(doc) < corte:
                continue
            uid = str(doc.get("name", "")).rsplit("/", 1)[-1]
            out.append((uid, _respuestas_del_bot(doc)))
            dialogos[uid] = _dialogo(doc)
            if len(out) >= tope:
                break
        token = datos.get("nextPageToken") or ""
        if len(out) >= tope or not token or not desde_s:
            break
    return out, {"ventana_s": desde_s, "vistas": vistas, "usuario": "",
                 "dialogos": dialogos}


# ── EL INFORME ──────────────────────────────────────────────────────────────
def transcripcion(revisadas: list, dialogos: dict) -> list:
    """La charla LITERAL, y va al FINAL del informe a proposito.

    El puente recorta `auditoria.txt` por la COLA -se queda con los ultimos
    20.000 caracteres-, asi que lo que va abajo es lo que sobrevive al recorte.
    Los topes de arriba estan puestos para que la transcripcion no empuje los
    numeros afuera de esa ventana.

    NO SE RESUME NI SE LIMPIA NADA. El unico recorte es por largo, y cuando
    pasa lo dice con el numero de caracteres que tenia el mensaje entero: un
    texto acortado en silencio es exactamente el defecto que este archivo
    existe para no repetir.
    """
    lineas = ["", "=" * 78,
              "LA CHARLA, TAL CUAL LA RECIBIO EL CLIENTE",
              "=" * 78,
              "Esto NO esta en los logs: `turno_ok` guarda el largo, la",
              "latencia y los puntos, nunca el texto. Sale del `history` de la",
              "conversacion, que es lo mismo que se le mando a Telegram o a",
              "WhatsApp.", ""]
    usadas, gastado, cortadas = 0, 0, 0
    for uid, _mensajes, _fallas in revisadas:
        dia = dialogos.get(uid) or []
        if not dia:
            continue
        if usadas >= TOPE_CHARLAS_TRANSCRIPTAS or gastado >= TOPE_TRANSCRIPCION:
            cortadas += 1
            continue
        usadas += 1
        recorte = dia[-TOPE_MENSAJES:]
        bloque = [f"-- charla {uid}: {len(dia)} mensajes"
                  + (f", se muestran los ultimos {TOPE_MENSAJES}"
                     if len(dia) > TOPE_MENSAJES else "")]
        for rol, texto in recorte:
            quien = {"user": "CLIENTE", "assistant": "BOT    "}.get(
                rol, f"{rol:<7}")
            t = (texto or "").strip()
            if len(t) > TOPE_CARACTERES_MENSAJE:
                t = (t[:TOPE_CARACTERES_MENSAJE]
                     + f" [...recortado, el mensaje entero tenia {len(texto)}"
                       " caracteres]")
            bloque.append(f"  {quien}  " + t.replace("\n", "\n           "))
        bloque.append("")
        gastado += sum(len(x) for x in bloque)
        lineas += bloque
    if cortadas:
        lineas += [f"[{cortadas} charlas quedaron sin transcribir por el tope. "
                   "Para ver una entera, pedila sola con usuario=<id>.]", ""]
    return lineas


def informe(revisadas: list, meta: dict | None = None) -> str:
    meta = meta or {}
    lineas = ["", "=" * 78,
              "PRODUCCION COMO BANCO — los invariantes sobre las charlas REALES",
              "=" * 78, ""]
    # QUE CONJUNTO SE MIDIO, ARRIBA DE TODO. Un numero sin su denominador se
    # compara con el de la corrida anterior y no significa nada.
    if meta.get("usuario"):
        lineas += [f"CONJUNTO: la charla {meta['usuario']}, sola.", ""]
    elif meta.get("ventana_s"):
        horas = meta["ventana_s"] / 3600
        lineas += [f"VENTANA: las ultimas {horas:.0f} horas. "
                   f"Se miraron {meta.get('vistas', 0)} charlas y entraron "
                   f"{len(revisadas)}.",
                   "Dos corridas con la MISMA ventana se comparan; con "
                   "ventanas distintas, no.", ""]
    else:
        lineas += ["SIN VENTANA: se midieron las primeras charlas por orden de "
                   "id, que son siempre las mismas.",
                   "El numero de abajo se mueve con --limite y NO se compara "
                   "con el de otra corrida. Pasa --desde para que se pueda.",
                   ""]
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
        "",
        "Y ESTE NUMERO MIDE EL TEXTO DE SALIDA, NADA MAS. `revisar` recibe el",
        "mensaje, el anterior y el vocabulario: no ve el estado del turno. Los",
        "avisos que el turno si deja -turno_incompleto,",
        "punto_con_material_sin_texto, turno_guarda_error- viven en los LOGS y",
        "no cuentan aca. Cero violaciones y tres avisos en la misma ventana es",
        "un resultado posible, no una contradiccion: leelo junto a los logs y",
        "junto a la charla de abajo.",
        "=" * 78]

    if todas:
        cuenta = {}
        for f in todas:
            cuenta[f["regla"]] = cuenta.get(f["regla"], 0) + 1
        lineas += ["", "POR REGLA, de la que mas duele para abajo:"]
        for regla, n in sorted(cuenta.items(), key=lambda x: -x[1]):
            lineas.append(f"  {n:>3}  {regla}")

    dialogos = meta.get("dialogos") or {}
    if dialogos:
        lineas += transcripcion(revisadas, dialogos)
    return "\n".join(lineas)


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limite", type=int, default=20,
                    help="tope de charlas. Con --desde es solo un tope de "
                         "seguridad: el conjunto lo elige la ventana.")
    ap.add_argument("--usuario", default="")
    ap.add_argument("--desde", default="",
                    help="ventana de tiempo: 30m, 18h, 2d. Audita SOLO las "
                         "charlas tocadas dentro de la ventana, que es lo "
                         "unico que hace comparables dos corridas.")
    ap.add_argument("--sin-transcripcion", action="store_true",
                    help="no imprime la charla literal al final. Por defecto "
                         "SE IMPRIME: el texto que recibio el cliente no esta "
                         "en ningun log y sin el no se puede juzgar un turno.")
    args = ap.parse_args(argv)
    desde_s = ventana_a_segundos(args.desde)
    if args.desde and not desde_s:
        print(f"No entiendo la ventana '{args.desde}'. Se espera 30m, 18h o 2d.")
        return 1

    tok = _token()
    if not tok:
        print("Sin GCP_SA_KEY_B64 en el entorno (o sin la libreria de firma):\n"
              "no se pueden bajar las charlas reales. No es un error del\n"
              "sistema; es que este entorno no tiene la credencial de lectura.")
        return 0

    try:
        crudas, meta = charlas(tok, args.limite, args.usuario, desde_s)
    except Exception as e:
        print(f"No se pudieron bajar las charlas: {type(e).__name__}: {e}")
        return 1

    if args.sin_transcripcion:
        meta["dialogos"] = {}

    revisadas = []
    for uid, mensajes in crudas:
        if not mensajes:
            continue
        revisadas.append((uid, mensajes, revisar_charla(mensajes)))

    if not revisadas:
        # NO ES LO MISMO "no hubo" que "no anduvo", y con ventana hay que
        # decirlo: cero charlas nuevas es un resultado valido del instrumento.
        if desde_s:
            print(f"Ninguna charla se toco en las ultimas "
                  f"{desde_s / 3600:.0f} horas. Se miraron "
                  f"{meta.get('vistas', 0)}. No hay nada nuevo que auditar.")
        else:
            print("No hay charlas con respuestas del bot para revisar.")
        return 0

    print(informe(revisadas, meta))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
