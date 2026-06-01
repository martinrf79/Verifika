# Calculadora defensiva — diseño y reglas (investigación 2026-06)

Documento de diseño para la capa defensiva de `calculate_total`. Recoge cómo
lo hacen motores de precios serios (Medusa, Shopify, Woo, retail POS) y el
patrón neurosimbólico para validar inputs de un LLM antes de ejecutar la cuenta.
Objetivo: cubrir la mayoría de las combinaciones de productos, envíos y
descuentos sin alucinar y sin que el modelo improvise números.

## Principio rector
La cuenta la hace SIEMPRE el código, nunca el modelo. Las reglas de negocio se
escriben como código ejecutable y auditable, no como texto en el prompt. Un
prompt es una sugerencia que el modelo puede ignorar; una regla en código es una
barrera que no puede saltar. Esto ya es la filosofía del verificador; la
calculadora defensiva la extiende a la ENTRADA, no solo a la salida.

## Patrón: guarda neurosimbólica antes de calcular
Interceptar y validar/normalizar los argumentos que manda el modelo ANTES de
ejecutar `calculate_total`. Tres etapas:

### A) Normalizar
- `product_id`, `faq_tema`, `concepto`: trim + lower de forma consistente.
  Hoy `tema` se baja a minúsculas pero `concepto` no, y eso dispara fallback.
- Fusionar `product_id` repetidos sumando cantidades en una sola línea.
- `cantidad`: forzar entero >= 1. Descartar 0 y negativos.

### B) Resolver dualidades (colapsar por categoría)
- Envío: una sola opción. Si el modelo manda dos conceptos de envío, hoy se
  SUMAN los dos. DECISIÓN DE MARTÍN: resolver el envío correcto por FILTRO sobre
  el destino, igual que filtra la búsqueda de productos. La capa mapea el destino
  que dijo el cliente, por ejemplo CABA, GBA o interior, al concepto de envío que
  corresponde, en vez de confiar en lo que eligió el modelo. Si el destino no es
  claro, se pide antes de cerrar. El umbral de envío gratis manda por encima.
- Descuento: deduplicar. Si vienen dos veces, se aplica una. Si hay varios
  descuentos no combinables, aplicar el de mayor prioridad o el mejor para el
  cliente, según regla.
- Seña/reserva: efecto informativo, no toca el total, va aparte.

### C) Validar reglas duras (lista de Rule deterministas)
Cada regla es una función booleana sobre el contexto ya normalizado. Si una
falla, `calculate_total` devuelve `ok: False` con `mensaje_para_llm` claro para
que el modelo vuelva a preguntar en vez de inventar. Reglas:
- producto existe en catálogo.
- cantidad > 0 y <= stock.
- no más de un concepto de envío.
- total final nunca negativo.
- piso de precio mínimo vendible (MVP): DECISIÓN DE MARTÍN, no por ahora. Hoy no
  se apilan descuentos grandes. Queda anotado como salvaguarda futura de retail
  por si algún día se combinan descuentos.

## Orden de operaciones (explícito y documentado)
Tomado de Medusa, Shopify y los motores de stacking. El envío y el envío gratis
se evalúan SIEMPRE al final.
1. Subtotal = suma de precio x cantidad por línea, a precisión plena.
2. Descuentos sobre el SUBTOTAL de productos. Regla de negocio de Martín:
   descuento por transferencia sobre subtotal de productos.
3. Envío: se evalúa al final. El umbral de envío gratis puede ponerlo en 0
   (flag ENVIO_GRATIS_AUTO, umbral 250000, ya implementado).
4. Total = subtotal - descuentos + envío.
5. Redondeo una sola vez al final. Mantener precisión plena en los intermedios.
   En pesos enteros casi no afecta, pero la regla evita errores de centavos si
   algún día entran porcentajes con fracción.
6. PROOF declara cada operando para que el verificador respalde cada cifra.

## Stacking de descuentos: definir explícito
Dos modos posibles, hay que elegir por regla:
- Secuencial: cada descuento se calcula sobre el precio ya rebajado. 10% + 10%
  no es 20%, es 19% efectivo.
- Simultáneo: los porcentajes se suman sobre el subtotal original.
Hoy Verifika aplica los porcentajes sobre el subtotal de productos (simultáneo
sobre el subtotal). Dejarlo documentado y como flag si alguna vez cambia.
Marcar descuentos como excluyentes cuando no se pueden combinar; si hay varios
excluyentes, aplicar el que da el mayor descuento (best-price), patrón estándar.

## Cómo cubrir la mayoría de las combinaciones: pruebas por propiedad
No se enumeran los casos a mano. Se generan combinaciones del producto cartesiano
productos x extras x destinos y se afirman INVARIANTES que deben valer siempre:
- total_ars == subtotal - descuentos + envío, exacto.
- el total nunca queda por debajo del piso MVP.
- nunca se cobran dos envíos.
- la presentación renderizada SIEMPRE pasa el verificador, ninguna cifra sin
  respaldo.
- si subtotal > umbral, envío == 0.
- monotonía de sanidad: agregar un producto nunca baja el total.
Esto es lo que de verdad da cobertura amplia: el banco de casos genera cientos de
combinaciones y verifica los invariantes, en vez de escribir cada caso a mano.

## Mapa a los agujeros detectados hoy en calculate_total
- Doble envío sumado: lo resuelve la etapa B, una sola opción de envío.
- Descuento duplicado: lo resuelve la deduplicación en B.
- cantidad 0 o negativa: lo resuelve la validación en C.
- product_id repetido en dos líneas: lo resuelve la fusión en A.
- concepto sensible a mayúsculas: lo resuelve la normalización en A.
- sin piso de precio: lo agrega la regla MVP en C.

## Implementación propuesta
- Todo detrás de flag CALC_DEFENSIVA en app/config.py, default false hasta probar.
- La capa vive ANTES de la lógica actual de calculate_total, no la reescribe.
  Si el flag está off, el comportamiento es idéntico al de hoy.
- Reglas como lista de objetos Rule, deterministas y testeables por separado.
- Se prueba test-first contra el banco determinista ampliado, sin DeepSeek.

## Estado de implementación (2026-06-01)
PRIMERA VERSIÓN HECHA, detrás de flag CALC_DEFENSIVA, default false.
- Archivo: app/core/calc_defensiva.py, función normalizar_inputs.
- Enganche: app/core/tools.py, al inicio de calculate_total, solo si el flag está on.
- Cubre: P2 cantidad cero o negativa rechazada, P3 concepto normalizado a
  minúscula, P4 producto repetido fusionado, P1 extra idéntico deduplicado.
- Verificado: scripts/banco_casos.py corre con la defensiva activa, los cuatro
  pasan a OK y las 335 combinaciones siguen en cero fallas; bateria_robustez con
  el flag apagado sigue 11/11.
- PENDIENTE P5: dos conceptos de envío DISTINTOS resueltos por destino. La capa
  de hoy solo deduplica identicos. Resolver por destino necesita que el destino
  del cliente llegue a calculate_total, hoy no llega. Próxima ronda.
- Para activar en prod, con OK de Martín: --update-env-vars=CALC_DEFENSIVA=true

## Fuentes
- Medusa, cálculo de totales de carrito: https://medusajs.com/blog/cart-totals/
- Guardas neurosimbólicas que interceptan tool calls: https://dev.to/aws/ai-agent-guardrails-rules-that-llms-cannot-bypass-596d
- Stacking y orden de operaciones de descuentos: https://www.voucherify.io/glossary/promotion-stacking
- Reglas de precios excluyentes y piso MVP en retail POS: https://medium.com/@rajeshkumar1980/inside-retail-pos-pricing-engines-how-mvp-promotions-and-discount-stacking-work-in-enterprise-8f8829e28b3a
- Herramientas deterministas contra alucinación: https://tinyfn.io/blog/prevent-llm-hallucinations-mcp
