import type { Metadata } from "next";
import type { ReactNode } from "react";
import "../dist/fonts.css";
import "../dist/tailwind.css";
import "../src/style.css";
import "./globals.css";

export const metadata: Metadata = { title: "PRISMA | Tanya data BPS", description: "Tanya jawab statistik BPS berbahasa Indonesia dengan layanan lokal." };
export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="id"><body>{children}</body></html>;
}
