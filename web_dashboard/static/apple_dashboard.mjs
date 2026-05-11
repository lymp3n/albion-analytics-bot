import React, { useEffect, useMemo, useState } from "https://esm.sh/react@18.3.1";
import { createRoot } from "https://esm.sh/react-dom@18.3.1/client";
import htm from "https://esm.sh/htm@3.1.1";
import { motion, AnimatePresence } from "https://esm.sh/framer-motion@11.3.24";

const html = htm.bind(React.createElement);
const spring = { type: "spring", stiffness: 125, damping: 16, mass: 0.85 };
const ease = [0.22, 1, 0.36, 1];
const glass = "apple-glass rounded-3xl border border-white/15";
const CACHE_MAIN = "aa:preload:main:v3";
const CACHE_ECON = "aa:preload:econ:v3";

const fmt = (v) => (Number.isFinite(Number(v)) ? Number(v).toLocaleString() : "—");
const pct = (v) => (Number.isFinite(Number(v)) ? `${Number(v).toFixed(1)}%` : "—");

function writeCached(key, data) {
  try { sessionStorage.setItem(key, JSON.stringify({ ts: Date.now(), data })); } catch {}
}
function readCached(key) {
  try { return JSON.parse(sessionStorage.getItem(key) || "{}")?.data || null; } catch { return null; }
}

function ChartCard({ title, subtitle, type, legend = [], children, height = "h-[320px]" }) {
  return html`
    <${motion.section}
      className=${`${glass} p-5 ${height}`}
      initial=${{ opacity: 0, y: 16 }}
      whileInView=${{ opacity: 1, y: 0 }}
      viewport=${{ once: true, amount: 0.2 }}
      transition=${spring}
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.14em] text-slate-300">${type}</p>
          <h3 className="mt-1 text-base font-medium">${title}</h3>
          <p className="apple-muted mt-1 text-xs">${subtitle}</p>
        </div>
        ${legend.length
          ? html`<div className="flex flex-wrap items-center gap-2">
              ${legend.map((l, i) => html`<span key=${i} className="rounded-full border border-white/15 px-2 py-1 text-[11px]">${l}</span>`)}
            </div>`
          : null}
      </div>
      ${children}
    </${motion.section}>
  `;
}

function AxisHint({ left = "min", right = "max", bottom = "categories" }) {
  return html`<div className="mt-2 flex items-center justify-between text-[11px] text-slate-400"><span>Y: ${left} - ${right}</span><span>X: ${bottom}</span></div>`;
}

function BarChart({ labels = [], values = [], color = "from-cyan-300 to-blue-500" }) {
  const max = Math.max(1, ...values.map((v) => Number(v) || 0));
  return html`
    <div className="grid h-[210px] grid-cols-[repeat(auto-fit,minmax(40px,1fr))] items-end gap-3">
      ${values.map((v, i) => {
        const num = Number(v) || 0;
        const h = Math.max(8, Math.round((num / max) * 100));
        return html`<div key=${i} className="group flex flex-col items-center gap-2">
          <div className="text-[11px] text-slate-300">${fmt(num)}</div>
          <div title=${`${labels[i] || "item"}: ${fmt(num)}`} className=${`w-full rounded-t-xl bg-gradient-to-t ${color} shadow-[0_8px_24px_rgba(0,0,0,.35)] transition-all duration-300 group-hover:scale-y-105`} style=${{ height: `${h}%` }}></div>
          <div className="line-clamp-2 text-center text-[11px] text-slate-400">${labels[i] || `#${i + 1}`}</div>
        </div>`;
      })}
    </div>
  `;
}

function LineChart({ labels = [], values = [], stroke = "#7dd3fc", fill = "rgba(125,211,252,.16)" }) {
  const nums = values.map((v) => Number(v) || 0);
  const max = Math.max(1, ...nums);
  const min = Math.min(...nums, 0);
  const w = 660;
  const h = 230;
  const points = nums.map((v, i) => {
    const x = nums.length === 1 ? 0 : (i / (nums.length - 1)) * w;
    const y = h - ((v - min) / (max - min || 1)) * h;
    return [x, y];
  });
  const poly = points.map((p) => `${p[0]},${p[1]}`).join(" ");
  const area = `0,${h} ${poly} ${w},${h}`;
  return html`
    <div className="h-[230px] w-full overflow-hidden rounded-xl border border-white/10 bg-white/[0.03]">
      <svg viewBox="0 0 ${w} ${h}" className="h-full w-full">
        <polyline points=${area} fill=${fill}></polyline>
        <polyline points=${poly} fill="none" stroke=${stroke} stroke-width="3"></polyline>
        ${points.map((p, i) => html`<g key=${i}>
          <circle cx=${p[0]} cy=${p[1]} r="4.5" fill=${stroke}></circle>
          <title>${labels[i] || `#${i + 1}`}: ${fmt(nums[i])}</title>
        </g>`)}
      </svg>
    </div>
  `;
}

function StackedAreaChart({ labels = [], series = [] }) {
  const w = 700;
  const h = 240;
  const count = Math.max(labels.length, ...series.map((s) => (s.values || []).length), 1);
  const valuesPerX = Array.from({ length: count }, (_, i) => series.reduce((acc, s) => acc + (Number((s.values || [])[i]) || 0), 0));
  const maxTotal = Math.max(1, ...valuesPerX);
  const stackedPolylines = [];
  let accumulated = Array.from({ length: count }, () => 0);
  series.forEach((s, idx) => {
    const vals = Array.from({ length: count }, (_, i) => Number((s.values || [])[i]) || 0);
    accumulated = accumulated.map((v, i) => v + vals[i]);
    const points = accumulated.map((v, i) => {
      const x = count === 1 ? 0 : (i / (count - 1)) * w;
      const y = h - (v / maxTotal) * h;
      return [x, y];
    });
    const bottom = idx === 0
      ? Array.from({ length: count }, (_, i) => [count === 1 ? 0 : (i / (count - 1)) * w, h])
      : stackedPolylines[idx - 1].points;
    const area = `${points.map((p) => `${p[0]},${p[1]}`).join(" ")} ${bottom.slice().reverse().map((p) => `${p[0]},${p[1]}`).join(" ")}`;
    stackedPolylines.push({ points, color: s.color, area, name: s.name, vals });
  });
  return html`
    <div className="h-[240px] w-full overflow-hidden rounded-xl border border-white/10 bg-white/[0.03]">
      <svg viewBox="0 0 ${w} ${h}" className="h-full w-full">
        ${stackedPolylines.map((s, i) => html`<g key=${i}>
          <polygon points=${s.area} fill=${s.color} fill-opacity="0.24"></polygon>
          <polyline points=${s.points.map((p) => `${p[0]},${p[1]}`).join(" ")} fill="none" stroke=${s.color} stroke-width="2.5"></polyline>
          ${s.points.map((p, pi) => html`<g key=${pi}><circle cx=${p[0]} cy=${p[1]} r="2.5" fill=${s.color}></circle><title>${s.name} - ${labels[pi] || `#${pi + 1}`}: ${fmt(s.vals[pi])}</title></g>`)}
        </g>`)}
      </svg>
    </div>
  `;
}

function HeatmapChart({ xLabels = [], yLabels = [], matrix = [], colorA = "34,211,238", colorB = "168,85,247" }) {
  const flat = matrix.flat().map((v) => Number(v) || 0);
  const max = Math.max(1, ...flat);
  const min = Math.min(...flat, 0);
  const scale = (v) => (Number(v) - min) / (max - min || 1);
  return html`
    <div className="apple-scrollbar overflow-auto">
      <div className="min-w-[520px]">
        <div className="mb-2 grid" style=${{ gridTemplateColumns: `160px repeat(${xLabels.length}, minmax(54px,1fr))` }}>
          <div></div>
          ${xLabels.map((x, i) => html`<div key=${i} className="px-1 text-center text-[11px] text-slate-400">${x}</div>`)}
        </div>
        ${yLabels.map((y, yi) => html`<div key=${yi} className="mb-1 grid items-center gap-1" style=${{ gridTemplateColumns: `160px repeat(${xLabels.length}, minmax(54px,1fr))` }}>
          <div className="pr-2 text-right text-[11px] text-slate-300">${y}</div>
          ${(matrix[yi] || []).map((v, xi) => {
            const k = scale(v);
            return html`<div
              key=${xi}
              className="h-9 rounded-md border border-white/10 text-center text-[11px] leading-9 text-white"
              style=${{ background: `linear-gradient(135deg, rgba(${colorA},${0.16 + k * 0.52}), rgba(${colorB},${0.12 + k * 0.45}))` }}
              title=${`${y} / ${xLabels[xi]}: ${fmt(v)}`}
            >${fmt(v)}</div>`;
          })}
        </div>`)}
      </div>
    </div>
  `;
}

function DonutChart({ segments = [] }) {
  const total = Math.max(1, segments.reduce((a, s) => a + (Number(s.value) || 0), 0));
  let offset = 0;
  const radius = 48;
  const circ = 2 * Math.PI * radius;
  return html`
    <div className="flex items-center gap-5">
      <svg viewBox="0 0 120 120" className="h-40 w-40">
        <circle cx="60" cy="60" r=${radius} fill="none" stroke="rgba(255,255,255,.08)" stroke-width="16"></circle>
        ${segments.map((seg, i) => {
          const val = Number(seg.value) || 0;
          const len = (val / total) * circ;
          const node = html`<circle key=${i} cx="60" cy="60" r=${radius} fill="none" stroke=${seg.color} stroke-width="16" stroke-dasharray=${`${len} ${circ - len}`} stroke-dashoffset=${-offset} stroke-linecap="round" transform="rotate(-90 60 60)"><title>${seg.label}: ${fmt(val)} (${pct((val / total) * 100)})</title></circle>`;
          offset += len;
          return node;
        })}
      </svg>
      <div className="space-y-2">
        ${segments.map((seg, i) => html`<div key=${i} className="flex items-center gap-2 text-sm"><span className="h-2.5 w-2.5 rounded-full" style=${{ background: seg.color }}></span><span>${seg.label}</span><span className="apple-muted ml-1">${fmt(seg.value)}</span></div>`)}
      </div>
    </div>
  `;
}

function DataTable({ columns, rows }) {
  return html`
    <div className="${glass} apple-scrollbar overflow-auto">
      <table className="apple-data-table w-full min-w-[760px] border-collapse">
        <thead>
          <tr>${columns.map((c) => html`<th key=${c} className="border-b border-white/10 px-3 py-2 text-left text-xs uppercase tracking-[0.12em] text-slate-300">${c}</th>`)}</tr>
        </thead>
        <tbody>
          ${rows.length
            ? rows.map((r, i) => html`<tr key=${i} className="apple-row-transition border-b border-white/5">${r.map((cell, ci) => html`<td key=${ci} className="px-3 py-2 text-sm text-slate-100">${String(cell ?? "—")}</td>`)}</tr>`)
            : html`<tr><td colSpan=${columns.length} className="px-3 py-6 text-sm text-slate-400">No data</td></tr>`}
        </tbody>
      </table>
    </div>
  `;
}

function PreviewModal({ open, close, title, children }) {
  return html`
    <${AnimatePresence}>
      ${open &&
      html`<${motion.div} className="fixed inset-0 z-[90] flex items-center justify-center bg-black/65 p-4" initial=${{ opacity: 0 }} animate=${{ opacity: 1 }} exit=${{ opacity: 0 }} onClick=${close}>
        <${motion.div} className=${`${glass} max-h-[90vh] w-full max-w-6xl overflow-auto p-6 apple-scrollbar`} initial=${{ opacity: 0, scale: 0.97, y: 18 }} animate=${{ opacity: 1, scale: 1, y: 0 }} exit=${{ opacity: 0, scale: 0.98, y: 18 }} transition=${{ ...spring, damping: 22 }} onClick=${(e) => e.stopPropagation()}>
          <div className="mb-5 flex items-center justify-between"><h3 className="text-2xl font-medium">${title}</h3><button className="apple-control-btn rounded-xl px-3 py-2 text-sm" onClick=${close}>Close</button></div>
          ${children}
        </${motion.div}>
      </${motion.div}>`}
    <//>
  `;
}

function FullscreenLoader({ done, progress, phase }) {
  return html`
    <${AnimatePresence}>
      ${!done &&
      html`<${motion.div} className="fixed inset-0 z-[120] overflow-hidden bg-[#0b0b0f]" initial=${{ opacity: 1 }} exit=${{ opacity: 0 }}>
        <${motion.div} className="absolute inset-x-0 top-0 h-1/2 bg-gradient-to-b from-[#111118] to-[#0d0d12]" initial=${{ y: 0 }} exit=${{ y: "-100%" }} transition=${{ duration: 0.9, ease }} />
        <${motion.div} className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-[#111118] to-[#0d0d12]" initial=${{ y: 0 }} exit=${{ y: "100%" }} transition=${{ duration: 0.9, ease }} />
        <div className="absolute inset-0 flex flex-col items-center justify-center px-5">
          <h1 className="apple-kern-title text-center text-4xl font-medium text-slate-100 md:text-6xl">Albion Analytics</h1>
          <p className="mt-3 text-center text-xs uppercase tracking-[0.17em] text-slate-400">${phase}</p>
          <div className="mt-8 w-[min(640px,92vw)]">
            <div className="h-2 overflow-hidden rounded-full border border-white/20 bg-white/5">
              <div className="h-full rounded-full bg-gradient-to-r from-cyan-300 via-blue-400 to-fuchsia-400 transition-all duration-200" style=${{ width: `${Math.max(4, Math.min(100, progress))}%` }}></div>
            </div>
            <div className="mt-2 flex justify-end text-[11px] text-slate-400">${Math.round(progress)}%</div>
          </div>
        </div>
      </${motion.div}>`}
    <//>
  `;
}

function Sidebar({ items, active, setActive }) {
  const [open, setOpen] = useState(true);
  return html`<div className=${`${glass} h-fit p-3 apple-soft-gap`}>
    <button onClick=${() => setOpen((v) => !v)} className="apple-control-btn w-full rounded-xl px-3 py-2 text-left text-sm">${open ? "Hide categories" : "Show categories"}</button>
    <${AnimatePresence} initial=${false}>
      ${open &&
      html`<${motion.div} initial=${{ height: 0, opacity: 0 }} animate=${{ height: "auto", opacity: 1 }} exit=${{ height: 0, opacity: 0 }} transition=${{ duration: 0.32, ease }} className="overflow-hidden">
        <div className="mt-3 space-y-2">
          ${items.map((item) => html`<button key=${item.id} onClick=${() => setActive(item.id)} className=${`w-full rounded-xl px-3 py-2 text-left text-sm apple-transition ${active === item.id ? "bg-blue-500/25 text-white" : "bg-white/5 text-slate-200 hover:bg-white/10"}`}>${item.label}</button>`)}
        </div>
      </${motion.div}>`}
    <//>
  </div>`;
}

function Landing() {
  const [ready, setReady] = useState(false);
  const [phase, setPhase] = useState("Boot sequence");
  const [progress, setProgress] = useState(2);
  useEffect(() => {
    let alive = true;
    const started = performance.now();
    const minimum = 2400;
    const tick = () => {
      if (!alive) return;
      setProgress((v) => Math.min(90, v + 0.6));
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
    const preload = async () => {
      setPhase("Preloading main dashboard");
      const pMain = fetch("/dashboard/api/data?days=30", { credentials: "same-origin" }).then((r) => r.json());
      setPhase("Preloading economy dashboard");
      const pEcon = fetch("/dashboard/api/economy/data?days=30", { credentials: "same-origin" }).then((r) => r.json());
      const [main, econ] = await Promise.allSettled([pMain, pEcon]);
      if (main.status === "fulfilled") writeCached(CACHE_MAIN, main.value);
      if (econ.status === "fulfilled") writeCached(CACHE_ECON, econ.value);
      const elapsed = performance.now() - started;
      if (elapsed < minimum) await new Promise((r) => setTimeout(r, minimum - elapsed));
      if (!alive) return;
      setPhase("Reveal");
      setProgress(100);
      setTimeout(() => setReady(true), 260);
    };
    preload().catch(() => setReady(true));
    return () => { alive = false; };
  }, []);
  const cards = [
    { title: "Main Dashboard", href: "/dashboard/main", desc: "Guild operations, players, events, system analytics." },
    { title: "Economy Dashboard", href: "/dashboard/economy", desc: "Accounting, routing, armory, imports and audit." },
  ];
  return html`
    <div className="apple-shell min-h-screen">
      <${FullscreenLoader} done=${ready} progress=${progress} phase=${phase} />
      <div className="pt-16 text-center">
        <h1 className="apple-kern-title text-5xl font-medium md:text-6xl">Albion Analytics</h1>
        <p className="apple-muted mt-3 text-lg">Choose your dashboard</p>
      </div>
      <div className="mt-16 grid gap-8 md:grid-cols-2">
        ${cards.map((card, i) => html`<${motion.a}
            key=${card.title}
            href=${card.href}
            className=${`${glass} apple-card-ceramic apple-floating-card apple-neon-card relative block min-h-[460px] overflow-hidden p-10 no-underline text-center`}
            initial=${{ y: 70, opacity: 0 }}
            animate=${ready ? { y: 0, opacity: 1 } : { y: 70, opacity: 0 }}
            transition=${{ ...spring, delay: 0.14 * (i + 1) }}
            whileHover=${{ scale: 1.02, y: -2 }}
            whileTap=${{ scale: 0.992 }}
          >
            <div className="absolute inset-0 bg-gradient-to-br from-blue-500/15 via-transparent to-violet-500/12"></div>
            <div className="relative z-10 flex h-full flex-col items-center justify-center">
              <h2 className="apple-kern-title text-4xl font-medium">${card.title}</h2>
              <p className="apple-muted mt-5 max-w-md text-base leading-relaxed">${card.desc}</p>
            </div>
          </${motion.a}>`)}
      </div>
    </div>
  `;
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
      const out = await fetch(`/dashboard/api/data?${qs.toString()}`, { credentials: "same-origin" }).then((r) => r.json());
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
  const events = data.events || {};
  const system = data.system || {};
  const botHealth = system.bot_health || {};
  const playersRows = (data.players || []).map((p) => [p.nickname, p.guild_name || "—", p.status, p.sessions_count, Number(p.avg_score || 0).toFixed(2), p.tickets_open ?? 0]);
  const ticketsRows = (data.tickets?.recent || []).map((t) => [t.id, t.status, t.player_nick || "—", t.mentor_nick || "—", t.created_at || "—"]);
  const eventsRows = (events.per_content || []).map((e) => [e.content_name || "—", e.events_count ?? 0, e.avg_players_per_event ?? "—", e.unique_players_on_content ?? 0]);

  const items = [{ id: "overview", label: "Overview" }, { id: "players", label: "Players" }, { id: "tickets", label: "Tickets" }, { id: "events", label: "Events" }, { id: "system", label: "System" }];

  const overview = html`
    <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
      <div className="${glass} p-4"><p className="text-xs uppercase tracking-[0.13em] text-slate-300">Tickets open</p><p className="mt-2 text-3xl font-medium text-cyan-200">${fmt(o.tickets_open)}</p></div>
      <div className="${glass} p-4"><p className="text-xs uppercase tracking-[0.13em] text-slate-300">Sessions 30d</p><p className="mt-2 text-3xl font-medium text-blue-200">${fmt(o.sessions_period)}</p></div>
      <div className="${glass} p-4"><p className="text-xs uppercase tracking-[0.13em] text-slate-300">Closed events</p><p className="mt-2 text-3xl font-medium text-violet-200">${fmt(o.events_period)}</p></div>
      <div className="${glass} p-4"><p className="text-xs uppercase tracking-[0.13em] text-slate-300">Closed CTA</p><p className="mt-2 text-3xl font-medium text-fuchsia-200">${fmt(o.events_period_cta)}</p></div>
    </div>
    <div className="mt-5 grid gap-5 xl:grid-cols-2">
      <${ChartCard} title="Tickets vs sessions" subtitle="Comparative operational load (counts)" type="Bar chart" legend=${["tickets", "sessions", "events"]}>
        <${BarChart} labels=${["Tickets open", "Tickets closed", "Sessions", "Events"]} values=${[o.tickets_open || 0, o.tickets_closed_period || 0, o.sessions_period || 0, o.events_period || 0]} color="from-cyan-300 to-blue-500" />
        <${AxisHint} left="0" right="max count" bottom="metrics" />
      </${ChartCard}>
      <${ChartCard} title="Participation trend" subtitle="Event activity and CTA engagement" type="Line chart" legend=${["events", "participants", "cta"]}>
        <${StackedAreaChart}
          labels=${["Events", "Participants", "CTA events", "CTA participants"]}
          series=${[
            { name: "Base events", values: [events.events_in_period || 0, events.events_in_period || 0, 0, 0], color: "#7dd3fc" },
            { name: "Participation", values: [0, events.unique_participants_period || 0, 0, 0], color: "#c4b5fd" },
            { name: "CTA lane", values: [0, 0, events.cta_events_in_period || 0, events.cta_unique_participants_period || 0], color: "#f9a8d4" },
          ]}
        />
        <${AxisHint} left="low activity" right="high activity" bottom="event metrics" />
      </${ChartCard}>
    </div>
  `;

  const body = useMemo(() => {
    if (loading) return html`<p className="apple-muted">Loading…</p>`;
    if (data.ok === false) return html`<p className="text-rose-300">${data.error || "Error"}</p>`;
    if (active === "overview") return overview;
    if (active === "tickets") return html`<${DataTable} columns=${["ID", "Status", "Player", "Mentor", "Created"]} rows=${ticketsRows} />`;
    if (active === "events") return html`<${DataTable} columns=${["Content", "Events", "Avg players", "Unique players"]} rows=${eventsRows} />`;
    if (active === "system") {
      return html`
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          <div className="${glass} p-4"><p className="text-xs uppercase tracking-[0.13em] text-slate-300">Bot signal</p><p className="mt-2 text-2xl font-medium">${botHealth.signal_status || "unknown"}</p></div>
          <div className="${glass} p-4"><p className="text-xs uppercase tracking-[0.13em] text-slate-300">DB latency</p><p className="mt-2 text-2xl font-medium">${fmt(system.db_query_ms)} ms</p></div>
          <div className="${glass} p-4"><p className="text-xs uppercase tracking-[0.13em] text-slate-300">HTTP uptime</p><p className="mt-2 text-2xl font-medium">${fmt(system.http_server_uptime_s)} s</p></div>
          <div className="${glass} p-4"><p className="text-xs uppercase tracking-[0.13em] text-slate-300">Python</p><p className="mt-2 text-2xl font-medium">${system.python_version || "—"}</p></div>
        </div>
        <div className="mt-5 grid gap-5 xl:grid-cols-2">
          <${ChartCard} title="Storage footprint" subtitle="DB usage profile" type="Bar chart" legend=${["used", "free", "% quota"]}>
            <${BarChart} labels=${["Used MB", "Free MB", "Quota %"]} values=${[system.db_used_mb || 0, system.db_free_mb_estimate || 0, system.db_used_pct_of_quota || 0]} color="from-emerald-300 to-cyan-500" />
            <${AxisHint} left="0" right="maximum" bottom="storage metrics" />
          </${ChartCard}>
          <div className="${glass} p-5"><p className="text-sm font-medium">Health summary</p><p className="apple-muted mt-2 text-sm leading-relaxed">${botHealth.summary || "No summary available."}</p></div>
        </div>
      `;
    }
    const shownRows = playersRows.slice(0, playersExpanded ? playersRows.length : 5);
    return html`
      <div className="${glass} p-5">
        <p className="mb-3 text-sm font-medium">Register player</p>
        <div className="grid gap-3 md:grid-cols-2">
          <input id="reg-nick" className="apple-control-input rounded-xl px-3 py-2 text-sm" placeholder="Nickname" />
          <input id="reg-username" className="apple-control-input rounded-xl px-3 py-2 text-sm" placeholder="Discord username" />
          <input id="reg-discord-id" className="apple-control-input rounded-xl px-3 py-2 text-sm" type="number" min="1" placeholder="Discord ID" />
          <select id="reg-status" className="apple-control-input apple-select-contrast rounded-xl px-3 py-2 text-sm">
            <option value="pending">pending</option><option value="active">active</option><option value="mentor">mentor</option><option value="founder">founder</option>
          </select>
          <button className="apple-control-btn rounded-xl px-3 py-2 text-sm" onClick=${async () => {
            const nick = document.getElementById("reg-nick")?.value || "";
            const user = document.getElementById("reg-username")?.value || "";
            const did = Number(document.getElementById("reg-discord-id")?.value || 0);
            const status = document.getElementById("reg-status")?.value || "pending";
            const gid = Number(guildId || data.guilds?.[0]?.id || 0);
            await fetch("/dashboard/api/players/register", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nickname: nick, discord_username: user, discord_id: did, guild_id: gid, status }) });
            load({ force: true });
          }}>Register player</button>
        </div>
      </div>
      <div className="${glass} p-4">
        <button className="flex w-full items-center justify-between rounded-xl bg-white/5 px-3 py-2 text-left text-sm" onClick=${() => setPlayersExpanded((v) => !v)}>
          <span>Players list (${playersRows.length})</span>
          <span className=${`transition-transform duration-300 ${playersExpanded ? "rotate-180" : "rotate-0"}`}>⌄</span>
        </button>
      </div>
      <${DataTable} columns=${["Nickname", "Guild", "Status", "Sessions", "Avg", "Open tickets"]} rows=${shownRows} />
    `;
  }, [active, data, loading, playersExpanded, guildId]);

  return html`
    <div className="apple-shell min-h-screen">
      <header className=${`${glass} mb-4 p-4`}><h1 className="apple-kern-title text-3xl font-medium">Main Dashboard</h1><p className="apple-muted text-sm">Visual-first analytics shell</p></header>
      <div className=${`${glass} mb-4 flex flex-wrap items-center gap-3 p-4`}>
        <label className="text-sm text-slate-200">Days <input className="ml-2 apple-control-input w-20 rounded-xl px-2 py-1" type="number" min="1" max="365" value=${days} onChange=${(e) => setDays(Number(e.target.value || 30))} /></label>
        ${(data.guilds || []).length ? html`<label className="text-sm text-slate-200">Guild <select className="ml-2 apple-control-input apple-select-contrast rounded-xl px-2 py-1" value=${guildId} onChange=${(e) => setGuildId(e.target.value)}><option value="">All</option>${(data.guilds || []).map((g) => html`<option key=${g.id} value=${String(g.id)}>${g.display_name || g.name || "Guild"}</option>`)}</select></label>` : null}
        <button className="apple-control-btn rounded-xl px-3 py-2 text-sm" onClick=${() => load({ force: true })}>Refresh</button>
        <div className="ml-auto flex gap-2"><a className="apple-control-btn rounded-xl px-3 py-2 text-sm text-white no-underline" href="/dashboard">Picker</a><a className="apple-control-btn rounded-xl px-3 py-2 text-sm text-white no-underline" href="/dashboard/economy">Economy</a></div>
      </div>
      <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]"><${Sidebar} items=${items} active=${active} setActive=${setActive} /><section className="space-y-4">${body}</section></div>
      <${PreviewModal} open=${!!preview} close=${() => setPreview(null)} title=${`Detailed ${preview || "overview"}`}>
        <div className="grid gap-5 xl:grid-cols-2">
          <${ChartCard} title="Tickets composition" subtitle="Detailed modal chart with labels" type="Donut chart" legend=${["open", "closed"]} height="h-[360px]">
            <${DonutChart} segments=${[{ label: "Open", value: o.tickets_open || 0, color: "#22d3ee" }, { label: "Closed", value: o.tickets_closed_period || 0, color: "#818cf8" }]} />
          </${ChartCard}>
          <${ChartCard} title="Sessions and events line" subtitle="Expanded detailed trend in modal" type="Line chart" legend=${["sessions", "events"]} height="h-[360px]">
            <${LineChart} labels=${["Sessions", "Events", "CTA"]} values=${[o.sessions_period || 0, o.events_period || 0, o.events_period_cta || 0]} stroke="#c4b5fd" fill="rgba(196,181,253,.16)" />
            <p className="apple-muted mt-3 text-sm leading-relaxed">This modal view gives a more detailed reading than the main cards: counts, relative distance between metrics, and contextual text for quick decisions.</p>
          </${ChartCard}>
        </div>
        <div className="mt-5">
          <${ChartCard} title="Participation intensity matrix" subtitle="Detailed density by activity lanes" type="Heatmap" legend=${["darker = higher"]} height="h-auto">
            <${HeatmapChart}
              xLabels=${["Roster", "Unique", "Stable", "Low attendance", "Never attended"]}
              yLabels=${["General events", "CTA events"]}
              matrix=${[
                [events.active_roster_count || 0, events.unique_participants_period || 0, (events.stable_attendance || []).length || 0, (events.low_attendance || []).length || 0, (events.never_attended || []).length || 0],
                [events.active_roster_count || 0, events.cta_unique_participants_period || 0, events.cta_events_in_period || 0, (events.low_attendance || []).length || 0, (events.never_attended || []).length || 0],
              ]}
            />
          </${ChartCard}>
        </div>
      </${PreviewModal}>
    </div>
  `;
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
      const out = await fetch(`/dashboard/api/economy/data?${qs.toString()}`, { credentials: "same-origin" }).then((r) => r.json());
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
      const out = await fetch(url, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then((r) => r.json());
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
    if (active === "reports") {
      return html`
        <div className="grid gap-5 xl:grid-cols-2">
          <${ChartCard} title="P&L structure" subtitle="Income/expense/profit comparison" type="Bar chart" legend=${["income", "expense", "profit"]}>
            <${BarChart} labels=${["Income", "Expense", "Profit"]} values=${[rep.pnl_summary?.income_total || 0, rep.pnl_summary?.expense_total || 0, rep.pnl_summary?.profit_total || 0]} color="from-emerald-300 to-teal-500" />
            <${AxisHint} left="0" right="peak value" bottom="financial metrics" />
          </${ChartCard}>
          <${ChartCard} title="Cashflow pattern" subtitle="Cash in / out / net" type="Line chart" legend=${["cash in", "cash out", "net"]}>
            <${LineChart} labels=${["Cash in", "Cash out", "Net"]} values=${[rep.cashflow_summary?.cash_in_total || 0, rep.cashflow_summary?.cash_out_total || 0, rep.cashflow_summary?.net_cashflow || 0]} stroke="#f9a8d4" fill="rgba(249,168,212,.16)" />
            <${AxisHint} left="0" right="peak flow" bottom="flow metrics" />
          </${ChartCard}>
        </div>
      `;
    }
    if (active === "operations") {
      return html`
        <div className="grid gap-5 xl:grid-cols-2">
          <div className="${glass} p-5"><h3 className="text-sm font-medium">Loot buyback</h3><p className="apple-muted mt-1 text-xs">Create manual buyback request</p><input className="apple-control-input mt-3 w-full rounded-xl px-3 py-2 text-sm" type="number" min="1" placeholder="Buyback price" value=${buybackPrice} onChange=${(e) => setBuybackPrice(e.target.value)} /><button className="apple-control-btn mt-3 rounded-xl px-3 py-2 text-sm" onClick=${() => post("/dashboard/api/economy/loot-buyback", { buyback_price: Number(buybackPrice || 0), approved_by: "dashboard_admin" })}>Create buyback</button></div>
          <div className="${glass} p-5"><h3 className="text-sm font-medium">Regear request</h3><p className="apple-muted mt-1 text-xs">Create player regear request</p><input className="apple-control-input mt-3 w-full rounded-xl px-3 py-2 text-sm" placeholder="Player nickname" value=${regear.player_name} onChange=${(e) => setRegear((v) => ({ ...v, player_name: e.target.value }))} /><input className="apple-control-input mt-2 w-full rounded-xl px-3 py-2 text-sm" placeholder="Content type" value=${regear.content_type} onChange=${(e) => setRegear((v) => ({ ...v, content_type: e.target.value }))} /><input className="apple-control-input mt-2 w-full rounded-xl px-3 py-2 text-sm" type="number" min="1" placeholder="Unit cost" value=${regear.unit_cost} onChange=${(e) => setRegear((v) => ({ ...v, unit_cost: e.target.value }))} /><textarea className="apple-control-input mt-2 w-full rounded-xl px-3 py-2 text-sm" rows="3" placeholder="Note" value=${regear.note} onChange=${(e) => setRegear((v) => ({ ...v, note: e.target.value }))}></textarea><button className="apple-control-btn mt-3 rounded-xl px-3 py-2 text-sm" onClick=${() => post("/dashboard/api/economy/regear", { ...regear, unit_cost: Number(regear.unit_cost || 0), action: "create" })}>Create regear</button></div>
        </div>
        ${opMsg ? html`<p className="apple-muted mt-3 text-sm">${opMsg}</p>` : null}
      `;
    }
    return html`
      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
        <div className="${glass} p-4"><p className="text-xs uppercase tracking-[0.13em] text-slate-300">Cash balance</p><p className="mt-2 text-3xl font-medium text-cyan-200">${fmt(k.cash_balance ?? rep.balance_snapshot?.cash_balance)}</p></div>
        <div className="${glass} p-4"><p className="text-xs uppercase tracking-[0.13em] text-slate-300">Energy balance</p><p className="mt-2 text-3xl font-medium text-blue-200">${fmt(k.energy_balance ?? rep.balance_snapshot?.energy_balance)}</p></div>
        <div className="${glass} p-4"><p className="text-xs uppercase tracking-[0.13em] text-slate-300">Pending entries</p><p className="mt-2 text-3xl font-medium text-violet-200">${fmt(k.pending_entries)}</p></div>
        <div className="${glass} p-4"><p className="text-xs uppercase tracking-[0.13em] text-slate-300">Open alerts</p><p className="mt-2 text-3xl font-medium text-fuchsia-200">${fmt(k.open_alerts)}</p></div>
      </div>
      <div className="mt-5 grid gap-5 xl:grid-cols-3">
        <${ChartCard} title="Operational pressure" subtitle="Entries, alerts, approvals" type="Bar chart" legend=${["entries", "alerts", "approvals"]}>
          <${BarChart} labels=${["Pending entries", "Alerts", "Approvals"]} values=${[k.pending_entries || 0, (data.alerts || []).length, (data.pending_approvals || []).length]} color="from-cyan-300 to-blue-500" />
          <${AxisHint} left="0" right="peak count" bottom="risk indicators" />
        </${ChartCard}>
        <${ChartCard} title="Armory pressure" subtitle="Top deficit values" type="Line chart" legend=${["deficit"]}>
          <${LineChart} labels=${(data.armory_stock || []).slice(0, 8).map((x) => x.item_name || x.item_id || "item")} values=${(data.armory_stock || []).slice(0, 8).map((x) => Number(x.deficit_abs || 0))} stroke="#fdba74" fill="rgba(251,146,60,.16)" />
          <${AxisHint} left="low deficit" right="high deficit" bottom="top items" />
        </${ChartCard}>
        <${ChartCard} title="Risk heatmap" subtitle="Cross-metric risk surface" type="Heatmap" legend=${["higher intensity = higher priority"]}>
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
        </${ChartCard}>
      </div>
      <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">${["Operations", "Entries", "Armory", "Reports", "Alerts", "Snapshot"].map((name) => html`<${motion.button} key=${name} className=${`${glass} p-4 text-left`} whileHover=${{ scale: 1.02, y: -2 }} whileTap=${{ scale: 0.99 }} onClick=${() => setPreview(true)}><p className="text-sm font-medium">${name}</p><p className="apple-muted mt-2 text-xs">Open detailed modal</p></${motion.button}>`)}</div>
    `;
  }, [active, data, loading, opMsg, buybackPrice, regear]);

  return html`
    <div className="apple-shell min-h-screen">
      <header className=${`${glass} mb-4 p-4`}><h1 className="apple-kern-title text-3xl font-medium">Economy Dashboard</h1><p className="apple-muted text-sm">Visual parity pass with expanded details</p></header>
      <div className=${`${glass} mb-4 flex flex-wrap items-center gap-3 p-4`}>
        <label className="text-sm">Days <input className="ml-2 apple-control-input w-20 rounded-xl px-2 py-1" type="number" min="1" max="365" value=${days} onChange=${(e) => setDays(Number(e.target.value || 30))} /></label>
        <label className="text-sm">Status <input className="ml-2 apple-control-input w-32 rounded-xl px-2 py-1" value=${entryStatus} onChange=${(e) => setEntryStatus(e.target.value)} placeholder="pending/posted" /></label>
        <label className="text-sm">Category <input className="ml-2 apple-control-input w-36 rounded-xl px-2 py-1" value=${category} onChange=${(e) => setCategory(e.target.value)} placeholder="regear" /></label>
        <label className="text-sm">Source <input className="ml-2 apple-control-input w-36 rounded-xl px-2 py-1" value=${source} onChange=${(e) => setSource(e.target.value)} placeholder="dashboard" /></label>
        <button className="apple-control-btn rounded-xl px-3 py-2 text-sm" onClick=${() => load({ force: true })}>Refresh</button>
        <div className="ml-auto flex gap-2"><a className="apple-control-btn rounded-xl px-3 py-2 text-sm text-white no-underline" href="/dashboard">Picker</a><a className="apple-control-btn rounded-xl px-3 py-2 text-sm text-white no-underline" href="/dashboard/main">Main</a></div>
      </div>
      <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]"><${Sidebar} items=${tabs} active=${active} setActive=${setActive} /><section className="space-y-4">${panel}</section></div>
      <${PreviewModal} open=${preview} close=${() => setPreview(false)} title="Economy detailed overview">
        <div className="grid gap-5 xl:grid-cols-2">
          <${ChartCard} title="Treasury distribution" subtitle="Detailed modal breakdown with exact values" type="Donut chart" legend=${["cash", "energy"]} height="h-[380px]">
            <${DonutChart} segments=${[{ label: "Cash", value: k.cash_balance || 0, color: "#22d3ee" }, { label: "Energy", value: k.energy_balance || 0, color: "#c4b5fd" }]} />
            <p className="apple-muted mt-2 text-sm">Modal charts provide deeper context than overview cards: exact split, relative ratio, and immediate reading of concentration risk.</p>
          </${ChartCard}>
          <${ChartCard} title="Risk and backlog curve" subtitle="Alerts, discrepancies, approvals, pending entries" type="Line chart" legend=${["risk lanes"]} height="h-[380px]">
            <${LineChart} labels=${["Alerts", "Discrepancies", "Approvals", "Pending entries"]} values=${[(data.alerts || []).length, (data.discrepancies || []).length, (data.pending_approvals || []).length, k.pending_entries || 0]} stroke="#f9a8d4" fill="rgba(249,168,212,.16)" />
            <p className="apple-muted mt-2 text-sm">Use this curve to prioritize review sequence: spikes indicate areas where operational response should happen first.</p>
          </${ChartCard}>
        </div>
        <div className="mt-5 grid gap-5 xl:grid-cols-2">
          <${ChartCard} title="Stacked financial lanes" subtitle="Income/expense/cashflow layered contribution" type="Stacked area" legend=${["income", "expense", "net"]} height="h-[380px]">
            <${StackedAreaChart}
              labels=${["P&L income", "P&L expense", "P&L profit", "Cash in", "Cash out", "Net cashflow"]}
              series=${[
                { name: "Income lane", values: [rep.pnl_summary?.income_total || 0, 0, 0, rep.cashflow_summary?.cash_in_total || 0, 0, 0], color: "#34d399" },
                { name: "Expense lane", values: [0, rep.pnl_summary?.expense_total || 0, 0, 0, rep.cashflow_summary?.cash_out_total || 0, 0], color: "#f97316" },
                { name: "Net lane", values: [0, 0, rep.pnl_summary?.profit_total || 0, 0, 0, rep.cashflow_summary?.net_cashflow || 0], color: "#60a5fa" },
              ]}
            />
          </${ChartCard}>
          <${ChartCard} title="Control heatmap" subtitle="Detailed control-plane intensity map" type="Heatmap" legend=${["high values are hotspots"]} height="h-[380px]">
            <${HeatmapChart}
              xLabels=${["alerts", "discrepancies", "approvals", "audit"]}
              yLabels=${["all", "open-only", "last-window"]}
              matrix=${[
                [(data.alerts || []).length, (data.discrepancies || []).length, (data.pending_approvals || []).length, (data.audit_trail || []).length],
                [(data.alerts || []).filter((x) => String(x.status || "").toLowerCase() !== "ack").length, (data.discrepancies || []).filter((x) => String(x.status || "").toLowerCase() !== "resolved").length, (data.pending_approvals || []).length, (data.audit_trail || []).slice(0, 40).length],
                [(data.alerts || []).slice(0, 20).length, (data.discrepancies || []).slice(0, 20).length, (data.pending_approvals || []).slice(0, 20).length, (data.audit_trail || []).slice(0, 20).length],
              ]}
              colorA="16,185,129"
              colorB="14,165,233"
            />
          </${ChartCard}>
        </div>
      </${PreviewModal}>
    </div>
  `;
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
