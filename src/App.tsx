import { FormEvent, useEffect, useMemo, useState } from "react";

type Outcome = "approved" | "denied" | "escalated";
type Customer = { id: number; name: string; email: string };
type Scenario = { id: string; customer_id: number; message: string; expected_outcome: Outcome; expected_amount: string };
type Receipt = { outcome: Outcome; amount: string; checks: { label: string; passed: boolean }[]; next_step: string };
type RefundResult = { request_id: number; outcome: Outcome; reply: string; receipt: Receipt; needs_clarification?: boolean; question?: string };
type RequestRow = {
  id: number; customer_id: number; order_id: string | null; message: string; outcome: Outcome;
  refund_amount: string; customer_reply: string; review_status: string; appeal_note?: string | null;
  reviewer_note?: string | null; created_at: string; resolved_at?: string | null; receipt: Receipt;
};
type AuditEvent = { id: number; request_id: number; step: string; detail: Record<string, unknown>; created_at: string };
type RequestDetail = RequestRow & { claim: Record<string, unknown> | null; policy_input: Record<string, unknown> | null; policy_result: Record<string, unknown> | null; audit_events: AuditEvent[] };

const api = async <T,>(path: string, init?: RequestInit, adminToken?: string): Promise<T> => {
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");
  if (adminToken) headers.set("X-Admin-Token", adminToken);
  const response = await fetch(path, { ...init, headers });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body?.detail?.message || body?.detail?.error || "Something went wrong");
  return body as T;
};

const outcomeStyles: Record<Outcome, string> = {
  approved: "bg-emerald-100 text-emerald-800 border-emerald-200",
  denied: "bg-rose-100 text-rose-800 border-rose-200",
  escalated: "bg-amber-100 text-amber-900 border-amber-200",
};

function Badge({ outcome }: { outcome: Outcome }) {
  return <span className={`rounded-full border px-2.5 py-1 text-xs font-bold uppercase tracking-wide ${outcomeStyles[outcome]}`}>{outcome}</span>;
}

function Layout({ page, setPage, aiMode, children }: { page: string; setPage: (page: string) => void; aiMode: string; children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4">
          <button onClick={() => setPage("customer")} className="flex items-center gap-3 text-left">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-navy text-lg font-black text-white">R</span>
            <span><span className="block text-lg font-black tracking-tight">RefundDesk</span><span className="block text-xs text-slate-500">Trust-first refund support</span></span>
          </button>
          <nav className="flex items-center gap-2 text-sm font-semibold">
            <button onClick={() => setPage("customer")} className={`rounded-lg px-3 py-2 ${page === "customer" ? "bg-slate-100 text-navy" : "text-slate-500 hover:text-navy"}`}>Customer chat</button>
            <button onClick={() => setPage("admin")} className={`rounded-lg px-3 py-2 ${page === "admin" ? "bg-slate-100 text-navy" : "text-slate-500 hover:text-navy"}`}>Support console</button>
          </nav>
          <span className="hidden items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-600 sm:flex">
            <span className={`h-2 w-2 rounded-full ${aiMode === "mock" ? "bg-amber-400" : "bg-emerald-500"}`} />
            {aiMode === "mock" ? "Mock AI mode" : `Live: ${aiMode}`}
          </span>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-5 py-8">{children}</main>
    </div>
  );
}

function CustomerPage({ customers, scenarios, onRefresh }: { customers: Customer[]; scenarios: Scenario[]; onRefresh: () => void }) {
  const [customerId, setCustomerId] = useState(1);
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<{ role: "customer" | "assistant"; text: string; receipt?: Receipt; id?: number; outcome?: Outcome }[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedScenario, setSelectedScenario] = useState("");

  useEffect(() => {
    const pending = messages.filter((item) => item.outcome === "escalated" && item.id);
    if (!pending.length) return;
    const timer = window.setInterval(() => {
      pending.forEach((item) => {
        void api<RequestRow>(`/api/refunds/${item.id}?customer_id=${customerId}`).then((updated) => {
          if (updated.review_status === "resolved") {
            setMessages((items) => items.map((current) => current.id === item.id ? { ...current, text: updated.customer_reply, outcome: updated.outcome, receipt: updated.receipt } : current));
          }
        }).catch(() => undefined);
      });
    }, 5000);
    return () => window.clearInterval(timer);
  }, [messages, customerId]);

  const appeal = async (requestId: number) => {
    const note = window.prompt("What would you like the support specialist to reconsider?", "Please review the decision and my order details.");
    if (!note) return;
    try {
      await api(`/api/refunds/${requestId}/appeal`, { method: "POST", body: JSON.stringify({ customer_id: customerId, note }) });
      setMessages((items) => items.map((item) => item.id === requestId ? { ...item, text: "Your appeal is in the support queue. We’ll update this conversation when it is resolved.", outcome: "escalated" } : item));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to submit the appeal.");
    }
  };

  const submit = async (event?: FormEvent) => {
    event?.preventDefault();
    if (!message.trim() || loading) return;
    const current = message.trim();
    setMessages((items) => [...items, { role: "customer", text: current }]);
    setMessage("");
    setLoading(true);
    setError("");
    try {
      const result = await api<RefundResult>("/api/refunds", { method: "POST", body: JSON.stringify({ customer_id: customerId, message: current }) });
      setMessages((items) => [...items, { role: "assistant", text: result.reply || result.question || "", receipt: result.receipt, id: result.request_id, outcome: result.outcome }]);
      onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to submit your request.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_340px]">
      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-soft">
        <div className="border-b border-slate-200 bg-gradient-to-br from-navy to-[#285a7d] px-7 py-8 text-white">
          <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-cyan-100">Customer support</p>
          <h1 className="max-w-xl text-3xl font-black tracking-tight sm:text-4xl">Let’s sort out your refund.</h1>
          <p className="mt-3 max-w-xl text-sm leading-6 text-blue-100">Describe what happened and include your order ID. Refund amounts are calculated from your order, not from the chat.</p>
        </div>
        <div className="min-h-[360px] space-y-4 bg-slate-50/70 p-6">
          {messages.length === 0 && (
            <div className="grid min-h-[280px] place-items-center rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
              <div><div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-mint text-2xl">✓</div><h2 className="font-bold text-navy">A clear answer, with a receipt</h2><p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-slate-500">Try a scenario from the panel, or tell us about your order in your own words.</p></div>
            </div>
          )}
          {messages.map((item, index) => (
            <div key={`${index}-${item.role}`} className={`flex ${item.role === "customer" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[88%] rounded-2xl px-4 py-3 text-sm leading-6 ${item.role === "customer" ? "rounded-br-md bg-navy text-white" : "rounded-bl-md border border-slate-200 bg-white text-slate-700"}`}>
                <p>{item.text}</p>
                {item.receipt && <ReceiptCard receipt={item.receipt} requestId={item.id} onAppeal={item.outcome === "denied" || item.outcome === "escalated" ? appeal : undefined} />}
              </div>
            </div>
          ))}
          {loading && <div className="flex items-center gap-2 text-sm text-slate-500"><span className="typing-dot" /><span className="typing-dot delay-1" /><span className="typing-dot delay-2" /> Checking the policy and order details…</div>}
          {error && <p className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}
        </div>
        <form onSubmit={submit} className="border-t border-slate-200 bg-white p-5">
          <div className="flex gap-3">
            <label className="sr-only" htmlFor="message">Describe your refund request</label>
            <textarea id="message" value={message} onChange={(event) => setMessage(event.target.value)} placeholder="What happened with your order?" rows={2} className="min-w-0 flex-1 resize-none rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none transition focus:border-navy focus:ring-2 focus:ring-blue-100" />
            <button disabled={!message.trim() || loading} className="self-end rounded-xl bg-navy px-5 py-3 text-sm font-bold text-white transition hover:bg-[#214a6d] disabled:cursor-not-allowed disabled:opacity-40">Send</button>
          </div>
        </form>
      </section>
      <aside className="space-y-5">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
          <label className="mb-2 block text-xs font-bold uppercase tracking-wide text-slate-500" htmlFor="customer">Sign in as…</label>
          <select id="customer" value={customerId} onChange={(event) => setCustomerId(Number(event.target.value))} className="w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-sm font-semibold outline-none focus:border-navy">
            {customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.name} · {customer.email}</option>)}
          </select>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
          <div className="mb-3 flex items-center justify-between"><h2 className="font-bold text-navy">Scenario picker</h2><span className="text-xs text-slate-400">15 tests</span></div>
          <select value={selectedScenario} onChange={(event) => { const value = event.target.value; setSelectedScenario(value); const scenario = scenarios.find((item) => item.id === value); if (scenario) { setCustomerId(scenario.customer_id); setMessage(scenario.message); } }} className="w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-sm outline-none focus:border-navy">
            <option value="">Choose a demo request…</option>
            {scenarios.map((scenario) => <option key={scenario.id} value={scenario.id}>{scenario.id} · {scenario.expected_outcome}</option>)}
          </select>
          <p className="mt-3 text-xs leading-5 text-slate-500">Each sample is built to exercise a specific safety rule. Pick one, then press Send.</p>
        </div>
        <div className="rounded-2xl border border-blue-100 bg-blue-50 p-5 text-sm leading-6 text-blue-900">
          <p className="font-bold">The trust principle</p>
          <p className="mt-1 text-blue-800">AI can help interpret your message, but deterministic policy code makes the money decision.</p>
        </div>
      </aside>
    </div>
  );
}

function ReceiptCard({ receipt, requestId, onAppeal }: { receipt: Receipt; requestId?: number; onAppeal?: (requestId: number) => void }) {
  return (
    <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4 text-left">
      <div className="flex items-center justify-between gap-3"><span className="text-xs font-bold uppercase tracking-wide text-slate-500">Decision receipt</span><Badge outcome={receipt.outcome} /></div>
      <p className="mt-3 text-lg font-black text-navy">{receipt.outcome === "approved" ? `Refund approved · $${receipt.amount}` : receipt.outcome === "denied" ? "Refund not approved" : "Specialist review requested"}</p>
      <ul className="mt-3 space-y-1.5 text-xs text-slate-600">{receipt.checks.map((check) => <li key={check.label} className="flex gap-2"><span className={check.passed ? "text-emerald-600" : "text-slate-400"}>{check.passed ? "✓" : "–"}</span>{check.label}</li>)}</ul>
      <p className="mt-3 border-t border-slate-200 pt-3 text-xs leading-5 text-slate-500">{receipt.next_step}</p>
      {requestId && onAppeal && <button onClick={() => onAppeal(requestId)} className="mt-3 w-full rounded-lg border border-navy px-3 py-2 text-xs font-bold text-navy hover:bg-white">Ask a human to review this</button>}
      {requestId && <p className="mt-2 text-[10px] font-bold uppercase tracking-wide text-slate-400">Request #{requestId}</p>}
    </div>
  );
}

function AdminPage() {
  const [token, setToken] = useState(() => sessionStorage.getItem("refunddesk-admin") || "");
  const [tokenInput, setTokenInput] = useState(token);
  const [stats, setStats] = useState<Record<string, number | string>>({});
  const [rows, setRows] = useState<RequestRow[]>([]);
  const [selected, setSelected] = useState<RequestDetail | null>(null);
  const [filter, setFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [lab, setLab] = useState<{ pass_rate?: number; passed?: number; total?: number } | null>(null);
  const [simulation, setSimulation] = useState<{ changed_count?: number; exposure_delta?: string; before?: Record<string, number>; after?: Record<string, number> } | null>(null);
  const [error, setError] = useState("");

  const load = async (activeToken = token) => {
    if (!activeToken) return;
    try {
      const [nextStats, nextRows] = await Promise.all([
        api<Record<string, number | string>>("/api/admin/stats", undefined, activeToken),
        api<RequestRow[]>(`/api/admin/requests?review_status=${statusFilter}&q=${encodeURIComponent(filter)}`, undefined, activeToken),
      ]);
      setStats(nextStats); setRows(nextRows); setError("");
    } catch (err) { setError(err instanceof Error ? err.message : "Admin access failed"); }
  };
  useEffect(() => { if (token) void load(); }, [token, statusFilter]);
  const authenticate = (event: FormEvent) => { event.preventDefault(); sessionStorage.setItem("refunddesk-admin", tokenInput); setToken(tokenInput); };
  const runLab = async () => setLab(await api("/api/admin/redteam/run", { method: "POST" }, token));
  const runSimulation = async () => setSimulation(await api("/api/admin/simulate", { method: "POST", body: JSON.stringify({ window_days: 45, review_threshold: 400, repeat_limit: 3 }) }, token));
  const resolve = async (decision: "approved" | "denied") => {
    if (!selected) return;
    await api(`/api/admin/requests/${selected.id}/resolve`, { method: "POST", body: JSON.stringify({ decision, note: "Resolved from the RefundDesk support console." }) }, token);
    setSelected(null); await load();
  };
  if (!token) return <div className="mx-auto max-w-md rounded-3xl border border-slate-200 bg-white p-8 shadow-soft"><p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-500">Support console</p><h1 className="mt-2 text-3xl font-black text-navy">Enter admin token</h1><p className="mt-3 text-sm leading-6 text-slate-500">This demo uses a single token instead of real authentication. The default is <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">admin-demo-token</code>.</p><form onSubmit={authenticate} className="mt-6 flex gap-3"><input type="password" value={tokenInput} onChange={(event) => setTokenInput(event.target.value)} className="min-w-0 flex-1 rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-navy" placeholder="Admin token" /><button className="rounded-xl bg-navy px-4 py-3 font-bold text-white">Open</button></form></div>;
  return (
    <div className="space-y-6">
      <div><p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-500">Operations</p><h1 className="mt-1 text-3xl font-black tracking-tight text-navy">Support console</h1><p className="mt-2 text-sm text-slate-500">Review decisions, inspect the full audit trail, and resolve escalations safely.</p></div>
      {error && <p className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">{[["Total", stats.total || 0], ["Approved", `${stats.approval_rate || 0}%`], ["Denied", `${stats.denial_rate || 0}%`], ["Escalated", `${stats.escalation_rate || 0}%`], ["Refunded", `$${stats.total_refunded || "0.00"}`]].map(([label, value]) => <div key={label} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-soft"><p className="text-xs font-bold uppercase tracking-wide text-slate-400">{label}</p><p className="mt-2 text-2xl font-black text-navy">{value}</p>{label === "Escalated" && <p className="mt-1 text-xs text-amber-700">{stats.pending_queue || 0} pending review</p>}</div>)}</div>
      <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
        <section className="rounded-2xl border border-slate-200 bg-white shadow-soft">
          <div className="flex flex-col gap-3 border-b border-slate-200 p-5 sm:flex-row"><input value={filter} onChange={(event) => setFilter(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void load(); }} placeholder="Search order or message…" className="min-w-0 flex-1 rounded-xl border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-navy" /><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className="rounded-xl border border-slate-300 px-3 py-2.5 text-sm"><option value="">All statuses</option><option value="pending_review">Pending review</option><option value="resolved">Resolved</option><option value="auto">Auto</option></select><button onClick={() => void load()} className="rounded-xl bg-slate-100 px-4 py-2.5 text-sm font-bold text-navy hover:bg-slate-200">Refresh</button></div>
          <div className="overflow-x-auto"><table className="w-full min-w-[680px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-400"><tr><th className="px-5 py-3">Request</th><th className="px-5 py-3">Message</th><th className="px-5 py-3">Outcome</th><th className="px-5 py-3">Status</th><th className="px-5 py-3">Amount</th></tr></thead><tbody className="divide-y divide-slate-100">{rows.map((row) => <tr key={row.id} onClick={() => void api<RequestDetail>(`/api/admin/requests/${row.id}`, undefined, token).then(setSelected)} className="cursor-pointer hover:bg-slate-50"><td className="whitespace-nowrap px-5 py-4 font-bold text-navy">#{row.id}<span className="block text-xs font-normal text-slate-400">{row.order_id || "No order"}</span></td><td className="max-w-[300px] truncate px-5 py-4 text-slate-600">{row.message}</td><td className="px-5 py-4"><Badge outcome={row.outcome} /></td><td className="px-5 py-4 text-xs font-semibold text-slate-500">{row.review_status.replace("_", " ")}</td><td className="px-5 py-4 font-semibold text-slate-700">${row.refund_amount}</td></tr>)}</tbody></table></div>
        </section>
        <aside className="space-y-5">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-soft"><p className="text-xs font-bold uppercase tracking-wide text-slate-400">Trust Lab</p><h2 className="mt-1 text-xl font-black text-navy">Attack the system</h2><p className="mt-2 text-sm leading-6 text-slate-500">Run the built-in attacks through the real pipeline and grade the safety invariants.</p><button onClick={() => void runLab()} className="mt-4 w-full rounded-xl bg-navy px-4 py-3 text-sm font-bold text-white">Run red team</button>{lab && <div className="mt-4 rounded-xl bg-mint p-4"><p className="text-2xl font-black text-emerald-900">{lab.pass_rate}% pass</p><p className="mt-1 text-xs text-emerald-800">{lab.passed} of {lab.total} attacks passed the invariants.</p></div>}</div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-soft"><p className="text-xs font-bold uppercase tracking-wide text-slate-400">Policy simulator</p><h2 className="mt-1 text-xl font-black text-navy">Try a what-if</h2><p className="mt-2 text-sm leading-6 text-slate-500">Replay stored policy snapshots with a 45-day window, $400 review threshold, and compare the exposure.</p><button onClick={() => void runSimulation()} className="mt-4 w-full rounded-xl border border-navy px-4 py-3 text-sm font-bold text-navy hover:bg-slate-50">Simulate change</button>{simulation && <div className="mt-4 rounded-xl bg-sun p-4"><p className="text-lg font-black text-amber-950">{simulation.changed_count} requests would change</p><p className="mt-1 text-xs text-amber-900">Refund exposure: {simulation.exposure_delta}</p></div>}</div>
        </aside>
      </div>
      {selected && <div className="fixed inset-0 z-20 flex justify-end bg-slate-950/30" onClick={() => setSelected(null)}><div className="h-full w-full max-w-xl overflow-y-auto bg-white p-6 shadow-2xl" onClick={(event) => event.stopPropagation()}><div className="flex items-start justify-between"><div><p className="text-xs font-bold uppercase tracking-wide text-slate-400">Audit drawer · #{selected.id}</p><h2 className="mt-1 text-2xl font-black text-navy">{selected.order_id || "Unmatched order"}</h2></div><button onClick={() => setSelected(null)} className="rounded-lg px-3 py-2 text-xl text-slate-400 hover:bg-slate-100">×</button></div><div className="mt-5 flex items-center gap-3"><Badge outcome={selected.outcome} /><span className="text-sm text-slate-500">{selected.review_status.replace("_", " ")}</span></div><div className="mt-6 rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-700"><p className="font-bold text-navy">Customer message</p><p className="mt-1">{selected.message}</p><p className="mt-4 font-bold text-navy">Reply sent</p><p className="mt-1">{selected.customer_reply}</p></div><div className="mt-6 space-y-3"><p className="text-xs font-bold uppercase tracking-wide text-slate-400">Pipeline timeline</p>{selected.audit_events.map((event) => <div key={event.id} className="relative border-l-2 border-slate-200 pl-4"><span className="absolute -left-[5px] top-1 h-2 w-2 rounded-full bg-navy" /><p className="text-sm font-bold text-navy">{event.step.replaceAll("_", " ")}</p><pre className="mt-1 whitespace-pre-wrap break-words text-[11px] leading-5 text-slate-500">{JSON.stringify(event.detail, null, 2)}</pre></div>)}</div>{selected.review_status === "pending_review" && <div className="mt-7 flex gap-3 border-t border-slate-200 pt-5"><button onClick={() => void resolve("approved")} className="flex-1 rounded-xl bg-emerald-600 px-4 py-3 text-sm font-bold text-white">Approve</button><button onClick={() => void resolve("denied")} className="flex-1 rounded-xl bg-rose-600 px-4 py-3 text-sm font-bold text-white">Deny</button></div>}</div></div>}
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState(window.location.pathname === "/admin" ? "admin" : "customer");
  const [aiMode, setAiMode] = useState("mock");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  useEffect(() => { void Promise.all([api<Customer[]>("/api/customers"), api<Scenario[]>("/api/scenarios"), api<{ ai_mode: string }>("/api/health")]).then(([nextCustomers, nextScenarios, health]) => { setCustomers(nextCustomers); setScenarios(nextScenarios); setAiMode(health.ai_mode); }); }, []);
  useEffect(() => { window.history.replaceState({}, "", page === "admin" ? "/admin" : "/"); }, [page]);
  return <Layout page={page} setPage={setPage} aiMode={aiMode}>{page === "admin" ? <AdminPage /> : <CustomerPage customers={customers} scenarios={scenarios} onRefresh={() => undefined} />}</Layout>;
}
