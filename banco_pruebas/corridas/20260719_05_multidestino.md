# Corrida 05_multidestino — 2026-07-19 12:10

Entorno: sim_firestore (880 productos, 50 FAQ), camino vivo por process_message, pausa 25.0s.

## Turno 1

CLIENTE: hola, quiero dos mouse genius dx-110 negro

BOT (5288 ms):

```
¡Hola! Soy el asistente automático de Verifika. Te ayudo con precios, stock y envíos al instante.

Listo, tomamos tu pedido.
Resumen:
Presupuesto:
- 2x Mouse Genius DX-110 Negro: $8.500 c/u = $17.000
Subtotal: $17.000
Envio: $9.000
Total: $26.000
El equipo te contacta para coordinar. Gracias por tu compra.
```

- JUEZ: limpio
- RADAR `guia_pedido_no_reconcilia` [warning] trace_id='cdffb373', pedido=[{'producto': 'mouse genius dx-110 negro', 'cantidad': 2, 'destino': None}], vistos=[], tienda_id='verifika_prod'
- RADAR `interprete_libre_presupuesto_sin_marcador` [warning] trace_id='cdffb373', tienda_id='verifika_prod'

## Turno 2

CLIENTE: uno va a cordoba capital y el otro a mendoza capital, cuanto sale cada envio?

BOT (6218 ms):

```
¡Hola! Qué bueno que quieras avanzar con tus mouse Genius, te cuento cómo queda el tema de los envíos para cada destino.

El envío a cordoba sale $7.500. Superando los $250.000 va gratis. Orientativo, puede variar al confirmar.

El envío a mendoza sale $9.000. Superando los $250.000 va gratis. Orientativo, puede variar al confirmar.

¿Querés que avancemos con alguno? Te armo el total al instante.

Presupuesto:
- 2x Mouse Genius DX-110 Negro: $8.500 c/u = $17.000
Subtotal: $17.000
Envio: $7.500
Total: $24.500

¿Seguimos adelante con tu pedido así te lo dejo preparado?
```

- JUEZ: limpio
- RADAR `guia_pedido_no_reconcilia` [warning] trace_id='7b88f89b', pedido=[{'producto': 'Mouse Genius DX-110 Negro', 'cantidad': 1, 'destino': 'Cordoba capital'}, {'producto': 'Mouse Genius DX-110 Negro', 'cantidad': 1, 'destino': 'Mendoza capital'}], vistos=['Mouse Genius DX-110 Negro'], tienda_id='verifika_prod'
- RADAR `interprete_libre_presupuesto_sin_marcador` [warning] trace_id='7b88f89b', tienda_id='verifika_prod'

## Turno 3

CLIENTE: y el total de todo?

BOT (4919 ms):

```
¡Dale, te paso el total de todo así ya tenés el panorama completo de tu compra!

Presupuesto:
- 2x Mouse Genius DX-110 Negro: $8.500 c/u = $17.000
Subtotal: $17.000
Envio (2 envios): $16.500
Total: $33.500

¿Lo dejamos confirmado? Decime la forma de pago: transferencia (10% de descuento) o Mercado Pago.
```

- JUEZ: limpio
- RADAR `interpretador_destino_fantasma` [warning] destinos=['cordoba capital', 'mendoza capital'], trace_id='e19372ef', tienda_id='verifika_prod'
- RADAR `guia_pedido_no_reconcilia` [warning] trace_id='e19372ef', pedido=[{'producto': 'Mouse Genius DX-110 Negro', 'cantidad': 1, 'destino': None}, {'producto': 'Mouse Genius DX-110 Negro', 'cantidad': 1, 'destino': None}], vistos=['Mouse Genius DX-110 Negro'], tienda_id='verifika_prod'
- RADAR `interprete_libre_presupuesto_sin_marcador` [warning] trace_id='e19372ef', tienda_id='verifika_prod'

## Resumen

- Juez: tanda limpia
- Radares de la corrida:
  - `guia_pedido_no_reconcilia`: 3
  - `interprete_libre_presupuesto_sin_marcador`: 3
  - `interpretador_destino_fantasma`: 1
