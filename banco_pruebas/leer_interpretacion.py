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


def _nombre_del_tema(t):
    """EL TEMA, VENGA COMO VENGA (22-sep-2026).

    Desde hoy `temas` son objetos `{tema, dicho}` —la cita del cliente al lado,
    que es lo que le pone costo a declarar de mas—. Antes eran textos pelados.

    Y ESTE RENGLON LO ESCRIBE UNA MEDICION QUE SALIO MAL. La primera tanda con
    el campo nuevo dio 51 de 57 contra 55, y el culpable no era el cambio: era
    este lector, que comparaba el nombre del tema contra un diccionario entero
    y no acertaba nunca. El modelo habia declarado `garantia` con su cita
    exacta y la vara lo conto como fallado.

    ES LA MISMA ENFERMEDAD QUE EL SANEO ANTES DEL LOG, de esta misma sesion,
    con el signo cambiado: alla el instrumento medía la correccion y el numero
    subia solo; aca dejo de ver el campo y el numero bajaba solo. Las dos veces
    el defecto estaba en el que mide, no en lo medido.
    """
    return _norm(t.get("tema") if isinstance(t, dict) else t)


def _c_tema(c, p):
    pedidos = [_nombre_del_tema(t) for t in (p.get("temas") or [])]
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


def _c_sin_umbral_inventado(c, p):
    """QUE NO SE INVENTE UN NUMERO QUE EL CLIENTE NO DIJO (21-sep-2026).

    MEDIDO EN M11. A "que no sea muy cara" —sin ninguna cifra— el modelo
    escribio `precio_ars menor 500000` en cuatro corridas y `menor 800000` en
    la quinta. **Se invento un techo, y ni siquiera el mismo.**

    POR QUE IMPORTA MAS DE LO QUE PARECE: un orden por precio no pierde nada,
    muestra lo barato primero y el cliente elige. Un FILTRO por un techo
    inventado BORRA productos que el cliente podria querer, y los borra en
    silencio: nadie se entera de lo que no salio. Es el codigo eligiendo por
    el cliente, que es la misma enfermedad que `geo_cp` con la localidad.

    Y ES LA SENAL DE UN HUECO: "muy cara" es una GAMA, la fuente no tiene
    campo de gama, y en vez de decirlo el modelo tapa el hueco con un numero.
    Un hueco que se tapa solo es un hueco que nadie va a arreglar.
    """
    for q in _consultas(p):
        for x in (q.get("condiciones") or []):
            if _norm(x.get("campo")) not in [_norm(v) for v in c["campo"]]:
                continue
            if _norm(x.get("operador")) in ("menor", "mayor", "menor_igual",
                                            "mayor_igual", "entre"):
                return False
    return True


def _c_afirma(c, p):
    """LO QUE EL CLIENTE DA POR SENTADO, DECLARADO (22-sep-2026).

    ERA DEUDA Y AHORA ES CASILLA. Hasta hoy la premisa falsa —clase F2— se
    contaba con `sin_mecanismo` y valia cero a proposito, porque el esquema no
    tenia donde anotarla. Es el mismo camino que `envio_va` el 20-sep: la
    casilla imposible se escribe primero, se construye el campo, y recien ahi
    se puede medir. Ese precedente dio 0 de 4 y hoy da 100%.

    Y NO ES AFLOJAR LA VARA NI ENDURECERLA: mide lo mismo que medía —si el
    modelo DECLARA la afirmacion en vez de tragarsela— sobre el campo donde
    eso por fin se puede escribir. Lo que cambio es el esquema, no el
    requisito.
    """
    for a in (p.get("afirma") or []):
        if not isinstance(a, dict):
            continue
        junto = _norm(str(a.get("sobre") or "") + " " + str(a.get("dice") or ""))
        if all(_norm(v) in junto for v in c.get("nombra") or []):
            return True
    return False


def _c_sin_mecanismo(c, p):
    """LA DEUDA, ESCRITA Y EN CERO A PROPOSITO (21-sep-2026).

    Es la clase que el cliente SI dice y el esquema de hoy no tiene donde
    anotar: el proposito del eje D, la premisa falsa, la urgencia, el
    condicional, el presupuesto como techo. No es que el modelo falle: es que
    NO HAY CASILLA.

    ES EL MISMO RECURSO QUE USO `envio_va` EL 20-sep -"queda escrita igual y
    en cero a proposito, que es como se ve una deuda"- y ahi funciono: la
    casilla imposible se volvio el pedido del campo `va`, que se construyo y
    hoy da 100%.

    POR ESO NO ENTRA EN EL DENOMINADOR. Si entrara, el numero bajaria por algo
    que el modelo no hizo mal, y las corridas dejarian de compararse con el
    piso. Se cuenta aparte y se imprime aparte: esta lista ES la
    especificacion de lo que la FICHA 57 tiene que construir.
    """
    return False


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
           "sin_consultas_obligatorias": _c_sin_consultas,
           "afirma": _c_afirma,
           "sin_mecanismo": _c_sin_mecanismo,
           "sin_umbral_inventado": _c_sin_umbral_inventado}

# LA DEUDA NO SE PUNTUA. Ver `_c_sin_mecanismo`.
DEUDA = "sin_mecanismo"


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


def puntuar(vistos: list, imprimir: bool = True) -> dict:
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
    # EL DETALLE VUELVE, Y NO SOLO SE IMPRIME (21-sep-2026). Con una sola
    # corrida alcanzaba con leer; para decir si un 12 de 12 es el numero o fue
    # suerte hacen falta varias, y para eso el puntaje tiene que ser un dato
    # que se pueda juntar. Lo que NO cambia es quien decide si una casilla esta
    # llena: esa sigue siendo la unica definicion, aca.
    detalle: dict = {}
    for t, m in vistos:
        v1 = _juntar({}, t["vueltas"][0] if t["vueltas"] else {})
        v2 = v1
        for p in t["vueltas"][1:2]:
            v2 = _juntar(v2, p)
        print(f"\n{m['id']}  {t['trace']}  {t['rev'][-8:]}  "
              f"{len(t['vueltas'])} llamada(s)")
        n1 = n2 = 0
        fallaron, deuda = [], []
        for c in m["casillas"]:
            # LA DEUDA SE LISTA Y NO SE PUNTUA, ni arriba ni abajo de la
            # fraccion: no es una falla del modelo, es una casilla que no
            # existe todavia.
            if c["tipo"] == DEUDA:
                deuda.append((c.get("clase", "?"), c["n"]))
                if imprimir:
                    print(f"   -- {c['n']}   [{c.get('clase', '?')}] SIN CASILLA")
                continue
            f = CASILLA[c["tipo"]]
            a = f(c, v1)
            # UNA CASILLA DE AUSENCIA NO SE ACUMULA: arrastra la vuelta 1.
            b = a if c["tipo"] in AUSENCIA else f(c, v2)
            n1 += a
            n2 += b
            if not a:
                fallaron.append(c["n"])
            marca = "OK " if a else ("v2 " if b else ".. ")
            if imprimir:
                print(f"   {marca} {c['n']}")
            # LO QUE ENSUCIO DESPUES NO CUENTA, PERO TAMPOCO SE PIERDE.
            if c["tipo"] in AUSENCIA and a and not f(c, v2):
                print(f"        ojo: limpia en la vuelta 1 y sucia despues "
                      f"— {(v2.get('temas') or [])}")
        puntuables = len(m["casillas"]) - len(deuda)
        total += puntuables
        tot1 += n1
        tot2 += n2
        # SE ACUMULA, NO SE PISA (22-sep-2026). Leyendo PRODUCCION el mismo
        # mensaje llega varias veces —M13 llego cuatro—, y con el detalle
        # indexado por id sobrevivia solo el ultimo. El TOTAL siempre estuvo
        # bien; lo que mentia era el renglon del nucleo y el conteo de deuda.
        # Un instrumento que miente sobre una repeticion es peor leyendo
        # produccion que leyendo el banco, porque alla la repeticion es lo
        # normal.
        detalle.setdefault(m["id"], []).append(
            {"v1": n1, "v2": n2, "de": puntuables,
             "fallaron": fallaron, "deuda": deuda,
             "nucleo": bool(m.get("nucleo")),
             "renglones": len(v1.get("renglones") or [])})
        print(f"   ── {n1} de {puntuables} en la vuelta 1, "
              f"{n2} hasta la vuelta 2"
              + (f"   (+{len(deuda)} sin casilla)" if deuda else ""))
        # EL NUMERO QUE NO EXISTIA HASTA EL 21-sep: cuantos renglones enumero
        # el modelo contra cuantas casillas lleno. Enumerar DE MENOS es que no
        # entendio el mensaje; enumerar bien y llenar poco es un problema de
        # REPARTO. Hasta hoy los dos fracasos se veian identicos y no habia
        # forma de saber cual de los dos arreglar.
        reng = v1.get("renglones") or []
        print(f"   ── {len(reng)} renglon(es): "
              + " | ".join(str(x)[:38] for x in reng[:9]))
    # EL NUCLEO SE INFORMA APARTE, y no es un adorno: son los seis mensajes
    # con los que se midio el piso del 21-sep. Si el total se mezclara con los
    # mensajes nuevos, el piso dejaria de tener con que compararse y se
    # perderia la unica referencia que hay.
    nuc = [x for xs in detalle.values() for x in xs if x["nucleo"]]
    n_v1, n_de = sum(x["v1"] for x in nuc), sum(x["de"] for x in nuc)
    deudas = len({c for xs in detalle.values() for x in xs
                  for c, _n in x["deuda"]})
    if imprimir:
        print(f"\n{'='*60}\nTOTAL   vuelta 1: {tot1} de {total}"
              f"   ({100*tot1//total}%)"
              f"\n        hasta la 2: {tot2} de {total}   ({100*tot2//total}%)"
              f"\n        turnos leidos: {len(vistos)}")
        if nuc and n_de and n_de != total:
            print(f"\n  NUCLEO ({len(nuc)} turnos): {n_v1} de {n_de}"
                  f"   — es el unico numero comparable con"
                  f" interpretacion_piso.json")
        if deudas:
            print(f"  SIN CASILLA: {deudas} clases que el cliente dice y el"
                  f" esquema no tiene donde anotar.")
    return {"v1": tot1, "v2": tot2, "de": total, "turnos": len(vistos),
            "nucleo_v1": n_v1, "nucleo_de": n_de, "deuda": deudas,
            "por_mensaje": detalle}


def main(argv):
    minutos = int(argv[0]) if argv else 30
    vistos = emparejar(_turnos(minutos), cargar_vara())
    if not vistos:
        print(f"ningun turno de la vara en los ultimos {minutos} minutos")
        return 1
    r = puntuar(vistos)
    return 0 if r["v1"] == r["de"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
