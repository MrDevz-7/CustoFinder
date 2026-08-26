// frontend/src/app/page.tsx
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const SECTIONS = [
  {
    href: "/search",
    title: "Buscar negocios",
    description:
      "Descubre negocios locales sin sitio web en una zona y categoría, vía OpenStreetMap.",
  },
  {
    href: "/leads",
    title: "Leads",
    description:
      "Lista de negocios evaluados por IA, con score de urgencia y servicio recomendado.",
  },
  {
    href: "/pipeline",
    title: "Pipeline",
    description:
      "Kanban de seguimiento comercial: nuevo, contactado, respondió, reunión, cerrado.",
  },
  {
    href: "/analytics",
    title: "Analytics",
    description:
      "Tasa de conversión por rubro, zona y rango de urgencia — qué segmentos conviene priorizar.",
  },
];

export default function HomePage() {
  return (
    <main className="p-6 max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">CustoFinder</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Prospección inteligente de clientes: descubre negocios locales sin
          sitio web, evaluá leads con IA, analizá a su competencia y llevá el
          seguimiento del pipeline de ventas — todo en un solo lugar.
        </p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {SECTIONS.map((section) => (
          <Link key={section.href} href={section.href}>
            <Card className="h-full transition-shadow hover:ring-2 hover:ring-blue-600">
              <CardHeader>
                <CardTitle>{section.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  {section.description}
                </p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </main>
  );
}