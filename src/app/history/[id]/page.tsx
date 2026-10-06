"use client";

import { useParams } from "next/navigation";

import { ResultScreen } from "@/components/ResultScreen";
import { RequireAuth } from "@/lib/auth";

/** A past assessment, shown read-only exactly as it was first given. */
export default function HistoryPage() {
  const { id } = useParams<{ id: string }>();
  return <RequireAuth><ResultScreen id={id} saved /></RequireAuth>;
}
