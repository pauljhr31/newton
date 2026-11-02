"use client";

import { useEffect, useState } from "react";

import { ErrorMessage, errorText } from "@/components/ErrorMessage";
import { useSession } from "@/components/SessionContext";
import { api, type Company } from "@/lib/api";

export default function HomePage() {
  const { me, reload } = useSession();
  const [company, setCompany] = useState<Company | null>(null);
  const [name, setName] = useState("");
  const [siret, setSiret] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api<Company>("/api/company")
      .then((c) => {
        setCompany(c);
        setName(c.name);
        setSiret(c.siret ?? "");
      })
      .catch((e) => setError(errorText(e)));
  }, []);

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    try {
      const body: Record<string, string> = { name };
      if (siret.trim()) body.siret = siret.replace(/\s/g, "");
      const c = await api<Company>("/api/company", { method: "PATCH", body });
      setCompany(c);
      setSaved(true);
      await reload();
    } catch (err) {
      setError(errorText(err));
    }
  }

  const isAdmin = me.role === "admin";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Bonjour {me.full_name}</h1>
      <section className="card max-w-xl">
        <h2 className="mb-4 text-lg font-medium">Entreprise</h2>
        {!company ? (
          <ErrorMessage message={error} />
        ) : (
          <form onSubmit={onSave} className="space-y-4">
            <div>
              <label htmlFor="name" className="label">
                Raison sociale
              </label>
              <input
                id="name"
                className="input"
                value={name}
                disabled={!isAdmin}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
            <div>
              <label htmlFor="siret" className="label">
                SIRET (14 chiffres)
              </label>
              <input
                id="siret"
                className="input"
                value={siret}
                disabled={!isAdmin}
                onChange={(e) => setSiret(e.target.value)}
                inputMode="numeric"
              />
            </div>
            <ErrorMessage message={error} />
            {saved && <p className="text-sm text-green-700">Modifications enregistrées.</p>}
            {isAdmin ? (
              <button type="submit" className="btn">
                Enregistrer
              </button>
            ) : (
              <p className="text-sm text-slate-500">Seul un administrateur peut modifier ces informations.</p>
            )}
          </form>
        )}
      </section>
      <section className="card max-w-xl text-sm text-slate-600">
        Prochaine étape du produit : import des dossiers d&apos;appel d&apos;offres (CCTP, DPGF) et
        chiffrage.
      </section>
    </div>
  );
}
