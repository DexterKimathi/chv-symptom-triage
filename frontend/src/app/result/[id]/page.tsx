"use client";

import { useParams } from "next/navigation";

import { ResultScreen } from "@/components/ResultScreen";
import { RequireAuth } from "@/lib/auth";

/** The result straight after an assessment is sent. */
export default function ResultPage() {
  const { id } = useParams<{ id: string }>();
  return <RequireAuth><ResultScreen id={id} saved={false} /></RequireAuth>;
}
