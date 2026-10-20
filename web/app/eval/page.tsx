"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, pct, type EvalMetrics } from "@/lib/api";

type Data = { available: boolean; metrics?: Record<string, EvalMetrics> };

export default function EvalPage() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.evaluation().then(setData).catch((e) => setError(String(e.message ?? e)));
  }, []);

  if (error)
    return (
      <Card role="alert" className="border-warn-border bg-warn-bg text-warn-fg">
        {error}
      </Card>
    );
  if (!data) return <Skeleton className="h-48 w-full" />;
  if (!data.available || !data.metrics)
    return (
      <Card data-testid="no-eval">
        <h1 className="text-xl font-bold">Evaluation dashboard</h1>
        <p className="mt-2 text-sm text-muted">
          No evaluation has been run yet. Scores appear here after <code>scripts/run_eval.py</code> is
          run on a labelled gold set. No numbers are shown until then.
        </p>
      </Card>
    );
  const rows = Object.entries(data.metrics);
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Evaluation dashboard</h1>
      <Card className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm">
          <caption className="sr-only">Metrics per configuration</caption>
          <thead>
            <tr className="border-b border-border text-xs uppercase text-muted">
              {["Config", "N", "Auto-answered", "Accuracy", "Hallucination", "Faithfulness", "Refusal P", "Refusal R"].map(
                (h) => (
                  <th key={h} scope="col" className="py-2 pr-3">
                    {h}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map(([name, m]) => (
              <tr key={name} className="border-b border-border/60">
                <th scope="row" className="py-2 pr-3 font-medium">
                  {name}
                </th>
                <td>{m.n}</td>
                <td>{pct(m.auto_answer_rate)}</td>
                <td>{pct(m.answer_accuracy)}</td>
                <td>
                  {m.hallucinations}/{m.answered} ({pct(m.hallucination_rate)}; 95% upper{" "}
                  {pct(m.hallucination_upper_95)})
                </td>
                <td>{pct(m.faithfulness)}</td>
                <td>{pct(m.refusal_precision)}</td>
                <td>{pct(m.refusal_recall)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <section aria-labelledby="bars">
        <h2 id="bars" className="mb-2 text-lg font-semibold">
          Questions answered automatically and correctly
        </h2>
        <div className="space-y-2">
          {rows.map(([name, m], i) => (
            <div key={name} className="flex items-center gap-3 text-sm">
              <span className="w-56 shrink-0 truncate">{name}</span>
              <div className="h-4 flex-1 rounded bg-border/50" role="img" aria-label={`${name}: ${pct(m.auto_answer_rate)}`}>
                <motion.div
                  className="h-4 rounded bg-accent"
                  initial={{ width: 0 }}
                  animate={{ width: `${100 * (m.auto_answer_rate ?? 0)}%` }}
                  transition={{ delay: i * 0.1, duration: 0.5 }}
                />
              </div>
              <span className="w-14 text-right tabular-nums">{pct(m.auto_answer_rate)}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
