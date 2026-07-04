# BORRADORES de respuestas curadas de FAQ — PENDIENTE DE APROBACION de Martin

Estado: BORRADOR. Nada de esto esta cargado en `faq.json` ni en Firestore.
Son los 41 temas que faltan (los 3 ya aprobados, cuotas / costo_envio /
descuento_transferencia, no se tocan). Redactados en la voz de las 3 curadas
existentes: espanol argentino, tuteo, sin acentos (como todo el faq.json),
corto, con gancho de venta al final, y TODO numero que puede cambiar va como
hueco `{{concepto}}` estampado desde los `valores` estructurados del MISMO tema.

Reglas que respetan los borradores:
- Ningun numero de politica hardcodeado si puede vivir en un valor (una sola
  fuente). Donde el tema no tenia valores, se proponen abajo del texto.
- Los valores nuevos se agregan SIN cambiar el `tipo` del tema (quedan
  informativos), asi la calculadora NO los ofrece como extras del total.
- Ningun texto promete dia exacto de entrega, retiro en local ni servicio
  fuera de FAQ (clases prohibidas de guardia_promesas).
- Cuando un numero pertenece a OTRO tema (ej el % de transferencia), el texto
  lo insinua sin decirlo, para no duplicar la fuente.

Como aprobar: marcar OK o corregir el texto de cada tema. Con el OK se aplican
a `faq.json` (texto + valores nuevos) y se re-sube la FAQ por
`/admin/upload-faq`, lo que ademas ACTIVA las 3 curadas ya deployadas.

---

## 1. ubicacion
Somos una tienda 100 por ciento online, sin local fisico, y despachamos desde
Buenos Aires a todo el pais. Vos elegis desde tu casa y te lo mandamos. Que
estas buscando?

## 2. horarios
Te atendemos de lunes a viernes de 9 a 18 hs y los sabados de 10 a 13 hs, por
WhatsApp y mail. Igual dejame tu consulta ahora y la vamos resolviendo. En que
te puedo ayudar?

## 3. formas_pago
Aceptamos transferencia bancaria, Mercado Pago y tarjetas Visa, Mastercard y
American Express, credito o debito. Con transferencia ademas tenes descuento.
Contame que producto te interesa y te paso el total con cada forma de pago.

## 4. envios
Si, llegamos a todo el pais por Andreani y OCA. Pasame tu provincia o codigo
postal y te digo la tarifa exacta y el plazo. A donde te lo mandariamos?

## 5. plazo_envio
Una vez acreditado el pago, a CABA y GBA llega en {{dias_caba_min}} a
{{dias_caba_max}} dias habiles, y al interior en {{dias_interior_min}} a
{{dias_interior_max}} dias habiles. Decime tu zona y te confirmo tambien el
costo del envio.
VALORES A AGREGAR: dias_caba_min=2, dias_caba_max=3, dias_interior_min=4,
dias_interior_max=7 (unidad dias).

## 6. garantia
Todos nuestros productos son originales y tienen garantia oficial del
fabricante, minimo {{garantia_minima_meses}} meses. El plazo exacto figura en
cada producto: decime cual te interesa y te lo confirmo.
VALORES A AGREGAR: garantia_minima_meses=6 (unidad meses).

## 7. devoluciones
Tenes {{dias_devolucion}} dias corridos desde que lo recibis para arrepentirte,
con el producto sin uso y en su empaque original. Compras tranquilo. Queres que
te ayude a elegir?
VALORES A AGREGAR: dias_devolucion=10 (unidad dias).

## 8. factura
Si, emitimos factura A o B segun corresponda, y todos los precios ya incluyen
IVA. Si necesitas factura A, pasame tu CUIT al momento de comprar y listo.

## 9. redes
Nos encontras en Instagram como arroba verifikademo y en verifikademo.com.ar.
Pero aca por chat te atiendo directo: decime que buscas y lo vemos ahora.

## 10. contacto_humano
Si, te puedo derivar con una persona del equipo. Contame brevemente tu consulta
asi la paso con todo el contexto y te contactan a la brevedad.

## 11. asesoramiento
Claro, para eso estoy. Contame que necesitas, para que lo vas a usar y tu
presupuesto aproximado, y te recomiendo las mejores opciones del catalogo.

## 12. reservas
Si esta sin stock lo podemos reservar con una sena del {{sena_reserva}}. El
plazo de reposicion depende del producto y el proveedor. Decime cual te
interesa y te confirmo si conviene reservarlo.
VALORES: usa sena_reserva que YA existe en el tema.

## 13. marcas_originales
Todas las marcas que vendemos son originales, con garantia oficial del
fabricante. Nada generico ni replica. Que producto estas mirando?

## 14. usados
Vendemos unicamente productos nuevos, en su caja original sellada. No
trabajamos usados ni reacondicionados. Te paso opciones nuevas de lo que buscas?

## 15. precios_iva
Los precios publicados son finales: ya incluyen IVA, sin sorpresas al pagar.
Decime que producto estas mirando y te paso el total con envio incluido.

## 16. defectuoso
Quedate tranquilo: si llega defectuoso lo cambiamos sin costo, avisandonos
dentro de los {{dias_cambio_defectuoso}} dias de recibido. Ademas todo tiene
garantia oficial del fabricante.
VALORES A AGREGAR: dias_cambio_defectuoso=7 (unidad dias).

## 17. envio_urgente
En CABA y GBA tenemos envio express con entrega en {{horas_express}} horas
habiles, con un costo extra. Decime tu zona y que necesitas, y te lo cotizo.
VALORES A AGREGAR: horas_express=24 (unidad horas).

## 18. mayoristas
Si, para compras por cantidad o reventa tenemos precios especiales. Contame que
productos y que cantidades pensas comprar y te armo una cotizacion mayorista.

## 19. formas_contacto
Nos podes escribir por WhatsApp o mail, y la atencion humana es de lunes a
viernes de 9 a 18 hs. Igual decime tu consulta ahora y la resolvemos aca mismo.

## 20. envoltorio_regalo
No tenemos envoltorio de regalo, pero el producto viaja en su caja original
sellada, prolijo para regalar. Si es un regalo, avisame y pido que vaya sin el
remito con el precio a la vista.

## 21. contenido_caja
Cada producto viene en su caja original sellada con el equipo y los accesorios
estandar del fabricante. El detalle exacto figura en la ficha. De que producto
queres que te lo confirme?

## 22. origen_procedencia
Trabajamos productos importados y nacionales segun la marca y el modelo; la
procedencia figura en la ficha de cada uno. Decime cual te interesa y te la
confirmo, no te la invento.

## 23. material_composicion
El material y la composicion dependen del modelo y estan en las
especificaciones de la ficha. Decime que producto miras y que dato necesitas y
te lo confirmo antes de que compres.

## 24. fabricacion
El pais de fabricacion varia segun la marca y figura en la ficha o en la caja
cuando el fabricante lo informa. Pasame el modelo puntual y lo verifico antes
de tu compra.

## 25. especificaciones
Las especificaciones completas estan en la ficha de cada producto. Decime el
modelo y el dato que te importa y te paso lo publicado; si algo no figura, lo
confirmo antes de que compres.

## 26. compatibilidad
Te lo chequeo con gusto. Decime que producto estas mirando y con que lo queres
usar, y lo verifico contra la ficha. Si ahi no lo aclara, lo confirmo antes de
que compres; no te arriesgo un si sin estar seguro.

## 27. garantia_como_usar
Si falla dentro de la garantia, escribinos con tu numero de pedido y una
descripcion de la falla, y coordinamos el service oficial o el cambio segun
corresponda, sin costo de gestion. El plazo de tu producto figura en su ficha.

## 28. stock_disponibilidad
La disponibilidad te la confirmo al instante contra el catalogo real. Decime
que producto buscas y te digo si hay stock; si esta agotado, lo podemos
reservar con una sena.

## 29. embalaje_envio
Va embalado reforzado y asegurado durante todo el envio. Si llegara danado por
el traslado, lo cambiamos sin costo avisandonos dentro de los
{{dias_aviso_dano}} dias de recibido.
VALORES A AGREGAR: dias_aviso_dano=7 (unidad dias).

## 30. retiro_local
Somos tienda online, sin punto de retiro: todo va por envio a la direccion que
nos digas, a todo el pais. Pasame tu zona y te cotizo el envio en el momento.

## 31. reembolso
Si corresponde reembolso por una devolucion aceptada, te reintegramos por el
mismo medio con el que pagaste. Apenas recibimos el producto gestionamos el
reintegro; el plazo final depende del banco o la tarjeta.

## 32. seguimiento_pedido
Cuando despachamos te mandamos el numero de seguimiento de Andreani u OCA para
rastrearlo online. Si no te llego, pasame tu numero de pedido y te lo reenvio.

## 33. cancelacion_pedido
Podes cancelar sin costo mientras el pedido no haya salido. Escribinos cuanto
antes con tu numero de pedido; si ya se despacho, lo gestionamos como
devolucion.

## 34. envio_exterior
Por ahora enviamos solo dentro de Argentina, no despachamos al exterior. Si
tenes una direccion en el pais, te lo mandamos ahi sin problema.

## 35. confianza_seguridad
Es una compra segura: los pagos van por Mercado Pago o medios bancarios
oficiales, no manejamos los datos de tu tarjeta, y todas las marcas son
originales con garantia oficial. Ademas te acompano por este canal en todo el
proceso.

## 36. como_comprar
Es simple: decime que producto te interesa y te paso precio y formas de pago.
Pagas por transferencia o Mercado Pago y, acreditado el pago, despachamos a tu
direccion. Te guio paso a paso. Arrancamos?

## 37. pago_contra_entrega
No trabajamos contra entrega: el pedido se abona antes del despacho, por
transferencia o Mercado Pago. Apenas se acredita, sale el envio. Con
transferencia ademas tenes descuento.

## 38. monedas_aceptadas
Operamos solo en pesos argentinos, por transferencia o Mercado Pago. No tomamos
dolares en efectivo ni criptomonedas. Te paso el total en pesos de lo que estes
mirando?

## 39. datos_fiscales
Emitimos factura A o B segun corresponda; los datos fiscales te los pasamos al
facturar tu compra. Si necesitas factura A, dejame tu CUIT y tu condicion
frente al IVA.

## 40. cambios
Si, tenes {{dias_cambio}} dias corridos desde que lo recibis para cambiarlo por
otro modelo, sin uso y en su empaque original. Si hay diferencia de precio la
ajustamos. Pasame tu numero de pedido y lo coordinamos.
VALORES A AGREGAR: dias_cambio=10 (unidad dias).

## 41. promociones
Hoy tenes descuento pagando por transferencia y cuotas sin interes con tarjeta.
Las promos puntuales por producto te las confirmo segun lo que mires. Contame
que buscas y te digo si tiene algo especial.

---

Resumen de valores estructurados NUEVOS propuestos (7 temas): plazo_envio (4),
garantia (1), devoluciones (1), defectuoso (1), envio_urgente (1),
embalaje_envio (1), cambios (1). Los numeros salen de la prosa actual del
mismo faq.json; no se invento ninguno. El resto de los temas no tiene numeros
que puedan cambiar, van texto puro.
