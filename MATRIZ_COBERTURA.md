# MATRIZ DE COBERTURA — el espacio de respuestas, cerrado

Fuente de verdad de los CASOS del sistema (16-jul-2026). Las preguntas posibles
son infinitas; lo que se cierra acá es el conjunto FINITO de familias de
situación y, para cada una, cinco cosas: qué fuente responde, cómo va atado el
modelo, qué invariante chequea el fiscal, qué sale si algo falla, y qué guion o
test del banco la lockea. La última fila atrapa TODO lo que no matcheó: no
existe entrada sin casilla.

El idioma común es el contrato tipado de punta a punta: el intérprete lee el
mensaje a estructura finita (intención, producto, pedido, criterio, tope,
exclusiones, uso, destino, negación, confianza), el generador emite fragmentos
tipados, y los filtros verifican por tipo. Cada falla real de producción se
absorbe AGREGANDO una fila, un bloque de prosa o un invariante; el contrato no
se cambia nunca.

Cómo leer cada fila: `familia — fuente | atadura | invariante | fallback | lock`.

Ataduras posibles (de más dura a más blanda):
- **DURA**: el código estampa el dato desde la fuente; el modelo solo referencia
  (id de enum). Imposible inventar.
- **CITA**: el modelo redacta apoyado en bloque jurado y cita el id; el
  verificador de cita chequea que exista. Poda de dígitos.
- **LIBRE-PODADA**: prosa libre sin dígitos ni datos duros; verificadores de
  salida como red. Radar de huecos si no hubo bloque.

---

## A. DATO DURO — atadura DURA, el código estampa

1. **Precio de un producto** — catálogo Firestore | DURA: id de enum, precio
   estampado | verificador de plata: toda cifra con proof | compositor
   determinista | guiones 04, 25.
2. **Stock / disponibilidad** — catálogo | DURA | verificador de stock, ancla
   por tokens | compositor | guiones 03, 20.
3. **Total / presupuesto de pedido** — calculate_total sella | DURA: fragmento
   presupuesto, el modelo solo posiciona | bloqueo de presupuesto inventado
   (es_presupuesto_inventado); un número ya con proof no se re-corrige |
   fallback "dame un segundo que lo calculo" | guiones 24, 29, 32.
4. **Envío: costo y destino** — cotizar_envio, 16.164 localidades | DURA |
   proof por tramo; destino ambiguo pregunta provincia | pregunta de
   provincia | guiones 05, 27, 30, 37.
5. **Multi-destino con reparto** — calculadora + reparto_envios_detalle |
   DURA | una tarifa por destino, proof por grupo | pregunta destinos
   pendientes | guiones 27, 30.
6. **Split / forma de pago** — pago_split | DURA: porcentajes suman 100 |
   proof respalda renglones, subtotal y extras | cascada determinista |
   guiones 17, 31, 38.
7. **Descuento por transferencia** — config de tienda | DURA | es_mercado_pago
   reconoce el medio | curada | guion 31.
8. **Edición de pedido (sacá/agregá/cambiá)** — carrito + recálculo sellado |
   DURA: ejecutar_calculo_plan todo-o-nada | nombres→ids validados | cascada |
   guiones 29, 36.
9. **Presupuesto retomado turnos después** — ultimo_presupuesto + carrito |
   DURA | el vigente no se pisa sin pedido nuevo | re-servir presupuesto |
   guiones 28, 34.
10. **IVA / factura / moneda** — FAQ | DURA: respuesta curada estampada |
    verificador de FAQ | curada | guion 23.

## B. IDENTIDAD — la decide el CERTIFICADOR, nunca el modelo

11. **Producto nombrado directo** — search certificada | DURA: exists /
    ambiguous / not_found | toda tool consume id certificado | ficha o A/B de
    variantes | guiones 01, 35.
12. **Variantes (color, modelo)** — certificador ambiguous | DURA | ante
    ambiguo se pregunta, prohibido elegir | A/B | test_busqueda_certificada.
13. **No existe / not_found** — certificador | DURA | not_found es resultado
    válido: honesto + categorías reales | not_found honesto | banco.
14. **El más barato** — guia_compra computa el mínimo con stock | DURA: problema
    cerrado, lo hace el código | guarda del más barato solo con criterio del
    turno | re-ancla | guiones 04, 25.
15. **El intermedio / gama media** — intermedio_con_stock | DURA | escalón
    arriba del mínimo | opciones | test en guia_compra.
16. **Referencia vaga ("el otro", "el que dijiste")** — intérprete +
    productos_vistos + ancla | DURA: enum de mostrados | corrección
    comparativa determinista ("el barato no") | candidatos + pregunta |
    guiones 28, 34; test_ancla_anotado.

## C. POLÍTICA DE LA TIENDA — FAQ curada, 44 temas

17. **Envíos, garantía, pagos, devoluciones, retiro, reservas…** — faq.json |
    DURA: tema de enum, texto curado estampado | verificador de FAQ | derivación
    honesta | guiones 01, 02, 17.
18. **Política que NO está en la FAQ** — sin fuente | LIBRE-PODADA: honesto
    "no lo tengo confirmado" + derivación | evento pregunta_sin_fuente = mina
    de curadas | derivación | guion 33.

## D. CRITERIO Y RAZONAMIENTO DE VENTA — la mitad blanda

19. **Para qué sirve / me conviene** — corpus jurado (33 temas) + ficha |
    CITA cuando hay bloque | verificador de cita | válvula: razona desde ficha
    sin bloque, criterio_sin_bloque al radar | guion 12.
20. **Comparación entre productos** — ficha de ambos + corpus | CITA o
    LIBRE-PODADA | poda de dígitos; specs solo de ficha | opciones | guion 35.
21. **Compatibilidad técnica** — ficha; SOLO si la ficha lo dice | CITA |
    prompt endurecido: sin dato en ficha se dice honesto | honesto + pedir
    modelo | guion 35.
22. **Recomendación con preferencias (tope, exclusiones, uso)** — intérprete
    normaliza; el filtro de universo excluye POR CONSTRUCCIÓN | DURA en el
    universo + LIBRE-PODADA en la frase | lo excluido ni entra al enum; si nada
    cumple, honesto | banco de paráfrasis; test_preferencias_cliente.
23. **Objeción de precio / regateo** — corpus (objecion_precio) + FAQ
    descuentos | CITA | sin rebaja inventada; criterio no queda sticky en B4/B5 |
    curada | guion 10.
24. **Pregunta técnica general (RAM, mecánico vs membrana…)** — corpus 16
    temas + FAQ de conocimiento | CITA | cero números en prosa | válvula +
    radar | banco.

## E. CONVERSACIÓN — memoria, hilo, correcciones

25. **Saludo / apertura** — movidas de venta | CITA | regresión de estado
    prohibida (no re-saludar a mitad de charla) | saludo corto | guion 01.
26. **Memoria de la charla (destino dado turno 1, criterio viejo)** —
    estado + resumen + _bloque_memoria | DURA: los números salen de tools |
    sticky solo lo que corresponde | repregunta | guiones 09, 16, 18, 37.
27. **Negación y cambio de decisión ida y vuelta** — intérprete (negación) |
    DURA: pedido re-sellado | lo negado no reaparece; pendiente no se sella
    con otra categoría | repregunta | guiones 07, 36.
28. **Varias preguntas en un mensaje** — generador: un fragmento por
    pregunta | mixta por fragmento | "responde TODAS"; juez de completitud |
    compositor | guion 15.
29. **Cliente desprolijo / typos / audio transcripto** — intérprete
    normaliza | mixta | confianza baja → repregunta corta | repregunta |
    guion 14.
30. **Indecisión eterna / cliente que vuelve** — estado + movidas
    (continuación, seguimiento) | CITA | sin presión inventada, urgencia solo
    honesta | seguimiento cordial | guiones 18, 22.
31. **Ironía / chiste / fuera de tema** — intérprete (intención otra) |
    LIBRE-PODADA | no se lee como compra | vuelta cordial al hilo | banco
    interpretación.

## F. ADVERSARIALES — el cliente ataca o miente

32. **Precio falso afirmado ("me dijiste que salía X")** — catálogo |
    DURA | negador de precio trae el real y rechaza | corrección con precio
    real | guion 10.
33. **Jailbreak comercial / cambio de rol** — antijailbreak | DURA |
    patrón detectado → respuesta fija | rechazo cordial | guion 19.
34. **Pedir dato inexistente insistiendo** — fuente | DURA | sin fuente no
    hay dato, honesto siempre | derivación | guion 33.
35. **Insulto / maltrato** — guía de tono | LIBRE-PODADA | sin respuesta
    espejo; ofrecer humano | derivar_humano | guion 13.

## G. OPERATIVA — acciones fuera de la charla

36. **Quiero un humano** — intérprete (derivar_humano) | DURA | notificador
    dispara | derivación inmediata | guion 13.
37. **Reclamo / posventa / seguimiento** — posventa + leads | DURA | estado
    posventa no vende | derivación | guion 21.
38. **Reserva / seña** — FAQ reservas | DURA | keywords reales ("me lo
    guardás") | curada | guion 17.
39. **Cierre: datos del cliente, lead** — cierre.py + extractor | DURA |
    forma de pago dada no se re-pide | pregunta de cierre única | guiones 06,
    11; test_cierre.
40. **Despedida / no quiero nada más** — curada B31 | DURA | despedida no es
    compra | cierre cordial | banco.

## Z. LA FILA FINAL — todo lo demás

41. **Cualquier entrada que ninguna fila cubra** — sin fuente | LIBRE-PODADA |
    honesto "eso no lo tengo confirmado" + derivación + evento
    `compositor_pregunta_sin_fuente` o `generador_v2_criterio_sin_bloque` en el
    log | derivación | por construcción: el fallback final siempre existe.

---

## El circuito que la mantiene completa

1. Los eventos `pregunta_sin_fuente` y `criterio_sin_bloque` en los logs de
   producción son el RADAR: cada uno es un hueco real visto en tráfico.
2. Cada hueco se resuelve agregando contenido (bloque de prosa, tema de FAQ,
   fila nueva) con su lock en el banco. NUNCA cambiando el contrato.
3. Toda charla real problemática de Martín se lockea como guion numerado.
4. La matriz se toca solo para AGREGAR filas o mejorar invariantes; si una fila
   cambia de atadura, se anota acá el porqué con fecha.
