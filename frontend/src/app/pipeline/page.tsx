// frontend/src/app/pipeline/page.tsx
"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  DndContext,
  DragEndEvent,
  useDraggable,
  useDroppable,
} from "@dnd-kit/core";
import { getLeads, updateLeadStage } from "@/lib/api";
import { LeadListItem, PipelineStage } from "@/types/api";
const COLUMNS: { value: PipelineStage; label: string }[] = [
  { value: "nuevo", label: "Nuevo" },
  { value: "contactado", label: "Contactado" },
  { value: "respondio", label: "Respondió" },
  { value: "reunion", label: "Reunión" },
  { value: "cerrado", label: "Cerrado" },
  { value: "descartado", label: "Descartado" },
];
function LeadCard({ lead }: { lead: LeadListItem }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: String(lead.id),
  });
  const style = transform
    ? {
        transform: `translate(${transform.x}px, ${transform.y}px)`,
        zIndex: isDragging ? 10 : undefined,
      }
    : undefined;
  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      className="bg-white border rounded p-3 shadow-sm cursor-grab active:cursor-grabbing space-y-1"
    >
      <Link
        href={`/leads/${lead.id}`}
        className="font-semibold text-sm hover:underline"
        onClick={(e) => e.stopPropagation()}
      >
        {lead.business_name}
      </Link>
      {lead.zone && <p className="text-xs text-muted-foreground">{lead.zone}</p>}
      {lead.urgency_score !== undefined && lead.urgency_score !== null && (
        <p className="text-xs">Urgencia: {lead.urgency_score}</p>
      )}
    </div>
  );
}
function Column({
  stage,
  label,
  leads,
}: {
  stage: PipelineStage;
  label: string;
  leads: LeadListItem[];
}) {
  const { setNodeRef, isOver } = useDroppable({ id: stage });
  return (
    <div
      ref={setNodeRef}
      className={`flex-1 min-w-55 rounded p-2 ${
        isOver ? "bg-blue-50" : "bg-gray-50"
      }`}
    >
      <h2 className="font-semibold text-sm mb-2 px-1">
        {label} <span className="text-muted-foreground">({leads.length})</span>
      </h2>
      <div className="space-y-2">
        {leads.map((lead) => (
          <LeadCard key={lead.id} lead={lead} />
        ))}
      </div>
    </div>
  );
}
export default function PipelinePage() {
  const [leads, setLeads] = useState<LeadListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    async function loadLeads() {
      setLoading(true);
      setError(null);
      try {
        const data = await getLeads();
        if (!cancelled) setLeads(data);
      } catch (err) {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "Error al cargar los leads");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    loadLeads();
    return () => {
      cancelled = true;
    };
  }, []);
  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over) return;
    const leadId = Number(active.id);
    const newStage = String(over.id);
    const lead = leads.find((l) => l.id === leadId);
    if (!lead || lead.pipeline_stage === newStage) return;
    const previousStage = lead.pipeline_stage;
    setError(null);
    setLeads((prev) =>
      prev.map((l) => (l.id === leadId ? { ...l, pipeline_stage: newStage } : l))
    );
    try {
      await updateLeadStage(leadId, { stage: newStage });
    } catch (err) {
      setLeads((prev) =>
        prev.map((l) => (l.id === leadId ? { ...l, pipeline_stage: previousStage } : l))
      );
      setError(
        err instanceof Error ? err.message : "No se pudo guardar el cambio de etapa"
      );
    }
  }
  if (loading) {
    return <main className="p-8">Cargando pipeline...</main>;
  }
  return (
    <main className="p-6 space-y-4">
      <h1 className="text-2xl font-bold">Pipeline de leads</h1>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <DndContext onDragEnd={handleDragEnd}>
        <div className="flex gap-3 overflow-x-auto">
          {COLUMNS.map((col) => (
            <Column
              key={col.value}
              stage={col.value}
              label={col.label}
              leads={leads.filter((l) => l.pipeline_stage === col.value)}
            />
          ))}
        </div>
      </DndContext>
    </main>
  );
}