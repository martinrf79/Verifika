# FICHA 73 — Los avisos: la información justa, dada solo donde falla

21-oct-2026, sesión con Martín. Viene de la 70 y de `banco_pruebas/traduccion58.py`. **Es un experimento del banco:
nada de esto está en el bot.** El código y los datos están en `banco_pruebas/avisos/`.

## El resultado

La vara es la de `traduccion58.py`: los 105 turnos de las 58 y de las K, en cinco formas —original, plana, WhatsApp,
redactada y coloquial—, 525 casos calificados con las casillas de `vara_58.json` por el flujo entero. Los turnos
anteriores de cada charla van con la agenda a mano, así la memoria es la correcta y se mide solo la traducción.

| paso | casos bien | rompe |
|---|---|---|
| producción | 455 | |
| la tabla mejorada de la sesión anterior, `TRAD_IDEAL=tabla` | 468 | 2 |
| **más 17 avisos de clase, con devuelta solo donde saltan** | **521** | **0** |

Los avisos saltan en 53 de los 525 casos, todos casos que fallaban. En los otros 472 la entrada no cambia y el modelo
ni se vuelve a llamar. Ningún caso recibe avisos de dos tandas distintas, así que puestos todos juntos dan lo mismo que
medidos por tanda: `candidatos.solapados()`.

**Lo que esto no prueba todavía.** Los avisos se escribieron mirando estas fallas. Dentro de las 525 no tocan ningún caso
que anda, pero falta una reserva: formas nuevas, escritas antes de correr, que no se usen para ajustar.

## El método, que es lo que vale

Un **aviso** es un control determinista sobre la primera traducción del modelo. Mira la agenda, el estado de la charla
y la fuente de la tienda, y si encuentra un error de clase lo dice en palabras, con el dato que lo corrige. El aviso va
en la devuelta que el intérprete ya tiene, `interprete.DEVUELTA`, junto a las faltas de cita.

Un aviso **entra** solo si cumple las tres cosas, en este orden:

1. **Se mide sin modelo, gratis.** Sobre la primera traducción grabada de las 525: en cuántos casos que fallan salta,
   en cuántos que andan y en cuántos ya arreglados por otro aviso. `candidatos.medir_primera(...)`.
2. **No salta en ningún caso que anda.** Si salta, se acota con un dato de la fuente o del estado, nunca con una lista de
   palabras, y se vuelve a medir. Si no se puede acotar, no entra.
3. **Se corre la devuelta solo donde salta**, como repetición: la primera traducción es la grabada, idéntica, y se agrega
   la devuelta con el aviso. `replay.py`. Entra si arregla.

Con temperatura cero, el modelo de producción traduce siempre igual la misma entrada. Medido: 60 casos corridos dos
veces dieron agendas idénticas palabra por palabra. Por eso lo que no recibe aviso no puede cambiar: no rompe por cómo
está armado, no por suerte.

Cuesta una segunda llamada en uno de cada diez mensajes.

## Los 17 avisos que entraron

| aviso | qué detecta | de dónde sale el dato | casos |
|---|---|---|---|
| `vacio` | cambia, saca o confirma renglones con el pedido vacío | el borrador | C34 en tres formas |
| `traba` | busca entre lo mostrado y por eso una condición no se aplica, que en la tienda sí | `catalogo.buscar` con y sin lo mostrado | C46 en tres formas |
| `suma` | pide la cuenta con lo buscado y el pedido vacío | el borrador y la agenda | K03 redactada |
| `dos_lugares` | un envío a un destino que nombra dos lugares | `envio.clasificar_provincia` | C26 en tres formas |
| `color_invalido` | cambia un color a algo que no es un color de la tienda | el catálogo | K21 T6 |
| `ultimo_de_muchos` | señala el último de tres o más mostrados sin nombrar cuál | la libreta y el marcador | C52 en cuatro formas |
| `envio_sin_cuenta_libreta` | precio y envío a la localidad de la libreta, sin cuenta | la libreta | C47 en cinco formas |
| `confirma_completo` | el mensaje solo confirma renglones que no tienen nada pendiente: es una cuenta | `borrador.faltantes` | K21 T3 y T5, diez casos |
| `politica_envio_con_destinos` | pregunta la regla de envíos cuando el pedido del mensaje ya tiene destinos | la agenda | C26 plana y redactada |
| `campo_inventado` | una compra con un campo que no existe | el menú de `agenda.ACCIONES` | C56 en cuatro formas |
| `elegir_por_dato` | lista dos productos nombrados con un dato que la tienda filtra: un producto por cada uno y la compra con si | `catalogo.atar` | C32 en cinco formas |
| `cuenta_sin_pedido_consultas` | la cuenta con el pedido vacío y las cantidades puestas como dato de un producto | la agenda | C25 WhatsApp |
| `repite_lo_mostrado` | soltó todas las condiciones de la búsqueda anterior y trae solo lo ya mostrado | `catalogo.buscar` y el estado | C35 en cuatro formas |
| `compat_rubro_con_dato` | compatibilidad de un rubro con un dato del equipo: es una búsqueda con esa condición | el catálogo | C54 en tres formas |
| `agrega_con_campo` | una compra cuyo artículo trae un campo de búsqueda, como el orden | el menú | K21 T2 |
| `cantidad_cero` | anota artículos con cantidad cero en vez de "los otros" | la agenda | K07 WhatsApp |
| `porcentaje_como_politica` | con el pedido armado, un porcentaje con un medio va como política y no como reparto | el borrador | K21 T6 WhatsApp |

Los tres primeros están en `seguros.py`; los otros catorce en `candidatos.py`, lista `SEGUROS`.

**Los que no entraron**, porque saltan también en casos que andan: `confirma_completo` sin acotar, `compat_contradice`,
`lista_nombrada`, `monto_suelto`, `uno_de_muchos`, `uno_de_muchos_sin_rubro` y `pedido_sin_cuenta`.

## Lo que queda: 4 casos

- **C30 original y coloquial.** Es del código, no de la traducción. La herramienta de compatibilidad da "compatible" a una
  memoria DDR4 con "una PC de escritorio con placa DDR5": reconoce la PC y no usa el DDR5, aunque la ficha del producto
  dice que en una placa DDR5 no entra. Con la condición "si no le sirve", la búsqueda de DDR5 no corre. Ninguna
  traducción lo arregla sin tocar `app/`.
- **C52 redactada,** "¿y cuánto cuesta ese?" con doce mostrados: el modelo elige el M-10. El aviso que lo cubre salta
  también en C49 T3 WhatsApp, que anda.
- **K20 WhatsApp:** la respuesta no avisa que el teclado no estaba en la lista. Sin señal limpia todavía.

## Lo que se probó antes, y por qué no se usa

Todo sobre los 20 turnos más difíciles en tres formas, 60 casos. Producción da 24.

| variante | de 60 | qué cambia |
|---|---|---|
| pistas: el modelo pide al código qué es cada palabra, y traduce con la consigna de hoy | 10 de 20, solo la original | dos llamadas |
| pistas y un idioma de comandos, un renglón por cosa pedida | 35 | |
| más el esquema de datos de cada rubro, avisos y una tercera vuelta | 36 | |
| lo mismo sin frases de los turnos medidos en los ejemplos | 39 | |
| **más fichas por tipo de respuesta: cuándo va y cuándo no** | **43** | |
| fichas reescritas por el propio modelo | 36 | |
| fichas más un banco curado que rota | 43 | |
| con avisos de clase en la tercera vuelta | 60 | |

**Las 525 con ese método dieron 491: arregla 68 y rompe 32.** Cambia la entrada de todos los mensajes —consigna, pistas,
formato— y eso rompe por construcción. Unos 15 de los 32 eran un error del traductor de comandos a agenda: no leía
"70 por ciento" ni "mitad". Queda en `comandos525.jsonl` como referencia.

Lo que dejó: qué información resuelve cada clase. De ahí salieron los avisos.

## Las entrevistas al modelo

`entrevista.json` y `entrevista2.json`, con el modelo de producción.

- **El modelo se desconoce.** Preguntado por qué falla o qué lo ayudaría, contestó casi lo mismo para doce tipos de caso:
  esquema, validación, no inventar. Sus fichas propias rindieron menos que las nuestras.
- **Lo útil salió de lo que hizo y de lo que pidió, no de lo que opinó.** Desde cero, con su propio formato, tradujo bien
  casos que con la consigna fallaba. Y pidió tres cosas: que le digan si el pedido está vacío, que le avisen cuando una
  referencia tiene varios candidatos, y que el código le diga cuando algo no se puede cumplir. Eso son los avisos.
- **Al modelo no se le pregunta: se lo prueba.** Se le cambia la información en un caso, se mide, y queda lo que funciona.

## Lo que sigue

1. **DeepSeek con el mismo método.** `traduccion58_corridas.jsonl` ya tiene las 525 de DeepSeek, una vez cada una. Se
   miden sin modelo los 17 avisos sobre esas traducciones, se corre la devuelta solo donde saltan, y se compara. Sirve
   también para ver si los avisos son de clase: no se escribieron mirando a DeepSeek.
2. **Los 4 que quedan**, sin romper. C30 pide arreglar la herramienta de compatibilidad, en `app/` y con el ok de Martín.
3. **Una reserva:** formas nuevas de las complejas, escritas antes de correr. Es lo de ESPERA A MARTIN en `PENDIENTE.md`.
4. **Llevarlo al bot**, con su ficha y el ok de Martín: la tabla de `traduccion58._tabla_ideal` pasa a `flujo/marcador.py`,
   y los avisos van como faltas de la devuelta en `interprete.interpretar`. Cada aviso con su test.

## Cómo se repite

Todo desde la raíz del repo. La paga necesita la orden de Martín en la sesión.

```bash
python3 banco_pruebas/avisos/seguros.py --ver           # sin modelo: donde saltan los tres primeros
python3 -c "import sys; sys.path.insert(0,'banco_pruebas/avisos'); import candidatos as C; C.medir_primera(C.SEGUROS)"
python3 -c "import sys; sys.path.insert(0,'banco_pruebas/avisos'); import candidatos as C; C.solapados()"
python3 banco_pruebas/avisos/replay.py <nombre> <aviso> [<aviso> ...]   # la devuelta, solo donde saltan
python3 banco_pruebas/avisos/informe525.py              # las 525 del método de comandos
```

`base521.json` es el estado final de las 525: para cada caso, de dónde sale la traducción, la agenda, la nota y las
casillas que fallan. `replay.py` y `medir_primera` lo leen por defecto.

## Dónde está cada cosa, en `banco_pruebas/avisos/`

| archivo | qué es |
|---|---|
| `contexto.py` | arma, sin modelo, lo que ve el intérprete en un turno, y la llamada al modelo |
| `seguros.py` | la base de la sesión anterior y los tres primeros avisos |
| `candidatos.py` | los demás avisos, la medición sin modelo y los solapamientos |
| `replay.py` | la devuelta como repetición, solo donde saltan los avisos |
| `base521.json` | el estado final de las 525 |
| `pistas.py`, `comandos.py`, `variante3.py`, `limpio.py`, `fichas.py`, `banco.py`, `opciones.py`, `vuelta2.py` | el método de comandos, que no se usa |
| `fichas_gemini.py`, `fichas_gemini.txt` | las fichas reescritas por el modelo |
| `comandos525.jsonl`, `informe525.py`, `tabla.py`, `comparar.py` | sus resultados |
| `entrevista.py`, `entrevista2.py`, `entrevista.json`, `entrevista2.json`, `casos6.pkl` | las dos entrevistas |

**Gasto de la sesión:** cerca de 1,80 dólares de la paga, con el tope subido a 4 por orden de Martín para el día.
