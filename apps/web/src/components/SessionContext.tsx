"use client";

import { createContext, useContext } from "react";

import type { Me } from "@/lib/api";

export const SessionContext = createContext<{ me: Me; reload: () => Promise<void> } | null>(null);

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside the authenticated layout");
  return ctx;
}
