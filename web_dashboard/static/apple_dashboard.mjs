import React, { useEffect, useMemo, useState } from "https://esm.sh/react@18.3.1";
import { createRoot } from "https://esm.sh/react-dom@18.3.1/client";
import htm from "https://esm.sh/htm@3.1.1";
import { motion, AnimatePresence } from "https://esm.sh/framer-motion@11.3.24";

const html = htm.bind(React.createElement);
const spring = { type: "spring", stiffness: 130, damping: 17, mass: 0.8 };
const cardEase = [0.21, 1, 0.22, 1];
const glass = "apple-glass rounded-3xl border border-white/15";
const CACHE_MAIN = "aa:preload:main:v2";
const CACHE_ECON = "aa:preload:econ:v2";

function safeJson(v) {
  return JSON.stringify(v ?? {}, null, 2);
}

function writeCached(key, data) {
  try {
    sessionStorage.setItem(key, JSON.stringify({ ts: Date.now(), data }));
  } catch {}
}

function readCached(key) {
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) return null;
    return JSON.parse(raw)?.data || null;
  } catch {
    return null;
  }
}

function spark(values = [], color = "from-cyan-300 to-blue-500") {
  const arr = values.filter((v) => Number.isFinite(Number(v))).map((v) => Number(v));
  const max = Math.max(...arr, 1);
  return html`<div className="flex h-24 items-end gap-1.5">
    ${arr.length
      ? arr.map((v, i) => html`<div key=${i} className=${`w-full rounded-t-md bg-gradient-to-t ${color}`} style=${{ height: `${Math.max(8, Math.round((v / max) * 100))}%`, opacity: 0.56 + i / (arr.length * 1.8) }}></div>`)
      : html`<div className="text-xs text-slate-400">No chart data</div>`}
  </div>`;
}

function Loader({ done, phaseText, progress }) {
  return html`
    <${AnimatePresence}>
      ${!done &&
      html`<${motion.div} className="fixed inset-0 z-[100] flex items-center justify-center bg-[#0a0a0e]" initial=${{ opacity: 1 }} exit=${{ opacity: 0, transition: { duration: 0.8, ease: cardEase } }}>
        <div className="relative h-44 w-44">
          <${motion.div} className="absolute inset-0 rounded-full border border-cyan-200/40" animate=${{ rotate: 360 }} transition=${{ repeat: Infinity, duration: 2.1, ease: "linear" }} />
          <${motion.div} className="absolute inset-5 rounded-full border border-blue-400/40" animate=${{ rotate: -360, scale: [1, 1.04, 1] }} transition=${{ repeat: Infinity, duration: 2.8, ease: "linear" }} />
          <div className="absolute inset-11 rounded-full bg-white/5 backdrop-blur-3xl"></div>
          <p className="absolute -bottom-10 left-1/2 -translate-x-1/2 text-xs tracking-[0.18em] uppercase text-slate-300">${phaseText}</p>
        </div>
        <div className="absolute bottom-[18vh] left-1/2 w-[min(520px,88vw)] -translate-x-1/2">
          <div className="mb-2 text-center text-xs tracking-[0.15em] uppercase text-slate-300">Loading both dashboards</div>
          <div className="h-2 overflow-hidden rounded-full border border-cyan-200/30 bg-white/10">
            <div className="h-full rounded-full bg-gradient-to-r from-cyan-300 via-blue-400 to-fuchsia-400 transition-all duration-200" style=${{ width: `${Math.max(4, Math.min(100, progress))}%` }}></div>
          </div>
        </div>
      </${motion.div}>`}
    <//>
  `;
}

function Sidebar({ items, active, setActive }) {
  const [open, setOpen] = useState(true);
  return html`
    <div className=${`${glass} h-fit p-3 apple-soft-gap`}>
      <button onClick=${() => setOpen((v) => !v)} className="apple-control-btn w-full rounded-xl px-3 py-2 text-left text-sm">${open ? "Hide categories" : "Show categories"}</button>
      <${AnimatePresence} initial=${false}>
        ${open &&
        html`<${motion.div} initial=${{ height: 0, opacity: 0 }} animate=${{ height: "auto", opacity: 1 }} exit=${{ height: 0, opacity: 0 }} transition=${{ duration: 0.35, ease: cardEase }} className="overflow-hidden">
          <div className="mt-3 space-y-2">
            ${items.map((item) => html`<button key=${item.id} onClick=${() => setActive(item.id)} className=${`w-full rounded-xl px-3 py-2 text-left text-sm apple-transition ${active === item.id ? "bg-blue-500/25 text-white" : "bg-white/5 text-slate-200 hover:bg-white/10"}`}>${item.label}</button>`)}
          </div>
        </${motion.div}>`}
      <//>
    </div>
  `;
}

function Metric({ label, value }) {
  return html`<${motion.div} className=${`${glass} p-4`} initial=${{ opacity: 0, y: 14, scale: 0.98 }} whileInView=${{ opacity: 1, y: 0, scale: 1 }} viewport=${{ once: true, amount: 0.3 }} transition=${spring} whileHover=${{ scale: 1.02, y: -2 }}>
    <p className="apple-muted text-[11px] uppercase tracking-[0.16em]">${label}</p>
    <p className="mt-2 text-2xl font-medium">${value}</p>
  </${motion.div}>`;
}

function DataTable({ columns, rows }) {
  return html`<div className="${glass} apple-scrollbar overflow-auto"><table className="w-full min-w-[640px] border-collapse"><thead><tr>${columns.map((c) => html`<th key=${c} className="border-b border-white/10 px-3 py-2 text-left text-xs uppercase tracking-[0.12em] text-slate-300">${c}</th>`)}</tr></thead><tbody>${rows.length ? rows.map((r, i) => html`<tr key=${i} className="apple-row-transition border-b border-white/5">${r.map((cell, ci) => html`<td key=${ci} className="px-3 py-2 text-sm text-slate-100">${String(cell ?? "—")}</td>`)}</tr>`) : html`<tr><td colSpan=${columns.length} className="px-3 py-5 text-sm text-slate-400">No data</td></tr>`}</tbody></table></div>`;
}

function PreviewModal({ open, close, title, children }) {
  return html`<${AnimatePresence}>${open &&
    html`<${motion.div} className="fixed inset-0 z-[90] flex items-center justify-center bg-black/62 p-4" initial=${{ opacity: 0 }} animate=${{ opacity: 1 }} exit=${{ opacity: 0 }} onClick=${close}>
      <${motion.div} className=${`${glass} max-h-[85vh] w-full max-w-3xl overflow-auto p-5 apple-scrollbar`} initial=${{ opacity: 0, scale: 0.96, y: 20 }} animate=${{ opacity: 1, scale: 1, y: 0 }} exit=${{ opacity: 0, scale: 0.98, y: 20 }} transition=${{ ...spring, damping: 22 }} onClick=${(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between"><h3 className="text-xl font-medium">${title}</h3><button className="apple-control-btn rounded-xl px-3 py-2 text-sm" onClick=${close}>Close</button></div>${children}
      </${motion.div}>
    </${motion.div}>`}
  <//>`;
}

function Landing() {
  const [ready, setReady] = useState(false);
  const [phase, setPhase] = useState("Boot sequence");
  const [progress, setProgress] = useState(2);
  useEffect(() => {
    let alive = true;
    const started = performance.now();
    const minDurationMs = 2300;
    const tick = () => {
      if (!alive) return;
      setProgress((v) => Math.min(92, v + 0.8));
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
    const preload = async () => {
      setPhase("Preloading main analytics");
      const pMain = fetch("/dashboard/api/data?days=30", { credentials: "same-origin" }).then((r) => r.json());
      setPhase("Preloading economy analytics");
      const pEcon = fetch("/dashboard/api/economy/data?days=30", { credentials: "same-origin" }).then((r) => r.json());
      const [main, econ] = await Promise.allSettled([pMain, pEcon]);
      if (main.status === "fulfilled") writeCached(CACHE_MAIN, main.value);
      if (econ.status === "fulfilled") writeCached(CACHE_ECON, econ.value);
      const elapsed = performance.now() - started;
      if (elapsed < minDurationMs) await new Promise((r) => setTimeout(r, minDurationMs - elapsed));
      if (!alive) return;
      setPhase("Preparing cinematic reveal");
      setProgress(100);
      setTimeout(() => setReady(true), 250);
    };
    preload().catch(() => setReady(true));
    return () => { alive = false; };
  }, []);
  const cards = [
    { title: "Main Dashboard", href: "/dashboard/main", desc: "Guild operations, tickets, events and health snapshots." },
    { title: "Economy Dashboard", href: "/dashboard/economy", desc: "Accounting, armory, reconciliation and economy controls." },
  ];
  return html`<div className="apple-shell min-h-screen">
    <${Loader} done=${ready} phaseText=${phase} progress=${progress} />
    <div className="pt-16 text-center"><h1 className="apple-kern-title text-5xl font-medium md:text-6xl">Albion Analytics</h1><p className="apple-muted mt-3 text-lg">Choose your dashboard</p></div>
    <div className="mt-16 grid gap-6 md:grid-cols-2">
      ${cards.map((card, i) => html`<${motion.a} key=${card.title} href=${card.href} className=${`${glass} apple-card-ceramic apple-floating-card apple-neon-card relative block min-h-[430px] overflow-hidden p-8 no-underline text-center`} initial=${{ y: 74, opacity: 0 }} animate=${ready ? { y: 0, opacity: 1 } : { y: 74, opacity: 0 }} transition=${{ ...spring, delay: 0.12 * (i + 1) }} whileHover=${{ scale: 1.02, y: -2 }} whileTap=${{ scale: 0.992 }}>
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/15 via-transparent to-violet-500/10"></div>
        <div className="relative z-10 flex h-full flex-col items-center justify-center"><h2 className="apple-kern-title text-3xl font-medium">${card.title}</h2><p className="apple-muted mt-4 max-w-sm text-base leading-relaxed">${card.desc}</p></div>
      </${motion.a}>`)}
    </div>
  </div>`;
}

function MainDashboard() {
  const [active, setActive] = useState("overview");
  const [days, setDays] = useState(30);
  const [guildId, setGuildId] = useState("");
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);
  const [preview, setPreview] = useState(null);
  const [playersExpanded, setPlayersExpanded] = useState(false);
  const load = async ({ force = false } = {}) => {
    setLoading(true);
    if (!force) {
      const c = readCached(CACHE_MAIN);
      if (c?.ok) { setData(c); setLoading(false); return; }
    }
    const qs = new URLSearchParams({ days: String(days) });
    if (guildId) qs.set("guild_id", guildId);
    try {
      const res = await fetch(`/dashboard/api/data?${qs.toString()}`, { credentials: "same-origin" });
      const out = await res.json();
      setData(out || {});
      writeCached(CACHE_MAIN, out || {});
    } catch {
      setData({ ok: false, error: "Failed to load dashboard data." });
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, [days, guildId]);
  const o = data.overview || {};
  const playersRows = (data.players || []).map((p) => [p.nickname, p.guild_name || "—", p.status, p.sessions_count, Number(p.avg_score || 0).toFixed(2), p.tickets_open ?? 0]);
  const ticketsRows = (data.tickets?.recent || []).map((t) => [t.id, t.status, t.player_nick || "—", t.mentor_nick || "—", t.created_at || "—"]);
  const eventsRows = (data.events?.per_content || []).map((e) => [e.content_name || "—", e.events_count ?? 0, e.avg_players_per_event ?? "—", e.unique_players_on_content ?? 0]);
  const items = [{ id: "overview", label: "Overview" }, { id: "players", label: "Players" }, { id: "tickets", label: "Tickets" }, { id: "events", label: "Events" }, { id: "system", label: "System" }];
  const body = useMemo(() => {
    if (loading) return html`<p className="apple-muted">Loading…</p>`;
    if (data.ok === false) return html`<p className="text-rose-300">${data.error || "Error"}</p>`;
    if (active === "tickets") return html`<${DataTable} columns=${["ID", "Status", "Player", "Mentor", "Created"]} rows=${ticketsRows} />`;
    if (active === "events") return html`<${DataTable} columns=${["Content", "Events", "Avg players", "Unique players"]} rows=${eventsRows} />`;
    if (active === "system") {
      const s = data.system || {};
      const bh = s.bot_health || {};
      return html`<div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4"><${Metric} label="Bot signal" value=${bh.signal_status || "unknown"} /><${Metric} label="DB latency (ms)" value=${s.db_query_ms ?? "—"} /><${Metric} label="HTTP uptime (s)" value=${s.http_server_uptime_s ?? "—"} /><${Metric} label="Python" value=${s.python_version || "—"} /></div><div className="grid gap-4 xl:grid-cols-2"><div className="${glass} p-4"><p className="text-sm font-medium">Bot health summary</p><p className="apple-muted mt-2 text-sm">${bh.summary || "No summary"}</p></div><div className="${glass} p-4"><p className="mb-2 text-xs uppercase tracking-[0.13em] text-emerald-200">Database footprint</p>${spark([s.db_used_mb || 0, s.db_free_mb_estimate || 0, s.db_used_pct_of_quota || 0], "from-emerald-300 to-cyan-500")}</div></div>`;
    }
    if (active === "players") {
      const showRows = playersRows.slice(0, playersExpanded ? playersRows.length : 5);
      return html`<div className="${glass} p-4"><div className="grid gap-3 md:grid-cols-2"><input id="reg-nick" className="apple-control-input rounded-xl px-3 py-2 text-sm" placeholder="Nickname" /><input id="reg-username" className="apple-control-input rounded-xl px-3 py-2 text-sm" placeholder="Discord username" /><input id="reg-discord-id" className="apple-control-input rounded-xl px-3 py-2 text-sm" type="number" min="1" placeholder="Discord ID" /><select id="reg-status" className="apple-control-input rounded-xl px-3 py-2 text-sm"><option value="pending">pending</option><option value="active">active</option><option value="mentor">mentor</option><option value="founder">founder</option></select><button className="apple-control-btn rounded-xl px-3 py-2 text-sm" onClick=${async () => { const nick = document.getElementById("reg-nick")?.value || ""; const user = document.getElementById("reg-username")?.value || ""; const did = Number(document.getElementById("reg-discord-id")?.value || 0); const status = document.getElementById("reg-status")?.value || "pending"; const gid = Number(guildId || data.guilds?.[0]?.id || 0); await fetch("/dashboard/api/players/register", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nickname: nick, discord_username: user, discord_id: did, guild_id: gid, status }) }); load({ force: true }); }}>Register player</button><button className="apple-control-btn rounded-xl px-3 py-2 text-sm" onClick=${() => setPlayersExpanded((v) => !v)}>${playersExpanded ? "Collapse to 5" : "Expand all"}</button></div></div><${DataTable} columns=${["Nickname", "Guild", "Status", "Sessions", "Avg", "Open tickets"]} rows=${showRows} />`;
    }
    return html`<div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4"><${Metric} label="Tickets Open" value=${o.tickets_open ?? "—"} /><${Metric} label="Sessions 30d" value=${o.sessions_period ?? "—"} /><${Metric} label="Closed Events" value=${o.events_period ?? "—"} /><${Metric} label="Closed CTA" value=${o.events_period_cta ?? "—"} /></div><div className="grid gap-4 xl:grid-cols-2"><div className="${glass} p-4"><p className="mb-2 text-xs uppercase tracking-[0.13em] text-cyan-200">Tickets vs Sessions</p>${spark([o.tickets_open || 0, o.tickets_closed_period || 0, o.sessions_period || 0, o.events_period || 0], "from-cyan-300 to-blue-500")}</div><div className="${glass} p-4"><p className="mb-2 text-xs uppercase tracking-[0.13em] text-fuchsia-200">Event Participation</p>${spark([data.events?.events_in_period || 0, data.events?.unique_participants_period || 0, data.events?.cta_events_in_period || 0, data.events?.cta_unique_participants_period || 0], "from-fuchsia-300 to-violet-500")}</div></div><div className="mt-2 grid gap-4 md:grid-cols-2 xl:grid-cols-4">${["players", "tickets", "events", "system"].map((k) => html`<${motion.button} key=${k} onClick=${() => setPreview(k)} className=${`${glass} p-4 text-left`} whileHover=${{ scale: 1.02 }} whileTap=${{ scale: 0.99 }}><p className="text-sm font-medium capitalize">${k}</p><p className="apple-muted mt-2 text-xs">Quick view in modal</p></${motion.button}>`)}</div>`;
  }, [active, data, loading, playersExpanded, guildId]);
  return html`<div className="apple-shell min-h-screen"><header className=${`${glass} mb-4 p-4`}><h1 className="apple-kern-title text-3xl font-medium">Main Dashboard</h1><p className="apple-muted text-sm">Visual-first analytics shell</p></header><div className=${`${glass} mb-4 flex flex-wrap items-center gap-3 p-4`}><label className="text-sm text-slate-200">Days <input className="ml-2 apple-control-input w-20 rounded-xl px-2 py-1" type="number" min="1" max="365" value=${days} onChange=${(e) => setDays(Number(e.target.value || 30))} /></label>${(data.guilds || []).length ? html`<label className="text-sm text-slate-200">Guild <select className="ml-2 apple-control-input rounded-xl px-2 py-1" value=${guildId} onChange=${(e) => setGuildId(e.target.value)}><option value="">All</option>${(data.guilds || []).map((g) => html`<option key=${g.id} value=${String(g.id)}>${g.display_name || g.name || "Guild"}</option>`)}</select></label>` : null}<button className="apple-control-btn rounded-xl px-3 py-2 text-sm" onClick=${() => load({ force: true })}>Refresh</button><div className="ml-auto flex gap-2"><a className="apple-control-btn rounded-xl px-3 py-2 text-sm text-white no-underline" href="/dashboard">Picker</a><a className="apple-control-btn rounded-xl px-3 py-2 text-sm text-white no-underline" href="/dashboard/economy">Economy</a></div></div><div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]"><${Sidebar} items=${items} active=${active} setActive=${setActive} /><section className="space-y-4">${body}</section></div><${PreviewModal} open=${!!preview} close=${() => setPreview(null)} title=${`Preview: ${preview || ""}`}><div className="grid gap-4 md:grid-cols-2"><div className="${glass} p-4"><p className="mb-2 text-xs uppercase tracking-[0.13em] text-cyan-200">Values</p>${spark([o.tickets_open || 0, o.sessions_period || 0, o.events_period || 0], "from-cyan-300 to-blue-500")}</div><div className="${glass} p-4"><p className="text-sm font-medium capitalize">${preview}</p><p className="apple-muted mt-2 text-sm">Focused summary preview (visual mode).</p></div></div></${PreviewModal}></div>`;
}

function EconomyDashboard() {
  const [active, setActive] = useState("overview");
  const [days, setDays] = useState(30);
  const [entryStatus, setEntryStatus] = useState("");
  const [category, setCategory] = useState("");
  const [source, setSource] = useState("");
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);
  const [preview, setPreview] = useState(false);
  const [opMsg, setOpMsg] = useState("");
  const [buybackPrice, setBuybackPrice] = useState("");
  const [regear, setRegear] = useState({ player_name: "", content_type: "", unit_cost: "", note: "" });
  const load = async ({ force = false } = {}) => {
    setLoading(true);
    if (!force) {
      const c = readCached(CACHE_ECON);
      if (c?.ok) { setData(c); setLoading(false); return; }
    }
    const qs = new URLSearchParams({ days: String(days), entry_status: entryStatus, category, source });
    try {
      const res = await fetch(`/dashboard/api/economy/data?${qs.toString()}`, { credentials: "same-origin" });
      const out = await res.json();
      setData(out || {});
      writeCached(CACHE_ECON, out || {});
    } catch {
      setData({ ok: false, error: "Failed to load economy data." });
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, [days, entryStatus, category, source]);
  const post = async (url, payload) => {
    setOpMsg("Sending...");
    try {
      const res = await fetch(url, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const out = await res.json();
      if (!out.ok) throw new Error(out.error || "Request failed");
      setOpMsg("Saved successfully.");
      load({ force: true });
    } catch (e) {
      setOpMsg(String(e.message || e));
    }
  };
  const k = data.kpis || {};
  const rep = data.reports || {};
  const entriesRows = (data.entries || []).slice(0, 80).map((e) => [e.id, e.category || e.entry_type || "—", e.amount ?? "—", e.status || "—", e.created_at || e.ts || "—"]);
  const armoryRows = (data.armory_stock || []).slice(0, 100).map((s) => [s.item_name || "—", s.item_id || "—", s.qty ?? 0, s.target_qty ?? 0, s.deficit_abs ?? 0]);
  const alertsRows = (data.alerts || []).slice(0, 80).map((a) => [a.id, a.severity || "—", a.status || "—", a.message || a.title || "—"]);
  const routesRows = (data.routing_rules || []).slice(0, 80).map((r) => [r.category || r.op_type || "—", r.debit_account || "—", r.credit_account || "—", r.auto_post ? "yes" : "no"]);
  const importsRows = (data.imports || []).slice(0, 80).map((i) => [i.id, i.source || "—", i.rows_count ?? 0, i.created_at || "—"]);
  const pendingRows = (data.pending_approvals || []).slice(0, 80).map((p) => [p.id, p.category || "—", p.amount ?? "—", p.status || "—"]);
  const discrepanciesRows = (data.discrepancies || []).slice(0, 80).map((d) => [d.id, d.kind || d.category || "—", d.status || "—", d.delta_amount ?? "—"]);
  const auditRows = (data.audit_trail || []).slice(0, 80).map((a) => [a.id, a.actor || "—", a.action || "—", a.created_at || "—"]);
  const tabs = [{ id: "overview", label: "Overview" }, { id: "entries", label: "Entries" }, { id: "operations", label: "Operations" }, { id: "armory", label: "Armory" }, { id: "reports", label: "Reports" }, { id: "alerts", label: "Alerts" }, { id: "routing", label: "Routing" }, { id: "imports", label: "Imports" }, { id: "approvals", label: "Approvals" }, { id: "discrepancies", label: "Discrepancies" }, { id: "audit", label: "Audit" }];
  const panel = useMemo(() => {
    if (loading) return html`<p className="apple-muted">Loading…</p>`;
    if (data.ok === false) return html`<p className="text-rose-300">${data.error || "Error"}</p>`;
    if (active === "entries") return html`<${DataTable} columns=${["ID", "Category", "Amount", "Status", "Created"]} rows=${entriesRows} />`;
    if (active === "armory") return html`<${DataTable} columns=${["Item", "Item ID", "Qty", "Target", "Deficit"]} rows=${armoryRows} />`;
    if (active === "alerts") return html`<${DataTable} columns=${["ID", "Severity", "Status", "Message"]} rows=${alertsRows} />`;
    if (active === "routing") return html`<${DataTable} columns=${["Category", "Debit", "Credit", "Auto"]} rows=${routesRows} />`;
    if (active === "imports") return html`<${DataTable} columns=${["ID", "Source", "Rows", "Created"]} rows=${importsRows} />`;
    if (active === "approvals") return html`<${DataTable} columns=${["ID", "Category", "Amount", "Status"]} rows=${pendingRows} />`;
    if (active === "discrepancies") return html`<${DataTable} columns=${["ID", "Kind", "Status", "Delta"]} rows=${discrepanciesRows} />`;
    if (active === "audit") return html`<${DataTable} columns=${["ID", "Actor", "Action", "Created"]} rows=${auditRows} />`;
    if (active === "reports") return html`<div className="grid gap-4 xl:grid-cols-2"><div className="${glass} p-4"><p className="mb-2 text-xs uppercase tracking-[0.13em] text-emerald-200">P&L dynamics</p>${spark([rep.pnl_summary?.income_total || 0, rep.pnl_summary?.expense_total || 0, rep.pnl_summary?.profit_total || 0], "from-emerald-300 to-teal-500")}</div><div className="${glass} p-4"><p className="mb-2 text-xs uppercase tracking-[0.13em] text-fuchsia-200">Cashflow dynamics</p>${spark([rep.cashflow_summary?.cash_in_total || 0, rep.cashflow_summary?.cash_out_total || 0, rep.cashflow_summary?.net_cashflow || 0], "from-fuchsia-300 to-violet-500")}</div><pre className="${glass} apple-scrollbar overflow-auto p-4 text-xs">${safeJson(rep.pnl_summary)}</pre><pre className="${glass} apple-scrollbar overflow-auto p-4 text-xs">${safeJson(rep.cashflow_summary)}</pre></div>`;
    if (active === "operations") return html`<div className="grid gap-4 xl:grid-cols-2"><div className="${glass} p-4"><h3 className="text-sm font-medium">Loot buyback</h3><input className="apple-control-input mt-3 w-full rounded-xl px-3 py-2 text-sm" type="number" min="1" placeholder="Buyback price" value=${buybackPrice} onChange=${(e) => setBuybackPrice(e.target.value)} /><button className="apple-control-btn mt-3 rounded-xl px-3 py-2 text-sm" onClick=${() => post("/dashboard/api/economy/loot-buyback", { buyback_price: Number(buybackPrice || 0), approved_by: "dashboard_admin" })}>Create buyback</button></div><div className="${glass} p-4"><h3 className="text-sm font-medium">Regear request</h3><input className="apple-control-input mt-3 w-full rounded-xl px-3 py-2 text-sm" placeholder="Player nickname" value=${regear.player_name} onChange=${(e) => setRegear((v) => ({ ...v, player_name: e.target.value }))} /><input className="apple-control-input mt-2 w-full rounded-xl px-3 py-2 text-sm" placeholder="Content type" value=${regear.content_type} onChange=${(e) => setRegear((v) => ({ ...v, content_type: e.target.value }))} /><input className="apple-control-input mt-2 w-full rounded-xl px-3 py-2 text-sm" type="number" min="1" placeholder="Unit cost" value=${regear.unit_cost} onChange=${(e) => setRegear((v) => ({ ...v, unit_cost: e.target.value }))} /><textarea className="apple-control-input mt-2 w-full rounded-xl px-3 py-2 text-sm" rows="3" placeholder="Note" value=${regear.note} onChange=${(e) => setRegear((v) => ({ ...v, note: e.target.value }))}></textarea><button className="apple-control-btn mt-3 rounded-xl px-3 py-2 text-sm" onClick=${() => post("/dashboard/api/economy/regear", { ...regear, unit_cost: Number(regear.unit_cost || 0), action: "create" })}>Create regear</button></div></div>${opMsg ? html`<p className="apple-muted mt-3 text-sm">${opMsg}</p>` : null}`;
    return html`<div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4"><${Metric} label="Cash Balance" value=${k.cash_balance ?? rep.balance_snapshot?.cash_balance ?? "—"} /><${Metric} label="Energy Balance" value=${k.energy_balance ?? rep.balance_snapshot?.energy_balance ?? "—"} /><${Metric} label="Pending Entries" value=${k.pending_entries ?? "—"} /><${Metric} label="Open Alerts" value=${k.open_alerts ?? "—"} /></div><div className="mt-4 grid gap-4 xl:grid-cols-3"><div className="${glass} p-4"><p className="mb-2 text-xs uppercase tracking-[0.13em] text-cyan-200">Entries / alerts / approvals</p>${spark([k.pending_entries || 0, (data.alerts || []).length, (data.pending_approvals || []).length], "from-cyan-300 to-blue-500")}</div><div className="${glass} p-4"><p className="mb-2 text-xs uppercase tracking-[0.13em] text-amber-200">Armory pressure</p>${spark((data.armory_stock || []).slice(0, 8).map((x) => Number(x.deficit_abs || 0)), "from-amber-300 to-orange-500")}</div><div className="${glass} p-4"><p className="mb-2 text-xs uppercase tracking-[0.13em] text-emerald-200">Treasury split</p>${spark([rep.balance_snapshot?.cash_balance || 0, rep.balance_snapshot?.energy_balance || 0], "from-emerald-300 to-teal-500")}</div></div><div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">${["Operations", "Entries", "Armory", "Reports", "Alerts", "Snapshot"].map((name) => html`<${motion.button} key=${name} className=${`${glass} p-4 text-left`} whileHover=${{ scale: 1.02, y: -2 }} whileTap=${{ scale: 0.99 }} onClick=${() => setPreview(true)}><p className="text-sm font-medium">${name}</p><p className="apple-muted mt-2 text-xs">Open focused detail in modal</p></${motion.button}>`)}</div>`;
  }, [active, data, loading, opMsg, buybackPrice, regear]);
  return html`<div className="apple-shell min-h-screen"><header className=${`${glass} mb-4 p-4`}><h1 className="apple-kern-title text-3xl font-medium">Economy Dashboard</h1><p className="apple-muted text-sm">Visual parity pass for economy operations</p></header><div className=${`${glass} mb-4 flex flex-wrap items-center gap-3 p-4`}><label className="text-sm">Days <input className="ml-2 apple-control-input w-20 rounded-xl px-2 py-1" type="number" min="1" max="365" value=${days} onChange=${(e) => setDays(Number(e.target.value || 30))} /></label><label className="text-sm">Status <input className="ml-2 apple-control-input w-32 rounded-xl px-2 py-1" value=${entryStatus} onChange=${(e) => setEntryStatus(e.target.value)} placeholder="pending/posted" /></label><label className="text-sm">Category <input className="ml-2 apple-control-input w-36 rounded-xl px-2 py-1" value=${category} onChange=${(e) => setCategory(e.target.value)} placeholder="regear" /></label><label className="text-sm">Source <input className="ml-2 apple-control-input w-36 rounded-xl px-2 py-1" value=${source} onChange=${(e) => setSource(e.target.value)} placeholder="dashboard" /></label><button className="apple-control-btn rounded-xl px-3 py-2 text-sm" onClick=${() => load({ force: true })}>Refresh</button><div className="ml-auto flex gap-2"><a className="apple-control-btn rounded-xl px-3 py-2 text-sm text-white no-underline" href="/dashboard">Picker</a><a className="apple-control-btn rounded-xl px-3 py-2 text-sm text-white no-underline" href="/dashboard/main">Main</a></div></div><div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]"><${Sidebar} items=${tabs} active=${active} setActive=${setActive} /><section className="space-y-4">${panel}</section></div><${PreviewModal} open=${preview} close=${() => setPreview(false)} title="Economy quick overview"><div className="grid gap-4 md:grid-cols-2"><div className="${glass} p-4"><p className="mb-2 text-xs uppercase tracking-[0.13em] text-cyan-200">Core balances</p>${spark([k.cash_balance || 0, k.energy_balance || 0, k.pending_entries || 0], "from-cyan-300 to-blue-500")}</div><div className="${glass} p-4"><p className="mb-2 text-xs uppercase tracking-[0.13em] text-fuchsia-200">Risk lanes</p>${spark([(data.alerts || []).length, (data.discrepancies || []).length, (data.pending_approvals || []).length], "from-fuchsia-300 to-violet-500")}</div></div></${PreviewModal}></div>`;
}

function mount() {
  const rootEl = document.getElementById("apple-root");
  if (!rootEl) return;
  const page = rootEl.dataset.page || "landing";
  const root = createRoot(rootEl);
  if (page === "main") root.render(html`<${MainDashboard} />`);
  else if (page === "economy") root.render(html`<${EconomyDashboard} />`);
  else root.render(html`<${Landing} />`);
}

mount();
