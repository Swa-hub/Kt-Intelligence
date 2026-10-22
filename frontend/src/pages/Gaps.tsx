import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, Finding } from "../api";
import { PageHeader } from "../components/Layout";

const STATUSES = ["open", "awaiting", "resolved", "dismissed"];

export default function Gaps() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [status, setStatus] = useState<string>("");
  const [severity, setSeverity] = useState<string>("");
  const [err, setErr] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);
  const [saving, setSaving] = useState<number | null>(null);

  async function load() {
    try { setFindings(await api.findings(id, { status: status || undefined, severity: severity || undefined })); }
    catch (e: any) { setErr(e.message || String(e)); }
  }
  useEffect(() => { load(); }, [id, status, severity]);

  async function setStatusFor(f: Finding, s: string) {
    setSaving(f.id);
    try { await api.updateFinding(f.id, s); await load(); }
    catch (e: any) { setErr(e.message || String(e)); }
    finally { setSaving(null); }
  }

  async function saveToMemory(f: Finding) {
    const content = `${f.title}\n\n${f.explanation}` + (f.suggested_question ? `\n\nQuestion: ${f.suggested_question}` : "");
    try {
      await api.createMemory(id, {
        topic: f.title,
        content,
        verification_status: "unverified",
        sources: [f.kt_evidence, ...(f.code_evidence || [])].filter(Boolean) as any,
      });
      await setStatusFor(f, "awaiting");
    } catch (e: any) { setErr(e.message || String(e)); }
  }

  return (
    <div className="anim-fade">
      <PageHeader
        eyebrow="Gap analysis"
        title="What was said. What the code shows."
        subtitle="A compact editorial index of findings. Open any to see the evidence on both sides."
      />
      <div className="px-10 lg:px-14 py-10 space-y-10 max-w-6xl">
        <div className="flex gap-3 items-end flex-wrap">
          <div>
            <div className="eyebrow mb-2">Status</div>
            <select className="input py-1.5 w-[180px]" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All</option>
              {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <div className="eyebrow mb-2">Severity</div>
            <select className="input py-1.5 w-[180px]" value={severity} onChange={(e) => setSeverity(e.target.value)}>
              <option value="">All</option>
              <option value="high">high</option>
              <option value="medium">medium</option>
              <option value="low">low</option>
            </select>
          </div>
          <div className="ml-auto eyebrow text-stone self-end pb-2">{findings.length} finding{findings.length === 1 ? "" : "s"}</div>
        </div>

        {err && <div className="text-rust text-[13px]">{err}</div>}

        {findings.length === 0 ? (
          <p className="italic-serif text-[18px] text-stone">
            Nothing here yet. Upload at least one transcript or document plus a code file, then run analysis from the Sources page.
          </p>
        ) : (
          <ol className="divide-y divide-mist">
            {findings.map((f) => (
              <FindingRow
                key={f.id}
                f={f}
                open={openId === f.id}
                saving={saving === f.id}
                onToggle={() => setOpenId(openId === f.id ? null : f.id)}
                onStatus={setStatusFor}
                onSave={saveToMemory}
              />
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}

function FindingRow({ f, open, saving, onToggle, onStatus, onSave }: {
  f: Finding; open: boolean; saving: boolean;
  onToggle: () => void; onStatus: (f: Finding, s: string) => void; onSave: (f: Finding) => void;
}) {
  const sevCls = f.severity === "high" ? "sev-high" : f.severity === "medium" ? "sev-med" : "sev-low";
  return (
    <li className="py-6 row-accent pl-4 -ml-4 rounded-sm">
      <button className="w-full text-left group" onClick={onToggle}>
        <div className="flex items-start gap-6">
          <div className="section-number pt-1 min-w-[52px]">{String(f.id).padStart(2, "0")}</div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 mb-2 flex-wrap">
              <span className={sevCls}>{f.severity}</span>
              <span className="eyebrow text-stone">{f.category}</span>
              <span className="eyebrow text-stone">status · {f.status}</span>
              {f.confidence !== null && <span className="eyebrow text-stone">conf · {Math.round((f.confidence || 0) * 100)}%</span>}
            </div>
            <h3 className="serif text-[22px] text-ink leading-snug group-hover:underline underline-offset-4 decoration-mist">{f.title}</h3>
          </div>
          <div className="pt-1 text-stone group-hover:text-ink transition-colors">{open ? "−" : "+"}</div>
        </div>
      </button>

      {open && (
        <div className="mt-6 pl-[76px] space-y-8 anim-fade">
          <p className="text-graphite text-[14.5px] leading-relaxed max-w-3xl">{f.explanation}</p>

          <div className="grid md:grid-cols-2 gap-10">
            <div>
              <div className="eyebrow mb-3">What was said</div>
              {f.kt_evidence ? (
                <div>
                  <div className="mono text-[11px] text-stone mb-2">{f.kt_evidence.filename}:{f.kt_evidence.start_line}–{f.kt_evidence.end_line}</div>
                  <blockquote className="serif italic-serif text-[18px] text-ink leading-snug border-l border-mist pl-5">
                    "{f.kt_evidence.excerpt}"
                  </blockquote>
                </div>
              ) : <div className="text-stone">—</div>}
            </div>
            <div>
              <div className="eyebrow mb-3">What the sources show</div>
              {f.code_evidence && f.code_evidence.length ? (
                <div className="space-y-3">
                  {f.code_evidence.slice(0, 3).map((e: any, i: number) => (
                    <div key={i}>
                      <div className="mono text-[11px] text-stone mb-2">{e.filename}:{e.start_line}–{e.end_line}</div>
                      <pre className="code">{e.excerpt || e.text}</pre>
                    </div>
                  ))}
                </div>
              ) : <div className="italic-serif text-stone text-[15px]">No matching source retrieved — this is itself a signal.</div>}
            </div>
          </div>

          {f.suggested_question && (
            <div>
              <div className="eyebrow mb-2">What to ask next</div>
              <p className="serif italic-serif text-[20px] text-ink max-w-2xl leading-snug">"{f.suggested_question}"</p>
            </div>
          )}

          <div className="flex gap-3 flex-wrap pt-2 items-center">
            <button className="btn btn-ghost" disabled={saving || f.status === "resolved"} onClick={() => onStatus(f, "resolved")}>Mark resolved</button>
            <button className="btn btn-ghost" disabled={saving || f.status === "dismissed"} onClick={() => onStatus(f, "dismissed")}>Dismiss</button>
            <button className="btn btn-ghost" disabled={saving} onClick={async () => {
              const owner = prompt("Assign to (name or email):", f.owner || "") ?? null;
              if (owner !== null) { await api.assignFinding(f.id, owner.trim() || null); location.reload(); }
            }}>Assign</button>
            <button className="btn btn-ghost" disabled={saving} onClick={async () => {
              const days = prompt("Snooze for how many days?", "7");
              if (!days) return;
              const n = parseInt(days, 10);
              if (!n || n <= 0) return;
              const until = new Date(Date.now() + n * 86400 * 1000).toISOString();
              await api.snoozeFinding(f.id, until);
              location.reload();
            }}>Snooze</button>
            <button className="btn btn-primary ml-auto" disabled={saving} onClick={() => onSave(f)}>Send to memory</button>
          </div>
          {(f.owner || f.snoozed_until) && (
            <div className="mt-3 text-[12px] text-stone flex gap-6">
              {f.owner && <span><span className="eyebrow mr-2">Owner</span>{f.owner}</span>}
              {f.snoozed_until && <span><span className="eyebrow mr-2">Snoozed until</span>{new Date(f.snoozed_until).toLocaleDateString()}</span>}
            </div>
          )}
        </div>
      )}
    </li>
  );
}
