# Informe de Cierre — Día 1 de 7
## Proyecto CustoFinder — Fundaciones de Backend

**Fecha:** 22 de julio de 2026
**Alcance del día:** Fundaciones de backend (FastAPI + PostgreSQL + SQLAlchemy).
Sin IA/Gemini (Día 2) ni frontend (Día 4-5).

---

## 1. Qué se construyó

- **Estructura del proyecto** (`backend/`) con las carpetas del roadmap
  completo: `api/`, `database/`, `scrapers/` (activas hoy) y `analyzer/`,
  `tracker/`, `scheduler/` (vacías, reservadas para Días 2, 6 y 3
  respectivamente).
- **Entorno de desarrollo**: `requirements.txt` con FastAPI, SQLAlchemy
  2.x, Alembic, psycopg2, httpx, pydantic-settings; venv funcional.
- **Docker Compose** con un servicio de Postgres 16 para desarrollo local
  (usuario/db `custofinder`, puerto 5432, volumen persistente).
- **Esquema de base de datos completo** (5 tablas) modelado en SQLAlchemy
  2.x con sintaxis moderna (`Mapped`/`mapped_column`):
  `businesses`, `leads`, `competitor_infos`, `pipeline_events`,
  `search_runs`. Incluye el `CheckConstraint` de los 6 estados del
  pipeline (`nuevo/contactado/respondio/reunion/cerrado/descartado`) y el
  `UniqueConstraint` de `place_id` en `businesses`.
- **Alembic** inicializado, con la migración inicial generada por
  autogenerate y **aplicada y verificada contra una instancia real de
  Postgres**: las 5 tablas existen con los constraints correctos.
- **Integración con Google Places API (New)** (`scrapers/maps_discovery.py`):
  función `discover_businesses(zone, category)` que hace Text Search +
  Place Details, marca `has_website` según `websiteUri`, y maneja rate
  limit / key inválida / negocios sin dirección sin tumbar toda la corrida.
- **API FastAPI** (`api/main.py`):
  - `POST /api/search`: crea `SearchRun`, llama a `discover_businesses`,
    hace upsert de `Business` por `place_id` (no duplica en corridas
    repetidas), actualiza conteos, retorna `run_id`, `businesses_found`,
    `leads_without_website`.
  - `GET /api/health`: healthcheck simple para Railway (Día 7).
- **README.md** de setup desde cero, **checklist** del día, y este informe.

---

## 2. Decisiones técnicas tomadas (y por qué)

| Decisión | Justificación |
|---|---|
| **httpx en vez de la librería `googlemaps`** para llamar Places API | `googlemaps` (PyPI) apunta mayormente a los endpoints *legacy*. La "Places API (New)" que pide el proyecto usa otro formato de endpoint/payload (field masks vía headers). Llamar el REST directo con httpx nos da control total sobre qué campos pedimos, lo cual importa porque Places API (New) cobra distinto según el field mask — pedir de más cuesta más. |
| **Text Search + Place Details (dos llamadas por negocio)** en vez de una sola | Text Search no siempre trae `websiteUri` completo con field masks livianos; separarlo en Place Details da control fino sobre ese campo específico, que es el que determina `has_website`. |
| **Alembic desde el Día 1**, no `Base.metadata.create_all()` | `create_all()` crea las tablas tal cual están en el código *una sola vez*, pero no sabe versionar cambios: si el Día 3 agregamos una columna, no hay forma de aplicar ese cambio a una base ya poblada sin migraciones. Alembic genera un historial de cambios (como git, pero para el esquema de la DB), permite hacer rollback, y es el estándar para proyectos que van a iterar el esquema (como este, con 6 días más de cambios previstos). |
| **Postgres real desde el Día 1 (no SQLite)**, vía Docker Compose | El proyecto final corre en Postgres (Railway, Día 7). SQLite es más laxo con tipos y constraints (por ejemplo, el `CheckConstraint` de `pipeline_stage` se comporta distinto); desarrollar contra el mismo motor desde el día 1 evita sorpresas de compatibilidad más adelante. |
| **`sales_arguments` como `Text` con JSON serializado**, no `JSONB` nativo | Se siguió la especificación tal cual la diste. Sugerencia para Día 2: si el JSON de argumentos de venta va a tener una forma estable y se va a querer filtrar/consultar por campos internos, migrar a `JSONB` nativo de Postgres da mejor performance de queries. Por ahora, `Text` es más simple y no bloquea nada. |
| **`pydantic-settings` para configuración** en vez de `os.getenv` disperso | Centraliza y tipa las variables de entorno en un solo archivo (`database/config.py`), y falla rápido al arrancar si falta una variable obligatoria, en vez de fallar a mitad de una request. |

---

## 3. Qué se probó y qué resultado dio

### 3.1. Infraestructura de datos
- Postgres real levantado, migración de Alembic aplicada: **5 tablas + tabla
  de control `alembic_version` confirmadas**, incluyendo el
  `CheckConstraint` de los 6 estados de pipeline (verificado con
  `\d leads` en psql).

### 3.2. `discover_businesses()`
- **Importante y transparente:** el entorno donde construí esto hoy no
  tiene salida de red hacia `places.googleapis.com` (es un entorno de
  desarrollo aislado, sin acceso general a internet salvo un puñado de
  dominios técnicos como PyPI/npm). Esto significa que **no pude probar
  la función contra la Google Places API real con una key real** — no es
  que haya fallado, es que este entorno no tiene forma de llegar a
  Google.
- Para no dejar la función sin validar, escribí un test (
  `scrapers/test_maps_discovery_mock.py`) que simula las respuestas HTTP
  de Text Search y Place Details con la misma forma exacta que documenta
  Google, y confirmé que el parsing/mapeo a dict de `Business` es
  correcto (nombres, coordenadas, `has_website` según presencia de
  `websiteUri`, zona, etc.).
- **Esto queda como el ítem principal a validar por ti antes de Día 2**
  (ver sección 5).

### 3.3. `POST /api/search` end-to-end
- Con el mismo enfoque (datos simulados con la forma real de la API, por
  la misma limitación de red), corrí el flujo completo:
  `scrapers/test_search_endpoint_e2e.py` levanta la API real, simula 3
  negocios (2 sin sitio web, 1 con sitio web) para la zona "Laureles,
  Medellín" / categoría "restaurantes", y llama `POST /api/search` dos
  veces seguidas.
- **Resultado obtenido:**
  - 1ra corrida: `{"run_id": 3, "businesses_found": 3, "leads_without_website": 2}`
    — 3 negocios insertados en Postgres.
  - 2da corrida (misma zona/categoría, simulando una búsqueda repetida):
    mismo resultado de conteos, **y se confirmó en Postgres que siguen
    existiendo solo 3 registros en `businesses` (no 6)** — el upsert por
    `place_id` funciona.
  - 2 `SearchRun` quedaron registrados (uno por cada llamada), como se
    espera.
- `GET /api/health` probado con `curl`: responde `200 OK` con
  `{"status": "ok", "environment": "development"}`.
- `/docs` (Swagger UI) y `/openapi.json` verificados, ambos `200 OK`.
- Los datos de prueba fueron limpiados de la base (`TRUNCATE`) al cerrar
  el día, para que arranques Día 2 con las tablas vacías y recién
  migradas.

---

## 4. Qué quedó pendiente o bloqueado

1. **Bloqueado — API key real de Google Places API (New):** no la tengo
   ni puedo generarla (requiere tu cuenta de Google Cloud con
   facturación asociada). El código está listo para usarla en cuanto la
   configures en `.env`. Instrucciones paso a paso en `README.md`.
2. **Pendiente de validar por ti — llamada real a Google Places:** una
   vez tengas la key, corre el `curl` de la sección 7 del README con una
   zona/categoría real y confirma que los conteos de `businesses_found` /
   `leads_without_website` tienen sentido para ese lugar. Si algo falla
   (403, 429, campos vacíos), el mensaje de error debería ser claro
   gracias al manejo de errores en `maps_discovery.py`.
3. **No bloqueante, a decidir en Día 2:** si `sales_arguments` se queda
   como `Text` (JSON serializado, como pediste) o se migra a `JSONB`
   nativo cuando definamos la forma exacta del output de Gemini.
4. **No bloqueante, nota para Día 7:** `GET /api/health` hoy no valida la
   conexión a la base de datos a propósito (para no tumbar el healthcheck
   de Railway si la DB tarda en levantar). Si se necesita un check
   "profundo", se agrega como endpoint separado más adelante.

---

## 5. Qué se necesita validar antes de Día 2

- [ ] Crear la API key de Google Places (New) y confirmar que
      `discover_businesses()` trae resultados reales para al menos 2-3
      zonas/categorías distintas.
- [ ] Confirmar que el pricing/free tier de Places API (New) es acorde al
      volumen de búsquedas que se espera hacer (revisar la página de
      pricing enlazada en el README, los precios pueden cambiar).
- [ ] Decidir si `sales_arguments` se queda en `Text` o pasa a `JSONB`
      antes de que Día 2 empiece a escribir en esa columna.
- [ ] Levantar el `docker-compose.yml` en tu máquina (no en este entorno
      de construcción, que no tiene Docker) y confirmar que el flujo del
      README funciona igual ahí.

---

## 6. Desviaciones respecto al prompt original

- Se usó **httpx** en vez de `googlemaps`, explicado y justificado en la
  sección 2. Ningún campo del esquema fue cambiado respecto a lo pedido.
- El **`docker-compose.yml` no fue ejecutado literalmente en este
  entorno** (no tiene Docker instalado). En su lugar, para poder probar
  todo de verdad hoy, instalé y usé Postgres 16 nativo dentro del
  entorno de construcción, con la misma versión y comportamiento que el
  contenedor define. El archivo `docker-compose.yml` entregado es el que
  debes usar en tu máquina real; no debería haber diferencias de
  comportamiento (misma versión de Postgres, mismas credenciales).
- La **llamada real a Google Places API no pudo probarse** por falta de
  acceso de red a `googleapis.com` desde este entorno (detallado en
  sección 3.2 y 4). Se compensó con pruebas simuladas que validan toda
  la lógica de parsing y persistencia; la validación contra la API real
  queda como tarea tuya antes de Día 2.
