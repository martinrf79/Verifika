# FICHA 41 — Un idioma. Una sesión.

La interpretación está bien y se toma como base. El defecto no era
entender: era que el índice hablaba otro idioma que el molde.

`registrar_pedido` declara diez campos. El índice abría los mismos hechos
con otros nombres: item, condicion, duda, politica, precio. Dos listas
sobre lo mismo. Si el cliente pregunta dos campos, el sistema tiene que
abrir esos dos, con esos nombres. Sin apodo no hay teléfono descompuesto.

Las dieciocho clases difíciles de `banco_pruebas/preguntas.py` no son una
tercera taxonomía: cada una cae en esos campos. `cierre` queda afuera del
molde a propósito: "me lo llevo" no lo declara la llamada uno.

## Qué se hace

1. `CAMPOS_PEDIDO` sale de `RegistrarPedido.model_fields`. Una sola lista.
2. `tipo` del punto ES el campo. Ids `items:1`, `temas:1`, `pide_precio:1`.
3. Candado: dos campos declarados, dos tipos. Diez, diez. Ningún apodo.
4. Las dieciocho clases apuntan a esos campos.

No se toca la redacción. Esta ficha unifica el contrato. La respuesta
campo a campo es la etapa siguiente.

## Qué no se toca

El molde que ve el modelo. La calculadora. La FAQ. El catálogo.
`data/clientes/`. El prompt del redactor. Posventa. Segunda tienda.
