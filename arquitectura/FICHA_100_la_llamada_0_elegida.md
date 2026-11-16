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

## 3. Lo que sigue, en este orden

1. **Pasar la llamada 0 del banco al modelo elegido con el v2**, en `banco_pruebas/flujo_nuevo.py`, y correr los nexos
   sobre lo nuevo: las búsquedas nuevas piden sus vectores y lo dudoso nuevo pide Jev. Se miran las fallas por causa.
2. **Lo contado dos veces en los mensajes de siete artículos**, K20 y K21: una línea por producto y otra por destino. Se
   resuelve con las cantidades y los destinos, después de la llamada 0.
3. **La memoria:** acoplar al flujo nuevo la del agente, `memoria_agente`, con el pedido anotado, lo mostrado, el pago y
   el tope, o una más efectiva si se mide mejor. Bancos: las 32 claves de memoria fuera de las 525, y K10, K11, K16 y K21.
4. **La segunda llamada, la que redacta**, con la vara de la FICHA 90.
5. Al pasar a `app/`: el modelo de la llamada 0 va en `app/config.py` y su clave en Secret Manager.

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
