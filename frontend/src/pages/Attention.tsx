import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, AttentionFeed } from "../api";
import { PageHeader } from "../components/Layout";

export default function Attention() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const [feed, setFeed] = useState<AttentionFeed | null>(null);
  const [err, setErr] = useState("");
  const [sev, setSev] = useState<string>("");
  const [sort, setSort] = useState<"severity" | "recent">("severity");

  async function load() {
    try { setFeed(await api.attention(id)); }
    catch (e: any) { setErr(e.message || String(e)); }
  }
  useEffect(() => { load(); }, [id]);

  const sevOrder = { high: 0, medium: 1, low: 2 } as const;
  const filteredFindings = (feed?.open_findings || [])
    .filter((f) => !sev || f.severity === sev)
    .slice()
    .sort((a, b) => sort === "severity"
      ? sevOrder[a.severity] - sevOrder[b.severity] || b.created_at.localeCompare(a.created_at)
      : b.created_at.localeCompare(a.created_at));
  const sortedMemory = (feed?.memory_needs_review || []).slice()
    .sort((a, b) => sort === "recent"
      ? b.updated_at.localeCompare(a.updated_at)
      : (a.verification_status === "conflicting" ? -1 : 1) - (b.verification_status === "conflicting" ? -1 : 1));

  const total = (feed?.open_findings.length ?? 0) + (feed?.memory_needs_review.length ?? 0);
  const high = feed?.open_findings.filter(f => f.severity === "high").length ?? 0;
  const conflicting = feed?.memory_needs_review.filter(m => m.verification_status === "conflicting").length ?? 0;

  function sevPill(s: string) {
    const cls = s === "high" ? "sev-high" : s === "medium" ? "sev-med" : "sev-low";
    return <span className={cls}>{s}</span>;
  }
  function statusPill(s: string) {
    if (s === "conflicting") return <span className="pill pill-ochre">conflicting · source changed</span>;
    if (s === "ai_suggested") return <span className="pill pill-champagne">ai-suggested</span>;
    return <span className="pill pill-neutral">unverified</span>;
  }

  return (
    <div className="anim-fade">
      <PageHeader
        eyebrow="Needs attention"
        title="The queue for human judgement."
        subtitle="Everything on this project waiting for a decision — gap findings and memory records flagged by source drift or review."
      />
      <div className="px-10 lg:px-14 py-10 max-w-5xl space-y-14">
        {err && <div className="text-rust text-[13px]">{err}</div>}

        <section className="grid grid-cols-2 md:grid-cols-4 gap-10 anim-stagger">
          <Metric label="Open items" value={total} />
          <Metric label="High-severity gaps" value={high} />
          <Metric label="Conflicting records" value={conflicting} hint="source changed since verification" />
          <Metric label="Awaiting review" value={feed?.memory_needs_review.length ?? 0} />
        </section>

        <div className="rule" />

        <div className="flex gap-3 items-end flex-wrap">
          <div>
            <div className="eyebrow mb-2">Severity</div>
            <select className="input py-1.5 w-[180px]" value={sev} onChange={(e) => setSev(e.target.value)}>
              <option value="">All</option>
              <option value="high">high</option>
              <option value="medium">medium</option>
              <option value="low">low</option>
            </select>
          </div>
          <div>
            <div className="eyebrow mb-2">Sort</div>
            <select className="input py-1.5 w-[180px]" value={sort} onChange={(e) => setSort(e.target.value as any)}>
              <option value="severity">Severity, then newest</option>
              <option value="recent">Most recent</option>
            </select>
          </div>
        </div>

        <section>
          <div className="eyebrow">Open gap findings</div>
          <h3 className="display-s mt-2 text-ink">Where KT and the code disagree.</h3>
          {filteredFindings.length ? (
            <ol className="divide-y divide-mist mt-6">
              {filteredFindings.map((f) => (
                <li key={f.id} className="py-5 row-accent pl-4 -ml-4 rounded-sm">
                  <div className="flex items-center gap-3 flex-wrap">
                    {sevPill(f.severity)}
                    <span className="eyebrow text-stone">{f.category}</span>
                    <span className="eyebrow text-stone">status · {f.status}</span>
                  </div>
                  <Link to={`/projects/${id}/gaps`} className="block mt-2 serif text-[20px] text-ink leading-snug hover:text-graphite transition-colors">
                    {f.title}
                  </Link>
                </li>
              ))}
            </ol>
          ) : (
            <p className="mt-4 italic-serif text-[16px] text-stone">{sev ? `No ${sev}-severity findings match the filter.` : "No open findings."}</p>
          )}
          {filteredFindings.length ? (
            <div className="mt-4"><Link to={`/projects/${id}/gaps`} className="btn-link text-[13px]">Review in Gap Analysis</Link></div>
          ) : null}
        </section>

        <div className="rule" />

        <section>
          <div className="eyebrow">Memory needing review</div>
          <h3 className="display-s mt-2 text-ink">Records with changed context.</h3>
          {sortedMemory.length ? (
            <ol className="divide-y divide-mist mt-6">
              {sortedMemory.map((m) => (
                <li key={m.id} className="py-5 row-accent pl-4 -ml-4 rounded-sm">
                  <div className="flex items-center gap-3 flex-wrap">
                    {statusPill(m.verification_status)}
                    <span className="eyebrow text-stone">updated · {new Date(m.updated_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span>
                  </div>
                  <Link to={`/projects/${id}/memory`} className="block mt-2 serif text-[20px] text-ink leading-snug hover:text-graphite transition-colors">
                    {m.topic}
                  </Link>
                </li>
              ))}
            </ol>
          ) : (
            <p className="mt-4 italic-serif text-[16px] text-stone">Memory is up to date.</p>
          )}
          {feed?.memory_needs_review.length ? (
            <div className="mt-4"><Link to={`/projects/${id}/memory`} className="btn-link text-[13px]">Review in Project Memory</Link></div>
          ) : null}
        </section>
      </div>
    </div>
  );
}

function Metric({ label, value, hint }: { label: string; value: number | string; hint?: string }) {
  return (
    <div>
      <div className="eyebrow">{label}</div>
      <div className="serif text-[44px] text-ink leading-none mt-3 tracking-tightest tabular-nums metric-up">{value}</div>
      {hint && <div className="text-stone text-[12px] mt-2">{hint}</div>}
    </div>
  );
}
