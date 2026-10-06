import type { Metadata, Viewport } from "next";
import "./globals.css";

import { AuthProvider } from "@/lib/auth";

export const metadata: Metadata = {
  title: "CHV Symptom Triage",
  description: "Decision support for community health volunteers. Not a diagnosis.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0f766e",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col bg-slate-50 text-slate-900">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
