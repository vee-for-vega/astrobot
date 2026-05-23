import type { ChatTurn } from "../types";
import OrbitCard from "./OrbitCard";
import RobotAvatar from "./RobotAvatar";

type Props = {
  turn: ChatTurn;
};

export default function Message({ turn }: Props) {
  if (turn.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-neutral-900 px-4 py-2 text-sm text-white">
          {turn.content}
        </div>
      </div>
    );
  }

  // Tier 2/3 answers are Claude-generated. They're auto-submitted to the
  // pending corpus for admin review — until an admin approves them, they
  // are NOT in the verified knowledge base, so we surface that to the user.
  const unverified = !turn.trajectory && (turn.tier === 2 || turn.tier === 3);

  return (
    <div className="flex gap-3">
      <RobotAvatar size={32} className="mt-1 shrink-0" />
      <div className="min-w-0 flex-1">
        {turn.content && (
          <div className="whitespace-pre-wrap text-sm text-neutral-900">{turn.content}</div>
        )}
        {turn.trajectory && <OrbitCard trajectory={turn.trajectory} />}
        {unverified && (
          <p className="mt-2 text-[11px] italic text-neutral-500">
            Generated answer — not yet in the verified corpus. Queued for admin review.
          </p>
        )}
      </div>
    </div>
  );
}
