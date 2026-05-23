import RobotAvatar from "./RobotAvatar";

export default function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-3">
      <RobotAvatar size={32} className="shrink-0" />
      <div className="flex gap-1">
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-neutral-400 [animation-delay:-0.3s]" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-neutral-400 [animation-delay:-0.15s]" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-neutral-400" />
      </div>
    </div>
  );
}
