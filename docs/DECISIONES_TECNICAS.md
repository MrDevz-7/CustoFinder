# Decisiones técnicas de CustoFinder

Registro de decisiones de arquitectura no obvias: qué se eligió, por qué,
y qué trade-offs implica. Formato tipo ADR liviano — una sección por
decisión, no un log cronológico del proyecto.

## OpenStreetMap en vez de Google Places API

**Contexto:** el proyecto exige 100% gratis, sin tarjeta en ningún
servicio. Google Places API (New) requiere una cuenta de Google Cloud con
facturación habilitada para poder usarla, aunque el uso real caiga dentro
del crédito gratuito mensual. OpenStreetMap (Nominatim + Overpass) no pide
tarjeta ni cuenta para sus APIs públicas.

**Decisión:** se usa OSM para descubrir negocios (`scrapers/maps_discovery.py`),
con `httpx` en vez de un SDK dedicado — da control total sobre el formato
de las queries y evita atarse a una librería que apunte a endpoints legacy.

**Limitaciones conocidas (leer antes de confiar ciegamente en los datos):**
- **Cobertura en Colombia:** depende de mapeo colaborativo. En zonas como
  Laureles/El Poblado (Medellín) la cobertura suele ser razonable; en
  zonas menos mapeadas, un resultado vacío no significa "no hay negocios
  ahí" — puede significar que nadie los cargó todavía.
- **Campo `website` poco confiable:** un negocio puede tener sitio web real
  sin tener el tag `website`/`contact:website` cargado en OSM. Esto genera
  falsos positivos en `has_website=False`. Tratar ese campo como
  "candidato a validar manualmente", no como verdad absoluta.
- **Sin rating ni review_count:** OSM no tiene sistema de reseñas: esos
  campos quedan siempre en `None`. Cualquier scoring que dependa de esas
  señales necesita ajustarse o buscar otra fuente.
- **Rate limiting:** Nominatim exige ~1 request/segundo y un User-Agent
  identificable ([política](https://operations.osmfoundation.org/policies/nominatim/)).
  Overpass no tiene límite fijo documentado pero banea IPs temporalmente
  ante abuso ([política](https://dev.overpass-api.de/overpass-doc/en/preface/commons.html)).
  El código respeta ambas: pausa 1s entre llamadas y manda un User-Agent
  con contacto real (`OSM_CONTACT_EMAIL`).

## Por qué `find_businesses_with_website_url()` está separada de `discover_businesses()`

`discover_businesses()` alimenta `/api/search` y no expone la URL real del
negocio (la tabla `Business` solo guarda el booleano `has_website`).
`find_businesses_with_website_url()` la necesita porque Playwright necesita
un URL al cual navegar para el scraping de competencia. En vez de tocar
`discover_businesses()` y arriesgar romper `/api/search`, se creó una
función separada que reutiliza los mismos helpers internos
(`_geocode_zone`, `_overpass_query`) para no duplicar la lógica de
geocodificación ni el rate-limiting.

## Salida forzada por IPv4 en llamadas a OSM

**Contexto:** al desplegar en Render (plan Free), las llamadas a Overpass
API fallaban con `[Errno 101] Network is unreachable`, mientras que las
llamadas a Nominatim (mismo módulo, mismo patrón de cliente) funcionaban
bien. Nominatim respondía 200 OK; solo Overpass fallaba.

**Diagnóstico:** `overpass-api.de` resuelve tanto a IPv4 como IPv6. La red
de salida de Render (al menos en el plan Free) no tiene ruta configurada
para IPv6 saliente, así que cualquier intento de conexión por esa vía
falla a nivel de sistema operativo, antes de llegar al servidor.

**Decisión:** `_ipv4_client()` en `scrapers/maps_discovery.py` fuerza
`httpx.HTTPTransport(local_address="0.0.0.0")`, que liga el socket a una
dirección IPv4 local y descarta cualquier intento por IPv6. Cambio de bajo
riesgo: si el servidor de destino tiene IPv4 disponible (caso normal), el
comportamiento no cambia; si el diagnóstico es correcto, resuelve el error.