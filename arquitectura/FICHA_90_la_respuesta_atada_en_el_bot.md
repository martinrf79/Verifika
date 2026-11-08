# FICHA 90 — La respuesta atada en el bot

7-nov-2026, con Martín. **Está en el bot y en `main`.** Desde el 8-nov la sesión arranca por la FICHA 91; esta ficha es el
estado de la respuesta, y vale sobre la FICHA 88 y la 89, que la daban por descartada.

## Por qué

El agente escribía libre y la verificación posterior no garantiza cero alucinaciones: cada día aparece una forma nueva.
En WhatsApp el 6-nov: "más de 100 artículos" con 25 filas visibles, "70 transferencia y 30 Mercado Pago" cuando el cliente
dijo solo "setenta treinta", "marca suiza", "ya te los reservé" sin nombre, el presupuesto viejo y el nuevo juntos, un
solo envío para dos destinos, "lo menos chino" ordenado por país alfabético.

## Qué es

El modelo contesta con la herramienta `responder`, atada por la API (`tool_choice` requerido, esquema armado en cada
vuelta): cita por número lo que devolvieron las herramientas en el turno —P productos, R reglas, E envíos, N lo que la
tienda no vende, D cantidades y búsquedas vacías— y escribe solo un saludo y una pregunta cortos. Los datos los pega el
código con las filas reales: `app/core/flujo/respuesta.py`. El control mira lo único que escribe el modelo: un número en
cifras o en palabras, una marca o modelo, un valor de la ficha o un medio de pago en el saludo o la pregunta vuelve una
vez al modelo, y si sigue, ese campo no sale. Sin garantías de más: lo que el código pega sale de la tienda tal cual.

Lo medido el 5-nov con la paga en las 42 charlas reales (FICHA 88): ningún dato de producto ni de plata inventado, y
peor que el agente libre por una sola causa, el orden por país en "lo menos chino". Esa causa ya no está en el modelo.

## Lo que decide el código y antes decidía el modelo

- **El criterio del cliente:** un orden del vocabulario de la tienda ("más barato") si el mensaje dice uno solo, y lo que
  el cliente quiere de menos ("menos partes chinas") por las columnas cerradas de la tabla. Va antes del orden que
  escribe el modelo, `agente.orden_del_cliente`, `tabla.con_orden`.
- **Lo que la tienda no vende:** se detecta en el mensaje del cliente y llega citable en el turno.
- **Una búsqueda vacía y un COUNT** se citan: sin eso el modelo no tenía cómo decir "no tenemos" ni cuántos hay.
- **Un renglón, un destino:** "Córdoba y Concordia" en un renglón no se aplica y vuelve al modelo.
- **Un pago sin pedido** no muestra al cliente la pregunta interna "¿De qué productos querés la cuenta?".
- **Una pregunta del código por vez:** si lo pegado ya pregunta, la pregunta del modelo se calla.
- **El pedido y la cotización salen solos y una vez:** el modelo no puede repetir un presupuesto.
- **Conciso:** hasta 6 productos y 3 columnas por producto, `respuesta.MAX_PRODUCTOS` y `MAX_COLUMNAS`. Umbrales de lo
  visto en WhatsApp con el modelo real, que citaba 15 productos con 6 columnas.

## Cómo se midió, 7-nov

- Sin modelo, `agente_replay.py`: un modelo simulado que pasa cada texto grabado a una llamada `responder` y cada
  llamada vieja a `presupuesto` a `pedido` o `cotizar`. 75 de 75 turnos. Mide el código, no al modelo.
- El candado de las 42 charlas reales: los 100 turnos que andaban conservan presupuestos, cobros y verificador; cambia
  solo el texto, que es lo buscado. La foto se sacó de nuevo.
- `tests/test_respuesta_atada.py`: 11 pruebas, una por clase de falla de WhatsApp.
- Con el modelo real, OpenRouter gratis y embeddings con la paga: las charlas de WhatsApp del 6-nov. Ver el commit.
  Gemini gratis, agotada hasta el reinicio de la cuota.

## Lo que falta

1. **Regrabar la vara con el modelo de producción**, `agente_replay.py --gratis --etiqueta atada --regrabar`, cuando la
   cuota se reinicie, y tres corridas. Hoy la vara usa el modelo simulado.
2. **Medir en WhatsApp.** Si el modelo cita de más o de menos, se ajusta la consigna, no se suman guardas.
3. **La llamada corta de pulido** que Martín propuso: el código redacta el borrador, un modelo lo suaviza, y el control
   compara contra el borrador con lista permitida. No está hecha; se mide si el texto suena seco.
4. **Pago por persona o por destino**, "lo de Bariloche con transferencia a nombre de Joaquín y lo de Comodoro con Mercado
   Pago a nombre de Mariana": hoy el pago se divide solo por porcentaje.
5. **El pedido de siete artículos** en un solo mensaje con el modelo libre pedía modelos y colores durante tres turnos.
