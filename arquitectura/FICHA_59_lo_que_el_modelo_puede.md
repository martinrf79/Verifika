# FICHA 59 — Lo que el modelo puede, lo que puede con ayuda y lo que no

Medido el 26-sep-2026 con `banco_pruebas/sonda_modelo.py`, antes de diseñar
nada. El modelo es el de `app/config.py`. Cada prueba va con contexto nuevo,
herramientas simuladas con guion y cinco repeticiones a temperatura 0,2. Las
respuestas están en `banco_pruebas/sonda_modelo_corridas.jsonl` y el informe se
vuelve a sacar con `python3 -m banco_pruebas.sonda_modelo --informe`.

## El hallazgo que ordena todo

**Cada caso dio cinco de cinco o cero de cinco.** No hubo casos a medias. A
esta temperatura el modelo no es azaroso: cuando falla, falla siempre igual.
Eso significa que cada falla se arregla una vez, con diseño, y queda
arreglada.

## Lo hace solo

- Partir un mensaje de uno a seis pedidos, aun sin puntuación.
- Elegir la herramienta correcta, con siete o con veinte herramientas.
- Esperar un resultado antes de decidir: "si no hay", "si anda", "si pasa de",
  comparar y elegir, y cadenas de tres eslabones, en las dos ramas de cada
  condición.
- Resolver "el segundo", "el otro", "el de 37 mil", "el más barato de esos",
  "el logi del principio", y "el jbl de hace rato" con noventa productos en la
  libreta.
- Decir "ambiguo" cuando se lo preguntan directo.
- Aplicar correcciones: destino, color, "lo mismo más barato", "ah no, mejor".
- Decir que le falta un dato del cliente.
- Buscar un producto por nombre en una lista de 880 filas.
- Cuentas de dos a tres productos, porcentajes, cuotas y umbral.

## Lo hace con ayuda: la ayuda ya está medida

- **Nombres de campo.** Leyó `sin_marca` como un sí o un no y puso "verdadero".
  Con el campo llamado `marca_excluida`, pasó de cero de cinco a cinco de cinco.
  Regla: el nombre del campo dice qué va adentro.
- **Repregunta con ordinal.** Ante "el primero", contó por el orden de la
  libreta y no por el de la pregunta. Con las opciones numeradas en la
  pendiente, cinco de cinco. Regla: la pendiente guarda las opciones numeradas.
- **Dato que la ficha no trae.** Contestó "12.000 DPI" de su propia memoria.
  Marcar en la ficha que el dato no figura ayudó a medias, tres de cinco. La
  regla puesta al final del sistema, más dura, dio cinco de cinco. Regla: lo
  crítico va al final, y el código verifica igual.

## No lo hace: va al código

- **Cuentas de cinco productos o más, y repartir entre varios.** Cero de cinco.
- **Contar filas** en una lista de cien o más. Cero de cinco.
- **La ambigüedad dentro de una tarea grande.** Dice "ambiguo" si se le
  pregunta sólo eso, pero cuando planifica, ante "¿y ese cuánto?" con tres
  productos, elige en vez de preguntar. La referencia se resuelve en un paso
  aparte, o la resuelve el código con la libreta.
- **Su confianza no sirve.** Dijo noventa o más en todas, también cuando se
  equivocaba.

## El diálogo

- Planificar los pasos con dependencias lo hace bien en nueve de once. Falla
  en no preguntar por "ese", y en olvidar la compra cuando el cliente dice
  "dame".
- Consultado, prefiere llamar a la herramienta y ver el resultado antes que
  escribir un plan cerrado. Coincide con lo medido: el loop de herramientas no
  falló ninguna dependencia.
- Su opinión sobre sí mismo vale poco: a una pregunta sobre cuentas contestó
  sobre contabilidad general.

## Segunda tanda, el mismo día

**La regla dura no rompe nada.** Con la regla al final en todas las pruebas
con herramientas: elegir, dependencias y no inventar dieron todo bien, 205 de
205, incluido el "12.000 DPI" que antes fallaba siempre.

**La temperatura alta trae el azar.** A temperatura 1 aparecen los casos a
medias: partir, correcciones y planes, y una vez inventó un precio que antes
nunca inventaba. Regla: temperatura baja en todo lo que interpreta o decide.

**Charlas de varios turnos.** Se corrieron las 104 charlas de las varas del
repo, 179 turnos, con el historial entero como memoria y sin libreta, con
`banco_pruebas/sonda_charlas.py`. Quedaron 60 enteras bien por la nota
automática. Leídas una por una, las fallas son de tres clases:

- **Del banco, no del modelo, la mayoría.** La nota no reconocía un producto
  pedido por id, una compra por id, o una respuesta correcta sacada del
  historial sin llamar a nada.
- **De las herramientas, muchas.** El buscador de prueba no tiene precio
  mínimo, origen ni peso, y su rubro no entiende "disco externo". El modelo
  entonces concluye mal con datos parciales: dijo que no había notebooks de
  más de 900 mil porque la herramienta le mostró sólo tres. **El buscador es
  el cuello, no el modelo.**
- **Del modelo, pocas y conocidas:** no repregunta ante "el asus" con varios;
  pierde la marca cuando el cliente cambia de rubro, "el monitor" después de
  hablar de Samsung; suma plata él mismo en vez de llamar a calcular, cinco
  turnos, con la cuenta bien; y una vez dio por sabido el costo de envío a
  Salta sin consultarlo.

La memoria lejana sin libreta anduvo: el destino de hace varios turnos, "el
tercero", "cuál sale menos", "la impresora del principio".

**El caché anda, también con herramientas obligatorias.** Con un comienzo
largo e idéntico, la API informó entre 57 y 85 por ciento de la entrada
cacheada, con herramientas y con llamada obligatoria. En las charlas dio cero
porque el prompt no llegaba al mínimo que el proveedor cachea. Regla: adelante
lo fijo y largo —sistema, herramientas y tablero, siempre iguales y en el
mismo orden—; atrás lo que cambia. Lo que lo rompe es variar la lista de
herramientas por turno o meter algo cambiante adelante.

## Lo que queda por medir

- Las charlas reales del issue 31, como fuente de pruebas nuevas.
- El buscador de verdad del repo en lugar del simulado, que es donde se
  concentraron las fallas.
