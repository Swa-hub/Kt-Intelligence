import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, BenchmarkResult, Finding, MemoryRecord, ProjectDetail, ProjectOverview } from "../api";
import { PageHeader } from "../components/Layout";

export default function Dashboard() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [memory, setMemory] = useState<MemoryRecord[]>([]);
  const [overview, setOverview] = useState<ProjectOverview | null>(null);
  const [overviewBusy, setOverviewBusy] = useState(false);
  const [overviewErr, setOverviewErr] = useState("");
  const [bench, setBench] = useState<BenchmarkResult | null>(null);
  const [benchBusy, setBenchBusy] = useState(false);
  const [err, setErr] = useState("");

  async function runBenchmark() {
    setBenchBusy(true);
    try { setBench(await api.benchmark()); }
    catch (e: any) { setErr(e.message || String(e)); }
    finally { setBenchBusy(false); }
  }

  async function load() {
    try {
      const [p, f, m] = await Promise.all([api.getProject(id), api.findings(id), api.listMemory(id)]);
      setProject(p); setFindings(f); setMemory(m);
    } catch (e: any) { setErr(e.message || String(e)); }
  }
  useEffect(() => { load(); }, [id]);

  async function generateOverview() {
    setOverviewBusy(true); setOverviewErr("");
    try { setOverview(await api.overview(id)); }
    catch (e: any) { setOverviewErr(e.message || String(e)); }
    finally { setOverviewBusy(false); }
  }

  const open = findings.filter((f) => f.status === "open");
  const awaiting = findings.filter((f) => f.status === "awaiting");
  const verified = memory.filter((m) => m.verification_status === "verified");

  return (
    <div className="anim-fade">
      <PageHeader
        eyebrow="Overview"
        title={project?.name || ""}
        subtitle={project?.description || "Overview of what's known, what's open, and what's verified."}
        actions={
          <>
            <a
              className="btn btn-ghost"
              href={api.exportUrl(id)}
              download={`${project?.name?.replace(/[^a-z0-9-_]+/gi, "_") || "project"}-handover.md`}
            >Export handover</a>
            <Link to={`/projects/${id}/ingest`} className="btn btn-ghost">Add sources</Link>
            <Link to={`/projects/${id}/gaps`} className="btn btn-primary">Review gaps →</Link>
          </>
        }
      />

      <div className="px-10 lg:px-14 py-12 space-y-16 max-w-6xl">
        {err && <div className="text-rust text-[13px]">{err}</div>}

        {/* Metric strip — typographic, not boxed */}
        <section className="grid grid-cols-2 md:grid-cols-4 gap-10 anim-stagger">
          <Metric label="Sources" value={project?.sources.length ?? 0} />
          <Metric label="Open findings" value={open.length} hint={open.filter((f) => f.severity === "high").length ? `${open.filter((f) => f.severity === "high").length} high severity` : undefined} />
          <Metric label="Awaiting verification" value={awaiting.length + memory.filter((m) => m.verification_status === "unverified").length} />
          <Metric label="Verified knowledge" value={verified.length} hint="in Project Memory" />
        </section>

        <div className="rule" />

        {/* Benchmark panel — the ROI number */}
        <section>
          <div className="flex items-end justify-between gap-6 mb-6 flex-wrap">
            <div>
              <div className="eyebrow">Benchmark</div>
              <h2 className="display-s mt-2 text-ink">What this product measurably does.</h2>
              <p className="text-stone text-[13px] mt-2 max-w-xl leading-relaxed">
                Runs the planted-contradiction scenario end-to-end on a disposable project and reports the real timings and detection outcome.
              </p>
            </div>
            <button className="btn btn-ghost" onClick={runBenchmark} disabled={benchBusy}>
              {benchBusy ? "Running…" : bench ? "Re-run benchmark" : "Run benchmark"}
            </button>
          </div>
          {bench && (
            <div className="anim-fade grid grid-cols-2 md:grid-cols-4 gap-10">
              <div>
                <div className="eyebrow">Bytes ingested</div>
                <div className="serif text-[36px] text-ink leading-none mt-2 tabular-nums metric-up">{bench.bytes_ingested.toLocaleString()}</div>
                <div className="text-stone text-[12px] mt-2">{bench.files_ingested} files</div>
              </div>
              <div>
                <div className="eyebrow">Claims examined</div>
                <div className="serif text-[36px] text-ink leading-none mt-2 tabular-nums metric-up" style={{ animationDelay: "60ms" }}>{bench.claims_examined}</div>
                <div className="text-stone text-[12px] mt-2">via {bench.extraction_method} extraction</div>
              </div>
              <div>
                <div className="eyebrow">Findings</div>
                <div className="serif text-[36px] text-ink leading-none mt-2 tabular-nums metric-up" style={{ animationDelay: "120ms" }}>{bench.findings_created}</div>
                <div className="text-stone text-[12px] mt-2">
                  {bench.findings_by_severity.high} high · {bench.findings_by_severity.medium} med · {bench.findings_by_severity.low} low
                </div>
              </div>
              <div>
                <div className="eyebrow">Time</div>
                <div className="serif text-[36px] text-ink leading-none mt-2 tabular-nums metric-up" style={{ animationDelay: "180ms" }}>{bench.timings_sec.total}s</div>
                <div className="text-stone text-[12px] mt-2">ingest {bench.timings_sec.ingest}s · analyze {bench.timings_sec.analyze}s</div>
              </div>
              <div className="col-span-2 md:col-span-4 mt-2">
                {bench.hero_contradiction_detected ? (
                  <div className="serif italic-serif text-[20px] text-ink leading-snug">
                    Hero contradiction detected · <span className="pill pill-forest">pass</span>
                  </div>
                ) : (
                  <div className="serif italic-serif text-[20px] text-ink leading-snug">
                    Hero contradiction missed · <span className="pill pill-rust">fail</span>
                  </div>
                )}
                <div className="text-stone text-[12px] mt-2">
                  Mode: <span className="mono">{bench.mode}</span> — set <code className="code-inline">LLM_API_KEY</code> for a live run.
                </div>
              </div>
            </div>
          )}
          {!bench && !benchBusy && (
            <p className="italic-serif text-[16px] text-stone">
              Click to measure. The result is a single demo-reproducible number you can quote in your pitch.
            </p>
          )}
        </section>

        <div className="rule" />

        {/* Overview panel */}
        <section>
          <div className="flex items-end justify-between gap-6 mb-6">
            <div>
              <div className="eyebrow">Project overview</div>
              <h2 className="display-s mt-2 text-ink">Grounded, module by module.</h2>
            </div>
            <button className="btn btn-ghost" onClick={generateOverview} disabled={overviewBusy || !project?.sources.length}>
              {overviewBusy ? "Generating…" : overview ? "Regenerate" : "Generate overview"}
            </button>
          </div>
          {overviewErr && <div className="text-rust text-[13px]">{overviewErr}</div>}
          {overview && !overview.parse_error && !overview.error && (
            <div className="space-y-8 anim-fade">
              {overview.purpose && (
                <p className="serif text-[22px] text-ink max-w-3xl leading-snug text-balance">{overview.purpose}</p>
              )}
              {overview.stack && overview.stack.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {overview.stack.map((s, i) => (<span key={i} className="pill pill-neutral">{s}</span>))}
                </div>
              )}
              {overview.modules && overview.modules.length > 0 && (
                <div>
                  <div className="eyebrow mb-4">Modules</div>
                  <ul className="divide-y divide-mist">
                    {overview.modules.map((m, i) => (
                      <li key={i} className="py-4 grid md:grid-cols-[160px_1fr] gap-6">
                        <div className="serif text-[18px] text-ink">{m.name}</div>
                        <div>
                          <div className="text-graphite text-[13.5px] leading-relaxed">{m.purpose}</div>
                          {m.files && m.files.length > 0 && (
                            <div className="mono text-[11px] text-stone mt-2">{m.files.join(" · ")}</div>
                          )}
                          {m.notes && <div className="italic-serif text-[14px] text-ink mt-2">{m.notes}</div>}
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {overview.open_questions && overview.open_questions.length > 0 && (
                <div>
                  <div className="eyebrow mb-3">Open questions</div>
                  <ol className="space-y-2 text-[14px] text-graphite max-w-2xl list-decimal list-inside marker:text-stone">
                    {overview.open_questions.map((q, i) => (<li key={i}>{q}</li>))}
                  </ol>
                </div>
              )}
            </div>
          )}
          {overview?.parse_error && <div className="text-ochre text-[13px]">The model returned an unparseable response. Try regenerating.</div>}
          {!overview && !overviewBusy && !overviewErr && (
            <div className="text-stone text-[13.5px] italic-serif text-[16px]">
              Not yet generated. The overview reads your project's sources and produces a module-by-module summary.
            </div>
          )}
        </section>

        <div className="rule" />

        {/* Two editorial sections side by side */}
        <section className="grid md:grid-cols-2 gap-12">
          <div>
            <div className="eyebrow">Needs attention</div>
            <h3 className="display-s mt-2 text-ink">Open findings.</h3>
            {open.length === 0 ? (
              <p className="mt-4 italic-serif text-[16px] text-stone">Nothing open right now.</p>
            ) : (
              <ul className="mt-6 divide-y divide-mist">
                {open.slice(0, 5).map((f) => (
                  <li key={f.id} className="py-4">
                    <div className="flex items-center gap-3">
                      <SevBadge sev={f.severity} />
                      <span className="eyebrow text-stone">{f.category}</span>
                    </div>
                    <div className="serif text-[18px] text-ink mt-2 leading-snug">{f.title}</div>
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-6"><Link to={`/projects/${id}/gaps`} className="btn-link text-[13px]">All findings</Link></div>
          </div>

          <div>
            <div className="eyebrow">Recently established</div>
            <h3 className="display-s mt-2 text-ink">Verified knowledge.</h3>
            {memory.length === 0 ? (
              <p className="mt-4 italic-serif text-[16px] text-stone">Memory is empty.</p>
            ) : (
              <ul className="mt-6 divide-y divide-mist">
                {memory.slice(0, 5).map((m) => (
                  <li key={m.id} className="py-4">
                    <div className="flex items-center gap-3">
                      <MemoryStatus status={m.verification_status} />
                      <span className="eyebrow text-stone">{new Date(m.updated_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span>
                    </div>
                    <div className="serif text-[18px] text-ink mt-2 leading-snug">{m.topic}</div>
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-6"><Link to={`/projects/${id}/memory`} className="btn-link text-[13px]">All records</Link></div>
          </div>
        </section>

        <div className="rule" />

        {/* Sources table */}
        <section>
          <div className="eyebrow">Sources</div>
          <h3 className="display-s mt-2 text-ink">What this project contains.</h3>
          {project && project.sources.length > 0 ? (
            <table className="table mt-6">
              <thead><tr><th>File</th><th>Kind</th><th>Size</th><th>Added</th></tr></thead>
              <tbody>
                {project.sources.map((s) => (
                  <tr key={s.id}>
                    <td className="mono text-ink">{s.filename}</td>
                    <td>{s.kind}</td>
                    <td>{Math.round(s.size_bytes / 1024)} KB</td>
                    <td>{new Date(s.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="mt-4 italic-serif text-[16px] text-stone">No sources uploaded yet.</p>
          )}
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

function SevBadge({ sev }: { sev: "high" | "medium" | "low" }) {
  const cls = sev === "high" ? "sev-high" : sev === "medium" ? "sev-med" : "sev-low";
  return <span className={cls}>{sev}</span>;
}

function MemoryStatus({ status }: { status: string }) {
  if (status === "verified") return <span className="pill pill-forest">verified</span>;
  if (status === "conflicting") return <span className="pill pill-ochre">conflicting</span>;
  if (status === "outdated") return <span className="pill pill-neutral">outdated</span>;
  if (status === "ai_suggested") return <span className="pill pill-champagne">ai-suggested</span>;
  return <span className="pill pill-neutral">unverified</span>;
}
