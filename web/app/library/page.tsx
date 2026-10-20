"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type DocInfo } from "@/lib/api";

export default function LibraryPage() {
  const [docs, setDocs] = useState<DocInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.documents().then((d) => setDocs(d.documents)).catch((e) => setError(String(e.message ?? e)));
  }, []);

  if (error)
    return (
      <Card role="alert" className="border-warn-border bg-warn-bg text-warn-fg">
        {error}
      </Card>
    );
  if (!docs) return <Skeleton className="h-48 w-full" />;
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Document library</h1>
      {docs.length === 0 ? (
        <Card data-testid="no-docs">
          <p className="text-sm text-muted">
            No documents are loaded. Add real public documents with <code>scripts/download.py</code>{" "}
            and build the index with <code>scripts/build_index.py</code>.
          </p>
        </Card>
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <caption className="sr-only">Indexed documents</caption>
            <thead>
              <tr className="border-b border-border text-xs uppercase text-muted">
                {["Document", "Pages", "Chunks", "Publisher", "Pulled", "SHA-256"].map((h) => (
                  <th key={h} scope="col" className="py-2 pr-3">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.doc} className="border-b border-border/60">
                  <th scope="row" className="py-2 pr-3 font-medium">
                    {d.url ? (
                      <a className="text-accent underline" href={d.url}>
                        {d.doc}
                      </a>
                    ) : (
                      d.doc
                    )}
                  </th>
                  <td>{d.pages}</td>
                  <td>{d.chunks}</td>
                  <td>{d.publisher ?? "n/a"}</td>
                  <td>{d.date_pulled?.slice(0, 10) ?? "n/a"}</td>
                  <td className="font-mono text-xs">{d.sha256?.slice(0, 12) ?? "n/a"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
