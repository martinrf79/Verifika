# Arquitecturas cognitivas para agentes LLM que imitan el razonamiento humano, 2025 y 2026, y el código abierto que las implementa

Nota de método: búsquedas hechas el 26-nov-2026 contra la API de arXiv, export.arxiv.org, y el texto HTML de cada paper bajado entero; páginas de GitHub y blogs oficiales con fetch. La API de GitHub quedó bloqueada por el proxy de la sesión, así que estrellas y licencias salen de la página web del repo y la fecha del último commit no se pudo ver en casi ningún caso. No se repite lo de la carpeta "Integración LLM y código 2026": ni compuertas, ni Rasa CALM, Parlant, Arbor, ReacTOD, salida estructurada, GEPA, DSPy, abstención conformal, tau2-bench, ni Mem0, Zep o Letta como benchmark de memoria.

## 1. Marcos de arquitectura cognitiva después de CoALA: híbridos con Soar o ACT-R, espacio de trabajo global, sistema 1 y sistema 2, metacognición

### Takeaway
Después de CoALA hay tres líneas que se implementan de verdad: el LLM como fábrica de reglas para un motor simbólico tipo Soar, que aprende por "chunking" cuando se traba; la división en dos agentes, uno rápido que conversa y uno lento que arma creencias y planes, que es la forma más directa de llevar el sistema 1 y 2 a un diálogo; y el monitoreo metacognitivo como etapa explícita. El espacio de trabajo global tiene papers de 2026 pero sin evidencia medida que sirva para un bot de ventas.

### Cited Findings

Marco de referencia
- CoALA, Sumers, Yao y otros, TMLR, material de 2023: describe un agente de lenguaje con memorias modulares, de trabajo, episódica, semántica y procedimental, un espacio de acciones internas, que leen y escriben memoria, y externas, y un ciclo de decisión que propone, evalúa y elige acciones — [arXiv 2309.02427](https://arxiv.org/abs/2309.02427)
- "Applying Cognitive Design Patterns to General LLM Agents", Wray, Kirk y Laird, mayo de 2025, presentación oral en AGI25: arman una tabla de patrones que aparecen en Soar, ACT-R y BDI y buscan su par en los agentes LLM. Ejemplos de la tabla: observar, decidir, actuar, que en Soar es elaborar y proponer, decidir y aplicar operadores; compromiso en tres etapas, que en BDI es deseo, intención y reconsideración de la intención, y en Soar propuesta, selección y retracción de operador; descomposición jerárquica, que en Soar son los "impasses" sin cambio de operador; memoria de corto plazo, que en ACT-R son los buffers de meta y recuperación; memoria procedimental como producciones, recuperada por coincidencia de condiciones. Usan la tabla para predecir huecos de los agentes LLM, en especial la falta de reconsideración de compromisos — [arXiv 2505.07087](https://arxiv.org/abs/2505.07087)
- "The Missing Knowledge Layer in Cognitive Architectures for AI Agents", abril de 2026: sostiene que CoALA y JEPA no tienen una capa de conocimiento con semántica de persistencia propia, y que eso lleva a aplicar olvido a hechos o a tratar hechos y experiencias con la misma regla de actualización; propone cuatro capas, conocimiento, memoria, sabiduría e inteligencia, cada una con su forma de persistir. Es propuesta conceptual, sin medición propia — [arXiv 2604.11364](https://arxiv.org/abs/2604.11364)
- ODD+LLM, noviembre de 2026, taller SocialAgent en NeurIPS 2026: usa CoALA como vocabulario para documentar el armado del prompt, la serialización de memoria, el parseo y los reintentos, y muestra que omitir una sola instrucción cambia el resultado de una simulación publicada. Sirve como evidencia de que CoALA quedó como lenguaje común más que como arquitectura ejecutable — [arXiv 2611.08932](https://arxiv.org/abs/2611.08932)

Híbridos con Soar
- CogRec, diciembre de 2025: recomendador que usa Soar como motor simbólico central. Paso a paso: el LLM inicializa la memoria de Soar con reglas de producción; el agente corre un ciclo percepción, cognición, acción; cuando Soar llega a un impasse, es decir no tiene regla para decidir, le consulta al LLM; la respuesta se convierte en una nueva regla simbólica por el mecanismo de chunking de Soar, así la próxima vez decide sin LLM. Dice ventajas en exactitud, explicabilidad y cola larga sobre tres datasets públicos; el resumen no da cifras — [arXiv 2512.24113](https://arxiv.org/abs/2512.24113)
- NL2GenSym, octubre de 2025: el LLM genera reglas de Soar desde lenguaje natural con un generador y un crítico anclados en la ejecución; cada regla se corre en Soar enseguida y el crítico reflexiona sobre el resultado para refinarla. Más de 86% de éxito generando reglas en el problema de las jarras de agua; las reglas heurísticas nuevas bajan los ciclos de decisión a 1,98 veces el óptimo y a una milésima de las líneas base; modelos chicos rinden mejor que grandes con el marco. Dominio de juguete — [arXiv 2510.09355](https://arxiv.org/abs/2510.09355)
- Soar sigue vivo como código: repo SoarGroup/Soar, licencia BSD, más de 10.000 commits en la rama development, versión 9.6.5 mencionada en la página; el repo no trae integración con LLM — [GitHub SoarGroup/Soar](https://github.com/SoarGroup/Soar)
- Material anterior, 2024: "Cognitive LLMs", integra ACT-R con LLM para decisiones de manufactura — [arXiv 2408.09176](https://arxiv.org/abs/2408.09176)

Sistema 1 y sistema 2
- Talker-Reasoner, Google DeepMind, octubre de 2024, material anterior pero es el diseño más citado para diálogo: un Talker, sistema 1, siempre activo, genera la respuesta conversacional y lee la memoria para "cebar" su respuesta; un Reasoner, sistema 2, hace planificación de varios pasos, llama herramientas y forma creencias sobre el usuario, y las escribe en memoria. El Talker no espera al Reasoner salvo que una variable lo obligue, cuando hace falta pensar antes de contestar. El costo admitido: el Talker trabaja con una visión del mundo desactualizada. Se evaluó sólo cualitativamente en un coach de sueño — [arXiv 2410.08328](https://arxiv.org/abs/2410.08328)
- D-Mem, marzo de 2026: memoria de dos procesos; búsqueda vectorial liviana para lo rutinario y un módulo de deliberación completa que relee todo como respaldo, con una compuerta de calidad multidimensional que decide cuándo escalar. En LoCoMo con GPT-4o-mini, F1 de 53,5 contra 51,2 de Mem0 y 55,3 de la deliberación completa siempre, es decir recupera 96,7% con mucho menos cómputo — [arXiv 2603.18631](https://arxiv.org/abs/2603.18631)
- KC-Agent, agosto de 2026, IEEE COMPSAC 2026: sistema 1 de reconocimiento de patrones que reutiliza soluciones que el sistema 2 descubrió antes y dejó en memoria estructurada; dominio de mejora de modelos ML, no diálogo — [arXiv 2608.02351](https://arxiv.org/abs/2608.02351)
- Material anterior: DUMA, 2023, dos LLM, el rápido decide si hace falta el lento — [arXiv 2310.18075](https://arxiv.org/abs/2310.18075); SwiftSage, NeurIPS 2023 — [arXiv 2305.17390](https://arxiv.org/abs/2305.17390); planificación de diálogo de dos procesos, ACL 2024: política chica entrenada para lo familiar y búsqueda MCTS para lo nuevo — [arXiv 2406.05374](https://arxiv.org/abs/2406.05374)

Espacio de trabajo global
- Global Workspace Agents, abril de 2026: un hub central que difunde a un enjambre de agentes con funciones restringidas, ciclo cognitivo continuo dirigido por eventos, un "impulso intrínseco" basado en entropía semántica que sube la temperatura cuando el razonamiento se estanca, y memoria en dos capas. El resumen no trae números medidos — [arXiv 2604.08206](https://arxiv.org/abs/2604.08206)
- Unified Mind Model, marzo de 2025: arquitectura basada en espacio de trabajo global para agentes autónomos con LLM — [arXiv 2503.03459](https://arxiv.org/abs/2503.03459)
- COGENT, 23-nov-2026: arquitectura cognitiva modular para simular cómo una persona percibe, razona y actúa frente a una interfaz de escritorio, apoyada en teorías cognitivas establecidas; está pensada para simular usuarios, no para el agente que atiende — [arXiv 2611.31559](https://arxiv.org/abs/2611.31559)

Metacognición
- "Truly Self-Improving Agents Require Intrinsic Metacognitive Learning", Liu y van der Schaar, ICML 2025, paper de posición: tres componentes, conocimiento metacognitivo, que es autoevaluación de capacidades; planificación metacognitiva, qué y cómo aprender; y evaluación metacognitiva, reflexionar sobre lo aprendido. Concluyen que los agentes actuales usan casi sólo metacognición extrínseca, lazos fijos diseñados por humanos — [arXiv 2506.05109](https://arxiv.org/abs/2506.05109)
- KAPRO, junio de 2026: benchmark de autoconciencia del agente, si distingue cuándo un problema necesita una herramienta externa y cuándo lo resuelve con lo que sabe — [arXiv 2606.20661](https://arxiv.org/abs/2606.20661)
- Meta-Cognitive Memory Policy Optimization, mayo de 2026: localiza en qué paso se degrada un resumen recursivo de memoria, en vez de premiar sólo el resultado final — [arXiv 2605.30159](https://arxiv.org/abs/2605.30159)
- MAGELLAN, febrero de 2025: el agente predice su propio progreso de aprendizaje por meta para elegir qué practicar, una forma de monitoreo metacognitivo — [arXiv 2502.07709](https://arxiv.org/abs/2502.07709)

### Inferences
- El patrón Soar más chunking, consultar al LLM sólo en el impasse y congelar la respuesta en una regla, es lo más parecido a "aprender como un vendedor que ya sabe": en un bot de ventas el impasse sería "no tengo regla para esta frase del cliente"; el LLM la resuelve una vez y la resolución, revisada, queda como regla. Ninguno de los papers lo midió en diálogo comercial.
- El Talker-Reasoner calca la separación que el bot ya tiene entre traducir y contestar, pero agrega algo que no tiene: un Reasoner que escribe un estado de creencias sobre el cliente, qué busca, qué presupuesto, qué objeción, que el Talker lee en cada turno.
- La predicción de Wray, Kirk y Laird sobre la falta de "reconsideración de intención" aplica directo a ventas: cuando el cliente cambia de idea, el agente LLM tiende a seguir el compromiso viejo.

### Gaps
- No encontré ningún híbrido LLM con Soar o ACT-R evaluado en diálogo de ventas o soporte con números.
- CogRec no da cifras en el resumen y no pude bajar el texto completo en esta ronda.
- No hay evidencia cuantitativa del espacio de trabajo global aplicado a diálogo.

## 2. Agentes que planifican o simulan antes de contestar: teoría de la mente del cliente, seguimiento de creencias, simular el próximo turno, razonamiento oculto

### Takeaway
La evidencia más sólida no está en prompts sino en entrenar con simulación del futuro: CollabLLM y "Modeling Future Conversation Turns" puntúan cada respuesta por lo que pasa varios turnos después con un usuario simulado, y eso enseña a repreguntar cuando conviene. Para teoría de la mente, el diseño que mide bien es hipótesis sobre el estado mental, refinarla, y validar la respuesta contra esa hipótesis. El razonamiento oculto en producción se mueve del "think tool" al pensamiento extendido intercalado.

### Cited Findings

Simular turnos futuros
- CollabLLM, Microsoft y Stanford, febrero de 2025, premio a paper destacado en ICML 2025. Paso a paso: dado un contexto, el modelo genera una respuesta; para puntuarla, un simulador de usuario LLM continúa la conversación varios turnos hacia adelante, limitados por un tamaño de ventana; la "recompensa consciente de varios turnos" es la contribución de esa respuesta al resultado de toda la charla, combinando tarea lograda, eficiencia e interactividad; después se hace ajuste fino por refuerzo con esa recompensa. Resultados: 18,5% más de desempeño de tarea y 46,3% más interactividad según jueces LLM; estudio con 201 personas: 17,6% más satisfacción y 10,4% menos tiempo — [arXiv 2502.00640](https://arxiv.org/abs/2502.00640)
- "Modeling Future Conversation Turns to Teach LLMs to Ask Clarifying Questions", ICLR 2025: las preferencias no se etiquetan por el contexto previo sino simulando el resultado en turnos futuros; si una repregunta permite después respuestas a medida para cada interpretación, gana. Mejora 5% de F1 sobre el conjunto de respuestas de distintas interpretaciones, y 3% de exactitud en decidir cuándo repreguntar y cuándo contestar directo — [arXiv 2410.13788](https://arxiv.org/abs/2410.13788)
- Material anterior: Trip, EMNLP 2024, planificación estratégica en diálogos no colaborativos con usuarios simulados diversos, para que el planificador se adapte al tipo de usuario — [arXiv 2403.06769](https://arxiv.org/abs/2403.06769); Deep Dyna-Q, 2018, el "modelo del mundo" en diálogo como simulador de la respuesta del usuario para generar experiencia — [arXiv 1801.06176](https://arxiv.org/abs/1801.06176)

Teoría de la mente del interlocutor
- MetaMind, mayo de 2025, NeurIPS 2025 spotlight. Tres etapas: un agente de teoría de la mente genera varias hipótesis sobre el estado mental del usuario, intención, emoción, creencia; un agente de normas las refina con restricciones culturales y éticas; un agente de respuesta genera la contestación y valida que se alinee con la intención inferida. 35,7% de mejora en escenarios sociales reales y 6,2% en razonamiento de teoría de la mente; dice igualar el desempeño humano en tareas clave; la ablación muestra que cada etapa importa. Código en GitHub XMZhangAI/MetaMind, texto con licencia CC BY-NC-ND — [arXiv 2505.18943](https://arxiv.org/abs/2505.18943)
- ToMAP, mayo de 2025: persuasor con dos módulos de teoría de la mente; primero se le pide que enumere las objeciones posibles a la tesis, después un codificador de texto con un clasificador entrenado predice cuánto está de acuerdo el oponente con cada objeción, y ese dato entra al persuasor entrenado por refuerzo. Con 3.000 millones de parámetros supera a GPT-4o con ganancia relativa de 39,4% sobre varios modelos persuadidos; produce menos repetición y gana de forma sostenida en charlas largas. Código en GitHub ulab-uiuc/ToMAP — [arXiv 2505.22961](https://arxiv.org/abs/2505.22961)
- PersuasiveToM, febrero de 2025: benchmark de teoría de la mente en diálogos persuasivos, qué cree y qué quiere el otro a lo largo de la charla — [arXiv 2502.21017](https://arxiv.org/abs/2502.21017)
- RebuttalAgent, enero de 2026, ICLR 2026: persuasión estratégica con toma de perspectiva bajo asimetría de información — [arXiv 2601.15715](https://arxiv.org/abs/2601.15715)

Arquitectura para agentes de venta
- "Commercial Intent in Human-AI Conversations", octubre de 2026, documento técnico: sobre 725.219 registros de conversaciones de Aiso, 5,76% son comerciales y 0,33% transaccionales; propone separar preguntas sobre producto de compromisos de compra, con conocimiento anclado en el negocio, un estado de conversación que guarda de dónde salió cada dato, y una política de próxima acción restringida. Aclara que no valida conversión de ventas — [arXiv 2610.06205](https://arxiv.org/abs/2610.06205)

Razonamiento oculto dentro del agente
- "Think tool" de Anthropic, 20-mar-2025: una herramienta que no trae datos ni cambia nada, sólo registra un pensamiento en medio de la respuesta, después de leer resultados de herramientas. En tau-bench aerolínea con Claude 3.7 Sonnet, pass^1: base 0,332, pensamiento extendido 0,412, think solo 0,404, think con prompt optimizado 0,584; en retail, think solo 0,812 contra base 0,783. El texto del post da 0,570 contra 0,370, no coincide con la tabla. Nota del 15-dic-2025: ahora recomiendan el pensamiento extendido en lugar del think tool en la mayoría de los casos — [Anthropic Engineering](https://www.anthropic.com/engineering/claude-think-tool)
- RITE, octubre de 2025: refuerzo para pensamiento intercalado con herramientas, ciclo plan, acción, reflexión forzado en cada paso, para generalizar fuera de matemática — [arXiv 2510.11184](https://arxiv.org/abs/2510.11184)
- Advertencia: "Correct Answers, Invalid Traces", septiembre de 2026, en matemática verificable: las respuestas correctas no siempre vienen con trazas de razonamiento válidas, así que leer la traza como registro de cómo decidió el modelo es riesgoso — [arXiv 2609.38107](https://arxiv.org/abs/2609.38107)

### Inferences
- Para el bot, la simulación del próximo turno puede usarse sin entrenar: el banco ya graba charlas; un simulador de cliente que continúe dos o tres turnos permitiría puntuar "repreguntar contra contestar" por lo que pasa después, que es justamente la regla de CollabLLM. Lo medido en CollabLLM es con ajuste fino; usarlo sólo en evaluación es inferencia mía.
- El esquema de ToMAP, listar las objeciones probables del cliente y estimar cuánto pesa cada una, mapea a ventas casi sin traducción: "es caro", "no sé si es compatible", "lo necesito para mañana".
- El esquema de MetaMind, hipótesis sobre intención, refinamiento, y validar la respuesta contra la hipótesis, es una forma de que el texto final se compare contra lo que el cliente quería y no sólo contra el catálogo.

### Gaps
- No encontré papers 2025 o 2026 que midan teoría de la mente del cliente en ventas de comercio electrónico con conversión real.
- No encontré cómo productos comerciales de venta por chat usan razonamiento oculto; sólo la guía de Anthropic.

## 3. Agentes que aprenden de la experiencia sin ajuste fino: memoria procedimental, bibliotecas de habilidades, reflexión que escribe lecciones, repetición de experiencia, skills

### Takeaway
La línea más madura de 2025 y 2026 es el "manual que evoluciona": después de cada tarea, un reflector extrae lecciones de éxitos y fracasos, un curador las mete como ítems chicos con identificador y contadores, nunca reescribiendo todo, y en la próxima tarea se recuperan los ítems relevantes. ACE, ReasoningBank, Memp y Memento lo hacen con mecánicas distintas y números medidos; el formato Agent Skills es el equivalente abierto y estandarizado de las skills de Claude.

### Cited Findings

Manuales que evolucionan
- Dynamic Cheatsheet, Stanford, abril de 2025: memoria persistente que el propio modelo cura, con estrategias, fragmentos de código e ideas cortas y transferibles, no transcripciones. Claude 3.5 Sonnet más que duplica su exactitud en AIME; GPT-4o pasa de 10% a 99% en Game of 24 al descubrir y reutilizar una solución en Python; 9% más en GPQA-Diamond y 8% en MMLU-Pro para Claude — [arXiv 2504.07952](https://arxiv.org/abs/2504.07952)
- ACE, Agentic Context Engineering, Stanford y SambaNova, octubre de 2025, ICLR 2026. Mecánica: el contexto es una lista de viñetas; cada viñeta tiene metadatos, un identificador único y contadores de cuántas veces se marcó útil o dañina, y un contenido chico, una estrategia, un concepto o un modo de falla común. Tres roles: el Generador resuelve y marca qué viñetas sirvieron o confundieron; el Reflector critica la traza y extrae lecciones, con varias iteraciones si hace falta; el Curador convierte las lecciones en entradas delta que se fusionan de forma determinista, sin reescribir el todo; un paso de "crecer y refinar" controla duplicados. Motivo: con Dynamic Cheatsheet midieron "colapso de contexto": en el paso 60 el contexto tenía 18.282 tokens y 66,7 de exactitud, y en el paso siguiente el modelo lo resumió a 122 tokens y cayó a 57,1, peor que el 63,7 sin adaptación. Resultados: más 10,6% en agentes, más 8,6% en finanzas, 86,9% menos latencia de adaptación; en AppWorld iguala al primer agente de producción del ranking, con GPT-4.1, usando DeepSeek-V3.1, y lo supera en la parte difícil. Funciona sin etiquetas, con la retroalimentación natural de la ejecución. Código en ace-agent/ace, Apache-2.0, unos 1.500 estrellas, 12 commits, novedades de noviembre de 2025 — [arXiv 2510.04618](https://arxiv.org/abs/2510.04618); [GitHub ace-agent/ace](https://github.com/ace-agent/ace)
- Implementación comunitaria de ACE, kayba-ai/agentic-context-engine, Apache-2.0, unos 2.600 estrellas y 944 commits: Agente, Entorno, un "Reflector recursivo" que escribe y corre Python en un arenero para buscar patrones en la traza, un SkillManager que agrega, refina o borra estrategias, y un Skillbook persistente. Dicen, sin paper revisado: en tau2 aerolínea con Claude Haiku 4.5, duplica pass^4 con 15 estrategias aprendidas en el split de entrenamiento sin señal de recompensa y probadas en el split retenido — [GitHub kayba-ai](https://github.com/kayba-ai/agentic-context-engine)
- ReasoningBank, Google Research, septiembre de 2025, ICLR 2026. Mecánica: al terminar una tarea, un LLM como juez etiqueta la trayectoria como éxito o fracaso sin respuesta de referencia; de los éxitos se extraen estrategias validadas y de los fracasos lecciones preventivas; cada ítem tiene título, descripción y contenido; se consolidan en el banco y en la próxima tarea se recuperan los relevantes. MaTTS agrega cómputo por tarea para generar experiencias contrastantes y mejores ítems. En WebArena con Gemini-2.5-flash, éxito total 40,5 sin memoria, 44,1 con AWM, 48,8 con ReasoningBank y 51,8 con MaTTS; en la parte Shopping, de 39,0 a 49,7; en SWE-Bench-Verified con Gemini-2.5-flash, de 34,2 a 38,8. Hasta 20% de mejora relativa y 16% menos pasos. Repo google-research/reasoning-bank, Apache-2.0, unas 650 estrellas, 6 commits — [arXiv 2509.25140](https://arxiv.org/abs/2509.25140); [GitHub](https://github.com/google-research/reasoning-bank)

Memoria procedimental y basada en casos
- Memp, Zhejiang, agosto de 2025, ACL 2026 Findings: destila trayectorias en instrucciones paso a paso y en abstracciones tipo guion, y estudia estrategias de construir, recuperar y actualizar, con un régimen que corrige y da de baja ítems. En TravelPlanner y ALFWorld la tasa de éxito sube a medida que se refina el repositorio; la memoria construida con un modelo fuerte, pasada a uno débil, también le da ganancias sustanciales. Código zjunlp/MemP — [arXiv 2508.06433](https://arxiv.org/abs/2508.06433)
- Benchmark de recuperación de memoria procedimental, noviembre de 2025: los embeddings andan bien en contextos conocidos y caen mucho en contextos nuevos con vocabulario distinto, porque tratan un procedimiento como bolsa de palabras y pierden el orden; las abstracciones generadas por LLM sí transfieren. Más corpus ayuda más que enriquecer la representación — [arXiv 2511.21730](https://arxiv.org/abs/2511.21730)
- AFTER, junio de 2026: 382 tareas empresariales, seis roles, 22 habilidades procedimentales; una sola ronda de refinamiento sube 3,7 a 6,7 puntos; habilidades evolucionadas con trazas de varios modelos logran 73,1% de exactitud entre modelos; algunas habilidades generalizan y otras se especializan y pierden valor al transferirse — [arXiv 2606.23127](https://arxiv.org/abs/2606.23127)
- Memento, agosto de 2025: "ajuste fino de agentes sin ajustar el LLM", formalizado como proceso de decisión de Markov con memoria; las experiencias pasadas quedan como casos en una memoria episódica y una política neuronal de selección de casos decide cuál recuperar; la política mejora reescribiendo la memoria según la retroalimentación. 87,88% pass@3 en validación de GAIA y 79,40% en test; la memoria de casos agrega 4,7 a 9,6 puntos en tareas fuera de distribución. Código Agent-on-the-Fly/Memento — [arXiv 2508.16153](https://arxiv.org/abs/2508.16153)
- Neural Procedural Memory, junio de 2026: en vez de inyectar guías de texto, guarda la habilidad como dirección de activación interna del modelo; requiere acceso a pesos, no aplica a modelos por API — [arXiv 2606.29824](https://arxiv.org/abs/2606.29824)
- Material anterior: Agent Workflow Memory, 2024, induce rutinas reutilizables de trayectorias y las selecciona para guiar tareas nuevas — [arXiv 2409.07429](https://arxiv.org/abs/2409.07429)

Skills al estilo Claude y su equivalente abierto
- Agent Skills: una skill es una carpeta con un SKILL.md que tiene nombre, descripción e instrucciones, más scripts y referencias opcionales. Carga progresiva en tres etapas: al arrancar el agente lee sólo nombre y descripción; si la tarea coincide, lee el SKILL.md entero; los archivos anexos los carga recién cuando los necesita. Anthropic lo publicó como estándar abierto en diciembre de 2025 — [agentskills.io](https://agentskills.io/); [README del estándar](https://cdn.jsdelivr.net/gh/agentskills/agentskills@main/README.md)
- Anthropic dice que más de 70 plataformas lo integraron, entre ellas ChatGPT, Cursor, GitHub Copilot y VS Code, y lo donó a la Agentic AI Foundation de la Linux Foundation; cifras del propio proveedor — [Anthropic](https://www.anthropic.com/news/donating-agent-skills-to-the-agentic-ai-foundation)

### Inferences
- El bot hoy aprende sólo cuando una sesión cambia el código. ACE o ReasoningBank darían un camino intermedio: lecciones chicas con identificador y contadores de útil o dañina, extraídas de charlas grabadas, que entran como contexto. La regla de CLAUDE.md de no sumar una capa por falla choca con esto si se lo usa como depósito de casos; el diseño de ACE, con contadores y baja de ítems dañinos, es lo que lo diferencia de acumular parches.
- El colapso de contexto medido en ACE es un argumento fuerte contra resumir la memoria de la charla reescribiéndola entera en cada turno.
- El hallazgo del benchmark procedimental, que los embeddings no transfieren a vocabulario nuevo y las abstracciones del LLM sí, aplica a recuperar "cómo se resolvió una charla parecida" cuando el cliente lo dice con otras palabras.

### Gaps
- No pude ver fechas de último commit de los repos por el bloqueo de la API de GitHub.
- No encontré estos métodos medidos en diálogo de ventas; los números son de web, código, finanzas y tau2 aerolínea en el caso de kayba, que no tiene revisión.

## 4. Anclaje del diálogo como lo hacen las personas: terreno común, reparación, clarificación

### Takeaway
La medición más útil es Rifts, ACL 2025: los LLM inician clarificación tres veces menos que las personas y piden seguimiento dieciséis veces menos, los fallos de anclaje tempranos predicen rupturas posteriores, y los modelos de frontera rinden alrededor de 25% en el benchmark. Una intervención simple que primero predice si hace falta un acto de anclaje duplica el resultado.

### Cited Findings
- "Navigating Rifts in Human-LLM Grounding", Shaikh y otros, Stanford, ACL 2025. Paso a paso: arman una taxonomía de actos de anclaje, clarificación, seguimiento, reparación, reconocimiento; anotan con un LLM los registros de WildChat, Bing Chat y MultiWOZ, validado con 108 mensajes anotados por tres autores y Kappa de Cohen 0,71; entrenan un pronosticador que predice si el próximo turno va a necesitar un acto de anclaje. Hallazgos: los LLM son tres veces menos propensos a iniciar clarificación y dieciséis veces menos a pedir seguimiento que las personas; las reparaciones las inician sobre todo las personas; los fallos de anclaje tempranos predicen rupturas. En Rifts, GPT-4o 25,26, o3-mini 25,26, Claude Sonnet 3.5 26,95, Llama 3.1 8B 24,22; Llama 3.1 8B con la intervención GROUND, que usa el pronosticador, 54,48 — [arXiv 2503.13975](https://arxiv.org/abs/2503.13975)
- "Understanding Common Ground Misalignment in Goal-Oriented Dialog", marzo de 2025, en chats de soporte técnico de Ubuntu: las interrupciones del flujo vienen de desalineación del terreno común, por divergencia en creencias y supuestos de cada parte — [arXiv 2503.12370](https://arxiv.org/abs/2503.12370)
- "Seeing Is Not Sharing", SIGDIAL 2026: con 13.077 expresiones de referencia de MapTask, algunos modelos sobreestiman el terreno común; confunden lo que podría estar compartido con lo que ya se estableció en la interacción — [arXiv 2606.31719](https://arxiv.org/abs/2606.31719)
- DPIP, marzo de 2026: tarea colaborativa con información repartida para estudiar cómo se construye el terreno común bajo asimetría epistémica — [arXiv 2603.05450](https://arxiv.org/abs/2603.05450)
- DiagFlowBench, EMNLP 2026: 50 diagramas de diagnóstico industrial de un fabricante; mide si el modelo reconoce cuando el operador se sale del procedimiento — [arXiv 2606.17904](https://arxiv.org/abs/2606.17904)
- Lo de clarificación con turnos futuros y CollabLLM está en la sección 2: son las implementaciones entrenadas de "repreguntar como un humano".

### Inferences
- En ventas, el terreno común es lo que el cliente y el bot ya dieron por establecido: el producto que se está hablando, el precio dicho, la cuota. "Seeing Is Not Sharing" sugiere separar en la memoria lo que se le mostró al cliente de lo que el cliente confirmó, que no es lo mismo.
- El pronosticador de Rifts es un clasificador por turno de "acá hace falta un acto de anclaje"; conceptualmente es distinto de decidir por confianza en la búsqueda, porque mira la charla y no el catálogo.

### Gaps
- No encontré implementaciones de código abierto mantenidas de seguimiento de terreno común para chat comercial.
- No pude ver el detalle de la intervención GROUND ni si el código de Rifts está publicado.

## 5. Qué tiene código abierto activo en 2026

### Takeaway
Lo que tiene código y movimiento verificable es la familia de aprendizaje por experiencia: ACE con su versión comunitaria más activa, ReasoningBank, Memp, Memento y Dynamic Cheatsheet, todos con licencias permisivas en lo que pude ver, más el estándar Agent Skills. Soar está vivo como motor pero sin integración LLM en el repo. MetaMind y ToMAP publican código de investigación.

### Cited Findings
- ACE, ace-agent/ace: Apache-2.0, unos 1.500 estrellas, 12 commits, 14 issues y 10 PR abiertos; modos de adaptación offline, online y sólo evaluación; tareas AppWorld, FiNER y fórmulas XBRL; se agregan datasets con una clase DataProcessor — [GitHub](https://github.com/ace-agent/ace)
- kayba-ai/agentic-context-engine: Apache-2.0, unos 2.600 estrellas, 312 forks, 944 commits, sin releases publicadas — [GitHub](https://github.com/kayba-ai/agentic-context-engine)
- google-research/reasoning-bank: Apache-2.0, unas 650 estrellas, 6 commits, soporta WebArena y SWE-Bench — [GitHub](https://github.com/google-research/reasoning-bank)
- Memp, zjunlp/MemP — [arXiv 2508.06433](https://arxiv.org/abs/2508.06433); Memento, Agent-on-the-Fly/Memento — [arXiv 2508.16153](https://arxiv.org/abs/2508.16153); Dynamic Cheatsheet, suzgunmirac/dynamic-cheatsheet — [arXiv 2504.07952](https://arxiv.org/abs/2504.07952); MetaMind, XMZhangAI/MetaMind — [arXiv 2505.18943](https://arxiv.org/abs/2505.18943); ToMAP, ulab-uiuc/ToMAP — [arXiv 2505.22961](https://arxiv.org/abs/2505.22961); benchmark procedimental, qpiai/Proced_mem_bench — [arXiv 2511.21730](https://arxiv.org/abs/2511.21730)
- Soar, SoarGroup/Soar, BSD, más de 10.000 commits — [GitHub](https://github.com/SoarGroup/Soar)
- Agent Skills, agentskills/agentskills, estándar bajo la Linux Foundation — [agentskills.io](https://agentskills.io/)
- CollabLLM: el paper apunta a aka.ms/CollabLLM — [arXiv 2502.00640](https://arxiv.org/abs/2502.00640)

### Inferences
- Para un bot con modelo por API, sin acceso a pesos, lo aplicable sin entrenar es ACE, ReasoningBank, Memento en su variante no paramétrica, Dynamic Cheatsheet, Talker-Reasoner y el esquema de MetaMind. CollabLLM, ToMAP y Neural Procedural Memory requieren ajuste fino o acceso a pesos.
- Hallazgo lateral: "Think Before You Act: Decision Gate for LLM Agents", octubre de 2026, presenta JevAct, que compila políticas en chequeos de estado y preguntas evaluadas por un modelo sólo de prefill — [arXiv 2610.38620](https://arxiv.org/abs/2610.38620). Es del tema de compuertas, ya cubierto, pero el nombre coincide con un componente del bot; conviene ver si es la misma pieza.

### Gaps
- Fechas de último commit y actividad 2026 de cada repo: no verificables por el bloqueo de la API de GitHub en esta sesión; las estrellas salen de la página web en el momento del fetch.
- No verifiqué la licencia de Memp, Memento, MetaMind, ToMAP ni Dynamic Cheatsheet.
