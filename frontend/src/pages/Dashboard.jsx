import { useEffect, useState, useCallback, useMemo } from "react";
import api from "../services/api";

function formatUsd(n) {
  if (n == null || n === 0) return "—";
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(1)}k`;
  return `$${Math.round(n)}`;
}

function formatAge(m) {
  if (m == null) return "—";
  if (m < 1) return "<1m";
  if (m < 60) return `${Math.round(m)}m`;
  return `${(m / 60).toFixed(1)}h`;
}

function CurveBar({ progress, stage }) {
  const pct = Math.min(100, Math.max(0, progress || 0));
  const hot = stage === "bonding" && pct >= 75;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[10px] text-slate-500">
        <span>Bonding curve</span>
        <span className={hot ? "text-amber-300 font-medium" : "text-slate-400"}>
          {stage === "bonding" ? `${Math.round(pct)}%` : stage === "graduated" ? "100%" : "—"}
        </span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-slate-800 overflow-hidden">
        <div
          className={`h-full transition-all duration-700 ${
            hot ? "bg-amber-400" : stage === "bonding" ? "bg-emerald-400" : "bg-violet-400"
          }`}
          style={{ width: `${stage === "graduated" ? 100 : pct}%` }}
        />
      </div>
    </div>
  );
}

function StageBadge({ stage, curve, signal }) {
  if (signal === "graduating" || (stage === "bonding" && curve >= 75)) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-300 border border-amber-500/40">
        <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />
        GRADUATING
      </span>
    );
  }
  if (stage === "bonding") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-300 border border-emerald-500/30">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
        ON CURVE
      </span>
    );
  }
  if (stage === "graduated") {
    return (
      <span className="rounded-full bg-violet-500/15 px-2 py-0.5 text-[10px] font-medium text-violet-300 border border-violet-500/30">
        GRADUATED
      </span>
    );
  }
  return (
    <span className="rounded-full bg-slate-500/15 px-2 py-0.5 text-[10px] text-slate-400 border border-slate-600/40">
      LISTED
    </span>
  );
}

function TokenCard({ token, rank }) {
  const [copied, setCopied] = useState(false);
  const isPrime = (token.hawk_score ?? token.alpha_score ?? 0) >= 82;
  const isHigh = (token.hawk_score ?? token.alpha_score ?? 0) >= 70;
  const isGrad = token.signal === "graduating" || (token.stage === "bonding" && (token.curve_progress || 0) >= 75);
  const isNew = (token.age_minutes || 99) <= 10;

  const copyMint = () => {
    if (!token.address) return;
    navigator.clipboard?.writeText(token.address);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <article
      className={`relative rounded-2xl bg-slate-900/85 border p-4 transition hover:bg-slate-900 ${
        isGrad
          ? "border-amber-500/50 shadow-[0_0_32px_rgba(245,158,11,0.12)]"
          : isPrime
          ? "border-yellow-500/40 card-glow-prime"
          : isHigh
          ? "border-emerald-500/25 card-glow"
          : "border-slate-800"
      }`}
    >
      {isNew && (
        <span className="absolute -top-2 right-3 rounded-full bg-sky-500 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-slate-950">
          NEW
        </span>
      )}

      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-800 font-display text-xs font-bold text-slate-400">
            #{rank}
          </div>
          {token.image ? (
            <img src={token.image} alt="" className="h-10 w-10 rounded-xl object-cover bg-slate-800" loading="lazy" />
          ) : (
            <div className="h-10 w-10 rounded-xl bg-slate-800 flex items-center justify-center text-slate-600 text-xs">
              ?
            </div>
          )}
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="font-display text-lg font-bold tracking-tight truncate">${token.ticker}</h3>
              <StageBadge stage={token.stage} curve={token.curve_progress} signal={token.signal} />
            </div>
            <p className="text-xs text-slate-500 truncate">{token.name}</p>
          </div>
        </div>
        <div className="text-right shrink-0">
          <div
            className={`font-display text-2xl font-bold tabular-nums ${
              isGrad ? "text-amber-300" : isPrime ? "text-yellow-300" : "text-white"
            }`}
          >
            {token.hawk_score ?? token.alpha_score}
          </div>
          <div className="text-[10px] text-slate-500">HAWK</div>
          <div className="text-[10px] text-slate-500 mt-1">Conf {token.confidence ?? "—"}</div>
        </div>
      </div>

      <CurveBar progress={token.curve_progress} stage={token.stage} />

      <div className="mt-3 grid grid-cols-4 gap-2 text-center">
        <div>
          <div className="text-[10px] text-slate-500">MCAP</div>
          <div className="text-xs font-medium tabular-nums">{formatUsd(token.market_cap)}</div>
        </div>
        <div>
          <div className="text-[10px] text-slate-500">AGE</div>
          <div className="text-xs font-medium tabular-nums text-sky-300/90">{formatAge(token.age_minutes)}</div>
        </div>
        <div>
          <div className="text-[10px] text-slate-500">REPLIES</div>
          <div className="text-xs font-medium tabular-nums">{token.reply_count ?? "—"}</div>
        </div>
        <div>
          <div className="text-[10px] text-slate-500">RUG RISK</div>
          <div className={`text-xs font-medium tabular-nums ${
            (token.rug_risk || 0) >= 55 ? "text-rose-400" :
            (token.rug_risk || 0) >= 40 ? "text-amber-400" : "text-emerald-400"
          }`}>{token.rug_risk ?? "—"}</div>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        <span className="rounded-md bg-slate-800 px-2 py-0.5 text-[10px] text-slate-300">{token.rating}</span>
        <span className="rounded-md bg-slate-800 px-2 py-0.5 text-[10px] text-slate-500">{token.recommendation}</span>
        {token.entry_state && (
          <span className={`rounded-md px-2 py-0.5 text-[10px] border ${
            token.entry_state === "EARLY_ENTRY" || token.entry_state === "CONFIRMATION_ENTRY"
              ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300"
              : token.entry_state === "AVOID"
              ? "bg-rose-500/15 border-rose-500/40 text-rose-300"
              : "bg-sky-500/15 border-sky-500/30 text-sky-300"
          }`}>
            {token.entry_state === "WATCH" ? "WATCH · research only" : token.entry_state}
          </span>
        )}
        {token.ladder && token.ladder !== "NOISE" && (
          <span className={`rounded-md px-2 py-0.5 text-[10px] border ${
            token.ladder === "LOTTERY" ? "bg-fuchsia-500/15 border-fuchsia-500/40 text-fuchsia-300" :
            token.ladder === "BREAKOUT" ? "bg-amber-500/15 border-amber-500/40 text-amber-300" :
            "bg-slate-800 border-slate-600 text-slate-300"
          }`}>{token.ladder}{token.size_hint ? ` · ${token.size_hint}` : ""}</span>
        )}
        {token.lifecycle && (
          <span className="rounded-md bg-slate-800 px-2 py-0.5 text-[10px] text-slate-500">{token.lifecycle}</span>
        )}
        {token.is_live && (
          <span className="rounded-md bg-rose-500/20 px-2 py-0.5 text-[10px] text-rose-300 border border-rose-500/30">
            LIVE
          </span>
        )}
      </div>

      {token.winner_watch && (
        <span className="rounded-md px-2 py-0.5 text-[10px] border bg-emerald-500/15 border-emerald-500/40 text-emerald-300">
          {token.runner_label || "RUNNER"} · {token.runner_score}
        </span>
      )}
      {token.developer_intel?.serial_deployer && (
        <p className="mt-1 text-[10px] text-rose-400 font-medium">
          SERIAL DEPLOYER · {token.developer_intel?.serial_rug_risk || "ELEVATED"} · {token.developer_intel?.launches_observed || "?"} mints seen
        </p>
      )}
      {token.developer_intel?.journal_death_rate != null && token.developer_intel.journal_death_samples >= 3 && (
        <p className="mt-1 text-[10px] text-rose-300">
          Journal death rate {Math.round(token.developer_intel.journal_death_rate * 100)}% ({token.developer_intel.journal_death_samples} samples)
        </p>
      )}
      {token.convergence_label && (
        <p className="mt-2 text-[11px] text-violet-300/90">
          {token.convergence_label} · conv {token.convergence_score} · rel {token.reliability}
          {token.display_score != null ? ` · display ${token.display_score}` : ""}
        </p>
      )}
      {token.pattern_summary && (
        <p className="mt-2 text-[11px] text-slate-400 leading-snug">{token.pattern_summary}</p>
      )}
      {token.hidden_signals?.length > 0 && (
        <ul className="mt-1 space-y-0.5">
          {token.hidden_signals.slice(0, 2).map((s, i) => (
            <li key={i} className={`text-[10px] ${s.severity === "bearish" ? "text-rose-400/90" : s.severity === "bullish" ? "text-emerald-400/90" : "text-slate-500"}`}>
              ▹ {s.note}
            </li>
          ))}
        </ul>
      )}
      
      <div className="mt-3 flex flex-wrap gap-1.5">
        <button
          type="button"
          className="rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-[10px] text-slate-300 hover:border-slate-500"
          onClick={async () => {
            try {
              await api.logJournal({
                action: "skip",
                address: token.address,
                ticker: token.ticker,
                ladder: token.ladder,
                entry_state: token.entry_state,
                display_score: token.display_score,
                convergence_score: token.convergence_score,
                reliability: token.reliability,
                hawk_score: token.hawk_score || token.alpha_score,
                rug_risk: token.rug_risk,
                market_cap: token.market_cap,
                reply_count: token.reply_count,
                age_minutes: token.age_minutes,
                breakout_score: token.breakout_score,
                lottery_score: token.lottery_score,
                size_hint: token.size_hint,
                convergence_label: token.convergence_label,
                pattern_summary: token.pattern_summary,
              });
              alert("Logged SKIP");
            } catch (e) {
              alert("Journal failed");
            }
          }}
        >
          Log skip
        </button>
        <button
          type="button"
          className="rounded-md border border-fuchsia-700/50 bg-fuchsia-950/40 px-2 py-1 text-[10px] text-fuchsia-200 hover:border-fuchsia-500"
          onClick={async () => {
            try {
              await api.logJournal({
                action: "micro_entry",
                address: token.address,
                ticker: token.ticker,
                ladder: token.ladder,
                entry_state: token.entry_state,
                display_score: token.display_score,
                convergence_score: token.convergence_score,
                reliability: token.reliability,
                hawk_score: token.hawk_score || token.alpha_score,
                rug_risk: token.rug_risk,
                market_cap: token.market_cap,
                reply_count: token.reply_count,
                age_minutes: token.age_minutes,
                breakout_score: token.breakout_score,
                lottery_score: token.lottery_score,
                size_hint: token.size_hint,
                convergence_label: token.convergence_label,
                pattern_summary: token.pattern_summary,
              });
              alert("Logged MICRO ENTRY — journal for outcome later");
            } catch (e) {
              alert("Journal failed");
            }
          }}
        >
          Log micro
        </button>
        <button
          type="button"
          className="rounded-md border border-amber-700/50 bg-amber-950/30 px-2 py-1 text-[10px] text-amber-200 hover:border-amber-500"
          onClick={async () => {
            try {
              await api.logJournal({
                action: "watch",
                address: token.address,
                ticker: token.ticker,
                ladder: token.ladder,
                entry_state: token.entry_state,
                display_score: token.display_score,
                convergence_score: token.convergence_score,
                reliability: token.reliability,
                hawk_score: token.hawk_score || token.alpha_score,
                rug_risk: token.rug_risk,
                market_cap: token.market_cap,
                reply_count: token.reply_count,
                age_minutes: token.age_minutes,
                breakout_score: token.breakout_score,
                lottery_score: token.lottery_score,
                size_hint: token.size_hint,
                convergence_label: token.convergence_label,
                pattern_summary: token.pattern_summary,
              });
              alert("Logged WATCH");
            } catch (e) {
              alert("Journal failed");
            }
          }}
        >
          Log watch
        </button>
      </div>
      {token.reasons?.length > 0 && (

        <ul className="mt-3 space-y-1">
          {token.reasons.slice(0, 4).map((r, i) => (
            <li key={i} className="text-[11px] text-emerald-400/90 flex items-start gap-1.5">
              <span className="mt-0.5 text-emerald-500">▸</span>
              <span>{r}</span>
            </li>
          ))}
        </ul>
      )}

      {token.risk_flags?.length > 0 && (
        <p className="mt-2 text-[10px] text-amber-500/80">Flags: {token.risk_flags.join(", ")}</p>
      )}

      <div className="mt-4 flex items-center gap-2 text-[11px] flex-wrap">
        {token.address && (
          <a
            href={`https://pump.fun/${token.address}`}
            target="_blank"
            rel="noreferrer"
            className="rounded-lg bg-emerald-600/25 hover:bg-emerald-600/40 border border-emerald-500/40 px-3 py-1.5 text-emerald-200 font-medium transition"
          >
            Open Pump
          </a>
        )}
        {token.dex_url && (
          <a
            href={token.dex_url}
            target="_blank"
            rel="noreferrer"
            className="rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 px-3 py-1.5 text-slate-300 transition"
          >
            Dex
          </a>
        )}
        {token.twitter && (
          <a
            href={token.twitter.startsWith("http") ? token.twitter : `https://x.com/${token.twitter}`}
            target="_blank"
            rel="noreferrer"
            className="rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 px-3 py-1.5 text-slate-300 transition"
          >
            X
          </a>
        )}
        <button
          type="button"
          onClick={copyMint}
          className="ml-auto rounded-lg bg-slate-800/90 hover:bg-slate-700 border border-slate-700 px-3 py-1.5 text-slate-400 transition"
        >
          {copied ? "Copied ✓" : "Copy mint"}
        </button>
      </div>
    </article>
  );
}

const FILTERS = [
  { id: "focus", label: "Focus (private)" },
  { id: "lottery", label: "Lottery" },
  { id: "breakout", label: "Breakout $30k+" },
  { id: "actionable", label: "Actionable" },
  { id: "early", label: "Early" },
  { id: "all", label: "All noise" },
  { id: "graduating", label: "Graduating" },
  { id: "prime", label: "Prime" },
];

export default function Dashboard() {
  const [feed, setFeed] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdate, setLastUpdate] = useState(null);
  const [filter, setFilter] = useState("focus");
  const [waking, setWaking] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [hawkRes, statsRes] = await Promise.all([api.hawk(40), api.stats()]);
      setFeed(hawkRes.results || []);
      setStats(statsRes);
      setError("");
      setWaking(false);
      setLastUpdate(new Date());
    } catch (e) {
      setError("Feed unavailable — free tier may be waking up (30–60s). Retrying…");
      setWaking(true);
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 25_000);
    return () => clearInterval(id);
  }, [refresh]);

  const filtered = useMemo(() => {
    let list = feed;
    if (filter === "bonding") list = list.filter((t) => t.stage === "bonding");
    if (filter === "graduating")
      list = list.filter(
        (t) => t.signal === "graduating" || t.lifecycle === "GRADUATING" || (t.stage === "bonding" && (t.curve_progress || 0) >= 75)
      );
    if (filter === "prime")
      list = list.filter((t) => t.signal === "prime" || (t.hawk_score ?? t.alpha_score ?? 0) >= 80);
    if (filter === "focus") {
      list = list.filter((t) => t.ladder === "LOTTERY" || t.ladder === "EARLY" || t.ladder === "BREAKOUT" || t.operator_priority);
      list = [...list].sort((a, b) => (b.display_score || b.focus_score || 0) - (a.display_score || a.focus_score || 0));
    }
    if (filter === "early")
      list = list.filter((t) => t.ladder === "EARLY");
    if (filter === "lottery")
      list = list.filter((t) => t.ladder === "LOTTERY" || ((t.lottery_score || 0) >= 40)).sort((a, b) => (b.lottery_score || 0) - (a.lottery_score || 0));
    if (filter === "breakout")
      list = list.filter((t) => (t.market_cap || 0) >= 30000).sort((a, b) => (b.breakout_score || 0) - (a.breakout_score || 0));
    if (filter === "actionable")
      list = list.filter((t) => t.entry_state === "EARLY_ENTRY" || t.entry_state === "CONFIRMATION_ENTRY");
    if (filter === "emerging")
      list = list.filter(
        (t) =>
          t.stage === "bonding" &&
          (t.age_minutes || 0) >= 6 &&
          (t.age_minutes || 0) <= 45 &&
          (t.reply_count || 0) >= 3
      );
    if (filter === "postgrad")
      list = list.filter((t) => t.stage === "graduated" || t.lifecycle === "POST_GRADUATION");
    return list;
  }, [feed, filter]);

  return (
    <div className="min-h-screen hawk-grid">
      <header className="sticky top-0 z-20 border-b border-slate-800/80 bg-slate-950/90 backdrop-blur-md">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 py-3.5 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-xl">
              🦅
            </div>
            <div>
              <h1 className="font-display text-xl font-extrabold tracking-tight text-white">
                ASILI <span className="text-emerald-400">HAWK</span>
              </h1>
              <p className="text-[11px] text-slate-500">Pre-terminal · bonding curve edge</p>
            </div>
          </div>
          <div className="flex items-center gap-3 text-xs text-slate-400">
            {stats && (
              <div className="hidden md:flex items-center gap-3">
                <span className="text-emerald-400 font-medium">{stats.on_curve} curve</span>
                {(stats.graduating || 0) > 0 && (
                  <span className="text-amber-300 font-medium">{stats.graduating} graduating</span>
                )}
                <span className="text-yellow-400/90">{stats.prime} prime</span>
              </div>
            )}
            <div className="flex items-center gap-2">
              <span
                className={`h-2 w-2 rounded-full ${
                  error ? "bg-amber-400 animate-pulse" : "bg-emerald-400 animate-pulse"
                }`}
              />
              <span className="hidden sm:inline">{error ? "Waking" : "Live"}</span>
            </div>
            <button
              onClick={refresh}
              className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 hover:bg-slate-800 transition text-slate-300"
            >
              Refresh
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 sm:px-6 py-6">
        <section className="mb-6 rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 to-slate-950 p-5">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
            <div>
              <p className="text-[10px] uppercase tracking-widest text-emerald-500/80 font-medium mb-1">Mission</p>
              <h2 className="font-display text-xl sm:text-2xl font-bold text-white max-w-xl">
                Catch them <span className="text-emerald-400">before the curve completes</span>
              </h2>
              <p className="mt-1.5 text-sm text-slate-400 max-w-lg">
                Ranked by freshness, curve position, and early traction — not hype after terminals fill up.
              </p>
            </div>
            {lastUpdate && (
              <p className="text-[11px] text-slate-600 shrink-0">Updated {lastUpdate.toLocaleTimeString()}</p>
            )}
          </div>
        </section>

        {/* Filters */}
        <div className="mb-5 flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setFilter(f.id)}
              className={`rounded-full px-3.5 py-1.5 text-xs font-medium transition border ${
                filter === f.id
                  ? "bg-emerald-500/20 border-emerald-500/50 text-emerald-300"
                  : "bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-600"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {(error || waking) && (
          <div className="mb-5 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
            {error || "Waking free-tier instance…"}
          </div>
        )}

        {loading ? (
          <div className="flex h-56 items-center justify-center text-slate-500">
            <div className="text-center">
              <div className="mb-3 text-3xl animate-pulse">🦅</div>
              <p className="text-sm">Scanning bonding curves…</p>
            </div>
          </div>
        ) : filtered.length === 0 ? (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-12 text-center text-slate-500">
            Nothing on Focus — market may be dead or nothing meets the bar. Switch to <button className="text-emerald-400 underline" onClick={() => setFilter("all")}>All</button> or wait for the next launches.
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {filtered.map((token, i) => (
              <TokenCard key={token.address || i} token={token} rank={i + 1} />
            ))}
          </div>
        )}

        <footer className="mt-14 border-t border-slate-900 pt-8 pb-10 text-center text-[11px] text-slate-600">
          ASILI HAWK v0.4 · Research only · Not financial advice · Public Pump.fun + DexScreener data
        </footer>
      </main>
    </div>
  );
}
