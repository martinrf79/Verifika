# Fiabilidad de componentes LLM dentro de software determinista, estado a fines de 2026

Nota de método: arxiv.org no resuelve desde esta sesión, así que no se pudo abrir ningún paper completo. Las cifras de arXiv salen de los resúmenes y fragmentos que devolvió el buscador. Cuando el buscador dio números, se citan; hay que confirmarlos contra el PDF antes de usarlos para decidir. Varias referencias son preprints de 2026 sin revisión por pares.

## 1. Salidas estructuradas y decodificación con gramática: ¿mejoran la exactitud o sólo el formato?

### Takeaway
Las APIs y las librerías ya garantizan JSON válido casi siempre, pero la validez de formato no implica respuestas correctas. Para modelos chicos la evidencia de 2026 muestra que forzar el esquema puede bajar la exactitud, y que el orden de los campos y el prompt pesan más que el decodificador.

### Cited Findings
- Gemini API, noviembre 2025: el soporte de JSON Schema pasa a cubrir todos los modelos Gemini activos, acepta esquemas de Pydantic y Zod directamente, y el orden de claves de la salida sigue al del esquema desde Gemini 2.5, también en el endpoint compatible con OpenAI — [Google blog](https://blog.google/technology/developers/gemini-api-structured-outputs/)
- Antes, el soporte de Gemini se basaba en un objeto de esquema derivado de OpenAPI 3.0 — [Google blog](https://blog.google/innovation-and-ai/technology/developers-tools/gemini-api-structured-outputs/)
- Vertex AI soporta sólo un subconjunto del esquema y los campos no soportados se ignoran en silencio — [Vertex AI docs](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/control-generated-output)
- Documentación vigente de salidas estructuradas de Gemini, con esquemas por Pydantic o Zod — [Gemini docs](https://ai.google.dev/gemini-api/docs/generate-content/structured-output); [Gemini docs, interactions](https://ai.google.dev/gemini-api/docs/interactions/structured-output)
- JSONSchemaBench, enero 2025, ICML 2025: compara seis marcos de decodificación restringida, entre ellos Guidance con llguidance, XGrammar y OpenAI, en cobertura, eficiencia y calidad, junto con la suite oficial de pruebas de JSON Schema. En el conjunto GlaiveAI, la cobertura teórica fue 0,96 Guidance, 0,87 XGrammar y 0,87 OpenAI; los autores dicen que Guidance supera a los demás — [arXiv 2501.10868](https://arxiv.org/html/2501.10868v3); [ICML 2025](https://icml.cc/virtual/2025/51849)
- Origen del debate, 2024, material anterior: Tam y otros, "Let Me Speak Freely?", encontraron que restricciones de formato más estrictas tienden a dañar más el razonamiento — [arXiv 2408.02442](https://arxiv.org/pdf/2408.02442v2)
- Preprint 2026, 2604.03616: el costo mayor viene del prompt, no del decodificador; los ejemplos y la descripción explícita del esquema dejan la mayor parte de la degradación; los modelos cerrados recientes muestran degradación casi nula — [arXiv 2604.03616](https://arxiv.org/pdf/2604.03616)
- Preprint 2026, 2610.35328, once modelos abiertos con ablaciones causales: la degradación aparente viene mayormente de prompts y formatos no equivalentes, no del enmascarado del decodificador; las restricciones que imponen una trayectoria de razonamiento útil pueden subir la exactitud — [arXiv 2610.35328](https://arxiv.org/pdf/2610.35328)
- Preprint 2026 sobre modelos chicos, 2605.26128: la decodificación dura del esquema sube la validez pero baja la exactitud de la respuesta de 19,7% a 11,0% — [arXiv 2605.26128](https://arxiv.org/pdf/2605.26128)
- Nota no revisada por pares, Qwen2.5-7B: poner el campo de respuesta antes del razonamiento baja la exactitud de 79,6% a 22,4% con JSON pedido por prompt; el autor dice que la restricción no es dañina en general — [dev.to](https://dev.to/vaibhav_mittal_ac22a2c5d6/structured-output-fixed-my-json-and-cut-math-accuracy-by-18-points-jm5)
- Preprint 2026 sobre reflexión: la exactitud base cae de 50,0% a 38,0% bajo restricción, con McNemar marginal, p cercano a 0,059 — [arXiv 2604.06066](https://arxiv.org/pdf/2604.06066)
- Preprint 2026, "Draft-Conditioned Constrained Decoding": propone generar un borrador libre y después restringir, como forma de evitar el costo oculto — [arXiv 2603.03305](https://arxiv.org/pdf/2603.03305)
- BAML, parseo alineado al esquema en vez de decodificación restringida: según su propio blog, con n igual a 1.000 por modelo sobre BFCL, gpt-4o pasa de 87,4% con function calling nativo a 93%, y claude-3-5-sonnet de 78,1% a 94,4%; el mismo post admite prompts y esquemas ambiguos en el benchmark. Son cifras del fabricante sin réplica independiente — [Boundary ML](https://boundaryml.com/blog/sota-function-calling); [Boundary ML, SAP](https://www.boundaryml.com/blog/schema-aligned-parsing)
- Capítulo arXiv 2026: las restricciones de esquema garantizan salida parseable, no llamadas semánticamente correctas — [arXiv 2611.10845](https://arxiv.org/pdf/2611.10845)

### Inferences
- Para el bot: la llamada 0 que emite etiquetas de vocabulario debería poner el razonamiento o la línea literal del cliente antes de la etiqueta en el esquema, y la etiqueta como enum cerrado. El orden de campos medido es el efecto más grande que apareció.
- Como el modelo de producción es Gemini y el orden de claves sigue al esquema desde 2.5, ese orden es controlable en la API.
- Si se usa Vertex en vez de la Gemini API, conviene comprobar que ninguna restricción del esquema se esté ignorando en silencio.
- Validez de formato no es exactitud: la vara de turnos acertados sigue siendo la medida, no la tasa de JSON válido.

### Gaps
- No se buscaron mediciones propias de Outlines, XGrammar, llguidance, Guidance, Instructor ni Pydantic AI más allá de JSONSchemaBench; tampoco sus licencias, versiones ni fechas de release. Hay que verlo en sus repos.
- No se encontró ninguna medición de enum restringido contra texto libre en clasificación de etiquetas de catálogo, que es el caso exacto del bot.

## 2. Optimización de programas y prompts: DSPy, MIPROv2, GEPA, SIMBA, TextGrad

### Takeaway
GEPA, oral en ICLR 2026, es hoy el optimizador de prompts con mejor evidencia publicada y está integrado en DSPy como dspy.GEPA. Para clasificación con modelos chicos no apareció una comparación directa y limpia; la recomendación de las propias fuentes es medir sobre el conjunto propio.

### Cited Findings
- GEPA, julio 2025, ICLR 2026 oral: en seis tareas supera a GRPO por 6% de promedio y hasta 20%, con hasta 35 veces menos rollouts; supera a MIPROv2 por más de 10 puntos, por ejemplo más 12 en AIME-2025 — [arXiv 2507.19457](https://arxiv.org/abs/2507.19457); [ICLR 2026 oral](https://www.iclr.cc/virtual/2026/oral/10009494)
- Método de GEPA: muestrea trayectorias, reflexiona en lenguaje natural sobre ellas para diagnosticar fallas, propone y prueba cambios al prompt, y combina lecciones desde un frente de Pareto — [arXiv 2507.19457](https://arxiv.org/html/2507.19457v1)
- Integración y ejemplo: dspy.GEPA; GPT-4.1 Mini en AIME de 46,6% a 56,6% — [repo GEPA](https://github.com/CerebrasResearch/gepa); [Berkeley Sky](https://sky.cs.berkeley.edu/project/gepa/)
- Casos reportados por la vitrina de GEPA, sin revisión: Nubank optimizó prompts de juez, una evaluación de soporte pasó de 68,88% a 88,89%; Databricks dice inferencia 90 veces más barata manteniendo o mejorando — [GEPA use cases](https://gepa-ai.github.io/gepa/guides/use-cases/)
- MIPRO, 2024, material anterior: con Llama3-8B supera a las bases en cinco de siete programas, con ganancias de hasta 13% — [arXiv 2406.11695](https://arxiv.org/html/2406.11695v2)
- SIMBA en un clasificador de juguete: de 0,875 a 1,0, con un conjunto de prueba diminuto, anecdótico — [MLflow quickstart](https://mlflow.org/docs/latest/genai/flavors/dspy/notebooks/dspy_quickstart/)
- Informe de Stanford, ARPO: compara contra SIMBA, MIPROv2 y FewShotRandomSearch en LangProBe con Llama 3B, 8B y 70B, clasificación incluida, y dice que ARPO los supera; el fragmento no trae números — [Stanford CS224R](https://cs224r.stanford.edu/projects/pdfs/224r_project_final_report__1_.pdf)
- Opinión de libro: SIMBA y GEPA llegaron en DSPy 3 y se consideran los más fuertes, según tarea y modelo — [Manning, DSPy cap. 6](https://livebook.manning.com/book/building-llm-applications-with-dspy/chapter-6)
- Lista oficial de optimizadores de DSPy — [dspy.ai](https://dspy.ai/learn/optimization/optimizers)

### Inferences
- El bot ya tiene lo que estos optimizadores necesitan: un conjunto etiquetado, las 26 charlas y sus turnos, y una métrica determinista. GEPA usa la retroalimentación en texto, por ejemplo el motivo de una falla, y eso calza con el verificador que ya existe.
- Riesgo: optimizar contra 75 turnos sobreajusta. Hace falta un conjunto apartado, y la regla del repo sobre arreglos que sólo mueven el caso que los motivó aplica igual al prompt optimizado.
- Costo: GEPA hace muchas llamadas al modelo durante la búsqueda; con la clave gratis de 1.000 pedidos diarios, una corrida podría tomar más de un día.

### Gaps
- TextGrad no se buscó; no hay cifras 2025-2026 en estas notas.
- No apareció ningún número publicado de GEPA o SIMBA en clasificación o extracción con modelos chicos.

## 3. Verificación y autocorrección: verificadores deterministas, jueces LLM, autocorrección, incertidumbre y abstención

### Takeaway
La autocorrección sin señal externa no funciona de forma fiable; la que funciona usa un verificador externo. Los jueces LLM son inestables y sesgados de formas que el acuerdo bruto oculta. Para detectar fallas sin etiqueta, las señales más prometedoras son la consistencia entre consultas repetidas, las sondas sobre estados internos y la abstención calibrada por conformal prediction, todas con resultados dependientes del protocolo.

### Cited Findings
Autocorrección
- Huang y otros, material anterior: sin etiquetas oráculo, las técnicas de autocorrección bajan el rendimiento — [arXiv 2310.01798](https://arxiv.org/pdf/2310.01798)
- ACL 2025, "Dark Side of Intrinsic Self-Correction": la autocorrección intrínseca hace dudar al modelo en respuestas intermedias y finales; propone repetir la pregunta y ajustar con menos de 10 ejemplos — [ACL 2025](https://aclanthology.org/2025.acl-long.1314/); [arXiv 2412.14959](https://arxiv.org/html/2412.14959v2)
- Thought-ICS, 2026: 20 a 40% de mejora con verificador oráculo, y una mejora neta positiva aun sin él — [arXiv 2602.02416](https://arxiv.org/html/2602.02416v1)
- Preprint 2026, "Self-Correction Illusion": el señalamiento explícito de errores depende de cómo se reetiqueta el rol del texto — [arXiv 2606.05976](https://arxiv.org/pdf/2606.05976)

Jueces LLM
- "Reliability without Validity", 2026, 21 jueces de nueve proveedores: el acuerdo por coincidencia exacta no corrige por azar y sobreestima al juez; hay jueces con alta repetibilidad y fuerte sesgo de posición, citan Qwen 3 8B y Gemini 2.5 Flash; el sesgo de verbosidad resultó mucho menor que lo reportado en 2023 — [arXiv 2606.19544](https://arxiv.org/html/2606.19544)
- "Rating Roulette", EMNLP 2025 Findings: los jueces dan juicios inestables consigo mismos entre corridas — [arXiv 2510.27106](https://arxiv.org/html/2510.27106)
- Escala de puntaje, 2026: 0 a 5 maximiza el acuerdo con humanos, 0 a 10 es la peor — [arXiv 2601.03444](https://arxiv.org/pdf/2601.03444v1)
- "Judging the Judges", abril 2026, nueve estrategias de corrección de sesgo en cinco jueces: el sesgo de estilo domina sobre el de posición — [arXiv 2604.23178](https://arxiv.org/html/2604.23178)
- AACL 2026, "All Verdicts are Not Equal": la fiabilidad es por ítem, no por modelo; propone el acuerdo entre consultas repetidas como señal de confianza sin calibración — [ACL Anthology](https://aclanthology.org/2026.aacl-long.207.pdf)

Incertidumbre
- Sondas de entropía semántica, 2024, material anterior: sondas lineales sobre un solo estado oculto, sin muestreo en prueba, generalizan mejor que sondas entrenadas para predecir exactitud; evidencia limitada a QA — [arXiv 2406.15927](https://arxiv.org/abs/2406.15927)
- SEReDeEP, mayo 2025: extiende las sondas a RAG — [arXiv 2505.07528](https://arxiv.org/pdf/2505.07528)
- 2025, detección como etiquetado de tokens en respuestas largas: AUC 0,90 contra 0,71 de entropía semántica en Llama-3.3-70B — [arXiv 2509.03531](https://arxiv.org/pdf/2509.03531v2)
- Preprint 2026: entropía y sondas de corrección se correlacionan sólo moderadamente; combinarlas mejora detección y predicción selectiva en casi todas las configuraciones — [arXiv 2603.21172](https://arxiv.org/html/2603.21172v1)
- Confianza verbal contra probabilidad de token: la comparación cambia con el protocolo y ninguna es una lectura directa de la incertidumbre — [arXiv 2605.27752](https://arxiv.org/html/2605.27752); la incertidumbre verbal lingüística supera a la de tokens y a la numérica en MMLU-Pro, 2025 — [arXiv 2505.23854](https://arxiv.org/html/2505.23854v1); la confianza verbal tiende a sobreestimarse en modelos instruidos — [arXiv 2604.05306](https://arxiv.org/pdf/2604.05306); propuesta de tratar la calibración como criterio de primera clase — [arXiv 2609.26489](https://arxiv.org/pdf/2609.26489)

Abstención y conformal prediction
- Febrero 2025: aprendizaje por refuerzo para ajustar umbrales de conformal prediction en el tiempo, con mejor AUROC de detección de alucinación que los umbrales fijos — [arXiv 2502.06884](https://arxiv.org/html/2502.06884v1)
- UAI 2025: conjuntos de predicción para modelos generativos; la abstención es el conjunto que cubre todo el espacio — [arXiv 2503.10512](https://arxiv.org/pdf/2503.10512.pdf)
- Enero 2026, MedAbstain: conformal prediction marca de forma bastante robusta las respuestas sobreconfiadas; escalar el modelo o instruirlo no mejora la abstención de forma consistente — [arXiv 2601.12471](https://arxiv.org/html/2601.12471v1)
- Octubre 2025: las garantías conformales suponen intercambiabilidad, que se rompe con cambio de dominio — [arXiv 2510.22931](https://arxiv.org/html/2510.22931v2)
- NeurIPS 2026: abstención conformal calibrada por geometría, post hoc — [NeurIPS 2026](https://neurips.cc/virtual/2026/poster/148649)

### Inferences
- El verificador del bot, que compara contra filas reales y cae al texto del código si marca, es el tipo de señal externa que la literatura sí respalda. Agregar una segunda llamada que se autocorrija sin señal externa no tiene respaldo.
- Para los pasos dudosos de la llamada 0, la señal más barata y compatible con una API cerrada es repetir la consulta y medir acuerdo; si dos o tres corridas no coinciden en la etiqueta, repreguntar. Sondas internas no son posibles con Gemini por API.
- Conformal prediction encaja con la vara del repo, que premia repreguntar sobre errar: con un conjunto de calibración etiquetado se fija un umbral con garantía de tasa de error, siempre que el tráfico real se parezca al de calibración. El catálogo cambia, así que el umbral se recalibra.

### Gaps
- No se buscaron modelos de recompensa de proceso ni chain-of-verification con resultados 2025-2026.
- No hay cifras de cuánto acuerdo entre corridas predice error en clasificación de etiquetas.

## 4. Arquitecturas neurosimbólicas, LLM más reglas, LLM-Modulo

### Takeaway
LLM-Modulo, el LLM que propone y verificadores externos que aceptan o rechazan, tiene mejoras medidas grandes pero sobre bases bajas, y casi toda la evidencia encontrada es de 2024.

### Cited Findings
- Posición original, 2024, material anterior: los LLM no planifican solos pero ayudan dentro de marcos con críticos y verificadores externos — [arXiv 2402.01817](https://www.arxiv.org/pdf/2402.01817)
- Noviembre 2024: en Travel Planner, GPT-4o pasa de 8,3% a 23,89% y Claude-3.5-Sonnet de 4,4% a 25% — [arXiv 2411.14484](https://arxiv.org/html/2411.14484v1)
- Mayo 2024: LLM-Modulo con GPT-4-Turbo llega a 20,6% de aprobación final en validación de TravelPlanner — [arXiv 2405.20625](https://arxiv.org/pdf/2405.20625)
- Octubre 2024: o1 con verificadores externos en Sokoban sube de 12,7% a 43,6% — [arXiv 2410.02162](https://arxiv.org/pdf/2410.02162)
- 2026: arquitectura híbrida LLM más modelo chico destilado, con costo, latencia y gobernanza — [arXiv 2609.16091](https://arxiv.org/pdf/2609.16091)

### Inferences
- El diseño del bot, el modelo traduce, el código resuelve identidad con exists, ambiguous o not_found, el código pone los montos, ya es de esta familia. La evidencia dice que el beneficio viene de que el verificador sea duro y externo, y de que haya un bucle de reintento con el motivo del rechazo.

### Gaps
- No se encontraron trabajos 2025-2026 de LLM-Modulo con números en agentes de venta o atención al cliente.

## 5. Ajuste fino de modelos chicos contra prompting para extracción y clasificación

### Takeaway
En tareas estrechas y bien definidas, los modelos chicos ajustados con LoRA igualan o superan a modelos grandes por prompt, con evidencia consistente de 2024 a 2026. El costo real es mantener los datos etiquetados y reentrenar cuando cambia el vocabulario.

### Cited Findings
- Junio 2026, extracción de comercio en transacciones financieras: LLaMA 3.1-8B con LoRA llega a 96,95% de F1; Qwen 3.5 0.8B llega a 94,75% — [arXiv 2606.08051](https://arxiv.org/html/2606.08051)
- Octubre 2025: un Llama 3.2 ajustado llega a 99% de exactitud igualando a GPT-4.1, según el fragmento; la tarea no se pudo confirmar — [arXiv 2510.21970](https://arxiv.org/pdf/2510.21970v1)
- Tesis 2025: modelos chicos ajustados igualan o superan a GPT-4o en clasificación de documentos y extracción de metadatos — [Unibo](https://amslaurea.unibo.it/35299/1/Thesis_AliceTurrini.pdf)
- 2024, material anterior: modelos chicos ajustados superan de forma consistente a GPT-3.5, GPT-4 y Claude Opus sin ejemplos en clasificación de texto — [arXiv 2406.08660](https://arxiv.org/abs/2406.08660)
- 2024, material anterior, LoRA Land: 224 de 310 modelos ajustados superan a GPT-4 — [arXiv 2405.00732](https://arxiv.org/pdf/2405.00732)
- Ejemplo práctico: Llama 3.2 1B ajustado para reemplazar a GPT-4o — [Towards Data Science](https://towardsdatascience.com/i-fine-tuned-the-tiny-llama-3-2-1b-to-replace-gpt-4o-7ce1e5619f3d)

### Inferences
- La llamada 0 del bot, línea a etiqueta de vocabulario cerrado, es justo la clase de tarea donde el ajuste fino gana. Pero choca con dos reglas del repo: un solo servicio y producción con Gemini; servir un modelo propio suma una pieza. Ajustar Gemini por la plataforma de Google evitaría servir el modelo, pero no se verificó si está disponible para el modelo actual.
- Sin varios miles de líneas etiquetadas, la opción intermedia es destilar: etiquetar con un modelo grande, revisar a mano lo dudoso, y entrenar.

### Gaps
- No se encontraron comparaciones de 2025-2026 con números para clasificación en español rioplatense ni con jerga de tienda de tecnología.
- No se verificó el ajuste fino de Gemini en Vertex AI para los modelos actuales.

## 6. Cómo cortar la cascada de errores en tuberías de varias etapas

### Takeaway
La evidencia de 2025-2026 dice que la detección empeora a medida que el error avanza por las etapas, y que controlar la propagación temprano rinde más que detectar al final. Las etapas aguas abajo tienden a adoptar el error de arriba aunque tengan la evidencia para corregirlo.

### Cited Findings
- "Hallucination Snowball", ICML 2026: tubería financiera de 4 agentes sobre FinanceBench con 346 alucinaciones inyectadas; la detección de gpt-4o cae de 72,0% en la etapa 1 a 50,9% en la etapa 4; concluyen que controlar la propagación importa más que detectar — [ICML 2026](https://icml.cc/virtual/2026/77915); [arXiv 2608.14588](https://arxiv.org/pdf/2608.14588)
- Octubre 2025: en tuberías con roles, la etapa de planificación es el origen principal de fallas irrecuperables, y las tuberías sin estructura dejan acumular errores — [arXiv 2510.07614](https://arxiv.org/pdf/2510.07614)
- Marzo 2026, "From Spark to Fire": modela la colaboración como grafo de dependencias y define un criterio de riesgo temprano de amplificación; los errores chicos se endurecen en falso consenso — [arXiv 2603.04474](https://arxiv.org/pdf/2603.04474)
- Junio 2026, "Hallucination Cascade": mide propagación, amplificación y recuperación por afirmación — [arXiv 2606.07937](https://arxiv.org/abs/2606.07937)
- 2026, "When Upstream Messages Override Correct Answers": los agentes de abajo adoptan la respuesta equivocada de arriba aun teniendo la evidencia para corregirla; cita la taxonomía de 14 modos de falla de Cemri y otros, 2025 — [arXiv 2609.36855](https://arxiv.org/pdf/2609.36855)
- 2026, agentes de código: la fiabilidad depende del sistema alrededor del modelo — [arXiv 2608.13867](https://arxiv.org/pdf/2608.13867)

### Inferences
- Para el bot, la primera etapa, separar y traducir, es la equivalente a la planificación: un error ahí el verificador final no lo ve, porque el texto final es coherente con filas reales pero de otro producto. Eso respalda medir por capas con entrada perfecta, como ya hace el repo, y poner la compuerta de abstención en la salida de la llamada 0, no sólo al final.
- La segunda llamada no debería recibir la etiqueta como hecho cerrado sin la línea original del cliente; los estudios muestran que lo de arriba pisa a la evidencia.
- Con etapas independientes de exactitud p1, p2, p3 el total es el producto; la forma barata de subirlo es convertir errores en repreguntas en la etapa temprana.

### Gaps
- No se encontraron estudios con números sobre tuberías de comercio conversacional.
- Los números de 2026 salen de resúmenes; no se pudo abrir el texto completo por el bloqueo de arxiv.org.
