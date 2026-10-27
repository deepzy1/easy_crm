import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import {
  Button,
  Empty,
  ErrorBox,
  Input,
  Loading,
  Modal,
  Textarea,
} from "./components/ui";

type Source = {
  id: string;
  title: string;
  text: string;
  approved: boolean;
  kind: string;
  origin: string;
  state: string;
  error: string;
};

export function Knowledge({ base }: { base: string }) {
  const client = useQueryClient();
  const [kind, setKind] = useState("website");
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [authorized, setAuthorized] = useState(false);
  const [review, setReview] = useState<Source | null>(null);
  const [remove, setRemove] = useState<Source | null>(null);
  const [query, setQuery] = useState("");
  const [notice, setNotice] = useState("");
  const sources = useQuery({
    queryKey: ["knowledge", base],
    queryFn: () =>
      api<{ items: Source[]; can_manage: boolean }>(
        `${base}/knowledge/sources`,
      ),
  });
  const refresh = () => {
    void client.invalidateQueries({ queryKey: ["knowledge", base] });
    void client.invalidateQueries({
      queryKey: ["qualification-sources", base],
    });
    search.reset();
  };
  const ingest = useMutation({
    mutationFn: () =>
      kind === "website"
        ? api<Source>(`${base}/knowledge/sources`, {
            method: "POST",
            body: JSON.stringify({ title, url, authorized }),
          })
        : api<Source>(
            `${base}/knowledge/uploads?title=${encodeURIComponent(title)}`,
            {
              method: "POST",
              headers: { "Content-Type": "application/pdf" },
              body: file,
            },
          ),
    onSuccess: (source) => {
      refresh();
      setNotice(
        source.state === "failed"
          ? "Import failed. See the source error below."
          : "Text extracted. Review it before approving retrieval.",
      );
      if (source.state === "ready") setReview(source);
    },
  });
  const save = useMutation({
    mutationFn: (source: Source) =>
      api(`${base}/knowledge/sources/${source.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: source.title,
          text: source.text,
          approved: source.approved,
        }),
      }),
    onSuccess: () => {
      setReview(null);
      setNotice("Source review saved.");
      refresh();
    },
  });
  const erase = useMutation({
    mutationFn: (source: Source) =>
      api(`${base}/knowledge/sources/${source.id}`, { method: "DELETE" }),
    onSuccess: () => {
      setRemove(null);
      setNotice(
        "Source removed from future retrieval. Existing audit citations remain.",
      );
      refresh();
    },
  });
  const search = useMutation({
    mutationFn: () =>
      api<{ items: { source_id: string; title: string; text: string }[] }>(
        `${base}/knowledge/search?q=${encodeURIComponent(query)}`,
      ),
  });
  return (
    <div className="release-page">
      <div className="page-title">
        <div>
          <span className="eyebrow">BUSINESS KNOWLEDGE</span>
          <h1>Answers with a source.</h1>
          <p>
            Import a public page or text PDF, review the extracted content, then
            approve it for qualification.
          </p>
        </div>
      </div>
      <p className="release-note">
        One page per import; no crawling or OCR. PDFs: up to 2 MiB, first 30
        pages. Extracted text: up to 12,000 characters. Original files are
        discarded. Only approved sources can be retrieved.
      </p>
      {notice && (
        <p role="status" className="release-note">
          {notice}
        </p>
      )}
      {sources.data?.can_manage && (
        <form
          className="release-card release-form"
          onSubmit={(e) => {
            e.preventDefault();
            setNotice("");
            ingest.mutate();
          }}
        >
          <div className="view-toggle" aria-label="Import source type">
            <Button
              type="button"
              aria-pressed={kind === "website"}
              onClick={() => setKind("website")}
            >
              Website page
            </Button>
            <Button
              type="button"
              aria-pressed={kind === "pdf"}
              onClick={() => setKind("pdf")}
            >
              PDF document
            </Button>
          </div>
          <label>
            Source title
            <Input
              required
              maxLength={150}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          {kind === "website" ? (
            <label>
              Public HTTPS URL
              <Input
                type="url"
                required
                placeholder="https://your-business.example/policies"
                maxLength={500}
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
            </label>
          ) : (
            <label>
              Text PDF
              <Input
                type="file"
                accept="application/pdf,.pdf"
                required
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
            </label>
          )}
          <label className="release-check">
            <input
              type="checkbox"
              required
              checked={authorized}
              onChange={(e) => setAuthorized(e.target.checked)}
            />{" "}
            I am authorized to import this business content.
          </label>
          <Button
            type="submit"
            variant="primary"
            disabled={
              ingest.isPending || !authorized || (kind === "pdf" && !file)
            }
          >
            {ingest.isPending ? "Extracting content…" : "Import for review"}
          </Button>
        </form>
      )}
      {(sources.error || ingest.error || erase.error) && (
        <ErrorBox
          message={(sources.error || ingest.error || erase.error)!.message}
        />
      )}
      {sources.isPending ? (
        <Loading />
      ) : !sources.data?.items.length ? (
        <Empty
          title="Start with trusted information"
          text="No business sources yet. Add reviewed text in AI Qualification or import a page or PDF here."
        />
      ) : (
        <div className="release-source-list">
          {sources.data.items.map((source) => (
            <article className="release-card" key={source.id}>
              <div className="qualification-section-heading">
                <h2>{source.title}</h2>
                <span className="outline-pill">
                  {source.state === "failed"
                    ? "Failed"
                    : source.approved
                      ? "Approved"
                      : "Awaiting review"}
                </span>
              </div>
              <p className="release-note">
                {source.kind} · {source.origin || "Manually entered text"}
              </p>
              {source.error ? (
                <ErrorBox message={source.error} />
              ) : (
                <p className="source-preview">
                  {source.text.slice(0, 400)}
                  {source.text.length > 400 ? "…" : ""}
                </p>
              )}
              {sources.data.can_manage && (
                <div className="form-actions">
                  {source.state === "ready" && (
                    <Button
                      onClick={() => {
                        save.reset();
                        setReview({ ...source });
                      }}
                    >
                      Review source
                    </Button>
                  )}
                  <Button variant="ghost" onClick={() => setRemove(source)}>
                    Remove source
                  </Button>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
      <form
        className="release-card release-form"
        onSubmit={(e) => {
          e.preventDefault();
          search.mutate();
        }}
      >
        <h2>Check approved knowledge</h2>
        <p>
          Search the same workspace sources used by qualification. Results are
          verbatim excerpts, with no inference call.
        </p>
        <label>
          Business question
          <Input
            required
            maxLength={500}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <Button type="submit" disabled={search.isPending}>
          Search approved sources
        </Button>
        {search.error && <ErrorBox message={search.error.message} />}
        {search.data &&
          (search.data.items.length ? (
            search.data.items.map((s) => (
              <blockquote key={s.source_id}>
                <strong>{s.title}</strong>
                <p>{s.text}</p>
              </blockquote>
            ))
          ) : (
            <p role="status">
              No approved source supports this query. The qualification flow
              asks for human review for unsupported business questions.
            </p>
          ))}
      </form>
      {review && (
        <Modal
          title="Review business source"
          onClose={() => setReview(null)}
          wide
        >
          <form
            className="release-form"
            onSubmit={(e) => {
              e.preventDefault();
              save.mutate(review);
            }}
          >
            <label>
              Reviewed title
              <Input
                required
                maxLength={150}
                value={review.title}
                onChange={(e) =>
                  setReview({ ...review, title: e.target.value })
                }
              />
            </label>
            <label>
              Extracted text
              <Textarea
                required
                rows={14}
                maxLength={12000}
                value={review.text}
                onChange={(e) => setReview({ ...review, text: e.target.value })}
              />
            </label>
            <label className="release-check">
              <input
                type="checkbox"
                checked={review.approved}
                onChange={(e) =>
                  setReview({ ...review, approved: e.target.checked })
                }
              />{" "}
              I reviewed the text and approve it for retrieval
            </label>
            {save.error && <ErrorBox message={save.error.message} />}
            <Button type="submit" variant="primary" disabled={save.isPending}>
              Save source review
            </Button>
          </form>
        </Modal>
      )}
      {remove && (
        <Modal title="Remove this source?" onClose={() => setRemove(null)}>
          <p>
            {remove.title} will no longer be retrieved. Historical citations in
            conversations remain in their audit record.
          </p>
          <div className="form-actions">
            <Button onClick={() => setRemove(null)}>Cancel</Button>
            <Button
              variant="danger"
              disabled={erase.isPending}
              onClick={() => erase.mutate(remove)}
            >
              Confirm removal
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
