import { useState } from "react";
import { login, HttpError } from "../api";
import RobotAvatar from "./RobotAvatar";

type Props = {
  onAuthenticated: () => void;
};

export default function LoginGate({ onAuthenticated }: Props) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!password) return;
    setPending(true);
    setError(null);
    try {
      await login(password);
      onAuthenticated();
    } catch (err) {
      if (err instanceof HttpError && err.status === 401) {
        setError("Invalid password.");
      } else if (err instanceof HttpError) {
        setError(err.detail ?? `Error ${err.status}`);
      } else {
        setError("Network error.");
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="grid h-full place-items-center px-4">
      <form onSubmit={submit} className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-3">
          <RobotAvatar size={48} />
          <div>
            <h1 className="text-xl font-semibold text-neutral-900">AstroBot</h1>
            <p className="text-xs text-neutral-500">Demo password required.</p>
          </div>
        </div>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="password"
          disabled={pending}
          autoFocus
          className="block w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 placeholder:text-neutral-400 focus:border-neutral-500 focus:outline-none disabled:opacity-50"
        />
        {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={pending || !password}
          className="mt-3 w-full rounded-md bg-neutral-900 px-3 py-2 text-sm text-white transition hover:bg-neutral-700 disabled:cursor-not-allowed disabled:bg-neutral-300"
        >
          {pending ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
