import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, getApiToken, ProjectDetail, setApiToken } from "../api";
import { PageHeader } from "../components/Layout";

export default function Settings() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const nav = useNavigate();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [health, setHealth] = useState<any>(null);
  const [confirming, setConfirming] = useState(false);
  const [err, setErr] = useState("");
  const [token, setToken] = useState(getApiToken());
  const [tokenSaved, setTokenSaved] = useState(false);

  useEffect(() => {
    api.getProject(id).then(setProject).catch(() => {});
    api.health().then(setHealth).catch(() => {});
  }, [id]);

  async function destroy() {
    try { await api.deleteProject(id); nav("/"); }
    catch (e: any) { setErr(e.message || String(e)); }
  }

  return (
    <div className="anim-fade">
      <PageHeader eyebrow="Settings" title="Project metadata." subtitle="Model status, project information, data controls." />
      <div className="px-10 lg:px-14 py-10 space-y-14 max-w-3xl">

        <section>
          <div className="eyebrow mb-4">Intelligence</div>
          {health ? (
            <dl className="divide-y divide-mist">
              <Row label="Status">
                {health.llm_configured ? <span className="pill pill-forest">Connected</span> : <span className="pill pill-ochre">Not configured</span>}
              </Row>
              <Row label="Endpoint"><span className="mono text-[12px] break-all">{health.base_url}</span></Row>
              <Row label="Model"><span className="mono text-[12px]">{health.model}</span></Row>
              <Row label="Embeddings"><span className="mono text-[12px]">{health.embed_model || "disabled"}</span></Row>
            </dl>
          ) : <p className="italic-serif text-[16px] text-stone">Loading…</p>}
          {!health?.llm_configured && (
            <p className="text-stone text-[12.5px] mt-4 leading-relaxed max-w-xl">
              Set <code className="code-inline">LLM_API_KEY</code> in <code className="code-inline">backend/.env</code> and restart the backend. The key stays on the server; the browser never sees it.
            </p>
          )}
        </section>

        <div className="rule" />

        <section>
          <div className="eyebrow mb-4">Project</div>
          {project ? (
            <dl className="divide-y divide-mist">
              <Row label="Name"><span className="text-ink">{project.name}</span></Row>
              <Row label="Description"><span className="text-graphite">{project.description || "—"}</span></Row>
              <Row label="Created"><span className="text-graphite">{new Date(project.created_at).toLocaleString()}</span></Row>
              <Row label="Sources"><span className="text-graphite">{project.sources.length}</span></Row>
              <Row label="Chunks"><span className="text-graphite">{project.stats.chunks}</span></Row>
            </dl>
          ) : <p className="italic-serif text-[16px] text-stone">Loading…</p>}
        </section>

        <div className="rule" />

        <section>
          <div className="eyebrow mb-4">API access</div>
          <p className="text-stone text-[13px] max-w-xl leading-relaxed">
            If the backend has <code className="code-inline">API_AUTH_TOKEN</code> set, every request from the browser must send that token as a bearer header. The token is stored in your browser's <code className="code-inline">localStorage</code> only — never sent anywhere except to this backend.
          </p>
          <div className="mt-4 flex gap-2 items-end flex-wrap">
            <div className="flex-1 min-w-[280px]">
              <div className="eyebrow mb-2">Token</div>
              <input
                className="input"
                type="password"
                placeholder="Paste the API_AUTH_TOKEN from your backend .env"
                value={token}
                onChange={(e) => { setToken(e.target.value); setTokenSaved(false); }}
              />
            </div>
            <button
              className="btn btn-primary"
              onClick={() => { setApiToken(token.trim()); setTokenSaved(true); }}
            >Save</button>
            {token && (
              <button
                className="btn btn-ghost"
                onClick={() => { setApiToken(""); setToken(""); setTokenSaved(true); }}
              >Clear</button>
            )}
          </div>
          {tokenSaved && <div className="text-forest text-[12px] mt-2">Saved to this browser only.</div>}
        </section>

        <div className="rule" />

        <section>
          <div className="eyebrow mb-4">Connect this project to a GitHub repository</div>
          <p className="text-stone text-[13px] max-w-xl leading-relaxed">
            Two integrations watch a repo for drift: a push webhook (re-ingests changed files automatically) and a Pull Request action (posts a comment naming the memory records a PR might invalidate).
          </p>
          <div className="mt-4 panel panel-ivory p-5">
            <div className="eyebrow mb-2">1 · Push webhook</div>
            <p className="text-graphite text-[13px]">In your repo on GitHub: <strong>Settings → Webhooks → Add webhook</strong>.</p>
            <dl className="mt-3 divide-y divide-mist">
              <Row label="Payload URL">
                <span className="mono text-[12px] break-all">
                  {(health?.base_url || window.location.origin).replace(/\/$/, "")}/api/webhooks/github/{id}
                </span>
              </Row>
              <Row label="Content type"><span className="mono text-[12px]">application/json</span></Row>
              <Row label="Secret">
                <div>
                  <div className="mono text-[12px]">Set the same string as <code className="code-inline">GITHUB_WEBHOOK_SECRET</code> in <code className="code-inline">backend/.env</code>.</div>
                  <div className="text-stone text-[11.5px] mt-1">Leave both empty to accept unsigned payloads (fine for local demos, not production).</div>
                </div>
              </Row>
              <Row label="Which events"><span className="text-graphite text-[13px]">Just the <strong>push</strong> event.</span></Row>
            </dl>
          </div>

          <div className="mt-4 panel panel-ivory p-5">
            <div className="eyebrow mb-2">2 · PR comment action</div>
            <p className="text-graphite text-[13px]">Drop the template into your repo at <code className="code-inline">.github/workflows/kt-drift.yml</code>.</p>
            <dl className="mt-3 divide-y divide-mist">
              <Row label="Template file"><span className="mono text-[12px]">samples/github-action-kt-drift.yml</span></Row>
              <Row label="Repo variable"><span className="mono text-[12px]">KT_API_URL = {(health?.base_url || window.location.origin).replace(/\/$/, "")}</span></Row>
              <Row label="Repo secret"><span className="mono text-[12px]">KT_PROJECT_ID = {id}</span></Row>
            </dl>
          </div>
        </section>

        <div className="rule" />

        <section>
          <div className="eyebrow mb-4">Integrations</div>
          <dl className="divide-y divide-mist">
            <Row label="Slack webhook">
              <div>
                <div className="text-graphite text-[13px]">Posts a summary when gap analysis runs or source drift is detected.</div>
                <div className="mono text-[11.5px] text-stone mt-2">Set <code className="code-inline">SLACK_WEBHOOK_URL</code> in <code className="code-inline">backend/.env</code> to enable.</div>
              </div>
            </Row>
            <Row label="GitHub webhook">
              <div>
                <div className="text-graphite text-[13px]">Receives push events, re-ingests changed files, auto-flags affected memory as conflicting.</div>
                <div className="mono text-[11.5px] text-stone mt-2">Endpoint: <code className="code-inline">POST /api/webhooks/github/{id}</code></div>
                <div className="mono text-[11.5px] text-stone mt-1">Set <code className="code-inline">GITHUB_WEBHOOK_SECRET</code> in <code className="code-inline">backend/.env</code> to verify signatures.</div>
              </div>
            </Row>
            <Row label="PR comment">
              <div>
                <div className="text-graphite text-[13px]">A GitHub Action drops a knowledge-drift comment on every PR naming affected memory and findings.</div>
                <div className="mono text-[11.5px] text-stone mt-2">Template: <code className="code-inline">samples/github-action-kt-drift.yml</code></div>
              </div>
            </Row>
          </dl>
        </section>

        <div className="rule" />

        <section>
          <div className="eyebrow mb-3" style={{ color: "var(--color-rust, #8A4B2A)" }}>Danger zone</div>
          <p className="text-stone text-[13px] max-w-xl leading-relaxed">
            Deleting the project removes all its sources, chunks, findings, memory, and chat history. This cannot be undone.
          </p>
          {err && <div className="text-rust text-[12px] mt-3">{err}</div>}
          <div className="mt-5 flex gap-2">
            {confirming ? (
              <>
                <button className="btn btn-ghost" onClick={() => setConfirming(false)}>Cancel</button>
                <button className="btn" style={{ background: "#8A4B2A", color: "#FAF9F6", borderColor: "#8A4B2A" }} onClick={destroy}>Confirm delete</button>
              </>
            ) : (
              <button className="btn btn-ghost" onClick={() => setConfirming(true)}>Delete project…</button>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[180px_1fr] gap-4 py-3 text-[13px]">
      <dt className="text-stone">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}
