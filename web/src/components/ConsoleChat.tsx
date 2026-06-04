import { useEffect, useRef, useState } from "react";
import type { ChatTurn, View } from "../types";
import { chat, HttpError } from "../api";

// Suggestion prompts shown for the current view. They feed the normal chat
// pipeline (corpus -> RAG -> Claude), so answers auto-stage for review.
function chipsFor(view: View): string[] {
  if (view.level === "galaxy") {
    return [
      "What does this view of the Milky Way show?",
      "Where is the Sun located in the galaxy?",
      "How large is the Milky Way?",
    ];
  }
  if (view.level === "system") {
    return [
      "What is the order of the planets from the Sun?",
      "Which planet is the largest?",
      "Why are the orbits spaced the way they are?",
    ];
  }
  return [
    `Is ${view.planet} habitable, and why or why not?`,
    `What is ${view.planet}'s atmosphere like?`,
    `How has ${view.planet} been explored?`,
    `Tell me a notable fact about ${view.planet}.`,
  ];
}

type Props = {
  view: View;
};

export default function ConsoleChat({ view }: Props) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  // Typewriter state for narration so the bot visibly "talks" before unlocking.
  const [typing, setTyping] = useState<{ text: string; shown: number } | null>(null);
  const typingMetaRef = useRef<{ question: string; tier?: 1 | 2 | 3 }>({ question: "" });
  const lastKeyRef = useRef<string>("galaxy");

  const logRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const locked = pending || typing !== null;

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, pending, typing]);

  function mapError(err: unknown): string {
    if (err instanceof HttpError && err.status === 429) {
      return `RATE LIMIT // RETRY IN ~${err.retryAfter ?? "?"}S`;
    }
    if (err instanceof HttpError && err.status === 503) {
      return (err.detail ?? "DAILY BUDGET EXHAUSTED").toUpperCase();
    }
    if (err instanceof HttpError) {
      return (err.detail ?? `ERR ${err.status}`).toUpperCase();
    }
    return "NETWORK ERR";
  }

  // Advance the typewriter; commit the finished line as an assistant turn.
  useEffect(() => {
    if (!typing) return;
    if (typing.shown >= typing.text.length) {
      const meta = typingMetaRef.current;
      const finished = typing.text;
      setTurns((prev) => [
        ...prev,
        { role: "assistant", content: finished, question: meta.question, tier: meta.tier },
      ]);
      setTyping(null);
      return;
    }
    const id = setTimeout(() => {
      setTyping((cur) =>
        cur ? { ...cur, shown: Math.min(cur.text.length, cur.shown + 2) } : cur,
      );
    }, 16);
    return () => clearTimeout(id);
  }, [typing]);

  // Bot narration triggered by entering a view (system / planet).
  async function narrate(question: string, prefix: string) {
    setError(null);
    setPending(true);
    try {
      const res = await chat(question, turns);
      setPending(false);
      typingMetaRef.current = { question, tier: res.tier };
      setTyping({ text: prefix + res.answer, shown: 0 });
    } catch (err) {
      setPending(false);
      setError(mapError(err));
    }
  }

  // Fire narration on view transitions. Skipped on the galaxy level, on repeat
  // entries of the same view, and while the user is mid-exchange.
  useEffect(() => {
    const key = view.level === "planet" ? `planet:${view.planet}` : view.level;
    if (key === lastKeyRef.current) return;
    lastKeyRef.current = key;

    if (view.level === "galaxy") return;
    if (pending || typing) return;

    if (view.level === "system") {
      narrate("Give me a brief overview of our solar system.", "Entering the solar system view. ");
    } else {
      narrate(`Describe the orbit of ${view.planet}.`, `Entering ${view.planet}. `);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view]);

  async function send(text: string) {
    const q = text.trim();
    if (!q || locked) return;
    setError(null);
    setInput("");
    const next: ChatTurn[] = [...turns, { role: "user", content: q }];
    setTurns(next);
    setPending(true);
    try {
      const res = await chat(q, turns);
      setTurns([
        ...next,
        {
          role: "assistant",
          content: res.answer,
          trajectory: res.trajectory,
          tier: res.tier,
          question: q,
        },
      ]);
    } catch (err) {
      setError(mapError(err));
    } finally {
      setPending(false);
    }
  }

  function handleKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  // Planet chips are contextual (always shown); galaxy/system chips act as
  // landing suggestions, shown only before the conversation starts.
  const showChips = !locked && (view.level === "planet" || turns.length === 0);

  return (
    <div className="console-panel pointer-events-auto fixed top-6 right-6 bottom-6 z-10 flex w-[360px] flex-col">
      <div className="console-scanlines" />

      <div className="console-header">
        <div className="console-header-title">ASTROBOT // MU-TH-R TERMINAL</div>
        <div className="console-header-sub">
          <span className="console-led" /> SYSTEM ONLINE
        </div>
      </div>

      <div ref={logRef} className="console-log flex-1 overflow-y-auto px-3 py-3">
        {turns.length === 0 && !typing && !pending && (
          <div className="console-dim">
            <div>&gt; AWAITING INPUT.</div>
            <div className="mt-1.5">&gt; QUERY THE GALACTIC ARCHIVE.</div>
          </div>
        )}
        {turns.map((t, i) =>
          t.role === "user" ? (
            <div key={i} className="console-line">
              <span className="console-dim">&gt; USR:</span> {t.content}
            </div>
          ) : (
            <div key={i} className="console-line">
              <span className="console-dim">&gt; SYS:</span>{" "}
              <span className="console-resp whitespace-pre-wrap">{t.content}</span>
            </div>
          ),
        )}
        {typing && (
          <div className="console-line">
            <span className="console-dim">&gt; SYS:</span>{" "}
            <span className="console-resp whitespace-pre-wrap">
              {typing.text.slice(0, typing.shown)}
            </span>
            <span className="console-blink">█</span>
          </div>
        )}
        {pending && (
          <div className="console-line">
            <span className="console-dim">&gt; SYS:</span> <span className="console-blink">█</span>
          </div>
        )}
        {error && <div className="console-line console-err">&gt; ERR: {error}</div>}
      </div>

      {showChips && (
        <div className="flex flex-wrap gap-1.5 px-3 pb-2">
          {chipsFor(view).map((chip) => (
            <button key={chip} type="button" onClick={() => send(chip)} className="console-chip">
              {chip}
            </button>
          ))}
        </div>
      )}

      <div className="console-input-row">
        <span className="console-prompt">&gt;</span>
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          rows={1}
          placeholder={pending ? "PROCESSING..." : typing ? "..." : "TYPE QUESTION..."}
          disabled={locked}
          className="console-input"
        />
      </div>
    </div>
  );
}
