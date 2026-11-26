# Herramientas abiertas para entender el pedido del cliente y enlazarlo al catálogo, estado al 26-nov-2026

Nota de método. Estrellas, fecha del último push y licencia salen de la API de búsqueda de GitHub consultada el 26-nov-2026 por el conector; versiones y fechas de release salen de la API JSON de PyPI el mismo día; descargas, fechas y licencias de modelos salen de la API de Hugging Face el mismo día. En esta sesión arxiv.org y aclanthology.org no resolvían, así que las tablas de los papers no se leyeron completas: lo que viene de ahí sale de resúmenes del buscador y va marcado. Las notas previas de "Integración LLM y código 2026" ya cubren el patrón LLM a restricciones más filtro en código, Instacart, 2601.16492, la detección fuera de base de ACL 2026, Outlines, Instructor, XGrammar y Rasa; acá no se repiten y se apunta a herramientas concretas.

Regla de lectura de "activo": push o release en 2026 es activo; último release en 2025 sin actividad posterior se marca como frenado; anterior a 2025 se marca como viejo.

## 1. Modelos chicos y librerías de extracción, slot filling y clasificación de intención, 2025 y 2026

### Takeaway
La opción más práctica y viva para la llamada 0 es la familia GLiNER2 de Fastino: un modelo de 205M a 287M parámetros, multilingüe con español, que hace en una sola pasada entidades, clasificación con lista cerrada de etiquetas y extracción a JSON con campos de opciones fijas, en CPU, Apache 2.0, con release en PyPI del 20-nov-2026. SetFit sirve para clasificar línea a categoría con pocos ejemplos por clase, en CPU. NuExtract 2.0 es más preciso en extracción libre pero es un modelo de visión y lenguaje de 2B o más, que en la práctica pide GPU. No encontré números publicados de ninguno en español rioplatense ni en consultas de tienda.

### Cited Findings
GLiNER2 y GLiNER2.5, Fastino
- Repo fastino-ai/GLiNER2: 2.506 estrellas, último push 23-nov-2026, Apache-2.0, creado en julio de 2025 — [GitHub fastino-ai/GLiNER2](https://github.com/fastino-ai/GLiNER2)
- Paquete gliner2 versión 2.2.0 subido a PyPI el 20-nov-2026 — [PyPI gliner2](https://pypi.org/project/gliner2/)
- Une NER, clasificación de texto, extracción estructurada y relaciones en un modelo de 205M parámetros, con inferencia en CPU sin GPU — [HF fastino/gliner2-multi-v1](https://huggingface.co/fastino/gliner2-multi-v1)
- gliner2-multi-v1 declara seis idiomas, español incluido; 53.844 descargas, creado 4-dic-2025, modificado 28-sep-2026, Apache-2.0 — [HF fastino/gliner2-multi-v1](https://huggingface.co/fastino/gliner2-multi-v1)
- Línea GLiNER2.5 de arquitectura por bordes: small de 74M en inglés, base de 194M en inglés, multi de 287M sobre mDeBERTa-v3-base, presentado como el checkpoint multilingüe por defecto para entidades, clasificación, registros y relaciones; corre en CPU, CUDA o MPS con gliner2 con el extra local — [HF fastino/gliner2.5-multi-v1](https://huggingface.co/fastino/gliner2.5-multi-v1)
- gliner2.5-multi-v1: creado 14-ago-2026, 89.374 descargas; hay además GLiNER2.5-multi-Decide, de clasificación, creado 24-sep-2026 — [HF API fastino](https://huggingface.co/fastino)
- Funciones que calzan con el bot: campos con opciones cerradas, por ejemplo tipo con valores fijos, o choices en el constructor del esquema; umbral global y por campo; validadores por regex que filtran valores; puntajes de confianza y posiciones del texto; extracción en lote; ajuste fino completo y adaptadores LoRA de 2 a 10 MB según el README, sin medición; cliente de API paga aparte. El README no reporta números de exactitud ni menciona ONNX — [GitHub fastino-ai/GLiNER2](https://github.com/fastino-ai/GLiNER2)
- Ejemplo del model card: de "iPhone 15 Pro Max with 256GB storage, A17 Pro chip, priced at $1199" saca nombre, almacenamiento, procesador y precio a JSON — [HF fastino/gliner2-multi-v1](https://huggingface.co/fastino/gliner2-multi-v1)
- Paper de demo en EMNLP 2025, arXiv 2507.18546. Según el resumen del buscador, en CPU GLiNER2 tiene latencia de clasificación comparable a GLiClass, unas 2,6 veces más rápido que GPT-4o por API, y el zero-shot con DeBERTa por NLI es unas 6,8 veces más lento a 20 etiquetas porque hace una pasada por etiqueta. Una cifra de terceros de menos de 200 ms para hasta 50 etiquetas en CPU no está confirmada en el paper — [arXiv 2507.18546](https://arxiv.org/pdf/2507.18546); [ACL Anthology EMNLP demos](https://aclanthology.org/2025.emnlp-demos.10)

GLiNER original y variantes multilingües
- urchade/GLiNER: 4.298 estrellas, push 11-nov-2026, Apache-2.0; paquete gliner 0.2.30 del 31-oct-2026 — [GitHub urchade/GLiNER](https://github.com/urchade/GLiNER); [PyPI gliner](https://pypi.org/project/gliner/)
- knowledgator/gliner-x-base y large: backbone mT5, 20 idiomas con español, entrenados con datos sintéticos anotados por LLM sobre Fineweb-2; Apache-2.0; modificados 29-abr-2026. Tabla F1 propia: large de 0,75 a 0,88 en daneses, alemán, inglés, portugués y sueco, frente a 0,57 a 0,74 de gliner_multi-v2.1; no hay fila de español en la tabla — [HF knowledgator/gliner-x-base](https://huggingface.co/knowledgator/gliner-x-base)
- NuNER_Zero de NuMind: MIT, último cambio 26-feb-2025, frenado — [HF numind/NuNER_Zero](https://huggingface.co/numind/NuNER_Zero)

NuExtract 2.0, NuMind
- Familia para extracción estructurada, multimodal y multilingüe, basada en QwenVL: 2B sobre Qwen2-VL-2B con MIT, 4B sobre Qwen2.5-VL-3B con Qwen Research License no comercial, 8B sobre Qwen2.5-VL-7B con MIT — [HF numind/NuExtract-2.0-2B](https://huggingface.co/numind/NuExtract-2.0-2B)
- La plantilla JSON admite tipos enum, de opción única, y multi-label, con valores de una lista fija; también verbatim-string — [HF numind/NuExtract-2.0-2B](https://huggingface.co/numind/NuExtract-2.0-2B)
- El benchmark publicado es sobre unas 1.000 muestras variadas de texto e imagen, y sólo aparece como gráfico, sin cifras en texto — [HF numind/NuExtract-2.0-2B](https://huggingface.co/numind/NuExtract-2.0-2B)
- Repo numindai/nuextract: 273 estrellas, push 17-ago-2026, MIT; modelos modificados 19-may-2026 — [GitHub numindai/nuextract](https://github.com/numindai/nuextract)

SetFit y clasificadores de pocos ejemplos
- huggingface/setfit: 2.875 estrellas, push 17-nov-2026, Apache-2.0; release 1.2.0 del 4-sep-2026 — [GitHub huggingface/setfit](https://github.com/huggingface/setfit); [PyPI setfit](https://pypi.org/project/setfit/)
- El paper evaluó con 8 ejemplos por clase sobre el Multilingual Amazon Reviews Corpus usando paraphrase-multilingual-mpnet-base-v2, y supera a fine-tuning y a ADAPET en los tres regímenes de idioma; la tabla por idioma no se pudo leer — [arXiv 2209.11055](https://arxiv.org/pdf/2209.11055); [HF blog SetFit](https://huggingface.co/blog/setfit)
- Funciona con cualquier Sentence Transformer del Hub, multilingüe incluido — [HF Hub docs SetFit](https://huggingface.co/docs/hub/en/setfit)
- Bases multilingües vivas para SetFit o para embeddings: multilingual-e5-small, MIT, 93 idiomas, modificado 2-abr-2026; paraphrase-multilingual-mpnet-base-v2, Apache-2.0, 50 idiomas; mmBERT-base, MIT, julio de 2025 — [HF e5-small](https://huggingface.co/intfloat/multilingual-e5-small); [HF paraphrase-multilingual-mpnet](https://huggingface.co/sentence-transformers/paraphrase-multilingual-mpnet-base-v2); [HF mmBERT-base](https://huggingface.co/jhu-clsp/mmBERT-base)
- Zero-shot por NLI, alternativa vieja: mDeBERTa-v3-base-xnli-multilingual-nli-2mil7, MIT, 26 idiomas, último cambio abr-2024 — [HF MoritzLaurer mDeBERTa xnli](https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7)

spaCy, spacy-llm y Sparrow
- spaCy: 34.095 estrellas, push 21-nov-2026, MIT, versión 3.8.18 del 26-oct-2026 — [GitHub explosion/spaCy](https://github.com/explosion/spaCy); [PyPI spacy](https://pypi.org/project/spacy/)
- spacy-llm: 1.401 estrellas, push 23-oct-2026, último release 0.7.4 del 24-mar-2026; integra LLM en pipelines de spaCy para NER y clasificación — [GitHub explosion/spacy-llm](https://github.com/explosion/spacy-llm); [PyPI spacy-llm](https://pypi.org/project/spacy-llm/)
- katanaml/sparrow: 5.234 estrellas, push 26-nov-2026, GPL-3.0; orientado a extracción de documentos y visión, con vLLM — [GitHub katanaml/sparrow](https://github.com/katanaml/sparrow)

### Inferences
- GLiNER2 o GLiNER2.5-multi pueden hacer en local lo que hoy hace la llamada 0 en la parte de etiquetar: una clasificación con la lista cerrada de categorías de la tienda y campos con opciones cerradas para color, conectividad o marca, más el número del tope de precio como entidad. Lo que no hace es partir el mensaje en líneas por pedido con la misma soltura de un LLM; habría que probar si su extracción de listas de estructuras, varias "product" en un mensaje, alcanza para eso.
- Calza con la regla del repo de achicarle al modelo lo que falla seguido: la salida está acotada por esquema y el umbral da un "no sé" medible, que se puede mapear a ambiguous.
- Tamaño y despliegue: 205M a 287M parámetros entran en un contenedor Cloud Run con CPU; es estimación propia, no medida, que pide del orden de 1 a 2 GB de memoria y suma segundos de arranque en frío por cargar el modelo. Corre dentro del mismo servicio Python, sin servicio nuevo.
- NuExtract-2.0-2B, por ser un modelo de visión y lenguaje de 2B, en CPU de Cloud Run sería lento; es inferencia mía, sin medición encontrada. Encaja mejor como etiquetador offline para generar datos que como pieza en el camino vivo.
- SetFit es la ruta más barata para un clasificador línea a categoría si se juntan 8 a 30 ejemplos reales por categoría de las charlas grabadas del banco; corre en CPU y no agrega dependencia fuera de sentence-transformers.
- Sparrow es de documentos y facturas, no de chat; queda fuera del caso.

### Gaps
- No pude leer las tablas del paper de GLiNER2 por la red; faltan F1 de NER, exactitud de clasificación y latencias exactas. El README de GLiNER2 no publica exactitud, y la tabla de gliner-x no trae español.
- El benchmark de NuExtract 2.0 sólo está como imagen.
- No encontré ninguna medición pública de estas herramientas sobre consultas de compra en español, ni rioplatense.

## 2. Parseo de consultas de compra a filtros: texto a filtro y texto a SQL con validación, entender la consulta en comercio, extracción de atributos

### Takeaway
No encontré una librería abierta y viva dedicada a "consulta de compra en lenguaje natural a filtros validados" para Python. Lo más cercano listo para usar es la búsqueda en lenguaje natural de Typesense, desde la v29: un LLM convierte la consulta en filter_by, sort_by y q, Typesense la ejecuta y devuelve lo que interpretó. El resto se arma con extracción por esquema, GLiNER2 o NuExtract, más validación en código contra el catálogo, que es lo que el bot ya hace.

### Cited Findings
- Typesense Natural Language Search: envía la consulta a un LLM que genera filter_by, sort_by y q y ejecuta la búsqueda; ejemplo "Latest Ford under 40K$" a make:Ford y msrp menor a 40000 ordenado por año descendente; los filtros del LLM se combinan con AND con los filtros explícitos, así que los del código siempre mandan; la respuesta trae parsed_nl_query para depurar; el modelo se registra en el endpoint nl_search_models con prompt de sistema propio — [Typesense docs NL search](https://typesense.org/docs/guide/natural-language-search.html); [Typesense API 30.2](https://typesense.org/docs/30.2/api/natural-language-search.html)
- Un hilo de la comunidad de Typesense dice que lograr sintaxis válida de forma consistente depende de refinar el prompt — [Typesense threads](https://threads.typesense.org/t/29632151/hi-all-same-as-u05lnql0uq0-going-through-the-docs-for-the-na)
- Demo oficial de referencia con restaurantes — [GitHub typesense/showcase-natural-language-search-restaurants](https://github.com/typesense/showcase-natural-language-search-restaurants)
- typesense/typesense: 27.179 estrellas, push 24-nov-2026, GPL-3.0, servidor en C++ en memoria; cliente Python typesense 2.2.0 del 25-nov-2026 — [GitHub typesense/typesense](https://github.com/typesense/typesense); [PyPI typesense](https://pypi.org/project/typesense/)
- sqlglot, parser y validador de SQL en Python, versión 30.35.0 del 24-nov-2026; sirve para validar un filtro generado antes de ejecutarlo — [PyPI sqlglot](https://pypi.org/project/sqlglot/)
- Instructor 1.18.0 del 26-nov-2026 y Outlines 1.3.3 del 6-ago-2026 siguen activos; ya están cubiertos en las notas previas — [PyPI instructor](https://pypi.org/project/instructor/); [PyPI outlines](https://pypi.org/project/outlines/)

### Inferences
- El NL search de Typesense hace lo mismo que el bot con el LLM chico más filtro en código, pero mueve la traducción adentro de otro servidor. No resuelve lo difícil del caso, que es partir el mensaje en varios pedidos y decir "no lo vendemos". Para este bot no ahorra trabajo y suma un servicio.
- La pieza que vale tomar de Typesense es la idea, no el producto: devolver siempre la interpretación, parsed_nl_query, junto al resultado, y hacer AND con los filtros del código. El bot ya tiene el equivalente en memoria_agente y el verificador.
- Texto a SQL no aplica a un catálogo de cientos de filas en memoria; filtrar en Python sobre las filas ya es determinista y verificable.

### Gaps
- No encontré un repo abierto activo de "query understanding" de comercio con modelos publicados en español.
- No encontré mediciones de exactitud del NL search de Typesense.

## 3. Enlace de productos al catálogo: rerankers, búsqueda híbrida, interacción tardía, entity linking y detección fuera de catálogo

### Takeaway
Para un catálogo chico dentro del mismo servicio Python, lo que se puede sumar sin servicio nuevo es: bm25s para la parte léxica de modelos y códigos, RapidFuzz para nombres con errores, un reranker multilingüe chico de licencia comercial, como gte-multilingual-reranker-base de 306M o mxbai-rerank-base-v2, y fastembed o Model2Vec para embeddings rápidos en CPU. Los motores Typesense, Meilisearch, Qdrant y Weaviate están muy activos pero son servidores aparte. ReFinED y RAGatouille están frenados. No hay una herramienta abierta específica de detección fuera de catálogo.

### Cited Findings
Léxico y difuso
- xhluca/bm25s: 1.830 estrellas, push 13-nov-2026, MIT, versión 0.3.16 del 28-oct-2026; BM25 en Python con NumPy y Numba — [GitHub xhluca/bm25s](https://github.com/xhluca/bm25s); [PyPI bm25s](https://pypi.org/project/bm25s/)
- Speedup frente a rank-bm25 en un hilo de CPU, medido por los autores: ArguAna 573,91 contra 2,00 consultas por segundo, msmarco 12,20 contra 0,07; dicen hasta 500 veces — [bm25s.github.io](https://bm25s.github.io); [arXiv 2407.03618](https://arxiv.org/pdf/2407.03618)
- rank-bm25, la alternativa clásica, último release 0.2.2 de feb-2022, vieja — [PyPI rank-bm25](https://pypi.org/project/rank-bm25/)
- RapidFuzz: 4.221 estrellas, push 26-nov-2026, MIT, 3.14.6 del 30-ago-2026; comparación difusa de cadenas, Levenshtein y otras — [GitHub rapidfuzz/RapidFuzz](https://github.com/rapidfuzz/RapidFuzz); [PyPI rapidfuzz](https://pypi.org/project/rapidfuzz/)

Rerankers, con licencia
- gte-multilingual-reranker-base, Alibaba: 306M, más de 70 idiomas con español, hasta 8.192 tokens, Apache-2.0, modificado 21-nov-2026 — [HF gte-multilingual-reranker-base](https://huggingface.co/Alibaba-NLP/gte-multilingual-reranker-base)
- mxbai-rerank-base-v2, 0,5B, Apache-2.0, más de 100 idiomas; tabla propia: BEIR 55,57, multilingüe 28,56, latencia 0,67 s medida en A100 — [HF mxbai-rerank-base-v2](https://huggingface.co/mixedbread-ai/mxbai-rerank-base-v2)
- Qwen3-Reranker-0.6B, Apache-2.0, 1,2 millones de descargas, modificado abr-2026 — [HF Qwen3-Reranker-0.6B](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B)
- bge-reranker-v2-m3, Apache-2.0, 14,5 millones de descargas, sin cambios desde jun-2024 — [HF bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3)
- jina-reranker-v2-base-multilingual y jina-reranker-v3 son CC-BY-NC-4.0, no comerciales — [HF jina-reranker-v3](https://huggingface.co/jinaai/jina-reranker-v3); [HF jina-reranker-v2](https://huggingface.co/jinaai/jina-reranker-v2-base-multilingual)
- Librería AnswerDotAI/rerankers, API única para rerankers: 1.645 estrellas, último release 0.10.0 del 22-may-2025, último push 20-dic-2025, frenada — [GitHub AnswerDotAI/rerankers](https://github.com/AnswerDotAI/rerankers); [PyPI rerankers](https://pypi.org/project/rerankers/)
- FlashRank, reranking liviano en CPU: 1.015 estrellas, push 11-jul-2026, pero último release 0.2.10 del 6-ene-2025 — [GitHub FlashRank](https://github.com/PrithivirajDamodaran/FlashRank); [PyPI flashrank](https://pypi.org/project/flashrank/)
- sentence-transformers 6.3.0 del 11-nov-2026, que carga cross-encoders directamente — [PyPI sentence-transformers](https://pypi.org/project/sentence-transformers/)

Embeddings rápidos en CPU
- qdrant/fastembed: 3.313 estrellas, push 26-nov-2026, Apache-2.0, 0.9.1 del 24-oct-2026 — [GitHub qdrant/fastembed](https://github.com/qdrant/fastembed); [PyPI fastembed](https://pypi.org/project/fastembed/)
- Model2Vec potion-multilingual-128M: embeddings estáticos destilados de bge-m3, 101 idiomas, 256 dimensiones, MIT; dicen órdenes de magnitud más rápido en CPU y 90,86 por ciento del rendimiento de LaBSE, puntaje medio MTEB 47,31; model2vec 0.10.0 del 11-oct-2026 — [HF potion-multilingual-128M](https://huggingface.co/minishlab/potion-multilingual-128M); [PyPI model2vec](https://pypi.org/project/model2vec/)
- Qwen3-Embedding-0.6B, Apache-2.0, 6,8 millones de descargas; embeddinggemma-300m con licencia Gemma; granite-embedding-278m-multilingual Apache-2.0 con 12 idiomas, español incluido — [HF Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B); [HF embeddinggemma-300m](https://huggingface.co/google/embeddinggemma-300m); [HF granite multilingual](https://huggingface.co/ibm-granite/granite-embedding-278m-multilingual)

Interacción tardía, ColBERT
- lightonai/pylate: 916 estrellas, push 23-jul-2026, MIT, 1.6.0 del 11-jun-2026 — [GitHub lightonai/pylate](https://github.com/lightonai/pylate); [PyPI pylate](https://pypi.org/project/pylate/)
- GTE-ModernColBERT-v1, Apache-2.0, modificado ago-2026, sin español declarado en etiquetas; colbert-xm, MIT, 80 idiomas; jina-colbert-v2, no comercial — [HF GTE-ModernColBERT-v1](https://huggingface.co/lightonai/GTE-ModernColBERT-v1); [HF colbert-xm](https://huggingface.co/antoinelouis/colbert-xm); [HF jina-colbert-v2](https://huggingface.co/jinaai/jina-colbert-v2)
- stanford-futuredata/ColBERT: 3.962 estrellas, último push 14-oct-2025, frenado; RAGatouille: 3.977 estrellas, último push 17-may-2025, release 0.0.9.post2 del 19-may-2025, frenado — [GitHub ColBERT](https://github.com/stanford-futuredata/ColBERT); [GitHub RAGatouille](https://github.com/AnswerDotAI/RAGatouille)

Motores de búsqueda híbrida, todos activos y todos servidores aparte
- Meilisearch: 60.019 estrellas, push 26-nov-2026, licencia marcada por GitHub como Other; tolerancia a errores de tipeo incorporada y configurable por atributo; híbrido con semanticRatio de 0 a 1, por defecto 0,5; la guía recomienda 0 para códigos y SKU — [GitHub meilisearch](https://github.com/meilisearch/meilisearch); [Meilisearch hybrid](https://www.meilisearch.com/docs/capabilities/hybrid_search/overview); [Meilisearch semantic vs hybrid](https://www.meilisearch.com/docs/capabilities/hybrid_search/advanced/semantic_vs_hybrid); [Meilisearch glosario](https://www.meilisearch.com/docs/getting_started/glossary.md)
- Qdrant: 35.729 estrellas, push 26-nov-2026, Apache-2.0; qdrant-client 1.20.0 del 22-oct-2026 — [GitHub qdrant](https://github.com/qdrant/qdrant); [PyPI qdrant-client](https://pypi.org/project/qdrant-client/)
- Weaviate: 16.967 estrellas, push 26-nov-2026; weaviate-client 4.25.0 del 26-nov-2026 — [GitHub weaviate](https://github.com/weaviate/weaviate); [PyPI weaviate-client](https://pypi.org/project/weaviate-client/)
- Embebidos en el proceso Python: LanceDB, 11.995 estrellas, Apache-2.0, 0.41.0 del 29-oct-2026; txtai, 13.737 estrellas, Apache-2.0, 9.15.0 del 23-nov-2026 — [GitHub lancedb](https://github.com/lancedb/lancedb); [GitHub txtai](https://github.com/neuml/txtai); [PyPI lancedb](https://pypi.org/project/lancedb/); [PyPI txtai](https://pypi.org/project/txtai/)

Entity linking
- amazon-science/ReFinED: 253 estrellas, último push 13-dic-2024, Apache-2.0; enlaza a Wikidata y Wikipedia, no a un catálogo propio; viejo — [GitHub ReFinED](https://github.com/amazon-science/ReFinED)

### Inferences
- El bot ya tiene embeddings dentro de la categoría. Lo que más probablemente sume, sin servicio nuevo, es un canal léxico con bm25s o RapidFuzz para nombres propios, modelos y números, y un reranker de licencia comercial sobre los 15 candidatos. Los dos corren en CPU dentro del servicio Python de Cloud Run; un reranker de 306M a 0,5B suma latencia por candidato que no está medida en CPU.
- Ojo con licencias: los modelos de Jina, reranker y ColBERT, son no comerciales y no sirven para una tienda que vende.
- Typesense y Meilisearch traen tolerancia a errores, sinónimos y filtros listos, pero son un segundo servicio, contra la regla del repo de un servicio vivo. Para unos cientos de productos no se justifican. LanceDB o txtai embebidos evitan el segundo servicio, pero reemplazan algo que hoy ya funciona en memoria.
- Para "no lo vendemos" no apareció herramienta lista. Lo práctico sigue siendo la compuerta determinista de categoría y marca contra el catálogo de las notas previas, y usar el puntaje calibrado del reranker o el umbral de GLiNER2 como señal secundaria de ambiguous, no como decisión.
- ColBERT y la interacción tardía no tienen sentido de costo para un catálogo de este tamaño; además las piezas más conocidas están frenadas.

### Gaps
- No encontré mediciones de latencia en CPU para gte-multilingual-reranker-base ni para mxbai-rerank-base-v2; la de mxbai es en A100.
- No encontré ninguna librería abierta activa de detección fuera de catálogo.
- No verifiqué en esta sesión el modo local, sin servidor, de qdrant-client.

## 4. Recursos para español y rioplatense: texto coloquial, normalización y errores de tipeo

### Takeaway
No hay herramienta viva y lista para normalizar español rioplatense de chat. Los recursos de normalización de español son de 2015 y 2016 y están viejos. Lo usable hoy es genérico: symspellpy y pyspellchecker, activos en 2026, con un diccionario armado desde el vocabulario de la propia tienda, más la tolerancia a errores de RapidFuzz.

### Cited Findings
- TweetNorm_es: benchmark y corpus anotado de normalización léxica de tuits en español, Alegria y otros, Language Resources and Evaluation, 2015; viejo — [CiTIUS TweetNorm](https://citius.gal/research/publications/tweetnorm-a-benchmark-for-lexical-normalization-of-spanish-tweets/)
- normalesp: corrector para español con foco en tuits, ligado a un paper de 2016, escrito para Python 2.7; viejo — [GitHub jacerong/normalesp](https://www.github.com/jacerong/normalesp)
- Tesis con un corpus de tuits en español de Argentina, con errores típicos de normalización y un sistema que combina recursos léxicos, reglas y modelos de lenguaje; no se confirmó si el corpus está publicado — [Repositorios Latinoamericanos UChile](https://repositorioslatinoamericanos.uchile.cl/handle/2250/4265493?show=full)
- symspellpy: 874 estrellas, push 7-nov-2026, MIT, 6.10.2 del 7-nov-2026; corrección por borrado simétrico, se carga con diccionario propio de frecuencias — [GitHub symspellpy](https://github.com/mammothb/symspellpy); [PyPI symspellpy](https://pypi.org/project/symspellpy/)
- pyspellchecker 0.9.1 del 10-oct-2026 — [PyPI pyspellchecker](https://pypi.org/project/pyspellchecker/)
- jamspell, último release 0.0.12 de sep-2020, viejo — [PyPI jamspell](https://pypi.org/project/jamspell/)
- Modelos en español: robertuito-base-uncased, entrenado en tuits en español, sin cambios desde mayo de 2023; bert-base-spanish-wwm-cased, BETO, sin cambios desde enero de 2024; ambos viejos — [HF robertuito](https://huggingface.co/pysentimiento/robertuito-base-uncased); [HF BETO](https://huggingface.co/dccuchile/bert-base-spanish-wwm-cased)

### Inferences
- Para el bot, el diccionario de corrección debería salir del catálogo y de la ficha de vocabulario de la tienda, FICHA 104, no de un diccionario general: así "auris", "joistik" o un modelo mal escrito se corrigen hacia términos que existen en la tienda y nunca hacia algo que la tienda no vende.
- El modismo rioplatense, "algo piola", "lo más barato que tengas", lo resuelve mejor el LLM o un clasificador con ejemplos reales que una normalización léxica; ninguna herramienta abierta encontrada lo cubre.

### Gaps
- No encontré un recurso abierto, activo y específico de español rioplatense de chat o WhatsApp, ni diccionario de jerga de tecnología argentina.
- No pude confirmar si el corpus de la tesis argentina está disponible ni con qué licencia.
