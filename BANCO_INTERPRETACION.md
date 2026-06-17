# Banco de interpretación — fuente única

Objetivo: medir SOLO la interpretación, de mensaje más contexto a mensaje
estructurado completo (Dialogue State Tracking). No toca el Solver, ni el
provider, ni producción. Una llamada al modelo por caso, barato, model-swappable.

La regla madre: el modelo nunca inventa un hecho que comprometa al cliente; acá
medimos si ENTIENDE bien, que es la base de todo lo de abajo.

## 1. El esquema estructurado (lo que el modelo debe completar cada turno)

- intencion: saludo, exploracion, pregunta_producto, pregunta_faq, aporta_dato,
  cambio_pedido, decision_compra, confirma_eleccion, objecion, despedida, otra
- confianza: 0 a 1
- respondiendo_a: a qué pregunta del bot responde, o vacío
- estado_venta: saludo, explorando, cotizando, esperando_confirmacion,
  esperando_datos, cerrando, cerrado, postventa
- tipo_confirmacion: a_o_b, te_referis_a, confirmar_compra, o null
- items: lista; por ítem termino_crudo, producto_id (null acá, lo resuelve la
  búsqueda después), nombre_resuelto, cantidad, atributos (color, modelo, marca,
  conectividad), criterio_seleccion (mas_barato, mas_caro, mejor, indistinto, null)
- candidatos: opciones reales cuando no se puede resolver a uno
- eje_ambiguedad: modelo, color, cantidad, cual_producto, o null
- operacion: ninguna, agregar, sacar, cambiar_cantidad, cambiar_producto,
  vaciar_carrito, nueva_compra
- objetivo_operacion: a qué ítem aplica
- cambio_de_idea: true o false
- zona_o_cp: localidad, provincia o CP, o null
- pide_envio: true o false
- modalidad_entrega: envio, retiro, o null
- forma_pago: transferencia, efectivo, tarjeta, mercadopago, o null
- datos_cliente: nombre, telefono, direccion, email, cuit (los que aporte)
- pide_cerrar: true o false
- tema_faq: envio, devolucion, garantia, stock, horarios, formas_pago,
  procedencia, o null
- pregunta_atributo: garantia, origen, material, contenido, medidas, o null
- objecion: precio, confianza, tiempo, competencia, o null
- negacion_o_postergacion: true o false
- seguridad: ok, jailbreak, fuera_de_dominio

Nota: producto_id NO se evalúa acá. Resolver el ID real es búsqueda, otra etapa.
El banco mide el ENTENDER: término, cantidad, atributos, operación, intención.

## 2. Reglas de continuidad (lo que el banco da por correcto)

1. Herencia: una ranura persiste hasta que se cambia explícito; la cantidad se
   hereda del pedido abierto; producto nuevo desde cero reinicia la cantidad.
2. Conflicto: el turno gana sobre el estado guardado para la misma ranura.
3. Anáfora (ese, lo, el): ata al sujeto de la pregunta abierta, si no al foco, si
   no al único ítem del carrito; si nada queda claro, ambiguo.
4. Responder vs pivotear: con pregunta abierta, se toma como respuesta salvo que
   claramente abra tema nuevo; ahí pivotea y la pregunta queda pendiente.
5. Corrección y cambio de idea: ambas son operación sobre el ítem objetivo.
6. Multi parcial: el estado guarda cada ítem como resuelto o pendiente; una
   respuesta posterior se engancha a la ranura pendiente, no crea ítem nuevo.

## 3. Puntaje por campo

- Categóricos (intencion, operacion, tema_faq, forma_pago, criterio): exacto.
- confianza: por banda (alta mayor o igual a 0.8, etc.), no número clavado.
- items: coincidencia de término y cantidad, no orden estricto.
- zona y datos: contiene el valor esperado.
- booleanos: exacto.
Cada caso afirma SOLO los campos que le importan; lo demás no se penaliza.

## 4. Cómo correr

    .\correr_local.ps1 py scripts\bench_interpretacion.py

Model-swappable por entorno, sin tocar código:
- DeepSeek (default): usa DEEPSEEK_API_KEY y DEEPSEEK_MODEL de .secrets6.env.
- Otro modelo o OpenRouter: setear BENCH_MODEL, BENCH_BASE_URL, BENCH_API_KEY.
  Rotar modelos reparte el límite diario del tier gratis y compara cuál entiende
  mejor.

## 5. Qué decide el banco

Por campo y por tipo de pregunta, qué modelo entiende bien y dónde falla. Los
fallos son la hoja de ruta: cada uno es un caso etiquetado que tiene que pasar a
verde antes de avanzar. El banco mide, no opina.
