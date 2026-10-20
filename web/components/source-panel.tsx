"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { Source } from "@/lib/api";

export function SourcePanel({ source, highlight }: { source: Source | null; highlight?: string }) {
  return (
    <aside aria-label="Source viewer" className="lg:sticky lg:top-4 lg:self-start">
      <Card>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">Source</h2>
        <AnimatePresence mode="wait">
          {source ? (
            <motion.div
              key={source.chunk_id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
            >
              <div className="mb-3 flex flex-wrap gap-2">
                <Badge>{source.doc}</Badge>
                <Badge>page {source.page}</Badge>
                <Badge>{source.section}</Badge>
                <Badge className="font-mono">{source.chunk_id}</Badge>
              </div>
              <p className="whitespace-pre-wrap text-sm leading-relaxed">
                <Highlighted text={source.text} highlight={highlight} />
              </p>
            </motion.div>
          ) : (
            <p className="text-sm text-muted">
              Select a citation chip to read the exact passage the sentence was taken from.
            </p>
          )}
        </AnimatePresence>
      </Card>
    </aside>
  );
}

function Highlighted({ text, highlight }: { text: string; highlight?: string }) {
  const needle = highlight?.replace(/\s*\[[^\]]*\]\.?\s*$/, "").trim();
  const i = needle ? text.indexOf(needle) : -1;
  if (!needle || i < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, i)}
      <mark className="rounded bg-accent-soft px-0.5 text-foreground">{needle}</mark>
      {text.slice(i + needle.length)}
    </>
  );
}
