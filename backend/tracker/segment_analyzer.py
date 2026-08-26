"""
Analytics de efectividad por segmento (Día 6) — funcionalidad diferencial
#2 del proyecto: para cada combinación de rubro (Business.category) +
zona (Business.zone) + rango de urgency_score, calcula cuántos leads
llegaron a esa combinación, cuántos "convirtieron", y la tasa resultante.

DEFINICIÓN DE "CONVERSIÓN" (decisión documentada, ver informe de cierre
Día 6 para el detalle completo):

Un lead cuenta como convertido si existe al menos un PipelineEvent con
to_stage == "cerrado" para ese lead — es decir, PASÓ por "cerrado" en
algún momento de su historial. NO usamos Lead.pipeline_stage == "cerrado"
(el estado actual), porque eso perdería conversiones reales de leads que
se cerraron y luego se movieron a otro estado (reapertura, corrección de
un error de captura en el kanban, etc). La conversión es un evento que
ocurrió, no una condición que tiene que seguir vigente hoy — es el mismo
criterio que "deal won" en un CRM: queda registrado aunque el deal se
reabra después por otra razón administrativa.

Consecuencia práctica: el número de "cerrados" que arroja este módulo
puede no coincidir con un filtro simple de
`SELECT COUNT(*) FROM leads WHERE pipeline_stage = 'cerrado'` — esto es
intencional, no un bug.

Los leads sin urgency_score (todavía no analizados por Gemini) se
excluyen del cálculo: no hay rango de score que asignarles, y
mezclarlos en un bucket "sin score" ensuciaría la comparación de
efectividad, que es justamente lo que este análisis quiere resaltar.
"""
from typing import Optional, TypedDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Lead, Business, PipelineEvent

# Rangos de urgency_score. Los límites son inclusivos en ambos extremos
# de cada bucket (0-33, 34-66, 67-100) y cubren todo el rango 0-100 sin
# huecos ni solapamientos.
SCORE_BUCKETS: tuple[tuple[float, float, str], ...] = (
    (0, 3.3, "0-3.3 (baja)"),
    (3.4, 6.6, "3.4-6.6 (media)"),
    (6.7, 10, "6.7-10 (alta)"),
)


class SegmentEffectiveness(TypedDict):
    category: str
    zone: str
    score_range: str
    total_leads: int
    closed_leads: int
    conversion_rate: float


def _score_bucket(score: float) -> str:
    """Mapea un urgency_score al rango que le corresponde.
    Si por algún motivo el score viniera fuera de 0-100 (no debería,
    pero Gemini es un modelo externo y no controlamos su output al
    100%), lo asignamos al bucket extremo más cercano en vez de
    excluirlo silenciosamente -- así un dato raro se ve en el
    resultado y se puede investigar, en vez de desaparecer.
    """
    if score < 0:
        return SCORE_BUCKETS[0][2]
    if score > 10:
        return SCORE_BUCKETS[-1][2]
    for low, high, label in SCORE_BUCKETS:
        if low <= score <= high:
            return label
    return SCORE_BUCKETS[-1][2]  # inalcanzable en teoría, red de seguridad


def compute_segment_effectiveness(
    db: Session,
    zone: Optional[str] = None,
    category: Optional[str] = None,
) -> list[SegmentEffectiveness]:
    """Calcula la tabla de efectividad por segmento (rubro + zona + rango
    de score). `zone` y `category` son filtros opcionales exactos
    (case-sensitive, tal como están guardados en `businesses`).
    """
    query = (
        select(Lead.id, Lead.urgency_score, Business.category, Business.zone)
        .join(Business, Lead.business_id == Business.id)
        .where(Lead.urgency_score.is_not(None))
    )
    if zone:
        query = query.where(Business.zone == zone)
    if category:
        query = query.where(Business.category == category)
    rows = db.execute(query).all()

    # Un solo query aparte para saber qué leads pasaron por "cerrado"
    # alguna vez -- más barato que hacer un EXISTS por cada lead.
    closed_lead_ids = set(
        db.scalars(
            select(PipelineEvent.lead_id)
            .where(PipelineEvent.to_stage == "cerrado")
            .distinct()
        ).all()
    )

    segments: dict[tuple[str, str, str], dict[str, int]] = {}
    for lead_id, score, biz_category, biz_zone in rows:
        key = (biz_category or "sin categoría", biz_zone or "sin zona", _score_bucket(score))
        seg = segments.setdefault(key, {"total": 0, "closed": 0})
        seg["total"] += 1
        if lead_id in closed_lead_ids:
            seg["closed"] += 1

    result: list[SegmentEffectiveness] = []
    for (seg_category, seg_zone, score_range), counts in segments.items():
        total = counts["total"]
        closed = counts["closed"]
        conversion_rate = round(closed / total, 4) if total else 0.0
        result.append(
            SegmentEffectiveness(
                category=seg_category,
                zone=seg_zone,
                score_range=score_range,
                total_leads=total,
                closed_leads=closed,
                conversion_rate=conversion_rate,
            )
        )

    # Mejor tasa de conversión primero -- es lo que el usuario quiere ver
    # arriba: qué segmento conviene más priorizar.
    result.sort(key=lambda r: r["conversion_rate"], reverse=True)
    return result