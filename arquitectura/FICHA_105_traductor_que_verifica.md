# FICHA 105 — EL TRADUCTOR QUE VERIFICA: DE LA JERGA DEL CLIENTE A LAS FILAS DEL CATÁLOGO (22 y 23-nov-2026)

Todo en el banco, nada en `app/`. Los guiones y lo grabado están en `banco_pruebas/flujo/traductor/`.

## 1. El problema

Los embeddings traen al producto correcto entre sus 15 candidatos casi siempre: 40 de 40 en la muestra nueva. El cuello
de botella es elegir. El pedido del cliente viene en jerga y la fila está en el idioma del catálogo. Jev y el nexo de
condición eligen nombres de campo sin ver los productos, y ahí se perdía la condición: acertaba el 73% e inventaba el 5%.

## 2. Lo que se probó, y por qué se descartó

- **El selector por código**, que vota por rubro: erra 64 de 330. Sirve para agrupar y filtrar, no para elegir.
- **La búsqueda híbrida**, BM25 más embeddings: empata en rubro y es peor en condición.
- **Los operadores, las descripciones de campo y la opción "no es exactamente esto"**: no mejoran, y Luna queda más
  cauta.
- **El diccionario de jerga** que escribe un modelo por cada valor del catálogo: 5 de 23. La jerga real es abierta y no
  entra en una lista.
- **El extractor a un esquema canónico**, sin ver las filas: 38%. Todo lo que no entra en el esquema termina repreguntado.
- **El agente archivado con Luna**, en el examen real: 61%. Falla por estado mal guardado, 29 de 51 fallas, y en el
  primer mensaje.
- **El reordenador de OpenRouter**: el saldo se acabó a mitad de la corrida y no quedó resultado.

## 3. Lo que anda: el verificador podado

Una sola llamada a un modelo rápido. Recibe la frase del cliente y las 15 filas candidatas, recortadas: nombre, rubro,
precio y campos técnicos, sin descripción, stock ni etiquetas. Devuelve solo los requisitos con la cita del cliente, las
filas que sirven y las dudosas con el dato que les falta.

El código hace el resto:
- controla que la cita esté en la frase;
- aplica el tope de precio con el precio de la fila;
- decide: si alguna fila sirve, la ofrece; si hay dudosas, repregunta; si no queda ninguna, responde que no hay.

El modelo y la clave están en `podado.py` y `run.py`. El prompt es `podado.SIS`.

**Medido el 23-nov** sobre 48 frases reales nuevas, con jerga, congeladas con hash antes de correr:
- **Todas:** acierta 39, repregunta 5, erra 4.
- **Sin las 14 de regla dudosa:** acierta 32 de 34, repregunta 2, erra 0.
- **Tiempo del modelo:** mediana 2,5 segundos y percentil 90 de 3,5.
- **Tokens:** 1.900 de entrada y 170 de salida.
- **Costo:** menos de una décima de centavo por frase.
- **Para comparar,** el verificador entero, con filas completas y un veredicto por requisito: el mismo acierto, pero 9
  segundos y 5.000 tokens.

**El piso:** un "di hola" a ese modelo tarda 2,5 segundos desde el contenedor del banco. El verificador ya está en el
piso de la API, y bajar de ahí depende de cómo y desde dónde se lo llama, no del prompt.

## 4. Lo que sigue, en orden

1. **Medir el piso desde Cloud Run**, en `southamerica-east1`: la llamada mínima y el verificador podado, por la puerta
   OpenAI-compatible y por la nativa.
2. **El orden por campo pedido**, "el más liviano" o "el más barato". El código ordena las filas que sirven por ese
   campo; hoy ofrece tres sin ordenar. Es el error de V06.
3. **Las reglas dudosas, con Martín:** "que no sea chino", que hoy da "no hay"; "mouse con luces"; "mucha plata para
   gastar". Ver `muestra.py`, la marca `dudosa`.
4. **El cableado detrás de la llamada 0 v14f1b**, en una ficha propia y con el ok de Martín. Cada línea que separa Luna
   pasa por los embeddings, después por el verificador podado y después por la decisión del código. Las varias líneas de
   un mensaje van en paralelo. V46, "un mouse barato y un mousepad", necesita esa separación.
5. **Más adelante:** destilar el verificador en un modelo chico, usando sus propias salidas como etiquetas, servido con
   GPU fuera de Cloud Run; y que la jerga de producción, sacada de las frases que repreguntó, alimente la muestra.

## 5. Cómo se prueba: la regla de validez

1. Antes de correr se escriben, en el `plan.md` de la prueba, la hipótesis, la métrica y la muestra.
2. La muestra se congela con hash. Cada patrón entra 2 o 3 veces como máximo; "lo menos chino" no puede pesar 16 veces.
   La respuesta correcta sale de una regla sobre el catálogo, no del modelo que se prueba. Las reglas dudosas se marcan
   y se reportan aparte.
3. Una sola cosa cambia contra la base, y sobre los mismos casos.
4. Antes de gastar:
   - se mira el saldo;
   - se prueban 3 casos y se ve que la entrada no venga vacía;
   - cada resultado se guarda al momento, nunca al final.
5. Al final se revisan a mano 10 casos al azar, para saber si la corrección está bien.
6. El informe da N, acierta, repregunta, erra, el tiempo con mediana y percentil 90, y el costo.

**Las claves:** primero la gratis. Ante 429 o 503 repetidos se pasa a la paga, solo con
`MARTIN_AUTORIZO_LA_PAGA=<fecha>` y el ok de Martín en la sesión. El gasto va a `banco_pruebas/libro_paga.jsonl`. El
manejo está en `run.llamar`.

## 6. Cómo se usa Sonnet sin gastar de más

Lo que gasta Sonnet cuenta para el plan de Martín. En esta sesión, cada informe costó entre 80 y 300 mil tokens, porque
leía archivos enteros y exploraba.

- **Para lo corto lo hace Opus directo:** ver un archivo, una cuenta sobre lo grabado, correr un guion que ya existe.
  Delegar sale más caro.
- **A Sonnet se le delega una corrida larga o una clasificación de muchos casos**, nunca la exploración.
- **El prompt a Sonnet lleva:**
  - las rutas exactas de los archivos a leer y a reusar, y la prohibición de explorar el repo;
  - el pedido de no imprimir JSON enteros ni releer archivos grandes;
  - el guion base a copiar, como `podado.py`, en lugar de describir el método;
  - las reglas de validez de la sección 5 y el tope de gasto;
  - un informe en prosa, sin tablas y de 6 a 10 líneas, con los números de la sección 5.
- **Los tokens de cada informe** se leen en su `usage`. Si pasa de 150 mil, el prompt estaba flojo.
- **Una corrida que tarda** se corre en segundo plano. Si no avanza en 10 minutos, se mira el archivo de resultados y
  los procesos, no se espera.
