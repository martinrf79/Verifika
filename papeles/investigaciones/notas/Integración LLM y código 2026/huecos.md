# Huecos de la primera ronda: frameworks, Rasa CALM en detalle, evaluación, decodificación restringida, incertidumbre y verificación, a fines de noviembre de 2026

Nota de método: las versiones, fechas y licencias salen de PyPI y npm consultados el 26-nov-2026, que es la fuente más fresca que se pudo leer. La API de GitHub no estaba habilitada en esta sesión, así que no hay estrellas ni changelogs de GitHub. rasa.com y arxiv.org se leyeron por descarga directa; openai.github.io, promptfoo.dev, docs.nvidia.com, google.github.io, langfuse.com, inspect.aisi.org.uk y taubench.com quedaron bloqueados, y tau-bench.com redirige a taubench.com, así que lo de esos sitios viene de fragmentos de búsqueda.

## 1. Frameworks de agentes como máquinas de estado: LangGraph, OpenAI Agents SDK, Google ADK, Microsoft Agent Framework, Botpress, Voiceflow, NeMo Guardrails con Colang 2

### Takeaway
Los cinco grandes SDK convergieron en lo mismo durante 2026: grafo explícito de nodos, estado con checkpoints, pausa durable para un humano y guardrails como funciones que cortan la corrida. Ninguno publica una tasa de fiabilidad medida de la conversación; lo que dan es infraestructura, no exactitud. Para un bot que ya tiene su tubería determinista, aportan poco más que persistencia y pausa, y suman una dependencia que se mueve cada dos semanas.

### Cited Findings
Versiones y licencias al 26-nov-2026
- LangGraph 1.2.24, publicado el 20-nov-2026, licencia MIT — [PyPI langgraph](https://pypi.org/project/langgraph/)
- OpenAI Agents SDK, paquete openai-agents 0.26.0, 24-nov-2026, MIT; sigue en versión cero — [PyPI openai-agents](https://pypi.org/project/openai-agents/)
- Google ADK, google-adk 2.15.1, 25-nov-2026, Apache 2.0 — [PyPI google-adk](https://pypi.org/project/google-adk/)
- Microsoft Agent Framework, agent-framework 1.26.0, 12-nov-2026, MIT — [PyPI agent-framework](https://pypi.org/project/agent-framework/)
- NeMo Guardrails, nemoguardrails 0.25.0, 19-nov-2026, Apache 2.0 — [PyPI nemoguardrails](https://pypi.org/project/nemoguardrails/)
- Botpress CLI 7.1.16, 23-nov-2026, MIT; la plataforma en sí es un servicio en la nube — [npm @botpress/cli](https://www.npmjs.com/package/@botpress/cli)

LangGraph
- Una interrupción suspende el grafo en el punto exacto donde se llama a interrupt y el valor de reanudación vuelve a esa llamada; exige un checkpointer, y en producción uno durable respaldado por base de datos — [LangGraph docs, interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- Al reanudar, el runtime vuelve a correr el nodo entero desde el principio, no desde la línea de interrupt; se desaconseja envolver interrupt en try y catch. Los esquemas tipados de respuesta a una interrupción piden langgraph 1.2.12 o más — [LangGraph docs, interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- Temporal, en un post del 16-jul-2026, sostiene que el checkpoint de LangGraph no es ejecución durable y propone correr los grafos como workflows de Temporal para sobrevivir caídas del proceso; es fuente de proveedor — [Temporal blog](https://temporal.io/blog/temporal-langgraph-plugin-durable-execution.md)

OpenAI Agents SDK
- Los guardrails de entrada corren sólo sobre el primer agente de la cadena; si salta el tripwire, el agente no se ejecuta, lo que evita gasto de tokens y efectos de herramientas — [OpenAI Agents SDK, guardrails](https://openai.github.io/openai-agents-python/guardrails/)
- Los guardrails de herramienta envuelven funciones: chequeo antes y después de la ejecución, con tres comportamientos, permitir, rechazar el contenido o lanzar excepción. Hay una opción para correr esos chequeos antes de la pausa de aprobación humana — [OpenAI Agents JS, guardrails](https://openai.github.io/openai-agents-js/guides/guardrails); [OpenAI, guardrails and approvals](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals)
- Los handoffs van por su propio canal, no por el de herramientas, así que los guardrails de herramienta no se aplican a un handoff; la documentación recomienda validar en la herramienta que produce el efecto o en los guardrails de agente — [OpenAI Agents SDK, guardrails](https://openai.github.io/openai-agents-python/guardrails/)

Google ADK
- ADK Python 2.0 salió en disponibilidad general el 19-may-2026 y Go el 30-jun-2026. El cambio central es un runtime de workflows por grafo: los agentes pasan a ser nodos, con ruteo, abanico y unión, bucles, reintento, estado, nodos dinámicos, humano en el lazo y workflows anidados — [ADK 2.0 docs](https://adk.dev/2.0/); [Google Developers Blog, Why we built ADK 2.0](https://developers.googleblog.com/en/why-we-built-adk-20/)
- En Go cualquier nodo puede pausar el grafo y preguntarle a un humano, y el workflow espera de forma durable — [Google Developers Blog, ADK Go 2.0](https://developers.googleblog.com/en/announcing-adk-go-20/)
- 2.0 trae cambios incompatibles en la API de agentes, el modelo de eventos y el esquema de sesión; las sesiones de 2.0 sólo las lee ADK 1.28 o más. La cadencia es de unas dos semanas — [ADK 2.0 docs](https://adk.dev/2.0/); [PyPI google-adk](https://pypi.org/project/google-adk/)

Microsoft Agent Framework
- Llegó a 1.0 con disponibilidad general el 3-abr-2026, para .NET y Python, como sucesor de Semantic Kernel y AutoGen, con workflows por grafo, checkpoints y humano en el lazo, y compromiso de compatibilidad hacia atrás desde 1.0 — [Microsoft devblogs, Agent Framework 1.0](https://devblogs.microsoft.com/agent-framework/microsoft-agent-framework-version-1-0/); [Visual Studio Magazine](https://visualstudiomagazine.com/articles/2026/04/06/microsoft-ships-production-ready-agent-framework-1-0-for-net-and-python.aspx)
- Sobre los predecesores las fuentes no coinciden: VentureBeat dice que AutoGen y Semantic Kernel quedan en mantenimiento, sin funciones nuevas; Visual Studio Magazine dice que Semantic Kernel sigue sacando versiones — [VentureBeat](https://venturebeat.com/orchestration/microsoft-retires-autogen-and-debuts-agent-framework-to-unify-and-govern); contradicho por [Visual Studio Magazine](https://visualstudiomagazine.com/articles/2026/04/06/microsoft-ships-production-ready-agent-framework-1-0-for-net-and-python.aspx)

Botpress y Voiceflow
- El nodo autónomo de Botpress corre sobre LLMz, un paso único dirigido por el LLM que interpreta instrucciones, maneja memoria, elige herramientas y ejecuta código — [Botpress docs, autonomous node](https://botpress.com/docs/learn/reference/nodes/autonomous-node); [Botpress blog](https://botpress.com/blog/autonomous-nodes)
- Botpress atribuye la fiabilidad a mezclar cadena de razonamiento con su protocolo propio de llamadas a herramientas; es afirmación del fabricante sin cifra. Un modelo chico puede truncar partes del prompt y perder parámetros de herramientas — [Botpress blog](https://botpress.com/blog/autonomous-nodes); [Botpress docs, different LLM](https://www.botpress.com/docs/studio/guides/how-to/different-an-models/)
- Un artículo de testing de terceros advierte que el nodo autónomo puede rutear distinto con la misma entrada y que cambiar la versión de LLMz o el modelo mueve ruteo y redacción sin que el emulador lo vuelva a chequear — [TestMu AI blog](https://www.testmuai.com/blog/botpress-chatbot-testing/)
- Voiceflow V4 separa playbooks, agénticos y guiados por instrucciones, de workflows, deterministas y paso a paso; el paso Playbook deja que un workflow le pase el control a una charla flexible y vuelva a su lógica fija. Las entry conditions son chequeos deterministas que tienen que dar verdadero para que el agente pueda rutear a un playbook — [Voiceflow docs, playbook step](https://docs.voiceflow.com/documentation/build/steps/playbook.md); [Voiceflow glossary](https://www.voiceflow.com/docs/resources/glossary/build/playbooks-workflows)
- El paso Operator rutea un workflow con un LLM que interpreta condiciones, a diferencia de los condicionales en código — [Voiceflow glossary](https://docs.voiceflow.com/resources/glossary/build)

NeMo Guardrails y Colang 2
- La guía de Colang 2.0 todavía lo llama beta, y la página principal dice que la biblioteca mantiene Colang 1.0 como default hasta que 2.0 salga de beta; no aparece aviso de deprecación — [NVIDIA docs, Colang 2](https://docs.nvidia.com/nemo/guardrails/latest/colang-2); [NVIDIA docs, Colang](https://docs.nvidia.com/nemo/guardrails/latest/configure-guardrails/colang.md)
- La primera ronda ya registró que 0.25.0 depreca LLMRails a favor de IORails y que el README habla de filtros de entrada y salida; este dato se complementa con la fecha de 0.25.0, 19-nov-2026 — [PyPI nemoguardrails](https://pypi.org/project/nemoguardrails/)

### Inferences
- La idea común a ADK 2.0, Agent Framework, LangGraph y Voiceflow es la misma que ya usa el bot: el modelo decide en nodos chicos y el grafo determinista decide el camino. Voiceflow lo dice explícito con sus entry conditions deterministas, que equivalen a lo que hace el código del bot antes de dejar hablar al modelo.
- Lo transferible sin adoptar ninguno: la regla de LangGraph de que un nodo reanudado vuelve a correr entero obliga a que cada paso sea idempotente; vale para el turno del bot si se reintenta tras un error.
- El hueco de los handoffs del SDK de OpenAI, que no pasan por los guardrails de herramienta, muestra que en esos marcos la validación hay que ponerla donde está el efecto, que es lo que el ejecutor del bot ya hace con montos y envíos.
- Botpress y Voiceflow son plataformas cerradas en la parte que importa, el runtime; adoptarlas va contra la regla de un solo servicio vivo.
- Colang 2 lleva más de dos años en beta y NVIDIA movió el foco a filtros de entrada y salida; no es base firme para diálogo.

### Gaps
- No encontré ninguna medición publicada de fiabilidad conversacional, tasa de error por turno o pass a la k, de LangGraph, OpenAI Agents SDK, ADK, Agent Framework, Botpress ni Voiceflow. Sólo hay latencia de NeMo, ya registrada.
- No se pudo leer la página de handoffs del SDK de OpenAI, bloqueada, así que faltan los parámetros exactos de filtro de historial.
- Licencia de la plataforma Botpress y de Voiceflow: son servicios comerciales, sin licencia de código del runtime verificada.

## 2. Rasa CALM en detalle: comandos, correcciones, digresiones, clarificación y evaluación

### Takeaway
CALM fija un vocabulario cerrado de comandos que el LLM emite, recupera por embeddings sólo los flows relevantes para el prompt, y resuelve cada reparación de la charla con un pattern, que es un flow más y se puede sobrescribir. Corrección, interrupción, clarificación, cancelación, no puedo y derivación a humano son patterns separados. Rasa sigue sin publicar números de exactitud propios en la documentación.

### Cited Findings
Versión
- Rasa Pro 3.22.1, publicado el 25-nov-2026 en PyPI; la licencia no figura en los metadatos del paquete. Los generadores SingleStep y MultiStep están deprecados y se van en Rasa 4.0.0 — [PyPI rasa-pro](https://pypi.org/project/rasa-pro/); [Rasa docs, LLM command generators](https://rasa.com/docs/reference/config/components/llm-command-generators)

El juego de comandos
- El prompt del generador lista las acciones disponibles: start flow, para arrancar un flow; set slot, para llenar un slot del flow activo, que la propia documentación dice que sirve para corregir valores ya puestos; disambiguate flows con varios nombres, cuando el mensaje puede ir a varios flows; search and reply, para responder desde la base de conocimiento cuando ningún flow sirve, incluido lo social; cancel flow; y repeat message, repetir el último mensaje del bot — [Rasa docs, LLM command generators](https://rasa.com/docs/reference/config/components/llm-command-generators)
- La otra variante de prompt cambia search and reply por provide info, para preguntas frecuentes, y offtopic reply, para lo social; el ejemplo distingue "cómo cambio el PIN" como provide info de "no sé qué tan segura es la digitalización" como offtopic — [Rasa docs, LLM command generators](https://rasa.com/docs/reference/config/components/llm-command-generators)
- Reglas del prompt: arrancar un flow sólo si el mensaje está claro y lo cubre por completo la descripción, sin estirar su alcance; no llenar slots con valores abstractos ni de relleno; en slots categóricos, igualar a los valores permitidos o usar other; extraer el texto tal como lo dio el usuario; todo concepto mencionado tiene que recibir su set slot — [Rasa docs, LLM command generators](https://rasa.com/docs/reference/config/components/llm-command-generators)
- Los recomendados son CompactLLMCommandGenerator y SearchReadyLLMCommandGenerator, este último cuando el generador dispara búsqueda en documentos; minimize_num_calls viene activo por defecto. Si el adaptador de NLU clásico y el LLM emiten StartFlow distintos, gana el del adaptador — [Rasa docs, LLM command generators](https://rasa.com/docs/reference/config/components/llm-command-generators)
- Recuperación de flows: viene activa, con embeddings text-embedding-3-large por defecto; parámetros turns_to_embed, por defecto 1, sólo el último turno; should_embed_slots, por defecto verdadero; num_flows, por defecto 20, que no es igual a los flows que entran, porque se suman los marcados como siempre incluidos — [Rasa docs, LLM command generators](https://rasa.com/docs/reference/config/components/llm-command-generators)

Reparación de la charla, los patterns
- Lista vigente: pattern_continue_interrupted para interrupciones, pattern_correction, pattern_cancel_flow, pattern_skip_question, pattern_chitchat, pattern_completed, pattern_clarification, pattern_internal_error, pattern_external_agent_processing para mensajes que llegan mientras corre una tarea A2A, pattern_cannot_handle, pattern_human_handoff, pattern_session_start, pattern_validate_slot para validaciones independientes de la lógica de negocio, pattern_repeat_bot_messages, pattern_customer_satisfaction, y pattern_user_silence para voz. Cada uno es un flow con la misma sintaxis y se sobrescribe definiéndolo en el proyecto — [Rasa docs, patterns](https://rasa.com/docs/reference/primitives/patterns)
- Corrección: si el contexto indica que es sólo un reseteo, aplica action_correct_flow_slot directo; si no, pregunta "querés actualizar tal slot", con sí y no, y sólo corrige si el usuario confirma — [Rasa docs, patterns](https://rasa.com/docs/reference/primitives/patterns)
- Digresión e interrupción: cuando el usuario salta a otro flow, pattern_continue_interrupted pregunta al terminar si quiere seguir con el interrumpido; si hay varios interrumpidos, llena un slot con el nombre del que quiere continuar o none, y cancela los demás — [Rasa docs, patterns](https://rasa.com/docs/reference/primitives/patterns)
- Clarificación: por defecto le ofrece al usuario una lista de flows posibles, máximo 3 opciones, configurable con el slot max_clarification_options desde 3.15. Por defecto sigue preguntando sin límite; la documentación propone contar las clarificaciones y derivar a humano al pasar un umbral. Desde 3.15, con CLARIFY_ON_MULTIPLE_START_FLOWS, si el generador predice varios StartFlow sin flow activo, pregunta en vez de arrancarlos en fila; con un flow activo no cambia — [Rasa docs, patterns](https://rasa.com/docs/reference/primitives/patterns)
- No puedo: pattern_cannot_handle distingue razones, chitchat sin política, no soportado, y sin respuesta relevante en la búsqueda; por defecto pide que el usuario reformule — [Rasa docs, patterns](https://rasa.com/docs/reference/primitives/patterns)
- Chitchat libre: las respuestas las genera un LLM y la documentación admite que pueden contestar fuera del dominio — [Rasa docs, patterns](https://rasa.com/docs/reference/primitives/patterns)
- Error interno: pattern_internal_error ramifica por tipo, entrada demasiado larga, entrada vacía, falla de herramienta MCP o de agente, y permite un mensaje propio por herramienta, por ejemplo si falla la de colocar la orden — [Rasa docs, patterns](https://rasa.com/docs/reference/primitives/patterns)
- Las respuestas fijas de los patterns pueden pasar por el Contextual Response Rephraser con rephrase verdadero en su metadata — [Rasa docs, patterns](https://rasa.com/docs/reference/primitives/patterns)

Evaluación publicada
- La primera ronda ya registró los Dialogue Understanding Tests y el repo de comparación con LangGraph de 14 tests; en la documentación leída ahora no aparece ninguna tabla nueva de exactitud — [Rasa docs, LLM command generators](https://rasa.com/docs/reference/config/components/llm-command-generators)

### Inferences
- El vocabulario de CALM tiene un comando para cada salida que hoy el bot resuelve a mano: disambiguate flows es la repregunta ante ambigüedad, search and reply o provide info es responder desde la ficha, cancel flow, set slot para corregir, repeat message. Lo que el bot no tiene como pieza propia es la corrección con confirmación y la reanudación del flow interrumpido.
- La corrección de CALM confirma antes de pisar el slot, salvo reseteo; para el pedido del bot, donde un cambio de cantidad o producto toca la plata, ese paso de confirmación es barato y corta la cascada de un slot mal pisado.
- El tope de tres opciones y el contador de clarificaciones que deriva a humano son reglas simples para que repreguntar no se vuelva un bucle.
- turns_to_embed en 1 por defecto muestra que Rasa recupera sólo con el último mensaje; en el bot, la memoria de lo que ya vio el cliente cumple el rol de no perder el contexto para "esa".

### Gaps
- Rasa no publica en estas páginas exactitud del generador de comandos por modelo, ni tasa de clarificaciones innecesarias.
- Licencia exacta de Rasa Pro 3.22: no figura en PyPI; la primera ronda la marcó como comercial.
- No se leyeron los release notes de 3.16 a 3.22 en detalle.

## 3. Herramientas abiertas de evaluación de agentes y simuladores de usuario

### Takeaway
Todas las herramientas siguen vivas, con versiones de esta semana, y casi todas tienen simulador de usuario multi-turno inspirado en tau-bench. La evidencia de 2026 es dura con esos simuladores: son demasiado cooperativos y inflan el éxito del agente, el mejor queda en 76 contra 92,9 de humanos en un índice de parecido, y cambiar el modelo del usuario simulado mueve el éxito hasta 9 puntos.

### Cited Findings
Versiones y licencias al 26-nov-2026
- Inspect, del AISI británico, inspect-ai 0.3.292, 23-nov-2026, MIT — [PyPI inspect-ai](https://pypi.org/project/inspect-ai/)
- Promptfoo 0.126.0, 18-nov-2026, MIT — [npm promptfoo](https://www.npmjs.com/package/promptfoo)
- DeepEval 4.3.6, 25-nov-2026, Apache 2.0 — [PyPI deepeval](https://pypi.org/project/deepeval/)
- Langfuse SDK de Python 5.2.0, 5-nov-2026, MIT — [PyPI langfuse](https://pypi.org/project/langfuse/)
- Arize Phoenix 22.1.0, 26-nov-2026, licencia Elastic 2.0, que no es de código abierto según OSI y restringe ofrecerlo como servicio — [PyPI arize-phoenix](https://pypi.org/project/arize-phoenix/)
- Braintrust SDK 0.53.0, 26-nov-2026, MIT; autoevals 0.5.0, 19-nov-2026; la plataforma de Braintrust es comercial — [PyPI braintrust](https://pypi.org/project/braintrust/); [PyPI autoevals](https://pypi.org/project/autoevals/)

Langfuse
- Liberó todas las funciones de producto bajo MIT el 4-jun-2025; el repo es MIT salvo las carpetas ee, que cubren SCIM, auditoría, RBAC por proyecto, etiquetas protegidas y retención de datos. Se puede autohospedar sin clave de licencia — [Langfuse changelog](https://langfuse.com/changelog/2025-06-04-open-sourcing-langfuse.md); [Langfuse clarifications](https://langfuse.com/resources/engineering/clarifications)
- Un análisis de terceros dice que ClickHouse compró Langfuse en enero de 2026 y que el anuncio mantiene el código abierto y el autohospedaje — [DEV Community](https://dev.to/beton/langfuse-pricing-teardown-2026-2pi9)

Simuladores de usuario en las herramientas
- Promptfoo tiene el proveedor promptfoo:simulated-user, inspirado en tau-bench, con maxTurns, instructions para la persona e initialMessages; supone que el destino acepta mensajes en formato chat de OpenAI. Trae un ejemplo con 31 personas de cliente y aserciones. La estrategia de red team Mischievous User hace lo mismo con un usuario que busca romper al agente — [Promptfoo docs, simulated user](https://www.promptfoo.dev/docs/providers/simulated-user); [Promptfoo docs, mischievous user](https://www.promptfoo.dev/docs/red-team/strategies/mischievous-user/)
- DeepEval tiene ConversationSimulator: genera un turno de usuario, lo manda a la app por callback y registra la respuesta hasta terminar; devuelve casos conversacionales para sus métricas multi-turno; el usuario se guía con una descripción y un grafo de simulación opcional — [DeepEval docs, conversation simulator](https://deepeval.com/docs/conversation-simulator)
- MLflow tiene un ConversationSimulator equivalente, con objetivo, persona opcional y pautas que el usuario simulado tiene que respetar — [MLflow docs](https://mlflow.org/docs/latest/genai/eval-monitor/running-evaluation/conversation-simulation.md)
- AWS lo ofrece en Strands Evals y Bedrock AgentCore — [AWS blog](https://aws.amazon.com/blogs/machine-learning/simulate-realistic-users-to-evaluate-multi-turn-ai-agents-in-strands-evals); [AWS docs](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/user-simulation.html)

Qué tan buenos son los simuladores, evidencia 2025-2026
- Mind the Sim2Real Gap, marzo de 2026, revisado en julio: primer estudio con el protocolo completo de tau-bench con humanos reales, 451 participantes y 165 tareas, contra 31 simuladores. El mejor simulador saca 76,0 en su índice USI frente a 92,9 de humanos. Los simuladores son excesivamente cooperativos, uniformes y sin frustración ni ambigüedad, un modo fácil que infla el éxito del agente por encima del de humanos; dan feedback más positivo; más capacidad general no da más fidelidad — [arXiv 2603.11245](https://arxiv.org/abs/2603.11245)
- Lost in Simulation, enero de 2026: en tau-bench retail con usuarios de Estados Unidos, India, Kenia y Nigeria, el éxito del agente varía hasta 9 puntos según el LLM que hace de usuario; subestiman en tareas difíciles y sobreestiman en las medianas; peor proxy para hablantes de AAVE e inglés indio — [arXiv 2601.17087](https://arxiv.org/abs/2601.17087)
- UGST, julio de 2025: los LLM cuesta que sigan orientados al objetivo en varios turnos cuando simulan al usuario — [arXiv 2507.20152](https://arxiv.org/pdf/2507.20152.pdf)
- SAGE: personas armadas desde la lógica de negocio encuentran 33% más fallas que los métodos previos, cifra de los autores — [arXiv 2510.11997](https://arxiv.org/pdf/2510.11997v3)
- RUT-Bench, junio de 2026, modela usuarios poco cooperativos o ambiguos — [arXiv 2606.03318](https://arxiv.org/html/2606.03318v1)
- UserProxyBench, en NeurIPS 2026, mide qué tan fiel sigue un simulador sus instrucciones privadas — [NeurIPS 2026](https://neurips.cc/virtual/2026/160096)

### Inferences
- Para el bot, las 26 charlas grabadas con clientes reales valen más que cualquier simulador: la evidencia dice que el usuario simulado es más fácil que el real. Un simulador sirve para generar volumen de variantes, no para dar el número que decide.
- Si se usa un simulador, que sea con personas armadas desde lo que falló en producción, al estilo SAGE, y con instrucciones de ser ambiguo o cambiar de idea, que es lo que los simuladores no hacen solos.
- En licencias: Inspect, Promptfoo y DeepEval son libres de verdad; Phoenix es Elastic 2.0; Langfuse es MIT salvo lo de empresa. Ninguna exige cambiar la vara actual del repo.

### Gaps
- No pude leer la documentación de Inspect sobre agentes ni de Phoenix sobre evaluaciones, sitios bloqueados.
- No encontré comparación independiente entre estas herramientas.
- El leaderboard de tau-bench no se pudo leer: tau-bench.com redirige a taubench.com, bloqueado.

## 4. Decodificación restringida y salida estructurada: versiones, licencias y benchmarks independientes

### Takeaway
Las bibliotecas siguen activas y con licencias permisivas. La única comparación amplia sigue siendo JSONSchemaBench de enero de 2025, ya registrada en la primera ronda, y la mantiene el equipo de Guidance, que compite. Para un bot que usa modelos por API, la restricción la hace el proveedor; lo que se elige del lado propio es la validación y el reintento, Instructor o Pydantic AI, o el parseo tolerante de BAML.

### Cited Findings
Versiones y licencias al 26-nov-2026
- Outlines 1.3.3, 6-ago-2026, Apache 2.0 — [PyPI outlines](https://pypi.org/project/outlines/)
- XGrammar 0.2.9, 9-nov-2026, Apache 2.0 — [PyPI xgrammar](https://pypi.org/project/xgrammar/)
- llguidance 1.9.1, 30-sep-2026, MIT — [PyPI llguidance](https://pypi.org/project/llguidance/)
- Guidance 0.3.1, 3-feb-2026; la licencia no figura en los metadatos — [PyPI guidance](https://pypi.org/project/guidance/)
- Instructor 1.18.0, 26-nov-2026, MIT — [PyPI instructor](https://pypi.org/project/instructor/)
- Pydantic AI 2.75.0, 25-nov-2026, MIT — [PyPI pydantic-ai](https://pypi.org/project/pydantic-ai/)
- BAML, paquete baml-py 0.226.3, 28-oct-2026, sigue en versión cero; la licencia no figura en los metadatos — [PyPI baml-py](https://pypi.org/project/baml-py/)

Benchmarks
- JSONSchemaBench, arXiv 2501.10868, ICML 2025: unos 10.000 esquemas reales en 10 conjuntos, seis marcos, Guidance, Outlines, llama.cpp, XGrammar, OpenAI y Gemini. La decodificación restringida, sea cual sea el marco, rinde más que sin restricción y puede acelerar la generación hasta 50%. Lo publica el repositorio de guidance-ai, con autores de Microsoft y EPFL — [arXiv 2501.10868](https://arxiv.org/abs/2501.10868); [ICML 2025](https://icml.cc/virtual/2025/51849)
- El paper de XGrammar se compara contra Outlines, la gramática de llama.cpp y lm-format-enforcer en latencia de máscara por token y dice ganar siempre; es autoevaluación — [arXiv 2411.15100](https://arxiv.org/pdf/2411.15100)

### Inferences
- Para el bot, que llama a Gemini y modelos gratis por OpenRouter, Outlines, XGrammar y llguidance sólo sirven si se corre un modelo propio; con API, la gramática la aplica el proveedor o no se aplica.
- Lo que sí cambia la exactitud en esta tubería es validar el JSON contra un esquema con los ids posibles como enumeración y reintentar con el error; Instructor y Pydantic AI hacen eso, y son MIT. Ya lo cubre en parte el verificador del bot.

### Gaps
- No encontré un benchmark independiente 2025-2026 que incluya llguidance, ni uno que compare Instructor, Pydantic AI y BAML en exactitud.
- No se pudieron leer los changelogs de GitHub, por eso no hay notas de qué cambió en cada versión.

## 5. Incertidumbre y abstención con modelos sólo por API

### Takeaway
Lo que funciona con API es muestrear varias veces y medir acuerdo, y calibrar el umbral con conformal sobre un conjunto etiquetado. El trabajo más directo para el bot es de febrero de 2026: autoconsistencia más calibración conformal da un nivel de fiabilidad por par sistema y tarea, con garantía a 1 sobre n más 1 del objetivo, y la parada secuencial ahorra cerca de 50% de llamadas. La entropía semántica se abarató: 47% menos muestras para la misma detección.

### Cited Findings
- Black-Box Reliability Certification, 24-feb-2026: un nivel de fiabilidad por par sistema y tarea, con autoconsistencia y calibración conformal, como compuerta de despliegue con garantías exactas en muestra finita y sin supuestos de distribución. La calibración garantiza acierto dentro de 1 sobre n más 1 del nivel buscado; las preguntas difíciles se ven como conjuntos de respuestas más grandes. GPT-4.1 gana 94,6% en GSM8K y 96,8% en TruthfulQA; GPT-4.1-nano 89,8% en GSM8K y 66,5% en MMLU. Cinco benchmarks, cinco modelos de tres familias; cobertura condicional en ítems resolubles mayor a 0,93 en todas las configuraciones; parar el muestreo de forma secuencial baja el costo de API alrededor de 50% — [arXiv 2602.21368](https://arxiv.org/abs/2602.21368)
- UniCR, septiembre de 2025, revisado en junio de 2026: junta verosimilitud, dispersión de autoconsistencia, compatibilidad con lo recuperado y la señal de herramientas o verificadores en una probabilidad calibrada de acierto, y abstiene para cumplir un presupuesto de error con control de riesgo conformal; funciona sólo con API. Dice mejorar calibración y cobertura a riesgo fijo frente a umbrales de entropía o logits; las causas dominantes de abstención son contradicción con la evidencia, dispersión semántica e inconsistencia de herramientas. El resumen no da cifras — [arXiv 2509.01455](https://arxiv.org/abs/2509.01455)
- Taming Variability, septiembre de 2025: un actuador en la interfaz de la API que decide mandar, abstenerse o escalar con control de riesgo conformal sobre un puntaje escalar de salidas opacas, sin etiquetas; variantes con bootstrap que bajan llamadas de calibración. Cuatro conjuntos de datos, sin cifras en el resumen — [arXiv 2509.23007](https://arxiv.org/abs/2509.23007)
- TECP, 2025: entropía de tokens de generaciones muestreadas dentro de conformal partido, sin logits; mejor cobertura y conjuntos más chicos que métodos de autoconsistencia previos en seis LLM, CoQA y TriviaQA — [arXiv 2509.00461](https://arxiv.org/html/2509.00461v1)
- Hallucination Detection on a Budget, TMLR septiembre de 2025: estimador bayesiano de entropía semántica que baja 47% en promedio las generaciones necesarias para la misma calidad de detección, útil aun con una muestra — [arXiv 2504.03579](https://arxiv.org/abs/2504.03579)
- Adaptive Bayesian Semantic Entropy, marzo de 2026, preprint: muestreo adaptativo por varianza; cerca de 50% menos muestras para igual detección y AUROC 12,6% mejor con el mismo presupuesto, cifras de los autores — [arXiv 2603.22812](https://arxiv.org/html/2603.22812v1)
- Entropy Alone is Insufficient for Safe Selective Prediction, marzo de 2026: el título sostiene que la entropía sola no alcanza para abstenerse de forma segura — [arXiv 2603.21172](https://arxiv.org/pdf/2603.21172)
- Conformal para clasificación de intención con repregunta, CICC, NAACL Findings 2024, material anterior: convierte el puntaje de cualquier clasificador en una pregunta de aclaración que contiene la intención verdadera con la confianza pedida, con un conjunto de calibración modesto y sin reentrenar; la cobertura es en promedio, no por entrada — [ACL Anthology 2024.findings-naacl.156](https://aclanthology.org/2024.findings-naacl.156)

### Inferences
- CICC encaja casi exacto con el bot: el conjunto conformal de candidatos es la lista de opciones de la repregunta; si tiene un elemento, se afirma; si tiene varios, se pregunta entre ellos; si está vacío, no se vende. Es la misma lógica de exists, ambiguous y not_found, pero con un umbral calibrado en vez de elegido a ojo.
- La autoconsistencia con parada secuencial es aplicable a la llamada que elige la fila: se muestrea dos o tres veces, si coinciden se sigue, si no se muestrea más o se repregunta. El costo extra cae sólo en los casos dudosos.
- Calibrar exige etiquetas; las 75 casillas de la vara ya son un conjunto chico de calibración, y la garantía de 1 sobre n más 1 dice que con unas 75 el margen es de algo más de un punto. La primera ronda ya advirtió que el cambio de catálogo rompe la intercambiabilidad y obliga a recalibrar.

### Gaps
- No encontré un trabajo 2025-2026 que aplique conformal a un clasificador LLM de intención o producto con cifras de tamaño de conjunto y tasa de repregunta.
- Las cifras de UniCR, Taming Variability y TECP no están en los resúmenes; no se leyeron los textos completos.

## 6. TextGrad y chain-of-verification, resultados nuevos

### Takeaway
TextGrad está quieto como paquete desde marzo de 2025 y lo nuevo son trabajos que lo superan o lo corrigen, con la crítica concreta de que el gradiente textual explota o se desvanece en tuberías profundas. Chain-of-verification no tiene resultados nuevos fuertes en 2025-2026; lo vigente sigue siendo la versión factorizada de 2024.

### Cited Findings
TextGrad
- El paquete textgrad está en 0.1.8, del 26-mar-2025, MIT; no hubo versiones en 2026 — [PyPI textgrad](https://pypi.org/project/textgrad/)
- El resultado original, material de 2024: en GPQA lleva la exactitud de cero disparos de 51% a 55% refinando la solución en tiempo de prueba — [arXiv 2406.07496](https://arxiv.org/html/2406.07496v1); [Stanford HAI](https://hai.stanford.edu/news/textgrad-autograd-text)
- Textual Equilibrium Propagation, enero de 2026, revisado en abril: en flujos agénticos largos el feedback textual explota con la profundidad, mensajes larguísimos que amplifican sesgos del evaluador, o se desvanece, pierde especificidad al viajar hacia atrás. Propone crítica local por módulo y ediciones acotadas; dice superar a TextGrad en QA de varios pasos y uso de herramientas multiagente, con ventaja que crece con la profundidad — [arXiv 2601.21064](https://arxiv.org/abs/2601.21064)
- TSGD-M, 2025: momento por muestreo para gradientes textuales, se integra en TextGrad, DSPy-COPRO y AdalFlow, mejoras en cinco benchmarks; envío anónimo, cifras provisorias — [arXiv 2506.00400](https://arxiv.org/html/2506.00400v3)
- DSPy, contra el que se compara, está en 3.5.0, 10-nov-2026, MIT — [PyPI dspy](https://pypi.org/project/dspy/)

Chain-of-verification
- CoVe, material de 2023 y 2024: borrador, preguntas de verificación, respuesta a cada una por separado y revisión; la variante factorizada, que responde sin ver el borrador, reduce copiar el mismo error y mejora en las tres tareas; los autores admiten que no elimina las alucinaciones — [ACL Anthology 2024.findings-acl.212](https://aclanthology.org/2024.findings-acl.212)
- Un trabajo de 2026, arXiv 2609.26229, combina autoverificación con recuperación; no pude confirmar sus cifras — [arXiv 2609.26229](https://arxiv.org/pdf/2609.26229)

### Inferences
- La crítica de TEP aplica de lleno a la tubería del bot: optimizar los prompts de la llamada 0 y la segunda llamada con un gradiente textual global sería propagar feedback por varias etapas, justo donde falla. Optimizar cada etapa contra su propia casilla, que es la medición por capas, es la versión local que TEP recomienda.
- Lo útil de CoVe para el bot es la idea factorizada, verificar cada afirmación sin ver el borrador, y eso ya lo hace mejor un verificador determinista contra las filas de la tienda.

### Gaps
- No encontré resultados 2025-2026 de CoVe con cifras de reducción de alucinación.
- No hay comparación independiente reciente de TextGrad contra GEPA o MIPROv2 en tareas de diálogo.
