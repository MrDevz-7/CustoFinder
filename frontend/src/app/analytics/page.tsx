// frontend/src/app/analytics/page.tsx
"use client";
import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getEffectiveness } from "@/lib/api";
import { EffectivenessSegment } from "@/types/api";

function formatPct(rate: number): string {
  return `${(rate * 100).toFixed(0)}%`;
}

export default function AnalyticsPage() {
  const [segments, setSegments] = useState<EffectivenessSegment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [zoneFilter, setZoneFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await getEffectiveness({
          zone: zoneFilter || undefined,
          category: categoryFilter || undefined,
        });
        if (!cancelled) setSegments(data.segments);
      } catch (err) {
        if (!cancelled)
          setError(
            err instanceof Error ? err.message : "Error al cargar el análisis"
          );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
    }, [zoneFilter, categoryFilter]);

  const chartData = useMemo(
    () =>
      segments.map((s) => ({
        label: `${s.category} · ${s.zone} · ${s.score_range}`,
        conversion_pct: Math.round(s.conversion_rate * 1000) / 10,
        total_leads: s.total_leads,
        closed_leads: s.closed_leads,
      })),
    [segments]
  );

  const zones = useMemo(
    () => Array.from(new Set(segments.map((s) => s.zone))).sort(),
    [segments]
  );
  const categories = useMemo(
    () => Array.from(new Set(segments.map((s) => s.category))).sort(),
    [segments]
  );

  return (
    <main className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Efectividad por segmento</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Tasa de conversión (leads que llegaron a &quot;cerrado&quot; alguna
          vez) por rubro + zona + rango de urgency_score.
        </p>
      </div>

      <div className="flex flex-wrap gap-3">
        <select
          className="border rounded px-2 py-1 text-sm"
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
        >
          <option value="">Todos los rubros</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select
          className="border rounded px-2 py-1 text-sm"
          value={zoneFilter}
          onChange={(e) => setZoneFilter(e.target.value)}
        >
          <option value="">Todas las zonas</option>
          {zones.map((z) => (
            <option key={z} value={z}>
              {z}
            </option>
          ))}
        </select>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {loading ? (
        <p className="text-sm text-muted-foreground">Cargando análisis...</p>
      ) : segments.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Todavía no hay suficientes leads analizados (con urgency_score) para
          calcular efectividad por segmento.
        </p>
      ) : (
        <>
          <div className="border rounded p-4" style={{ height: 360 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={chartData}
                layout="vertical"
                margin={{ top: 8, right: 24, bottom: 8, left: 8 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  type="number"
                  domain={[0, 100]}
                  unit="%"
                  tick={{ fontSize: 12 }}
                />
                <YAxis
                  type="category"
                  dataKey="label"
                  width={220}
                  tick={{ fontSize: 11 }}
                />
                <Tooltip
                  formatter={(value: number, name: string) =>
                    name === "conversion_pct" ? [`${value}%`, "Conversión"] : value
                  }
                />
                <Bar dataKey="conversion_pct" fill="#2563eb" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Rubro</TableHead>
                <TableHead>Zona</TableHead>
                <TableHead>Score</TableHead>
                <TableHead className="text-right">Total leads</TableHead>
                <TableHead className="text-right">Cerrados</TableHead>
                <TableHead className="text-right">Conversión</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {segments.map((s, i) => (
                <TableRow key={`${s.category}-${s.zone}-${s.score_range}-${i}`}>
                  <TableCell>{s.category}</TableCell>
                  <TableCell>{s.zone}</TableCell>
                  <TableCell>{s.score_range}</TableCell>
                  <TableCell className="text-right">{s.total_leads}</TableCell>
                  <TableCell className="text-right">{s.closed_leads}</TableCell>
                  <TableCell className="text-right font-semibold">
                    {formatPct(s.conversion_rate)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </>
      )}
    </main>
  );
}