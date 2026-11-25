PLAN, escrito antes de entrenar y de correr (23-nov-2026, orden de Martin)

Hipotesis: un modelo chico, un reordenador ya entrenado en varios idiomas y ajustado con la fuente de la tienda, elige
entre los 15 candidatos de los embeddings igual que el verificador podado de la FICHA 105, en una decima de segundo, con
el procesador y sin tokens.

Datos de entrenamiento, ninguno de la muestra de prueba:
- Reglas armadas por codigo desde el catalogo: rubro solo, y rubro con marca, modelo nombrado, inalambrico, plataforma,
  color o uso gamer. Los aceptables de cada regla los da `traductor/catalogo.acept`, no un modelo.
- Por cada regla, Luna escribe frases como las diria un cliente por WhatsApp, con jerga y errores. Luna solo redacta:
  la etiqueta sigue siendo la de la regla.
- Pares para entrenar: cada frase contra todos los modelos de su rubro y algunos de otros rubros, con la fila recortada
  igual a la que lee el podado, `traductor/podado.fila`.
- Una parte de las reglas queda aparte para validar y fijar los dos umbrales, sirve y dudosa.

Prueba: las 48 frases de `traductor/muestra.py`, congeladas con hash, con sus 15 candidatos grabados en
`traductor/cand.json`. La misma decision por codigo que el podado: tope de precio por la frase, ofrece si alguna fila
pasa el umbral alto, repregunta si alguna pasa el bajo, si no, no hay. Los umbrales se fijan en la validacion,
maximizando acierta menos tres veces erra, porque errar pesa mas que repreguntar; no se tocan despues de ver la prueba.
Se mide tambien el modelo sin ajustar, tal como viene, para saber cuanto pone el ajuste.

Una sola cosa cambia contra la base: el que elige. Mismos 48 casos, mismos 15 candidatos, misma correccion.

Metricas: acierta, repregunta, erra, con y sin las dudosas; tiempo por frase en el procesador, mediana y percentil 90;
memoria del modelo cargado. Costo: lo que gasta Luna en redactar las frases, tope de 15 centavos.

Base: el podado, 39 / 5 / 4 en las 48, y 32 / 2 / 0 sin las dudosas.

---

PLAN DE LA SEGUNDA PRUEBA, escrito antes de correr (25-nov-2026, orden de Martin): EL MODELO CHICO COMO VERIFICADOR DE
CONDICION, NO COMO TRADUCTOR

Hipotesis: el modelo chico no entiende la frase del cliente, pero puede decir si una condicion corta, como "mecanico" o
"con luces", esta escrita en la ficha de un producto. Tres veredictos: cumple, no cumple, sin dato.

Guion: `chico/condicion.py`. Modelo: multilingual-e5-small, tal como viene, en ONNX cuantizado, sin ajustar. Corre fuera
del repo, en la carpeta de la sesion, sin tocar `requirements.txt`.

La ficha de cada producto, en frases: los campos de texto de `fuente.VISTA` como "campo: valor", lo extra partido por
coma, cada color, cada forma de conexion y cada plataforma.

La regla, por codigo: el puntaje de una condicion contra un producto es el parecido mas alto con alguna de sus frases.
Cumple si pasa el umbral. Si no pasa y algun producto del rubro lo pasa, no cumple. Si ningun producto del rubro lo pasa,
sin dato.

La verdad, por codigo, de `conceptos.json`: cumple si el producto esta en las filas del concepto; sin dato si el campo del
concepto esta vacio en ese producto; si no, no cumple. Las condiciones etiquetadas sin_dato del examen son sin dato en
todo el rubro.

Calibracion: el umbral se fija con los conceptos de atributo, color y plataforma que el examen NO usa, contra todos los
productos de los rubros donde el concepto tiene alguna fila, maximizando aciertos menos tres veces los "cumple" falsos,
que son la alucinacion. No se toca despues.

Prueba: las condiciones de atributo, color y plataforma del examen fijo, y las de sin_dato, contra todos los productos
de su rubro. Dos entradas: las palabras del cliente tal cual, y el nombre del concepto, que es lo que escribiria Luna.

Metricas: por veredicto verdadero, cuantos acierta; los cumple falsos aparte; tiempo por par.

Que diria que anda: cumple falsos por debajo del 2 por ciento y sin dato bien detectado en la mayoria. Si no, el modelo
chico tal como viene no sirve como verificador y se dice.
