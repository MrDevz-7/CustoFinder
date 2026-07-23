"""
Scraper de sitios de competencia (Día 3).

Dos responsabilidades separadas:
1. find_competitors_with_website(business, limit): descubre negocios
   cercanos (misma zona/categoría) que sí tienen sitio web, usando OSM
   (reutiliza scrapers/maps_discovery.py).
2. analyze_competitor_site(url) / analyze_competitor_sites(urls): visita
   cada sitio con Playwright y detecta, con heurísticas conservadoras de
   texto, si tiene menú online, reservas, e-commerce o blog.

Filosofía de detección: mejor un falso negativo (no detectar algo que sí
está) que un falso positivo (inventar una característica). Si el sitio no
usa ninguna palabra/selector reconocible, se marca como False, no se
adivina.

Manejo de errores: un sitio caído, lento o con certificado inválido NUNCA
debe tumbar el batch completo. Cada análisis individual atrapa sus propios
errores y los reporta en el campo "error" del dict devuelto.
"""

import logging

from playwright.sync_api import Browser, TimeoutError as PlaywrightTimeoutError, sync_playwright

from scrapers.maps_discovery import PlacesAPIError, find_businesses_with_website_url

logger = logging.getLogger(__name__)

# Límite de tiempo por sitio: si un sitio individual tarda más que esto,
# lo abandonamos y seguimos con el siguiente, en vez de colgar todo el batch.
SITE_TIMEOUT_MS = 10_000

# Heurísticas de texto (todo en minúsculas, se compara contra el texto
# visible de <body>). Listas conservadoras a propósito: mejor pocas
# palabras muy específicas que muchas genéricas que generen falsos positivos.
MENU_KEYWORDS = ["menú", "menu", "carta", "nuestros platos", "food menu"]
BOOKING_KEYWORDS = [
    "reservar", "reserva tu", "reserva ahora", "agendar cita", "agenda tu cita",
    "pedir cita", "book now", "book a table", "booking",
]
ECOMMERCE_KEYWORDS = [
    "añadir al carrito", "agregar al carrito", "add to cart", "carrito de compras",
    "comprar ahora", "finalizar compra", "checkout",
]
BLOG_KEYWORDS = ["blog", "últimas noticias", "últimas novedades", "artículos recientes"]


def find_competitors_with_website(business: dict, limit: int = 5) -> list[dict]:
    """
    Busca hasta `limit` negocios cercanos (misma zona/categoría que
    `business`) que sí tengan sitio web, para poder analizarlos.

    `business` debe traer al menos: place_id, zone, category (las mismas
    claves que expone el modelo Business).

    Excluye al propio negocio de los resultados (por place_id, para no
    "competir contra sí mismo" si aparece en su propia búsqueda de OSM).

    Nunca lanza excepción: si falla la búsqueda en OSM (zona no
    geocodificable, categoría no soportada, rate limit), loguea el error
    y devuelve lista vacía — es preferible un lead sin competencia
    analizada a que el endpoint completo falle con un 500.
    """
    zone = business.get("zone")
    category = business.get("category")

    if not zone or not category:
        logger.warning(
            "Lead con business_id=%s no tiene zone/category cargados; "
            "no se puede buscar competencia.",
            business.get("place_id"),
        )
        return []

    try:
        candidates = find_businesses_with_website_url(zone=zone, category=category)
    except PlacesAPIError as exc:
        logger.error("No se pudo buscar competencia vía OSM para zone=%s category=%s: %s",
                     zone, category, exc)
        return []

    own_place_id = business.get("place_id")
    competitors = [
        c for c in candidates
        if c.get("website") and c.get("place_id") != own_place_id
    ]

    return competitors[:limit]


def _detect_features(page) -> dict:
    """Corre las heurísticas de texto/selector sobre una página ya cargada."""
    try:
        text = page.inner_text("body").lower()
    except Exception:
        # Si ni siquiera se puede leer el <body> (sitio raro, todo en
        # iframes, etc.), seguimos con texto vacío: todas las heurísticas
        # de texto darán False, que es el resultado conservador correcto.
        text = ""

    has_online_menu = any(keyword in text for keyword in MENU_KEYWORDS)

    has_booking = any(keyword in text for keyword in BOOKING_KEYWORDS)
    if not has_booking:
        try:
            has_booking = page.locator(
                "a[href*='calendly'], iframe[src*='calendly'], a[href*='booking.com'], "
                "a[href*='reservas'], a[href*='booksy']"
            ).count() > 0
        except Exception:
            pass

    has_ecommerce = any(keyword in text for keyword in ECOMMERCE_KEYWORDS)
    if not has_ecommerce:
        try:
            has_ecommerce = page.locator(
                "[class*='cart'], [id*='cart'], a[href*='/cart'], a[href*='/checkout'], "
                "a[href*='shopify'], form[action*='cart']"
            ).count() > 0
        except Exception:
            pass

    has_blog = any(keyword in text for keyword in BLOG_KEYWORDS)
    if not has_blog:
        try:
            has_blog = page.locator("a[href*='/blog'], a[href*='/noticias']").count() > 0
        except Exception:
            pass

    return {
        "has_online_menu": has_online_menu,
        "has_booking": has_booking,
        "has_ecommerce": has_ecommerce,
        "has_blog": has_blog,
    }


def _analyze_with_browser(browser: Browser, url: str) -> dict:
    """Analiza un sitio reutilizando un navegador ya abierto (uso interno)."""
    result = {
        "competitor_url": url,
        "has_online_menu": False,
        "has_booking": False,
        "has_ecommerce": False,
        "has_blog": False,
        "error": None,
    }

    normalized_url = url if url.startswith(("http://", "https://")) else f"https://{url}"

    page = browser.new_page()
    try:
        page.set_default_timeout(SITE_TIMEOUT_MS)
        try:
            # domcontentloaded (no "load"/"networkidle") a propósito: no
            # queremos esperar a que carguen TODOS los recursos (imágenes,
            # analytics, chat widgets) de un sitio de negocio pequeño; con
            # que el HTML esté listo alcanza para nuestras heurísticas de
            # texto. Playwright sigue redirects automáticamente.
            page.goto(normalized_url, timeout=SITE_TIMEOUT_MS, wait_until="domcontentloaded")
        except PlaywrightTimeoutError:
            result["error"] = f"Timeout: el sitio no respondió en {SITE_TIMEOUT_MS // 1000}s"
            return result
        except Exception as exc:
            result["error"] = f"No se pudo cargar el sitio: {exc}"
            return result

        result["competitor_url"] = page.url  # URL final, después de redirects
        result.update(_detect_features(page))
    finally:
        page.close()

    return result


def analyze_competitor_site(url: str) -> dict:
    """
    Analiza UN sitio suelto, abriendo y cerrando su propio Chromium.
    Útil para probar un sitio individual desde una consola de Python.
    Para analizar varios sitios (el caso del endpoint), usa
    analyze_competitor_sites() en vez de llamar esta en un loop —
    reutiliza un solo navegador y es mucho más rápido.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            return _analyze_with_browser(browser, url)
        finally:
            browser.close()


def analyze_competitor_sites(urls: list[str]) -> list[dict]:
    """
    Versión batch: abre UN Chromium y lo reutiliza para todas las URLs en
    orden, en vez de lanzar un proceso de Chromium nuevo por cada sitio.
    Un sitio individual que falle (timeout, DNS, certificado) no aborta
    el resto: su dict de resultado trae "error" con el detalle y se sigue
    con el siguiente.
    """
    if not urls:
        return []

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for url in urls:
                results.append(_analyze_with_browser(browser, url))
        finally:
            browser.close()

    return results