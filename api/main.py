"""
App principal de FastAPI.

Se corre con: uvicorn api.main:app --reload --port 8000
(desde la carpeta backend/, con el venv activado)

`--reload` hace que uvicorn reinicie el servidor automáticamente cada vez
que guardas un cambio en el código; es solo para desarrollo, en
producción (Día 7, Railway) no se usa.
"""
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.config import settings
from database.session import get_db
from database.models import Business, SearchRun, Lead
from scrapers.maps_discovery import discover_businesses, PlacesAPIError
from analyzer.gemini_client import GeminiClient, GeminiQuotaExhaustedError
from analyzer.prompt_builder import should_skip_lead
from analyzer.lead_evaluator import parse_gemini_response, GeminiResponseParseError
from api.schemas import (
    SearchRequest,
    SearchResponse,
    HealthResponse,
    AnalyzeLeadResponse,
    LeadDetail,
    LeadListItem,
    GenerateEmailResponse,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CustoFinder API",
    description="Sistema de prospección inteligente de clientes para freelancers/agencias de software.",
    version="0.1.0",
)

# Cliente de Gemini "perezoso": se crea la primera vez que se necesita,
# no al arrancar la app. Así, si GEMINI_API_KEYS está mal configurada en
# .env, /api/health y /api/search siguen funcionando normalmente y el
# error solo aparece cuando de verdad se llama a un endpoint de leads.
_gemini_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client


def _business_context(biz: Business) -> dict:
    return {
        "name": biz.name,
        "category": biz.category,
        "zone": biz.zone,
        "address": biz.address,
        "phone": biz.phone,
        "has_website": biz.has_website,
    }


@app.get("/api/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """
    Healthcheck simple. Railway (Día 7) lo va a golpear periódicamente
    para saber si el contenedor sigue vivo y responde. Hoy no valida la
    conexión a la base de datos a propósito: lo dejamos simple para no
    tumbar el deploy si la DB tarda en arrancar. Si Día 2+ necesitamos
    un healthcheck "profundo" (que sí chequee la DB), lo agregamos como
    endpoint separado, ej. /api/health/db.
    """
    return HealthResponse(status="ok", environment=settings.ENVIRONMENT)


@app.post("/api/search", response_model=SearchResponse)
def search_businesses(payload: SearchRequest, db: Session = Depends(get_db)) -> SearchResponse:
    """
    Flujo:
    1. Crea un SearchRun (registro de esta corrida).
    2. Llama a discover_businesses(zone, category) contra OpenStreetMap.
    3. Hace UPSERT de cada negocio por `place_id`: si ya existe (porque el
       usuario repitió la búsqueda), actualiza sus datos; si no existe, lo
       inserta. Esto evita duplicados cuando la misma zona/categoría se
       busca más de una vez.
    4. Actualiza el SearchRun con los conteos finales y hace commit.
    """
    search_run = SearchRun(zone=payload.zone, category=payload.category)
    db.add(search_run)
    db.flush()  # asigna el id sin cerrar la transacción todavía

    try:
        businesses_data = discover_businesses(zone=payload.zone, category=payload.category)
    except PlacesAPIError as exc:
        db.rollback()
        logger.error("Error llamando a OpenStreetMap: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    leads_without_website = 0

    for biz in businesses_data:
        existing = db.scalar(select(Business).where(Business.place_id == biz["place_id"]))

        if existing:
            # UPDATE: el negocio ya existía (búsqueda repetida). Refrescamos
            # sus datos por si cambiaron (teléfono, etc).
            for field, value in biz.items():
                if field != "place_id":
                    setattr(existing, field, value)
        else:
            # INSERT: negocio nuevo.
            db.add(Business(**biz))

        if not biz["has_website"]:
            leads_without_website += 1

    search_run.businesses_found = len(businesses_data)
    search_run.leads_without_website = leads_without_website

    db.commit()
    db.refresh(search_run)

    return SearchResponse(
        run_id=search_run.id,
        businesses_found=search_run.businesses_found,
        leads_without_website=search_run.leads_without_website,
    )


@app.post("/api/leads/{business_id}/analyze", response_model=AnalyzeLeadResponse)
def analyze_lead_endpoint(
    business_id: int, force: bool = False, db: Session = Depends(get_db)
) -> AnalyzeLeadResponse:
    """
    Evalúa (o reevalúa) un negocio con Gemini. Por defecto, si el lead ya
    fue analizado antes, NO vuelve a gastar cuota de Gemini — devuelve el
    resultado guardado. Pasa ?force=true para forzar una reevaluación.
    """
    business = db.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail=f"Business {business_id} no existe")

    lead = db.scalar(select(Lead).where(Lead.business_id == business_id))
    if lead is None:
        lead = Lead(business_id=business_id)
        db.add(lead)
        db.flush()

    if lead.analyzed_at is not None and not force:
        return AnalyzeLeadResponse(
            lead_id=lead.id,
            business_id=business_id,
            skipped=lead.pipeline_stage == "descartado",
            skip_reason=None,
            urgency_score=lead.urgency_score,
            recommended_service=lead.recommended_service,
            sales_arguments=json.loads(lead.sales_arguments) if lead.sales_arguments else None,
            pipeline_stage=lead.pipeline_stage,
        )

    context = _business_context(business)
    skip, reason = should_skip_lead(context)

    if skip:
        lead.pipeline_stage = "descartado"
        lead.urgency_score = None
        lead.recommended_service = None
        lead.sales_arguments = json.dumps([reason])
        lead.analyzed_at = datetime.now(timezone.utc)
        db.commit()
        return AnalyzeLeadResponse(
            lead_id=lead.id,
            business_id=business_id,
            skipped=True,
            skip_reason=reason,
            urgency_score=None,
            recommended_service=None,
            sales_arguments=[reason],
            pipeline_stage=lead.pipeline_stage,
        )

    try:
        client = get_gemini_client()
        raw = client.analyze_lead(context)
        parsed = parse_gemini_response(raw)
    except GeminiQuotaExhaustedError as exc:
        db.rollback()
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except (GeminiResponseParseError, RuntimeError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"Error evaluando con Gemini: {exc}") from exc

    lead.urgency_score = parsed["urgency_score"]
    lead.recommended_service = parsed["recommended_service"]
    lead.sales_arguments = json.dumps(parsed["sales_arguments"])
    lead.analyzed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(lead)

    return AnalyzeLeadResponse(
        lead_id=lead.id,
        business_id=business_id,
        skipped=False,
        skip_reason=None,
        urgency_score=lead.urgency_score,
        recommended_service=lead.recommended_service,
        sales_arguments=parsed["sales_arguments"],
        pipeline_stage=lead.pipeline_stage,
    )


@app.post("/api/leads/{lead_id}/generate-email", response_model=GenerateEmailResponse)
def generate_email_endpoint(lead_id: int, db: Session = Depends(get_db)) -> GenerateEmailResponse:
    """Genera (o regenera) el email de prospección de un lead YA analizado."""
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} no existe")
    if lead.analyzed_at is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"El lead {lead_id} todavía no fue analizado. Llama primero a "
                f"POST /api/leads/{lead.business_id}/analyze"
            ),
        )

    business = db.get(Business, lead.business_id)
    lead_context = {
        **_business_context(business),
        "recommended_service": lead.recommended_service,
        "sales_arguments": json.loads(lead.sales_arguments) if lead.sales_arguments else [],
    }

    try:
        client = get_gemini_client()
        email_text = client.generate_email(lead_context)
    except GeminiQuotaExhaustedError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"Error generando email con Gemini: {exc}") from exc

    lead.email_draft = email_text
    db.commit()

    return GenerateEmailResponse(lead_id=lead.id, email_draft=email_text)


@app.get("/api/leads/{lead_id}", response_model=LeadDetail)
def get_lead_endpoint(lead_id: int, db: Session = Depends(get_db)) -> LeadDetail:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} no existe")

    business = db.get(Business, lead.business_id)

    return LeadDetail(
        id=lead.id,
        business_id=lead.business_id,
        business_name=business.name,
        zone=business.zone,
        category=business.category,
        urgency_score=lead.urgency_score,
        recommended_service=lead.recommended_service,
        sales_arguments=json.loads(lead.sales_arguments) if lead.sales_arguments else None,
        email_draft=lead.email_draft,
        pipeline_stage=lead.pipeline_stage,
        analyzed_at=lead.analyzed_at,
    )


@app.get("/api/leads", response_model=List[LeadListItem])
def list_leads_endpoint(
    stage: Optional[str] = None,
    min_urgency: Optional[float] = None,
    db: Session = Depends(get_db),
) -> List[LeadListItem]:
    """Filtros opcionales: ?stage=nuevo&min_urgency=7"""
    query = select(Lead, Business).join(Business, Lead.business_id == Business.id)

    if stage:
        query = query.where(Lead.pipeline_stage == stage)
    if min_urgency is not None:
        query = query.where(Lead.urgency_score >= min_urgency)

    rows = db.execute(query).all()

    return [
        LeadListItem(
            id=lead.id,
            business_id=lead.business_id,
            business_name=business.name,
            zone=business.zone,
            urgency_score=lead.urgency_score,
            recommended_service=lead.recommended_service,
            pipeline_stage=lead.pipeline_stage,
        )
        for lead, business in rows
    ]