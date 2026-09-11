# FICHA 50 — Los tres mapas y la herramienta de búsqueda. Abierta.

**Decidida con Martín el 11-sep-2026, después del apagón.** El diseño no se
cambia sin preguntarle; se lee esta ficha entera antes de tocar nada.

**ESTADO al 11-sep, noche. EL MOTOR ESTÁ; EL MAPA 2 TAMBIÉN; FALTAN EL 1 Y EL 3.**

El mapa 2 —ENVÍO— se hizo primero y fuera de orden, con motivo: no era que
faltara el mapa, era que el motor de envío estaba ENTERO y desenchufado. Vive en
`fuente.texto_envio`, se genera de la fuente igual que los otros —la FAQ y la
tabla de provincias— y viaja siempre, como el inventario. Con destino trae la
tarifa exacta ya cotizada y el plazo; sin destino, las zonas, el umbral de envío
gratis y qué dato falta para cotizar. Cuesta 70 tokens y apaga la política del
rango, que pesaba 251 caracteres: en un mensaje de envío no cuesta nada, y el
número que sale pasa a ser el exacto en vez del rango.

El renglón de "lo que NO tenemos" ya está adentro de ese mapa: sin provincia ni
código postal el bloque dice que no hay tarifa y que hay que pedir el dato, en
vez de dejar que el modelo prometa un monto.

Hecho: la recorrida única del catálogo —`filtros_catalogo.recorrida`— con el
tipo de campo en tres valores, y **el motor**, `app/core/motor.py`: una sola
puerta, consulta estructurada, el modelo la llama y el código la ejecuta.
Borradas las cuatro funciones que adivinaban por el cliente.

Faltan el mapa 1 —PRODUCTO— y el 3 —POLÍTICAS—, y el orden se invirtió con
motivo. **El motor va primero
porque sin él el mapa no se puede medir.** Medido con la clave gratis, 6 de 6:
el modelo busca sin mapa ninguno. O sea que el mapa no es lo que lo habilita:
es lo que le ahorra vueltas. Cuánto ahorra es lo que falta medir.

**TRES DECISIONES QUE ESTA FICHA NO TENÍA Y AHORA SÍ:**

1. **Son tres mapas y UN motor.** No tres motores. El mecanismo de buscar es el
   mismo en los tres; un segundo motor sería la complejidad volviendo.
2. **La forma de la búsqueda es consulta estructurada.** Ni palabra clave sola
   —ya falló, medido— ni embeddings, que quedan afuera por la regla 10.4: un
   vecino cercano no se puede mapear a un id certificado. El texto libre entra
   como un campo más, no como el mecanismo.
3. **Lo que el mapa 1 tiene que sumar y esta ficha no decía:** qué se puede
   HACER con cada campo —filtrar, ordenar, las dos, ninguna— y en cuántos
   productos está cargado. Y enumerar por VARIEDAD, no por tipo ni por largo:
   `dimensiones` tiene 850 valores distintos en 880 productos y listarlos es
   basura; `pais_fabricacion` tiene 5 y es justo el que hace falta para D8.
   Maqueta medida del mapa 1 entero con esa regla: 1.349 tokens.

El detalle del cambio está en `git log`, no acá.

---

## EL PROBLEMA, en una línea

El código no razona, así que no puede elegir qué fichas ponerle delante al
modelo. Y el catálogo entero no entra cuando la tienda tiene siete mil
productos. Entre esas dos paredes vivió el proyecto durante meses.

Lo que se probó y falló, para no repetirlo: que el código adivine la búsqueda
desde el texto crudo, y que el modelo declare veinte campos de una taxonomía
nuestra antes de ver un solo dato.

---

## LA SALIDA: vocabulario, no datos

**El modelo no recibe el catálogo. Recibe el VOCABULARIO de la fuente, y una
herramienta para buscar en ella.**

Un resumen del catálogo crece con el catálogo. Un vocabulario no: crece con la
VARIEDAD, no con la cantidad. Siete mil productos de las mismas categorías
tienen el mismo vocabulario que ochocientos.

Medido el 11-sep sobre la tienda viva, con las tres piezas que ya existen
—`fuente.inventario`, `filtros_catalogo.campos_filtrables` y
`fuente.temas_consultables`—: **823 tokens** para 880 productos, 22 categorías,
41 campos y 129 temas. La estimación para siete mil productos es 1.500 a 2.500
tokens, y el motivo es que sólo crecen dos cosas: los nombres de categoría y los
valores distintos de cada campo.

---

## SON TRES MAPAS, NO UNO

Tres áreas, tres vocabularios, y **no se mezclan**. Mezclar dos enums en uno ya
costó caro en este repo —los 50 temas de la FAQ contra los 106 de criterio, con
27 nombres repetidos— y la lección está en `git log`.

### Mapa 1 — PRODUCTO

- Las categorías reales con cuántos hay en cada una.
- Los campos filtrables con su tipo: número, texto, sí/no.
- Los valores más frecuentes de cada campo de texto, con tope de 30 y un
  "y otros" al final. Marcas, colores, materiales.
- El rango de precios de la tienda.

### Mapa 2 — ENVÍO

- Las zonas que la tienda cotiza.
- Qué hace falta para cotizar: localidad, provincia o código postal.
- Si hay umbral de envío gratis.

### Mapa 3 — POLÍTICAS

- Los nombres de los temas que la casa tiene escritos.
- Nada más. La política entera la trae la búsqueda, no el mapa.

---

## EL RENGLÓN QUE HOY NO EXISTE Y ES EL QUE COMPRA HONESTIDAD

**Cada mapa dice también lo que NO tiene.**

Que no hay campo de ruido. Que no hay campo de comodidad. Que `origen` es prosa
—"Marca Genius de Taiwán. Fabricado en China"— y por eso no se puede filtrar ni
ordenar por él.

Sin ese renglón el modelo promete "el más silencioso". Con ese renglón contesta
que ese dato no lo tenemos cargado, que es la verdad.

Vale tanto como la lista de campos.

---

## EL ESPAÑOL NO ES PROBLEMA DEL MAPA

El mapa cubre la TIENDA. El idioma lo cubre el modelo, que para eso está.

"Un rectángulo con teclas" no está en ningún mapa: el modelo ve que existe la
categoría `teclado` y traduce. El typo, la capciosa, la indecisión y la
referencia lejana son idioma, y el modelo ya sabe.

Lo único que le pedimos es que traduzca del español al vocabulario de la tienda.

---

## LA HERRAMIENTA DE BÚSQUEDA

Una sola puerta, un solo nombre. El modelo la llama, el código la ejecuta.

Qué tiene que poder:

- Buscar con las palabras del cliente.
- Filtrar por los campos reales de la fuente.
- Ordenar por cualquier campo numérico.
- Excluir lo que el cliente negó.
- Buscar por id, que es como resuelve la memoria.
- Aceptar varias consultas en una sola llamada.
- Devolver veredicto: existe, ambiguo, no existe.
- Decir cuántos había, no sólo los que trae.
- Decir qué condición no se pudo cumplir.
- Traer lo más parecido cuando nada cumple.
- Nunca volver vacía sin motivo escrito.
- Tope de filas, para no inundar el prompt.
- **Poder llamarse de nuevo**: si lo que salió no sirve, el modelo busca otra vez.

`filtros_catalogo` ya sabe hacer casi todo esto sobre los 41 campos. La pieza
que falta es que el modelo pueda pedirla y recibir el resultado en el mismo
turno.

---

## CÓMO QUEDA ATADA AL MODELO — tres candados, no uno

1. **El esquema.** Va como herramienta del proveedor, no como texto. El modelo
   la ve en cada turno.
2. **La guarda de procedencia**, que ya existe en `app/core/numeros.py`. Un
   número que no está en lo que se le puso delante no sale al cliente.
3. **La medición.** Un renglón por turno, `motor_turno`, y sale SIEMPRE: haya
   buscado o no. Dice cuántas vueltas costó, si volvió a buscar, si repitió la
   misma consulta, qué veredictos salieron y **qué condición no se pudo
   cumplir**, que es el renglón que dice qué campo le falta a la fuente. Lo
   agrega `banco_pruebas/produccion.py` sobre la ventana que se pida, así que
   el número se lee desde el issue 31 sin entrar a ninguna consola.

Con los tres, el modelo no puede evitarla. Y con el tercero sabemos cuántas
veces lo intentó.

---

## POR QUÉ ESTO ES MOTOR Y NO PARCHE

**Los tres mapas se GENERAN de la fuente. No se escriben a mano.**

Tienda nueva, catálogo nuevo, mapa nuevo, sin tocar una línea de código. Es la
propiedad que lo hace servir para cualquier ecommerce y no sólo para la demo.

---

## QUÉ SE HACE, en orden

1. Los tres mapas, generados de la fuente, con su renglón de lo que no existe.
2. La herramienta de búsqueda, una sola, con el contrato de arriba.
3. El turno pasa a tener una vuelta más: el modelo busca y después contesta.
4. Los veinte moldes de `app/core/tipos.py` se adelgazan: el mapa dice qué se
   puede contestar, el molde dice cómo suena.
5. Cada falla real de WhatsApp entra como caso en `tests/test_turno_nuevo.py`,
   antes de arreglarla.

## QUÉ NO SE TOCA

La memoria. Las diez herramientas deterministas. La guarda de procedencia. La
cuenta, que siempre es del código. `data/clientes/`. La sonda. El cierre. Lo
apagado en `archivo/apagado_11sep/`, que no se reenchufa.

Y no se crea nada nuevo sin mirar antes si ya está en el repo. El inventario,
los campos filtrables y los temas ya existían: el mapa es en su mayor parte
pegar tres cosas que están.
