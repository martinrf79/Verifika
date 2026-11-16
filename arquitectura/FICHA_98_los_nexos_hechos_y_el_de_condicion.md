# FICHA 98 — Los nexos hechos y el de condición, el último

16-nov-2026, sesiones con Martín del 15 y 16-nov. Sigue a la FICHA 97, que tiene el detalle y los números de cada paso,
secciones 8 a 11. **Escrita para que una sesión nueva arranque el nexo de condición sin volver al chat.** Lo hecho, en
`git log` del 15 y 16-nov.

---

## 1. Dónde estamos

El flujo de la FICHA 96 en el banco, `banco_pruebas/flujo_nuevo.py`: la llamada 0 separa, traduce y marca el destino; un
solo pedido de embeddings por mensaje; cada nexo busca con su propia configuración; el código elige; Jev confirma lo
dudoso; el código redacta. Todavía no hay segunda llamada al modelo: se hace cuando estén todos los nexos.

| Nexo | Estado | Dónde |
| --- | --- | --- |
| Rubro y producto | hecho, calibrado, Jev en lo dudoso | `banco_pruebas/nexo_rubro.py` |
| Destino | hecho, código de producción | `flujo_nuevo.nexo_destino` |
| Tema de la FAQ | hecho, Jev en lo dudoso | `banco_pruebas/nexo_tema.py` |
| Producto nombrado | hecho, palabra exacta | `banco_pruebas/nexo_nombrado.py` |
| **Condición** | **falta: es el de esta sesión** | |

**Cómo busca cada nexo está en un solo lugar, `banco_pruebas/busquedas.py`**, y los nexos toman de ahí sus números.
`python3 banco_pruebas/busquedas.py` lo imprime. El de condición suma su entrada ahí.

## 2. Lo medido, en mensajes que los nexos no vieron

| Banco | Qué es | Resultado |
| --- | --- | --- |
| las 140, `nuevas70` y `nuevas70b` | donde se armaron | rubro elige bien 74, 72, 73 y 106; lo que no se vende 14 de 14 |
| `nombrados38.py` | modelos gemelos | 39 de 40, ningún modelo cambiado |
| `reales.py` | 40 mensajes reales de WhatsApp | 39 sin falla, 45 de 45 rubros, 13 de 13 temas |
| `reales.py --525` | las 525 de `traduccion58` sin las de memoria, 365 | 312 sin falla, 320 de 320 rubros, 132 de 135 modelos |

Lo que falla en los bancos nuevos casi no es de los nexos: es la llamada 0, que con dos modelos en una frase,
"entre el G305 y el G203", deja uno solo.

**Datos de la fuente, decididos el 16-nov con el criterio que Martín delegó:** "off" pasa a palabra clave de promociones
en `faq.json`; "keyboard" y "keyboard gamer", a alias de teclado en `alias.json`; escritorio y cámara de fotos, a
`no_vendidas.json`. Los reales pasan de 38 a 39 sin falla y las 365 de 305 a 312; las 140 y la batería, 532 tests, igual.
Los números romanos, "hyperx cloud 2", no: sería una lista en el código, y hoy pregunta entre los Cloud en vez de
equivocarse.

## 3. Lo que decidió Martín y vale para el de condición

1. **La elección final es una función de código** entre los candidatos que traen los embeddings. Lo dudoso lo confirma
   **Jev** con una pregunta de lista cerrada por mensaje: le ganó a la llamada corta de Gemini, 15-nov.
2. **Sin umbral de puntaje**: los puntajes de lo que hay y lo que no hay se pisan, FICHA 95. "Ninguno" es una opción de
   la lista cerrada, no un corte.
3. **Se contesta solo con la fuente**; lo que no se confirma, no hay o se repregunta.
4. **Se calibra la búsqueda, no la vara.** Cada variante cambia una cosa y se mide con la misma vara; lo que se elige se
   prueba en bancos que no se usaron para calibrar. `nexo_rubro.py --calibrar` es el modelo.
5. **Sin listas de palabras.** Lo que haga falta sale de la fuente: catálogo, alias, FAQ, `no_vendidas.json`.
6. **La paga, con la autorización de Martín en la sesión**; la gratis se traba con la cuota de embeddings. Todo gasto,
   anotado en `banco_pruebas/libro_paga.jsonl`.
7. **El push solo con el ok de Martín**, al final.

## 4. El nexo de condición

**Qué le llega:** las palabras de la búsqueda después del producto, sobre el rubro o el modelo que ya eligió el nexo de
rubro o el nombrado. En el flujo, 188 líneas de las 140: "mouse barato", "monitor 24 pulgadas", "teclado mecanico",
"memoria 8gb ddr4", "router wifi 6", "silla que aguante 120 kilos", "disco externo chiquito que entre en el bolsillo".
Hoy el ruteo las manda por tener palabras después del producto, y el nexo devuelve repreguntar.

**Lo que ya existe en producción y conviene usar, no rehacer:**
- `app/core/flujo/catalogo.py`, `buscar`: rubro más condiciones en palabras del cliente más orden; cada condición se ata
  a un campo del catálogo en el orden de `PRIORIDAD`, y lo que no se ata no filtra y se dice.
- `catalogo.atar` y `tests/test_atar_indice.py`: de 63 condiciones de la ficha nativa ata 52; las vagas de verdad,
  "silencioso", "chiquito", "marca conocida", no.
- Los campos de la tienda: `productos.csv`, `specs_por_modelo.csv`, `specs_por_categoria.json`,
  `specs_preguntables.json`.

**Cómo encaja en el diseño de los otros nexos:**
- **Los candidatos:** los campos del rubro elegido. Embeddings de cada palabra o frase de condición contra los campos y
  sus valores, o el atado de producción por texto; se mide cuál trae el campo correcto entre los primeros.
- **La función de código que elige:** los números los lee el código, "24 pulgadas", "650w", "120 kilos", "200 lucas";
  orden y tope, "barato", "el más liviano", "que no pase", también.
- **Jev en lo vago:** "que no haga ruido", "chiquito", "bueno para editar". Lista cerrada: los valores del campo, o
  ninguno.
- **El borde con el nombrado:** el catálogo mete atributos en el nombre del modelo, "Mesh", "Curvo", "DDR4", y ahí corren
  los dos. Hay que decidir quién manda.

**La vara, escrita antes:** las 188 líneas de las 140 y las condiciones de los 40 reales y de las 365, con
`agendas58.py`, que trae las condiciones de cada `buscar` escritas a mano. Lo que filtra tiene que estar en la fila real.

## 5. Después del de condición

1. **La llamada 0 con otros modelos**, con todos los nexos, sobre los cuatro bancos. Lo que mirar: separar dos modelos
   en una frase y no perder preguntas en mensajes largos.
2. **Modelos de embeddings locales**, FastEmbed o Model2Vec, contra los de Gemini en los mismos bancos: menos latencia y
   sin costo, si dan igual. Suma paquetes a `requirements.txt`: lo decide Martín.
3. La auditoría y el pase a `app/` reemplazando al agente.

## 6. Cómo se corre todo, sin gasto

```bash
python3 banco_pruebas/flujo_nuevo.py              # el flujo de punta a punta sobre las 140
python3 banco_pruebas/nexo_rubro.py --jev         # el nexo de rubro con Jev
python3 banco_pruebas/nexo_rubro.py --calibrar    # las variantes de su búsqueda
python3 banco_pruebas/nexo_tema.py --con jev      # el nexo de tema
python3 banco_pruebas/nexo_nombrado.py [--sonda]  # el nombrado y sus variantes de escritura
python3 banco_pruebas/reales.py [--525]           # los mensajes que no vieron
python3 banco_pruebas/busquedas.py                # cómo busca cada nexo
```

Los vectores no están en el repo: pesan decenas de megas. Quedan los puntajes, que alcanzan para repetir los números.
Si cambia un documento o una consulta, se recalculan por centavos; recalculados el 15-nov dieron diferencia cero.
