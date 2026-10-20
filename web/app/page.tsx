"use client";

import { motion } from "framer-motion";
import { AlertTriangle, Search, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { CitationText } from "@/components/citation-text";
import { SourcePanel } from "@/components/source-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type AskResult, type Source } from "@/lib/api";
import { useReveal } from "@/lib/use-reveal";

const REASONS: Record<string, string> = {
  no_evidence: "No passage in the documents matched the question.",
  low_score: "The best matching passage was too weak to rely on.",
  unsupported_facts: "The drafted answer contained a fact that is not in the retrieved text.",
  key_term_missing: "The answer lacked a term or figure the question asked about.",
  verifier_removed_all: "Every drafted sentence failed verification against its cited passage.",
  no_answer_sentence: "No sentence in the retrieved passages answered the question.",
};

const SUGGESTIONS = [
  "What is the management fee?",
  "What is the carried interest and hurdle rate?",
  "What is the net asset value of the fund?",
];

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AskResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [source, setSource] = useState<Source | null>(null);
  const [highlight, setHighlight] = useState<string>("");

  async function submit(q: string) {
    if (!q.trim() || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setSource(null);
    try {
      setResult(await api.ask(q));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
      <section aria-labelledby="ask-h" className="space-y-5">
        <div>
          <h1 id="ask-h" className="text-2xl font-bold">
            Ask the fund documents
          </h1>
          <p className="mt-1 text-sm text-muted">
            Every sentence cites its source page. If the documents do not support an answer, the
            system refuses instead of guessing.
          </p>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit(question);
          }}
          className="flex flex-col gap-3 sm:flex-row"
        >
          <label htmlFor="q" className="sr-only">
            Your question
          </label>
          <input
            id="q"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. What is the management fee?"
            className="min-h-11 flex-1 rounded-lg border border-border bg-card px-3 text-sm"
          />
          <Button type="submit" disabled={loading || !question.trim()}>
            <Search aria-hidden className="size-4" /> Ask
          </Button>
        </form>
        <div className="flex flex-wrap gap-2" aria-label="Example questions">
          {SUGGESTIONS.map((s) => (
            <Button
              key={s}
              variant="outline"
              className="min-h-11 text-xs"
              onClick={() => {
                setQuestion(s);
                submit(s);
              }}
            >
              {s}
            </Button>
          ))}
        </div>

        {loading && (
          <Card aria-busy="true" aria-label="Loading answer" className="space-y-3">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-2/3" />
          </Card>
        )}
        {error && (
          <Card role="alert" className="border-warn-border bg-warn-bg text-warn-fg">
            {error}
          </Card>
        )}
        {result &&
          (result.refused ? (
            <Refusal r={result} />
          ) : (
            <AnswerCard
              key={result.text}
              r={result}
              onOpen={(s, sentence) => {
                setSource(s);
                setHighlight(sentence);
              }}
            />
          ))}
      </section>
      <SourcePanel source={source} highlight={highlight} />
    </div>
  );
}

function AnswerCard({
  r,
  onOpen,
}: {
  r: AskResult;
  onOpen: (s: Source, sentence: string) => void;
}) {
  const { shown, done } = useReveal(r.text);
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <Card data-testid="answer" className="space-y-4">
        <p role="status" className="sr-only">
          {r.text}
        </p>
        <div aria-hidden={!done ? true : undefined}>
          {done ? <CitationText text={r.text} sources={r.sources} onOpen={onOpen} /> : <p>{shown}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
          <Badge className="gap-1 text-ok">
            <ShieldCheck aria-hidden className="size-3.5" />
            {r.verified ? "Verified against cited pages" : "Partly verified"}
          </Badge>
          <Badge>retrieval: {r.mode}</Badge>
          {r.stripped.length > 0 && (
            <Badge>{r.stripped.length} unsupported sentence(s) removed</Badge>
          )}
        </div>
      </Card>
    </motion.div>
  );
}

function Refusal({ r }: { r: AskResult }) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <Card
        data-testid="refusal"
        role="status"
        className="space-y-2 border-warn-border bg-warn-bg text-warn-fg"
      >
        <h2 className="flex items-center gap-2 font-semibold">
          <AlertTriangle aria-hidden className="size-5" /> Not answerable from the provided documents
        </h2>
        <p>{REASONS[r.reason] ?? r.reason}</p>
        <p className="text-sm">
          Refusal reason: <code>{r.reason}</code>. Refusing is the correct behaviour when the evidence
          is missing; the refusal is counted in the evaluation.
        </p>
      </Card>
    </motion.div>
  );
}
