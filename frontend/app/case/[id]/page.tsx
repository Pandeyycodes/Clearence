"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { CaseRecord, getCase } from "@/lib/api";
import { CaseCard } from "@/components/case";

export default function CasePage() {
  const { id } = useParams<{ id: string }>();
  const [c, setC] = useState<CaseRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCase(id).then(setC).catch((e) => setError(e.message));
  }, [id]);

  if (error) return <div className="error-note">{error}</div>;
  if (!c) return <p className="mono small">Retrieving case…</p>;
  return (
    <main>
      <CaseCard c={c} />
      {c.batch_id && (
        <p><Link href={`/batch/${c.batch_id}`}>← back to batch</Link></p>
      )}
    </main>
  );
}
