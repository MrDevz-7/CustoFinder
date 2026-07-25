// frontend/src/app/leads/[id]/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getLead, generateEmail, getCompetitors, updateLeadStage } from "@/lib/api";
import { LeadDetail, CompetitorInfoOut, PipelineStage } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const STAGES: { value: PipelineStage; label: string }[] = [
  { value: "nuevo", label: "Nuevo" },
  { value: "contactado", label: "Contactado" },
  { value: "respondio", label: "Respondió" },
  { value: "reunion", label: "Reunión" },
  { value: "cerrado", label: "Cerrado" },
  { value: "descartado", label: "Descartado" },
];

export default function LeadDetailPage() {
  const params = useParams();
  const leadId = Number(params.id);

  const [lead, setLead] = useState<LeadDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [emailLoading, setEmailLoading] = useState(false);
  const [emailError, setEmailError] = useState<string | null>(null);

  const [competitors, setCompetitors] = useState<CompetitorInfoOut[] | null>(null);
  const [competitorsLoading, setCompetitorsLoading] = useState(false);
  const [competitorsError, setCompetitorsError] = useState<string | null>(null);

  const [stageSaving, setStageSaving] = useState(false);
  const [stageError, setStageError] = useState<string | null>(null);

  useEffect(() => {
    if (Number.isNaN(leadId)) return;
    let cancelled = false;

    async function loadLead() {
      setLoading(true);
      setError(null);
      try {
        const data = await getLead(leadId);
        if (!cancelled) setLead(data);
      } catch (err) {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "Error al cargar el lead");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadLead();
    return () => {
      cancelled = true;
    };
  }, [leadId]);

  async function handleGenerateEmail() {
    setEmailLoading(true);
    setEmailError(null);
    try {
      const result = await generateEmail(leadId);
      setLead((prev) => (prev ? { ...prev, email_draft: result.email_draft } : prev));
    } catch (err) {
      setEmailError(err instanceof Error ? err.message : "Error al generar el email");
    } finally {
      setEmailLoading(false);
    }
  }

  async function handleAnalyzeCompetitors() {
    setCompetitorsLoading(true);
    setCompetitorsError(null);
    try {
      const result = await getCompetitors(leadId);
      setCompetitors(result.competitors);
    } catch (err) {
      setCompetitorsError(
        err instanceof Error ? err.message : "Error al analizar la competencia"
      );
    } finally {
      setCompetitorsLoading(false);
    }
  }

  async function handleStageChange(newStage: string) {
    if (!lead) return;
    const previousStage = lead.pipeline_stage;
    setStageSaving(true);
    setStageError(null);
    setLead({ ...lead, pipeline_stage: newStage });
    try {
      await updateLeadStage(leadId, { stage: newStage });
    } catch (err) {
      setLead((prev) => (prev ? { ...prev, pipeline_stage: previousStage } : prev));
      setStageError(err instanceof Error ? err.message : "Error al cambiar la etapa");
    } finally {
      setStageSaving(false);
    }
  }

  if (loading) {
    return <main className="p-8">Cargando lead...</main>;
  }

  if (error || !lead) {
    return (
      <main className="p-8">
        <p className="text-red-600">{error ?? "Lead no encontrado"}</p>
      </main>
    );
  }

  return (
    <main className="p-8 max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{lead.business_name}</h1>
        <p className="text-sm text-muted-foreground">
          {[lead.zone, lead.category].filter(Boolean).join(" · ")}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Etapa del pipeline</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <Select
            value={lead.pipeline_stage}
            onValueChange={(value) => handleStageChange(value ?? lead.pipeline_stage)}
            disabled={stageSaving}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STAGES.map((s) => (
                <SelectItem key={s.value} value={s.value}>
                  {s.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {stageError && <p className="text-sm text-red-600">{stageError}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Evaluación</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <p>
            <strong>Urgencia:</strong>{" "}
            {lead.urgency_score !== undefined && lead.urgency_score !== null
              ? lead.urgency_score
              : "sin evaluar"}
          </p>
          <p>
            <strong>Servicio recomendado:</strong>{" "}
            {lead.recommended_service ?? "sin evaluar"}
          </p>
          {lead.sales_arguments && lead.sales_arguments.length > 0 && (
            <div>
              <strong>Argumentos de venta:</strong>
              <ul className="list-disc list-inside">
                {lead.sales_arguments.map((arg, i) => (
                  <li key={i}>{arg}</li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Email de prospección</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {lead.email_draft ? (
            <pre className="whitespace-pre-wrap text-sm bg-muted p-3 rounded">
              {lead.email_draft}
            </pre>
          ) : (
            <p className="text-sm text-muted-foreground">Todavía no se ha generado.</p>
          )}
          <Button onClick={handleGenerateEmail} disabled={emailLoading}>
            {emailLoading
              ? "Generando..."
              : lead.email_draft
              ? "Regenerar email"
              : "Generar email"}
          </Button>
          {emailError && <p className="text-sm text-red-600">{emailError}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Competencia</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button onClick={handleAnalyzeCompetitors} disabled={competitorsLoading}>
            {competitorsLoading ? "Analizando..." : "Analizar competencia"}
          </Button>
          {competitorsError && <p className="text-sm text-red-600">{competitorsError}</p>}

          {competitors && competitors.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No se encontraron competidores con sitio web cerca.
            </p>
          )}

          {competitors && competitors.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {competitors.map((c) => (
                <div key={c.id} className="border rounded p-3 text-sm space-y-1">
                  <p className="font-semibold">{c.competitor_name ?? c.competitor_url}</p>
                  {c.competitor_url && (
                    <a
                      href={c.competitor_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-blue-600 underline break-all"
                    >
                      {c.competitor_url}
                    </a>
                  )}
                  <ul className="space-y-0.5">
                    <li>Menú online: {c.has_online_menu ? "Sí" : "No"}</li>
                    <li>Reservas: {c.has_booking ? "Sí" : "No"}</li>
                    <li>E-commerce: {c.has_ecommerce ? "Sí" : "No"}</li>
                    <li>Blog: {c.has_blog ? "Sí" : "No"}</li>
                  </ul>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </main>
  );
}