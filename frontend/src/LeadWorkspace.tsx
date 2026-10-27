import { Input, Select, Textarea, Card, Table } from "./components/ui";
import { useEffect, useState } from "react";
import { LeadQualificationPanel } from "./Qualification";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowUpRight,
  Building2,
  Check,
  ChevronDown,
  Columns3,
  GripVertical,
  List,
  Mail,
  MessageCircle,
  MoreHorizontal,
  Plus,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { allLeads, api, label, money, sources, statuses } from "./api";
import type { Lead, Note, Stage, Overview } from "./api";
import {
  Avatar,
  Badge,
  Button,
  Empty,
  ErrorBox,
  Loading,
  Modal,
  SectionHeading,
} from "./components/ui";

type Props = {
  base: string;
  stages: Stage[];
  notify: (s: string) => void;
  page: string;
  initialSearch?: string;
};
export function LeadWorkspace({
  base,
  stages,
  notify,
  page,
  initialSearch = "",
}: Props) {
  const client = useQueryClient();
  const [view, setView] = useState(page === "Leads" ? "list" : "board");
  const [search, setSearch] = useState(initialSearch);
  const [source, setSource] = useState("");
  const [status, setStatus] = useState("");
  const [stage, setStage] = useState("");
  const [newStage, setNewStage] = useState("");
  const [filters, setFilters] = useState(false);
  const [editing, setEditing] = useState<Lead | "new" | null>(null);
  const [dragged, setDragged] = useState<string | null>(null);
  const [over, setOver] = useState<string | null>(null);
  const query = new URLSearchParams({
    q: search,
    ...(source && { source }),
    ...(status && { status }),
    ...(stage && { stage_id: stage }),
  });
  const leads = useQuery({
    queryKey: ["leads", base, query.toString()],
    queryFn: () => allLeads(base, query.toString()),
  });
  const refresh = () => {
    void client.invalidateQueries({ queryKey: ["leads", base] });
    void client.invalidateQueries({ queryKey: ["overview", base] });
  };
  const move = useMutation({
    mutationFn: ({ id, stage_id }: { id: string; stage_id: string }) =>
      api(`${base}/leads/${id}/stage`, {
        method: "POST",
        body: JSON.stringify({ stage_id }),
      }),
    onSuccess: () => {
      refresh();
      notify("Pipeline stage updated");
    },
  });
  const reset = () => {
    setSearch("");
    setSource("");
    setStatus("");
    setStage("");
  };
  const add = (stageId = "") => {
    setNewStage(stageId);
    setEditing("new");
  };
  return (
    <>
      <div className="pipeline-toolbar">
        <div className="filters">
          <div className="search-field">
            <Search size={16} />
            <Input
              aria-label="Search leads"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search leads or companies…"
            />
            {search && (
              <button
                aria-label="Clear search"
                className="icon-button"
                onClick={() => setSearch("")}
              >
                <X size={14} />
              </button>
            )}
          </div>
          <label className="select-filter">
            <span className="sr-only">Filter by source</span>
            <Select value={source} onChange={(e) => setSource(e.target.value)}>
              <option value="">All sources</option>
              {sources.map((s) => (
                <option key={s} value={s}>
                  {label(s)}
                </option>
              ))}
            </Select>
            <ChevronDown size={13} />
          </label>
          <Button
            className={filters ? "filter-active" : ""}
            onClick={() => setFilters(!filters)}
            aria-expanded={filters}
          >
            <span className="filter-lines">☷</span> Filters
            {(status || stage) && (
              <span className="filter-count">
                {Number(!!status) + Number(!!stage)}
              </span>
            )}
          </Button>
        </div>
        <div className="view-actions">
          <div className="segmented" aria-label="Lead view">
            <button
              aria-pressed={view === "board"}
              className={view === "board" ? "selected" : ""}
              onClick={() => setView("board")}
            >
              <Columns3 size={15} />
              <span>Kanban</span>
            </button>
            <button
              aria-pressed={view === "list"}
              className={view === "list" ? "selected" : ""}
              onClick={() => setView("list")}
            >
              <List size={16} />
              <span>List</span>
            </button>
          </div>
          <Button variant="primary" onClick={() => add()}>
            <Plus size={17} />
            New lead
          </Button>
        </div>
      </div>
      {filters && (
        <div className="expanded-filters">
          <label>
            Status
            <Select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All statuses</option>
              {statuses.map((s) => (
                <option key={s} value={s}>
                  {label(s)}
                </option>
              ))}
            </Select>
          </label>
          <label>
            Pipeline stage
            <Select value={stage} onChange={(e) => setStage(e.target.value)}>
              <option value="">All stages</option>
              {stages.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          </label>
          <label className="mobile-source">
            Source
            <Select value={source} onChange={(e) => setSource(e.target.value)}>
              <option value="">All sources</option>
              {sources.map((s) => (
                <option key={s} value={s}>
                  {label(s)}
                </option>
              ))}
            </Select>
          </label>
          <Button variant="ghost" onClick={reset}>
            Clear filters
          </Button>
        </div>
      )}
      {move.error && <ErrorBox message={move.error.message} />}
      {leads.isPending ? (
        <Loading />
      ) : leads.error ? (
        <ErrorBox
          message={leads.error.message}
          retry={() => void leads.refetch()}
        />
      ) : (
        <>
          <div className="results-line">
            <span>
              {leads.data.length}{" "}
              {search || source || status || stage ? "matching " : ""}leads
              <span className="muted-separator">/</span>
              {view === "board"
                ? "Drag cards to move stages"
                : "Your relationships, at a glance"}
            </span>
            {(search || source || status || stage) && (
              <button className="text-button" onClick={reset}>
                Reset filters
              </button>
            )}
            <span className="workspace-currency">Values in USD</span>
          </div>
          {view === "board" ? (
            <div className="kanban" aria-label="Lead pipeline">
              {stages.map((s) => {
                const rows = leads.data.filter((l) => l.stage_id === s.id);
                return (
                  <section
                    key={s.id}
                    className={`kanban-column ${over === s.id ? "drag-over" : ""}`}
                    onDragOver={(e) => {
                      e.preventDefault();
                      setOver(s.id);
                    }}
                    onDragLeave={(e) => {
                      if (!e.currentTarget.contains(e.relatedTarget as Node))
                        setOver(null);
                    }}
                    onDrop={(e) => {
                      e.preventDefault();
                      const id = e.dataTransfer.getData("text/plain");
                      if (dragged && id === dragged && !move.isPending)
                        move.mutate({ id, stage_id: s.id });
                      setDragged(null);
                      setOver(null);
                    }}
                  >
                    <header className="column-heading">
                      <div>
                        <span
                          className="stage-dot"
                          style={{ background: s.color }}
                        />
                        <h3>{s.name}</h3>
                        <span className="count">{rows.length}</span>
                      </div>
                      <button
                        className="icon-button"
                        aria-label={`Add lead to ${s.name}`}
                        onClick={() => add(s.id)}
                      >
                        <Plus size={16} />
                      </button>
                    </header>
                    <div className="column-value">
                      {money(rows.reduce((sum, l) => sum + Number(l.value), 0))}
                      <span> potential value</span>
                    </div>
                    <div className="column-cards">
                      {rows.map((l) => (
                        <article
                          key={l.id}
                          className={`lead-card ${dragged === l.id ? "dragging" : ""}`}
                          draggable={!move.isPending}
                          onDragStart={(e) => {
                            setDragged(l.id);
                            e.dataTransfer.setData("text/plain", l.id);
                            e.dataTransfer.effectAllowed = "move";
                          }}
                          onDragEnd={() => {
                            setDragged(null);
                            setOver(null);
                          }}
                        >
                          <button
                            className="lead-main"
                            onClick={() => setEditing(l)}
                            aria-label={`Open ${l.company || l.name}`}
                          >
                            <div className="lead-title">
                              <span className="company-icon">
                                <Building2 size={17} />
                              </span>
                              <div>
                                <h4>{l.company || l.name}</h4>
                                <span className="lead-contact">{l.name}</span>
                              </div>
                              <MoreHorizontal size={16} className="lead-more" />
                            </div>
                            <div className="lead-value">
                              {money(l.value)}
                              <span>
                                {new Date(l.created_at).toLocaleDateString(
                                  undefined,
                                  { month: "short", day: "numeric" },
                                )}
                              </span>
                            </div>
                            <p className="lead-summary">
                              {l.summary ||
                                l.title ||
                                "A new opportunity. Add a note to start the conversation."}
                            </p>
                            <Badge value={l.source} />
                            {l.qualification_score != null && (
                              <span className="card-qualification">
                                <Badge value={l.status} />
                                <strong>{l.qualification_score}/100</strong>
                              </span>
                            )}
                          </button>
                          <footer className="lead-footer">
                            <span>
                              <Avatar name={l.name} small />
                              {l.name.split(" ")[0]}
                            </span>
                            <label className="card-stage-select">
                              <span className="sr-only">
                                Stage for {l.company || l.name}
                              </span>
                              <Select
                                value={l.stage_id}
                                disabled={move.isPending}
                                onChange={(e) =>
                                  move.mutate({
                                    id: l.id,
                                    stage_id: e.target.value,
                                  })
                                }
                              >
                                {stages.map((s) => (
                                  <option key={s.id} value={s.id}>
                                    {s.name}
                                  </option>
                                ))}
                              </Select>
                              <GripVertical size={13} />
                            </label>
                          </footer>
                        </article>
                      ))}
                      {!rows.length && (
                        <button
                          className="column-empty"
                          onClick={() => add(s.id)}
                        >
                          <Plus size={17} />
                          Add your first lead
                        </button>
                      )}
                    </div>
                  </section>
                );
              })}
            </div>
          ) : leads.data.length ? (
            <div className="table-wrap">
              <Table>
                <thead>
                  <tr>
                    <th>
                      Lead <ArrowDown size={12} />
                    </th>
                    <th>Company</th>
                    <th>Stage</th>
                    <th>Status</th>
                    <th>Score</th>
                    <th>Source</th>
                    <th className="right">Value</th>
                  </tr>
                </thead>
                <tbody>
                  {leads.data.map((l) => (
                    <tr key={l.id}>
                      <td>
                        <button
                          className="person-link"
                          onClick={() => setEditing(l)}
                        >
                          <Avatar name={l.name} />
                          <span>
                            <strong>{l.name}</strong>
                            <small>{l.email || "No email added"}</small>
                          </span>
                        </button>
                      </td>
                      <td>{l.company || "—"}</td>
                      <td>
                        <label>
                          <span className="sr-only">Stage for {l.name}</span>
                          <Select
                            className="table-select"
                            disabled={move.isPending}
                            value={l.stage_id}
                            onChange={(e) =>
                              move.mutate({
                                id: l.id,
                                stage_id: e.target.value,
                              })
                            }
                          >
                            {stages.map((s) => (
                              <option key={s.id} value={s.id}>
                                {s.name}
                              </option>
                            ))}
                          </Select>
                        </label>
                      </td>
                      <td>
                        <Badge value={l.status} />
                      </td>
                      <td className="tabular">
                        {l.qualification_score == null
                          ? "—"
                          : `${l.qualification_score}/100`}
                      </td>
                      <td>
                        <Badge value={l.source} />
                      </td>
                      <td className="right tabular">{money(l.value)}</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
          ) : (
            <Empty
              title="A fresh start for your pipeline"
              text="Add your first lead, or adjust your filters to find an existing relationship."
            >
              <Button variant="primary" onClick={() => add()}>
                <Plus size={16} />
                Create a lead
              </Button>
            </Empty>
          )}
        </>
      )}
      {editing && (
        <LeadEditor
          key={editing === "new" ? "new" : editing.id}
          base={base}
          lead={editing === "new" ? undefined : editing}
          stages={stages}
          initialStage={newStage}
          onClose={() => setEditing(null)}
          onSaved={(message) => {
            refresh();
            notify(message);
            setEditing(null);
          }}
        />
      )}
    </>
  );
}

function LeadEditor({
  base,
  lead,
  stages,
  initialStage,
  onClose,
  onSaved,
}: {
  base: string;
  lead?: Lead;
  stages: Stage[];
  initialStage: string;
  onClose: () => void;
  onSaved: (s: string) => void;
}) {
  const [form, setForm] = useState({
    name: lead?.name || "",
    company: lead?.company || "",
    email: lead?.email || "",
    phone: lead?.phone || "",
    title: lead?.title || "",
    source: lead?.source || "manual",
    status: lead?.status || "new",
    value: lead?.value || "0",
    summary: lead?.summary || "",
    stage_id: lead?.stage_id || initialStage || stages[0]?.id,
  });
  const [confirm, setConfirm] = useState(false);
  const [note, setNote] = useState("");
  const client = useQueryClient();
  const currentLead = useQuery({
    queryKey: ["lead", base, lead?.id],
    queryFn: () => api<Lead>(`${base}/leads/${lead!.id}`),
    enabled: !!lead,
  });
  useEffect(() => {
    if (currentLead.data)
      setForm((f) => ({
        ...f,
        status: currentLead.data!.status,
        summary: currentLead.data!.summary,
      }));
  }, [currentLead.data?.status, currentLead.data?.summary]);
  const notes = useQuery({
    queryKey: ["notes", base, lead?.id],
    queryFn: () => api<Note[]>(`${base}/leads/${lead!.id}/notes`),
    enabled: !!lead,
  });
  const save = useMutation({
    mutationFn: () =>
      api(`${base}/leads${lead ? "/" + lead.id : ""}`, {
        method: lead ? "PATCH" : "POST",
        body: JSON.stringify(form),
      }),
    onSuccess: () => onSaved(lead ? "Lead updated" : "A new opportunity added"),
  });
  const remove = useMutation({
    mutationFn: () => api(`${base}/leads/${lead!.id}`, { method: "DELETE" }),
    onSuccess: () => onSaved("Lead deleted"),
  });
  const exportSubject = useMutation({
    mutationFn: () => api(`${base}/leads/${lead!.id}/export`),
    onSuccess: (data) => {
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download = `easycrm-subject-${lead!.id}.json`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
  });
  const addNote = useMutation({
    mutationFn: () =>
      api(`${base}/leads/${lead!.id}/notes`, {
        method: "POST",
        body: JSON.stringify({ body: note }),
      }),
    onSuccess: () => {
      setNote("");
      void client.invalidateQueries({ queryKey: ["notes", base, lead?.id] });
    },
  });
  const update = (key: keyof typeof form, value: string) =>
    setForm((f) => ({ ...f, [key]: value }));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate();
  };
  return (
    <Modal
      title={lead ? "Lead details" : "A new opportunity"}
      subtitle={
        lead
          ? "Keep the details and the relationship moving."
          : "Great relationships start with a little context."
      }
      onClose={onClose}
      wide
    >
      {confirm ? (
        <div className="confirm-delete">
          <div className="delete-icon">
            <Trash2 size={24} />
          </div>
          <h3>Delete {lead?.name}?</h3>
          <p>
            This permanently removes the lead, notes, messages and qualification
            history. An admin must pause workspace integrations and drain
            pending intake first. Related intake content is redacted; a deletion
            audit remains.
          </p>
          {remove.error && <ErrorBox message={remove.error.message} />}
          <div className="form-actions">
            <Button onClick={() => setConfirm(false)}>Keep lead</Button>
            <Button
              variant="danger"
              disabled={remove.isPending}
              onClick={() => remove.mutate()}
            >
              {remove.isPending ? "Deleting…" : "Delete lead"}
            </Button>
          </div>
        </div>
      ) : (
        <>
          <form onSubmit={submit}>
            <div className="form-grid">
              <label>
                Full name
                <Input
                  autoFocus
                  required
                  maxLength={100}
                  value={form.name}
                  onChange={(e) => update("name", e.target.value)}
                  placeholder="e.g. Olivia Chen"
                />
              </label>
              <label>
                Company
                <Input
                  maxLength={120}
                  value={form.company}
                  onChange={(e) => update("company", e.target.value)}
                  placeholder="Company name"
                />
              </label>
              <label>
                Email address
                <Input
                  type="email"
                  maxLength={254}
                  value={form.email}
                  onChange={(e) => update("email", e.target.value)}
                  placeholder="name@company.com"
                />
              </label>
              <label>
                Phone number
                <Input
                  type="tel"
                  maxLength={40}
                  value={form.phone}
                  onChange={(e) => update("phone", e.target.value)}
                  placeholder="+1 555 000 0000"
                />
              </label>
              <label className="span-2">
                Opportunity title
                <Input
                  maxLength={200}
                  value={form.title}
                  onChange={(e) => update("title", e.target.value)}
                  placeholder="What are they interested in?"
                />
              </label>
              <label>
                Pipeline stage
                <Select
                  value={form.stage_id}
                  onChange={(e) => update("stage_id", e.target.value)}
                >
                  {stages.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </Select>
              </label>
              <label>
                Qualification status
                <Select
                  aria-label="Qualification status"
                  disabled={currentLead.data?.qualification_score != null}
                  value={form.status}
                  onChange={(e) => update("status", e.target.value)}
                >
                  {statuses.map((s) => (
                    <option key={s} value={s}>
                      {label(s)}
                    </option>
                  ))}
                </Select>
              </label>
              <label>
                Lead source
                <Select
                  value={form.source}
                  onChange={(e) => update("source", e.target.value)}
                >
                  {sources.map((s) => (
                    <option key={s} value={s}>
                      {label(s)}
                    </option>
                  ))}
                </Select>
              </label>
              <label>
                Potential value (USD)
                <Input
                  type="number"
                  min="0"
                  max="999999999999"
                  step="0.01"
                  value={form.value}
                  onChange={(e) => update("value", e.target.value)}
                />
              </label>
              <label className="span-2">
                Summary
                <Textarea
                  maxLength={1000}
                  rows={3}
                  value={form.summary}
                  onChange={(e) => update("summary", e.target.value)}
                  placeholder="A little context for your next conversation…"
                />
              </label>
            </div>
            {save.error && <ErrorBox message={save.error.message} />}
            {exportSubject.error && (
              <ErrorBox message={exportSubject.error.message} />
            )}
            <div className="form-actions">
              {lead && (
                <Button
                  type="button"
                  disabled={exportSubject.isPending}
                  onClick={() => exportSubject.mutate()}
                >
                  Export subject data
                </Button>
              )}
              {lead && (
                <Button
                  type="button"
                  variant="ghost"
                  className="delete-button"
                  onClick={() => setConfirm(true)}
                >
                  <Trash2 size={15} />
                  Delete lead
                </Button>
              )}
              <Button type="button" onClick={onClose}>
                Cancel
              </Button>
              <Button variant="primary" type="submit" disabled={save.isPending}>
                <Check size={16} />
                {save.isPending
                  ? "Saving…"
                  : lead
                    ? "Save changes"
                    : "Create lead"}
              </Button>
            </div>
          </form>
          {lead && <LeadQualificationPanel base={base} leadId={lead.id} />}
          {lead && (
            <section className="notes-section">
              <SectionHeading
                title="Notes"
                right={
                  <span className="muted">A shared memory for your team</span>
                }
              />
              {notes.isPending ? (
                <Loading />
              ) : notes.error ? (
                <ErrorBox message={notes.error.message} />
              ) : (
                <div className="note-list">
                  {notes.data?.map((n) => (
                    <div className="note" key={n.id}>
                      <MessageCircle size={15} />
                      <div>
                        <p>{n.body}</p>
                        <small>{new Date(n.created_at).toLocaleString()}</small>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <form
                className="note-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  addNote.mutate();
                }}
              >
                <label className="sr-only" htmlFor="note">
                  Add a note
                </label>
                <Input
                  id="note"
                  required
                  maxLength={5000}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="Add a note…"
                />
                <Button
                  disabled={addNote.isPending || !note.trim()}
                  type="submit"
                >
                  {addNote.isPending ? "Adding…" : "Add note"}
                </Button>
              </form>
              {addNote.error && <ErrorBox message={addNote.error.message} />}
            </section>
          )}
        </>
      )}
    </Modal>
  );
}

export function DashboardMetrics({ data }: { data: Overview }) {
  const items = [
    {
      label: "Total leads",
      value: data.total_leads,
      icon: Building2,
      foot: "Every relationship in your workspace",
      color: "blue",
      bars: data.pipeline.map((s) => s.count),
    },
    {
      label: "Qualified leads",
      value: data.qualified_leads,
      icon: Check,
      foot: "Ready for the next conversation",
      color: "green",
      bars: data.pipeline.map((s) => s.count),
    },
    {
      label: "Qualification rate",
      value: `${data.qualification_rate}%`,
      icon: ArrowUpRight,
      foot: "Qualified leads / total leads",
      color: "blue",
      bars: data.sources.map((s) => s.count),
    },
    {
      label: "Active leads",
      value: data.active_leads,
      icon: MessageCircle,
      foot: "Excludes closed and disqualified",
      color: "violet",
      bars: data.pipeline.map((s) => s.count),
    },
  ];
  return (
    <div className="metric-grid">
      {items.map((item) => (
        <Card className="metric-card" key={item.label}>
          <div className="metric-label">
            <span className={`metric-icon ${item.color}`}>
              <item.icon size={16} />
            </span>
            {item.label}
          </div>
          <div className="metric-row">
            <strong>{item.value}</strong>
            <div className={`mini-bars ${item.color}`} aria-hidden="true">
              {item.bars.map((n, i) => (
                <span
                  key={i}
                  style={{
                    height: `${n ? 8 + (n / Math.max(...item.bars, 1)) * 28 : 3}px`,
                  }}
                />
              ))}
            </div>
          </div>
          <small>{item.foot}</small>
        </Card>
      ))}
    </div>
  );
}

export function DashboardBottom({
  data,
  onNavigate,
}: {
  data: Overview;
  onNavigate: (s: string) => void;
}) {
  return (
    <div className="dashboard-bottom">
      <section className="panel recent-panel">
        <SectionHeading
          title="Recent relationships"
          right={
            <button className="text-button" onClick={() => onNavigate("Leads")}>
              View all leads <ArrowUpRight size={14} />
            </button>
          }
        />
        {data.recent_leads.length ? (
          data.recent_leads.map((l) => (
            <button
              className="recent-row"
              key={l.id}
              onClick={() => onNavigate("Leads")}
            >
              <Avatar name={l.name} />
              <span>
                <strong>{l.name}</strong>
                <small>{l.company || l.email || "Individual contact"}</small>
              </span>
              <Badge value={l.status} />
              <span className="recent-value">{money(l.value)}</span>
            </button>
          ))
        ) : (
          <p className="panel-empty">Your latest leads will appear here.</p>
        )}
      </section>
      <section className="panel sources-panel">
        <SectionHeading
          title="Where leads find you"
          right={<span className="muted">By source</span>}
        />
        {data.sources.length ? (
          data.sources.map((s) => (
            <div className="source-row" key={s.source}>
              <div>
                <span>
                  {s.source === "email" ? (
                    <Mail size={14} />
                  ) : (
                    <ArrowUpRight size={14} />
                  )}{" "}
                  {label(s.source)}
                </span>
                <strong>
                  {s.count}
                  <small>
                    {Math.round((s.count / data.total_leads) * 100)}%
                  </small>
                </strong>
              </div>
              <div className="source-bar">
                <span
                  style={{ width: `${(s.count / data.total_leads) * 100}%` }}
                />
              </div>
            </div>
          ))
        ) : (
          <p className="panel-empty">Add leads to understand your sources.</p>
        )}
        <p className="source-caption">
          A clear view of what brings people to your business.
        </p>
      </section>
    </div>
  );
}
