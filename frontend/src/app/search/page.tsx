
// frontend/src/app/search/page.tsx
"use client";
import { useState } from "react";
import Link from "next/link";
import { search, getBusinesses, analyzeLead } from "@/lib/api";
import { SearchResponse, BusinessOut } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
export default function SearchPage() {
  const [zone, setZone] = useState("");
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [businesses, setBusinesses] = useState<BusinessOut[]>([]);
  const [businessesError, setBusinessesError] = useState<string | null>(null);
  // Guarda qué business_id está analizando ahora mismo (o null si ninguno),
  // así solo ese botón muestra "Analizando..." y no todos a la vez.
  const [analyzingId, setAnalyzingId] = useState<number | null>(null);
  const [analyzeErrors, setAnalyzeErrors] = useState<Record<number, string>>({});
  async function loadBusinesses(z: string, c: string) {
    setBusinessesError(null);
    try {
      const data = await getBusinesses(z, c);
      setBusinesses(data);
    } catch (err) {
      setBusinessesError(
        err instanceof Error ? err.message : "Error al cargar los negocios"
      );
    }
  }
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    setBusinesses([]);
    try {
      const res = await search({ zone, category });
      setResult(res);
      await loadBusinesses(zone, category);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  }
  async function handleAnalyze(businessId: number) {
    setAnalyzingId(businessId);
    setAnalyzeErrors((prev) => ({ ...prev, [businessId]: "" }));
    try {
      const analyzed = await analyzeLead(businessId);
      setBusinesses((prev) =>
        prev.map((b) =>
          b.id === businessId
            ? { ...b, lead_id: analyzed.lead_id, lead_analyzed: true }
            : b
        )
      );
    } catch (err) {
      setAnalyzeErrors((prev) => ({
        ...prev,
        [businessId]: err instanceof Error ? err.message : "Error al analizar",
      }));
    } finally {
      setAnalyzingId(null);
    }
  }
  return (
    <main className="max-w-2xl mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold">Buscar leads</h1>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="zone">Zona</Label>
          <Input
            id="zone"
            name="zone"
            value={zone}
            onChange={(e) => setZone(e.target.value)}
            placeholder="Ej: Laureles, Medellín"
            required
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="category">Categoría</Label>
          <Input
            id="category"
            name="category"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            placeholder="Ej: restaurantes"
            required
          />
        </div>
        <Button type="submit" disabled={loading}>
          {loading ? "Buscando..." : "Buscar"}
        </Button>
      </form>
      {error && (
        <p className="text-red-600 text-sm">Error: {error}</p>
      )}
      {result && (
        <Card>
          <CardHeader>
            <CardTitle>Resultado (run #{result.run_id})</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <p>Negocios encontrados: {result.businesses_found}</p>
            <p>Leads sin sitio web: {result.leads_without_website}</p>
            {result.source === "cache" && (
              <p className="text-amber-600 text-sm pt-1">
                ⚠ La infraestructura pública de OpenStreetMap (Overpass) está
                degradada en este momento. Estos son resultados guardados de
                una búsqueda anterior para esta zona/categoría, no datos en
                vivo.
              </p>
            )}
          </CardContent>
        </Card>
      )}
      {businessesError && (
        <p className="text-red-600 text-sm">Error: {businessesError}</p>
      )}
      {businesses.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Negocios encontrados</h2>
          {businesses.map((b) => (
            <Card key={b.id}>
              <CardContent className="p-4 flex items-start justify-between gap-4">
                <div className="space-y-1">
                  <p className="font-semibold">{b.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {[b.address, b.phone].filter(Boolean).join(" · ") || "Sin dirección"}
                  </p>
                  <p className="text-xs">
                    Sitio web: {b.has_website ? "Sí" : "No"}
                  </p>
                  {analyzeErrors[b.id] && (
                    <p className="text-sm text-red-600">{analyzeErrors[b.id]}</p>
                  )}
                </div>
                {b.lead_analyzed && b.lead_id ? (
                  <Link href={`/leads/${b.lead_id}`}>
                    <Button variant="outline">Ver lead</Button>
                  </Link>
                ) : (
                  <Button
                    onClick={() => handleAnalyze(b.id)}
                    disabled={analyzingId === b.id}
                  >
                    {analyzingId === b.id ? "Analizando..." : "Analizar con Gemini"}
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </main>
  );
}