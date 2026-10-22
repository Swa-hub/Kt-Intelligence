import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, MemoryEvent, MemoryRecord } from "../api";
import { PageHeader } from "../components/Layout";

const STATUSES = ["verified", "unverified", "ai_suggested", "conflicting", "outdated"];

function pillFor(s: string): string {
  if (s === "verified") return "pill pill-forest";
  if (s === "conflicting") return "pill pill-ochre";
  if (s === "ai_suggested") return "pill pill-champagne";
  if (s === "outdated") return "pill pill-neutral";
  return "pill pill-neutral";
}

function Timeline({ recordId }: { recordId: number }) {
  const [open, setOpen] = useState(false);
  const [events, setEvents] = useState<MemoryEvent[] | null>(null);
  const [loading, setLoading] = useState(false);
  async function toggle() {
    if (open) { setOpen(false); return; }
    setOpen(true);
    if (events || loading) return;
    setLoading(true);
    try { setEvents(await api.memoryEvents(recordId)); } catch {}
    finally { setLoading(false); }
  }
  return (
    <>
      <button className="btn-link text-[12px]" onClick={toggle}>{open ? "Hide history" : "History"}</button>
      {open && (
        <div className="basis-full mt-3 anim-fade">
          {loading && <div className="h-10 skel" />}
          {events && events.length > 0 && (
            <ol className="divide-y divide-mist border-l border-mist pl-5 ml-1">
              {events.map((e) => (
                <li key={e.id} className="py-2 text-[12.5px]">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="eyebrow text-stone">{new Date(e.created_at).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                    <span className="text-ink">{e.from_status ? `${e.from_status} → ${e.to_status}` : `${e.to_status}`}</span>
                    <span className="text-stone">by {e.actor}</span>
                  </div>
                  {e.reason && <div className="text-stone italic-serif text-[13px] mt-0.5">{e.reason}</div>}
                </li>
              ))}
            </ol>
          )}
          {events && events.length === 0 && <div className="text-stone text-[12px]">No events recorded.</div>}
        </div>
      )}
    </>
  );
}

export default function Memory() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const [records, setRecords] = useState<MemoryRecord[]>([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [showNew, setShowNew] = useState(false);
  const [topic, setTopic] = useState("");
  const [content, setContent] = useState("");
  const [vStatus, setVStatus] = useState("verified");
  const [err, setErr] = useState("");

  async function load() {
    try { setRecords(await api.listMemory(id, q || undefined, status || undefined)); }
    catch (e: any) { setErr(e.message || String(e)); }
  }
  useEffect(() => { load(); }, [id, status]);

  async function save() {
    try {
      await api.createMemory(id, { topic, content, verification_status: vStatus });
      setTopic(""); setContent(""); setShowNew(false); load();
    } catch (e: any) { setErr(e.message || String(e)); }
  }

  async function updateStatus(r: MemoryRecord, s: string) {
    try { await api.updateMemory(r.id, s); load(); } catch (e: any) { setErr(e.message || String(e)); }
  }

  return (
    <div className="anim-fade">
      <PageHeader
        eyebrow="Project memory"
        title="A curated archive of what is known."
        subtitle="Verified facts, decisions, bugs, and gaps. Conflicts are preserved rather than overwritten."
        actions={<button className="btn btn-primary" onClick={() => setShowNew((v) => !v)}>+ New record</button>}
      />
      <div className="px-10 lg:px-14 py-10 space-y-10 max-w-5xl">
        <div className="flex gap-3 items-end flex-wrap">
          <div className="flex-1 min-w-[260px] max-w-sm">
            <div className="eyebrow mb-2">Search</div>
            <input className="input" placeholder="Topic or content…" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && load()} />
          </div>
          <div>
            <div className="eyebrow mb-2">Status</div>
            <select className="input py-1.5 w-[200px]" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All</option>
              {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <button className="btn btn-ghost" onClick={load}>Search</button>
        </div>

        {err && <div className="text-rust text-[13px]">{err}</div>}

        {showNew && (
          <div className="panel p-6 anim-fade">
            <div className="eyebrow mb-3">New record</div>
            <div className="space-y-3">
              <input className="input" placeholder="Topic (e.g. Auth on /checkout)" value={topic} onChange={(e) => setTopic(e.target.value)} />
              <textarea className="input min-h-[120px]" placeholder="What is known, verified against what, by whom?" value={content} onChange={(e) => setContent(e.target.value)} />
              <select className="input py-1.5 max-w-[240px]" value={vStatus} onChange={(e) => setVStatus(e.target.value)}>
                {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
              <div className="flex gap-2">
                <button className="btn btn-primary" onClick={save} disabled={!topic.trim() || !content.trim()}>Save record</button>
                <button className="btn btn-ghost" onClick={() => setShowNew(false)}>Cancel</button>
              </div>
            </div>
          </div>
        )}

        {records.length === 0 ? (
          <p className="italic-serif text-[18px] text-stone">No records yet.</p>
        ) : (
          <ol className="divide-y divide-mist">
            {records.map((r) => (
              <li key={r.id} className="py-6">
                <div className="flex items-start gap-6">
                  <div className="eyebrow min-w-[80px] text-stone pt-1">{new Date(r.updated_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 flex-wrap">
                      <span className={pillFor(r.verification_status)}>{r.verification_status}</span>
                    </div>
                    <h3 className="serif text-[22px] text-ink mt-2 leading-snug">{r.topic}</h3>
                    <p className="text-graphite text-[14px] mt-3 leading-relaxed whitespace-pre-wrap max-w-3xl">{r.content}</p>
                    {r.sources && r.sources.length > 0 && (
                      <div className="mono text-[11px] text-stone mt-4">
                        {r.sources.map((s: any, i: number) => (
                          <span key={i} className="mr-4">{s.filename}{s.start_line ? `:${s.start_line}–${s.end_line}` : ""}</span>
                        ))}
                      </div>
                    )}
                    <div className="flex gap-4 mt-4 items-center flex-wrap">
                      {r.verification_status !== "verified" && <button className="btn-link text-[12px]" onClick={() => updateStatus(r, "verified")}>Mark verified</button>}
                      {r.verification_status !== "outdated" && <button className="btn-link text-[12px]" onClick={() => updateStatus(r, "outdated")}>Mark outdated</button>}
                      <Timeline recordId={r.id} />
                    </div>
                  </div>
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
