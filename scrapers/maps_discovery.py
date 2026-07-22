"""
Descubrimiento de negocios locales vía OpenStreetMap (Nominatim + Overpass API).

DECISIÓN TÉCNICA (Día 2): se migra de Google Places API (New) a OpenStreetMap
por la restricción del proyecto de "100% gratis, sin tarjeta de crédito en
ningún lado". Google Places API (New) requiere una cuenta de Google Cloud con
facturación habilitada (tarjeta registrada) para poder usar la API, incluso
si el uso real cae dentro del crédito gratuito mensual. OSM no requiere
tarjeta ni cuenta para consultar sus APIs públicas.

LIMITACIONES HONESTAS (léelas antes de confiar en los resultados):

1. Cobertura de datos en Colombia: OSM depende de mapeo colaborativo. En
   zonas como Laureles/El Poblado en Medellín la cobertura de comercios
   suele ser razonable, pero en zonas menos mapeadas puede haber muchos
   negocios reales que simplemente NO están en el mapa. A diferencia de
   Google Places, un resultado vacío o escaso no siempre significa "no hay
   negocios ahí" — puede significar "nadie los ha mapeado todavía".

2. Campo "website": su confiabilidad es baja. Un negocio puede tener sitio
   web real y no tener el tag `website`/`contact:website` cargado en OSM
   (nadie lo agregó). Esto genera FALSOS POSITIVOS en el sentido inverso al
   de Día 1: negocios marcados como `has_website=False` que en realidad sí
   tienen web. Es un trade-off inherente a usar una fuente sin el nivel de
   verificación de Google Places. Recomendación: tratar `has_website=False`
   como "candidato a validar manualmente", no como verdad absoluta.

3. Sin rating/review_count: OSM no tiene sistema de reseñas. Estos dos
   campos del dict quedan siempre en `None`. Si el scoring de urgencia de
   Gemini (más abajo) usaba estos campos como señal, hay que ajustarlo para
   no depender de ellos, o buscar otra señal.

4. Rate limiting y User-Agent: tanto Nominatim como Overpass son servicios
   públicos gratuitos compartidos por toda la comunidad OSM, con políticas
   de uso estrictas:
   - Nominatim exige máximo ~1 request/segundo y un User-Agent que
     identifique la app (idealmente con un contacto real). Política:
     https://operations.osmfoundation.org/policies/nominatim/
   - Overpass no tiene un límite fijo documentado, pero excesos devuelven
     429 y pueden derivar en baneos temporales de IP. Política:
     https://dev.overpass-api.de/overpass-doc/en/preface/commons.html
   Este módulo respeta ambas: pausa 1 segundo entre Nominatim y Overpass, y
   manda un User-Agent identificable (configurable vía OSM_CONTACT_EMAIL
   en .env).

Este módulo hace DOS llamadas por búsqueda (no por negocio, a diferencia de
Google Places):
  a) Nominatim -> GET https://nominatim.openstreetmap.org/search
     Geocodifica `zone` (texto libre) a un bounding box.
  b) Overpass -> POST https://overpass-api.de/api/interpreter
     Trae todos los negocios que matchean el tag de `category` dentro de
     ese bounding box, en una sola consulta.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

from database.config import settings

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Mapeo de categorías (texto libre en español, como las escribe el usuario)
# a tags de OpenStreetMap. Si necesitas otra categoría, búscala en
# https://wiki.openstreetmap.org/wiki/Map_Features y agrégala aquí.
CATEGORY_TAG_MAP: dict[str, list[tuple[str, str]]] = {
    "restaurantes": [("amenity", "restaurant")],
    "cafes": [("amenity", "cafe")],
    "panaderias": [("shop", "bakery")],
    "peluquerias": [("shop", "hairdresser")],
    "barberias": [("shop", "hairdresser")],
    "gimnasios": [("leisure", "fitness_centre")],
    "veterinarias": [("amenity", "veterinary")],
    "odontologos": [("amenity", "dentist")],
    "clinicas dentales": [("amenity", "dentist")],
    "farmacias": [("amenity", "pharmacy")],
    "hoteles": [("tourism", "hotel")],
    "abogados": [("office", "lawyer")],
    "contadores": [("office", "accountant")],
    "talleres mecanicos": [("shop", "car_repair")],
    "salones de belleza": [("shop", "beauty")],
    "tiendas de ropa": [("shop", "clothes")],
    "ferreterias": [("shop", "hardware")],
}


class PlacesAPIError(Exception):
    """Error genérico al descubrir negocios (Nominatim/Overpass): red, rate
    limit, zona sin geocodificar, categoría no soportada, etc.
    Se mantiene el mismo nombre que en Día 1 (aunque ya no hablemos de
    'Places') para no romper el import en api/main.py."""


def _user_agent() -> str:
    contact = settings.OSM_CONTACT_EMAIL or "sin-contacto-configurado"
    return f"CustoFinder/0.1 (contacto: {contact})"


def _geocode_zone(zone: str, client: httpx.Client) -> tuple[float, float, float, float]:
    """Geocodifica `zone` con Nominatim y devuelve el bounding box como
    (south, west, north, east), listo para usar en la query de Overpass."""
    params = {"q": f"{zone}, Colombia", "format": "json", "limit": 1}
    headers = {"User-Agent": _user_agent()}

    try:
        response = client.get(NOMINATIM_URL, params=params, headers=headers, timeout=15.0)
    except httpx.RequestError as exc:
        raise PlacesAPIError(f"Error de red llamando Nominatim: {exc}") from exc

    if response.status_code == 429:
        raise PlacesAPIError(
            "Rate limit alcanzado en Nominatim (429). Nominatim permite ~1 "
            "request/segundo; evita disparar búsquedas en paralelo."
        )
    if response.status_code != 200:
        raise PlacesAPIError(
            f"Nominatim falló con status {response.status_code}: {response.text[:300]}"
        )

    results = response.json()
    if not results:
        raise PlacesAPIError(
            f"Nominatim no encontró la zona '{zone}'. Prueba con un nombre "
            "más específico, ej. 'Laureles, Medellín, Colombia'."
        )

    south, north, west, east = (float(v) for v in results[0]["boundingbox"])
    return south, west, north, east


def _overpass_query(
    bbox: tuple[float, float, float, float],
    tags: list[tuple[str, str]],
    client: httpx.Client,
) -> list[dict]:
    """Ejecuta la query Overpass para uno o más pares tag=valor dentro del
    bbox dado. Devuelve los elementos crudos (nodes/ways/relations)."""
    bbox_str = ",".join(str(v) for v in bbox)

    filters = "".join(
        f'node["{k}"="{v}"]({bbox_str});way["{k}"="{v}"]({bbox_str});relation["{k}"="{v}"]({bbox_str});'
        for k, v in tags
    )
    query = f"[out:json][timeout:25];({filters});out center tags;"

    headers = {"User-Agent": _user_agent()}
    try:
        response = client.post(OVERPASS_URL, data={"data": query}, headers=headers, timeout=30.0)
    except httpx.RequestError as exc:
        raise PlacesAPIError(f"Error de red llamando Overpass: {exc}") from exc

    if response.status_code == 429:
        raise PlacesAPIError(
            "Rate limit alcanzado en Overpass API (429). El servidor público "
            "comparte cuota entre todos los usuarios de OSM; espera unos "
            "minutos antes de reintentar."
        )
    if response.status_code != 200:
        raise PlacesAPIError(
            f"Overpass falló con status {response.status_code}: {response.text[:300]}"
        )

    return response.json().get("elements", [])


def _element_to_business_dict(element: dict, zone: str, category: str) -> Optional[dict]:
    """Convierte un elemento crudo de Overpass (node/way/relation) al dict
    que espera api/main.py — MISMA forma que en Día 1 con Google Places."""
    tags = element.get("tags", {})
    name = tags.get("name")
    if not name:
        # Sin nombre no sirve como lead (no hay a quién contactar ni qué
        # mostrar en el pipeline comercial).
        return None

    if element["type"] == "node":
        lat, lon = element.get("lat"), element.get("lon")
    else:
        # ways/relations no traen lat/lon directo; "out center" en la query
        # nos da un punto representativo del polígono.
        center = element.get("center", {})
        lat, lon = center.get("lat"), center.get("lon")

    website = tags.get("website") or tags.get("contact:website")
    phone = tags.get("phone") or tags.get("contact:phone")

    street = tags.get("addr:street", "")
    housenumber = tags.get("addr:housenumber", "")
    address = f"{street} {housenumber}".strip() or None

    return {
        "place_id": f"osm_{element['type']}_{element['id']}",
        "name": name,
        "category": category,
        "address": address,
        "zone": zone,
        "phone": phone,
        "has_website": bool(website),
        "rating": None,        # OSM no tiene sistema de reseñas.
        "review_count": None,  # idem.
        "latitude": lat,
        "longitude": lon,
    }


def discover_businesses(zone: str, category: str) -> list[dict]:
    """
    Descubre negocios de `category` en `zone` usando OpenStreetMap
    (Nominatim para geocodificar + Overpass para buscar negocios).

    Retorna una lista de dicts con las mismas claves que la versión de
    Google Places (Día 1), lista para mapear 1:1 a columnas de `businesses`:
      place_id, name, category, address, zone, phone, has_website,
      rating, review_count, latitude, longitude

    Maneja los siguientes casos sin tumbar toda la búsqueda:
    - Elemento sin tag "name" -> se descarta (no sirve como lead).
    - Zona sin resultados de geocodificación -> levanta PlacesAPIError.
    - Categoría no mapeada a un tag de OSM -> levanta PlacesAPIError con la
      lista de categorías soportadas.
    - Rate limit en Nominatim u Overpass -> levanta PlacesAPIError, que el
      endpoint /api/search debe capturar y traducir a un HTTP 502/503.
    """
    tags = CATEGORY_TAG_MAP.get(category.strip().lower())
    if not tags:
        raise PlacesAPIError(
            f"Categoría '{category}' no está mapeada a un tag de OpenStreetMap "
            f"todavía. Categorías soportadas hoy: {', '.join(sorted(CATEGORY_TAG_MAP))}. "
            "Para agregar otra, edita CATEGORY_TAG_MAP en scrapers/maps_discovery.py "
            "(busca el tag correcto en https://wiki.openstreetmap.org/wiki/Map_Features)."
        )

    seen_place_ids: set[str] = set()
    results: list[dict] = []

    with httpx.Client() as client:
        bbox = _geocode_zone(zone, client)
        time.sleep(1)  # respeta el límite de ~1 req/seg de Nominatim antes de pegarle a Overpass
        elements = _overpass_query(bbox, tags, client)

        for element in elements:
            biz = _element_to_business_dict(element, zone, category)
            if biz is None:
                continue
            if biz["place_id"] in seen_place_ids:
                continue
            seen_place_ids.add(biz["place_id"])
            results.append(biz)

    if not results:
        logger.info("Overpass sin resultados para zona=%r category=%r", zone, category)

    return results