# Frameworks y arquitecturas de diálogo orientado a tareas: LLM más lógica determinista, estado a noviembre 2026

Nota de método: se hicieron 17 llamadas de búsqueda o lectura. rasa.com y arxiv.org no resolvieron en la red de esta sesión, así que lo de Rasa docs y lo de arXiv sale de fragmentos de búsqueda y de los repos de GitHub, no de leer el texto completo. Donde un número viene sólo de un fragmento de búsqueda se marca "de fragmento".

## Rasa CALM: cómo restringe al LLM y qué evidencia publica

### Takeaway
CALM sigue siendo el ejemplo más maduro de "el LLM sólo emite comandos, los flows corren en código": el LLM traduce el mensaje a un conjunto fijo de comandos, el estado y los pasos los ejecuta el motor de flows. Rasa no publica una tasa de alucinación; publica precisión de generación de comandos, y su repo de comparación con LangGraph tiene una suite chica, 14 tests.

### Cited Findings
- El command generator emite un conjunto fijo de comandos mantenidos por Rasa, como StartFlowCommand, CancelFlowCommand y SetSlotCommand; existen variantes de generador, CompactLLMCommandGenerator y SearchReadyLLMCommandGenerator, de fragmento — [Rasa docs, command generator](https://rasa.com/docs/pro/customize/command-generator)
- Los docs de CALM describen la arquitectura como una que mantiene la charla fluida pero "no adivina tu lógica de negocio", sin cifra de alucinación, de fragmento — [Rasa docs, CALM](https://rasa.com/docs/learn/concepts/calm)
- Rasa 3.16, primavera 2026: dicen que en sus benchmarks GPT-5.2 y los Claude recientes superan a GPT-4o en precisión de generación de comandos, y traen plantillas de prompt afinadas para GPT-5.1, GPT-5.2 y Claude Sonnet 4.5; el fragmento no da los números — [Rasa blog, Spring 2026](https://rasa.com/blog/behind-the-release-notes-product-updates-spring-2026)
- Hay herramienta de "Dialogue Understanding Tests" que mide precisión total por turno y precisión, recall y F1 por comando — [Rasa docs, DU tests](https://rasa.com/docs/reference/testing/e2e/dialogue-understanding-tests)
- Repo de comparación CALM contra el ejemplo de soporte de LangGraph, con Rasa 3.17.2: 14 de 14 tests en gpt-4o y 14 de 14 en gpt-5.2; categorías de prueba: caminos felices, correcciones de slot, cambios de contexto, cancelaciones y multi-habilidad. En una corrida de 5 tests felices, por mensaje del usuario: costo medio 0,031 dólares, unos 1.017 tokens de prompt, 10,4 de salida, latencia media 2,57 s y máxima 4,78 s. El README no publica los números de LangGraph — [GitHub RasaHQ/calm-langgraph-customer-service-comparison](https://github.com/RasaHQ/calm-langgraph-customer-service-comparison)
- Hay modelos afinados para generar comandos, por ejemplo Llama 3.1 8B, con F1 por tipo de comando como métrica — [Hugging Face rasa/command-generator-llama-3.1-8b-instruct](https://huggingface.co/rasa/command-generator-llama-3.1-8b-instruct)
- El Rasa open source clásico está prácticamente quieto: último release 3.6.21 del 14-ene-2025, el anterior de abril 2024; el README apunta a "Hello Rasa" y CALM como el futuro, que es Rasa Pro, con licencia comercial — [GitHub RasaHQ/rasa releases](https://github.com/RasaHQ/rasa/releases); [GitHub RasaHQ/rasa](https://github.com/rasahq/rasa)

### Inferences
- Lo que se traslada al bot: el LLM produce un comando chico y tipado por turno, del tipo arrancar pedido, setear slot, corregir, cancelar, y el código decide todo lo demás. La salida de 10 tokens por turno muestra lo acotado que queda el trabajo del modelo. Es la misma idea que la llamada única de Luna, pero con el vocabulario de comandos cerrado y versionado.
- CALM cubre explícitamente correcciones y cambios de contexto como comandos propios, que es justamente donde aparece la cascada entre turnos: la corrección no se infiere de un texto libre sino que es un comando que pisa un slot.
- 14 tests no alcanzan como evidencia de fiabilidad; es una muestra de que la arquitectura funciona, no una medición.

### Gaps
- No se encontró una tasa de alucinación publicada por Rasa ni las tablas numéricas del benchmark de 3.16.
- No se pudo leer cómo maneja CALM la baja confianza o la repregunta, los "patterns" de clarificación, porque rasa.com no resolvió.
- Fecha exacta y licencia de la última versión de Rasa Pro: no confirmadas.

## Parlant de Emcie

### Takeaway
Parlant está muy activo, con versión 4 desde el 2-nov-2026 y releases casi diarios, Apache 2.0, unas 18 mil estrellas. Su enfoque no es un flujo cerrado sino reglas contextuales que se cargan al prompt sólo cuando aplican, más journeys como procedimientos de varios turnos, revisión de herramientas antes de ejecutarlas y respuestas pre-aprobadas. No publica números medidos de precisión.

### Cited Findings
- 18,3 mil estrellas, 1,6 mil forks, licencia Apache-2.0; describe políticas en lenguaje natural que se traen sólo cuando son relevantes, respuestas enlatadas que el agente adapta, herramientas como funciones Python con decorador, y "tool reviews" que controlan acciones como reembolsos antes de correr. Afirma ser 20 a 100 veces más barato que plataformas cerradas, sin datos. El SOC 2 Type II es del Dashboard, no del framework — [GitHub emcie-co/parlant](https://github.com/emcie-co/parlant)
- Versión 4.0.0 el 2-nov-2026; la landing describe las reglas de comportamiento como guidelines contextuales que se emparejan con cada momento del diálogo; journeys como SOP de varios turnos que se adaptan a cómo interactúa el cliente — [next.parlant.io](https://next.parlant.io/); [README de Parlant](https://raw.githubusercontent.com/emcie-co/parlant/HEAD/README.md)
- Renombres anteriores: en 3.0 las "utterance templates" pasan a "canned responses"; en 3.3.0 aparecen las "transient guidelines" — [newreleases v3.0.1](https://newreleases.io/project/github/emcie-co/parlant/release/v3.0.1); [newreleases v3.3.0](https://newreleases.io/project/github/emcie-co/parlant/release/v3.3.0)
- Últimos releases: v4.0.5 del 12-nov-2026 suma Gemini 4 Hydrogen y un modelo "Gemini Decision 1" para ranquear reglas; v4.0.6 del 16-nov suma `parlant lint` con chequeos de comportamiento y de redacción de las respuestas enlatadas; v4.0.7 del 21-nov suma `exclude()` y `except_when=`, y una regla excluida no ofrece sus herramientas salvo que otra regla las habilite; v4.0.9 del 24-nov agrupa en una sola llamada la poda de reglas descubiertas y agrega `min_relevance_score` al recordador de herramientas — [GitHub Parlant releases](https://github.com/emcie-co/parlant/releases)
- En 4.0.6, las observaciones agrupan varias situaciones y cada regla tiene un id estable entre versiones — [newreleases v4.0.6](https://newreleases.io/project/github/emcie-co/parlant/release/v4.0.6)

### Inferences
- Parlant ataca un problema distinto al de CALM: no le saca al LLM la decisión del turno, sino que le achica el contexto a las reglas relevantes y ata las herramientas a esas reglas. La regla "una herramienta sólo existe si una regla activa la concede" es la parte más trasladable al bot, porque evita que el modelo cotice o cobre fuera de momento.
- Las respuestas enlatadas con lint son parecidas al verificador del bot: el texto final sale de plantillas aprobadas y el modelo sólo las adapta.
- Más llamadas por turno: emparejar reglas, ranquear, elegir herramientas, redactar. Para un bot de WhatsApp con modelo barato eso suma costo y latencia; no hay números publicados para estimarlo.

### Gaps
- No se encontró ninguna medición independiente de cumplimiento o precisión de Parlant.
- No se confirmó si en 4.0 "guidelines" pasó a llamarse "policies" u "observations" de forma oficial; los release notes usan rules, policies y observations.

## Otros proyectos 2025-2026 con la misma idea

### Takeaway
Del lado open source, lo nuevo con evidencia está en papers con código: Genie Worksheets de Stanford, Arbor de Sword Health y CoDial. De las herramientas de infraestructura sólo se pudo verificar el estado de Pipecat Flows y NeMo Guardrails; LangGraph, OpenAI Agents SDK, Botpress, Voiceflow y los de Microsoft y Google quedaron sin revisar por presupuesto de búsqueda.

### Cited Findings
- Genie Worksheets, Stanford OVAL: el desarrollador escribe una planilla declarativa; el runtime guarda el estado crítico, corre las consultas y las APIs y genera acciones deterministas que siguen el flujo declarado. Reportan hasta 20,5% de mejora sobre el estado del arte en StarV2 y superan al function calling del LLM, de 10,2% a 40,7% en su escenario, de fragmento. Publicado en ACL 2025; paquete PyPI genie-worksheets en beta 1.0.0b3 — [arXiv 2407.05674](https://arxiv.org/abs/2407.05674); [ACL 2025](https://preview.aclanthology.org/ingestion-acl-25/2025.acl-long.1323.pdf); [PyPI](https://pypi.org/project/genie-worksheets/); [sitio](https://ws.genie.stanford.edu/)
- Arbor, Sword Health, arXiv 2602.14643, primera versión 16-feb-2026, v4 del 20-jul-2026: árbol de decisión como DAG; en cada turno se traen sólo las aristas salientes del nodo actual, una llamada LLM dedicada evalúa la transición válida y otra llamada separada redacta. Promediando modelos, mejora la precisión de navegación 29 puntos y baja la varianza; 97,3% de aceptación clínica según el anuncio del vendedor; en la tabla, Claude Sonnet 4.5 con Arbor 91,15% — [arXiv 2602.14643](https://arxiv.org/abs/2602.14643); [Sword Health](https://swordhealth.com/newsroom/arbor-healthcare-conversation-flows-framework)
- CoDial, arXiv 2506.02264, junio 2025: representa los flujos como grafo heterogéneo, CHIEF, y genera con el LLM código de guardrails ejecutables a partir del flujo, sin entrenamiento — [arXiv 2506.02264](https://arxiv.org/html/2506.02264v1)
- Conversation Routines, arXiv 2501.11613, 2025: marco de ingeniería de prompts para diálogos de tareas; no se leyó en detalle — [arXiv 2501.11613](https://arxiv.org/html/2501.11613v3)
- GRACE, de Mentomy AI, arXiv 2609.07152, 2026: un compilador convierte la intención de negocio en objetivos fijos, vector de prioridades, preguntas canónicas y estado inicial; en ejecución recibe historial, mensaje, estado y la respuesta de un RAG separado. Evalúan escenarios estándar, multi-objetivo, desvío a RAG, validación, rechazo y robustez; los números no se pudieron leer — [arXiv 2609.07152](https://arxiv.org/pdf/2609.07152)
- Pipecat Flows: 628 estrellas, BSD-2-Clause; desde pipecat-ai 1.5.0 vive dentro del paquete principal y el paquete suelto quedó congelado — [GitHub pipecat-ai/pipecat-flows](https://github.com/pipecat-ai/pipecat-flows)
- NeMo Guardrails de NVIDIA: 7,6 mil estrellas, Apache 2.0; la versión 0.25.0 depreca `LLMRails` a favor de `IORails`; latencia agregada con LLM simulado, concurrencia 64: IORails 13 ms p50 y 126 ms p99, contra 93 ms y 2.094 ms de LLMRails. El README actual habla de chequeos de entrada y salida, control de tema y rails de herramientas, no de dialog rails — [GitHub NVIDIA/NeMo-Guardrails](https://github.com/NVIDIA/NeMo-Guardrails)
- Microsoft Copilot Studio tiene una guía de cómo elegir el control de la conversación en agentes de voz, no leída — [Microsoft Learn](https://learn.microsoft.com/en-us/microsoft-copilot-studio/guidance/voice-agents-control-conversation)

### Inferences
- Arbor es el patrón más cercano al problema del bot y con mejor número: limitar en cada turno lo que el modelo puede elegir a las salidas válidas del estado actual, y separar la decisión de la redacción. Es parecido a lo que el bot hace con los candidatos de la tienda, aplicado a las transiciones del pedido.
- Genie y GRACE comparten la idea de declarar el flujo en una planilla o un compilador y que el runtime, no el modelo, guarde el estado; es la forma de que la memoria de la charla no dependa del texto del historial.
- NeMo Guardrails parece haberse corrido hacia filtros de entrada y salida, menos hacia controlar el diálogo con Colang; inferencia del README, no confirmada.

### Gaps
- Sin revisar: LangGraph, OpenAI Agents SDK con handoffs y guardrails, Botpress, Voiceflow, Google Conversational Agents y el estado de Colang 2.
- Últimas fechas de release de Pipecat Flows y NeMo Guardrails: las páginas de GitHub no las mostraban.

## Papers 2025-2026: estado de diálogo, control simbólico, fiabilidad en varios turnos, cascada y repregunta

### Takeaway
La evidencia 2025-2026 dice dos cosas útiles: los LLM pierden mucho en charlas de varios turnos porque asumen temprano y se aferran a eso, y la validación simbólica del estado en cada turno, con un lazo acotado de autocorrección, mejora medible el seguimiento del estado. Sobre cuándo repreguntar, la evidencia es mixta: ayuda en pruebas controladas pero los usuarios esperan respuestas inmediatas.

### Cited Findings
- Laban y otros, "LLMs Get Lost In Multi-Turn Conversation", arXiv 2505.06120, ICLR 2026: todos los LLM probados rinden bastante peor en varios turnos, con caída media de 39% en seis tareas; la caída es sobre todo aumento de inestabilidad, no de aptitud; los modelos asumen en los primeros turnos, intentan cerrar antes de tiempo y se apoyan demasiado en esas suposiciones — [arXiv 2505.06120](https://arxiv.org/abs/2505.06120v1); [ICLR 2026](https://iclr.cc/virtual/2026/oral/10009147)
- Liu y otros, arXiv 2602.07338, 2026: lo explican como desajuste de intención; pedirle al modelo que repregunte funciona en pruebas controladas pero choca con las normas reales de ayuda, porque el usuario espera una respuesta provisoria inmediata y no repreguntas repetidas — [arXiv 2602.07338](https://arxiv.org/html/2602.07338v1)
- Estudio de degradación en RAG de varios turnos, arXiv 2609.36700: consolidar la conversación, reescribirla como un pedido único, puede recuperar todo lo perdido en algunas familias de recuperación; el resultado no se leyó entero — [arXiv 2609.36700](https://arxiv.org/pdf/2609.36700)
- ReacTOD, Amazon, TrustNLP 2026, arXiv 2605.19077: convierte la comprensión en llamadas a herramientas discretas dentro de un lazo ReAct acotado con validación determinista; el validador simbólico corrige 93,1% de los errores que intercepta; el lazo suma hasta 9,3 puntos sobre una sola pasada en MultiWOZ; en MultiWOZ 2.1 cero-shot, gpt-oss-20B da 52,71% de precisión de meta conjunta contra 38,71% del mejor anterior; Qwen3-8B 47,34%; en SGD, Claude Opus 4.6 80,68% y Qwen3-32B 64,09%. Sólo necesita el esquema del dominio y predice el estado de forma incremental — [arXiv 2605.19077](https://arxiv.org/html/2605.19077v1); [ACL Anthology](https://aclanthology.org/2026.trustnlp-main.21/)
- NL-DST, arXiv 2503.08857, marzo 2025: reemplaza el estado por slots con resúmenes en lenguaje natural, evaluado en MultiWOZ 2.1 y Taskmaster-1 — [arXiv 2503.08857](https://arxiv.org/pdf/2503.08857)
- Seguimiento de estado con varios usuarios, arXiv 2506.10504: caída significativa contra el caso de un usuario — [arXiv 2506.10504](https://arxiv.org/pdf/2506.10504)

### Inferences
- La cascada del bot calza con lo que mide Laban: el error no es de no saber sino de fijar una suposición en un turno y arrastrarla. Las dos defensas con evidencia son guardar el estado fuera del texto y validarlo en cada actualización, como ReacTOD y CALM, y reescribir la charla como un pedido consolidado antes de buscar, como el estudio de RAG.
- ReacTOD da una regla práctica para la repregunta: si el validador determinista rechaza la actualización del estado, el lazo reintenta un número acotado de veces, y si no converge se repregunta. Eso coincide con la regla del repo de que vale acertar o repreguntar y lo que importa es no errar, y con el veredicto ambiguous de la regla técnica 0.
- Por lo de Liu, la repregunta conviene sólo cuando falta un dato que cambia el precio o el producto, no por cualquier duda; en el resto, respuesta provisoria con lo que hay.

### Gaps
- No se leyeron los textos completos de estos papers; los números vienen de abstracts y fragmentos.
- No se encontró ningún paper 2025-2026 que mida la cascada de errores entre turnos en un bot de ventas real con catálogo.
