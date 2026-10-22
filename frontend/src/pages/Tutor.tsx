import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api, ChatAnswer, ChatMessage, LearningProgress, QuizQuestion } from "../api";
import { PageHeader } from "../components/Layout";

const LEVELS = ["beginner", "intermediate", "advanced"];
const SUGGESTIONS = [
  "Explain this project as if I joined today.",
  "Which endpoints are protected?",
  "What happens on admin cancel?",
  "What did the KT session fail to explain?",
];

export default function Tutor() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const [mode, setMode] = useState<"chat" | "quiz">("chat");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [level, setLevel] = useState("intermediate");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [speakingId, setSpeakingId] = useState<number | null>(null);
  const [progress, setProgress] = useState<LearningProgress | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { api.chatHistory(id).then(setMessages).catch(() => {}); }, [id]);
  useEffect(() => { api.learning(id).then(setProgress).catch(() => {}); }, [id, messages.length]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  async function ask(q?: string) {
    const question = (q ?? input).trim();
    if (!question) return;
    setBusy(true); setErr(""); setInput("");
    setMessages((m) => [...m, { id: Date.now(), role: "user", content: question, citations: null, created_at: new Date().toISOString() }]);
    try {
      await api.chat(id, question, level);
      setMessages(await api.chatHistory(id));
    } catch (e: any) { setErr(e.message || String(e)); }
    finally { setBusy(false); }
  }

  function speak(m: ChatMessage) {
    if (!("speechSynthesis" in window)) { setErr("Browser speech synthesis is not available."); return; }
    speechSynthesis.cancel();
    if (speakingId === m.id) { setSpeakingId(null); return; }
    const u = new SpeechSynthesisUtterance(m.content.replace(/\[\d+\]/g, "").replace("⚑", ""));
    u.rate = 1;
    u.onend = () => setSpeakingId(null);
    setSpeakingId(m.id);
    speechSynthesis.speak(u);
  }

  return (
    <div className="anim-fade flex flex-col h-screen">
      <PageHeader
        eyebrow="AI tutor"
        title="A quiet, grounded tutor."
        subtitle="Every answer cites evidence from your uploaded sources. Admits when it doesn't know."
        actions={
          <>
            <div className="inline-flex border border-mist rounded-md overflow-hidden">
              <button className={`px-4 py-1.5 text-[12.5px] ${mode==='chat' ? 'bg-ink text-paper' : 'text-graphite hover:bg-ivory'}`} onClick={() => setMode('chat')}>Chat</button>
              <button className={`px-4 py-1.5 text-[12.5px] ${mode==='quiz' ? 'bg-ink text-paper' : 'text-graphite hover:bg-ivory'}`} onClick={() => setMode('quiz')}>Quiz</button>
            </div>
            <select className="input py-1.5 max-w-[160px]" value={level} onChange={(e) => setLevel(e.target.value)}>
              {LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
          </>
        }
      />

      {mode === "quiz" ? <QuizPanel projectId={id} /> : (
      <>
      <div className="flex-1 overflow-y-auto px-10 lg:px-14 py-10 max-w-4xl w-full mx-auto">
        {progress && progress.questions_asked > 0 && (
          <div className="mb-10 pb-6 border-b border-mist flex gap-8 items-end flex-wrap text-[12px]">
            <div>
              <div className="eyebrow">Questions asked</div>
              <div className="serif text-[26px] text-ink leading-none mt-1 tabular-nums">{progress.questions_asked}</div>
            </div>
            {progress.files_covered.length > 0 && (
              <div className="min-w-[220px]">
                <div className="eyebrow mb-2">Files covered</div>
                <div className="flex flex-wrap gap-2">
                  {progress.files_covered.slice(0, 6).map((f) => (
                    <span key={f.filename} className="pill pill-neutral">
                      <span className="mono">{f.filename}</span>
                      <span className="text-stone">· {f.times_cited}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}
            {progress.quiz_by_topic.length > 0 && (
              <div className="min-w-[220px]">
                <div className="eyebrow mb-2">Quiz accuracy</div>
                <ul className="space-y-1 text-[12px]">
                  {progress.quiz_by_topic.slice(0, 4).map((q) => (
                    <li key={q.topic} className="flex items-center gap-2">
                      <span className="text-ink">{q.topic}</span>
                      <span className={`mono ${q.accuracy >= 0.7 ? "text-forest" : "text-ochre"}`}>
                        {q.correct}/{q.attempts}
                      </span>
                    </li>
                  ))}
                </ul>
                {progress.weak_topics.length > 0 && (
                  <div className="mt-2 italic-serif text-[13px] text-ochre">
                    Revisit: {progress.weak_topics.slice(0, 3).join(", ")}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
        {messages.length === 0 && (
          <div>
            <div className="eyebrow mb-4">Try asking</div>
            <ul className="divide-y divide-mist max-w-2xl">
              {SUGGESTIONS.map((s) => (
                <li key={s}>
                  <button className="w-full text-left py-4 serif text-[20px] text-ink leading-snug hover:text-graphite transition-colors flex items-center justify-between gap-4 group" onClick={() => ask(s)}>
                    <span>"{s}"</span>
                    <span className="text-stone group-hover:text-ink transition-colors">→</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        <div className="space-y-10">
          {messages.map((m) => <Message key={m.id} m={m} speakingId={speakingId} onSpeak={speak} />)}
          {err && <div className="text-rust text-[13px]">{err}</div>}
          <div ref={bottomRef} />
        </div>
      </div>
      <div className="border-t border-mist bg-paper">
        <div className="max-w-4xl mx-auto px-10 lg:px-14 py-5 flex gap-3">
          <input
            className="input flex-1"
            placeholder="Ask about this project…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !busy && ask()}
          />
          <button className="btn btn-primary" disabled={busy || !input.trim()} onClick={() => ask()}>
            {busy ? "Thinking…" : "Ask"}
          </button>
        </div>
      </div>
      </>
      )}
    </div>
  );
}

function Message({ m, speakingId, onSpeak }: { m: ChatMessage; speakingId: number | null; onSpeak: (m: ChatMessage) => void }) {
  if (m.role === "user") {
    return (
      <div className="anim-rise">
        <div className="eyebrow mb-2">You</div>
        <div className="serif italic-serif text-[20px] text-ink leading-snug">"{m.content}"</div>
      </div>
    );
  }
  return (
    <div className="anim-rise">
      <div className="eyebrow mb-2 flex items-center gap-3">
        <span>Tutor</span>
        <button className="btn-link text-[11px]" onClick={() => onSpeak(m)}>
          {speakingId === m.id ? "Stop" : "Speak"}
        </button>
      </div>
      <div className="text-ink text-[15px] leading-[1.7] whitespace-pre-wrap">{m.content}</div>
      {m.citations && m.citations.length > 0 && (
        <div className="mt-6">
          <div className="eyebrow mb-3">Evidence</div>
          <ol className="divide-y divide-mist">
            {m.citations.map((c, i) => (
              <CitationItem key={i} citation={c} index={i + 1} />
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

function CitationItem({ citation, index }: { citation: ChatAnswer["citations"][number]; index: number }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  async function toggle() {
    if (open) { setOpen(false); return; }
    setOpen(true);
    if (text || loading || !citation.chunk_id) return;
    setLoading(true);
    try { const r = await api.getChunk(citation.chunk_id); setText(r.text); }
    catch (e: any) { setErr(e.message || String(e)); }
    finally { setLoading(false); }
  }

  return (
    <li className="py-3">
      <button className="w-full text-left flex items-center justify-between gap-4 group" onClick={toggle}>
        <span className="flex items-baseline gap-3">
          <span className="section-number text-[14px] min-w-[24px]">{String(index).padStart(2, "0")}</span>
          <span className="mono text-[12px] text-ink">{citation.filename}<span className="text-stone">:{citation.start_line}–{citation.end_line}</span></span>
          <span className="eyebrow text-stone">{citation.kind}</span>
        </span>
        <span className="text-stone group-hover:text-ink transition-colors text-[12px]">{open ? "hide" : "view"}</span>
      </button>
      {open && (
        <div className="mt-3 pl-[36px] anim-fade">
          {loading && <div className="skel h-16" />}
          {err && <div className="text-rust text-[12px]">{err}</div>}
          {text && <pre className="code max-h-72 overflow-y-auto">{text}</pre>}
        </div>
      )}
    </li>
  );
}

const QUIZ_PLACEHOLDER = "Topic (e.g. authentication, order creation)…";

function QuizPanel({ projectId }: { projectId: number }) {
  const [topic, setTopic] = useState("authentication");
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [picked, setPicked] = useState<Record<number, number>>({});
  const [revealed, setRevealed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [note, setNote] = useState("");

  async function start() {
    if (!topic.trim()) return;
    setBusy(true); setErr(""); setNote(""); setRevealed(false); setPicked({});
    try {
      const r = await api.quiz(projectId, topic.trim(), 3);
      setQuestions(r.questions || []);
      if (r.note) setNote(r.note);
    } catch (e: any) { setErr(e.message || String(e)); }
    finally { setBusy(false); }
  }
  const score = revealed ? questions.filter((q, i) => picked[i] === q.correct_index).length : 0;

  return (
    <div className="flex-1 overflow-y-auto px-10 lg:px-14 py-10 max-w-4xl w-full mx-auto">
      <div className="flex gap-3 items-end flex-wrap">
        <div className="flex-1 min-w-[280px]">
          <div className="eyebrow mb-2">Topic</div>
          <input className="input" placeholder={QUIZ_PLACEHOLDER} value={topic} onChange={(e) => setTopic(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && !busy && start()} />
        </div>
        <button className="btn btn-primary" disabled={busy || !topic.trim()} onClick={start}>{busy ? "Generating…" : "Start quiz"}</button>
      </div>
      {note && <div className="mt-3 text-[12px] text-stone">{note}</div>}
      {err && <div className="mt-3 text-rust text-[13px]">{err}</div>}

      {questions.length > 0 && (
        <div className="mt-10 space-y-10">
          {questions.map((q, i) => (
            <div key={i} className="anim-rise">
              <div className="eyebrow mb-3">Question {String(i + 1).padStart(2, "0")}</div>
              <h3 className="serif text-[22px] text-ink leading-snug">{q.question}</h3>
              <ul className="mt-5 space-y-2">
                {q.options.map((opt, j) => {
                  const isPicked = picked[i] === j;
                  const isCorrect = revealed && j === q.correct_index;
                  const isWrong = revealed && isPicked && j !== q.correct_index;
                  const base = "w-full text-left px-4 py-3 border rounded transition-colors text-[13.5px]";
                  const cls = isCorrect ? "border-forest bg-forestSoft text-forest" :
                              isWrong   ? "border-rust bg-rustSoft text-rust" :
                              isPicked  ? "border-ink bg-ivory text-ink" :
                                          "border-mist text-graphite hover:bg-ivory hover:border-stone";
                  return (
                    <li key={j}>
                      <button className={`${base} ${cls}`} disabled={revealed} onClick={() => setPicked((p) => ({ ...p, [i]: j }))}>
                        {opt}
                      </button>
                    </li>
                  );
                })}
              </ul>
              {revealed && (
                <div className="mt-4 text-stone text-[13px]">
                  <div><span className="eyebrow mr-2">Explanation</span>{q.explanation}</div>
                  {q.evidence_refs && q.evidence_refs.length > 0 && (
                    <div className="mono text-[11px] mt-1">{q.evidence_refs.map((r, k) => <span key={k} className="mr-3">{r.filename}:{r.start_line}–{r.end_line}</span>)}</div>
                  )}
                </div>
              )}
            </div>
          ))}
          <div className="flex items-center justify-between gap-4 pt-4 border-t border-mist">
            {revealed ? (
              <div className="text-[14px]">Score · <span className="serif text-[20px] text-ink">{score}</span> / {questions.length}</div>
            ) : <div className="text-stone text-[12px]">Answer each question, then reveal.</div>}
            <div className="flex gap-2">
              <button className="btn btn-ghost" onClick={() => { setQuestions([]); setPicked({}); setRevealed(false); }}>Reset</button>
              <button className="btn btn-primary" disabled={revealed || Object.keys(picked).length !== questions.length} onClick={async () => {
                setRevealed(true);
                for (let i = 0; i < questions.length; i++) {
                  const q = questions[i];
                  try {
                    await api.recordQuizAttempt(projectId, topic.trim() || "quiz", q.question, picked[i] === q.correct_index);
                  } catch {}
                }
              }}>Reveal answers</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
