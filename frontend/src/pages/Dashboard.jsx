import { useEffect, useState, useCallback } from "react";
import api from "../services/api";

function formatUsd(n) {
  if (n == null || n === 0) return "—";
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(1)}k`;
  return `$${n.toFixed(0)}`;
}

function formatAge(m) {
  if (m == null) return "—";
  if (m < 60) return `${Math.round(m)}m`;
  return `${(m / 60).toFixed(1)}h`;
}

function ScoreBar({ score }) {
  const pct = Math.min(100, score || 0);
  let color = "bg-slate-500";
  if (pct >= 82) color = "bg-yellow-400";
  else if (pct >= 70) color = "bg-emerald-400";
  else if (pct >= 58) color = "bg-sky-400";
  return (
    <div className="h-1.5 w-full rounded-full bg-slate-800 overflow-hidden">
      <div className={`h-full ${color} transition-all duration-500`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function StageBadge({ stage, curve }) {
  if (stage === "bonding") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-300 border border-emerald-500/30">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
        ON CURVE {curve != null ? `${Math.round(curve)}%` : ""}
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
  const isPrime = (token.alpha_score || 0) >= 82;
  const isHigh = (token.alpha_score || 0) >= 70;

  return (
    <article
      className={`relative rounded-2xl bg-slate-900/80 border p-4 transition hover:bg-slate-900 ${
        isPrime ? "border-yellow-500/40 card-glow-prime" : isHigh ? "border-emerald-500/25 card-glow" : "border-slate-800"
      }`}
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-800 font-display text-sm font-bold text-slate-300">
            #{rank}
          </div>
          {token.image ? (
            <img src={token.image} alt="" className="h-10 w-10 rounded-xl object-cover bg-slate-800" />
          ) : null}
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="font-display text-lg font-bold tracking-tight truncate">{token.ticker}</h3>
              <StageBadge stage={token.stage} curve={token.curve_progress} />
            </div>
            <p className="text-xs text-slate-500 truncate">{token.name}</p>
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="font-display text-2xl font-bold tabular-nums text-white">{token.alpha_score}</div>
          <div className="text-[10px] text-slate-500">ALPHA</div>
        </div>
      </div>

      <ScoreBar score={token.alpha_score} />

      <div className="mt-3 grid grid-cols-4 gap-2 text-center">
        <div>
          <div className="text-[10px] text-slate-500">MCAP</div>
          <div className="text-xs font-medium tabular-nums">{formatUsd(token.market_cap)}</div>
        </div>
        <div>
          <div className="text-[10px] text-slate-500">LIQ</div>
          <div className="text-xs font-medium tabular-nums">{formatUsd(token.liquidity)}</div>
        </div>
        <div>
          <div className="text-[10px] text-slate-500">AGE</div>
          <div className="text-xs font-medium tabular-nums">{formatAge(token.age_minutes)}</div>
        </div>
        <div>
          <div className="text-[10px] text-slate-500">REPLIES</div>
          <div className="text-xs font-medium tabular-nums">{token.reply_count ?? "—"}</div>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        <span className="rounded-md bg-slate-800 px-2 py-0.5 text-[10px] text-slate-300">{token.rating}</span>
        <span className="rounded-md bg-slate-800 px-2 py-0.5 text-[10px] text-slate-400">{token.recommendation}</span>
        {token.source && (
          <span className="rounded-md bg-slate-800/80 px-2 py-0.5 text-[10px] text-slate-500">{token.source}</span>
        )}
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

      <div className="mt-4 flex items-center gap-2 text-[11px]">
        {token.address && (
          <a
            href={`https://pump.fun/${token.address}`}
            target="_blank"
            rel="noreferrer"
            className="rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-500/30 px-3 py-1.5 text-emerald-300 transition"
          >
            Pump.fun
          </a>
        )}
        {token.dex_url && (
          <a
            href={token.dex_url}
            target="_blank"
            rel="noreferrer"
            className="rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 px-3 py-1.5 text-slate-300 transition"
          >
            DexScreener
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
          onClick={() => navigator.clipboard?.writeText(token.address)}
          className="ml-auto rounded-lg bg-slate-800/80 hover:bg-slate-700 border border-slate-700 px-2 py-1.5 text-slate-500 transition"
          title="Copy mint"
        >
          Mint
        </button>
      </div>
    </article>
  );
}

export default function Dashboard() {
  const [feed, setFeed] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdate, setLastUpdate] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const [hawkRes, statsRes] = await Promise.all([api.hawk(30), api.stats()]);
      setFeed(hawkRes.results || []);
      setStats(statsRes);
      setError("");
      setLastUpdate(new Date());
    } catch (e) {
      setError("Live feed temporarily unavailable — retrying…");
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 28_000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <div className="min-h-screen hawk-grid">
      {/* Header */}
      <header className="sticky top-0 z-20 border-b border-slate-800/80 bg-slate-950/90 backdrop-blur-md">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-xl">
              🦅
            </div>
            <div>
              <h1 className="font-display text-xl font-extrabold tracking-tight text-white">
                ASILI <span className="text-emerald-400">HAWK</span>
              </h1>
              <p className="text-[11px] text-slate-500">Early memecoin intelligence · pre-terminal</p>
            </div>
          </div>
          <div className="flex items-center gap-4 text-xs text-slate-400">
            {stats && (
              <div className="hidden sm:flex items-center gap-3">
                <span className="text-emerald-400 font-medium">{stats.on_curve} on curve</span>
                <span className="text-yellow-400/90">{stats.prime} prime</span>
                <span>{stats.high} high</span>
              </div>
            )}
            <div className="flex items-center gap-2">
              <span className={`h-2 w-2 rounded-full ${error ? "bg-amber-400" : "bg-emerald-400 animate-pulse"}`} />
              <span>{error ? "Reconnecting" : "Live"}</span>
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

      <main className="mx-auto max-w-7xl px-4 sm:px-6 py-8">
        {/* Hero strip */}
        <section className="mb-8 rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 to-slate-950 p-6">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-widest text-emerald-500/80 font-medium mb-1">Mission</p>
              <h2 className="font-display text-2xl sm:text-3xl font-bold text-white max-w-xl">
                Find tomorrow&apos;s winners{" "}
                <span className="text-emerald-400">before the bonding curve completes</span>
              </h2>
              <p className="mt-2 text-sm text-slate-400 max-w-lg">
                Scanning Pump.fun curves + fresh Solana pairs. Prioritizing tokens still on-curve with early momentum.
              </p>
            </div>
            {lastUpdate && (
              <p className="text-[11px] text-slate-600 shrink-0">
                Updated {lastUpdate.toLocaleTimeString()}
              </p>
            )}
          </div>
        </section>

        {error && (
          <div className="mb-6 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex h-64 items-center justify-center text-slate-500">
            <div className="text-center">
              <div className="mb-3 text-3xl animate-pulse">🦅</div>
              <p className="text-sm">Scanning early launches…</p>
            </div>
          </div>
        ) : feed.length === 0 ? (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-12 text-center text-slate-500">
            No qualifying early opportunities right now. Scanner is live and will surface the next ones.
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {feed.map((token, i) => (
              <TokenCard key={token.address || i} token={token} rank={i + 1} />
            ))}
          </div>
        )}

        <footer className="mt-16 border-t border-slate-900 pt-8 pb-12 text-center text-[11px] text-slate-600">
          ASILI HAWK v0.3 · Not financial advice · Data from public Pump.fun & DexScreener endpoints
        </footer>
      </main>
    </div>
  );
}
