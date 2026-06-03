"""
ANCLAJE DEL INTERPRETADOR AL CATALOGO.

El Interpretador con LLM entiende el lenguaje del cliente y corrige typos, pero
NO ve el catalogo: sus candidatos los inventa el modelo y a veces no existen.
Esta capa aterriza esa interpretacion a la fuente de verdad usando LA MISMA
busqueda que la herramienta de productos (buscar_con_score, en app/storage/
search.py). Asi el Interpretador y el Solver comparten criterio y, cuando se
agreguen embeddings, los dos lo aprovechan.

Decision por puntaje del catalogo, no por listas fijas, asi escala a catalogos
chicos y grandes:
- Compuerta: solo anclamos si el modelo entendio que el mensaje habla de un
  producto (dio producto_resuelto o candidatos). Evita enganchar productos en
  consultas de FAQ, saludos o cierres.
- Un producto domina el puntaje -> se resuelve a ese (producto_resuelto real).
- Pocos empatados (2 a 4) -> candidatos REALES y se pide elegir, bajando la
  confianza para que el bot pregunte.
- Muchos empatados (5 o mas) -> es una exploracion de categoria, no se fuerza
  nada: lo maneja el Solver mostrando opciones.
- Nada matchea -> se limpian los candidatos inventados.

El LLM dice que quiere el cliente; el codigo lo aterriza a productos reales.
Detras del flag INTERPRETE_ANCLA_CATALOGO. Apagado, no se invoca.
"""
from app.storage.search import buscar_con_score

# Si hay mas de este numero de productos empatados arriba, es exploracion de
# categoria, no una referencia a un producto puntual. Vale para cualquier
# tamaño de catalogo: no se le pregunta a alguien entre diez opciones.
MAX_OFRECER = 4
# Un producto cuenta como empatado con el mejor si su puntaje llega a esta
# fraccion del puntaje top. Relativo, asi no depende de la escala del score.
UMBRAL_CERCANIA = 0.8


def anclar_items(resultado: dict, productos: list[dict]) -> dict:
    """Ancla cada item de la interpretacion rica (Defensa 1) al catalogo. Si la
    referencia de un item resuelve a UN producto dominante por puntaje, le setea
    producto_resuelto, le sube la confianza y lo saca de ambiguedades. Si matchea
    varios o ninguno, lo deja ambiguo. Asi un producto nombrado exacto deja de
    disparar la confirmacion, y una referencia vaga la sigue disparando. Mismo
    criterio de cercania que anclar_a_catalogo."""
    if not productos:
        return resultado
    items = resultado.get("items") or []
    amb = resultado.get("ambiguedades") or []
    for i, it in enumerate(items):
        if it.get("producto_resuelto"):
            continue
        ref = str(it.get("referencia") or "").strip()
        if not ref:
            continue
        scored = buscar_con_score(ref, productos)
        if not scored:
            continue
        top = scored[0][0]
        cercanos = [p for s, p in scored if s >= top * UMBRAL_CERCANIA]
        if len(cercanos) == 1:
            it["producto_resuelto"] = cercanos[0]["nombre"]
            it["confianza"] = 0.9
            clave = f"items[{i}]"
            if clave in amb:
                amb.remove(clave)
    resultado["ambiguedades"] = amb
    return resultado


def anclar_a_catalogo(resultado: dict, mensaje: str, productos: list[dict],
                      umbral_alta: float = 0.85) -> dict:
    """Aterriza la interpretacion del LLM al catalogo real. Muta y devuelve
    resultado. Si no hay con que anclar, lo deja igual."""
    if not productos:
        return resultado

    # Compuerta: el modelo tiene que haber visto un producto en el mensaje.
    if not (resultado.get("producto_resuelto") or resultado.get("candidatos")):
        return resultado

    # La query sale de lo que el modelo estructuro (producto o candidatos), que
    # ya viene con los typos corregidos. La busqueda contra el catalogo decide
    # cuantos productos reales corresponden.
    query = resultado.get("producto_resuelto") or " ".join(
        resultado.get("candidatos") or [])
    if not query.strip():
        return resultado

    scored = buscar_con_score(query, productos)
    if not scored:
        # Nada real matcheo: limpiamos los candidatos inventados por el modelo.
        resultado["candidatos"] = []
        resultado["producto_resuelto"] = None
        return resultado

    # Guarda de pedido compuesto: si el CLIENTE nombra dos o mas categorias del
    # catalogo en el mensaje (ej "combo teclado mouse y auriculares", o "sillas y
    # monitores"), no es una referencia a un producto unico, es un pedido de
    # varios. No resolvemos: lo maneja el Solver. Las categorias se derivan del
    # catalogo en vivo, sin lista fija, asi escala a cualquier catalogo.
    cats_catalogo = {str(p.get("categoria", "")).lower() for p in productos}
    msg_n = mensaje.lower()
    cats_en_mensaje = {c for c in cats_catalogo if c and c in msg_n}
    if len(cats_en_mensaje) >= 2:
        resultado["producto_resuelto"] = None
        resultado["candidatos"] = []
        return resultado

    top = scored[0][0]
    cercanos = [p for s, p in scored if s >= top * UMBRAL_CERCANIA]
    n = len(cercanos)

    def _ofrecer(nombres):
        # El anclaje NO fuerza al solver a presentar opciones: cuando no hay un
        # producto unico claro, deja candidatos reales como pista y baja la
        # confianza, pero NO setea ofrecer_opciones. El solver hace su propia
        # busqueda y lista bien por su cuenta. Esto evita que un match flojo del
        # anclaje, ej una frase vaga que engancha una lampara, se filtre como
        # opcion A o B a la respuesta final. Resolvemos uno o nos quedamos en
        # silencio; ofrecer es trabajo del solver.
        resultado["producto_resuelto"] = None
        resultado["candidatos"] = nombres
        if resultado.get("confianza", 0) >= umbral_alta:
            resultado["confianza"] = round(umbral_alta - 0.05, 2)

    if n == 1:
        # Un producto real domina: lo resolvemos.
        resultado["producto_resuelto"] = cercanos[0]["nombre"]
        resultado["candidatos"] = []
    elif n <= MAX_OFRECER:
        # Pocos reales empatados: candidatos REALES y pedir elegir.
        _ofrecer([p["nombre"] for p in cercanos])
    else:
        # Muchos empatados. Si el cliente dio un termino DISCRIMINANTE (marca,
        # atributo, modelo) ademas de la categoria, ofrecemos los 3 mejores en
        # vez de rendirnos. Si solo nombro una categoria suelta, es exploracion
        # y la maneja el Solver listando.
        toks = [t for t in query.lower().split()
                if len(t) >= 3 and t not in cats_catalogo
                and t not in {"para", "con", "que", "los", "las", "una", "del"}]
        if toks:
            _ofrecer([p["nombre"] for _, p in scored[:3]])
        else:
            resultado["producto_resuelto"] = None
            resultado["candidatos"] = []

    return resultado
