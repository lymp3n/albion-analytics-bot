import React, { useEffect, useMemo, useState } from "https://esm.sh/react@18.3.1";
import { createRoot } from "https://esm.sh/react-dom@18.3.1/client";
import htm from "https://esm.sh/htm@3.1.1";
import { motion, AnimatePresence } from "https://esm.sh/framer-motion@11.3.24";

const html = htm.bind(React.createElement);
const glass = "apple-glass rounded-3xl border border-white/15";
const ease = [0.22, 1, 0.36, 1];
const PRELOAD_KEY = "aa:preload:v5";
const PERIODS = ["1d", "7d", "14d", "30d", "all"];

const fmt = (v) => (Number.isFinite(Number(v)) ? Number(v).toLocaleString() : "—");
const toNum = (v) => (Number.isFinite(Number(v)) ? Number(v) : 0);

function storePreload(data) {
  try { sessionStorage.setItem(PRELOAD_KEY, JSON.stringify(data)); } catch {}
}
function readPreload() {
  try { return JSON.parse(sessionStorage.getItem(PRELOAD_KEY) || "{}"); } catch { return {}; }
}

function periodDays(kind, isEconomy = false) {
  if (kind === "1d") return 1;
  if (kind === "7d") return 7;
  if (kind === "14d") return 14;
  if (kind === "30d") return 30;
  return isEconomy ? 365 : 730;
}

function ChartShell({ title, subtitle, children }) {
  return html`<div className=${`${glass} p-5`}><h3 className="text-lg font-medium">${title}</h3><p className="apple-muted mt-1 text-sm">${subtitle}</p><div className="mt-4">${children}</div></div>`;
}

function HealthStatusCard({ botHealth }) {
  const status = String(botHealth?.signal_status || "unknown").toLowerCase();
  const map = {
    ok: { color: "#34d399", label: "Healthy" },
    warn: { color: "#fbbf24", label: "Warning" },
    down: { color: "#f87171", label: "Down" },
    unknown: { color: "#94a3b8", label: "Unknown" },
  };
  const p = map[status] || map.unknown;
  return html`<div className="${glass} max-w-[360px] p-4">
    <div className="flex items-center gap-2">
      <span className="h-2.5 w-2.5 rounded-full" style=${{ background: p.color }}></span>
      <h4 className="text-sm font-medium">Health summary: ${p.label}</h4>
    </div>
    <p className="apple-muted mt-2 text-sm">${botHealth?.summary || "No summary available."}</p>
  </div>`;
}

function BarChart({ labels = [], values = [], color = "from-cyan-300 to-blue-500", heightClass = "h-[320px]" }) {
  const max = Math.max(1, ...values.map((v) => toNum(v)));
  return html`<div className=${`grid ${heightClass} grid-cols-[repeat(auto-fit,minmax(52px,1fr))] items-end gap-3`}>
    ${values.map((v, i) => {
      const n = toNum(v);
      const h = Math.max(10, Math.round((n / max) * 100));
      return html`<div key=${i} className="group flex flex-col items-center gap-2">
        <div className="text-[11px] text-slate-300">${fmt(n)}</div>
        <div title=${`${labels[i]} (${n})`} className=${`w-full rounded-t-xl bg-gradient-to-t ${color} transition-all duration-300 group-hover:scale-y-105`} style=${{ height: `${h}%` }}></div>
        <div className="text-center text-[11px] text-slate-400">${labels[i]}</div>
      </div>`;
    })}
  </div>`;
}

function LineChart({ labels = [], values = [], stroke = "#7dd3fc", fill = "rgba(125,211,252,.14)" }) {
  const nums = values.map((v) => toNum(v));
  const max = Math.max(1, ...nums);
  const min = Math.min(0, ...nums);
  const W = 860;
  const H = 300;
  const pts = nums.map((n, i) => {
    const x = nums.length === 1 ? 0 : (i / (nums.length - 1)) * W;
    const y = H - ((n - min) / (max - min || 1)) * H;
    return [x, y];
  });
  const poly = pts.map((p) => `${p[0]},${p[1]}`).join(" ");
  const area = `0,${H} ${poly} ${W},${H}`;
  // Simple tooltip (fast, no DOM measuring beyond container width)
  const [hoverIdx, setHoverIdx] = useState(null);
  const [hoverX, setHoverX] = useState(0);
  const onMove = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (e.clientX - r.left) / Math.max(1, r.width)));
    const idx = nums.length <= 1 ? 0 : Math.round(x * (nums.length - 1));
    setHoverIdx(idx);
    setHoverX((idx / Math.max(1, nums.length - 1)) * 100);
  };
  const onLeave = () => setHoverIdx(null);
  return html`<div className="relative h-[320px] w-full overflow-hidden rounded-xl border border-white/10 bg-white/[0.03]" onMouseMove=${onMove} onMouseLeave=${onLeave}>
    ${hoverIdx != null ? html`<div className="pointer-events-none absolute z-10 -translate-x-1/2 rounded-xl border border-white/15 bg-[#0f0f16]/90 px-3 py-2 text-xs text-slate-100 shadow-lg" style=${{ left: `${hoverX}%`, top: "10px" }}>
      <div className="text-[11px] uppercase tracking-[0.12em] text-slate-300">${labels[hoverIdx] || `#${hoverIdx + 1}`}</div>
      <div className="mt-1 text-sm font-medium">${fmt(nums[hoverIdx])}</div>
    </div>` : null}
    <svg viewBox="0 0 ${W} ${H}" className="h-full w-full" preserveAspectRatio="none">
      <polyline points=${area} fill=${fill}></polyline>
      <polyline points=${poly} fill="none" stroke=${stroke} stroke-width="3"></polyline>
      ${pts.map((p, i) => html`<g key=${i}><circle cx=${p[0]} cy=${p[1]} r="4.5" fill=${stroke}></circle></g>`)}
    </svg>
  </div>`;
}

function AreaChart({ labels = [], values = [] }) {
  // More distinct than Line: softer stroke, no dots (handled by LineChart), stronger fill.
  return html`<${LineChart} labels=${labels} values=${values} stroke="rgba(196,181,253,0.72)" fill="rgba(196,181,253,.34)" />`;
}

function HeatmapChart({ xLabels = [], yLabels = [], matrix = [], colorA = "34,211,238", colorB = "168,85,247" }) {
  const flat = matrix.flat().map((v) => toNum(v));
  const min = Math.min(...flat, 0);
  const max = Math.max(1, ...flat);
  const scale = (v) => (toNum(v) - min) / (max - min || 1);
  return html`<div className="w-full">
    <div className="mb-2 grid gap-2" style=${{ gridTemplateColumns: `140px repeat(${xLabels.length}, minmax(0,1fr))` }}>
      <div></div>
      ${xLabels.map((x, i) => html`<div key=${i} className="text-center text-[11px] text-slate-400">${x}</div>`)}
    </div>
    ${yLabels.map((y, yi) => html`<div key=${yi} className="mb-2 grid gap-2" style=${{ gridTemplateColumns: `140px repeat(${xLabels.length}, minmax(0,1fr))` }}>
      <div className="pr-2 text-right text-[11px] text-slate-300">${y}</div>
      ${(matrix[yi] || []).map((v, xi) => {
        const k = scale(v);
        return html`<div key=${xi} title=${`${y} / ${xLabels[xi]}: ${fmt(v)}`} className="h-9 rounded-md border border-white/10 text-center text-[11px] leading-9 text-white" style=${{ background: `linear-gradient(135deg, rgba(${colorA},${0.16 + k * 0.52}), rgba(${colorB},${0.12 + k * 0.45}))` }}>${fmt(v)}</div>`;
      })}
    </div>`)}
  </div>`;
}

function CustomGraph({ title, subtitle, metricsMap, defaultPeriod = "7d", id }) {
  const metricKeys = Object.keys(metricsMap || {});
  const [selected, setSelected] = useState(metricKeys);
  const [period, setPeriod] = useState(defaultPeriod);
  const [kind, setKind] = useState("line");

  useEffect(() => { setSelected(metricKeys); }, [id]);

  const labels = selected;
  const values = selected.map((k) => toNum(metricsMap[k]?.[period] ?? metricsMap[k]?.["7d"] ?? 0));

  const toggleMetric = (m) => setSelected((prev) => (prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m]));

  const chart = kind === "bar"
    ? html`<${BarChart} labels=${labels} values=${values} color="from-cyan-300 to-blue-500" />`
    : kind === "area"
      ? html`<${AreaChart} labels=${labels} values=${values} />`
      : html`<${LineChart} labels=${labels} values=${values} />`;

  return html`<${ChartShell} title=${title} subtitle=${subtitle}>
    <div className="mb-4 grid gap-3 lg:grid-cols-[1fr_auto_auto]">
      <div className="flex flex-wrap gap-2">
        ${metricKeys.map((m) => html`<button key=${m} className=${`rounded-full border px-3 py-1 text-xs ${selected.includes(m) ? "border-cyan-300/70 bg-cyan-300/15 text-cyan-100" : "border-white/15 bg-white/5 text-slate-300"}`} onClick=${() => toggleMetric(m)}>${m}</button>`)}
      </div>
      <select className="apple-control-input apple-select-contrast rounded-xl px-3 py-2 text-sm" value=${period} onChange=${(e) => setPeriod(e.target.value)}>
        ${PERIODS.map((p) => html`<option key=${p} value=${p}>${p}</option>`)}
      </select>
      <select className="apple-control-input apple-select-contrast rounded-xl px-3 py-2 text-sm" value=${kind} onChange=${(e) => setKind(e.target.value)}>
        <option value="line">Line Chart</option>
        <option value="bar">Bar Chart</option>
        <option value="area">Area Chart</option>
      </select>
    </div>
    <${motion.div} key=${`${kind}-${period}-${selected.join(",")}`} initial=${{ opacity: 0, y: 10 }} animate=${{ opacity: 1, y: 0 }} transition=${{ duration: 0.24, ease }}>
      ${chart}
      <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400"><span>Y: metric value</span><span>X: selected metrics</span></div>
    </${motion.div}>
  </${ChartShell}>`;
}

function DataTable({ columns, rows }) {
  return html`<div className="${glass} apple-scrollbar overflow-auto"><table className="apple-data-table w-full min-w-[760px] border-collapse"><thead><tr>${columns.map((c) => html`<th key=${c} className="border-b border-white/10 px-3 py-2 text-left text-xs uppercase tracking-[0.12em] text-slate-300">${c}</th>`)}</tr></thead><tbody>${rows.length ? rows.map((r, i) => html`<tr key=${i} className="apple-row-transition border-b border-white/5">${r.map((cell, ci) => html`<td key=${ci} className="px-3 py-2 text-sm text-slate-100">${String(cell ?? "—")}</td>`)}</tr>`) : html`<tr><td colSpan=${columns.length} className="px-3 py-6 text-sm text-slate-400">No data</td></tr>`}</tbody></table></div>`;
}

function PreviewModal({ open, close, title, children }) {
  return html`<${AnimatePresence}>${open && html`<${motion.div} className="fixed inset-0 z-[90] flex items-center justify-center bg-black/65 p-4" initial=${{ opacity: 0 }} animate=${{ opacity: 1 }} exit=${{ opacity: 0 }} onClick=${close}><${motion.div} className=${`${glass} max-h-[90vh] w-full max-w-6xl overflow-auto p-6 apple-scrollbar`} initial=${{ opacity: 0, scale: 0.97, y: 18 }} animate=${{ opacity: 1, scale: 1, y: 0 }} exit=${{ opacity: 0, scale: 0.98, y: 18 }} transition=${{ duration: 0.26, ease }} onClick=${(e) => e.stopPropagation()}><div className="mb-5 flex items-center justify-between"><h3 className="text-2xl font-medium">${title}</h3><button className="apple-control-btn rounded-xl px-3 py-2 text-sm" onClick=${close}>Close</button></div>${children}</${motion.div}></${motion.div}>`}<//>`;
}

function Loader({ done, progress, phase }) {
  return html`<${AnimatePresence}>${!done && html`<${motion.div} className="fixed inset-0 z-[120] overflow-hidden bg-[#0b0b0f]" initial=${{ opacity: 1 }} exit=${{ opacity: 0 }}>
    <${motion.div} className="absolute inset-x-0 top-0 h-1/2 bg-gradient-to-b from-[#111118] to-[#0d0d12]" initial=${{ y: 0 }} exit=${{ y: "-100%" }} transition=${{ duration: 0.9, ease }} />
    <${motion.div} className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-[#111118] to-[#0d0d12]" initial=${{ y: 0 }} exit=${{ y: "100%" }} transition=${{ duration: 0.9, ease }} />
    <div className="absolute inset-0 flex flex-col items-center justify-center px-5">
      <${motion.h1}
        className="apple-preload-title apple-kern-title text-center text-4xl font-semibold text-slate-100 md:text-6xl"
        initial=${{ opacity: 0, y: 8 }}
        animate=${{ opacity: 1, y: 0 }}
        transition=${{ duration: 0.6, ease }}
      >Albion Analytics</${motion.h1}>
      <${motion.div}
        className="mt-2 h-[2px] w-[min(520px,78vw)] rounded-full bg-gradient-to-r from-cyan-300/0 via-cyan-300/70 to-fuchsia-300/0"
        initial=${{ scaleX: 0 }}
        animate=${{ scaleX: 1 }}
        transition=${{ duration: 0.9, ease }}
        style=${{ transformOrigin: "50% 50%" }}
      />
      <p className="mt-4 text-center text-xs uppercase tracking-[0.17em] text-slate-400">${phase}</p>
      <div className="mt-8 w-[min(640px,92vw)]">
        <div className="h-2 overflow-hidden rounded-full border border-white/20 bg-white/5">
          <div className="h-full rounded-full bg-gradient-to-r from-cyan-300 via-blue-400 to-fuchsia-400 transition-[width] duration-300 ease-out" style=${{ width: `${Math.max(4, Math.min(100, progress))}%` }}></div>
        </div>
        <div className="mt-2 flex justify-end text-[11px] text-slate-400">${Math.round(progress)}%</div>
      </div>
    </div>
  </${motion.div}>`}<//>`;
}

function Sidebar({ items, active, setActive }) {
  const [open, setOpen] = useState(true);
  return html`<div className=${`${glass} h-fit p-3 apple-soft-gap`}><button onClick=${() => setOpen((v) => !v)} className="apple-control-btn w-full rounded-xl px-3 py-2 text-left text-sm">${open ? "Hide categories" : "Show categories"}</button>${open ? html`<div className="mt-3 space-y-2">${items.map((item) => html`<button key=${item.id} onClick=${() => setActive(item.id)} className=${`w-full rounded-xl px-3 py-2 text-left text-sm apple-transition ${active === item.id ? "bg-blue-500/25 text-white" : "bg-white/5 text-slate-200 hover:bg-white/10"}`}>${item.label}</button>`)}</div>` : null}</div>`;
}

function getMainMetrics(preload, period) {
  const p = preload?.main?.[period] || preload?.main?.["7d"] || {};
  const ov = p.overview || {};
  const ev = p.events || {};
  const sys = p.system || {};
  return {
    "tickets_open": toNum(ov.tickets_open),
    "tickets_closed": toNum(ov.tickets_closed_period),
    "sessions": toNum(ov.sessions_period),
    "events_closed": toNum(ov.events_period),
    "events_cta": toNum(ov.events_period_cta),
    "participants": toNum(ev.unique_participants_period),
    "db_latency_ms": toNum(sys.db_query_ms),
  };
}

function getEconMetrics(preload, period) {
  const p = preload?.econ?.[period] || preload?.econ?.["7d"] || {};
  const k = p.kpis || {};
  const rep = p.reports || {};
  return {
    "cash_balance": toNum(k.cash_balance ?? rep.balance_snapshot?.cash_balance),
    "energy_balance": toNum(k.energy_balance ?? rep.balance_snapshot?.energy_balance),
    "pending_entries": toNum(k.pending_entries),
    "open_alerts": toNum(k.open_alerts),
    "pnl_income": toNum(rep.pnl_summary?.income_total),
    "pnl_expense": toNum(rep.pnl_summary?.expense_total),
    "cashflow_net": toNum(rep.cashflow_summary?.net_cashflow),
  };
}

function metricsByPeriod(preload, getter) {
  const out = {};
  Object.keys(getter(preload, "7d")).forEach((metric) => {
    out[metric] = {};
    PERIODS.forEach((p) => { out[metric][p] = getter(preload, p)[metric] ?? 0; });
  });
  return out;
}

async function fetchJsonWithTimeout(url, timeoutMs) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, { credentials: "same-origin", signal: ctrl.signal });
    return await res.json();
  } finally {
    clearTimeout(t);
  }
}

async function preloadAll(onProgress) {
  const pack = { main: {}, econ: {}, errors: [] };
  const total = PERIODS.length;
  let done = 0;

  // Load each period with timeout; never block indefinitely.
  for (const p of PERIODS) {
    const dMain = periodDays(p, false);
    const dEcon = periodDays(p, true);
    try {
      const [main, econ] = await Promise.all([
        fetchJsonWithTimeout(`/dashboard/api/data?days=${dMain}`, 12000),
        fetchJsonWithTimeout(`/dashboard/api/economy/data?days=${dEcon}`, 12000),
      ]);
      pack.main[p] = main;
      pack.econ[p] = econ;
    } catch (e) {
      pack.errors.push({ period: p, error: String(e?.message || e) });
      pack.main[p] = pack.main[p] || {};
      pack.econ[p] = pack.econ[p] || {};
    } finally {
      done += 1;
      if (typeof onProgress === "function") onProgress(done / total);
    }
  }
  return pack;
}

function Landing() {
  const [ready, setReady] = useState(false);
  const [phase, setPhase] = useState("Boot");
  const [progress, setProgress] = useState(2);
  useEffect(() => {
    let alive = true;
    (async () => {
      setPhase("Preloading all metric periods");
      const pack = await preloadAll((ratio) => {
        // Smooth non-stalling progress, always converges to 98 while working.
        setProgress((prev) => {
          const target = Math.min(98, 6 + ratio * 92);
          return prev + (target - prev) * 0.18;
        });
      });
      storePreload(pack);
      if (!alive) return;
      setProgress(100);
      setPhase("Reveal");
      setTimeout(() => setReady(true), 260);
    })().catch(() => setReady(true));
    return () => { alive = false; };
  }, []);
  const cards = [
    { title: "Main Dashboard", href: "/dashboard/main", desc: "Guild operations, players, events, system analytics." },
    { title: "Economy Dashboard", href: "/dashboard/economy", desc: "Accounting, routing, armory, imports and audit." },
  ];
  return html`<div className="apple-shell min-h-screen"><${Loader} done=${ready} progress=${progress} phase=${phase} /><div className="pt-16 text-center"><h1 className="apple-kern-title text-5xl font-medium md:text-6xl">Albion Analytics</h1><p className="apple-muted mt-3 text-lg">Choose your dashboard</p></div><div className="mt-16 grid gap-8 md:grid-cols-2">${cards.map((c, i) => html`<${motion.a} key=${c.title} href=${c.href} className=${`${glass} apple-card-ceramic apple-floating-card apple-neon-card relative block min-h-[460px] overflow-hidden p-10 no-underline text-center`} initial=${{ y: 70, opacity: 0 }} animate=${ready ? { y: 0, opacity: 1 } : { y: 70, opacity: 0 }} transition=${{ duration: 0.34, delay: 0.14 * (i + 1), ease }} whileHover=${{ scale: 1.02 }}><div className="relative z-10 flex h-full flex-col items-center justify-center"><h2 className="apple-kern-title text-4xl font-medium">${c.title}</h2><p className="apple-muted mt-5 max-w-md text-base leading-relaxed">${c.desc}</p></div></${motion.a}>`)}</div></div>`;
}

function MainDashboard() {
  const [active, setActive] = useState("overview");
  const [days, setDays] = useState(7);
  const [guildId, setGuildId] = useState("");
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);
  const [preview, setPreview] = useState(false);
  const [playersExpanded, setPlayersExpanded] = useState(false);
  const preload = readPreload();

  const load = async ({ force = false } = {}) => {
    setLoading(true);
    const pKey = days === 1 ? "1d" : days === 7 ? "7d" : days === 14 ? "14d" : days === 30 ? "30d" : "all";
    const cached = preload?.main?.[pKey];
    if (!force && cached?.ok) { setData(cached); setLoading(false); return; }
    const qs = new URLSearchParams({ days: String(days) });
    if (guildId) qs.set("guild_id", guildId);
    const out = await fetch(`/dashboard/api/data?${qs.toString()}`, { credentials: "same-origin" }).then((r) => r.json());
    setData(out || {});
    setLoading(false);
  };
  useEffect(() => { load(); }, [days, guildId]);

  const o = data.overview || {};
  const events = data.events || {};
  const playersRows = (data.players || []).map((p) => [p.nickname, p.guild_name || "—", p.status, p.sessions_count, Number(p.avg_score || 0).toFixed(2), p.tickets_open ?? 0]);
  const ticketsRows = (data.tickets?.recent || []).map((t) => [t.id, t.status, t.player_nick || "—", t.mentor_nick || "—", t.created_at || "—"]);
  const eventsRows = (events.per_content || []).map((e) => [e.content_name || "—", e.events_count ?? 0, e.avg_players_per_event ?? "—", e.unique_players_on_content ?? 0]);
  const metricMap = metricsByPeriod(preload, getMainMetrics);
  const botHealth = data.system?.bot_health || {};

  const body = useMemo(() => {
    if (loading) return html`<p className="apple-muted">Loading…</p>`;
    if (data.ok === false) return html`<p className="text-rose-300">${data.error || "Error"}</p>`;
    if (active === "overview") {
      return html`<${CustomGraph} id="main-overview-custom" title="Main custom analytics graph" subtitle="Select metrics, period and chart type. Defaults: all metrics + 7d + line." metricsMap=${metricMap} defaultPeriod="7d" /><div className="mt-4"><${HealthStatusCard} botHealth=${botHealth} /></div>`;
    }
    if (active === "tickets") return html`<${DataTable} columns=${["ID", "Status", "Player", "Mentor", "Created"]} rows=${ticketsRows} />`;
    if (active === "events") return html`<${DataTable} columns=${["Content", "Events", "Avg players", "Unique players"]} rows=${eventsRows} />`;
    if (active === "system") return html`<div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4"><div className="${glass} p-4"><p className="text-xs uppercase tracking-[0.13em] text-slate-300">Bot signal</p><p className="mt-2 text-2xl font-medium">${botHealth.signal_status || "unknown"}</p></div><div className="${glass} p-4"><p className="text-xs uppercase tracking-[0.13em] text-slate-300">DB latency</p><p className="mt-2 text-2xl font-medium">${fmt(data.system?.db_query_ms)} ms</p></div><div className="${glass} p-4"><p className="text-xs uppercase tracking-[0.13em] text-slate-300">HTTP uptime</p><p className="mt-2 text-2xl font-medium">${fmt(data.system?.http_server_uptime_s)} s</p></div><div className="${glass} p-4"><p className="text-xs uppercase tracking-[0.13em] text-slate-300">Python</p><p className="mt-2 text-2xl font-medium">${data.system?.python_version || "—"}</p></div></div><div className="mt-4"><${HealthStatusCard} botHealth=${botHealth} /></div>`;
    const shownRows = playersRows.slice(0, playersExpanded ? playersRows.length : 5);
    return html`<div className="${glass} p-5"><p className="mb-3 text-sm font-medium">Register player</p><div className="grid gap-3 md:grid-cols-2"><input id="reg-nick" className="apple-control-input rounded-xl px-3 py-2 text-sm" placeholder="Nickname" /><input id="reg-username" className="apple-control-input rounded-xl px-3 py-2 text-sm" placeholder="Discord username" /><input id="reg-discord-id" className="apple-control-input rounded-xl px-3 py-2 text-sm" type="number" min="1" placeholder="Discord ID" /><select id="reg-status" className="apple-control-input apple-select-contrast rounded-xl px-3 py-2 text-sm"><option value="pending">pending</option><option value="active">active</option><option value="mentor">mentor</option><option value="founder">founder</option></select><button className="apple-control-btn rounded-xl px-3 py-2 text-sm" onClick=${async () => { const nick = document.getElementById("reg-nick")?.value || ""; const user = document.getElementById("reg-username")?.value || ""; const did = Number(document.getElementById("reg-discord-id")?.value || 0); const status = document.getElementById("reg-status")?.value || "pending"; const gid = Number(guildId || data.guilds?.[0]?.id || 0); await fetch("/dashboard/api/players/register", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nickname: nick, discord_username: user, discord_id: did, guild_id: gid, status }) }); load({ force: true }); }}>Register player</button></div></div><div className="${glass} mt-4 p-4"><button className="flex w-full items-center justify-between rounded-xl bg-white/5 px-3 py-2 text-left text-sm" onClick=${() => setPlayersExpanded((v) => !v)}><span>Players list (${playersRows.length})</span><span className=${`transition-transform duration-300 ${playersExpanded ? "rotate-180" : "rotate-0"}`}>⌄</span></button></div><${DataTable} columns=${["Nickname", "Guild", "Status", "Sessions", "Avg", "Open tickets"]} rows=${shownRows} />`;
  }, [active, data, loading, playersExpanded, guildId]);

  return html`<div className="apple-shell min-h-screen"><header className=${`${glass} mb-4 p-4`}><h1 className="apple-kern-title text-3xl font-medium">Main Dashboard</h1><p className="apple-muted text-sm">Design QA pass</p></header><div className=${`${glass} mb-4 flex flex-wrap items-center gap-3 p-4`}><label className="text-sm text-slate-200">Days <input className="ml-2 apple-control-input w-20 rounded-xl px-2 py-1" type="number" min="1" max="730" value=${days} onChange=${(e) => setDays(Number(e.target.value || 7))} /></label>${(data.guilds || []).length ? html`<label className="text-sm text-slate-200">Guild <select className="ml-2 apple-control-input apple-select-contrast rounded-xl px-2 py-1" value=${guildId} onChange=${(e) => setGuildId(e.target.value)}><option value="">All</option>${(data.guilds || []).map((g) => html`<option key=${g.id} value=${String(g.id)}>${g.display_name || g.name || "Guild"}</option>`)}</select></label>` : null}<button className="apple-control-btn rounded-xl px-3 py-2 text-sm" onClick=${() => load({ force: true })}>Refresh</button><div className="ml-auto flex gap-2"><a className="apple-control-btn rounded-xl px-3 py-2 text-sm text-white no-underline" href="/dashboard">Picker</a><a className="apple-control-btn rounded-xl px-3 py-2 text-sm text-white no-underline" href="/dashboard/economy">Economy</a></div></div><div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]"><${Sidebar} items=${[{ id: "overview", label: "Overview" }, { id: "players", label: "Players" }, { id: "tickets", label: "Tickets" }, { id: "events", label: "Events" }, { id: "system", label: "System" }]} active=${active} setActive=${setActive} /><section className="space-y-4">${body}</section></div><${PreviewModal} open=${preview} close=${() => setPreview(false)} title="Detailed main analytics"><p className="apple-muted text-sm">Use Overview custom graph controls for deep metric comparison.</p></${PreviewModal}></div>`;
}

function EconomyDashboard() {
  const [active, setActive] = useState("overview");
  const [days, setDays] = useState(7);
  const [entryStatus, setEntryStatus] = useState("");
  const [category, setCategory] = useState("");
  const [source, setSource] = useState("");
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);
  const [preview, setPreview] = useState(false);
  const [opMsg, setOpMsg] = useState("");
  const [importOpen, setImportOpen] = useState(false);
  const [importLogType, setImportLogType] = useState("bank");
  const [importSmartMerge, setImportSmartMerge] = useState(true);
  const [importContent, setImportContent] = useState("");
  const [armorySheetUrl, setArmorySheetUrl] = useState("");
  const [buybackPrice, setBuybackPrice] = useState("");
  const [regear, setRegear] = useState({ player_name: "", content_type: "", unit_cost: "", note: "" });
  const preload = readPreload();

  const load = async ({ force = false } = {}) => {
    setLoading(true);
    const pKey = days === 1 ? "1d" : days === 7 ? "7d" : days === 14 ? "14d" : days === 30 ? "30d" : "all";
    const cached = preload?.econ?.[pKey];
    if (!force && cached?.ok) { setData(cached); setLoading(false); return; }
    const qs = new URLSearchParams({ days: String(days), entry_status: entryStatus, category, source });
    const out = await fetch(`/dashboard/api/economy/data?${qs.toString()}`, { credentials: "same-origin" }).then((r) => r.json());
    setData(out || {});
    setLoading(false);
  };
  useEffect(() => { load(); }, [days, entryStatus, category, source]);

  const post = async (url, payload) => {
    setOpMsg("Sending...");
    try {
      const out = await fetch(url, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then((r) => r.json());
      if (!out.ok) throw new Error(out.error || "Request failed");
      setOpMsg("Saved successfully.");
      load({ force: true });
    } catch (e) {
      setOpMsg(String(e.message || e));
    }
  };

  const runSmartImport = async () => {
    setOpMsg("Importing...");
    try {
      const out = await fetch("/dashboard/api/economy/import-log", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ log_type: importLogType, content: importContent, smart_merge: importSmartMerge }),
      }).then((r) => r.json());
      if (!out.ok) throw new Error(out.error || "Import failed");
      setOpMsg("Import OK.");
      setImportOpen(false);
      load({ force: true });
    } catch (e) {
      setOpMsg(String(e.message || e));
    }
  };

  const importArmoryFromSheet = async () => {
    setOpMsg("Fetching sheet...");
    try {
      const out = await fetch("/dashboard/api/economy/armory-import-sheet", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sheet_url: armorySheetUrl, actor: "dashboard_admin" }),
      }).then((r) => r.json());
      if (!out.ok) throw new Error(out.error || "Sheet import failed");
      setOpMsg("Armory import OK.");
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
  const metricMap = metricsByPeriod(preload, getEconMetrics);

  const panel = useMemo(() => {
    if (loading) return html`<p className="apple-muted">Loading…</p>`;
    if (data.ok === false) return html`<p className="text-rose-300">${data.error || "Error"}</p>`;
    if (active === "overview") {
      return html`
        <${CustomGraph} id="econ-overview-custom" title="Economy custom analytics graph" subtitle="Main graph: choose metrics, period and chart type. Defaults: all + 7d + line." metricsMap=${metricMap} defaultPeriod="7d" />
        <div className="mt-5 grid gap-5 xl:grid-cols-2">
          <${ChartShell} title="Operational pressure" subtitle="Entries, alerts, approvals">
            <${BarChart} labels=${["Pending entries", "Alerts", "Approvals"]} values=${[k.pending_entries || 0, (data.alerts || []).length, (data.pending_approvals || []).length]} color="from-cyan-300 to-blue-500" heightClass="h-[220px]" />
          </${ChartShell}>
          <${ChartShell} title="Risk heatmap" subtitle="Cross-metric risk surface">
            <${HeatmapChart}
              xLabels=${["alerts", "discrepancies", "approvals", "entries"]}
              yLabels=${["live queue", "review queue"]}
              matrix=${[
                [(data.alerts || []).length, (data.discrepancies || []).length, (data.pending_approvals || []).length, k.pending_entries || 0],
                [(data.alerts || []).filter((x) => String(x.status || "").toLowerCase() !== "ack").length, (data.discrepancies || []).filter((x) => String(x.status || "").toLowerCase() !== "resolved").length, (data.pending_approvals || []).length, (data.entries || []).filter((x) => String(x.status || "").toLowerCase() !== "posted").length],
              ]}
              colorA="245,158,11"
              colorB="236,72,153"
            />
          </${ChartShell}>
        </div>
      `;
    }
    if (active === "entries") return html`<${DataTable} columns=${["ID", "Category", "Amount", "Status", "Created"]} rows=${entriesRows} />`;
    if (active === "armory") return html`<${DataTable} columns=${["Item", "Item ID", "Qty", "Target", "Deficit"]} rows=${armoryRows} />`;
    if (active === "alerts") return html`<${DataTable} columns=${["ID", "Severity", "Status", "Message"]} rows=${alertsRows} />`;
    if (active === "routing") return html`<${DataTable} columns=${["Category", "Debit", "Credit", "Auto"]} rows=${routesRows} />`;
    if (active === "imports") return html`<${DataTable} columns=${["ID", "Source", "Rows", "Created"]} rows=${importsRows} />`;
    if (active === "approvals") return html`<${DataTable} columns=${["ID", "Category", "Amount", "Status"]} rows=${pendingRows} />`;
    if (active === "discrepancies") return html`<${DataTable} columns=${["ID", "Kind", "Status", "Delta"]} rows=${discrepanciesRows} />`;
    if (active === "audit") return html`<${DataTable} columns=${["ID", "Actor", "Action", "Created"]} rows=${auditRows} />`;
    if (active === "reports") return html`<div className="grid gap-5 xl:grid-cols-2"><${ChartShell} title="P&L structure" subtitle="Income/expense/profit"><${BarChart} labels=${["Income", "Expense", "Profit"]} values=${[rep.pnl_summary?.income_total || 0, rep.pnl_summary?.expense_total || 0, rep.pnl_summary?.profit_total || 0]} color="from-emerald-300 to-teal-500" /></${ChartShell}><${ChartShell} title="Cashflow pattern" subtitle="Cash in/out/net"><${LineChart} labels=${["Cash in", "Cash out", "Net"]} values=${[rep.cashflow_summary?.cash_in_total || 0, rep.cashflow_summary?.cash_out_total || 0, rep.cashflow_summary?.net_cashflow || 0]} stroke="#f9a8d4" fill="rgba(249,168,212,.16)" /></${ChartShell}></div>`;
    return html`<div className="grid gap-5 xl:grid-cols-2">
      <div className="${glass} p-5">
        <h3 className="text-sm font-medium">Operations</h3>
        <div className="mt-3 grid gap-3">
          <button className="apple-control-btn rounded-xl px-3 py-2 text-sm" onClick=${() => setImportOpen(true)}>Smart import (log)</button>
          <div className="${glass} p-4">
            <p className="text-sm font-medium">Armory import from Google Sheets</p>
            <p className="apple-muted mt-1 text-xs">Paste public sheet URL. Use File → Share → Anyone with link, or publish.</p>
            <input className="apple-control-input mt-3 w-full rounded-xl px-3 py-2 text-sm" placeholder="https://docs.google.com/spreadsheets/..." value=${armorySheetUrl} onChange=${(e) => setArmorySheetUrl(e.target.value)} />
            <button className="apple-control-btn mt-3 rounded-xl px-3 py-2 text-sm" onClick=${importArmoryFromSheet}>Import armory</button>
          </div>
        </div>
      </div>
      <div className="${glass} p-5">
        <h3 className="text-sm font-medium">Loot buyback</h3>
        <input className="apple-control-input mt-3 w-full rounded-xl px-3 py-2 text-sm" type="number" min="1" placeholder="Buyback price" value=${buybackPrice} onChange=${(e) => setBuybackPrice(e.target.value)} />
        <button className="apple-control-btn mt-3 rounded-xl px-3 py-2 text-sm" onClick=${() => post("/dashboard/api/economy/loot-buyback", { buyback_price: Number(buybackPrice || 0), approved_by: "dashboard_admin" })}>Create buyback</button>
        <h3 className="mt-6 text-sm font-medium">Regear request</h3>
        <input className="apple-control-input mt-3 w-full rounded-xl px-3 py-2 text-sm" placeholder="Player nickname" value=${regear.player_name} onChange=${(e) => setRegear((v) => ({ ...v, player_name: e.target.value }))} />
        <input className="apple-control-input mt-2 w-full rounded-xl px-3 py-2 text-sm" placeholder="Content type" value=${regear.content_type} onChange=${(e) => setRegear((v) => ({ ...v, content_type: e.target.value }))} />
        <input className="apple-control-input mt-2 w-full rounded-xl px-3 py-2 text-sm" type="number" min="1" placeholder="Unit cost" value=${regear.unit_cost} onChange=${(e) => setRegear((v) => ({ ...v, unit_cost: e.target.value }))} />
        <textarea className="apple-control-input mt-2 w-full rounded-xl px-3 py-2 text-sm" rows="3" placeholder="Note" value=${regear.note} onChange=${(e) => setRegear((v) => ({ ...v, note: e.target.value }))}></textarea>
        <button className="apple-control-btn mt-3 rounded-xl px-3 py-2 text-sm" onClick=${() => post("/dashboard/api/economy/regear", { ...regear, unit_cost: Number(regear.unit_cost || 0), action: "create" })}>Create regear</button>
        ${opMsg ? html`<p className="apple-muted mt-3 text-sm">${opMsg}</p>` : null}
      </div>
      <${PreviewModal} open=${importOpen} close=${() => setImportOpen(false)} title="Smart import (economy log)">
        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-sm">Log type
            <select className="apple-control-input apple-select-contrast mt-2 w-full rounded-xl px-3 py-2 text-sm" value=${importLogType} onChange=${(e) => setImportLogType(e.target.value)}>
              <option value="bank">bank</option>
              <option value="market">market</option>
              <option value="loot">loot</option>
              <option value="other">other</option>
            </select>
          </label>
          <label className="text-sm">Smart merge
            <select className="apple-control-input apple-select-contrast mt-2 w-full rounded-xl px-3 py-2 text-sm" value=${importSmartMerge ? "1" : "0"} onChange=${(e) => setImportSmartMerge(e.target.value === "1")}>
              <option value="1">on</option>
              <option value="0">off</option>
            </select>
          </label>
        </div>
        <label className="mt-4 block text-sm">CSV content (paste from Google Sheets export or game log)</label>
        <textarea className="apple-control-input mt-2 w-full rounded-xl px-3 py-2 text-sm" rows="10" value=${importContent} onChange=${(e) => setImportContent(e.target.value)} placeholder="Paste CSV here..."></textarea>
        <div className="mt-4 flex gap-2">
          <button className="apple-control-btn rounded-xl px-3 py-2 text-sm" onClick=${runSmartImport}>Run import</button>
          <button className="apple-control-btn rounded-xl px-3 py-2 text-sm" onClick=${() => setImportOpen(false)}>Cancel</button>
        </div>
        ${opMsg ? html`<p className="apple-muted mt-3 text-sm">${opMsg}</p>` : null}
      </${PreviewModal}>
    </div>`;
  }, [active, data, loading, opMsg, buybackPrice, regear]);

  return html`<div className="apple-shell min-h-screen"><header className=${`${glass} mb-4 p-4`}><h1 className="apple-kern-title text-3xl font-medium">Economy Dashboard</h1><p className="apple-muted text-sm">Design QA pass</p></header><div className=${`${glass} mb-4 flex flex-wrap items-center gap-3 p-4`}><label className="text-sm">Days <input className="ml-2 apple-control-input w-20 rounded-xl px-2 py-1" type="number" min="1" max="365" value=${days} onChange=${(e) => setDays(Number(e.target.value || 7))} /></label><label className="text-sm">Status <input className="ml-2 apple-control-input w-32 rounded-xl px-2 py-1" value=${entryStatus} onChange=${(e) => setEntryStatus(e.target.value)} placeholder="pending/posted" /></label><label className="text-sm">Category <input className="ml-2 apple-control-input w-36 rounded-xl px-2 py-1" value=${category} onChange=${(e) => setCategory(e.target.value)} placeholder="regear" /></label><label className="text-sm">Source <input className="ml-2 apple-control-input w-36 rounded-xl px-2 py-1" value=${source} onChange=${(e) => setSource(e.target.value)} placeholder="dashboard" /></label><button className="apple-control-btn rounded-xl px-3 py-2 text-sm" onClick=${() => load({ force: true })}>Refresh</button><div className="ml-auto flex gap-2"><a className="apple-control-btn rounded-xl px-3 py-2 text-sm text-white no-underline" href="/dashboard">Picker</a><a className="apple-control-btn rounded-xl px-3 py-2 text-sm text-white no-underline" href="/dashboard/main">Main</a></div></div><div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]"><${Sidebar} items=${[{ id: "overview", label: "Overview" }, { id: "entries", label: "Entries" }, { id: "operations", label: "Operations" }, { id: "armory", label: "Armory" }, { id: "reports", label: "Reports" }, { id: "alerts", label: "Alerts" }, { id: "routing", label: "Routing" }, { id: "imports", label: "Imports" }, { id: "approvals", label: "Approvals" }, { id: "discrepancies", label: "Discrepancies" }, { id: "audit", label: "Audit" }]} active=${active} setActive=${setActive} /><section className="space-y-4">${panel}</section></div><${PreviewModal} open=${preview} close=${() => setPreview(false)} title="Economy detailed overview"><p className="apple-muted text-sm">Overview contains main customizable graph and priority heatmaps for speed and control-plane clarity.</p></${PreviewModal}></div>`;
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
