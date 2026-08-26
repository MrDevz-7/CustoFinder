
// frontend/src/lib/api.ts
import {
  SearchRequest,
  SearchResponse,
  BusinessOut,
  HealthResponse,
  LeadDetail,
  LeadListItem,
  StageUpdateRequest,
  LeadStageResponse,
  CompetitorsResponse,
  PipelineHistoryResponse,
  GenerateEmailResponse,
  AnalyzeLeadResponse,
} from "@/types/api";
const API_URL = process.env.NEXT_PUBLIC_API_URL;
async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}
export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_URL}/api/health`);
  return handleResponse<HealthResponse>(res);
}
export async function search(payload: SearchRequest): Promise<SearchResponse> {
  const res = await fetch(`${API_URL}/api/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<SearchResponse>(res);
}
export async function getBusinesses(
  zone: string,
  category: string
): Promise<BusinessOut[]> {
  const query = new URLSearchParams({ zone, category });
  const res = await fetch(`${API_URL}/api/businesses?${query.toString()}`);
  return handleResponse<BusinessOut[]>(res);
}
export async function analyzeLead(businessId: number): Promise<AnalyzeLeadResponse> {
  const res = await fetch(`${API_URL}/api/leads/${businessId}/analyze`, {
    method: "POST",
  });
  return handleResponse<AnalyzeLeadResponse>(res);
}
export async function getLeads(params?: {
  stage?: string;
  min_urgency?: number;
}): Promise<LeadListItem[]> {
  const query = new URLSearchParams();
  if (params?.stage) query.set("stage", params.stage);
  if (params?.min_urgency !== undefined)
    query.set("min_urgency", String(params.min_urgency));
  const qs = query.toString();
  const res = await fetch(`${API_URL}/api/leads${qs ? `?${qs}` : ""}`);
  return handleResponse<LeadListItem[]>(res);
}
export async function getLead(leadId: number): Promise<LeadDetail> {
  const res = await fetch(`${API_URL}/api/leads/${leadId}`);
  return handleResponse<LeadDetail>(res);
}
export async function updateLeadStage(
  leadId: number,
  payload: StageUpdateRequest
): Promise<LeadStageResponse> {
  const res = await fetch(`${API_URL}/api/leads/${leadId}/stage`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<LeadStageResponse>(res);
}
export async function getCompetitors(
  leadId: number
): Promise<CompetitorsResponse> {
  const res = await fetch(`${API_URL}/api/leads/${leadId}/competitors`, {
    method: "POST",
  });
  return handleResponse<CompetitorsResponse>(res);
}
export async function getPipelineHistory(
  leadId: number
): Promise<PipelineHistoryResponse> {
  const res = await fetch(`${API_URL}/api/leads/${leadId}/pipeline-history`);
  return handleResponse<PipelineHistoryResponse>(res);
}
export async function generateEmail(leadId: number): Promise<GenerateEmailResponse> {
  const res = await fetch(`${API_URL}/api/leads/${leadId}/generate-email`, {
    method: "POST",
  });
  return handleResponse<GenerateEmailResponse>(res);
}
import { EffectivenessResponse } from "@/types/api";
export async function getEffectiveness(params?: {
  zone?: string;
  category?: string;
}): Promise<EffectivenessResponse> {
  const query = new URLSearchParams();
  if (params?.zone) query.set("zone", params.zone);
  if (params?.category) query.set("category", params.category);
  const qs = query.toString();
  const res = await fetch(
    `${API_URL}/api/dashboard/effectiveness${qs ? `?${qs}` : ""}`
  );
  return handleResponse<EffectivenessResponse>(res);
}