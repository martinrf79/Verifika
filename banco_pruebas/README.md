# EL BANCO — cómo se mide Verifika

Referencia única de cómo se prueba el bot. Si un documento viejo dice otra cosa,
manda este.

**La regla que nació el 2-ago-2026, después de cinco sesiones seguidas
declarando "ahora sí anda":** ninguna sesión declara verde sin un número que
salga de una charla real, y el número se reporta **con su control al lado**. Un
número solo, sin el antes, no dice nada.

---

## EL MARCADOR, antes que las capas — `python3 banco_pruebas/las_40.py`

**El único número que dice si el proyecto avanzó.** Las 40 pruebas reales de
Martín —25 sueltas y 15 series— listadas con nombre y con la fuente de cada una,
y por cada una la prueba de su parte de **CÓDIGO**: que la herramienta entregue
el conjunto correcto, el número exacto o el "no sé" honesto. Cero tokens, dos
segundos, y `tests/test_las_40.py` lo corre en cada push, así que la pregunta
que se rompa vuelve con nombre y apellido.

No mide cómo **redacta** el modelo: eso es la fase siguiente. Los casos no se
duplican, se delegan a `banco_candidatos.py` y `banco_memoria.py`, que siguen
siendo el lugar donde se define cada uno.

---

## Las tres capas, y qué prueba cada una

### 1. Offline — `python3 -m pytest tests/ -q`
Sin LLM, sin credenciales, sin red. 413 tests sobre las piezas deterministas:
calculadora, envío, stock, compatibilidad, certificador, pagos, memoria,
multi-tenant, contratos de herramientas.

**Lo que NO prueba, y hay que tenerlo claro:** no le habla al modelo. Su verde
nunca dijo nada sobre cómo contesta el bot. Un verde acá no autoriza un deploy.

### 2. Vivo — `banco_atado_charlas.py`
Una pasada por guion contra el modelo real, para mirar una charla entera con los
ojos.

```bash
export GEMINI_API_KEY=$GEMINI_API_KEY_PROD
python3 banco_pruebas/banco_atado_charlas.py banco_pruebas/guiones/07_*.txt
```

**No sirve para concluir.** El modelo no es determinista: la misma pregunta
elige otras herramientas en cada pasada. Una corrida buena y la siguiente rota
es lo normal, no la excepción.

### 3. Repetido, con compuerta — `banco_repetido.py`
**El único que autoriza a decir que algo mejoró.** Corre cada guion N veces por
el camino real del webhook, calcula las cuatro métricas y las compara contra el
piso histórico.

```bash
export GEMINI_API_KEY=$GEMINI_API_KEY_PROD
python3 banco_pruebas/banco_repetido.py                            # el set del piso
python3 banco_pruebas/banco_repetido.py 5 '7?_*.txt'               # compara
python3 banco_pruebas/banco_repetido.py 5 '7?_*.txt' --fijar-piso  # graba piso
```

Sin guiones corre **los que grabó el piso**, que es contra lo que compara la
compuerta. Si el default fuera el glob, cada guion nuevo movería el set y la
comparación pasaría a ser orientativa sin que nadie se entere.

Sale con código 1 si una métrica **dura** empeoró. Es lo que corre el CI: el
workflow `calidad.yml` lo dispara todas las noches a las 06:00 UTC con la clave
gratis de Gemini y a mano desde Actions. Un rojo ahí es una regresión medida, no
un aviso.

---

## El clon: por qué el banco es fiel

`clon_produccion.py` no llama a `procesar_venta` por atajo: entra por
`app.main._process_and_reply_whatsapp`, **la función real del webhook de
WhatsApp**. Adentro corre el mismo código que la nube: orchestrator,
antijailbreak, `hub_venta`, herramientas, reconciliador, memoria, persistencia,
cierre, partición del mensaje en partes y hasta el fallback de "estoy con mucha
demanda".

Solo se doblan los bordes externos:

| Borde | En producción | En el banco |
|---|---|---|
| Meta | HTTP a la API de WhatsApp | `ConectorBanco` guarda los mensajes |
| Firestore | Firestore real | `sim_firestore` en RAM, con el catálogo de 880 y la FAQ **reales** del repo |
| Audio | transcripción | no se ejercita, el banco manda texto |

`verificar_clon.py` confirma que el doble no derivó del repo.

**Por qué importa:** hasta el 31-jul el banco llamaba a `procesar_venta` directo
y se salteaba el partido del mensaje, así que el juez leía un bloque entero que
el cliente nunca recibe entero. Ese era el abismo entre "el banco da verde" y
"en WhatsApp falla".

---

## Las cuatro métricas — `piso.py`

Se calculan sobre todos los turnos de todas las vueltas.

**Duras. La compuerta frena si empeoran más de 5 puntos:**

- `sin_caida` — el turno no explotó ni cayó al fallback.
- `sin_invento` — ningún invariante del juez violado: stock contradicho, precio
  falso, promesa prohibida, cobro inventado.

**Blandas. Avisan, no frenan, porque son más ruidosas:**

- `completa` — cumplió las expectativas escritas en el guion.
- `avanza` — la respuesta mueve la venta: trae un precio o pregunta algo. Un
  muro honesto tipo "no tenemos nada" **no avanza**.

Más latencia p50 y p95.

### Por qué hicieron falta las blandas
El juez sólo tenía invariantes negativos: mide que no mienta sobre el catálogo,
que es justo lo que ya estaba resuelto. Medido el 2-ago sobre un pedido real de
seis ítems: el bot cotizó cuatro categorías sobre un pedido de tres, inventó un
teclado, borró un auricular e ignoró la condición que el cliente puso, y el juez
dijo **LIMPIO**, porque ninguna de esas cuatro fallas es una mentira sobre el
catálogo. Por eso "0% de fallo" convivía con "en WhatsApp se cae la venta".

---

## El piso histórico — `piso.json`

Guarda el mejor número alcanzado, con fecha, commit, modelo, guiones y cuántas
vueltas se usaron.

**El piso vigente se fijó el 3-ago-2026 sobre `main`, commit `3c18608`, modelo
`gemini-3.1-flash-lite`:** 78 turnos, `sin_caida` 100%, `sin_invento` 97,4%,
`completa` 93,6%, `avanza` 96,2%, latencia p50 5283 ms y p95 9453 ms, sobre los
ocho guiones `70` a `76`. **Se fijó con 3 vueltas, no con 5, así que arrastra
ruido:** el propio reporte lo avisa, y volver a fijarlo con 5 vueltas sigue
pendiente.

Se graba **a mano** con `--fijar-piso`, y eso es a propósito: si el piso se
moviera solo en cada corrida, una regresión lenta se volvería el piso nuevo y
nadie la vería nunca.

**El ruido es real y no se tapa.** Con 5 vueltas, un turno de diferencia son 20
puntos. Por eso la compuerta tiene 5 puntos de tolerancia y el reporte avisa
cuando el piso se fijó con menos de 5 vueltas. Un piso de 3 vueltas no autoriza
a nadie a declarar nada.

---

## Los guiones

En `guiones/`. Un mensaje del cliente por línea, y las expectativas del turno
con `>`:

```
quiero 2 mouse genius dx-110 negro y 1 teclado, cuanto sale?
> contiene: Total
no, el teclado sacalo, dejame solo los mouse
> no_contiene: teclado Genius | 1x Teclado
```

En `contiene`, el `|` son alternativas: alcanza con que aparezca una.

El más duro es `76_pedido_multiple_criterio_no_binario.txt`: un mensaje real de
Martín con cuatro trampas juntas, seis ítems en tres categorías, una
contradicción a propósito entre lo pedido y los envíos, un criterio que no es
binario, y una frase que invita a malinterpretar el precio.

**Lo que falta, dicho:** guiones de dificultad alta hay uno solo. Sin más, la
dificultad alta no se puede medir, y lo que no se mide no se mejora.

---

## DeepEval: se fue con el flujo atado (4-ago-2026)

Existía `banco_deepeval.py`, que le ponía número a cada respuesta con juez
DeepSeek, y el workflow `deepeval.yml` que lo corría de noche. El runner se
borró el 1-ago junto con el flujo atado que medía, pero el workflow siguió
llamándolo: **cuatro noches en rojo por `No such file or directory`**, y el
correo del rojo llegando igual.

Se consolidó en una sola compuerta: el nocturno es ahora `calidad.yml` y corre
`banco_repetido.py` contra el piso, que es la medición del camino que de verdad
corre. Se fueron con él `juez_deepeval.py` y `requirements-eval.txt`, que ya no
los usaba nadie.

---

## Límites honestos

- La tarifa por provincia no está en el repo, vive solo en Firestore real. En
  `sim_firestore.py` se siembra como **asunción**; confirmalo contra Firestore.
- El link de pago de Mercado Pago está stubeado.
- La clave gratis de Gemini son 15 pedidos por minuto: usar `BANCO_PAUSA_S` para
  no comer 429, o la clave paga vía `GEMINI_API_KEY_PROD`.
- El audio no se ejercita.

---

## Lo aprendido, para no repetirlo

- **Agregar reglas al prompt no agrega control.** El 2-ago se agregó una regla
  para tapar un caso: `avanza` bajó de 3/5 a 2/5 y `sin_invento` de 5/5 a 4/5.
  Se revirtió. Después se sacaron 14 reglas y `avanza` subió a 5/5. De las 20
  reglas viejas, 19 no compraban nada y una sí.
- **El modelo no era el cuello de botella.** `gemini-3.6-flash` contra
  `gemini-3.1-flash-lite`, 5 pasadas cada uno: idénticos en las tres columnas.
  `gemini-3.1-pro-preview` razona mejor pero tarda 94 segundos: descartado para
  WhatsApp.
- **Un run no es un veredicto.** Nunca. Ni el bueno ni el malo.
