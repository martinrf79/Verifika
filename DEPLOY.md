# DEPLOY y arranque de chat — datos operativos a la vista

Archivo operativo. NO describe comportamiento del bot (eso vive en `tests/`), NO
son reglas (esas viven en `CLAUDE.md`), NO es el estado del día (ese vive en
`RESUMEN_PARA_NUEVO_CHAT.md`). Acá está solo cómo se deploya y cómo arranca un
chat nuevo gastando pocos tokens.

---

## 1. Cómo se deploya

Hay UN solo servicio de bot y DOS formas de deployarlo. Las dos terminan en el
mismo lugar: `agente-bot` en Cloud Run.

### Forma A — automática por CI (la normal)

Un push a la rama `main` dispara el workflow `.github/workflows/deploy.yml`, que
deploya solo. No hace falta tener `gcloud` en la máquina: la autenticación es por
Workload Identity Federation desde GitHub.

- **Se saltea si el push toca SOLO archivos que no llegan a producción.** Cuáles
  son no se escribe acá: están en `paths-ignore` de `deploy.yml`, y salen de
  `.gcloudignore` —son las carpetas que el build ni siquiera sube—. Si hace
  falta saberlo, se mira el workflow, no este archivo.
- También se puede disparar a mano desde la pestaña Actions (`workflow_dispatch`).
- Después de mergear a `main`, verificar la corrida **Deploy a Cloud Run** en
  GitHub: recién con el verde se dice "listo". Si falla, leer el log y arreglar.

### Forma B — manual con `./deploy.sh` (desde tu Cloud Shell)

Desde `~/verifika`, con `gcloud` autenticado:

```bash
cd ~/verifika && ./deploy.sh
```

El script sincroniza `main` (`git reset --hard origin/main`), verifica que exista
`app/logger.py` y corre el deploy. Nunca un `gcloud run deploy` suelto a mano.

### Datos del deploy (fuente: `deploy.yml` y `deploy.sh`, ya en el repo)

| Dato | Valor |
|---|---|
| Servicio vivo del bot | `agente-bot` |
| Región | `southamerica-east1` |
| Proyecto GCP | `memory-engine-v1` |
| Origen | `--source .` (build desde el repo, usa el `Dockerfile`) |
| Auth del CI | Workload Identity Federation |
| Service account del deploy | `github-deployer@memory-engine-v1.iam.gserviceaccount.com` |
| Otro servicio | `video-engine` (otro producto), APAGADO (min-instances 0), NO se borra |

Reglas duras del deploy (de `CLAUDE.md`):

- UN solo servicio de bot: `agente-bot`. Nunca crear ni deployar a otro.
- La config vive en el código (`config.py`), no en variables de la nube. El
  servicio solo lleva secretos + `TIENDA_ID`. Secretos en Secret Manager.
- **El proveedor y el modelo del LLM los define `app/config.py`**, y no se
  escriben en ningún documento. Lo que se consulta con Martín no es la marca:
  es el GASTO. No se pasa a un modelo más caro sin su OK.
- Después de CADA deploy, verificar el verde en GitHub antes de dar por hecho.

---

## 2. Cómo arranca un chat nuevo sin quemar tokens

El error caro es que cada chat nuevo re-explore el repo entero. No hace falta.
Hay CUATRO fuentes de verdad y nada más:

1. `CLAUDE.md` — las reglas permanentes.
2. `RESUMEN_PARA_NUEVO_CHAT.md` — el estado y el foco de hoy.
3. `tests/` — el comportamiento del bot. Un test verde es un hecho. Correr
   `pytest` muestra el tablero de pendientes en segundos, sin gastar tokens.
4. `DEPLOY.md` — este archivo, lo operativo del deploy.

Método para arrancar barato:

- Leer `CLAUDE.md` y `RESUMEN`, correr `pytest`. Con eso ya sabés todo. No
  re-investigues lo que un test ya afirma.
- Para arreglar un rojo: leer SOLO el test que falla y el módulo que apunta, no
  el repo entero. Seguir el traceback si te manda a otro archivo. Nada más.
- El código de producción vive en `app/`. Los contratos, en `tests/`. No busques
  comportamiento en scripts sueltos: tienen copias viejas del prompt y mienten.
- Evitá `grep`/lectura masiva sobre `data/`, `scripts/` y fixtures: son ruido.
  El catálogo real y la FAQ son fuente de verdad pero NO se leen para razonar el
  flujo; se suben a Firestore por los endpoints de admin.
- Consolidar, no agregar: por cada cosa que se prende, se apaga o borra una
  vieja. No sumar un quinto documento de comportamiento ni flags apagadas.
- **Un dato que vive en un archivo no se copia a un documento.** Si un `.md` te
  dice un número o un nombre que el código también dice, gana el código y el
  `.md` está mal. Ya pasó tres veces: la FAQ que decía 44 temas y tenía 50, el
  modelo del LLM que estuvo mal nombrado durante meses, y el `paths-ignore` de
  este mismo archivo.

---

## 3. Pendiente de orden en la raíz (candidatos a consolidar)

La raíz todavía tiene arnés viejo de experimentación que quedó suelto y que la
suite de regresión en `tests/` reemplaza como fuente de verdad. NO se borraron
sin tu OK porque pueden ser herramientas tuyas. Cuando quieras, decidís en una
mirada qué sirve y qué sale:

- Scripts de arnés y consola: `arnes_aserciones.py`, `arnes_atacante.py`,
  `charla_cierre.py`, `charla_local.py`, `correr_molino_focos.py`,
  `correr_molino_multiturno.py`, `correr_pruebas.py`, `smoke_local.py`,
  `ver_catalogo.py`, `ver_colecciones.py`, `ver_productos.py`, `ver_tiendas.py`.
- Guiones y casos: `guion_*.txt` (varios), `top15_casos.txt`,
  `casos_vendibles.txt`, `casos_arnes.json`, `conversaciones_multiturno*.json`,
  `preguntas_100.json`, `productos_test_50.csv`.
- Scripts de Windows: `auditar.ps1`, `correr_local.ps1`.

Ya se sacó en este pase: el virtualenv commiteado `venv-win/` (4345 archivos, no
lo importa nadie y ya estaba excluido del deploy) y los CSV de resultados de
benchmark de proveedores alternativos, que son regenerables. Ambos quedaron
ignorados en `.gitignore` para que no vuelvan.
