import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api, ProjectDetail } from "../api";
import { PageHeader } from "../components/Layout";

const KINDS = ["auto", "transcript", "doc", "code", "ticket", "note"];

type LogEntry = { ok: boolean; title: string; detail?: string };

export default function Ingest() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [kind, setKind] = useState("auto");
  const [log, setLog] = useState<LogEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<string>("");
  const [ghUrl, setGhUrl] = useState("");
  const [ghBusy, setGhBusy] = useState(false);
  const [ghResult, setGhResult] = useState<string>("");
  const dropRef = useRef<HTMLDivElement>(null);

  async function reload() { try { setProject(await api.getProject(id)); } catch {} }
  useEffect(() => { reload(); }, [id]);

  async function upload(files: FileList) {
    setBusy(true);
    for (const f of Array.from(files)) {
      try {
        const r = await api.upload(id, f, kind === "auto" ? undefined : kind);
        let detail = `${r.chunks} chunks indexed`;
        if (r.unchanged) detail = "no change — identical content";
        else if (r.replaced_source_id) {
          detail = `${r.chunks} chunks · replaced earlier version`;
          if (r.flagged_memory_ids?.length) detail += ` · flagged ${r.flagged_memory_ids.length} record${r.flagged_memory_ids.length>1?'s':''}`;
        }
        if (r.transcribed_from) detail = `transcribed from ${r.transcribed_from} · ${r.chunks} chunks`;
        setLog((L) => [{ ok: true, title: `${r.filename} → ${r.kind}`, detail }, ...L]);
      } catch (e: any) {
        setLog((L) => [{ ok: false, title: f.name, detail: e.message || String(e) }, ...L]);
      }
    }
    setBusy(false); reload();
  }

  async function importRepo() {
    if (!ghUrl.trim()) return;
    setGhBusy(true); setGhResult("");
    try {
      const r = await api.importGithub(id, ghUrl.trim());
      setGhResult(`Imported ${r.repo} on ${r.branch} — ${r.files_ingested} files, ${r.files_skipped} skipped.`);
      setLog((L) => [{ ok: true, title: `github · ${r.repo}`, detail: `${r.files_ingested} files` }, ...L]);
      setGhUrl(""); reload();
    } catch (e: any) {
      setGhResult(`Import failed: ${e.message || String(e)}`);
    } finally { setGhBusy(false); }
  }

  async function runAnalysis() {
    setAnalyzing(true); setAnalysisResult("");
    try {
      const r = await api.analyze(id);
      setAnalysisResult(r.note || `Examined ${r.claims_examined} claims; recorded ${r.findings_created || 0} findings.`);
    } catch (e: any) {
      setAnalysisResult(`Analysis failed: ${e.message || String(e)}`);
    } finally { setAnalyzing(false); reload(); }
  }

  return (
    <div className="anim-fade">
      <PageHeader
        eyebrow="Sources"
        title="Bring the project into focus."
        subtitle="Upload transcripts, documentation, source code, or import a public GitHub repository. Audio recordings are transcribed automatically. Files are parsed as data — never executed."
      />
      <div className="px-10 lg:px-14 py-12 space-y-14 max-w-5xl">
        {/* GitHub import — single line, calm */}
        <section>
          <div className="eyebrow mb-4">Import from GitHub</div>
          <div className="flex gap-3 flex-wrap">
            <input
              className="input flex-1 min-w-[280px]"
              placeholder="https://github.com/pallets/flask"
              value={ghUrl}
              onChange={(e) => setGhUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !ghBusy && importRepo()}
            />
            <button className="btn btn-primary" onClick={importRepo} disabled={ghBusy || !ghUrl.trim()}>
              {ghBusy ? "Importing…" : "Import repository"}
            </button>
          </div>
          <div className="text-stone text-[12px] mt-3 leading-relaxed">
            Public repositories only. Up to 150 code, markdown, and configuration files. For a branch other than main/master, append <code className="code-inline">/tree/your-branch</code>.
          </div>
          {ghResult && <div className="mt-3 text-[13px] text-graphite">{ghResult}</div>}
        </section>

        <div className="rule" />

        {/* File upload */}
        <section>
          <div className="flex items-end justify-between mb-5 gap-4 flex-wrap">
            <div>
              <div className="eyebrow">Upload files</div>
              <div className="text-stone text-[12px] mt-1">
                Supported: <code className="code-inline">.txt .md .pdf .docx</code> · code (<code className="code-inline">.py .js .ts .java .go .sql</code> and more) · audio (<code className="code-inline">.mp3 .m4a .mp4 .wav</code>, auto-transcribed)
              </div>
            </div>
            <label className="text-[13px] text-graphite flex items-center gap-2">
              <span className="eyebrow">Classify</span>
              <select className="input max-w-[160px] py-1.5" value={kind} onChange={(e) => setKind(e.target.value)}>
                {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
              </select>
            </label>
          </div>

          <div
            ref={dropRef}
            onDragOver={(e) => { e.preventDefault(); dropRef.current?.classList.add("border-ink"); }}
            onDragLeave={() => dropRef.current?.classList.remove("border-ink")}
            onDrop={(e) => {
              e.preventDefault();
              dropRef.current?.classList.remove("border-ink");
              if (e.dataTransfer.files) upload(e.dataTransfer.files);
            }}
            className="border border-mist border-dashed rounded-md p-10 text-center transition-colors"
          >
            <div className="serif text-[22px] text-ink leading-tight">Drop files here.</div>
            <div className="text-stone text-[13px] mt-1">
              or <label className="btn-link cursor-pointer">choose files
                <input type="file" multiple className="hidden" onChange={(e) => { if (e.target.files) upload(e.target.files); e.currentTarget.value = ""; }} />
              </label>
            </div>
          </div>
          {busy && (
            <div className="mt-4 text-[12px] text-stone flex items-center gap-2">
              <span className="w-1 h-1 rounded-full bg-ink pulse-soft" />
              Uploading & indexing…
            </div>
          )}
        </section>

        {log.length > 0 && (
          <section className="anim-fade">
            <div className="eyebrow mb-4">Processing log</div>
            <ul className="divide-y divide-mist">
              {log.map((l, i) => (
                <li key={i} className="py-2.5 grid grid-cols-[24px_1fr_auto] gap-3 items-baseline text-[13px]">
                  <span className={l.ok ? "text-forest" : "text-rust"}>{l.ok ? "✓" : "✗"}</span>
                  <span className="mono text-ink">{l.title}</span>
                  <span className="text-stone text-[12px]">{l.detail}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        <div className="rule" />

        {/* Analyze */}
        <section>
          <div className="flex items-end justify-between gap-4 flex-wrap">
            <div>
              <div className="eyebrow">Analyze</div>
              <h2 className="display-s mt-2 text-ink">Compare claims against the evidence.</h2>
              <p className="text-stone text-[13px] mt-2 max-w-xl">Pulls assertion-shaped claims from transcripts and docs, retrieves candidate code, and classifies each as supported, contradicted, missing, or unverified.</p>
            </div>
            <button className="btn btn-primary" onClick={runAnalysis} disabled={analyzing || !project || project.sources.length < 2}>
              {analyzing ? "Analyzing…" : "Run analysis"}
            </button>
          </div>
          {analysisResult && <div className="mt-4 text-[13px] text-graphite anim-fade">{analysisResult}</div>}
        </section>

        <div className="rule" />

        {/* Source inventory */}
        <section>
          <div className="eyebrow mb-4">Source inventory</div>
          {project && project.sources.length ? (
            <table className="table">
              <thead><tr><th>File</th><th>Kind</th><th>Size</th><th>Added</th></tr></thead>
              <tbody>
                {project.sources.map((s) => (
                  <tr key={s.id}>
                    <td className="mono text-ink">{s.filename}</td>
                    <td>{s.kind}</td>
                    <td>{Math.round(s.size_bytes / 1024)} KB</td>
                    <td>{new Date(s.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="italic-serif text-[16px] text-stone">Nothing uploaded yet.</p>
          )}
        </section>
      </div>
    </div>
  );
}
