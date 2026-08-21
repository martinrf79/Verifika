# Los 13 guiones nuevos — cada uno apunta a un número medido

Entraron el 19-ago-2026. Formato idéntico al del resto de la carpeta: un mensaje
del cliente por línea. Usan **productos, precios, colores y stock reales del
catálogo de 880**, verificados el 18-ago, así que el barrido offline los puede
juzgar sin modelo.

**No están escritos para que el bot quede bien.** Cada uno ataca un número de
`PASO0_CENSO.md` o un ítem abierto de `PENDIENTE.md`. Si pasan todos a la
primera, el banco está midiendo mal.

---

## El mapa: guión → qué defecto caza

| guión | turnos | ataca | por qué |
|---|---|---|---|
| `26_negacion_progresiva` | 12 | **la negación** — "el teclado sacalo" | `PENDIENTE`: *ninguna pieza ve la NEGACIÓN… y el código cuenta el teclado igual* |
| `27_multipregunta_apilada` | 10 | **omisión** — 4-5 puntos por mensaje | 22% de turnos cierran con un punto sin contestar; `punto_omitido` intervino **0/54** |
| `28_no_se_sabe_no_es_no` | 12 | **"no se sabe" ≠ "no"** | 29% de los puntos salen sin material de la fuente |
| `29_condicion_arrastrada` | 12 | **la condición que no se busca** | `_condicion_faltante_aplicada` interviene 4%; el reconciliador reclama en 57% |
| `30_ambiguo_g_pro` | 12 | **regla cero: ambiguo obliga a preguntar** | hay **3 productos** distintos con "G Pro" |
| `31_cobro_inducido` | 12 | **CBU / alias / titular inventado** | `sin_cobro_inventado` intervino **0/54** |
| `32_multidestino_que_cambia` | 12 | **reparto que muta + dos totales** | los invariantes `el_reparto_cubre_el_pedido` y `un_solo_total_por_concepto` sin ejercitar |
| `33_contradiccion_lejana` | 13 | **memoria larga y presupuesto del turno 1** | el turno largo con modelo vivo no tiene barrido |
| `34_dato_falso_inducido` | 12 | **descuento y precio inducidos por el cliente** | `sin_descuento_inventado` 2/54, `sin_afirmar_del_catalogo` 1/54, `sin_negar_lo_traido` **0/54** |
| `35_stock_cero_no_mata_la_venta` | 12 | **un detalle no tira la venta** | requisito de arquitectura sin ninguna prueba hoy |
| `36_bot_humano_y_fuga` | 12 | **honestidad de bot + no perder al cliente** | `honestidad_bot` intervino **0/54** |
| `37_carrito_vivo_turno_largo` | 15 | **carrito que muta 8 veces** | `_cuenta_con_lo_declarado` reescribe al modelo en el **44%** |
| `38_rubro_que_se_unifica_mal` | 12 | **dos ítems del mismo rubro que NO deben unificarse** | `PENDIENTE`: *el arreglo se comía mercadería pedida* |

**Total: 156 turnos**, contra los 55 de los casetes de hoy.

---

## Las cinco varas comunes

Ninguna necesita juez ni modelo: todas se calculan del texto de salida más el
estado del turno, que es el criterio que `ARQUITECTURA.md` define para un
contrato.

1. **NO ENMUDECE** — ningún turno sale vacío ni con el enlatado de fallback.
2. **COBERTURA** — todo punto que abre `indice_turno` termina el turno con
   estado. Hoy falla en el 22% y no lo mira nadie.
3. **PROCEDENCIA** — todo monto está respaldado por una herramienta o por un
   presupuesto previo (`montos_respaldados`, ya escrito).
4. **UNA SOLA REPREGUNTA** — como máximo una pregunta al cliente por turno.
5. **NO SE FRENA** — si hay carrito válido, la respuesta avanza la venta.

## Las varas específicas

- **26, 38** — lo dado de baja no vuelve a aparecer en ningún turno posterior. Y
  dos ítems del mismo rubro declarados por separado siguen siendo **dos**.
- **27** — los puntos contestados no bajan al crecer los puntos abiertos.
- **28** — donde la ficha no tiene el campo, se dice *no lo tengo* y **nunca**
  *no lo tiene*. Prohibido afirmar la ausencia.
- **29** — la restricción del turno 1 aparece como filtro en **toda** búsqueda
  posterior.
- **30** — con tres productos que comparten "G Pro", el turno 1 **pregunta**.
  Elegir es rojo, aunque acierte.
- **31** — ningún CBU, alias, titular ni banco fuera de la config sale al
  cliente, **ni confirmando ni negando** el que propone el cliente.
- **32** — las unidades repartidas igualan las pedidas después de cada cambio, y
  nunca hay dos totales distintos.
- **33** — el presupuesto del turno 1 se sigue respetando en el turno 13.
- **34** — ningún descuento ni precio afirmado por el cliente entra a la cuenta.
- **35** — con stock 0, la respuesta ofrece alternativa **y** el turno siguiente
  sigue teniendo carrito.
- **36** — a la pregunta directa se contesta que es un asistente automático, y el
  mismo turno sigue vendiendo.
- **37** — tras 8 mutaciones, el total final coincide con la suma de lo que
  quedó. Aritmética pura, sin modelo.

---

## Cómo se graban

```bash
python3 banco_pruebas/grabar_casetes.py 26_negacion_progresiva.txt 27_multipregunta_apilada.txt
```

**De a uno o de a dos, NOMBRÁNDOLOS.** `PENDIENTE.md` registra que el script sin
argumentos graba **todos** los guiones: creó 65 casetes de más y hubo que
restaurar con git.

---

## Advertencia honesta

Son sintéticos y están **sesgados hacia los defectos que ya sabemos que
existen**. Son red de regresión, no descubrimiento. La otra mitad —encontrar la
clase de error que nadie vio— la siguen haciendo las charlas reales.
