"use client";

import { useEffect, useState } from "react";

import { ErrorMessage, errorText } from "@/components/ErrorMessage";
import { api, type AuditEntry } from "@/lib/api";

const ACTION_LABELS: Record<string, string> = {
  "auth.login": "Connexion",
  "auth.logout": "Déconnexion",
  "auth.switch_company": "Changement d'entreprise",
  "auth.refresh_reuse_detected": "Session suspecte révoquée",
  "company.created": "Entreprise créée",
  "company.updated": "Entreprise modifiée",
  "membership.created": "Utilisateur ajouté",
  "membership.updated": "Utilisateur modifié",
  "sessions.revoked": "Sessions révoquées",
  "user.password_changed": "Mot de passe changé",
};

const ACTOR_LABELS = { user: "Utilisateur", ai: "IA", system: "Système" } as const;

function changes(e: AuditEntry): string {
  if (!e.after) return "";
  return Object.entries(e.after)
    .filter(([k, v]) => !e.before || JSON.stringify(e.before[k]) !== JSON.stringify(v))
    .map(([k, v]) => (e.before ? `${k} : ${String(e.before[k])} → ${String(v)}` : `${k} : ${String(v)}`))
    .join(" ; ");
}

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const PAGE = 50;

  async function load(beforeId?: number) {
    try {
      const qs = new URLSearchParams({ limit: String(PAGE) });
      if (beforeId) qs.set("before_id", String(beforeId));
      const page = await api<AuditEntry[]>(`/api/audit?${qs}`);
      setEntries((prev) => (beforeId ? [...prev, ...page] : page));
      setHasMore(page.length === PAGE);
    } catch (e) {
      setError(errorText(e));
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Journal d&apos;audit</h1>
        <p className="text-sm text-slate-500">
          Historique non modifiable de toutes les actions sur votre entreprise.
        </p>
      </div>
      <ErrorMessage message={error} />
      <section className="card overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-left text-slate-600">
            <tr>
              <th className="px-4 py-2 font-medium">Date</th>
              <th className="px-4 py-2 font-medium">Auteur</th>
              <th className="px-4 py-2 font-medium">Action</th>
              <th className="px-4 py-2 font-medium">Détail</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id} className="border-b border-slate-100 align-top last:border-0">
                <td className="whitespace-nowrap px-4 py-2 text-slate-600">
                  {new Date(e.created_at).toLocaleString("fr-FR")}
                </td>
                <td className="px-4 py-2">{e.actor_email ?? ACTOR_LABELS[e.actor_type]}</td>
                <td className="px-4 py-2">{ACTION_LABELS[e.action] ?? e.action}</td>
                <td className="px-4 py-2 text-slate-600">{changes(e)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      {hasMore && (
        <button className="btn-secondary" onClick={() => load(entries[entries.length - 1]?.id)}>
          Voir plus
        </button>
      )}
    </div>
  );
}
