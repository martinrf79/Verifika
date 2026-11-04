"""LA TRADUCCION SOLA, CONTRA LAS 42 CHARLAS REALES — 4-nov-2026, con Martin.

La pregunta que decide si se construye el flujo de dos llamadas: el modelo, leyendo el mensaje y la charla, le pasa al
codigo lo que necesita para contestar? Si sale bien en 9 de cada 10 partes o mas, se construye; si no, no.

  ORO        la lista correcta de cada turno, escrita a mano ANTES de correr, sobre lo que dijo el cliente. Cada parte
             dice que hace el cliente, que fuente de las siete la contesta, y lo que el codigo necesita: rubro, producto,
             sobre que, condiciones, orden, cantidades por destino, color, medio y porcentaje del pago, tope.
  la llamada el modelo de produccion con la clave gratis, una vez por turno, con la charla grabada del 3-nov como historia.
  la nota    la pone este programa, comparando cada parte contra el oro. Nadie la interpreta.

Las palabras de la tienda que usa el modelo son las de la fuente: rubros del catalogo, temas de la FAQ, campos de la
ficha y equipos de la tabla de compatibilidad. No son etiquetas inventadas.

    python3 banco_pruebas/examen_real/traduccion.py --correr [--etiqueta r1] [id ...]   con la clave gratis
    python3 banco_pruebas/examen_real/traduccion.py --nota [--etiqueta r1] [--ver]
"""
import csv
import json
import os
import re
import sys
import time
import unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, RAIZ)
FUENTE = os.path.join(RAIZ, "data", "clientes", "verifika_prod")
SALIDA = os.path.join(AQUI, "traduccion_corridas.jsonl")
ARGS = sys.argv[1:]


# ---------------------------------------------------------------- el oro
def P(accion, fuente=None, **kw):
    return {"accion": accion, "fuente": fuente, **kw}


M7 = [P("agrega", "pedido", rubro="auricular", destinos={"cordoba": 1, "posadas": 1}, conds=[("origen", "no chin")]),
      P("agrega", "pedido", rubro="mouse", destinos={"cordoba": 1, "concordia": 1}, conds=[("origen", "no chin")]),
      P("agrega", "pedido", rubro="memoria", destinos={"posadas": 2}, conds=[("origen", "no chin")]),
      P("agrega", "pedido", rubro="teclado", destinos={"concordia": 1}, opt=True),
      P("pago", "plata", porcentaje=70, medio=None), P("pago", "plata", porcentaje=30, medio=None)]
BARATOS_CAROS = [P("pregunta", "catalogo", orden="barat", cantidad=2), P("pregunta", "catalogo", orden="car", cantidad=2),
                 P("pregunta", "faq", sobre="formas_pago"), P("pregunta", "faq", sobre="mayorista")]
TRES_MOUSE = [P("agrega", "pedido", rubro="mouse", destinos={"rosario": 2, "neuquen": 1}),
              P("agrega", "pedido", rubro="teclado", destinos={"rosario": 1, "neuquen": 1}),
              P("agrega", "pedido", rubro="auricular", destinos={"neuquen": 1}),
              P("agrega", "pedido", rubro="webcam", destinos={"rosario": 1}),
              P("tope", "plata", monto=600000),
              P("pago", "plata", porcentaje=50, medio="transfer"), P("pago", "plata", porcentaje=50, medio="master")]
TECLADO_A = lambda lugar: P("agrega|cambia|confirma", "pedido", rubro="teclado", destino=lugar)  # noqa: E731
PAGO70 = P("pago", "plata", porcentaje=70, medio="transfer")
NOMBRE = [P("nombre", "cierre")]
SI = [P("confirma", "pedido")]
PS5 = [P("pregunta", "compatibilidad|catalogo", rubro="auricular", equipo="ps5|playstation|play")]
ECO_NEGRO = [P("agrega", "pedido", rubro="auricular", orden="barat", color="negr")]
NO_MP = P("pago", "plata", medio="no mp|no mercado|sin mp|sin mercado|no tengo")
VILLA = [P("cambia|agrega|confirma", "pedido", destino="villa del prado")]
NEUQUEN = [P("pregunta", "envio", destino="neuquen")]
G305_G203 = [P("agrega|pregunta", "pedido|catalogo", conds=[("conexion", "inalambric|no cable|sin cable")])]
GARANTIA_G305 = [P("pregunta", "catalogo", producto="g305", sobre="garantia")]

ORO = {
    "76eac58c67": [[P("charla|pregunta", "ninguna|faq")], [P("pregunta", "catalogo", sobre="rubros")]],
    "1fdccdd0d7": [BARATOS_CAROS],
    "e4ed989771": [G305_G203,
                   [P("pregunta", "compatibilidad", producto="g305", equipo="mac"), P("agrega", "pedido", producto="g305")],
                   [P("pregunta", "faq", sobre="promocion|descuento")]],
    "6740e01771": [[P("agrega", "pedido", rubro="notebook", destinos={"la plata": 2}, orden="barat"),
                    P("agrega", "pedido", rubro="microfono", cantidad=1, orden="barat"),
                    P("agrega", "pedido", rubro="memoria", cantidad=4, orden="barat")],
                   BARATOS_CAROS],
    "7c7947db9f": [[P("pregunta", "catalogo", conds=[("origen", "no chin")])]],
    "58cd96dfb4": [[P("pregunta", "catalogo", sobre="rubros")], [P("pregunta", "catalogo", orden="car", cantidad=1)]],
    "33dbb56c1b": [[P("pregunta", "catalogo", rubro="teclado", orden="barat")],
                   [P("pregunta", "catalogo", rubro="teclado")],
                   [P("pregunta", "catalogo|compatibilidad", producto="k617", sobre="conexion|pc")],
                   [P("pregunta", "ninguna"), P("pregunta", "catalogo", rubro="teclado", conds=[("conexion", "cable")])]],
    "7f8cd4a5ca": [[P("pregunta", "catalogo", conds=[("uso", "gam|jueg")])],
                   [P("pregunta", "catalogo", sobre="rubros")],
                   [P("pregunta", "ninguna|catalogo", rubro="placa", sobre="temperat|calien|termic")],
                   [P("agrega", "pedido", producto="rx 7600")],
                   [P("nombre", "cierre"), P("cambia|agrega|confirma", "pedido", destino="cordoba")],
                   [P("pago", "plata", medio="naranja")]],
    "e3585160f3": [[P("pregunta", "no_vendemos")],
                   [P("pregunta", "catalogo|no_vendemos")],
                   [P("pregunta", "catalogo", rubro="tablet", orden="barat"), P("pregunta", "faq", sobre="cuota"),
                    P("pregunta", "faq|catalogo", sobre="garantia", opt=True),
                    P("pregunta", "faq|envio", sobre="envio", opt=True)],
                   [P("agrega|cambia|confirma", "pedido", producto="redmi pad", color="gris", destino="palermo")]],
    "d0c439c575": [M7, [P("pregunta", "catalogo", rubro="teclado", opt=True), TECLADO_A(None)]],
    "fe67b477ec": [M7, [TECLADO_A("concordia")],
                   [P("cambia", "pedido", orden="barat")], SI, NOMBRE, SI,
                   [P("cambia|confirma", "pedido", color="indistint|cualquier|igual", opt=True), PAGO70],
                   [P("cambia", "pedido", color="blanc")]],
    "b5ddaad494": [M7, [TECLADO_A("posadas")]],
    "83e58acb78": [M7, [TECLADO_A(None), P("cambia", "pedido", orden="barat")]],
    "386b8a84eb": [M7, [TECLADO_A(None), P("pregunta", "plata|envio")]],
    "b8df72a33c": [M7, [TECLADO_A(None)], [P("agrega|confirma", "pedido", rubro="teclado", cantidad=1)],
                   [P("pregunta", "plata")]],
    "157b658bc8": [M7, [TECLADO_A("concordia")], [TECLADO_A(None)]],
    "6344deed8c": [M7, [TECLADO_A("posadas"), PAGO70]],
    "08e6c44238": [M7, [TECLADO_A("posadas"), PAGO70]],
    "96b39fa8fd": [M7, [TECLADO_A("posadas"), PAGO70], [P("pregunta", "faq", sobre="formas_pago")],
                   [P("pago", "plata", medio="visa")], NOMBRE],
    "781919fa60": [M7, [TECLADO_A(None), P("pregunta", "faq", sobre="descuento|formas_pago|cuota")]],
    "854f1bea2c": [[P("agrega", "pedido", rubro="auricular", destinos={"cordoba": 2, "posadas": 1},
                      conds=[("origen", "no estados|no ee|no usa|no eeuu")]),
                    P("agrega", "pedido", rubro="mouse", destinos={"cordoba": 2}),
                    P("agrega", "pedido", rubro="memoria", destinos={"concordia": 3, "posadas": 1}),
                    P("agrega", "pedido", rubro="teclado", destinos={"concordia": 1}),
                    P("pago", "plata", porcentaje=70), P("pago", "plata", porcentaje=30)]],
    "e328e77809": [[P("agrega", "pedido", rubro="mouse", destinos={"rosario": 1, "mendoza": 3}),
                    P("agrega", "pedido", rubro="monitor", destinos={"rosario": 1, "mendoza": 1}),
                    P("agrega", "pedido", rubro="webcam", destinos={"mendoza": 1})],
                   [P("pregunta", "faq", sobre="cuota"), P("confirma", "pedido", opt=True)], NOMBRE],
    "06d02631b7": [TRES_MOUSE, NEUQUEN, [P("pregunta", "faq|catalogo", sobre="garantia")]],
    "e105d5a00b": [TRES_MOUSE, [P("cambia|pregunta", "pedido|catalogo", orden="mejor|car")],
                   [P("cambia", "pedido", orden="mejor|car")], [P("cambia", "pedido", orden="car")], NEUQUEN,
                   [P("cambia", "pedido", orden="barat")], NOMBRE],
    "a96e63a0cb": [TRES_MOUSE, [P("tope", "plata", monto=600000)]],
    "c48ed9921d": [[P("pregunta", "envio", destino="posadas")]],
    "aecba84109": [GARANTIA_G305],
    "c52411bf07": [GARANTIA_G305],
    "389090ca1a": [[P("pregunta", "catalogo", rubro="mouse", conds=[("marca", "logitech")]),
                    P("pregunta", "catalogo", rubro="teclado", conds=[("marca", "logitech")]),
                    P("pregunta", "catalogo", rubro="auricular", conds=[("marca", "jbl")])],
                   [P("pregunta", "catalogo", sobre="precio")]],
    "815c0c9b65": [G305_G203, [P("agrega|confirma|pregunta", "pedido|catalogo", producto="g305")],
                   [P("confirma|cambia", "pedido")], [P("charla|pregunta", "ninguna|faq")], SI],
    "0cdeffc8a2": [G305_G203],
    "e993ae644d": [[P("agrega", "pedido", producto="m170", cantidad=3, conds=[("precio", "15")])],
                   [P("cambia", "pedido", producto="m170", color="blanc")], NOMBRE,
                   [P("pago", "plata", medio="transfer")], [P("pregunta", "plata")], SI],
    "7355526504": [[P("pregunta", "catalogo", rubro="mouse", conds=[("retroilumin|luz|luces", "rgb|si|luz|luces|color")])]],
    "badf4f114b": [[P("pregunta", "compatibilidad", producto="k380", equipo="ios|ipad"), P("agrega", "pedido", producto="k380")],
                   [P("pregunta", "catalogo|no_vendemos", conds=[("marca", "samsung")])]],
    "c499622280": [[P("agrega", "pedido", producto="m170", cantidad=1)], [P("cambia", "pedido", color="blanc")],
                   [P("agrega", "pedido", producto="cobra")]],
    "353270d278": [[P("pregunta", "catalogo", rubro="auricular", orden="barat")]],
    "c3391deb1a": [[P("pregunta", "catalogo", rubro="teclado", orden="barat"), P("pregunta", "faq", sobre="cuota"),
                    P("pregunta", "catalogo", rubro="auricular", opt=True)]],
    "b8bb001ee8": [PS5, ECO_NEGRO, VILLA, NOMBRE, [NO_MP]],
    "bf4a05c745": [[P("pregunta", "compatibilidad", producto="m170", equipo="ps|play")],
                   [P("pregunta", "compatibilidad|catalogo", rubro="mouse", equipo="ps|play")]],
    "d29c5ac43a": [[P("pregunta|agrega", "catalogo|pedido", rubro="mouse", orden="livian")]],
    "58b5a11775": [PS5, ECO_NEGRO, VILLA, NOMBRE + [NO_MP]],
    "8e13ecbb7c": [[P("pregunta", "catalogo", producto="k120", sobre="precio")]],
}

# ---------------------------------------------------------------- la llamada
FUENTES = {
    "catalogo": "precio, stock, colores, la ficha de un producto, buscar productos con condiciones, el mas barato o caro",
    "compatibilidad": "si un producto anda con un equipo: PC, Mac, PS5, Xbox, iPad, celular",
    "faq": "las reglas de la tienda: los temas de la lista",
    "envio": "costo y plazo del envio a un lugar",
    "plata": "totales, presupuesto, descuentos sobre el pedido, cuanto queda",
    "cierre": "el nombre del cliente y el link o los datos para pagar",
    "no_vendemos": "algo que la tienda no vende",
    "pedido": "lo que el cliente compra, cambia, saca o confirma",
    "ninguna": "saludo, charla, o una pregunta que ninguna fuente puede contestar",
}

CONSIGNA = """Sos la primera lectura de un bot de ventas de una tienda de tecnologia de Argentina por WhatsApp. No le
contestas al cliente: separas su ULTIMO mensaje en partes para que el sistema conteste cada una con datos reales.

Devolve solo JSON: {{"partes": [ ... ]}}. Cada parte:
  "cita"        las palabras del cliente que la piden, tal cual
  "accion"      pregunta | agrega | cambia | saca | confirma | pago | tope | nombre | charla
  "fuente"      cual la contesta: {fuentes}
  "rubro"       uno de estos, si aplica: {rubros}
  "producto"    el modelo que nombro, o el que senala de lo que el bot ya mostro ("ese", "el mas economico de los que
                mencionaste"), con su nombre como figura en la charla
  "sobre"       lo que quiere saber: un campo de la ficha ({campos}), un tema de la FAQ ({temas}), un equipo ({equipos}),
                "rubros" si pregunta que vende la tienda, o con tus palabras si no esta en ninguna lista
  "condiciones" lista de {{"campo": ..., "valor": ..., "niega": true|false}}: lo que tiene que cumplir el producto
  "orden"       barato | caro | liviano | mejor, si pidio el mas algo
  "cantidad"    numero
  "destino"     el lugar del envio
  "color"       el color dicho
  "medio"       el medio de pago dicho, solo si lo dijo
  "porcentaje"  la parte del total que paga con ese medio
  "monto"       el tope de plata, en pesos

Reglas:
- Una parte por cosa. Si una pregunta toca dos fuentes, dos partes.
- Lo que compra: una parte "agrega" por rubro o producto Y por destino, con la cantidad que va a ese destino.
- El pago: una parte por cada porcentaje. Si no dijo el medio, "medio" va vacio: nunca lo completes vos.
- Una pregunta sobre el pago no es un pago: es "pregunta" a la faq.
- Lo que el cliente no dijo no se pone. Lo que vale para todo el pedido va en cada parte.
- Los campos que no aplican se omiten."""


def _lista(campo):
    return sorted({r[campo] for r in csv.DictReader(open(os.path.join(FUENTE, "productos.csv")))})


def consigna():
    temas = [f["tema"] for f in json.load(open(os.path.join(FUENTE, "faq.json")))]
    campos = [c for c in next(csv.reader(open(os.path.join(FUENTE, "productos.csv"))))
              if c not in ("id", "nombre", "categoria", "descripcion", "tags", "descripcion_rica", "modelo")]
    campos += [c for c in next(csv.reader(open(os.path.join(FUENTE, "specs_por_modelo.csv"))))
               if c not in ("marca", "modelo", "categoria")]
    equipos = set()
    for r in csv.DictReader(open(os.path.join(FUENTE, "compatibilidad.csv"))):
        equipos |= set(filter(None, (r["plataformas"] + "|" + r["no_compatible"]).split("|")))
    return CONSIGNA.format(fuentes="; ".join(f"{k}: {v}" for k, v in FUENTES.items()), rubros=", ".join(_lista("categoria")),
                           campos=", ".join(campos), temas=", ".join(temas), equipos=", ".join(sorted(equipos)))


def _charlas():
    ch = json.load(open(os.path.join(AQUI, "charlas.json")))
    bots = {}
    for f in ("corrida_31oct.jsonl", "corrida_3nov.jsonl"):  # la del 3-nov pisa; b8df72a33c solo esta el 31-oct
        for line in open(os.path.join(AQUI, f)):
            r = json.loads(line)
            bots[r["id"]] = [t["bot"] for t in r["turnos"]]
    return ch, bots


def _mensajes(sistema, mensajes, bots, i):
    msgs = [{"role": "system", "content": sistema}]
    for j in range(max(0, i - 6), i):
        msgs += [{"role": "user", "content": mensajes[j]}, {"role": "assistant", "content": (bots[j] if j < len(bots) else "")[:1500]}]
    msgs.append({"role": "user", "content": "ULTIMO MENSAJE DEL CLIENTE, a separar: " + mensajes[i]})
    return msgs


def correr(etiqueta, ids):
    from openai import OpenAI
    from app.config import get_settings
    s = get_settings()
    cli = OpenAI(api_key=os.environ["GEMINI_API_KEY"], base_url=s.GEMINI_BASE_URL)
    hecho = {(r["etiqueta"], r["id"], r["turno"]) for r in _leer()}
    ch, bots = _charlas()
    sistema = consigna()
    for c in ch:
        if ids and c["id"] not in ids:
            continue
        for i, m in enumerate(c["mensajes"]):
            if (etiqueta, c["id"], i + 1) in hecho:
                continue
            for intento in range(4):
                try:
                    r = cli.chat.completions.create(model=s.GEMINI_MODEL, temperature=0, messages=_mensajes(
                        sistema, c["mensajes"], bots.get(c["id"], []), i), response_format={"type": "json_object"})
                    crudo = r.choices[0].message.content
                    break
                except Exception as e:  # noqa: BLE001
                    if "per day" in str(e).lower() or "PerDay" in str(e):
                        print("se agoto la cuota del dia; se sigue con la misma orden"); return
                    print("reintento", c["id"], i + 1, str(e)[:120]); time.sleep(65)
            else:
                print("sin respuesta", c["id"], i + 1); return
            with open(SALIDA, "a") as f:
                f.write(json.dumps({"etiqueta": etiqueta, "id": c["id"], "turno": i + 1, "crudo": crudo}, ensure_ascii=False) + "\n")
            print(c["id"], i + 1, "ok")
            time.sleep(6)


def _leer():
    return [json.loads(x) for x in open(SALIDA)] if os.path.exists(SALIDA) else []


# ---------------------------------------------------------------- la nota
def _n(x):
    x = unicodedata.normalize("NFKD", str(x or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", x).strip()


def _cumple(espec, valor):
    v = _n(valor)
    return any(t in v for t in _n(espec).split("|")) if v else False


def _condtxt(p):
    out = []
    for c in p.get("condiciones") or []:
        val = _n(c.get("valor"))
        out.append((_n(c.get("campo")), ("no " if c.get("niega") and not val.startswith(("no ", "sin ")) else "") + val))
    return out


def _medio(p):
    m = _n(p.get("medio"))
    return ("no " if p.get("niega") and m and not m.startswith(("no ", "sin ")) else "") + m


def _parte_cumple(o, p, sin_cantidad=False):
    if not _cumple(o["accion"], p.get("accion")):
        return False
    # la fuente se califica en lo que se pregunta; en lo que compra, cambia o paga la accion ya dice adonde va
    if o.get("fuente") and _cumple("pregunta|charla", o["accion"]) and not _cumple(o["fuente"], p.get("fuente")):
        return False
    for k in ("rubro", "producto", "sobre", "orden", "destino", "color"):
        if o.get(k) and not _cumple(o[k], p.get(k)):
            return False
    if o.get("equipo") and not _cumple(o["equipo"], " ".join([_n(p.get("sobre"))] + [" ".join(c) for c in _condtxt(p)])):
        return False
    for campo, valor in o.get("conds", []):
        if not any(_cumple(campo, c) and _cumple(valor, v) for c, v in _condtxt(p)):
            return False
    if "medio" in o:
        if o["medio"] is None and _medio(p):
            return False
        if o["medio"] and not _cumple(o["medio"], _medio(p)):
            return False
    # lo de forma no se cuenta como error: el porcentaje dicho como fraccion, 0.5 es 50; la cantidad 1 callada
    if o.get("porcentaje") is not None and _pct(p.get("porcentaje")) != o["porcentaje"]:
        return False
    if o.get("monto") is not None and _num(p.get("monto")) != o["monto"]:
        return False
    if not sin_cantidad and o.get("cantidad") is not None and (_num(p.get("cantidad")) or 1) != o["cantidad"]:
        return False
    return True


def _pct(x):
    try:
        v = float(re.sub(r"[^\d.]", "", str(x)))
    except ValueError:
        return None
    return round(v * 100) if v <= 1 else round(v)


def _num(x):
    try:
        return int(float(re.sub(r"[^\d.]", "", str(x)) or "nan"))
    except ValueError:
        return None


def notar_turno(oro, partes):
    usadas, faltan = set(), []
    for o in oro:
        if o.get("destinos"):  # lo que compra: se suman las partes del mismo rubro, destino por destino
            grupo = [i for i, p in enumerate(partes) if i not in usadas and _cumple(o["accion"], p.get("accion"))
                     and _cumple(o["rubro"], p.get("rubro"))]
            suma = {}
            for i in grupo:
                d = next((k for k in o["destinos"] if _cumple(k, partes[i].get("destino"))), "?" + _n(partes[i].get("destino")))
                suma[d] = suma.get(d, 0) + (_num(partes[i].get("cantidad")) or 1)
            bien = suma == o["destinos"] and all(_parte_cumple({**o, "destino": None}, partes[i], True) for i in grupo[:1])
            if grupo:
                usadas |= set(grupo)
            if not bien and not o.get("opt"):
                faltan.append((o, suma))
            continue
        i = next((i for i, p in enumerate(partes) if i not in usadas and _parte_cumple(o, p)), None)
        if i is None:
            if not o.get("opt"):
                faltan.append((o, None))
        else:
            usadas.add(i)
    # pedir el precio de lo mismo que compra en ese mensaje no es una parte de mas: no le cambia nada al codigo
    comprados = {_n(p.get("rubro"))[:5] for p in partes if _n(p.get("accion")) == "agrega" and p.get("rubro")}
    demas = [p for i, p in enumerate(partes) if i not in usadas and _n(p.get("accion")) != "charla"
             and not (_n(p.get("accion")) == "pregunta" and p.get("rubro") and _n(p.get("rubro"))[:5] in comprados
                      and _cumple("precio", p.get("sobre") or "precio"))]
    return faltan, demas


def nota(etiqueta, ver):
    filas = {(r["id"], r["turno"]): r for r in _leer() if r["etiqueta"] == etiqueta}
    tot = bien_p = turnos = bien_t = 0
    for cid, turnos_oro in ORO.items():
        for t, oro in enumerate(turnos_oro, 1):
            r = filas.get((cid, t))
            if not r:
                continue
            try:
                partes = json.loads(r["crudo"]).get("partes", [])
            except (ValueError, AttributeError):
                partes = []
            faltan, demas = notar_turno(oro, partes)
            n = sum(1 for o in oro if not o.get("opt"))
            tot += n + len(demas)
            bien_p += n - len(faltan)
            turnos += 1
            bien_t += not faltan and not demas
            if ver and (faltan or demas):
                print(f"## {cid} t{t}")
                for o, suma in faltan:
                    print("   FALTA o MAL:", {k: v for k, v in o.items() if v not in (None, False)}, "| sumo:" if suma else "", suma or "")
                for p in demas:
                    print("   DE MAS:", json.dumps(p, ensure_ascii=False)[:220])
                if ver == 2:
                    print("   MODELO:", json.dumps(partes, ensure_ascii=False)[:900])
    print(f"{etiqueta}: {turnos} turnos corridos de {sum(len(v) for v in ORO.values())}")
    print(f"  partes bien: {bien_p} de {tot}, el {100 * bien_p / max(tot, 1):.0f}%  (las de mas cuentan como mal)")
    print(f"  turnos enteros bien: {bien_t} de {turnos}, el {100 * bien_t / max(turnos, 1):.0f}%")


if __name__ == "__main__":
    et = ARGS[ARGS.index("--etiqueta") + 1] if "--etiqueta" in ARGS else "r1"
    ids = [a for a in ARGS if re.fullmatch(r"[0-9a-f]{10}", a)]
    if "--correr" in ARGS:
        correr(et, ids)
    nota(et, 2 if "--ver2" in ARGS else "--ver" in ARGS)
