# FICHA 113 — LA ETAPA 1: LO CONFIRMADO, LAS DOS ARQUITECTURAS Y COMO SE MIDE CADA PROCESO (28-nov-2026)

Se lee entera antes de tocar la traduccion. Viene de las FICHAS 111 y 112. Lo hecho, en `git log` del 27 y 28-nov. El
objetivo de esta etapa, de Martin: **la primera traduccion lograda, con la latencia adecuada.** Acertar o repreguntar
vale; errar no.

## 1. Las palabras, para que no se mezclen

- **Dato 1:** a que se refiere el cliente, traducido desde sus palabras: rubro, producto, atributo, orden, tema. Un
  concepto de la lista cerrada, escrita del lado del usuario: `rubro:auriculares`, `orden:mas_barato`.
- **Dato 2:** el dato de la tienda que responde: modelo, precio, stock, campo de la ficha tecnica. Lo pone el codigo,
  abajo. No es de la etapa 1.
- **El redactor:** el codigo que escribe la respuesta. Necesita el dato 1 y el dato 2.
- **Un reconocedor:** un proceso que produce el dato 1. No redacta.
- **Etapa 1:** cada fila del cliente a su dato 1, desde su punto de vista, aunque la tienda no lo tenga. **Etapa 2:**
  el dato 1 enlazado a la tienda para sacar el dato 2. No se toca hasta que la 1 este cerrada.
- **Luna en la primera llamada solo interpreta** lo que dijo el usuario. No busca en la tienda ni pone el dato 2.

## 2. El principio, Martin, 28-nov

Las preguntas del cliente piden razonamiento, y el razonamiento lo hace el modelo; el codigo no alcanza, porque cada
forma nueva de decir lo mismo pediria una regla nueva, que es el patron que el CLAUDE.md prohibe. Pero al modelo hay que
pasarle la informacion correcta. Cada uno en lo suyo:
- **El modelo razona y decide.**
- **Los embeddings le acercan la informacion correcta:** generalizan a frases nuevas sin reglas nuevas, pero no
  razonan, no entienden la negacion ni el papel de la fila.
- **El codigo hace lo determinista y controla al modelo:** que lo elegido exista en la lista, precios, montos,
  identidad. Nunca interpreta.
- **La base de jerga crece con datos, no con reglas**, desde las charlas reales y medido.

## 3. LA SEPARACION: CONFIRMADA. Se sigue asi

**Luna separa bien y no pierde datos, con razonamiento bajo.** Es lo unico confirmado de la etapa 1.

- **Lo que pierde:** con el tipeo corregido contado como presente, 3 datos en el examen de 138 mensajes y 1 en las 52
  reales, y los cuatro, leidos a mano, son normalizaciones: "pa jugar" escrito "para jugar". Ninguna perdida real.
  `primeros/perdidas.py --examen --ficha` y `--reales --ficha`. Antes del 28-nov se decia que perdia 28 y 5: era el
  guion, que buscaba la palabra literal cuando Luna habia corregido "mause" a "mouse".
- **La latencia, razonamiento bajo:** 2,7 s de mediana sobre las 7.213 llamadas grabadas de Luna en
  `llamada0_modelos`; 2,66 s en los 300 del examen de `primeros`, 3,07 en las 52 reales y 3,49 en el examen de 138,
  con el prompt v14f1b y la ficha.
- **Razonamiento medio:** grabado sobre las 140 con el prompt v2, 4,27 s de mediana. Su acierto no quedo escrito en
  ninguna ficha; no mejora la separacion por lo que se sabe, y tarda mas.
- **Sin razonamiento:** 1,44 s de mediana sobre los 300, FICHA 106, pero con la consigna de separar Y traducir: los
  rubros bien en 133 de 161 mensajes, contra 150 con bajo. **Nunca se midio sin razonamiento con la consigna de solo
  separar.** Si da lo mismo que el bajo, la separacion baja a un segundo y medio.

**Decision de Martin, 28-nov:** se parte de la separacion con razonamiento bajo, unos 3 segundos. Lo de solo separar
sin razonamiento es la primera medicion pendiente; si no iguala, queda el bajo.

## 4. Las dos arquitecturas de la traduccion

Las dos empiezan igual: Luna separa en filas literales.

**A. Luna traduce directo.** En la misma llamada que separa, con el prompt y la ficha del vocabulario de la tienda con
ejemplos, Luna pone la traduccion de cada fila; lo que no entiende lo deja tal cual, y eso va a los embeddings.
Medido en las FICHAS 104 a 107 con otra vara, la etiqueta del examen, y en esta sesion se vio cuanto traduce mal: de las
filas bien separadas, 13 rubros sin marcar o mal marcados, "lo que imprime", "aparato cuadrado con teclas", "una compu
o algo para jugar", "una pantalla tactil portatil" marcada monitor, y condiciones sin traducir, "se escuchan de la otra
cuadra", "grande para pasar fotos", "ineal". Por diseno del prompt, Luna solo marca los campos de la ficha: "gamer" o
"para la oficina" quedan sin marcar a proposito, no es error. Lo que pesa en A: que el prompt y la ficha esten bien
hechos, y eso solo se sabe midiendo.

**B. Luna separa, los embeddings traen candidatos, y Luna elige.** Para cada fila, cinco conceptos de la base de jerga
con la expresion que trajo a cada uno; Luna elige uno, vago si pide algo sin concepto, o ninguno si no pide nada. La
salida va atada por esquema a los candidatos.

**B con herramienta.** Variante pedida por Martin: Luna maneja la busqueda por su cuenta, `buscar_jerga`, hasta tres
veces, reformulando. Va por la puerta Responses de OpenAI: la de chat no acepta herramientas con razonamiento para Luna.

### Lo medido el 28-nov, las 20 filas que Luna separo bien y tradujo mal en A, juzgadas a mano

| Como | Bien | Vago | Error | Mediana | La mas lenta | Costo de las 20 |
|---|---|---|---|---|---|---|
| B, Luna elige, razonamiento bajo | 15 | 3 | 2 | 1,47 s | 2,8 s | 0,16 centavos |
| B, Luna elige, sin razonamiento | 14 | 4 | 2 | 1,04 s | 1,6 s | 0,10 centavos |
| B con herramienta, razonamiento bajo | 15 | 2 | 3 | 3,85 s | 10,6 s | 0,33 centavos |
| B con herramienta, razonamiento medio | 15 | 3 | 2 | 4,05 s | 7,7 s | 0,35 centavos |

La latencia es solo de la eleccion; los embeddings locales suman 1,3 s de mediana por busqueda nueva.
`jerga/prueba20.py` y `jerga/herramienta20.py`.

- **B arregla 15 de las 20 que A tradujo mal**, sin errar en 18. La herramienta acierta lo mismo con el triple de
  latencia y el doble de costo; lo unico que gana es reformular la busqueda, "se escuchan de la otra cuadra" a "muy
  potentes", y eso se puede hacer sin herramienta: que Luna escriba la frase de busqueda de cada fila al separar.
- **Los errores, por proceso:** la salida tiene lugar para un solo concepto, y "una compu o algo para jugar" pierde el
  rubro en todos los modos; la busqueda no trae el bueno para "necesito una compu", porque en la base "compu" va a la
  plataforma, "para la compu"; sin razonamiento, "decime la memoria" va al campo ram en vez del rubro.

### Lo medido el 28-nov sobre 189 tramos con el tramo perfecto de las etiquetas, B sin herramienta

Contra la casilla que escribio Claude, ver seccion 6: no es una vara firme. Sin los 20 datos tecnicos, sobre 169:

| Motor | Bien | Repregunta | Sin el bueno | Error | Mediana | p90 |
|---|---|---|---|---|---|---|
| Gemini Flash Lite, la paga | 142 | 6 | 5 | 16 | 1,29 s | 1,54 s |
| Luna, razonamiento bajo | 139 | 16 | 5 | 9 | 1,13 s | 2,01 s |
| Luna, sin razonamiento | 142 | 11 | 5 | 11 | 1,00 s | 1,42 s |

La clase que se repite en los tres: el papel de la fila. El cliente nombra el producto y se elige el campo de la ficha:
"ddr5 6000" a la pregunta por la RAM, "lo que imprime" a la descripcion.

### Cual de las dos

No se comparo A contra B sobre la misma vara. Por los numeros de las 20, el camino es B, y la proxima sesion mide B
completo y lo compara con A con la misma vara, a mano. Lo dice Claude despues de esta ficha, a pedido de Martin.

## 5. Cada proceso, como se configura y en que estado esta

Cada fila se confirma con una medicion y se anota aca con la fecha y el commit, para no volver a medir lo medido.

| Proceso | Que se configura | Estado |
|---|---|---|
| La vara | juicio a mano de cada salida, con criterio por clase escrito antes de leer; Martin revisa una muestra | por hacer; la casilla del 28-nov no vale |
| Separar | prompt, ficha, razonamiento | confirmado con bajo; solo separar sin razonamiento, sin medir |
| El papel de la fila | Luna lo marca al separar: producto, condicion, pregunta, equipo del cliente, nada | sin medir; es el error que mas se repite |
| La frase de busqueda | Luna escribe al separar como buscaria cada fila | sin medir; reemplaza a la herramienta |
| A, traducir directo | prompt, ficha del vocabulario con ejemplos, razonamiento | medido con la etiqueta del examen, no con la vara nueva |
| La base de jerga | expresiones por concepto, trampas, vagas, descripciones por funcion | hecha, 5.918 y 1.237; faltan formas como "una compu" al rubro |
| Modelo de embeddings | e5 grande local o los de Gemini de produccion | e5 medido; Gemini sin medir, la gratis tiene tope de 1.000 textos por dia |
| Contra que se busca | la base de jerga o el catalogo | medido: la base |
| Como se consulta | fila entera, pedazos, o la frase de busqueda de Luna | medido: la fila entera gana a los pedazos |
| Contexto | el rubro de otra fila | medido: suma uno de 89, si no entran rubros en la busqueda con contexto |
| Cuantos candidatos | 3, 5 | 5, medido en la FICHA 106 que alcanzan |
| Que ve el modelo de cada candidato | el nombre, la expresion que lo trajo, el puntaje | con la expresion, en las 20; falta compararlo |
| Intermediario de codigo | negacion, filtro por papel, datos tecnicos aparte | negacion hecha; lo demas sin medir |
| El atajo de codigo para lo claro | exacta o contenida en la base, sin modelo | 98% de lo que da por claro; falta ver si Luna lo iguala, y si no, sacarlo: un solo camino |
| Elegir | prompt, un concepto o uno por clase, razonamiento | medido; falta uno por clase |
| La herramienta | Luna busca por su cuenta | medido: no conviene |
| Los datos tecnicos | "ddr4", "am4", "4070": el codigo de numeros y compatibilidad | sin vara de etapa 1 |
| La latencia de la etapa entera | separar, embeddings, elegir, en paralelo por fila | sin medir de punta a punta |
| La variacion entre corridas | dos o tres corridas por variante | sin medir en estas pruebas; Luna cambia hasta 7 de 140 |

## 6. Como se mide, para no repetir ni enganarse

1. **La vara es el juicio a mano**, Martin, 28-nov: no se escribe una respuesta correcta de antemano; se lee cada salida
   y se juzga. Para no aceptar lo que suena bien, el criterio de cada clase se escribe antes de leer, y Martin revisa
   una muestra. La casilla del 28-nov, `jerga/casilla_cliente.json`, no vale: la escribio Claude despues de ver lo que
   contesto Gemini, acepta varias respuestas en 37 de 71 tramos, deja sin definir conceptos como uso streaming, y cubre
   solo lo que el examen marca como que no pide nada.
2. **Se mide desde el cliente:** lo que quiso decir, aunque la tienda no lo venda. Las etiquetas del examen mezclan las
   dos etapas, "airpods" figura como no vendido y "wifi 6" para ignorar; cambiar una etiqueta se consulta.
3. **Antes de tocar un prompt, se leen las fallas y se agrupan por clase.** Se corrige la clase, no el caso.
4. **Una variable por prueba**, para saber que movio el numero.
5. **Un conjunto para ajustar y otro congelado** que no se mira al ajustar.
6. **Dos o tres corridas por variante**, por la variacion del modelo.
7. **Siempre latencia y costo**, de cada paso por separado.
8. **Primero una prueba chica**, unas 20 filas, juzgada a mano; si funciona, la grande.
9. Un modelo grande puede proponer variantes de prompt desde las fallas, pero decide la medicion.

## 7. Lo que sigue, en este orden, para la sesion nueva

1. **Separar solo, sin razonamiento**, sobre las 52 reales y el examen de 138: si no pierde datos, la separacion baja a
   un segundo y medio; si pierde, queda el bajo y se parte de los 3 segundos.
2. **El papel de la fila y la frase de busqueda**, que Luna escribe al separar. Se mide con las 20 y despues con todo.
3. **Elegir uno por clase en cada fila**, para no perder el rubro en "una compu o algo para jugar".
4. **Los embeddings de Gemini con la paga** para la base, menos de un centavo: acierto de los candidatos contra el e5
   local y latencia de una consulta.
5. **B completo contra A con la misma vara**, a mano, con criterio por clase escrito antes, sobre las reales y el examen.
6. **Si Luna con candidatos iguala al atajo de codigo**, se saca el atajo y queda un solo camino.
7. Recien con el error de la etapa 1 en cero, o en lo que Martin acepte, se pasa a la etapa 2, con el mismo principio:
   el modelo elige y el codigo pone los datos y controla.

## 8. Los comandos

    python3 banco_pruebas/flujo/primeros/perdidas.py --examen --ficha     # la separacion de Luna, lo que pierde
    python3 banco_pruebas/flujo/jerga/tabla.py                           # arma la base de jerga
    python3 banco_pruebas/flujo/jerga/medir.py [--semillas] [--ver error]   # el atajo de codigo
    python3 banco_pruebas/flujo/jerga/medir.py --vectores [--ver x]      # los candidatos
    python3 banco_pruebas/flujo/jerga/prueba20.py [--correr]             # B sobre las 20, Luna elige
    python3 banco_pruebas/flujo/jerga/herramienta20.py [--correr]        # B con herramienta, las 20
    python3 banco_pruebas/flujo/jerga/elegir.py luna-nada [--correr] [--ver error]   # B sobre los 189

`vectores.py` necesita `onnxruntime`, `tokenizers` y `huggingface_hub`, solo del banco, fuera de requirements.txt. La
cache de embeddings no va al repo y se rearma en un minuto. Luna va por la clave de OpenAI; Gemini con la paga solo con
`MARTIN_AUTORIZO_LA_PAGA=<fecha>` y queda en `libro_paga`.
