# Inventario de la fuente de verdad — verifika_prod

Productos en el repo: **880** | categorias: **22** | specs preguntables: **25**

## 1. Campos del producto: lo que el codigo lee vs lo que la fuente da

| campo | lo usa | en el CSV | en Firestore |
|---|---|---|---|
| nombre | ficha, universo, cita | 880/880 | - |
| categoria | enum del universo | 880/880 | - |
| precio_ars | presupuesto, calculadora | 880/880 | - |
| stock | guardia de stock | 778/880 | - |
| descripcion | ficha | 880/880 | - |
| origen | ficha: procedencia | 880/880 | - |
| garantia_detalle | ficha: garantia | 880/880 | - |
| garantia_meses | verificador | 880/880 | - |
| material | ficha | 880/880 | - |
| peso_gramos | ficha: medidas | 880/880 | - |
| dimensiones | ficha: medidas | 880/880 | - |
| contenido_caja | ficha: que trae | 880/880 | - |
| uso_recomendado | ficha: uso | 880/880 | - |
| caracteristicas_extra | ficha: specs | 852/880 | - |
| marca | buscador | 880/880 | - |
| modelo | certificador de modelo puntual | 880/880 | - |
| color | buscador, variantes | 861/880 | - |
| tags | buscador: sinonimos | 880/880 | - |
| descripcion_rica | buscador: score | 880/880 | - |

## 2. Specs preguntables: que puede contestar la fuente

Cada celda = productos de esa categoria con el dato / productos donde la spec aplica. Un `-` es que la spec no aplica a esa categoria. Donde dice 0 el bot contesta el honesto 'la ficha no lo especifica': no es un bug, es el hueco de datos a llenar en la fuente.

| spec | almacenamiento externo | auriculares | cargador | cooler | fuente | gabinete | impresora | memoria ram | microfono | monitor | motherboard | mouse | notebook | parlante | placa de video | procesador | router | silla gamer | ssd | tablet | teclado | webcam | total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hz | - | - | - | - | - | - | - | - | - | 24/24 | - | - | 171/171 | - | - | - | - | - | - | 27/27 | - | - | 222/222 |
| thunderbolt | - | - | - | - | - | - | - | - | - | 24/24 | 15/15 | - | 171/171 | - | - | - | - | - | - | - | - | - | 210/210 |
| ram_ampliable | - | - | - | - | - | - | - | - | - | - | 15/15 | - | 171/171 | - | - | - | - | - | - | - | - | - | 186/186 |
| puertos | - | - | - | - | - | 30/30 | 22/22 | - | - | 24/24 | 15/15 | - | 171/171 | - | - | - | 22/22 | - | - | 27/27 | - | - | 311/311 |
| bateria | - | 46/46 | - | - | - | - | - | - | 24/24 | - | - | 52/52 | 171/171 | 36/36 | - | - | - | - | - | 27/27 | 48/48 | - | 404/404 |
| retroiluminacion | - | - | - | - | - | 30/30 | - | - | - | - | - | 52/52 | 171/171 | 36/36 | - | - | - | 39/39 | - | - | 48/48 | - | 376/376 |
| lector_huella | - | - | - | - | - | - | - | - | - | - | - | - | 171/171 | - | - | - | - | - | - | 27/27 | - | - | 198/198 |
| bluetooth | - | 46/46 | - | - | - | - | 22/22 | - | 24/24 | - | - | 52/52 | 171/171 | 36/36 | - | - | - | - | - | 27/27 | 48/48 | 10/10 | 436/436 |
| wifi | - | - | - | - | - | - | 22/22 | - | - | - | - | - | 171/171 | 36/36 | - | - | 22/22 | - | - | 27/27 | - | 10/10 | 288/288 |
| camara | - | - | - | - | - | - | - | - | 24/24 | - | - | - | 171/171 | - | - | - | - | - | - | 27/27 | - | 10/10 | 232/232 |
| tactil | - | - | - | - | - | - | 22/22 | - | - | 24/24 | - | - | 171/171 | - | - | - | - | - | - | 27/27 | - | - | 244/244 |
| lector_tarjetas | - | - | - | - | - | - | 22/22 | - | - | - | - | - | 171/171 | - | - | - | - | - | - | 27/27 | - | 10/10 | 230/230 |
| resistencia_agua | - | 46/46 | - | - | - | - | - | - | - | - | - | 52/52 | - | 36/36 | - | - | - | - | - | - | 48/48 | - | 182/182 |
| ram | - | - | - | - | - | - | - | 96/96 | - | - | 15/15 | - | 171/171 | - | - | - | - | - | - | 27/27 | - | - | 309/309 |
| almacenamiento | 72/72 | - | - | - | - | - | - | - | - | - | - | - | 171/171 | - | - | - | - | - | 60/60 | 27/27 | - | - | 330/330 |
| garantia | 72/72 | 46/46 | 20/20 | 14/14 | 15/15 | 30/30 | 22/22 | 96/96 | 24/24 | 24/24 | 15/15 | 52/52 | 171/171 | 36/36 | 18/18 | 19/19 | 22/22 | 39/39 | 60/60 | 27/27 | 48/48 | 10/10 | 880/880 |
| procesador | - | - | - | - | - | - | - | - | - | - | 15/15 | - | 171/171 | - | - | 19/19 | - | - | - | 27/27 | - | - | 232/232 |
| resolucion | - | - | - | - | - | - | - | - | - | 24/24 | - | - | 171/171 | - | - | - | - | - | - | 27/27 | - | 10/10 | 232/232 |
| panel | - | - | - | - | - | - | - | - | - | 24/24 | - | - | 171/171 | - | - | - | - | - | - | 27/27 | - | - | 222/222 |
| conexion | - | 46/46 | - | - | - | - | 22/22 | - | 24/24 | - | - | 52/52 | - | 36/36 | - | - | - | - | - | - | 48/48 | 10/10 | 238/238 |
| switch_teclado | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | 48/48 | - | 48/48 |
| sensor | - | - | - | - | - | - | - | - | - | - | - | 52/52 | - | - | - | - | - | - | - | - | - | - | 52/52 |
| potencia | - | - | 20/20 | 14/14 | 15/15 | - | - | - | - | - | - | - | - | 36/36 | - | - | - | - | - | - | - | - | 85/85 |
| memoria_video | - | - | - | - | - | - | - | - | - | - | - | - | - | - | 18/18 | - | - | - | - | - | - | - | 18/18 |
| formato | - | - | - | - | 15/15 | 30/30 | - | - | - | - | 15/15 | - | - | - | - | - | - | - | - | - | - | - | 60/60 |

## 3. El resto de la fuente

- FAQ: **50** temas
- Base de conocimiento: **106** categorias de criterio
- Movidas de venta escritas: **32**
- Mensajes fijos al cliente: **54**
- Identidad del vendedor en la fuente: **si**
- Categorias no vendidas: **29**
- Specs preguntables: **25**

## 3-bis. Cobertura: que fuente contesta cada cosa

Generado de `base_conocimiento.json`. El `pilar` dice de donde sale la respuesta: `criterio` la razona el modelo desde la prosa de la casa, `politica` sale de la FAQ por `consultar_temas`, `dato` lo estampa una herramienta, `conversacion` y `seguridad` son la conduccion.

| grupo | pilar | categorias | con criterio | con movida | con FAQ propia |
|---|---|---|---|---|---|
| asesoramiento | criterio | 6 | 5 | 3 | 0 |
| casos_borde | conversacion, criterio, dato | 4 | 2 | 2 | 0 |
| comparacion_compatibilidad | criterio, dato | 4 | 3 | 2 | 1 |
| conversacion | conversacion | 19 | 14 | 7 | 1 |
| criterio_producto | criterio | 28 | 28 | 0 | 0 |
| identidad_dato | criterio, dato | 3 | 2 | 3 | 0 |
| objeciones | criterio, politica | 4 | 4 | 4 | 0 |
| politica_faq | dato, politica | 27 | 26 | 6 | 23 |
| postventa | conversacion, criterio, dato, politica | 6 | 5 | 4 | 2 |
| seguridad | seguridad | 5 | 4 | 1 | 0 |

**Cero categorias sin nada escrito:** toda categoria tiene criterio, movida o su tema de FAQ.

Temas de FAQ sin categoria espejo: **23**. NO es un hueco: el modelo los pide por nombre en el enum de `consultar_temas`. La vieja regla de oro que exigia el espejo era del interprete atado, que se borro el 2-ago.

## 4. Calidad del dato: spec fantasma depurada

Fichas del CSV que traian una spec de OTRO producto pegada: **427/880**. La ingesta las depura dejando la spec avalada por el nombre del propio producto.

