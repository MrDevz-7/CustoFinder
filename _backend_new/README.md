# CustoFinder — Backend

Sistema de prospección inteligente de clientes para freelancers/agencias de
software. Descubre negocios locales sin sitio web (OpenStreetMap), los
evalúa con IA (Gemini) y genera propuestas de prospección personalizadas.

Este README cubre el setup del **backend** (FastAPI + PostgreSQL +
SQLAlchemy). El frontend (Next.js/TypeScript) se aborda en Día 4-5.

## Requisitos

- Python 3.11 o superior
- Docker y Docker Compose (para levantar Postgres localmente)
- Una API key gratis de Gemini (Google AI Studio) — ver sección más abajo

## 1. Clonar y ubicarte en la carpeta backend

```bash
cd backend
```

## 2. Levantar Postgres con Docker Compose

```bash
docker compose up -d
```

Esto levanta un contenedor de Postgres 16 en `localhost:5432` con:
- usuario: `custofinder`
- password: `custofinder`
- base de datos: `custofinder`

Verifica que esté corriendo y sano:

```bash
docker compose ps
```

Deberías ver el servicio `postgres` en estado `healthy`.

## 3. Crear el entorno virtual e instalar dependencias

```bash
python3 -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 4. Configurar variables de entorno

```bash
cp .env.example .env
```

Edita `.env` y completa:
- `OSM_CONTACT_EMAIL`: tu email real (Nominatim lo exige para identificar tu app).
- `GEMINI_API_KEYS`: una o más API keys de Google AI Studio, separadas por
  coma (ver sección "Gemini" más abajo).

Si usaste el `docker-compose.yml` tal cual, `DATABASE_URL` ya viene correcta
por defecto.

## 5. Aplicar las migraciones de base de datos

```bash
alembic upgrade head
```

Esto crea las 5 tablas del esquema (`businesses`, `leads`,
`competitor_infos`, `pipeline_events`, `search_runs`). Puedes verificarlo
conectándote a Postgres:

```bash
docker compose exec postgres psql -U custofinder -d custofinder -c '\dt'
```

## 6. Levantar el servidor de desarrollo

```bash
uvicorn api.main:app --reload --port 8000
```

- Documentación interactiva (Swagger UI): http://localhost:8000/docs
- Healthcheck: http://localhost:8000/api/health

## 7. Probar el endpoint de búsqueda

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"zone": "Laureles, Medellín", "category": "restaurantes"}'
```

Respuesta esperada:

```json
{
  "run_id": 1,
  "businesses_found": 14,
  "leads_without_website": 8
}
```

(Los números exactos dependen de qué negocios devuelva OpenStreetMap para
esa zona/categoría en el momento de la consulta.)

## OpenStreetMap (Nominatim + Overpass)

No requiere API key ni tarjeta de crédito. Dos servicios públicos gratuitos:

- **Nominatim** geocodifica el texto de `zone` a un área geográfica.
- **Overpass API** busca negocios dentro de esa área según la categoría.

Configura `OSM_CONTACT_EMAIL` en tu `.env` con un email real (Nominatim pide
identificar la app que la consulta). Categorías soportadas hoy: ver
`CATEGORY_TAG_MAP` en `scrapers/maps_discovery.py`.

**Limitaciones a tener en cuenta:** la cobertura de datos en Colombia varía
por zona, el campo "website" (y también "phone"/"address") no siempre está
cargado aunque el negocio sí tenga esos datos en la realidad, y OSM no
tiene rating ni número de reseñas (a diferencia de Google Places). Además,
Nominatim/Overpass son servicios públicos compartidos: pueden responder
lento o con 429/504 en horas pico — esto no es un bug del proyecto.

## Gemini (Google AI Studio) — evaluación de leads

Usa **solo** modelos Flash / Flash-Lite del free tier de Google AI Studio
(nunca Vertex AI, nunca modelos Pro), 100% gratis, sin tarjeta de crédito.

1. Ve a https://aistudio.google.com/apikey y crea una API key gratis.
2. Pégala en `.env`, en `GEMINI_API_KEYS` (puedes poner varias separadas
   por coma para rotar cuota entre ellas).
3. Opcional: cambia `GEMINI_MODEL` a `gemini-2.5-flash-lite` si necesitas
   más cuota diaria en vez de mejor calidad de respuesta.

**Límites del free tier** (Google los ajusta seguido, confirma en
https://ai.google.dev/gemini-api/docs/rate-limits):
- `gemini-2.5-flash`: ~10 requests/minuto, ~250 requests/día
- `gemini-2.5-flash-lite`: ~15 requests/minuto, ~1000 requests/día

El endpoint `POST /api/leads/{business_id}/analyze` filtra automáticamente
(sin gastar cuota de Gemini) los negocios que ya tienen sitio web, o que no
tienen ningún dato de contacto (ni teléfono ni dirección) — ver
`analyzer/prompt_builder.py::should_skip_lead`.

## Endpoints de leads (Día 2)

- `POST /api/leads/{business_id}/analyze` — evalúa un negocio con Gemini
  (o descarta automáticamente si no aplica). Usa `?force=true` para
  reevaluar un lead ya analizado.
- `POST /api/leads/{lead_id}/generate-email` — genera el email de
  prospección para un lead ya analizado.
- `GET /api/leads/{lead_id}` — detalle de un lead.
- `GET /api/leads?stage=nuevo&min_urgency=7` — lista de leads, con
  filtros opcionales por etapa de pipeline y score mínimo de urgencia.

## Estructura del proyecto

backend/
├── api/ # FastAPI: endpoints y schemas Pydantic
│ ├── main.py
│ └── schemas.py
├── database/ # Modelos SQLAlchemy, conexión, config
│ ├── models.py
│ ├── session.py
│ └── config.py
├── scrapers/ # Descubrimiento de negocios (OpenStreetMap)
│ └── maps_discovery.py
├── analyzer/ # Evaluación con IA (Gemini) — Día 2
│ ├── gemini_client.py
│ ├── prompt_builder.py
│ └── lead_evaluator.py
├── tracker/ # Día 6 — seguimiento de pipeline, vacío por ahora
├── scheduler/ # Día 3 — jobs programados, vacío por ahora
├── alembic/ # Migraciones de base de datos
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md

## Comandos útiles de Alembic

- Crear una nueva migración a partir de cambios en `database/models.py`:
```bash
  alembic revision --autogenerate -m "descripción del cambio"
```
- Aplicar todas las migraciones pendientes:
```bash
  alembic upgrade head
```
- Revertir la última migración:
```bash
  alembic downgrade -1
```

## Apagar el entorno

```bash
docker compose down          # detiene Postgres (conserva los datos)
docker compose down -v       # detiene Postgres Y borra los datos (volumen)
```