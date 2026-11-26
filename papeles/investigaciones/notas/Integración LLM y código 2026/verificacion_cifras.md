# Verificación de cifras contra fuentes primarias

Notas del 26-nov-2026. Se leyeron con la API de arXiv, export.arxiv.org, los resúmenes y metadatos de las catorce preprints; se bajaron y leyeron los PDF de Laban, Arbor, tau-bench y StateMemBench; se leyó la nota de Anthropic y las notas de versión y los datos del tablero de tau2-bench en el repo de Sierra. Quedaron bloqueados por la red: iclr.cc, proceedings.iclr.cc, openreview.net y aclanthology.org. tau-bench.com redirige a taubench.com, que no está habilitado, y en el reintento dio 522 y la misma redirección; el tablero se leyó desde sus datos en GitHub. Los venues que no se pudieron abrir se marcan como confirmados por buscador, no por página primaria.

## Fiabilidad multi-turno, flujos y estado de diálogo

### Takeaway
Laban, Arbor y ReacTOD se confirman en lo esencial, con tres matices: el PDF de Laban dice 39% en el texto y 35% en la figura 1; la cifra de Arbor es 29,4 puntos sobre turnos, no navegación en general, y con Claude Sonnet 4.5 Arbor fue más lento; ReacTOD es un taller, TrustNLP, no la conferencia principal. El estudio de cascada no es de la conferencia ICML sino de un taller de ICML 2026.

### Cited Findings
- CONFIRMADO. Laban, Hayashi, Zhou, Neville, "LLMs Get Lost In Multi-Turn Conversation", arXiv 2505.06120, v1 del 9-may-2025. Resumen: "an average drop of 39% across six generation tasks". Texto, sección 6.1: "an average degradation of -39%" y "CONCAT performance averaging 95.1% of the FULL counterpart". Los modelos chicos, Llama3.1-8B, OLMo-2-13B y Claude 3 Haiku, recuperan menos en CONCAT, 86 a 92 — [arXiv 2505.06120](https://arxiv.org/abs/2505.06120); [PDF](https://arxiv.org/pdf/2505.06120)
- INCONSISTENCIA INTERNA. El mismo PDF, en el epígrafe de la figura 1: "The 15 LLMs we test perform much worse in multi-turn settings (-35%)". Conviene citar 39% del texto y del resumen, y aclarar que la figura dice 35% — [PDF](https://arxiv.org/pdf/2505.06120)
- VENUE, confirmado sólo por buscador: hay página de oral y de póster en ICLR 2026; una página de Microsoft Research habla de premio a mejor paper y otras de Outstanding Paper, sin confirmar. Revisado por pares en ICLR 2026, pero la versión de arXiv no lo dice — [ICLR oral](https://iclr.cc/virtual/2026/oral/10009147); [ICLR póster](https://iclr.cc/virtual/2026/poster/10009146); [Microsoft Research](https://www.microsoft.com/en-us/research/?p=1139409)
- CORREGIDO EN EL MATIZ. Arbor, Sword Health, arXiv 2602.14643, v1 16-feb-2026, v4 20-jul-2026, sin venue en arXiv, preprint. Resumen: "Arbor improves mean turn accuracy by 29.4 percentage points, reduces per-turn latency by 57.1%, and achieves an average 13.8x reduction in per-turn cost", sobre 10 modelos y turnos anotados de triage clínico real. Tabla 2: precisión de turno 88,23% con Arbor contra 58,80% de base, más 29,42 puntos. Tabla 4: Claude Sonnet 4.5 con Arbor 91,15% más o menos 2,1, contra 43,33% más o menos 3,8 con un solo prompt — [arXiv 2602.14643](https://arxiv.org/abs/2602.14643); [PDF v4](https://arxiv.org/pdf/2602.14643v4)
- MATIZ de Arbor: con Claude Sonnet 4.5 la latencia empeora, 17,63 s con Arbor contra 9,10 s de base, por las varias llamadas; es la única excepción — [PDF v4](https://arxiv.org/pdf/2602.14643v4)
- CONFIRMADO. ReacTOD, arXiv 2605.19077, 18-may-2026, "Accepted at TrustNLP Workshop at ACL 2026", taller con revisión. Resumen: lazo ReAct acotado, "improving accuracy by up to 9.3 percentage points over single-pass inference on MultiWOZ"; validador simbólico "achieving a 93.1% self-correction rate on intercepted errors". MultiWOZ 2.1 cero-shot: gpt-oss-20B 52,71% de JGA, 14 puntos sobre el mejor anterior; Qwen3-8B 47,34%; SGD: Claude-Opus-4.6 80,68%, Qwen3-32B 64,09%. La filiación a Amazon no se verificó: el resumen de la API no trae autores con empresa — [arXiv 2605.19077](https://arxiv.org/abs/2605.19077)
- CORREGIDO EN EL VENUE. "The Hallucination Snowball", arXiv 2608.14588, fecha de publicación en arXiv 22-jun-2026. Comentario: "accepted at the FAGEN Workshop (Failure Modes in Agentic AI), ICML 2026". Es taller, no conferencia principal. Resumen: "gpt-4o detection drops from 72.0% at Stage 1 to 50.9% at Stage 4", 346 alucinaciones inyectadas en una tubería de 4 agentes sobre FinanceBench; 23,7% sobrevive sin detectar; probabilidades de escape por frontera 24,6%, 48,3% y 89,3%; las compuertas en cada frontera bajan la supervivencia de 58,4% a 16,2% contra chequear sólo al final, que mejora apenas 2,3 puntos — [arXiv 2608.14588](https://arxiv.org/abs/2608.14588)
- RAREZA: el identificador 2608 corresponde a agosto pero la API da publicado el 22-jun-2026; no cambia las cifras — [arXiv 2608.14588](https://arxiv.org/abs/2608.14588)

### Inferences
- La compuerta en cada frontera, no al final, es lo que mide el Snowball; calza con validar la salida de la llamada 0 antes de los nexos y no sólo con el verificador final.
- Arbor no promete menos latencia con modelos grandes y rápidos; con Gemini habría que medirla.

### Gaps
- No se pudo abrir iclr.cc ni openreview.net para confirmar el venue de Laban ni el premio.
- No se confirmó la filiación de ReacTOD a Amazon ni se abrió la página de ACL Anthology del taller.

## Salidas estructuradas y optimización de prompts

### Takeaway
Las tres cifras se confirman. El 19,7 a 11,0 es sobre modelos de menos de 3B, Qwen2.5-0.5B, Qwen2.5-1.5B y SmolLM2-1.7B, con decodificación dura de sólo la respuesta. GEPA se confirma tal cual, ICLR 2026 oral.

### Cited Findings
- CONFIRMADO. "The Constraint Tax", arXiv 2605.26128, 20-may-2026, preprint sin venue. Resumen: en 15.000 generaciones con Qwen2.5-0.5B, Qwen2.5-1.5B y SmolLM2-1.7B, "hard answer-only schema decoding raises schema validity from 61.5% to 100.0%, but lowers answer accuracy from 19.7% to 11.0% and increases wrong-valid-schema outputs from 49.5% to 88.9%". En una tarea de llamada a herramienta de calendario, Qwen2.5-1.5B da 91,5% con JSON pedido por prompt y 48,0% con el esquema duro, ambos 100% válidos. Patrón propuesto: "reason free, constrain late" — [arXiv 2605.26128](https://arxiv.org/abs/2605.26128)
- CONFIRMADO. "Constrained Decoding: Harmful or Beneficial?", arXiv 2610.35328, 26-oct-2026, preprint. Resumen: "Across four model families and eleven open-source models, causal ablations ... reveal that apparent performance degradation largely stems from non-equivalent prompting and output formats rather than from decoder-level masking"; las restricciones de validez mejoran la extracción y las de razonamiento pueden subir la exactitud — [arXiv 2610.35328](https://arxiv.org/abs/2610.35328)
- CONFIRMADO, complementario. "The Format Tax", arXiv 2604.03616, 4-abr-2026, preprint: "format-requesting instructions alone cause most of the accuracy loss, before any decoder constraint is applied"; separar razonamiento de formato recupera la mayor parte; los modelos cerrados recientes casi no pagan ese costo. Seis modelos abiertos y cuatro de API — [arXiv 2604.03616](https://arxiv.org/abs/2604.03616)
- CONFIRMADO. GEPA, arXiv 2507.19457, v1 25-jul-2025, v2 14-feb-2026, comentario "Accepted to ICLR 2026 (Oral)". Resumen: "Across six tasks, GEPA outperforms GRPO by 6% on average and by up to 20%, while using up to 35x fewer rollouts. GEPA also outperforms the leading prompt optimizer, MIPROv2, by over 10% (e.g., +12% accuracy on AIME-2025)". El resumen dice "6%" y "10%", sin aclarar si son puntos o relativos — [arXiv 2507.19457](https://arxiv.org/abs/2507.19457)

### Inferences
- El modelo de producción no es un modelo de menos de 3B, así que el 19,7 a 11,0 no se traslada directo; lo que sí se traslada es el patrón de las tres preprints: pedir el razonamiento o la línea literal antes del campo cerrado.

### Gaps
- No se leyó la tabla de GEPA para saber si "10%" son puntos absolutos.

## Memoria y estado vigente

### Takeaway
StateMemBench se confirma: los cuatro valores de Mem0 y A-Mem van de 0,127 a 0,199, o sea 13 a 20% redondeado, y StateMem sube de 0,205 a 0,363. La cifra de Anthropic de 39% se confirma, pero es de septiembre de 2025, de una evaluación interna de búsqueda agéntica, no revisada.

### Cited Findings
- CONFIRMADO. "Can Agent Memory Systems Track Evolving State?", StateMemBench, arXiv 2608.19652, 20-ago-2026, preprint. 234 escenarios de varias sesiones. Resumen: StateMem "improves current-state accuracy over the strongest same-backbone baseline by 1.8x (0.205 -> 0.363) on DeepSeek-V4-Flash and over the strongest memory system by 1.6x (0.149 -> 0.233) on Qwen-3.5-9B"; como envoltorio de una llamada suma "+32 to +67 points" sobre seis backends, y un control de largo y costo atribuye "+15 to +32" a la estructura de estado — [arXiv 2608.19652](https://arxiv.org/abs/2608.19652)
- CONFIRMADO en la tabla del PDF: estado vigente, Mem0 0,149 y A-Mem 0,127 con Qwen-3.5-9B; Mem0 0,177 y A-Mem 0,199 con DeepSeek-V4-Flash. El texto dice que StateMem supera "the best memory system by 1.8× (A-Mem, 0.199)". Con el envoltorio, Mem0 llega a 0,566 y 0,594. Zep se cita pero no aparece evaluado en las tablas leídas — [PDF](https://arxiv.org/pdf/2608.19652)
- CORRECCIÓN DE REDACCIÓN: el 0,205 a 0,363 es contra la mejor línea base del mismo backbone; contra el mejor sistema de memoria en DeepSeek el salto es desde 0,199 — [PDF](https://arxiv.org/pdf/2608.19652)
- CONFIRMADO. Anthropic, "Managing context on the Claude Developer Platform", 29-sep-2025: "On an internal evaluation set for agentic search ... combining the memory tool with context editing improved performance by 39% over baseline. Context editing alone delivered a 29% improvement." En una evaluación de 100 turnos de búsqueda web, la edición de contexto bajó el consumo de tokens 84%. Evaluación interna del fabricante, sin revisión — [Anthropic](https://www.anthropic.com/news/context-management)

### Inferences
- StateMemBench es el único de estos números que mide justo la falla del pedido que se corrige; el dato fuerte para el bot no es el 0,363 sino que la memoria extraída da el estado viejo o falla en más del 80% de los casos.

### Gaps
- No se encontró evaluación de Zep ni Letta en StateMemBench.

## Catálogo, fuera de base y benchmarks de compra

### Takeaway
ShoppingBench, ShoppingComp, la caída de pass^k de tau-bench y 2508.02296 se confirman. tau2-bench 2.0 del 19-oct-2026 trae español para retail. En el tablero oficial, los datos del repo dan primero en retail a Qwen3.5-397B-A17B con 84,43 de pass^1, y ninguna entrega es todavía de la versión 2.0.

### Cited Findings
- CONFIRMADO. "Knowing When Not to Answer", arXiv 2508.02296, v1 4-ago-2025, v3 2-jul-2026. Resumen: PCA sobre embeddings de la base, 16 dominios, ataques generados por LLM y uno de 4chan; "low-dimensional detectors achieve competitive OOD performance while being faster, cheaper, and more interpretable than prompted LLM-based judges". Venue ACL 2026 long, páginas 16266 a 16301, revisado por pares, confirmado por buscador; la Anthology quedó bloqueada — [arXiv 2508.02296](https://arxiv.org/abs/2508.02296); [ACL Anthology](https://aclanthology.org/2026.acl-long.740/)
- CONFIRMADO. ShoppingBench, arXiv 2508.04266, v1 6-ago-2025, v4 18-jun-2026, comentario "Accepted for oral presentation at AAAI 2026". Resumen: "even state-of-the-art language agents (such as GPT-4.1) achieve absolute success rates under 50%"; arenero con más de 2,5 millones de productos reales — [arXiv 2508.04266](https://arxiv.org/abs/2508.04266)
- CONFIRMADO. ShoppingComp, ByteDance BandAI, arXiv 2511.22978, v1 28-nov-2025, v2 8-feb-2026, preprint. Resumen: 145 instancias, 558 escenarios, 35 expertos; "17.76% for GPT-5.2, 15.82% for Gemini-3-Pro" — [arXiv 2511.22978](https://arxiv.org/abs/2511.22978)
- CONFIRMADO. tau-bench, arXiv 2406.12045, 17-jun-2024, ICLR 2025. Tabla de pass^1: gpt-4o retail 61,2, airline 35,2. Texto: la probabilidad cae "to as low as ∼25% for pass^8 on τ-retail"; resumen: "pass^8 <25% in retail" — [arXiv 2406.12045](https://arxiv.org/abs/2406.12045); [PDF](https://arxiv.org/pdf/2406.12045)
- CONFIRMADO. tau2-bench 2.0.0, "Release Date: October 19, 2026": "`--language` selects a language pack (`en`, `es`, `pt`, `hi`, `zh`, `ko`) with a localized database, tasks and caller personas for airline, retail and telecom, in text and voice"; "Scores are not comparable with 1.x" — [RELEASE_NOTES](https://raw.githubusercontent.com/sierra-research/tau2-bench/main/RELEASE_NOTES.md)
- TABLERO OFICIAL, leído de los datos del repo el 26-nov-2026, 30 entregas de texto. Retail pass^1 y pass^4: Qwen3.5-397B-A17B 84,43 y 59,65, Sierra, 2-mar-2026; RAFT-30B-A3B 82,46 y 61,40, Northeastern, 30-abr-2026, entrega custom con simulador claude-sonnet-4-5; GPT-5.2 81,58 y 51,75; Claude Opus 4.5 79,61 y 51,75; Gemini 3 Flash 76,75; Gemini 3 Pro 75,88; GLM-5 73,68; Claude Sonnet 4.5 72,37. Todas las de Sierra con tau2 1.0.1 y simulador gpt-5.2, 4 intentos. Las entregas de mayo a octubre de 2026, entre ellas GPT-5.5, Claude Opus 4.6 a 5 y Gemini 3.1 Pro, no traen retail: sólo banking_knowledge — [manifest](https://raw.githubusercontent.com/sierra-research/tau2-bench/main/web/leaderboard/public/submissions/manifest.json); [entrega Claude Opus 4.5](https://raw.githubusercontent.com/sierra-research/tau2-bench/main/web/leaderboard/public/submissions/claude-opus-4-5_sierra_2026-02-26/submission.json)
- CONTRADICE al agregador: el 0,919 de Claude Opus 4.6 en retail que lista llm-stats no aparece en el tablero oficial; ahí Opus 4.6 no tiene retail — [manifest](https://raw.githubusercontent.com/sierra-research/tau2-bench/main/web/leaderboard/public/submissions/manifest.json)
- CONFIRMADO con matiz de venue. Extracción de comercio, arXiv 2606.08051, v1 6-jun-2026, v4 8-sep-2026, "Accepted for publication at the IEEE International Conference on Data Mining (ICDM) 2026", revisado por pares. Resumen: "Our deployed LoRA-fine-tuned LLaMA 3.1-8B reaches 96.95% F1"; "Qwen 3.5 0.8B reaches 94.75% F1"; Qwen 3.5 4B con JSON-Only 96,60% de F1 y 91,67% de coincidencia exacta por registro — [arXiv 2606.08051](https://arxiv.org/abs/2606.08051)

### Inferences
- Para el bot, la cifra útil de tau2 es la caída de pass^1 a pass^4: aun el mejor de retail baja de 84 a 60. Mide consistencia, que es lo que el bot necesita.
- El 96,95 es extracción de campos desde descriptores bancarios, no vinculación a un catálogo; sirve como cota de lo que da un modelo chico afinado en una tarea cerrada.

### Gaps
- No se pudo abrir tau-bench.com: redirige a taubench.com, fuera de la red de la sesión. La tabla se reconstruyó desde los datos del repo; la página puede ordenar o filtrar distinto.
- No hay entregas tau2 2.0 en el manifest, así que no hay puntaje oficial en español.
- No se confirmó si el paquete en español es rioplatense.
