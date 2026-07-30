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
  `recall_modelos.py` (qué modelos del catálogo PUEDE nombrar el intérprete).
- **Estado:** sólido y MEDIDO. `banco_recall_modelos.py`, 1552 casos sobre el
  catálogo real: recall@30 100%, recall@5 87,6%.
- **Ojo con el recall, que es el techo de esta capa:** el enum de
  `producto_resuelto` no lleva los 482 modelos, lleva los que recupera la etapa
  1. Lo que no entra ahí, el intérprete no lo puede nombrar aunque lo haya
  entendido perfecto.

## ⚠ LA COSTURA QUE HAY QUE ARREGLAR (diagnostico 30-jul-2026)

Entre la Capa 1 y la Capa 2 hay un corte medido: **la lectura estructurada del
interprete se usa solo para armar el MENU de lo que el modelo PUEDE decir, nunca
como ORDEN de lo que el sistema DEBE contestar.**

El caso mas claro: el interprete emite, por cada producto consultado, un campo
`consulta` -precio, ficha, stock, opinion, comparacion, envio- atado por enum y
bien resuelto. **No lo lee nadie: cero usos en todo `app/core`.** Lo mismo con
`specs_preguntadas`, que el solver no recibe y solo se usa despues para corregir
lo ya escrito, y con `intencion`, `criterio` y `confianza`.

Consecuencia: como la lectura no ordena la respuesta, hay que suplirla con un
prompt que anticipe cualquier combinacion. Hoy se arma con 11 entradas y 42 ramas
en `universo_productos`. Cada capacidad nueva engorda ESE prompt en vez de sumar
una pieza al lado, y por eso arreglar un caso rompe otro.

El detalle completo, con la tabla campo por campo y la medicion en vivo, esta al
tope de `RESUMEN_PARA_NUEVO_CHAT.md`. **Es el punto de partida del proximo
trabajo, y es un diagnostico: la solucion se planifica con Martin antes de tocar
codigo.**

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
- **La CITA.** Cuando `renderizar` emite un fragmento de criterio, deja el
  bloque jurado que lo respalda en `meta['tools_called']`; de ahí la deriva
  `verificador_cita.citas_de_meta`. Determinista: los ids salen del propio
  corpus, nunca del modelo. Es el "Citador" de la Capa A aplicado a la prosa.

## Capa 3 — Orquestación

Decide, en cada turno, si responde, repregunta o dispara un flujo, y compone la
respuesta uniendo dato duro y prosa.

- **Módulo vivo primario:** `generador_v2.py` — el modelo emite FRAGMENTOS
  atados a enums del universo del turno y el código estampa cada dato desde la
  fuente. Conduce el caso general.
- **Si el modelo falla:** sale el mensaje de fallback enlatado. La red de
  degradación determinista (`selector` + `compositor` + `redactor`) se BORRÓ el
  29-jul: llevaba desde el corte al hub sin que la llamara nadie, y una segunda
  maquinaria de composición en paralelo es la clase de camino doble que costó
  los 70 flags. Si un día el modelo se cae seguido, se ataca con reintento.
- **Estado y memoria:** `estado_venta.py`, `memoria_larga.py`, `guia_pedido.py`,
  `cierre.py`.
- **Estado:** vivo y deployado. `hub_atado.py` conduce el turno entero y es el
  ÚNICO camino: el orchestrator entra ahí y no hay otro.

## Capa 4 — Acción y guardrails

Ejecuta las tareas estructuradas y verifica todo lo que sale, con logs cruzando
las capas. Es el diferencial de Verifika.

- **Acción:** `calculate_total` que sella, carrito, `pago.py`, `pago_split.py`,
  `envio.py`, `entrega.py`, `leads.py`, `notificador.py`, `posventa.py`.
- **Guardrails de salida:** todos en `hub_atado._red_de_verificadores`, en un
  solo orden, de lo más duro a lo más blando: montos (`verificador.py`), stock
  (`verificador_stock.py`), FAQ numérica (`verificador_faq.py`), intención
  (`verificador_intencion.py`), cita (`verificador_cita.py`), promesas
  (`guardia_promesas.py`) y el LLM juez (`checker_afirmaciones.py`). Después
  las guardas deterministas de `guardas_salida.py`. Más `antijailbreak.py` a la
  entrada y `calc_defensiva.py` en la calculadora.
- **Observabilidad y evaluación:** logs con `trace_id`, `tests/` y `banco_pruebas/`.
- **Estado:** robusto. La red de verificadores es lo que más te distingue.
- **El verificador de cita** resuelve cada id citado con `texto_de(id)` y marca
  el que no exista; loguea `hub_atado_cita_prosa`.

---

## Resumen de dónde estamos

Las cuatro capas existen y corren en producción, y desde el 29-jul TODO lo que
está escrito corre: la auditoría de alcance (partir de `app.main` y seguir los
imports, también los que están dentro de funciones) da CERO módulos huérfanos.

Cómo se llegó a eso, que es la lección que este documento tiene que conservar:
el 29-jul esa misma auditoría daba **5.429 líneas que no alcanzaba nadie**. Al
pasar el orchestrator de `interprete_libre` al hub, todo lo que colgaba del
camino viejo se cayó con él —el LLM juez, cinco verificadores, cinco guardas—
y siguió meses con sus tests en verde, probando código muerto. Este documento
mismo daba por viva la red de degradación determinista, que no lo estaba.

**Verde sobre código muerto es peor que rojo: da confianza falsa.** Por eso hoy
cada pieza tiene un test que exige que el hub la LLAME, no solo que funcione.

Lo que falta ya no es código nuestro, son DATOS de la tienda: las relaciones de
compatibilidad producto por producto, y los datos reales de cobro. Mientras no
estén, la compatibilidad es opinión y hay que decirlo así, no venderla como
verificada.
