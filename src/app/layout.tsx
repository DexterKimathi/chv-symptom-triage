import type { Metadata, Viewport } from "next";
import { Atkinson_Hyperlegible, Atkinson_Hyperlegible_Mono } from "next/font/google";
import "./globals.css";

import { AuthProvider } from "@/lib/auth";

// Fonts are downloaded at build time and served with the app, so phones never fetch them
// from Google. The system font shows until they load.
const atkinson = Atkinson_Hyperlegible({
  weight: ["400", "700"],
  subsets: ["latin"],
  variable: "--font-atkinson",
  display: "swap",
});
const atkinsonMono = Atkinson_Hyperlegible_Mono({
  weight: ["400", "700"],
  subsets: ["latin"],
  variable: "--font-atkinson-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "CHV Triage",
  description: "Symptom checklist and referral support for community health volunteers. Not a diagnosis.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#13588a",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${atkinson.variable} ${atkinsonMono.variable} antialiased`}>
      <body className="bg-canvas font-sans text-ink">
        {/* Phone-width column; on a wider screen it sits centred on the grey canvas. */}
        <div className="mx-auto flex min-h-dvh w-full max-w-[480px] flex-col bg-white">
          <AuthProvider>{children}</AuthProvider>
        </div>
      </body>
    </html>
  );
}
