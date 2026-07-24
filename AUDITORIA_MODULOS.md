# Auditoría de Módulos — Fase 1 (24-jul-2026)

## TL;DR

| Módulo | Líneas | Vivo en prod | Tests que lo usan | Para borrar |
|---|---|---|---|---|
| `app/core/interprete_libre.py` | 2236 | **NO** | 9 archivos / ~25 imports | Mover 8 funciones a `pedido_helpers.py` / `generador_v2.py` / nuevo módulo |
| `app/core/solver_gemini.py` | 500 | **NO** | 2 archivos / 3 imports | Mover 3 funciones a módulos vivos |

---

## 1. `interprete_libre.py` (2236 líneas)

### ¿Dónde vive?
`app/core/interprete_libre.py`

### ¿Lo usa algún módulo de producción?
**No.** Ningún `import` desde `app/core/`, `app/connectors/`, `app/main.py`, `app/storage/` ni `app/verifika/`.

El camino vivo es: `orchestrator.py` → `hub_atado.py` → `generador_v2.py` / `compositor.py`.

### ¿Qué tests lo importan?

| Archivo de test | Qué importa | Función en uso real |
|---|---|---|
| `test_consigna_llaves.py` | `_mensaje_con_contenido`, `_sin_sustancia` | Lógica de piso de composición |
| `test_guia_pedido.py` | `_forzar_opciones_si_presupuesto` | Forzado de opciones en presupuesto |
| `test_estres_correcciones.py` | `_estampar_productos` | Estampado de productos en texto |
| `test_criterio_concordancia.py` | `_es_afirmacion_barato` | Detección de afirmación "barato" |
| `test_saludo.py` | `_con_saludo_inicial`, `_asegurar_honestidad_bot`, `_RE_DESTINO_UNICO` | Saludo + honestidad + regex destino |
| `test_fiscal_niveles.py` | `_con_saludo_inicial` | Saludo en respuesta fiscal |
| `test_curadas.py` | `_fallback_o_curada` | Fallback vs curada en FAQ |
| `test_guarda_producto.py` | `_reanclar_si_producto_divergente`, `_resolver_nombre_a_producto` | Re-anclado de producto divergente |

> Nota: `_resolver_nombre_a_producto` YA fue movido a `pedido_helpers.py`; `interprete_libre.py` lo re-importa desde allí.

### Funciones exportadas que usan los tests

```
_mensaje_con_contenido      → test_consigna_llaves.py
_sin_sustancia              → test_consigna_llaves.py, test_consigna_llaves.py
_forzar_opciones_si_presupuesto → test_guia_pedido.py × 2
_estampar_productos         → test_estres_correcciones.py × 2
_es_afirmacion_barato       → test_criterio_concordancia.py
_con_saludo_inicial         → test_saludo.py, test_fiscal_niveles.py
_asegurar_honestidad_bot    → test_saludo.py × 4
_RE_DESTINO_UNICO           → test_saludo.py
_fallback_o_curada          → test_curadas.py × 2
_reanclar_si_producto_divergente → test_guarda_producto.py × 3
_resolver_nombre_a_producto  → test_guarda_producto.py (ya vive en pedido_helpers)
```

### ¿Qué pasa si lo borramos hoy?

**Falla:** 9 archivos de tests. Ningún módulo de producción.

### Para borrar: pasos necesarios

1. **Mover a `pedido_helpers.py`:**
   - `_mensaje_con_contenido`
   - `_sin_sustancia`
   - `_es_afirmacion_barato`

2. **Mover a `generador_v2.py` (o `hub_atado.py`):**
   - `_estampar_productos`
   - `_forzar_opciones_si_presupuesto`

3. **Mover a nuevo `app/core/honestidad.py` (o `compositor.py`):**
   - `_con_saludo_inicial`
   - `_asegurar_honestidad_bot`
   - `_RE_DESTINO_UNICO`
   - `_fallback_o_curada`

4. **Mover a `pedido_helpers.py`:**
   - `_reanclar_si_producto_divergente` (depende de `_resolver_nombre_a_producto` que ya está allí)

5. **Actualizar tests:** cambiar `from app.core.interprete_libre import X` por los módulos destino.

6. **Verificar:** `pytest` pasa verde puro.

7. **Borrar:** `app/core/interprete_libre.py`.

**Tiempo estimado:** 3-4 horas de trabajo enfocado (Fase 2).

---

## 2. `solver_gemini.py` (500 líneas)

### ¿Dónde vive?
`app/core/solver_gemini.py`

### ¿Lo usa algún módulo de producción?
**No.** Solo referenciado desde `banco_pruebas/` (experimentos fuera del camino vivo).

### ¿Qué tests lo importan?

| Archivo de test | Qué importa | Función en uso real |
|---|---|---|
| `test_verificador_cita.py` | `_prosa_citada`, `es_turno_criterio` | Verificación de citas + criterio por turno |
| `test_solver_memoria.py` | `_bloque_memoria` | Bloque de memoria del solver |

### Funciones exportadas que usan los tests

```
_prosa_citada     → test_verificador_cita.py
es_turno_criterio → test_verificador_cita.py
_bloque_memoria   → test_solver_memoria.py
```

### ¿Qué pasa si lo borramos hoy?

**Falla:** 2 archivos de tests. Ningún módulo de producción.

### Para borrar: pasos necesarios

1. **Mover a `verificador_cita.py` (ya existe, verificar si cabe):**
   - `_prosa_citada`
   - `es_turno_criterio`

2. **Mover a `pedido_helpers.py` o nuevo `app/core/solver_helpers.py`:**
   - `_bloque_memoria`

3. **Actualizar tests:** cambiar `from app.core.solver_gemini import X` por los módulos destino.

4. **Verificar:** `pytest` pasa verde puro.

5. **Borrar:** `app/core/solver_gemini.py`.

**Tiempo estimado:** 1-2 horas de trabajo enfocado (Fase 2).

---

## 3. `_money`: consolidación (ver PR asociado)

Definida en 6 módulos con comportamiento inconsistente (tabla abajo). Consolidada
en `pedido_helpers.py` como función canónica. El resto importa desde allí.

| Módulo | `$` incluido | `int(round)` | Error fallback |
|---|---|---|---|
| `pedido_helpers.py` (nuevo, canónico) | ✅ | ✅ | `str(n)` |
| `tools.py` (antes) | ✅ | ✅ | `str(n)` |
| `curadas.py` (antes) | ✅ | ✅ | `str(n)` |
| `estado_venta.py` (antes) | ❌ | ❌ | `str(n)` |
| `pago.py` (antes) | ❌ | ❌ | `str(n)` |
| `pago_split.py` (antes) | ❌ | ✅ | ❌ sin manejo |

---

## Resumen ejecutivo

```
Para borrar interprete_libre.py:
  - Bloqueado por 9 archivos de tests
  - Requiere mover ~10 funciones a módulos vivos
  - Impacto en producción: 0 (no se usa en el camino vivo)

Para borrar solver_gemini.py:
  - Bloqueado por 2 archivos de tests
  - Requiere mover 3 funciones
  - Impacto en producción: 0

Recomendación Fase 2:
  1. Empezar por solver_gemini (más simple, 3 funciones)
  2. Luego interprete_libre (más trabajo pero limpia 2236 líneas)
  3. Gate: pytest 652+ verde puro después de cada movida
```
