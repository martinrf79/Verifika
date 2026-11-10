# FICHA 92 — Las capas hasta el camino fijo

10-nov-2026, orden de Martín. Sigue a `arquitectura/PLAN_CAPAS.md`, que tiene lo medido del 9-nov. **La sesión nueva arranca
acá, por el paso 1.** Cada paso con su corte escrito antes en `PLAN_CAPAS.md`; se pushea cada capa que lo pase.

## El orden

Primero lo determinista con lo grabado, sin modelo. Después la clave gratis. Al final WhatsApp.

## Los pasos

1. **El banco cubre las charlas enteras.** `banco_pruebas/capa_buscar.py` mide hoy solo el primer turno. Se extiende a todos
   los turnos de las 58, J y K que tradujeron los modelos en `traduccion58_corridas.jsonl`: los turnos anteriores corren con
   su agenda a mano, `agendas58.py`, y el estado queda en la memoria, hoy `banco_pruebas/camino_grabadas.py` sobre el turno fijo de `banco_pruebas/camino_fijo.py`. La vara: los
   mismos productos que la agenda a mano y, donde hay cuenta, los mismos montos.
2. **Capa por capa, por tipo:** cuenta y plata, envío, política, compatibilidad, otro. Se arregla en la forma normal,
   `normal.py`, o en la receta, `ejecutor.py`. Lo que es intención del cliente va a la consigna de la llamada 1, no al código:
   sin listas de palabras. Una regla entra si arregla y no rompe ningún caso de ningún modelo en ninguna capa.
3. **La llamada 1 al bot, camino fijo.** El turno queda: llamada 1 con la consigna del 21-oct más el párrafo B2,
   `banco_pruebas/llamada1/`; la forma normal; el ejecutor; la respuesta atada de `respuesta.py`, que es la llamada 2.
   Antes, repetir dos veces la corrida de B2 con la gratis. Se mide con la gratis, tres corridas, contra el agente en las
   mismas charlas. Cuando lo supera, reemplaza al bucle de `agente.responder`. Recién ahí, WhatsApp.

## Líneas y funciones

- **El conflicto que se resuelve en el paso 3:** anotar el pedido tiene dos caminos, el del agente —`pedido`,
  `presupuesto`, `omitidos`, `sin_buscar`— y el del ejecutor con el borrador. Queda uno solo, el del ejecutor, que es el que
  mide el banco.
- Al archivar el bucle salen esas herramientas y la consigna del agente. El techo de `app/` puede subir mientras conviven;
  **después del cambio tiene que quedar por debajo de 8776**, que era el del 7-nov.
- Lo demás de funciones y líneas espera. Se toca solo si traba una capa.

## Decidido el 10-nov

- **C32**, "entre el G305 y el G203, el inalámbrico": Martín lo dejó a criterio. Queda como está, `lista_con_dato`: se
  contesta por el que cumple y se ofrece. Es más corto y lleva a la venta.
- El push lo autoriza Martín para cada capa que pase su corte.
