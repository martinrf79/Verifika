# Corrida 05_multidestino — 2026-07-19 12:22

Entorno: sim_firestore (880 productos, 50 FAQ), camino vivo por process_message, pausa 25.0s.

## Turno 1

CLIENTE: hola, quiero dos mouse genius dx-110 negro

BOT (6822 ms):

```
¡Hola! Soy el asistente automático de Verifika. Te ayudo con precios, stock y envíos al instante.

Listo, tomamos tu pedido.
Resumen:
Presupuesto:
- 2x Mouse Genius DX-110 Negro: $8.500 c/u = $17.000
Subtotal: $17.000
Total: $17.000
El equipo te contacta para coordinar. Gracias por tu compra.
```

- JUEZ: limpio
- RADAR `guia_pedido_no_reconcilia` [warning] trace_id='6f5fd609', pedido=[{'producto': 'mouse genius dx-110 negro', 'cantidad': 2, 'destino': None}], vistos=[], tienda_id='verifika_prod'
- RADAR `generador_v2_destino_fantasma` [warning] trace_id='6f5fd609', destinos=['no especificado'], tienda_id='verifika_prod'
- RADAR `interprete_libre_presupuesto_sin_marcador` [warning] trace_id='6f5fd609', tienda_id='verifika_prod'

## Turno 2

CLIENTE: uno va a cordoba capital y el otro a mendoza capital, cuanto sale cada envio?

BOT (6351 ms):

```
¡Hola! Qué bueno que avanzamos. Te cuento que para envíos a distintas provincias, el sistema los calcula por separado según la logística de cada destino.

El envío a cordoba sale $7.500. Superando los $250.000 va gratis. Orientativo, puede variar al confirmar.

El envío a mendoza sale $9.000. Superando los $250.000 va gratis. Orientativo, puede variar al confirmar.

¿Alguno te interesa? Decime y te paso el total en el momento.

Presupuesto:
- 2x Mouse Genius DX-110 Negro: $8.500 c/u = $17.000
Subtotal: $17.000
Envio: $7.500
Total: $24.500

¿Seguimos adelante con tu pedido así te lo dejo preparado?
```

- JUEZ: limpio
- RADAR `guia_pedido_no_reconcilia` [warning] trace_id='3cde2cde', pedido=[{'producto': 'Mouse Genius DX-110 Negro', 'cantidad': 1, 'destino': 'cordoba capital'}, {'producto': 'Mouse Genius DX-110 Negro', 'cantidad': 1, 'destino': 'mendoza capital'}], vistos=['Mouse Genius DX-110 Negro'], tienda_id='verifika_prod'
- RADAR `interprete_libre_presupuesto_sin_marcador` [warning] trace_id='3cde2cde', tienda_id='verifika_prod'

## Turno 3

CLIENTE: y el total de todo?

BOT (5180 ms):

```
¡Dale, te paso el resumen total de los dos envíos y los equipos así ya queda todo listo!

Presupuesto:
- 2x Mouse Genius DX-110 Negro: $8.500 c/u = $17.000
Subtotal: $17.000
Envio (2 envios): $16.500
Total: $33.500

¿Lo dejamos confirmado? Decime la forma de pago: transferencia (10% de descuento) o Mercado Pago.
```

- JUEZ: limpio
- RADAR `interpretador_destino_fantasma` [warning] destinos=['cordoba capital', 'mendoza capital'], tienda_id='verifika_prod', trace_id='76112f61'
- RADAR `guia_pedido_no_reconcilia` [warning] trace_id='76112f61', pedido=[{'producto': 'Mouse Genius DX-110 Negro', 'cantidad': 1, 'destino': None}, {'producto': 'Mouse Genius DX-110 Negro', 'cantidad': 1, 'destino': None}], vistos=['Mouse Genius DX-110 Negro'], tienda_id='verifika_prod'
- RADAR `interprete_libre_presupuesto_sin_marcador` [warning] trace_id='76112f61', tienda_id='verifika_prod'

## Resumen

- Juez: tanda limpia
- Radares de la corrida:
  - `guia_pedido_no_reconcilia`: 3
  - `interprete_libre_presupuesto_sin_marcador`: 3
  - `generador_v2_destino_fantasma`: 1
  - `interpretador_destino_fantasma`: 1
