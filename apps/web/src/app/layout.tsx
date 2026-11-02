import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NEWTON",
  description: "Chiffrage et pilotage pour entreprises d'électricité",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
