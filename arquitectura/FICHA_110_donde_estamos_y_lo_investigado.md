# FICHA 110 — DÓNDE ESTAMOS Y LO INVESTIGADO (26-nov-2026, para la sesión que sigue)

Se lee entera antes de proponer. Viene de la FICHA 109: la primera etapa de la condición quedó hecha y medida. En la
sesión que sigue, Martín decide por dónde seguir; esta ficha deja el punto exacto y lo que dijeron las dos
investigaciones del 26-nov.

## 1. Dónde estamos

La condición tiene dos etapas:

1. **Cómo tiene que ser el producto.** Hecha y medida, `banco_pruebas/flujo/primeros/condicion.py`, FICHA 109, sección 8.
   El cliente dice "inalámbrico, negro, hasta 50 mil, el más barato" y el código ata cada condición a la fuente, filtra,
   ordena sobre lo que cumple y dice no hay con la alternativa si nada cumple. Con el orden aplicado, el primero sirve
   en 33 de 42 sintéticas, 34 de 43 del examen y 16 de 17 reales, contra 9, 4 y 4 sin la capa. Los números y las
   fallas clasificadas, en el Resultado 6 de `banco_pruebas/flujo/lab/plan.md`.
2. **Qué pregunta el cliente del producto.** Falta. "Tiene luces", "cuánto dura la batería", "anda con la PS5",
   "contame qué trae". Lo previsto, FICHA 108, sección 9.3: el campo preguntado se lee de `specs_por_modelo.csv` para
   el producto elegido, y vacío es "la ficha no lo trae"; compatibilidad con `conceptos/compat.py`; las
   características, de la descripción recortada; los temas de la FAQ, por id.

Tres arreglos chicos de la rueda, que no son de la condición y no la frenan: "ryzen 7"[procesador] abre otro pedido en
la notebook; Luna junta dos productos en una fila; el rubro dicho sin marcar, "la memoria más cara".

## 2. Lo que dice algo falso, medido el 26-nov

`banco_pruebas/flujo/primeros/falsos.py`, primeros mensajes sin memoria, con la rueda y la capa. Falso es ofrecer un
producto que no sirve, ofrecer lo que no hay, decir no hay cuando hay, o dar como el más barato uno que no lo es.

De 627 mensajes: 88% todo bien, 3,5% sin contestar algo, que el bot repreguntaría, y 8,6% dice algo falso. Por
conjunto: sintéticas 7,7%, examen 10%, reales 11,5%, muestras 8%.

Los falsos del examen y las reales, uno por uno: cerca de la mitad son productos que la tienda no vende y el bot mete
en el rubro más parecido, termo Stanley, drone DJI, impresora 3D, un Razer que no existe, alquilar notebooks, memoria
DDR3; cerca de un cuarto es memoria de la charla, "la notebook que te pregunté primero"; el resto, palabras raras,
"monitor grande", y regateos o frases de prueba.

Martín, 26-nov: un bot que falla así al tercer o cuarto mensaje no es vendible. La vara que se acordó mirar primero
es cuántas veces dice algo falso, con las repreguntas contadas aparte.

## 3. Las dos investigaciones del 26-nov, en corto

Los informes completos, con cada fuente, en `papeles/investigaciones/`; las notas de cada frente, en
`papeles/investigaciones/notas/`. Martín, 26-nov: las conclusiones de la primera ya las conocía; se guardan por si
hacen falta.

**Integración LLM y código 2026.** Lo medido en fuente primaria:
- revisar en cada frontera de una cadena baja los errores que sobreviven de 58 a 16%; revisar solo al final, 2 puntos;
- los modelos rinden 39% menos con el pedido repartido en turnos, y recuperan el 95% si se les da todo junto;
- la memoria extraída por un modelo da el estado vigente solo entre 13 y 20 de cada 100 veces cuando el cliente
  corrige;
- forzar un esquema duro no da exactitud: la línea literal del cliente va antes de la etiqueta;
- ningún framework de agentes ni bot en producción publica cuánto se equivoca en una charla.
Lo que propone para el bot: un "no lo vendemos" antes de la búsqueda por parecido, un control a la salida de Luna, y
el pedido como estado que escribe solo el código.

**Arquitecturas cognitivas y herramientas.** Lo nuevo:
- la causa de perder el hilo es la interferencia: el dato viejo sigue a la vista y le gana al nuevo, en 39 modelos, sin
  mejora con el tamaño; casi nunca es un dato inventado;
- reescribir lo que dijo el cliente pierde el matiz, "estoy viendo" pasa a "quiere": guardar la frase literal al lado
  del valor normalizado;
- marcar qué dato reemplaza a cuál, guardar versiones del pedido y cortar la charla en partes cuando cambia el producto
  en foco, para "la otra" o "la segunda";
- reglas más modelo donde el modelo interviene solo si las reglas no alcanzan; un agente rápido que contesta y otro
  lento que piensa qué quiere el cliente; lecciones cortas de las charlas con contador de útil y dañina.
Herramientas abiertas y activas: GLiNER2, clasificador chico en español que corre en CPU; LettuceDetect, detector de
lo que no tiene respaldo, con modelo en español; python-statemachine, para el estado del pedido; LangWatch Scenario,
para probar charlas largas; bm25s, RapidFuzz y symspellpy, para nombres, tipeo y abreviaturas. Un modelo local suma
torch y transformers, que hoy no están en `requirements.txt`: se consulta antes.

## 4. Lo que se decide en la sesión que sigue

Martín, 26-nov, lo decide en el chat nuevo:
1. Seguir por la segunda etapa de la condición, la ficha técnica, y después la memoria.
2. O sumarle datos a la arquitectura actual, por ejemplo la jerga de los clientes.

Antes de proponer: leer esta ficha, la 108 y la 109, y mostrar lo grabado del caso, regla de CLAUDE.md.

## 5. Los comandos

    python3 banco_pruebas/flujo/primeros/condicion.py --atar [--ver]         # la capa sola contra la etiqueta
    python3 banco_pruebas/flujo/primeros/condicion.py [--examen|--reales|--muestras] [--ver]   # punta a punta
    python3 banco_pruebas/flujo/primeros/falsos.py [--examen|--reales|--muestras]              # lo que dice algo falso

Los embeddings de las consultas quedan en `banco_pruebas/flujo/lab/vectores.json.gz`, fuera de git. La gratis tiene un
tope de mil por día; el 26-nov se completaron con la paga autorizada por Martín, un centavo.
