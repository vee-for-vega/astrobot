import { useState } from "react";
import GalaxyView from "./components/GalaxyView";
import OrreryView from "./components/OrreryView";
import ConsoleChat from "./components/ConsoleChat";
import type { View } from "./types";

export default function App() {
  const [view, setView] = useState<View>({ level: "galaxy" });

  return (
    <>
      {view.level === "galaxy" ? (
        <GalaxyView onEnterSystem={() => setView({ level: "system" })} />
      ) : (
        <OrreryView
          view={view}
          onSelectPlanet={(planet) => setView({ level: "planet", planet })}
          onBack={() =>
            setView(view.level === "planet" ? { level: "system" } : { level: "galaxy" })
          }
        />
      )}
      <ConsoleChat view={view} />
    </>
  );
}
