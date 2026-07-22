"""
Cliente HTTP para la API de Gemini (Google AI Studio, REST directo).

DECISIÓN TÉCNICA (Día 2): se llama al endpoint REST de Gemini con httpx
directo, en vez de instalar el SDK oficial (google-generativeai /
google-genai). Razones: (1) ya usamos httpx en scrapers/maps_discovery.py,
mismo patrón, sin dependencias nuevas; (2) el SDK de Google ha cambiado de
nombre más de una vez; llamar al REST endpoint evita quedar atado a eso;
(3) queremos control fino sobre reintentos y rotación de keys.

RESTRICCIÓN DEL PROYECTO: SOLO modelos Flash / Flash-Lite de Google AI
Studio (gratis, sin tarjeta, sin Vertex AI, sin modelos Pro).

LÍMITES DEL FREE TIER (Google los ajusta seguido, confírmalos en
https://ai.google.dev/gemini-api/docs/rate-limits si algo no cuadra):
  - gemini-2.5-flash:      ~10 req/min, ~250 req/día
  - gemini-2.5-flash-lite: ~15 req/min, ~1000 req/día
Por eso soportamos varias GEMINI_API_KEYS separadas por coma — cada key
gratuita de Google AI Studio tiene su propia cuota independiente.
"""
from __future__ import annotations

import json
import logging
import time
from itertools import cycle
from typing import Optional

import httpx

from database.config import settings
from analyzer.prompt_builder import build_system_prompt, build_lead_prompt, build_email_prompt

logger = logging.getLogger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

# Nunca agregues aquí un modelo Pro o de Vertex AI: rompe la restricción
# no negociable del proyecto de "100% gratis, sin tarjeta".
ALLOWED_MODELS = {"gemini-2.5-flash", "gemini-2.5-flash-lite"}


class GeminiQuotaExhaustedError(Exception):
    """Se agotó la cuota de TODAS las API keys configuradas: todas
    respondieron 429 en el mismo ciclo de reintentos."""


class GeminiClient:
    def __init__(self, api_keys: Optional[list[str]] = None, model: Optional[str] = None):
        keys = api_keys if api_keys is not None else [
            k.strip() for k in settings.GEMINI_API_KEYS.split(",") if k.strip()
        ]
        if not keys:
            raise ValueError(
                "No hay ninguna GEMINI_API_KEYS configurada en .env. "
                "Consigue una gratis (sin tarjeta) en https://aistudio.google.com/apikey"
            )
        self._keys = keys
        self._key_cycle = cycle(keys)

        chosen_model = model or getattr(settings, "GEMINI_MODEL", None) or "gemini-2.5-flash"
        if chosen_model not in ALLOWED_MODELS:
            raise ValueError(
                f"Modelo '{chosen_model}' no permitido. Este proyecto solo usa "
                f"modelos gratis de Google AI Studio: {', '.join(sorted(ALLOWED_MODELS))}."
            )
        self._model = chosen_model

    def _endpoint(self, api_key: str) -> str:
        return f"{GEMINI_BASE_URL}/{self._model}:generateContent?key={api_key}"

    def _call(self, system_prompt: str, user_prompt: str) -> str:
        """
        Hace UNA llamada "lógica" a Gemini (con reintentos internos).
        Rota de API key en cada 429 y reintenta con backoff en 503.
        Devuelve el TEXTO CRUDO de la respuesta — sin parsear JSON todavía,
        eso lo hace lead_evaluator.py.
        """
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024},
        }

        keys_tried = 0
        backoff = 2.0

        with httpx.Client() as client:
            while True:
                api_key = next(self._key_cycle)
                try:
                    response = client.post(self._endpoint(api_key), json=payload, timeout=30.0)
                except httpx.RequestError as exc:
                    raise RuntimeError(f"Error de red llamando a Gemini: {exc}") from exc

                if response.status_code == 200:
                    # NO uses response.json() acá: httpx a veces falla al
                    # adivinar la codificación cuando Google no manda un
                    # charset explícito en el header Content-Type, y termina
                    # leyendo los bytes UTF-8 como si fueran Latin-1 (produce
                    # "Ã©" en vez de "é"). Decodificamos UTF-8 a mano.
                    try:
                        data = json.loads(response.content.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        raise RuntimeError(
                            f"No se pudo decodificar la respuesta de Gemini como UTF-8: {exc}"
                        ) from exc
                    try:
                        return data["candidates"][0]["content"]["parts"][0]["text"]
                    except (KeyError, IndexError) as exc:
                        raise RuntimeError(
                            f"Respuesta de Gemini con forma inesperada: {data}"
                        ) from exc

                if response.status_code == 429:
                    keys_tried += 1
                    logger.warning("Gemini 429 (cuota agotada) en una API key. Rotando.")
                    if keys_tried >= len(self._keys):
                        raise GeminiQuotaExhaustedError(
                            f"Las {len(self._keys)} GEMINI_API_KEYS configuradas están "
                            "sin cuota (todas respondieron 429). Espera a que se resetee "
                            "la cuota diaria, o agrega otra key gratis en "
                            "https://aistudio.google.com/apikey"
                        )
                    continue

                if response.status_code == 503:
                    if backoff > 20:
                        raise RuntimeError(
                            "Gemini respondió 503 (modelo sobrecargado) varias veces "
                            "seguidas. Intenta de nuevo en unos minutos."
                        )
                    logger.warning("Gemini 503 (sobrecargado). Reintentando en %.0fs...", backoff)
                    time.sleep(backoff)
                    backoff *= 2
                    continue

                raise RuntimeError(
                    f"Gemini respondió {response.status_code} inesperado: {response.text[:300]}"
                )

    def analyze_lead(self, context: dict) -> str:
        """Evalúa un negocio como lead. `context` es el dict de un Business
        (name, category, zone, address, phone, has_website). Devuelve el
        texto crudo de Gemini (probablemente JSON envuelto en markdown)."""
        system_prompt = build_system_prompt()
        user_prompt = build_lead_prompt(context)
        return self._call(system_prompt, user_prompt)

    def generate_email(self, lead_context: dict) -> str:
        """Genera el email de prospección para un lead ya evaluado.
        `lead_context` incluye los datos del negocio + el resultado de
        analyze_lead (urgency_score, recommended_service, sales_arguments).
        Devuelve texto plano (asunto + cuerpo), no JSON."""
        system_prompt = build_system_prompt()
        user_prompt = build_email_prompt(lead_context)
        return self._call(system_prompt, user_prompt)