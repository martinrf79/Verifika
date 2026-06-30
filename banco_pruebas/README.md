# Banco de pruebas — herramienta reutilizable

Permite probar el **camino vivo del bot** de punta a punta sin credenciales de
Google. Corre el código de producción real (intérprete, solver, calculate_total,
cotizar_envio, query_faq, verificador, guardia) sobre un doble local de Firestore
cargado con el catálogo y la FAQ reales del repo, usando DeepSeek vivo.

Es una herramienta genérica: **no trae casos ni errores hardcodeados**. Quien la
usa carga sus propios casos en un guion y saca sus propias conclusiones.

## Piezas

| Archivo | Qué hace |
|---|---|
| `sim_firestore.py` | Doble local de Firestore con el catálogo real (880) y la FAQ real (44). Parchea SOLO el almacenamiento; el resto del bot corre tal cual. |
| `charla_sim.py` | Corre una charla de punta a punta sobre el doble + DeepSeek vivo. |

## Cómo correr

```bash
python3 banco_pruebas/charla_sim.py               # guion de ejemplo
python3 banco_pruebas/charla_sim.py guion.txt     # un mensaje por línea (tus casos)
```

Cada línea del guion es un mensaje del cliente; el bot responde turno a turno
manteniendo la memoria de la conversación.

## Límites honestos del doble
- La tarifa por provincia (`tarifas_envio`, ej Córdoba 7.500) NO está en el repo:
  vive solo en Firestore real. En `sim_firestore.py` se siembra como **asunción**;
  confirmá el valor contra Firestore.
- El cierre y el link de Mercado Pago están apagados en el doble: este banco apunta
  a la interpretación y la anti-alucinación, no al pago.

## Requisitos
- `DEEPSEEK_API_KEY` en el entorno.
- No requiere credenciales de Google: la base es local.
