import { useEffect, useRef, useState } from "react";
import type { ChatTurn } from "../types";
import WelcomeHero from "./WelcomeHero";
import PromptInput from "./PromptInput";
import SuggestionChips from "./SuggestionChips";
import Message from "./Message";
import ThinkingIndicator from "./ThinkingIndicator";
import { chat, clearToken, HttpError } from "../api";

const SUGGESTIONS = [
  "Show me the trajectory of Mars",
  "Show me Earth's orbit",
  "Trajectory of Jupiter",
  "Show me Mercury's path",
];

type Props = {
  onUnauthorized: () => void;
};

export default function Chat({ onUnauthorized }: Props) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, pending]);

  async function send(text: string) {
    setError(null);
    const next: ChatTurn[] = [...turns, { role: "user", content: text }];
    setTurns(next);
    setPending(true);
    try {
      const res = await chat(text, turns);
      setTurns([
        ...next,
        {
          role: "assistant",
          content: res.answer,
          trajectory: res.trajectory,
          tier: res.tier as 1 | 2 | 3,
          question: text,
        },
      ]);
    } catch (err) {
      if (err instanceof HttpError && err.status === 401) {
        clearToken();
        onUnauthorized();
        return;
      }
      if (err instanceof HttpError && err.status === 429) {
        setError(`Rate limited. Retry in ~${err.retryAfter ?? "?"}s.`);
      } else if (err instanceof HttpError) {
        setError(err.detail ?? `Error ${err.status}`);
      } else {
        setError("Network error.");
      }
    } finally {
      setPending(false);
    }
  }

  const isEmpty = turns.length === 0;

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col px-4">
      {isEmpty ? (
        <div className="flex flex-1 flex-col justify-center">
          <WelcomeHero />
          <div className="mt-6">
            <PromptInput onSubmit={send} disabled={pending} />
            <SuggestionChips suggestions={SUGGESTIONS} onPick={send} />
          </div>
        </div>
      ) : (
        <>
          <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto py-6">
            {turns.map((turn, i) => (
              <Message key={i} turn={turn} />
            ))}
            {pending && <ThinkingIndicator />}
            {error && <p className="text-xs text-red-600">{error}</p>}
          </div>
          <div className="border-t border-neutral-200 py-4">
            <PromptInput onSubmit={send} disabled={pending} />
          </div>
        </>
      )}
    </div>
  );
}
