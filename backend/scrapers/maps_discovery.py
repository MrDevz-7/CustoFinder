"""
Descubre negocios locales vía OpenStreetMap: Nominatim geocodifica la zona,
Overpass API trae los negocios de esa categoría dentro del área resultante.
Decisiones de diseño, limitaciones conocidas y trade-offs frente a Google
Places: ver docs/DECISIONES_TECNICAS.md.
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

# Categoría (texto libre en español) -> tag(s) de OpenStreetMap.
# Agregar categorías nuevas: https://wiki.openstreetmap.org/wiki/Map_Features
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
    """Error al descubrir negocios: red, rate limit, zona o categoría
    inválida. Nombre heredado de la integración con Google Places."""


def _user_agent() -> str:
    contact = settings.OSM_CONTACT_EMAIL or "sin-contacto-configurado"
    return f"CustoFinder/0.1 (contacto: {contact})"


def _ipv4_client() -> httpx.Client:
    """Cliente httpx forzado a IPv4 (algunos hosts gratuitos, ej. Render,
    no rutean IPv6 de salida). Detalle: docs/DECISIONES_TECNICAS.md."""
    return httpx.Client(transport=httpx.HTTPTransport(local_address="0.0.0.0"))


def _geocode_zone(zone: str, client: httpx.Client) -> tuple[float, float, float, float]:
    """Geocodifica `zone` con Nominatim. Devuelve bbox (south, west, north, east)."""
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
    """Trae los elementos (nodes/ways/relations) que matchean `tags` dentro de `bbox`."""
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
    """Convierte un elemento crudo de Overpass al dict que espera api/main.py."""
    tags = element.get("tags", {})
    name = tags.get("name")
    if not name:
        return None
    if element["type"] == "node":
        lat, lon = element.get("lat"), element.get("lon")
    else:
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
    Descubre negocios de `category` en `zone` vía OpenStreetMap.

    Returns:
        Lista de dicts: place_id, name, category, address, zone, phone,
        has_website, rating, review_count, latitude, longitude.
    Raises:
        PlacesAPIError: zona no geocodificable, categoría no soportada,
        o rate limit en Nominatim/Overpass.
    """
    tags = CATEGORY_TAG_MAP.get(category.strip().lower())
    if not tags:
        raise PlacesAPIError(
            f"Categoría '{category}' no está mapeada a un tag de OpenStreetMap "
            f"todavía. Categorías soportadas hoy: {', '.join(sorted(CATEGORY_TAG_MAP))}."
        )
    seen_place_ids: set[str] = set()
    results: list[dict] = []
    with _ipv4_client() as client:
        bbox = _geocode_zone(zone, client)
        time.sleep(1)  # respeta el límite de ~1 req/seg de Nominatim antes de Overpass
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


def find_businesses_with_website_url(zone: str, category: str) -> list[dict]:
    """
    Como discover_businesses(), más la clave "website" (URL cruda de OSM)
    que Playwright necesita para navegar. Separada de discover_businesses()
    para no arriesgar ese flujo — detalle en docs/DECISIONES_TECNICAS.md.
    """
    tags = CATEGORY_TAG_MAP.get(category.strip().lower())
    if not tags:
        supported = ", ".join(sorted(CATEGORY_TAG_MAP.keys()))
        raise PlacesAPIError(
            f"Categoría '{category}' no soportada. Categorías disponibles: {supported}"
        )
    seen_place_ids: set[str] = set()
    results: list[dict] = []
    with _ipv4_client() as client:
        bbox = _geocode_zone(zone, client)
        time.sleep(1)  # mismo respeto al rate limit que discover_businesses()
        elements = _overpass_query(bbox, tags, client)
    for element in elements:
        biz = _element_to_business_dict(element, zone, category)
        if biz is None:
            continue
        if biz["place_id"] in seen_place_ids:
            continue
        seen_place_ids.add(biz["place_id"])
        element_tags = element.get("tags", {})
        biz["website"] = element_tags.get("website") or element_tags.get("contact:website")
        results.append(biz)
    return results