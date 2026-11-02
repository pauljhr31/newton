"use client";

import { useCallback, useEffect, useState } from "react";

import { ErrorMessage, errorText } from "@/components/ErrorMessage";
import { useSession } from "@/components/SessionContext";
import { api, ROLE_LABELS, type Member, type MemberCreated, type Role } from "@/lib/api";

const ROLES: Role[] = ["admin", "estimator", "viewer"];

export default function UsersPage() {
  const { me } = useSession();
  const [members, setMembers] = useState<Member[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<MemberCreated | null>(null);
  const [form, setForm] = useState({ email: "", full_name: "", role: "estimator" as Role });

  const load = useCallback(async () => {
    try {
      setMembers(await api<Member[]>("/api/users"));
    } catch (e) {
      setError(errorText(e));
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  async function addMember(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setCreated(null);
    try {
      const res = await api<MemberCreated>("/api/users", { method: "POST", body: form });
      setCreated(res);
      setForm({ email: "", full_name: "", role: "estimator" });
      await load();
    } catch (err) {
      setError(errorText(err));
    }
  }

  async function update(userId: string, changes: Partial<Pick<Member, "role" | "is_active">>) {
    setError(null);
    try {
      await api(`/api/users/${userId}`, { method: "PATCH", body: changes });
      await load();
    } catch (err) {
      setError(errorText(err));
      await load();
    }
  }

  async function revoke(userId: string) {
    setError(null);
    try {
      await api(`/api/users/${userId}/revoke-sessions`, { method: "POST" });
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Utilisateurs</h1>
      <ErrorMessage message={error} />

      <section className="card overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-left text-slate-600">
            <tr>
              <th className="px-4 py-2 font-medium">Nom</th>
              <th className="px-4 py-2 font-medium">E-mail</th>
              <th className="px-4 py-2 font-medium">Rôle</th>
              <th className="px-4 py-2 font-medium">Statut</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {members.map((m) => (
              <tr key={m.user_id} className="border-b border-slate-100 last:border-0">
                <td className="px-4 py-2">{m.full_name}</td>
                <td className="px-4 py-2 text-slate-600">{m.email}</td>
                <td className="px-4 py-2">
                  <select
                    aria-label={`Rôle de ${m.full_name}`}
                    className="rounded-md border border-slate-300 bg-white px-2 py-1"
                    value={m.role}
                    onChange={(e) => update(m.user_id, { role: e.target.value as Role })}
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>
                        {ROLE_LABELS[r]}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-4 py-2">
                  {m.is_active ? (
                    m.must_change_password ? (
                      <span className="text-amber-700">Mot de passe provisoire</span>
                    ) : (
                      <span className="text-green-700">Actif</span>
                    )
                  ) : (
                    <span className="text-slate-400">Désactivé</span>
                  )}
                </td>
                <td className="space-x-2 whitespace-nowrap px-4 py-2 text-right">
                  {m.user_id !== me.user_id && (
                    <button className="btn-secondary" onClick={() => revoke(m.user_id)}>
                      Déconnecter
                    </button>
                  )}
                  <button
                    className="btn-secondary"
                    onClick={() => update(m.user_id, { is_active: !m.is_active })}
                  >
                    {m.is_active ? "Désactiver" : "Réactiver"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card max-w-xl">
        <h2 className="mb-4 text-lg font-medium">Ajouter un utilisateur</h2>
        <form onSubmit={addMember} className="space-y-4">
          <div>
            <label htmlFor="full_name" className="label">
              Nom complet
            </label>
            <input
              id="full_name"
              className="input"
              required
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            />
          </div>
          <div>
            <label htmlFor="new_email" className="label">
              E-mail
            </label>
            <input
              id="new_email"
              type="email"
              className="input"
              required
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </div>
          <div>
            <label htmlFor="role" className="label">
              Rôle
            </label>
            <select
              id="role"
              className="input"
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value as Role })}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABELS[r]}
                </option>
              ))}
            </select>
          </div>
          <button type="submit" className="btn">
            Ajouter
          </button>
        </form>

        {created && (
          <div className="mt-4 rounded-md border border-blue-200 bg-blue-50 p-4 text-sm">
            {created.temporary_password ? (
              <>
                <p>
                  Compte créé pour <strong>{created.member.email}</strong>. Transmettez-lui ce mot de
                  passe provisoire (il ne sera plus affiché) :
                </p>
                <p className="mt-2 select-all rounded bg-white px-2 py-1 font-mono">
                  {created.temporary_password}
                </p>
                <p className="mt-2 text-slate-600">Il devra le changer à sa première connexion.</p>
              </>
            ) : (
              <p>
                <strong>{created.member.email}</strong> avait déjà un compte NEWTON : il a été ajouté à
                votre entreprise et garde son mot de passe actuel.
              </p>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
