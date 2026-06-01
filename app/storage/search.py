"""
Búsqueda híbrida de productos:
1. Búsqueda por keywords (rápida, exacta) sobre nombre, categoría, descripción.
2. Búsqueda semántica con embeddings (entiende sinónimos y conceptos).
3. Combina y devuelve los TOP-N más relevantes.

Diseño escalable:
- Filtra primero por categoría (índice natural) si está disponible → reduce el universo.
- Usa keyword match con score por aparición en nombre > categoría > descripción.
- Si hay embedding de la query y de los productos, ordena por similitud coseno.
- Devuelve TOP-N (default 10).

Para 100 productos: instantáneo.
Para 5.000 productos: ~50ms (cargados en cache local).
Para 50.000 productos: hay que mover a búsqueda con índice (Algolia, Pinecone, etc).
"""
from app.storage.firestore_client import get_all_products
from app.storage.embeddings import generate_embedding, cosine_similarity
from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)

DEFAULT_TOP_N = 10


def hybrid_search(query: str | None = None,
                  categoria: str | None = None,
                  precio_min: int | None = None,
                  precio_max: int | None = None,
                  top_n: int = DEFAULT_TOP_N,
                  tienda_id: str | None = None) -> list[dict]:
    """
    Búsqueda híbrida de productos. Devuelve hasta top_n más relevantes.
    """
    productos = get_all_products(tienda_id=tienda_id)

    # 1) Filtros duros (categoría, precio)
    candidatos = productos
    if categoria:
        cat_lower = categoria.lower().strip()
        candidatos = [p for p in candidatos if p.get("categoria", "").lower() == cat_lower]

    if precio_min is not None:
        candidatos = [p for p in candidatos if p.get("precio_ars", 0) >= precio_min]

    if precio_max is not None:
        candidatos = [p for p in candidatos if p.get("precio_ars", 0) <= precio_max]

    # Si no hay query de texto, devolvemos los primeros top_n por nombre
    if not query or not query.strip():
        return sorted(candidatos, key=lambda p: p.get("nombre", ""))[:top_n]

    q = query.lower().strip()

    # 2) Score por keyword match (rápido, no requiere LLM)
    scored: list[tuple[float, dict]] = []
    for p in candidatos:
        score = _keyword_score(p, q)
        if score > 0:
            scored.append((score, p))

    # 3) Si hay productos con embeddings, agregamos score semántico
    semantic_used = False
    if scored:
        # Solo intentamos semántica si tenemos al menos algunos resultados de keyword
        productos_con_embedding = [p for _, p in scored if p.get("embedding")]
        if len(productos_con_embedding) > 0:
            query_emb = generate_embedding(q)
            if query_emb:
                semantic_used = True
                # Re-scoreamos: 60% keyword + 40% semántica
                rescored = []
                for kw_score, p in scored:
                    sem_score = 0.0
                    if p.get("embedding"):
                        sem_score = cosine_similarity(query_emb, p["embedding"])
                    final_score = 0.6 * (kw_score / 10.0) + 0.4 * sem_score
                    rescored.append((final_score, p))
                scored = rescored
    else:
        # No hubo match de keyword. Probemos solo semántica si hay embeddings.
        productos_con_embedding = [p for p in candidatos if p.get("embedding")]
        if productos_con_embedding:
            query_emb = generate_embedding(q)
            if query_emb:
                semantic_used = True
                for p in productos_con_embedding:
                    sem_score = cosine_similarity(query_emb, p["embedding"])
                    if sem_score > 0.3:  # umbral mínimo
                        scored.append((sem_score, p))

    log.info("hybrid_search_done",
             query=q[:50], categoria=categoria,
             total_candidatos=len(candidatos),
             encontrados=len(scored),
             semantic_used=semantic_used)

    # 4) Ordenar por score descendente y devolver top_n
    scored.sort(key=lambda t: t[0], reverse=True)
    return [p for _, p in scored[:top_n]]


def buscar_con_score(query: str | None,
                     productos: list[dict]) -> list[tuple[float, dict]]:
    """
    Igual que hybrid_search pero sobre una lista de productos YA dada (no relee
    Firestore) y devuelve [(score, producto)] ordenado de mayor a menor.

    Comparte el scoring con hybrid_search via _keyword_score, asi la busqueda de
    productos y el anclaje del Interpretador usan el MISMO criterio. Cuando se
    agreguen embeddings (flag), el blend semantico entra aca igual que en
    hybrid_search, y los dos caminos lo aprovechan sin duplicar logica.

    Lo usa el anclaje del Interpretador para decidir, por el catalogo y no por el
    modelo, si una referencia resuelve a un producto unico o a varios. Escala a
    catalogos chicos y grandes porque la decision sale de los puntajes, no de una
    lista fija de categorias.
    """
    if not query or not query.strip():
        return []
    q = query.lower().strip()
    pares: list[list] = []  # [score, producto] (mutable para reescalar)
    for p in productos:
        s = _keyword_score(p, q)
        if s > 0:
            pares.append([s, p])

    # Blend semantico (flag EMBEDDINGS_ON). Mezcla palabras 60% + significado
    # 40%, igual que hybrid_search. Suma tambien productos que NO matchearon por
    # palabras pero estan semanticamente cerca, para cubrir sinonimos.
    s = get_settings()
    if s.EMBEDDINGS_ON and any(p.get("embedding") for p in productos):
        qemb = generate_embedding(q)
        if qemb:
            con_kw = {id(p) for _, p in pares}
            for par in pares:
                kw, p = par
                sem = cosine_similarity(qemb, p["embedding"]) if p.get("embedding") else 0.0
                par[0] = 0.6 * (kw / 10.0) + 0.4 * sem
            for p in productos:
                if p.get("embedding") and id(p) not in con_kw:
                    sem = cosine_similarity(qemb, p["embedding"])
                    if sem > 0.45:
                        pares.append([0.4 * sem, p])

    pares.sort(key=lambda t: t[0], reverse=True)
    return [(score, p) for score, p in pares]


def _keyword_score(producto: dict, query_lower: str) -> float:
    """
    Score simple por aparición de la query en campos del producto.
    nombre > categoría > descripción.
    """
    score = 0.0
    nombre = producto.get("nombre", "").lower()
    categoria = producto.get("categoria", "").lower()
    desc = producto.get("descripcion", "").lower()

    # Match de la query completa pesa más
    if query_lower in nombre:
        score += 5.0
    if query_lower in categoria:
        score += 3.0
    if query_lower in desc:
        score += 2.0

    # Match de palabras individuales de la query
    palabras = [w for w in query_lower.split() if len(w) >= 3]
    for palabra in palabras:
        if palabra in nombre:
            score += 1.5
        elif palabra in categoria:
            score += 1.0
        elif palabra in desc:
            score += 0.5

    return score
