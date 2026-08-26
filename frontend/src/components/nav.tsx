// frontend/src/components/nav.tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/search", label: "Buscar" },
  { href: "/leads", label: "Leads" },
  { href: "/pipeline", label: "Pipeline" },
  { href: "/analytics", label: "Analytics" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <nav className="border-b bg-white">
      <div className="max-w-5xl mx-auto px-6 py-3 flex items-center gap-6">
        <Link href="/" className="font-bold text-lg mr-4">
          CustoFinder
        </Link>
        {LINKS.map((link) => {
          const active =
            pathname === link.href || pathname.startsWith(`${link.href}/`);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={
                active
                  ? "text-sm font-semibold text-blue-600"
                  : "text-sm text-muted-foreground hover:text-foreground"
              }
            >
              {link.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}