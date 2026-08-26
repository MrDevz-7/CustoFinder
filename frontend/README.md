# CustoFinder — Frontend

Interfaz web de CustoFinder: buscar negocios, evaluar leads con IA,
generar emails de prospección, analizar competencia, y llevar el
pipeline de ventas en un kanban.

Este README cubre el setup del **frontend** (Next.js 16 + React 19 +
TypeScript + Tailwind + shadcn/ui). El backend (FastAPI + PostgreSQL)
vive en la carpeta hermana `backend/` — ver su propio README ahí.

## Requisitos

- Node.js 20 o superior
- El backend corriendo (local en `http://localhost:8000`, o la URL de
  producción en Render)

## 1. Ubicarte en la carpeta frontend

```powershell
cd frontend
```

## 2. Instalar dependencias

```powershell
npm install
```

## 3. Configurar variables de entorno

```powershell
copy .env.example .env.local
```

Editá `.env.local` y completá:

NEXT_PUBLIC_API_URL=http://localhost:8000


En producción (Vercel) esta variable apunta a la URL de Render
(`https://custofinder-backend.onrender.com`). Se incrusta en **build
time**, así que cambiarla en Vercel requiere un redeploy, no alcanza con
reiniciar la app.

## 4. Levantar el servidor de desarrollo

```powershell
npm run dev
```

Abrí [http://localhost:3000](http://localhost:3000).

## 5. Build de producción (para verificar antes de un deploy)

```powershell
npm run build
```

## Estructura relevante

src/
app/
page.tsx → home
search/page.tsx → buscar negocios + analizar con Gemini
leads/page.tsx → tabla de leads
leads/[id]/page.tsx → detalle: evaluación, email, competencia, pipeline
pipeline/page.tsx → kanban drag-and-drop
analytics/page.tsx → efectividad por segmento
icon.svg → favicon
lib/api.ts → cliente HTTP hacia el backend
types/api.ts → tipos TS compartidos con las respuestas del backend


## Deploy

Vercel Hobby, auto-deploy on push a `main`. Variable de entorno
`NEXT_PUBLIC_API_URL` configurada en el dashboard de Vercel (Project →
Settings → Environment Variables).