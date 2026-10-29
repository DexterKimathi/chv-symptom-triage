import { PHASE_PRODUCTION_BUILD } from "next/constants";
import type { NextConfig } from "next";

const nextConfig = (phase: string): NextConfig => {
  // NEXT_PUBLIC_ values are written into the app when it is built. Without this check a
  // production build silently points every phone at http://localhost:8000, which is the
  // phone itself. `npm run dev` keeps that default for local work, and `next typegen`
  // (which loads this file in the same phase but builds nothing) is let through.
  const typegen = process.argv.includes("typegen");
  if (phase === PHASE_PRODUCTION_BUILD && !typegen && !process.env.NEXT_PUBLIC_API_BASE_URL) {
    throw new Error(
      "NEXT_PUBLIC_API_BASE_URL is not set. Set it to the backend's URL (for example in .env.local " +
        "or .env.production) before running `npm run build`.",
    );
  }
  return {};
};

export default nextConfig;
