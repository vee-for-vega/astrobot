import { useEffect, useRef, useState } from "react";
import type { ChatTurn } from "../types";
import { chat, HttpError } from "../api";

export default function ConsoleChat() {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const logRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, pending]);

  async function send(text: string) {
    const q = text.trim();
    if (!q || pending) return;
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
          tier: res.tier as 1 | 2 | 3,
          question: q,
        },
      ]);
    } catch (err) {
      if (err instanceof HttpError && err.status === 429) {
        setError(`RATE LIMIT // RETRY IN ~${err.retryAfter ?? "?"}S`);
      } else if (err instanceof HttpError && err.status === 503) {
        setError((err.detail ?? "DAILY BUDGET EXHAUSTED").toUpperCase());
      } else if (err instanceof HttpError) {
        setError((err.detail ?? `ERR ${err.status}`).toUpperCase());
      } else {
        setError("NETWORK ERR");
      }
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
        {turns.length === 0 && (
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
          )
        )}
        {pending && (
          <div className="console-line">
            <span className="console-dim">&gt; SYS:</span> <span className="console-blink">█</span>
          </div>
        )}
        {error && (
          <div className="console-line console-err">
            &gt; ERR: {error}
          </div>
        )}
      </div>

      <div className="console-input-row">
        <span className="console-prompt">&gt;</span>
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          rows={1}
          placeholder={pending ? "PROCESSING..." : "TYPE QUERY..."}
          disabled={pending}
          className="console-input"
        />
      </div>
    </div>
  );
}
