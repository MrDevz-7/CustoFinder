"""
Modelos SQLAlchemy 2.x (sintaxis declarativa moderna con `Mapped` /
`mapped_column`).

Por qué esta sintaxis y no la "vieja" (`Column(String)` suelto):
- `Mapped[str]` le dice al editor/type-checker el tipo real de Python
  de cada atributo, así te autocompleta y  avisa errores de tipo antes
  de correr el código.
- `mapped_column(...)` es donde configuro lo específico de la base de
  datos (tipo de columna SQL, si es nullable, default, índices, etc).

Este archivo define el ESQUEMA COMPLETO del proyecto (5 tablas), aunque
hoy (Día 1) solo usamos activamente `Business` y `SearchRun`. Las otras
tres (`Lead`, `CompetitorInfo`, `PipelineEvent`) se llenan de lógica en
días siguientes, pero las creamos ya para que Alembic las versione desde
el principio y no tengamos que generar migraciones de "agregar tabla"
después con datos ya en producción.
"""
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import (
    String,
    Float,
    Integer,
    Boolean,
    Text,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    DateTime,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    """Helper para timestamps en UTC. Evitamos datetime.utcnow() (deprecado
    en Python 3.12+ y ambiguo sobre timezone); usamos datetime.now(timezone.utc)."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Business(Base):
    """Un negocio local descubierto vía Google Places API."""

    __tablename__ = "businesses"
    __table_args__ = (UniqueConstraint("place_id", name="uq_business_place_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    place_id: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    zone: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    has_website: Mapped[bool] = mapped_column(Boolean, default=False)
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    review_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    leads: Mapped[List["Lead"]] = relationship(back_populates="business")

    def __repr__(self) -> str:
        return f"<Business id={self.id} name={self.name!r} has_website={self.has_website}>"


# Los 6 stages permitidos del embudo comercial. DEBEN calzar exacto con el
# CheckConstraint de la tabla `leads` (ck_lead_pipeline_stage, más abajo) --
# si agregas un stage aquí sin agregarlo también al CheckConstraint (o
# viceversa), un PATCH que pase la validación de Python fallará igual al
# hacer commit, con un IntegrityError de Postgres.
# Nota: "respondio" y "reunion" van sin tilde a propósito -- estos valores
# viajan en URLs/JSON/query params y ya tuvimos un bug de encoding en
# PowerShell con tildes en el body de las respuestas (ver ForceUTF8JSONMiddleware
# en api/main.py).
PIPELINE_STAGES: tuple[str, ...] = (
    "nuevo",
    "contactado",
    "respondio",
    "reunion",
    "cerrado",
    "descartado",
)


class Lead(Base):
    """Un negocio evaluado por IA (Día 2) con score de urgencia y
    seguimiento comercial (pipeline)."""

    __tablename__ = "leads"
    __table_args__ = (
        CheckConstraint(
            "pipeline_stage IN ('nuevo','contactado','respondio','reunion','cerrado','descartado')",
            name="ck_lead_pipeline_stage",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    urgency_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recommended_service: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # sales_arguments guarda un JSON serializado como texto (Text). En Día 2,
    # cuando definamos la forma exacta de este JSON, se puede migrar a JSONB
    # nativo de Postgres si conviene.
    sales_arguments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    email_draft: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pipeline_stage: Mapped[str] = mapped_column(String(20), default="nuevo")
    analyzed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    business: Mapped["Business"] = relationship(back_populates="leads")
    competitor_infos: Mapped[List["CompetitorInfo"]] = relationship(back_populates="lead")
    pipeline_events: Mapped[List["PipelineEvent"]] = relationship(back_populates="lead")

    def __repr__(self) -> str:
        return f"<Lead id={self.id} business_id={self.business_id} stage={self.pipeline_stage!r}>"


class CompetitorInfo(Base):
    """Información de competidores cercanos al lead (se llena en días
    siguientes con scraping adicional)."""

    __tablename__ = "competitor_infos"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"))
    competitor_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    competitor_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    has_online_menu: Mapped[bool] = mapped_column(Boolean, default=False)
    has_booking: Mapped[bool] = mapped_column(Boolean, default=False)
    has_ecommerce: Mapped[bool] = mapped_column(Boolean, default=False)
    has_blog: Mapped[bool] = mapped_column(Boolean, default=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lead: Mapped["Lead"] = relationship(back_populates="competitor_infos")


class PipelineEvent(Base):
    """Historial de cambios de etapa de un Lead (auditoría del embudo
    comercial). Se llena cuando el equipo mueve un lead de etapa."""

    __tablename__ = "pipeline_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"))
    from_stage: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    to_stage: Mapped[str] = mapped_column(String(20))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lead: Mapped["Lead"] = relationship(back_populates="pipeline_events")


class SearchRun(Base):
    """Registro de cada corrida de búsqueda/prospección (una llamada a
    POST /api/search)."""

    __tablename__ = "search_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    zone: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(120))
    businesses_found: Mapped[int] = mapped_column(Integer, default=0)
    leads_without_website: Mapped[int] = mapped_column(Integer, default=0)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"<SearchRun id={self.id} zone={self.zone!r} category={self.category!r}>"