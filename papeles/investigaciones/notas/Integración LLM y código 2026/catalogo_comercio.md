# Cómo los agentes de venta conectan el pedido libre del cliente con el catálogo, estado a fines de 2026

Nota de método: en esta sesión el fetch directo a arxiv.org y dev.to estaba bloqueado por la red. Todo lo de abajo sale de los resúmenes del buscador sobre esas páginas, no del texto completo. Por eso faltan varias tablas de números, que van en Gaps. Las cifras de proveedores no tienen auditoría independiente.

## 1. Vincular el pedido a un producto del catálogo y decidir "eso no lo vendemos" frente a ofrecer un sustituto

### Takeaway
No encontré un paper de 2025 o 2026 dedicado a detectar que lo pedido no está en el catálogo de una tienda. Lo más cercano y medido es la detección de preguntas fuera de la base de conocimiento para RAG, ACL 2026: detectores livianos sobre los embeddings de la base compiten con un LLM juez y salen más baratos. En la práctica, lo que funciona es chequear categoría y marca contra la metadata del catálogo antes de buscar, y no dejar que el ranking por similitud decida solo.

### Cited Findings
- "Knowing When Not to Answer: Lightweight KB-Aligned OOD Detection for Safe RAG", Triantafyllopoulos y otros, arXiv 2508.02296, agosto de 2025, revisado en enero de 2026, publicado en ACL 2026. Aplica PCA a los embeddings de la base y puntúa la consulta en un subespacio chico, elegido por varianza explicada o por un ranking de separabilidad con test t. Evaluado en 16 dominios, con ataques generados por LLM y un ataque real de 4chan. Conclusión: los detectores de baja dimensión logran un rendimiento competitivo fuera de dominio y son más rápidos, baratos e interpretables que un LLM juez con prompt. También reporta que las consultas fuera de dominio dañan sobre todo la relevancia de la respuesta del RAG — [arXiv 2508.02296](https://arxiv.org/abs/2508.02296); [ACL 2026](https://aclanthology.org/2026.acl-long.740/)
- El mismo trabajo dice que los guardrails apuntan sobre todo a contenido tóxico y protegen poco contra preguntas benignas sin respuesta en la base, y que un LLM juez siempre prendido tiene un costo grande de latencia y de API — [ACL 2026 pdf](https://aclanthology.org/2026.acl-long.740.pdf)
- "Know Or Not", arXiv 2505.13545, 2025: una librería para evaluar la robustez fuera de la base de conocimiento — [arXiv 2505.13545](https://arxiv.org/html/2505.13545v2)
- ELOQ, arXiv 2410.14567, de 2024, material anterior: recursos para que un LLM detecte preguntas fuera de alcance — [arXiv 2410.14567](https://arxiv.org/pdf/2410.14567)
- Nota de practicante en DEV Community, "Your chatbot recommends products you don't sell": el asistente consulta la metadata del catálogo, categorías y marcas, antes de buscar, y desvía las consultas de categorías o marcas que la tienda no tiene. El autor reporta menos alucinaciones en consultas sin stock o de categoría equivocada. No pude abrirla para ver números ni fecha — [DEV Community](https://dev.to/rosen_hristov/your-chatbot-recommends-products-you-dont-sell-3jnl)
- "Query Carefully", diciembre de 2025, arXiv 2512.21345: detección de preguntas sin respuesta en text-to-SQL, en una base biomédica — [arXiv 2512.21345](https://arxiv.org/abs/2512.21345)
- Matching de entidades con LLM, del lado de los papers: "Entity Matching using LLMs", arXiv 2310.11244, publicado en EDBT 2025, reporta que GPT-4 sin datos de entrenamiento supera a RoBERTa y Ditto ajustados en tres de cinco benchmarks, con productos incluidos — [arXiv 2310.11244](https://arxiv.org/html/2310.11244v4)
- Paper de DOLAP 2025: modelos de 7B parámetros hacen matching de productos de forma efectiva en dos benchmarks de productos — [CEUR-WS Vol-3931](https://ceur-ws.org/Vol-3931/paper4.pdf)
- arXiv 2405.16884: el matching por pares independientes pierde información; propone usar la interacción entre registros, matching por conjuntos — [arXiv 2405.16884](https://arxiv.org/pdf/2405.16884v3.pdf)
- Benchmarks habituales del matching de productos: WDC Products, en la variante difícil con 80 por ciento de casos límite, Walmart-Amazon y Abt-Buy — [arXiv 2409.08185](https://arxiv.org/html/2409.08185v1)
- OpenSanctions Pairs, arXiv 2603.11051, 2026: 755.540 pares etiquetados de 293 fuentes; no es de productos, pero es el benchmark de matching con LLM más reciente que encontré — [arXiv 2603.11051](https://arxiv.org/html/2603.11051)
- Del lado de los asistentes grandes: tests de prensa encontraron que Rufus de Amazon se equivoca seguido, no recomienda lo pedido y a veces no sugiere nada — [ConsumerAffairs](https://www.consumeraffairs.com/news/amazons-ai-shopping-assistant-rufus-is-often-wrong-110724.html); [Marketplace Pulse](https://www.marketplacepulse.com/articles/amazons-shopping-ai-is-confidently-wrong)
- Una prueba de Bernstein sobre cinco herramientas de compra con agente, Sparky, Alexa, ChatGPT, Gemini y Claude, encontró que ninguna completó compras sin supervisión, y que los agentes propios del comercio como Sparky dan resultados precisos y listos para comprar, pero limitados a lo que está en el surtido — [rallies.ai](https://rallies.ai/news/walmarts-sparky-delivers-transaction-ready-precision-but-lacks-assortment-breadth); [Fortune, nov 2025](https://fortune.com/2025/11/27/ai-shopping-apps-chatgpt-perplexity-amazon-walmart-google/)

### Inferences
- La mitad del 9 por ciento de errores del bot, ofrecer lo más parecido cuando la tienda no vende lo pedido, coincide con la clase que el trabajo de ACL 2026 llama consulta benigna fuera de la base: la similitud siempre devuelve un vecino, y nada en el ranking dice "no hay". El remedio que mejor mide en la literatura es una compuerta separada antes del ranking, no un umbral sobre el puntaje del primer resultado.
- Para un catálogo de unos cientos de productos, la compuerta más barata y verificable es determinista: ¿la categoría, la marca o el tipo nombrado existen en el catálogo? Esto calza con la regla del repo de tres veredictos, exists, ambiguous, not_found. El detector PCA de ACL 2026 es una segunda opción si la compuerta por vocabulario deja pasar casos.
- Ofrecer sustituto debería ser una decisión explícita después del not_found, dicha como tal al cliente, y no el resultado por defecto del ranking.

### Gaps
- No encontré ningún paper de 2025 o 2026 con un número medido para "decir que no lo vendemos" contra "ofrecer sustituto" en comercio.
- No pude leer las tablas de 2508.02296 ni el post de DEV Community; faltan AUROC, F1 y fechas.

## 2. Búsqueda híbrida, BM25 más embeddings más reranker, extracción de atributos, y texto a filtro con validación

### Takeaway
El patrón 2025 y 2026 es: el LLM convierte el pedido en restricciones estructuradas, el código filtra, los embeddings ordenan, y una capa de validación descarta lo que no está en la taxonomía. Instacart lo describe así en producción, y un paper de enero de 2026 lo mide sobre Amazon ESCI.

### Cited Findings
- "LLM-based Semantic Search for Conversational Queries in E-commerce", Siddiqui, Terikuti y Lu, Universidad de Arizona, arXiv 2601.16492, 23 de enero de 2026. Combina embeddings de dominio con filtros estructurados; usa datos sintéticos generados por LLM para ajustar un modelo de embeddings y un modelo generativo que convierte la consulta en restricciones numéricas y categóricas. Evaluado sobre Amazon ESCI; según un resumen, la combinación de similitud más filtro por restricciones da precisión y recall fuertes frente a las bases. Publican el dataset — [arXiv 2601.16492](https://arxiv.org/abs/2601.16492); [resumen](https://api.emergentmind.com/papers/2601.16492)
- Instacart, 2025, "Building The Intent Engine": pasó de varios modelos de ML independientes a un enfoque unificado con LLM para entender la consulta, por capas, desde ingeniería de contexto con guardrails hasta fine-tuning para destilar conocimiento propio. Capas de validación filtran alucinaciones y fuerzan el alineamiento con la taxonomía de productos de Instacart. Los extractos no traen números antes y después — [Instacart](https://company.instacart.com/tech-innovation/building-the-intent-engine-how-instacart-is-revamping-query-understanding-with-llms); [ZenML](https://www.zenml.io/llmops-database/revamping-query-understanding-with-llms-in-e-commerce-search)
- Yelp, febrero de 2025: LLM para entender millones de búsquedas diarias, con segmentación de la consulta — [Yelp Engineering](https://engineeringblog.yelp.com/2025/02/search-query-understanding-with-LLMs.html)
- Amazon Science, borrador: interfaz en lenguaje natural para la API de búsqueda de productos; el problema es extraer pares atributo valor de una consulta ruidosa, ambigua y no canónica, para filtrar resultados. El texto tiene citas sin completar, parece un borrador — [Amazon Science](https://cdn.amazon.science/a1/97/116ffa7f44e28bcc4bcdfccaceee/building-natural-language-interface-for-product-search.pdf)
- TRACE, DoorDash, arXiv 2608.20844, 2026: enriquecimiento de atributos del catálogo con un agente juez en el camino de servicio, que verifica antes de escribir — [arXiv 2608.20844](https://arxiv.org/pdf/2608.20844)
- BEATS, arXiv 2606.04909, 2026: control de calidad por los desarrolladores y anotación humana experta de taxonomías de atributos, para habilitar filtros finos por atributo — [arXiv 2606.04909](https://arxiv.org/html/2606.04909v1)
- arXiv 2607.22949, 2026, "Beyond Exact Match": en extracción de atributos con LLM, la metodología de evaluación explica una parte sustancial de la variación de rendimiento reportada, más que la elección del modelo — [arXiv 2607.22949](https://arxiv.org/pdf/2607.22949)
- Brinkmann y otros, arXiv 2310.12537, 2023, material anterior: LLM como alternativa más eficiente en datos y más robusta que BERT para extraer atributos — [arXiv 2310.12537](https://arxiv.org/abs/2310.12537v5)
- Elastic: con su API rank_eval, sumar embeddings de Jina a BM25 subió el recall de 0,43 a 0,75 sobre juicios etiquetados a mano que mezclan consultas por palabra clave y por intención — [Elastic Search Labs](https://www.elastic.co/search-labs/blog/elasticsearch-relevance-tuning-improve-recall)
- Comparación informal con Vespa, seis métodos de ranking: dentro del dominio ganan los embeddings y el híbrido parece innecesario; fuera del dominio el híbrido ayuda. Es un post de Medium — [Level Up Coding](https://levelup.gitconnected.com/evaluating-hybrid-search-in-and-out-of-domain-with-vespa-d79df4b8847a)
- Target, arXiv 2609.31498: búsqueda híbrida en producción, embeddings entrenados con etiquetas derivadas del uso, canales léxico y vectorial combinados. No pude confirmar el identificador ni la fecha — [arXiv 2609.31498](https://arxiv.org/pdf/2609.31498)
- Taobao, LEAPS, arXiv 2601.05513, 2026: plugin adaptativo con LLM en la búsqueda con IA de Taobao — [arXiv 2601.05513](https://arxiv.org/pdf/2601.05513)
- DeepShop, arXiv 2506.02839, junio de 2025: en consultas con filtros de varios atributos y orden personalizado, los agentes web manejan mal filtros y orden, y aun los sistemas de deep research fallan en filtrar — [arXiv 2506.02839](https://arxiv.org/html/2506.02839v1)

### Inferences
- La arquitectura actual del bot, LLM chico etiqueta, embeddings ordenan dentro de la categoría, código filtra color, inalámbrico, tope de precio y lo más barato, es el mismo patrón que Instacart y 2601.16492. No hay evidencia de que reemplazarla por otra cosa mejore; la evidencia apunta a reforzar la validación contra la taxonomía.
- DeepShop indica que filtrar y ordenar es justo donde fallan los agentes que lo hacen solos; dejar eso en el código es lo correcto.
- BM25 sumado a embeddings ayuda en nombres exactos, modelos y números, como un código de modelo de auricular; en catálogos chicos y dentro del dominio, la ganancia del híbrido puede ser chica.

### Gaps
- No encontré números de ESCI, NDCG o recall, de 2601.16492 ni de otros trabajos 2025 y 2026.
- No encontré mediciones publicadas de Zalando ni Shopify sobre entender la consulta.

## 3. Benchmarks de agentes de compra y qué sacan los mejores

### Takeaway
Los benchmarks de compra de 2025 y 2026 siguen siendo duros: ShoppingBench queda bajo 50 por ciento con GPT-4.1 y ShoppingComp bajo 18 por ciento con GPT-5.2. En tau2-bench retail los números altos, cerca de 92 por ciento, son autoinformados y no coinciden con los envíos oficiales, cerca de 80 por ciento. La métrica que más le sirve a un bot de ventas es pass^k, la constancia.

### Cited Findings
- tau-bench, Yao y otros, Sierra, ICLR 2025: introduce pass^k, la probabilidad de resolver la misma tarea en k intentos. GPT-4o con function calling hace cerca de 61 por ciento pass^1 en retail y cae a cerca de 25 por ciento en pass^8 — [ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/file/1b126cc38b8638e07bef37e7b2bb72bf-Paper-Conference.pdf); [Sierra blog](https://sierra.ai/blog/benchmarking-ai-agents)
- tau2-bench retail: un agregador lista a Claude Opus 4.6 primero con 0,919 entre 23 modelos, autoinformado — [llm-stats](https://llm-stats.com/benchmarks/tau2-retail)
- Lectura de los envíos oficiales de tau2-bench, taubench.com: cerca de 79,6 para Claude Opus 4.5 y 81,6 para GPT-5.2, muy por debajo de los agregadores — [benchmarkingagents](https://benchmarkingagents.com/tau-bench-retail-airline)
- El README de Sierra dice que los puntajes 2.0 no se comparan con el tablero 1.x — [benchmarkingagents](https://benchmarkingagents.com/tau-bench)
- Ya existe tau3-retail; Mistral Medium 3.5 lidera con 0,761, con un solo modelo evaluado — [llm-stats](https://llm-stats.com/benchmarks/tau3-retail)
- ShoppingBench, Wang y otros, arXiv 2508.04266, agosto de 2025, AAAI 2026, volumen 40, número 39, páginas 33521 a 33529: 3.310 instrucciones en cuatro tipos de intención, buscar productos, conocimiento, varios productos de un vendedor, y cupón y presupuesto. Aun GPT-4.1 queda bajo 50 por ciento de éxito absoluto. Entrenaron un agente chico que compite con GPT-4.1. Código en GitHub, yjwjy/ShoppingBench — [arXiv 2508.04266](https://arxiv.org/abs/2508.04266v3); [AAAI](https://ojs.aaai.org/index.php/AAAI/article/view/40640)
- ShoppingComp, ByteDance BandAI, arXiv 2511.22978, noviembre de 2025: recuperación precisa de productos, informe experto y decisiones críticas de seguridad con preguntas trampa. En la v2, 145 instancias y 558 escenarios de 35 expertos; GPT-5.2 saca 17,76 por ciento y Gemini-3-Pro 15,82 por ciento. En la v1, 120 tareas y 1.026 escenarios; GPT-5 11,22 por ciento y Gemini-2.5-Flash 3,92 por ciento. Según un resumen de la v1, en recuperación de productos los humanos sacan F1 de cerca de 26 por ciento y GPT-5 11 por ciento. Repo en GitHub, ByteDance-BandAI/ShoppingComp — [arXiv 2511.22978](https://arxiv.org/html/2511.22978v2); [emergentmind](https://www.emergentmind.com/papers/2511.22978)
- WebMall, arXiv 2508.13024, 2025: cuatro tiendas simuladas de electrónica con datos de Common Crawl, 91 tareas en 11 categorías, entorno en Docker, ocho configuraciones de agente — [arXiv 2508.13024](https://arxiv.org/html/2508.13024v2)
- EcomBench, Alibaba-NLP, arXiv 2512.08868, diciembre de 2025: preguntas curadas por expertos a partir de demandas reales, en tres niveles. En la v2, el gráfico va de cerca de 43 a cerca de 65 por ciento; no pude atribuir el 65 a un modelo — [arXiv 2512.08868](https://arxiv.org/html/2512.08868)
- DeepShop, junio de 2025, ver la sección 2 — [arXiv 2506.02839](https://arxiv.org/html/2506.02839v1)

### Inferences
- WebMall es de electrónica, el mismo rubro de la tienda, y es offline: podría servir como banco externo, aunque mide navegación web y no chat.
- Los puntajes de tau-bench retail miden cambios y devoluciones con herramientas, no la vinculación de un pedido libre al catálogo; no sirven para juzgar el 9 por ciento.
- La caída de pass^1 a pass^8 respalda la regla del repo de medir con varias corridas y no con una.

### Gaps
- No pude abrir taubench.com para confirmar el tablero oficial de tau2 retail a noviembre de 2026.
- Faltan los números por modelo de WebMall y de seguridad de ShoppingComp.
- No encontré un benchmark de compra conversacional en español.

## 4. Reportes de producción de bots de venta o soporte en WhatsApp o chat, 2025 y 2026, con casos de América Latina

### Takeaway
Hay cifras de resolución de 60 a 92 por ciento en casos latinoamericanos, todas publicadas por el proveedor que vende la plataforma y sin decir cómo se mide "resuelto". El caso más citado de marcha atrás es Klarna, mayo de 2025, por caída de calidad.

### Cited Findings
- Grupo Rossetti, Argentina, en VTEX: 84 por ciento de resolución por IA y 80,62 por ciento de clics en WhatsApp, Instagram y Facebook. La misma página dice 27.900 por ciento de retorno, cifra poco creíble — [VTEX](https://www.vtex.com/en-us/commerce-stories/rossetti/)
- Grupo Líder, Brasil, en VTEX: 92 por ciento de resolución automática y 16 por ciento de crecimiento de ingresos — [VTEX](https://www.vtex.com/en-us/commerce-stories/lider)
- Mueblería de México, Villareal, en VTEX, WhatsApp: 14,12 por ciento de conversión en 30 días — [VTEX](https://vtex.com/en-us/commerce-executive-stories/villareal-furniture-1524-roi-whatsapp-agentic-cx)
- Grupo Falabella con Salesforce Agentforce: una página cita 60 por ciento de resolución; otra dice que un piloto en Colombia llegó a 70 por ciento a las tres semanas — [Salesforce](https://www.salesforce.com/customer-stories/grupo-falabella/); [Salesforce ES](https://www.salesforce.com/es/customer-stories/grupo-falabella/)
- Telecom latinoamericana con Sprinklr: 110.000 ventas en el canal en los primeros seis meses — [Sprinklr](https://www.sprinklr.com/stories/latin-american-telecom)
- Diskat con respond.io: 80 por ciento de conversión con agentes de IA, según el título del caso — [respond.io](https://respond.io/pt/customers/diskat-maintains-80-percent-conversion-rate-with-ai-agents.md)
- Klarna, mayo de 2025: el CEO dijo a Bloomberg que volvían a contratar humanos porque el enfoque centrado en IA bajó la calidad, y que el costo pesó demasiado — [Bloomberg](https://www.bloomberg.com/news/articles/2025-05-08/klarna-turns-from-ai-to-real-person-customer-service); [Entrepreneur](https://www.entrepreneur.com/business-news/klarna-ceo-reverses-course-by-hiring-more-humans-not-ai/491396)
- Klarna, cifra de lanzamiento: 2,3 millones de charlas, dos tercios del chat de soporte, en el primer mes — [HubSpot](https://blog.hubspot.com/ai/klarna-ai-assistant)
- Amazon dice que quien usa Rufus tiene cerca de 60 por ciento más de probabilidad de comprar; Walmart dice que quien usa Sparky tiene un ticket promedio 35 por ciento más alto. Ninguna cifra mide precisión — [eMarketer](https://www.emarketer.com/content/walmart-amazon-say-ai-boosts-ecommerce-sales)

### Inferences
- Ningún reporte encontrado mide la tasa de respuestas falsas del bot; miden resolución o conversión. El 9 por ciento medido del bot no tiene contra qué compararse en público.
- Rossetti es un caso argentino de retail en WhatsApp; vale como referencia de mercado, no como evidencia técnica.

### Gaps
- No encontré la cifra de 2026 de Intercom Fin de fuente propia; solo un artículo sin fecha que dice más de 50 por ciento de resolución al primer contacto.
- Ningún caso trae tasa de derivación a humano con su definición.
- No encontré casos de tiendas de tecnología en Argentina con números de precisión.

## 5. Protocolos y herramientas de comercio con agentes, 2025 y 2026

### Takeaway
En 2026 conviven ACP, de OpenAI y Stripe, y UCP, de Google con Apache 2, y Shopify ya expone su catálogo por MCP siguiendo UCP. Sirven para que agentes de terceros encuentren y compren; no resuelven la vinculación del pedido libre dentro de un bot propio, pero sus esquemas de búsqueda y ficha de producto son una referencia para ordenar el catálogo.

### Cited Findings
- ACP, Agentic Commerce Protocol, codesarrollado por Stripe y OpenAI; impulsa Instant Checkout en ChatGPT — [Stripe](https://stripe.com/en-at/blog/developing-an-open-standard-for-agentic-commerce)
- Checkout.com aclara que Instant Checkout es la primera implementación de ACP, no el protocolo — [Checkout.com](https://www.checkout.com/blog/openai-acp-google-ucp-difference)
- UCP, Universal Commerce Protocol de Google, presentado en NRF en enero de 2026, licencia Apache 2, con Shopify, Etsy, Wayfair, Target y Walmart — [eWEEK](https://www.eweek.com/news/google-universal-commerce-protocol-launch/); [The New Stack](https://thenewstack.io/shopify-walmart-endorse-googles-new-open-commerce-protocol/)
- Comparación de un proveedor: UCP es descentralizado, con un archivo /.well-known/ucp en el dominio del comercio; ACP es centralizado, vía el catálogo de productos de OpenAI. Sin verificar — [DEV Community](https://dev.to/ucptools/ucp-vs-acp-in-2026-a-technical-comparison-of-ai-commerce-protocols-50j7)
- Marzo de 2026: OpenAI retrocedió con Instant Checkout mientras Google extendía UCP; es la lectura de medios y blogs, no de OpenAI — [Retail TouchPoints](https://www.retailtouchpoints.com/news/google-adds-new-agentic-shopping-features-as-openai-pivots-amazon-enters-the-mix/)
- 24 de abril de 2026: Amazon, Meta, Microsoft, Salesforce y Stripe se sumaron al consejo técnico de UCP, según un Substack, sin confirmar en fuente primaria — [Ken Huang](https://kenhuangus.substack.com/p/googles-ucp-just-won-agentic-commerce)
- Shopify Storefront Catalog MCP: un servidor MCP por tienda, en https://{storeDomain}/api/ucp/mcp, con las herramientas search_catalog, lookup_catalog y get_product, que siguen la capacidad Catalog de UCP — [Shopify](https://shopify.dev/docs/agents/catalog/storefront-mcp); [changelog](https://shopify.dev/changelog/posts/storefront-catalog-mcp-now-implements-ucp.md)
- Shopify Global Catalog MCP: búsqueda en todos los comercios de Shopify, agrupada por un identificador universal de producto, UPID — [Shopify](https://shopify.dev/docs/agents/catalog/global-catalog)
- El viejo Storefront MCP, /api/mcp, perdió las herramientas de catálogo y carrito, que pasaron a UCP y a un Cart MCP aparte — [Shopify](https://shopify.dev/docs/apps/build/storefront-mcp/servers/storefront)
- Shop MCP, de cara al consumidor, en https://shop.app/mcp — [Shopify](https://shopify.dev/docs/apps/build/shop-mcp)
- Servidor MCP no oficial para Shopify Storefront, QuentinCody/shopify-storefront-mcp-server — [archestra.ai](https://archestra.ai/mcp-catalog/quentincody__shopify-storefront-mcp-server)
- El W3C tuvo un encuentro sobre agentes de comercio electrónico en septiembre de 2026 — [W3C](https://www.w3.org/2026/09/ecommerce-agents/slides/Amit_Handa.pdf)

### Inferences
- El trío search_catalog, lookup_catalog, get_product separa buscar de confirmar una identidad, igual que el veredicto determinista del repo; es un buen modelo para la interfaz interna entre el modelo y el catálogo.
- Publicar el catálogo con UCP sería un canal de venta nuevo, no un arreglo del error del 9 por ciento.

### Gaps
- No pude leer el esquema formal del feed de productos de ACP ni de UCP.
- No encontré adopción de ACP o UCP por tiendas de Argentina o por Mercado Libre.
