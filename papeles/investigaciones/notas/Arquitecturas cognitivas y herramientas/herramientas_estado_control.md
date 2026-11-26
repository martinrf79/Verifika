# Herramientas abiertas para el estado del pedido y para controlar lo que dice el bot, a fines de noviembre de 2026

Nota de método, 26-nov-2026. La API de GitHub y github.com estaban bloqueadas en esta sesión, así que no hay estrellas ni fechas de último commit de GitHub. Las versiones y fechas salen de PyPI, npm, Docker Hub y la API de Hugging Face, consultadas ese día; los README se leyeron por raw.githubusercontent.com. El sitio oficial del tablero LLM-AggreFact, llm-aggrefact.github.io, no resolvía desde la sesión: sus cifras vienen de las tarjetas de los modelos, de papers y de un espejo de terceros. Lo ya relevado en `research_notes/Integración LLM y código 2026/` no se repite: Rasa CALM, Parlant, NeMo Guardrails, Pipecat Flows, LangGraph y los SDK de agentes, Promptfoo, DeepEval, Langfuse, Phoenix, los simuladores de usuario de MLflow, ADK y Strands, y los sistemas de memoria. Acá sólo se suma lo nuevo de esos que importa para el inventario.

## 1. Modelos y herramientas que verifican una respuesta contra el documento fuente

### Takeaway
Hay verificadores abiertos que corren en CPU y entran en Cloud Run: HHEM 2.1 Open, de 110 millones de parámetros, y los detectores por tramo de LettuceDetect, de 68 a 610 millones, que son los únicos con un modelo entrenado en español y que marcan qué pedazo de la respuesta no está respaldado. Los mejores en LLM-AggreFact, Bespoke-MiniCheck-7B y Granite Guardian, tienen 7 a 8 mil millones de parámetros y piden GPU; Bespoke-MiniCheck además es de licencia no comercial. Ninguno está medido en el caso del bot, precios y stock en español rioplatense contra filas de catálogo, así que sirven como segunda red detrás del verificador propio, no como reemplazo, y hay que medirlos con las respuestas grabadas del banco antes de creerles.

### Cited Findings

LLM-AggreFact, el tablero de referencia
- LLM-AggreFact junta 11 conjuntos de datos con anotación humana sobre verificación de afirmaciones contra documentos; la métrica es exactitud balanceada; las afirmaciones las generaron modelos recientes sin inyección manual de errores — [README de MiniCheck](https://raw.githubusercontent.com/Liyan06/MiniCheck/main/README.md); [dataset en Hugging Face](https://huggingface.co/datasets/lytang/LLM-AggreFact)
- Un espejo de terceros del tablero, con datos importados el 29-may-2026, pone arriba a Bespoke-MiniCheck-7B con 77,4 de promedio, un modelo con 77,2 y Granite Guardian 3.3 con 76,5. No pude leer el tablero oficial para confirmarlo — [resultado de búsqueda, benchmarklist.com](https://benchmarklist.com/benchmarks/llm_aggrefact/); [alphaxiv](https://alphaxiv.org/benchmarks/the-university-of-texas-at-austin/llm-aggrefact)
- IBM dice que Granite Guardian 3.3 quedó tercero en LLM-AggreFact en septiembre de 2025 — [README de granite-guardian](https://raw.githubusercontent.com/ibm-granite/granite-guardian/main/README.md)

MiniCheck y Bespoke-MiniCheck
- Bespoke-MiniCheck-7B recibe un documento y una sola oración y devuelve 0 o 1; para una respuesta de varias oraciones hay que partirla en oraciones primero; el documento no se trocea salvo que pase 32 mil tokens — [tarjeta en Hugging Face](https://huggingface.co/bespokelabs/Bespoke-MiniCheck-7B)
- Se ajustó desde internlm2.5-7b-chat con 35 mil ejemplos; con vLLM en una A6000 de 48 GB rinde más de 500 documentos por minuto; licencia CC BY-NC 4.0, uso comercial con licencia aparte de Bespoke Labs; idioma declarado inglés — [tarjeta en Hugging Face](https://huggingface.co/bespokelabs/Bespoke-MiniCheck-7B)
- Variantes chicas con licencia MIT: MiniCheck-Flan-T5-Large de 0,8 mil millones, RoBERTa-Large y DeBERTa-v3-Large de 0,4 mil millones; última modificación de las tarjetas entre septiembre y diciembre de 2024 — [lytang/MiniCheck-Flan-T5-Large](https://huggingface.co/lytang/MiniCheck-Flan-T5-Large); [API de Hugging Face](https://huggingface.co/api/models/lytang/MiniCheck-Flan-T5-Large)
- El paquete se instala desde git; el nombre `minicheck` en PyPI es otro proyecto, un verificador de modelos de estado, versión 0.4.0 del 30-jul-2026 — [README de MiniCheck](https://raw.githubusercontent.com/Liyan06/MiniCheck/main/README.md); [PyPI minicheck](https://pypi.org/project/minicheck/)
- Las novedades del README terminan en septiembre de 2024: ollama y validador de Guardrails. Está quieto, se marca como viejo — [README de MiniCheck](https://raw.githubusercontent.com/Liyan06/MiniCheck/main/README.md)

Vectara HHEM 2.1 Open
- Recibe pares premisa e hipótesis y devuelve un puntaje de 0 a 1 de respaldo; licencia Apache 2.0; 110 millones de parámetros; tarjeta modificada el 6-oct-2026; anda con transformers 4 y 5 — [tarjeta en Hugging Face](https://huggingface.co/vectara/hallucination_evaluation_model); [API de Hugging Face](https://huggingface.co/api/models/vectara/hallucination_evaluation_model)
- Ocupa menos de 600 MB de RAM en 32 bits y tarda alrededor de 1,5 segundos para una entrada de 2 mil tokens en un CPU x86 moderno — [tarjeta en Hugging Face](https://huggingface.co/vectara/hallucination_evaluation_model)
- Cifras publicadas: AggreFact-SOTA exactitud balanceada 76,55%; RAGTruth-Summ 64,42%; RAGTruth-QA 74,28%; ambas por encima de GPT-4 de 2023 en zero-shot según Vectara — [tarjeta en Hugging Face](https://huggingface.co/vectara/hallucination_evaluation_model)
- La versión abierta es sólo inglés; el soporte entre idiomas, español incluido, es de HHEM-2.3, que es comercial — [tarjeta en Hugging Face](https://huggingface.co/vectara/hallucination_evaluation_model)

LettuceDetect, de KRLabs
- Detector por tramo: etiqueta cada token de la respuesta como respaldado o no, y devuelve los tramos sin respaldo con su confianza. Paquete `lettucedetect` 0.2.3 del 13-ago-2026, MIT — [README](https://raw.githubusercontent.com/KRLabsOrg/LettuceDetect/main/README.md); [PyPI lettucedetect](https://pypi.org/project/lettucedetect/)
- Historia: 0.1.7 del 18-may-2025 suma siete idiomas con EuroBERT, español incluido; 0.1.8 del 31-ago-2025 suma TinyLettuce de 17, 32 y 68 millones; 0.2.0 del 22-jun-2026 suma modelos para código, salida de herramientas y tramos tipificados; 0.2.2 del 5-jul-2026 — [README](https://raw.githubusercontent.com/KRLabsOrg/LettuceDetect/main/README.md)
- Modelo español lettucedect-610m-eurobert-es-v1, MIT, contexto de 8.192 tokens, entrenado en RAGTruth traducido al español: F1 73,25%, precisión 76,32%, recuperación 70,41%, contra F1 62,40% de GPT-4.1-mini como juez; el de 210 millones da F1 71,38% — [tarjeta en Hugging Face](https://huggingface.co/KRLabsOrg/lettucedect-610m-eurobert-es-v1)
- Ese modelo carga código remoto de EuroBERT que no anda con transformers 5; pide `transformers>=4.48.3,<5` — [tarjeta en Hugging Face](https://huggingface.co/KRLabsOrg/lettucedect-610m-eurobert-es-v1)
- Generación v2 del 26-oct-2026: lettucedect-v2-mmbert-base de 307 millones, Apache 2.0, multilingüe con español; span-F1 0,642 y F1 por ejemplo 0,869 sobre 10.698 casos; RAGTruth F1 por ejemplo 74,3; lettucedect-v2-qwen-2b llega a span-F1 0,689 y puede dar el tipo de error y una razón por tramo — [tarjeta mmbert-base](https://huggingface.co/KRLabsOrg/lettucedect-v2-mmbert-base); [tarjeta LFM2.5](https://huggingface.co/KRLabsOrg/LFM2.5-Encoder-350M-hallucination-detector)
- Según los autores, en respuestas de agentes de código HHEM, Lynx, Granite Guardian, MiniCheck y jueces grandes quedan cerca del azar; Nemotron de 550 mil millones da span-F1 0,216. Es un dominio, código, distinto del bot — [tarjeta LFM2.5](https://huggingface.co/KRLabsOrg/LFM2.5-Encoder-350M-hallucination-detector); [paper GroundLM 2026](https://aclanthology.org/2026.groundlm-1.44/)

Lynx de Patronus
- Llama-3-Patronus-Lynx-8B-Instruct-v1.1: licencia CC BY-NC 4.0, tarjeta sin cambios desde el 31-jul-2024, 84 descargas en el último registro de la API; el repo de GitHub sólo trae instrucciones de ajuste e inferencia con vLLM. Viejo y no comercial — [API de Hugging Face](https://huggingface.co/api/models/PatronusAI/Llama-3-Patronus-Lynx-8B-Instruct-v1.1); [README](https://raw.githubusercontent.com/patronus-ai/Lynx-hallucination-detection/main/README.md)

Granite Guardian de IBM
- Granite Guardian 4.1 8B, abril de 2026, Apache 2.0, idioma declarado inglés; criterios propios en lenguaje natural, modo con y sin razonamiento; trae criterios de groundedness, relevancia del contexto, relevancia de la respuesta y alucinación en llamadas a funciones — [tarjeta en Hugging Face](https://huggingface.co/ibm-granite/granite-guardian-4.1-8b)
- Cifras del fabricante: groundedness en LLM-AggreFact 0,76 de exactitud balanceada con razonamiento, igual que 3.3; alucinación en llamadas a funciones de 0,74 a 0,79 sin razonamiento; IFEval con varias restricciones de 0,458 a 0,844 — [tarjeta en Hugging Face](https://huggingface.co/ibm-granite/granite-guardian-4.1-8b); [README de granite-guardian](https://raw.githubusercontent.com/ibm-granite/granite-guardian/main/README.md)
- Hay versión GGUF de la 4.1, del 26-may-2026, y adaptadores LoRA de detección y corrección de factualidad sobre la 3.2, del 10-nov-2025 — [API de Hugging Face, ibm-granite](https://huggingface.co/api/models?author=ibm-granite&search=guardian)
- El ejemplo oficial corre con vLLM y `max_model_len=8192`, o sea GPU — [tarjeta en Hugging Face](https://huggingface.co/ibm-granite/granite-guardian-4.1-8b)

Recién llegados 2025-2026
- Paladin-mini de Qualifire, junio de 2025, 3,8 mil millones sobre Phi-4-mini: 73,08% promedio en ocho subconjuntos de LLM-AggreFact contra 77,7% de Bespoke-MiniCheck-7B; en su propio banco da 96% en "precios y matemática" y 82% en fechas; licencia "other" en Hugging Face — [arXiv 2506.20384](https://arxiv.org/html/2506.20384); [qualifire/context-grounding-paladin-mini](https://huggingface.co/qualifire/context-grounding-paladin-mini)
- HalluGuard, modelos chicos de razonamiento con evidencia para RAG; hay una versión Qwen3-4B con Apache 2.0 de abril de 2026 y GGUF de julio — [arXiv 2510.00880](https://arxiv.org/pdf/2510.00880); [lrsbrgrn/HalluGuard-Qwen3-4B](https://huggingface.co/lrsbrgrn/HalluGuard-Qwen3-4B)
- FactCG-DeBERTa-v3-Large, MIT, febrero de 2025 — [arXiv 2501.17144](https://arxiv.org/pdf/2501.17144); [Hugging Face](https://huggingface.co/yaxili96/FactCG-DeBERTa-v3-Large)
- Un paper de mayo de 2026 con modelos chicos que verifican afirmaciones con estrategias de examen humano reporta estado del arte en su banco FacTax y una brecha chica contra FactCG y MiniCheck-FT5 en LLM-AggreFact — [arXiv 2605.29712](https://arxiv.org/html/2605.29712)

Marcos que envuelven a estos verificadores
- Guardrails AI 0.11.0, 14-ago-2026, Apache 2.0. Desde el 6-jul-2026 los validadores pasan a paquetes comunes de PyPI y se discontinúa la inferencia remota hospedada; MiniCheck está como validador desde 2024 — [README](https://raw.githubusercontent.com/guardrails-ai/guardrails/main/README.md); [PyPI guardrails-ai](https://pypi.org/project/guardrails-ai/); [README de MiniCheck](https://raw.githubusercontent.com/Liyan06/MiniCheck/main/README.md)
- LLM Guard de Protect AI está archivado: el README dice que el proyecto y sus modelos ya no se mantienen; última versión 0.3.16 del 19-may-2025 — [README](https://raw.githubusercontent.com/protectai/llm-guard/main/README.md); [PyPI llm-guard](https://pypi.org/project/llm-guard/)
- Ragas 0.4.4, 14-nov-2026, Apache; el repo se mudó a vibrantlabsai/ragas; es un marco de evaluación con métricas por LLM, faithfulness incluida, pensado para medir fuera de línea — [PyPI ragas](https://pypi.org/project/ragas/); [README](https://raw.githubusercontent.com/vibrantlabsai/ragas/main/README.md)
- UQLM de CVS Health 0.6.8, 8-nov-2026, Apache 2.0, incertidumbre por consistencia entre muestras — [PyPI uqlm](https://pypi.org/project/uqlm/)
- TruLens 2.16.0, 19-oct-2026, MIT — [PyPI trulens](https://pypi.org/project/trulens/)

### Inferences
- Para el 9% de primeros mensajes con algo falso, lo más barato de probar es LettuceDetect en español, el EuroBERT de 210 o 610 millones o el mmbert-base v2: corre en CPU, dice qué tramo es el falso, y se puede pasar como contexto las filas reales del catálogo que ya arma el código. Se mide primero en `banco_pruebas/alucinaciones.py` con las respuestas grabadas: si no caza lo que el verificador propio ya caza, o mete falsas alarmas sobre precios correctos, no entra.
- HHEM 2.1 Open es la opción más simple de correr en el mismo contenedor, pero es sólo inglés en la versión abierta; con texto rioplatense hay que medirlo antes, no suponerlo.
- Bespoke-MiniCheck-7B y Lynx quedan afuera para producción por la licencia no comercial. Granite Guardian 4.1 es Apache y el de más criterios, pero pide GPU o un servidor aparte, lo que suma un servicio, contra la regla de un solo servicio vivo.
- Estos modelos verifican si el texto se apoya en el documento; no saben si "lo tenemos en stock" o "$85.000" coinciden con un campo concreto. Para montos, cuotas y envíos el verificador determinista por filas sigue siendo mejor herramienta; el modelo sirve para las afirmaciones en prosa: compatibilidades, características, lo que el código no puede comparar campo a campo.
- Paladin-mini reporta un banco de "precios y matemática" con 96%, que es justo la clase de error del bot, pero su licencia no está clara y el banco es del propio autor.

### Gaps
- No pude leer el tablero oficial de LLM-AggreFact; las cifras de ranking son del espejo de terceros y de los fabricantes.
- Ningún modelo publica resultados en español de Argentina ni en catálogos de comercio. El modelo español de LettuceDetect se evaluó sobre RAGTruth traducido.
- No hay latencia publicada de LettuceDetect en CPU; sólo la de HHEM.
- No verifiqué si Cloud Run con GPU está disponible en `southamerica-east1` ni su costo.
- Licencia exacta de Paladin-mini sin confirmar: la API dice "other".

## 2. Estado del diálogo y seguimiento del pedido entre turnos

### Takeaway
En Python hay tres librerías vivas que sirven para que el estado del pedido lo mande el código y no el modelo: python-statemachine 3.2, con statecharts al estilo XState, transitions 0.9, la más usada y simple, y Apache Burr 0.43, que suma persistencia y una interfaz para ver cada paso. Ninguna llena slots con el LLM; el llenado sigue siendo de la llamada 0. Las plataformas de WhatsApp abiertas, Typebot, Chatwoot, Evolution API y WAHA, resuelven canal, bandeja humana y flujos visuales, no la memoria del pedido, y suman un servicio.

### Cited Findings

Librerías de máquinas de estado en Python
- python-statemachine 3.2.2, 14-oct-2026, MIT: statecharts y máquinas finitas con estados compuestos, regiones paralelas e historia, API declarativa, síncrona y asíncrona — [PyPI python-statemachine](https://pypi.org/project/python-statemachine/); [README](https://raw.githubusercontent.com/fgmacedo/python-statemachine/main/README.md)
- transitions 0.9.3, 2-jul-2025, MIT: máquina de estados liviana orientada a objetos con extensiones; la última versión tiene más de un año, actividad baja — [PyPI transitions](https://pypi.org/project/transitions/)
- sismic 1.6.14, 5-oct-2026: intérprete y verificador de statecharts, con chequeo de contratos — [PyPI sismic](https://pypi.org/project/sismic/)
- Apache Burr, incubadora de Apache: el paquete `burr` 0.42.0 del 18-jul-2026 avisa que se mudó a `apache-burr`, 0.43.0 del 25-ago-2026; pide Python 3.10 o más; arma aplicaciones como acciones sobre un estado, con persistidores enchufables para guardar y recuperar estado y una interfaz para seguir cada paso en vivo — [PyPI burr](https://pypi.org/project/burr/); [PyPI apache-burr](https://pypi.org/project/apache-burr/); [README](https://raw.githubusercontent.com/apache/burr/main/README.md)
- pydantic-graph 2.75.0, 25-nov-2026, MIT, se describe como librería de grafos y máquinas de estado, del equipo de Pydantic — [PyPI pydantic-graph](https://pypi.org/project/pydantic-graph/)
- XState 5.33.4, 7-nov-2026, MIT, es la referencia en JavaScript — [npm xstate](https://www.npmjs.com/package/xstate)
- Para comparar con lo ya relevado: LangGraph 1.2.24 del 20-nov-2026, Rasa Pro 3.22.2 del 26-nov-2026, Parlant 4.0.9 del 24-nov-2026, Pipecat 1.17.0 del 22-nov-2026; pipecat-ai-flows suelto quedó en 1.4.0 del 5-jul-2026 — [PyPI langgraph](https://pypi.org/project/langgraph/); [PyPI rasa-pro](https://pypi.org/project/rasa-pro/); [PyPI parlant](https://pypi.org/project/parlant/); [PyPI pipecat-ai](https://pypi.org/project/pipecat-ai/); [PyPI pipecat-ai-flows](https://pypi.org/project/pipecat-ai-flows/)

Plataformas y puentes de WhatsApp abiertos
- Typebot: constructor visual de chatbots con integraciones de OpenAI, webhooks y Chatwoot; licencia Functional Source License 1.1 con conversión futura a Apache 2.0, o sea "fair source", no OSI; imagen 3.19 del 20-oct-2026 — [README](https://raw.githubusercontent.com/baptisteArno/typebot.io/main/README.md); [LICENSE](https://raw.githubusercontent.com/baptisteArno/typebot.io/main/LICENSE); [Docker Hub](https://hub.docker.com/r/baptistearno/typebot-builder)
- Chatwoot: bandeja unificada con WhatsApp y agente de IA "Captain"; MIT; imagen v4.20.1-ce del 20-nov-2026 — [README](https://raw.githubusercontent.com/chatwoot/chatwoot/master/README.md); [Docker Hub](https://hub.docker.com/r/chatwoot/chatwoot)
- Evolution API: API de WhatsApp sobre Baileys o sobre la Cloud API oficial, con integraciones a Typebot, Chatwoot, Dify, OpenAI, Flowise y n8n; licencia Apache 2.0 con condiciones extra sobre logo y uso; v2.3.8 del 23-nov-2026; junta telemetría anónima — [README](https://raw.githubusercontent.com/EvolutionAPI/evolution-api/main/README.md); [LICENSE](https://raw.githubusercontent.com/EvolutionAPI/evolution-api/main/LICENSE); [Docker Hub](https://hub.docker.com/r/evoapicloud/evolution-api)
- WAHA: API HTTP de WhatsApp, Apache 2.0; desde 2026.6 las funciones Plus pasan al núcleo; versión 2026.10.1 del 28-oct-2026 — [README](https://raw.githubusercontent.com/devlikeapro/waha/master/README.md); [Docker Hub](https://hub.docker.com/r/devlikeapro/waha)
- Baileys 7.0.0-rc14, 29-jul-2026, MIT; habla con WhatsApp Web por WebSocket; aclara que no está afiliado a WhatsApp; whatsapp-web.js 1.34.8, 12-nov-2026, Apache 2.0 — [README](https://raw.githubusercontent.com/WhiskeySockets/Baileys/master/README.md); [npm baileys](https://www.npmjs.com/package/baileys); [npm whatsapp-web.js](https://www.npmjs.com/package/whatsapp-web.js)
- Botpress v12, la versión que se podía autohospedar, tiene su última imagen 12.31.10 del 10-abr-2025; lo activo es la nube con CLI 7.1.16 del 23-nov-2026. v12 se marca como viejo — [Docker Hub botpress/server](https://hub.docker.com/r/botpress/server); [README v12](https://raw.githubusercontent.com/botpress/v12/master/README.md); [npm @botpress/cli](https://www.npmjs.com/package/@botpress/cli)

### Inferences
- La pérdida del hilo al tercer o cuarto mensaje no la arregla un puente de WhatsApp; la arregla que el pedido sea un objeto con estados y transiciones validadas. python-statemachine encaja con el código actual: es una dependencia de Python pura, se serializa el estado a Firestore junto a `memoria_agente` y cada comando de la segunda llamada pasa a ser un evento que la máquina acepta o rechaza. Eso es la regla 2 del repo, el código puede invalidar al modelo, hecha estructura.
- Burr da lo mismo con persistencia e interfaz de traza incluidas, pero trae su propio modelo de aplicación; reemplaza más de lo que hace falta y suma una forma nueva al lado de la vieja.
- Typebot, Evolution API y WAHA usan WhatsApp Web no oficial o suman un servicio con su base; Typebot no es de código abierto según OSI. Contra la regla de un servicio vivo, no conviene adoptarlos; Chatwoot sí puede servir si un día hace falta pasarle la charla a un humano.

### Gaps
- No encontré ninguna librería abierta de llenado de slots con LLM que sea independiente de un marco; lo que hay vive dentro de Rasa Pro, Parlant o los SDK de agentes, ya relevados.
- No hay mediciones publicadas de cuánto baja la pérdida de hilo al pasar a una máquina de estados explícita.
- Sin estrellas ni actividad de commits de GitHub por el bloqueo.

## 3. Herramientas para probar bots conversacionales

### Takeaway
Lo nuevo frente a lo ya relevado es LangWatch Scenario, una librería de pruebas por simulación para Python con guion: se puede fijar qué dice el usuario simulado en cada turno, mezclar turnos libres y verificar en cualquier punto, y corre dentro de pytest. Encaja con las 26 charlas del banco como forma de sumar charlas largas, de cinco o más turnos, que es donde se pierde el hilo.

### Cited Findings
- langwatch-scenario 1.7.1, 22-nov-2026, Apache 2.0, en Python, TypeScript y Go: simula usuarios, juzga en cualquier punto de la charla y permite un guion con turnos del usuario simulado, turnos fijos y cortes de éxito o falla — [PyPI langwatch-scenario](https://pypi.org/project/langwatch-scenario/); [README](https://raw.githubusercontent.com/langwatch/scenario/main/README.md)
- Ya relevados con versión: Promptfoo con usuario simulado, DeepEval con ConversationSimulator, Langfuse para trazas, Phoenix con licencia Elastic 2.0 — [huecos.md, sección 3](../Integración%20LLM%20y%20código%202026/huecos.md)
- Versiones actuales de esos: deepeval 4.3.6 del 25-nov-2026, Apache 2.0; TruLens 2.16.0, MIT — [PyPI deepeval](https://pypi.org/project/deepeval/); [PyPI trulens](https://pypi.org/project/trulens/)
- Botium, el clásico de pruebas de chatbots: en PyPI sólo hay un paquete homónimo de 2018 que no es el mismo; está viejo — [PyPI botium](https://pypi.org/project/botium/)

### Inferences
- Scenario con turnos de usuario fijos, sin simulación libre, es la manera más barata de grabar charlas de siete u ocho turnos que repitan "esa", "la segunda" y cambios de pedido, y medir si el estado sobrevive. Los turnos libres con modelo cuestan llamadas y quedan para una corrida final.

### Gaps
- No encontré mediciones de qué tan bien Scenario predice fallas reales; ni de su costo por corrida.

## 4. Agentes de venta abiertos para WhatsApp que se pueden estudiar o copiar

### Takeaway
Hay varios repos chicos de un solo desarrollador, sin despliegues reales verificables. El más parecido al bot en tecnología es Subhan696/Whatsapp-Sales-Agent: Python 3.11, FastAPI, LangGraph con checkpoint en Postgres y reglas contra inventar SKU y precios. Sirven para ver cómo otros guardan el carrito, no como base para copiar.

### Cited Findings
- Subhan696/Whatsapp-Sales-Agent: Python 3.11 o más, FastAPI, LangGraph con checkpointer en PostgreSQL para la memoria entre turnos; cotiza sólo desde datos sincronizados, no ofrece variantes agotadas, registra talle y color en el pedido; dice tener "protocolos estrictos" contra inventar SKU y precios, sin cifras — [README](https://raw.githubusercontent.com/Subhan696/Whatsapp-Sales-Agent/main/README.md)
- bibinprathap/whatsapp-chatbot, Node.js: pasa el pedido en lenguaje natural a un carrito en SQLite con llamadas a funciones de OpenAI, y mantiene los menús clásicos para lo simple; se presenta como "el primer agente de ventas abierto para WhatsApp" — [README](https://raw.githubusercontent.com/bibinprathap/whatsapp-chatbot/main/README.md)
- mklabs-ecommerce/wanas: agente de pedidos por WhatsApp para una tienda de ropa egipcia, con Shopify como fuente de stock y precios, búsqueda en árabe e inglés — [GitHub, por resultado de búsqueda](https://github.com/mklabs-ecommerce/wanas)
- melgarafael/DeskcommCRM: CRM de ventas con agentes sobre WAHA o la Cloud API, multitenant con aislamiento por fila probado en CI, en portugués — [README](https://raw.githubusercontent.com/melgarafael/DeskcommCRM/main/README.md)
- Otros: JeevanRishiP/WhatsApp-AI-Sales-Agent, Apache 2.0, para marcas de India; FarhanUllah382/whatsapp-shop-agent, tienda paquistaní, dice haber sido probado en vivo en septiembre de 2026 — [resultado de búsqueda](https://github.com/JeevanRishiP/WhatsApp-AI-Sales-Agent); [resultado de búsqueda](https://github.com/FarhanUllah382/whatsapp-shop-agent)

### Inferences
- Ninguno publica una tasa de error ni una batería de charlas; el bot del repo ya mide más que todos. Lo único que vale mirar es cómo Subhan696 guarda el carrito como estado de LangGraph con checkpoint por turno, que es la misma idea que una máquina de estados con persistencia en Firestore.

### Gaps
- Sin estrellas, fechas de commit ni licencias de GitHub para estos repos por el bloqueo de la API; no hay despliegues reales verificables de ninguno.
- No encontré agentes de venta abiertos en español rioplatense.
