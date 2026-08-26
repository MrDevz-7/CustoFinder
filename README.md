# CustoFinder

Prospección inteligente de clientes para freelancers y agencias de
software: descubre negocios locales sin sitio web, evalúa cada uno como
lead con IA, analiza a su competencia y hace seguimiento del pipeline de
ventas en un kanban — todo en un solo lugar.

**Demo en vivo:** https://custo-finder.vercel.app
**API:** https://custofinder-backend.onrender.com

> El backend está en el plan Free de Render: si nadie lo usó en los
> últimos 15 minutos, el primer request puede tardar ~50s en responder
> mientras la instancia arranca. Es normal, no es un error.

## Qué hace

1. **Buscar** — dado una zona y una categoría de negocio, descubre
   negocios locales vía OpenStreetMap (Nominatim + Overpass) y marca
   cuáles no tienen sitio web (el filtro más simple de "lead con
   oportunidad real").
2. **Analizar con Gemini** — evalúa cada negocio como lead: score de
   urgencia, servicio recomendado, argumentos de venta.
3. **Generar email** — redacta un borrador de email de prospección
   personalizado para ese lead.
4. **Analizar competencia** — visita sitios de competidores cercanos
   (Playwright) y detecta si tienen menú online, reservas, e-commerce o
   blog — para argumentar por qué el prospecto se está quedando atrás.
5. **Pipeline** — kanban drag-and-drop de seguimiento comercial (nuevo →
   contactado → respondió → reunión → cerrado / descartado), con
   historial de cambios de etapa.
6. **Analytics** — tasa de conversión por rubro + zona + rango de
   urgencia, para saber qué segmentos conviene priorizar.

## Stack

| Capa | Tecnología |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL |
| IA | Google Gemini (Flash / Flash-Lite, vía REST directo) |
| Descubrimiento de negocios | OpenStreetMap (Nominatim + Overpass) |
| Scraping de competencia | Playwright (Chromium headless) |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind, shadcn/ui |
| Infra | Docker (backend), Render Free (backend), Vercel Hobby
(frontend), Supabase Free (Postgres) |

**Costo real: $0.** Sin tarjeta de crédito en ningún servicio. Ver
limitaciones conocidas de este enfoque más abajo.

## Cómo correr en local

Requisitos: Docker Desktop, Node 20+, una API key gratis de Gemini
([aistudio.google.com/apikey](https://aistudio.google.com/apikey), sin
tarjeta).

```bash
git clone https://github.com/MrDevz-7/CustoFinder.git
cd CustoFinder

# Backend
cd backend
copy .env.example .env    # completar GEMINI_API_KEYS y OSM_CONTACT_EMAIL
docker compose up -d      # levanta Postgres local
docker build -t custofinder-backend .
docker run --env-file .env -p 8000:8000 custofinder-backend

# Frontend (otra terminal)
cd frontend
copy .env.example .env.local   # completar NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev
```

Backend en `http://localhost:8000/docs` (Swagger), frontend en
`http://localhost:3000`.

## Cómo desplegar (gratis, sin tarjeta)

- **Backend → Render Free** (Web Service, Docker, branch `main`,
  auto-deploy on push). Variables de entorno: `DATABASE_URL`,
  `GEMINI_API_KEYS`, `OSM_CONTACT_EMAIL`, `ENVIRONMENT=production`.
- **Base de datos → Supabase Free** (Postgres administrado).
- **Frontend → Vercel Hobby**. Variable `NEXT_PUBLIC_API_URL` apuntando
  a la URL de Render — se incrusta en build time, así que un cambio
  requiere redeploy, no alcanza con reiniciar.

## Limitaciones conocidas

- **OpenStreetMap es infraestructura pública gratuita** y puede estar
  degradada en el momento de una demo. El backend detecta cuando los 3
  mirrors de Overpass fallan y responde con la última búsqueda exitosa
  guardada en Postgres para esa misma zona/categoría (marcado como
  `source: "cache"` en la respuesta). Detalle técnico completo:
  [`docs/DECISIONES_TECNICAS.md`](./docs/DECISIONES_TECNICAS.md).
- **El caché de zona hace match por texto exacto**, no geocodificación
  difusa: "Laureles" y "Laureles, Medellín" son búsquedas distintas. Para
  una demo garantizada, usar el botón "Usar zona de demo" en la página
  de búsqueda.
- **Google Gemini free tier**: límite de requests por minuto/día en el
  modelo Flash. El cliente rota entre varias API keys si se configuran
  varias separadas por coma.
- **Render Free duerme tras 15 min de inactividad**: el primer request
  después de eso tarda más.

## Estructura

- [`backend/`](./backend/README.md) — FastAPI + PostgreSQL + SQLAlchemy.
- [`frontend/`](./frontend/README.md) — Next.js + TypeScript.
- [`docs/`](./docs/) — decisiones técnicas, informes de cierre y
  checklists del proceso de desarrollo.

## Repo

https://github.com/MrDevz-7/CustoFinder