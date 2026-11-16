# FICHA 100 — La llamada 0 elegida: el prompt v2 y el modelo nuevo; los cinco nexos cerrados

16-nov-2026, sesión con Martín. Sigue a la FICHA 99. **Escrita para que una sesión nueva siga sin volver al chat.** Lo
hecho, en `git log` del 16-nov; los números, en los commits que graban cada corrida.

---

## 1. Lo que decidió Martín el 16-nov

1. **La llamada 0 cambia de modelo:** al que dio la medición completa, `llamada0_modelos.MODELOS["luna"]`, con
   razonamiento bajo. Su clave directa está en el entorno y anda; por OpenRouter queda poco saldo.
2. **El prompt de la llamada 0 es el v2**, `llamada0_modelos.PROMPTS["v2"]`: una línea por producto o variante, la
   condición en la búsqueda de cada línea, también la que vale para todo el mensaje, y lo corregido no cuenta.
3. **Los cinco nexos quedan cerrados por ahora**, salvo arreglos menores. Lo que sigue es la memoria y la segunda
   llamada, la que redacta.

## 2. Lo medido, sin modelo después de la llamada 0

Las varas se escribieron antes de correr, en `banco_pruebas/llamada0_vara.py`, y la corre
`banco_pruebas/llamada0_modelos.py`. Una corrida por modelo, salvo donde se dice.

| Qué | La llamada 0 de hoy | Prompt v2, modelo de hoy | Prompt v2, modelo elegido |
| --- | --- | --- | --- |
| Las 140: mensajes sin falla | 128 | 134 | 135 |
| Las 140: mensajes bien separados | 139 | 139 | 137 |
| Las 365: condiciones en la búsqueda, de 200 sin memoria | 121 | 191 | 200 |
| Las 365: perdidas al separar / al traducir | 58 / 21 | 7 / 2 | 0 / 0 |
| Los 40 reales: condiciones en la búsqueda, de 16 | 5 | 14 | 14 |
| Las 365: rubro pedido en el primer candidato, de 320 | 316 | — | 315 |
| Las 365: duplicadas / contadas dos veces / inventadas | 6 / 24 / 3 | 11 / 14 / 6 | 6 / 17 / 4 |
| Segundos por mensaje, las 140 | 4,3 | 10,8 | 3,4 |

- **Dónde se perdía la condición:** casi toda al separar, dicha una vez para todo el mensaje, "los más baratos", "las
  menos partes chinas", y no llegaba a cada línea. Embeddings y Jev sobre líneas ya separadas no lo arreglan: el v2 sí.
- **Los embeddings con el fragmento y la búsqueda juntos** traen el rubro correcto entre 8 productos en 189 de 189 de
  las 140, `banco_pruebas/embeddings_candidatos.py`. La jerga sin traducir casi no llega como falla al final.
- **Jev no separa:** elige de listas cerradas. Sirve para confirmar lo dudoso, como ya hace en los nexos.
- **Lo que no sirvió:** el prompt v3, primero los productos y las condiciones en lista con un ejemplo, empeora: copia
  las palabras del cliente en vez de traducir. Tres corridas. Qwen 3.8 con razonamiento piensa hasta 210 segundos por
  mensaje; sin él inventa condiciones. El mismo modelo con razonamiento medio no mejora.
- **La variación:** el modelo de hoy cambia hasta 7 mensajes de 140 entre corridas. Las diferencias chicas de la tabla
  no separan modelos; las de las 365 sí.
- **Lo que la vara cuenta y no es falla:** las inventadas son casi todas tipeos del cliente que el modelo corrige,
  "inlaambrico"; el rubro de más es sobre todo C14 y C37, que preguntan por memorias sin buscar.

## 3. Lo que sigue, en este orden, orden de Martín del 16-nov

El flujo nuevo vive solo en el banco y pasa a `app/` todo junto, de una vez, cuando el camino completo supere al agente
en las mismas charlas. Hasta entonces no se toca producción. Para que no se pierda nada:

1. **Ordenar, la sesión que sigue.** Juntar el flujo nuevo en una sola carpeta, `banco_pruebas/flujo/`: un archivo por
   paso, llamada 0, cada nexo, Jev y redactar; las grabaciones en una subcarpeta; los vectores en un lugar fijo y no en
   el scratchpad de una sesión. Cortar las dependencias del banco viejo, sección 5. Se comprueba que todos los números
   salgan iguales que hoy, sin gasto, antes y después de mover. `MAPA.md` apunta a la carpeta.
2. **Los nexos sobre la llamada 0 elegida.**
   - Cambiar la llamada 0 de `flujo_nuevo.py` al modelo de `llamada0_modelos.MODELOS["luna"]` con el prompt v2, por la
     clave directa de OpenAI.
   - Correr los cinco nexos sobre lo nuevo: las búsquedas nuevas piden sus vectores y lo dudoso nuevo pide Jev.
   - El nexo de rubro con lo medido en `embeddings_candidatos.py`: consulta con el fragmento y la búsqueda juntos, y 8
     candidatos en vez de 5; Jev elige entre ellos en lo dudoso.
   - Se miran las fallas por causa y se calibra cada nexo con su `--calibrar`, de a una cosa, con la confirmación en
     los bancos que no se usaron.
3. **Lo contado dos veces en los mensajes de siete artículos**, K20 y K21: una línea por producto y otra por destino. Se
   resuelve con las cantidades y los destinos, después de la llamada 0.
4. **La memoria:** acoplar al flujo nuevo la del agente, `memoria_agente`, con el pedido anotado, lo mostrado, el pago y
   el tope, o una más efectiva si se mide mejor. Bancos: las 32 claves de memoria fuera de las 525, y K10, K11, K16 y K21.
5. **La segunda llamada, la que redacta**, con la vara de la FICHA 90, citando por número lo que dieron los nexos.
6. **El camino completo contra el agente**, en las mismas charlas: `tests/test_agente.py` y las corridas con el modelo.
   Si lo supera, pasa a `app/` reemplazando al agente: el modelo de la llamada 0 en `app/config.py`, su clave en Secret
   Manager, los índices de la tienda calculados al subir el catálogo y la FAQ, y el cobro, el cierre y el verificador.

## 4. Cómo se corre

```bash
python3 banco_pruebas/llamada0_modelos.py                  # las 140, sin gasto
python3 banco_pruebas/llamada0_modelos.py --reales         # los 40 reales y las 365: dónde se pierde la condición
python3 banco_pruebas/llamada0_modelos.py --sobra --ver    # lo que sobra y lo inventado
python3 banco_pruebas/llamada0_modelos.py --correr luna v2 --banco reales525   # con gasto, retoma lo que falta
python3 banco_pruebas/embeddings_candidatos.py --informe   # cuántos candidatos hacen falta, de lo grabado
```

Gasto de la sesión: unos 30 centavos de la paga de Gemini, anotados en `libro_paga.jsonl`; 15 de OpenRouter; unos 30
entre Haiku y DeepSeek por sus claves.

## 5. Inventario del flujo nuevo al 16-nov: dónde está cada cosa

Todo en `banco_pruebas/`, salvo la fuente de la tienda, que está en `data/clientes/verifika_prod/`.

| Paso | Código | Grabado, para repetir sin gasto |
| --- | --- | --- |
| El flujo de punta a punta | `flujo_nuevo.py` | `flujo_nuevo_llamada0.jsonl`, `flujo_nuevo_puntajes.json`, `flujo_nuevo_respuestas.json` |
| Cómo busca cada nexo, el registro | `busquedas.py` | — |
| La llamada 0: prompts, modelos y varas | `llamada0_modelos.py`, `llamada0_vara.py`, `engranaje0.py` | `llamada0_modelos.jsonl`, `engranaje0_corridas.jsonl` |
| Cuántos candidatos hacen falta | `embeddings_candidatos.py` | `embeddings_candidatos_rangos.json`, `embeddings_candidatos_rangos_reales.json` |
| Nexo de rubro y producto | `nexo_rubro.py` | `nexo_rubro_puntajes.json`, `nexo_rubro_jev.jsonl`, `nexo_rubro_respuestas.json` |
| Nexo de tema de la FAQ | `nexo_tema.py` | `nexo_tema_puntajes.json`, `nexo_tema_dudoso.jsonl` |
| Nexo de producto nombrado | `nexo_nombrado.py`, `nombrados38.py` | `nexo_nombrado_puntajes.json`, `nexo_nombrado_llamada0.jsonl` |
| Nexo de condición | `nexo_condicion.py`, `nexo_condicion_vara.py` | `nexo_condicion_puntajes.json`, `nexo_condicion_jev.jsonl`, `nexo_condicion_respuestas.json` |
| Nexo de destino | el código de producción, `app/core/flujo/normal.lugares` y `app/core/fuente._cotizar`, desde `flujo_nuevo.nexo_destino`; antecedente en `nexo_destino.py` | — |
| Jev | `nexo_tema.llamar_jev`; la API y el índice en `jev/` | `jev/gasto_jev.jsonl` |
| Las 140 | `nuevas70.py`, `nuevas70b.py`, `momento0_b.py` | `momento0_b_corridas.jsonl`, `momento0_b_puntajes.json` |
| Los 40 reales y las 365 | `reales.py`, `agendas58.py`, `traduccion58.py`, `vara_58.json` | `reales_llamada0.jsonl`, `reales_puntajes.json`, `reales_jev.jsonl` y lo mismo con `reales525` |
| El gasto | `libro_paga.py`, `costo.py` | `libro_paga.jsonl`, `jev/gasto_jev.jsonl` |

**Lo que hay que cortar al ordenar:** `nexo_rubro.py` usa `camino_fijo.py`; `llamada1_modelos.py`, de donde sale la
función de embeddings `_emb`, usa `separar_charlas.py` y `clon_produccion.py`; `reales.py` usa `traduccion58.py`, que
usa `cableado58.py`. Son del banco viejo y no van a `app/`.

**Los vectores:** `nexo_rubro.CACHE`, `nexo_tema.CACHE` y `nexo_nombrado.CACHE` apuntan al scratchpad de una sesión que
ya no existe; `embeddings_candidatos.CACHE` a `/tmp`. Los puntajes grabados alcanzan para repetir los números; lo nuevo
pide vectores, unos centavos por la paga o lento por la gratis.

