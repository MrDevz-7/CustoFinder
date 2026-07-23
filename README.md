# CustoFinder — Backend

Sistema de prospección inteligente de clientes para freelancers/agencias de
software. Descubre negocios locales sin sitio web (OpenStreetMap), los
evalúa con IA (Gemini), analiza a su competencia local (Playwright), y
lleva el seguimiento del pipeline de ventas.

Este README cubre el setup del **backend** (FastAPI + PostgreSQL +
SQLAlchemy). El frontend (Next.js/TypeScript) se aborda desde Día 4 en la
carpeta hermana `frontend/` — **no dentro de `backend/`**.

## Requisitos

- Python 3.11 o superior
- Docker Desktop (para levantar Postgres localmente) — debe estar
  **abierto y corriendo** antes de usar `docker compose`
- Una API key gratis de Gemini (Google AI Studio) — ver sección más abajo
- ~200 MB libres para el navegador Chromium que instala Playwright

Todo lo de este README es 100% gratis, sin tarjeta de crédito en ningún
paso.

## 1. Ubicarte en la carpeta backend

Todos los comandos de este README se corren **desde dentro de `backend/`**,
no desde la raíz del proyecto:

```powershell
cd backend
```

## 2. Levantar Postgres con Docker Compose

Abre Docker Desktop primero y espera a que termine de cargar (la ballena 🐳
en la barra de tareas debe dejar de animarse). Luego, desde `backend/`:

```powershell
docker compose up -d
```

Esto levanta un contenedor de Postgres 16 en `localhost:5432` con:
- usuario: `custofinder`
- password: `custofinder`
- base de datos: `custofinder`

Verifica que esté corriendo y sano:

```powershell
docker compose ps
```

Deberías ver el servicio `postgres` en estado `healthy`.

## 3. Crear el entorno virtual e instalar dependencias

En Windows/PowerShell, desde `backend/`:

```powershell
py -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Si `py` no funciona, prueba `python -m venv venv`. Si `Activate.ps1` da un
error de "execution policy", corre una sola vez
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` y reintenta.
Sabrás que el venv está activo porque tu línea de comandos empieza con
`(venv)`.

### 3.1 Instalar el navegador de Playwright (necesario para el scraper de competencia)

Con el venv activo:

```powershell
playwright install chromium
```

Descarga un Chromium local (puede tardar uno o dos minutos). Es un paso
aparte de `pip install` porque Playwright no distribuye el navegador
dentro del paquete de Python.

## 4. Configurar variables de entorno

```powershell
copy .env.example .env
```

Edita `.env` y completa:
- `OSM_CONTACT_EMAIL`: tu email real (Nominatim lo exige para identificar tu app).
- `GEMINI_API_KEYS`: una o más API keys de Google AI Studio, separadas por
  coma (ver sección "Gemini" más abajo).

Si usaste el `docker-compose.yml` tal cual, `DATABASE_URL` ya viene correcta
por defecto.

## 5. Aplicar las migraciones de base de datos

```powershell
alembic upgrade head
```

Esto crea las 5 tablas del esquema (`businesses`, `leads`,
`competitor_infos`, `pipeline_events`, `search_runs`). Puedes verificarlo:

```powershell
docker compose exec postgres psql -U custofinder -d custofinder -c "\dt"
```

## 6. Levantar el servidor de desarrollo

```powershell
uvicorn api.main:app --reload --port 8000
```

- Documentación interactiva (Swagger UI): http://localhost:8000/docs
- Healthcheck: http://localhost:8000/api/health

## 7. Probar el flujo completo

**Buscar negocios sin web en una zona:**

```powershell
curl -X POST http://localhost:8000/api/search -H "Content-Type: application/json" -d '{\"zone\": \"Laureles, Medellin\", \"category\": \"restaurantes\"}'
```

**Analizar un negocio con Gemini** (usa un `business_id` real que haya
salido de la búsqueda anterior, revisa la tabla `businesses` o `/docs`):

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/leads/1/analyze" -Method Post
```

**Generar el email de prospección:**

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/leads/1/generate-email" -Method Post
```

**Analizar la competencia local del lead:**

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/leads/1/competitors" -Method Post
```

**Cambiar de etapa en el pipeline:**

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/leads/1/stage" -Method Patch -ContentType "application/json" -Body '{\"stage\":\"contactado\"}'
```

**Ver el historial de etapas de un lead:**

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/leads/1/pipeline-history" -Method Get
```

## OpenStreetMap (Nominatim + Overpass) — descubrimiento de negocios

No requiere API key ni tarjeta de crédito. Dos servicios públicos gratuitos:
- **Nominatim** geocodifica el texto de `zone` a un área geográfica.
- **Overpass API** busca negocios dentro de esa área según la categoría.

Configura `OSM_CONTACT_EMAIL` en tu `.env` (Nominatim pide identificar la
app que la consulta). Categorías soportadas hoy: ver `CATEGORY_TAG_MAP` en
`scrapers/maps_discovery.py`.

**Limitaciones:** la cobertura de datos en Colombia varía por zona, el
campo "website" (y también "phone"/"address") no siempre está cargado
aunque el negocio sí tenga esos datos en la realidad, y OSM no tiene
rating ni número de reseñas. Nominatim/Overpass son servicios públicos
compartidos: pueden responder lento o con 429/504 en horas pico — no es
un bug del proyecto.

## Gemini (Google AI Studio) — evaluación de leads

Usa **solo** modelos Flash / Flash-Lite del free tier (nunca Vertex AI,
nunca modelos Pro), 100% gratis, sin tarjeta.

1. Ve a https://aistudio.google.com/apikey y crea una API key gratis.
2. Pégala en `.env`, en `GEMINI_API_KEYS` (puedes poner varias separadas
   por coma para rotar cuota entre ellas).
3. Opcional: cambia `GEMINI_MODEL` a `gemini-2.5-flash-lite` si necesitas
   más cuota diaria en vez de mejor calidad de respuesta.

**Límites del free tier** (Google los ajusta seguido, confirma en
https://ai.google.dev/gemini-api/docs/rate-limits):
- `gemini-2.5-flash`: ~10 requests/minuto, ~250 requests/día
- `gemini-2.5-flash-lite`: ~15 requests/minuto, ~1000 requests/día

`POST /api/leads/{business_id}/analyze` filtra automáticamente (sin gastar
cuota) los negocios que ya tienen sitio web, o sin ningún dato de contacto
— ver `analyzer/prompt_builder.py::should_skip_lead`.

## Playwright — análisis de competencia local

Dado un lead, busca negocios cercanos del mismo rubro que **sí** tienen
sitio web (vía OpenStreetMap) y visita cada sitio con un navegador
Chromium local (gratis, sin servicios de terceros) para detectar: menú
online, sistema de reservas, e-commerce, blog.

**Importante:** cada vez que llamas `POST /api/leads/{lead_id}/competitors`,
se **reemplaza** el análisis anterior de ese lead (se borran los
`CompetitorInfo` previos antes de insertar los nuevos). La tabla
`competitor_infos` siempre refleja la foto más reciente del mercado, no
un historial acumulado. Si en el futuro se necesita comparar cómo cambió
la competencia en el tiempo, este comportamiento debe rediseñarse.

## Pipeline de leads

Cada lead tiene un `pipeline_stage`, uno de 6 valores fijos (reforzado por
un `CheckConstraint` en la base de datos, no solo por la aplicación):
`nuevo`, `contactado`, `respondio`, `reunion`, `cerrado`, `descartado`.

- `PATCH /api/leads/{lead_id}/stage` — cambia la etapa y registra un
  `PipelineEvent` (`from_stage → to_stage`). Si pides la misma etapa que
  ya tiene, no crea un evento nuevo (`changed: false`).
- `GET /api/leads/{lead_id}/pipeline-history` — historial completo de
  cambios de etapa de ese lead, en orden cronológico.

**Nota para quien agregue una etapa nueva en el futuro:** hay que
actualizar DOS lugares que deben coincidir manualmente: la lista
`PIPELINE_STAGES` en el código Python, y el `CheckConstraint` en
`database/models.py` (tabla `leads`). No hay una sola fuente de verdad
para esto todavía.

## Scheduler (parcialmente implementado, no conectado)

`scheduler/jobs.py` contiene `check_stale_new_leads()`: revisa leads en
etapa "nuevo" analizados hace más de 3 días sin avanzar, y los registra
en el log como advertencia. **Este job existe pero no se ejecuta** — nadie
llama todavía a `start_scheduler()` desde `api/main.py`. Queda pendiente
conectarlo (ver checklist de pendientes).

## Endpoints disponibles

- `GET /api/health` — healthcheck.
- `POST /api/search` — descubre negocios en una zona/categoría (OpenStreetMap).
- `POST /api/leads/{business_id}/analyze` — evalúa un negocio con Gemini (`?force=true` para reevaluar).
- `POST /api/leads/{lead_id}/generate-email` — genera el email de prospección.
- `GET /api/leads/{lead_id}` — detalle de un lead.
- `GET /api/leads?stage=nuevo&min_urgency=7` — lista de leads con filtros.
- `POST /api/leads/{lead_id}/competitors` — analiza competencia local (reemplaza análisis previo).
- `PATCH /api/leads/{lead_id}/stage` — cambia etapa de pipeline.
- `GET /api/leads/{lead_id}/pipeline-history` — historial de etapas.

## Estructura del proyecto

```
CustoFinder/
├── backend/
│   ├── api/                # FastAPI: endpoints y schemas Pydantic
│   │   ├── main.py
│   │   └── schemas.py
│   ├── database/           # Modelos SQLAlchemy, conexión, config
│   │   ├── models.py
│   │   ├── session.py
│   │   └── config.py
│   ├── scrapers/           # Descubrimiento (OpenStreetMap) + competencia (Playwright)
│   │   ├── maps_discovery.py
│   │   └── competitor_scraper.py
│   ├── analyzer/           # Evaluación con IA (Gemini)
│   │   ├── gemini_client.py
│   │   ├── prompt_builder.py
│   │   └── lead_evaluator.py
│   ├── scheduler/          # Jobs programados (existe, no conectado aún)
│   │   └── jobs.py
│   ├── tracker/            # Día 6 — seguimiento de efectividad, vacío por ahora
│   ├── alembic/            # Migraciones de base de datos
│   ├── docker-compose.yml
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md           # este archivo
└── frontend/                # Next.js + TypeScript — desde Día 4
```

## Comandos útiles de Alembic

```powershell
alembic revision --autogenerate -m "descripción del cambio"   # nueva migración
alembic upgrade head                                           # aplicar pendientes
alembic downgrade -1                                            # revertir la última
```

## Apagar el entorno

```powershell
docker compose down          # detiene Postgres (conserva los datos)
docker compose down -v       # detiene Postgres Y borra los datos (volumen)
```

## Checkpoints en GitHub

Repo: https://github.com/MrDevz-7/CustoFinder — un commit por día de
desarrollo. Al final de cada día: `git add .`, `git commit -m "Día N: ..."`,
`git push`.
