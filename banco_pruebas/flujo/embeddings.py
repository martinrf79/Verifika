"""LOS EMBEDDINGS DEL FLUJO NUEVO: LA RECETA, LA UNICA FUNCION QUE PIDE VECTORES Y EL REGISTRO DE CADA NEXO.

15-nov-2026, el registro de como busca cada nexo, antes `busquedas.py`. 16-nov, orden de Martin al ordenar el flujo,
FICHA 100 seccion 3 paso 1: la informacion de los embeddings se perdia de una sesion a otra, repartida en nueve
funciones con cinco caches en carpetas de sesiones que ya no existian. Desde el 16-nov todo esta aca:

LA RECETA, igual en el banco y en produccion, `app/core/flujo/agente._vectores`:
  modelo       gemini-embedding-001, por la puerta nativa de Google, `batchEmbedContents`, de a cien textos.
  dimension    la completa, sin `outputDimensionality`. Cada vector se normaliza al llegar, asi el producto punto es
               el coseno. La taxonomia de Shopify, `antecedentes/momento0_shopify.py`, fue la unica con 768.
  tareas       las consultas con RETRIEVAL_QUERY; los indices de la tienda con RETRIEVAL_DOCUMENT.
  clave        la gratis, GEMINI_API_KEY, con pausas por su cuota; la paga solo con MARTIN_AUTORIZO_LA_PAGA=<fecha>,
               mirando el tope del dia y anotada en `libro_paga.jsonl`.
  el cache     una sola clave para todo, "TAREA|texto". Lo que se pidio en la sesion queda en `vectores/cache.*`, con
               la precision entera de la API y escrito de a lote; no se sube: pesa mas de cien megas. Se borra a mano.
  verificado   el 16-nov, rehechos todos los vectores con la paga, dos centavos: los puntajes de los cinco nexos, el
               flujo, los reales, las 365 y los candidatos salen iguales byte a byte a los grabados entre el 15 y el
               16-nov. Los de `engranaje0` y `momento0_b`, del 15-nov, difieren solo en teclado: el 16-nov se le sumo el
               alias "keyboard". La API devuelve lo mismo de una sesion a otra.
  el indice    los documentos de la tienda que usan los nexos vivos, `indice_tienda`, quedan en el repo, en
               `vectores/indice_tienda.json.gz`, en float32: una sesion nueva paga solo sus consultas. Se rehace con
               `--indice` cuando cambian el catalogo, los alias, la FAQ o lo que la tienda no vende. Medido el 16-nov:
               cada componente difiere en menos de dos cienmillonesimos de la precision entera, y 150 busquedas
               contra todos los productos dan los mismos puntajes al cuarto decimal. `EMB_SIN_INDICE=1` lo saltea.
  los numeros  salen de los puntajes grabados en `grabado/`, no de los vectores: repiten todo sin gasto.

LOS INDICES DE LA TIENDA, un documento por texto:
  rubros       "rubro: alias, alias", `nexo_rubro.doc_rubro`, y lo que la tienda no vende, "no se vende: x".
  productos    un documento por modelo, "rubro: alias del rubro. Marca Modelo. etiquetas", `nexo_rubro.doc_producto`.
  temas        cada alias de cada tema de la FAQ como documento suelto, `nexo_tema.docs`.
  condicion    un documento por campo de cada rubro, "rubro, etiqueta: valores", y dos ordenes, precio y peso,
               `nexo_condicion.docs_campo`.

    python3 banco_pruebas/flujo/embeddings.py                    # la receta y el registro de cada nexo
    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/flujo/embeddings.py --indice   # rehace el indice
"""
import array
import base64
import datetime
import gzip
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from entorno import VECTORES  # noqa: E402

MODELO = "gemini-embedding-001"
CONSULTA = "RETRIEVAL_QUERY"
DOCUMENTO = "RETRIEVAL_DOCUMENT"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:batchEmbedContents"
USD_POR_MILLON = 0.15
CACHE = os.environ.get("EMB_CACHE") or os.path.join(VECTORES, "cache")
INDICE = os.path.join(VECTORES, "indice_tienda.json.gz")

NEXOS = {
    "rubro y producto": {
        "archivo": "banco_pruebas/flujo/nexo_rubro.py",
        "consulta": "busqueda, lo que tradujo el modelo en la llamada 0",
        "indice": ["rubro: sus alias, `nexo_rubro.doc_rubro`; y lo que la tienda declara que no vende, "
                   "`no_vendidas.json`, como rubro sin productos, `nexo_rubro.indice_rubros`",
                   "modelo de la tienda: rubro con sus alias, marca, modelo y etiquetas, `nexo_rubro.doc_producto`"],
        "candidatos": {"rubros": 3, "productos": 5},
        "elige": "la primera palabra de la busqueda contra el nombre y el rubro de cada candidato; si solo esta en "
                 "etiquetas o alias, o no esta, es dudoso y lo confirma Jev entre los cinco candidatos con los alias de "
                 "su rubro, o ninguno; lo que no se vende gana solo si queda primero y la busqueda lo dice",
        "calibrado": "16-nov, `nexo_rubro.py --calibrar` y `--jev`: elige bien 74, 72, 73 y 106, rubro equivocado 1, "
                     "lo que no se vende 14 de 14; antes 71, 70, 71 y 104, 5 y 8",
        "puntajes": ["banco_pruebas/flujo/grabado/nexo_rubro_puntajes.json",
                     "banco_pruebas/flujo/grabado/flujo_nuevo_puntajes.json",
                     "banco_pruebas/flujo/grabado/nexo_rubro_jev.jsonl"],
    },
    "destino": {
        "archivo": "banco_pruebas/flujo/flujo_nuevo.py, nexo_destino",
        "consulta": "destino, el lugar que marco el modelo",
        "indice": ["sin embeddings: el padron de lugares de produccion, `normal.lugares` y `fuente._cotizar`"],
        "candidatos": {},
        "elige": "el codigo de lugares",
        "puntajes": [],
    },
    "tema de la FAQ": {
        "archivo": "banco_pruebas/flujo/nexo_tema.py",
        "consulta": "fragmento, las palabras del cliente: en una pregunta de la tienda la busqueda queda vacia",
        "indice": ["cada alias de cada tema como documento suelto, pregunta contra pregunta; el puntaje del tema es el "
                   "de su alias mas parecido"],
        "candidatos": {"temas": 3},
        "elige": "palabra clave de la FAQ compartida, menos el vocabulario de productos; Jev confirma lo dudoso",
        "puntajes": ["banco_pruebas/flujo/grabado/nexo_tema_puntajes.json",
                     "banco_pruebas/flujo/grabado/nexo_tema_dudoso.jsonl"],
    },
    "producto nombrado": {
        "archivo": "banco_pruebas/flujo/nexo_nombrado.py",
        "consulta": "busqueda",
        "indice": ["el mismo de rubro y producto, sin vectores nuevos: da el rubro",
                   "palabra exacta: marca, nombre de modelo y codigo del catalogo en ese rubro"],
        "candidatos": {"rubros": 1},
        "elige": "el rubro donde calzan mas palabras de identidad, con marca o codigo exacto, y los embeddings "
                 "desempatan; despues la identidad de produccion, `catalogo._identificar`: exists, ambiguous, not_found",
        "puntajes": ["banco_pruebas/flujo/grabado/flujo_nuevo_puntajes.json",
                     "banco_pruebas/flujo/grabado/nexo_nombrado_puntajes.json"],
    },
    "condicion": {
        "archivo": "banco_pruebas/flujo/nexo_condicion.py",
        "consulta": "cada parte de la busqueda que el codigo no ato, con el rubro adelante: \"mouse: economico\"",
        "indice": ["cada campo del rubro elegido, su etiqueta de `specs_preguntables` y sus valores; y dos ordenes, "
                   "precio y peso, `nexo_condicion.docs_campo`"],
        "candidatos": {"campos": 3},
        "variante": "V2 segmento con rubro, documento por campo",
        "elige": "primero el codigo, sin modelo: el tope de plata; el numero con su unidad contra los campos que miden "
                 "en ella, si no hay ninguno no se ata; el valor de un campo con plural, genero y negacion; el campo de "
                 "si o no por su clave; el orden. Lo que queda lo confirma Jev entre los valores reales de los tres "
                 "campos, los ordenes, solo producto o ninguno, que es no se ata. Lo que vale para todo el rubro se "
                 "saca; lo atado sin ningun producto con stock es no hay",
        "calibrado": "16-nov, `nexo_condicion.py --calibrar` con Jev perfecto: V1, V2 y V3 dan 150 de 188 en las 140; "
                     "V2 con 3 candidatos, la elegida. La busqueda no es el cuello: el codigo solo da 144. V4, un "
                     "documento por valor, con la paga: 151 con 2 candidatos, una linea mas, no alcanza para cambiar",
        "puntajes": ["banco_pruebas/flujo/grabado/nexo_condicion_puntajes.json",
                     "banco_pruebas/flujo/grabado/nexo_condicion_jev.jsonl"],
    },
}


# ══ EL CACHE ═════════════════════════════════════════════════════════════════
# Dos archivos que crecen de a lote: las claves, una por linea, y los vectores en float64 seguidos. Lo ya guardado no se
# reescribe. Un proceso tiene un solo cache en memoria: todos los pasos de una corrida comparten lo pedido.
_MEMORIA = {}
_GUARDADAS = set()
_DEL_INDICE = set()


def _leer_indice():
    if not os.path.exists(INDICE) or os.environ.get("EMB_SIN_INDICE"):
        return {}
    d = json.load(gzip.open(INDICE, "rt", encoding="utf-8"))
    v = array.array("f")
    v.frombytes(base64.b64decode(d["f32"]))
    n = d["dimension"]
    return {f"{DOCUMENTO}|{t}": v[i * n:(i + 1) * n].tolist() for i, t in enumerate(d["textos"])}


def cargar():
    """{"TAREA|texto": vector}: el indice de la tienda del repo y lo pedido en la sesion. Lo de la sesion manda: tiene
    la precision entera que devolvio la API."""
    if not _MEMORIA:
        indice = _leer_indice()
        _MEMORIA.update(indice)
        _DEL_INDICE.update(indice)
        if os.path.exists(CACHE + ".claves"):
            claves = [json.loads(x) for x in open(CACHE + ".claves", encoding="utf-8")]
            v = array.array("d")
            v.frombytes(open(CACHE + ".f64", "rb").read())
            n = len(v) // max(len(claves), 1)
            for i, k in enumerate(claves):
                _MEMORIA[k] = v[i * n:(i + 1) * n].tolist()
            _GUARDADAS.update(claves)
            _DEL_INDICE.difference_update(claves)
    return _MEMORIA


def guardar(cache):
    """Agrega al cache del disco lo pedido que todavia no esta. Lo que vino del indice del repo no: es float32."""
    nuevas = [k for k in cache if k not in _GUARDADAS and k not in _DEL_INDICE]
    if not nuevas:
        return
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE + ".f64", "ab") as fv, open(CACHE + ".claves", "a", encoding="utf-8") as fk:
        for k in nuevas:
            fv.write(array.array("d", cache[k]).tobytes())
            fk.write(json.dumps(k, ensure_ascii=False) + "\n")
    _GUARDADAS.update(nuevas)


# ══ LA UNICA FUNCION QUE PIDE VECTORES ═══════════════════════════════════════
def _anotar_paga(textos):
    """Los vectores con la paga, en `libro_paga.jsonl`: unos cuatro caracteres por token, a 0,15 dolares el millon."""
    from banco_pruebas import libro_paga as LP
    tok = sum(len(t) for t in textos) // 4 + 1
    with open(LP.LIBRO, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"dia": LP._hoy(), "hora": datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S"),
                             "modelo": MODELO, "entrada": tok, "salida": 0,
                             "dolares": round(tok * USD_POR_MILLON / 1e6, 6), "proceso": os.getpid()}) + "\n")


def _lote(textos, tarea, clave):
    body = json.dumps({"requests": [{"model": f"models/{MODELO}", "content": {"parts": [{"text": t}]}, "taskType": tarea}
                                    for t in textos]}).encode()
    req = urllib.request.Request(URL, data=body, headers={"x-goog-api-key": clave, "Content-Type": "application/json"})
    out = []
    for x in json.load(urllib.request.urlopen(req, timeout=120))["embeddings"]:
        nrm = math.sqrt(sum(v * v for v in x["values"])) or 1
        out.append([v / nrm for v in x["values"]])
    return out


def pedir(textos, tarea, cache, callado=False):
    """Los vectores de `textos` con la tarea dada, pidiendo a la API solo los que no estan en `cache`, que se completa
    y se guarda despues de cada lote. Con la paga, de a cien y anotado; con la gratis, de a cuarenta con pausa."""
    falta = [t for t in dict.fromkeys(textos) if t and f"{tarea}|{t}" not in cache]
    if falta:
        paga = bool(os.environ.get("MARTIN_AUTORIZO_LA_PAGA"))
        if paga:
            from banco_pruebas import libro_paga as LP
            LP.puede()
        clave = os.environ["GEMINI_API_KEY_PROD" if paga else "GEMINI_API_KEY"].split()[0]
        n = 100 if paga else 40
        for i in range(0, len(falta), n):
            parte = falta[i:i + n]
            for intento in range(8):
                try:
                    for t, v in zip(parte, _lote(parte, tarea, clave)):
                        cache[f"{tarea}|{t}"] = v
                    break
                except urllib.error.HTTPError as e:
                    if e.code not in (429, 500, 502, 503) or intento == 7:
                        raise
                    print(f"  {tarea}: {e.code}, espero {30 * (intento + 1)} s", flush=True)
                    time.sleep(30 * (intento + 1))
            if paga:
                _anotar_paga(parte)
            elif i + n < len(falta):
                time.sleep(25)
            guardar(cache)
        if not callado:
            print(f"  vectores nuevos {tarea}: {len(falta)}, {sum(len(t) for t in falta)} caracteres, "
                  f"{'con la paga' if paga else 'con la gratis'}", flush=True)
    return [cache[f"{tarea}|{t}"] for t in textos]


# ══ EL INDICE DE LA TIENDA ═══════════════════════════════════════════════════
def indice_tienda():
    """[(indice, texto)]: los documentos de la tienda que usan los nexos vivos, con los mismos constructores que ellos."""
    import nexo_condicion as NC
    import nexo_rubro as NR
    import nexo_tema as NT
    _, alias, rubros, modelos = NR.fuente()
    out = [("rubros", d) for _, d in NR.indice_rubros(rubros, alias)]
    out += [("productos", NR.doc_producto(k, modelos[k], alias)) for k in modelos]
    out += [("temas", a) for _, a in NT.docs(*NT.fuente())]
    fx = NC.Fuente()
    out += [("condicion", d) for r in fx.campos for _, d in NC.docs_campo(r, fx)]
    return list(dict.fromkeys(out))


def rehacer_indice():
    docs = indice_tienda()
    textos = list(dict.fromkeys(t for _, t in docs))
    cache = cargar()
    vs = pedir(textos, DOCUMENTO, cache)
    v = array.array("f", [x for vec in vs for x in vec])
    d = {"modelo": MODELO, "tarea": DOCUMENTO, "dimension": len(vs[0]), "normalizado": True,
         "cuando": time.strftime("%Y-%m-%d"), "textos": textos, "f32": base64.b64encode(v.tobytes()).decode()}
    os.makedirs(VECTORES, exist_ok=True)
    with gzip.open(INDICE, "wt", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False)
    por = {}
    for k, _ in docs:
        por[k] = por.get(k, 0) + 1
    print(f"indice de la tienda: {len(textos)} documentos, {', '.join(f'{k} {n}' for k, n in por.items())}; "
          f"{os.path.getsize(INDICE) // 1024} KB")


def registro():
    print(f"embeddings: {MODELO}, consultas {CONSULTA}, indices {DOCUMENTO}; dimension completa, normalizados; "
          "un pedido por mensaje")
    print(f"  cache de la sesion  {os.path.relpath(CACHE)}")
    print(f"  indice de la tienda {os.path.relpath(INDICE)}" + ("" if os.path.exists(INDICE) else ", falta: --indice"))
    for nombre, x in NEXOS.items():
        print(f"\n{nombre.upper()} · {x['archivo']}")
        print(f"  consulta    {x['consulta']}")
        for i in x["indice"]:
            print(f"  indice      {i}")
        if x["candidatos"]:
            print("  candidatos  " + ", ".join(f"{v} {k}" for k, v in x["candidatos"].items()))
        print(f"  elige       {x['elige']}")
        if x.get("calibrado"):
            print(f"  calibrado   {x['calibrado']}")
        for p in x["puntajes"]:
            print(f"  puntajes    {p}")


if __name__ == "__main__":
    if "--indice" in sys.argv:
        rehacer_indice()
    else:
        registro()
