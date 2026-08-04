# Inventario de la fuente de verdad — verifika_prod

Productos en el repo: **880** | categorias: **22** | specs preguntables: **24**

## 1. Campos del producto: lo que el codigo lee vs lo que la fuente da

Firestore vivo: **880** productos.

| campo | lo usa | en el CSV | en Firestore |
|---|---|---|---|
| nombre | ficha, universo, cita | 880/880 | 880/880 |
| categoria | enum del universo | 880/880 | 880/880 |
| precio_ars | presupuesto, calculadora | 880/880 | 880/880 |
| stock | guardia de stock | 778/880 | 880/880 |
| descripcion | ficha | 880/880 | 880/880 |
| origen | ficha: procedencia | 880/880 | 880/880 |
| garantia_detalle | ficha: garantia | 880/880 | 880/880 |
| garantia_meses | verificador | 880/880 | 880/880 |
| material | ficha | 880/880 | 880/880 |
| peso_gramos | ficha: medidas | 880/880 | 880/880 |
| dimensiones | ficha: medidas | 880/880 | 880/880 |
| contenido_caja | ficha: que trae | 880/880 | 880/880 |
| uso_recomendado | ficha: uso | 880/880 | 880/880 |
| caracteristicas_extra | ficha: specs | 880/880 | 880/880 |
| marca | buscador | 880/880 | 880/880 |
| modelo | certificador de modelo puntual | 880/880 | 880/880 |
| color | buscador, variantes | 861/880 | 880/880 |
| tags | buscador: sinonimos | 880/880 | 880/880 |
| descripcion_rica | buscador: score | 880/880 | 880/880 |

## 2. Specs preguntables: que puede contestar la fuente

Cada celda = productos de esa categoria con el dato / productos donde la spec aplica. Un `-` es que la spec no aplica a esa categoria. Donde dice 0 el bot contesta el honesto 'la ficha no lo especifica': no es un bug, es el hueco de datos a llenar en la fuente.

| spec | almacenamiento externo | auriculares | cargador | cooler | fuente | gabinete | impresora | memoria ram | microfono | monitor | motherboard | mouse | notebook | parlante | placa de video | procesador | router | silla gamer | ssd | tablet | teclado | webcam | total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hz | - | - | - | - | - | - | - | - | - | 24/24 | - | - | **0**/171 | - | - | - | - | - | - | **0**/27 | - | - | 24/222 |
| thunderbolt | - | - | - | - | - | - | - | - | - | **0**/24 | **0**/15 | - | **0**/171 | - | - | - | - | - | - | - | - | - | 0/210 |
| ram_ampliable | - | - | - | - | - | - | - | - | - | - | **0**/15 | - | **0**/171 | - | - | - | - | - | - | - | - | - | 0/186 |
| puertos | - | - | - | - | - | **0**/30 | 22/22 | - | - | **0**/24 | **0**/15 | - | **0**/171 | - | - | - | **0**/22 | - | - | **0**/27 | - | - | 22/311 |
| bateria | - | **0**/46 | - | - | - | - | - | - | **0**/24 | - | - | **0**/52 | **0**/171 | **0**/36 | - | - | - | - | - | **0**/27 | **0**/48 | - | 0/404 |
| retroiluminacion | - | - | - | - | - | **0**/30 | - | - | - | - | - | **0**/52 | **0**/171 | **0**/36 | - | - | - | **0**/39 | - | - | 6/48 | - | 6/376 |
| lector_huella | - | - | - | - | - | - | - | - | - | - | - | - | **0**/171 | - | - | - | - | - | - | **0**/27 | - | - | 0/198 |
| bluetooth | - | **0**/46 | - | - | - | - | **0**/22 | - | **0**/24 | - | - | **0**/52 | **0**/171 | 3/36 | - | - | - | - | - | **0**/27 | **0**/48 | **0**/10 | 3/436 |
| wifi | - | - | - | - | - | - | **0**/22 | - | - | - | - | - | **0**/171 | **0**/36 | - | - | 22/22 | - | - | **0**/27 | - | **0**/10 | 22/288 |
| camara | - | - | - | - | - | - | - | - | **0**/24 | - | - | - | **0**/171 | - | - | - | - | - | - | **0**/27 | - | 10/10 | 10/232 |
| tactil | - | - | - | - | - | - | **0**/22 | - | - | **0**/24 | - | - | **0**/171 | - | - | - | - | - | - | **0**/27 | - | - | 0/244 |
| lector_tarjetas | - | - | - | - | - | - | **0**/22 | - | - | - | - | - | **0**/171 | - | - | - | - | - | - | **0**/27 | - | **0**/10 | 0/230 |
| resistencia_agua | - | **0**/46 | - | - | - | - | - | - | - | - | - | **0**/52 | - | **0**/36 | - | - | - | - | - | - | **0**/48 | - | 0/182 |
| ram | - | - | - | - | - | - | - | 96/96 | - | - | **0**/15 | - | 171/171 | - | - | - | - | - | - | **0**/27 | - | - | 267/309 |
| almacenamiento | 72/72 | - | - | - | - | - | - | - | - | - | - | - | 171/171 | - | - | - | - | - | 60/60 | 27/27 | - | - | 330/330 |
| procesador | - | - | - | - | - | - | - | - | - | - | **0**/15 | - | 171/171 | - | - | 19/19 | - | - | - | **0**/27 | - | - | 190/232 |
| resolucion | - | - | - | - | - | - | - | - | - | 24/24 | - | - | **0**/171 | - | - | - | - | - | - | **0**/27 | - | 10/10 | 34/232 |
| panel | - | - | - | - | - | - | - | - | - | 24/24 | - | - | 9/171 | - | - | - | - | - | - | **0**/27 | - | - | 33/222 |
| conexion | - | 46/46 | - | - | - | - | **0**/22 | - | 24/24 | - | - | 2/52 | - | **0**/36 | - | - | - | - | - | - | **0**/48 | **0**/10 | 72/238 |
| switch_teclado | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - | 48/48 | - | 48/48 |
| sensor | - | - | - | - | - | - | - | - | - | - | - | 52/52 | - | - | - | - | - | - | - | - | - | - | 52/52 |
| potencia | - | - | 18/20 | **0**/14 | 15/15 | - | - | - | - | - | - | - | - | **0**/36 | - | - | - | - | - | - | - | - | 33/85 |
| memoria_video | - | - | - | - | - | - | - | - | - | - | - | - | - | - | 18/18 | - | - | - | - | - | - | - | 18/18 |
| formato | - | - | - | - | **0**/15 | 30/30 | - | - | - | - | 15/15 | - | - | - | - | - | - | - | - | - | - | - | 45/60 |

**Specs que la fuente NO responde en ningun producto** (el bot es honesto y no vende con ellas; llenarlas es dato del proveedor, no codigo):
- `thunderbolt` (el puerto Thunderbolt) — aplicaria a 210 productos
- `ram_ampliable` (si la RAM se puede ampliar) — aplicaria a 186 productos
- `bateria` (la autonomia de bateria) — aplicaria a 404 productos
- `lector_huella` (el lector de huella) — aplicaria a 198 productos
- `tactil` (si la pantalla es tactil) — aplicaria a 244 productos
- `lector_tarjetas` (el lector de tarjetas) — aplicaria a 230 productos
- `resistencia_agua` (la resistencia al agua) — aplicaria a 182 productos

## 3. El resto de la fuente

- FAQ: **50** temas
- Base de conocimiento: **106** categorias de criterio
- Movidas de venta escritas: **32**
- Mensajes fijos al cliente: **6**
- Identidad del vendedor en la fuente: **si**
- Categorias no vendidas: **29**
- Specs preguntables: **24**

La prosa se unifico el 3-ago: la identidad del vendedor, las movidas de venta y
los mensajes fijos al cliente vivian en markdowns y en constantes de Python, y
ahora estan todas en `base_conocimiento.json`, la misma fuente que el criterio.

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

Fichas del CSV que traian una spec de OTRO producto pegada: **399/880**. La ingesta las depura dejando la spec avalada por el nombre del propio producto.

