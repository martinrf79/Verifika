# Arneses de agentes y práctica de evaluación 2025-2026: qué sirve para un bot de ventas

Notas de investigación, 26-nov-2026. Quince llamadas de búsqueda. Varios hosts quedaron fuera de la red de la sesión: tau-bench.com, llm-stats.com y fin.ai no se pudieron leer, así que las cifras de tablas de posiciones vienen de fragmentos de buscador y se marcan como no verificadas.

## Diseño publicado de arneses 2025-2026: qué principios reportan para que un agente sea confiable

### Takeaway
Los arneses de Anthropic, OpenAI y Google convergen en lo mismo: estado externo estructurado que el modelo no puede reescribir, una sola unidad de trabajo por vuelta, verificación de punta a punta hecha por algo distinto del que produjo, y controles automáticos más aprobación humana que deciden si el turno sigue, se pausa o se corta. Anthropic además avisa que parte del andamiaje caduca cuando el modelo mejora, y hay que medirlo para sacarlo.

### Cited Findings
- Anthropic, "Effective harnesses for long-running agents", 26-nov-2025: cada sesión arranca sin memoria; la compactación sola no alcanzó para terminar una app desde un pedido general. — [Anthropic Engineering](https://anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- Mismo post: un agente inicializador escribe una lista de más de 200 funciones en JSON, todas con `passes: false`; el agente de trabajo sólo puede cambiar ese campo y tiene prohibido borrar o editar pruebas. Eligieron JSON porque el modelo lo sobrescribía de forma indebida menos que un Markdown. — [Anthropic Engineering](https://anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- Mismo post: una función por sesión corrigió la tendencia a querer resolver todo de una; cada sesión termina en estado limpio, con commit descriptivo y nota de progreso; al arrancar, lee la nota, el git log y la lista, y corre primero una prueba básica de punta a punta para arreglar lo roto antes de sumar. — [Anthropic Engineering](https://anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- Mismo post, fallas observadas: declarar victoria antes de tiempo, marcar funciones como hechas sin verificarlas, y verificar sólo con pruebas unitarias o curl, que no veían fallas de punta a punta; pedir explícitamente probar como usuario real, con automatización del navegador, destapó errores invisibles en el código. — [Anthropic Engineering](https://anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- Post posterior de Anthropic sobre diseño de arneses, de Prithvi Rajasekaran: tres agentes, planificador, generador y evaluador; el evaluador separado hace falta porque los agentes sobrevaloran su propio trabajo; reinicios de contexto con traspaso estructurado contra la deriva. Sólo leído en fragmento de buscador. — [Anthropic Engineering](https://anthropic.com/engineering/harness-design-long-running-apps)
- Post de Anthropic sobre Managed Agents: al correr el mismo arnés con Opus 4.5, el comportamiento que justificaba los reinicios de contexto desapareció y los reinicios pasaron a ser peso muerto. Sólo fragmento. — [Anthropic Engineering](https://anthropic.com/engineering/managed-agents)
- Artículo de Claude sobre diseño de arneses: diseñar el arnés es decidir qué va en el andamiaje y, a medida que el modelo mejora, qué se puede sacar. Sólo fragmento. — [Claude](https://claude.com/resources/articles/harnessing-claudes-intelligence)
- Anthropic, "Writing effective tools for agents": ciclo de prototipo, tareas realistas, correr el agente y repetir; la evaluación puede fijar qué herramientas se esperan por tarea; herramientas con poca superposición de funciones, nombres con espacio de nombres y respuestas con contexto útil y eficiente en tokens. — [Anthropic Engineering](https://anthropic.com/engineering/writing-tools-for-agents)
- Anthropic, "Effective context engineering for AI agents": las herramientas mejoran la eficiencia al devolver información económica en tokens y al empujar al agente a comportarse de forma eficiente; remite a herramientas bien entendidas por el modelo y con mínima superposición. Sólo fragmento. — [Anthropic Engineering](https://anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- OpenAI Agents SDK, guía de guardrails y aprobaciones: los guardrails son controles automáticos y la revisión humana es la capa de aprobación; juntos deciden si el turno sigue, se pausa o se corta. Las aprobaciones frenan una llamada a herramienta hasta que alguien la apruebe o rechace. Guardrail bloqueante cuando arrancar el agente es caro o riesgoso; en paralelo cuando importa más la latencia. — [OpenAI Developers](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals)
- OpenAI Agents SDK: un guardrail devuelve un objeto con `tripwire_triggered`, que corta la corrida; el trazador incluido manda los datos a la plataforma de OpenAI, no a la propia. Fuente de terceros. — [DEV Community](https://dev.to/gabrielanhaia/the-openai-agents-sdk-in-production-what-it-gives-you-and-what-it-hides-16a9)
- OpenAI, "A practical guide to building agents": armar evals para tener una línea de base antes de elegir modelo. — [OpenAI](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf)

### Inferences
- El patrón de Anthropic coincide con lo que Verifika ya hace por fuera del modelo: `PENDIENTE.md` como nota de progreso, tests `xfail` estrictos como lista de funciones con `passes: false`, techos que sólo bajan y la regla de que el que implementa no reescribe la vara. Lo que se puede tomar es llevar esa disciplina adentro del turno del bot: un estado del pedido en estructura cerrada que la segunda llamada sólo puede modificar por comandos, nunca reescribir entero.
- "Evaluador separado porque el agente sobrevalora su trabajo" es la justificación publicada del verificador de Verifika; la lección extra es probar como el cliente real, de punta a punta, no sólo pieza por pieza.
- La advertencia de Managed Agents sugiere medir periódicamente cada capa con el modelo de producción y sacar la que ya no mueve el número.
- Los arneses de agentes de código optimizan tareas largas con un solo usuario confiable; un bot de ventas tiene turnos cortos con un usuario no confiable. Lo trasladable es el estado externo, la verificación separada y los guardrails; la autonomía larga y los subagentes paralelos encajan menos.

### Gaps
- No pude leer el texto completo de los posts de context engineering, harness design y Managed Agents; sólo fragmentos.
- No encontré documentación de Claude Agent SDK ni de Google ADK sobre subagentes, compactación o permisos con resultados medidos; los posts describen diseño, no números de confiabilidad.
- No revisé otros arneses abiertos de GitHub por límite de llamadas.

## Evaluación multi-turno: tau-bench, tau2-bench, pass^k y simuladores de usuario

### Takeaway
pass^k, que exige acertar en las k repeticiones, es la métrica publicada para agentes de cara al cliente, y castiga fuerte: con 75% por intento, pass^3 da cerca de 42%. tau2-bench 2.0, del 19-oct-2026, trae paquete en español para retail, airline y telecom, y sus puntajes no se comparan con la serie 1.x. Las cifras de los mejores modelos en 2026 están dispersas y se contradicen entre agregadores.

### Cited Findings
- Definición: pass@k es al menos un acierto en k intentos; pass^k es que acierten los k; para agentes de cara al cliente importa pass^k. Ejemplo: 75% por intento da pass^3 de aproximadamente 42%. — [Anthropic, Demystifying evals, 9-ene-2026](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- En el paper original de tau-bench, 2024, GPT-4o en retail bajaba de 61,2% en pass^1 a menos de 25% en pass^8. Material anterior a 2025, citado por terceros. — [Future AGI](https://futureagi.com/blog/tau-bench-explained/)
- tau2-bench, versiones: 0.1.0 del 12-jun-2025 con dominios airline, retail y telecom y simulación de control dual; 0.2.0 del 6-oct-2025 lanza tabla web; 0.2.1 de noviembre 2025 suma soporte para aprendizaje por refuerzo con entornos de agente y de usuario; 1.0.1 de julio 2026 corrige el dominio `banking_knowledge`; 2.0.0 del 19-oct-2026 suma seis idiomas, español incluido, en texto y voz, benchmarks congelados y un juego de jueces `tau2 judges` sólo diagnóstico, que no entra en la recompensa. — [tau2-bench RELEASE_NOTES](https://raw.githubusercontent.com/sierra-research/tau2-bench/main/RELEASE_NOTES.md)
- tau2-bench 2.0: el simulador de usuario pasó de `gpt-4.1` a `openai/gpt-5.5` con poco razonamiento; los controles de comunicación pasan a juzgarse por modelo; los puntajes 2.0 no se comparan con 1.x. — [tau2-bench RELEASE_NOTES](https://raw.githubusercontent.com/sierra-research/tau2-bench/main/RELEASE_NOTES.md)
- tau2-bench 1.0.1, `banking_knowledge` pass^1 tras recalificar: gpt-5-5 de 37,37 a 46,39; claude-opus-4-7 de 25,26 a 30,15; gemini-3-flash de 20,62 a 27,32. Recalificar sólo subió recompensas. Muestra que errores de la prueba movían hasta nueve puntos. — [tau2-bench RELEASE_NOTES](https://raw.githubusercontent.com/sierra-research/tau2-bench/main/RELEASE_NOTES.md)
- Las notas de versión dicen que pass^k cuenta como falla las corridas con error de infraestructura. Según resumen de buscador. — [tau2-bench RELEASE_NOTES](https://raw.githubusercontent.com/sierra-research/tau2-bench/main/RELEASE_NOTES.md)
- Cifras de punta en 2026, no verificadas, sólo fragmentos de buscador y en conflicto: OpenRouter pone a GPT-5.1 primero en airline con 80,0% al 13-nov-2026 — [OpenRouter](https://openrouter.ai/benchmarks/tau2-bench-airline); su versión coreana muestra otro modelo empatado en 80,0% con fecha 10-dic-2026, posterior a hoy, por lo que esa entrada parece errónea — [OpenRouter KR](https://openrouter.ai/ko-KR/benchmarks/tau2-bench-airline); LLM-Stats pone a LongCat-Flash-Thinking-2601 primero en airline con 0,765 — [LLM-Stats](https://llm-stats.com/benchmarks/tau2-airline) y a Claude Opus 4.6 primero en retail con 0,919 — [LLM-Stats](https://llm-stats.com/benchmarks/tau2-retail); un espejo de la tabla de Sierra lista a Qwen3.5-397B-A17B con retail 84,43 y airline 81,5 en pass^1 — [Developers Digest](https://www.developersdigest.tech/benchmarks/tau-bench).
- La tabla original de tau-bench quedó congelada con modelos de fines de 2024; lo nuevo vive en tau2. — [Steel leaderboard](https://leaderboard.steel.dev/leaderboards/tau-bench)
- Google ADK trae simulación de usuario: un generador de mensajes de usuario por modelo, corre local, con un objetivo en lenguaje natural por escenario y sigue hasta cumplirlo; se ajusta por EvalConfig. — [Google Developers Blog](https://developers.googleblog.com/en/announcing-user-simulation-in-adk-evaluation/)
- Google ADK, criterios: `tool_trajectory_avg_score` compara herramientas llamadas contra las esperadas, con coincidencia EXACT por defecto, o IN_ORDER, ANY_ORDER; existen criterios juzgados por modelo para la calidad del simulador por turno y de la trayectoria multi-turno. — [ADK docs](https://google.github.io/adk-docs/evaluate/criteria)

### Inferences
- La vara de Verifika, 26 charlas grabadas con piezas del banco, mide el pipeline con entrada fija; tau2 mide con usuario simulado que reacciona. Son complementarias: lo grabado da reproducibilidad y costo cero, el simulador destapa errores que se componen cuando el cliente contesta distinto.
- El paquete en español de tau2 2.0 y el dominio retail permiten medir un modelo candidato en una tarea parecida a vender, sin armar nada, antes de compararlo con Gemini. Habría que confirmar si el español es rioplatense; lo más probable es que no.
- pass^k aplicado a las 26 charlas con el modelo: correr cada charla k veces y contar sólo las que salen bien todas las veces. Con corridas a un centavo, k igual a 3 o 4 es barato y muestra la variabilidad que un solo número esconde.
- El caso de banking_knowledge confirma la regla del CLAUDE.md de revisar la prueba antes de creer el número: corregir la prueba movió más que muchos cambios de modelo.

### Gaps
- No pude leer tau-bench.com, la tabla oficial, por bloqueo de red; no tengo pass^k de punta verificado para retail o airline en 2026.
- No busqué otros benchmarks conversacionales de 2025-2026 además de tau2 por límite de llamadas.

## Herramientas y práctica de evaluación 2025-2026

### Takeaway
La práctica publicada pone primero el análisis de errores sobre trazas reales, después tareas chicas sacadas de fallas reales, y combina calificadores por código, por modelo calibrado y humanos. Anthropic recomienda arrancar con 20 a 50 tareas de fallas reales y trae un caso donde arreglar la prueba subió un puntaje de 42% a 95%.

### Cited Findings
- Anthropic, 9-ene-2026: arrancar con 20 a 50 tareas simples sacadas de fallas reales; tareas sin ambigüedad, donde dos expertos lleguen al mismo veredicto; una solución de referencia por tarea; 0% en muchas corridas suele ser tarea rota; equilibrar casos donde algo debe pasar y donde no debe; aislar cada corrida; calificar el resultado, no el camino exacto. — [Anthropic Engineering](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- Mismo post: al juez por modelo se le da la opción "Desconocido" para que no invente notas; un juez separado por dimensión; calibrar contra humanos. — [Anthropic Engineering](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- Mismo post: Opus 4.5 sacaba 42% en CORE-Bench hasta que se corrigieron errores de calificación, como rechazar "96.12" contra "96.124991"; con eso y un andamiaje menos rígido llegó a 95%. — [Anthropic Engineering](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- Mismo post: evals de capacidad arrancan bajas y, al llegar alto, pasan a regresión que debe quedar cerca de 100%. — [Anthropic Engineering](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- Mismo post, ejemplo de agente de soporte con usuario simulado: llamadas obligatorias a verificar identidad, procesar reembolso con monto tope y mandar confirmación; control de estado final; rúbrica de tono y de apego a la política leída; tope de 10 turnos. — [Anthropic Engineering](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- Husain y Shankar, FAQ de evals, 27-jun-2025: juntar trazas representativas, codificación abierta con notas libres sobre lo que falló, codificación axial en una taxonomía de fallas, y contar por categoría; leer al menos 100 trazas hasta que no aparezcan fallas nuevas; no arrancar de categorías prefijadas como "alucinación". — [hamel.dev](https://hamel.dev/blog/posts/evals-faq/why-is-error-analysis-so-important-in-llm-evals-and-how-is-it-performed.html)
- Un resumen reporta que en sus proyectos 60 a 80% del tiempo de desarrollo se fue en análisis de errores y evaluación. Fuente secundaria. — [Pragmatic Engineer](https://newsletter.pragmaticengineer.com/p/evals)
- Un equipo usa un modelo para la primera agrupación de notas abiertas y humanos revisan el resultado. — [Pragmatic Engineer](https://newsletter.pragmaticengineer.com/p/evals)
- Libro "Evals for AI Engineers", de Shankar y Husain, listado por O'Reilly para octubre 2026. — [O'Reilly](https://www.oreilly.com/library/view/-/9798341660717/ch03.html)

### Inferences
- La clasificación de fallas del CLAUDE.md, faltó el dato, la herramienta confundió, el modelo se equivocó, la casilla está mal o la prueba está rota, es una taxonomía axial; lo que agrega Husain y Shankar es construirla desde notas libres sobre trazas de producción, leyendo cien o más, y contarla por categoría para elegir qué arreglar.
- `banco_pruebas/produccion.py` ya da las charlas literales; una tanda periódica de lectura y codificación de cien charlas reales sería la fuente de las próximas tareas de la vara.
- La opción "Desconocido" para el juez es trasladable al verificador: que pueda decir "no sé" y que eso vaya a repregunta, no a texto.

### Gaps
- No relevé herramientas abiertas específicas como Inspect, Promptfoo, DeepEval, Langfuse o Phoenix, ni sus versiones y licencias, por límite de llamadas.
- No encontré resultados medidos de cuánto baja la tasa de error al aplicar análisis de errores; la evidencia es de práctica, no experimental.

## Confiabilidad reportada de agentes de cara al cliente y cómo se separa "dice algo falso" de "repregunta"

### Takeaway
No encontré cifras públicas confiables de tasa de afirmaciones falsas en agentes de atención en producción para 2025-2026. Lo publicado mide resolución o puntajes de benchmark, y separa el error del pedido de aclaración sólo de forma indirecta.

### Cited Findings
- Anthropic recomienda combinar evals automáticas para iterar, monitoreo de producción como verdad de base y revisión humana periódica para calibrar. — [Anthropic Engineering](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- Anthropic pide equilibrar tareas donde la conducta debe ocurrir y donde no debe, lo que aplica a responder contra repreguntar. — [Anthropic Engineering](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- tau2-bench 2.0 suma jueces post hoc sólo diagnósticos, fuera de la recompensa, y controles de comunicación juzgados por modelo. — [tau2-bench RELEASE_NOTES](https://raw.githubusercontent.com/sierra-research/tau2-bench/main/RELEASE_NOTES.md)

### Inferences
- La regla de Verifika, vale acertar o repreguntar, lo que importa es no errar, equivale a medir con tres resultados por turno: correcto, abstención o repregunta, y error. Esa separación es la de la predicción selectiva: cobertura contra riesgo. Conviene reportar las dos tasas por separado y no un solo porcentaje.

### Gaps
- Sin cifras verificadas de alucinación en producción de Intercom Fin, Sierra, Decagon u otros; fin.ai quedó bloqueado por la red.
- No encontré estudios que midan la tasa de repregunta contra la tasa de error en bots de venta.

## Escalamiento a humano y ruteo por confianza

### Takeaway
Los diseños publicados rutean en tres bandas, alta confianza resuelve, media deja borrador para humano, baja pasa a humano, pero la evidencia medida es escasa y casi toda de proveedores.

### Cited Findings
- OpenAI Agents SDK: la aprobación humana pausa la llamada a herramienta hasta que se apruebe o rechace. — [OpenAI Developers](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals)
- Fin.ai reporta un modelo codificador multitarea que predice si escalar y por qué, con más de 98% de acierto según la empresa; no verificado, sólo fragmento de buscador. — [fin.ai](https://fin.ai/research/?p=325)
- Ruteo en tres bandas por confianza, de un proveedor. — [eesel.ai](https://eesel.ai/blog/ai-escalation-management)
- Diseño que ante la duda va a humano en vez de responder. — [freeCodeCamp](https://www.freecodecamp.org/news/how-to-build-an-ai-support-agent-that-knows-when-not-to-answer-tickets/)
- Disparadores de escalamiento: confianza de intención bajo umbral, sentimiento y límites de política. — [NICE](https://www.nice.com/agentic-ai/ai-to-human-handoff-in-autonomous-service)
- CHAP, arXiv 2606.09751: protocolo donde el agente con baja confianza declara abstención con categoría y un coordinador abre escalamiento; es diseño, no evaluación. — [arXiv](https://arxiv.org/pdf/2606.09751)
- SCOPE, arXiv 2610.31062: compila políticas en lenguaje natural a programas de predicados; uno verifica si la respuesta realmente conecta al cliente con un humano y lo compara con si correspondía escalar. — [arXiv](https://arxiv.org/pdf/2610.31062)

### Inferences
- Los veredictos deterministas de Verifika, `exists`, `ambiguous`, `not_found`, ya son un ruteo por confianza sin modelo; SCOPE sugiere el paso siguiente: escribir las políticas de la tienda como predicados que el código evalúa sobre cada respuesta, del mismo modo que el verificador.

### Gaps
- No encontré benchmark de 2025-2026 que mida precisión y recall de escalamiento ni calibración de umbrales en atención al cliente.
- La cifra de 98% de fin.ai no se pudo leer en la fuente.
