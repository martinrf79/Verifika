# Memoria conversacional para agentes LLM, estado a noviembre de 2026

Nota de método: en esta sesión no se pudo abrir ninguna página completa. arxiv.org, mem0.ai y letta.com no resuelven desde la red de la sesión, y la API de GitHub no tiene acceso a esos repos. Todo lo de abajo sale de los resúmenes del buscador sobre esas páginas. Los números conviene confirmarlos contra el paper o el repo antes de usarlos en una decisión. Fecha de corte: 26-nov-2026.

## 1. Inventario de sistemas: Letta, Mem0, Zep y Graphiti, LangMem, Cognee, MemOS, A-Mem y los nuevos

### Takeaway
Todos los grandes son Apache-2.0 y siguen activos en 2026. Pero ninguno está pensado para el estado de una transacción, como un carrito que se corrige turno a turno. Están pensados para recordar hechos del usuario entre sesiones. En la prueba de 2026 hecha para estado que cambia, Mem0 y A-Mem dan entre 13 y 20% de respuestas con el estado vigente.

### Cited Findings
- Versiones según la API de GitHub al 20-nov-2026, citadas por un tercero: Mem0 ts-v3.3.1 del 25-sep-2026; Cognee v1.6.10 del 18-nov-2026; Graphiti v0.31.2 del 20-oct-2026; servidor de Letta 0.16.8 del 14-may-2026, con el desarrollo movido a letta-code, v0.34.67 del 20-nov-2026; MemOS v2.0.36 del 9-nov-2026 — [kxdevelopers, nov 2026](https://kxdevelopers.com/blogs/best-ai-agent-memory-libraries-2026); [evermind, comparativa de licencias](https://evermind.ai/blogs/best-open-source-agent-memory-frameworks-2026)
- Licencias: varias comparativas listan Letta, Mem0, Graphiti, Cognee y MemOS como Apache-2.0 — [evermind](https://evermind.ai/blogs/best-open-source-agent-memory-frameworks-2026); [aiagentmemory.org](https://aiagentmemory.org/articles/open-source-memory-systems-compared/)
- Mem0: según terceros, el SDK abierto dejó la memoria en grafo en la v3. Mem0 dice que sus números de benchmark salen de la plataforma paga, con "optimizaciones propietarias que no están en el SDK abierto" — [kxdevelopers](https://kxdevelopers.com/blogs/best-ai-agent-memory-libraries-2026); [mcp.directory](https://mcp.directory/blog/mem0-vs-letta-vs-zep-vs-cognee-2026)
- Zep y Graphiti: es un grafo de conocimiento bitemporal. Una línea de tiempo guarda cuándo pasó cada hecho y otra cuándo se cargó, así que un hecho viejo queda invalidado sin borrarse. Paper de enero de 2025, material de 2025: dice hasta 18,5% más de acierto y 90% menos de latencia; en el benchmark DMR saca 94,8% contra 93,4% de MemGPT — [arXiv 2501.13956](https://arxiv.org/html/2501.13956)
- Tabla de Zep en LongMemEval, 2025: con GPT-4o, Zep 71,2% contra 60,2% de contexto completo; con GPT-4o-mini, 63,8% contra 55,4%. El texto de la tabla llegó desordenado en el buscador — [blog de Zep](https://blog.getzep.com/state-of-the-art-agent-memory/)
- Letta, antes MemGPT: bloques de memoria que el propio agente edita con herramientas. Su prueba de agosto de 2025 metió la charla de LoCoMo en un archivo plano y le dio al agente herramientas de archivos. Sacó 74,0% con GPT-4o mini, contra 68,5% que Mem0 reportaba para su mejor variante con grafo. Mem0 no contestó cómo calculó sus números — [blog de Letta, 12-ago-2025](https://www.letta.com/blog/benchmarking-ai-agent-memory)
- MemOS, paper de julio de 2025: en LoCoMo, MemOS-0630 saca 73,31 con juez LLM, con p95 de búsqueda de 1.969 ms y p95 total de 7.937 ms. LangMem saca 55,76, con p95 de búsqueda cerca de 29.344 ms y total cerca de 30.139 ms — [arXiv 2507.03724](https://arxiv.org/pdf/2507.03724)
- LangMem: un blog de Mem0, fuente interesada, le da un p95 de 60 s, contra 1,4 s de Mem0 — [blog de Mem0](https://mem0.ai/blog/benchmarked-openai-memory-vs-langmem-vs-memgpt-vs-mem0-for-long-term-memory-here-s-how-they-stacked-up)
- Proyectos 2026 en arXiv: MemStrata dice 95% en LongMemEval-500 y 90,91% en LoCoMo-1540 con un Qwen local de 27B — [arXiv 2610.05343](https://arxiv.org/pdf/2610.05343); Mnemis, recuperación en dos rutas sobre grafos jerárquicos — [arXiv 2602.15313](https://arxiv.org/pdf/2602.15313); MIRIX-2.0, memoria multiagente — [arXiv 2611.12068](https://arxiv.org/pdf/2611.12068); Agent Zero Memory, con procedencia de cada recuerdo — [arXiv 2608.29606](https://arxiv.org/pdf/2608.29606); StateMem, memoria que pone el estado primero — [arXiv 2608.19652](https://arxiv.org/abs/2608.19652)

### Inferences
- Para el bot, Zep y Graphiti son lo más cercano a "el cliente corrigió lo que había elegido", por la invalidación temporal. Igual exige otro servicio y un grafo, y el CLAUDE.md del repo pide cero cosas sueltas.
- Las latencias de LangMem y de algunos grafos, de segundos a decenas de segundos, no entran en un turno de WhatsApp.

### Gaps
- No pude confirmar en el repo las versiones, fechas y licencias de A-Mem, LangMem, Supermemory ni Memori. Tampoco las del resto contra GitHub mismo.
- No hay números de MemStrata, Mnemis ni MIRIX-2.0 reproducidos por terceros.

## 2. Benchmarks y qué tan creíbles son los números

### Takeaway
LoCoMo y LongMemEval están casi saturados y los números de los vendedores no se pueden comparar entre sí. Cambian el modelo que contesta, el juez y el arnés, y hubo una pelea pública Mem0 contra Zep. Las pruebas nuevas de 2026, que miden estado que cambia o tareas que dependen unas de otras, hunden a los mismos sistemas.

### Cited Findings
- Números que Mem0 publica de sí mismo: 92,5% en LoCoMo y 94,4% en LongMemEval. Otra página de Mem0 da 93,4% y 91,6%, o sea hay más de una cifra oficial — [Mem0, benchmarks 2026](https://mem0.ai/library/agent-memory/ai-memory-benchmarks-in-2026); [Mem0, estado 2026](https://mem0.ai/blog/state-of-ai-agent-memory-2026)
- Zep dice en 2026: LoCoMo 94,7%, 1.459 de 1.540, y LongMemEval 90,2%, 451 de 500, con GPT-5.4 contestando y juzgando — mismas fuentes de arriba, citando la página de investigación de Zep
- La pelea de 2025: Zep dijo 84% en LoCoMo; Mem0 lo "corrigió" a 58,44% alegando que se incluyó mal la categoría adversarial; Zep contestó con 75,14% y culpó a cómo Mem0 había configurado Zep — [blog de Zep, "Lies, damn lies, statistics"](https://blog.getzep.com/lies-damn-lies-statistics-is-mem0-really-sota-in-agent-memory/); [atlan](https://atlan.com/know/zep-vs-mem0/)
- La prueba del archivo plano de Letta, 74%, le ganó al 68,5% de Mem0 en 2025. No se volvió a correr contra los números nuevos de Mem0 — [blog de Letta](https://www.letta.com/blog/benchmarking-ai-agent-memory)
- Una prueba independiente con un solo Gemini contestando y juzgando: Mem0 64,3% sobre 42 preguntas y Letta 70,0% sobre 40. La muestra es demasiado chica para ordenarlos — [agentsystems.blog](https://agentsystems.blog/agent-memory-benchmark)
- StateMemBench, 20-ago-2026: 234 escenarios de varias sesiones y se puntúa si la respuesta da el estado vigente o uno ya reemplazado. Estado vigente: Mem0 0,177 y A-Mem 0,199 con DeepSeek-V4-Flash; 0,149 y 0,127 con Qwen-3.5-9B. StateMem sube de 0,205 a 0,363, 1,8 veces, y como envoltorio suma de 32 a 67 puntos sobre seis backends. Zep no está evaluado. Los números salen de resúmenes secundarios — [alphaxiv 2608.19652](https://www.alphaxiv.org/abs/2608.19652); [ibl.ai](https://ibl.ai/blog/agent-memory-state-transitions-world-models-vs-rag)
- Otros de 2026: MINTEval o LongMINT, con interferencia entre varios objetivos y un dominio de seguimiento de estado — [arXiv 2605.18565](https://arxiv.org/pdf/2605.18565); EvoMemBench, estado de ejecución con referencias implícitas a turnos anteriores — [arXiv 2605.18421](https://arxiv.org/html/2605.18421v2); AMA-Bench, seguimiento del estado de objetos ligado a cada turno — [arXiv 2602.22769](https://arxiv.org/pdf/2602.22769); según una encuesta, modelos casi saturados en LoCoMo bajan a 40 a 60% en MemoryArena — [arXiv 2602.16313](https://arxiv.org/pdf/2602.16313)
- Encuesta de 2026 sobre memoria de agentes autónomos — [arXiv 2603.07670](https://arxiv.org/html/2603.07670v1)

### Inferences
- Un 90% en LoCoMo no predice nada sobre un carrito que se corrige. StateMemBench es el único que mide justo esa clase de falla, y ahí los sistemas comerciales andan mal.
- Coincide con la regla de la FICHA 108 del repo, medir por capas con entrada perfecta: un número de memoria vale sólo con el mismo modelo y el mismo juez.

### Gaps
- Sin acceso al PDF de StateMemBench no pude confirmar los cinco modos de falla ni las cifras exactas.
- No encontré resultados de Zep, Letta ni Graphiti en StateMemBench.

## 3. Memoria dentro de las plataformas y los SDK

### Takeaway
En 2025 y 2026 las tres plataformas grandes sacaron piezas propias: Anthropic con la herramienta de memoria, la edición de contexto y la compactación; OpenAI con las sesiones y la compactación del Agents SDK; Google con el Memory Bank. Las tres resuelven el historial largo o el recuerdo entre sesiones, no el estado de un pedido.

### Cited Findings
- Anthropic, herramienta de memoria: un directorio de archivos del lado del cliente, tipo `memory_20250818`, para Claude 4 en adelante. La edición de contexto borra resultados de herramientas viejos y está en beta con el header `context-management-2025-06-27`. La compactación es un resumen del lado del servidor, estrategia `compact_20260112` con el header `compact-2026-01-12`. Anthropic dice que memoria más edición de contexto mejoró 39% sobre la línea base, y la edición sola 29%, en su evaluación interna de búsqueda agéntica — [Anthropic, context management](https://www.anthropic.com/news/context-management); [docs de compactación](https://platform.claude.com/docs/en/build-with-claude/compaction.md); [docs de edición de contexto](https://platform.claude.com/docs/en/build-with-claude/context-editing.md); [docs de la herramienta de memoria](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- Cookbook de Anthropic de marzo de 2026 que combina compactación, edición de contexto y memoria — [cookbook](https://platform.claude.com/cookbook/tool-use-context-engineering-context-engineering-tools)
- OpenAI Agents SDK: sesiones que guardan el historial; `OpenAIResponsesCompactionSession` llama a `responses.compact` después de cada turno cuando un gancho lo decide, y sólo anda con modelos de Responses. En el SDK de TypeScript se compacta por defecto al juntarse 10 ítems que no son del usuario. Para baja latencia se recomienda compactar a mano entre turnos — [referencia Python](https://openai.github.io/openai-agents-python/ref/memory/openai_responses_compaction_session/); [cookbook de sesiones](https://developers.openai.com/cookbook/examples/agents_sdk/session_memory)
- OpenAI agregó compactación nativa en la Responses API, según un post de marzo de 2026 citado por SentinelLABS — [SentinelLABS](https://www.sentinelone.com/labs/context-engineering-compaction-agent-memory-for-automated-malware-analysis)
- Google: el Memory Bank de Vertex AI Agent Engine, hoy bajo Gemini Enterprise Agent Platform, arma recuerdos de largo plazo a partir de las charlas y se integra con ADK por medio de `VertexAiMemoryBankService`. Lo de corto plazo es el estado de la sesión de ADK. La documentación advierte sobre envenenamiento de memoria e inyección de instrucciones — [docs de Memory Bank](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank); [Google, estado y memoria con ADK](https://cloud.google.com/blog/topics/developers-practitioners/remember-this-agent-state-and-memory-with-adk?hl=en)

### Inferences
- El bot corre con Gemini en producción, así que de esto lo aplicable es la idea, no la API: separar el estado de la sesión, que es exacto, del recuerdo de largo plazo, que es extraído por un modelo. Memory Bank no aporta para un pedido dentro de una misma charla.
- La compactación resume, y un resumen puede perder justo un ítem sacado del carrito. Para estado transaccional es riesgosa salvo que el estado viva aparte.

### Gaps
- No conseguí el número de versión del Agents SDK que trajo la compactación, ni una evaluación de la compactación medida en charlas comerciales.

## 4. Estado estructurado contra memoria en texto libre para tareas transaccionales

### Takeaway
No encontré ningún estudio de 2025 o 2026 que compare de frente un carrito estructurado contra memoria en texto libre. La evidencia indirecta apunta a lo estructurado y autoritativo, escrito por código: la memoria en texto libre o extraída falla justo al revisar hechos, y los modelos se pierden en charlas de varios turnos aun con toda la información.

### Cited Findings
- "LLMs Get Lost in Multi-Turn Conversation", mayo de 2025, ICLR 2026: con la instrucción repartida en pedazos, uno por turno, todos los modelos grandes rinden 39% menos de promedio que con todo en un turno. Juntar los mismos pedazos en un solo prompt recupera el 95,1%. La caída es sobre todo falta de confiabilidad, no de capacidad: los modelos se apuran a suponer, arrastran respuestas viejas y no se corrigen. Claude 3.7 Sonnet, Gemini 2.5 y GPT-4.1 caen 30 a 40% — [arXiv 2505.06120](https://arxiv.org/pdf/2505.06120); [ICLR 2026](https://iclr.cc/virtual/2026/oral/10009147)
- StateMemBench: la memoria extraída responde con el estado vigente sólo 13 a 20% de las veces cuando los hechos se revisan — [alphaxiv](https://www.alphaxiv.org/abs/2608.19652); [ibl.ai](https://ibl.ai/blog/agent-memory-state-transitions-world-models-vs-rag)
- MemGuide, 2025: dice que en el diálogo orientado a tareas hace falta seguir casilleros, intenciones que cambian y un estado consistente, a diferencia del recuerdo libre — [arXiv 2505.20231](https://arxiv.org/html/2505.20231v2)
- NL-DST, marzo de 2025: el estado del diálogo como resumen en lenguaje natural escrito por un LLM, en vez de pares casillero y valor, evaluado en MultiWOZ 2.1 y Taskmaster-1 — [arXiv 2503.08857](https://arxiv.org/pdf/2503.08857)
- Factores que afectan el aprendizaje en contexto para seguir el estado del diálogo, 2025 — [arXiv 2506.08753](https://arxiv.org/pdf/2506.08753)
- TPBench, 2026: benchmark de puntos de giro para comprimir diálogo — [arXiv 2610.02736](https://arxiv.org/pdf/2610.02736)

### Inferences
- Que el bot "se pierda al tercer o cuarto mensaje" coincide con la curva de Laban y compañía. Lo que más ayuda según ese paper es lo que hace CONCAT: volver a darle al modelo, en cada turno, el estado consolidado completo en vez de dejarlo deducir del historial.
- Para el carrito, la forma que respalda la evidencia es la que el repo ya tiene en parte: el pedido en `memoria_agente` como fuente autoritativa, cambiado sólo por comandos que aplica el código, como agregar, sacar, reemplazar o fijar destino, y mostrado completo en cada turno. El historial queda como contexto, no como fuente.

### Gaps
- No hay un benchmark público de carritos o pedidos de varios turnos con números de 2025 o 2026. Lo más cercano son MultiWOZ, StateMemBench y los benchmarks de estado de ejecución.

## 5. Correferencia entre turnos: "esa", "la primera que te pregunté"

### Takeaway
La investigación de 2025 y 2026 sigue tratando la anáfora y la elipsis entre turnos como un problema abierto para los LLM. Lo que mejor funciona en lo publicado es anclar cada mención a un id persistente y reescribir el mensaje antes de resolver. No encontré trabajo específico sobre "la primera".

### Cited Findings
- Encuesta sobre interacciones de varios turnos, 2025: la anáfora y la elipsis siguen abiertas, y los modelos pierden hechos dichos por el usuario cuando después se los nombra de forma implícita — [arXiv 2504.04717](https://arxiv.org/html/2504.04717v6)
- Correferencia con cadena de razonamiento y reescritura del diálogo, junio de 2025, para mejorar el enlace de entidades — [arXiv 2506.12496](https://www.arxiv.org/pdf/2506.12496v1)
- Semantic Anchoring, agosto de 2025: liga las menciones a ids de entidad persistentes entre turnos; sacar la correferencia empeora la coherencia — [arXiv 2508.12630](https://arxiv.org/pdf/2508.12630)
- Razonar sobre las descripciones de los objetos mejora la correferencia en diálogo de tareas, 2026 — [arXiv 2604.27850](https://arxiv.org/pdf/2604.27850)
- DiscoTrack, 2025, benchmark multilingüe de seguimiento del discurso — [arXiv 2510.17013](https://arxiv.org/pdf/2510.17013); tarea compartida CRAC sobre si los LLM le ganan a los sistemas clásicos de correferencia — [arXiv 2509.17796](https://arxiv.org/pdf/2509.17796); [CRAC 2026](https://arxiv.org/pdf/2605.16984)

### Inferences
- Para "la primera que te pregunté", lo confiable es que el código guarde una lista ordenada de lo mostrado, con id, turno y posición, y que el modelo sólo elija un índice o un id de esa lista. Resolver contra el historial en texto falla por la causa del punto 4. Encaja con la regla 7.0 del CLAUDE.md: la identidad la decide una función con tres veredictos, y ante `ambiguous` se repregunta.

### Gaps
- No encontré un benchmark ni un número sobre referencias ordinales del tipo "la primera" o "la segunda" en charlas comerciales, ni en español.

## 6. Prácticas de ingeniería de contexto publicadas en 2025 y 2026

### Takeaway
Las guías de 2025 y 2026 coinciden en que el contexto es un recurso finito que se degrada al crecer. La receta es contexto mínimo y de alta señal, notas estructuradas fuera de la ventana y el objetivo o el estado actual repetido al final del contexto.

### Cited Findings
- Anthropic, septiembre de 2025: el contexto es finito y se pudre al crecer, la precisión de extracción cae con el largo. Propone compactación, notas estructuradas fuera de la ventana y subagentes — [Anthropic, effective context engineering](https://anthropic.com/research/effective-context-engineering-for-ai-agents)
- Anthropic, arneses para agentes largos: cada sesión arranca sin memoria y hay que dejar el estado escrito para la siguiente — [Anthropic engineering](https://anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- Manus, 18-jul-2025: reescribir un todo.md para mantener los objetivos en la atención reciente, la "recitación". Una crítica posterior dice que eso gastaba cerca de 30% de los tokens y propone un subagente planificador; ese 30% sale de un blog, no de Manus — [Manus](https://www.manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus); [resumen en agentic-ai](https://agentic-ai.readthedocs.io/en/latest/ContextEngineering/manus/); [Phil Schmid, parte 2](https://www.philschmid.de/context-engineering-part-2)
- "When Attention Closes", 2026, sobre cómo los LLM pierden el hilo en interacciones de varios turnos — [arXiv 2605.12922](https://arxiv.org/pdf/2605.12922)
- Estrategias de producción recopiladas por ZenML — [ZenML](https://www.zenml.io/llmops-database/context-engineering-strategies-for-production-ai-agents)

### Inferences
- Para el bot, lo aplicable es que en cada turno el modelo reciba un bloque corto y fijo con el pedido vigente, lo mostrado y numerado, y el destino si ya está, al final del prompt; y que el historial crudo vaya recortado. Es la recitación de Manus, pero escrita por el código, sin gastar una llamada.

### Gaps
- No encontré mediciones publicadas de estas prácticas en bots de venta por WhatsApp, ni comparaciones de recitación contra no recitación con números.
