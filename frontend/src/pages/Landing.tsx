import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Project } from "../api";

export default function Landing() {
  const nav = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.listProjects().then(setProjects).catch(() => {}); }, []);

  async function create() {
    if (!name.trim()) return;
    setBusy(true); setErr("");
    try {
      const p = await api.createProject(name.trim(), desc.trim() || undefined);
      nav(`/projects/${p.id}/ingest`);
    } catch (e: any) {
      setErr(e.message || String(e));
    } finally { setBusy(false); }
  }

  return (
    <div className="anim-fade">
      {/* HERO */}
      <section className="relative px-8 lg:px-12 pt-16 lg:pt-24 pb-20 max-w-7xl mx-auto overflow-hidden">
        <div className="accent-orb" style={{ top: -40, right: 40 }} aria-hidden="true" />
        <div className="accent-orb forest" style={{ top: 160, right: -60 }} aria-hidden="true" />
        <div className="relative">
          <div className="eyebrow">Engineering knowledge, reimagined</div>
          <div className="mt-6 grid lg:grid-cols-[1.1fr_1fr] gap-16 items-start">
            <div>
              <h1 className="display-xl text-ink text-balance anim-rise">
                Knowledge is only valuable <span className="italic-serif ink-shimmer">when it works.</span>
              </h1>
            <p className="mt-8 text-lg text-graphite leading-relaxed max-w-xl anim-rise" style={{ animationDelay: "80ms" }}>
              Connect technical conversations, documentation, and source code
              to uncover what your team knows, what it's missing, and what
              needs to be verified.
            </p>
            <div className="mt-10 flex items-center gap-4 flex-wrap anim-rise" style={{ animationDelay: "160ms" }}>
              <a href="#start" className="btn btn-primary">Enter the Workspace →</a>
              <a href="#how" className="btn btn-ghost">Discover how it works</a>
            </div>
            <div className="mt-10 flex items-center gap-3 text-stone text-[11.5px]">
              <span className="inline-block w-1 h-1 rounded-full bg-forest"></span>
              <span className="eyebrow">Source-grounded intelligence</span>
            </div>
          </div>

            <div className="anim-rise" style={{ animationDelay: "240ms" }}>
              <ProductPreview />
            </div>
          </div>
        </div>
      </section>

      <Divider />

      {/* CAPABILITIES */}
      <section id="capabilities" className="px-8 lg:px-12 py-24 max-w-7xl mx-auto">
        <div className="max-w-3xl">
          <div className="eyebrow">Capabilities</div>
          <h2 className="display-l mt-6 text-ink text-balance">
            Four quiet instruments. <span className="italic-serif">One continuous memory.</span>
          </h2>
        </div>

        <div className="mt-16 space-y-16">
          <Capability
            num="01"
            title="Understand"
            body="Transform transcripts, documentation, and source code into a structured project knowledge base. Each fact keeps its provenance — the file, the line, the person."
            right={<CapabilityVisual kind="understand" />}
          />
          <Divider />
          <Capability
            num="02"
            title="Verify"
            body="Detect contradictions, missing explanations, outdated information, and unverified claims. Evidence lives on both sides of every finding."
            right={<CapabilityVisual kind="verify" />}
            reverse
          />
          <Divider />
          <Capability
            num="03"
            title="Learn"
            body="Help developers understand unfamiliar systems through grounded, personalised AI tutoring — beginner through advanced, every answer cites its source."
            right={<CapabilityVisual kind="learn" />}
          />
          <Divider />
          <Capability
            num="04"
            title="Remember"
            body="Preserve verified knowledge and track changes across future handovers. Conflicts are kept side-by-side rather than silently overwritten."
            right={<CapabilityVisual kind="remember" />}
            reverse
          />
        </div>
      </section>

      <Divider />

      {/* HOW IT WORKS */}
      <section id="how" className="px-8 lg:px-12 py-24 max-w-7xl mx-auto">
        <div className="grid md:grid-cols-[1fr_2fr] gap-12">
          <div>
            <div className="eyebrow">How it works</div>
            <h2 className="display-m mt-4 text-ink text-balance">
              A workflow for teams that <span className="italic-serif">can't afford to forget.</span>
            </h2>
          </div>
          <ol className="space-y-10">
            {[
              ["Ingest", "Drop in transcripts, documents, source code, or a public GitHub URL. Audio recordings transcribe automatically."],
              ["Analyse", "The model compares KT claims against retrieved evidence from your sources and classifies each as supported, contradicted, missing, or unverified."],
              ["Review", "A compact editorial index of findings — each with the transcript statement, the matching code, and the question to ask next."],
              ["Teach", "An AI tutor grounded in your project, with inline citations, learning levels and quiz mode."],
              ["Preserve", "Verified knowledge enters a durable memory. Changes to source files flag affected records for human review."],
            ].map(([step, body], i) => (
              <li key={step} className="grid grid-cols-[52px_1fr] gap-6 items-baseline">
                <div className="section-number">{String(i + 1).padStart(2, "0")}</div>
                <div>
                  <div className="serif text-[22px] text-ink leading-tight">{step}</div>
                  <div className="mt-2 text-graphite text-[14px] leading-relaxed max-w-xl">{body}</div>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <Divider />

      {/* FINAL CTA + WORKSPACE */}
      <section id="start" className="px-8 lg:px-12 py-24 max-w-7xl mx-auto">
        <div className="max-w-3xl">
          <h2 className="display-l text-ink text-balance">
            Make every handover <span className="italic-serif">count.</span>
          </h2>
          <p className="mt-5 text-stone max-w-xl leading-relaxed">
            Turn scattered project knowledge into something your team can trust,
            understand, and build on.
          </p>
        </div>

        <div id="projects" className="mt-14 grid md:grid-cols-[1.2fr_1fr] gap-10 items-start">
          <div className="panel p-8">
            <div className="eyebrow">New workspace</div>
            <h3 className="serif text-[26px] mt-3 text-ink">Create a project.</h3>
            <p className="text-stone text-[13px] mt-1">Upload KT material, run analysis, preserve verified knowledge.</p>
            <div className="mt-6 space-y-3">
              <input
                className="input"
                placeholder="Project name (e.g. billing-service handover)"
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && create()}
              />
              <textarea
                className="input min-h-[88px]"
                placeholder="Short description (optional)"
                value={desc}
                onChange={(e) => setDesc(e.target.value)}
              />
              {err && <div className="text-rust text-[12px]">{err}</div>}
              <div>
                <button className="btn btn-primary" onClick={create} disabled={busy || !name.trim()}>
                  {busy ? "Creating…" : "Launch Workspace →"}
                </button>
              </div>
            </div>
          </div>

          <div>
            <div className="eyebrow">Recent projects</div>
            {projects.length === 0 ? (
              <div className="mt-6 text-stone text-[13px] italic-serif text-[16px]">
                Nothing here yet.
              </div>
            ) : (
              <ul className="mt-6 divide-y divide-mist">
                {projects.map((p) => (
                  <li key={p.id} className="py-4 flex items-center justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="serif text-[18px] text-ink truncate">{p.name}</div>
                      <div className="text-stone text-[12px] mt-0.5">{new Date(p.created_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}</div>
                    </div>
                    <button className="btn-link text-[13px] shrink-0" onClick={() => nav(`/projects/${p.id}`)}>Open</button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

function Divider() { return <div className="max-w-7xl mx-auto px-8 lg:px-12"><div className="rule" /></div>; }

function Capability({ num, title, body, right, reverse = false }: { num: string; title: string; body: string; right: React.ReactNode; reverse?: boolean }) {
  return (
    <div className={`grid lg:grid-cols-2 gap-10 items-center ${reverse ? "lg:[&>*:first-child]:order-2" : ""}`}>
      <div className="max-w-lg">
        <div className="flex items-baseline gap-6">
          <div className="section-number">{num}</div>
          <h3 className="display-m text-ink">{title}</h3>
        </div>
        <p className="mt-5 text-graphite leading-relaxed text-[15px]">{body}</p>
      </div>
      <div>{right}</div>
    </div>
  );
}

/* ---------- Bespoke product preview (SVG + composed UI) ---------- */

function ProductPreview() {
  return (
    <div className="relative">
      <div className="panel panel-ivory panel-hover p-5 shadow-[0_30px_80px_-50px_rgba(17,17,16,0.3)]">
        <div className="eyebrow text-stone">Gap · routes.py vs. transcript 2026-09-14</div>
        <div className="mt-4 grid grid-cols-2 gap-4">
          <div className="bg-paper border border-mist rounded p-3">
            <div className="eyebrow text-stone">What was said</div>
            <blockquote className="mt-2 serif text-[15px] italic-serif text-ink leading-snug">
              "Every endpoint on this service requires authentication."
            </blockquote>
            <div className="mt-3 mono text-[10.5px] text-stone">transcript.txt:11–14</div>
          </div>
          <div className="bg-paper border border-mist rounded p-3">
            <div className="eyebrow text-stone">What the code shows</div>
            <pre className="code mt-2 text-[11px] bg-paper border-0 p-0">
{`@bp.get("/orders/<int:order_id>")
@rate_limit
def get_order(order_id):
    ...`}
            </pre>
            <div className="mt-2 mono text-[10.5px] text-stone">routes.py:33–50</div>
          </div>
        </div>
        <div className="mt-4 flex items-center justify-between">
          <span className="sev-high">Contradiction · high</span>
          <span className="eyebrow text-stone">Confidence 82%</span>
        </div>
      </div>
      <div className="absolute -bottom-5 -right-5 panel bg-paper px-4 py-3 shadow-[0_12px_30px_-20px_rgba(17,17,16,0.4)] hidden sm:block">
        <div className="eyebrow text-stone">Next question</div>
        <div className="serif text-[15px] text-ink mt-1 max-w-[280px] leading-snug">
          Was the missing <span className="code-inline">@require_auth</span> intentional?
        </div>
      </div>
    </div>
  );
}

function CapabilityVisual({ kind }: { kind: "understand" | "verify" | "learn" | "remember" }) {
  if (kind === "understand") {
    return (
      <div className="panel panel-hover p-6">
        <div className="eyebrow mb-4">Sources ingested</div>
        <ul className="divide-y divide-mist text-[13px]">
          {[
            ["transcript.txt", "transcript", "2 KB"],
            ["routes.py", "code", "2 KB"],
            ["payments.py", "code", "1 KB"],
            ["ORDR-412.md", "doc", "1 KB"],
          ].map(([n, k, s]) => (
            <li key={n} className="py-2.5 flex items-center justify-between">
              <span className="mono text-ink">{n}</span>
              <span className="text-stone text-[11.5px]">{k} · {s}</span>
            </li>
          ))}
        </ul>
      </div>
    );
  }
  if (kind === "verify") {
    return (
      <div className="panel panel-ivory panel-hover p-6">
        <div className="eyebrow mb-4">Findings</div>
        <ul className="space-y-3 text-[13px]">
          <li className="flex items-start gap-3"><span className="sev-high">high</span><span className="text-ink">Transcript claims every endpoint requires auth — <span className="italic-serif">get_order is missing @require_auth.</span></span></li>
          <li className="flex items-start gap-3"><span className="sev-med">med</span><span className="text-ink">Idempotency key handling is mentioned but never implemented.</span></li>
          <li className="flex items-start gap-3"><span className="pill pill-forest">supported</span><span className="text-stone">Stripe retry policy matches payments.charge.</span></li>
        </ul>
      </div>
    );
  }
  if (kind === "learn") {
    return (
      <div className="panel panel-hover p-6">
        <div className="eyebrow">Tutor</div>
        <div className="mt-3 serif text-[16px] text-ink leading-snug">
          Which endpoints are protected?
        </div>
        <div className="mt-4 text-graphite text-[13px] leading-relaxed">
          Three endpoints apply <span className="code-inline">@require_auth</span> in <span className="code-inline">routes.py</span> [1]. <span className="italic-serif">get_order</span> [2] is undecorated — only rate limiting is applied.
        </div>
        <div className="mt-4 mono text-[10.5px] text-stone">
          [1] routes.py:25–32 &nbsp; [2] routes.py:33–50
        </div>
      </div>
    );
  }
  return (
    <div className="panel panel-ivory panel-hover p-6">
      <div className="eyebrow mb-4">Memory</div>
      <ul className="divide-y divide-mist text-[13px]">
        <li className="py-3 flex items-start justify-between gap-3">
          <div>
            <div className="serif text-[16px] text-ink">Stripe retry policy</div>
            <div className="text-stone text-[12px] mt-0.5">Verified · 2 sources</div>
          </div>
          <span className="pill pill-forest">verified</span>
        </li>
        <li className="py-3 flex items-start justify-between gap-3">
          <div>
            <div className="serif text-[16px] text-ink">Deployment target</div>
            <div className="text-stone text-[12px] mt-0.5">Unverified · needs confirmation</div>
          </div>
          <span className="pill pill-neutral">unverified</span>
        </li>
      </ul>
    </div>
  );
}
