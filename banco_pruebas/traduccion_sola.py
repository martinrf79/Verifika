"""LA TRADUCCION SOLA Y LA ATADURA — la primera llamada sin etiquetar nada, 23-oct, pedido de Martin.

La entrevista de la traduccion mostro que el modelo traduce bien de cabeza y que la lista cerrada de la tienda lo puede
forzar: "que no haga quilombo de ruido" termino en "teclado membrana" porque silencioso no esta en la lista. Cuando la
lista va en el esquema que la API de Google hace cumplir, el modelo no puede contestar otra cosa: eso es la atadura.

Cada frase se traduce sola, una llamada por frase, a lo que pide en nombres de la tienda: clase de producto, regla,
caracteristica u orden. Cinco variantes, la misma consigna:
  libre      los nombres de la tienda en la consigna, la respuesta en JSON sin esquema: nada lo obliga.
  atado      los nombres como lista cerrada del esquema: la API no deja contestar otra cosa.
  salida     la lista cerrada mas "otro", con la palabra del cliente al lado.
  razon      salida, con un campo primero donde escribe como lo penso.
  ejemplos   salida, con veinte frases resueltas que no son de la prueba.

Lo correcto, escrito antes de correr y sin pasar por `alias.json`: las 14 frases de la entrevista, y de `cobertura.py`
los rubros dichos por razonamiento y con errores de tipeo, y los temas dichos de costado.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> TOPE_CORRIDA=0.30 python3 banco_pruebas/traduccion_sola.py [--ver] [variante ...]
"""
import asyncio
import collections
import os
import sys

ARGS = sys.argv[1:]
VER = "--ver" in ARGS
sys.argv = [sys.argv[0]]
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import cobertura as CO  # noqa: E402  — el entorno y los casos escritos a mano
import entrevista_traduccion as EN  # noqa: E402
from banco_pruebas import libro_paga  # noqa: E402
from app.core import agente  # noqa: E402
from app.core.flujo import catalogo as K  # noqa: E402
from app.core.flujo import interprete  # noqa: E402

TID = "verifika_prod"
TOPE = float(os.environ.get("TOPE_CORRIDA", "0.30"))
VARIANTES = ("libre", "atado", "salida", "razon", "ejemplos")
ORDENES = ["el mas barato", "el mas caro"]
OTRO = "otro"


def nombres() -> dict:
    from app.core.filtros_catalogo import campos_filtrables
    i = agente.indice(TID)
    return {"clases de producto": sorted(i["rubros"]),
            "reglas de la tienda": [t.replace("_", " ") for t in i["temas"]],
            "caracteristicas": [c.replace("_", " ") for c in campos_filtrables(TID)
                                if c not in ("descripcion", "nombre", "modelo", "precio_ars")],
            "ordenes": ORDENES}


# ══ LOS CASOS, con lo que vale ═══════════════════════════════════════════════

def casos() -> list:
    """(id, frase, lo que vale): cada cosa que vale es un nombre de la tienda o, para una condicion, palabras."""
    out = []
    de_la_entrevista = {
        "rubro mouse": {"mouse"}, "rubro auriculares": {"auriculares"}, "rubro cooler": {"cooler"},
        "rubro ssd": {"ssd"}, "rubro router": {"router"}, "rubro monitor": {"monitor"}, "rubro webcam": {"webcam"},
        "rubro fuente": {"fuente"}, "orden: el mas barato": {"el mas barato"}, "orden: el mas caro": {"el mas caro"},
        "condicion: silencioso": {"silencioso", "silencio", "silent", "ruido"},
        "condicion: liviano, por el peso": {"liviano", "peso gramos", "peso"},
        "tema de la tienda: producto defectuoso o garantia": {"defectuoso", "garantia", "cambios", "devoluciones"},
        "tema de la tienda: plazo de envio o envio urgente": {"plazo envio", "envio urgente", "envios",
                                                              "seguimiento pedido"},
    }
    for n, (f, c) in enumerate(EN.FRASES, 1):
        out.append((f"E{n:02}", f, de_la_entrevista[c]))
    for rub, _simple, razon, tipeo in CO.RUBROS:
        out.append((f"R {rub} razonamiento", razon, {rub}))
        out.append((f"R {rub} tipeo", tipeo, {rub}))
    for temas, _directa, costado in CO.TEMAS:
        out.append((f"T {'/'.join(sorted(temas))}", costado, {t.replace("_", " ") for t in temas}))
    return out


# ══ LA LLAMADA ═══════════════════════════════════════════════════════════════

CONSIGNA = """Sos el traductor de una tienda online de tecnologia de Argentina que vende por WhatsApp. No le contestas al
cliente: pasas lo que dice a los nombres con que la tienda nombra sus cosas, para que el codigo busque. Por cada cosa
que pide la frase devolve su "tipo" —clase de producto, regla de la tienda, caracteristica u orden— y su "nombre".
{reglas}
Asi nombra la tienda sus cosas:
{lista}{ejemplos}
Devolve SOLO el JSON: {forma}"""

REGLA_LIBRE = "Usa el nombre de la tienda que corresponda; si ninguno corresponde, la palabra del cliente."
REGLA_ATADO = "El nombre es uno de los de la tienda."
REGLA_SALIDA = ('El nombre es uno de los de la tienda; si ninguno corresponde, "otro", y en "palabra" la palabra del '
                'cliente. Nunca fuerces un nombre que no es.')

# Frases resueltas que no son de la prueba: otras formas, otros rubros y otras reglas.
EJEMPLOS = [
    ("lo que se enchufa a la pared para que el celu tenga bateria", "clase de producto", "cargador"),
    ("el coso donde va todo adentro de la compu, con vidrio", "clase de producto", "gabinete"),
    ("algo para pasar las fotos de la camara a papel", "clase de producto", "impresora"),
    ("una compu que pueda llevar a la facu", "clase de producto", "notebook"),
    ("para que mi voz se escuche clarita en el stream", "clase de producto", "microfono"),
    ("la placa grande donde se enchufa todo", "clase de producto", "motherboard"),
    ("una pantalla tactil para que los chicos miren videos", "clase de producto", "tablet"),
    ("lo que hace que los juegos se vean fluidos", "clase de producto", "placa de video"),
    ("algo para poner musica en el asado", "clase de producto", "parlante"),
    ("lo mas economico, que la cosa esta brava", "orden", "el mas barato"),
    ("lo top de gama, sin mirar precio", "orden", "el mas caro"),
    ("que aguante si se moja", "caracteristica", "resistencia agua"),
    ("que ande sin cable", "caracteristica", "conexion"),
    ("que tenga luces de colores", "caracteristica", "retroiluminacion"),
    ("que la marca no sea china", "caracteristica", "pais marca"),
    ("que sea comodo para las manos chicas", "caracteristica", "otro: comodo para manos chicas"),
    ("¿me hacen factura A?", "regla de la tienda", "factura"),
    ("¿puedo pagar en varias veces?", "regla de la tienda", "cuotas"),
    ("¿si no me gusta lo puedo devolver?", "regla de la tienda", "devoluciones"),
    ("¿se puede retirar por el local?", "regla de la tienda", "retiro local"),
]


def consigna(v: str) -> str:
    n = nombres()
    lista = "\n".join(f"- {k}: {', '.join(vs)}" for k, vs in n.items())
    forma = ('{"razon": "como lo pensaste, en una oracion", "pide": [{"tipo": "...", "nombre": "...", "palabra": "..."}]}'
             if v == "razon" else '{"pide": [{"tipo": "...", "nombre": "...", "palabra": "..."}]}')
    ej = ("\nEJEMPLOS:\n" + "\n".join(
        f'- "{f}" -> {t}: ' + (f'otro, palabra "{n.split(": ", 1)[1]}"' if n.startswith("otro") else n)
        for f, t, n in EJEMPLOS)) if v == "ejemplos" else ""
    reglas = {"libre": REGLA_LIBRE, "atado": REGLA_ATADO}.get(v, REGLA_SALIDA)
    return CONSIGNA.format(reglas=reglas, lista=lista, ejemplos=ej, forma=forma)


def formato(v: str) -> dict:
    if v == "libre":
        return {"type": "json_object"}
    n = nombres()
    todos = sorted({x for vs in n.values() for x in vs}) + ([OTRO] if v != "atado" else [])
    item = {"type": "object", "required": ["tipo", "nombre", "palabra"], "properties": {
        "tipo": {"type": "string", "enum": ["clase de producto", "regla de la tienda", "caracteristica", "orden"]},
        "nombre": {"type": "string", "enum": todos}, "palabra": {"type": "string"}}}
    props = {"pide": {"type": "array", "items": item}}
    req = ["pide"]
    if v == "razon":
        props = {"razon": {"type": "string"}, **props}
        req = ["razon", "pide"]
    return {"type": "json_schema", "json_schema": {"name": "traduccion", "schema": {
        "type": "object", "required": req, "properties": props}}}


async def traducir(v: str, frase: str) -> list:
    msgs = [{"role": "system", "content": consigna(v)}, {"role": "user", "content": f"FRASE: {frase}"}]
    r = interprete._json(await interprete._pedir(msgs, "traduccion_sola", formato(v)))
    return [p for p in r.get("pide") or [] if isinstance(p, dict)]


def vale(pide: list, valen: set) -> bool:
    """Bien si algun nombre es lo que vale, o si el nombre es "otro" y la palabra del cliente lo dice."""
    for p in pide:
        nombre, palabra = K.n(p.get("nombre") or "").strip(), K.n(p.get("palabra") or "")
        for v in map(K.n, valen):
            if nombre == v or (len(v) > 3 and v in nombre) or (nombre in (OTRO, "") and v in palabra):
                return True
    return False


def main() -> None:
    elegidas = [v for v in ARGS if v in VARIANTES] or list(VARIANTES)
    desde = libro_paga.gastado(libro_paga._hoy())
    nota = collections.defaultdict(collections.Counter)
    faltas = collections.defaultdict(list)
    for v in elegidas:
        for cid, frase, valen in casos():
            if libro_paga.gastado(libro_paga._hoy()) - desde >= TOPE:
                print(f"TOPE de la corrida: {TOPE} dolares")
                break
            pide = asyncio.run(traducir(v, frase))
            grupo = cid[0]
            ok = vale(pide, valen)
            nota[v][(grupo, "casos")] += 1
            nota[v][(grupo, "bien")] += ok
            if not ok:
                faltas[v].append((cid, frase, sorted(valen), [(p.get("nombre"), p.get("palabra")) for p in pide]))
    if VER:
        for v in elegidas:
            print(f"\n=== {v}: lo que no salio")
            for cid, frase, valen, pide in faltas[v]:
                print(f"  {cid}: {frase[:80]}\n      vale {valen} · dio {pide}")
    print("\nLA TRADUCCION SOLA: E, las 14 de la entrevista; R, rubros por razonamiento y tipeo; T, temas de costado")
    for v in elegidas:
        print(f"  {v:9} " + " · ".join(f"{g} {nota[v][(g, 'bien')]} de {nota[v][(g, 'casos')]}" for g in "ERT")
              + f" · total {sum(nota[v][(g, 'bien')] for g in 'ERT')} de {sum(nota[v][(g, 'casos')] for g in 'ERT')}")
    print(f"Gasto: {libro_paga.gastado(libro_paga._hoy()) - desde:.3f} dolares")


if __name__ == "__main__":
    main()
