import RobotAvatar from "./RobotAvatar";

export default function WelcomeHero() {
  return (
    <div className="flex items-center gap-4">
      <RobotAvatar size={56} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">
          Welcome to AstroBot
        </h1>
        <p className="mt-1 text-sm text-neutral-500">
          Ask me about a planet's trajectory in our solar system.
        </p>
      </div>
    </div>
  );
}
