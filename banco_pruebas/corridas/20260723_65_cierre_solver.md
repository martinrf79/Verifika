# Corrida 65_cierre_solver — 2026-07-23 00:50

Entorno: sim_firestore (880 productos, 50 FAQ), camino vivo por process_message, pausa 6.0s.

## Turno 1

CLIENTE: hola quiero dos mouse genius dx-110

BOT (7877 ms):

```
¡Hola! Soy el asistente automático de Verifika. Te ayudo con precios, stock y envíos al instante.

Qué bueno que te comuniques, te ayudo enseguida con esos mouse para que los tengas cuanto antes.

Presupuesto:
- 2x Mouse Genius DX-110 Negro: $8.500 c/u = $17.000
Subtotal: $17.000
Total: $17.000

Pago dividido:
- transferencia (100%): $17.000 - 10% descuento = $15.300
Total final: $15.300

¿Cómo lo ves? Cualquier ajuste de modelos, cantidades o destinos me decís y lo dejamos a tu medida.
```

- JUEZ: limpio
- RADAR `guia_pedido_no_reconcilia` [warning] trace_id='b9c3da5d', pedido=[{'producto': 'mouse genius dx-110', 'cantidad': 2, 'destino': None}], vistos=[], tienda_id='verifika_prod'
- RADAR `generador_v2_destino_fantasma` [warning] trace_id='b9c3da5d', destinos=['Argentina'], tienda_id='verifika_prod'
- RADAR `interprete_libre_presupuesto_sin_marcador` [warning] trace_id='b9c3da5d', tienda_id='verifika_prod'
- RADAR `interprete_libre_faq_numerica_sin_respaldo` [warning] trace_id='b9c3da5d', sin_respaldo=[{'clase': 'porcentaje', 'n': 0}], respuesta_preview='¡Hola! Qué bueno que te comuniques, te ayudo enseguida con esos mouse para que los tengas cuanto antes.\n\nPresupuesto:\n- 2x Mouse Genius DX-110 Negro: $8.500 c/u = $17.000\nSubtotal: $17.000\nTotal: $17.', tienda_id='verifika_prod'

## Turno 2

CLIENTE: dale lo llevo, pago por transferencia

BOT (7392 ms):

```
Listo, tomamos tu pedido.
Resumen:
Presupuesto:
- 2x Mouse Genius DX-110 Negro: $8.500 c/u = $17.000
Subtotal: $17.000
Total: $17.000

Pago dividido:
- transferencia (100%): $17.000 - 10% descuento = $15.300
Total final: $15.300
El equipo te contacta para coordinar el pago por transferencia. Gracias por tu compra.
```

- JUEZ: limpio
- RADAR `interprete_libre_presupuesto_sin_marcador` [warning] trace_id='ab83d305', tienda_id='verifika_prod'
- RADAR `interprete_libre_faq_numerica_sin_respaldo` [warning] trace_id='ab83d305', sin_respaldo=[{'clase': 'porcentaje', 'n': 0}], respuesta_preview='¡Excelente elección! Son unos clásicos que no fallan para el día a día, te van a venir bárbaro.\n\nHaciendo la transferencia te ahorrás un buen porcentaje, es la mejor forma de aprovechar el precio fina', tienda_id='verifika_prod'

## Resumen

- Juez: tanda limpia
- Radares de la corrida:
  - `interprete_libre_presupuesto_sin_marcador`: 2
  - `interprete_libre_faq_numerica_sin_respaldo`: 2
  - `guia_pedido_no_reconcilia`: 1
  - `generador_v2_destino_fantasma`: 1
