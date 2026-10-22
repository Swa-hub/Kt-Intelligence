import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, ProjectDetail, Source } from "../api";
import { PageHeader } from "../components/Layout";

export default function KnowledgeMap() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [selected, setSelected] = useState<Source | null>(null);
  useEffect(() => { api.getProject(id).then(setProject).catch(() => {}); }, [id]);

  const groups = project
    ? project.sources.reduce<Record<string, Source[]>>((acc, s) => { (acc[s.kind] = acc[s.kind] || []).push(s); return acc; }, {})
    : {};

  return (
    <div className="anim-fade">
      <PageHeader
        eyebrow="Knowledge map"
        title="The project at a glance."
        subtitle="A clean index of everything ingested, grouped by kind. Select a file to see its details."
      />
      <div className="px-10 lg:px-14 py-10 max-w-6xl">
        {!project ? (
          <p className="italic-serif text-[18px] text-stone">Loading…</p>
        ) : project.sources.length === 0 ? (
          <p className="italic-serif text-[18px] text-stone">Nothing to map yet — upload sources on the Sources page.</p>
        ) : (
          <div className="grid lg:grid-cols-[1.3fr_1fr] gap-12">
            <div className="space-y-10">
              {Object.entries(groups).map(([kind, items]) => (
                <section key={kind}>
                  <div className="flex items-baseline gap-3 mb-3">
                    <h3 className="display-s text-ink capitalize">{kind}</h3>
                    <span className="eyebrow text-stone">{items.length}</span>
                  </div>
                  <ul className="divide-y divide-mist">
                    {items.map((s) => (
                      <li key={s.id}>
                        <button
                          className={`w-full text-left py-3 flex items-center justify-between gap-4 transition-colors ${selected?.id === s.id ? "text-ink" : "text-graphite hover:text-ink"}`}
                          onClick={() => setSelected(s)}
                        >
                          <span className="mono text-[12.5px] truncate">{s.filename}</span>
                          <span className="text-stone text-[11.5px] shrink-0">{Math.round(s.size_bytes / 1024)} KB</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
            </div>

            <aside className="panel panel-ivory p-6 h-fit sticky top-10">
              {selected ? (
                <>
                  <div className="eyebrow">{selected.kind}</div>
                  <h4 className="serif text-[22px] text-ink mt-2 leading-snug break-words">{selected.filename}</h4>
                  <dl className="mt-6 space-y-3 text-[13px]">
                    <div className="grid grid-cols-[100px_1fr] gap-3">
                      <dt className="text-stone">Size</dt><dd className="text-graphite">{Math.round(selected.size_bytes / 1024)} KB</dd>
                    </div>
                    <div className="grid grid-cols-[100px_1fr] gap-3">
                      <dt className="text-stone">Added</dt><dd className="text-graphite">{new Date(selected.created_at).toLocaleString()}</dd>
                    </div>
                  </dl>
                  <div className="rule my-5" />
                  <p className="text-stone text-[12.5px] italic-serif text-[14px] leading-relaxed">
                    A richer graph view — showing which files cite which, and where evidence is attached — is on the roadmap. The MVP deliberately avoids drawing speculative relationships.
                  </p>
                </>
              ) : (
                <>
                  <div className="eyebrow">Details</div>
                  <p className="italic-serif text-[18px] text-stone mt-3">Select a file.</p>
                </>
              )}
            </aside>
          </div>
        )}
      </div>
    </div>
  );
}
