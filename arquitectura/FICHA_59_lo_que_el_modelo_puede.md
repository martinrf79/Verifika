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

## Lo que queda por medir

- Si la regla dura del final rompe otras pruebas de no inventar.
- Temperatura más alta, que es donde puede aparecer la variación.
- Charlas de varios turnos: la sonda mide un turno por vez.
- Las charlas reales del issue 31, como fuente de pruebas nuevas.
