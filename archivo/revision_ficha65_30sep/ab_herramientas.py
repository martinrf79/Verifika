"""A/B de la descripcion de las herramientas: temas y datos. Solo la primera llamada. Scratch."""
import copy, json, sys
sys.path.insert(0, "/home/user/Verifika")
from banco_pruebas import clon_produccion
clon_produccion.preparar_entorno(); clon_produccion.instalar()
import logging; logging.disable(logging.CRITICAL)
from app.core import agente as A
from app.core.llm_reintento import _cliente, _modelo
from app.storage.firestore_client import get_all_faq
from concurrent.futures import ThreadPoolExecutor

T = "verifika_prod"
cli, mod = _cliente(), _modelo()
SIS, ESQ0 = A.sistema(T), A.esquema(T)
REPS = 3
faq = get_all_faq(tienda_id=T)
f = A.indice(T)["fichas"]

def temas_linea(frases):
    out = []
    for t, d in faq.items():
        kws = [k for k in (d.get("keywords") or []) if A._n(k) != A._n(t.replace("_", " "))]
        out.append(f"{t} ({', '.join(kws[:frases])})" if frases and kws else t)
    return ", ".join(out)

def datos_linea():
    si_no = sorted(c for c, x in f.items() if x["tipo"] == "si_no")
    listas = sorted(c for c, x in f.items() if x["tipo"] == "lista")
    med = sorted(c for c, x in f.items() if x["tipo"] == "magnitud")
    return ("Los de si o no se piden con valor si o no: " + ", ".join(si_no) + ". Medidas, se comparan y ordenan: "
            + ", ".join(med) + ". Valores cerrados: " + "; ".join(f"{c} ({' | '.join(f[c]['valores'])})" for c in listas)
            + ". El resto es texto.")

def datos_texto():
    """Cada campo con como lo escribe la fuente: los de texto con sus valores frecuentes."""
    partes = []
    for c, x in sorted(f.items()):
        if c in ("nombre", "modelo", "descripcion", "contenido_caja", "garantia_detalle", "dimensiones", "caracteristicas_extra"):
            continue
        if x["tipo"] == "si_no":
            partes.append(f"{c}: si o no")
        elif x["valores"]:
            partes.append(f"{c}: {' | '.join(x['valores'][:4])}")
        else:
            partes.append(c)
    return "Como escribe la fuente cada dato. " + "; ".join(partes)


def esquema(var):
    e = copy.deepcopy(ESQ0)
    by = {x["function"]["name"]: x["function"] for x in e}
    if var in ("T1", "T2", "T3"):
        pol = by["politica"]
        pol["parameters"]["properties"]["tema"] = {"type": "string", "description":
            "el tema de la casa que contesta la pregunta: " + temas_linea({"T1": 0, "T2": 1, "T3": 3}[var])}
    if var in ("D1", "D2"):
        c = by["buscar"]["parameters"]["properties"]["condiciones"]["items"]["properties"]["campo"]
        c["description"] = datos_linea() if var == "D1" else datos_texto()
    return e

FAQ = {  # mensaje: temas aceptables
 "si me llega roto que hago": {"defectuoso"},
 "me vino fallado el mouse, que hago": {"defectuoso"},
 "llego y no prende": {"defectuoso"},
 "quiero devolverlo porque no me gusto": {"devoluciones", "cambios", "reembolso"},
 "lo puedo cambiar por otro color?": {"cambios"},
 "me devuelven la plata si lo devuelvo?": {"reembolso", "devoluciones"},
 "cuanto dura la garantia?": {"garantia"},
 "como hago valer la garantia?": {"garantia_como_usar"},
 "tienen algun descuento o promo ahora?": {"promociones", "descuento_transferencia"},
 "puedo pagar con cripto?": {"monedas_aceptadas", "formas_pago"},
 "si compro hoy cuando me llega?": {"plazo_envio"},
 "lo necesito para manana, se puede?": {"envio_urgente"},
 "mandan a Chile?": {"envio_exterior"},
 "me mude, puedo cambiar la direccion del pedido?": {"cambio_direccion"},
 "es seguro comprarles, no son truchos?": {"confianza_seguridad", "marcas_originales"},
 "donde veo como va mi pedido?": {"seguimiento_pedido"},
 "puedo pasar a buscarlo?": {"retiro_local", "ubicacion"},
 "me pueden pasar con una persona?": {"contacto_humano"},
}
DATOS = {  # mensaje: (campo aceptable, condicion extra)
 "busco un parlante que se pueda mojar": {"resistencia_agua"},
 "parlante para la pileta": {"resistencia_agua"},
 "auris que aguanten la lluvia": {"resistencia_agua"},
 "notebook con pantalla tactil": {"tactil"},
 "teclado que se ilumine": {"retroiluminacion"},
 "notebook que se le pueda agregar memoria": {"ram_ampliable"},
 "notebook que lea tarjetas SD": {"lector_tarjetas"},
 "monitor con panel IPS": {"panel"},
 "auriculares sin cable": {"bluetooth", "conexion"},
 "una tablet, lo menos china posible": {"pais_marca", "pais_fabricacion", "origen"},
 "mouse que no sea negro": {"color"},
}

def primera(var, msg):
    r = cli.chat.completions.create(model=mod, messages=[{"role": "system", "content": SIS}, {"role": "user", "content": msg}],
                                    temperature=0.2, tools=esquema(var), tool_choice="auto")
    m = r.choices[0].message
    return [(c.function.name, json.loads(c.function.arguments or "{}")) for c in (m.tool_calls or [])], (m.content or "")

def nota_faq(var, msg, calls):
    ok = FAQ[msg]
    pol = [a for n, a in calls if n == "politica"]
    if not pol:
        return False, "sin politica"
    elegido = [a.get("tema") for a in pol if a.get("tema")]
    servidos = []
    for a in pol:
        t = a.get("tema")
        servidos += ([t] if t in A.indice(T)["temas"] else []) + A.temas_de(a.get("pregunta") or "", T)[:3]
    return bool(ok & set(servidos[:4])), f"eligio={elegido} sirve={servidos[:4]}"

def nota_datos(msg, calls):
    ok = DATOS[msg]
    campos = [c.get("campo") for n, a in calls if n == "buscar" for c in (a.get("condiciones") or [])]
    return bool(ok & set(campos)), f"campos={campos}"

trabajos = [(v, m) for v in ("T0",) for m in FAQ for _ in range(REPS)] + \
           [(v, m) for v in ("D2",) for m in DATOS for _ in range(REPS)]

def una(vm):
    v, m = vm
    try:
        calls, texto = primera(v, m)
    except Exception as e:
        return v, m, False, f"ERR {str(e)[:80]}"
    ok, det = (nota_faq(v, m, calls) if v.startswith("T") else nota_datos(m, calls))
    return v, m, ok, det

with ThreadPoolExecutor(10) as ex:
    res = list(ex.map(una, trabajos))
json.dump(res, open("/tmp/claude-0/-home-user-Verifika/9485093e-efa9-58bd-a799-27a093938332/scratchpad/ab_herr.json", "w"), ensure_ascii=False)
from collections import defaultdict
tot = defaultdict(lambda: [0, 0]); falla = defaultdict(list)
for v, m, ok, det in res:
    tot[v][0] += ok; tot[v][1] += 1
    if not ok:
        falla[v].append(f"{m[:38]} -> {det[:120]}")
for v in sorted(tot):
    print(v, f"{tot[v][0]}/{tot[v][1]}")
    for x in sorted(set(falla[v])):
        print("     ", x)
