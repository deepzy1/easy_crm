import { Input, Select, Sidebar, Toast } from "./components/ui";
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Building2,
  ChartNoAxesCombined,
  Check,
  ChevronsUpDown,
  CircleHelp,
  Command,
  Ellipsis,
  House,
  Inbox,
  Layers2,
  LogOut,
  Menu,
  PanelLeftClose,
  Plug,
  Plus,
  Search,
  Settings as SettingsIcon,
  ShieldCheck,
  Sparkles,
  Users,
  X,
} from "lucide-react";
import { api, initials } from "./api";
import type { Overview, Stage, User, Workspace } from "./api";
import {
  Avatar,
  Button,
  ErrorBox,
  FuturePage,
  Loading,
  Modal,
} from "./components/ui";
import {
  DashboardBottom,
  DashboardMetrics,
  LeadWorkspace,
} from "./LeadWorkspace";
import { Playground, Settings } from "./AI";

const navigation = [
  { name: "Dashboard", icon: House },
  { name: "Leads", icon: Users },
  { name: "Pipeline", icon: Layers2 },
  { name: "Inbox", icon: Inbox },
  { name: "AI Qualification", icon: Sparkles },
  { name: "Knowledge Base", icon: BookOpen },
  { name: "Integrations", icon: Plug },
  { name: "Analytics", icon: ChartNoAxesCombined },
];
const pageFromHash = () => {
  try {
    const name = decodeURIComponent(location.hash.slice(1));
    return [...navigation.map((n) => n.name), "Settings"].includes(name)
      ? name
      : "Dashboard";
  } catch {
    return "Dashboard";
  }
};
function Brand() {
  return (
    <span className="brand">
      <span className="brand-symbol">
        <span />
        <span />
        <span />
      </span>
      EasyCRM<span className="brand-period">.</span>
    </span>
  );
}
export default function App() {
  const client = useQueryClient();
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api<{ user: User; workspaces: Workspace[] }>("/auth/me"),
    retry: false,
  });
  const [expired, setExpired] = useState(false);
  useEffect(() => {
    const handle = () => {
      setExpired(true);
      client.clear();
    };
    window.addEventListener("session-expired", handle);
    return () => window.removeEventListener("session-expired", handle);
  }, [client]);
  if (me.isPending && !expired)
    return (
      <div className="app-loading">
        <Brand />
        <Loading />
      </div>
    );
  if (!me.data || expired)
    return (
      <Auth
        onSuccess={() => {
          setExpired(false);
          void client.invalidateQueries({ queryKey: ["me"] });
        }}
      />
    );
  return (
    <WorkspaceShell
      user={me.data.user}
      workspaces={me.data.workspaces}
      onLogout={() => {
        client.clear();
        setExpired(true);
      }}
      refreshWorkspaces={() =>
        void client.invalidateQueries({ queryKey: ["me"] })
      }
    />
  );
}
function Auth({ onSuccess }: { onSuccess: () => void }) {
  const [register, setRegister] = useState(false);
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    workspace_name: "",
  });
  const auth = useMutation({
    mutationFn: () =>
      api(`/auth/${register ? "register" : "login"}`, {
        method: "POST",
        body: JSON.stringify(
          register ? form : { email: form.email, password: form.password },
        ),
      }),
    onSuccess,
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    auth.mutate();
  };
  return (
    <div className="auth-layout">
      <div className="auth-story">
        <Brand />
        <div className="auth-story-content">
          <span className="auth-eyebrow">
            <span />
            GOOD RELATIONSHIPS. GREAT POSSIBILITIES.
          </span>
          <h1>
            A clearer view.
            <br />A closer connection.
          </h1>
          <p>
            Bring your relationships, your pipeline, and a little intelligence
            together.
          </p>
          <div className="concept-board" aria-hidden="true">
            <div className="concept-top">
              <Layers2 size={17} />
              <strong>Your next opportunity</strong>
              <Ellipsis size={18} />
            </div>
            <div className="concept-stages">
              <span>
                <i />
                Connect
              </span>
              <ArrowRight size={14} />
              <span>
                <i />
                Understand
              </span>
              <ArrowRight size={14} />
              <span>
                <i />
                Grow
              </span>
            </div>
            <div className="concept-card">
              <div className="concept-avatar">
                <Building2 size={23} />
              </div>
              <div>
                <strong>Relationships with context.</strong>
                <p>A little more human. A lot more connected.</p>
              </div>
              <span className="concept-check">
                <Check size={17} />
              </span>
            </div>
            <div className="concept-ai">
              <Sparkles size={19} />
              <div>
                <strong>Intelligence, on your terms.</strong>
                <p>Your provider. Your model. Your workspace.</p>
              </div>
            </div>
          </div>
        </div>
        <div className="auth-footer">
          <span>Thoughtfully built for what’s next.</span>
          <span>EasyCRM © 2026</span>
        </div>
      </div>
      <main className="auth-form-panel">
        <div className="auth-top">
          <span>
            {register ? "Already part of a workspace?" : "New around here?"}
          </span>
          <button
            onClick={() => {
              setRegister(!register);
              auth.reset();
            }}
          >
            {register ? "Sign in" : "Create a workspace"}{" "}
            <ArrowUpRight size={13} />
          </button>
        </div>
        <div className="auth-form-content">
          <span className="auth-small-icon">
            <Command size={22} />
          </span>
          <span className="eyebrow">YOUR RELATIONSHIPS, REIMAGINED</span>
          <h2>
            {register ? "Make room for possibility." : "Good to see you again."}
          </h2>
          <p>
            {register
              ? "Create your account and give your pipeline a home."
              : "Sign in to pick up where you left off."}
          </p>
          <form onSubmit={submit}>
            {register && (
              <>
                <label>
                  Your name
                  <Input
                    autoComplete="name"
                    required
                    maxLength={100}
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder="Alex Morgan"
                  />
                </label>
                <label>
                  Workspace name
                  <Input
                    autoComplete="organization"
                    required
                    maxLength={100}
                    value={form.workspace_name}
                    onChange={(e) =>
                      setForm({ ...form, workspace_name: e.target.value })
                    }
                    placeholder="Your company"
                  />
                </label>
              </>
            )}
            <label>
              Work email
              <Input
                type="email"
                autoComplete="email"
                required
                maxLength={254}
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="you@company.com"
              />
            </label>
            <label>
              Password
              <Input
                type="password"
                autoComplete={register ? "new-password" : "current-password"}
                minLength={register ? 10 : 1}
                maxLength={128}
                required
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder={
                  register ? "At least 10 characters" : "Enter your password"
                }
              />
            </label>
            {auth.error && <ErrorBox message={auth.error.message} />}
            <Button variant="primary" type="submit" disabled={auth.isPending}>
              {auth.isPending
                ? "Just a moment…"
                : register
                  ? "Create your workspace"
                  : "Sign in to EasyCRM"}
              <ArrowRight size={16} />
            </Button>
          </form>
          <p className="auth-security">
            <ShieldCheck size={14} />A private space for your business
            relationships.
          </p>
        </div>
        <span className="auth-bottom">
          A little less busywork. A little more possibility.
        </span>
      </main>
    </div>
  );
}
function WorkspaceShell({
  user,
  workspaces,
  onLogout,
  refreshWorkspaces,
}: {
  user: User;
  workspaces: Workspace[];
  onLogout: () => void;
  refreshWorkspaces: () => void;
}) {
  const [wsId, setWsId] = useState(workspaces[0]?.id || "");
  const workspace = workspaces.find((w) => w.id === wsId) || workspaces[0];
  const [page, setPage] = useState(pageFromHash);
  const [mobile, setMobile] = useState(false);
  const [narrow, setNarrow] = useState(
    () => window.matchMedia("(max-width: 680px)").matches,
  );
  const sidebar = useRef<HTMLElement>(null);
  const menuButton = useRef<HTMLButtonElement>(null);
  const [help, setHelp] = useState(false);
  const [create, setCreate] = useState(false);
  const [workspaceName, setWorkspaceName] = useState("");
  const [toast, setToast] = useState("");
  const [globalSearch, setGlobalSearch] = useState("");
  const [leadSearch, setLeadSearch] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const client = useQueryClient();
  useEffect(() => {
    const media = window.matchMedia("(max-width: 680px)");
    const change = () => setNarrow(media.matches);
    media.addEventListener("change", change);
    return () => media.removeEventListener("change", change);
  }, []);
  useEffect(() => {
    if (mobile && narrow)
      sidebar.current?.querySelector<HTMLButtonElement>("nav button")?.focus();
  }, [mobile, narrow]);
  useEffect(() => {
    const handle = () => setPage(pageFromHash());
    window.addEventListener("hashchange", handle);
    return () => window.removeEventListener("hashchange", handle);
  }, []);
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(""), 4500);
      return () => clearTimeout(timer);
    }
  }, [toast]);
  const navigate = (name: string) => {
    location.hash = encodeURIComponent(name);
    setPage(name);
    setMobile(false);
    setLeadSearch("");
  };
  const base = `/workspaces/${workspace?.id}`;
  const stages = useQuery({
    queryKey: ["stages", base],
    queryFn: () => api<Stage[]>(`${base}/stages`),
    enabled: !!workspace,
  });
  const overview = useQuery({
    queryKey: ["overview", base],
    queryFn: () => api<Overview>(`${base}/analytics/overview`),
    enabled: !!workspace && ["Dashboard", "Analytics"].includes(page),
  });
  const search = useQuery({
    queryKey: ["global-search", base, globalSearch],
    queryFn: () =>
      api<{ items: { id: string; name: string; company: string }[] }>(
        `${base}/leads?q=${encodeURIComponent(globalSearch)}&limit=8`,
      ),
    enabled: searchOpen && !!globalSearch.trim() && !!workspace,
  });
  const logout = useMutation({
    mutationFn: () => api("/auth/logout", { method: "POST" }),
    onSuccess: onLogout,
  });
  const addWorkspace = useMutation({
    mutationFn: () =>
      api<Workspace>("/workspaces", {
        method: "POST",
        body: JSON.stringify({ name: workspaceName }),
      }),
    onSuccess: (result) => {
      setWsId(result.id);
      refreshWorkspaces();
      setCreate(false);
      setWorkspaceName("");
      setToast("A new workspace, ready for you");
    },
  });
  const changeWs = (id: string) => {
    setWsId(id);
    setGlobalSearch("");
    setSearchOpen(false);
    client.removeQueries({ queryKey: ["global-search"] });
  };
  return (
    <div className="app-shell">
      {mobile && (
        <div className="sidebar-scrim" onClick={() => setMobile(false)} />
      )}
      <Sidebar
        ref={sidebar}
        inert={narrow && !mobile}
        className={`sidebar ${mobile ? "mobile-open" : ""}`}
        onKeyDown={(event) => {
          if (!narrow || !mobile) return;
          if (event.key === "Escape") {
            setMobile(false);
            menuButton.current?.focus();
          }
          if (event.key === "Tab") {
            const controls =
              sidebar.current?.querySelectorAll<HTMLButtonElement>(
                "button:not(:disabled)",
              );
            if (!controls?.length) return;
            const first = controls[0];
            const last = controls[controls.length - 1];
            if (event.shiftKey && document.activeElement === first) {
              event.preventDefault();
              last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
              event.preventDefault();
              first.focus();
            }
          }
        }}
      >
        <div className="sidebar-brand">
          <Brand />
          <button
            className="icon-button collapse-button"
            onClick={() => setMobile(false)}
            aria-label="Close sidebar"
          >
            <PanelLeftClose size={17} />
          </button>
        </div>
        <div className="sidebar-section-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {navigation.map((n) => (
            <button
              key={n.name}
              onClick={() => navigate(n.name)}
              className={`nav-item ${page === n.name ? "active" : ""}`}
            >
              <n.icon size={18} />
              <span>{n.name}</span>
              {n.name === "AI Qualification" && (
                <span className="nav-ai">AI</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="workspace-tip">
            <div>
              <span className="tip-icon">
                <Sparkles size={17} />
              </span>
              <span>Meet your AI copilot</span>
            </div>
            <p>A little intelligence for your next big opportunity.</p>
            <button onClick={() => navigate("AI Qualification")}>
              Explore the playground <ArrowUpRight size={14} />
            </button>
          </div>
          <button
            className={`nav-item ${page === "Settings" ? "active" : ""}`}
            onClick={() => navigate("Settings")}
          >
            <SettingsIcon size={18} />
            <span>Settings</span>
          </button>
          <div className="user-footer">
            <Avatar name={user.name} />
            <div>
              <strong>{user.name}</strong>
              <span>{user.email}</span>
            </div>
            <button
              className="icon-button"
              aria-label="Sign out"
              onClick={() => logout.mutate()}
              disabled={logout.isPending}
            >
              <LogOut size={16} />
            </button>
          </div>
          {logout.error && <ErrorBox message={logout.error.message} />}
        </div>
      </Sidebar>
      <div className="main-shell">
        <header className="topbar">
          <button
            className="icon-button mobile-menu"
            ref={menuButton}
            aria-expanded={mobile}
            onClick={() => setMobile(true)}
            aria-label="Open navigation"
          >
            <Menu size={21} />
          </button>
          <div className="workspace-switcher">
            <span className="workspace-avatar">
              {initials(workspace?.name || "Workspace")}
            </span>
            <label>
              <span className="sr-only">Current workspace</span>
              <Select
                value={workspace?.id || ""}
                onChange={(e) =>
                  e.target.value === "__new"
                    ? setCreate(true)
                    : changeWs(e.target.value)
                }
              >
                {workspaces.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
                <option value="__new">＋ Create workspace</option>
              </Select>
              <span className="workspace-subtitle">Your workspace</span>
            </label>
            <ChevronsUpDown size={13} />
          </div>
          <div className="global-search">
            <Search size={16} />
            <label className="sr-only" htmlFor="global-search">
              Search workspace leads
            </label>
            <Input
              id="global-search"
              value={globalSearch}
              onFocus={() => setSearchOpen(true)}
              onChange={(e) => {
                setGlobalSearch(e.target.value);
                setSearchOpen(true);
              }}
              placeholder="Search your relationships…"
            />
            <span className="search-key">Search</span>
            {searchOpen && globalSearch && (
              <div className="search-results">
                <div className="search-results-heading">
                  LEADS
                  <button
                    className="icon-button"
                    aria-label="Close results"
                    onClick={() => setSearchOpen(false)}
                  >
                    <X size={13} />
                  </button>
                </div>
                {search.isPending ? (
                  <Loading />
                ) : search.error ? (
                  <ErrorBox message={search.error.message} />
                ) : search.data?.items.length ? (
                  search.data.items.map((l) => (
                    <button
                      key={l.id}
                      onClick={() => {
                        navigate("Leads");
                        setLeadSearch(l.name);
                        setSearchOpen(false);
                      }}
                    >
                      <Avatar name={l.name} small />
                      <span>
                        {l.name}
                        <small>{l.company}</small>
                      </span>
                      <ArrowUpRight size={14} />
                    </button>
                  ))
                ) : (
                  <p>No leads found. Try another name or company.</p>
                )}
              </div>
            )}
          </div>
          <div className="topbar-end">
            <span className="local-status">
              <span />
              Private workspace
            </span>
            <span className="topbar-divider" />
            <button
              className="icon-button"
              aria-label="About EasyCRM"
              onClick={() => setHelp(true)}
            >
              <CircleHelp size={19} />
            </button>
            <Avatar name={user.name} />
          </div>
        </header>
        <main className="main-content">
          <div className="breadcrumb">
            <House size={13} />
            <span>/</span>
            {page}
            <span className="breadcrumb-dot" />
            <span className="breadcrumb-context">
              Your relationship workspace
            </span>
          </div>
          {!workspace ? (
            <div className="empty">
              <h1>A space to call your own</h1>
              <Button variant="primary" onClick={() => setCreate(true)}>
                <Plus size={16} />
                Create workspace
              </Button>
            </div>
          ) : page === "Settings" ? (
            <Settings
              key={base}
              base={base}
              workspace={workspace}
              notify={setToast}
              refreshWorkspaces={refreshWorkspaces}
            />
          ) : page === "AI Qualification" ? (
            <Playground
              key={base}
              base={base}
              onSettings={() => navigate("Settings")}
            />
          ) : ["Dashboard", "Leads", "Pipeline", "Analytics"].includes(page) ? (
            <>
              <div className="page-title">
                <div>
                  <span className="eyebrow">
                    {page === "Dashboard"
                      ? "A CLEARER PICTURE. A STRONGER PIPELINE."
                      : page === "Analytics"
                        ? "THE STORY BEHIND YOUR RELATIONSHIPS"
                        : "RELATIONSHIPS IN MOTION"}
                  </span>
                  <h1>
                    {page === "Dashboard"
                      ? "Lead qualification pipeline"
                      : page === "Leads"
                        ? "Good people. Great possibilities."
                        : page === "Pipeline"
                          ? "Move your next opportunity forward."
                          : "Your pipeline, in perspective."}
                  </h1>
                  <p>
                    {page === "Dashboard"
                      ? "A little less guesswork. A lot more meaningful connections."
                      : page === "Leads"
                        ? "Every relationship has a story. Keep yours in one place."
                        : page === "Pipeline"
                          ? "From the first hello to the next big win."
                          : "Real workspace data. A clear view of where you stand."}
                  </p>
                </div>
                <span className="date-pill">
                  <span className="live-dot" />
                  All time
                </span>
              </div>
              {["Dashboard", "Analytics"].includes(page) &&
                (overview.isPending ? (
                  <Loading />
                ) : overview.error ? (
                  <ErrorBox
                    message={overview.error.message}
                    retry={() => void overview.refetch()}
                  />
                ) : (
                  <DashboardMetrics data={overview.data} />
                ))}
              {page !== "Analytics" && (
                <>
                  <div className="pipeline-section-title">
                    <h2>
                      {page === "Leads" ? "All relationships" : "Your pipeline"}
                      <span className="subtle-dot" />
                      <span>{workspace.name}</span>
                    </h2>
                    <span>
                      <span className="tiny-live-dot" />
                      Changes saved as you go
                    </span>
                  </div>
                  {stages.isPending ? (
                    <Loading />
                  ) : stages.error ? (
                    <ErrorBox
                      message={stages.error.message}
                      retry={() => void stages.refetch()}
                    />
                  ) : (
                    <LeadWorkspace
                      key={`${base}-${page}-${leadSearch}`}
                      initialSearch={leadSearch}
                      base={base}
                      stages={stages.data}
                      notify={setToast}
                      page={page}
                    />
                  )}
                </>
              )}
              {["Dashboard", "Analytics"].includes(page) && overview.data && (
                <DashboardBottom data={overview.data} onNavigate={navigate} />
              )}
              {page === "Dashboard" && (
                <div className="insights-banner">
                  <div className="insight-stars">
                    <Sparkles size={22} />
                  </div>
                  <div>
                    <h3>A smarter perspective is on its way.</h3>
                    <p>
                      Knowledge-grounded qualification and AI insights are
                      planned for a future session.
                    </p>
                  </div>
                  <Button onClick={() => navigate("AI Qualification")}>
                    Explore AI playground <ArrowUpRight size={15} />
                  </Button>
                </div>
              )}
            </>
          ) : page === "Inbox" ? (
            <FuturePage
              name="Every conversation, connected."
              description="A shared home for customer conversations, with message history and human takeover. WhatsApp connectivity is planned for a future session; no channels are connected yet."
              icon={<Inbox size={32} />}
            />
          ) : page === "Knowledge Base" ? (
            <FuturePage
              name="Give your AI a little context."
              description="Your company’s website pages, documents, and trusted knowledge will live here. Source review, scoped retrieval, and grounded answers are planned for a future session."
              icon={<BookOpen size={32} />}
            />
          ) : (
            <FuturePage
              name="Better, together."
              description="Connect your website forms and messaging channels to bring new relationships into EasyCRM. Signed webhooks, WhatsApp, and other connectors are planned; no live integrations are enabled."
              icon={<Plug size={32} />}
            />
          )}
          <footer className="main-footer">
            <span>Made for meaningful connections.</span>
            <span>
              EasyCRM <span>·</span> Session 1
            </span>
          </footer>
        </main>
      </div>
      {toast && <Toast message={toast} onDismiss={() => setToast("")} />}
      {help && (
        <Modal
          title="A little clarity goes a long way."
          subtitle="Welcome to EasyCRM, your relationship workspace."
          onClose={() => setHelp(false)}
        >
          <div className="help-content">
            <p>
              Create leads, keep their details up to date, and move
              opportunities through your pipeline. Use a card’s stage menu for a
              keyboard-friendly way to move it.
            </p>
            <p>
              Choose a server-configured Gemini or NVIDIA model in Settings,
              then try a real prompt in the AI playground.
            </p>
            <p>
              Inbox, knowledge ingestion, integrations, and automated
              qualification are planned for future sessions.
            </p>
            <Button variant="primary" onClick={() => setHelp(false)}>
              Got it <Check size={15} />
            </Button>
          </div>
        </Modal>
      )}
      {create && (
        <Modal
          title="Make space for what’s next."
          subtitle="Each workspace has its own leads, pipeline, and AI preferences."
          onClose={() => setCreate(false)}
        >
          <form
            className="create-workspace-form"
            onSubmit={(e) => {
              e.preventDefault();
              addWorkspace.mutate();
            }}
          >
            <label>
              Workspace name
              <Input
                required
                minLength={1}
                maxLength={100}
                autoFocus
                value={workspaceName}
                onChange={(e) => setWorkspaceName(e.target.value)}
                placeholder="Your company or team"
              />
            </label>
            {addWorkspace.error && (
              <ErrorBox message={addWorkspace.error.message} />
            )}
            <div className="form-actions">
              <Button type="button" onClick={() => setCreate(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                disabled={addWorkspace.isPending}
                type="submit"
              >
                {addWorkspace.isPending ? "Creating…" : "Create workspace"}
                <ArrowRight size={15} />
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
