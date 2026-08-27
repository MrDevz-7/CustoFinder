// frontend/src/app/leads/page.tsx
"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { getLeads } from "@/lib/api";
import { LeadListItem, PipelineStage } from "@/types/api";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
const STAGES: PipelineStage[] = [
  "nuevo",
  "contactado",
  "respondio",
  "reunion",
  "cerrado",
  "descartado",
];
export default function LeadsPage() {
  const [leads, setLeads] = useState<LeadListItem[]>([]);
  const [stage, setStage] = useState<string>("all");
  const [minUrgency, setMinUrgency] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getLeads({
      stage: stage !== "all" ? stage : undefined,
      min_urgency: minUrgency ? Number(minUrgency) : undefined,
    })
      .then((data) => {
        if (!cancelled) setLeads(data);
      })
      .catch((err) => {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "Error desconocido");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [stage, minUrgency]);
  return (
    <main className="max-w-4xl mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold">Leads</h1>
      <div className="flex gap-4 items-end">
        <div className="space-y-2">
          <Label htmlFor="stage-filter">Stage</Label>
          <Select value={stage} onValueChange={(value) => setStage(value ?? "all")}>
            <SelectTrigger id="stage-filter" className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos</SelectItem>
              {STAGES.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="min-urgency">Urgencia mínima</Label>
          <Input
            id="min-urgency"
            name="min_urgency"
            type="number"
            value={minUrgency}
            onChange={(e) => setMinUrgency(e.target.value)}
            placeholder="0-10"
            className="w-32"
          />
        </div>
      </div>
      {loading && <p className="text-sm text-muted-foreground">Cargando...</p>}
      {error && <p className="text-red-600 text-sm">Error: {error}</p>}
      {!loading && !error && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Negocio</TableHead>
              <TableHead>Zona</TableHead>
              <TableHead>Urgencia</TableHead>
              <TableHead>Servicio recomendado</TableHead>
              <TableHead>Stage</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {leads.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-gray-500">
                  Sin resultados
                </TableCell>
              </TableRow>
            )}
            {leads.map((lead) => (
              <TableRow key={lead.id} className="cursor-pointer hover:bg-muted/50">
                <TableCell className="p-0">
                  <Link href={`/leads/${lead.id}`} className="block px-4 py-2">
                    {lead.business_name}
                  </Link>
                </TableCell>
                <TableCell>{lead.zone ?? "-"}</TableCell>
                <TableCell>{lead.urgency_score ?? "-"}</TableCell>
                <TableCell>{lead.recommended_service ?? "-"}</TableCell>
                <TableCell>{lead.pipeline_stage}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </main>
  );
}