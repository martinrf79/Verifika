PLAN, escrito antes de correr (24-nov-2026, orden de Martin)

Hipotesis: una base de conocimiento cargada a mano, con la jerga, lo que quiere decir y la condicion ejecutable sobre la
fuente, mas codigo que filtra el catalogo, resuelve las caracteristicas de producto sin modelo de lenguaje en buena parte
de las frases, sin errar, y manda al verificador solo las que no reconoce.

La base, `base.py`, tres grupos por entrada:
- expresiones: como lo dice el cliente;
- concepto: lo que quiere decir;
- condicion: campo de la fuente, operador y valor, que el codigo ejecuta sobre productos.csv, compatibilidad.csv y
  specs_por_modelo.csv. Los rubros salen de `alias.json`, la jerga de la tienda que ya esta en el repo. Marcas y
  modelos salen del catalogo por codigo.
Cada condicion se controla contra el catalogo: si no apunta a ninguna fila, la entrada no vale.

El resolvedor, `resolver.py`:
- precio por regex, como el tope del podado; negacion por codigo, "no", "sin", "que no sea" antes del concepto;
- marca y modelo por coincidencia aproximada contra el catalogo;
- el resto: cada trozo de la frase, de una a cuatro palabras, contra las expresiones de la base con un modelo de
  embeddings local, multilingual-e5, en el procesador;
- zona verde: el trozo esta cerca de una expresion, se aplica la condicion; zona amarilla: cerca pero no tanto, se
  repregunta, que en el bot seria pasar al verificador; lejos: se ignora.
- decide: si hay rubro, marca o modelo y el filtro deja filas, ofrece hasta tres, ordenadas si se pidio orden; si la
  zona amarilla tiene algo sin resolver, repregunta; si nada apunta a la tienda, no hay.

Los cortes de las zonas se fijan en la validacion, las frases de Luna de `chico/frases.jsonl`, con etiquetas por regla,
maximizando acierta menos tres veces erra. No se tocan despues de ver la prueba.

Prueba: las 48 frases de `traductor/muestra.py`, congeladas con hash, misma correccion que el podado: acierta, repregunta,
erra, con y sin dudosas. Se informa tambien que parte iria al verificador.

Aviso de validez: quien escribe la base ya vio las 48. Las expresiones salen del conocimiento general y de alias.json,
no se copian de la prueba; por eso se mide ademas sobre la validacion, que nadie miro al escribir la base.

Cambio de alcance, 24-nov, antes de correr la prueba y despues de ver la validacion: la mitad de los errores de la
validacion eran modelos nombrados, "el i5 12400F", "la Fury Beast", que en el bot resuelve el nexo de nombrado y no
esta base. La validacion queda en las reglas sin modelo nombrado, y en la prueba se informan aparte las frases que
nombran un modelo. El detector de modelos de este resolvedor es provisorio.

Base: el podado, 39 / 5 / 4 en las 48, y 32 / 2 / 0 sin las dudosas, 2,5 s y una decima de centavo por frase.
Costo: cero tokens; tiempo por frase en el procesador, mediana y percentil 90.
