PLAN (escrito antes de correr modelos)
Muestra: 45 frases reales (prod y examen_real) que no estan en traductor/muestra.py; max 3 por patron; con vacias y dudosas marcadas. Reglas escritas en muestra.py y congeladas con sha256 en hash.txt antes de cualquier llamada.
Top-15: embeddings de cada frase (gemini-embedding-001, clave GEMINI_API_KEY primero) contra el indice de la tienda, como cand.py.
Combinacion fijada: extractor canonico (extraer.py, gemini-3.1-flash-lite) + decidir canonico. Si decide ofrece: camino rapido, se responde. Si no_hay o repregunta: verificador por requisitos (prompt de luna.py, mismo modelo gemini-3.1-flash-lite) sobre los 15 y decision por codigo de decidir_verif.py. Sin otras ramas, sin ajustes despues de ver resultados.
Correccion: acierta / repregunta / erra contra aceptables; falla_busqueda si ningun aceptable en los 15 (se informa). Con y sin dudosas.
Tiempo: segundos por frase de punta a punta = embedding + extractor + (verificador si corresponde), sin esperas de 429.
Costo: gastos.jsonl; tope 10 centavos. Primero 3 casos, luego todo, resultados guardados al momento. Auditoria de 10 al azar.
Claves: GEMINI_API_KEY (gratis) primero; paga solo si 429 no cede en 2 reintentos y con la autorizacion indicada.
