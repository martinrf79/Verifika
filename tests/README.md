# Batería de regresión — el tablero de verdad del bot

Esta carpeta es la **fuente de verdad ejecutable** del proyecto. No es prosa que
se desactualiza: son tests que corren. Un test verde es un hecho comprobable, no
la opinión de nadie. El tablero de rojos es la lista de pendientes, y no puede
mentir ni quedar vieja porque la genera el código corriendo.

## Cómo se corre

```bash
pytest            # piso offline: Python puro, sin LLM, sin Google. Gratis y en segundos.
pytest -m vivo    # piso vivo: llama a DeepSeek. A propósito y en tanda. Gasta tokens.
```

Por default corre solo el piso offline (`addopts = -m 'not vivo'` en pyproject).
El CI de GitHub (`.github/workflows/test.yml`) corre ese mismo piso en cada push
y pull request: el juez es la plataforma, verde o rojo automático.

## Cómo se organiza — por ÁREA, una por herramienta del bot

Un archivo por área. Adentro de cada área, los errores confirmados son las
primeras semillas; a medida que se arregla cada uno, se suman casos vecinos y un
**camino feliz** que fija lo que sí funciona. Así el área crece hasta cubrir el
contrato entero de su herramienta, no un bug suelto.

| Área | Archivo | Herramienta del bot | Errores sembrados |
|---|---|---|---|
| Verificador de plata | `test_verificador.py` | `verificar_respuesta`, `_totales_derivables`, `decidir_accion_no_respaldado` | E1, E2, E7, A |
| Calculadora y total | `test_calculadora.py` | `calculate_total`, `calc_defensiva` | E5, E13 |
| Envío y zona | `test_envio.py` | `cotizar_envio` (CP / provincia) | locks (crece) |
| Cierre | `test_cierre.py` | `extraer_forma_pago`, `extraer_direccion` | E8, E9, E10 |
| Guardia de promesas | `test_guardia_promesas.py` | `detectar` | E3, E4 |
| Antijailbreak | `test_antijailbreak.py` | `evaluar_mensaje` | E12 |
| Identidad / certificador | `test_certificador.py` | `certificar` (Regla Cero) | E6, E15 |
| Cobro del cierre | `test_pago.py` | `elegir_medio_pago`, `mensaje_transferencia`, `instruccion_cobro` | CBU / MP |

E11 (teléfono en leads) y E14 (veto de negación en interpretador) se retiraron:
el teléfono y el DNI no se piden para la venta, los procesa Mercado Pago o el
banco, y el veto de negación se saca a propósito porque manda la interpretación
del LLM libre con filtros más abajo. Se borraron sus tests y su código muerto.

## Historial de la charla de WhatsApp (1-jul) — lo hecho y lo pendiente

Cuatro errores no graves reproducidos en el banco sobre el camino vivo. Cada uno
se asienta acá como contrato; el verde dice hecho, la fila sin archivo dice falta.

| Caso | Qué garantiza | Estado | Archivo |
|---|---|---|---|
| **A** | La melliza activa NO tira el canned cuando el solver repite un presupuesto ya calculado en memoria (sin tools ese turno). Bloquea solo sin evidencia en ningún lado. | ✅ verde | `test_verificador.py` |
| **B** | El criterio del cliente persiste como decisión: "lo más barato" se detecta con código, viaja por el estado y el solver no repregunta modelo ni color. | ✅ verde | `test_preferencias.py` |
| **C** | La provincia que el cliente dio viaja por el estado a todos los destinos: no se repide el CP de cada pueblo. | ✅ verde | `test_envio.py` |
| **D** | Gatillo de cierre: el bot hace UNA pregunta ("¿Seguimos adelante con tu pedido?") y la respuesta del cliente decide determinista, un no lo toma un humano, cualquier otra respuesta dispara el lead fuerte. Las dos versiones (avisar al cliente vs vender hasta el link) las gobierna `modo_cierre`. | ✅ verde | `test_cierre.py` |
| **D-pago** | En modo venta el bot cobra solo por el medio que el cliente eligió: CBU/alias de la tienda para transferencia, link de Mercado Pago para MP. El CBU sale de la config de la tienda; sin datos cargados, cae al humano. | ✅ verde | `test_pago.py` |

Cada pendiente arranca escribiendo su test en rojo, se arregla el código hasta el
verde y recién ahí pasa a hecho, sin dejar rojos en main.

## Dos pisos

- **offline**: lógica viva en Python puro. No llama a ningún modelo, no necesita
  credenciales. Es el que corre siempre. Cubre los 13 errores confirmados vivos,
  todos en verde.
- **vivo**: marcado `@pytest.mark.vivo`, usa el doble local de `banco_pruebas`
  con DeepSeek vivo. Para lo que sí depende de interpretación del modelo.

## La regla que sostiene todo

1. Un rojo se apaga arreglando su error; recién ahí se pasa al siguiente.
2. Nada se da por hecho sin que su test pase.
3. Nada se mergea en rojo (lo bloquea el CI).
4. Consolidar, no agregar: un cambio sin test no cuenta como hecho.

## Cómo se mantiene — contra el teléfono descompuesto

**Qué vive en un test.** Un solo contrato: dado este dato, el bot da este
resultado, porque esto importa. El *qué* es la afirmación, el *por qué* es el
docstring en una línea. NADA más: ni fechas, ni historia, ni estado. El *cuándo*
lo guarda git. Un test con fecha en el nombre es un diario disfrazado, no un test.

**Cómo se actualiza cada uno.** Un rojo tiene tres motivos y hay que distinguirlos:
1. El código está mal → se arregla el código, el test NO se toca.
2. El requisito cambió a propósito → se cambia la afirmación, y el commit explica
   el nuevo requisito. Es el único motivo legítimo para editar lo que un test espera.
3. El test prueba algo equivocado o repetido → se borra.

**Regla de oro:** nunca edites un test para que pase. Editás el código para que
pase, o editás el test porque el requisito cambió de verdad. Confundir esas dos
cosas es el momento exacto en que entra la mentira. Una afirmación cambiada en un
diff SIEMPRE lleva su porqué en el commit.

**Archivos que no crecen sin fin.** El archivo crece con contratos nuevos, no con
variaciones. Muchas formas de decir lo mismo = una TABLA de casos
(`pytest.mark.parametrize`), no muchas funciones. Ver `test_cierre.py` como
plantilla: agregar un caso visto en WhatsApp es agregar una FILA. Un archivo = una
herramienta del bot; si no se describe en una frase, son dos archivos.

**Podar, no solo sumar.** Cada arreglo pregunta si deja algún test viejo de más.
Cuando se consolida un camino, se borran en el MISMO commit los tests del camino
que se sacó. Un test de código muerto es un test muerto.

**Una autoridad por cada cosa.** El test dice cómo se comporta el bot. El README
es el mapa (dónde), no describe comportamiento. CLAUDE.md son las reglas. RESUMEN
es el foco de hoy. No hay un quinto documento que describa comportamiento. Si un
dato de comportamiento no está en un test, es una opinión, no un hecho.

## Cómo arranca un chat nuevo

Leer `CLAUDE.md` (reglas) y `RESUMEN_PARA_NUEVO_CHAT.md` (estado), y correr
`pytest` para ver qué está en rojo. Con eso el chat arranca sabiendo todo y sigue
por el próximo rojo, sin re-investigar ni quemar tokens.
