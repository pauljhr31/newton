"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { SessionContext } from "@/components/SessionContext";
import { api, loadMe, ROLE_LABELS, type Me } from "@/lib/api";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [me, setMe] = useState<Me | null>(null);

  const reload = useCallback(async () => {
    const m = await loadMe();
    if (!m) return router.replace("/login");
    if (m.must_change_password) return router.replace("/change-password");
    setMe(m);
  }, [router]);

  useEffect(() => {
    // Initial session check: loads the user, or redirects to the login page.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    reload();
  }, [reload]);

  async function logout() {
    await api("/api/auth/logout", { method: "POST" }).catch(() => undefined);
    router.replace("/login");
  }

  async function switchCompany(companyId: string) {
    await api("/api/auth/switch-company", { method: "POST", body: { company_id: companyId } });
    // Deliberate full reload: no client state from the previous company may survive.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign("/");
  }

  if (!me) return <p className="p-8 text-sm text-slate-500">Chargement…</p>;

  const nav = [
    { href: "/", label: "Accueil", show: true },
    { href: "/users", label: "Utilisateurs", show: me.role === "admin" },
    { href: "/audit", label: "Journal d'audit", show: me.role === "admin" },
  ];

  return (
    <SessionContext.Provider value={{ me, reload }}>
      {me.company.is_demo && (
        <div className="bg-amber-400 px-4 py-1 text-center text-sm font-semibold text-amber-950">
          ENTREPRISE DE DÉMONSTRATION : données fictives, ne pas utiliser pour un vrai chiffrage
        </div>
      )}
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-4 px-4 py-3">
          <span className="text-lg font-semibold tracking-tight">NEWTON</span>
          {me.companies.length > 1 ? (
            <select
              aria-label="Changer d'entreprise"
              className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm"
              value={me.company.id}
              onChange={(e) => switchCompany(e.target.value)}
            >
              {me.companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          ) : (
            <span className="text-sm text-slate-600">{me.company.name}</span>
          )}
          <nav className="flex gap-1">
            {nav
              .filter((n) => n.show)
              .map((n) => (
                <Link
                  key={n.href}
                  href={n.href}
                  className={`rounded-md px-3 py-1.5 text-sm ${
                    pathname === n.href ? "bg-slate-100 font-medium" : "text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {n.label}
                </Link>
              ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            <span className="text-slate-600">
              {me.full_name} · {ROLE_LABELS[me.role]}
            </span>
            <Link href="/change-password" className="text-slate-600 underline-offset-2 hover:underline">
              Mot de passe
            </Link>
            <button className="btn-secondary" onClick={logout}>
              Déconnexion
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
    </SessionContext.Provider>
  );
}
