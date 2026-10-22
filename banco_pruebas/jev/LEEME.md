# banco_pruebas/jev — Jev, el índice en niveles y las dos vueltas del modelo

El experimento del 22-oct, FICHA 75. Nada de esto está en el bot. Lo que se mide y lo que dio está en la ficha.

Jev necesita `TYPESAFE_API_KEY` en el entorno; cada llamada se anota con sus tokens en `gasto_jev.jsonl`. Gemini va
por `clon_produccion`, con la gratis por defecto y la paga solo con la marca de Martín, y queda en `libro_paga.jsonl`.

| Archivo | Qué hace |
| --- | --- |
| `captura.py` | Los 105 turnos de las 58 y las K con la libreta que vio el modelo y la agenda a mano: `turnos.jsonl` |
| `fuente.py` | La fuente entera como texto para Jev, y la llamada a Jev |
| `prueba.py`, `bateria.py`, `nota_bateria.py` | Jev sobre el mensaje crudo: qué rubros, reglas, datos y productos trae. `bateria_resp.jsonl.gz` |
| `vagas.py`, `redactadas.py`, `recorte.py`, `sondas.py`, `sondas2.py` | Las pruebas de lo que Jev hace bien y mal |
| `indice_jev.py` | El índice en niveles, armado con lo que ya hay en `data/`: rubros y temas; por rubro, campo y valores |
| `comparar_indice.py` | El índice contra la fuente entera |
| `calibrar.py` | Cuánto tiene que traer Jev desde el mensaje limpio |
| `vuelta1.py` | La primera vuelta de Gemini, el mensaje limpio, con Jev encima: consignas v1 a v4 |
| `reserva.py` | 24 mensajes nuevos con condiciones vagas, controlados contra los datos |
| `ronda2.py` | Las dos vueltas de punta a punta con el ejecutor de prueba, campo=valor por el índice |
| `gemini_jev.py` | La primera prueba, de una sola vuelta con el recorte de Jev |
| `casos_produccion.json`, `prod7.py` | Siete casos de las charlas reales del 15 al 21 de octubre, charla entera, con el modelo en cada turno |
| `arreglo_catalogo.py` | El arreglo de teclados y auriculares del commit faa0946. Ya aplicado: corrido de nuevo frena en sus asserts |
| `base_prod.json` | `regrado` de producción el 22-oct: 512 de 525 |
