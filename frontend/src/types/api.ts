// frontend/src/types/api.ts
export interface SearchRequest {
  zone: string;
  category: string;
}
export interface SearchResponse {
  run_id: number;
  businesses_found: number;
  leads_without_website: number;
  // "live": Overpass respondió en esta corrida. "cache": todos los
  // mirrors de Overpass fallaron y el backend devolvió una búsqueda
  // anterior guardada para esta zona/categoría. Ver backend/api/schemas.py.
  source: "live" | "cache";
}
export interface HealthResponse {
  status: string;
  environment: string;
}
export interface AnalyzeLeadResponse {
  lead_id: number;
  business_id: number;
  skipped: boolean;
  skip_reason?: string;
  urgency_score?: number;
  recommended_service?: string;
  sales_arguments?: string[];
  pipeline_stage: string;
}
export interface GenerateEmailResponse {
  lead_id: number;
  email_draft: string;
}
export interface LeadDetail {
  id: number;
  business_id: number;
  business_name: string;
  zone?: string;
  category?: string;
  urgency_score?: number;
  recommended_service?: string;
  sales_arguments?: string[];
  email_draft?: string;
  pipeline_stage: string;
  analyzed_at?: string;
}
export interface LeadListItem {
  id: number;
  business_id: number;
  business_name: string;
  zone?: string;
  urgency_score?: number;
  recommended_service?: string;
  pipeline_stage: string;
}
export interface CompetitorInfoOut {
  id: number;
  competitor_name?: string;
  competitor_url?: string;
  has_online_menu: boolean;
  has_booking: boolean;
  has_ecommerce: boolean;
  has_blog: boolean;
  scraped_at: string;
}
export interface CompetitorsResponse {
  lead_id: number;
  competitors_found: number;
  competitors_analyzed: number;
  competitors_with_errors: number;
  competitors: CompetitorInfoOut[];
}
export interface StageUpdateRequest {
  stage: string;
}
export interface LeadStageResponse {
  lead_id: number;
  from_stage?: string;
  to_stage: string;
  changed: boolean;
}
export interface PipelineEventOut {
  id: number;
  from_stage?: string;
  to_stage: string;
  changed_at: string;
}
export interface PipelineHistoryResponse {
  lead_id: number;
  events: PipelineEventOut[];
}
export type PipelineStage =
  | "nuevo"
  | "contactado"
  | "respondio"
  | "reunion"
  | "cerrado"
  | "descartado";
export interface EffectivenessSegment {
  category: string;
  zone: string;
  score_range: string;
  total_leads: number;
  closed_leads: number;
  conversion_rate: number;
}
export interface EffectivenessResponse {
  segments: EffectivenessSegment[];
}