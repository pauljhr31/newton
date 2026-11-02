"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ErrorMessage, errorText } from "@/components/ErrorMessage";
import { api, loadMe, type Me } from "@/lib/api";

export default function ChangePasswordPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    loadMe().then((m) => (m ? setMe(m) : router.replace("/login")));
  }, [router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (next !== confirm) {
      setError("Les deux nouveaux mots de passe ne sont pas identiques.");
      return;
    }
    setBusy(true);
    try {
      await api("/api/auth/change-password", {
        method: "POST",
        body: { current_password: current, new_password: next },
      });
      router.replace("/");
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  if (!me) return null;

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <form onSubmit={onSubmit} className="card w-full max-w-sm space-y-4">
        <div>
          <h1 className="text-xl font-semibold">Changer le mot de passe</h1>
          {me.must_change_password && (
            <p className="mt-1 text-sm text-slate-600">
              Votre mot de passe est provisoire : choisissez-en un nouveau pour continuer.
            </p>
          )}
        </div>
        <div>
          <label htmlFor="current" className="label">
            Mot de passe actuel
          </label>
          <input
            id="current"
            type="password"
            autoComplete="current-password"
            required
            className="input"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="new" className="label">
            Nouveau mot de passe
          </label>
          <input
            id="new"
            type="password"
            autoComplete="new-password"
            required
            className="input"
            value={next}
            onChange={(e) => setNext(e.target.value)}
          />
          <p className="mt-1 text-xs text-slate-500">
            12 caractères minimum, avec majuscules, minuscules et au moins un chiffre.
          </p>
        </div>
        <div>
          <label htmlFor="confirm" className="label">
            Confirmer le nouveau mot de passe
          </label>
          <input
            id="confirm"
            type="password"
            autoComplete="new-password"
            required
            className="input"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </div>
        <ErrorMessage message={error} />
        <button type="submit" className="btn w-full" disabled={busy}>
          Enregistrer
        </button>
        {!me.must_change_password && (
          <button type="button" className="btn-secondary w-full" onClick={() => router.push("/")}>
            Annuler
          </button>
        )}
      </form>
    </main>
  );
}
