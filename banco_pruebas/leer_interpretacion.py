#!/usr/bin/env python3
"""EL NUMERO DE LA INTERPRETACION, LEIDO DE PRODUCCION.

QUE HACE Y QUE NO. Lee los logs de Cloud Run del bot vivo, busca el
`motor_pedido` de cada turno y lo cruza contra `vara_interpretacion.json`.
NO llama al modelo, NO usa la clave de nadie y NO simula un turno: mide lo que
YA paso en WhatsApp. Por eso vive en `banco_pruebas/` —que no deploya— pero no
es un banco: es el instrumento del camino real.

POR QUE EXISTE, y es la leccion del 20-sep. Durante toda esa sesion la vara se
reconstruia a mano en cada tanda: "declaro el origen?", "declaro el reparto?".
Con el blanco dibujado de nuevo cada vez, un avance y un error de conteo se
parecen demasiado. Escrita, el numero sale solo.

LAS DOS COLUMNAS. `v1` es lo que el modelo declaro en su PRIMERA llamada; `<=v2`
es lo acumulado hasta la segunda. La consigna de Martin fue "una vuelta o a lo
sumo dos", asi que las dos se cuentan y ninguna sola alcanza para juzgar.

Uso, desde la raiz y con la credencial de lectura en el entorno:

    python3 banco_pruebas/leer_interpretacion.py            # ultimos 30 min
    python3 banco_pruebas/leer_interpretacion.py 90         # ultimos 90 min
"""
import base64
import json
import os
import sys
import unicodedata
from datetime import datetime, timedelta, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VARA = os.path.join(RAIZ, "banco_pruebas", "vara_interpretacion.json")
SERVICIO = "agente-bot"


def _norm(t) -> str:
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


# ── LAS CASILLAS, UNA FUNCION POR TIPO ──────────────────────────────────────
#
# Cada una recibe el pedido acumulado tal como el modelo lo escribio y contesta
# True o False. Sin puntajes parciales y sin ranking: o la casilla esta llena o
# no esta, que es la misma regla con la que `guardas_salida.campos_nombrados`
# decide, y por el mismo motivo —aparear por parecido es la enfermedad que el
# MAPA_CABLEADO ya tiene numerada cuatro veces—.

def _consultas(p):
    return p.get("consultas") or []


def _c_consulta(c, p):
    for q in _consultas(p):
        if c.get("categoria") and _norm(q.get("categoria")) != _norm(c["categoria"]):
            continue
        # DONDE SEA QUE LO HAYA NOMBRADO, y es el segundo bug de esta pieza.
        # La vara miraba solo `texto` y `categoria`, y a "cuanto sale el K120"
        # el modelo contesto `categoria: teclado` + `nombre contiene K120`,
        # que es una lectura MEJOR que la escrita. La vara daba mal al modelo
        # por acertar de otra forma. La casilla es "busca el producto
        # puntual": cualquier lugar de la consulta donde lo nombre cuenta.
        if c.get("texto_contiene") and _norm(c["texto_contiene"]) not in _norm(
                json.dumps(q, ensure_ascii=False)):
            continue
        if c.get("cantidad") and q.get("cantidad") not in c["cantidad"]:
            continue
        return True
    return False


def _c_condicion(c, p):
    for q in _consultas(p):
        for x in (q.get("condiciones") or []):
            if _norm(x.get("campo")) not in [_norm(v) for v in c["campo"]]:
                continue
            if c.get("valor") and _norm(c["valor"]) not in _norm(x.get("valor")):
                continue
            if c.get("acepta") and _norm(x.get("operador")) not in [
                    _norm(v) for v in c["acepta"]]:
                continue
            return True
    return False


def _c_envio(c, p):
    for e in (p.get("envios") or []):
        nombre = e.get("destino") if isinstance(e, dict) else e
        if _norm(c["destino"]) in _norm(nombre):
            return True
    return False


def _c_nombra(c, p):
    """La palabra aparece en ALGUN lado de lo declarado. Para lo que el cliente
    dijo una vez y el modelo puede anotar en mas de un campo con razon."""
    return _norm(c["palabra"]) in _norm(json.dumps(p, ensure_ascii=False))


def _c_temas_limpios(c, p):
    """NO declarar de mas. Es el defecto que trajo el enum de 104 temas del
    20-sep: medido 4 de 4 en M6, el modelo agrego `confianza_seguridad`,
    `pedir_descuento` y `envio_urgente` a un cliente que no pregunto ninguna.
    Antes del enum no podia pasar; es el costo del candado y se mide."""
    return len(p.get("temas") or []) <= int(c.get("tope", 0))


def _c_envio_va(c, p):
    # EL VINCULO. Hoy `envios` es una lista de textos pelados, asi que esta
    # casilla NO SE PUEDE llenar: un texto no tiene donde decir que va ahi.
    # Queda escrita igual y en cero a proposito, que es como se ve una deuda.
    atados = sum(1 for e in (p.get("envios") or [])
                 if isinstance(e, dict) and str(e.get("va") or "").strip())
    return atados >= int(c.get("cuantos", 1))


def _c_reparto(c, p):
    # POR CONJUNTO Y NO POR LISTA, y es el arreglo del primer bug de esta
    # pieza: acumular dos vueltas que declararon el MISMO 70/30 daba
    # [30,30,70,70] y la casilla se apagaba en la vuelta 2. Una vara que baja
    # cuando el modelo repite lo mismo no mide al modelo, mide al lector.
    hubo = {int(x.get("porcentaje") or 0)
            for x in (p.get("reparto_pago") or [])}
    return hubo == set(c["porcentajes"])


def _c_cuenta(c, p):
    """QUE EL MODELO CAPTO QUE LE PIDIERON UN TOTAL, y desde el 21-sep eso se
    declara en un campo plano de si o no.

    ANTES MEDIA OTRA COSA, Y ERA IMPOSIBLE DE LLENAR EN LA VUELTA 1. Miraba
    `cuenta.items`, que pide un ID por producto; el cliente nombro RUBROS
    -"dos notebooks"- y el modelo todavia no miro el catalogo, asi que no
    tiene un solo id que escribir. La casilla se salteaba: medido tres veces,
    el modelo hacia el reparto O la cuenta, nunca las dos. Esto NO es aflojar
    la vara, es que CAMBIO EL ESQUEMA: se mide lo mismo de siempre -si capto
    el pedido de presupuesto- y ahora sobre el campo donde eso se puede
    escribir de verdad.

    LA FORMA VIEJA SIGUE VALIENDO: un turno que ya eligio los ids llena la
    casilla como antes, asi que un log anterior al cambio se lee igual.
    """
    return bool(p.get("pedir_total")
                or ((p.get("cuenta") or {}).get("items")) or [])


def _c_tema(c, p):
    pedidos = [_norm(t) for t in (p.get("temas") or [])]
    return any(_norm(v) in pedidos for v in c["acepta"])


def _c_busco(c, p):
    return any(_norm(q.get("busco")) in [_norm(v) for v in c["acepta"]]
               for q in _consultas(p))


def _c_orden(c, p):
    for q in _consultas(p):
        o = q.get("ordenar_por") or {}
        if (_norm(o.get("campo")) in [_norm(v) for v in c["campo"]]
                and _norm(o.get("direccion")) in [_norm(v) for v in c["direccion"]]):
            return True
    return False


def _c_barato(c, p):
    """LO MAS BARATO PRIMERO, dicho de cualquiera de las dos formas validas:
    `ordenar_por precio_ars min`, o el grado sobre el precio apuntando al
    minimo del catalogo. Las dos son la misma lectura del cliente."""
    for q in _consultas(p):
        o = q.get("ordenar_por") or {}
        if _norm(o.get("campo")) == "precio_ars" and _norm(
                o.get("direccion")) == "min":
            return True
        for x in (q.get("condiciones") or []):
            if (_norm(x.get("campo")) == "precio_ars"
                    and _norm(x.get("operador")) == "prefiere"):
                return True
    return False


def _c_compat(c, p):
    return bool(p.get("compatibilidad"))


def _c_sin_consultas(c, p):
    return not _consultas(p)


# LAS CASILLAS DE AUSENCIA, Y NO SE ACUMULAN (21-sep-2026).
#
# TODAS LAS DEMAS SON MONOTONAS: una vez que el modelo declaro algo, sumar la
# vuelta siguiente no se lo puede quitar. `temas_limpios` mide lo contrario
# —que NO haya declarado de mas— asi que acumularla la apaga en cuanto una
# vuelta agrega un tema, y la columna 2 puede quedar POR DEBAJO de la 1.
#
# MEDIDO EN LA TANDA DEL 21-sep: M6 dio 10 de 10 en la vuelta 1 y 9 hasta la
# 2, porque en la segunda el modelo pidio `costo_envio` y `plazo_envio` —a un
# cliente que SI pregunto por envios—. Un numero que baja cuando el modelo
# hace mas trabajo no mide al modelo, mide al lector: es la misma enfermedad
# que el bug del `reparto` del 20-sep, un escalon mas adentro.
#
# SE EVALUAN SOBRE LA VUELTA 1 Y ESE VALOR SE ARRASTRA. La pregunta que
# contestan es "de entrada, ¿metio ruido?", y esa se contesta en la primera
# llamada. Lo que la vuelta 2 agregue se IMPRIME aparte para que no se pierda,
# pero no mueve el puntaje.
AUSENCIA = {"temas_limpios"}

CASILLA = {"consulta": _c_consulta, "condicion": _c_condicion,
           "envio": _c_envio, "envio_va": _c_envio_va, "reparto": _c_reparto,
           "cuenta": _c_cuenta, "tema": _c_tema, "busco": _c_busco,
           "orden": _c_orden, "compat": _c_compat, "nombra": _c_nombra,
           "temas_limpios": _c_temas_limpios, "barato": _c_barato,
           "sin_consultas_obligatorias": _c_sin_consultas}


def _juntar(a: dict, b: dict) -> dict:
    """Lo declarado hasta esta vuelta. Las listas se suman, el ultimo objeto no
    vacio gana: es lo mismo que hace el turno con las fichas y los envios."""
    fuera = dict(a)
    for k, v in (b or {}).items():
        if isinstance(v, list):
            junto = list(fuera.get(k) or []) + v
            # SIN REPETIR lo identico: el modelo manda la misma consulta en dos
            # vueltas seguidas mas seguido de lo que parece, y una lista con el
            # doble de todo no dice nada distinto.
            visto, limpio = set(), []
            for x in junto:
                clave = json.dumps(x, sort_keys=True, ensure_ascii=False)
                if clave in visto:
                    continue
                visto.add(clave)
                limpio.append(x)
            fuera[k] = limpio
        elif v:
            fuera[k] = v
    return fuera


# ── LOS LOGS DE PRODUCCION ──────────────────────────────────────────────────

def _turnos(minutos: int) -> list:
    """[{trace, texto, vueltas: [pedido, ...]}] del bot vivo."""
    import requests
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    bruto = next((v for k, v in os.environ.items()
                  if k.upper().startswith("GCP_SA_KEY")), "")
    if not bruto:
        raise SystemExit("falta la credencial de lectura en el entorno")
    s = bruto.strip()
    info = json.loads(s if s.startswith("{") else base64.b64decode(s).decode())
    cred = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/logging.read"])
    cred.refresh(Request())
    desde = (datetime.now(timezone.utc)
             - timedelta(minutes=minutos)).strftime("%Y-%m-%dT%H:%M:%SZ")
    filtro = (f'resource.type="cloud_run_revision" '
              f'resource.labels.service_name="{SERVICIO}" '
              f'timestamp>="{desde}" '
              f'(jsonPayload.event="message_received" OR '
              f'jsonPayload.event="motor_pedido")')
    r = requests.post(
        "https://logging.googleapis.com/v2/entries:list",
        headers={"Authorization": f"Bearer {cred.token}"},
        json={"resourceNames": [f"projects/{info['project_id']}"],
              "filter": filtro, "orderBy": "timestamp desc", "pageSize": 500},
        timeout=120)
    if r.status_code != 200:
        raise SystemExit(f"HTTP {r.status_code}: {r.text[:300]}")
    turnos, por_trace = [], {}
    for e in reversed(r.json().get("entries") or []):
        d = e.get("jsonPayload") or {}
        tr = d.get("trace_id")
        if d.get("event") == "message_received":
            t = {"trace": tr, "texto": d.get("msg_preview") or "",
                 "rev": (e.get("resource") or {}).get(
                     "labels", {}).get("revision_name", ""), "vueltas": []}
            turnos.append(t)
            por_trace[tr] = t
        elif d.get("event") == "motor_pedido" and tr in por_trace:
            try:
                por_trace[tr]["vueltas"].append(json.loads(d["pedido"]))
            except Exception:  # noqa: BLE001 — un pedido roto no tumba la lectura
                pass
    return turnos


def _clave(texto: str) -> str:
    """El texto sin nada que el dedo pueda cambiar: minusculas, sin acentos y
    sin puntuacion ni espacios."""
    return "".join(c for c in _norm(texto) if c.isalnum())


def _de_que_mensaje(texto: str, vara: dict):
    """El mensaje de la vara al que corresponde este turno.

    APAREA POR PREFIJO EXACTO, no por parecido: se comparan los primeros 30
    caracteres utiles, o el mensaje entero si es mas corto. No hay ranking ni
    distancia, que es la enfermedad que el MAPA_CABLEADO ya tiene numerada.

    LA PUNTUACION SE SACA, y es el primer bug de esta pieza: M3 se mando como
    "cuanto sale el K120" y la vara decia "cuanto sale el K120?". El turno
    existia en los logs y el lector lo tiro, o sea que un signo de pregunta de
    menos borraba tres corridas del numero.
    """
    plano = _clave(texto)
    for m in vara["mensajes"]:
        esperado = _clave(m["texto"])
        n = min(30, len(plano), len(esperado))
        if n >= 10 and plano[:n] == esperado[:n]:
            return m
    return None


def cargar_vara() -> dict:
    return json.load(open(VARA, encoding="utf-8"))


def emparejar(turnos: list, vara: dict) -> list:
    """[(turno, mensaje_de_la_vara)] de los turnos que la vara reconoce."""
    vistos = [(t, _de_que_mensaje(t["texto"], vara)) for t in turnos]
    return [(t, m) for t, m in vistos if m]


def puntuar(vistos: list) -> int:
    """EL PUNTAJE, Y ES LA UNICA DEFINICION DE 'CORRECTO' QUE HAY.

    LA SEPARACION DEL 21-sep, y es la regla 2 de CLAUDE.md aplicada a este
    archivo. La tanda offline -`banco_pruebas/tanda_interpretacion.py`- mide
    exactamente lo mismo que produccion, asi que NO puede tener su propio
    puntaje: dos definiciones de correcto se separan el dia que alguien toca
    una, y ahi los dos numeros dejan de compararse sin que nadie lo note.
    Lo que cambia entre los dos caminos es de donde salen los turnos; que
    cuenta como acierto, no.

    Recibe [(turno, mensaje_de_la_vara)] y cada turno es
    {trace, texto, rev, vueltas: [pedido, ...]}.
    """
    tot1 = tot2 = total = 0
    for t, m in vistos:
        v1 = _juntar({}, t["vueltas"][0] if t["vueltas"] else {})
        v2 = v1
        for p in t["vueltas"][1:2]:
            v2 = _juntar(v2, p)
        print(f"\n{m['id']}  {t['trace']}  {t['rev'][-8:]}  "
              f"{len(t['vueltas'])} llamada(s)")
        n1 = n2 = 0
        for c in m["casillas"]:
            f = CASILLA[c["tipo"]]
            a = f(c, v1)
            # UNA CASILLA DE AUSENCIA NO SE ACUMULA: arrastra la vuelta 1.
            b = a if c["tipo"] in AUSENCIA else f(c, v2)
            n1 += a
            n2 += b
            marca = "OK " if a else ("v2 " if b else ".. ")
            print(f"   {marca} {c['n']}")
            # LO QUE ENSUCIO DESPUES NO CUENTA, PERO TAMPOCO SE PIERDE.
            if c["tipo"] in AUSENCIA and a and not f(c, v2):
                print(f"        ojo: limpia en la vuelta 1 y sucia despues "
                      f"— {(v2.get('temas') or [])}")
        total += len(m["casillas"])
        tot1 += n1
        tot2 += n2
        print(f"   ── {n1} de {len(m['casillas'])} en la vuelta 1, "
              f"{n2} hasta la vuelta 2")
        # EL NUMERO QUE NO EXISTIA HASTA EL 21-sep: cuantos renglones enumero
        # el modelo contra cuantas casillas lleno. Enumerar DE MENOS es que no
        # entendio el mensaje; enumerar bien y llenar poco es un problema de
        # REPARTO. Hasta hoy los dos fracasos se veian identicos y no habia
        # forma de saber cual de los dos arreglar.
        reng = v1.get("renglones") or []
        print(f"   ── {len(reng)} renglon(es): "
              + " | ".join(str(x)[:38] for x in reng[:9]))
    print(f"\n{'='*60}\nTOTAL   vuelta 1: {tot1} de {total}"
          f"   ({100*tot1//total}%)"
          f"\n        hasta la 2: {tot2} de {total}   ({100*tot2//total}%)"
          f"\n        turnos leidos: {len(vistos)}")
    return 0


def main(argv):
    minutos = int(argv[0]) if argv else 30
    vistos = emparejar(_turnos(minutos), cargar_vara())
    if not vistos:
        print(f"ningun turno de la vara en los ultimos {minutos} minutos")
        return 1
    return puntuar(vistos)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
