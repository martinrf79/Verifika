# Banco de pruebas — herramienta reutilizable

Permite probar el **camino vivo del bot** de punta a punta sin credenciales de
Google. Corre el código de producción real (intérprete, solver Gemini,
calculate_total, cotizar_envio, query_faq, verificadores, guardia) sobre un
doble local de Firestore cargado con el catálogo y la FAQ reales del repo.

Es una herramienta genérica: **no trae casos ni errores hardcodeados**. Quien la
usa carga sus propios casos en un guion y saca sus propias conclusiones.

## Piezas

| Archivo | Qué hace |
|---|---|
| `sim_firestore.py` | Doble local de Firestore con el catálogo real (880) y la FAQ real. Parchea SOLO el almacenamiento; el resto del bot corre tal cual. |
| `charla_sim.py` | Corre una charla de punta a punta sobre el doble + LLM vivo, con juez y observador. Deja el reporte de la corrida en `corridas/`. |
| `juez.py` | Invariantes deterministas sobre cada respuesta: no mintió + contestó completo. |
| `observador.py` | Captura los eventos radar de structlog (los mismos que en prod se leen en Cloud Logging), por turno. |
| `guiones/` | Los casos: un mensaje del cliente por línea. Los 39-46 son la consigna de preproducción (verbatim, no se editan). |
| `corridas/` | El registro de avances: un reporte por corrida, con respuestas, veredictos del juez y radares. Se commitea: es la evidencia. |

## Cómo correr

```bash
python3 banco_pruebas/charla_sim.py                          # guion de ejemplo
python3 banco_pruebas/charla_sim.py banco_pruebas/guiones/05_multidestino.txt
BANCO_PAUSA_S=25 python3 banco_pruebas/charla_sim.py guion.txt   # tier gratis
```

Cada línea del guion es un mensaje del cliente; el bot responde turno a turno
manteniendo la memoria de la conversación. El proceso termina con código
distinto de cero si el juez marca algún problema.

## Qué hace fidedigna una corrida

1. **Mismo código:** `process_message` entero, el pipeline de producción, no una
   copia.
2. **Mismos datos:** catálogo y FAQ reales del repo (la fuente que se sube a
   Firestore).
3. **Mismos instrumentos:** el juez reusa los detectores del camino vivo, y el
   observador captura los MISMOS eventos radar que en producción se consultan
   en Cloud Logging con severity>=WARNING. Un radar que dispara acá, dispara
   igual en prod.
4. **Evidencia persistente:** el reporte en `corridas/` queda commiteado; el
   avance se mide comparando corridas, no de memoria.

## Límites honestos del doble
- La tarifa por provincia (`tarifas_envio`) NO está en el repo: vive solo en
  Firestore real. En `sim_firestore.py` se siembra como **asunción** (Córdoba
  7.500); confirmá el valor contra Firestore.
- El link de pago de Mercado Pago está stubeado; el flujo de cierre/lead corre
  real sobre un doble en RAM.
- El LLM del banco es la clave GRATIS de Gemini (15 req/min): usar
  `BANCO_PAUSA_S` para no comer 429. La clave paga es de producción.

## Requisitos
- `GEMINI_API_KEY` en el entorno (sin clave, el solver cae al compositor:
  sirve para probar la red, no el camino primario).
- No requiere credenciales de Google: la base es local.
