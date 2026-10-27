import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, label } from "./api";
import { Button, Empty, ErrorBox, Input, Loading } from "./components/ui";

type Metrics = {
  total_leads: number;
  inbound_leads: number;
  qualification_rate: number;
  sources: Record<string, number>;
  statuses: Record<string, number>;
  handoff_conversations: number;
  processing_failures: number;
  message_failures: number;
  ambiguous_sends: number;
  pipeline: { name: string; count: number }[];
  receipts: Record<string, number>;
  messages: Record<string, number>;
  inference_latency_ms: { samples: number; mean: number | null };
  intake_processing_ms: { samples: number; mean: number | null };
  worker_last_seen: string | null;
  definitions: Record<string, string>;
};

export function Analytics({ base }: { base: string }) {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [window, setWindow] = useState("");
  const data = useQuery({
    queryKey: ["operations", base, window],
    queryFn: () => api<Metrics>(`${base}/analytics/operations${window}`),
  });
  const groups = (title: string, values: Record<string, number>) => (
    <section className="release-card">
      <h2>{title}</h2>
      {Object.keys(values).length ? (
        <dl className="release-values">
          {Object.entries(values).map(([key, count]) => (
            <div key={key}>
              <dt>{label(key)}</dt>
              <dd>{count}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p>No records in this window.</p>
      )}
    </section>
  );
  return (
    <div className="release-page">
      <div className="page-title">
        <div>
          <span className="eyebrow">OPERATIONAL ANALYTICS</span>
          <h1>Every number has a record.</h1>
          <p>
            Workspace activity, qualification and delivery health. Updated when
            you refresh.
          </p>
        </div>
        <Button onClick={() => void data.refetch()}>Refresh analytics</Button>
      </div>
      <form
        className="release-window"
        onSubmit={(e) => {
          e.preventDefault();
          const params = new URLSearchParams();
          if (start) params.set("since", `${start}T00:00:00Z`);
          if (end) params.set("until", `${end}T00:00:00Z`);
          setWindow(params.size ? `?${params}` : "");
        }}
      >
        <label>
          Start date (UTC, inclusive)
          <Input
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </label>
        <label>
          End date (UTC, exclusive)
          <Input
            type="date"
            value={end}
            min={start || undefined}
            onChange={(e) => setEnd(e.target.value)}
          />
        </label>
        <Button type="submit">Apply dates</Button>
        <Button
          type="button"
          onClick={() => {
            setStart("");
            setEnd("");
            setWindow("");
          }}
        >
          All time
        </Button>
      </form>
      {data.isPending ? (
        <Loading />
      ) : data.error ? (
        <ErrorBox
          message={data.error.message}
          retry={() => void data.refetch()}
        />
      ) : (
        <>
          {!data.data.total_leads && (
            <Empty
              title="A fresh perspective starts here"
              text="No leads were created in this window. Add a lead or queue a signed integration test to begin."
            />
          )}
          <div className="release-metrics">
            {[
              [
                "Total leads",
                data.data.total_leads,
                data.data.definitions.leads,
              ],
              [
                "Inbound source leads",
                data.data.inbound_leads,
                data.data.definitions.leads,
              ],
              [
                "Qualification rate",
                `${data.data.qualification_rate}%`,
                data.data.definitions.rate,
              ],
              [
                "Handoff conversations",
                data.data.handoff_conversations,
                data.data.definitions.handoffs,
              ],
              [
                "Processing failures",
                data.data.processing_failures,
                data.data.definitions.failures,
              ],
              [
                "Message failures",
                data.data.message_failures,
                data.data.definitions.failures,
              ],
              [
                "Unknown sends",
                data.data.ambiguous_sends,
                "Ambiguous provider sends requiring manual reconciliation. Never automatically resent.",
              ],
            ].map(([name, value, definition]) => (
              <article
                className="release-card"
                key={name}
                title={String(definition)}
              >
                <h2>{name}</h2>
                <strong className="release-number">{value}</strong>
              </article>
            ))}
          </div>
          <div className="release-grid">
            {groups("Leads by source", data.data.sources)}
            {groups("Current qualification status", data.data.statuses)}
            {groups("Intake receipt states", data.data.receipts)}
            {groups("Message states", data.data.messages)}
            <section className="release-card">
              <h2>Current stage distribution</h2>
              <p className="release-note">
                Snapshot of the selected lead cohort, not historical stage
                conversion.
              </p>
              <dl className="release-values">
                {data.data.pipeline.map((stage) => (
                  <div key={stage.name}>
                    <dt>{stage.name}</dt>
                    <dd>{stage.count}</dd>
                  </div>
                ))}
              </dl>
            </section>
            <section className="release-card">
              <h2>Observed timing</h2>
              {[
                ["Provider inference", data.data.inference_latency_ms],
                ["Intake to processing", data.data.intake_processing_ms],
              ].map(([name, raw]) => {
                const timing = raw as { samples: number; mean: number | null };
                return (
                  <p key={String(name)}>
                    <strong>{String(name)}:</strong>{" "}
                    {timing.mean === null
                      ? "No measured samples"
                      : `${timing.mean} ms mean · ${timing.samples} samples`}
                  </p>
                );
              })}
              <p className="release-note">{data.data.definitions.timing}</p>
              {data.data.worker_last_seen && (
                <p>
                  Worker last seen:{" "}
                  {new Date(data.data.worker_last_seen).toLocaleString()}
                </p>
              )}
            </section>
          </div>
          <details className="release-card">
            <summary>Metric definitions and exclusions</summary>
            {Object.entries(data.data.definitions).map(([key, text]) => (
              <p key={key}>{text}</p>
            ))}
          </details>
        </>
      )}
    </div>
  );
}
