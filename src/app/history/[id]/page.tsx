"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { ResultView } from "@/components/ResultView";
import { ErrorMessage, Loading, Screen } from "@/components/ui";
import { api } from "@/lib/api";
import { RequireAuth, useAuth, useSessionGuard } from "@/lib/auth";
import type { Assessment } from "@/lib/types";

function Detail() {
  const { id } = useParams<{ id: string }>();
  const { session } = useAuth();
  const guard = useSessionGuard();
  const [result, setResult] = useState<Assessment | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    api.assessment(session.token, id)
      .then(setResult)
      .catch((e) => { if (!guard(e)) setError(e.message); });
  }, [session, id, guard]);

  return (
    <Screen title="Result" back="/">
      <ErrorMessage message={error} />
      {!result && !error && <Loading />}
      {result && <ResultView result={result} />}
    </Screen>
  );
}

export default function HistoryPage() {
  return <RequireAuth><Detail /></RequireAuth>;
}
