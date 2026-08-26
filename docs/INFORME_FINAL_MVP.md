# Informe Final — MVP CustoFinder

## Resumen ejecutivo

CustoFinder es un sistema de prospección inteligente de clientes para
freelancers y agencias de desarrollo web. Automatiza tres tareas que
normalmente se hacen a mano y de forma dispersa: encontrar negocios
locales sin sitio web, evaluar cuáles valen la pena contactar, y
argumentar por qué (comparándolos contra su competencia real).

**Demo en vivo:** https://custo-finder.vercel.app
**API:** https://custofinder-backend.onrender.com
**Repo:** https://github.com/MrDevz-7/CustoFinder

## Flujo completo (verificado end-to-end en producción, 26/08/2026)

1. Buscar negocios por zona + categoría (OpenStreetMap) → lista con
   quiénes no tienen sitio web.
2. Analizar cada negocio con Gemini → score de urgencia, servicio
   recomendado, argumentos de venta.
3. Generar un email de prospección personalizado por lead.
4. Analizar sitios de la competencia cercana (Playwright) → qué
   funcionalidades tienen que el prospecto no.
5. Mover el lead por un pipeline kanban (nuevo → contactado →
   respondió → reunión → cerrado / descartado), con historial de
   cambios de etapa.
6. Ver tasa de conversión por rubro + zona + rango de urgencia en
   Analytics, para saber qué segmentos priorizar.

## Qué NO incluye este MVP

- Autenticación / multiusuario — es una herramienta de un solo usuario,
  sin login.
- Envío real de emails — genera el borrador, no lo despacha (evita
  problemas de deliverability/spam sin infraestructura de email
  transaccional).
- Geocodificación difusa de zonas — el matching de caché es por texto
  exacto (ver limitación abajo).
- Notificaciones activas — hay un job en background (`scheduler/jobs.py`)
  que detecta leads estancados y los loguea, pero no envía alertas a
  nadie todavía.
- Multi-fuente de descubrimiento — solo OpenStreetMap; no hay fallback a
  Google Places ni otro proveedor.

## Costo real

**$0.** Render Free (backend), Vercel Hobby (frontend), Supabase Free
(Postgres), Google AI Studio free tier (Gemini Flash/Flash-Lite),
OpenStreetMap (gratis, sin key). Sin tarjeta de crédito registrada en
ningún servicio.

## Limitaciones conocidas

- **OpenStreetMap es infraestructura pública compartida.** Overpass
  (el motor de queries) puede estar degradado o rate-limiteado en
  cualquier momento — es un problema documentado y activo en la
  comunidad de OSM durante 2026. El sistema mitiga esto devolviendo la
  última búsqueda exitosa cacheada para la misma zona/categoría en vez
  de fallar con un 502. Detalle técnico completo en
  [`docs/DECISIONES_TECNICAS.md`](./DECISIONES_TECNICAS.md).
- **Render Free duerme tras 15 min de inactividad** — el primer request
  después de eso puede tardar ~50s.
- **Gemini free tier tiene límites de requests/día** por API key; el
  cliente rota entre varias keys si se configuran.
- **El campo `has_website` depende de qué tan bien mapeado esté un
  negocio en OSM** — puede haber falsos negativos (negocio con sitio
  real, pero no cargado en OSM).

## Próximos pasos (si el proyecto continuara)

1. Geocodificación difusa para el caché de búsquedas (hoy es texto
   exacto).
2. Envío real de emails vía un proveedor gratuito (ej. Resend free
   tier) con opt-in explícito.
3. Notificaciones activas para leads estancados (hoy solo se loguean).
4. Tests automatizados end-to-end contra staging (hoy la cobertura es
   de tests de humo con transportes simulados, por falta de salida de
   red en el entorno de desarrollo original).
5. Panel de administración para gestionar múltiples API keys de Gemini
   sin editar variables de entorno a mano.