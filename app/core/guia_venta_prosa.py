"""
GUIA DE VENTA EN PROSA — el "desde donde contestar" del solver para las
preguntas de RAZONAMIENTO (si un producto sirve para un uso, cual conviene,
por que uno sale mas, comparaciones). Es fuente de verdad de CRITERIO, no de
dato: NO trae numeros, precios ni stock (eso sale siempre de las tools). El
solver la consulta con la tool `consultar_guia_venta` y razona desde aca, en
vez de improvisar un criterio.

Semilla acotada (Martin, 12-jul): para un cliente real esta guia se extiende
mucho mas y por familia de producto. El MECANISMO es el que importa; sumar
temas es cargar texto, no tocar codigo. Registro: argentino, voseo, criterio
de vendedor, cero dato duro.

Ademas del criterio de producto, el corpus tiene MOVIDAS DE VENTA (15-jul):
frases profesionales de la charla, saludo, continuacion de un presupuesto,
consulta de si quiere algo mas, preguntas puente, preguntas de confirmacion,
cierre, seguimiento, prueba social y captura de lead. Le dan al modelo el COMO
vender con oficio, siempre sin numeros: el dato y el producto salen de las tools.
"""
import re
from difflib import get_close_matches

# Cada tema es criterio de venta en prosa, sin un solo numero.
GUIA_VENTA: dict[str, str] = {}


# Palabras del cliente -> tema de la guia. Se consulta ANTES del match difuso
# (get_close_matches con temas parecidos devolvia cualquier cosa: 'ram' caia
# en 'streaming', 'router' en 'mouse').
_ALIAS: dict[str, str] = {}


def consultar_guia_venta(tema: str | None = None, **_) -> dict:
    """Devuelve el criterio de venta de un tema (o la lista de temas). Match
    tolerante: exacto, alias por palabra, aproximado y por palabra suelta."""
    if not tema:
        return {"temas": list(GUIA_VENTA)}
    t = str(tema).lower().strip()
    if t in GUIA_VENTA:
        return {"tema": t, "id": t, "texto": GUIA_VENTA[t]}
    # Por palabra, en orden: tema literal o alias, lo primero que aparezca.
    # Cubre 'ram', 'compatibilidad de placa de video', 'sirve esta memoria
    # para mi notebook' (gana 'memoria', que aparece antes).
    for palabra in t.replace("/", " ").split():
        tema_p = palabra if palabra in GUIA_VENTA else _ALIAS.get(palabra)
        if tema_p:
            return {"tema": tema_p, "id": tema_p, "texto": GUIA_VENTA[tema_p]}
    m = get_close_matches(t, GUIA_VENTA.keys(), n=1, cutoff=0.6)
    if m:
        return {"tema": m[0], "id": m[0], "texto": GUIA_VENTA[m[0]]}
    for k in GUIA_VENTA:
        if k in t or t in k:
            return {"tema": k, "id": k, "texto": GUIA_VENTA[k]}
    return {"tema": None, "temas": list(GUIA_VENTA),
            "nota": "sin guia para ese tema; razona desde la ficha o se honesto"}


def recuperar(consulta: str | None = None, k: int = 3) -> list[dict]:
    """Recuperacion tipo RAG sobre el corpus de prosa. Puntua cada chunk contra
    la consulta del cliente por solapamiento de alias y del nombre del tema, y
    devuelve los K mejores como [{'id', 'texto'}], ordenados. El 'id' es la
    CITA: habilita pedirle al modelo que responda desde estos chunks y diga cual
    uso, y verificar despues que cito uno real. Sin match devuelve lista vacia
    (honesto: que el modelo diga que no tiene ese criterio, no que invente).

    Primer ladrillo del RAG: recuperacion simple por palabra clave, sin
    embeddings (gratis, cero infra). Si el corpus crece y esto no alcanza, se
    reemplaza el scoring por embeddings SIN tocar el resto del contrato."""
    if not consulta:
        return []
    q = str(consulta).lower()
    palabras = set(re.findall(r"\w+", q))
    puntajes: dict[str, int] = {}
    for palabra in palabras:
        tema = palabra if palabra in GUIA_VENTA else _ALIAS.get(palabra)
        if tema:
            puntajes[tema] = puntajes.get(tema, 0) + 1
    # El nombre del tema dicho literal pesa mas ('componentes pc', 'memoria ram').
    for tema in GUIA_VENTA:
        if tema.replace("_", " ") in q:
            puntajes[tema] = puntajes.get(tema, 0) + 2
    ordenados = sorted(puntajes.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
    return [{"id": t, "texto": GUIA_VENTA[t]} for t, _ in ordenados]


def texto_de(chunk_id: str) -> str | None:
    """Devuelve el texto de un chunk por id, o None. Para el verificador de
    cita: chequear que el id que dijo el modelo existe en el corpus."""
    return GUIA_VENTA.get(str(chunk_id).strip())


def tool_schema() -> dict:
    """Schema OpenAI de la tool, para sumarla al menu del solver."""
    return {
        "type": "function",
        "function": {
            "name": "consultar_guia_venta",
            "description": (
                "Guia de venta con CRITERIO (uso, comparativa, marcas, "
                "durabilidad, compatibilidad general) y MOVIDAS de venta "
                "(saludo_apertura, continuacion_presupuesto, consulta_algo_mas, "
                "preguntas_puente, preguntas_confirmacion, cierre_venta, "
                "seguimiento, prueba_social_confianza, lead_captura, "
                "urgencia_honesta, despedida_cordial). Usala para "
                "OPINAR, comparar, decir si un producto sirve para un uso, y para "
                "SABER COMO conducir la venta (abrir, confirmar, cerrar, seguir). "
                "No trae numeros; el dato duro sale de las otras tools. Temas: "
                + ", ".join(GUIA_VENTA)),
            "parameters": {
                "type": "object",
                "properties": {"tema": {
                    "type": "string",
                    "description": "uno de: " + ", ".join(GUIA_VENTA)}},
                "required": ["tema"]}}}


def _cargar_base_conocimiento() -> None:
    """Funde la FUENTE DE VERDAD del criterio (base_conocimiento.json) en el
    corpus vivo: por cada categoria mete su prosa en GUIA_VENTA y suma sus
    disparadores de una sola palabra a _ALIAS SIN pisar los ya definidos. El
    JSON es la fuente unica que Martin revisa y lima; este modulo solo la carga.
    Invariante intacto: una categoria con algun digito en el criterio NO entra
    (el dato duro sale de las tools, nunca del corpus)."""
    import json
    import os
    ruta = os.path.join(os.path.dirname(__file__), "..", "..", "data",
                        "clientes", "verifika_prod", "base_conocimiento.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            base = json.load(f)
    except Exception:
        return
    validas = [c for c in base.get("categorias", [])
               if c.get("id") and (c.get("criterio") or "").strip()
               and not re.search(r"\d", c["criterio"])]
    # Pasada 1: el criterio de cada categoria (la prosa de la que responde).
    for cat in validas:
        GUIA_VENTA[cat["id"]] = cat["criterio"].strip()
    # Pasada 2: los disparadores de una sola palabra como alias, sin pisar un
    # alias ya puesto ni un id de tema (por eso va despues de armar GUIA_VENTA).
    for cat in validas:
        for disp in cat.get("disparadores", []):
            d = str(disp).strip().lower()
            if d and " " not in d and d not in _ALIAS and d not in GUIA_VENTA:
                _ALIAS[d] = cat["id"]


_cargar_base_conocimiento()
