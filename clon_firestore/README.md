# Clon de Firestore — catálogo y FAQs

Copia EXACTA de la fuente de verdad del repo que alimenta Firestore:

- `catalogo_productos.csv` — 880 productos (idéntico a `data/clientes/verifika_prod/productos.csv`).
- `faqs.json` — 44 temas de FAQ (idéntico a `data/clientes/verifika_prod/faq.json`).

Sirve como referencia accesible del contenido que vive en Firestore, y como
base de datos local del banco de pruebas (`banco_pruebas/`).

## Salvedad honesta
Esta copia es idéntica a los archivos del repo. Según el proyecto, esos archivos
SON lo que está cargado en Firestore (subidos por los endpoints `/admin/upload-catalog`
y `/admin/upload-faq`). No se pudo diferenciar contra la Firestore VIVA desde acá
por falta de credenciales de Google; si hay duda de drift, comparar este clon
contra un export de Firestore.

Copiado: 30-jun-2026.
