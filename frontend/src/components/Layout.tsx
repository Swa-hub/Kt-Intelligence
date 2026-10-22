import { Link, NavLink, Outlet, useLocation, useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "../api";

const APP_NAV = [
  { to: "", label: "Overview" },
  { to: "attention", label: "Needs Attention" },
  { to: "ingest", label: "Sources" },
  { to: "map", label: "Knowledge Map" },
  { to: "gaps", label: "Gap Analysis" },
  { to: "tutor", label: "AI Tutor" },
  { to: "memory", label: "Project Memory" },
  { to: "settings", label: "Settings" },
];

export default function Layout() {
  const params = useParams();
  const loc = useLocation();
  const projectId = params.projectId;
  const [health, setHealth] = useState<{ llm_configured: boolean; base_url: string; model: string } | null>(null);
  const [projectName, setProjectName] = useState<string>("");

  useEffect(() => { api.health().then(setHealth).catch(() => {}); }, []);
  useEffect(() => {
    if (!projectId) { setProjectName(""); return; }
    api.getProject(Number(projectId)).then((p) => setProjectName(p.name)).catch(() => {});
  }, [projectId]);

  const isLanding = !projectId;

  if (isLanding) {
    return (
      <div className="min-h-screen flex flex-col">
        <TopNav />
        {health && !health.llm_configured && <DemoBanner />}
        <main className="flex-1"><Outlet /></main>
        <SiteFooter />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex">
      <aside className="w-[232px] shrink-0 border-r border-mist bg-paper flex flex-col sticky top-0 h-screen">
        <Link to="/" className="px-7 pt-8 pb-6 block">
          <div className="serif text-[22px] text-ink leading-none tracking-tightest">KT Intelligence</div>
          <div className="eyebrow mt-2 text-stone">Working knowledge</div>
        </Link>
        {projectName && (
          <div className="px-7 pb-5">
            <div className="eyebrow text-stone">Project</div>
            <div className="serif text-[17px] text-ink mt-1 leading-snug truncate" title={projectName}>{projectName}</div>
          </div>
        )}
        <div className="rule mx-7" />
        <nav className="flex-1 py-4 flex flex-col">
          {APP_NAV.map((n) => (
            <NavLink
              key={n.to}
              end={n.to === ""}
              to={`/projects/${projectId}/${n.to}`}
              className={({ isActive }) =>
                `nav-link ${isActive ? "" : ""}`
              }
            >
              <span className="pl-4">{n.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="rule mx-7" />
        <div className="px-7 py-5">
          <div className="eyebrow text-stone">Intelligence</div>
          <div className="flex items-center gap-2 mt-1 text-[12px] text-graphite">
            <span className={`inline-block w-1.5 h-1.5 rounded-full ${health?.llm_configured ? "bg-forest pulse-soft" : "bg-stone"}`} />
            {health?.llm_configured ? "Model connected" : "Demo mode"}
          </div>
          {health && (
            <div className="mono mt-2 text-[10.5px] text-stone truncate" title={health.model}>
              {health.model}
            </div>
          )}
        </div>
      </aside>
      <main className="flex-1 min-w-0">
        {health && !health.llm_configured && <DemoBanner />}
        <Outlet />
      </main>
    </div>
  );
}

export function PageHeader({ eyebrow, title, subtitle, actions }: { eyebrow?: string; title: string; subtitle?: string; actions?: React.ReactNode }) {
  return (
    <header className="px-10 lg:px-14 pt-14 pb-10 border-b border-mist">
      <div className="max-w-5xl flex items-end justify-between gap-6 flex-wrap">
        <div>
          {eyebrow && <div className="eyebrow mb-4">{eyebrow}</div>}
          <h1 className="display-m text-ink">{title}</h1>
          {subtitle && <p className="mt-3 text-stone max-w-xl leading-relaxed">{subtitle}</p>}
        </div>
        {actions && <div className="flex gap-2 flex-wrap">{actions}</div>}
      </div>
    </header>
  );
}

function TopNav() {
  return (
    <header className="border-b border-mist">
      <div className="max-w-7xl mx-auto px-8 lg:px-12 h-16 flex items-center justify-between">
        <Link to="/" className="serif text-[20px] text-ink tracking-tightest">
          KT <span className="italic-serif">Intelligence</span>
        </Link>
        <nav className="hidden md:flex items-center gap-8 text-[13px] text-graphite">
          <a href="#capabilities" className="hover:text-ink transition-colors">Product</a>
          <a href="#capabilities" className="hover:text-ink transition-colors">Capabilities</a>
          <a href="#how" className="hover:text-ink transition-colors">How it works</a>
          <a href="/#projects" className="hover:text-ink transition-colors">Sign in</a>
        </nav>
        <a href="#start" className="btn btn-primary">Explore Intelligence</a>
      </div>
    </header>
  );
}

function SiteFooter() {
  return (
    <footer className="border-t border-mist mt-24">
      <div className="max-w-7xl mx-auto px-8 lg:px-12 py-10 grid md:grid-cols-4 gap-8 text-[13px] text-graphite">
        <div>
          <div className="serif text-[18px] text-ink">KT Intelligence</div>
          <div className="eyebrow text-stone mt-3">Engineering knowledge, reimagined</div>
        </div>
        <div>
          <div className="eyebrow mb-3">Product</div>
          <ul className="space-y-1">
            <li><a href="#capabilities" className="hover:text-ink">Capabilities</a></li>
            <li><a href="#how" className="hover:text-ink">How it works</a></li>
            <li><a href="#start" className="hover:text-ink">Workspace</a></li>
          </ul>
        </div>
        <div>
          <div className="eyebrow mb-3">Documentation</div>
          <ul className="space-y-1">
            <li><span className="text-stone">README (local)</span></li>
            <li><span className="text-stone">Handover export</span></li>
          </ul>
        </div>
        <div>
          <div className="eyebrow mb-3">Project</div>
          <ul className="space-y-1">
            <li><span className="text-stone">MIT license</span></li>
            <li><span className="text-stone">Nebius · NVIDIA · Groq</span></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-mist">
        <div className="max-w-7xl mx-auto px-8 lg:px-12 py-5 text-[11px] text-stone flex items-center justify-between">
          <div>© {new Date().getFullYear()} KT Intelligence. Built for the Nebius × NVIDIA Global AI Hackathon.</div>
          <div className="mono">v3.0</div>
        </div>
      </div>
    </footer>
  );
}

function DemoBanner() {
  return (
    <div className="bg-bone border-b border-mist">
      <div className="max-w-7xl mx-auto px-8 lg:px-12 py-2 text-[12px] text-graphite flex items-center gap-3">
        <span className="eyebrow text-stone">Demo mode</span>
        <span>LLM key not set — AI responses are illustrative sample data. Add <span className="code-inline">LLM_API_KEY</span> to <span className="code-inline">backend/.env</span> and restart.</span>
      </div>
    </div>
  );
}
