"""EL TABLERO — el turno en tres pasos, calibrado en el laboratorio (30-sep-2026).

ES EL TURNO VIVO DESDE EL 30-SEP: `respuesta.procesar_turno` lo llama en vez
de `agente.turno`. Las herramientas y la completitud siguen en `agente`. Se
mide por el clon con `sonda_charlas --vara todas`.

MISMA ENTRADA Y MISMA SALIDA QUE `agente.turno`: el historial, el mensaje, la
tienda y la memoria que arma `respuesta`; vuelve el texto, las llamadas con lo
que devolvio cada herramienta y el uso. Por eso lo de alrededor —la guarda de
plata, la memoria, el cierre— es el de produccion sin tocar, y mudar es
cambiar una funcion por otra.

LOS TRES PASOS, y por que cada uno es como es (FICHA 65, laboratorio):

  1. INTERPRETAR. Dos llamadas en paralelo. Una parte el mensaje en piezas
     con el tablero: las acciones con una linea, cuatro reglas de partir que
     sugirio el propio modelo, y el vocabulario de la tienda como listas
     cerradas del esquema de salida. La otra contesta cinco preguntas de si o
     no. Temperatura cero y salida forzada: el JSON es siempre valido y los
     nombres siempre existen.
  2. EL CODIGO. Corre las mismas herramientas del agente, en orden de
     dependencia. Si lo que marcaron las preguntas de si o no, o lo que lee
     `agente.faltantes` en el mensaje, no esta en las piezas, se le pide UNA
     correccion al interprete. Si falta un dato del cliente o la referencia es
     ambigua, se repregunta. El modelo detecta esas cosas siempre; armar la
     estructura no, y por eso la arma el codigo.
  3. REDACTAR. El redactor no ve el catalogo ni las herramientas: ve solo lo
     que devolvio el codigo. Lo que no esta ahi no figura. Es la primera
     capa contra la alucinacion; la segunda es la guarda de plata de
     `respuesta`, que es la de siempre.
"""
import asyncio
import json
import re
import time

from app.core import agente as A
from app.core.agente import CLIENTE_DIJO, _TRACE, ejecutar, faltantes
from app.logger import get_logger

log = get_logger(__name__)

# Lo medido: temperatura cero para interpretar, un poco de soltura para redactar.
TEMP_INTERPRETAR = 0.0
TEMP_REDACTAR = 0.2

ACCIONES = {
    "producto": "un producto nombrado: precio, stock o un dato suyo",
    "buscar": "un rubro con condiciones u orden",
    "envio": "costo o plazo de envio a un destino",
    "politica": "una regla de la tienda",
    "compatibilidad": "si un producto anda con un equipo u otro producto",
    "cuenta": "el total de varios productos, cantidades, destino o reparto de pago",
    "comprar": "el cliente decide llevarse algo",
    "explicar": "saber general, no de la tienda",
    "verificar": "el cliente da algo por cierto de la tienda o de un producto",
    "repreguntar": "falta un dato del cliente o no se sabe a que se refiere",
    "charla": "saludo, gracias o algo que no es un pedido",
}

INTERPRETE = """Sos el interprete de una tienda online de tecnologia de Argentina. No le contestas al cliente: partis su ultimo mensaje en piezas para que el codigo las resuelva.
tipo es uno de estos: {acciones}.
REGLAS DE PARTIR:
1. Una pieza por cada producto o rubro, con la cantidad que pidio el cliente, aunque compartan condiciones: la condicion se repite en cada una.
2. Si el cliente hace algo segun un resultado —"si X, Y", "dame el que cumpla X"—, X es una pieza propia y Y otra con depende_de apuntando a X. Excepcion: una regla sobre el total de una cuenta va en las condiciones de esa cuenta.
3. En cuenta, inclui en items lo ya elegido en la charla y el destino si lo pide.
4. Si para contestar falta un dato del cliente, pone el tipo de lo que pide y el dato en "falta".
5. "Ese", "el otro", "el segundo" y lo que el cliente dijo antes estan en la charla y en la memoria: resolvelos con el nombre del producto. Una condicion que el cliente puso antes sigue valiendo hasta que la cambie, y el alcance de una busqueda sale de lo que busco el cliente, no de lo que mostro el bot.
6. producto es el nombre del producto como lo nombro el cliente o la charla, con el color o la variante si los dijo. Nunca inventes precios ni stock.
7. Si pide algo que la tienda no vende, el rubro es "{no_lo_vende}"."""

BANDERAS = {
    "condicional": "el mensaje pone una condicion: si pasa una cosa, hacer otra, o elegir segun un dato",
    "falta_dato_cliente": "para contestar falta un dato del cliente que no dio: su equipo, su modelo",
    "referencia_ambigua": "dice 'ese', 'el otro' y en la charla hay mas de un producto al que puede referirse",
    "afirma_algo": "el cliente da algo por cierto de la tienda o de un producto, aunque sea dentro de otra pregunta",
    "pide_total": "pide el total de una compra: varios productos, cantidades o envio sumados",
    "confirma_resumen": "el bot le resumio un pedido y le pregunto si esta bien, y el cliente lo acepta o le "
                        "corrige un detalle",
}

PREGUNTAS = ("Sos el interprete de una tienda online de tecnologia de Argentina. No le contestas al cliente. "
             "Del ULTIMO mensaje del cliente, contesta si o no a cada pregunta:\n"
             + "\n".join(f"{k}: {v}" for k, v in BANDERAS.items()))

# LAS GUIAS: procedimientos que el codigo suma a la correccion SOLO cuando la
# pregunta de si o no los detecto. Medido el 30-sep: los doce dificiles pasan
# de 24 a 33 de 36 sin tocar los de control, y el mensaje simple no los paga.
GUIAS = {
    "condicional": "GUIA · CONDICIONES. 1. Separa la condicion —lo que hay que averiguar— de la accion —lo que se hace "
                   "segun el resultado—. 2. La condicion es una pieza del tipo que la averigua: producto para stock, "
                   "color o precio; compatibilidad; verificar. 3. La accion es otra pieza —comprar, buscar, producto— "
                   "con depende_de apuntando a la condicion. 4. \"Dame el que cumpla X\" entre varios: una pieza que "
                   "averigua X de cada uno y una comprar que depende de ella. 5. Una condicion sobre el total de una "
                   "cuenta (\"si pasa de\") va en las condiciones de esa cuenta.",
    "pide_total": "GUIA · CUENTA. Una pieza cuenta con TODOS los productos elegidos, de este mensaje y de la charla, "
                  "cada uno con su cantidad y color. El destino si lo nombro ahora o antes. Si ademas pide mandarlo, "
                  "tambien una pieza envio.",
    "referencia_ambigua": "GUIA · REFERENCIAS. 1. Lista los productos que nombro el bot en su ultimo mensaje, en orden. "
                          "2. \"El primero\", \"el segundo\" es por posicion; \"el otro\" es el que NO eligio o "
                          "descarto; \"ese\" es el ultimo nombrado. 3. Si hay mas de uno posible y nada decide cual, "
                          "tipo repreguntar.",
    "afirma_algo": "GUIA · AFIRMACIONES. Ademas de lo que pregunta, una pieza verificar con lo que el cliente da por "
                   "cierto: si es de un producto, con el nombre del producto; si es de la tienda, con el tema.",
    "falta_dato_cliente": "GUIA · DATO QUE FALTA. Pone el tipo de lo que pide —compatibilidad, buscar— y en \"falta\" "
                          "el dato del cliente que hace falta. No inventes su equipo.",
}

REDACTOR = """Sos el vendedor de {negocio}, una tienda online de tecnologia de Argentina. Hablas en espanol argentino, con voseo, corto y claro, sin repetir.
Te paso el ultimo mensaje del cliente y los HECHOS que consulto el sistema para cada parte.
1. Contesta TODAS las partes del mensaje, en orden.
2. Cada dato de la tienda —producto, precio, stock, envio, politica, compatibilidad— sale SOLO de los HECHOS. Lo que no esta en los HECHOS no lo sabes, aunque lo conozcas de antes: deci que no figura. Nunca escribas un monto que no este en los HECHOS o en la charla, y no sumes ni calcules vos: si falta un total, no lo des.
3. Si un hecho dice ambiguo, falta_elegir o pregunta_al_cliente, hace UNA pregunta corta y contesta igual las demas partes. Si no existe, decilo y ofrece lo que si hay en los HECHOS. Las filas que trae un resultado son las que hay; una nota_interna no es un dato del producto y no se la digas al cliente. Si un resultado dice no_se_pudo_filtrar_por, ese dato no figura en la ficha: decilo asi y mostra lo que hay; nunca digas que no hay productos con ese dato.
9. No escribas codigos internos de producto: nombralos por su nombre.
4. Si una parte dependia de otra, decidi con lo que dicen los HECHOS y explicalo en una linea.
5. Si el cliente da algo por cierto y los HECHOS dicen otra cosa, corregilo con amabilidad.
6. Si hay una cuenta, copia su detalle tal cual, renglon por renglon: cada producto, el envio, cada parte del reparto y el total. Si hay un total_general, va al final y una sola vez, con su reparto.
11. Si hay un hecho confirmar_pedido, NO des precios ni totales: deci en pocas lineas que entendiste que va a cada destino, lo que no cierra con sus palabras, y pregunta una vez si esta bien para pasarle los presupuestos. Contesta igual las otras partes del mensaje.
10. Si hay un hecho de articulos, decilo en una linea antes de los presupuestos, con sus palabras: lo que no estaba en la lista y que se tomo en su lugar, lo que el cliente nombro fuera de la lista, o que articulo quedo sin destino; y pregunta una vez si esta bien. No le agregues motivos ni nombres al sistema.
7. El saber general de tecnologia lo explicas vos.
8. Pedile el nombre SOLO si el cliente dijo que compra. Nunca pidas DNI, tarjeta ni CBU. No cierres cada mensaje ofreciendo comprar."""


# ══ EL ESQUEMA DE SALIDA: el vocabulario de la tienda como listas cerradas ═

# EL RUBRO QUE LA TIENDA NO VENDE TAMBIEN ES UNA RESPUESTA (1-oct, K12). Con la
# lista cerrada el interprete tenia que elegir un rubro de la tienda, y
# "celulares" salia como notebook: el cliente leia notebooks Samsung que no
# pidio. `not_found` es un resultado valido, regla 10.0.
NO_LO_VENDE = "no lo vende la tienda"

def _vocabulario(tienda_id: str) -> tuple:
    from app.core.filtros_catalogo import campos_filtrables
    idx = A.indice(tienda_id)
    return sorted(idx["rubros"]), sorted(idx["temas"]), sorted(campos_filtrables(tienda_id))


def esquema_piezas(tienda_id: str) -> dict:
    rubros, temas, campos = _vocabulario(tienda_id)
    S, N = {"type": "string"}, {"type": "number"}
    pieza = {"type": "object", "properties": {
        "n": {"type": "integer"},
        "tipo": {"type": "string", "enum": list(ACCIONES)},
        "texto": S,
        "producto": S,
        "rubro": {"type": "string", "enum": rubros + [NO_LO_VENDE]},
        "cantidad": {"type": "integer", "description": "cuantos pidio el cliente de este producto o rubro"},
        "condiciones": {"type": "array", "items": {"type": "object", "properties": {
            "campo": {"type": "string", "enum": campos},
            "operador": {"type": "string", "enum": list(OPERADORES)},
            "valor": S}, "required": ["campo", "operador", "valor"]}},
        "orden": {"type": "object", "description": "si pide el mas barato, caro, liviano o grande: el campo y min o max",
                  "properties": {"campo": {"type": "string", "enum": campos},
                                 "direccion": {"type": "string", "enum": ["min", "max"]}}},
        "tema": {"type": "string", "enum": temas},
        "con": S,
        "destinos": {"type": "array", "items": S},
        "items": {"type": "array", "items": {"type": "object", "properties": {
            "producto": S, "cantidad": {"type": "integer"},
            "destino": {"type": "string", "description": "a donde va este item, si el cliente reparte por destino"}},
            "required": ["producto", "cantidad"]}},
        "reparto_pago": {"type": "array", "items": {"type": "object", "properties": {
            "medio": S, "porcentaje": {"type": "number", "description": "de 0 a 100"}},
            "required": ["medio", "porcentaje"]}},
        "depende_de": {"type": "array", "items": {"type": "integer"}},
        "falta": S,
    }, "required": ["n", "tipo", "texto"]}
    return {"type": "object", "properties": {"piezas": {"type": "array", "items": pieza}}, "required": ["piezas"]}


def _esquema_banderas() -> dict:
    return {"type": "object", "properties": {k: {"type": "boolean"} for k in BANDERAS},
            "required": list(BANDERAS)}


def _formato(nombre: str, esquema: dict) -> dict:
    from app.config import get_settings
    if get_settings().LLM_PROVIDER == "deepseek":  # sin esquema estricto: JSON a secas
        return {"type": "json_object"}
    return {"type": "json_schema", "json_schema": {"name": nombre, "schema": esquema}}


def _con_esquema(sistema: str, formato: dict, esquema: dict) -> str:
    """Sin esquema estricto el modelo no ve las listas cerradas: van en el prompt."""
    if formato.get("type") == "json_schema":
        return sistema
    return sistema + "\nDevolve SOLO un JSON con este esquema, y en los campos con enum SOLO esos valores:\n" \
        + json.dumps(esquema, ensure_ascii=False)


# ══ LA ATADURA: el vocabulario de la tienda lo garantiza el codigo ══════════
# (2-oct) Hasta hoy la lista cerrada la garantizaba el esquema estricto del
# proveedor, y un modelo que da JSON a secas —DeepSeek directo— podia nombrar un
# rubro, un campo o un tema que la tienda no tiene, o contestar "no" como texto
# a una pregunta de si o no, que en Python es verdadero. Ahora cada pieza pasa
# por aca con cualquier modelo: lo que no existe se lleva al valor mas cercano
# o se descarta, y lo descartado se le devuelve UNA vez al modelo con el error.

OPERADORES = ("contiene", "no_contiene", "igual", "mayor", "menor", "prefiere", "evita")
_SI = ("true", "si", "sí", "yes", "1")


def _cercano(valor, opciones) -> str:
    """El valor de la lista que el modelo quiso nombrar, o vacio. Primero igual
    sin tildes ni mayusculas; despues un unico prefijo —"precio" es
    "precio_ars"—; despues por parecido de letras."""
    import difflib
    v = A._n(valor).strip().replace(" ", "_")
    if not v:
        return ""
    norm = {A._n(o).replace(" ", "_"): o for o in opciones}
    if v in norm:
        return norm[v]
    pref = [o for k, o in norm.items() if k.startswith(v + "_") or v.startswith(k + "_")]
    if len(pref) == 1:
        return pref[0]
    m = difflib.get_close_matches(v, list(norm), n=1, cutoff=0.8)
    return norm[m[0]] if m else ""


def _entero(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    m = re.fullmatch(r"\s*(\d+)\s*", str(v or ""))
    return int(m.group(1)) if m else None


def _numero(v):
    """El numero tal cual vino; "70%" es 70, y entero si es entero."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    try:
        f = float(str(v).replace("%", "").replace(",", ".").strip())
    except ValueError:
        return None
    return int(f) if f.is_integer() else f


def piezas_de(texto: str) -> list:
    """Las piezas del JSON del interprete: bajo "piezas", o la lista sola."""
    try:
        crudo = json.loads(texto)
    except ValueError:
        crudo = _json(texto)
    if isinstance(crudo, dict):
        crudo = crudo.get("piezas") if "piezas" in crudo else ([crudo] if crudo.get("tipo") else [])
    return [p for p in crudo or [] if isinstance(p, dict)] if isinstance(crudo, list) else []


def banderas_de(texto: str) -> dict:
    """Las preguntas de si o no como booleanos: "no" en texto es falso."""
    crudo = _json(texto)
    return {k: (crudo.get(k) is True or str(crudo.get(k)).strip().lower() in _SI) for k in BANDERAS}


def atar(piezas: list, tienda_id: str) -> tuple:
    """(piezas atadas, errores, corregidos). Cada valor de lista cerrada que no
    existe se lleva al mas cercano —corregido— o se descarta —error—."""
    rubros, temas, campos = _vocabulario(tienda_id)
    errores, corregidos, out = [], [], []

    def cerrado(clave, valor, opciones, donde):
        if valor in opciones:
            return valor
        c = _cercano(valor, opciones) or (clave == "rubro" and _es_rubro(str(valor), tienda_id)) or ""
        if c:
            corregidos.append(f"{donde} {clave} {valor!r} -> {c!r}")
        else:
            errores.append(f"{donde}: {clave} {valor!r} no existe en la tienda; vale uno de: " + ", ".join(opciones))
        return c

    for i, p in enumerate(piezas):
        if not isinstance(p, dict):
            continue
        n = _entero(p.get("n"))
        p = {**p, "n": n if n is not None else i + 1}
        donde = f"pieza {p['n']}"
        tipo = cerrado("tipo", p.get("tipo"), list(ACCIONES), donde) if p.get("tipo") else ""
        if not tipo:
            if not p.get("tipo"):
                errores.append(f"{donde}: le falta el tipo")
            continue
        p["tipo"] = tipo
        p["texto"] = str(p.get("texto") or "")
        for k in ("producto", "con", "falta"):
            if k in p:
                p[k] = str(p[k] or "")
        if p.get("rubro"):
            r = cerrado("rubro", p["rubro"], rubros + [NO_LO_VENDE], donde)
            if r:
                p["rubro"] = r
            else:
                # Sin rubro la busqueda va por el texto: no se pierde lo pedido.
                p["producto"] = p.get("producto") or str(p.pop("rubro"))
                p.pop("rubro", None)
        else:
            p.pop("rubro", None)
        if p.get("tema"):
            t = cerrado("tema", p["tema"], temas, donde)
            p["tema"] = t
            if not t:
                p.pop("tema")
        else:
            p.pop("tema", None)
        for k in ("cantidad",):
            if k in p:
                v = _entero(p[k])
                if v is None:
                    p.pop(k)
                else:
                    p[k] = v
        conds = []
        for c in p.get("condiciones") or [] if isinstance(p.get("condiciones"), list) else []:
            if not isinstance(c, dict) or c.get("valor") in (None, ""):
                continue
            campo = cerrado("campo", c.get("campo"), campos, donde) if c.get("campo") else ""
            op = cerrado("operador", c.get("operador"), list(OPERADORES), donde) if c.get("operador") else ""
            if not c.get("campo") or not c.get("operador"):
                errores.append(f"{donde}: una condicion sin campo u operador")
            if campo and op:
                conds.append({"campo": campo, "operador": op, "valor": str(c["valor"])})
        if conds or "condiciones" in p:
            p["condiciones"] = conds
        o = p.get("orden")
        if isinstance(o, dict) and o.get("campo"):
            campo = cerrado("campo", o["campo"], campos, donde)
            dire = cerrado("direccion", o.get("direccion") or "min", ["min", "max"], donde)
            if campo and dire:
                p["orden"] = {"campo": campo, "direccion": dire}
            else:
                p.pop("orden")
        else:
            p.pop("orden", None)
        if "destinos" in p:
            ds = p["destinos"] if isinstance(p["destinos"], list) else [p["destinos"]]
            p["destinos"] = [str(d) for d in ds if str(d or "").strip()]
        if "items" in p:
            items = []
            for it in p["items"] if isinstance(p["items"], list) else []:
                if isinstance(it, dict) and str(it.get("producto") or "").strip():
                    it = {**it, "producto": str(it["producto"]), "cantidad": _entero(it.get("cantidad")) or 1}
                    if "destino" in it:
                        it["destino"] = str(it["destino"] or "")
                    items.append(it)
            p["items"] = items
        if "reparto_pago" in p:
            rep = []
            for r in p["reparto_pago"] if isinstance(p["reparto_pago"], list) else []:
                pct = _numero(r.get("porcentaje")) if isinstance(r, dict) else None
                if pct is not None and str(r.get("medio") or "").strip():
                    rep.append({"medio": str(r["medio"]), "porcentaje": pct})
            p["reparto_pago"] = rep
        if "depende_de" in p:
            ds = p["depende_de"] if isinstance(p["depende_de"], list) else [p["depende_de"]]
            p["depende_de"] = [d for d in (_entero(x) for x in ds) if d is not None]
        out.append(p)
    return out, errores, corregidos


def _pedido_de_atadura(errores: list) -> str:
    return ("ATADURA DEL SISTEMA, no es del cliente. Estas piezas traen valores que la tienda no tiene: "
            + "; ".join(errores) + ". Devolve TODAS las piezas de nuevo, con los valores de la lista.")


# ══ LAS LLAMADAS ════════════════════════════════════════════════════════════

async def _pedir(cli, msgs: list, temp: float, formato: dict | None, trace_id: str, uso: list, paso: str) -> str:
    from app.config import get_settings
    from app.core.llm_reintento import _modelo, llamar_con_reintento
    kw = {"response_format": formato} if formato else {}

    def _call():
        return cli.chat.completions.create(model=_modelo(), messages=msgs, temperature=temp, **kw)
    r = await llamar_con_reintento(_call, timeout_s=float(get_settings().LLM_TIMEOUT_SECONDS), trace_id=trace_id)
    u = r.usage
    det = getattr(u, "prompt_tokens_details", None) if u else None
    uso.append({"paso": paso, "entrada": u.prompt_tokens if u else 0, "salida": u.completion_tokens if u else 0,
                "cache": (getattr(det, "cached_tokens", 0) or 0) if det else 0})
    return r.choices[0].message.content or ""


def _json(texto: str) -> dict:
    try:
        return json.loads(texto)
    except ValueError:
        a, b = texto.find("{"), texto.rfind("}")
        try:
            return json.loads(texto[a:b + 1]) if a >= 0 else {}
        except ValueError:
            return {}


def _charla(historial: list, memoria: str, mensaje: str) -> list:
    msgs = []
    if memoria.strip():
        msgs.append({"role": "system", "content": "MEMORIA DE LA CHARLA:\n" + memoria.strip()})
    return msgs + list(historial or []) + [{"role": "user", "content": mensaje}]


# ══ EL CODIGO: de la pieza a la herramienta ═════════════════════════════════

def _nombre(pz: dict) -> str:
    color = next((c.get("valor") for c in pz.get("condiciones") or [] if c.get("campo") == "color"
                  and c.get("operador") in ("contiene", "igual")), "")
    base = pz.get("producto") or pz.get("texto") or ""
    if color and A._n(color) in A._n(base):
        color = ""
    return " ".join(x for x in (base, color or "") if x).strip()


def a_herramienta(pz: dict) -> tuple:
    """(herramienta, args) para una pieza, o (None, None) si no consulta nada."""
    t = pz.get("tipo")
    if t == "producto" or (t == "verificar" and pz.get("producto")):
        # "Sumame 3 de esos": con la cantidad, el motor trae el subtotal hecho
        # por la calculadora (2-oct, guion 52).
        cant = pz.get("cantidad") if isinstance(pz.get("cantidad"), int) and pz["cantidad"] > 1 else None
        return "producto", {"nombre": _nombre(pz), **({"cantidad": cant} if cant else {})}
    if t == "buscar" and pz.get("rubro") == NO_LO_VENDE:
        return None, None
    if t == "buscar":
        return "buscar", {"que": pz.get("producto") or "", "rubro": pz.get("rubro") or "",
                          "condiciones": pz.get("condiciones") or [], "orden": pz.get("orden") or None}
    if t == "envio":
        return "envio", {"destinos": pz.get("destinos") or []}
    if t in ("politica", "verificar") or (t in ("repreguntar", "explicar") and pz.get("tema")):
        # Una repregunta o una explicacion con un tema de la tienda —"como
        # pago" leido como falta el medio— tambien lleva lo que dice la tienda
        # (2-oct, guion 32).
        # El tema que eligio el modelo va adelante de la pregunta: `politica`
        # suma los del indice. Si no coinciden, se sirven los dos —la red—.
        return "politica", {"pregunta": f"{(pz.get('tema') or '').replace('_', ' ')} {pz.get('texto') or ''}".strip()}
    if t == "compatibilidad":
        return "compatibilidad", {"producto": pz.get("producto") or "", "con": pz.get("con") or ""}
    if t == "cuenta":
        items = pz.get("items") or ([{"producto": pz["producto"], "cantidad": pz.get("cantidad") or 1}]
                                    if pz.get("producto") else [])
        return "cuenta", {"items": items, "destino": (pz.get("destinos") or [""])[0],
                          "reparto_pago": pz.get("reparto_pago") or None}
    if t == "comprar" and (pz.get("producto") or pz.get("items")):
        prod = pz.get("producto") or pz["items"][0].get("producto")
        return "reservar", {"producto": _nombre({**pz, "producto": prod}), "cantidad": pz.get("cantidad") or 1}
    return None, None


def _orden(piezas: list) -> list:
    """Las piezas de las que otras dependen, primero."""
    hechas, out = set(), []
    pend = list(piezas)
    for _ in range(len(pend) + 1):
        for pz in list(pend):
            if all(d in hechas or d not in {p.get("n") for p in piezas} for d in pz.get("depende_de") or []):
                out.append(pz)
                hechas.add(pz.get("n"))
                pend.remove(pz)
    return out + pend


_ID = re.compile(r"\b([A-Z]{3}\d{4})\b")
_NO_ES_DATO = ("no_aplicado", "valores_en_el_rubro", "cuantos_habia", "rubros_posibles")
_ID_ENTRE_PARENTESIS = re.compile(r"\s*\((?:ID:?\s*)?[A-Z]{3}\d{4}\)")
_NOTAS = ("aviso", "nota")
_GENERICAS = {"mouse", "teclado", "auriculares", "auricular", "monitor", "notebook", "webcam", "parlante", "silla",
              "el", "la", "de", "los", "las", "un", "una", "en", "con"}


def _certificado(nombre: str, tienda_id: str, llamadas: list) -> str:
    """El id del producto si la identidad es UNA —regla 10.0—; si no, el nombre
    tal cual, y la cuenta devuelve la ambiguedad para preguntar."""
    if not nombre or _ID.fullmatch(nombre.strip()):
        return nombre
    r = ejecutar("producto", {"nombre": nombre}, tienda_id)
    # UNA FILA CERTIFICA SOLO SI NOMBRA TODO LO QUE SE PIDIO: el 30-sep "MX
    # Master 3S negro" volvia con un gabinete primero. Se mira cada fila y sus
    # colores; si queda una sola, ese es el id. Si no, va el nombre y la
    # cuenta devuelve la ambiguedad para preguntar.
    pedido = [w for w in re.findall(r"[a-z0-9]+", A._n(nombre)) if len(w) > 1 and w not in _GENERICAS]
    from app.storage.firestore_client import get_product_by_id
    hits = []
    for f in r.get("filas") or []:
        for pid in [f.get("id")] + [x.get("id") for x in f.get("variantes") or []]:
            nom = A._n((get_product_by_id(str(pid), tienda_id=tienda_id) or {}).get("nombre") or "") if pid else ""
            if nom and pedido and all(w in nom for w in pedido):
                hits.append(str(pid))
    hits = list(dict.fromkeys(hits))
    # EL NOMBRE EXACTO DE UNA FICHA ES ESA FICHA (2-oct, guion 30): el
    # interprete copia el nombre del catalogo, "Auriculares Logitech G Pro X
    # Negro", y el mouse "G Pro X Superlight Negro" tambien nombra todo eso.
    exacto = [pid for pid in hits if A._n((get_product_by_id(pid, tienda_id=tienda_id) or {}).get("nombre")
                                          or "").strip() == A._n(nombre).strip()]
    if len(exacto) == 1:
        return exacto[0]
    return hits[0] if len(hits) == 1 else nombre


def _lugar_en(texto: str) -> str:
    """Una localidad o provincia nombrada en texto libre: "soy de Mendoza"."""
    from app.core.geo_cp import es_lugar_conocido
    palabras = re.findall(r"[^\W\d_]+", texto or "")
    for largo in (3, 2, 1):
        for i in range(len(palabras) - largo + 1):
            span = " ".join(palabras[i:i + largo])
            if len(span) > 3 and span.lower() not in A._NO_ES_LUGAR and es_lugar_conocido(span):
                return span
    return ""


def _destino(pz: dict, piezas: list, mensaje: str, historial: list, memoria: str) -> str:
    """El destino de la pieza; si no lo trae, el que el cliente dijo en este
    mensaje o antes. Lo que el cliente dijo sigue valiendo: objetivo 3."""
    for d in (pz.get("destinos") or []) + [d for p in piezas if p.get("tipo") == "envio"
                                           for d in p.get("destinos") or []]:
        if str(d).strip():
            return str(d)
    for texto in [mensaje] + [m.get("content") or "" for m in reversed(historial or []) if m.get("role") == "user"]:
        ds = A._destinos_del_mensaje(texto)
        if ds:
            return ds[0]
        lugar = _lugar_en(texto)
        if lugar:
            return lugar
    m = re.search(r"Envia a: (.+)", memoria or "")
    return m.group(1).strip() if m else ""


def _es_rubro(nombre: str, tienda_id: str) -> str:
    """El rubro si el "producto" que escribio el interprete es un rubro y nada
    mas: "auriculares", "memorias". Un rubro no es un producto, es una busqueda."""
    n = A._n(nombre).strip()
    if not n:
        return ""
    for r in _vocabulario(tienda_id)[0]:
        rn = A._n(r)
        # "auricular" es "auriculares": el singular del rubro plural (1-oct, K20).
        singular = rn[:-2] if rn.endswith("es") else rn[:-1] if rn.endswith("s") else rn
        if n in (rn, rn + "s", rn + "es", singular) or rn in (n, n[:-1], n[:-2]) \
                or (" " in rn and n.split()[0] in (rn.split()[0], rn.split()[0] + "s", rn.split()[0] + "es")
                    and len(n.split()) == 1):
            return r
    return ""


def _normalizar(piezas: list, tienda_id: str) -> list:
    """Lo que el interprete parte bien y nombra mal, ordenado antes de correr.
    Medido el 1-oct con `laboratorio referencia`:
    - un rubro escrito como producto —"dos auriculares"— se busca;
    - una condicion o un orden sueltos, sin rubro ni producto —"lo menos
      chino posible", "los mas baratos"—, valen para todas las busquedas del
      mensaje: combinacion 24;
    - el reparto del pago pegado a otra pieza va a la cuenta;
    - la cuenta y la compra corren al final, despues de lo que buscan."""
    piezas = [dict(p) for p in piezas]
    for p in piezas:
        if p.get("tipo") == "producto" and not _ID.fullmatch(str(p.get("producto") or "")):
            r = _es_rubro(p.get("producto") or "", tienda_id)
            if r:
                p.update({"tipo": "buscar", "rubro": r, "producto": ""})
    # EL ORDEN QUE COMPARTE EL MENSAJE VALE PARA TODAS SUS BUSQUEDAS, como la
    # condicion de la regla 1: "dos mouse, dos teclados y dos auriculares, los
    # mas baratos" salia con el orden en dos de las tres (1-oct, K07). Solo si
    # dos o mas lo traen y ninguna trae otro.
    con_orden = [json.dumps(p["orden"], sort_keys=True) for p in piezas if p.get("tipo") == "buscar"
                 and (p.get("rubro") or p.get("producto")) and (p.get("orden") or {}).get("campo")]
    if len(con_orden) > 1 and len(set(con_orden)) == 1:
        for p in piezas:
            if p.get("tipo") == "buscar" and p.get("rubro") and not (p.get("orden") or {}).get("campo"):
                p["orden"] = json.loads(con_orden[0])
    busquedas = [p for p in piezas if p.get("tipo") == "buscar" and (p.get("rubro") or p.get("producto"))]
    sueltas = [p for p in piezas if p.get("tipo") == "buscar" and not p.get("rubro") and not p.get("producto")
               and not p.get("orden") and p.get("condiciones")]
    if busquedas and sueltas:
        for s in sueltas:
            for b in busquedas:
                b["condiciones"] = list(b.get("condiciones") or []) + [c for c in s["condiciones"]
                                                                       if c not in (b.get("condiciones") or [])]
        piezas = [p for p in piezas if p not in sueltas]
    # El orden suelto —"los mas baratos" como pieza propia— vale igual para
    # las busquedas que no traen el suyo (1-oct, K03).
    orden_suelto = [p for p in piezas if p.get("tipo") == "buscar" and not p.get("rubro") and not p.get("producto")
                    and not p.get("condiciones") and (p.get("orden") or {}).get("campo")]
    if busquedas and orden_suelto:
        for b in busquedas:
            if not (b.get("orden") or {}).get("campo"):
                b["orden"] = dict(orden_suelto[0]["orden"])
        piezas = [p for p in piezas if p not in orden_suelto]
    piezas = [q for p in piezas for q in _por_destino(p)]
    cuenta = next((p for p in piezas if p.get("tipo") == "cuenta"), None)
    if cuenta is not None and not cuenta.get("reparto_pago"):
        rep = next((p.get("reparto_pago") for p in piezas if p.get("reparto_pago")), None)
        if rep:
            cuenta["reparto_pago"] = rep
    al_final = ("cuenta", "comprar")
    return [p for p in piezas if p.get("tipo") not in al_final] + [p for p in piezas if p.get("tipo") in al_final]


def _por_destino(p: dict) -> list:
    """Una cuenta cuyos items van a dos o mas destinos es una cuenta por
    destino: "un auricular y un mouse a Cordoba, el resto a Posadas"."""
    if p.get("tipo") != "cuenta":
        return [p]
    items = [i for i in p.get("items") or [] if isinstance(i, dict)]
    destinos = list(dict.fromkeys(str(i.get("destino") or "").strip() for i in items))
    if len([d for d in destinos if d]) < 2:
        return [p]
    return [{**p, "texto": f"cuenta para {d}" if d else "items sin destino", "destinos": [d] if d else [],
             "items": [i for i in items if str(i.get("destino") or "").strip() == d]} for d in destinos]


def _palabras(texto: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", A._n(texto)) if len(w) > 2}


def _de_la_busqueda(nombre: str, busquedas: list, usados: dict, pendientes: int) -> str:
    """LA SEGUNDA VUELTA (1-oct). Un item de la cuenta que no es un producto
    —"auriculares", "el mouse mas liviano", "articulo mas barato 1"— sale de
    una busqueda que este mismo turno ya corrio: la de palabras mas parecidas, y
    de ella la fila que sigue, con stock. Asi "los dos mas baratos" son la
    primera y la segunda fila. El id lo pone el codigo, nunca el modelo."""
    if not busquedas:
        return ""
    pal = _palabras(nombre)
    puntos = [len(pal & _palabras(" ".join(str(b[0].get(k) or "") for k in ("texto", "rubro", "producto"))))
              + (5 if b[0].get("rubro") and A._n(b[0]["rubro"]).split()[0][:5] in A._n(nombre) else 0)
              for b in busquedas]
    if max(puntos) == 0:
        # Sin palabras en comun, solo si hay una busqueda por item y en orden.
        if pendientes != len(busquedas):
            return ""
        i = min(range(len(busquedas)), key=lambda j: usados.get(j, 0))
    else:
        i = puntos.index(max(puntos))
    pid, usados[i] = _fila_con_stock(busquedas[i][1], usados.get(i, 0))
    return pid


def _fila_con_stock(out: dict, desde: int = 0) -> tuple:
    """(id, siguiente) de la primera fila desde `desde` que tiene stock, en ella
    o en otro color. Sin ninguna, ("", fin)."""
    filas = (out or {}).get("filas") or []
    for k, f in enumerate(filas[desde:], desde):
        opciones = [{"id": f.get("id"), "stock": f.get("stock")}] + list(f.get("variantes") or [])
        con = next((o for o in opciones if o.get("id") and (o.get("stock") is None or int(o["stock"] or 0) > 0)),
                   None)
        if con:
            return str(con["id"]), k + 1
    return "", len(filas)


def _resolver_items(items: list, tienda_id: str, llamadas: list, ctx: dict) -> list:
    """Cada item de una cuenta, certificado por nombre; el que no certifica y
    vino de una busqueda de este turno, por la segunda vuelta."""
    out, pend = [], []
    for i in items:
        if not isinstance(i, dict):
            continue
        pid = _certificado(str(i.get("producto") or ""), tienda_id, llamadas)
        out.append({**i, "producto": pid})
        if not _ID.fullmatch(str(pid)):
            pend.append(out[-1])
    usados = ctx.setdefault("usados", {})
    for i in pend:
        pid = _de_la_busqueda(str(i["producto"]), ctx.get("busquedas") or [], usados, len(pend))
        if pid:
            i["producto"] = pid
            ctx.setdefault("resueltos", set()).add(pid)
    return out


def _destinos_del_turno(pz: dict, piezas: list) -> list:
    """Los destinos de una cuenta: un envio por destino. Los suyos si los trae,
    en la pieza o en su texto —"un auricular y un mouse a Cordoba"—. Si es la
    unica cuenta del mensaje, todos los que el mensaje cotiza. Con varias
    cuentas, cada una con el suyo: el 1-oct cada una de tres cuentas llevo los
    tres envios."""
    propios = [str(d) for d in pz.get("destinos") or [] if str(d).strip()]
    varias = sum(p.get("tipo") == "cuenta" for p in piezas) > 1
    if not propios and varias and pz.get("texto"):
        # Del texto, solo con varias cuentas y solo un lugar del padron.
        propios = [_lugar_en(pz["texto"])] if _lugar_en(pz["texto"]) else []
    if propios or varias:
        return list(dict.fromkeys(propios))
    return list(dict.fromkeys(str(d) for p in piezas if p.get("tipo") == "envio"
                              for d in p.get("destinos") or [] if str(d).strip()))


_FALTA_LUGAR = re.compile(r"destin|envi|direcc|localidad|ciudad|domicilio|calle|lugar")
# El esquema no tiene nulo para "falta": el modelo escribe "ninguna" y era una
# pregunta al cliente.
_NADA = re.compile(r"|ningun[oa]?|nada|no|none|null|n/?a|-")


def respondidos_en(memoria: str) -> set:
    """Los ids que la memoria marca como la respuesta a lo que el cliente pidio."""
    from app.core.respuesta import RESPUESTA
    return set(re.findall(r"([A-Z]{3}\d{4}): [^/\n]*?" + re.escape(RESPUESTA), memoria or ""))


def respondidos(busquedas: list) -> list:
    """Lo que respondio cada busqueda por criterio de este turno: con orden,
    las primeras filas hasta la cantidad pedida, uno si no dijo cuantos, con
    sus colores. Sin orden no hay una respuesta: hay una lista."""
    out = []
    for pz, res in busquedas or []:
        if not isinstance(pz, dict) or not (pz.get("orden") or {}).get("campo"):
            continue
        for f in ((res or {}).get("filas") or [])[:max(1, int(pz.get("cantidad") or 1))]:
            out += [str(f.get("id"))] + [str(v.get("id")) for v in f.get("variantes") or []]
    return list(dict.fromkeys(i for i in out if i and i != "None"))


def _elegidos(items: list, llamadas: list, memoria: str, tienda_id: str, resueltos: set = None) -> list:
    """LA CUENTA SUMA LO QUE EL CLIENTE ELIGIO, NO LO QUE EL BOT MOSTRO (30-sep,
    M10): ante "cuanto es todo" el interprete metia los doce productos de la
    lista. Elegido es lo que el cliente nombro, lo reservado y lo que ya estaba
    en el pedido. Si el filtro deja la cuenta vacia, queda como vino."""
    from app.storage.firestore_client import get_product_by_id
    dijo = A._n(CLIENTE_DIJO.get())
    reservados = {str((x.get("vuelve") or {}).get("id")) for x in llamadas if x.get("herramienta") == "reservar"}
    p = re.search(r"EN EL PEDIDO, tal como se conto: (.+)", memoria or "")
    pedido = set(_ID.findall(p.group(1))) if p else set()

    def nombrado(pid: str) -> bool:
        prod = get_product_by_id(pid, tienda_id=tienda_id) or {}
        todas = [w for w in re.findall(r"[a-z0-9]+", A._n(prod.get("modelo") or "")) if len(w) > 1]
        claves = [w for w in todas if any(c.isdigit() for c in w)]  # "G203 Lightsync": alcanza g203
        if claves:
            return all(w in dijo for w in claves)
        # Sin numero, la palabra mas larga del modelo: "stinger 2" nombra el
        # "Cloud Stinger 2" aunque no diga "cloud" (2-oct, guion 32).
        return bool(todas) and max(todas, key=len) in dijo
    resueltos = (resueltos or set()) | respondidos_en(memoria)
    quedan = [i for i in items if not _ID.fullmatch(str(i.get("producto"))) or str(i["producto"]) in reservados
              or str(i["producto"]) in pedido or str(i["producto"]) in resueltos or nombrado(str(i["producto"]))]
    return quedan or items


def _un_color_por_modelo(items: list, tienda_id: str) -> list:
    """UN MODELO EN VARIOS COLORES ES UNA OPCION (1-oct, K18). La memoria
    muestra cada renglon con sus colores, y ante "sumame uno de cada uno" el
    interprete metia el negro y el blanco. Si el cliente no nombro el color,
    de cada modelo queda uno: el primero con stock."""
    from app.storage.firestore_client import get_product_by_id
    dijo = A._n(CLIENTE_DIJO.get())
    grupos: dict = {}
    for i in items:
        pid = str(i.get("producto"))
        p = (get_product_by_id(pid, tienda_id=tienda_id) or {}) if _ID.fullmatch(pid) else {}
        clave = (p.get("categoria"), A._n(p.get("modelo") or "")) if p.get("modelo") else pid
        grupos.setdefault(clave, []).append((i, p))
    out = []
    for g in grupos.values():
        if len(g) == 1 or any(p.get("color") and A._n(p["color"]) in dijo for _, p in g):
            out += [i for i, _ in g]
            continue
        out.append(next((i for i, p in g if int(p.get("stock") or 0) > 0), g[0][0]))
    return [i for i in items if i in out]


def _reparto(rep):
    if not rep:
        return None
    rep = [r for r in rep if isinstance(r, dict)]
    # EL MEDIO LO NOMBRA EL CLIENTE O NO HAY MEDIO (1-oct): ante "dividi el
    # presupuesto en setenta treinta" el interprete escribio efectivo y
    # tarjeta, y el cliente leyo medios que nunca dijo.
    dijo = A._n(CLIENTE_DIJO.get())
    rep = [{**r, "medio": r.get("medio") if _palabras(str(r.get("medio") or "")) & _palabras(dijo)
            else f"parte {i}"} for i, r in enumerate(rep, 1)]
    if rep and all(float(r.get("porcentaje") or 0) <= 1 for r in rep):
        rep = [{**r, "porcentaje": round(float(r.get("porcentaje") or 0) * 100, 2)} for r in rep]
    return rep or None


def _sin_ids(texto: str, tienda_id: str) -> str:
    """El id entre parentesis se borra; el id suelto se cambia por el nombre."""
    from app.storage.firestore_client import get_product_by_id
    texto = _ID_ENTRE_PARENTESIS.sub("", texto or "")
    return _ID.sub(lambda m: (get_product_by_id(m.group(1), tienda_id=tienda_id) or {}).get("nombre") or m.group(1),
                   texto)


def _para_redactar(out: dict) -> dict:
    """Lo que devolvio la herramienta, sin lo que es para corregir la consulta:
    el redactor lo leia como dato del producto."""
    if not isinstance(out, dict):
        return out
    limpio = {k: v for k, v in out.items() if k not in _NO_ES_DATO and k not in _NOTAS}
    # LA CONDICION QUE NO SE PUDO FILTRAR SE DICE COMO TAL (30-sep, J02): sin
    # esto el redactor veia filas sin el dato y contestaba "no tenemos".
    sin_filtro = [str(x.get("campo")) for x in out.get("no_aplicado") or [] if isinstance(x, dict) and x.get("campo")]
    if sin_filtro:
        limpio["no_se_pudo_filtrar_por"] = sin_filtro
    notas = {k: out[k] for k in _NOTAS if out.get(k)}
    if notas:
        limpio["nota_interna"] = notas
    for k in ("por_condicion",):
        if isinstance(limpio.get(k), list):
            limpio[k] = [_para_redactar(x) for x in limpio[k]]
    for k in ("cuenta", "compatibilidad"):
        if isinstance(limpio.get(k), dict):
            limpio[k] = _para_redactar(limpio[k])
    return limpio


def _envios_juntos(piezas: list) -> list:
    """Todas las piezas de envio en una: un destino por pieza terminaba con el
    segundo destino afuera de lo que leia el redactor."""
    env = [p for p in piezas if p.get("tipo") == "envio"]
    if len(env) < 2:
        return piezas
    destinos = list(dict.fromkeys(d for p in env for d in p.get("destinos") or []))
    uno = {**env[0], "destinos": destinos, "texto": " / ".join(p.get("texto") or "" for p in env)}
    return [uno if p is env[0] else p for p in piezas if p not in env[1:]]


def _rubro_de(nombre: str, tienda_id: str) -> str:
    """El rubro de un item de cuenta: el nombre si es un rubro, o la categoria
    del producto si certifica a uno solo."""
    r = _es_rubro(nombre, tienda_id)
    if r or not nombre:
        return r
    pid = nombre if _ID.fullmatch(nombre.strip()) else _certificado(nombre, tienda_id, [])
    if not _ID.fullmatch(str(pid)):
        return ""
    from app.storage.firestore_client import get_product_by_id
    return str((get_product_by_id(str(pid), tienda_id=tienda_id) or {}).get("categoria") or "")


def _rubros_nombrados(texto: str, tienda_id: str) -> list:
    """Los rubros que el texto nombra, palabra por palabra: "un teclado"."""
    out = []
    for w in re.findall(r"[a-z]+", A._n(texto)):
        r = _es_rubro(w, tienda_id) if len(w) > 3 else ""
        if r and r not in out:
            out.append(r)
    return out


def _conservar(piezas: list, tienda_id: str, mensaje: str = "") -> dict:
    """LOS ARTICULOS SE CONSERVAN (1-oct, K20). Cuando el cliente pide una lista
    —"dos auriculares, dos mouse y dos memorias"— y la reparte en destinos, lo
    repartido tiene que cerrar con la lista. El modelo parte bien cada destino
    pero no cuenta: un teclado que no estaba entraba a Concordia y una memoria
    quedaba sin destino, sin que nadie lo dijera.

    Cuenta por rubro lo pedido —la cantidad de cada busqueda— contra lo que
    llevan las cuentas. Si un item no es de ningun rubro pedido y a la lista le
    falta exactamente esa cantidad, se toma lo que falta en su lugar y se dice.
    Lo que no cierra se informa: sin destino o fuera de la lista. Un rubro que
    el cliente nombro y no esta en la lista ni en ninguna cuenta —el
    interprete ya puso otro en su lugar— tambien se dice. Cambia las
    piezas en el lugar y vuelve lo que el redactor tiene que decir; vacio si
    cierra o si no hay lista con cantidades."""
    cuentas = [p for p in piezas if p.get("tipo") == "cuenta" and p.get("items")]
    pedido: dict = {}
    for p in piezas:
        if p.get("tipo") == "buscar" and p.get("rubro") and int(p.get("cantidad") or 0) > 0:
            # EL MAXIMO, NO LA SUMA: la revision repite la pieza del rubro —"ver
            # si hay" y "precio de"— y la suma daba cuatro auriculares pedidos.
            # Contar de menos solo debilita el aviso; contar de mas lo inventa.
            pedido[p["rubro"]] = max(pedido.get(p["rubro"], 0), int(p["cantidad"]))
    if len(cuentas) < 2 or not pedido:
        return {}
    asignado, fuera = {}, []
    for c in cuentas:
        for i in c["items"]:
            if not isinstance(i, dict):
                continue
            r = _rubro_de(str(i.get("producto") or ""), tienda_id)
            if r in pedido:
                asignado[r] = asignado.get(r, 0) + int(i.get("cantidad") or 1)
            elif r:
                fuera.append((c, i, r))
    faltan = [r for r in pedido for _ in range(pedido[r] - asignado.get(r, 0))]
    informe: dict = {}
    if fuera and sum(int(i.get("cantidad") or 1) for _, i, _ in fuera) == len(faltan):
        for c, i, r in fuera:
            toma = [faltan.pop(0) for _ in range(int(i.get("cantidad") or 1))][0]
            informe.setdefault("reemplazo", []).append(
                {"dijo": i.get("producto"), "destino": c.get("texto"), "se_tomo": toma,
                 # LA TIENDA SI LO VENDE, Y SE DICE (3-oct, produccion): "no estaba entre los
                 # articulos pedidos" salio como "el teclado no figura en nuestro catalogo",
                 # y el turno siguiente el bot le dio la razon al "no tenes teclados".
                 "por_que": f"la tienda si vende {r}; {i.get('producto')} no estaba entre los articulos "
                            f"que pidio el cliente y quedaba {toma} sin destino"})
            i["producto"] = toma
        fuera = []
    if faltan:
        informe["sin_destino"] = [f"{faltan.count(r)} {r}" for r in dict.fromkeys(faltan)]
    if fuera:
        informe["fuera_de_lista"] = [f"{i.get('producto')}: la tienda si vende {r}, pero no estaba entre los "
                                     f"articulos que pidio el cliente" for _, i, r in fuera]
    llevan = {_rubro_de(str(i.get("producto") or ""), tienda_id) for c in cuentas for i in c["items"]
              if isinstance(i, dict)}
    sin_pedir = [r for r in _rubros_nombrados(mensaje, tienda_id) if r not in pedido and r not in llevan
                 and r not in {x["dijo"] for x in informe.get("reemplazo") or []}]
    if sin_pedir and not informe.get("reemplazo"):
        lista = ", ".join(f"{n} {r}" for r, n in pedido.items())
        informe["nombro_fuera_de_la_lista"] = [f"{r}: la tienda vende {r}, pero no estaba entre los articulos que "
                                               f"pidio el cliente ({lista}); los presupuestos llevan los de su lista"
                                               for r in sin_pedir]
    if informe:
        informe["pedido"] = [f"{n} {r}" for r, n in pedido.items()]
    return informe


def _total_general(bloques: list, reparto, tienda_id: str) -> dict:
    """EL TOTAL GENERAL Y EL REPARTO SOBRE ESE TOTAL (1-oct, K20). Con un
    presupuesto por destino el cliente pide "dividi en setenta treinta" una vez:
    es sobre todo. La suma la hace el codigo con los totales que ya dio la
    cuenta de cada destino, y el reparto, la misma funcion de siempre."""
    from app.core.pago_split import calcular_split, descuento_de, render_split
    from app.core.calculadora import _money
    totales = [int(c["total_ars"]) for c in bloques]
    base = sum(totales)
    out = {"total_ars": base, "total": _money(base), "bloques_ars": totales}
    detalle = f"Total general de los {len(totales)} presupuestos: {_money(base)}"
    if reparto:
        split = calcular_split(base, reparto, *descuento_de(tienda_id))
        if split.get("ok"):
            out["split_pago"] = split
            out["total_final_ars"] = split["total_final_ars"]
            detalle += "\n\n" + render_split(split)
    out["detalle"] = detalle
    return out


def _reparto_en_cuentas(piezas: list) -> list:
    """Las piezas con el reparto pegado a la primera cuenta, donde lo busca
    el codigo al retomar el pedido."""
    rep = next((p.get("reparto_pago") for p in piezas if p.get("reparto_pago")), None)
    out = [dict(p) for p in piezas]
    cuenta = next((p for p in out if p.get("tipo") == "cuenta"), None)
    if rep and cuenta is not None and not cuenta.get("reparto_pago"):
        cuenta["reparto_pago"] = rep
    return out


_EXCLUYEN = ("no_contiene", "evita")


def exclusiones_vigentes(memoria: str) -> list:
    """Las exclusiones de la ultima busqueda del cliente, leidas del renglon
    que escribe `busqueda_vigente`: "buscar mouse, marca no_contiene Genius"."""
    out = []
    for renglon in re.findall(r"^buscar (.+)$", memoria or "", re.M):
        for parte in renglon.split(", "):
            w = parte.split(" ", 2)
            if len(w) == 3 and w[1] in _EXCLUYEN:
                c = {"campo": w[0], "operador": w[1], "valor": w[2]}
                if c not in out:
                    out.append(c)
    return out


def exclusiones_de(piezas: list) -> list:
    return [{"campo": c.get("campo"), "operador": c.get("operador"), "valor": c.get("valor")}
            for p in piezas if p.get("tipo") == "buscar" for c in p.get("condiciones") or []
            if isinstance(c, dict) and c.get("operador") in _EXCLUYEN]


def _heredar_exclusiones(piezas: list, memoria: str, mensaje: str, del_mensaje: list = None) -> list:
    """LA EXCLUSION SIGUE VALIENDO HASTA QUE EL CLIENTE LA SUELTE (2-oct, K17).
    "Que no sea Genius ni Logitech" y despues "y teclados?": la busqueda nueva
    salia sin la exclusion y el bot mostraba Logitech. La memoria la tenia
    como texto y el interprete no siempre la copiaba. Ahora la copia el
    codigo: solo lo que EXCLUYE, que es preferencia del cliente y vale para
    cualquier rubro; lo que elige —"auriculares JBL"— es de esa busqueda y no
    se hereda. Se suelta si el mensaje dice que la marca no importa o vuelve
    a nombrar lo excluido."""
    m = A._n(mensaje)
    vigentes = [] if A._SUELTA.search(m) else [c for c in exclusiones_vigentes(memoria)
                                               if A._n(c["valor"]) not in m]
    # Lo que la primera lectura de ESTE mensaje excluia tampoco se pierde en
    # la revision: el 2-oct, K17, la correccion paso las exclusiones a una
    # pieza verificar y dejo la busqueda limpia.
    vigentes += [c for c in del_mensaje or [] if c not in vigentes]
    if not vigentes:
        return piezas
    out = []
    for p in piezas:
        if p.get("tipo") == "buscar" and p.get("rubro") != NO_LO_VENDE:
            propias = p.get("condiciones") or []
            suma = [c for c in vigentes
                    if not any(A._n(x.get("valor")) == A._n(c["valor"]) for x in propias if isinstance(x, dict))]
            if suma:
                p = {**p, "condiciones": list(propias) + suma}
        out.append(p)
    return out


def correr_piezas(piezas: list, tienda_id: str, llamadas: list, vuelta: int, ctx: dict) -> list:
    """Corre cada pieza con su herramienta. Vuelve los HECHOS, uno por pieza."""
    piezas = _heredar_exclusiones(_normalizar(_envios_juntos(piezas), tienda_id), ctx.get("memoria") or "",
                                  ctx.get("mensaje") or "", ctx.get("excluye_el_mensaje"))
    hechos = []
    ctx["busquedas"], ctx["usados"], ctx["no_vende"] = [], {}, []
    antes = [dict(p) for p in piezas]
    articulos = _conservar(piezas, tienda_id, ctx.get("mensaje") or "")
    # SI LO REPARTIDO NO CIERRA, PRIMERO SE CONFIRMA (1-oct, K20): no se busca
    # ni se cuenta nada del pedido; se guarda y se le pregunta al cliente.
    confirmar = bool(articulos) and ctx.get("puede_confirmar")
    if confirmar:
        from app.core import pedido as PD
        ctx["pedido"] = PD.guardar(_reparto_en_cuentas(antes), articulos)
        hechos.append({"parte": "el pedido, antes de calcular", "tipo": "confirmar_pedido",
                       "resultado": {"entendi": PD.resumen(piezas), "no_cierra": articulos,
                                     "pregunta": "si esta bien asi; con su ok se pasan los presupuestos"}})
    elif articulos:
        hechos.append({"parte": "los articulos pedidos contra lo repartido por destino", "tipo": "articulos",
                       "resultado": articulos})
    # CON VARIOS DESTINOS EL REPARTO VA SOBRE EL TOTAL: cada bloque sale sin el
    # suyo, y el total general lo lleva una vez.
    varias = [p for p in piezas if p.get("tipo") == "cuenta"]
    reparto_total = None
    if len(varias) > 1:
        reparto_total = next((p.get("reparto_pago") for p in varias if p.get("reparto_pago")), None)
        for p in varias:
            p["reparto_pago"] = None
    bloques = []
    vistas = {json.dumps([x["herramienta"], x["args"]], sort_keys=True, default=str): x.get("vuelve") for x in llamadas}
    for pz in _orden(piezas):
        if confirmar and pz.get("tipo") in ("buscar", "cuenta", "producto", "comprar", "envio"):
            continue
        h, args = a_herramienta(pz)
        if h in ("cuenta", "reservar"):
            if h == "cuenta":
                args["items"] = _resolver_items(args.get("items") or [], tienda_id, llamadas, ctx)
                # UNA CUENTA CORRE SI EL CLIENTE PIDE UN TOTAL O UN REPARTO, o si
                # todo lo que suma quedo certificado: con pedido y destino, el
                # total lo tiene que dar la cuenta, no el redactor sumando.
                if len(args["items"]) > 1:
                    args["items"] = _un_color_por_modelo(args["items"], tienda_id)
                    args["items"] = _elegidos(args["items"], llamadas, ctx["memoria"], tienda_id,
                                              ctx.get("resueltos"))
                certificada = bool(args["items"]) and all(_ID.fullmatch(str(i["producto"])) for i in args["items"])
                if not (ctx["pide_total"] or args.get("reparto_pago") or certificada):
                    h = None
                    ctx["cuenta_pedida"] = True  # la pidio el interprete sin productos certificados
                args["destino"] = args.get("destino") or _destino(pz, piezas, ctx["mensaje"], ctx["historial"],
                                                                   ctx["memoria"])
                args["destinos"] = _destinos_del_turno(pz, piezas) or ([args["destino"]] if args["destino"] else [])
                if args["destinos"]:
                    args["destino"] = args["destinos"][0]
                args["reparto_pago"] = _reparto(args.get("reparto_pago"))
            else:
                args["producto"] = _certificado(args["producto"], tienda_id, llamadas)
                if not _ID.fullmatch(str(args["producto"])):
                    pid = _de_la_busqueda(args["producto"], ctx["busquedas"], ctx["usados"], 1)
                    if pid:
                        args["producto"] = pid
        if h == "envio" and not args.get("destinos"):
            d = _destino(pz, piezas, ctx["mensaje"], ctx["historial"], ctx["memoria"])
            args["destinos"] = [d] if d else []
        hecho = {"parte": pz.get("texto"), "tipo": pz.get("tipo")}
        if pz.get("tipo") == "buscar" and pz.get("rubro") == NO_LO_VENDE:
            hecho["resultado"] = {"veredicto": "no_existe", "motivo": "la tienda no vende ese rubro"}
            ctx["no_vende"].append((pz, {}))
        # LO QUE VENDE LA TIENDA LO DICE EL CODIGO (2-oct, K12 y K19): "que
        # venden?" llega como saber general, y "y algo parecido?" despues de
        # un rubro que no hay, como no lo vende. Sin la lista el redactor no
        # tenia de donde decir que si hay, y contestaba de memoria o nada.
        # Y una verificacion sin producto —"no tenes teclados?"— tambien: sin la
        # lista, el redactor le daba la razon al cliente (3-oct, produccion).
        if pz.get("tipo") == "explicar" or pz.get("rubro") == NO_LO_VENDE \
                or (pz.get("tipo") == "verificar" and not pz.get("producto")):
            hecho["la_tienda_vende"] = _vocabulario(tienda_id)[0]
        if pz.get("depende_de"):
            hecho["depende_de_la_parte"] = pz["depende_de"]
        # LO QUE EL MENSAJE YA DICE NO FALTA (1-oct): el interprete pone el
        # destino en "falta" aunque el cliente lo haya nombrado, y el bot le
        # preguntaba por la direccion que ya habia dado.
        falta = "" if _NADA.fullmatch(A._n(str(pz.get("falta") or "")).strip()) else pz.get("falta")
        if falta and not (_FALTA_LUGAR.search(A._n(falta)) and _destino(
                pz, piezas, ctx["mensaje"], ctx["historial"], ctx["memoria"])):
            hecho["pregunta_al_cliente"] = falta
        if h:
            # LA CONSULTA REPETIDA NO SE VUELVE A HACER, PERO SU RESULTADO SI
            # LLEGA AL REDACTOR. Sin esto, la correccion dejaba la parte sin
            # datos y el redactor inventaba para llenar el hueco (30-sep).
            clave = json.dumps([h, args], sort_keys=True, default=str)
            if clave not in vistas:
                out = ejecutar(h, args, tienda_id)
                llamadas.append({"vuelta": vuelta, "herramienta": h, "args": args, "vuelve": out})
                vistas[clave] = out
            if h == "cuenta" and ((vistas[clave] or {}).get("cuenta") or {}).get("total_ars") is None:
                ctx["cuenta_pedida"] = True  # corrio y no dio total: la arma el codigo al final
            hecho["resultado"] = _para_redactar(vistas[clave])
            if h == "buscar":
                ctx["busquedas"].append((pz, vistas[clave]))
            if h == "cuenta" and ((vistas[clave] or {}).get("cuenta") or {}).get("total_ars") is not None:
                bloques.append((args, vistas[clave]["cuenta"]))
        hechos.append(hecho)
    if len(bloques) > 1:
        hechos.append(_hecho_total_general(bloques, _reparto(reparto_total), tienda_id, llamadas, vuelta, ctx))
    return hechos


def _hecho_total_general(bloques: list, rep, tienda_id: str, llamadas: list, vuelta: int, ctx: dict) -> dict:
    """El total general como llamada —la guarda de plata ve sus montos— y como
    hecho para el redactor. Deja en `ctx["bloques"]` que va a cada destino,
    para que el turno siguiente lo encuentre en la memoria."""
    from app.storage.firestore_client import get_product_by_id
    tg = _total_general([c for _, c in bloques], rep, tienda_id)
    llamadas.append({"vuelta": vuelta, "herramienta": "total_general",
                     "args": {"bloques": len(bloques), "reparto_pago": rep}, "vuelve": tg})
    grupos = []
    for args, _ in bloques:
        items = [{"producto": str(i["producto"]), "cantidad": int(i.get("cantidad") or 1)}
                 for i in args.get("items") or [] if _ID.fullmatch(str(i.get("producto")))]
        # `cats` es el formato que `calculadora` ya lee de grupos_envio.
        cats = [{"n": i["cantidad"], "cat": str((get_product_by_id(i["producto"], tienda_id=tienda_id) or {})
                                                .get("categoria") or "")} for i in items]
        grupos.append({"destino": (args.get("destinos") or [args.get("destino") or ""])[0],
                       "items": items, "cats": cats})
    ctx["bloques"] = grupos
    return {"parte": "el total general de todos los presupuestos", "tipo": "total_general",
            "resultado": {"total_general": tg["total"], "detalle": tg["detalle"]}}


_BLOQUES = re.compile(r"LOS PRESUPUESTOS POR DESTINO[^\n]*\n((?:- .+\n?)+)")


def bloques_en_memoria(memoria: str) -> list:
    """Los presupuestos por destino que la memoria trae del turno anterior."""
    m = _BLOQUES.search(memoria or "")
    out = []
    for r in (m.group(1).splitlines() if m else []):
        d = re.match(r"- (.+?): ", r)
        items = [{"producto": pid, "cantidad": int(n)} for n, pid in re.findall(r"(\d+)x ([A-Z]{3}\d{4})", r)]
        if d and items:
            out.append({"destino": d.group(1).strip(), "items": items})
    return out


def _ids_recientes(memoria: str) -> list:
    """Los ids de lo que el bot nombro en su ultimo mensaje, y el pedido."""
    m = re.search(r"LO QUE NOMBRASTE EN TU ULTIMO MENSAJE.*?\n((?:\d+\..*\n?)+)", memoria or "", re.S)
    # Un renglon es un modelo en varios colores: vale el primero, el que se nombro.
    ids = [x[0] for x in (_ID.findall(r) for r in (m.group(1).splitlines() if m else [])) if x]
    p = re.search(r"EN EL PEDIDO, tal como se conto: (.+)", memoria or "")
    if p:
        ids += _ID.findall(p.group(1))
    if not ids:
        ids = _ID.findall(memoria or "")[-4:]
    return list(dict.fromkeys(ids))


def _cuenta_del_codigo(piezas: list, llamadas: list, tienda_id: str, ctx: dict, vuelta: int) -> dict:
    """Si el cliente pide un total y ninguna pieza lo trajo, la cuenta la arma
    el codigo: lo certificado en este turno o, si no hay, lo que el bot nombro
    en su ultimo mensaje. El modelo lo detecta siempre; armarla no."""
    ids = []
    for x in llamadas:
        v = x.get("vuelve") or {}
        filas = v.get("filas") or []
        if x["herramienta"] in ("producto", "reservar") and len(filas) == 1 and filas[0].get("id"):
            ids.append(str(filas[0]["id"]))
        if x["herramienta"] == "reservar" and v.get("id"):
            ids.append(str(v["id"]))
    cant = {str(i.get("producto")): i.get("cantidad") or 1 for p in piezas for i in p.get("items") or []}
    # LA SEGUNDA VUELTA TAMBIEN ACA: si este turno solo busco —"dos auriculares
    # y dos mouse, los mas baratos, sumame todo"—, la cuenta sale de lo que
    # encontro cada busqueda, con la cantidad que pidio el cliente.
    if not ids:
        for pz, out in ctx.get("busquedas") or []:
            pid = _fila_con_stock(out)[0]
            if pid:
                ids.append(pid)
                cant[pid] = pz.get("cantidad") or 1
    rep = next((p.get("reparto_pago") for p in piezas if p.get("reparto_pago")), None)
    # LOS PRESUPUESTOS POR DESTINO SOBREVIVEN AL TURNO (1-oct, K07): "decime
    # mitad transferencia y mitad mercado pago" despues de tres destinos es
    # sobre los tres. Se rearma cada bloque y el total general, con el reparto
    # nuevo.
    grupos = bloques_en_memoria(ctx["memoria"]) if not ids else []
    if len(grupos) > 1:
        bloques = []
        for g in grupos:
            args = {"items": g["items"], "destino": g["destino"], "destinos": [g["destino"]], "reparto_pago": None}
            out = ejecutar("cuenta", args, tienda_id)
            llamadas.append({"vuelta": vuelta, "herramienta": "cuenta", "args": args, "vuelve": out})
            if (out.get("cuenta") or {}).get("total_ars") is not None:
                bloques.append((args, out["cuenta"]))
        if len(bloques) > 1:
            return _hecho_total_general(bloques, _reparto(rep), tienda_id, llamadas, vuelta, ctx)
    if not ids:
        ids = _ids_recientes(ctx["memoria"])
    ids = list(dict.fromkeys(ids))
    if not ids:
        return {}
    destinos = _destinos_del_turno({}, piezas)
    args = {"items": [{"producto": i, "cantidad": cant.get(i, 1)} for i in ids],
            "destino": (destinos or [""])[0] or _destino({}, piezas, ctx["mensaje"], ctx["historial"],
                                                         ctx["memoria"]),
            "destinos": destinos, "reparto_pago": _reparto(rep)}
    out = ejecutar("cuenta", args, tienda_id)
    llamadas.append({"vuelta": vuelta, "herramienta": "cuenta", "args": args, "vuelve": out})
    return {"parte": "el total que pidio el cliente", "tipo": "cuenta", "resultado": _para_redactar(out)}


def _revision(piezas: list, banderas: dict, llamadas: list, mensaje: str, historial: list,
              tienda_id: str) -> str:
    """Lo que el mensaje pide y las piezas no traen, dicho como pedido de
    correccion. Vacio si esta todo. Es la MISMA lectura de completitud del
    agente, mas lo que marcaron las preguntas de si o no."""
    partes = []
    tipos = {p.get("tipo") for p in piezas}
    if banderas.get("pide_total") and "cuenta" not in tipos:
        partes.append("pide un total y no hay pieza cuenta: agregala con todos los productos y el destino")
    if banderas.get("condicional") and not any(p.get("depende_de") for p in piezas) \
            and not any(p.get("tipo") == "cuenta" and p.get("condiciones") for p in piezas):
        partes.append("pone una condicion y ninguna pieza depende de otra: separa la condicion y la accion "
                      "con depende_de")
    if banderas.get("afirma_algo") and "verificar" not in tipos:
        partes.append("da algo por cierto y ninguna pieza lo verifica")
    f = faltantes(mensaje, llamadas, historial, tienda_id)
    if f.get("destinos"):
        partes.append("nombra estos destinos y ninguna pieza los cotiza: " + ", ".join(f["destinos"]))
    if f.get("reparto"):
        partes.append("pide repartir el pago en porcentajes: la cuenta va con reparto_pago")
    if f.get("compra"):
        partes.append("dice que compra y no hay pieza comprar")
    destinos = list(dict.fromkeys(A._lugar(d) for d in A._destinos_del_mensaje(mensaje)))
    cuentas = [p for p in piezas if p.get("tipo") == "cuenta"]
    por_destino = len(cuentas) > 1 or any(len({str(i.get("destino") or "") for i in p.get("items") or []
                                                if isinstance(i, dict)} - {""}) > 1 for p in cuentas)
    buscados = {p.get("rubro") for p in piezas if p.get("tipo") == "buscar"} | {
        _es_rubro(p.get("producto") or "", tienda_id) for p in piezas if p.get("tipo") == "producto"}
    sin_buscar = list(dict.fromkeys(r for p in cuentas for i in p.get("items") or [] if isinstance(i, dict)
                                    for r in [_es_rubro(str(i.get("producto") or ""), tienda_id)]
                                    if r and r not in buscados))
    if sin_buscar:
        partes.append("la cuenta lleva rubros que ninguna pieza busca: " + ", ".join(sin_buscar)
                      + ". Agrega una pieza buscar por cada uno, con la cantidad y con orden si pide barato o caro")
    if len(destinos) > 1 and (banderas.get("pide_total") or f.get("reparto") or cuentas) and not por_destino:
        partes.append(f"reparte los articulos en {len(destinos)} destinos: en la cuenta, cada item con su destino, "
                      "y en cada buscar la cantidad que pidio")
    if f.get("excluidas"):
        partes.append("antes pidio que no sea " + ", ".join(f["excluidas"]) + ": la busqueda lo excluye con "
                      "una condicion evita o no_contiene")
    return ("REVISION DEL SISTEMA, no es del cliente. En el ultimo mensaje el cliente " + "; ".join(partes)
            + ". Devolve TODAS las piezas de nuevo, corregidas.") if partes else ""


def busqueda_vigente(busquedas: list) -> str:
    """LO QUE EL CLIENTE BUSCO, COMO SE INTERPRETO (1-oct, K17, K18, M03). La
    memoria guardaba lo que el bot mostro y no lo que el cliente pidio: "y el
    mas barato?" despues de "el mas caro que vendes" heredaba el rubro del
    producto mostrado, y "y teclados?" perdia el "que no sea Genius ni
    Logitech". Esto sobrevive al turno y el interprete lo lee en la memoria."""
    renglones = []
    for pz, _ in busquedas or []:
        if not isinstance(pz, dict):
            continue
        partes = [pz.get("rubro") or "toda la tienda"]
        if pz.get("producto") or pz.get("rubro") == NO_LO_VENDE:
            partes.append(f"que {pz.get('producto') or pz.get('texto')}")
        partes += [f"{c.get('campo')} {c.get('operador')} {c.get('valor')}" for c in pz.get("condiciones") or []
                   if isinstance(c, dict)]
        o = pz.get("orden") or {}
        if o.get("campo"):
            partes.append(f"orden {o['campo']} {o.get('direccion') or ''}".strip())
        r = "buscar " + ", ".join(str(x) for x in partes)
        if r not in renglones:
            renglones.append(r)
    return "\n".join(renglones[:4])


# ══ EL TURNO ════════════════════════════════════════════════════════════════

async def turno(historial: list, mensaje: str, tienda_id: str, trace_id: str = "",
                memoria: str = "", pedido: dict = None) -> dict:
    """Un turno con el tablero. Misma firma y misma salida que `agente.turno`. No lanza."""
    from app.core import guardas_salida as gs
    from app.core.contexto_turno import set_current_tienda
    from app.core.llm_reintento import _cliente
    set_current_tienda(tienda_id)
    _TRACE.set(trace_id or "tablero")
    CLIENTE_DIJO.set("\n".join([m.get("content") or "" for m in historial or [] if m.get("role") == "user"]
                                + [mensaje or ""]))
    cli = _cliente()
    if cli is None:
        return {"texto": "", "llamadas": [], "uso": [], "error": "sin clave"}
    t0 = time.time()
    uso, llamadas = [], []
    charla = _charla(historial, memoria, mensaje)
    sis_i = INTERPRETE.format(acciones="; ".join(f"{k}: {v}" for k, v in ACCIONES.items()), no_lo_vende=NO_LO_VENDE)
    esquema = esquema_piezas(tienda_id)
    esq = _formato("piezas", esquema)
    sis_i = _con_esquema(sis_i, esq, esquema)
    esq_b = _formato("banderas", _esquema_banderas())
    try:
        t_piezas, t_banderas = await asyncio.gather(
            _pedir(cli, [{"role": "system", "content": sis_i}] + charla, TEMP_INTERPRETAR, esq, trace_id, uso,
                   "interpretar"),
            _pedir(cli, [{"role": "system", "content": _con_esquema(PREGUNTAS, esq_b, _esquema_banderas())}]
                   + charla, TEMP_INTERPRETAR, esq_b, trace_id, uso, "banderas"))
    except Exception as e:  # noqa: BLE001 — el turno no se rompe por el modelo
        log.warning("tablero_modelo_error", trace_id=trace_id, paso="interpretar",
                    error=f"{type(e).__name__}: {str(e)[:150]}")
        return {"texto": "", "llamadas": [], "uso": uso}
    piezas, errores, corregidos = atar(piezas_de(t_piezas), tienda_id)
    if not piezas and not errores:
        # Todo mensaje es al menos una pieza: sin ninguna, la salida vino rota
        # (2-oct, M06 con DeepSeek: el texto vacio).
        errores = ["no devolviste ninguna pieza: todo mensaje es al menos una, aunque sea charla"]
    reintento = False
    if errores:
        # UNA vez: el modelo ve su salida y el error, y lo que siga roto se descarta.
        reintento = True
        try:
            t_piezas = await _pedir(cli, [{"role": "system", "content": sis_i}] + charla
                                    + [{"role": "assistant", "content": t_piezas},
                                       {"role": "user", "content": _pedido_de_atadura(errores)}],
                                    TEMP_INTERPRETAR, esq, trace_id, uso, "atadura")
            piezas, errores2, corregidos2 = atar(piezas_de(t_piezas), tienda_id)
            corregidos += corregidos2
            errores += errores2
        except Exception as e:  # noqa: BLE001 — se sigue con lo atado
            log.warning("tablero_modelo_error", trace_id=trace_id, paso="atadura", error=str(e)[:150])
    if errores or corregidos:
        log.info("tablero_atadura", trace_id=trace_id, errores=errores[:6], corregidos=corregidos[:6],
                 reintento=reintento)
    banderas = banderas_de(t_banderas)
    from app.core import pedido as PD
    guardado = PD.pendiente(pedido)
    ctx = {"mensaje": mensaje, "historial": historial, "memoria": memoria, "tienda_id": tienda_id,
           "pide_total": bool(banderas.get("pide_total")) or A._pide_reparto(mensaje),
           "puede_confirmar": not guardado}
    # EL PEDIDO GUARDADO SE RETOMA CON EL SI DEL CLIENTE. Si en vez de aceptar
    # corrige y el interprete rearmo las cuentas, cuenta la correccion. Si el
    # mensaje es de otra cosa, el pedido sigue esperando.
    consumido = False
    if guardado and (banderas.get("confirma_resumen") or any(p.get("tipo") == "cuenta" for p in piezas)):
        consumido = True
        ctx["pide_total"] = True
        if not any(p.get("tipo") == "cuenta" for p in piezas):
            piezas = PD.retomar(guardado, piezas)
    # El reparto que el interprete puso en una pieza tambien es un total pedido.
    ctx["pide_total"] = ctx["pide_total"] or any(p.get("reparto_pago") for p in piezas)
    hechos = correr_piezas(piezas, tienda_id, llamadas, 1, ctx)
    revision = _revision(piezas, banderas, llamadas, mensaje, historial, tienda_id)
    if revision and not ctx.get("pedido"):
        try:
            guias = "\n".join(GUIAS[k] for k, v in banderas.items() if v and k in GUIAS)
            t2 = await _pedir(cli, [{"role": "system", "content": sis_i + ("\n" + guias if guias else "")}] + charla
                              + [{"role": "assistant", "content": t_piezas}, {"role": "user", "content": revision}],
                              TEMP_INTERPRETAR, esq, trace_id, uso, "revision")
            nuevas, err_rev, corr_rev = atar(piezas_de(t2), tienda_id)
            if err_rev or corr_rev:
                log.info("tablero_atadura", trace_id=trace_id, paso="revision", errores=err_rev[:6],
                         corregidos=corr_rev[:6], reintento=False)
            if nuevas:
                ctx["excluye_el_mensaje"] = exclusiones_de(piezas)
                piezas = nuevas
                hechos = correr_piezas(piezas, tienda_id, llamadas, 2, ctx)
        except Exception as e:  # noqa: BLE001
            log.warning("tablero_modelo_error", trace_id=trace_id, paso="revision", error=str(e)[:150])
    if not ctx.get("pedido") and (ctx["pide_total"] or ctx.get("cuenta_pedida")) and not any(x["herramienta"] == "cuenta" and ((x.get("vuelve") or {}).get("cuenta") or {})
                                     .get("total_ars") is not None for x in llamadas):
        h = _cuenta_del_codigo(piezas, llamadas, tienda_id, ctx, 3)
        if h:
            hechos.append(h)
    # LO QUE EL MODELO DETECTA Y NO ARMA, LO ARMA EL CODIGO: si falta un dato
    # del cliente o la referencia es ambigua y ninguna pieza lo pregunta, se
    # pregunta.
    if not ctx.get("pedido") and (banderas.get("falta_dato_cliente") or banderas.get("referencia_ambigua")) \
            and not any(p.get("tipo") == "repreguntar" or p.get("falta") for p in piezas):
        hechos.append({"pregunta_al_cliente": "falta un dato del cliente o no se sabe a cual se refiere: "
                                              "preguntale eso solo"})
    sis_r = REDACTOR.format(negocio=gs.business_name(tienda_id))
    pedido = ("HECHOS del sistema para este mensaje, no los escribio el cliente:\n"
              + json.dumps(hechos, ensure_ascii=False, default=str))
    texto = ""
    try:
        texto = await _pedir(cli, [{"role": "system", "content": sis_r}] + charla
                             + [{"role": "user", "content": pedido}], TEMP_REDACTAR, None, trace_id, uso, "redactar")
    except Exception as e:  # noqa: BLE001 — sin texto el turno cae al aviso honesto
        log.warning("tablero_modelo_error", trace_id=trace_id, paso="redactar", error=str(e)[:150])
    # LOS IDS INTERNOS NO LLEGAN AL CLIENTE: lo borra el codigo, no se le pide.
    texto = _sin_ids(texto, tienda_id)
    # EL MISMO EVENTO QUE DEJABA EL AGENTE, con los mismos campos: el informe
    # del issue 31 y `leer_interpretacion` leen `agente_turno` y sus `pedidos`.
    log.info("agente_turno", trace_id=trace_id, vueltas=len(uso), llamadas=len(llamadas),
             herramientas=[x["herramienta"] for x in llamadas],
             pedidos=[f"{x['herramienta']} {json.dumps(x['args'], ensure_ascii=False)}"[:240] for x in llamadas][:10],
             piezas=[p.get("tipo") for p in piezas], banderas=[k for k, v in banderas.items() if v],
             revision=bool(revision), largo=len(texto),
             tokens=sum(x["entrada"] for x in uso), cache=sum(x["cache"] for x in uso),
             salida=sum(x["salida"] for x in uso), ms=int((time.time() - t0) * 1000))
    return {"texto": texto, "llamadas": llamadas, "uso": uso, "hechos": hechos,
            "busqueda": busqueda_vigente((ctx.get("busquedas") or []) + (ctx.get("no_vende") or [])),
            "bloques": ctx.get("bloques"),
            "respondidos": respondidos(ctx.get("busquedas")),
            # El pedido a confirmar se guarda; el retomado se borra; si no, no cambia.
            "pedido": ctx.get("pedido") or ({} if consumido else None)}
