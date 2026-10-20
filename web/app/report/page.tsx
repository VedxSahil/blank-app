"use client";

import { motion } from "framer-motion";
import { FileText, Minus } from "lucide-react";
import { useState } from "react";
import { CitationText } from "@/components/citation-text";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type ReportResult } from "@/lib/api";

export default function ReportPage() {
  const [report, setReport] = useState<ReportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function draft() {
    setLoading(true);
    setError(null);
    try {
      setReport(await api.report());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Quarterly report builder</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            Each line is assembled only from retrieved passages and bound to chunk IDs. Fields the
            documents do not support print &ldquo;Not disclosed in provided documents&rdquo;.
          </p>
        </div>
        <Button onClick={draft} disabled={loading}>
          <FileText aria-hidden className="size-4" /> {loading ? "Drafting..." : "Draft report"}
        </Button>
      </div>
      {error && (
        <Card role="alert" className="border-warn-border bg-warn-bg text-warn-fg">
          {error}
        </Card>
      )}
      {loading && (
        <div aria-busy="true" className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      )}
      {report && (
        <>
          <p data-testid="coverage" className="text-sm">
            <strong>{report.disclosed}</strong> of <strong>{report.total}</strong> fields supported by the
            documents.
          </p>
          <motion.div
            className="grid gap-4 md:grid-cols-2"
            initial="hidden"
            animate="show"
            variants={{ show: { transition: { staggerChildren: 0.08 } } }}
          >
            {report.sections.map((s) => (
              <motion.div
                key={s.title}
                variants={{ hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } }}
              >
                <Card>
                  <h2 className="mb-3 text-lg font-semibold">{s.title}</h2>
                  <dl className="space-y-3">
                    {s.lines.map((ln) => (
                      <div key={ln.label}>
                        <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
                          {ln.label}
                        </dt>
                        <dd className="text-sm">
                          {ln.disclosed ? (
                            <>
                              <CitationText text={ln.text} sources={[]} onOpen={() => {}} animate={false} />
                              <span className="mt-1 flex flex-wrap gap-1">
                                {ln.chunk_ids.map((id) => (
                                  <Badge key={id} className="font-mono">
                                    {id}
                                  </Badge>
                                ))}
                              </span>
                            </>
                          ) : (
                            <span className="inline-flex items-center gap-1 italic text-muted">
                              <Minus aria-hidden className="size-3" /> {ln.text}
                            </span>
                          )}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </Card>
              </motion.div>
            ))}
          </motion.div>
        </>
      )}
    </div>
  );
}
