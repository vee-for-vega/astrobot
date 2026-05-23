import { useState } from "react";
import Chat from "./components/Chat";
import LoginGate from "./components/LoginGate";
import { isAuthenticated } from "./api";

export default function App() {
  const [authed, setAuthed] = useState(isAuthenticated());
  return authed ? <Chat onUnauthorized={() => setAuthed(false)} /> : <LoginGate onAuthenticated={() => setAuthed(true)} />;
}
