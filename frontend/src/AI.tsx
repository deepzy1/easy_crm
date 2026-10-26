import { Input, Select, Textarea, Tabs } from "./components/ui";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Check,
  CheckCheck,
  CircleCheck,
  CircleHelp,
  Cpu,
  ExternalLink,
  FlaskConical,
  KeyRound,
  LoaderCircle,
  RefreshCw,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";
import { api } from "./api";
import type {
  AISettings,
  Generation,
  ModelCatalogue,
  Preference,
  Workspace,
} from "./api";
import { Button, Empty, ErrorBox, Loading } from "./components/ui";

export function Settings({
  base,
  workspace,
  notify,
  refreshWorkspaces,
}: {
  base: string;
  workspace: Workspace;
  notify: (s: string) => void;
  refreshWorkspaces: () => void;
}) {
  const [tab, setTab] = useState("ai");
  return (
    <>
      <div className="page-title">
        <div>
          <span className="eyebrow">MAKE IT YOURS</span>
          <h1>Workspace settings</h1>
          <p>A little configuration. A lot of possibility.</p>
        </div>
      </div>
      <Tabs
        value={tab}
        onChange={setTab}
        label="Settings sections"
        items={[
          {
            value: "ai",
            label: (
              <>
                <Sparkles size={16} />
                AI models
              </>
            ),
          },
          {
            value: "business",
            label: (
              <>
                <Settings2 size={16} />
                Business profile
              </>
            ),
          },
        ]}
      />
      {tab === "ai" ? (
        <AIModels base={base} notify={notify} />
      ) : (
        <BusinessProfile
          key={workspace.id}
          base={base}
          workspace={workspace}
          notify={notify}
          onSaved={refreshWorkspaces}
        />
      )}
    </>
  );
}
const availabilityLabels = {
  available: "Available",
  verified_working: "Verified working",
  rate_limited: "Rate-limited",
  access_restricted: "Access restricted",
  unavailable: "Unavailable",
  unknown: "Availability unknown",
};
function AIModels({
  base,
  notify,
}: {
  base: string;
  notify: (s: string) => void;
}) {
  const client = useQueryClient();
  const settings = useQuery({
    queryKey: ["ai", base],
    queryFn: () => api<AISettings>(`${base}/ai/settings`),
  });
  const [choice, setChoice] = useState<Preference>({
    provider: "gemini",
    model: "",
  });
  const [search, setSearch] = useState("");
  useEffect(() => {
    if (settings.data)
      setChoice(settings.data.active || { provider: "gemini", model: "" });
  }, [settings.data]);
  const modelKey = ["ai-models", base, choice.provider];
  const models = useQuery({
    queryKey: modelKey,
    queryFn: () =>
      api<ModelCatalogue>(`${base}/ai/models?provider=${choice.provider}`),
    enabled: !!settings.data,
    staleTime: 300_000,
  });
  const refresh = useMutation({
    mutationFn: (provider: string) =>
      api<ModelCatalogue>(
        `${base}/ai/models?provider=${provider}&refresh=true`,
      ),
    onSuccess: (data, provider) =>
      client.setQueryData(["ai-models", base, provider], data),
  });
  const save = useMutation({
    mutationFn: (preference: Preference) =>
      api(`${base}/ai/settings`, {
        method: "PUT",
        body: JSON.stringify(preference),
      }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["ai", base] });
      notify("Your default AI model is saved");
    },
  });
  const test = useMutation({
    mutationFn: (preference: Preference) =>
      api<Generation>(`${base}/ai/test`, {
        method: "POST",
        body: JSON.stringify(preference),
      }),
    onSettled: (_data, _error, preference) => {
      void client.invalidateQueries({
        queryKey: ["ai-models", base, preference.provider],
      });
    },
  });
  const changeProvider = (provider: string) => {
    setChoice(
      settings.data?.active?.provider === provider
        ? settings.data.active
        : { provider, model: "" },
    );
    setSearch("");
    test.reset();
    save.reset();
    refresh.reset();
  };
  if (settings.isPending) return <Loading />;
  if (settings.error)
    return (
      <ErrorBox
        message={settings.error.message}
        retry={() => void settings.refetch()}
      />
    );
  const selected = settings.data.providers.find(
    (p) => p.id === choice.provider,
  );
  const rows = models.data?.models || [];
  const current = rows.find((model) => model.id === choice.model);
  const filtered = rows.filter((model) =>
    `${model.id} ${model.name} ${model.family}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  const families = [...new Set(filtered.map((model) => model.family))];
  const busy = save.isPending || test.isPending || refresh.isPending;
  const disabled = !settings.data.can_manage || busy;
  const catalogueError = models.data?.error;
  const testMatches =
    test.variables?.provider === choice.provider &&
    test.variables?.model === choice.model;
  return (
    <div className="settings-layout">
      <div className="settings-main">
        <section className="settings-section">
          <span className="step-label">01 / YOUR PROVIDER</span>
          <h2>Choose your intelligence</h2>
          <p>Choose a provider configured on your server.</p>
          <div
            className="provider-grid"
            role="radiogroup"
            aria-label="AI provider"
          >
            {settings.data.providers.map((p) => (
              <button
                key={p.id}
                disabled={disabled}
                className={`provider-card ${choice.provider === p.id ? "chosen" : ""}`}
                role="radio"
                aria-checked={choice.provider === p.id}
                tabIndex={choice.provider === p.id ? 0 : -1}
                onKeyDown={(event) => {
                  const direction = ["ArrowRight", "ArrowDown"].includes(
                    event.key,
                  )
                    ? 1
                    : ["ArrowLeft", "ArrowUp"].includes(event.key)
                      ? -1
                      : 0;
                  if (!direction) return;
                  event.preventDefault();
                  const providers = settings.data.providers;
                  const index =
                    (providers.findIndex((item) => item.id === p.id) +
                      direction +
                      providers.length) %
                    providers.length;
                  changeProvider(providers[index].id);
                  (
                    event.currentTarget.parentElement?.querySelectorAll(
                      "button",
                    )[index] as HTMLButtonElement
                  )?.focus();
                }}
                onClick={() => changeProvider(p.id)}
              >
                <div className="provider-top">
                  <span className={`provider-logo ${p.id}`}>
                    {p.id === "gemini" ? (
                      <Sparkles size={24} />
                    ) : (
                      <Cpu size={24} />
                    )}
                  </span>
                  <span className="radio-circle">
                    {choice.provider === p.id && <span />}
                  </span>
                </div>
                <h3>{p.name}</h3>
                <p>
                  {p.id === "gemini"
                    ? "Versatile intelligence from Google."
                    : "Open models. Powerful possibilities."}
                </p>
                <span
                  className={`credential-status ${p.configured ? "connected" : ""}`}
                >
                  <span />
                  {p.configured
                    ? "Server credentials configured"
                    : "Server credentials needed"}
                </span>
              </button>
            ))}
          </div>
        </section>
        <section className="settings-section">
          <div className="model-section-heading">
            <div>
              <span className="step-label">02 / DEFAULT MODEL</span>
              <h2>The right model for the job</h2>
            </div>
            <Button
              disabled={disabled || models.isFetching}
              onClick={() => {
                test.reset();
                refresh.mutate(choice.provider);
              }}
            >
              <RefreshCw
                size={14}
                className={refresh.isPending ? "spin" : ""}
              />
              {refresh.isPending ? "Refreshing…" : "Refresh Models"}
            </Button>
          </div>
          <p>This model will power your workspace’s AI requests.</p>
          {models.isPending && <Loading />}
          {models.error && (
            <ErrorBox
              message={models.error.message}
              retry={() => void models.refetch()}
            />
          )}
          {refresh.error && <ErrorBox message={refresh.error.message} />}
          {catalogueError && catalogueError.code !== "missing_credentials" && (
            <ErrorBox
              message={`${models.data?.stale ? "Showing the previous catalogue. " : ""}${catalogueError.message}`}
            />
          )}
          <label className="model-search">
            <span>
              <Search size={13} /> Search models
            </span>
            <Input
              type="search"
              aria-label="Search models"
              placeholder="Search by name, ID, or family"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              disabled={disabled || !rows.length}
            />
          </label>
          <label className="model-label">
            Model
            <Select
              aria-label="Model"
              disabled={disabled || !rows.length}
              value={choice.model}
              onChange={(e) => {
                setChoice({ ...choice, model: e.target.value });
                test.reset();
                save.reset();
              }}
            >
              <option value="" disabled>
                Select a model
              </option>
              {choice.model && !current && (
                <option value={choice.model} disabled>
                  {choice.model} · Not in current catalogue
                </option>
              )}
              {current && !filtered.includes(current) && (
                <optgroup label="Selected model">
                  <option value={current.id}>
                    {current.id} · {availabilityLabels[current.availability]}
                  </option>
                </optgroup>
              )}
              {families.map((family) => (
                <optgroup label={family} key={family}>
                  {filtered
                    .filter((model) => model.family === family)
                    .map((model) => (
                      <option key={model.id} value={model.id}>
                        {model.id} · {availabilityLabels[model.availability]}
                      </option>
                    ))}
                </optgroup>
              ))}
            </Select>
          </label>
          {!models.isPending && !rows.length && (
            <p role="status" className="field-hint">
              No text-generation models found. Check provider configuration and
              refresh models.
            </p>
          )}
          {rows.length > 0 && filtered.length === 0 && (
            <p role="status" className="field-hint">
              No models match your search.
            </p>
          )}
          {current && (
            <div className="model-details" aria-live="polite">
              <span className={`model-availability ${current.availability}`}>
                {availabilityLabels[current.availability]}
              </span>
              <strong>{current.name}</strong>
              <p>Free-tier eligibility unverified</p>
              <p>
                {current.checked_at
                  ? `Last generation check: ${new Date(current.checked_at).toLocaleString()}`
                  : "Generation access has not been tested."}
              </p>
              {current.error && !testMatches && <p>{current.error.message}</p>}
            </div>
          )}
          {models.data?.fetched_at && (
            <p className="field-hint">
              Catalogue {models.data.stale ? "stale" : "updated"} ·{" "}
              {new Date(models.data.fetched_at).toLocaleString()}
            </p>
          )}
          {choice.provider === "nvidia" && (
            <p className="field-hint">
              NVIDIA chat models are configured on the server; refresh checks
              catalogue presence. Listing does not verify inference access.
            </p>
          )}
          {!selected?.configured && (
            <div className="key-notice">
              <KeyRound size={17} />
              <div>
                <strong>Add your server-side API key</strong>
                <p>
                  Set <code>{choice.provider.toUpperCase()}_API_KEY</code> in
                  your server’s .env file, then restart the backend. Your key
                  stays private.
                </p>
              </div>
            </div>
          )}
          {save.error && <ErrorBox message={save.error.message} />}
          {testMatches && test.error && (
            <ErrorBox message={test.error.message} />
          )}
          {testMatches && test.data && (
            <div className="success-box">
              <CircleCheck size={18} />
              Verified working: {test.data.model} · {test.data.latency_ms} ms.
              Free-tier eligibility remains unverified.
            </div>
          )}
          <div className="settings-actions">
            <Button
              disabled={disabled || !current}
              onClick={() => test.mutate(choice)}
            >
              {test.isPending ? (
                <LoaderCircle size={16} className="spin" />
              ) : (
                <Zap size={16} />
              )}
              {test.isPending ? "Testing model…" : "Test Model"}
            </Button>
            <Button
              variant="primary"
              disabled={
                disabled ||
                !current ||
                current.availability === "unavailable" ||
                (choice.provider === "gemini" && !!catalogueError)
              }
              onClick={() => save.mutate(choice)}
            >
              <Check size={16} />
              {save.isPending ? "Saving…" : "Save as Default"}
            </Button>
          </div>
          <p className="field-hint">
            Test Model sends one real generation request with a 256-token output
            cap. It may consume quota or incur charges. A successful test does
            not confirm free-tier eligibility.
          </p>
        </section>
      </div>
      <aside className="settings-aside">
        <div className="active-model">
          <div className="aside-icon">
            <Sparkles size={20} />
          </div>
          <span className="eyebrow">CURRENTLY ACTIVE</span>
          <h3>
            {settings.data.active
              ? settings.data.active.provider === "gemini"
                ? "Google Gemini"
                : "NVIDIA NIM"
              : "Your AI, your choice"}
          </h3>
          <p>
            {settings.data.active?.model ||
              "Save a default model to get started."}
          </p>
          {settings.data.active && (
            <span className="active-pill">
              <CheckCheck size={13} />
              Workspace default
            </span>
          )}
        </div>
        <div className="privacy-note">
          <ShieldCheck size={21} />
          <h4>Private by design</h4>
          <p>
            API keys live on your server. They’re never sent to your browser or
            saved in workspace preferences.
          </p>
        </div>
        <a className="inline-link" href="#AI%20Qualification">
          Try the AI playground <ArrowRight size={15} />
        </a>
      </aside>
    </div>
  );
}
function BusinessProfile({
  base,
  workspace,
  notify,
  onSaved,
}: {
  base: string;
  workspace: Workspace;
  notify: (s: string) => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState({
    name: workspace.name,
    industry: workspace.industry,
    website: workspace.website,
    description: workspace.description,
  });
  const save = useMutation({
    mutationFn: () =>
      api(`${base}/business-profile`, {
        method: "PATCH",
        body: JSON.stringify(form),
      }),
    onSuccess: () => {
      notify("Business profile saved");
      onSaved();
    },
  });
  return (
    <form
      className="business-form"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <h2>A home for your relationships</h2>
      <p>Your business details, shared across this workspace.</p>
      <label>
        Workspace name
        <Input
          required
          maxLength={100}
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
        />
      </label>
      <label>
        Industry
        <Input
          maxLength={100}
          value={form.industry}
          onChange={(e) => setForm({ ...form, industry: e.target.value })}
          placeholder="e.g. Software & technology"
        />
      </label>
      <label>
        Website
        <Input
          type="url"
          maxLength={500}
          value={form.website}
          onChange={(e) => setForm({ ...form, website: e.target.value })}
          placeholder="https://your-company.com"
        />
      </label>
      <label>
        About your business
        <Textarea
          rows={4}
          maxLength={5000}
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
          placeholder="What does your company do?"
        />
      </label>
      {save.error && <ErrorBox message={save.error.message} />}
      <Button type="submit" variant="primary" disabled={save.isPending}>
        <Check size={16} />
        {save.isPending ? "Saving…" : "Save business profile"}
      </Button>
    </form>
  );
}
export function Playground({
  base,
  onSettings,
}: {
  base: string;
  onSettings: () => void;
}) {
  const settings = useQuery({
    queryKey: ["ai", base],
    queryFn: () => api<AISettings>(`${base}/ai/settings`),
  });
  const [prompt, setPrompt] = useState("");
  const [sent, setSent] = useState("");
  const generate = useMutation({
    mutationFn: (value: string) =>
      api<Generation>(`${base}/ai/generate`, {
        method: "POST",
        body: JSON.stringify({ prompt: value }),
      }),
    onMutate: (value) => setSent(value),
  });
  const suggestions = [
    "Write a warm introduction for a new inbound lead.",
    "Suggest five questions to understand a prospect’s needs.",
    "Draft a friendly follow-up after a product demo.",
  ];
  return (
    <>
      <div className="page-title">
        <div>
          <span className="eyebrow">A SPACE TO EXPERIMENT</span>
          <h1>Meet your AI copilot</h1>
          <p>Try a prompt. Explore a possibility. Find your flow.</p>
        </div>
        <span className="outline-pill">
          <FlaskConical size={14} />
          Playground
        </span>
      </div>
      {settings.error && <ErrorBox message={settings.error.message} />}
      {!settings.isPending && !settings.error && !settings.data?.active && (
        <div className="setup-banner">
          <Sparkles size={18} />
          <span>Choose a default model to start exploring.</span>
          <Button onClick={onSettings}>
            Configure AI <ArrowRight size={14} />
          </Button>
        </div>
      )}
      <div className="playground">
        <div className="playground-header">
          <div>
            <span className="model-status-dot" />
            <strong>{settings.data?.active?.model || "No active model"}</strong>
            <span>
              {settings.data?.active?.provider || "Workspace default"}
            </span>
          </div>
          <button className="text-button" onClick={onSettings}>
            <Settings2 size={14} />
            Model settings
          </button>
        </div>
        <div className="playground-content">
          {sent ? (
            <>
              <div className="prompt-message">
                <span className="message-label">YOU</span>
                <p>{sent}</p>
              </div>
              {generate.isPending ? (
                <div className="ai-thinking" role="status">
                  <Sparkles size={18} />
                  <span>Your model is thinking</span>
                  <span className="thinking-dots">•••</span>
                </div>
              ) : generate.error ? (
                <ErrorBox message={generate.error.message} />
              ) : (
                generate.data && (
                  <div className="response-message">
                    <span className="message-label">
                      <Sparkles size={14} />
                      EASYCRM AI
                    </span>
                    <p>{generate.data.text}</p>
                    <div className="usage-line">
                      <span>
                        {generate.data.provider} / {generate.data.model}
                      </span>
                      <span>
                        {generate.data.latency_ms.toLocaleString()} ms
                      </span>
                      <span>
                        {generate.data.input_tokens ?? "—"} input ·{" "}
                        {generate.data.output_tokens ?? "—"} output tokens
                      </span>
                    </div>
                  </div>
                )
              )}
            </>
          ) : (
            <>
              <Empty
                title="A little curiosity goes a long way"
                text="Ask your configured model anything. This is a real model playground; no messages are sent to leads."
              />
              <div className="suggestion-grid">
                {suggestions.map((s) => (
                  <button key={s} onClick={() => setPrompt(s)}>
                    <Sparkles size={15} />
                    <span>{s}</span>
                    <ArrowRight size={15} />
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
        <form
          className="prompt-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (prompt.trim()) generate.mutate(prompt);
          }}
        >
          <label className="sr-only" htmlFor="prompt">
            Your AI prompt
          </label>
          <Textarea
            id="prompt"
            maxLength={8000}
            rows={3}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="What would you like to explore?"
            onKeyDown={(e) => {
              if (
                (e.metaKey || e.ctrlKey) &&
                e.key === "Enter" &&
                prompt.trim() &&
                !generate.isPending &&
                settings.data?.active
              )
                generate.mutate(prompt);
            }}
          />
          <div>
            <span>
              <CircleHelp size={13} />
              Prompts are sent to your selected provider.
            </span>
            <Button
              variant="primary"
              type="submit"
              disabled={
                !prompt.trim() || generate.isPending || !settings.data?.active
              }
            >
              {generate.isPending ? (
                <LoaderCircle size={16} className="spin" />
              ) : (
                <Send size={16} />
              )}
              Send prompt
            </Button>
          </div>
        </form>
      </div>
      <p className="playground-disclaimer">
        Explore freely. Review carefully. AI can make mistakes.{" "}
        <a
          href="https://ai.google.dev/gemini-api/docs"
          target="_blank"
          rel="noreferrer"
        >
          Provider documentation <ExternalLink size={11} />
        </a>
      </p>
    </>
  );
}
