"use client";

import { Upload } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type DocInfo, type UploadResult } from "@/lib/api";

export default function LibraryPage() {
  const [docs, setDocs] = useState<DocInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    api.documents().then((d) => setDocs(d.documents)).catch((e) => setError(String(e.message ?? e)));
  }, []);
  useEffect(load, [load]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file || busy) return;
    setBusy(true);
    setResult(null);
    setUploadError(null);
    try {
      setResult(await api.upload(file));
      if (fileRef.current) fileRef.current.value = "";
      load();
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

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
      <Card className="space-y-3">
        <h2 className="text-lg font-semibold">Try your own document</h2>
        <p className="max-w-2xl text-sm text-muted">
          Upload a PDF or an Excel file (.xlsx), up to 25 MB, then ask questions about it on the Ask
          screen. The file is held in memory by this app on your computer and is not sent anywhere
          else. Scanned PDFs without a text layer cannot be read.
        </p>
        <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <label htmlFor="file" className="sr-only">
            Document file
          </label>
          <input
            id="file"
            ref={fileRef}
            type="file"
            accept=".pdf,.xlsx"
            className="min-h-11 flex-1 rounded-lg border border-border bg-card px-3 py-2 text-sm"
          />
          <Button type="submit" disabled={busy}>
            <Upload aria-hidden className="size-4" /> {busy ? "Reading..." : "Upload"}
          </Button>
        </form>
        <div role="status" aria-live="polite" className="text-sm">
          {uploadError && <p className="text-warn-fg bg-warn-bg border border-warn-border rounded-lg p-3">{uploadError}</p>}
          {result && (
            <div data-testid="upload-result" className="space-y-1">
              <p>
                Added <strong>{result.doc}</strong>: {result.pages} {result.kind}, {result.chunks}{" "}
                passages. Pick it under &ldquo;Search in&rdquo; on the Ask screen.
              </p>
              <ul className="list-disc space-y-1 pl-5 text-muted">
                {result.notes.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </Card>
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
                    {d.uploaded && <span className="mr-2 rounded-full border border-border px-2 py-0.5 text-xs font-medium text-muted">uploaded</span>}
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
