# Arquitectura de Verifika — las cuatro capas del bot profesional

Mapa de referencia permanente. Muestra las CUATRO capas que usan los sistemas
de venta profesionales, adaptadas a Verifika: qué módulo real cumple cada capa,
qué está VIVO y qué LADRILLO falta. El estado del día vive en
`RESUMEN_PARA_NUEVO_CHAT.md`; esto es el mapa estable de cómo se ordena todo.

## El principio que cruza todo: las dos mitades

Cada respuesta se parte en dos, y cada mitad se ata distinto:

- **Dato duro** — precio, stock, total, envío, política. Se ata por herramienta:
  el código estampa el número desde la fuente. Garantía total. Ya resuelto.
- **Prosa de venta** — criterio, comparación, compatibilidad, por qué conviene.
  Se ata por grounding más cita: el modelo responde SOLO desde el corpus jurado
  y dice qué bloque usó. Garantía alta, en construcción.

El modelo nunca inventa un dato; a lo sumo elige mal un texto, y para eso está
la red de verificadores.

---

## Capa 1 — Interpretación

Entiende en lenguaje natural qué quiere el cliente, aunque haya negaciones,
ironía, cambios de decisión o pedidos enredados.

- **Módulos vivos:** `interpretador.py` (una llamada LLM con salida estructurada
  atada por enum: intención, producto, pedido, criterio, destino) y
  `interprete_libre.py` (orquesta el turno entero).
- **Estado:** sólido. Bancos de interpretación 29/29 en casos sueltos y 23/23
  en multiturno con Gemini.
- **Ladrillos que faltan:** nada grande; está afinado.

## Capa 2 — Recuperación y grounding

Trae el contexto real desde la fuente de verdad, nunca desde la memoria del
modelo. Es la capa anti-alucinación por construcción.

- **Módulos vivos, dato duro:** `tools.py` — búsqueda, ficha, FAQ,
  `cotizar_envio`, `calculate_total`; y la evidencia en `evidencia.py`.
- **Módulos vivos, prosa:** `guia_venta_prosa.py` — corpus de 33 temas jurados
  de criterio de venta, con `recuperar()` que devuelve los mejores bloques con
  su id, y `texto_de()` para chequear la cita.
- **Estado:** dato duro completo. Prosa: corpus recién ampliado, groundeado al
  catálogo real, con recuperación top-K andando.
- **Ladrillos que faltan:** la CITA. Que el solver diga qué bloque de prosa usó,
  con salida estructurada, y su verificación. Es una de las dos piezas del
  próximo chat.

## Capa 3 — Orquestación

Decide, en cada turno, si responde, repregunta o dispara un flujo, y compone la
respuesta uniendo dato duro y prosa.

- **Módulo vivo primario:** `solver_gemini.py` — el modelo llama las tools, el
  código las ejecuta contra la fuente, y compone. Conduce el caso general.
- **Red de degradación determinista:** `selector.py`, `compositor.py`,
  `redactor.py` — si el solver falla, el código arma la respuesta sin él. El
  peor caso es un mensaje soso, nunca un dato falso.
- **Estado y memoria:** `estado_venta.py`, `memoria_larga.py`, `guia_pedido.py`,
  `ruteo_venta.py`, `cierre.py`.
- **Estado:** vivo y deployado. El solver es primario salvo el pedido ya sellado
  por la calculadora.
- **Ladrillos que faltan:** medir en el tier gratis que el modelo obedece:
  llamado de tools consistente y memoria de contexto en turnos largos.

## Capa 4 — Acción y guardrails

Ejecuta las tareas estructuradas y verifica todo lo que sale, con logs cruzando
las capas. Es el diferencial de Verifika.

- **Acción:** `calculate_total` que sella, carrito, `pago.py`, `pago_split.py`,
  `envio.py`, `entrega.py`, `leads.py`, `notificador.py`, `posventa.py`.
- **Guardrails de salida:** `verificador.py` para la plata, `verificador_stock.py`,
  `verificador_faq.py`, `guardia_promesas.py`, `antijailbreak.py`,
  `calc_defensiva.py`.
- **Observabilidad y evaluación:** logs con `trace_id`, `tests/` y `banco_pruebas/`.
- **Estado:** robusto. La red de verificadores es lo que más te distingue.
- **Ladrillos que faltan:** el verificador de cita de la prosa, la otra pieza del
  próximo chat; y decidir qué filtros de prosa se aflojan según la regla de las
  dos mitades.

---

## Resumen de dónde estamos

Las cuatro capas existen y corren en producción. Lo que separa a Verifika de un
bot profesional no es un modelo más caro, son tres ladrillos concretos:

1. La cita sobre la prosa recuperada, capa 2.
2. El verificador de esa cita, capa 4.
3. Una suite de evaluación que no deje pasar regresiones, capa 4, ya a medias.

El corpus de prosa jurado, base de la capa 2 para la venta, ya está cargado.
