// frontend/src/app/search/page.tsx
"use client";
import { useState } from "react";
import { search } from "@/lib/api";
import { SearchResponse } from "@/types/api";
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
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await search({ zone, category });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  }
  return (
    <main className="max-w-md mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold">Buscar leads</h1>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="zone">Zona</Label>
          <Input
            id="zone"
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
    </main>
  );
}