import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageSquare, Plug, Send } from "lucide-react";
import { api, label } from "./api";
import {
  Badge,
  Button,
  Empty,
  ErrorBox,
  Input,
  Loading,
  Select,
  Textarea,
} from "./components/ui";

type Integration = {
  id: string;
  name: string;
  kind: string;
  active: boolean;
  ai_enabled: boolean;
  configured: boolean;
  webhook_url: string;
  field_map: Record<string, string>;
};
type IntegrationsData = {
  items: Integration[];
  website_configured: boolean;
  meta_credentials: { alias: string; kind: string }[];
  limits: string;
};
type Deliveries = {
  events: {
    id: string;
    integration_id: string;
    status: string;
    attempts: number;
    error: string;
    received_at: string;
  }[];
  requests: {
    id: string;
    integration_id: string;
    result: string;
    created_at: string;
  }[];
};
const post = <T,>(path: string, body?: unknown) =>
  api<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });

export function Integrations({ base }: { base: string }) {
  const client = useQueryClient();
  const data = useQuery({
    queryKey: [base, "integrations"],
    queryFn: () => api<IntegrationsData>(`${base}/integrations`),
  });
  const logs = useQuery({
    queryKey: [base, "deliveries"],
    queryFn: () => api<Deliveries>(`${base}/integrations/deliveries`),
    refetchInterval: 5000,
  });
  const [name, setName] = useState("Website enquiries");
  const [kind, setKind] = useState("website");
  const [alias, setAlias] = useState("");
  const [mapping, setMapping] = useState("{}");
  const [secret, setSecret] = useState("");
  const [result, setResult] = useState("");
  const mutation = useMutation({
    mutationFn: async ({
      path,
      body,
      method = "POST",
    }: {
      path: string;
      body?: unknown;
      method?: string;
    }) => {
      return api<{ signing_secret?: string; detail?: string }>(
        `${base}/integrations${path}`,
        { method, body: body === undefined ? undefined : JSON.stringify(body) },
      );
    },
    onSuccess: (value) => {
      if (value.signing_secret) setSecret(value.signing_secret);
      setResult(value.detail || "Integration updated.");
      void client.invalidateQueries({ queryKey: [base, "integrations"] });
      void client.invalidateQueries({ queryKey: [base, "deliveries"] });
    },
  });
  if (data.isPending) return <Loading />;
  if (data.error) return <ErrorBox message={data.error.message} />;
  return (
    <div className="channels-page">
      <header className="channels-heading">
        <Plug size={24} />
        <div>
          <h2>Connect your channels</h2>
          <p>
            Signed website forms and official WhatsApp messaging, with human
            control.
          </p>
        </div>
      </header>
      <p className="channel-notice">{data.data.limits}</p>
      {!data.data.website_configured && (
        <ErrorBox message="Website webhooks need WEBHOOK_MASTER_KEY configured on the backend (32 or more random characters)." />
      )}
      <form
        className="channel-card channel-form"
        onSubmit={(event) => {
          event.preventDefault();
          let fields: unknown;
          try {
            fields = JSON.parse(mapping);
          } catch {
            setResult("Field mapping must be valid JSON.");
            return;
          }
          mutation.mutate({
            path: "",
            body: {
              name,
              kind,
              credential_alias: kind === "website" ? "" : alias,
              field_map: fields,
              ai_enabled: false,
            },
          });
        }}
      >
        <h3>Add an integration</h3>
        <label>
          Name
          <Input
            required
            maxLength={100}
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <label>
          Channel
          <Select
            value={kind}
            onChange={(event) => {
              setKind(event.target.value);
              setAlias("");
            }}
          >
            <option value="website">Website form</option>
            <option value="whatsapp">WhatsApp Cloud API</option>
            <option value="meta_leads">Facebook Lead Ads</option>
            <option value="instagram">Instagram (receive only)</option>
          </Select>
        </label>
        {kind !== "website" && (
          <label>
            Authorized backend credential
            <Select
              required
              value={alias}
              onChange={(event) => setAlias(event.target.value)}
            >
              <option value="">Choose configured credentials</option>
              {data.data.meta_credentials
                .filter((item) => item.kind === kind)
                .map((item) => (
                  <option key={item.alias} value={item.alias}>
                    {item.alias}
                  </option>
                ))}
            </Select>
          </label>
        )}
        {kind === "website" && (
          <label>
            Field mapping (canonical field → your form field)
            <Textarea
              aria-label="Field mapping"
              value={mapping}
              onChange={(event) => setMapping(event.target.value)}
              placeholder={'{"name":"full_name","message":"enquiry"}'}
            />
          </label>
        )}
        {kind !== "website" && (
          <p>
            Set this workspace’s credentials in META_CONNECTIONS on the backend,
            then restart API and worker. No tokens are stored in your browser.
          </p>
        )}
        <Button
          variant="primary"
          disabled={
            mutation.isPending ||
            (kind === "website" && !data.data.website_configured)
          }
        >
          Create integration
        </Button>
      </form>
      {mutation.error && <ErrorBox message={mutation.error.message} />}
      {result && <p role="status">{result}</p>}
      {secret && (
        <section className="channel-card">
          <h3>Save your new signing secret</h3>
          <p>
            Shown once. Store it on your trusted website backend. Never place it
            in public HTML or JavaScript.
          </p>
          <code className="channel-secret">{secret}</code>
          <Button onClick={() => setSecret("")}>I have saved the secret</Button>
        </section>
      )}
      {data.data.items.length === 0 && (
        <Empty
          title="No integrations yet"
          text="Add a website form or configure an authorized Meta test account."
        />
      )}
      {data.data.items.map((item) => (
        <section className="channel-card" key={item.id}>
          <div className="channel-card-title">
            <h3>{item.name}</h3>
            <Badge value={label(item.kind)} />
            <Badge value={item.active ? "Active" : "Revoked"} />
          </div>
          <p>
            {item.configured
              ? "Backend configuration present"
              : "Backend configuration missing"}{" "}
            · Live delivery unverified
          </p>
          <label>
            Webhook callback URL
            <Input
              readOnly
              aria-label={`${item.name} webhook URL`}
              value={location.origin + item.webhook_url}
            />
          </label>
          <div className="channel-actions">
            <Button
              disabled={mutation.isPending}
              onClick={() => mutation.mutate({ path: `/${item.id}/test` })}
            >
              {item.kind === "website"
                ? "Queue fictional test"
                : "Test account lookup"}
            </Button>
            {item.kind === "website" && (
              <Button
                disabled={mutation.isPending}
                onClick={() => {
                  if (
                    window.confirm(
                      "Revoke the previous signing secret immediately?",
                    )
                  )
                    mutation.mutate({ path: `/${item.id}/rotate` });
                }}
              >
                Rotate secret
              </Button>
            )}
            <Button
              disabled={mutation.isPending}
              onClick={() =>
                mutation.mutate({
                  path: `/${item.id}`,
                  method: "PATCH",
                  body: { active: !item.active, ai_enabled: item.ai_enabled },
                })
              }
            >
              {item.active ? "Revoke integration" : "Reactivate"}
            </Button>
            <Button
              disabled={mutation.isPending || !item.active}
              onClick={() =>
                mutation.mutate({
                  path: `/${item.id}`,
                  method: "PATCH",
                  body: { active: item.active, ai_enabled: !item.ai_enabled },
                })
              }
            >
              {item.ai_enabled
                ? "Disable AI qualification"
                : "Enable AI qualification"}
            </Button>
          </div>
        </section>
      ))}
      <section className="channel-card">
        <h3>Website setup</h3>
        <p>
          Submit your public form to a trusted server endpoint. That server
          signs the exact JSON bytes with HMAC-SHA256 over timestamp + "." +
          event ID + "." + body and forwards them here.
        </p>
        <p>
          Use X-EasyCRM-Event-ID, X-EasyCRM-Timestamp (Unix seconds, within 5
          minutes) and X-EasyCRM-Signature (sha256=hex). Keep the same event ID
          and body when redelivering. Consent defaults to false. See the Session
          4 handoff for a runnable signing client and HTML form.
        </p>
      </section>
      <section className="channel-card">
        <h3>Delivery log</h3>
        <p>
          Accepted means durably queued. A running channel worker is required
          for processing.
        </p>
        {logs.error && <ErrorBox message={logs.error.message} />}
        {logs.data?.events.length === 0 && <p>No deliveries received.</p>}
        <div className="channel-deliveries">
          {logs.data?.events.map((event) => (
            <article key={event.id}>
              <div>
                <Badge value={event.status} />{" "}
                <small>
                  {new Date(event.received_at).toLocaleString()} ·{" "}
                  {event.attempts} attempts
                </small>
                <p>{event.error || "No processing errors"}</p>
              </div>
              {event.status === "failed" && (
                <Button
                  disabled={mutation.isPending}
                  onClick={() => {
                    if (
                      window.confirm(
                        "Retry this delivery? Qualification may consume provider quota.",
                      )
                    )
                      mutation.mutate({
                        path: `/deliveries/${event.id}/retry`,
                      });
                  }}
                >
                  Retry delivery
                </Button>
              )}
            </article>
          ))}
        </div>
        {logs.data?.requests.slice(0, 10).map((request) => (
          <p key={request.id}>
            <small>
              {new Date(request.created_at).toLocaleString()} · {request.result}
            </small>
          </p>
        ))}
      </section>
    </div>
  );
}

type Thread = {
  id: string;
  lead_id: string;
  name: string;
  source: string;
  mode: string;
  opted_out: boolean;
  last_inbound_at: string | null;
  active: boolean;
  summary: string;
  score: number | null;
  lead_status: string;
  can_send: boolean;
};
type Message = {
  id: string;
  direction: string;
  text: string;
  status: string;
  ai_generated: boolean;
  error: string;
  created_at: string;
};
export function ChannelInbox({
  base,
  onViewLead,
}: {
  base: string;
  onViewLead: (name: string) => void;
}) {
  const client = useQueryClient();
  const [selected, setSelected] = useState("");
  const threads = useQuery({
    queryKey: [base, "inbox"],
    queryFn: () => api<Thread[]>(`${base}/inbox`),
    refetchInterval: 4000,
  });
  const thread =
    threads.data?.find((item) => item.id === selected) || threads.data?.[0];
  const messages = useQuery({
    queryKey: [base, "messages", thread?.id],
    queryFn: () => api<Message[]>(`${base}/inbox/${thread!.id}/messages`),
    enabled: !!thread,
    refetchInterval: 3000,
  });
  const [text, setText] = useState("");
  const [reason, setReason] = useState("");
  const [receipt, setReceipt] = useState(() => crypto.randomUUID());
  const mutation = useMutation({
    mutationFn: ({ path, body }: { path: string; body: unknown }) =>
      post(`${base}/inbox/${thread!.id}/${path}`, body),
    onSuccess: (_, vars) => {
      if (vars.path === "messages") {
        setText("");
        setReceipt(crypto.randomUUID());
      }
      void client.invalidateQueries({ queryKey: [base, "inbox"] });
      void client.invalidateQueries({ queryKey: [base, "messages"] });
      void client.invalidateQueries({ queryKey: [base, "qualification"] });
    },
  });
  if (threads.isPending) return <Loading />;
  if (threads.error) return <ErrorBox message={threads.error.message} />;
  return (
    <div className="channels-page">
      <header className="channels-heading">
        <MessageSquare size={24} />
        <div>
          <h2>Your shared inbox</h2>
          <p>Customer messages, qualification context, and a clear handoff.</p>
        </div>
      </header>
      {!thread ? (
        <Empty
          title="No conversations yet"
          text="Connect a channel in Integrations and receive a signed event. Queued events need the channel worker to appear here."
        />
      ) : (
        <div className="channel-inbox">
          <aside className="channel-thread-list" aria-label="Conversations">
            {threads.data?.map((item) => (
              <button
                key={item.id}
                className={item.id === thread.id ? "selected" : ""}
                onClick={() => {
                  setSelected(item.id);
                  setText("");
                  setReason("");
                  setReceipt(crypto.randomUUID());
                  mutation.reset();
                }}
              >
                <strong>{item.name}</strong>
                <span>
                  {label(item.source)} · {item.mode === "ai" ? "AI" : "Human"}
                </span>
                {item.opted_out && <small>Opted out</small>}
              </button>
            ))}
          </aside>
          <section className="channel-conversation">
            <header>
              <h3>{thread.name}</h3>
              <Badge value={label(thread.source)} />
              <Badge value={thread.mode === "ai" ? "AI mode" : "Human mode"} />
              <Button onClick={() => onViewLead(thread.name)}>
                View CRM lead
              </Button>
            </header>
            <p>
              {label(thread.lead_status)} ·{" "}
              {thread.score === null
                ? "Not scored"
                : `${thread.score}/100 rubric points`}
            </p>
            <p>{thread.summary}</p>
            {thread.opted_out && (
              <ErrorBox message="This contact opted out. Messaging and AI resumption are blocked." />
            )}
            <div className="channel-actions">
              <label>
                Control reason
                <Input
                  aria-label="Control reason"
                  value={reason}
                  maxLength={300}
                  onChange={(event) => setReason(event.target.value)}
                  placeholder="Reason for changing mode"
                />
              </label>
              <Button
                disabled={
                  reason.trim().length < 3 ||
                  mutation.isPending ||
                  thread.opted_out
                }
                onClick={() =>
                  mutation.mutate({
                    path: "control",
                    body: {
                      mode: thread.mode === "ai" ? "human" : "ai",
                      reason,
                    },
                  })
                }
              >
                {thread.mode === "ai" ? "Take over" : "Resume AI"}
              </Button>
            </div>
            {mutation.error && <ErrorBox message={mutation.error.message} />}
            {messages.error && <ErrorBox message={messages.error.message} />}
            <div className="channel-message-list" aria-label="Message history">
              {messages.isPending ? (
                <Loading />
              ) : (
                messages.data?.map((message) => (
                  <article
                    className={`channel-message ${message.direction}`}
                    key={message.id}
                  >
                    <small>
                      {message.direction === "inbound"
                        ? "Customer"
                        : message.direction === "system"
                          ? "Control"
                          : message.ai_generated
                            ? "Automated assistant"
                            : "Sales team"}{" "}
                      · {new Date(message.created_at).toLocaleString()}
                    </small>
                    <p>{message.text}</p>
                    <small>
                      {message.status}
                      {message.error ? ` · ${message.error}` : ""}
                    </small>
                  </article>
                ))
              )}
            </div>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                mutation.mutate({
                  path: "messages",
                  body: { text, request_id: receipt },
                });
              }}
            >
              <label>
                Manual reply
                <Textarea
                  aria-label="Manual reply"
                  value={text}
                  maxLength={4000}
                  onChange={(event) => {
                    setText(event.target.value);
                    setReceipt(crypto.randomUUID());
                  }}
                  disabled={!thread.can_send}
                  placeholder={
                    thread.can_send
                      ? "Reply as a human…"
                      : "Reply unavailable: channel, opt-out, or 24-hour window restriction"
                  }
                />
              </label>
              <p>
                A manual reply takes over the conversation and cancels queued AI
                replies.
              </p>
              <Button
                variant="primary"
                disabled={
                  !thread.can_send || !text.trim() || mutation.isPending
                }
              >
                <Send size={14} />
                Queue manual reply
              </Button>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
