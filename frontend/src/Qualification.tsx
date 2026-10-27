import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUp,
  Check,
  MessageSquare,
  Plus,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  Trash2,
} from "lucide-react";
import { allLeads, api, label } from "./api";
import type { AISettings, Lead } from "./api";
import { Playground } from "./AI";
import {
  Badge,
  Button,
  Empty,
  ErrorBox,
  Input,
  Loading,
  Select,
  Tabs,
  Textarea,
} from "./components/ui";

type Criterion = {
  key: string;
  question: string;
  kind: "text" | "number";
  required: boolean;
  weight: number;
  operator: "present" | "one_of" | "minimum";
  choices: string[];
  minimum: number | null;
  disqualify_on_mismatch: boolean;
  handoff_on_match: boolean;
};
type Rules = {
  criteria: Criterion[];
  qualified_threshold: number;
  review_threshold: number;
  confidence_threshold: number;
  handoff_when_qualified: boolean;
};
type Draft = Rules & { name: string; activate: boolean };
type Template = {
  id: string;
  version: number;
  name: string;
  active: boolean;
  rules: Rules;
};
type Templates = {
  items: Template[];
  examples: Record<string, Draft>;
  can_manage: boolean;
};
type Collected = Record<
  string,
  {
    value: string | number;
    evidence: string;
    confidence: number;
    message_id: string;
  }
>;
type Assessment = {
  score: number;
  decision: string;
  explanation: string;
  missing_fields: string[];
  exclusion_reasons: string[];
  next_action: string;
  template_version: number;
  evaluated_at: string;
  summary: string;
  breakdown: {
    key: string;
    points: number;
    weight: number;
    matched: boolean;
    reason: string;
  }[];
};
type Citation = { source_id: string; title: string; quote: string };
type Plan = {
  state: string;
  mode: string;
  reply: string | null;
  assessment: Assessment;
  citations: Citation[];
  model: { provider: string; model: string; latency_ms: number } | null;
};
type Trace = {
  conversation: null | {
    id: string;
    state: string;
    mode: string;
    opted_out: boolean;
    fields: Collected;
    assessment: Assessment;
  };
  events: {
    id: string;
    kind: string;
    actor_id: string | null;
    created_at: string;
    payload: {
      text?: string;
      timestamp?: string;
      reason?: string;
      action?: string;
      plan?: Plan;
    };
  }[];
};
type Knowledge = { id: string; title: string; text: string; approved: boolean };

export function Qualification({
  base,
  onSettings,
  onLead,
}: {
  base: string;
  onSettings: () => void;
  onLead: (lead: Lead) => void;
}) {
  const [tab, setTab] = useState("simulator");
  const templates = useQuery({
    queryKey: ["qualification-templates", base],
    queryFn: () => api<Templates>(`${base}/qualification/templates`),
  });
  return (
    <>
      <div className="page-title">
        <div>
          <span className="eyebrow">BUSINESS-AWARE QUALIFICATION</span>
          <h1>Turn conversations into clarity.</h1>
          <p>
            Collect the facts. Understand the fit. Keep your team in control.
          </p>
        </div>
        <span className="outline-pill">
          <ShieldCheck size={15} /> No external messages
        </span>
      </div>
      <Tabs
        label="Qualification views"
        value={tab}
        onChange={setTab}
        items={[
          { value: "simulator", label: "Conversation simulator" },
          { value: "rules", label: "Qualification rules" },
          { value: "sources", label: "Business sources" },
          { value: "playground", label: "Text playground" },
        ]}
      />
      {templates.error && <ErrorBox message={templates.error.message} />}
      {tab === "simulator" && (
        <Simulator
          base={base}
          templates={templates.data}
          onSettings={onSettings}
          onRules={() => setTab("rules")}
          onLead={onLead}
        />
      )}
      {tab === "rules" &&
        (templates.isPending ? (
          <Loading />
        ) : (
          templates.data && <RuleEditor base={base} data={templates.data} />
        ))}
      {tab === "sources" && (
        <Sources base={base} canManage={templates.data?.can_manage ?? false} />
      )}
      {tab === "playground" && (
        <Playground base={base} onSettings={onSettings} />
      )}
    </>
  );
}

function Simulator({
  base,
  templates,
  onSettings,
  onRules,
  onLead,
}: {
  base: string;
  templates?: Templates;
  onSettings: () => void;
  onRules: () => void;
  onLead: (lead: Lead) => void;
}) {
  const client = useQueryClient();
  const [leadId, setLeadId] = useState("");
  const settings = useQuery({
    queryKey: ["ai", base],
    queryFn: () => api<AISettings>(`${base}/ai/settings`),
  });
  const leads = useQuery({
    queryKey: ["leads", base, "qualification"],
    queryFn: () => allLeads(base),
  });
  const create = useMutation({
    mutationFn: () =>
      api<Lead>(`${base}/leads`, {
        method: "POST",
        body: JSON.stringify({
          name: "Simulator prospect",
          title: "Fictional qualification exercise",
          source: "manual",
        }),
      }),
    onSuccess: (lead) => {
      setLeadId(lead.id);
      void client.invalidateQueries({ queryKey: ["leads", base] });
      void client.invalidateQueries({ queryKey: ["overview", base] });
    },
  });
  const active = templates?.items.find((t) => t.active);
  const lead = leads.data?.find((l) => l.id === leadId);
  return (
    <>
      <div className="qualification-context">
        <div>
          <span className="eyebrow">WORKSPACE MODEL</span>
          <strong>{settings.data?.active?.model || "No model selected"}</strong>
          <span className="muted">
            {settings.data?.active?.provider || "Choose a model in Settings"}
          </span>
        </div>
        <Button onClick={onSettings}>
          <Settings2 size={15} /> Model settings
        </Button>
      </div>
      {settings.error && <ErrorBox message={settings.error.message} />}
      {!active && (
        <div className="setup-banner">
          <Sparkles size={18} />
          <span>Activate a qualification template to begin.</span>
          <Button onClick={onRules}>Configure rules</Button>
        </div>
      )}
      <div className="qualification-selector">
        <label>
          CRM lead
          <Select
            aria-label="CRM lead"
            value={leadId}
            onChange={(e) => setLeadId(e.target.value)}
          >
            <option value="">Select a lead…</option>
            {leads.data?.map((l) => (
              <option value={l.id} key={l.id}>
                {l.name} · {l.title || l.company || "Lead"}
              </option>
            ))}
          </Select>
        </label>
        <Button onClick={() => create.mutate()} disabled={create.isPending}>
          <Plus size={15} /> Create fictional sample lead
        </Button>
        {lead && <Button onClick={() => onLead(lead)}>View CRM lead</Button>}
      </div>
      {(create.error || leads.error) && (
        <ErrorBox message={(create.error || leads.error)!.message} />
      )}
      <p className="field-hint">
        Simulator messages update the selected CRM lead. No WhatsApp or other
        external messages are sent. New conversations use{" "}
        {active ? `${active.name}, v${active.version}` : "the active template"};
        existing conversations retain their original rules.
      </p>
      {leadId ? (
        <Conversation
          key={`${base}-${leadId}`}
          base={base}
          leadId={leadId}
          canSend={!!active && !!settings.data?.active}
        />
      ) : (
        <Empty
          title="Start with a conversation"
          text="Select a CRM lead or create a fictional sample. Your transcript, evidence and score will be saved together."
        />
      )}
    </>
  );
}

function useTrace(base: string, leadId: string) {
  return useQuery({
    queryKey: ["qualification", base, leadId],
    queryFn: () => api<Trace>(`${base}/leads/${leadId}/qualification`),
  });
}

function Conversation({
  base,
  leadId,
  canSend,
}: {
  base: string;
  leadId: string;
  canSend: boolean;
}) {
  const trace = useTrace(base, leadId);
  const client = useQueryClient();
  const [text, setText] = useState("");
  const [receipt, setReceipt] = useState({
    id: crypto.randomUUID(),
    timestamp: new Date().toISOString(),
  });
  const send = useMutation({
    mutationFn: () =>
      api<Plan>(`${base}/qualification/simulate`, {
        method: "POST",
        body: JSON.stringify({
          lead_id: leadId,
          text,
          external_message_id: receipt.id,
          timestamp: receipt.timestamp,
        }),
      }),
    onSuccess: () => {
      setText("");
      setReceipt({
        id: crypto.randomUUID(),
        timestamp: new Date().toISOString(),
      });
      void client.invalidateQueries({
        queryKey: ["qualification", base, leadId],
      });
      void client.invalidateQueries({ queryKey: ["leads", base] });
      void client.invalidateQueries({ queryKey: ["lead", base, leadId] });
      void client.invalidateQueries({ queryKey: ["overview", base] });
    },
  });
  if (trace.isPending) return <Loading />;
  if (trace.error) return <ErrorBox message={trace.error.message} />;
  const conversation = trace.data.conversation;
  return (
    <div className="qualification-grid">
      <section className="qualification-chat">
        <div className="qualification-chat-heading">
          <MessageSquare size={17} />
          <h2>Conversation</h2>
          <span className="outline-pill">Simulator</span>
        </div>
        <div className="qualification-transcript" aria-live="polite">
          {!trace.data.events.length && (
            <Empty
              title="The first hello"
              text="Type as your prospective customer. Each turn uses the saved workspace model and real qualification services."
            />
          )}
          {trace.data.events.map((e) =>
            e.kind === "message" ? (
              <div key={e.id} className="qualification-turn">
                <div className="prompt-message">
                  <span className="message-label">
                    PROSPECT ·{" "}
                    {new Date(
                      e.payload.timestamp || e.created_at,
                    ).toLocaleTimeString()}
                  </span>
                  <p>{e.payload.text}</p>
                </div>
                {e.payload.plan?.reply ? (
                  <div className="response-message">
                    <span className="message-label">
                      <Sparkles size={14} /> EASYCRM AI
                    </span>
                    <p>{e.payload.plan.reply}</p>
                    {e.payload.plan.citations.map((c, index) => (
                      <blockquote key={`${c.source_id}-${index}`}>
                        <strong>{c.title}</strong>
                        <p>{c.quote}</p>
                        <small>Source {c.source_id}</small>
                      </blockquote>
                    ))}
                    {e.payload.plan.model && (
                      <small className="muted">
                        {e.payload.plan.model.provider} /{" "}
                        {e.payload.plan.model.model} ·{" "}
                        {e.payload.plan.model.latency_ms} ms
                      </small>
                    )}
                  </div>
                ) : (
                  <p className="qualification-audit">
                    Message saved · AI did not reply
                  </p>
                )}
              </div>
            ) : (
              <p className="qualification-audit" key={e.id}>
                Human {e.payload.action} · {e.payload.reason}
              </p>
            ),
          )}
          {send.isPending && (
            <div role="status" className="ai-thinking">
              <Sparkles size={17} /> Processing qualification…
            </div>
          )}
        </div>
        <form
          className="qualification-composer"
          onSubmit={(e) => {
            e.preventDefault();
            if (text.trim() && !send.isPending) send.mutate();
          }}
        >
          <label htmlFor="prospect-message">Prospect message</label>
          <Textarea
            id="prospect-message"
            maxLength={4000}
            rows={3}
            value={text}
            disabled={send.isPending}
            placeholder="I’m looking for…"
            onChange={(e) => {
              setText(e.target.value);
              send.reset();
              setReceipt({
                id: crypto.randomUUID(),
                timestamp: new Date().toISOString(),
              });
            }}
          />
          {send.error && <ErrorBox message={send.error.message} />}
          <div>
            <span className="field-hint">
              {conversation?.mode === "human"
                ? "Human control · messages are recorded without inference."
                : "One provider call per turn. Manual retry only."}
            </span>
            <Button
              type="submit"
              variant="primary"
              disabled={
                !text.trim() ||
                send.isPending ||
                (!canSend && conversation?.mode !== "human")
              }
            >
              <Send size={15} />{" "}
              {send.isPending
                ? "Processing…"
                : send.error
                  ? "Retry message"
                  : "Send simulator message"}
            </Button>
          </div>
        </form>
      </section>
      <aside className="qualification-results">
        <AssessmentView trace={trace.data} />
        <HumanControl base={base} leadId={leadId} trace={trace.data} />
      </aside>
    </div>
  );
}

function AssessmentView({ trace }: { trace: Trace }) {
  const c = trace.conversation;
  if (!c?.assessment?.evaluated_at)
    return (
      <Empty
        title="Every point has a reason"
        text="Your deterministic score, collected facts and missing information will appear here."
      />
    );
  const a = c.assessment;
  return (
    <>
      <div className="qualification-score">
        <span className="eyebrow">RUBRIC SCORE · V{a.template_version}</span>
        <div>
          <strong>{a.score}</strong>
          <span>/ 100</span>
          <Badge value={c.state.replaceAll("_", "-")} />
        </div>
        <p>{a.explanation}</p>
        <small>{new Date(a.evaluated_at).toLocaleString()}</small>
      </div>
      <h3>Score breakdown</h3>
      <div className="qualification-breakdown">
        {a.breakdown.map((row) => (
          <div key={row.key}>
            <span>
              {label(row.key.replaceAll("_", " "))}
              <small>{row.reason}</small>
            </span>
            <strong>
              {row.points} / {row.weight}
            </strong>
            <progress
              value={row.points}
              max={row.weight || 1}
              aria-label={`${row.key} points`}
            />
          </div>
        ))}
      </div>
      <h3>Collected facts</h3>
      {Object.keys(c.fields).length ? (
        <dl className="qualification-fields">
          {Object.entries(c.fields).map(([key, f]) => (
            <div key={key}>
              <dt>{label(key.replaceAll("_", " "))}</dt>
              <dd>
                <strong>{String(f.value)}</strong>
                <q>{f.evidence}</q>
                <small>
                  {Math.round(f.confidence * 100)}% extraction confidence ·
                  message {f.message_id}
                </small>
              </dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="muted">No supported facts collected.</p>
      )}
      <h3>Next action</h3>
      <p>{a.next_action}</p>
      {a.missing_fields.length > 0 && (
        <p className="field-hint">Missing: {a.missing_fields.join(", ")}</p>
      )}
      {a.exclusion_reasons.map((reason) => (
        <p key={reason} className="error-box">
          {reason}
        </p>
      ))}
      <p className="field-hint">
        A rubric score, not a purchase probability. Pipeline stages are managed
        separately.
      </p>
    </>
  );
}

function HumanControl({
  base,
  leadId,
  trace,
}: {
  base: string;
  leadId: string;
  trace: Trace;
}) {
  const client = useQueryClient();
  const [reason, setReason] = useState("");
  const [override, setOverride] = useState("needs_human");
  const control = useMutation({
    mutationFn: (action: string) =>
      api(`${base}/leads/${leadId}/qualification/control`, {
        method: "POST",
        body: JSON.stringify({
          action,
          reason,
          ...(action === "override" ? { state: override } : {}),
        }),
      }),
    onSuccess: () => {
      setReason("");
      void client.invalidateQueries({
        queryKey: ["qualification", base, leadId],
      });
      void client.invalidateQueries({ queryKey: ["leads", base] });
      void client.invalidateQueries({ queryKey: ["lead", base, leadId] });
      void client.invalidateQueries({ queryKey: ["overview", base] });
    },
  });
  const c = trace.conversation;
  if (!c) return null;
  const terminal = c.opted_out || ["closed", "disqualified"].includes(c.state);
  return (
    <section className="qualification-control">
      <h3>{c.mode === "human" ? "Human control" : "AI control"}</h3>
      <p className="field-hint">
        {terminal
          ? "Conversation is closed or disqualified. AI resumption is blocked."
          : "A team member can pause AI or resume it after review."}
      </p>
      <label>
        Reason for control change
        <Input
          maxLength={500}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Record why…"
        />
      </label>
      <div className="qualification-actions">
        <Button
          disabled={!reason.trim() || control.isPending || terminal}
          onClick={() =>
            control.mutate(c.mode === "ai" ? "takeover" : "resume")
          }
        >
          {c.mode === "ai" ? "Take over" : "Resume AI"}
        </Button>
        <Button
          disabled={!reason.trim() || control.isPending || c.state === "closed"}
          onClick={() => control.mutate("close")}
        >
          Close conversation
        </Button>
      </div>
      <label>
        Human decision
        <Select
          aria-label="Human decision"
          value={override}
          onChange={(e) => setOverride(e.target.value)}
        >
          {[
            "qualifying",
            "qualified",
            "needs_human",
            "disqualified",
            "closed",
          ].map((s) => (
            <option key={s} value={s}>
              {label(s.replaceAll("_", "-"))}
            </option>
          ))}
        </Select>
      </label>
      <Button
        disabled={!reason.trim() || control.isPending || terminal}
        onClick={() => control.mutate("override")}
      >
        Record human override
      </Button>
      {control.error && <ErrorBox message={control.error.message} />}
    </section>
  );
}

export function LeadQualificationPanel({
  base,
  leadId,
}: {
  base: string;
  leadId: string;
}) {
  const trace = useTrace(base, leadId);
  if (trace.isPending) return <Loading />;
  if (trace.error) return <ErrorBox message={trace.error.message} />;
  return (
    <section className="lead-qualification">
      <h3>Qualification & evidence</h3>
      {trace.data.conversation ? (
        <>
          <AssessmentView trace={trace.data} />
          <HumanControl base={base} leadId={leadId} trace={trace.data} />
          <details>
            <summary>
              Qualification timeline · {trace.data.events.length} events
            </summary>
            {trace.data.events.map((e) => (
              <div className="qualification-timeline-event" key={e.id}>
                <small>
                  {new Date(e.created_at).toLocaleString()} · {e.kind} ·{" "}
                  {e.actor_id ? "Workspace member" : "Channel adapter"}
                </small>
                <p>{e.payload.text || e.payload.reason}</p>
                {e.payload.plan && (
                  <>
                    <p>{e.payload.plan.reply || "AI paused"}</p>
                    <p>
                      {e.payload.plan.state} · {e.payload.plan.assessment.score}
                      /100 · rules v{e.payload.plan.assessment.template_version}
                    </p>
                    {e.payload.plan.citations.map((source, i) => (
                      <blockquote key={i}>
                        {source.title}: {source.quote}
                      </blockquote>
                    ))}
                  </>
                )}
              </div>
            ))}
          </details>
        </>
      ) : (
        <p className="muted">
          No qualification conversation yet. Start one in AI Qualification.
        </p>
      )}
    </section>
  );
}

function RuleEditor({ base, data }: { base: string; data: Templates }) {
  const client = useQueryClient();
  const [draft, setDraft] = useState<Draft>(() => {
    const active = data.items.find((t) => t.active);
    return active
      ? { name: active.name, ...active.rules, activate: true }
      : structuredClone(data.examples.generic_b2b);
  });
  const [notice, setNotice] = useState("");
  const update = (index: number, patch: Partial<Criterion>) =>
    setDraft((d) => ({
      ...d,
      criteria: d.criteria.map((c, i) =>
        i === index ? { ...c, ...patch } : c,
      ),
    }));
  const save = useMutation({
    mutationFn: () =>
      api<Template>(`${base}/qualification/templates`, {
        method: "POST",
        body: JSON.stringify(draft),
      }),
    onSuccess: (t) => {
      setNotice(
        `Saved ${t.name}, version ${t.version}${t.active ? " · active for new conversations" : " · inactive"}`,
      );
      void client.invalidateQueries({
        queryKey: ["qualification-templates", base],
      });
    },
  });
  const activate = useMutation({
    mutationFn: (id: string) =>
      api(`${base}/qualification/templates/${id}/activate`, { method: "POST" }),
    onSuccess: () => {
      void client.invalidateQueries({
        queryKey: ["qualification-templates", base],
      });
      setNotice("Template activated for new conversations");
    },
  });
  const weight = draft.criteria.reduce((sum, c) => sum + c.weight, 0);
  return (
    <div className="qualification-rules">
      <div className="qualification-section-heading">
        <div>
          <h2>Your business, your criteria.</h2>
          <p>
            Every save creates an immutable rule version. Required facts must be
            complete before a lead qualifies.
          </p>
        </div>
        <span className="outline-pill">
          {data.can_manage ? "Admin editor" : "Read only"}
        </span>
      </div>
      <div className="qualification-actions">
        {Object.entries(data.examples).map(([key, example]) => (
          <Button
            key={key}
            disabled={!data.can_manage}
            onClick={() => {
              setDraft(structuredClone(example));
              setNotice("Example loaded for editing. Save to persist it.");
            }}
          >
            Use{" "}
            {key === "furniture" ? "furniture example" : "generic B2B example"}
          </Button>
        ))}
      </div>
      {!!data.items.length && (
        <label>
          Saved rule versions
          <Select
            defaultValue=""
            onChange={(e) => {
              const t = data.items.find((t) => t.id === e.target.value);
              if (t) setDraft({ name: t.name, ...t.rules, activate: true });
            }}
          >
            <option value="">Load a version to edit…</option>
            {data.items.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} · v{t.version}
                {t.active ? " · active" : ""}
              </option>
            ))}
          </Select>
        </label>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <fieldset disabled={!data.can_manage || save.isPending}>
          <label>
            Template name
            <Input
              required
              maxLength={100}
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            />
          </label>
          <div className="qualification-thresholds">
            <label>
              Qualified threshold
              <Input
                type="number"
                min={1}
                max={100}
                required
                value={draft.qualified_threshold}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    qualified_threshold: Number(e.target.value),
                  })
                }
              />
            </label>
            <label>
              Human review threshold
              <Input
                type="number"
                min={0}
                max={draft.qualified_threshold - 1}
                required
                value={draft.review_threshold}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    review_threshold: Number(e.target.value),
                  })
                }
              />
            </label>
            <label>
              Minimum extraction confidence
              <Input
                type="number"
                min={0.5}
                max={1}
                step={0.05}
                required
                value={draft.confidence_threshold}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    confidence_threshold: Number(e.target.value),
                  })
                }
              />
            </label>
          </div>
          <p className="field-hint">
            Points total 100. Missing required facts keep a lead qualifying.
            Once complete: score at or above the qualified threshold qualifies;
            the review band needs a human; below the review threshold
            disqualifies. Explicit disqualifiers and handoff rules take
            priority.
          </p>
          {draft.criteria.map((c, i) => (
            <div className="qualification-criterion" key={i}>
              <div className="qualification-section-heading">
                <strong>Field {i + 1}</strong>
                <div className="qualification-actions">
                  <Button
                    type="button"
                    disabled={!i}
                    aria-label={`Move field ${i + 1} up`}
                    onClick={() =>
                      setDraft((d) => {
                        const criteria = [...d.criteria];
                        [criteria[i - 1], criteria[i]] = [
                          criteria[i],
                          criteria[i - 1],
                        ];
                        return { ...d, criteria };
                      })
                    }
                  >
                    <ArrowUp size={14} />
                  </Button>
                  <Button
                    type="button"
                    disabled={draft.criteria.length === 1}
                    aria-label={`Remove field ${i + 1}`}
                    onClick={() =>
                      setDraft({
                        ...draft,
                        criteria: draft.criteria.filter((_, j) => i !== j),
                      })
                    }
                  >
                    <Trash2 size={14} />
                  </Button>
                </div>
              </div>
              <div className="qualification-thresholds">
                <label>
                  Field key
                  <Input
                    required
                    pattern="[a-z][a-z0-9_]{0,39}"
                    value={c.key}
                    onChange={(e) => update(i, { key: e.target.value })}
                  />
                </label>
                <label>
                  Value type
                  <Select
                    value={c.kind}
                    onChange={(e) =>
                      update(i, {
                        kind: e.target.value as Criterion["kind"],
                        operator: "present",
                        choices: [],
                        minimum: null,
                      })
                    }
                  >
                    <option value="text">Text</option>
                    <option value="number">Number</option>
                  </Select>
                </label>
                <label>
                  Points
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    required
                    value={c.weight}
                    onChange={(e) =>
                      update(i, { weight: Number(e.target.value) })
                    }
                  />
                </label>
              </div>
              <label>
                Question
                <Input
                  required
                  maxLength={250}
                  value={c.question}
                  onChange={(e) => update(i, { question: e.target.value })}
                />
              </label>
              <div className="qualification-thresholds">
                <label>
                  Match rule
                  <Select
                    value={c.operator}
                    onChange={(e) =>
                      update(i, {
                        operator: e.target.value as Criterion["operator"],
                      })
                    }
                  >
                    <option value="present">Value is provided</option>
                    {c.kind === "text" ? (
                      <option value="one_of">One of these exact values</option>
                    ) : (
                      <option value="minimum">At least a minimum</option>
                    )}
                  </Select>
                </label>
                {c.operator === "one_of" && (
                  <label>
                    Accepted values (comma separated)
                    <Input
                      required
                      value={c.choices.join(",")}
                      onChange={(e) =>
                        update(i, { choices: e.target.value.split(",") })
                      }
                    />
                  </label>
                )}
                {c.operator === "minimum" && (
                  <label>
                    Minimum value
                    <Input
                      type="number"
                      min={0}
                      step="any"
                      required
                      value={c.minimum ?? ""}
                      onChange={(e) =>
                        update(i, { minimum: Number(e.target.value) })
                      }
                    />
                  </label>
                )}
              </div>
              <div className="qualification-checkboxes">
                <label>
                  <input
                    type="checkbox"
                    checked={c.required}
                    onChange={(e) => update(i, { required: e.target.checked })}
                  />{" "}
                  Required
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={c.disqualify_on_mismatch}
                    onChange={(e) =>
                      update(i, { disqualify_on_mismatch: e.target.checked })
                    }
                  />{" "}
                  Disqualify on mismatch
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={c.handoff_on_match}
                    onChange={(e) =>
                      update(i, { handoff_on_match: e.target.checked })
                    }
                  />{" "}
                  Human review on match
                </label>
              </div>
            </div>
          ))}
          <div className="qualification-actions">
            <Button
              type="button"
              disabled={draft.criteria.length >= 15}
              onClick={() =>
                setDraft({
                  ...draft,
                  criteria: [
                    ...draft.criteria,
                    {
                      key: `field_${draft.criteria.length + 1}`,
                      question: "What else should we know?",
                      kind: "text",
                      required: false,
                      weight: 0,
                      operator: "present",
                      choices: [],
                      minimum: null,
                      disqualify_on_mismatch: false,
                      handoff_on_match: false,
                    },
                  ],
                })
              }
            >
              <Plus size={15} /> Add field
            </Button>
            <strong
              className={weight === 100 ? "muted" : "qualification-invalid"}
            >
              {weight} / 100 points
            </strong>
          </div>
          <div className="qualification-checkboxes">
            <label>
              <input
                type="checkbox"
                checked={draft.handoff_when_qualified}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    handoff_when_qualified: e.target.checked,
                  })
                }
              />{" "}
              Pause AI when qualified
            </label>
            <label>
              <input
                type="checkbox"
                checked={draft.activate}
                onChange={(e) =>
                  setDraft({ ...draft, activate: e.target.checked })
                }
              />{" "}
              Activate for new conversations
            </label>
          </div>
          <Button type="submit" variant="primary" disabled={weight !== 100}>
            <Check size={15} />{" "}
            {save.isPending ? "Saving…" : "Save new rule version"}
          </Button>
        </fieldset>
      </form>
      {(save.error || activate.error) && (
        <ErrorBox message={(save.error || activate.error)!.message} />
      )}
      {notice && (
        <p role="status" className="success-box">
          {notice}
        </p>
      )}
      <h3>Version history</h3>
      {data.items.map((t) => (
        <div className="qualification-version" key={t.id}>
          <span>
            {t.name} · v{t.version}
          </span>
          {t.active ? (
            <span className="active-pill">Active</span>
          ) : (
            <Button
              disabled={!data.can_manage || activate.isPending}
              onClick={() => activate.mutate(t.id)}
            >
              Activate v{t.version}
            </Button>
          )}
        </div>
      ))}
    </div>
  );
}

function Sources({ base, canManage }: { base: string; canManage: boolean }) {
  const client = useQueryClient();
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [approved, setApproved] = useState(false);
  const sources = useQuery({
    queryKey: ["qualification-sources", base],
    queryFn: () => api<Knowledge[]>(`${base}/qualification/knowledge`),
  });
  const save = useMutation({
    mutationFn: () =>
      api(`${base}/qualification/knowledge`, {
        method: "POST",
        body: JSON.stringify({ title, text, approved }),
      }),
    onSuccess: () => {
      setTitle("");
      setText("");
      setApproved(false);
      void client.invalidateQueries({
        queryKey: ["qualification-sources", base],
      });
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) =>
      api(`${base}/qualification/knowledge/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      void client.invalidateQueries({
        queryKey: ["qualification-sources", base],
      });
    },
  });
  return (
    <div className="qualification-rules">
      <h2>Reviewed business sources</h2>
      <p>
        Add verified business text for grounded simulator answers. Only
        explicitly approved sources are retrieved. Import website pages and PDFs
        in Knowledge Base, then review and approve the extracted text there.
      </p>
      {canManage && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <label>
            Source title
            <Input
              required
              maxLength={150}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Furniture delivery policy"
            />
          </label>
          <label>
            Verified source text
            <Textarea
              required
              maxLength={12000}
              rows={6}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </label>
          <div className="qualification-checkboxes">
            <label>
              <input
                type="checkbox"
                checked={approved}
                onChange={(e) => setApproved(e.target.checked)}
              />{" "}
              I have reviewed this text and approve it for AI retrieval
            </label>
          </div>
          <Button type="submit" variant="primary" disabled={save.isPending}>
            Add business source
          </Button>
        </form>
      )}
      {(sources.error || save.error || remove.error) && (
        <ErrorBox
          message={(sources.error || save.error || remove.error)!.message}
        />
      )}
      {sources.isPending ? (
        <Loading />
      ) : !sources.data?.length ? (
        <Empty
          title="Build on verified information"
          text="No business sources yet. Unsupported product or policy questions go to human review."
        />
      ) : (
        sources.data.map((s) => (
          <article className="qualification-source" key={s.id}>
            <div className="qualification-section-heading">
              <h3>{s.title}</h3>
              <span className="outline-pill">
                {s.approved ? "Approved" : "Excluded from retrieval"}
              </span>
            </div>
            <p>{s.text}</p>
            {canManage && (
              <Button
                variant="ghost"
                disabled={remove.isPending}
                onClick={() => remove.mutate(s.id)}
              >
                <Trash2 size={14} /> Remove from retrieval
              </Button>
            )}
          </article>
        ))
      )}
    </div>
  );
}
