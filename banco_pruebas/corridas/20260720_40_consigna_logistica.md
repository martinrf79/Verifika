# Corrida 40_consigna_logistica — 2026-07-20 11:18

Entorno: sim_firestore (880 productos, 50 FAQ), camino vivo por process_message, pausa 25.0s.

## Turno 1

CLIENTE: Hola, ¿tienen disponibilidad del monitor Samsung Odyssey G5 de 27 pulgadas?

BOT (4198 ms):

```
¡Hola! Soy el asistente automático de Verifika. Te ayudo con precios, stock y envíos al instante.

¡Sí! De eso tengo en catálogo, con precio y stock reales:

- Monitor Samsung Odyssey G5 32 - $480.000 (18 en stock)

¿Te paso el total o querés la ficha completa?
```

- JUEZ: limpio

## Turno 2

CLIENTE: Genial. Si lo pago ahora mismo, ¿cuándo me llega a Villa María?

BOT (8560 ms):

```
Si buscás jugar, este monitor es una opción recomendada por su uso gaming. El envío a cordoba sale $7.500. Superando los $250.000 va gratis. Orientativo, puede variar al confirmar. Presupuesto: - 1x Monitor Samsung Odyssey G5 32: $480.000 c/u = $480.000 Subtotal: $480.000 Envio: gratis Total: $480.000 ¿Lo dejamos confirmado? Decime la forma de pago: transferencia (10% de descuento) o Mercado Pago. No trabajamos contra entrega: el pedido se abona antes del despacho, por transferencia o Mercado Pago. Apenas se acredita, sale el envio. Con transferencia ademas tenes descuento.
```

- JUEZ: limpio
- RADAR `interprete_libre_presupuesto_sin_marcador` [warning] trace_id='3ce56258', tienda_id='verifika_prod'

## Turno 3

CLIENTE: Perfecto. ¿Me lo mandan por correo privado? Otra consulta: si me equivoco en la altura de la calle, ¿puedo cambiar la dirección de entrega después de pagar?

BOT (6648 ms):

```
¡Hola! Qué bueno que te decidas.

Si, la direccion se puede corregir sin problema siempre que nos avises ANTES de que el pedido salga del deposito. Escribinos apenas lo notes con tu numero de pedido y la direccion correcta. Si ya se despacho, lo gestionamos con el correo, aunque en ese caso no siempre se llega a cambiar.

¿Querés que avancemos con alguno? Te armo el total al instante.
```

- JUEZ: limpio

## Turno 4

CLIENTE: Entendido, me aseguro de ponerla bien entonces. ¿Me pasan algún número de seguimiento apenas salga a la ruta?

BOT (10033 ms):

```
¡Claro que sí! Quédate tranquilo que apenas despachamos tu pedido, te enviamos el número de seguimiento para que puedas ir viendo cómo avanza el viaje hasta Villa María.

Cuando despachamos te mandamos el numero de seguimiento de Andreani u OCA para rastrearlo online. Si no te llego, pasame tu numero de pedido y te lo reenvio.

¿Alguno te interesa? Decime y te paso el total en el momento.
```

- JUEZ: limpio
- RADAR `checker_afirmaciones_error` [warning] trace_id='22072d49', error='', tienda_id='verifika_prod'

## Resumen

- Juez: tanda limpia
- Radares de la corrida:
  - `interprete_libre_presupuesto_sin_marcador`: 1
  - `checker_afirmaciones_error`: 1
